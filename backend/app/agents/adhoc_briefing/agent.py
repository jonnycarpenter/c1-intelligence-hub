"""
Ad Hoc Briefing Agent (Enhanced)
================================

Handles user-generated briefing requests on the Pulse page.

Key Features (v2 - January 2026):
- Thorough responses using Claude Sonnet 4.5
- Access to external tools: Exa news, StockNewsAPI, FMP premium news
- Structured context from current brief + recent digest
- SSE progress events for tool execution
- Max 2 follow-ups, then redirect to Deep Research
- Stores briefings in adhoc_briefings BigQuery table

Design Principles:
- "Wow" intelligence over raw speed
- Rich formatting with sections, bold, citations
- Corpus-first, then external sources
- 120-second timeout for thorough research
"""

import uuid
import json
import time
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, AsyncIterator, TYPE_CHECKING
from anthropic import AsyncAnthropic  # Keep for streaming support

from app.config.settings import settings
from app.utils.resilient_llm import get_resilient_async_client
from app.utils.logger import get_logger
from app.services.memory_service import build_agent_context

if TYPE_CHECKING:
    from .session_manager import BriefingSession

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
        active_category: Optional[str] = None,
        visible_digest_items: Optional[List[Dict[str, str]]] = None,
    ):
        self.current_brief_headlines = current_brief_headlines
        self.current_brief_date = current_brief_date
        self.recent_digest_topics = recent_digest_topics
        self.current_brief_id = current_brief_id
        self.active_filters = active_filters or []
        self.active_category = active_category
        self.visible_digest_items = visible_digest_items or []
    
    def to_context_string(self) -> str:
        """Format context for inclusion in prompt."""
        headlines = "\n".join(f"  - {h}" for h in self.current_brief_headlines[:5])
        topics = ", ".join(self.recent_digest_topics[:15])
        filters = ", ".join(self.active_filters) if self.active_filters else "None"
        
        # Format visible items if available (Discovery tab context)
        visible_items_str = ""
        if self.visible_digest_items:
            items_list = "\n".join([
                f"  - {item.get('title', 'Unknown')} (Source: {item.get('source', 'Unknown')})" 
                for item in self.visible_digest_items[:10]
            ])
            visible_items_str = f"\n\nVisible Feed Items (User is looking at these):\n{items_list}"
            
        # Format active category
        category_str = ""
        if self.active_category:
            category_str = f"\nActive Category/Tab: {self.active_category}"
        
        return f"""Current Weekly Briefing ({self.current_brief_date}):
{headlines}

Recent Digest Topics (last 7 days):
{topics}

Current UI Filters (Active): {filters}{category_str}{visible_items_str}"""
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BriefingContext":
        """Create context from dictionary."""
        return cls(
            current_brief_headlines=data.get("current_brief_headlines", []),
            current_brief_date=data.get("current_brief_date", "Unknown"),
            recent_digest_topics=data.get("recent_digest_topics", []),
            current_brief_id=data.get("current_brief_id"),
            active_filters=data.get("active_filters", []),
            active_category=data.get("active_category"),
            visible_digest_items=data.get("visible_digest_items", []),
        )


# =============================================================================
# Ad Hoc Briefing Agent
# =============================================================================

