"""Expert Feed API - Podcast quote insights feed."""

import json
from typing import Optional, List
from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.db.gcp_storage import get_storage
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


# =============================================================================
# Response Models
# =============================================================================

class ExpertFeedItem(BaseModel):
    id: str
    quote_text: str
    context_summary: Optional[str] = None
    speaker_name: str
    speaker_role: Optional[str] = None
    speaker_title: Optional[str] = None
    speaker_company: Optional[str] = None
    podcast_name: str
    episode_title: Optional[str] = None
    episode_url: Optional[str] = None
    published_at: Optional[str] = None
    themes: List[str] = []
    relevance_score: float = 0.0


class ExpertFeedResponse(BaseModel):
    items: List[ExpertFeedItem]
    total_count: int
    has_more: bool


# =============================================================================
# Helpers
# =============================================================================

def _parse_themes(raw: Optional[str]) -> List[str]:
    """Parse themes from JSON string or return empty list."""
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(t) for t in parsed]
    except (json.JSONDecodeError, TypeError):
        pass
    return []


def _normalize_podcast_quote(row: dict) -> ExpertFeedItem:
    """Convert a podcast_quotes BigQuery row to an ExpertFeedItem."""
    published = row.get("published_at")
    if published and hasattr(published, "isoformat"):
        published = published.isoformat()

    return ExpertFeedItem(
        id=row.get("id", ""),
        quote_text=row.get("quote_text", ""),
        context_summary=row.get("context_summary"),
        speaker_name=row.get("speaker_name", "Unknown"),
        speaker_role=row.get("speaker_role"),
        speaker_title=row.get("speaker_title"),
        speaker_company=row.get("speaker_company"),
        podcast_name=row.get("podcast_name", "Unknown Podcast"),
        episode_title=row.get("episode_title"),
        episode_url=row.get("episode_url"),
        published_at=str(published) if published else None,
        themes=_parse_themes(row.get("themes")),
        relevance_score=row.get("relevance_score") or 0.0,
    )


# =============================================================================
# Endpoint
# =============================================================================

TIME_RANGE_DAYS = {"7d": 7, "14d": 14, "30d": 30, "90d": 90, "180d": 180}


@router.get("/expert-feed", response_model=ExpertFeedResponse)
async def get_expert_feed(
    search: Optional[str] = Query(None, description="Full-text search"),
    podcast_name: Optional[str] = Query(None, description="Filter by podcast name"),
    speaker_name: Optional[str] = Query(None, description="Filter by speaker name"),
    themes: Optional[str] = Query(None, description="Comma-separated theme codes"),
    time_range: Optional[str] = Query("90d", description="Time range: 7d, 14d, 30d, 90d, 180d"),
    sort_by: Optional[str] = Query("newest", description="Sort: newest or relevance"),
    limit: int = Query(40, description="Items per page", ge=1, le=200),
    offset: int = Query(0, description="Pagination offset", ge=0),
):
    """
    Feed of podcast quote insights from industry expert interviews.

    Returns podcast quotes with speaker attribution, episode links, and theme tags.
    """
    logger.info(f"[EXPERT_FEED] Request: podcast={podcast_name}, speaker={speaker_name}, search={search}, limit={limit}, offset={offset}")

    try:
        storage = await get_storage()

        days = TIME_RANGE_DAYS.get(time_range or "90d", 90)
        theme_list = [t.strip() for t in themes.split(",")] if themes else None

        kwargs = {
            "days": days,
            "limit": limit + offset + 50,  # Fetch extra for pagination
        }
        if search:
            kwargs["search_query"] = search
        if podcast_name:
            kwargs["podcast_name"] = podcast_name
        if speaker_name:
            kwargs["speaker_name"] = speaker_name
        if theme_list:
            kwargs["themes"] = theme_list

        raw = await storage.get_podcast_quotes(**kwargs)
        items = [_normalize_podcast_quote(r) for r in raw]

        # Sort
        if sort_by == "relevance":
            items.sort(key=lambda x: x.relevance_score or 0.0, reverse=True)
        else:
            items.sort(key=lambda x: x.published_at or "", reverse=True)

        total_count = len(items)
        paginated = items[offset:offset + limit]

        logger.info(f"[EXPERT_FEED] Returning {len(paginated)} of {total_count} items")

        return ExpertFeedResponse(
            items=paginated,
            total_count=total_count,
            has_more=(offset + limit) < total_count,
        )

    except Exception as e:
        logger.error(f"[EXPERT_FEED] Error: {e}", exc_info=True)
        return ExpertFeedResponse(items=[], total_count=0, has_more=False)
