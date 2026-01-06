"""
StockNewsAPI MCP Tools

Provides on-demand news retrieval capabilities for the multi-agent research workflow:
- get_company_news: Fetch recent news for specific company tickers
- search_news_keyword: Search financial news by keyword or phrase
- get_press_releases: Fetch official press releases for companies
- get_analyst_ratings: Fetch analyst upgrades, downgrades, and price target changes
- get_sentiment_summary: Get aggregated sentiment for a company
- get_trending_headlines: Get trending headlines with high news coverage
"""

from typing import Optional, List
import json
import httpx
from datetime import datetime
from langchain_core.tools import tool

from app.config.settings import settings
from app.utils.logger import get_logger
from app.utils.retry import retry_with_backoff, skip_on_failure, tool_metrics
import time

logger = get_logger(__name__)

# Base URL for StockNewsAPI
STOCKNEWS_BASE_URL = "https://stocknewsapi.com/api/v1"


def _get_api_key() -> Optional[str]:
    """Get StockNewsAPI key from settings."""
    return settings.stocknews_api_key


def _format_article(article: dict) -> dict:
    """Format a single article with consistent structure."""
    return {
        "title": article.get("title", ""),
        "text": article.get("text", "")[:500] + "..." if len(article.get("text", "")) > 500 else article.get("text", ""),
        "source": article.get("source_name", article.get("source", "")),
        "url": article.get("news_url", article.get("url", "")),
        "published_date": article.get("date", ""),
        "sentiment": article.get("sentiment", ""),
        "tickers": article.get("tickers", []),
        "rank_score": article.get("rankscore", 0),
    }


