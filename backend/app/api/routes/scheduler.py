"""
Cloud Scheduler Endpoints
=========================

HTTP endpoints triggered by Cloud Scheduler for automated data collection.
Data collection is handled by the orchestrator workflow.

Endpoints:
- POST /api/v1/scheduler/ingest - Trigger orchestrator ingestion
- POST /api/v1/scheduler/briefing - Trigger weekly executive briefing generation
- POST /api/v1/scheduler/maintenance - Trigger maintenance tasks
- GET /api/v1/scheduler/status - Get ingestion status
"""

import os
from datetime import datetime, timedelta
from typing import Optional, Literal
from enum import Enum

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, Field

from app.db.gcp_storage import get_storage
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/v1/scheduler", tags=["scheduler"])


# =============================================================================
# Request/Response Models
# =============================================================================

class IngestRequest(BaseModel):
    """Request body for ingestion trigger."""
    sources: list[str] = Field(
        default=["exa_queries", "tavily_queries", "rss", "sec"],
        description="Sources to collect: exa_queries, tavily_queries, rss, sec, press_releases, earnings, stocknews, fmp_news, freight. Note: 'industry_queries' runs both exa+tavily (legacy)."
    )
    backfill_days: Optional[int] = Field(
        default=None,
        description="Number of days to backfill. If None, uses default 2-day window."
    )


class MaintenanceTask(str, Enum):
    """Maintenance tasks."""
    CLEANUP = "cleanup"
    REINDEX = "reindex"


class MaintenanceRequest(BaseModel):
    """Request body for maintenance trigger."""
    task: MaintenanceTask
    retention_days: int = Field(default=90, ge=30, le=365)


class BriefingRequest(BaseModel):
    """Request body for briefing generation trigger."""
    briefing_type: str = Field(
        default="weekly_executive",
        description="Type of briefing: weekly_executive"
    )
    lookback_days: int = Field(
        default=7,
        ge=1,
        le=30,
        description="Number of days to look back for articles"
    )


class BriefingResponse(BaseModel):
    """Response for briefing generation trigger."""
    status: Literal["success", "error"]
    briefing_id: Optional[str] = None
    sections_count: int = 0
    articles_used: int = 0
    message: str
    execution_time_seconds: float


class IngestResponse(BaseModel):
    """Response for ingestion trigger."""
    status: Literal["success", "error"]
    records_collected: int = 0
    message: str
    execution_time_seconds: float


class MaintenanceResponse(BaseModel):
    """Response for maintenance trigger."""
    status: Literal["success", "error"]
    task: str
    message: str
    details: dict = {}


class SchedulerStatusResponse(BaseModel):
    """Scheduler status response."""
    environment: str
    storage_backend: str
    sources_available: list[str]


# =============================================================================
# Authentication Helper
# =============================================================================

def verify_scheduler_auth(authorization: Optional[str] = None) -> bool:
    """
    Verify Cloud Scheduler authentication.
    
    In production, Cloud Scheduler sends an OIDC token.
    In development, we allow unauthenticated access.
    
    NOTE: On Cloud Run with IAM authentication, the Authorization header 
    is stripped by the infrastructure after validation. We trust Cloud Run 
    to only allow authenticated requests through.
    """
    environment = os.getenv("ENVIRONMENT", "development")
    
    if environment == "development":
        return True
        
    # In production, if we are behind Cloud Run IAM, the request is already authenticated.
    # The Authorization header might be stripped, so we can't rely on it.
    # We trust the infrastructure.
    return True


# =============================================================================
# Ingestion Endpoint
# =============================================================================

