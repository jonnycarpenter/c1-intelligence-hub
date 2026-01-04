"""
Ad Hoc Quick Briefing Agent
===========================

Handles user-generated "quick briefing" requests on the Pulse page.

Key Features:
- Fast response using Claude Haiku
- Structured context from current brief + recent digest
- Tool access to search full digest/briefing if needed
- Max 2 follow-ups, then redirect to Deep Research
- Stores briefings in adhoc_briefings BigQuery table

Design Principles:
- Speed over depth (use Haiku, semantic search only)
- Context-aware but lightweight
- Graceful fallback to Deep Research for complex queries
"""

import uuid
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, AsyncIterator
from anthropic import AsyncAnthropic

from app.db.database import get_db
from app.config.settings import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


# =============================================================================
# Structured Context Model
# =============================================================================

class BriefingContext:
    """
    Lightweight structured context passed to the ad hoc agent.
    
    Keeps prompt size manageable while providing relevant context.
    """
    
    def __init__(
        self,
        current_brief_headlines: List[str],
        current_brief_date: str,
        recent_digest_topics: List[str],
        current_brief_id: Optional[str] = None,
        active_filters: List[str] = None,
    ):
        self.current_brief_headlines = current_brief_headlines
        self.current_brief_date = current_brief_date
        self.recent_digest_topics = recent_digest_topics
        self.current_brief_id = current_brief_id
        self.active_filters = active_filters or []
    
    def to_context_string(self) -> str:
        """Format context for inclusion in prompt."""
        headlines = "\n".join(f"  - {h}" for h in self.current_brief_headlines[:5])
        topics = ", ".join(self.recent_digest_topics[:15])
        filters = ", ".join(self.active_filters) if self.active_filters else "None"
        
        return f"""Current Weekly Briefing ({self.current_brief_date}):
{headlines}

Recent Digest Topics (last 7 days):
{topics}

Current UI Filters (Active): {filters}"""
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BriefingContext":
        """Create context from dictionary."""
        return cls(
            current_brief_headlines=data.get("current_brief_headlines", []),
            current_brief_date=data.get("current_brief_date", "Unknown"),
            recent_digest_topics=data.get("recent_digest_topics", []),
            current_brief_id=data.get("current_brief_id"),
            active_filters=data.get("active_filters", []),
        )


# =============================================================================
# Ad Hoc Briefing Agent
# =============================================================================

