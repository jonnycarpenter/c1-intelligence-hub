"""
Ingestion API Endpoints
=======================

Control the data ingestion pipeline.
"""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel, Field

from app.ingestion.orchestrator import get_orchestrator
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


# ============================================================================
# Pydantic Models for API
# ============================================================================

class IngestionStatusResponse(BaseModel):
    """Response for ingestion status."""
    
    initialized: bool = Field(..., description="Whether orchestrator is initialized")
    entity_count: int = Field(..., description="Number of tracked entities")
    dedup_cache_size: int = Field(..., description="Size of deduplication cache")
    corpus_stats: dict = Field(default_factory=dict, description="Corpus statistics")
    latest_ingestion: Optional[dict] = Field(None, description="Latest ingestion run info")


class IngestionRunResponse(BaseModel):
    """Response for ingestion run."""
    
    id: str = Field(..., description="Ingestion run ID")
    status: str = Field(..., description="Status: running, completed, failed")
    started_at: datetime = Field(..., description="When the run started")
    completed_at: Optional[datetime] = Field(None, description="When the run completed")
    rss_articles_fetched: int = Field(0, description="Number of RSS articles fetched")
    duplicates_skipped: int = Field(0, description="Number of duplicates skipped")
    articles_enriched: int = Field(0, description="Number of articles enriched")
    articles_classified: int = Field(0, description="Number of articles classified")
    articles_stored: int = Field(0, description="Number of articles stored")
    errors: list = Field(default_factory=list, description="Errors encountered")
    duration_seconds: Optional[float] = Field(None, description="Duration in seconds")


class CorpusStatsResponse(BaseModel):
    """Response for corpus statistics."""
    
    total_items: int = Field(0, description="Total items in corpus")
    items_by_category: dict = Field(default_factory=dict)
    items_by_priority: dict = Field(default_factory=dict)
    items_by_source: dict = Field(default_factory=dict)
    latest_item_date: Optional[datetime] = None
    oldest_item_date: Optional[datetime] = None


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/status", response_model=IngestionStatusResponse)
async def get_ingestion_status():
    """
    Get current ingestion pipeline status.
    
    Returns:
    - Whether the orchestrator is initialized
    - Number of tracked entities
    - Deduplication cache size
    - Corpus statistics
    - Latest ingestion run info
    """
    try:
        orchestrator = get_orchestrator()
        await orchestrator.initialize()
        
        status = await orchestrator.get_status()
        return IngestionStatusResponse(**status)
        
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/run", response_model=IngestionRunResponse)
async def run_full_ingestion(background_tasks: BackgroundTasks):
    """
    Trigger a full ingestion run.
    
    This will:
    1. Fetch all RSS feeds
    2. Deduplicate articles
    4. Enrich with full text extraction
    5. Classify content
    6. Link entities
    7. Store in corpus
    8. Generate digest
    
    The ingestion runs in the foreground and returns stats when complete.
    For background execution, use /run-background.
    """
    try:
        logger.info("Starting full ingestion run")
        orchestrator = get_orchestrator()
        await orchestrator.initialize()
        
        stats = await orchestrator.run_full_ingestion()
        
        return IngestionRunResponse(
            id=stats.id,
            status=stats.status,
            started_at=stats.started_at,
            completed_at=stats.completed_at,
            rss_articles_fetched=stats.rss_articles_fetched,
            duplicates_skipped=stats.duplicates_skipped,
            articles_enriched=stats.articles_enriched,
            articles_classified=stats.articles_classified,
            articles_stored=stats.articles_stored,
            errors=stats.errors,
            duration_seconds=stats.duration_seconds,
        )
        
    except Exception as e:
        logger.error(f"Error running ingestion: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/run-background")
