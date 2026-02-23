"""
Pre-Brief Generator (Agent 1)
=============================

This agent performs the initial analysis of the last 14 days of news.
It produces a structured "Pre-Brief" that contains raw intelligence,
topic evolution signals, and detailed observations.

This output is stored in the `pre_briefings` table and is consumed by 
Agent 2 (Executive Synthesizer) to produce the final High-Conviction Briefing.

Key Design:
- Fetches ALL Medium/High/Critical priority digest items (no article cap)
- Processes in batches of ~40 to prevent context rot
- Merges batch results into a single compressed pre-brief
- Model: claude-sonnet-4-6
- Window: 14 days
"""

import uuid
import json
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from app.utils.resilient_llm import get_resilient_async_client
from app.config.settings import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Maximum articles per LLM batch to prevent context rot
BATCH_SIZE = 40


class PreBriefGenerator:
    """
    Agent 1: Analyzes 14 days of priority-filtered articles to create a raw intermediate "Pre-Brief".
    
    Uses batched processing to handle any volume of articles without context rot.
    """
    
    BATCH_ANALYSIS_PROMPT = """You are a senior intelligence analyst. Analyze the following batch of classified intelligence items from the last 14 days and extract structured observations.

<context>
Period: {period_start} to {period_end}
Batch: {batch_number} of {total_batches} ({item_count} items in this batch)
Total items across all batches: {total_items}
</context>

<items>
{items_text}
</items>

INSTRUCTIONS:
1. Identify all significant developments in the composites industry.
2. Group them into: "Suppliers and Competitors", "End Customers and OEMs", "Materials and Products", "Supply Chain".
3. For each observation, determine if it's "net_new", "evolution", or "stalled".
4. Assign a confidence score (0.0 - 1.0).
5. Include the item numbers that support each observation.

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

    MERGE_PROMPT = """You are a senior intelligence analyst. You have received observations from {batch_count} separate analysis batches covering {total_items} intelligence items from the last 14 days.

Your job is to MERGE these into a single, deduplicated, comprehensive pre-brief.

<batch_results>
{batch_results_json}
</batch_results>

