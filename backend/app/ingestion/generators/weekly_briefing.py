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
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Set
from collections import Counter
from exa_py import Exa

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
        self.client = get_resilient_async_client(
            anthropic_api_key=self.config.anthropic_api_key,
            openai_api_key=getattr(self.config, 'openai_api_key', None),
        )
        # Agent 2 uses the premium Opus model for strategic synthesis
        self.model = "claude-opus-4-5" 
        self._bq_storage = None
        self._vector_store = None
        # Initialize Exa client for peripheral intelligence search
        exa_api_key = getattr(self.config, 'exa_api_key', None)
        self.exa_client = Exa(exa_api_key) if exa_api_key else None
        if not self.exa_client:
            logger.warning("Exa API key not configured - peripheral search disabled")
        
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
        """Get the full article objects for those referenced in the pre-brief."""
        if not article_ids:
            return []
        
        # Batch query for articles from BigQuery
        bq_storage = await self._get_bq_storage()
        if bq_storage:
            articles = await bq_storage.get_articles_by_ids(article_ids)
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
        
        Returns:
            Tuple of (pre_brief_citations, exa_citations)
            - pre_brief_citations: List of [N] citation numbers (1-indexed)
            - exa_citations: List of [Exa:N] citation numbers (1-indexed)
        """
        # Match [1], [2], etc. but NOT [[Company]] or [Exa:N]
        pre_brief_pattern = r'\[(\d+)\](?!\])'
        pre_brief_citations = [int(m) for m in re.findall(pre_brief_pattern, text)]
        
        # Match [Exa:1], [Exa:2], etc.
        exa_pattern = r'\[Exa:(\d+)\]'
        exa_citations = [int(m) for m in re.findall(exa_pattern, text)]
        
        return sorted(set(pre_brief_citations)), sorted(set(exa_citations))
    
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
        exa_numbers: List[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Build source article metadata for the articles used in a section.
        
        Args:
            articles: List of article dicts from pre-brief (BigQuery returns dicts)
            article_numbers: List of [N] citation numbers from pre-brief (1-indexed)
            peripheral_articles: List of Exa search results (optional)
            exa_numbers: List of [Exa:N] citation numbers (1-indexed, optional)
        
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
        
        # Add Exa peripheral search articles
        if peripheral_articles and exa_numbers:
            for num in exa_numbers:
                # Find the Exa article with this ID
                exa_article = next(
                    (p for p in peripheral_articles if p.get('exa_id') == num), 
                    None
                )
                if exa_article:
                    exa_url = exa_article.get('url', '')
                    source_articles.append({
                        "article_number": num,  # Unified numbering, no "Exa:" prefix for frontend
                        "id": f"exa-{num}",
                        "title": exa_article.get('title', 'Unknown'),
                        "url": exa_url,
                        "source_name": self._extract_domain(exa_url),  # Real domain, not "Exa Research"
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
        
        Removes citations and formatting, expands abbreviations for clarity.
        """
        # Remove citation markers [1], [2], [Exa:1]
        text = re.sub(r'\[(?:Exa:)?\d+\]', '', text)
        
        # Remove company logo tags [[Company Name]] but keep the name
        text = re.sub(r'\[\[([^\]]+)\]\]', r'\1', text)
        
        # Expand currency: $2.4B -> 2.4 billion dollars
        text = re.sub(r'\$(\d+\.?\d*)B\b', r'\1 billion dollars', text, flags=re.IGNORECASE)
        text = re.sub(r'\$(\d+\.?\d*)M\b', r'\1 million dollars', text, flags=re.IGNORECASE)
        
        # Expand percentages: 40% -> 40 percent
        text = re.sub(r'(\d+\.?\d*)%', r'\1 percent', text)
        
        # Clean up any double spaces
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
        title = briefing.get('briefing_title', 'Executive Briefing')
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
                for insight in insights:
                    insight_text = insight.get('text', '') if isinstance(insight, dict) else str(insight)
                    if insight_text:
                        formatted_insight = self._format_text_for_speech(insight_text)
                        insight_texts.append(formatted_insight)
                
                if insight_texts:
                    # Combine insights into natural flow
                    combined = " ".join(insight_texts)
                    dialogue.append({
                        "speaker": "analyst",
                        "text": combined
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
            
            # 1. Build podcast dialogue (list of turns)
            dialogue = self._build_podcast_dialogue(briefing)
            total_words = sum(len(turn["text"].split()) for turn in dialogue)
            logger.info(f"Generated podcast dialogue ({len(dialogue)} turns, ~{total_words} words)")
            
            # 2. Convert dialogue to ElevenLabs Text-to-Dialogue format
            inputs = []
            for turn in dialogue:
                voice_id = self.host_voice_id if turn["speaker"] == "host" else self.analyst_voice_id
                inputs.append({
                    "text": turn["text"],
                    "voice_id": voice_id
                })
            
            # 3. Call ElevenLabs Text-to-Dialogue API (single call for entire conversation)
            max_retries = 3
            retry_delay = 2
            audio_data = None
            
            for attempt in range(max_retries):
                try:
                    logger.info(f"Calling ElevenLabs Text-to-Dialogue API (attempt {attempt + 1}/{max_retries})")
                    
                    async with httpx.AsyncClient(timeout=120.0) as client:
                        response = await client.post(
                            "https://api.elevenlabs.io/v1/text-to-dialogue",
                            headers={
                                "xi-api-key": elevenlabs_api_key,
                                "Content-Type": "application/json"
                            },
                            json={
                                "inputs": inputs,
                                "model_id": "eleven_v3",
                                "apply_text_normalization": "on"
                            }
                        )
                        
                        if response.status_code == 200:
                            audio_data = response.content
                            logger.info(f"Generated dialogue audio ({len(audio_data)} bytes)")
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
                            
                except Exception as e:
                    logger.error(f"Error calling ElevenLabs API: {e}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                    raise
            
            if not audio_data:
                logger.error("Failed to generate audio after all retries")
                return None
            
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
                response = await self.client.messages_create(
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
            # Process sections and add logos + source articles
            processed_sections = []
            for section in data.get("sections", []):
                # Aggregate companies for logo enrichment
                section_companies = set()
                headline = section.get("headline", {})
                section_companies.update(headline.get("companies_mentioned", []))
                for insight in section.get("insights", []):
                    section_companies.update(insight.get("companies_mentioned", []))
                
                # Extract citation numbers from section text
                all_section_text = headline.get("text", "")
                for insight in section.get("insights", []):
                    all_section_text += " " + insight.get("text", "")
                
                pre_brief_citations, exa_citations = self._extract_citation_numbers(all_section_text)
                
                # Build source articles for this section
                section_source_articles = self._build_source_articles(
                    articles=articles,
                    article_numbers=pre_brief_citations,
                    peripheral_articles=peripheral_results,
                    exa_numbers=exa_citations
                )
                
                processed_sections.append({
                    "header": section.get("header", "Update"),
                    "headline": headline,
                    "insights": section.get("insights", []),
                    "companies_with_logos": self._enrich_with_logos(list(section_companies)),
                    "source_articles": section_source_articles,
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
