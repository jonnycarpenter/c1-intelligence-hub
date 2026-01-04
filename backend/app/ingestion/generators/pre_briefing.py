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
from anthropic import AsyncAnthropic

from app.db.database import get_db
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
        self.db = get_db()
        self.client = AsyncAnthropic(api_key=self.config.anthropic_api_key)
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

    async def _get_articles(self, days: int = 14) -> tuple:
        period_end = datetime.utcnow()
        period_start = period_end - timedelta(days=days)
        
        articles = await self.db.query_corpus(
            hours=days * 24,
            limit=50
        )
        return articles, period_start, period_end

    def _build_articles_text(self, articles: List) -> str:
        articles_text = []
        for i, a in enumerate(articles, 1):
            source_name = a.source.name if hasattr(a.source, 'name') else 'Unknown'
            date_str = a.published_at.date() if a.published_at else 'Unknown'
            
            articles_text.append(
                f"[{i}] Title: {a.title}\n"
                f"Source: {source_name}\n"
                f"Date: {date_str}\n"
                f"Summary: {a.summary}"
            )
        return "\n\n".join(articles_text)

    async def generate_pre_brief(self, days: int = 14) -> Optional[Dict[str, Any]]:
        """Run Agent 1 analysis."""
        logger.info(f"Agent 1: Generating pre-brief for last {days} days")
        
        articles, period_start, period_end = await self._get_articles(days)
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
            response = await self.client.messages.create(
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

            # Save to both
            await self.db.save_pre_briefing(record)
            bq_storage = await self._get_bq_storage()
            if bq_storage:
                await bq_storage.save_pre_briefing(record)
            
            logger.info(f"Agent 1: Pre-brief {pre_brief_id} generated and stored")
            return record

        except Exception as e:
            logger.error(f"Error in Agent 1 generation: {e}", exc_info=True)
            return None

# Convenience function
async def run_agent_1() -> Optional[Dict[str, Any]]:
    generator = PreBriefGenerator()
    return await generator.generate_pre_brief(days=14)