class AdHocBriefingAgent:
    """
    Agent for generating thorough ad hoc briefings based on user questions.
    
    Uses:
    - Claude Sonnet 4.5 for quality responses
    - Corpus search FIRST (BigQuery vector store)
    - External tools: Exa news, StockNewsAPI, FMP premium news
    - Structured context from current brief + digest
    - Rich markdown formatting with citations
    """
    
    SYSTEM_PROMPT = """You are an intelligence analyst for Composites One (C1), the largest composites distributor in North America.

ABOUT COMPOSITES ONE:
- North America's premier composites materials distributor
- Supplies fiberglass, carbon fiber, resins, core materials, and related products
- Serves fabricators across multiple industries
- Focus on helping sales teams stay informed about market developments

KEY COMPETITORS TO MONITOR:
- Hexcel, Toray, Solvay, Owens Corning, Huntsman, Gurit
- Teijin, SGL Carbon, Mitsubishi Chemical
- Regional distributors and direct-to-fabricator suppliers

PRODUCT CATEGORIES:
- Reinforcements: Carbon fiber, fiberglass, glass fiber, aramid
- Resins: Epoxy, polyester, vinyl ester, phenolic
- Core Materials: Foam, balsa, honeycomb
- Prepregs and molding compounds
- Ancillaries: Gel coats, release agents, tooling materials

END MARKETS C1 SERVES:
- Aerospace: Commercial aircraft, defense, space
- Automotive: EV components, body panels, structural parts
- Marine: Boat hulls, yacht components, naval applications
- Wind Energy: Turbine blades, nacelles
- Infrastructure: Bridges, rebar, civil construction
- Sporting Goods: Golf, cycling, recreational equipment
- Industrial: Tanks, pipes, electrical

Your role is to provide THOROUGH, WELL-SOURCED briefings on industry news, competitor activity, and market developments relevant to C1's business.

CONTEXT AWARENESS:
You have access to the current weekly executive briefing, recent digest topics, and potentially the specific items the user is currently viewing on the Discovery feed. 
If the user asks about "this article" or "the first item", refer to the 'Visible Feed Items' in your context.
The user may be asking follow-up questions about topics they saw there.

DATA SOURCES PROVIDED:
The user's question has ALREADY been searched across multiple sources. The search results are provided to you below in the prompt - you do NOT need to call any tools or functions. Simply synthesize the provided search results into a response. The sources already searched include:
- Internal Corpus: Recent articles from our curated industry intelligence database
- Exa News: Real-time web news search
- StockNews: Financial and market news

If the provided search results are insufficient or empty, acknowledge this limitation and recommend the **Deep Research** feature for more comprehensive analysis. Do NOT attempt to call any tools or output any XML/function syntax.

RESPONSE FORMAT (use this exact structure):

## Overview
[2-3 sentence executive summary with **bold** for key insights]

## Key Findings
- **Finding 1**: Detail with citation [Source Title](url)
- **Finding 2**: Detail with citation
- **Finding 3**: Additional insight

## Market Context
[If applicable: broader market implications, trends, or competitive context]

## Sources
1. [Source Title](url) - brief description of why relevant
2. [Source Title](url) - brief description

CITATION RULES:
- ALWAYS include clickable URLs in [Title](url) format
- Cite inline AND in the Sources section
- If a source has no URL, just use the title

FALLBACK:
If you cannot find sufficient information, respond with:
"I found limited information on this topic. Here's what I found: [summary]. For comprehensive analysis with additional sources, I recommend the **Deep Research** feature."

Quality over speed - take time to synthesize actionable intelligence relevant to Composites One's business."""

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

    # =========================================================================
    # Per-Subtab System Prompts
    # =========================================================================

    FINANCIAL_SYSTEM_PROMPT = """You are a financial intelligence analyst for Composites One (C1), the largest composites distributor in North America.

You specialize in analyzing earnings calls and SEC filings for competitive intelligence relevant to the composites industry.

DATA SOURCES PROVIDED:
The search results below come from pre-extracted executive quotes from earnings calls and strategic insights from SEC filings. You do NOT need to call any tools. Simply synthesize the provided data.

RESPONSE FORMAT (use this exact structure):

## Executive Quotes
For each relevant quote, use this format:
> "quote text" — **Speaker Name**, Title (TICKER, QN YYYY)

Group quotes by theme (guidance, competitive, pricing, etc.) and add 1-2 sentence analysis after each.

## SEC Filing Insights
For each relevant SEC nugget:
- **Signal Type** (signal_strength): Key finding from filing
  - Filing: 10-K/10-Q/8-K, Section, Fiscal Year

## Analysis
[2-3 paragraphs synthesizing what the earnings + SEC data reveals for C1's business — competitive positioning, pricing trends, market outlook]

## Sources
1. [Company] QN YYYY Earnings Call — [speaker]
2. [Company] 10-K YYYY — [section]

CITATION RULES:
- Attribute every quote to its speaker with ticker and quarter
- Reference SEC filing type and section
- Bold the signal type (guidance, risk_admission, competitive_disclosure, etc.)

If data is insufficient, recommend the **Deep Research** feature."""

    EXPERT_SYSTEM_PROMPT = """You are an industry intelligence analyst for Composites One (C1), the largest composites distributor in North America.

You specialize in synthesizing insights from composites industry podcasts and expert commentary.

DATA SOURCES PROVIDED:
The search results below come from pre-extracted speaker-attributed quotes from industry podcasts (CW Talks, Composites Weekly, The Chemical Show, ICIS Chemical, Uptime Wind Energy). You do NOT need to call any tools. Simply synthesize the provided data.

RESPONSE FORMAT (use this exact structure):

## Expert Insights
For each relevant quote, use this format:
> "quote text" — **Speaker Name**, *Podcast Name* (date)

Group by theme and add 1-2 sentence analysis connecting to C1's business.

## Key Themes
- **Theme 1**: Summary of what experts are saying about this theme
- **Theme 2**: Summary with supporting quotes

## Industry Sentiment
[1-2 paragraphs on the overall industry mood, emerging trends, and what practitioners are signaling about the near-term outlook for composites]

## Sources
1. *Podcast Name* — Speaker Name (date)
2. *Podcast Name* — Speaker Name (date)

CITATION RULES:
- Always attribute quotes to speakers with podcast name and date
- Italicize podcast names
- Bold speaker names
- Group insights by theme (fiber_materials, resin_systems, sustainability, pricing, supply_chain, etc.)

If data is insufficient, recommend the **Deep Research** feature."""

    def __init__(self, config=None):
        self.config = config or settings
        # Resilient client for non-streaming calls
        self.client = get_resilient_async_client(
            anthropic_api_key=self.config.anthropic_api_key,
            openai_api_key=getattr(self.config, 'openai_api_key', None),
        )
        # Raw client for streaming (fallback to Anthropic-only for streaming)
        self._streaming_client = AsyncAnthropic(api_key=self.config.anthropic_api_key)
        self.model = "claude-opus-4-5"  # Upgraded for quality intelligence responses
        self.timeout_seconds = 120  # 2-minute timeout
        self._vector_store = None
        self._bq_storage = None
        
        # Track conversation for follow-up limit
        self.conversation_history: List[Dict[str, str]] = []
        self.follow_up_count = 0
        self.max_follow_ups = 2
    
    async def _get_vector_store(self):
        """Get or initialize vector store (BigQuery)."""
        if self._vector_store is None:
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
        search_start = time.time()
        query_preview = query[:80] + ("..." if len(query) > 80 else "")
        logger.info(f"[ADHOC_AGENT] Corpus search START: query='{query_preview}', limit={limit}")
        
        vector_store = await self._get_vector_store()
        
        if not vector_store.is_available:
            logger.warning("[ADHOC_AGENT] Vector store not available for ad hoc search")
            return []
        
        results = await vector_store.search(query=query, limit=limit)
        
        search_elapsed = time.time() - search_start
        logger.info(
            f"[ADHOC_AGENT] Corpus search COMPLETE: {search_elapsed:.2f}s, "
            f"{len(results)} results found"
        )
        
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
                "summary": r.get("document", ""),  # Full content, no truncation
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
    
    async def search_external_news(self, query: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Search external news sources (Exa, StockNews) in parallel.

        Returns combined results from available external tools.
        This supplements the corpus search with live/recent sources.
        """
        external_start = time.time()
        query_preview = query[:60] + ("..." if len(query) > 60 else "")
        logger.info(f"[ADHOC_AGENT] External news search START: query='{query_preview}'")

        results = {
            "exa_news": [],
            "stocknews": [],
        }

        async def _search_exa():
            try:
                exa_start = time.time()
                from app.mcp.tools.exa_search import news_search
                exa_result = await asyncio.to_thread(
                    news_search.invoke, {"query": query, "max_results": 5, "time_range": "week"}
                )
                exa_elapsed = time.time() - exa_start
                if exa_result and isinstance(exa_result, str):
                    data = json.loads(exa_result)
                    if data.get("results"):
                        results["exa_news"] = data["results"][:5]
                        logger.info(
                            f"[ADHOC_AGENT] Exa news COMPLETE: {exa_elapsed:.2f}s, "
                            f"{len(results['exa_news'])} results"
                        )
            except Exception as e:
                logger.warning(f"[ADHOC_AGENT] Exa news search FAILED: {str(e)}")

        async def _search_stocknews():
            try:
                sn_start = time.time()
                from app.mcp.tools.stocknews_api import search_news_keyword
                stocknews_result = await asyncio.to_thread(
                    search_news_keyword.invoke, {"keyword": query, "days": 7, "items": 8}
                )
                sn_elapsed = time.time() - sn_start
                if stocknews_result and isinstance(stocknews_result, str):
                    data = json.loads(stocknews_result)
                    if data.get("articles"):
                        results["stocknews"] = data["articles"][:8]
                        logger.info(
                            f"[ADHOC_AGENT] StockNews COMPLETE: {sn_elapsed:.2f}s, "
                            f"{len(results['stocknews'])} results"
                        )
            except Exception as e:
                logger.warning(f"[ADHOC_AGENT] StockNews search FAILED: {str(e)}")

        # Run Exa and StockNews in parallel
        await asyncio.gather(_search_exa(), _search_stocknews())

        external_elapsed = time.time() - external_start
        total_results = len(results["exa_news"]) + len(results["stocknews"])
        logger.info(
            f"[ADHOC_AGENT] External news search COMPLETE: {external_elapsed:.2f}s, "
            f"{total_results} total results"
        )

        return results

    async def search_financial_data(self, query: str) -> Dict[str, Any]:
        """
        Search earnings quotes and SEC nuggets for the financial subtab.
        """
        start_time = time.time()
        query_preview = query[:60] + ("..." if len(query) > 60 else "")
        logger.info(f"[ADHOC_AGENT] Financial data search START: query='{query_preview}'")

        results = {
            "earnings_quotes": [],
            "sec_nuggets": [],
        }

        # Search earnings quotes
        try:
            eq_start = time.time()
            from app.mcp.tools.earnings_quotes import search_earnings_quotes
            eq_result = await search_earnings_quotes.ainvoke({"query": query, "limit": 15, "quotable_only": True})
            eq_elapsed = time.time() - eq_start
            if eq_result and isinstance(eq_result, str):
                data = json.loads(eq_result)
                if data.get("quotes"):
                    results["earnings_quotes"] = data["quotes"]
                    logger.info(f"[ADHOC_AGENT] Earnings quotes COMPLETE: {eq_elapsed:.2f}s, {len(results['earnings_quotes'])} quotes")
        except Exception as e:
            logger.warning(f"[ADHOC_AGENT] Earnings quotes search FAILED: {str(e)}")

        # Search SEC nuggets
        try:
            sn_start = time.time()
            from app.mcp.tools.sec_nuggets import search_sec_nuggets
            sn_result = await search_sec_nuggets.ainvoke({"query": query, "limit": 15})
            sn_elapsed = time.time() - sn_start
            if sn_result and isinstance(sn_result, str):
                data = json.loads(sn_result)
                if data.get("nuggets"):
                    results["sec_nuggets"] = data["nuggets"]
                    logger.info(f"[ADHOC_AGENT] SEC nuggets COMPLETE: {sn_elapsed:.2f}s, {len(results['sec_nuggets'])} nuggets")
        except Exception as e:
            logger.warning(f"[ADHOC_AGENT] SEC nuggets search FAILED: {str(e)}")

        elapsed = time.time() - start_time
        total = len(results["earnings_quotes"]) + len(results["sec_nuggets"])
        logger.info(f"[ADHOC_AGENT] Financial data search COMPLETE: {elapsed:.2f}s, {total} total results")
        return results

    def _format_financial_results(self, results: Dict[str, Any]) -> str:
        """Format earnings quotes and SEC nuggets for the prompt."""
        sections = []

        if results.get("earnings_quotes"):
            section = "## Earnings Call Quotes\n"
            for q in results["earnings_quotes"][:12]:
                section += f"### {q.get('speaker_name', 'Unknown')} — {q.get('speaker_role', '')} ({q.get('ticker', '?')}, Q{q.get('quarter', '?')} {q.get('year', '')})\n"
                section += f"**Type:** {q.get('quote_type', 'unknown')} | **Section:** {q.get('section', 'unknown')}\n"
                section += f"> {q.get('quote_text', '')}\n"
                if q.get('context'):
                    section += f"*Context: {q['context']}*\n"
                section += "\n"
            sections.append(section)

        if results.get("sec_nuggets"):
            section = "## SEC Filing Nuggets\n"
            for n in results["sec_nuggets"][:12]:
                section += f"### {n.get('ticker', '?')} — {n.get('filing_type', 'Filing')} ({n.get('fiscal_year', '')})\n"
                section += f"**Type:** {n.get('nugget_type', 'unknown')} | **Signal:** {n.get('signal_strength', 'standard')} | **Section:** {n.get('section', 'unknown')}\n"
                section += f"{n.get('nugget_text', '')}\n"
                if n.get('companies_mentioned'):
                    section += f"*Companies: {', '.join(n['companies_mentioned'])}*\n"
                section += "\n"
            sections.append(section)

        return "\n\n".join(sections)

    async def search_expert_data(self, query: str) -> Dict[str, Any]:
        """
        Search podcast quotes for the expert subtab.
        """
        start_time = time.time()
        query_preview = query[:60] + ("..." if len(query) > 60 else "")
        logger.info(f"[ADHOC_AGENT] Expert data search START: query='{query_preview}'")

        results = {"podcast_quotes": []}

        try:
            pq_start = time.time()
            from app.mcp.tools.podcast_quotes import search_podcast_quotes
            pq_result = search_podcast_quotes.invoke({"search_query": query, "limit": 15, "days": 90})
            pq_elapsed = time.time() - pq_start
            if pq_result and isinstance(pq_result, str):
                data = json.loads(pq_result)
                if data.get("quotes"):
                    results["podcast_quotes"] = data["quotes"]
                    logger.info(f"[ADHOC_AGENT] Podcast quotes COMPLETE: {pq_elapsed:.2f}s, {len(results['podcast_quotes'])} quotes")
        except Exception as e:
            logger.warning(f"[ADHOC_AGENT] Podcast quotes search FAILED: {str(e)}")

        elapsed = time.time() - start_time
        logger.info(f"[ADHOC_AGENT] Expert data search COMPLETE: {elapsed:.2f}s, {len(results['podcast_quotes'])} results")
        return results

    def _format_expert_results(self, results: Dict[str, Any]) -> str:
        """Format podcast quotes for the prompt."""
        if not results.get("podcast_quotes"):
            return ""

        section = "## Podcast Expert Quotes\n"
        for q in results["podcast_quotes"][:12]:
            section += f"### {q.get('speaker_name', 'Unknown')} — *{q.get('podcast_name', 'Podcast')}*\n"
            if q.get('themes'):
                themes = q['themes'] if isinstance(q['themes'], list) else [q['themes']]
                section += f"**Themes:** {', '.join(themes)}\n"
            section += f"> {q.get('quote_text', '')}\n"
            if q.get('context'):
                section += f"*Context: {q['context']}*\n"
            section += "\n"

        return section

    def _get_system_prompt_for_subtab(self, subtab: Optional[str] = None) -> str:
        """Return the appropriate system prompt based on the active subtab."""
        if subtab == "financialFeed":
            return self.FINANCIAL_SYSTEM_PROMPT
        elif subtab == "expertFeed":
            return self.EXPERT_SYSTEM_PROMPT
        return self.SYSTEM_PROMPT

    def _format_external_results(self, external_results: Dict[str, List]) -> str:
        """Format external tool results for inclusion in prompt."""
        sections = []
        
        if external_results.get("exa_news"):
            exa_section = "## Exa News Search Results\n"
            for r in external_results["exa_news"]:
                exa_section += f"### {r.get('title', 'Untitled')}\n"
                exa_section += f"**URL:** {r.get('url', '')}\n"
                exa_section += f"**Published:** {r.get('published_date', 'Unknown')}\n"
                content = r.get('content', r.get('snippet', ''))
                exa_section += f"**Content:** {content[:500] if content else ''}\n\n"
            sections.append(exa_section)
        
        if external_results.get("stocknews"):
            sn_section = "## StockNews Results\n"
            for r in external_results["stocknews"]:
                sn_section += f"### {r.get('title', 'Untitled')}\n"
                sn_section += f"**Source:** {r.get('source', '')} | **URL:** {r.get('url', '')}\n"
                sn_section += f"**Sentiment:** {r.get('sentiment', 'neutral')}\n"
                text = r.get('text', '')
                sn_section += f"**Content:** {text[:500] if text else ''}\n\n"
            sections.append(sn_section)
        
        return "\n".join(sections) if sections else ""
    
    def _should_redirect_to_deep_research(self) -> bool:
        """Check if we should redirect user to deep research."""
        return self.follow_up_count >= self.max_follow_ups
    
    async def generate_briefing(
        self,
        question: str,
        context: BriefingContext,
        is_follow_up: bool = False,
        session: Optional["BriefingSession"] = None,
        user_team: Optional[str] = None,
        subtab: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate an ad hoc briefing response.
        
        Args:
            question: User's question
            context: Structured context from current brief/digest
            is_follow_up: Whether this is a follow-up question
            session: Optional session for stateful conversation tracking
            user_team: User's team for team-scoped memory context
        
        Returns:
            Briefing response with answer, sources, and metadata
        """
        request_start = time.time()
        question_preview = question[:100] + ("..." if len(question) > 100 else "")
        session_id = session.session_id if session else "no-session"
        
        logger.info(
            f"[ADHOC_AGENT] Briefing START: question='{question_preview}', "
            f"is_follow_up={is_follow_up}, session={session_id}"
        )
        
        # Fetch memory context (preferences + relevant memories)
        memory_start = time.time()
        memory_context = await build_agent_context(question, user_team)
        memory_prompt_addition = memory_context.prompt_addition if memory_context else ""
        memory_elapsed = time.time() - memory_start
        if memory_prompt_addition:
            logger.info(
                f"[ADHOC_AGENT] Memory context loaded: {memory_elapsed:.2f}s, "
                f"{len(memory_prompt_addition)} chars"
            )
        # Use session state if available, otherwise fall back to instance state
        if session:
            if is_follow_up:
                session.increment_follow_up()
            follow_up_count = session.follow_up_count
            should_redirect = session.should_redirect_to_deep_research()
            # Add question to conversation history
            session.add_to_history("user", question)
        else:
            # Legacy behavior for backward compatibility
            if is_follow_up:
                self.follow_up_count += 1
            follow_up_count = self.follow_up_count
            should_redirect = self._should_redirect_to_deep_research()
        
        if should_redirect:
            redirect_response = {
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
                "follow_up_count": follow_up_count,
                "generated_at": datetime.utcnow().isoformat(),
            }
            if session:
                redirect_response["session_id"] = session.session_id
                redirect_response["session"] = session.to_dict()
            return redirect_response
        
        # =====================================================================
        # Route search by subtab
        # =====================================================================
        logger.info(f"[ADHOC_AGENT] Subtab routing: subtab={subtab or 'default'}")

        search_context = ""
        has_results = False

        if subtab == "financialFeed":
            # Financial subtab: earnings quotes + SEC nuggets
            financial_results = await self.search_financial_data(question)
            search_context = self._format_financial_results(financial_results)
            has_results = bool(financial_results.get("earnings_quotes") or financial_results.get("sec_nuggets"))

        elif subtab == "expertFeed":
            # Expert subtab: podcast quotes
            expert_results = await self.search_expert_data(question)
            search_context = self._format_expert_results(expert_results)
            has_results = bool(expert_results.get("podcast_quotes"))

        else:
            # Article feed (default): corpus + exa + stocknews
            search_query = question
            if context.active_filters:
                filter_str = " ".join(context.active_filters)
                search_query = f"{question} {filter_str}"
                logger.info(f"Ad hoc search using active filters: {context.active_filters}")

            search_results = await self.search_articles(search_query, limit=10)

            if not search_results and context.active_filters:
                logger.info("No results found with filters, falling back to original question")
                search_results = await self.search_articles(question, limit=8)

            if search_results:
                has_results = True
                search_context = "## Internal Corpus Results\n" + "\n".join([
                    f"### {r['title']}\n**Source:** {r['source']} | **Date:** {r['date']}\n**URL:** {r['url']}\n**Content:** {r['summary']}\n"
                    for r in search_results[:8]
                ])

            external_results = await self.search_external_news(question)
            external_context = self._format_external_results(external_results)
            if external_context:
                search_context += "\n\n" + external_context
                has_results = True
                logger.info("Added external tool results to context")

        if not has_results:
            return {
                "id": str(uuid.uuid4()),
                "question": question,
                "answer": (
                    "I couldn't find relevant information in the available data sources. "
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
        
        # Include conversation history if session exists
        conversation_context = ""
        if session and session.conversation_history:
            conversation_context = f"\n\n{session.get_conversation_context()}\n"
        
        # Inject memory context (preferences + relevant past memories) if available
        memory_section = ""
        if memory_prompt_addition:
            memory_section = f"\n\n{memory_prompt_addition}\n"
            logger.info(f"Injecting memory context into ad-hoc briefing ({len(memory_prompt_addition)} chars)")
        
        full_prompt = f"""{context_string}{memory_section}
{conversation_context}
{search_context}

User Question: {question}

Using the search results above, provide a thorough briefing response.
Follow the response format from your instructions.
Use **bold** for key insights and include citations where applicable.
{f"This is follow-up #{follow_up_count}. You have {max(0, (session.max_follow_ups if session else self.max_follow_ups) - follow_up_count)} follow-ups remaining." if is_follow_up else ""}

Respond with a JSON object:
{{
    "answer": "Your formatted briefing with ## sections, **bold**, and [Title](url) citations",
    "sources_used": [{{"title": "...", "url": "...", "relevance": "..."}}],
    "confidence": "high|medium|low",
    "suggest_deep_research": true|false
}}"""

        try:
            # LLM call with timeout protection
            llm_start = time.time()
            logger.info(f"[ADHOC_AGENT] LLM call START: model={self.model}")
            
            try:
                response = await asyncio.wait_for(
                    self.client.messages_create(
                        model=self.model,
                        max_tokens=3000,  # Increased for richer formatting
                        temperature=0,
                        system=self._get_system_prompt_for_subtab(subtab),
                        messages=[{"role": "user", "content": full_prompt}]
                    ),
                    timeout=120.0  # 2 minutes
                )
                llm_elapsed = time.time() - llm_start
                logger.info(f"[ADHOC_AGENT] LLM call COMPLETE: {llm_elapsed:.2f}s")
            except asyncio.TimeoutError:
                llm_elapsed = time.time() - llm_start
                logger.error(f"[ADHOC_AGENT] LLM call TIMEOUT: exceeded 120s (elapsed: {llm_elapsed:.2f}s)")
                raise Exception(
                    "Request timed out while generating briefing (120s limit). "
                    "Please try again or use Deep Research for complex queries."
                )
            
            result_text = response.content[0].text.strip()
            
            # Parse JSON response
            if result_text.startswith("```json"):
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif result_text.startswith("```"):
                result_text = result_text.split("```")[1].split("```")[0].strip()
            
            data = json.loads(result_text)
            
            # Build response record
            answer_text = data.get("answer", "")
            briefing_response = {
                "id": str(uuid.uuid4()),
                "question": question,
                "answer": answer_text,
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
                "follow_up_count": follow_up_count,
                "generated_at": datetime.utcnow().isoformat(),
                "model": self.model,
            }
            
            # Add session info if available
            if session:
                briefing_response["session_id"] = session.session_id
                briefing_response["session"] = session.to_dict()
                # Add response to conversation history
                session.add_to_history("assistant", answer_text)
            
            # Save to storage
            await self._save_adhoc_briefing(briefing_response)
            
            total_elapsed = time.time() - request_start
            logger.info(
                f"[ADHOC_AGENT] Briefing COMPLETE: {total_elapsed:.2f}s, "
                f"confidence={briefing_response['confidence']}, "
                f"sources={len(briefing_response['sources_used'])}, "
                f"answer_len={len(answer_text)}"
            )
            
            return briefing_response
            
        except json.JSONDecodeError as e:
            total_elapsed = time.time() - request_start
            logger.error(
                f"[ADHOC_AGENT] Briefing FAILED (JSON parse): {total_elapsed:.2f}s, error={str(e)}",
                exc_info=True
            )
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
            total_elapsed = time.time() - request_start
            logger.error(
                f"[ADHOC_AGENT] Briefing FAILED: {total_elapsed:.2f}s, "
                f"error_type={type(e).__name__}, error={str(e)}",
                exc_info=True
            )
            return {
                "id": str(uuid.uuid4()),
                "question": question,
                "answer": f"I encountered an error while generating the briefing. Please try again or use Deep Research for this query.",
                "error": str(e),
                "suggest_deep_research": True,
                "generated_at": datetime.utcnow().isoformat(),
            }
    
    async def _save_adhoc_briefing(self, briefing: Dict[str, Any]):
        """Save ad hoc briefing to BigQuery."""
        try:
            save_start = time.time()
            bq_storage = await self._get_bq_storage()
            if bq_storage:
                await bq_storage.save_adhoc_briefing(briefing)
                save_elapsed = time.time() - save_start
                logger.info(
                    f"[ADHOC_AGENT] Saved briefing to BigQuery: {briefing['id']}, {save_elapsed:.2f}s"
                )
            else:
                logger.warning(
                    f"[ADHOC_AGENT] BigQuery storage not available - briefing {briefing['id']} not saved"
                )
        except Exception as e:
            logger.error(f"[ADHOC_AGENT] Failed to save briefing: {str(e)}", exc_info=True)
    
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
        session: Optional["BriefingSession"] = None,
        user_team: Optional[str] = None,
        subtab: Optional[str] = None,
    ) -> AsyncIterator[str]:
        """
        Stream an ad hoc briefing response with progress events.
        
        NOTE: Logging is lighter in streaming mode since progress events provide UX feedback.
        
        Yields chunks of the response as they're generated, with progress
        events for each research phase.
        
        SSE Event Types:
        - progress: Research phase updates (step, message, status, count)
        - content: Response text chunks
        - session_info: Session state at end
        - redirect: Redirect to Deep Research
        - no_results: No articles found
        
        Args:
            question: User's question
            context: Structured context from current brief/digest
            is_follow_up: Whether this is a follow-up question
            session: Optional session for stateful conversation tracking
            user_team: User's team for team-scoped memory context
        """
        stream_start = time.time()
        question_preview = question[:100] + ("..." if len(question) > 100 else "")
        session_id = session.session_id if session else "no-session"
        
        logger.info(
            f"[ADHOC_AGENT] Streaming briefing START: question='{question_preview}', "
            f"is_follow_up={is_follow_up}, session={session_id}"
        )
        
        # Fetch memory context (preferences + relevant memories) early
        memory_context = await build_agent_context(question, user_team)
        memory_prompt_addition = memory_context.prompt_addition if memory_context else ""
        # Use session state if available
        if session:
            if is_follow_up:
                session.increment_follow_up()
            follow_up_count = session.follow_up_count
            should_redirect = session.should_redirect_to_deep_research()
            session.add_to_history("user", question)
        else:
            if is_follow_up:
                self.follow_up_count += 1
            follow_up_count = self.follow_up_count
            should_redirect = self._should_redirect_to_deep_research()
        
        if should_redirect:
            yield json.dumps({
                "type": "redirect",
                "message": "For deeper analysis, please use the Deep Research feature.",
                "deep_research_query": question,
                "follow_up_count": follow_up_count,
                "session_id": session.session_id if session else None,
            })
            return
        
        # =========================================================================
        # Search Phases — routed by subtab
        # =========================================================================
        logger.info(f"[ADHOC_AGENT] Stream subtab routing: subtab={subtab or 'default'}")

        search_context = ""
        has_results = False

        if subtab == "financialFeed":
            # --- Financial subtab: earnings quotes + SEC nuggets ---
            yield json.dumps({
                "type": "progress",
                "step": "earnings_search",
                "label": "Earnings Quotes",
                "message": "Searching earnings call transcripts...",
                "status": "running",
            })

            financial_results = await self.search_financial_data(question)
            eq_count = len(financial_results.get("earnings_quotes", []))
            sn_count = len(financial_results.get("sec_nuggets", []))

            yield json.dumps({
                "type": "progress",
                "step": "earnings_search",
                "label": "Earnings Quotes",
                "message": f"Found {eq_count} executive quotes" if eq_count else "No quotes found",
                "status": "complete",
                "count": eq_count,
            })

            yield json.dumps({
                "type": "progress",
                "step": "sec_search",
                "label": "SEC Filings",
                "message": f"Found {sn_count} filing insights" if sn_count else "No nuggets found",
                "status": "complete",
                "count": sn_count,
            })

            search_context = self._format_financial_results(financial_results)
            has_results = eq_count > 0 or sn_count > 0

        elif subtab == "expertFeed":
            # --- Expert subtab: podcast quotes ---
            yield json.dumps({
                "type": "progress",
                "step": "podcast_search",
                "label": "Podcast Insights",
                "message": "Searching industry podcast transcripts...",
                "status": "running",
            })

            expert_results = await self.search_expert_data(question)
            pq_count = len(expert_results.get("podcast_quotes", []))

            yield json.dumps({
                "type": "progress",
                "step": "podcast_search",
                "label": "Podcast Insights",
                "message": f"Found {pq_count} expert quotes" if pq_count else "No quotes found",
                "status": "complete",
                "count": pq_count,
            })

            search_context = self._format_expert_results(expert_results)
            has_results = pq_count > 0

        else:
            # --- Article feed (default): corpus + exa + stocknews ---
            # Show all search steps as running simultaneously
            yield json.dumps({
                "type": "progress",
                "step": "corpus_search",
                "label": "Knowledge Base",
                "message": "Searching internal knowledge base...",
                "status": "running",
            })
            yield json.dumps({
                "type": "progress",
                "step": "exa_search",
                "label": "Advanced Web Search",
                "message": "Searching web for recent news...",
                "status": "running",
            })
            yield json.dumps({
                "type": "progress",
                "step": "stocknews_search",
                "label": "Stock Market News",
                "message": "Searching stock market news...",
                "status": "running",
            })

            # Run all searches in parallel for speed
            search_results, external_results = await asyncio.gather(
                self.search_articles(question, limit=8),
                self.search_external_news(question),
            )

            # Emit completion events for each search
            yield json.dumps({
                "type": "progress",
                "step": "corpus_search",
                "label": "Knowledge Base",
                "message": f"Found {len(search_results)} relevant articles" if search_results else "No articles found",
                "status": "complete",
                "count": len(search_results),
            })

            if search_results:
                has_results = True
                search_context = "## Internal Corpus Results\n" + "\n".join([
                    f"### {r['title']}\n**Source:** {r['source']} | **Date:** {r['date']}\n**URL:** {r['url']}\n**Content:** {r['summary']}\n"
                    for r in search_results[:8]
                ])

            exa_count = len(external_results.get("exa_news", []))
            stocknews_count = len(external_results.get("stocknews", []))

            yield json.dumps({
                "type": "progress",
                "step": "exa_search",
                "label": "Advanced Web Search",
                "message": f"Found {exa_count} articles" if exa_count else "No results",
                "status": "complete",
                "count": exa_count,
            })

            yield json.dumps({
                "type": "progress",
                "step": "stocknews_search",
                "label": "Stock Market News",
                "message": f"Found {stocknews_count} articles" if stocknews_count else "No results",
                "status": "complete",
                "count": stocknews_count,
            })

            external_context = self._format_external_results(external_results)
            if external_context:
                search_context += "\n\n" + external_context
                has_results = True

        if not has_results:
            yield json.dumps({
                "type": "no_results",
                "message": "No relevant data found. Try Deep Research for more sources.",
                "session_id": session.session_id if session else None,
            })
            return

        # =========================================================================
        # Synthesis Phase
        # =========================================================================
        synthesis_label = "Financial Analysis" if subtab == "financialFeed" else "Analysis"
        yield json.dumps({
            "type": "progress",
            "step": "synthesis",
            "label": synthesis_label,
            "message": "Synthesizing intelligence response...",
            "status": "running",
        })

        # Build context
        context_string = context.to_context_string()

        # Include conversation history if session exists
        conversation_context = ""
        if session and session.conversation_history:
            conversation_context = f"\n\n{session.get_conversation_context()}\n"

        # Inject memory context if available
        memory_section = ""
        if memory_prompt_addition:
            memory_section = f"\n\n{memory_prompt_addition}\n"
            logger.info(f"Injecting memory context into streaming briefing ({len(memory_prompt_addition)} chars)")

        full_prompt = f"""{context_string}{memory_section}
{conversation_context}
{search_context}

User Question: {question}

Using the search results above, provide a thorough briefing response.
Follow the response format from your instructions.
Use **bold** for key insights and include citations where applicable."""

        # Stream response and collect full text for history
        # Note: Streaming uses raw Anthropic client (no OpenAI fallback for streaming)
        llm_start = time.time()
        logger.info(f"[ADHOC_AGENT] Streaming LLM call START")

        full_response = ""
        try:
            async with self._streaming_client.messages.stream(
                model=self.model,
                max_tokens=3000,
                temperature=0,
                system=self._get_system_prompt_for_subtab(subtab),
                messages=[{"role": "user", "content": full_prompt}]
            ) as stream:
                async for text in stream.text_stream:
                    full_response += text
                    yield json.dumps({"type": "content", "text": text})
            
            llm_elapsed = time.time() - llm_start
            logger.info(f"[ADHOC_AGENT] Streaming LLM call COMPLETE: {llm_elapsed:.2f}s")
        except Exception as stream_error:
            llm_elapsed = time.time() - llm_start
            logger.error(
                f"[ADHOC_AGENT] Streaming LLM call FAILED: {llm_elapsed:.2f}s, "
                f"error={str(stream_error)}",
                exc_info=True
            )
            raise
        
        # Mark synthesis complete
        yield json.dumps({
            "type": "progress",
            "step": "synthesis",
            "label": synthesis_label,
            "message": "Response complete",
            "status": "complete",
        })
        
        # Save response to conversation history
        if session and full_response:
            session.add_to_history("assistant", full_response)
        
        # Emit session info at end
        if session:
            yield json.dumps({
                "type": "session_info",
                "session_id": session.session_id,
                "follow_up_count": session.follow_up_count,
                "turns_remaining": max(0, session.max_follow_ups - session.follow_up_count),
            })
        
        stream_elapsed = time.time() - stream_start
        logger.info(
            f"[ADHOC_AGENT] Streaming briefing COMPLETE: {stream_elapsed:.2f}s, "
            f"response_len={len(full_response)}"
        )


# =============================================================================
# Factory function
# =============================================================================

def get_adhoc_briefing_agent(streaming: bool = False) -> AdHocBriefingAgent:
    """Get an ad hoc briefing agent instance."""
    if streaming:
        return StreamingAdHocBriefingAgent()
    return AdHocBriefingAgent()
