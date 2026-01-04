"""
Data Ingestion API Routes
=========================

Endpoints for querying collected articles from the corpus.
Data collection is handled by the orchestrator workflow.

Endpoints:
- GET /api/data/articles - Get recent articles from the corpus
- GET /api/data/status - Get collection status
"""

from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.db.gcp_storage import get_storage
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/data", tags=["data"])


# =============================================================================
# Response Models
# =============================================================================

class DataStatusResponse(BaseModel):
    """Data status response."""
    storage_type: str  # local or bigquery
    articles: dict
    last_check: str


# =============================================================================
# Data Query Endpoints
# =============================================================================

@router.get("/status", response_model=DataStatusResponse)
async def get_data_status():
    """
    Get data collection status and latest timestamps.
    
    Use this to monitor that the corpus has recent data.
    """
    storage = await get_storage()
    
    # Determine storage type
    storage_type = "bigquery" if hasattr(storage, "client") else "local"
    
    try:
        article_records = await storage.get_articles(limit=1)
        article_status = {
            "latest_date": article_records[0].published_at.isoformat() if article_records else None,
            "has_data": len(article_records) > 0,
        }
    except Exception as e:
        article_status = {"error": str(e)}
    
    return DataStatusResponse(
        storage_type=storage_type,
        articles=article_status,
        last_check=datetime.utcnow().isoformat(),
    )


@router.get("/articles")
async def get_articles(
    source_type: Optional[str] = Query(None, description="Filter by source type (web_news, rss_feed, sec_filing, press_release)"),
    category: Optional[str] = Query(None, description="Filter by category"),
    search: Optional[str] = Query(None, description="Search in title/summary"),
    days_back: int = Query(14, description="Number of days of history"),
    limit: int = Query(50, description="Max records to return"),
):
    """
    Get collected articles from the corpus.
    
    Examples:
    - /api/data/articles - Recent articles
    - /api/data/articles?source_type=sec_filing - SEC filings only
    - /api/data/articles?search=carbon fiber - Search for specific topics
    """
    storage = await get_storage()
    
    start_date = datetime.utcnow() - timedelta(days=days_back)
    
    records = await storage.get_articles(
        source_type=source_type,
        category=category,
        search_query=search,
        start_date=start_date,
        limit=limit,
    )
    
    return {
        "count": len(records),
        "days_back": days_back,
        "articles": [
            {
                "id": r.id,
                "title": r.title,
                "url": r.url,
                "published_at": r.published_at.isoformat(),
                "source_name": r.source_name,
                "source_type": r.source_type,
                "summary": r.summary[:200] if r.summary else None,
                "category": r.category,
                "topics": r.topics,
            }
            for r in records
        ],
    }
