"""
Pre-Brief Generator (Agent 1)
=============================

This agent performs the initial analysis of the last 14 days of news.
It produces a structured "Pre-Brief" that contains raw intelligence,
topic evolution signals, and detailed observations.

This output is stored in the `pre_briefings` table and is consumed by 
Agent 2 (Executive Synthesizer) to produce the final High-Conviction Briefing.

Model: claude-3-5-sonnet-20241022
Window: 14 days
"""

import uuid
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from app.utils.resilient_llm import get_resilient_async_client
from app.config.settings import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

class PreBriefGenerator:
    """
    Agent 1: Analyzes 14 days of articles to create a raw intermediate "Pre-Brief".
    """
    
    PRE_BRIEF_PROMPT = """You are a senior intelligence analyst. Analyze the following articles from the last 14 days and produce a structured Pre-Brief.

<context>
Period: {period_start} to {period_end}
Total articles: {article_count}
</context>

<articles>
{articles_text}
</articles>

INSTRUCTIONS:
1. Identify all significant developments in the composites industry.
2. Group them into: "Suppliers and Competitors", "End Customers and OEMs", "Materials and Products", "Supply Chain".
3. For each observation, determine if it's "net_new", "evolution", or "stalled".
4. Assign a confidence score (0.0 - 1.0).

OUTPUT FORMAT:
You must respond with a single, valid JSON object. Do not include any text before or after the JSON.
{{
    "observations": [
        {{
            "category": "Suppliers and Competitors",
            "summary": "Full factual summary of the development",
            "companies": ["Company name"],
            "signal_type": "net_new",
            "confidence": 0.9,
            "related_topics": ["Topic A"],
            "article_numbers": [1]
        }}
    ],
    "raw_topic_list": ["topic1"]
}}"""

    def __init__(self, config=None):
        self.config = config or settings
        self.client = get_resilient_async_client(
            anthropic_api_key=self.config.anthropic_api_key,
            openai_api_key=getattr(self.config, 'openai_api_key', None),
        )
        self.model = "claude-sonnet-4-5"
        self._bq_storage = None

    async def _get_bq_storage(self):
        if self._bq_storage is None:
            try:
                from app.db.gcp_storage import BigQueryDataStorage, gcp_config
                if gcp_config.is_configured:
                    self._bq_storage = BigQueryDataStorage(gcp_config)
                    await self._bq_storage.initialize()
            except Exception as e:
                logger.warning(f"Could not initialize BigQuery storage: {e}")
        return self._bq_storage

    def _get_this_weeks_monday(self) -> datetime:
        """
        Get the Monday of the current week (most recent Monday).
        
        This ensures that executive briefings always reference the same week,
        regardless of when they're run (manual vs scheduled).
        
        Convention: "Week of [Monday date]" (e.g., "Week of Jan 6")
        
        Returns:
            datetime: This week's Monday at midnight UTC
        """
        today = datetime.utcnow()
        # Python weekday(): Monday=0, Tuesday=1, ..., Sunday=6
        # So weekday() directly gives us days since Monday
        days_since_monday = today.weekday()
        this_monday = today - timedelta(days=days_since_monday)
        # Reset to start of day (midnight UTC)
        return this_monday.replace(hour=0, minute=0, second=0, microsecond=0)

    async def _get_articles(
        self, 
        days: int = 14,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> tuple:
        """
        Fetch articles from BigQuery for the specified period.
        
        Args:
            days: Number of days to look back (used if start_date/end_date not provided)
            start_date: Custom period start (for historical pre-briefings)
            end_date: Custom period end (for historical pre-briefings)
            
        Returns:
            tuple: (articles, period_start, period_end)
        """
        # Determine period
        if start_date and end_date:
            period_start = start_date
            period_end = end_date
        else:
            # Use this week's Monday as the reference point
            # This ensures manual runs always show the same "Week of" date
            period_end = self._get_this_weeks_monday()
            period_start = period_end - timedelta(days=days)
        
        # Query BigQuery (primary source of truth)
        bq_storage = await self._get_bq_storage()
        if bq_storage:
            logger.info(f"Agent 1: Querying BigQuery articles from {period_start.date()} to {period_end.date()}")
            articles = await bq_storage.get_articles(
                start_date=period_start,
                end_date=period_end,
                limit=50
            )
            logger.info(f"Agent 1: Found {len(articles)} articles in BigQuery")
        else:
            raise RuntimeError("BigQuery is required but not configured")
        
        return articles, period_start, period_end

    def _build_articles_text(self, articles: List) -> str:
        """Build formatted text from articles for LLM prompt."""
        articles_text = []
        for i, a in enumerate(articles, 1):
            # Handle both ArticleRecord (BigQuery) and CorpusItem (SQLite) objects
            if hasattr(a, 'source_name'):
                # ArticleRecord from BigQuery
                source_name = a.source_name or 'Unknown'
            elif hasattr(a, 'source') and hasattr(a.source, 'name'):
                # CorpusItem from SQLite
                source_name = a.source.name
            else:
                source_name = 'Unknown'
            
            date_str = a.published_at.date() if a.published_at else 'Unknown'
            
            articles_text.append(
                f"[{i}] Title: {a.title}\n"
                f"Source: {source_name}\n"
                f"Date: {date_str}\n"
                f"Summary: {a.summary or 'No summary available'}"
            )
        return "\n\n".join(articles_text)

    async def generate_pre_brief(
        self, 
        days: int = 14,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Run Agent 1 analysis.
        
        Args:
            days: Number of days to look back (used if start_date/end_date not provided)
            start_date: Custom period start (for historical pre-briefings)
            end_date: Custom period end (for historical pre-briefings)
            
        Returns:
            Pre-brief record dict or None on failure
        """
        if start_date and end_date:
            logger.info(f"Agent 1: Generating pre-brief for {start_date.date()} to {end_date.date()}")
        else:
            logger.info(f"Agent 1: Generating pre-brief for last {days} days")
        
        articles, period_start, period_end = await self._get_articles(
            days=days, 
            start_date=start_date, 
            end_date=end_date
        )
        if not articles:
            logger.warning("No articles found for pre-briefing")
            return None

        articles_text = self._build_articles_text(articles)
        logger.info(f"Agent 1: Analysis articles text built ({len(articles)} articles)")
        
        prompt = self.PRE_BRIEF_PROMPT.format(
            period_start=period_start.date(),
            period_end=period_end.date(),
            article_count=len(articles),
            articles_text=articles_text
        )

        try:
            response = await self.client.messages_create(
                model=self.model,
                max_tokens=8000,
                temperature=0.0,
                system="You are a strict JSON-only intelligence agent. You always output valid, parseable JSON and never include conversational filler or markdown if it breaks the structure.",
                messages=[{"role": "user", "content": prompt}]
            )
            
            result_json = response.content[0].text.strip()
            logger.debug(f"Agent 1 raw response: {result_json[:200]}...")
            if "```json" in result_json:
                result_json = result_json.split("```json")[1].split("```")[0].strip()
            
            data = json.loads(result_json)
            
            # Build storage record
            pre_brief_id = str(uuid.uuid4())
            record = {
                "id": pre_brief_id,
                "briefing_type": "pre_briefing",
                "data": data,
                "period_start": period_start,
                "period_end": period_end,
                "generated_at": datetime.utcnow(),
                "model": self.model,
                "article_count": len(articles),
                "article_ids": [a.id for a in articles]
            }

            # Save to BigQuery
            bq_storage = await self._get_bq_storage()
            if bq_storage:
                await bq_storage.save_pre_briefing(record)
            else:
                raise RuntimeError("BigQuery is required but not configured")
            
            logger.info(f"Agent 1: Pre-brief {pre_brief_id} generated and stored")
            return record

        except Exception as e:
            logger.error(f"Error in Agent 1 generation: {e}", exc_info=True)
            return None

# Convenience function
async def run_agent_1(
    days: int = 14,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> Optional[Dict[str, Any]]:
    """
    Run Agent 1 (Pre-Brief Generator).
    
    Args:
        days: Number of days to look back (used if start_date/end_date not provided)
        start_date: Custom period start (for historical pre-briefings)
        end_date: Custom period end (for historical pre-briefings)
    """
    generator = PreBriefGenerator()
    return await generator.generate_pre_brief(
        days=days,
        start_date=start_date,
        end_date=end_date
    )
