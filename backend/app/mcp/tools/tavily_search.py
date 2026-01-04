"""
Tavily Web Search, Extract, and Crawl Tools

Provides comprehensive web intelligence capabilities:
- web_search: Advanced search with date filtering (time_range or start_date/end_date)
- news_search: News-focused search with reliable date filtering
- extract_content: Extract content from specific URLs (for datasheets, specs)
- crawl_website: Discover and extract documents from websites
"""

from typing import Optional, List, Literal
import json
import httpx
from datetime import datetime, date
from langchain_core.tools import tool

from app.config.settings import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Base URLs for Tavily API endpoints
TAVILY_SEARCH_URL = "https://api.tavily.com/search"
TAVILY_EXTRACT_URL = "https://api.tavily.com/extract"


def _get_api_key() -> Optional[str]:
    """Get Tavily API key from settings."""
    return settings.tavily_api_key


def _parse_date(date_str: str) -> Optional[date]:
    """Parse date string in various formats to date object."""
    if not date_str:
        return None
    
    formats = [
        "%Y-%m-%d",      # 2025-07-01
        "%m/%d/%Y",      # 07/01/2025
        "%B %d, %Y",     # July 1, 2025
        "%b %d, %Y",     # Jul 1, 2025
        "%Y%m%d",        # 20250701
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue
    
    return None


def _format_results(results: List[dict], source_label: str = "Tavily") -> List[dict]:
    """Format search results with consistent structure."""
    formatted = []
    for r in results:
        formatted.append({
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "content": r.get("content", ""),
            "snippet": r.get("content", "")[:300] + "..." if len(r.get("content", "")) > 300 else r.get("content", ""),
            "published_date": r.get("published_date", ""),
            "score": r.get("score", 0),
            "source": source_label,
        })
    return formatted


@tool
def web_search(
    query: str,
    max_results: int = 10,
    search_depth: Literal["basic", "advanced"] = "advanced",
    time_range: Optional[Literal["day", "week", "month", "year"]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    include_domains: Optional[List[str]] = None,
    exclude_domains: Optional[List[str]] = None,
    include_answer: bool = True,
) -> str:
    """
    Search the web using Tavily API with advanced filtering capabilities.
    
    Use this for comprehensive web searches about companies, products, industry news,
    and market intelligence. Supports both quick time filters and specific date ranges.
    
    Date Filtering Options (use ONE approach):
    - time_range: Quick filter - "day", "week", "month", "year"
    - start_date + end_date: Specific date range (format: YYYY-MM-DD)
    
    For quarterly recaps or historical research, use start_date/end_date:
    - Q1 2025: start_date="2025-01-01", end_date="2025-03-31"
    - Q2 2025: start_date="2025-04-01", end_date="2025-06-30"
    - Q3 2025: start_date="2025-07-01", end_date="2025-09-30"
    - Q4 2025: start_date="2025-10-01", end_date="2025-12-31"
    
    Args:
        query: Search query - be specific with company names, materials, topics
        max_results: Number of results (default 10, max 20)
        search_depth: "basic" for quick search, "advanced" for comprehensive results
        time_range: Quick time filter - "day", "week", "month", "year"
        start_date: Start of date range (YYYY-MM-DD format) for historical searches
        end_date: End of date range (YYYY-MM-DD format) for historical searches
        include_domains: List of domains to limit search to (e.g., ["bloomberg.com", "reuters.com"])
        exclude_domains: List of domains to exclude from results
        include_answer: Whether to include AI-generated summary answer (default True)
    
    Returns:
        JSON with search results including title, url, content, date, relevance score
    """
    logger.info(f"Tavily web search: '{query[:60]}...' depth={search_depth}")
    
    api_key = _get_api_key()
    if not api_key:
        return json.dumps({"error": "Tavily API key not configured. Set TAVILY_API_KEY in .env"})
    
    try:
        payload = {
            "api_key": api_key,
            "query": query,
            "max_results": min(max_results, 20),
            "search_depth": search_depth,
            "include_answer": include_answer,
            "include_raw_content": False,
        }
        
        # Date filtering - prefer specific dates over time_range if both provided
        if start_date and end_date:
            # Validate and format dates
            start = _parse_date(start_date)
            end = _parse_date(end_date)
            
            if start and end:
                # Tavily uses days parameter, calculate from today
                # For historical ranges, we need to use their date parameters
                payload["start_date"] = start.isoformat()
                payload["end_date"] = end.isoformat()
                date_filter_desc = f"{start.isoformat()} to {end.isoformat()}"
            else:
                return json.dumps({"error": f"Invalid date format. Use YYYY-MM-DD. Got start={start_date}, end={end_date}"})
        elif time_range:
            # Map time_range to Tavily's days parameter
            time_map = {"day": 1, "week": 7, "month": 30, "year": 365}
            if time_range in time_map:
                payload["days"] = time_map[time_range]
                date_filter_desc = f"last {time_range}"
            else:
                date_filter_desc = "all time"
        else:
            date_filter_desc = "all time (no filter)"
        
        if include_domains:
            payload["include_domains"] = include_domains
        if exclude_domains:
            payload["exclude_domains"] = exclude_domains
        
        # Make API request
        with httpx.Client(timeout=45) as client:
            response = client.post(TAVILY_SEARCH_URL, json=payload)
            response.raise_for_status()
            data = response.json()
        
        results = _format_results(data.get("results", []), "Tavily Web Search")
        
        return json.dumps({
            "source": "Tavily Web Search",
            "query": query,
            "search_depth": search_depth,
            "date_filter": date_filter_desc,
            "answer": data.get("answer") if include_answer else None,
            "result_count": len(results),
            "results": results,
        }, indent=2)
        
    except httpx.HTTPStatusError as e:
        logger.error(f"Tavily API error: {e.response.status_code} - {e.response.text}")
        return json.dumps({"error": f"Tavily API error: {e.response.status_code}"})
    except Exception as e:
        logger.error(f"Tavily search error: {e}")
        return json.dumps({"error": str(e)})


@tool
def news_search(
    query: str,
    max_results: int = 10,
    time_range: Literal["day", "week", "month"] = "week",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    include_domains: Optional[List[str]] = None,
) -> str:
    """
    Search for news articles using Tavily with news-optimized settings.
    
    Use this for:
    - Current events and breaking news
    - Industry developments and announcements
    - Company news and press coverage
    - Market and regulatory updates
    
    For historical news (e.g., quarterly recaps), use start_date and end_date
    instead of time_range. Dates should be in YYYY-MM-DD format.
    
    Args:
        query: News search query (e.g., "carbon fiber aerospace news", "Hexcel earnings")
        max_results: Number of results (default 10, max 20)
        time_range: Quick filter - "day" (24h), "week" (7d), "month" (30d)
        start_date: Start of date range (YYYY-MM-DD) for historical searches
        end_date: End of date range (YYYY-MM-DD) for historical searches
        include_domains: Limit to specific news sources (e.g., ["reuters.com", "bloomberg.com"])
    
    Returns:
        JSON with news articles including title, url, content, date, source
    """
    logger.info(f"Tavily news search: '{query[:60]}...'")
    
    api_key = _get_api_key()
    if not api_key:
        return json.dumps({"error": "Tavily API key not configured"})
    
    try:
        payload = {
            "api_key": api_key,
            "query": f"{query} news",  # Append 'news' to improve relevance
            "max_results": min(max_results, 20),
            "search_depth": "advanced",
            "include_answer": True,
            "include_raw_content": False,
            "topic": "news",  # Tavily news topic filter
        }
        
        # Date filtering
        if start_date and end_date:
            start = _parse_date(start_date)
            end = _parse_date(end_date)
            if start and end:
                payload["start_date"] = start.isoformat()
                payload["end_date"] = end.isoformat()
                date_filter_desc = f"{start.isoformat()} to {end.isoformat()}"
            else:
                return json.dumps({"error": "Invalid date format. Use YYYY-MM-DD"})
        else:
            time_map = {"day": 1, "week": 7, "month": 30}
            payload["days"] = time_map.get(time_range, 7)
            date_filter_desc = f"last {time_range}"
        
        if include_domains:
            payload["include_domains"] = include_domains
        
        with httpx.Client(timeout=45) as client:
            response = client.post(TAVILY_SEARCH_URL, json=payload)
            response.raise_for_status()
            data = response.json()
        
        results = _format_results(data.get("results", []), "Tavily News")
        
        # Add relative date info
        today = datetime.now().date()
        for r in results:
            if r.get("published_date"):
                pub_date = _parse_date(r["published_date"])
                if pub_date:
                    days_ago = (today - pub_date).days
                    if days_ago == 0:
                        r["relative_date"] = "Today"
                    elif days_ago == 1:
                        r["relative_date"] = "Yesterday"
                    else:
                        r["relative_date"] = f"{days_ago} days ago"
        
        return json.dumps({
            "source": "Tavily News Search",
            "query": query,
            "date_filter": date_filter_desc,
            "answer": data.get("answer"),
            "result_count": len(results),
            "results": results,
        }, indent=2)
        
    except Exception as e:
        logger.error(f"Tavily news search error: {e}")
        return json.dumps({"error": str(e)})


@tool
def extract_content(
    urls: List[str],
    extract_depth: Literal["basic", "advanced"] = "basic",
) -> str:
    """
    Extract content from specific URLs using Tavily Extract API.
    
    Use this to pull detailed content from known URLs, such as:
    - Product datasheets and technical specifications
    - Company press releases and announcements
    - Technical articles and whitepapers
    - Competitor product pages
    
    The extract API retrieves the main content from each URL, filtering out
    navigation, ads, and other non-essential elements.
    
    Args:
        urls: List of URLs to extract content from (max 10)
        extract_depth: "basic" for main content, "advanced" for more thorough extraction
    
    Returns:
        JSON with extracted content for each URL including title, text, metadata
    """
    logger.info(f"Tavily extract: {len(urls)} URLs")
    
    api_key = _get_api_key()
    if not api_key:
        return json.dumps({"error": "Tavily API key not configured"})
    
    if len(urls) > 10:
        urls = urls[:10]
        logger.warning("Truncated URL list to 10 items (Tavily limit)")
    
    try:
        payload = {
            "api_key": api_key,
            "urls": urls,
        }
        
        with httpx.Client(timeout=60) as client:
            response = client.post(TAVILY_EXTRACT_URL, json=payload)
            response.raise_for_status()
            data = response.json()
        
        results = []
        for item in data.get("results", []):
            results.append({
                "url": item.get("url", ""),
                "title": item.get("title", ""),
                "content": item.get("raw_content", item.get("content", "")),
                "content_length": len(item.get("raw_content", item.get("content", ""))),
                "extraction_success": bool(item.get("raw_content") or item.get("content")),
            })
        
        # Include any failed URLs
        failed = data.get("failed_results", [])
        
        return json.dumps({
            "source": "Tavily Extract",
            "urls_requested": len(urls),
            "urls_extracted": len(results),
            "urls_failed": len(failed),
            "results": results,
            "failed_urls": failed,
        }, indent=2)
        
    except Exception as e:
        logger.error(f"Tavily extract error: {e}")
        return json.dumps({"error": str(e)})


@tool
def crawl_website(
    url: str,
    search_query: Optional[str] = None,
    max_pages: int = 10,
    include_patterns: Optional[List[str]] = None,
) -> str:
    """
    Crawl a website to discover and extract documents using Tavily.
    
    Use this to find technical documents on supplier/competitor websites:
    - Product datasheets and TDS (Technical Data Sheets)
    - Safety Data Sheets (SDS/MSDS)
    - Product catalogs and brochures
    - Technical guides and application notes
    
    The crawler will discover links on the page and extract content from
    pages matching your criteria.
    
    Args:
        url: Starting URL to crawl (e.g., "https://www.hexcel.com/Products")
        search_query: Optional query to filter relevant pages (e.g., "carbon fiber prepreg")
        max_pages: Maximum pages to crawl (default 10, max 50)
        include_patterns: URL patterns to include (e.g., ["/datasheet", "/tds", ".pdf"])
    
    Returns:
        JSON with discovered pages and their content
    """
    logger.info(f"Tavily crawl: {url}")
    
    api_key = _get_api_key()
    if not api_key:
        return json.dumps({"error": "Tavily API key not configured"})
    
    try:
        # First, search within the specific domain to find relevant pages
        from urllib.parse import urlparse
        domain = urlparse(url).netloc
        
        search_query_full = f"site:{domain} {search_query}" if search_query else f"site:{domain}"
        
        payload = {
            "api_key": api_key,
            "query": search_query_full,
            "max_results": min(max_pages, 50),
            "search_depth": "advanced",
            "include_answer": False,
            "include_domains": [domain],
        }
        
        with httpx.Client(timeout=60) as client:
            response = client.post(TAVILY_SEARCH_URL, json=payload)
            response.raise_for_status()
            data = response.json()
        
        # Filter results by URL patterns if specified
        results = data.get("results", [])
        if include_patterns:
            filtered = []
            for r in results:
                url_lower = r.get("url", "").lower()
                if any(pattern.lower() in url_lower for pattern in include_patterns):
                    filtered.append(r)
            results = filtered if filtered else results  # Fall back to all if no matches
        
        # Format results
        formatted = []
        for r in results:
            formatted.append({
                "url": r.get("url", ""),
                "title": r.get("title", ""),
                "content_preview": r.get("content", "")[:500] + "..." if len(r.get("content", "")) > 500 else r.get("content", ""),
                "score": r.get("score", 0),
                "is_pdf": ".pdf" in r.get("url", "").lower(),
            })
        
        return json.dumps({
            "source": "Tavily Crawl",
            "base_url": url,
            "domain": domain,
            "search_query": search_query,
            "pages_found": len(formatted),
            "include_patterns": include_patterns,
            "results": formatted,
        }, indent=2)
        
    except Exception as e:
        logger.error(f"Tavily crawl error: {e}")
        return json.dumps({"error": str(e)})


# Convenience function for quarterly searches
def get_quarter_dates(year: int, quarter: int) -> tuple:
    """Get start and end dates for a fiscal quarter."""
    quarters = {
        1: ("01-01", "03-31"),
        2: ("04-01", "06-30"),
        3: ("07-01", "09-30"),
        4: ("10-01", "12-31"),
    }
    if quarter not in quarters:
        raise ValueError(f"Quarter must be 1-4, got {quarter}")
    
    start_md, end_md = quarters[quarter]
    return f"{year}-{start_md}", f"{year}-{end_md}"
