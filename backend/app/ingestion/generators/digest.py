import uuid
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any

from app.utils.resilient_llm import get_resilient_async_client
from app.models.corpus import Digest, DigestItem, DigestStats, Priority

logger = logging.getLogger(__name__)

class DigestGenerator:
    """
    Generates pre-computed intelligence digests.
    
    Note: This class now uses BigQuery storage for querying digest items.
    The actual digest item storage is handled by the orchestrator's store_digest_items() call.
    """
    
    SUMMARY_PROMPT = """You are creating an executive intelligence briefing for Composites One's commercial team.

Based on the following intelligence items from the past {hours} hours, write a concise executive summary (3-5 sentences) highlighting:
1. The most important competitive or market developments
2. Any urgent items requiring attention
3. Key themes or patterns

<intelligence_items>
{items}
</intelligence_items>

Write the executive summary in a professional, direct style. Focus on actionable intelligence.
Do not use bullet points - write in flowing paragraphs."""

    def __init__(self, config, storage):
        """Initialize DigestGenerator.
        
        Args:
            config: Ingestion configuration
            storage: BigQuery storage instance (from get_storage())
        """
        self.config = config
        self.storage = storage  # BigQuery storage
        self.client = get_resilient_async_client(
            anthropic_api_key=config.anthropic_api_key,
            gemini_api_key=getattr(config, 'gemini_api_key', None),
        )
        self.max_items = getattr(config, 'digest_max_items', 50)
        self.model = getattr(config, 'digest_model', "claude-sonnet-4-5")
    
    async def generate(self, hours: int = 72) -> Digest:
        """Generate a digest for the specified time period"""
        logger.info(f"Generating {hours}-hour digest...")
        
        period_end = datetime.utcnow()
        period_start = period_end - timedelta(hours=hours)
        
        # Query digest items from BigQuery
        raw_items = await self.storage.get_digest_items(hours=hours, limit=self.max_items * 2)
        
        if not raw_items:
            logger.warning("No digest items found for digest generation")
            return self._empty_digest(period_start, period_end, hours)
        
        # Sort by priority and relevance (raw_items are dicts from BigQuery)
        def priority_sort_key(item):
            priority = (item.get("priority") or "medium").lower()
            priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
            relevance = item.get("relevance_score") or 0.5
            return (priority_order.get(priority, 2), -relevance)
        
        sorted_items = sorted(raw_items, key=priority_sort_key)
        top_items = sorted_items[:self.max_items]
        
        # Convert BigQuery dict items to DigestItem objects
        digest_items = []
        for item in top_items:
            # Parse published_at if string
            published_at = item.get("published_at")
            if isinstance(published_at, str):
                try:
                    published_at = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
                except:
                    published_at = None
            
            # Get entity mentions from companies field
            companies = item.get("companies") or []
            if isinstance(companies, str):
                companies = [c.strip() for c in companies.split(",") if c.strip()]
            
            digest_items.append(DigestItem(
                corpus_item_id=item.get("article_id") or item.get("id"),
                title=item.get("title", ""),
                summary=item.get("digest_summary") or item.get("original_summary") or "",
                category=item.get("category", "general"),
                priority=item.get("priority", "medium"),
                source_name=item.get("source_name", ""),
                source_url=item.get("url", ""),
                published_at=published_at,
                entity_mentions=companies[:5],
            ))
        
        executive_summary = await self._generate_summary(digest_items, hours)
        stats = self._calculate_stats(digest_items)
        
        digest = Digest(
            id=str(uuid.uuid4()),
            period_start=period_start,
            period_end=period_end,
            hours_covered=hours,
            executive_summary=executive_summary,
            items=digest_items,
            stats=stats,
            generated_at=datetime.utcnow(),
        )
        
        await self._save_digest(digest)
        return digest
    
    async def _generate_summary(self, items: List[DigestItem], hours: int) -> str:
        """Generate executive summary using Claude"""
        if not items:
            return "No significant intelligence to report for this period."
        
        items_text = "\n\n".join([
            f"[{item.priority.upper()}] {item.title}\n{item.summary[:200]}"
            for item in items[:20]
        ])
        
        prompt = self.SUMMARY_PROMPT.format(hours=hours, items=items_text)
        
        try:
            response = await self.client.messages_create(
                model=self.model,
                max_tokens=500,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text.strip()
        except Exception as e:
            logger.error(f"Error generating digest summary: {e}")
            return "Executive summary generation failed. Please review individual items."
    
    def _calculate_stats(self, items: List[DigestItem]) -> DigestStats:
        """Calculate digest statistics"""
        stats = DigestStats(
            total_items=len(items)
        )
        
        unique_entities = set()
        sources = set()
        
        for item in items:
            stats.by_category[item.category] = stats.by_category.get(item.category, 0) + 1
            stats.by_priority[item.priority] = stats.by_priority.get(item.priority, 0) + 1
            sources.add(item.source_name)
            for entity in item.entity_mentions:
                unique_entities.add(entity)
        
        stats.unique_entities = len(unique_entities)
        stats.sources_count = len(sources)
        return stats
    
    async def _save_digest(self, digest: Digest):
        """Save digest metadata.
        
        Note: Individual digest items are stored by the orchestrator via store_digest_items().
        This method logs the digest generation for tracking purposes.
        """
        # The actual items are already in BigQuery via the orchestrator's store_digest_items() call
        # This method is kept for logging and potential future digest metadata storage
        logger.info(f"Generated digest {digest.id} with {len(digest.items)} items")
    
    def _empty_digest(self, start: datetime, end: datetime, hours: int) -> Digest:
        return Digest(
            id=str(uuid.uuid4()),
            period_start=start,
            period_end=end,
            hours_covered=hours,
            executive_summary="No intelligence items found for this period.",
            items=[],
            generated_at=datetime.utcnow(),
        )