async def run_ingestion_background(background_tasks: BackgroundTasks):
    """
    Trigger a full ingestion run in the background.
    
    Returns immediately with a job ID.
    Use /status to check progress.
    """
    try:
        orchestrator = get_orchestrator()
        await orchestrator.initialize()
        
        # Run in background
        background_tasks.add_task(_run_ingestion_task)
        
        return {
            "message": "Ingestion started in background",
            "status": "running",
            "check_status_at": "/api/ingest/status",
        }
        
    except Exception as e:
        logger.error(f"Error starting background ingestion: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _run_ingestion_task():
    """Background task for ingestion."""
    try:
        orchestrator = get_orchestrator()
        await orchestrator.run_full_ingestion()
    except Exception as e:
        logger.error(f"Background ingestion error: {e}")


@router.post("/run-rss")
async def run_rss_only():
    """
    Run RSS-only ingestion (faster).
    
    This skips enrichment for quicker updates.
    Good for frequent polling.
    """
    try:
        logger.info("Starting RSS-only ingestion")
        orchestrator = get_orchestrator()
        await orchestrator.initialize()
        
        stats = await orchestrator.run_rss_only()
        
        return IngestionRunResponse(
            id=stats.id,
            status=stats.status,
            started_at=stats.started_at,
            completed_at=stats.completed_at,
            rss_articles_fetched=stats.rss_articles_fetched,
            duplicates_skipped=stats.duplicates_skipped,
            articles_enriched=0,
            articles_classified=stats.articles_classified,
            articles_stored=stats.articles_stored,
            errors=stats.errors,
            duration_seconds=stats.duration_seconds,
        )
        
    except Exception as e:
        logger.error(f"Error running RSS ingestion: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/digest/refresh")
async def refresh_digest_only():
    """
    Regenerate the intelligence digest without running ingestion.
    
    Use this to get fresh analysis of existing corpus items.
    """
    try:
        logger.info("Refreshing digest only")
        orchestrator = get_orchestrator()
        await orchestrator.initialize()
        
        digest = await orchestrator.run_digest_only()
        
        return {
            "message": "Digest refreshed",
            "digest_id": digest.id if digest else None,
            "item_count": len(digest.items) if digest else 0,
        }
        
    except Exception as e:
        logger.error(f"Error refreshing digest: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/corpus/stats")
async def get_corpus_stats():
    """
    Get corpus statistics.
    
    Returns counts by category, priority, source, and date range.
    """
    try:
        orchestrator = get_orchestrator()
        await orchestrator.initialize()
        
        stats = await orchestrator.db.get_corpus_stats()
        return CorpusStatsResponse(**stats) if stats else CorpusStatsResponse()
        
    except Exception as e:
        logger.error(f"Error getting corpus stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/corpus/search")
async def search_corpus(
    query: Optional[str] = Query(None, description="Search query"),
    category: Optional[str] = Query(None, description="Filter by category"),
    priority: Optional[str] = Query(None, description="Filter by priority (high, medium, low)"),
    hours: int = Query(72, description="Hours to look back"),
    limit: int = Query(50, max=200, description="Maximum items to return"),
):
    """
    Search the corpus.
    
    Returns corpus items matching the filters.
    """
    try:
        orchestrator = get_orchestrator()
        await orchestrator.initialize()
        
        # Build filters
        filters = {}
        if category:
            filters["category"] = category
        if priority:
            filters["priority"] = priority
        
        items = await orchestrator.db.query_corpus(
            query=query,
            hours=hours,
            limit=limit,
            **filters,
        )
        
        return {
            "count": len(items),
            "items": [
                {
                    "id": item.id,
                    "title": item.title,
                    "summary": item.summary[:300] if item.summary else None,
                    "url": item.url,
                    "source": item.source.name if item.source else None,
                    "category": item.primary_category.value if item.primary_category else None,
                    "priority": item.priority.value if item.priority else None,
                    "relevance_score": item.relevance_score,
                    "published_at": item.published_at.isoformat() if item.published_at else None,
                }
                for item in items
            ],
        }
        
    except Exception as e:
        logger.error(f"Error searching corpus: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/feeds")
async def list_feeds():
    """
    List configured RSS feeds.
    """
    from app.ingestion.config import RSS_FEEDS
    
    return {
        "count": len(RSS_FEEDS),
        "feeds": RSS_FEEDS,
    }


@router.get("/history")
async def get_ingestion_history(
    limit: int = Query(10, max=50, description="Number of runs to return"),
):
    """
    Get recent ingestion run history.
    """
    try:
        orchestrator = get_orchestrator()
        await orchestrator.initialize()
        
        runs = await orchestrator.db.get_ingestion_history(limit=limit)
        
        return {
            "count": len(runs),
            "runs": [
                {
                    "id": run.id,
                    "status": run.status,
                    "started_at": run.started_at.isoformat() if run.started_at else None,
                    "completed_at": run.completed_at.isoformat() if run.completed_at else None,
                    "articles_stored": run.articles_stored,
                    "duration_seconds": run.duration_seconds,
                    "errors": len(run.errors) if run.errors else 0,
                }
                for run in runs
            ],
        }
        
    except Exception as e:
        logger.error(f"Error getting history: {e}")
        raise HTTPException(status_code=500, detail=str(e))