@tool
@skip_on_failure(default_return=json.dumps({"error": "Service temporarily unavailable", "skipped": True}), log_level="warning")
def get_company_news(
    tickers: List[str],
    days: int = 7,
    sentiment: Optional[str] = None,
    items: int = 20,
) -> str:
    """
    Fetch recent financial news for specific company tickers.
    
    Use this tool to get news about publicly traded companies in the composites,
    aerospace, wind energy, and related industries.
    
    Key Ticker Reference:
    - Composites: HXL (Hexcel), OC (Owens Corning), TRYIY (Toray), SOLVY (Solvay), TPIC (TPI Composites)
    - Aerospace: BA (Boeing), EADSY (Airbus), RTX, LMT (Lockheed), NOC (Northrop), GE, GD
    - Wind Energy: VWDRY (Vestas), GEV (GE Vernova), GCTAF (Siemens Gamesa)
    - Marine: BC (Brunswick), MBUU (Malibu Boats)
    
    Args:
        tickers: List of stock symbols (e.g., ["HXL", "BA", "OC"])
        days: Days to look back (1-365, default: 7)
        sentiment: Optional filter - "positive", "negative", or "neutral"
        items: Number of articles (1-100, default: 20)
    
    Returns:
        JSON string with articles containing: title, text, source, url, 
        published_date, sentiment, tickers, rank_score
    """
    logger.info(f"Fetching company news: tickers={tickers}, days={days}, items={items}")
    start_time = time.time()
    
    api_key = _get_api_key()
    if not api_key:
        tool_metrics.record_failure("get_company_news", "API key not configured")
        return json.dumps({"error": "StockNewsAPI key not configured"})
    
    try:
        # Build params
        params = {
            "tickers": ",".join(tickers),
            "items": min(items, 100),
            "days": min(days, 365),
            "type": "article",
            "sortby": "rank",
            "extra": "rankscore,id",
            "token": api_key,
        }
        
        if sentiment and sentiment in ["positive", "negative", "neutral"]:
            params["sentiment"] = sentiment
        
        with httpx.Client(timeout=30) as client:
            response = client.get(STOCKNEWS_BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()
        
        articles = data.get("data", [])
        if not articles:
            return json.dumps({
                "message": f"No news found for tickers: {tickers}",
                "tickers": tickers,
                "days": days,
                "total_results": 0,
            })
        
        formatted_articles = [_format_article(a) for a in articles]
        
        duration = time.time() - start_time
        tool_metrics.record_success("get_company_news", duration)
        
        return json.dumps({
            "source": "StockNewsAPI",
            "tickers": tickers,
            "days": days,
            "total_results": len(formatted_articles),
            "articles": formatted_articles,
        })
        
    except httpx.HTTPStatusError as e:
        duration = time.time() - start_time
        error_msg = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
        tool_metrics.record_failure("get_company_news", error_msg, duration)
        logger.error(f"StockNewsAPI HTTP error: {error_msg}")
        # Raise to trigger skip_on_failure decorator
        raise
    except Exception as e:
        duration = time.time() - start_time
        tool_metrics.record_failure("get_company_news", str(e), duration)
        logger.error(f"StockNewsAPI error: {e}")
        # Raise to trigger skip_on_failure decorator
        raise


@tool
@skip_on_failure(default_return=json.dumps({"error": "Service temporarily unavailable", "skipped": True}), log_level="warning")
def search_news_keyword(
    keyword: str,
    days: int = 30,
    items: int = 20,
) -> str:
    """
    Search financial news by keyword or phrase.
    
    Use this for:
    - Industry terms (e.g., "carbon fiber", "wind turbine")
    - Private company names (e.g., "SpaceX", "Hexion", "Blue Origin")
    - Material/process terms (e.g., "prepreg", "composites", "thermoplastic")
    - Emerging technologies (e.g., "hydrogen storage", "eVTOL")
    
    Args:
        keyword: Search term (e.g., "composites", "SpaceX", "carbon fiber")
        days: Days to look back (1-365, default: 30)
        items: Number of articles (1-100, default: 20)
    
    Returns:
        JSON string with matching articles
    """
    logger.info(f"Searching news by keyword: keyword={keyword}, days={days}, items={items}")
    start_time = time.time()
    api_key = _get_api_key()
    if not api_key:
        tool_metrics.record_failure("search_news_keyword", "API key not configured")
        return json.dumps({"error": "StockNewsAPI key not configured"})
    try:
        url = f"{STOCKNEWS_BASE_URL}/category"
        params = {
            "search": keyword,
            "items": min(items, 100),
            "days": min(days, 365),
            "type": "article",
            "token": api_key,
        }
        
        with httpx.Client(timeout=30) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
        
        articles = data.get("data", [])
        if not articles:
            duration = time.time() - start_time
            tool_metrics.record_success("search_news_keyword", duration)
            return json.dumps({
                "message": f"No news found for keyword: {keyword}",
                "keyword": keyword,
                "days": days,
                "total_results": 0,
            })
        
        formatted_articles = [_format_article(a) for a in articles]
        
        duration = time.time() - start_time
        tool_metrics.record_success("search_news_keyword", duration)

        return json.dumps({
            "source": "StockNewsAPI",
            "keyword": keyword,
            "days": days,
            "total_results": len(formatted_articles),
            "articles": formatted_articles,
        })
        
    except httpx.HTTPStatusError as e:
        duration = time.time() - start_time
        error_msg = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
        tool_metrics.record_failure("search_news_keyword", error_msg, duration)
        logger.error(f"StockNewsAPI HTTP error: {error_msg}")
        raise
    except Exception as e:
        duration = time.time() - start_time
        tool_metrics.record_failure("search_news_keyword", str(e), duration)
        logger.error(f"StockNewsAPI error: {e}")
        raise


@tool
@skip_on_failure(default_return=json.dumps({"error": "Service temporarily unavailable", "skipped": True}), log_level="warning")
def get_press_releases(
    tickers: List[str],
    days: int = 30,
    items: int = 20,
) -> str:
    """
    Fetch official press releases for companies.
    
    Includes: Earnings announcements, M&A activity, leadership changes,
    product launches, partnership announcements.
    
    Args:
        tickers: List of stock symbols (e.g., ["HXL", "BA", "TRYIY"])
        days: Days to look back (default: 30)
        items: Number of releases (default: 20)
    
    Returns:
        JSON string with press release articles
    """
    logger.info(f"Fetching press releases: tickers={tickers}, days={days}, items={items}")
    start_time = time.time()
    api_key = _get_api_key()
    if not api_key:
        tool_metrics.record_failure("get_press_releases", "API key not configured")
        return json.dumps({"error": "StockNewsAPI key not configured"})
    
    try:
        params = {
            "tickers": ",".join(tickers),
            "items": min(items, 100),
            "days": min(days, 365),
            "type": "article",
            "topic": "pressreleases",
            "token": api_key,
        }
        
        with httpx.Client(timeout=30) as client:
            response = client.get(STOCKNEWS_BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()
        
        articles = data.get("data", [])
        if not articles:
            duration = time.time() - start_time
            tool_metrics.record_success("get_press_releases", duration)
            return json.dumps({
                "message": f"No press releases found for tickers: {tickers}",
                "tickers": tickers,
                "days": days,
                "total_results": 0,
            })
        
        formatted_articles = [_format_article(a) for a in articles]

        duration = time.time() - start_time
        tool_metrics.record_success("get_press_releases", duration)

        return json.dumps({
            "source": "StockNewsAPI Press Releases",
            "tickers": tickers,
            "days": days,
            "total_results": len(formatted_articles),
            "articles": formatted_articles,
        })
        
    except httpx.HTTPStatusError as e:
        duration = time.time() - start_time
        error_msg = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
        tool_metrics.record_failure("get_press_releases", error_msg, duration)
        logger.error(f"StockNewsAPI HTTP error: {error_msg}")
        raise
    except Exception as e:
        duration = time.time() - start_time
        tool_metrics.record_failure("get_press_releases", str(e), duration)
        logger.error(f"StockNewsAPI error: {e}")
        raise


@tool
@skip_on_failure(default_return=json.dumps({"error": "Service temporarily unavailable", "skipped": True}), log_level="warning")
def get_analyst_ratings(
    tickers: Optional[List[str]] = None,
    items: int = 20,
) -> str:
    """
    Fetch analyst upgrades, downgrades, and price target changes.
    
    Provides insights into how Wall Street views specific companies,
    including rating changes and price target adjustments.
    
    Args:
        tickers: Optional list to filter specific companies (e.g., ["HXL", "BA"])
        items: Number of ratings to return (default: 20)
    
    Returns:
        JSON string with analyst rating information
    """
    logger.info(f"Fetching analyst ratings: tickers={tickers}, items={items}")
    start_time = time.time()
    api_key = _get_api_key()
    if not api_key:
        tool_metrics.record_failure("get_analyst_ratings", "API key not configured")
        return json.dumps({"error": "StockNewsAPI key not configured"})
    
    try:
        url = f"{STOCKNEWS_BASE_URL}/stat/updown"
        params = {
            "items": min(items, 100),
            "token": api_key,
        }
        
        if tickers:
            params["tickers"] = ",".join(tickers)
        
        with httpx.Client(timeout=30) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
        
        ratings = data.get("data", [])
        if not ratings:
            duration = time.time() - start_time
            tool_metrics.record_success("get_analyst_ratings", duration)
            return json.dumps({
                "message": "No analyst ratings found",
                "tickers": tickers,
                "total_results": 0,
            })
        
        # Format ratings
        formatted_ratings = []
        for r in ratings:
            formatted_ratings.append({
                "ticker": r.get("ticker", ""),
                "company": r.get("company", ""),
                "action": r.get("action", ""),  # upgrade, downgrade, initiated, etc.
                "analyst": r.get("analyst", ""),
                "firm": r.get("firm", ""),
                "rating_from": r.get("rating_from", ""),
                "rating_to": r.get("rating_to", ""),
                "price_target_from": r.get("price_target_from"),
                "price_target_to": r.get("price_target_to"),
                "date": r.get("date", ""),
            })
        
        duration = time.time() - start_time
        tool_metrics.record_success("get_analyst_ratings", duration)

        return json.dumps({
            "source": "StockNewsAPI Analyst Ratings",
            "tickers": tickers,
            "total_results": len(formatted_ratings),
            "ratings": formatted_ratings,
        })
        
    except httpx.HTTPStatusError as e:
        duration = time.time() - start_time
        error_msg = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
        tool_metrics.record_failure("get_analyst_ratings", error_msg, duration)
        logger.error(f"StockNewsAPI HTTP error: {error_msg}")
        raise
    except Exception as e:
        duration = time.time() - start_time
        tool_metrics.record_failure("get_analyst_ratings", str(e), duration)
        logger.error(f"StockNewsAPI error: {e}")
        raise


@tool
def get_sentiment_summary(
    ticker: str,
    days: int = 30,
) -> str:
    """
    Get aggregated news sentiment for a company.
    
    Provides a sentiment overview showing positive, negative, and neutral
    news coverage ratios over the specified period.
    
    Args:
        ticker: Single stock symbol (e.g., "HXL", "BA")
        days: Analysis period (default: 30)
    
    Returns:
        JSON string with sentiment breakdown
    """
    logger.info(f"Fetching sentiment summary: ticker={ticker}, days={days}")
    
    api_key = _get_api_key()
    if not api_key:
        return json.dumps({"error": "StockNewsAPI key not configured"})
    
    try:
        url = f"{STOCKNEWS_BASE_URL}/stat/sentiment"
        params = {
            "tickers": ticker,
            "days": min(days, 365),
            "token": api_key,
        }
        
        with httpx.Client(timeout=30) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
        
        sentiment_data = data.get("data", {})
        if not sentiment_data:
            return json.dumps({
                "message": f"No sentiment data found for ticker: {ticker}",
                "ticker": ticker,
                "days": days,
            })
        
        return json.dumps({
            "source": "StockNewsAPI Sentiment",
            "ticker": ticker,
            "days": days,
            "sentiment": sentiment_data,
        })
        
    except httpx.HTTPStatusError as e:
        logger.error(f"StockNewsAPI HTTP error: {e}")
        return json.dumps({"error": f"HTTP error: {e.response.status_code}"})
    except Exception as e:
        logger.error(f"StockNewsAPI error: {e}")
        return json.dumps({"error": str(e)})


@tool
def get_trending_headlines(
    ticker: Optional[str] = None,
    items: int = 10,
) -> str:
    """
    Get trending/important headlines with high news coverage.
    
    Identifies the most important and widely-covered financial news stories,
    optionally filtered to a specific company.
    
    Args:
        ticker: Optional ticker to filter (None for market-wide trending news)
        items: Number of headlines (default: 10)
    
    Returns:
        JSON string with trending headlines
    """
    logger.info(f"Fetching trending headlines: ticker={ticker}, items={items}")
    
    api_key = _get_api_key()
    if not api_key:
        return json.dumps({"error": "StockNewsAPI key not configured"})
    
    try:
        url = f"{STOCKNEWS_BASE_URL}/stat/trending"
        params = {
            "items": min(items, 50),
            "token": api_key,
        }
        
        if ticker:
            params["ticker"] = ticker
        
        with httpx.Client(timeout=30) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
        
        headlines = data.get("data", [])
        if not headlines:
            return json.dumps({
                "message": "No trending headlines found",
                "ticker": ticker,
                "total_results": 0,
            })
        
        # Format headlines
        formatted_headlines = []
        for h in headlines:
            formatted_headlines.append({
                "title": h.get("title", ""),
                "url": h.get("news_url", h.get("url", "")),
                "source": h.get("source_name", h.get("source", "")),
                "published_date": h.get("date", ""),
                "tickers": h.get("tickers", []),
                "coverage_score": h.get("coverage_score", 0),
            })
        
        return json.dumps({
            "source": "StockNewsAPI Trending",
            "ticker": ticker,
            "total_results": len(formatted_headlines),
            "headlines": formatted_headlines,
        })
        
    except httpx.HTTPStatusError as e:
        logger.error(f"StockNewsAPI HTTP error: {e}")
        return json.dumps({"error": f"HTTP error: {e.response.status_code}"})
    except Exception as e:
        logger.error(f"StockNewsAPI error: {e}")
        return json.dumps({"error": str(e)})
