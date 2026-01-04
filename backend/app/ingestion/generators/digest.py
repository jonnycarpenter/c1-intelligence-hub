import uuid
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
from anthropic import AsyncAnthropic

from app.models.corpus import Digest, DigestItem, DigestStats, Priority

logger = logging.getLogger(__name__)

class DigestGenerator:
    """
    Generates pre-computed intelligence digests.
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

    def __init__(self, config, db):
        self.config = config
        self.db = db
        self.client = AsyncAnthropic(api_key=config.anthropic_api_key)
        self.max_items = getattr(config, 'digest_max_items', 50)
        self.model = getattr(config, 'digest_model', "claude-sonnet-4-5")
    
    async def generate(self, hours: int = 72) -> Digest:
        """Generate a digest for the specified time period"""
        logger.info(f"Generating {hours}-hour digest...")
        
        period_end = datetime.utcnow()
        period_start = period_end - timedelta(hours=hours)
        
        corpus_items = await self.db.query_corpus(hours=hours, limit=self.max_items * 2)
        
        if not corpus_items:
            logger.warning("No corpus items found for digest")
            return self._empty_digest(period_start, period_end, hours)
        
        # Sort by priority and relevance
        sorted_items = sorted(
            corpus_items,
            key=lambda x: (
                0 if x.priority == Priority.HIGH else 1 if x.priority == Priority.MEDIUM else 2,
                -x.relevance_score
            )
        )
        
        top_items = sorted_items[:self.max_items]
        
        digest_items = []
        for item in top_items:
            digest_items.append(DigestItem(
                corpus_item_id=item.id,
                title=item.title,
                summary=item.summary,
                category=item.categories[0].value if item.categories else "general",
                priority=item.priority.value,
                source_name=item.source.name,
                source_url=item.url,
                published_at=item.published_at,
                entity_mentions=[m.entity_name for m in item.entity_mentions[:5]],
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
            response = await self.client.messages.create(
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
        """Save digest to database"""
        try:
            await self.db.save_digest(digest)
            logger.info(f"Saved digest {digest.id}")
        except Exception as e:
            logger.error(f"Error saving digest: {e}")
    
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
