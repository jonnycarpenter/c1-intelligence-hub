"""Digest API endpoints - Intelligence Digest/Pulse functionality."""

import uuid
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query

from app.api.schemas import (
    Digest,
    DigestItem,
    DigestStats,
    DigestRequest,
    DigestCategory,
    DigestEntities,
    Priority,
    Source,
)
from app.utils.logger import get_logger
from app.services.digest_service import DigestService

logger = get_logger(__name__)
router = APIRouter()

# Initialize digest service
digest_service = DigestService()


@router.get("", response_model=Digest)
async def get_digest(
    hours: Optional[int] = Query(72, description="Number of hours to look back"),
    categories: Optional[str] = Query(None, description="Comma-separated categories to filter"),
    priorities: Optional[str] = Query(None, description="Comma-separated priorities to filter"),
    limit: Optional[int] = Query(100, description="Max items to return (default 100, max 1000)"),
):
    """
    Get the current intelligence digest.
    
    This returns pre-computed digest items from the last N hours,
    filtered by optional category and priority.
    
    Categories: priority, competitor, market, regulatory, product, c1_mention
    Priorities: high, medium, low
    """
    logger.info(f"Digest request: hours={hours}, categories={categories}, priorities={priorities}, limit={limit}")
    
    try:
        # Parse filter parameters
        category_list = None
        if categories:
            # Map common frontend slugs to Title Case enum values
            enum_map = {c.value.lower().replace(" ", "_"): c for c in DigestCategory}
            parsed_cats = []
            for c in categories.split(","):
                val = c.strip().lower()
                if val in enum_map:
                    parsed_cats.append(enum_map[val])
                else:
                    # Fallback to direct lookup which handles Title Case
                    parsed_cats.append(DigestCategory(c.strip()))
            category_list = parsed_cats
        
        priority_list = None
        if priorities:
            priority_list = [Priority(p.strip()) for p in priorities.split(",")]
        
        # Clamp limit to reasonable bounds
        safe_limit = max(1, min(limit or 100, 1000))
        
        # Get digest from service
        digest = await digest_service.get_digest(
            hours=hours,
            categories=category_list,
            priorities=priority_list,
            limit=safe_limit,
        )
        
        return digest
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting digest: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve digest")


@router.post("/refresh", response_model=Digest)
async def refresh_digest():
    """
    Force refresh the intelligence digest.
    
    This clears cache and regenerates the digest from stored items.
    """
    logger.info("Digest refresh requested")
    
    try:
        digest = await digest_service.refresh_digest()
        return digest
        
    except Exception as e:
        logger.error(f"Error refreshing digest: {e}")
        raise HTTPException(status_code=500, detail="Failed to refresh digest")


@router.post("/ingest")
async def trigger_ingest():
    """
    Trigger digest ingestion pipeline.
    
    This fetches new articles, classifies them with LLM,
    and stores them for the digest. Admin/internal use.
    """
    logger.info("Manual digest ingestion triggered")
    
    try:
        result = await digest_service.trigger_ingestion()
        return result
        
    except Exception as e:
        logger.error(f"Error triggering ingestion: {e}")
        raise HTTPException(status_code=500, detail="Failed to trigger ingestion")


@router.get("/item/{item_id}", response_model=DigestItem)
async def get_digest_item(item_id: str):
    """
    Get a specific digest item by ID.
    
    Returns full details for a single digest item.
    """
    try:
        item = await digest_service.get_item(item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Digest item not found")
        return item
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting digest item: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve digest item")


@router.get("/stats", response_model=DigestStats)
async def get_digest_stats(
    hours: Optional[int] = Query(72, description="Number of hours to look back"),
):
    """
    Get statistics for the digest without full item details.
    
    Useful for dashboard widgets showing counts by category/priority.
    """
    try:
        stats = await digest_service.get_stats(hours=hours)
        return stats
        
    except Exception as e:
        logger.error(f"Error getting digest stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve stats")


@router.get("/data-freshness")
async def get_data_freshness():
    """
    Get the date of the most recent article in the corpus.
    
    Used by the frontend header to show "Data through [date]".
    Very lightweight query (single row aggregate, cached).
    """
    try:
        from app.db.gcp_storage import get_storage
        storage = await get_storage()
        
        # Check if storage has the method, otherwise fall back
        if hasattr(storage, 'client') and hasattr(storage, 'config'):
            # Demo mode: cap at the frozen horizon so stray future-dated
            # articles don't show as the "Data through" date
            demo_cap = ""
            from app.config.settings import settings
            if settings.demo_mode:
                try:
                    frozen = datetime.fromisoformat(settings.demo_frozen_now)
                    demo_cap = f"WHERE published_at <= TIMESTAMP('{frozen.strftime('%Y-%m-%d %H:%M:%S')}')"
                except (ValueError, TypeError):
                    pass

            # BigQuery path
            query = f"""
                SELECT MAX(published_at) as latest_date
                FROM `{storage.config.full_dataset_id}.digest_items`
                {demo_cap}
            """
            rows = list(storage.client.query(query))
            if rows and rows[0].latest_date:
                return {
                    "latest_date": rows[0].latest_date.isoformat(),
                    "formatted": rows[0].latest_date.strftime("%B %d, %Y"),
                }
        
        return {"latest_date": None, "formatted": None}
        
    except Exception as e:
        logger.error(f"Error getting data freshness: {e}")
        return {"latest_date": None, "formatted": None}