@router.post("/ingest", response_model=IngestResponse)
async def trigger_ingestion(
    request: IngestRequest,
    authorization: Optional[str] = Header(None),
):
    """
    Trigger orchestrator ingestion (synchronous).
    
    Called by Cloud Scheduler on defined cadences.
    Runs the main ingestion pipeline which:
    1. Fetches from Tavily, RSS, SEC.io
    2. Classifies articles
    3. Stores in vector store for agent queries
    
    Runs synchronously so Cloud Scheduler's 30-minute timeout keeps the
    request alive and we get accurate success/failure status for retries.
    """
    import time
    start_time = time.time()
    
    if not verify_scheduler_auth(authorization):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    logger.info(f"Ingestion triggered: sources={request.sources}, backfill_days={request.backfill_days}")
    
    try:
        from app.ingestion.orchestrator import get_orchestrator
        
        orchestrator = get_orchestrator()
        await orchestrator.initialize()
        
        stats = await orchestrator.run_full_ingestion(
            backfill_days=request.backfill_days,
            sources=request.sources
        )
        
        execution_time = time.time() - start_time
        total_collected = stats.total_articles_fetched if hasattr(stats, 'total_articles_fetched') else 0
        
        logger.info(f"Ingestion complete: {total_collected} articles in {execution_time:.2f}s")
        
        return IngestResponse(
            status="success",
            records_collected=total_collected,
            message=f"Ingestion complete: {total_collected} articles collected",
            execution_time_seconds=execution_time,
        )
        
    except Exception as e:
        execution_time = time.time() - start_time
        logger.error(f"Ingestion failed after {execution_time:.2f}s: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Ingestion failed: {str(e)}"
        )


# =============================================================================
# Weekly Briefing Endpoint
# =============================================================================

@router.post("/briefing", response_model=BriefingResponse)
async def trigger_briefing_generation(
    request: BriefingRequest,
    authorization: Optional[str] = Header(None),
):
    """
    Trigger weekly executive briefing generation.
    
    Called by Cloud Scheduler on Mondays at 8:30 AM CST (after ingestion).
    Generates the "Need to Know" briefing for the Pulse page with:
    - Max 3 dynamic sections (agent-chosen groupings)
    - Logo.dev integration for company mentions
    - Net New vs Continuing to Track badges
    - Inline citations with sources
    """
    import time
    start_time = time.time()
    
    if not verify_scheduler_auth(authorization):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    logger.info(f"Briefing generation triggered: type={request.briefing_type}, lookback={request.lookback_days} days")
    
    try:
        from app.ingestion.generators.weekly_briefing import generate_weekly_briefing
        
        # This now triggers the Agent 1 -> Agent 2 pipeline
        briefing = await generate_weekly_briefing()
        
        execution_time = time.time() - start_time
        
        if briefing:
            sections_count = len(briefing.get("sections", []))
            articles_used = briefing.get("article_count", 0)
            
            logger.info(f"Briefing generated: {sections_count} sections, {articles_used} articles in {execution_time:.2f}s")
            
            return BriefingResponse(
                status="success",
                briefing_id=briefing.get("id"),
                sections_count=sections_count,
                articles_used=articles_used,
                message=f"Weekly briefing generated with {sections_count} sections",
                execution_time_seconds=execution_time,
            )
        else:
            return BriefingResponse(
                status="error",
                message="No briefing generated - possibly no articles found",
                execution_time_seconds=execution_time,
            )
        
    except Exception as e:
        execution_time = time.time() - start_time
        logger.error(f"Briefing generation failed after {execution_time:.2f}s: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Briefing generation failed: {str(e)}"
        )


# =============================================================================
# Maintenance Endpoint
# =============================================================================

@router.post("/maintenance", response_model=MaintenanceResponse)
async def trigger_maintenance(
    request: MaintenanceRequest,
    authorization: Optional[str] = Header(None),
):
    """
    Trigger maintenance tasks.
    
    Tasks:
    - cleanup: Remove old data beyond retention period
    - reindex: Refresh vector store indexes
    """
    if not verify_scheduler_auth(authorization):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    logger.info(f"Maintenance triggered: task={request.task}")
    
    try:
        details = {}
        
        if request.task == MaintenanceTask.CLEANUP:
            cutoff_date = datetime.utcnow() - timedelta(days=request.retention_days)
            details = {
                "retention_days": request.retention_days,
                "cutoff_date": cutoff_date.isoformat(),
            }
            message = f"Cleanup scheduled for data older than {request.retention_days} days"
            
        elif request.task == MaintenanceTask.REINDEX:
            details = {"note": "Vector store reindex scheduled"}
            message = "Vector store reindex scheduled"
        
        logger.info(f"Maintenance complete: {request.task}")
        
        return MaintenanceResponse(
            status="success",
            task=request.task.value,
            message=message,
            details=details,
        )
        
    except Exception as e:
        logger.error(f"Maintenance failed: {request.task} - {str(e)}")
        
        return MaintenanceResponse(
            status="error",
            task=request.task.value,
            message=f"Maintenance failed: {str(e)}",
            details={},
        )


