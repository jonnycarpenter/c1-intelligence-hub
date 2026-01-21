"""
Digest Service - Production Implementation
==========================================

Generates and manages intelligence digest items from real data sources.

Data Flow:
1. IngestionOrchestrator collects & classifies articles → stores in BigQuery
2. DigestService queries stored digest items → serves to API

Features:
- Real-time data from classified articles
- Caching with configurable TTL
- LLM-generated executive summaries
- Fallback to mock data when no real data available
"""

import uuid
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from collections import defaultdict

from app.utils.resilient_llm import get_resilient_async_client

from app.api.schemas import (
    Digest,
    DigestItem,
    DigestStats,
    DigestCategory,
    DigestEntities,
    Priority,
    Source,
)
from app.db.gcp_storage import get_storage, DataStorageInterface
from app.utils.logger import get_logger
from app.config.settings import settings

logger = get_logger(__name__)


# =============================================================================
# LLM Summary Prompt
# =============================================================================

EXECUTIVE_SUMMARY_PROMPT = """You are creating an executive intelligence briefing for Composites One's commercial team.

Based on the following {count} intelligence items from the past {hours} hours, write a concise executive summary (3-5 sentences) highlighting:
1. The most important competitive or market developments
2. Any urgent items requiring attention
3. Key themes or patterns across the items

<intelligence_items>
{items_text}
</intelligence_items>

Write the executive summary in a professional, direct style. Focus on actionable intelligence.
Do not use bullet points - write in flowing paragraphs.
If there are critical or high priority items, lead with those."""


