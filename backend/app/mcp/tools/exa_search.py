"""
Exa.ai Web Search, Extract, and Content Tools

Provides comprehensive web intelligence capabilities with RELIABLE published dates:
- web_search: Advanced semantic search with date filtering
- news_search: News-focused search with accurate publishedDate
- extract_content: Extract content from specific URLs
- find_similar: Find similar content to a given URL

Key advantage over Tavily: Exa returns clean publishedDate fields,
critical for the 72-hour digest and 30-day executive summary features.
"""

from typing import Optional, List, Literal
import json
import httpx
from datetime import datetime, date, timedelta
from langchain_core.tools import tool

from app.config.settings import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Base URL for Exa API
EXA_BASE_URL = "https://api.exa.ai"


def _get_api_key() -> Optional[str]:
    """Get Exa API key from settings."""
    return settings.exa_api_key


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


def _format_results(results: List[dict], source_label: str = "Exa") -> List[dict]:
    """Format search results with consistent structure."""
    formatted = []
    for r in results:
        # Exa returns publishedDate in ISO format
        published_date = r.get("publishedDate", "")
        
        # Build snippet from highlights or text
        highlights = r.get("highlights", [])
        text = r.get("text", "")
        content = " ... ".join(highlights) if highlights else text
        snippet = content[:300] + "..." if len(content) > 300 else content
        
        formatted.append({
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "content": content,
            "snippet": snippet,
            "published_date": published_date,  # Clean date from Exa!
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
) -> str:
    """
    Search the web using Exa API with advanced semantic search.
    
    Use this for comprehensive web searches about companies, products, industry news,
    and market intelligence. Returns results with RELIABLE published dates.
    
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
        search_depth: "basic" for keyword search, "advanced" for neural/semantic search
        time_range: Quick time filter - "day", "week", "month", "year"
        start_date: Start of date range (YYYY-MM-DD format) for historical searches
        end_date: End of date range (YYYY-MM-DD format) for historical searches
        include_domains: List of domains to limit search to (e.g., ["bloomberg.com", "reuters.com"])
        exclude_domains: List of domains to exclude from results
    
    Returns:
        JSON with search results including title, url, content, published_date, score
    """
    logger.info(f"Exa web search: '{query[:60]}...' depth={search_depth}")
    
    api_key = _get_api_key()
    if not api_key:
        return json.dumps({"error": "Exa API key not configured. Set EXA_AI_API_KEY in .env"})
    
    try:
        headers = {
            "x-api-key": api_key,
            "Content-Type": "application/json"
        }
        
        payload = {
            "query": query,
            "numResults": min(max_results, 20),
            "useAutoprompt": search_depth == "advanced",
            "type": "neural" if search_depth == "advanced" else "keyword",
            "contents": {
                "text": {"maxCharacters": 2000},
                "highlights": True,
            }
        }
        
        # Date filtering
        date_filter_desc = "all time (no filter)"
        if start_date and end_date:
            start = _parse_date(start_date)
            end = _parse_date(end_date)
            
            if start and end:
                payload["startPublishedDate"] = f"{start.isoformat()}T00:00:00.000Z"
                payload["endPublishedDate"] = f"{end.isoformat()}T23:59:59.999Z"
                date_filter_desc = f"{start.isoformat()} to {end.isoformat()}"
            else:
                return json.dumps({"error": f"Invalid date format. Use YYYY-MM-DD. Got start={start_date}, end={end_date}"})
        elif time_range:
            time_map = {"day": 1, "week": 7, "month": 30, "year": 365}
            if time_range in time_map:
                days_back = time_map[time_range]
                start_dt = datetime.utcnow() - timedelta(days=days_back)
                payload["startPublishedDate"] = start_dt.strftime("%Y-%m-%dT00:00:00.000Z")
                date_filter_desc = f"last {time_range}"
        
        if include_domains:
            payload["includeDomains"] = include_domains
        if exclude_domains:
            payload["excludeDomains"] = exclude_domains
        
        # Make API request
        with httpx.Client(timeout=45) as client:
            response = client.post(f"{EXA_BASE_URL}/search", headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
        
        results = _format_results(data.get("results", []), "Exa Web Search")
        
        return json.dumps({
            "source": "Exa Web Search",
            "query": query,
            "search_depth": search_depth,
            "date_filter": date_filter_desc,
            "result_count": len(results),
            "results": results,
        }, indent=2)
        
    except httpx.HTTPStatusError as e:
        logger.error(f"Exa API error: {e.response.status_code} - {e.response.text}")
        return json.dumps({"error": f"Exa API error: {e.response.status_code}"})
    except Exception as e:
        logger.error(f"Exa search error: {e}")
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
    Search for news articles using Exa with news-optimized settings.
    
    Use this for:
    - Current events and breaking news
    - Industry developments and announcements
    - Company news and press coverage
    - Market and regulatory updates
    
    Returns results with RELIABLE published dates - critical for time-sensitive analysis.
    
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
        JSON with news articles including title, url, content, published_date, source
    """
    logger.info(f"Exa news search: '{query[:60]}...'")
    
    api_key = _get_api_key()
    if not api_key:
        return json.dumps({"error": "Exa API key not configured"})
    
    try:
        headers = {
            "x-api-key": api_key,
            "Content-Type": "application/json"
        }
        
        payload = {
            "query": f"{query} news",  # Append 'news' to improve relevance
            "numResults": min(max_results, 20),
            "useAutoprompt": True,
            "type": "neural",
            "category": "news",  # Exa news category
            "contents": {
                "text": {"maxCharacters": 2000},
                "highlights": True,
            }
        }
        
        # Date filtering
        if start_date and end_date:
            start = _parse_date(start_date)
            end = _parse_date(end_date)
            if start and end:
                payload["startPublishedDate"] = f"{start.isoformat()}T00:00:00.000Z"
                payload["endPublishedDate"] = f"{end.isoformat()}T23:59:59.999Z"
                date_filter_desc = f"{start.isoformat()} to {end.isoformat()}"
            else:
                return json.dumps({"error": "Invalid date format. Use YYYY-MM-DD"})
        else:
            time_map = {"day": 1, "week": 7, "month": 30}
            days_back = time_map.get(time_range, 7)
            start_dt = datetime.utcnow() - timedelta(days=days_back)
            payload["startPublishedDate"] = start_dt.strftime("%Y-%m-%dT00:00:00.000Z")
            date_filter_desc = f"last {time_range}"
        
        if include_domains:
            payload["includeDomains"] = include_domains
        
        with httpx.Client(timeout=45) as client:
            response = client.post(f"{EXA_BASE_URL}/search", headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
        
        results = _format_results(data.get("results", []), "Exa News")
        
        # Add relative date info
        today = datetime.now().date()
        for r in results:
            if r.get("published_date"):
                try:
                    # Parse ISO date from Exa
                    pub_str = r["published_date"]
                    if "T" in pub_str:
                        pub_date = datetime.fromisoformat(pub_str.replace("Z", "+00:00")).date()
                    else:
                        pub_date = _parse_date(pub_str)
                    
                    if pub_date:
                        days_ago = (today - pub_date).days
                        if days_ago == 0:
                            r["relative_date"] = "Today"
                        elif days_ago == 1:
                            r["relative_date"] = "Yesterday"
                        else:
                            r["relative_date"] = f"{days_ago} days ago"
                except Exception:
                    pass
        
        return json.dumps({
            "source": "Exa News Search",
            "query": query,
            "date_filter": date_filter_desc,
            "result_count": len(results),
            "results": results,
        }, indent=2)
        
    except Exception as e:
        logger.error(f"Exa news search error: {e}")
        return json.dumps({"error": str(e)})


@tool
def extract_content(
    urls: List[str],
) -> str:
    """
    Extract content from specific URLs using Exa Contents API.
    
    Use this to pull detailed content from known URLs, such as:
    - Product datasheets and technical specifications
    - Company press releases and announcements
    - Technical articles and whitepapers
    - Competitor product pages
    
    Args:
        urls: List of URLs to extract content from (max 10)
    
    Returns:
        JSON with extracted content for each URL including title, text, publishedDate
    """
    logger.info(f"Exa extract: {len(urls)} URLs")
    
    api_key = _get_api_key()
    if not api_key:
        return json.dumps({"error": "Exa API key not configured"})
    
    if len(urls) > 10:
        urls = urls[:10]
        logger.warning("Truncated URL list to 10 items")
    
    try:
        headers = {
            "x-api-key": api_key,
            "Content-Type": "application/json"
        }
        
        payload = {
            "urls": urls,
            "text": True,
        }
        
        with httpx.Client(timeout=60) as client:
            response = client.post(f"{EXA_BASE_URL}/contents", headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
        
        results = []
        for item in data.get("results", []):
            results.append({
                "url": item.get("url", ""),
                "title": item.get("title", ""),
                "content": item.get("text", ""),
                "published_date": item.get("publishedDate", ""),
                "content_length": len(item.get("text", "")),
                "extraction_success": bool(item.get("text")),
            })
        
        return json.dumps({
            "source": "Exa Extract",
            "urls_requested": len(urls),
            "urls_extracted": len(results),
            "results": results,
        }, indent=2)
        
    except Exception as e:
        logger.error(f"Exa extract error: {e}")
        return json.dumps({"error": str(e)})


@tool
def find_similar(
    url: str,
    max_results: int = 10,
    include_domains: Optional[List[str]] = None,
) -> str:
    """
    Find similar content to a given URL using Exa's find-similar API.
    
    Use this to:
    - Find related articles to a known piece of content
    - Discover competitor content similar to a product page
    - Find follow-up coverage on a news story
    
    Args:
        url: URL to find similar content for
        max_results: Number of similar results (default 10)
        include_domains: Limit to specific domains
    
    Returns:
        JSON with similar content including title, url, content, published_date
    """
    logger.info(f"Exa find-similar: {url}")
    
    api_key = _get_api_key()
    if not api_key:
        return json.dumps({"error": "Exa API key not configured"})
    
    try:
        headers = {
            "x-api-key": api_key,
            "Content-Type": "application/json"
        }
        
        payload = {
            "url": url,
            "numResults": max_results,
            "contents": {
                "text": {"maxCharacters": 2000},
                "highlights": True,
            }
        }
        
        if include_domains:
            payload["includeDomains"] = include_domains
        
        with httpx.Client(timeout=45) as client:
            response = client.post(f"{EXA_BASE_URL}/find-similar", headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
        
        results = _format_results(data.get("results", []), "Exa Similar")
        
        return json.dumps({
            "source": "Exa Find Similar",
            "reference_url": url,
            "result_count": len(results),
            "results": results,
        }, indent=2)
        
    except Exception as e:
        logger.error(f"Exa find-similar error: {e}")
        return json.dumps({"error": str(e)})


@tool
def crawl_website(
    url: str,
    search_query: Optional[str] = None,
    max_pages: int = 10,
    include_patterns: Optional[List[str]] = None,
) -> str:
    """
    Crawl a website to discover and extract documents using Exa.
    
    Use this to find technical documents on supplier/competitor websites:
    - Product datasheets and TDS (Technical Data Sheets)
    - Safety Data Sheets (SDS/MSDS)
    - Product catalogs and brochures
    - Technical guides and application notes
    
    Args:
        url: Starting URL to crawl (e.g., "https://www.hexcel.com/Products")
        search_query: Optional query to filter relevant pages (e.g., "carbon fiber prepreg")
        max_pages: Maximum pages to crawl (default 10, max 50)
        include_patterns: URL patterns to include (e.g., ["/datasheet", "/tds", ".pdf"])
    
    Returns:
        JSON with discovered pages and their content
    """
    logger.info(f"Exa crawl: {url}")
    
    api_key = _get_api_key()
    if not api_key:
        return json.dumps({"error": "Exa API key not configured"})
    
    try:
        headers = {
            "x-api-key": api_key,
            "Content-Type": "application/json"
        }
        
        # Extract domain from URL
        from urllib.parse import urlparse
        domain = urlparse(url).netloc
        
        # Build search query scoped to domain
        search_query_full = f"site:{domain} {search_query}" if search_query else f"site:{domain}"
        
        payload = {
            "query": search_query_full,
            "numResults": min(max_pages, 50),
            "useAutoprompt": True,
            "type": "neural",
            "includeDomains": [domain],
            "contents": {
                "text": {"maxCharacters": 1000},
            }
        }
        
        with httpx.Client(timeout=60) as client:
            response = client.post(f"{EXA_BASE_URL}/search", headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
        
        results = data.get("results", [])
        
        # Filter by URL patterns if specified
        if include_patterns:
            filtered = []
            for r in results:
                url_lower = r.get("url", "").lower()
                if any(pattern.lower() in url_lower for pattern in include_patterns):
                    filtered.append(r)
            results = filtered if filtered else results
        
        # Format results
        formatted = []
        for r in results:
            formatted.append({
                "url": r.get("url", ""),
                "title": r.get("title", ""),
                "content_preview": r.get("text", "")[:500] + "..." if len(r.get("text", "")) > 500 else r.get("text", ""),
                "published_date": r.get("publishedDate", ""),
                "score": r.get("score", 0),
                "is_pdf": ".pdf" in r.get("url", "").lower(),
            })
        
        return json.dumps({
            "source": "Exa Crawl",
            "base_url": url,
            "domain": domain,
            "search_query": search_query,
            "pages_found": len(formatted),
            "include_patterns": include_patterns,
            "results": formatted,
        }, indent=2)
        
    except Exception as e:
        logger.error(f"Exa crawl error: {e}")
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