INSTRUCTIONS:
1. Merge duplicate/overlapping observations into single entries (combine article_numbers).
2. Keep the highest confidence score when merging.
3. Preserve ALL unique signals — do not drop anything that appears in only one batch.
4. Consolidate the raw_topic_list across all batches (deduplicate).
5. Re-rank by signal importance: net_new > evolution > stalled.

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
            "article_numbers": [1, 15, 42]
        }}
    ],
    "raw_topic_list": ["topic1", "topic2"]
}}"""

    def __init__(self, config=None):
        self.config = config or settings
        self.client = get_resilient_async_client(
            anthropic_api_key=self.config.anthropic_api_key,
            gemini_api_key=getattr(self.config, 'gemini_api_key', None),
        )
        self.model = "claude-sonnet-4-6"
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

    async def _get_priority_items(
        self, 
        days: int = 14,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> tuple:
        """
        Fetch ALL Medium/High/Critical priority digest items from BigQuery.
        
        Uses the digest_items table (which has AI-assigned priority, category,
        topics, companies, digest_summary) instead of raw articles.
        
        Args:
            days: Number of days to look back (used if start_date/end_date not provided)
            start_date: Custom period start (for historical pre-briefings)
            end_date: Custom period end (for historical pre-briefings)
            
        Returns:
            tuple: (items, period_start, period_end)
        """
        # Determine period
        if start_date and end_date:
            period_start = start_date
            period_end = end_date
        else:
            # Use this week's Monday as the reference point
            period_end = self._get_this_weeks_monday()
            period_start = period_end - timedelta(days=days)
        
        # Calculate hours for the lookback window
        hours = int((period_end - period_start).total_seconds() / 3600) + 24  # +24h buffer
        
        # Query BigQuery digest_items with priority filter (no limit)
        bq_storage = await self._get_bq_storage()
        if not bq_storage:
            raise RuntimeError("BigQuery is required but not configured")
        
        logger.info(f"Agent 1: Querying digest_items from {period_start.date()} to {period_end.date()} (priorities: Medium/High/Critical)")
        
        items = await bq_storage.get_digest_items(
            hours=hours,
            priorities=["critical", "high", "medium"],
            limit=1000,  # Safety cap, should never hit this
        )
        
        # Filter to our actual date range (get_digest_items uses hours from now,
        # but we want a specific window)
        filtered_items = []
        for item in items:
            pub_date = item.get("published_at")
            if pub_date:
                if isinstance(pub_date, str):
                    try:
                        pub_dt = datetime.fromisoformat(pub_date.replace("Z", "+00:00")).replace(tzinfo=None)
                    except (ValueError, TypeError):
                        continue
                else:
                    pub_dt = pub_date
                if period_start <= pub_dt <= period_end + timedelta(days=1):
                    filtered_items.append(item)
        
        logger.info(f"Agent 1: Found {len(filtered_items)} priority items (from {len(items)} total digest items)")
        
        # Sort: Critical first, then High, then Medium, then by published_at DESC
        priority_order = {"critical": 0, "high": 1, "medium": 2}
        filtered_items.sort(key=lambda x: (
            priority_order.get((x.get("priority") or "medium").lower(), 3),
            -(datetime.fromisoformat(x["published_at"].replace("Z", "+00:00")).timestamp() 
              if isinstance(x.get("published_at"), str) and x.get("published_at")
              else 0)
        ))
        
        return filtered_items, period_start, period_end

    def _build_items_text(self, items: List[Dict[str, Any]], start_index: int = 1) -> str:
        """Build formatted text from digest items for LLM prompt."""
        items_text = []
        for i, item in enumerate(items, start_index):
            priority = (item.get("priority") or "medium").upper()
            source_name = item.get("source_name") or "Unknown"
            date_str = str(item.get("published_at", "Unknown"))[:10]
            
            # Use digest_summary (AI-generated, concise) with fallback to original
            summary = item.get("digest_summary") or item.get("original_summary") or "No summary available"
            
            # Include companies and topics if available
            companies = item.get("companies", [])
            topics = item.get("topics", [])
            
            entry = (
                f"[{i}] [{priority}] {item.get('title', 'Untitled')}\n"
                f"Source: {source_name} | Date: {date_str}\n"
                f"Summary: {summary}"
            )
            if companies:
                entry += f"\nCompanies: {', '.join(companies[:5])}"
            if topics:
                entry += f"\nTopics: {', '.join(topics[:5])}"
            
            items_text.append(entry)
        
        return "\n\n".join(items_text)

    async def _analyze_batch(
        self,
        items: List[Dict[str, Any]],
        batch_number: int,
        total_batches: int,
        total_items: int,
        period_start: datetime,
        period_end: datetime,
        start_index: int,
    ) -> Optional[Dict[str, Any]]:
        """Analyze a single batch of items with the LLM."""
        items_text = self._build_items_text(items, start_index=start_index)
        
        prompt = self.BATCH_ANALYSIS_PROMPT.format(
            period_start=period_start.date(),
            period_end=period_end.date(),
            batch_number=batch_number,
            total_batches=total_batches,
            item_count=len(items),
            total_items=total_items,
            items_text=items_text,
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
            if "```json" in result_json:
                result_json = result_json.split("```json")[1].split("```")[0].strip()
            elif "```" in result_json:
                result_json = result_json.split("```")[1].split("```")[0].strip()
            
            return json.loads(result_json)
            
        except Exception as e:
            logger.error(f"Agent 1: Batch {batch_number} analysis failed: {e}", exc_info=True)
            return None

    async def _merge_batch_results(
        self,
        batch_results: List[Dict[str, Any]],
        total_items: int,
    ) -> Optional[Dict[str, Any]]:
        """Merge multiple batch analysis results into a single pre-brief."""
        if len(batch_results) == 1:
            # Only one batch — no merge needed
            return batch_results[0]
        
        batch_results_json = json.dumps(batch_results, indent=2)
        
        prompt = self.MERGE_PROMPT.format(
            batch_count=len(batch_results),
            total_items=total_items,
            batch_results_json=batch_results_json,
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
            if "```json" in result_json:
                result_json = result_json.split("```json")[1].split("```")[0].strip()
            elif "```" in result_json:
                result_json = result_json.split("```")[1].split("```")[0].strip()
            
            return json.loads(result_json)
            
        except Exception as e:
            logger.error(f"Agent 1: Merge failed: {e}", exc_info=True)
            # Fallback: concatenate all observations without dedup
            merged = {"observations": [], "raw_topic_list": []}
            for result in batch_results:
                merged["observations"].extend(result.get("observations", []))
                merged["raw_topic_list"].extend(result.get("raw_topic_list", []))
            merged["raw_topic_list"] = list(set(merged["raw_topic_list"]))
            return merged

    async def generate_pre_brief(
        self, 
        days: int = 14,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Run Agent 1 analysis with batched processing.
        
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
        
        items, period_start, period_end = await self._get_priority_items(
            days=days, 
            start_date=start_date, 
            end_date=end_date
        )
        if not items:
            logger.warning("No priority items found for pre-briefing")
            return None

        # Split into batches
        batches = [items[i:i + BATCH_SIZE] for i in range(0, len(items), BATCH_SIZE)]
        total_items = len(items)
        total_batches = len(batches)
        
        logger.info(f"Agent 1: Processing {total_items} items in {total_batches} batch(es) of ~{BATCH_SIZE}")
        
        # Analyze each batch
        batch_results = []
        article_index = 1
        for batch_num, batch in enumerate(batches, 1):
            logger.info(f"Agent 1: Analyzing batch {batch_num}/{total_batches} ({len(batch)} items)")
            
            result = await self._analyze_batch(
                items=batch,
                batch_number=batch_num,
                total_batches=total_batches,
                total_items=total_items,
                period_start=period_start,
                period_end=period_end,
                start_index=article_index,
            )
            
            if result:
                batch_results.append(result)
                obs_count = len(result.get("observations", []))
                logger.info(f"Agent 1: Batch {batch_num} produced {obs_count} observations")
            else:
                logger.warning(f"Agent 1: Batch {batch_num} failed — skipping")
            
            article_index += len(batch)
        
        if not batch_results:
            logger.error("Agent 1: All batches failed")
            return None
        
        # Merge batch results
        logger.info(f"Agent 1: Merging {len(batch_results)} batch result(s)")
        data = await self._merge_batch_results(batch_results, total_items)
        
        if not data:
            logger.error("Agent 1: Merge failed")
            return None
        
        obs_count = len(data.get("observations", []))
        logger.info(f"Agent 1: Final pre-brief has {obs_count} observations from {total_items} items")
        
        # Build storage record
        # Collect article IDs from digest items for traceability
        article_ids = [item.get("article_id", "") for item in items if item.get("article_id")]
        
        pre_brief_id = str(uuid.uuid4())
        record = {
            "id": pre_brief_id,
            "briefing_type": "pre_briefing",
            "data": data,
            "period_start": period_start,
            "period_end": period_end,
            "generated_at": datetime.utcnow(),
            "model": self.model,
            "article_count": total_items,
            "article_ids": article_ids,
            "processing_metadata": {
                "batch_size": BATCH_SIZE,
                "total_batches": total_batches,
                "successful_batches": len(batch_results),
                "priority_filter": ["critical", "high", "medium"],
                "source_table": "digest_items",
            }
        }

        try:
            # Save to BigQuery
            bq_storage = await self._get_bq_storage()
            if bq_storage:
                await bq_storage.save_pre_briefing(record)
            else:
                raise RuntimeError("BigQuery is required but not configured")
            
            logger.info(f"Agent 1: Pre-brief {pre_brief_id} generated and stored ({obs_count} observations from {total_items} items)")
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
