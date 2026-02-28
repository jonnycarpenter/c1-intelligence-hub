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
import asyncio
import time
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Set
from collections import Counter
from exa_py import Exa
from anthropic import AsyncAnthropic

from app.utils.resilient_llm import get_resilient_async_client

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
3. Voice Enrichment: Pre-fetched executive quotes, SEC filings nuggets, and expert podcast quotes. These are real, sourced quotes that ground the briefing themes in authoritative voices. Use them selectively — only when they genuinely reinforce or add conviction to a strategic theme.
4. TOOL AVAILABLE: search_peripheral_intelligence - Use this to fill gaps or validate high-conviction claims.
5. Scratchpad: Your notes from previous peripheral searches in this session.

YOUR TASK: "The Differential"
Analyze the Pre-Brief against the Historical Context to identify:
- "Continuing to Track": Topics from previous weeks that have significant new "evolution" signals.
- "Net New": High-confidence developments that have not appeared in recent history.
- "Conviction Filtering": Filter out transient news or low-confidence signals. Focus only on items with high strategic impact.

VOICE ENRICHMENT GUIDELINES:
You have been provided with three types of authoritative voice data:
- SEC Filing Nuggets: Legally mandated disclosures from competitor/supplier 10-K, 10-Q, and 8-K filings. Use these for hard evidence of strategic shifts, risk factors, and competitive positioning.
- Earnings Call Quotes: Executive quotes from Q&A sessions. Use these for management sentiment, forward guidance, and market outlook.
- Podcast Expert Quotes: Practitioner insights from composites industry podcasts. Use these for on-the-ground perspective, technology adoption trends, and supply chain signals.

When using voice data:
- Attribute clearly: "As [Speaker Name], [Role] at [Company] noted in [Source]..."
- Only include quotes that genuinely support or add nuance to a strategic theme
- Do NOT force-fit quotes. If the enrichment data has nothing relevant to a section, that is fine.
- Mark voice-supported insights with the source type in parentheses: (SEC Filing), (Earnings Call), (Industry Podcast)

TOOL USE GUIDELINES:
You have access to search_peripheral_intelligence(query: str) for finding adjacent intelligence that may have "slipped through the cracks".

Use this tool ONLY when:
1. A high-conviction topic has <70% confidence and needs validation
2. A company/technology is mentioned prominently but lacks strategic context
3. You need to validate a surprising claim from the pre-briefing
4. Adjacent signals could materially enhance the narrative (e.g., regulatory context, competing technologies, supply chain alternatives)

LIMIT: Maximum 3 tool calls per iteration. Be selective and strategic. Check the scratchpad to avoid redundant searches.

Query Format Examples:
- "Boeing 787 composites supply chain alternatives 2025"
- "EU carbon fiber import tariffs regulatory changes"
- "Hydrogen pressure vessel certification requirements updates"

Tool Response: You will receive 5 articles with full citations (title, URL, date, text snippets). Mark these as [Exa:N] in your final briefing.

IMPORTANT: When you request tool calls, also include a "scratchpad_notes" field to record what you learned and what questions remain:
{{
    "tool_calls": [
        {{
            "tool": "search_peripheral_intelligence",
            "query": "your strategic search query here",
            "reason": "brief explanation of why this search is needed"
        }}
    ],
    "scratchpad_notes": "Key findings so far: ... | Questions remaining: ... | Topics to validate: ..."
}}

{final_iteration_warning}

REQUIREMENTS:

1. CREATE 3-4 STRATEGIC SECTIONS
   - Group the most critical developments into logical strategic themes.
   - Use punchy, executive-level headers (e.g., "The Aerospace Recovery Pivot", "Hydrogen Pressure Vessel Consolidation").

2. FOR EACH SECTION:
   - ONE Bold Headline: The single most important high-conviction development.
   - 2-4 Supporting Insights: Detailed, evidence-backed bullets.
   - Each item must be marked "net_new" or "continuing" based on your differential analysis.
   - Include citations using the article ID or reference provided in the Pre-Brief (use [N] for pre-brief sources, [Exa:N] for peripheral search results).
   - Where voice data reinforces a theme, weave in the quote naturally: e.g., "This aligns with [Speaker]'s recent earnings comment that '[quote excerpt]' (Earnings Call)."

3. INLINE LOGOS (applies to sections AND overall_trend)
   - Wrap company names in double brackets: [[Company Name]].
   - Use this in headline text, insight text, AND the overall_trend field.

4. ENTITY HIGHLIGHTING (for overall_trend)
   - Wrap important NON-company entities in double curly braces: {{Entity Name}}.
   - Use this for: industry initiatives ({{UK LSIC}}), material technologies ({{recycled PET}}), process acronyms ({{PCM}}), standards/certifications, key programs.
   - This creates bold highlighting without logos.

5. OVERALL TREND
   - Provide a detailed 2-3 sentence analysis of the week's strategic shift.
   - Use [[Company]] tags for companies mentioned and {{Entity}} tags for important non-company terms.
   - This is the executive summary paragraph, make it substantive.

FINAL BRIEFING JSON FORMAT:
{{
    "briefing_title": "Strategic Intelligence Briefing: Week of {period_end_short}",
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
    "overall_trend": "[[Company A]] is driving the {{fast-cure prepreg}} transition while {{UK LSIC}} investments signal infrastructure buildout. The [[Company B]] acquisition positions them for {{hydrogen pressure vessel}} scale."
}}

<historical_context>
{historical_context}
</historical_context>

<pre_brief_data>
{pre_brief_data}
</pre_brief_data>

<enrichment_context>
{enrichment_context}
</enrichment_context>

<peripheral_search_results>
{peripheral_results}
</peripheral_search_results>