class DigestService:
    """
    Production service for managing the intelligence digest.
    
    Retrieves classified articles from storage and serves them
    through the digest API with caching and filtering.
    """
    
    def __init__(
        self,
        cache_ttl_minutes: int = 15,
        use_llm_summaries: bool = True,
    ):
        """
        Initialize the digest service.
        
        Args:
            cache_ttl_minutes: How long to cache digests
            use_llm_summaries: Whether to generate LLM summaries (costs tokens)
        """
        self._storage: Optional[DataStorageInterface] = None
        self._cache: Dict[str, Digest] = {}
        self._items_cache: Dict[str, DigestItem] = {}
        self._last_refresh: Optional[datetime] = None
        self._cache_ttl_minutes = cache_ttl_minutes
        self._use_llm_summaries = use_llm_summaries
        self._initialized = False
        
        # Resilient client for summaries (Anthropic primary, OpenAI fallback)
        if use_llm_summaries and settings.anthropic_api_key:
            self._anthropic = get_resilient_async_client(
                anthropic_api_key=settings.anthropic_api_key,
                openai_api_key=settings.openai_api_key,
            )
        else:
            self._anthropic = None
    
    async def _ensure_initialized(self):
        """Ensure storage is initialized."""
        if not self._initialized:
            self._storage = await get_storage()
            self._initialized = True
    
    async def get_digest(
        self,
        hours: int = 72,
        categories: Optional[List[DigestCategory]] = None,
        priorities: Optional[List[Priority]] = None,
        limit: int = 100,
    ) -> Digest:
        """
        Get the current digest, optionally filtered.
        
        Args:
            hours: Number of hours to look back
            categories: Filter by these categories (None = all)
            priorities: Filter by these priorities (None = all)
            limit: Max items to return (default 100)
            
        Returns:
            Filtered digest
        """
        await self._ensure_initialized()
        
        # Create cache key (include limit to cache different result sizes separately)
        cat_key = "_".join(sorted(c.value for c in categories)) if categories else "all"
        pri_key = "_".join(sorted(p.value for p in priorities)) if priorities else "all"
        cache_key = f"{hours}_{cat_key}_{pri_key}_{limit}"
        
        # Check cache
        if cache_key in self._cache and not self._is_cache_stale():
            return self._cache[cache_key]
        
        # Generate fresh digest
        digest = await self._generate_digest(hours, categories, priorities, limit)
        
        # Cache it
        self._cache[cache_key] = digest
        self._last_refresh = datetime.now()
        
        return digest
    
    async def _generate_digest(
        self,
        hours: int,
        categories: Optional[List[DigestCategory]] = None,
        priorities: Optional[List[Priority]] = None,
        limit: int = 100,
    ) -> Digest:
        """Generate a digest from stored items."""
        logger.info(f"Generating digest for last {hours} hours, limit={limit}")
        
        now = datetime.now()
        period_start = now - timedelta(hours=hours)
        
        # Convert enums to strings for storage query
        cat_strs = [c.value for c in categories] if categories else None
        pri_strs = [p.value for p in priorities] if priorities else None
        
        # Query stored digest items
        try:
            raw_items = await self._storage.get_digest_items(
                hours=hours,
                categories=cat_strs,
                priorities=pri_strs,
                min_confidence=0.3,  # Filter low-confidence classifications
                limit=limit,
            )
        except Exception as e:
            logger.error(f"Error querying digest items: {e}")
            raw_items = []
        
        # If no items, return empty digest (no mock data fallback)
        if not raw_items:
            logger.warning(f"No digest items found in the last {hours} hours")
            return Digest(
                id=f"digest_{uuid.uuid4().hex[:8]}",
                generated_at=now,
                period_start=period_start,
                period_end=now,
                stats=DigestStats(
                    total_items=0,
                    by_category={},
                    by_priority={},
                ),
                items=[],
                summary="No recent intelligence items found. The data collection pipeline may need to be run, or there may not be any new developments in the monitored areas.",
            )
        
        # Convert to DigestItem objects
        items = []
        for raw in raw_items:
            try:
                item = self._convert_to_digest_item(raw)
                items.append(item)
                self._items_cache[item.id] = item
            except Exception as e:
                logger.warning(f"Error converting digest item: {e}")
        
        # Generate summary
        summary = await self._generate_summary(items, hours)
        
        # Calculate stats
        stats = self._calculate_stats(items)
        
        return Digest(
            id=f"digest_{uuid.uuid4().hex[:8]}",
            generated_at=now,
            period_start=period_start,
            period_end=now,
            stats=stats,
            items=items,
            summary=summary,
        )
    
    def _format_pill(self, text: str) -> str:
        """Format string for display as a pill (e.g. supply_chain -> Supply Chain)."""
        if not text:
            return ""
        # Replace underscores with spaces
        formatted = text.replace("_", " ")
        # Title case (capitalize first letter of each word)
        return formatted.title()
    
    def _convert_to_digest_item(self, raw: Dict[str, Any]) -> DigestItem:
        """Convert storage dict to DigestItem."""
        import json
        
        # Parse published_at
        published_at = raw.get("published_at")
        if isinstance(published_at, str):
            published_at = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        elif published_at is None:
            published_at = datetime.now()
        
        # Parse classified_at as ingested_at
        ingested_at = raw.get("classified_at")
        if isinstance(ingested_at, str):
            ingested_at = datetime.fromisoformat(ingested_at.replace("Z", "+00:00"))
        elif ingested_at is None:
            ingested_at = datetime.now()
        
        # Build sources list - primary source first, then duplicates
        sources = []
        
        # Primary source
        primary_source = Source(
            title=raw.get("source_name", "Unknown"),
            url=raw.get("url", ""),
            published_at=published_at.strftime("%Y-%m-%d") if published_at else None,
        )
        sources.append(primary_source)
        
        # Add duplicate sources if any (when coverage_count > 1)
        duplicate_sources = raw.get("duplicate_sources", [])
        all_urls = raw.get("all_urls", [])
        
        # Parse if stored as JSON strings
        if isinstance(duplicate_sources, str):
            try:
                duplicate_sources = json.loads(duplicate_sources)
            except:
                duplicate_sources = []
        if isinstance(all_urls, str):
            try:
                all_urls = json.loads(all_urls)
            except:
                all_urls = []
        
        # Match duplicate sources with their URLs (best effort)
        # all_urls includes the primary URL, so we need to pair extras with duplicate_sources
        extra_urls = [u for u in all_urls if u != raw.get("url")]
        
        for i, source_name in enumerate(duplicate_sources):
            # Try to pair with an extra URL
            url = extra_urls[i] if i < len(extra_urls) else ""
            sources.append(Source(
                title=source_name,
                url=url,
                published_at=published_at.strftime("%Y-%m-%d") if published_at else None,
            ))
        
        # Get coverage count (default to 1 if not present)
        coverage_count = raw.get("coverage_count", 1) or 1
        
        # Format entities for pills
        entities_raw = {
            "companies": raw.get("companies", []),
            "materials": raw.get("materials", []),
            "topics": raw.get("topics", []),
            "industries": raw.get("industries", []),
        }
        
        # Apply formatting to industries (and others if needed/requested)
        formatted_industries = [self._format_pill(i) for i in entities_raw["industries"]]
        formatted_topics = [self._format_pill(t) for t in entities_raw["topics"]]
        
        # Get relevance_score, defaulting to None if not present
        relevance_score = raw.get("relevance_score")
        if relevance_score is not None:
            try:
                relevance_score = float(relevance_score)
            except (TypeError, ValueError):
                relevance_score = None

        return DigestItem(
            id=raw.get("id", str(uuid.uuid4())),
            title=raw.get("title", ""),
            headline=raw.get("headline") or raw.get("title", ""),
            summary=raw.get("digest_summary") or raw.get("original_summary", ""),
            category=self._format_pill(raw.get("category", "market")),
            priority=Priority(self._format_pill(raw.get("priority", "medium"))),
            sources=sources,
            entities=DigestEntities(
                companies=entities_raw["companies"],
                materials=entities_raw["materials"],
                topics=formatted_topics,
                industries=formatted_industries,
            ),
            published_at=published_at,
            ingested_at=ingested_at,
            coverage_count=coverage_count,
            relevance_score=relevance_score,
        )
    
    async def _generate_summary(self, items: List[DigestItem], hours: int) -> str:
        """Generate executive summary using LLM."""
        if not items:
            return "No significant intelligence to report for this period."
        
        # If LLM summaries disabled or no client, use simple summary
        if not self._anthropic:
            return self._generate_simple_summary(items)
        
        # Prepare items text for LLM
        # Prioritize critical and high priority items
        critical = [i for i in items if i.priority == Priority.CRITICAL]
        high = [i for i in items if i.priority == Priority.HIGH]
        medium = [i for i in items if i.priority == Priority.MEDIUM]
        
        selected = critical + high[:10] + medium[:5]
        if not selected:
            selected = items[:15]
        
        items_text = "\n\n".join([
            f"[{item.priority.value.upper()}] {item.title}\n{item.summary[:300]}"
            for item in selected[:20]
        ])
        
        prompt = EXECUTIVE_SUMMARY_PROMPT.format(
            count=len(items),
            hours=hours,
            items_text=items_text,
        )
        
        try:
            response = await self._anthropic.messages_create(
                model="claude-sonnet-4-5",
                max_tokens=500,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}],
            )
            
            return response.content[0].text.strip()
            
        except Exception as e:
            logger.error(f"LLM summary generation failed: {e}")
            return self._generate_simple_summary(items)
    
    def _generate_simple_summary(self, items: List[DigestItem]) -> str:
        """Generate a simple non-LLM summary."""
        critical = [i for i in items if i.priority == Priority.CRITICAL]
        high_priority = [i for i in items if i.priority == Priority.HIGH]
        
        if critical:
            return (
                f"ALERT: {len(critical)} critical items require immediate attention. "
                f"Additionally, {len(high_priority)} high-priority items. "
                f"Total of {len(items)} intelligence items collected."
            )
        elif high_priority:
            return (
                f"Key developments include {len(high_priority)} high-priority items requiring attention. "
                f"Total of {len(items)} intelligence items collected across market, competitor, and regulatory topics."
            )
        
        return f"Total of {len(items)} intelligence items collected. No critical or high-priority items requiring immediate attention."
    
    def _calculate_stats(self, items: List[DigestItem]) -> DigestStats:
        """Calculate statistics for a list of items."""
        by_category = defaultdict(int)
        by_priority = defaultdict(int)
        
        for item in items:
            by_category[item.category.value] += 1
            by_priority[item.priority.value] += 1
        
        return DigestStats(
            total_items=len(items),
            by_category=dict(by_category),
            by_priority=dict(by_priority),
        )
    
    def _is_cache_stale(self) -> bool:
        """Check if the cache is stale."""
        if self._last_refresh is None:
            return True
        age = datetime.now() - self._last_refresh
        return age > timedelta(minutes=self._cache_ttl_minutes)
    
    async def refresh_digest(self) -> Digest:
        """Force refresh the digest."""
        self._cache.clear()
        self._items_cache.clear()
        self._last_refresh = None
        return await self.get_digest(hours=72)
    
    async def get_item(self, item_id: str) -> Optional[DigestItem]:
        """Get a specific digest item by ID."""
        # Check cache first
        if item_id in self._items_cache:
            return self._items_cache[item_id]
        
        # Try to load from storage
        await self._ensure_initialized()
        try:
            items = await self._storage.get_digest_items(
                hours=168,  # 1 week
                limit=500,
            )
            for raw in items:
                if raw.get("id") == item_id:
                    item = self._convert_to_digest_item(raw)
                    self._items_cache[item_id] = item
                    return item
        except Exception as e:
            logger.error(f"Error fetching item {item_id}: {e}")
        
        return None
    
    async def get_stats(self, hours: int = 72) -> DigestStats:
        """Get digest statistics without full items."""
        await self._ensure_initialized()
        
        try:
            stats = await self._storage.get_digest_stats(hours=hours)
            return DigestStats(
                total_items=stats.get("total_items", 0),
                by_category=stats.get("by_category", {}),
                by_priority=stats.get("by_priority", {}),
            )
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return DigestStats(total_items=0, by_category={}, by_priority={})
    
    async def trigger_ingestion(self) -> Dict[str, Any]:
        """
        Trigger a background ingestion run via orchestrator.
        
        Returns status of the triggered ingestion.
        """
        try:
            from app.ingestion.orchestrator import get_orchestrator
            
            orchestrator = get_orchestrator()
            await orchestrator.initialize()
            stats = await orchestrator.run_full_ingestion()
            
            # Clear cache to pick up new items
            self._cache.clear()
            self._last_refresh = None
            
            return stats
        except Exception as e:
            logger.error(f"Ingestion trigger failed: {e}")
            return {"status": "error", "error": str(e)}


# =============================================================================
# Singleton Instance
# =============================================================================

_service_instance: Optional[DigestService] = None


def get_digest_service() -> DigestService:
    """Get or create the digest service singleton."""
    global _service_instance
    if _service_instance is None:
        _service_instance = DigestService()
    return _service_instance
