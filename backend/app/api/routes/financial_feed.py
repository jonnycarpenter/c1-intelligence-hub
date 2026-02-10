"""Financial Feed API - Combined earnings quotes and SEC filing nuggets feed."""

import asyncio
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

class FinancialFeedItem(BaseModel):
    id: str
    source_type: str  # "earnings" or "sec"
    text: str
    context: Optional[str] = None
    ticker: str
    company_name: Optional[str] = None
    # Earnings-specific
    speaker_name: Optional[str] = None
    speaker_role: Optional[str] = None
    speaker_title: Optional[str] = None
    speaker_company: Optional[str] = None
    sentiment: Optional[str] = None
    confidence_level: Optional[str] = None
    quote_type: Optional[str] = None
    call_section: Optional[str] = None
    year: Optional[int] = None
    quarter: Optional[int] = None
    # SEC-specific
    filing_type: Optional[str] = None
    section: Optional[str] = None
    nugget_type: Optional[str] = None
    signal_strength: Optional[str] = None
    risk_level: Optional[str] = None
    is_new_disclosure: Optional[bool] = None
    is_actionable: Optional[bool] = None
    # Common
    themes: List[str] = []
    relevance_score: float = 0.0
    date: Optional[str] = None


class FinancialFeedResponse(BaseModel):
    items: List[FinancialFeedItem]
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


def _normalize_earnings_quote(row: dict) -> FinancialFeedItem:
    """Convert an earnings_quotes BigQuery row to a FinancialFeedItem."""
    return FinancialFeedItem(
        id=row.get("quote_id", ""),
        source_type="earnings",
        text=row.get("quote_text", ""),
        context=row.get("context_summary"),
        ticker=row.get("ticker", ""),
        company_name=row.get("company_name"),
        speaker_name=row.get("speaker_name"),
        speaker_role=row.get("speaker_role"),
        speaker_title=row.get("speaker_title"),
        speaker_company=row.get("speaker_company"),
        sentiment=row.get("sentiment"),
        confidence_level=row.get("confidence_level"),
        quote_type=row.get("quote_type"),
        call_section=row.get("call_section"),
        year=row.get("year"),
        quarter=row.get("quarter"),
        themes=_parse_themes(row.get("themes")),
        relevance_score=row.get("relevance_score") or 0.0,
        date=row.get("call_date"),
    )


def _normalize_sec_nugget(row: dict) -> FinancialFeedItem:
    """Convert a sec_filing_nuggets BigQuery row to a FinancialFeedItem."""
    return FinancialFeedItem(
        id=row.get("nugget_id", ""),
        source_type="sec",
        text=row.get("nugget_text", ""),
        context=row.get("context_text"),
        ticker=row.get("ticker", ""),
        company_name=row.get("company_name"),
        filing_type=row.get("filing_type"),
        section=row.get("section"),
        nugget_type=row.get("nugget_type"),
        signal_strength=row.get("signal_strength"),
        risk_level=row.get("risk_level"),
        is_new_disclosure=row.get("is_new_disclosure"),
        is_actionable=row.get("is_actionable"),
        themes=_parse_themes(row.get("themes")),
        relevance_score=row.get("relevance_score") or 0.0,
        date=row.get("filing_date"),
    )


# =============================================================================
# Endpoint
# =============================================================================

@router.get("/financial-feed", response_model=FinancialFeedResponse)
async def get_financial_feed(
    search: Optional[str] = Query(None, description="Full-text search"),
    source_type: Optional[str] = Query("all", description="Filter: earnings, sec, or all"),
    ticker: Optional[str] = Query(None, description="Filter by stock ticker"),
    type_filter: Optional[str] = Query(None, description="Filter by quote_type or nugget_type"),
    themes: Optional[str] = Query(None, description="Comma-separated theme codes"),
    sentiment: Optional[str] = Query(None, description="Sentiment filter (earnings only): bullish, bearish, cautious, neutral"),
    sort_by: Optional[str] = Query("newest", description="Sort: newest or relevance"),
    limit: int = Query(40, description="Items per page", ge=1, le=200),
    offset: int = Query(0, description="Pagination offset", ge=0),
):
    """
    Combined feed of earnings call quotes and SEC filing nuggets.

    Returns a merged, sorted list of financial intelligence items
    with a source_type discriminator for distinct card rendering.
    """
    logger.info(f"[FINANCIAL_FEED] Request: source={source_type}, ticker={ticker}, search={search}, limit={limit}, offset={offset}")

    try:
        storage = await get_storage()

        theme_list = [t.strip() for t in themes.split(",")] if themes else None
        fetch_earnings = source_type in ("all", "earnings")
        fetch_sec = source_type in ("all", "sec")

        # Build kwargs for each query
        earnings_kwargs = {}
        sec_kwargs = {}

        if search:
            earnings_kwargs["search_query"] = search
            sec_kwargs["search_query"] = search
        if ticker:
            earnings_kwargs["ticker"] = ticker
            sec_kwargs["ticker"] = ticker
        if theme_list:
            earnings_kwargs["themes"] = theme_list
            sec_kwargs["themes"] = theme_list
        if sentiment and fetch_earnings:
            # Sentiment is earnings-only; filter applied post-query since storage method doesn't support it
            pass
        if type_filter:
            earnings_kwargs["quote_type"] = type_filter
            sec_kwargs["nugget_type"] = type_filter

        # Fetch a generous amount to allow merged sorting + pagination
        fetch_limit = limit + offset + 50
        earnings_kwargs["limit"] = fetch_limit
        sec_kwargs["limit"] = fetch_limit

        # Parallel fetch
        earnings_items: List[FinancialFeedItem] = []
        sec_items: List[FinancialFeedItem] = []

        if fetch_earnings and fetch_sec:
            earnings_raw, sec_raw = await asyncio.gather(
                storage.get_earnings_quotes(**earnings_kwargs),
                storage.get_sec_filing_nuggets(**sec_kwargs),
            )
            earnings_items = [_normalize_earnings_quote(r) for r in earnings_raw]
            sec_items = [_normalize_sec_nugget(r) for r in sec_raw]
        elif fetch_earnings:
            earnings_raw = await storage.get_earnings_quotes(**earnings_kwargs)
            earnings_items = [_normalize_earnings_quote(r) for r in earnings_raw]
        elif fetch_sec:
            sec_raw = await storage.get_sec_filing_nuggets(**sec_kwargs)
            sec_items = [_normalize_sec_nugget(r) for r in sec_raw]

        # Merge
        all_items = earnings_items + sec_items

        # Post-query sentiment filter (earnings only)
        if sentiment:
            all_items = [i for i in all_items if i.source_type != "earnings" or i.sentiment == sentiment]

        # Sort
        if sort_by == "relevance":
            all_items.sort(key=lambda x: x.relevance_score or 0.0, reverse=True)
        else:
            # newest: sort by date descending, items without dates go last
            all_items.sort(key=lambda x: x.date or "", reverse=True)

        total_count = len(all_items)
        paginated = all_items[offset:offset + limit]

        logger.info(f"[FINANCIAL_FEED] Returning {len(paginated)} of {total_count} items")

        return FinancialFeedResponse(
            items=paginated,
            total_count=total_count,
            has_more=(offset + limit) < total_count,
        )

    except Exception as e:
        logger.error(f"[FINANCIAL_FEED] Error: {e}", exc_info=True)
        return FinancialFeedResponse(items=[], total_count=0, has_more=False)
