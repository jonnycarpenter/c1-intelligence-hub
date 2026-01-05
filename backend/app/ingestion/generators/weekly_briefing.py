"""
Weekly Executive Briefing Generator
===================================

Generates the "Need to Know" weekly executive briefing for the Pulse page.

Key Features:
- Max 3 dynamic sections (agent chooses groupings and headers)
- "Net New" vs "Continuing to Track" badges for each item
- Logo.dev integration for company mentions  
- Inline citations with numbered references
- Runs weekly on Mondays at 8:30 AM CST (after ingestion completes)

Cadence: Monday 8:30 AM CST (14:30 UTC)
"""

import uuid
import json
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Set
from collections import Counter
from anthropic import AsyncAnthropic
from exa_py import Exa

from app.db.database import get_db
from app.db.vector_store import get_production_vector_store
from app.config.settings import settings
from app.services.logo_service import logo_service, company_name_to_domain
from app.utils.logger import get_logger

logger = get_logger(__name__)


class WeeklyBriefingGenerator:
    """
    Generates dynamic weekly "Need to Know" executive briefings.
    
    The agent analyzes the week's articles and decides:
    - How to group insights into max 3 sections
    - What header best describes each section
    - Which insight is the most important (bolded headline)
    - Which items are "Net New" vs "Continuing to Track"
    """
    
    EXECUTIVE_SYNTHESIZER_PROMPT = """You are the "Executive Synthesizer" (Agent 2) for a composites industry intelligence hub.
Your goal is to produce a high-conviction, strategic "Need to Know" briefing for C1-level executives.

You are provided with:
1. A "Pre-Brief" (Agent 1 Output): This is a raw analysis of the last 14 days of news, containing categories, summaries, companies, and "Signal Types" (evolution, net_new, stalled).
2. Historical Context: Topics and headlines from the last 2 weekly briefings.
3. TOOL AVAILABLE: search_peripheral_intelligence - Use this to fill gaps or validate high-conviction claims.

YOUR TASK: "The Differential"
Analyze the Pre-Brief against the Historical Context to identify:
- "Continuing to Track": Topics from previous weeks that have significant new "evolution" signals.
- "Net New": High-confidence developments that have not appeared in recent history.
- "Conviction Filtering": Filter out transient news or low-confidence signals. Focus only on items with high strategic impact.

TOOL USE GUIDELINES:
You have access to search_peripheral_intelligence(query: str) for finding adjacent intelligence that may have "slipped through the cracks".

Use this tool ONLY when:
1. A high-conviction topic has <70% confidence and needs validation
2. A company/technology is mentioned prominently but lacks strategic context
3. You need to validate a surprising claim from the pre-briefing
4. Adjacent signals could materially enhance the narrative (e.g., regulatory context, competing technologies, supply chain alternatives)

LIMIT: Maximum 3 tool calls per briefing. Be selective and strategic.

Query Format Examples:
- "Boeing 787 composites supply chain alternatives 2025"
- "EU carbon fiber import tariffs regulatory changes"
- "Hydrogen pressure vessel certification requirements updates"

Tool Response: You will receive 5 articles with full citations (title, URL, date, text snippets). Mark these as [Exa:N] in your final briefing.

REQUIREMENTS:

1. CREATE 3-4 STRATEGIC SECTIONS
   - Group the most critical developments into logical strategic themes.
   - Use punchy, executive-level headers (e.g., "The Aerospace Recovery Pivot", "Hydrogen Pressure Vessel Consolidation").

2. FOR EACH SECTION:
   - ONE Bold Headline: The single most important high-conviction development.
   - 2-4 Supporting Insights: Detailed, evidence-backed bullets.
   - Each item must be marked "net_new" or "continuing" based on your differential analysis.
   - Include citations using the article ID or reference provided in the Pre-Brief (use [N] for pre-brief sources, [Exa:N] for peripheral search results).

3. INLINE LOGOS
   - Wrap company names in double brackets: [[Company Name]].

4. OVERALL TREND
   - Provide a 1-sentence "Bottom Line Up Front" (BLUF) for the week.

If you need to use tools, respond with:
{{
    "tool_calls": [
        {{
            "tool": "search_peripheral_intelligence",
            "query": "your strategic search query here",
            "reason": "brief explanation of why this search is needed"
        }}
    ]
}}

Otherwise, respond with the final briefing JSON:
{{
    "briefing_title": "Executive Briefing: Week of {period_end_short}",
    "bluf": "Single sentence high-level summary",
    "sections": [
        {{
            "header": "Strategic Theme Header",
            "headline": {{
                "text": "Critical development headline [[Company]] [1]",
                "status": "net_new" | "continuing",
                "companies_mentioned": ["Company"]
            }},
            "insights": [
                {{
                    "text": "Detailed strategic insight [[Company B]] [2]",
                    "status": "continuing",
                    "companies_mentioned": ["Company B"]
                }}
            ]
        }}
    ],
    "all_companies_mentioned": ["Company A", "Company B"],
    "key_topics_this_week": ["Topic 1", "Topic 2"],
    "overall_trend": "Detailed analysis of the week's strategic shift"
}}

<historical_context>
{historical_context}
</historical_context>

<pre_brief_data>
{pre_brief_data}
</pre_brief_data>

<peripheral_search_results>
{peripheral_results}
</peripheral_search_results>
"""

    def __init__(self, config=None):
        """Initialize the executive synthesizer (Agent 2)."""
        self.config = config or settings
        self.db = get_db()
        self.client = AsyncAnthropic(api_key=self.config.anthropic_api_key)
        # Agent 2 uses the premium Opus model for strategic synthesis
        self.model = "claude-opus-4-5" 
        self._bq_storage = None
        self._vector_store = None
        # Initialize Exa client for peripheral intelligence search
        exa_api_key = getattr(self.config, 'exa_api_key', None)
        self.exa_client = Exa(exa_api_key) if exa_api_key else None
        if not self.exa_client:
            logger.warning("Exa API key not configured - peripheral search disabled")
    
    async def _get_bq_storage(self):
        """Lazy-load BigQuery storage."""
        if self._bq_storage is None:
            try:
                from app.db.gcp_storage import BigQueryDataStorage, gcp_config
                if gcp_config.is_configured:
                    self._bq_storage = BigQueryDataStorage(gcp_config)
                    await self._bq_storage.initialize()
                    logger.info("BigQuery storage initialized for weekly briefing")
            except Exception as e:
                logger.warning(f"Could not initialize BigQuery storage: {e}")
        return self._bq_storage
    
    async def _get_vector_store(self):
        """Get or initialize vector store (BigQuery-backed)."""
        if self._vector_store is None:
            self._vector_store = await get_production_vector_store()
        return self._vector_store
    
    async def _get_historical_context(self, limit: int = 2) -> str:
        """Get context from the last N weekly briefings."""
        try:
            bq_storage = await self._get_bq_storage()
            briefings = []
            if bq_storage:
                briefings = await bq_storage.get_weekly_briefing_history(limit=limit)
            
            if not briefings:
                briefings = await self.db.get_weekly_briefing_history(limit=limit)
            
            if not briefings:
                return "No historical briefings found."
            
            context = []
            for b in briefings:
                date_str = b.get('period_end', 'Unknown')
                topics = ", ".join(b.get("key_topics_this_week", []))
                context.append(f"Briefing Date: {date_str}\nTopics: {topics}")
                
            return "\n\n".join(context)
                
        except Exception as e:
            logger.warning(f"Could not get historical context: {e}")
        
        return "Error retrieving historical context."
    
    async def _get_latest_pre_brief(self) -> Optional[Dict[str, Any]]:
        """Fetch the latest Agent 1 output from BigQuery."""
        try:
            bq_storage = await self._get_bq_storage()
            if bq_storage:
                return await bq_storage.get_latest_pre_briefing()
            return None
        except Exception as e:
            logger.error(f"Error fetching latest pre-brief: {e}")
            return None
    
    async def _get_pre_brief_articles(self, article_ids: List[str]) -> List[Dict[str, Any]]:
        """Get the full article objects for those referenced in the pre-brief."""
        if not article_ids:
            return []
        
        # Batch query for articles
        articles = await self.db.get_articles_by_ids(article_ids)
        return articles
    
    def _build_articles_text(self, articles: List) -> str:
        """Build formatted article text for the prompt."""
        articles_text = []
        for i, a in enumerate(articles, 1):
            source_name = a.source.name if hasattr(a.source, 'name') else 'Unknown'
            date_str = a.published_at.date() if a.published_at else 'Unknown'
            # Use primary_category (the correct attribute name)
            category = a.primary_category.value if hasattr(a.primary_category, 'value') else str(a.primary_category)
            
            articles_text.append(
                f"[{i}] Title: {a.title}\n"
                f"Source: {source_name}\n"
                f"Date: {date_str}\n"
                f"Category: {category}\n"
                f"Summary: {a.summary}"
            )
        
        return "\n\n".join(articles_text)
    
    def _build_source_articles(self, articles: List, article_numbers: List[int]) -> List[Dict[str, Any]]:
        """Build source article metadata for the articles used in a section."""
        source_articles = []
        for num in article_numbers:
            if 1 <= num <= len(articles):
                a = articles[num - 1]  # Convert to 0-indexed
                source_articles.append({
                    "article_number": num,
                    "id": a.id,
                    "title": a.title,
                    "url": a.url,
                    "source_name": a.source.name if hasattr(a.source, 'name') else str(a.source),
                    "published_at": a.published_at.isoformat() if a.published_at else None,
                })
        return source_articles
    
    def _enrich_with_logos(self, companies: List[str]) -> List[Dict[str, Any]]:
        """Add logo URLs for mentioned companies."""
        enriched = []
        for company in companies:
            domain = company_name_to_domain(company)
            logo_url = logo_service.get_logo_url(domain) if domain else None
            enriched.append({
                "name": company,
                "domain": domain,
                "logo_url": logo_url
            })
        return enriched
    
    async def _search_peripheral_intelligence(
        self,
        query: str,
        num_results: int = 5,
        time_range: str = "1month"
    ) -> List[Dict[str, Any]]:
        """
        Use Exa.ai Search + Contents API for peripheral intelligence gathering.
        
        This allows Agent 2 to find adjacent signals or validate claims that may have
        "slipped through the cracks" in the initial corpus.
        
        Args:
            query: Strategic search query (e.g., "Boeing composites supply chain alternatives")
            num_results: Number of articles to retrieve (default: 5)
            time_range: Time filter for results (default: "1month")
            
        Returns:
            List of article dictionaries with full metadata for citations
        """
        if not self.exa_client:
            logger.warning("Exa client not configured - skipping peripheral search")
            return []
        
        try:
            logger.info(f"Agent 2: Peripheral search query: '{query}'")
            
            # Calculate start date (Exa requires ISO 8601)
            start_date = None
            if time_range == "1month":
                start_date = (datetime.utcnow() - timedelta(days=30)).isoformat()
            else:
                start_date = time_range

            # Use search_and_contents for full article data
            results = self.exa_client.search_and_contents(
                query=query,
                num_results=num_results,
                # use_autoprompt=True,  # Removed as it caused ValueError
                start_published_date=start_date,
                text={"max_characters": 1500},  # Get enough context
                highlights={"num_sentences": 3}  # Key excerpts
            )
            
            # Format results for Agent 2 consumption
            peripheral_articles = []
            for idx, result in enumerate(results.results, 1):
                article = {
                    "exa_id": idx,
                    "title": result.title,
                    "url": result.url,
                    "published_date": result.published_date if hasattr(result, 'published_date') else None,
                    "author": result.author if hasattr(result, 'author') else None,
                    "text_snippet": result.text[:500] if hasattr(result, 'text') else "",  # First 500 chars
                    "highlights": result.highlights if hasattr(result, 'highlights') else [],
                    "relevance_score": result.score if hasattr(result, 'score') else None,
                    "source": "exa_peripheral"
                }
                peripheral_articles.append(article)
            
            logger.info(f"Agent 2: Retrieved {len(peripheral_articles)} peripheral articles")
            return peripheral_articles
            
        except Exception as e:
            logger.error(f"Error in peripheral intelligence search: {e}", exc_info=True)
            return []
    
    async def generate(self, pre_brief: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """
        Agent 2: Generate the final high-conviction executive briefing.
        
        Enhanced with peripheral intelligence search capability.
        
        Args:
            pre_brief: Optional pre-brief data (if not provided, fetches latest)
        
        Returns:
            Complete executive briefing record
        """
        logger.info("Agent 2: Starting executive synthesis")
        
        # 1. Ensure we have pre-brief data
        if not pre_brief:
            pre_brief = await self._get_latest_pre_brief()
            
        if not pre_brief:
            logger.error("Agent 2: No pre-brief available for synthesis")
            return None
            
        # 2. Get historical context
        historical_context = await self._get_historical_context(limit=2)
        
        # 3. Get articles for metadata enrichment
        article_ids = pre_brief.get('article_ids', [])
        articles = await self._get_pre_brief_articles(article_ids)
        
        # 4. Peripheral intelligence gathering loop
        peripheral_results = []
        max_iterations = 2  # Prevent infinite loops
        iteration = 0
        
        period_end = pre_brief.get('period_end')
        if isinstance(period_end, str):
            period_end = datetime.fromisoformat(period_end)
        
        data = None
        result_json = None
        
        while iteration < max_iterations:
            iteration += 1
            logger.info(f"Agent 2: Synthesis iteration {iteration}")
            
            # Format peripheral results for prompt
            peripheral_results_text = "No peripheral search conducted yet."
            if peripheral_results:
                formatted_results = []
                for result in peripheral_results:
                    formatted_results.append(
                        f"[Exa:{result['exa_id']}] {result['title']}\n"
                        f"URL: {result['url']}\n"
                        f"Date: {result['published_date']}\n"
                        f"Snippet: {result['text_snippet']}"
                    )
                peripheral_results_text = "\n\n".join(formatted_results)
            
            # 5. Prepare prompt with current context
            prompt = self.EXECUTIVE_SYNTHESIZER_PROMPT.format(
                period_end_short=period_end.strftime("%b %d") if period_end else "Current",
                historical_context=historical_context,
                pre_brief_data=json.dumps(pre_brief.get('data', {}), indent=2),
                peripheral_results=peripheral_results_text
            )
            
            try:
                response = await self.client.messages.create(
                    model=self.model,
                    max_tokens=4000,
                    temperature=0.0,
                    messages=[{"role": "user", "content": prompt}]
                )
                
                result_json = response.content[0].text.strip()
                if "```json" in result_json:
                    result_json = result_json.split("```json")[1].split("```")[0].strip()
                
                data = json.loads(result_json)
                
                # Check if Agent 2 wants to make tool calls
                if "tool_calls" in data and iteration < max_iterations:
                    tool_calls = data["tool_calls"]
                    logger.info(f"Agent 2: Requesting {len(tool_calls)} tool calls")
                    
                    # Limit to 3 tool calls total
                    tool_calls = tool_calls[:3]
                    
                    # Execute tool calls
                    for tool_call in tool_calls:
                        if tool_call.get("tool") == "search_peripheral_intelligence":
                            query = tool_call.get("query")
                            reason = tool_call.get("reason", "No reason provided")
                            logger.info(f"Agent 2: Tool call reason: {reason}")
                            
                            # Execute peripheral search
                            search_results = await self._search_peripheral_intelligence(query)
                            
                            # Assign incremental IDs based on existing results
                            start_id = len(peripheral_results) + 1
                            for idx, result in enumerate(search_results):
                                result['exa_id'] = start_id + idx
                            
                            peripheral_results.extend(search_results)
                    
                    # Continue to next iteration with enriched context
                    continue
                
                # No tool calls or max iterations reached - proceed with final synthesis
                break
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse Agent 2 response: {e}")
                logger.debug(f"Raw response: {result_json[:500] if result_json else 'No response'}")
                return None
            except Exception as e:
                logger.error(f"Error in Agent 2 synthesis iteration: {e}", exc_info=True)
                return None
        
        # Process final briefing data
        if not data or "tool_calls" in data:
            logger.error("Agent 2: Failed to generate final briefing after tool calls")
            return None
        
        try:
            # Process sections and add logos
            processed_sections = []
            for section in data.get("sections", []):
                # Aggregate companies for logo enrichment
                section_companies = set()
                headline = section.get("headline", {})
                section_companies.update(headline.get("companies_mentioned", []))
                for insight in section.get("insights", []):
                    section_companies.update(insight.get("companies_mentioned", []))
                
                processed_sections.append({
                    "header": section.get("header", "Update"),
                    "headline": headline,
                    "insights": section.get("insights", []),
                    "companies_with_logos": self._enrich_with_logos(list(section_companies)),
                })
            
            # Build the complete briefing record
            briefing_record = {
                "id": str(uuid.uuid4()),
                "briefing_type": "weekly_executive",
                "briefing_title": data.get("briefing_title", f"Executive Briefing: Week of {period_end.strftime('%b %d')}"),
                "bluf": data.get("bluf", ""),
                "sections": processed_sections,
                "all_companies_mentioned": self._enrich_with_logos(data.get("all_companies_mentioned", [])),
                "key_topics_this_week": data.get("key_topics_this_week", []),
                "overall_trend": data.get("overall_trend", ""),
                "period_start": pre_brief.get('period_start'),
                "period_end": pre_brief.get('period_end'),
                "generated_at": datetime.utcnow(),
                "model": self.model,
                "article_count": pre_brief.get('article_count', 0),
                "article_ids": article_ids,
                "peripheral_searches_count": len(peripheral_results),
                "peripheral_articles": peripheral_results if peripheral_results else [],
            }
            
            # Save to storage
            await self._save_briefing(briefing_record)
            
            logger.info(f"Agent 2: Synthesis complete. Generated {len(processed_sections)} strategic sections.")
            return briefing_record
            
        except Exception as e:
            logger.error(f"Error in Agent 2 synthesis: {e}", exc_info=True)
            return None
    
    async def _save_briefing(self, briefing: Dict[str, Any]):
        """Save briefing to BigQuery."""
        try:
            bq_storage = await self._get_bq_storage()
            if bq_storage:
                await bq_storage.save_weekly_briefing(briefing)
                logger.info("Saved weekly briefing to BigQuery")
            else:
                logger.warning("BigQuery storage not available - briefing not saved")
        except Exception as e:
            logger.error(f"Failed to save briefing to BigQuery: {e}")


# Convenience function for scheduler
async def generate_weekly_briefing() -> Optional[Dict[str, Any]]:
    """
    Orchestrates the two-agent briefing pipeline:
    1. Run Agent 1 (Pre-Brief Generator) to analyze last 14 days.
    2. Run Agent 2 (Executive Synthesizer) to produce final briefing.
    """
    from app.ingestion.generators.pre_briefing import PreBriefGenerator
    
    # Run Agent 1
    logger.info("Orchestrator: Triggering Agent 1 (Pre-Brief)")
    agent1 = PreBriefGenerator()
    pre_brief = await agent1.generate_pre_brief(days=14)
    
    if not pre_brief:
        logger.error("Orchestrator: Agent 1 failed to produce pre-brief. Aborting.")
        return None
        
    # Run Agent 2
    logger.info("Orchestrator: Triggering Agent 2 (Synthesis)")
    agent2 = WeeklyBriefingGenerator()
    return await agent2.generate(pre_brief=pre_brief)