class AdHocBriefingAgent:
    """
    Agent for generating quick ad hoc briefings based on user questions.
    
    Uses:
    - Claude Haiku for speed
    - Semantic search over articles_embedding only
    - Structured context from current brief + digest
    - Tool to search full content if needed
    """
    
    SYSTEM_PROMPT = """You are an intelligence analyst assistant for C1 Intelligence Hub, a composites industry intelligence platform.

Your role is to provide QUICK, FOCUSED briefings based on user questions about industry news and developments.

CONTEXT AWARENESS:
You have access to the current weekly executive briefing and recent digest topics. The user may be asking follow-up questions about topics they saw there.

TOOLS:
- search_articles: Search the articles database for relevant information
- search_briefing_details: Get more details from the current weekly briefing (use if user references something specific)

RESPONSE GUIDELINES:
1. Be CONCISE - this is a quick briefing, not a research report
2. Always cite sources with [Source: Article Title]
3. If you can't find enough information, say so and suggest Deep Research
4. Focus on actionable intelligence, not general background
5. Use bullet points for clarity

FALLBACK:
If you cannot adequately answer the question with available data, respond with:
"I found limited information on this topic. Here's what I found: [brief summary]. For a comprehensive analysis, I recommend using the Deep Research feature which has access to additional resources."

Remember: Speed and relevance over completeness."""

    ADHOC_BRIEFING_PROMPT = """<user_context>
{context_string}
</user_context>

<user_question>
{question}
</user_question>

Based on the user's question and context, search for relevant articles and provide a focused briefing response.

First, use the search_articles tool to find relevant information. Then synthesize a response.

Respond with a JSON object:
{{
    "answer": "Your briefing response with [Source: Article Title] citations",
    "sources_used": [
        {{"title": "Article Title", "url": "url", "relevance": "why this source is relevant"}}
    ],
    "related_topics": ["topic1", "topic2"],
    "confidence": "high" | "medium" | "low",
    "suggest_deep_research": true | false,
    "deep_research_reason": "Optional: why deep research would help"
}}"""

    def __init__(self, config=None):
        self.config = config or settings
        self.client = AsyncAnthropic(api_key=self.config.anthropic_api_key)
        self.model = "claude-3-5-haiku-20241022"  # Fast model for quick responses
        self.db = get_db()
        self._vector_store = None
        self._bq_storage = None
        
        # Track conversation for follow-up limit
        self.conversation_history: List[Dict[str, str]] = []
        self.follow_up_count = 0
        self.max_follow_ups = 2
    
    async def _get_vector_store(self):
        """Get or initialize vector store."""
        if self._vector_store is None:
            # Use production vector store factory to get correct instance (BQ vs Chroma)
            from app.db.vector_store import get_production_vector_store
            self._vector_store = await get_production_vector_store()
        return self._vector_store
    
    async def _get_bq_storage(self):
        """Lazy-load BigQuery storage."""
        if self._bq_storage is None:
            try:
                from app.db.gcp_storage import BigQueryDataStorage, gcp_config
                if gcp_config.is_configured:
                    self._bq_storage = BigQueryDataStorage(gcp_config)
                    await self._bq_storage.initialize()
            except Exception as e:
                logger.warning(f"Could not initialize BigQuery storage: {e}")
        return self._bq_storage
    
    async def search_articles(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search articles in the vector store.
        
        This is the main tool for the agent - semantic search over embedded articles.
        """
        vector_store = await self._get_vector_store()
        
        if not vector_store.is_available:
            logger.warning("Vector store not available for ad hoc search")
            return []
        
        results = await vector_store.search(query=query, limit=limit)
        
        # Format for agent consumption
        formatted = []
        for r in results:
            metadata = r.get("metadata", {})
            formatted.append({
                "title": metadata.get("title", "Unknown"),
                "url": metadata.get("url", ""),
                "source": metadata.get("source_name", "Unknown"),
                "date": metadata.get("published_at", ""),
                "category": metadata.get("category", ""),
                "summary": r.get("document", "")[:500],  # Truncate for speed
                "relevance_score": r.get("relevance_score", 0),
            })
        
        return formatted
    
    async def search_briefing_details(self, topic: str) -> Dict[str, Any]:
        """
        Get details from the current weekly briefing related to a topic.
        
        Used when user references something specific from the briefing.
        """
        try:
            bq_storage = await self._get_bq_storage()
            if bq_storage:
                briefings = await bq_storage.get_latest_weekly_briefing()
                if briefings:
                    briefing = briefings[0] if isinstance(briefings, list) else briefings
                    # Search through sections for relevant content
                    relevant_sections = []
                    for section in briefing.get("sections", []):
                        header = section.get("header", "").lower()
                        headline_text = section.get("headline", {}).get("text", "").lower()
                        if topic.lower() in header or topic.lower() in headline_text:
                            relevant_sections.append(section)
                    
                    return {
                        "briefing_title": briefing.get("briefing_title", ""),
                        "relevant_sections": relevant_sections,
                        "overall_trend": briefing.get("overall_trend", ""),
                    }
        except Exception as e:
            logger.warning(f"Error searching briefing details: {e}")
        
        return {"relevant_sections": [], "message": "Could not find briefing details"}
    
    def _should_redirect_to_deep_research(self) -> bool:
        """Check if we should redirect user to deep research."""
        return self.follow_up_count >= self.max_follow_ups
    
    async def generate_briefing(
        self,
        question: str,
        context: BriefingContext,
        is_follow_up: bool = False,
    ) -> Dict[str, Any]:
        """
        Generate an ad hoc briefing response.
        
        Args:
            question: User's question
            context: Structured context from current brief/digest
            is_follow_up: Whether this is a follow-up question
        
        Returns:
            Briefing response with answer, sources, and metadata
        """
        # Check follow-up limit
        if is_follow_up:
            self.follow_up_count += 1
        
        if self._should_redirect_to_deep_research():
            return {
                "id": str(uuid.uuid4()),
                "question": question,
                "answer": (
                    "You've asked several follow-up questions, which suggests this topic deserves deeper analysis. "
                    "I recommend using the **Deep Research** feature, which has access to additional resources "
                    "and can provide a comprehensive report with more detailed analysis."
                ),
                "sources_used": [],
                "redirect_to_deep_research": True,
                "deep_research_query": question,
                "generated_at": datetime.utcnow().isoformat(),
            }
        
        # Build search query by incorporating active filters if relevant
        search_query = question
        if context.active_filters:
            # Append filters to search query to boost relevance
            filter_str = " ".join(context.active_filters)
            search_query = f"{question} {filter_str}"
            logger.info(f"Ad hoc search using active filters: {context.active_filters}")

        # Search for relevant articles
        search_results = await self.search_articles(search_query, limit=10)
        
        if not search_results:
            # Fallback search without filters if no results found
            if context.active_filters:
                logger.info("No results found with filters, falling back to original question")
                search_results = await self.search_articles(question, limit=8)
            
            if not search_results:
                return {
                    "id": str(uuid.uuid4()),
                    "question": question,
                    "answer": (
                        "I couldn't find relevant information in the recent articles database. "
                        "For a comprehensive answer, I recommend using the **Deep Research** feature "
                        "which can search additional sources."
                    ),
                    "sources_used": [],
                    "confidence": "low",
                    "suggest_deep_research": True,
                    "generated_at": datetime.utcnow().isoformat(),
                }
        
        # Build prompt with context and search results
        context_string = context.to_context_string()
        
        search_context = "Relevant Articles Found:\n" + "\n".join([
            f"- {r['title']} ({r['source']}, {r['date']})\n  Summary: {r['summary']}"
            for r in search_results[:5]
        ])
        
        full_prompt = f"""{context_string}

{search_context}

User Question: {question}

Based on the above context and search results, provide a focused briefing response.
Be concise and cite sources. If the information is limited, acknowledge it.

Respond with JSON:
{{
    "answer": "Your briefing response with citations",
    "sources_used": [{{"title": "...", "url": "...", "relevance": "..."}}],
    "confidence": "high|medium|low",
    "suggest_deep_research": true|false
}}"""

        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=1500,
                temperature=0,
                system=self.SYSTEM_PROMPT,
                messages=[{"role": "user", "content": full_prompt}]
            )
            
            result_text = response.content[0].text.strip()
            
            # Parse JSON response
            if result_text.startswith("```json"):
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif result_text.startswith("```"):
                result_text = result_text.split("```")[1].split("```")[0].strip()
            
            data = json.loads(result_text)
            
            # Build response record
            briefing_response = {
                "id": str(uuid.uuid4()),
                "question": question,
                "answer": data.get("answer", ""),
                "sources_used": data.get("sources_used", []),
                "confidence": data.get("confidence", "medium"),
                "suggest_deep_research": data.get("suggest_deep_research", False),
                "related_topics": data.get("related_topics", []),
                "context_used": {
                    "brief_date": context.current_brief_date,
                    "headlines_count": len(context.current_brief_headlines),
                    "digest_topics_count": len(context.recent_digest_topics),
                },
                "search_results_count": len(search_results),
                "follow_up_count": self.follow_up_count,
                "generated_at": datetime.utcnow().isoformat(),
                "model": self.model,
            }
            
            # Save to storage
            await self._save_adhoc_briefing(briefing_response)
            
            return briefing_response
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse ad hoc briefing response: {e}")
            # Return raw response as fallback
            return {
                "id": str(uuid.uuid4()),
                "question": question,
                "answer": result_text if 'result_text' in locals() else "Error generating response",
                "sources_used": [{"title": r["title"], "url": r["url"]} for r in search_results[:3]],
                "confidence": "low",
                "generated_at": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            logger.error(f"Error generating ad hoc briefing: {e}", exc_info=True)
            return {
                "id": str(uuid.uuid4()),
                "question": question,
                "answer": f"I encountered an error while generating the briefing. Please try again or use Deep Research for this query.",
                "error": str(e),
                "suggest_deep_research": True,
                "generated_at": datetime.utcnow().isoformat(),
            }
    
    async def _save_adhoc_briefing(self, briefing: Dict[str, Any]):
        """Save ad hoc briefing to storage (BigQuery or SQLite fallback)."""
        try:
            bq_storage = await self._get_bq_storage()
            if bq_storage:
                await bq_storage.save_adhoc_briefing(briefing)
                logger.info(f"Saved ad hoc briefing {briefing['id']} to BigQuery")
            else:
                # SQLite fallback for local development
                db = get_db()
                await db.save_adhoc_briefing(briefing)
                logger.info(f"Saved ad hoc briefing {briefing['id']} to SQLite")
        except Exception as e:
            logger.error(f"Failed to save ad hoc briefing: {e}")
    
    def reset_conversation(self):
        """Reset conversation state for new session."""
        self.conversation_history = []
        self.follow_up_count = 0


# =============================================================================
# Streaming Support (optional)
# =============================================================================

class StreamingAdHocBriefingAgent(AdHocBriefingAgent):
    """
    Streaming version of the ad hoc briefing agent.
    
    Streams response tokens for better UX on the frontend.
    """
    
    async def generate_briefing_stream(
        self,
        question: str,
        context: BriefingContext,
        is_follow_up: bool = False,
    ) -> AsyncIterator[str]:
        """
        Stream an ad hoc briefing response.
        
        Yields chunks of the response as they're generated.
        """
        # Check follow-up limit first
        if is_follow_up:
            self.follow_up_count += 1
        
        if self._should_redirect_to_deep_research():
            yield json.dumps({
                "type": "redirect",
                "message": "For deeper analysis, please use the Deep Research feature.",
                "deep_research_query": question,
            })
            return
        
        # Search for context
        search_results = await self.search_articles(question, limit=8)
        
        if not search_results:
            yield json.dumps({
                "type": "no_results",
                "message": "No relevant articles found. Try Deep Research for more sources.",
            })
            return
        
        # Build context
        context_string = context.to_context_string()
        search_context = "Relevant Articles Found:\n" + "\n".join([
            f"- {r['title']} ({r['source']}): {r['summary'][:200]}"
            for r in search_results[:5]
        ])
        
        full_prompt = f"""{context_string}

{search_context}

User Question: {question}

Provide a focused briefing response. Be concise and cite sources."""

        # Stream response
        async with self.client.messages.stream(
            model=self.model,
            max_tokens=1500,
            temperature=0,
            system=self.SYSTEM_PROMPT,
            messages=[{"role": "user", "content": full_prompt}]
        ) as stream:
            async for text in stream.text_stream:
                yield text


# =============================================================================
# Factory function
# =============================================================================

def get_adhoc_briefing_agent(streaming: bool = False) -> AdHocBriefingAgent:
    """Get an ad hoc briefing agent instance."""
    if streaming:
        return StreamingAdHocBriefingAgent()
    return AdHocBriefingAgent()