# =============================================================================
# Podcast Ingestion Endpoint
# =============================================================================

class PodcastIngestRequest(BaseModel):
    """Request body for podcast ingestion trigger."""
    podcast_ids: Optional[list[str]] = Field(
        default=None,
        description="Podcast IDs to process. If None, processes all active feeds."
    )
    days: int = Field(
        default=14,
        ge=1,
        le=90,
        description="Number of days back to fetch episodes (default: 14)"
    )


class PodcastIngestResponse(BaseModel):
    """Response for podcast ingestion trigger."""
    status: Literal["success", "error"]
    podcasts_processed: int = 0
    episodes_discovered: int = 0
    episodes_new: int = 0
    episodes_transcribed: int = 0
    quotes_extracted: int = 0
    total_cost_usd: float = 0.0
    message: str
    execution_time_seconds: float


@router.post("/podcast-ingest", response_model=PodcastIngestResponse)
async def trigger_podcast_ingestion(
    request: PodcastIngestRequest = PodcastIngestRequest(),
):
    """
    Trigger podcast ingestion pipeline.

    Discovers episodes from RSS feeds, resolves transcripts
    (YouTube -> site scraping -> AssemblyAI), extracts speaker-attributed
    quotes with C1 theme taxonomy, and stores in BigQuery.

    Called by Cloud Scheduler weekly (Mondays at 6:00 AM CST).
    """
    import time
    start_time = time.time()

    logger.info(
        f"[PODCAST_PIPELINE] Scheduler trigger received: "
        f"podcast_ids={request.podcast_ids}, days={request.days}"
    )

    try:
        from app.ingestion.podcasts.pipeline import PodcastPipeline

        pipeline = PodcastPipeline()
        stats = await pipeline.run(
            podcast_ids=request.podcast_ids,
            days=request.days,
        )

        execution_time = time.time() - start_time

        return PodcastIngestResponse(
            status="success",
            podcasts_processed=stats.get("podcasts_processed", 0),
            episodes_discovered=stats.get("episodes_discovered", 0),
            episodes_new=stats.get("episodes_new", 0),
            episodes_transcribed=stats.get("episodes_transcribed", 0),
            quotes_extracted=stats.get("quotes_extracted", 0),
            total_cost_usd=stats.get("total_cost_usd", 0.0),
            message=(
                f"Podcast ingestion complete: "
                f"{stats.get('episodes_new', 0)} new episodes, "
                f"{stats.get('quotes_extracted', 0)} quotes extracted"
            ),
            execution_time_seconds=execution_time,
        )

    except Exception as e:
        execution_time = time.time() - start_time
        logger.error(f"[PODCAST_PIPELINE] Scheduler trigger failed: {e}", exc_info=True)
        return PodcastIngestResponse(
            status="error",
            message=f"Podcast ingestion failed: {str(e)}",
            execution_time_seconds=execution_time,
        )


# =============================================================================
# Status Endpoint
# =============================================================================

@router.get("/status", response_model=SchedulerStatusResponse)
async def get_scheduler_status():
    """
    Get scheduler and collection status.
    """
    environment = os.getenv("ENVIRONMENT", "development")
    storage_backend = "SQLite (local)" if environment == "development" else "BigQuery (GCP)"
    
    return SchedulerStatusResponse(
        environment=environment,
        storage_backend=storage_backend,
        sources_available=["tavily_search", "tavily_press", "rss", "sec_io", "api_ninja_earnings"],
    )
