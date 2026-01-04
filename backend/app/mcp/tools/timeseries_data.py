"""
Archive Search Tools
====================

Tools for searching the collected article corpus.
Provides agents with access to:
- Press release archives
- News article corpus
- Historical article data

These tools enable historical searches and grounding responses
in collected data rather than just real-time API calls.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from langchain_core.tools import tool
from pydantic import Field

from app.db.gcp_storage import get_storage, ArticleRecord
from app.utils.logger import get_logger

logger = get_logger(__name__)


# =============================================================================
# Press Release Archive Tool
# =============================================================================

@tool
def search_press_release_archive(
    company: Optional[str] = Field(default=None, description="Company name or ticker to filter (e.g., 'Hexcel', 'Toray', 'BASF')"),
    keyword: Optional[str] = Field(default=None, description="Keyword to search in title/content (e.g., 'acquisition', 'earnings', 'expansion')"),
    days: int = Field(default=30, description="Number of days to search back (default 30, max 180)"),
) -> Dict[str, Any]:
    """
    Search the collected press release archive for company announcements.
    
    Use this to find historical press releases, track company announcements,
    and identify patterns in corporate communications.
    
    Example: "What has Hexcel announced in the past 3 months?"
    """
    try:
        return asyncio.run(_search_press_releases_async(company, keyword, min(days, 180)))
    except Exception as e:
        logger.error(f"Error searching press releases: {e}")
        return {"error": str(e)}


async def _search_press_releases_async(
    company: Optional[str], 
    keyword: Optional[str], 
    days: int
) -> Dict[str, Any]:
    """Async implementation of press release search."""
    storage = await get_storage()
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    # Build search query
    search_terms = []
    if company:
        search_terms.append(company)
    if keyword:
        search_terms.append(keyword)
    
    search_query = " ".join(search_terms) if search_terms else None
    
    records = await storage.get_articles(
        source_type="press_release",
        start_date=start_date,
        end_date=end_date,
        search_query=search_query,
        limit=100,
    )
    
    if not records:
        return {
            "company": company,
            "keyword": keyword,
            "days_searched": days,
            "results_found": 0,
            "message": "No press releases found matching criteria.",
        }
    
    # Format results
    results = []
    for r in records:
        results.append({
            "title": r.title,
            "source": r.source_name,
            "published": r.published_at.strftime("%Y-%m-%d") if r.published_at else None,
            "url": r.url,
            "snippet": r.summary[:300] + "..." if r.summary and len(r.summary) > 300 else r.summary,
        })
    
    return {
        "company": company,
        "keyword": keyword,
        "days_searched": days,
        "results_found": len(results),
        "press_releases": results[:20],  # Top 20
        "note": f"Showing top 20 of {len(results)} results" if len(results) > 20 else None,
    }


# =============================================================================
# News Archive Tool
# =============================================================================

@tool
def search_news_archive(
    query: str = Field(description="Search query for news articles (company names, topics, keywords)"),
    source_type: Optional[str] = Field(default=None, description="Filter by source: 'web_news', 'rss_feed', 'sec_filing', or None for all"),
    days: int = Field(default=14, description="Number of days to search back (default 14, max 90)"),
) -> Dict[str, Any]:
    """
    Search the collected news article archive.
    
    Use this to find historical news coverage, track media mentions,
    and identify trending topics over time. Includes web news from Tavily,
    RSS feeds from industry publications, and SEC filings.
    
    Example: "What news coverage has there been about carbon fiber supply?"
    """
    try:
        return asyncio.run(_search_news_async(query, source_type, min(days, 90)))
    except Exception as e:
        logger.error(f"Error searching news archive: {e}")
        return {"error": str(e)}


async def _search_news_async(
    query: str,
    source_type: Optional[str],
    days: int,
) -> Dict[str, Any]:
    """Async implementation of news search."""
    storage = await get_storage()
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    records = await storage.get_articles(
        source_type=source_type,
        start_date=start_date,
        end_date=end_date,
        search_query=query,
        limit=100,
    )
    
    if not records:
        return {
            "query": query,
            "source_type": source_type,
            "days_searched": days,
            "results_found": 0,
            "message": "No news articles found matching criteria.",
        }
    
    # Format results
    results = []
    for r in records:
        results.append({
            "title": r.title,
            "source": r.source_name,
            "source_type": r.source_type,
            "published": r.published_at.strftime("%Y-%m-%d %H:%M") if r.published_at else None,
            "url": r.url,
            "snippet": r.summary[:250] + "..." if r.summary and len(r.summary) > 250 else r.summary,
        })
    
    # Count by source type
    by_source: Dict[str, int] = {}
    for r in records:
        src = r.source_type or "unknown"
        by_source[src] = by_source.get(src, 0) + 1
    
    return {
        "query": query,
        "source_type": source_type,
        "days_searched": days,
        "results_found": len(results),
        "by_source": by_source,
        "articles": results[:25],  # Top 25
        "note": f"Showing top 25 of {len(results)} results" if len(results) > 25 else None,
    }


# =============================================================================
# Corpus Summary Tool
# =============================================================================

@tool
def get_corpus_summary() -> Dict[str, Any]:
    """
    Get a summary of the collected article corpus.
    
    Returns statistics about available data including:
    - Recent article count by source
    - Date range of available data
    - Topic distribution
    
    Use this to understand what historical data is available and to
    provide context for analysis.
    """
    try:
        return asyncio.run(_get_corpus_summary_async())
    except Exception as e:
        logger.error(f"Error getting corpus summary: {e}")
        return {"error": str(e)}


async def _get_corpus_summary_async() -> Dict[str, Any]:
    """Async implementation of corpus summary."""
    storage = await get_storage()
    
    week_ago = datetime.now() - timedelta(days=7)
    month_ago = datetime.now() - timedelta(days=30)
    
    # Get recent articles
    recent_articles = await storage.get_articles(
        start_date=week_ago,
        limit=200,
    )
    
    # Get month articles for broader stats
    month_articles = await storage.get_articles(
        start_date=month_ago,
        limit=500,
    )
    
    # Count by source type
    by_source: Dict[str, int] = {}
    for a in month_articles:
        src = a.source_type or "unknown"
        by_source[src] = by_source.get(src, 0) + 1
    
    # Get topic distribution
    topic_counts: Dict[str, int] = {}
    for a in month_articles:
        if a.topics:
            for topic in a.topics:
                topic_counts[topic] = topic_counts.get(topic, 0) + 1
    
    # Top topics
    top_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    
    return {
        "summary_date": datetime.now().isoformat(),
        "last_7_days": {
            "total_articles": len(recent_articles),
        },
        "last_30_days": {
            "total_articles": len(month_articles),
            "by_source_type": by_source,
            "top_topics": [{"topic": t[0], "count": t[1]} for t in top_topics],
        },
        "data_sources": [
            "Tavily Web Search",
            "Tavily Press Releases", 
            "RSS Feeds (Industry Publications)",
            "SEC.io Filings",
            "Drewry World Container Index (Freight Rates)",
        ],
    }


# =============================================================================
# Freight Intelligence Tool
# =============================================================================

@tool
def get_freight_rates(
    lane: Optional[str] = Field(default=None, description="Trade lane to filter by (e.g., 'Shanghai - Los Angeles', 'Composite Index')"),
    days: int = Field(default=30, description="Number of days of history to retrieve (default 30)"),
) -> Dict[str, Any]:
    """
    Get shipping freight rates and container costs from the Drewry World Container Index.
    
    Provides current rates and historical trends for major global shipping lanes.
    Useful for estimating logistics costs, analyzing supply chain inflation, 
    and identifying global trade headwinds.
    
    Lanes available: Composite Index, Shanghai - Rotterdam, Rotterdam - Shanghai, 
    Shanghai - Genoa, Shanghai - Los Angeles, Los Angeles - Shanghai, 
    Shanghai - New York, New York - Rotterdam, Rotterdam - New York.
    """
    try:
        return asyncio.run(_get_freight_rates_async(lane, days))
    except Exception as e:
        logger.error(f"Error fetching freight rates: {e}")
        return {"error": str(e)}


async def _get_freight_rates_async(lane: Optional[str], days: int) -> Dict[str, Any]:
    """Async implementation of freight rates retrieval."""
    storage = await get_storage()
    
    start_date = datetime.now() - timedelta(days=days)
    
    records = await storage.get_freight_rates(
        lane=lane,
        start_date=start_date,
        limit=200
    )
    
    if not records:
        return {
            "lane": lane,
            "days_searched": days,
            "results_count": 0,
            "message": "No freight rate data found for the specified criteria. Check if data ingestion has run."
        }
    
    # Format results
    formatted_rates = []
    for r in records:
        formatted_rates.append({
            "lane": r.lane,
            "rate": r.rate,
            "currency": r.currency,
            "unit": r.unit,
            "change_pct": r.change_pct,
            "as_of": r.as_of.strftime("%Y-%m-%d") if r.as_of else None,
            "source": r.source
        })
    
    # Group by lane for easier analysis if multiple lanes were returned
    by_lane = {}
    for r in formatted_rates:
        l = r["lane"]
        if l not in by_lane:
            by_lane[l] = []
        by_lane[l].append(r)
    
    # Get latest rate for each lane
    latest_rates = {}
    for l, items in by_lane.items():
        # Sorted by as_of desc already from storage
        latest_rates[l] = items[0]
        
    return {
        "search_lane": lane,
        "days_searched": days,
        "total_records": len(formatted_rates),
        "latest_rates": latest_rates,
        "historical_data": formatted_rates if lane else "Filter by lane to see full history",
        "available_lanes": list(latest_rates.keys())
    }