<scratchpad>
{scratchpad}
</scratchpad>
"""

    def __init__(self, config=None):
        """Initialize the executive synthesizer (Agent 2)."""
        self.config = config or settings
        # Use Anthropic Opus 4.5 for highest quality executive synthesis
        api_key = self.config.anthropic_api_key or os.getenv('ANTHROPIC_API_KEY')
        gemini_api_key = getattr(self.config, 'gemini_api_key', None)
        self.client = get_resilient_async_client(
            anthropic_api_key=api_key, 
            gemini_api_key=gemini_api_key
        )
        self.model = "claude-opus-4-6"  # Best quality for executive briefings
        self._bq_storage = None
        self._vector_store = None
        # Initialize Exa client for peripheral intelligence search
        # DISABLED (Feb 2026 cost reduction) - Exa API is a paid service
        # To re-enable, uncomment the lines below and remove the forced None
        # exa_api_key = getattr(self.config, 'exa_api_key', None)
        # self.exa_client = Exa(exa_api_key) if exa_api_key else None
        self.exa_client = None
        logger.info("Exa peripheral search DISABLED (Feb 2026 cost reduction)")
        
        # ElevenLabs config for podcast generation (uses Text-to-Dialogue API)
        # Voice IDs: Host=Rachel (warm, engaging), Analyst=Josh (professional, clear)
        self.host_voice_id = getattr(self.config, 'elevenlabs_host_voice_id', '21m00Tcm4TlvDq8ikWAM')  # Rachel
        self.analyst_voice_id = getattr(self.config, 'elevenlabs_analyst_voice_id', 'TxGEqnHWrfWFTfGW9XjX')  # Josh
        
        if not getattr(self.config, 'elevenlabs_api_key', None):
            logger.warning("ElevenLabs API key not configured - podcast generation disabled")
        
        # GCS client for podcast upload (lazy-loaded)
        self._gcs_client = None
        self._gcs_bucket = None
    
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
        """
        Get rich context from the last N weekly briefings for differential analysis.
        
        Includes:
        - BLUF (Bottom Line Up Front) summary
        - Section headlines with net_new/continuing status
        - Key companies mentioned
        - Overall trend analysis
        
        This enables Agent 2 to accurately identify what's genuinely new vs. continuing.
        """
        try:
            bq_storage = await self._get_bq_storage()
            briefings = []
            if bq_storage:
                briefings = await bq_storage.get_weekly_briefing_history(limit=limit)
            
            if not briefings:
                return "No historical briefings found. Treat all developments as potentially new."
            
            context_parts = []
            for idx, b in enumerate(briefings, 1):
                # Format date
                period_end = b.get('period_end', 'Unknown')
                if hasattr(period_end, 'strftime'):
                    date_str = period_end.strftime('%B %d, %Y')
                else:
                    date_str = str(period_end)[:10] if period_end else 'Unknown'
                
                # Start with header and BLUF
                briefing_context = [f"=== PRIOR BRIEFING {idx}: Week ending {date_str} ==="]
                
                bluf = b.get('bluf', '')
                if bluf:
                    briefing_context.append(f"BLUF: {bluf}")
                
                # Extract section headlines with status
                sections = b.get('sections', [])
                if sections:
                    briefing_context.append("\nSECTION HEADLINES:")
                    for section in sections:
                        header = section.get('header', 'Update')
                        headline = section.get('headline', {})
                        headline_text = headline.get('text', '') if isinstance(headline, dict) else str(headline)
                        headline_status = headline.get('status', 'unknown') if isinstance(headline, dict) else 'unknown'
                        
                        # Clean up headline text (remove [[Company]] tags for readability)
                        clean_headline = re.sub(r'\[\[([^\]]+)\]\]', r'\1', headline_text)
                        # Remove citation markers for context clarity
                        clean_headline = re.sub(r'\[(?:Exa:)?\d+\]', '', clean_headline).strip()
                        
                        briefing_context.append(f"  • [{header}] ({headline_status}): {clean_headline}")
                        
                        # Include key insights with status
                        insights = section.get('insights', [])
                        for insight in insights[:2]:  # Limit to top 2 insights per section
                            insight_text = insight.get('text', '') if isinstance(insight, dict) else str(insight)
                            insight_status = insight.get('status', 'unknown') if isinstance(insight, dict) else 'unknown'
                            clean_insight = re.sub(r'\[\[([^\]]+)\]\]', r'\1', insight_text)
                            clean_insight = re.sub(r'\[(?:Exa:)?\d+\]', '', clean_insight).strip()
                            if clean_insight:
                                briefing_context.append(f"      - ({insight_status}): {clean_insight[:150]}...")
                
                # Key companies
                companies = b.get('all_companies_mentioned', [])
                if companies:
                    # Handle both list of strings and list of dicts with 'name' key
                    company_names = []
                    for c in companies[:10]:  # Limit to top 10
                        if isinstance(c, dict):
                            company_names.append(c.get('name', str(c)))
                        else:
                            company_names.append(str(c))
                    briefing_context.append(f"\nKEY COMPANIES: {', '.join(company_names)}")
                
                # Topics covered
                topics = b.get('key_topics_this_week', [])
                if topics:
                    briefing_context.append(f"TOPICS: {', '.join(topics[:8])}")  # Limit to 8
                
                # Overall trend
                overall_trend = b.get('overall_trend', '')
                if overall_trend:
                    briefing_context.append(f"\nOVERALL TREND: {overall_trend[:300]}...")
                
                context_parts.append("\n".join(briefing_context))
            
            return "\n\n".join(context_parts)
                
        except Exception as e:
            logger.warning(f"Could not get historical context: {e}", exc_info=True)
        
        return "Error retrieving historical context. Proceed with caution on net_new classifications."
    
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
        """Get the full article objects for those referenced in the pre-brief.
        
        Returns articles in the SAME ORDER as article_ids to preserve citation mapping.
        Citation [N] in the briefing corresponds to article_ids[N-1].
        """
        if not article_ids:
            return []
        
        # Batch query for articles from BigQuery (order-preserving)
        bq_storage = await self._get_bq_storage()
        if bq_storage:
            articles = await bq_storage.get_articles_by_ids(article_ids)
            logger.info(f"Agent 2: Fetched {len(articles)} articles for {len(article_ids)} article_ids (order preserved)")
            return articles
        return []
    
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
    
    def _extract_citation_numbers(self, text: str) -> tuple[List[int], List[int]]:
        """
        Extract citation numbers from text.
        
        Handles both individual citations [N] and comma-separated [N, M, Exa:K].
        
        Returns:
            Tuple of (pre_brief_citations, exa_citations)
            - pre_brief_citations: List of [N] citation numbers (1-indexed)
            - exa_citations: List of [Exa:N] citation numbers (1-indexed)
        """
        pre_brief_citations = []
        exa_citations = []
        
        # First, find all bracket contents (but not double brackets [[Company]])
        # This matches [4], [11], [4,11], [1, 2, Exa:3], etc.
        bracket_pattern = r'\[([^\[\]]+)\](?!\])'
        bracket_contents = re.findall(bracket_pattern, text)
        
        for content in bracket_contents:
            # Split by comma and process each part
            parts = [p.strip() for p in content.split(',')]
            
            for part in parts:
                # Check if it's an Exa citation
                exa_match = re.match(r'Exa:(\d+)', part)
                if exa_match:
                    exa_citations.append(int(exa_match.group(1)))
                    continue
                
                # Check if it's a plain number (pre-brief citation)
                num_match = re.match(r'^(\d+)$', part)
                if num_match:
                    pre_brief_citations.append(int(num_match.group(1)))
        
        return sorted(set(pre_brief_citations)), sorted(set(exa_citations))
    
    def _clean_citation_text(
        self,
        text: str,
        max_pre_brief_articles: int,
        exa_id_to_unified: Dict[int, int]
    ) -> str:
        """
        Clean citation text for final output:
        1. Handle comma-separated citations like [37, Exa:6] or [1, 2, Exa:3]
        2. Remove "Exa:" prefix, converting to unified citation numbers
        3. Filter out invalid pre-brief citation numbers (> max articles)
        
        Args:
            text: Raw text with citations
            max_pre_brief_articles: Maximum valid pre-brief article number (typically 50)
            exa_id_to_unified: Mapping of Exa IDs to unified citation numbers
            
        Returns:
            Cleaned text with unified citation numbers
        """
        # Handle complex bracket contents like [37, Exa:6] or [1, 2, Exa:3]
        def process_bracket_content(match):
            content = match.group(1)
            # Split by comma and process each part
            parts = [p.strip() for p in content.split(',')]
            valid_nums = []
            
            for part in parts:
                # Check if it's an Exa citation
                exa_match = re.match(r'Exa:(\d+)', part)
                if exa_match:
                    exa_num = int(exa_match.group(1))
                    unified = exa_id_to_unified.get(exa_num)
                    if unified:
                        valid_nums.append(str(unified))
                    # Skip if no mapping (don't add invalid Exa refs)
                    continue
                
                # Check if it's a plain number
                num_match = re.match(r'(\d+)', part)
                if num_match:
                    num = int(num_match.group(1))
                    # Keep if valid pre-brief citation OR valid unified Exa number
                    if 1 <= num <= max_pre_brief_articles:
                        valid_nums.append(str(num))
                    elif num in exa_id_to_unified.values():
                        valid_nums.append(str(num))
                    # Skip invalid numbers
            
            if valid_nums:
                return '[' + ', '.join(valid_nums) + ']'
            return ''  # Remove empty brackets
        
        # Match anything in square brackets (but not [[Company]] double brackets)
        text = re.sub(r'\[([^\[\]]+)\](?!\])', process_bracket_content, text)
        
        # Clean up extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def _extract_domain(self, url: str) -> str:
        """
        Extract domain from URL for source attribution.
        
        Examples:
            'https://www.reuters.com/article/...' -> 'reuters.com'
            'https://compositeworld.com/news/...' -> 'compositeworld.com'
        """
        from urllib.parse import urlparse
        try:
            if not url:
                return 'Unknown'
            parsed = urlparse(url)
            domain = parsed.netloc.replace('www.', '')
            return domain or 'Unknown'
        except Exception:
            return 'Unknown'
    
    def _build_source_articles(
        self, 
        articles: List, 
        article_numbers: List[int],
        peripheral_articles: List[Dict[str, Any]] = None,
        exa_numbers: List[int] = None,
        max_pre_brief_num: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Build source article metadata for the articles used in a section.
        
        Args:
            articles: List of article dicts from pre-brief (BigQuery returns dicts)
            article_numbers: List of [N] citation numbers from pre-brief (1-indexed)
            peripheral_articles: List of Exa search results (optional)
            exa_numbers: List of [Exa:N] citation numbers (1-indexed, optional)
            max_pre_brief_num: Number of pre-brief articles for unified numbering
        
        Returns:
            List of source article dicts for the frontend
        """
        source_articles = []
        
        # Add pre-brief articles (articles are dicts from BigQuery)
        for num in article_numbers:
            if 1 <= num <= len(articles):
                a = articles[num - 1]  # Convert to 0-indexed
                url = a.get('url', '')
                # Handle published_at - may be datetime object or string
                pub_at = a.get('published_at')
                if pub_at and hasattr(pub_at, 'isoformat'):
                    pub_at_str = pub_at.isoformat()
                else:
                    pub_at_str = str(pub_at) if pub_at else None
                
                source_articles.append({
                    "article_number": num,
                    "id": a.get('id', ''),
                    "title": a.get('title', 'Unknown'),
                    "url": url,
                    "source_name": self._extract_domain(url),
                    "published_at": pub_at_str,
                })
        
        # Add Exa peripheral search articles with UNIFIED numbering
        # Exa article N becomes citation [max_pre_brief_num + N]
        if peripheral_articles and exa_numbers:
            for exa_num in exa_numbers:
                # Find the Exa article with this ID
                exa_article = next(
                    (p for p in peripheral_articles if p.get('exa_id') == exa_num), 
                    None
                )
                if exa_article:
                    exa_url = exa_article.get('url', '')
                    # Unified citation number = max_pre_brief + exa_id
                    unified_num = max_pre_brief_num + exa_num
                    source_articles.append({
                        "article_number": unified_num,  # Unified numbering matches cleaned text
                        "id": f"exa-{exa_num}",
                        "title": exa_article.get('title', 'Unknown'),
                        "url": exa_url,
                        "source_name": self._extract_domain(exa_url),  # Real domain, not "Exa"
                        "published_at": exa_article.get('published_date'),
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
    
    async def _fetch_voice_enrichment(
        self,
        pre_brief_data: Dict[str, Any],
    ) -> str:
        """
        Fetch voice enrichment data from SEC nuggets, earnings quotes, and podcast quotes.
        
        Strategy: Search by individual COMPANY NAMES (which match ticker/company fields)
        rather than concatenating topics into a single search string (which matches nothing).
        Also searches by individual topic keywords for broader coverage.
        
        Returns a formatted text block for injection into the synthesis prompt.
        """
        # Extract companies and topics from pre-brief observations
        observations = pre_brief_data.get("observations", [])
        topics = set(pre_brief_data.get("raw_topic_list", []))
        companies = set()
        
        for obs in observations:
            for company in obs.get("companies", []):
                companies.add(company)
            for topic in obs.get("related_topics", []):
                topics.add(topic)
        
        if not topics and not companies:
            return "No enrichment data available — pre-brief had no extractable topics or companies."
        
        company_list = list(companies)[:15]
        topic_list = list(topics)[:10]
        
        logger.info(f"Agent 2: Voice enrichment — {len(company_list)} companies, {len(topic_list)} topics")
        logger.info(f"Agent 2: Companies: {company_list}")
        logger.info(f"Agent 2: Topics: {topic_list[:5]}")
        
        enrichment_parts = []
        
        try:
            bq_storage = await self._get_bq_storage()
            if not bq_storage:
                return "Voice enrichment unavailable — BigQuery not configured."
            
            # 1. SEC Filing Nuggets — search by individual company names
            try:
                all_sec_nuggets = []
                seen_nugget_ids = set()
                
                # First: try each company name as a search query (matches ticker, companies_mentioned, etc.)
                for company in company_list[:10]:
                    nuggets = await bq_storage.get_sec_filing_nuggets(
                        search_query=company,
                        min_relevance=0.3,
                        limit=5,
                    )
                    for n in nuggets:
                        nid = n.get("nugget_id", n.get("id", ""))
                        if nid not in seen_nugget_ids:
                            seen_nugget_ids.add(nid)
                            all_sec_nuggets.append(n)
                
                # Also try key topic keywords individually
                for topic in topic_list[:5]:
                    if len(topic) > 3:  # Skip very short/generic terms
                        nuggets = await bq_storage.get_sec_filing_nuggets(
                            search_query=topic,
                            min_relevance=0.3,
                            limit=3,
                        )
                        for n in nuggets:
                            nid = n.get("nugget_id", n.get("id", ""))
                            if nid not in seen_nugget_ids:
                                seen_nugget_ids.add(nid)
                                all_sec_nuggets.append(n)
                
                # Sort by relevance and cap
                all_sec_nuggets.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
                all_sec_nuggets = all_sec_nuggets[:10]
                
                if all_sec_nuggets:
                    sec_parts = ["=== SEC FILING NUGGETS ==="]
                    for nugget in all_sec_nuggets:
                        ticker = nugget.get("ticker", "N/A")
                        filing_type = nugget.get("filing_type", "")
                        nugget_type = nugget.get("nugget_type", "")
                        text = nugget.get("nugget_text", "")
                        signal = nugget.get("signal_strength", "")
                        sec_parts.append(
                            f"[{ticker} / {filing_type}] ({nugget_type}, signal: {signal})\n{text[:300]}"
                        )
                    enrichment_parts.append("\n\n".join(sec_parts))
                    logger.info(f"Agent 2: Found {len(all_sec_nuggets)} SEC nuggets (from {len(seen_nugget_ids)} unique)")
                else:
                    logger.info("Agent 2: No SEC nuggets matched any company or topic")
            except Exception as e:
                logger.warning(f"Agent 2: SEC nugget fetch failed: {e}")
            
            # 2. Earnings Call Quotes — search by individual company names
            try:
                all_earnings_quotes = []
                seen_quote_ids = set()
                
                for company in company_list[:10]:
                    quotes = await bq_storage.get_earnings_quotes(
                        search_query=company,
                        quotable_only=True,
                        min_relevance=0.3,
                        limit=5,
                    )
                    for q in quotes:
                        qid = q.get("quote_id", q.get("id", ""))
                        if qid not in seen_quote_ids:
                            seen_quote_ids.add(qid)
                            all_earnings_quotes.append(q)
                
                # Also try key topics
                for topic in topic_list[:5]:
                    if len(topic) > 3:
                        quotes = await bq_storage.get_earnings_quotes(
                            search_query=topic,
                            quotable_only=True,
                            min_relevance=0.3,
                            limit=3,
                        )
                        for q in quotes:
                            qid = q.get("quote_id", q.get("id", ""))
                            if qid not in seen_quote_ids:
                                seen_quote_ids.add(qid)
                                all_earnings_quotes.append(q)
                
                all_earnings_quotes.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
                all_earnings_quotes = all_earnings_quotes[:10]
                
                if all_earnings_quotes:
                    eq_parts = ["=== EARNINGS CALL QUOTES ==="]
                    for quote in all_earnings_quotes:
                        speaker = quote.get("speaker_name", "Unknown")
                        role = quote.get("speaker_role", "")
                        ticker = quote.get("ticker", "")
                        company = quote.get("company_name", "")
                        text = quote.get("quote_text", "")
                        quarter = quote.get("quarter", "")
                        year = quote.get("year", "")
                        eq_parts.append(
                            f"[{company} ({ticker}) — {speaker}, {role} — Q{quarter} {year}]\n\"{text[:300]}\""
                        )
                    enrichment_parts.append("\n\n".join(eq_parts))
                    logger.info(f"Agent 2: Found {len(all_earnings_quotes)} earnings quotes")
                else:
                    logger.info("Agent 2: No earnings quotes matched any company or topic")
            except Exception as e:
                logger.warning(f"Agent 2: Earnings quote fetch failed: {e}")
            
            # 3. Podcast Expert Quotes — search by theme mapping AND individual company names
            try:
                # Map pre-brief topics to podcast themes
                theme_mapping = {
                    "carbon fiber": "fiber_materials",
                    "glass fiber": "fiber_materials",
                    "resin": "resin_systems",
                    "epoxy": "resin_systems",
                    "wind": "wind_energy",
                    "aerospace": "aerospace_composites",
                    "automotive": "automotive_composites",
                    "sustainability": "sustainability",
                    "supply chain": "supply_chain",
                    "pricing": "pricing",
                    "manufacturing": "manufacturing_processes",
                    "regulatory": "regulatory",
                    "M&A": "competitive",
                    "acquisition": "competitive",
                    "marine": "marine",
                    "construction": "construction",
                    "defense": "defense",
                    "recycling": "sustainability",
                }
                detected_themes = []
                for topic in topics:
                    topic_lower = topic.lower()
                    for keyword, theme in theme_mapping.items():
                        if keyword.lower() in topic_lower:
                            detected_themes.append(theme)
                            break
                detected_themes = list(set(detected_themes))[:5]
                
                all_podcast_quotes = []
                seen_pq_ids = set()
                
                # Search by detected themes
                if detected_themes:
                    quotes = await bq_storage.get_podcast_quotes(
                        themes=detected_themes,
                        days=90,
                        limit=10,
                    )
                    for q in quotes:
                        qid = q.get("quote_id", q.get("id", ""))
                        if qid not in seen_pq_ids:
                            seen_pq_ids.add(qid)
                            all_podcast_quotes.append(q)
                
                # Also search by individual company names
                for company in company_list[:5]:
                    quotes = await bq_storage.get_podcast_quotes(
                        search_query=company,
                        days=90,
                        limit=3,
                    )
                    for q in quotes:
                        qid = q.get("quote_id", q.get("id", ""))
                        if qid not in seen_pq_ids:
                            seen_pq_ids.add(qid)
                            all_podcast_quotes.append(q)
                
                all_podcast_quotes.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
                all_podcast_quotes = all_podcast_quotes[:10]
                
                if all_podcast_quotes:
                    pq_parts = ["=== INDUSTRY PODCAST QUOTES ==="]
                    for quote in all_podcast_quotes:
                        speaker = quote.get("speaker_name", "Unknown")
                        role = quote.get("speaker_role", "")
                        company = quote.get("speaker_company", "")
                        podcast = quote.get("podcast_name", "")
                        text = quote.get("quote_text", "")
                        pq_parts.append(
                            f"[{podcast} — {speaker}, {role} at {company}]\n\"{text[:300]}\""
                        )
                    enrichment_parts.append("\n\n".join(pq_parts))
                    logger.info(f"Agent 2: Found {len(all_podcast_quotes)} podcast quotes")
                else:
                    logger.info("Agent 2: No podcast quotes matched any theme or company")
            except Exception as e:
                logger.warning(f"Agent 2: Podcast quote fetch failed: {e}")
            
        except Exception as e:
            logger.error(f"Agent 2: Voice enrichment failed: {e}", exc_info=True)
        
        if enrichment_parts:
            total = enrichment_parts[0].count('\n') + enrichment_parts[-1].count('\n') if enrichment_parts else 0
            logger.info(f"Agent 2: Voice enrichment complete — {len(enrichment_parts)} categories with data")
            return "\n\n".join(enrichment_parts)
        return "No matching voice enrichment data found for this week's themes. Proceed without voice grounding."

    def _repair_truncated_json(self, raw_text: str) -> str:
        """
        Attempt to repair JSON that was truncated due to max_tokens limit.
        
        Strategy:
        1. Extract JSON start (find the opening '{')
        2. Close any open strings, arrays, and objects
        3. Return something json.loads can parse (even if incomplete)
        """
        # Find the JSON start
        json_text = raw_text
        if "```json" in json_text:
            json_text = json_text.split("```json")[1].split("```")[0].strip()
        elif not json_text.startswith("{"):
            start_idx = json_text.find("{")
            if start_idx != -1:
                json_text = json_text[start_idx:]
            else:
                return raw_text  # No JSON found, return as-is
        
        # Try parsing as-is first (maybe it's fine)
        try:
            json.loads(json_text)
            return json_text
        except json.JSONDecodeError:
            pass
        
        # Attempt repair: close open strings, arrays, objects
        repaired = json_text
        
        # If truncated mid-string, close the string
        # Count unescaped quotes to see if we're inside a string
        in_string = False
        i = 0
        while i < len(repaired):
            ch = repaired[i]
            if ch == '\\' and in_string:
                i += 2  # Skip escaped character
                continue
            if ch == '"':
                in_string = not in_string
            i += 1
        
        if in_string:
            # We're inside an unclosed string - close it
            # Trim trailing incomplete escape sequences
            repaired = repaired.rstrip('\\')
            repaired += '"'
        
        # Count open brackets/braces and close them
        open_braces = 0
        open_brackets = 0
        in_str = False
        i = 0
        while i < len(repaired):
            ch = repaired[i]
            if ch == '\\' and in_str:
                i += 2
                continue
            if ch == '"':
                in_str = not in_str
            if not in_str:
                if ch == '{':
                    open_braces += 1
                elif ch == '}':
                    open_braces -= 1
                elif ch == '[':
                    open_brackets += 1
                elif ch == ']':
                    open_brackets -= 1
            i += 1
        
        # Remove trailing comma before closing
        repaired = repaired.rstrip()
        if repaired.endswith(','):
            repaired = repaired[:-1]
        
        # Close open brackets then braces
        repaired += ']' * max(0, open_brackets)
        repaired += '}' * max(0, open_braces)
        
        # Validate the repair worked
        try:
            json.loads(repaired)
            logger.info(f"Agent 2: JSON repair successful ({len(repaired)} chars, closed {open_brackets} brackets + {open_braces} braces)")
            return repaired
        except json.JSONDecodeError as e:
            logger.warning(f"Agent 2: JSON repair failed: {e}. Will fall through to error handler.")
            return raw_text  # Return original, let the caller handle the error

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
    
    def _format_text_for_speech(self, text: str) -> str:
        """
        Format text for natural speech synthesis.
        
        Removes citations, visual formatting, and expands abbreviations for clarity.
        """
        if not text:
            return ""
        
        # Remove citation markers [1], [2], [Exa:1], and comma-separated [1, Exa:2]
        text = re.sub(r'\[(?:Exa:)?\d+(?:,\s*(?:Exa:)?\d+)*\]', '', text)
        
        # Remove company logo tags [[Company Name]] but keep the name
        text = re.sub(r'\[\[([^\]]+)\]\]', r'\1', text)
        
        # Remove entity highlight tags {{Entity Name}} but keep the name
        text = re.sub(r'\{\{([^}]+)\}\}', r'\1', text)
        
        # Remove markdown bold/italic
        text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
        text = re.sub(r'\*([^*]+)\*', r'\1', text)
        text = re.sub(r'__([^_]+)__', r'\1', text)
        text = re.sub(r'_([^_]+)_', r'\1', text)
        
        # Expand currency: $2.4B -> 2.4 billion dollars
        text = re.sub(r'\$(\d+\.?\d*)B\b', r'\1 billion dollars', text, flags=re.IGNORECASE)
        text = re.sub(r'\$(\d+\.?\d*)M\b', r'\1 million dollars', text, flags=re.IGNORECASE)
        text = re.sub(r'\$(\d+\.?\d*)K\b', r'\1 thousand dollars', text, flags=re.IGNORECASE)
        
        # Expand percentages: 40% -> 40 percent
        text = re.sub(r'(\d+\.?\d*)%', r'\1 percent', text)
        
        # Expand common abbreviations for natural speech
        abbreviations = {
            "M&A": "mergers and acquisitions",
            "YoY": "year over year",
            "QoQ": "quarter over quarter",
            "Q1": "first quarter",
            "Q2": "second quarter",
            "Q3": "third quarter",
            "Q4": "fourth quarter",
            "FY": "fiscal year",
            "CEO": "C E O",
            "CFO": "C F O",
            "COO": "C O O",
            "CMO": "C M O",
            "SEC": "S E C",
            "FDA": "F D A",
            "OEM": "O E M",
            "CFRP": "carbon fiber reinforced polymer",
            "RTM": "resin transfer molding",
            "SMC": "sheet molding compound",
            "BMC": "bulk molding compound",
        }
        for abbr, expansion in abbreviations.items():
            text = re.sub(rf'\b{abbr}\b', expansion, text)
        
        # Clean up multiple spaces and strip
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def _build_podcast_dialogue(self, briefing: Dict[str, Any]) -> List[Dict[str, str]]:
        """
        Build conversational podcast dialogue from briefing data.
        
        Returns a list of dialogue turns: [{"speaker": "host"|"analyst", "text": "..."}]
        Host (Rachel) handles introductions and transitions.
        Analyst (Josh) delivers the content and insights.
        """
        dialogue = []
        
        # 1. Opening - Host introduces the briefing
        title = briefing.get('briefing_title', 'Strategic Intelligence Briefing')
        # Convert "Week of Jan 6" to "Week of January 6th"
        title = re.sub(r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b', 
                      lambda m: {
                          'Jan': 'January', 'Feb': 'February', 'Mar': 'March',
                          'Apr': 'April', 'May': 'May', 'Jun': 'June',
                          'Jul': 'July', 'Aug': 'August', 'Sep': 'September',
                          'Oct': 'October', 'Nov': 'November', 'Dec': 'December'
                      }[m.group(1)], title)
        
        dialogue.append({
            "speaker": "host",
            "text": f"Good morning. Welcome to your {title}. I'm here with our analyst to break down what you need to know."
        })
        
        # 2. BLUF - Analyst delivers the bottom line
        bluf = briefing.get('bluf', '')
        if bluf:
            formatted_bluf = self._format_text_for_speech(bluf)
            dialogue.append({
                "speaker": "host",
                "text": "Let's start with the bottom line."
            })
            dialogue.append({
                "speaker": "analyst",
                "text": formatted_bluf
            })
        
        # 3. Sections - Host introduces, Analyst delivers
        sections = briefing.get('sections', [])
        section_transitions = [
            "Let's dive into our first area of focus.",
            "Moving on to our next topic.",
            "And finally,"
        ]
        
        for idx, section in enumerate(sections):
            section_header = section.get('header', f'Section {idx + 1}')
            
            # Host introduces section
            transition = section_transitions[min(idx, len(section_transitions) - 1)]
            dialogue.append({
                "speaker": "host",
                "text": f"{transition} {section_header}."
            })
            
            # Analyst delivers headline
            headline = section.get('headline', {})
            headline_text = headline.get('text', '') if isinstance(headline, dict) else str(headline)
            headline_status = headline.get('status', 'continuing') if isinstance(headline, dict) else 'continuing'
            
            if headline_text:
                formatted_headline = self._format_text_for_speech(headline_text)
                
                # Add status context naturally
                if headline_status == 'net_new':
                    analyst_text = f"This is a new development. {formatted_headline}"
                else:
                    analyst_text = f"We're continuing to track this. {formatted_headline}"
                
                dialogue.append({
                    "speaker": "analyst",
                    "text": analyst_text
                })
            
            # Analyst delivers insights
            insights = section.get('insights', [])
            if insights:
                insight_texts = []
                voice_insights = []  # Track which insights contain voice attribution
                for insight in insights:
                    insight_text = insight.get('text', '') if isinstance(insight, dict) else str(insight)
                    if insight_text:
                        formatted_insight = self._format_text_for_speech(insight_text)
                        insight_texts.append(formatted_insight)
                        # Detect voice-enriched insights (contain source attribution markers)
                        if any(marker in insight_text for marker in ['(SEC Filing)', '(Earnings Call)', '(Industry Podcast)']):
                            voice_insights.append(formatted_insight)
                
                if insight_texts:
                    # Combine insights into natural flow
                    combined = " ".join(insight_texts)
                    dialogue.append({
                        "speaker": "analyst",
                        "text": combined
                    })
                    
                    # If we had voice-enriched insights, add a host reaction
                    if voice_insights and idx < len(sections) - 1:
                        dialogue.append({
                            "speaker": "host",
                            "text": "That's a strong data point. Hearing it directly from the executives adds real weight to that signal."
                        })
            
            # Host acknowledges after each section (except last)
            if idx < len(sections) - 1:
                acknowledgments = ["Interesting.", "Good to know.", "Thanks for that."]
                dialogue.append({
                    "speaker": "host",
                    "text": acknowledgments[idx % len(acknowledgments)]
                })
        
        # 4. Overall trend - Host asks, Analyst summarizes
        overall_trend = briefing.get('overall_trend', '')
        if overall_trend:
            dialogue.append({
                "speaker": "host",
                "text": "Zooming out, what's the bigger picture here?"
            })
            formatted_trend = self._format_text_for_speech(overall_trend)
            dialogue.append({
                "speaker": "analyst",
                "text": formatted_trend
            })
        
        # 5. Closing - Host wraps up
        dialogue.append({
            "speaker": "host",
            "text": "That's your briefing for this week. Stay sharp, and we'll see you next time."
        })
        
        return dialogue
    
    # =========================================================================
    # Dialogue Naturalization (LLM Rewriting)
    # =========================================================================
    
    NATURALIZATION_PROMPT = """You are a podcast script editor. Your job is to transform a structured briefing script into natural, conversational dialogue between two speakers.

**Speakers:**
- **Host**: A sharp, curious business podcast host. Asks follow-up questions, reacts to interesting points, occasionally interjects with "wait, say more about that" or "that's significant."
- **Analyst**: An industry expert who sounds knowledgeable but approachable. Uses natural speech patterns - occasional "so", "well", "actually", "you know what's interesting..."

**Your task:**
1. Keep ALL the factual content and data points - don't lose any information
2. Make it sound like a real conversation, not a script being read
3. Add natural reactions, brief acknowledgments, and occasional back-and-forth
4. Break up long monologues with host interjections or questions
5. Vary the energy - some moments more casual, others more emphatic on key insights
6. Add subtle filler words that real speakers use (sparingly)
7. Keep total length similar to input (don't pad excessively)

**Voice Enrichment Handling:**
The script may contain executive quotes, SEC filing references, or expert podcast quotes that were woven into the insights. These are EXTREMELY valuable — they ground the analysis in real authority.
- PRESERVE the substance and attribution of any executive/expert quotes verbatim. Do not paraphrase quotes.
- Make them sound natural: e.g., "And here's where it gets interesting — the CFO actually said, and I quote, '...'" or "One of the executives put it really well when they said..."
- The host should react to strong quotes: "That's a telling statement" or "That's pretty direct from management."
- Attribute the source naturally: "from their latest earnings call", "in the SEC filing", "on a recent industry podcast"

**Rules:**
- Output ONLY valid JSON array of objects with "speaker" and "text" keys
- Speaker must be exactly "host" or "analyst" (lowercase)
- Preserve the general flow: opening → BLUF → themes → closing
- Don't add fabricated facts or statistics
- Keep it professional but warm

**Input script:**
{dialogue_json}

**Output the naturalized dialogue as a JSON array:**"""
    
    async def _naturalize_dialogue(
        self,
        dialogue: List[Dict[str, str]],
        max_retries: int = 2,
    ) -> List[Dict[str, str]]:
        """
        Use Claude to rewrite structured dialogue into natural conversation.
        
        Takes the deterministic scaffold from _build_podcast_dialogue() and
        rewrites it to sound like a real podcast conversation with natural
        reactions, interjections, and varied energy.
        
        Falls back to original dialogue if naturalization fails.
        """
        api_key = getattr(self.config, 'anthropic_api_key', None) or os.getenv('ANTHROPIC_API_KEY', '')
        if not api_key:
            logger.warning("[PODCAST] No Anthropic API key - skipping dialogue naturalization")
            return dialogue
        
        dialogue_json = json.dumps(dialogue, indent=2)
        prompt = self.NATURALIZATION_PROMPT.format(dialogue_json=dialogue_json)
        
        for attempt in range(max_retries):
            try:
                logger.info(f"[PODCAST] Naturalizing dialogue (attempt {attempt + 1}/{max_retries}, {len(dialogue)} turns)")
                start_time = time.time()
                
                response = await self.client.messages_create(
                    model="claude-sonnet-4-6",
                    max_tokens=8000,
                    messages=[
                        {"role": "user", "content": prompt}
                    ],
                    _caller="weekly_briefing_podcast_naturalizer"
                )
                
                elapsed = time.time() - start_time
                
                # Extract the response text
                response_text = response.content[0].text.strip()
                
                # Parse JSON - handle potential markdown code blocks
                if response_text.startswith("```"):
                    lines = response_text.split("\n")
                    json_lines = []
                    in_block = False
                    for line in lines:
                        if line.startswith("```") and not in_block:
                            in_block = True
                            continue
                        elif line.startswith("```") and in_block:
                            break
                        elif in_block:
                            json_lines.append(line)
                    response_text = "\n".join(json_lines)
                
                naturalized = json.loads(response_text)
                
                # Validate structure
                if not isinstance(naturalized, list):
                    raise ValueError("Response is not a list")
                
                for turn in naturalized:
                    if not isinstance(turn, dict):
                        raise ValueError("Turn is not a dict")
                    if "speaker" not in turn or "text" not in turn:
                        raise ValueError("Turn missing speaker or text")
                    if turn["speaker"] not in ("host", "analyst"):
                        raise ValueError(f"Invalid speaker: {turn['speaker']}")
                
                logger.info(f"[PODCAST] Naturalized dialogue: {len(dialogue)} → {len(naturalized)} turns in {elapsed:.2f}s")
                return naturalized
                
            except json.JSONDecodeError as e:
                logger.warning(f"[PODCAST] JSON parse error on attempt {attempt + 1}: {e}")
            except Exception as e:
                logger.warning(f"[PODCAST] Naturalization error on attempt {attempt + 1}: {e}")
            
            if attempt < max_retries - 1:
                await asyncio.sleep(1)
        
        # Fallback to original dialogue
        logger.warning("[PODCAST] Naturalization failed after all retries, using original dialogue")
        return dialogue
    
    async def _generate_podcast(self, briefing: Dict[str, Any], briefing_id: str) -> Optional[Dict[str, Any]]:
        """
        Generate conversational podcast audio from briefing data using ElevenLabs Text-to-Dialogue API.
        
        Uses two voices (Host: Rachel, Analyst: Josh) for a natural dialogue.
        Single API call handles all speaker transitions smoothly.
        
        Returns:
            Dict with {podcast_url, podcast_duration_seconds, podcast_generated_at}
            or None if generation fails.
        """
        import httpx
        
        elevenlabs_api_key = getattr(self.config, 'elevenlabs_api_key', None)
        if not elevenlabs_api_key:
            logger.warning("ElevenLabs API key not configured - skipping podcast generation")
            return None
        
        try:
            logger.info(f"Starting podcast generation for briefing {briefing_id}")
            start_time = time.time()
            
            # 1. Build podcast dialogue scaffold (deterministic structure)
            dialogue = self._build_podcast_dialogue(briefing)
            logger.info(f"[PODCAST] Built dialogue scaffold ({len(dialogue)} turns)")
            
            # 2. Naturalize dialogue using LLM (makes it conversational)
            dialogue = await self._naturalize_dialogue(dialogue)
            
            total_words = sum(len(turn["text"].split()) for turn in dialogue)
            logger.info(f"[PODCAST] Final dialogue: {len(dialogue)} turns, ~{total_words} words")
            
            # 2. Convert dialogue to ElevenLabs Text-to-Dialogue format and chunk
            # ElevenLabs text-to-dialogue has a 5000 char limit per request
            CHAR_LIMIT = 4800  # Leave margin below 5000
            
            all_inputs = []
            for turn in dialogue:
                voice_id = self.host_voice_id if turn["speaker"] == "host" else self.analyst_voice_id
                all_inputs.append({
                    "text": turn["text"],
                    "voice_id": voice_id
                })
            
            total_chars = sum(len(inp["text"]) for inp in all_inputs)
            logger.info(f"[PODCAST] Total dialogue chars: {total_chars} (limit per call: {CHAR_LIMIT})")
            
            # Split inputs into chunks that fit within the character limit
            chunks = []
            current_chunk = []
            current_chars = 0
            for inp in all_inputs:
                inp_chars = len(inp["text"])
                if current_chunk and current_chars + inp_chars > CHAR_LIMIT:
                    chunks.append(current_chunk)
                    current_chunk = [inp]
                    current_chars = inp_chars
                else:
                    current_chunk.append(inp)
                    current_chars += inp_chars
            if current_chunk:
                chunks.append(current_chunk)
            
            logger.info(f"[PODCAST] Split into {len(chunks)} API chunks: {[sum(len(i['text']) for i in c) for c in chunks]} chars each")
            
            # 3. Call ElevenLabs Text-to-Dialogue API for each chunk
            audio_segments = []
            max_retries = 3
            
            for chunk_idx, chunk_inputs in enumerate(chunks):
                retry_delay = 2
                chunk_audio = None
                
                for attempt in range(max_retries):
                    try:
                        logger.info(f"Calling ElevenLabs API chunk {chunk_idx + 1}/{len(chunks)} (attempt {attempt + 1}/{max_retries}, {sum(len(i['text']) for i in chunk_inputs)} chars)")
                        
                        async with httpx.AsyncClient(timeout=300.0) as client:
                            response = await client.post(
                                "https://api.elevenlabs.io/v1/text-to-dialogue",
                                headers={
                                    "xi-api-key": elevenlabs_api_key,
                                    "Content-Type": "application/json"
                                },
                                json={
                                    "inputs": chunk_inputs,
                                    "model_id": "eleven_v3",
                                    "apply_text_normalization": "on"
                                }
                            )
                            
                            if response.status_code == 200:
                                chunk_audio = response.content
                                logger.info(f"Chunk {chunk_idx + 1}/{len(chunks)} generated ({len(chunk_audio)} bytes)")
                                break
                            elif response.status_code == 429:
                                logger.warning(f"Rate limited by ElevenLabs, retrying in {retry_delay}s...")
                                if attempt < max_retries - 1:
                                    await asyncio.sleep(retry_delay)
                                    retry_delay *= 2
                                    continue
                            else:
                                logger.error(f"ElevenLabs API error: {response.status_code} - {response.text}")
                                if attempt < max_retries - 1:
                                    await asyncio.sleep(retry_delay)
                                    retry_delay *= 2
                                    continue
                                
                    except httpx.TimeoutException as e:
                        logger.error(f"ElevenLabs API timeout after 300s: {type(e).__name__}")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(retry_delay)
                            retry_delay *= 2
                            continue
                        raise
                    except Exception as e:
                        logger.error(f"Error calling ElevenLabs API: {type(e).__name__}: {e}")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(retry_delay)
                            retry_delay *= 2
                            continue
                        raise
                
                if not chunk_audio:
                    logger.error(f"Failed to generate audio for chunk {chunk_idx + 1} after all retries")
                    return None
                
                audio_segments.append(chunk_audio)
            
            # Concatenate MP3 segments (MP3 frames are self-contained, simple concat works)
            audio_data = b"".join(audio_segments)
            logger.info(f"[PODCAST] Combined {len(audio_segments)} segments: {len(audio_data)} bytes total")
            
            # 4. Upload to Google Cloud Storage
            from google.cloud import storage
            
            if self._gcs_client is None:
                self._gcs_client = storage.Client(project=self.config.gcp_project_id)
            if self._gcs_bucket is None:
                self._gcs_bucket = self._gcs_client.bucket(self.config.gcs_bucket_name)
            
            blob_name = f"podcasts/{briefing_id}.mp3"
            blob = self._gcs_bucket.blob(blob_name)
            
            blob.upload_from_string(audio_data, content_type='audio/mpeg')
            
            # Construct public URL (bucket has allUsers read access)
            podcast_url = f"https://storage.googleapis.com/{self.config.gcs_bucket_name}/{blob_name}"
            logger.info(f"Uploaded podcast to GCS: {podcast_url}")
            
            # 5. Calculate duration (approximate: 150 words/min)
            duration_seconds = int((total_words / 150) * 60)
            
            generation_time = time.time() - start_time
            logger.info(f"Podcast generation complete in {generation_time:.2f}s (estimated {duration_seconds}s audio)")
            
            return {
                "podcast_url": podcast_url,
                "podcast_duration_seconds": duration_seconds,
                "podcast_generated_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to generate podcast: {e}", exc_info=True)
            return None

    async def generate(
        self, 
        pre_brief: Dict[str, Any] = None,
        target_week_monday: datetime = None
    ) -> Optional[Dict[str, Any]]:
        """
        Agent 2: Generate the final high-conviction executive briefing.
        
        Enhanced with peripheral intelligence search capability.
        
        Args:
            pre_brief: Optional pre-brief data (if not provided, fetches latest)
            target_week_monday: Override the "Week of" date for backfilling.
                If provided, uses this date instead of calculating this week's Monday.
                Should be a Monday at 12:00 UTC.
        
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
        
        # 4. Fetch voice enrichment (SEC nuggets, earnings quotes, podcast quotes)
        enrichment_context = await self._fetch_voice_enrichment(
            pre_brief.get('data', {})
        )
        logger.info(f"Agent 2: Voice enrichment context length: {len(enrichment_context)} chars")
        
        # 5. Peripheral intelligence gathering loop
        peripheral_results = []
        max_iterations = 5  # Allow thorough research while preventing infinite loops
        iteration = 0
        scratchpad_notes = []  # Accumulates Agent 2's notes across iterations
        
        period_end = pre_brief.get('period_end')
        if isinstance(period_end, str):
            period_end = datetime.fromisoformat(period_end)
        
        # Determine the "Week of" date for the briefing title
        if target_week_monday:
            # Use explicit target date (for backfilling)
            week_of_date = target_week_monday.strftime("%B %d, %Y")
            logger.info(f"Agent 2: Using target 'Week of {week_of_date}' for backfill briefing")
        else:
            # Calculate this week's Monday for current runs
            today = datetime.utcnow()
            days_since_monday = today.weekday()  # 0=Monday, 6=Sunday
            this_weeks_monday = today - timedelta(days=days_since_monday)
            week_of_date = this_weeks_monday.strftime("%B %d, %Y")  # e.g., "January 06, 2026"
            logger.info(f"Agent 2: Using 'Week of {week_of_date}' for briefing title (today={today.strftime('%A %B %d')})")
        
        data = None
        result_json = None
        
        while iteration < max_iterations:
            iteration += 1
            is_final_iteration = (iteration == max_iterations)
            logger.info(f"Agent 2: Synthesis iteration {iteration}/{max_iterations} (final={is_final_iteration})")
            
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
            
            # Format scratchpad notes for prompt
            scratchpad_text = "No notes yet - this is your first iteration."
            if scratchpad_notes:
                scratchpad_text = "\n---\n".join([f"[Iteration {i+1}]: {note}" for i, note in enumerate(scratchpad_notes)])
            
            # Final iteration warning - force LLM to produce final output
            final_iteration_warning = ""
            if is_final_iteration:
                final_iteration_warning = """
**FINAL ITERATION WARNING**: This is your LAST iteration. You MUST produce the final briefing JSON now.
Do NOT request any more tool calls. Use the peripheral search results you have gathered to produce a comprehensive briefing.
Your response MUST be the final JSON briefing format, NOT a tool_calls request.
"""
                logger.info("Agent 2: Final iteration - forcing final output")
            
            # 5. Prepare prompt with current context
            # Use this week's Monday for consistent title regardless of when generated
            prompt = self.EXECUTIVE_SYNTHESIZER_PROMPT.format(
                period_end_short=week_of_date,
                historical_context=historical_context,
                pre_brief_data=json.dumps(pre_brief.get('data', {}), indent=2),
                enrichment_context=enrichment_context,
                peripheral_results=peripheral_results_text,
                scratchpad=scratchpad_text,
                final_iteration_warning=final_iteration_warning
            )
            
            try:
                synthesis_max_tokens = 8192
                logger.info(f"Agent 2: Calling LLM model={self.model}, max_tokens={synthesis_max_tokens}")
                response = await self.client.messages_create(
                    model=self.model,
                    max_tokens=synthesis_max_tokens,
                    messages=[{"role": "user", "content": prompt}],
                    _caller="weekly_briefing_agent"
                )
                
                # Log response metadata for debugging
                stop_reason = getattr(response, 'stop_reason', 'unknown')
                usage = getattr(response, 'usage', None)
                logger.info(f"Agent 2: LLM response received - stop_reason={stop_reason}, usage={usage}")
                
                # Check if we got any content
                if not response.content or len(response.content) == 0:
                    logger.error(f"Agent 2: LLM returned empty content! stop_reason={stop_reason}")
                    return None
                
                result_json = response.content[0].text.strip()
                logger.info(f"Agent 2: Raw response length={len(result_json)} chars")
                
                # Handle max_tokens truncation - try to repair JSON before giving up
                if stop_reason == "max_tokens":
                    logger.warning(f"Agent 2: Response truncated (stop_reason=max_tokens, {len(result_json)} chars). Attempting JSON repair...")
                    result_json = self._repair_truncated_json(result_json)
                
                # Log first/last bits for debugging (avoid logging full response)
                if len(result_json) < 100:
                    logger.warning(f"Agent 2: Short response - full content: {result_json}")
                else:
                    logger.info(f"Agent 2: Response preview: {result_json[:200]}...")
                
                # Extract JSON from various formats
                if "```json" in result_json:
                    result_json = result_json.split("```json")[1].split("```")[0].strip()
                elif "```" in result_json and "{" in result_json:
                    # Handle ```\n{...}\n``` without json marker
                    parts = result_json.split("```")
                    for part in parts:
                        part = part.strip()
                        if part.startswith("{"):
                            result_json = part
                            break
                elif not result_json.startswith("{"):
                    # Try to find JSON object in the response
                    start_idx = result_json.find("{")
                    if start_idx != -1:
                        logger.info(f"Agent 2: Found JSON starting at char {start_idx}")
                        result_json = result_json[start_idx:]
                
                data = json.loads(result_json)
                
                # Check if Agent 2 wants to make tool calls (only allow if not final iteration)
                if "tool_calls" in data and not is_final_iteration:
                    tool_calls = data["tool_calls"]
                    logger.info(f"Agent 2: Requesting {len(tool_calls)} tool calls")
                    
                    # Extract and save scratchpad notes if provided
                    if "scratchpad_notes" in data:
                        scratchpad_notes.append(data["scratchpad_notes"])
                        logger.info(f"Agent 2: Scratchpad updated with notes from iteration {iteration}")
                    
                    # Limit to 3 tool calls per iteration
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
                elif "tool_calls" in data and is_final_iteration:
                    # Final iteration but LLM still wants tool calls - log warning and strip them
                    logger.warning(f"Agent 2: Final iteration but received tool_calls - stripping and proceeding with available data")
                    del data["tool_calls"]
                    # Fall through to break and process what we have
                
                # No tool calls or max iterations reached - proceed with final synthesis
                break
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse Agent 2 response: {e}")
                # Log at ERROR level so it's visible in production
                raw_preview = result_json[:1000] if result_json else 'EMPTY/NONE'
                logger.error(f"Agent 2: Raw response that failed to parse: {raw_preview}")
                
                # If this was a truncation issue and we haven't exhausted iterations, retry
                if stop_reason == "max_tokens" and iteration < max_iterations:
                    logger.warning(f"Agent 2: JSON parse failed due to truncation - retrying iteration {iteration} as continuation")
                    continue
                return None
            except Exception as e:
                logger.error(f"Error in Agent 2 synthesis iteration: {e}", exc_info=True)
                return None
        
        # Process final briefing data
        if not data:
            logger.error("Agent 2: No data produced after iterations")
            return None
        
        if "tool_calls" in data:
            logger.error("Agent 2: Final data still contains tool_calls - this should have been stripped")
            return None
        
        if "sections" not in data or not data["sections"]:
            logger.error(f"Agent 2: Final data missing required 'sections' field. Keys present: {list(data.keys())}")
            return None
        
        try:
            # Build unified citation mapping for Exa articles
            # Exa citations will be renumbered starting after pre-brief articles
            max_pre_brief_num = len(articles)  # e.g., 50
            exa_id_to_unified = {}
            for p in peripheral_results:
                exa_id = p.get('exa_id')
                if exa_id:
                    # Assign unified number: max_pre_brief + exa_id
                    exa_id_to_unified[exa_id] = max_pre_brief_num + exa_id
            
            logger.info(f"Agent 2: Citation mapping - {max_pre_brief_num} pre-brief articles, {len(exa_id_to_unified)} Exa articles")
            
            # Process sections and add logos + source articles
            processed_sections = []
            for section in data.get("sections", []):
                # Aggregate companies for logo enrichment
                section_companies = set()
                headline = section.get("headline", {})
                section_companies.update(headline.get("companies_mentioned", []))
                for insight in section.get("insights", []):
                    section_companies.update(insight.get("companies_mentioned", []))
                
                # Extract citation numbers from section text (before cleanup)
                all_section_text = headline.get("text", "")
                for insight in section.get("insights", []):
                    all_section_text += " " + insight.get("text", "")
                
                pre_brief_citations, exa_citations = self._extract_citation_numbers(all_section_text)
                
                # Filter pre_brief_citations to only valid numbers
                valid_pre_brief_citations = [n for n in pre_brief_citations if 1 <= n <= max_pre_brief_num]
                if len(valid_pre_brief_citations) < len(pre_brief_citations):
                    invalid = [n for n in pre_brief_citations if n not in valid_pre_brief_citations]
                    logger.warning(f"Agent 2: Filtered out invalid citations {invalid} (max={max_pre_brief_num})")
                
                # Build source articles for this section
                section_source_articles = self._build_source_articles(
                    articles=articles,
                    article_numbers=valid_pre_brief_citations,
                    peripheral_articles=peripheral_results,
                    exa_numbers=exa_citations,
                    max_pre_brief_num=max_pre_brief_num
                )
                
                # Clean up citation text in headline and insights
                # This removes "Exa:" prefix and filters invalid citations
                cleaned_headline = headline.copy() if isinstance(headline, dict) else {"text": str(headline)}
                if "text" in cleaned_headline:
                    cleaned_headline["text"] = self._clean_citation_text(
                        cleaned_headline["text"], 
                        max_pre_brief_num, 
                        exa_id_to_unified
                    )
                
                cleaned_insights = []
                for insight in section.get("insights", []):
                    cleaned_insight = insight.copy() if isinstance(insight, dict) else {"text": str(insight)}
                    if "text" in cleaned_insight:
                        cleaned_insight["text"] = self._clean_citation_text(
                            cleaned_insight["text"],
                            max_pre_brief_num,
                            exa_id_to_unified
                        )
                    cleaned_insights.append(cleaned_insight)
                
                logger.info(
                    f"Agent 2: Section '{section.get('header', 'Update')}' — "
                    f"{len(valid_pre_brief_citations)} pre-brief citations, "
                    f"{len(exa_citations)} exa citations, "
                    f"{len(section_source_articles)} source articles built"
                )
                
                processed_sections.append({
                    "header": section.get("header", "Update"),
                    "headline": cleaned_headline,
                    "insights": cleaned_insights,
                    "companies_with_logos": self._enrich_with_logos(list(section_companies)),
                    "source_articles": section_source_articles,
                })
            
            # Build the complete briefing record
            # ALWAYS use calculated Monday date for title (LLM often gets it wrong)
            forced_title = f"Strategic Intelligence Briefing: Week of {week_of_date}"
            llm_title = data.get("briefing_title", "")
            if llm_title and llm_title != forced_title:
                logger.info(f"Agent 2: Overriding LLM title '{llm_title}' with '{forced_title}'")
            
            briefing_record = {
                "id": str(uuid.uuid4()),
                "briefing_type": "weekly_executive",
                "briefing_title": forced_title,
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
            
            # Generate podcast audio
            podcast_metadata = await self._generate_podcast(briefing_record, briefing_record["id"])
            if podcast_metadata:
                briefing_record.update(podcast_metadata)
                logger.info(f"Podcast added to briefing: {podcast_metadata['podcast_url']}")
            else:
                logger.warning("Podcast generation failed or skipped - briefing will be saved without podcast")
            
            # Save to storage - this MUST succeed for the briefing to be valid
            logger.info(f"Agent 2: About to save briefing {briefing_record['id']}")
            save_success = await self._save_briefing(briefing_record)
            
            if not save_success:
                logger.error(f"Agent 2: CRITICAL - Briefing {briefing_record['id']} was NOT saved to BigQuery!")
                # Return None to indicate failure to the scheduler
                return None
            
            logger.info(f"Agent 2: Synthesis complete. Generated {len(processed_sections)} strategic sections.")
            return briefing_record
            
        except Exception as e:
            logger.error(f"Error in Agent 2 synthesis: {e}", exc_info=True)
            return None
    
    async def _save_briefing(self, briefing: Dict[str, Any]) -> bool:
        """Save briefing to BigQuery.
        
        Returns:
            True if save succeeded, False otherwise
        
        Raises:
            Exception: Re-raises any BigQuery errors after logging
        """
        try:
            bq_storage = await self._get_bq_storage()
            if bq_storage:
                # Log briefing structure for debugging
                logger.info(f"[SAVE] Attempting to save briefing {briefing.get('id')}")
                logger.info(f"[SAVE] Sections count: {len(briefing.get('sections', []))}")
                logger.info(f"[SAVE] Article count: {briefing.get('article_count')}")
                
                success = await bq_storage.save_weekly_briefing(briefing)
                if success:
                    logger.info(f"[SAVE] SUCCESS - Saved weekly briefing {briefing.get('id')} to BigQuery")
                    return True
                else:
                    logger.error(f"[SAVE] FAILED - save_weekly_briefing returned False for {briefing.get('id')}")
                    return False
            else:
                logger.error("[SAVE] BigQuery storage not available - briefing NOT saved!")
                return False
        except Exception as e:
            logger.error(f"[SAVE] EXCEPTION while saving briefing to BigQuery: {e}", exc_info=True)
            raise  # Re-raise so caller knows save failed


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
