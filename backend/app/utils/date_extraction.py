"""
Date Extraction Utilities
=========================

Extract publication dates from URLs and content for various press release
and news sources where the API doesn't provide reliable date information.

Supported sources:
- BusinessWire: Date in URL pattern /home/YYYYMMDD...
- GlobeNewswire: Date in URL pattern /news-release/YYYY/MM/DD/
- PRNewswire: Date in content body "CITY, Month DD, YYYY /PRNewswire/" or JSON-LD metadata
- Generic: Meta tags, structured data, common date patterns
"""

import re
import json
import logging
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

# Month name mappings
MONTH_NAMES = {
    'january': 1, 'jan': 1,
    'february': 2, 'feb': 2,
    'march': 3, 'mar': 3,
    'april': 4, 'apr': 4,
    'may': 5,
    'june': 6, 'jun': 6,
    'july': 7, 'jul': 7,
    'august': 8, 'aug': 8,
    'september': 9, 'sept': 9, 'sep': 9,
    'october': 10, 'oct': 10,
    'november': 11, 'nov': 11,
    'december': 12, 'dec': 12,
}


def extract_date_from_url(url: str) -> Optional[datetime]:
    """
    Extract publication date from URL patterns used by major PR services.
    
    Args:
        url: The URL of the press release or article
        
    Returns:
        datetime if found, None otherwise
    """
    if not url:
        return None
        
    url_lower = url.lower()
    
    try:
        # BusinessWire: /home/YYYYMMDD...
        if 'businesswire.com' in url_lower:
            match = re.search(r'/home/(\d{8})', url)
            if match:
                date_str = match.group(1)
                return datetime.strptime(date_str, "%Y%m%d")
        
        # GlobeNewswire: /news-release/YYYY/MM/DD/
        if 'globenewswire.com' in url_lower:
            match = re.search(r'/news-release/(\d{4})/(\d{2})/(\d{2})/', url)
            if match:
                return datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        
        # Accesswire: /newsroom/YYYY/MM/DD or similar
        if 'accesswire.com' in url_lower:
            match = re.search(r'/(\d{4})/(\d{2})/(\d{2})/', url)
            if match:
                return datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)))
                
        # Generic: Look for YYYY/MM/DD or YYYY-MM-DD in URL
        match = re.search(r'/(\d{4})[/-](\d{2})[/-](\d{2})', url)
        if match:
            year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
            if 2000 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31:
                return datetime(year, month, day)
                
    except (ValueError, IndexError) as e:
        logger.debug(f"Could not extract date from URL {url}: {e}")
        
    return None


def extract_date_from_jsonld(url: str, timeout: float = 10.0) -> Optional[datetime]:
    """
    Extract publication date from JSON-LD structured data embedded in the page HTML.
    
    Many news sites (especially PRNewswire) include datePublished in JSON-LD metadata.
    Example: "datePublished": "2025-05-28T05:00:00-04:00"
    
    This is a fallback when Tavily doesn't return the date - we fetch the raw HTML
    and parse the JSON-LD script tags directly.
    
    Args:
        url: The URL of the article/press release
        timeout: Request timeout in seconds
        
    Returns:
        datetime if found, None otherwise
    """
    if not url:
        return None
    
    try:
        # Fetch raw HTML
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        response = httpx.get(url, headers=headers, timeout=timeout, follow_redirects=True)
        response.raise_for_status()
        html = response.text
        
        # Find JSON-LD script tags
        # Pattern matches: <script type="application/ld+json">...</script>
        jsonld_pattern = r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>'
        matches = re.findall(jsonld_pattern, html, re.DOTALL | re.IGNORECASE)
        
        for jsonld_content in matches:
            try:
                data = json.loads(jsonld_content.strip())
                
                # Handle array of JSON-LD objects
                if isinstance(data, list):
                    for item in data:
                        date = _extract_date_from_jsonld_object(item)
                        if date:
                            logger.debug(f"Extracted datePublished from JSON-LD array: {date}")
                            return date
                else:
                    date = _extract_date_from_jsonld_object(data)
                    if date:
                        logger.debug(f"Extracted datePublished from JSON-LD: {date}")
                        return date
                        
            except json.JSONDecodeError:
                continue
                
    except httpx.HTTPError as e:
        logger.debug(f"HTTP error fetching URL for JSON-LD extraction: {url} - {e}")
    except Exception as e:
        logger.debug(f"Error extracting JSON-LD date from {url}: {e}")
    
    return None


def _extract_date_from_jsonld_object(data: dict) -> Optional[datetime]:
    """
    Extract datePublished from a JSON-LD object.
    
    Handles nested @graph structures commonly used by news sites.
    """
    if not isinstance(data, dict):
        return None
    
    # Check for datePublished directly
    date_str = data.get("datePublished") or data.get("dateCreated") or data.get("dateModified")
    if date_str:
        return _parse_iso_date(date_str)
    
    # Check in @graph array (common pattern)
    if "@graph" in data:
        graph = data["@graph"]
        if isinstance(graph, list):
            for item in graph:
                if isinstance(item, dict):
                    date_str = item.get("datePublished") or item.get("dateCreated")
                    if date_str:
                        return _parse_iso_date(date_str)
    
    return None


def _parse_iso_date(date_str: str) -> Optional[datetime]:
    """Parse various date formats into datetime.
    
    Handles:
    - ISO format: 2025-07-28T00:00:00Z
    - RFC 2822: Mon, 28 Jul 2025 00:00:00 GMT
    - Other common formats
    """
    if not date_str or not isinstance(date_str, str):
        return None
    
    # Try ISO format first
    try:
        cleaned = date_str.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(cleaned)
        if parsed.year >= 2000:
            return parsed
    except ValueError:
        pass
    
    # Try RFC 2822 format (e.g., "Mon, 28 Jul 2025 00:00:00 GMT")
    try:
        from email.utils import parsedate_to_datetime
        parsed = parsedate_to_datetime(date_str)
        if parsed.year >= 2000:
            return parsed.replace(tzinfo=None)  # Return naive datetime
    except (ValueError, TypeError):
        pass
    
    # Try common date formats
    formats = [
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%d/%m/%Y",
        "%B %d, %Y",  # January 28, 2025
        "%b %d, %Y",  # Jan 28, 2025
        "%d %B %Y",   # 28 January 2025
        "%d %b %Y",   # 28 Jan 2025
    ]
    for fmt in formats:
        try:
            parsed = datetime.strptime(date_str.strip(), fmt)
            if parsed.year >= 2000:
                return parsed
        except ValueError:
            continue
    
    return None


def extract_date_from_content(content: str, source_hint: str = None) -> Optional[datetime]:
    """
    Extract publication date from article/press release content.
    
    Different sources have different content formats:
    - PRNewswire: "CITY, Month DD, YYYY /PRNewswire/ --"
    - BusinessWire: "Month DD, YYYY" at the start
    - GlobeNewswire: Various formats
    
    Args:
        content: The full text content of the article
        source_hint: Optional hint about the source (e.g., "prnewswire")
        
    Returns:
        datetime if found, None otherwise
    """
    if not content:
        return None
        
    # Look at more content for date extraction (some PRs have headers before date)
    content_start = content[:2000]
    
    try:
        # PRNewswire pattern 1: "CITY, Month DD, YYYY /PRNewswire/"
        # Example: "TOKYO, Nov. 12, 2024 /PRNewswire/ --"
        prn_pattern = r'([A-Z][A-Za-z\s,]+),?\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?\s+(\d{1,2}),?\s+(\d{4})\s*/PRNewswire/'
        match = re.search(prn_pattern, content_start, re.IGNORECASE)
        if match:
            month_str = match.group(2).lower()[:3]
            month = MONTH_NAMES.get(month_str)
            day = int(match.group(3))
            year = int(match.group(4))
            if month and 2000 <= year <= 2100:
                logger.debug(f"PRNewswire pattern 1 matched: {year}-{month}-{day}")
                return datetime(year, month, day)
        
        # PRNewswire pattern 2: More flexible - just look for PRNewswire mention with nearby date
        # Example: "PRNewswire/ -- SALT LAKE CITY, April 9, 2025"
        prn_pattern2 = r'PRNewswire[/\s\-]*.*?([A-Z][A-Za-z\s,]+),?\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+(\d{1,2}),?\s+(\d{4})'
        match = re.search(prn_pattern2, content_start, re.IGNORECASE)
        if match:
            month_str = match.group(2).lower()[:3]
            month = MONTH_NAMES.get(month_str)
            day = int(match.group(3))
            year = int(match.group(4))
            if month and 2000 <= year <= 2100:
                logger.debug(f"PRNewswire pattern 2 matched: {year}-{month}-{day}")
                return datetime(year, month, day)
        
        # PRNewswire pattern 3: Date appears before /PRNewswire/ marker anywhere in content
        # Example: "April 9, 2025 ... /PRNewswire/"
        if 'prnewswire' in content_start.lower():
            # Look for any "Month DD, YYYY" pattern in the first 500 chars before PRNewswire marker
            prn_idx = content_start.lower().find('prnewswire')
            before_prn = content_start[:prn_idx + 200] if prn_idx > 0 else content_start[:500]
            date_pattern = r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+(\d{1,2}),?\s+(\d{4})'
            match = re.search(date_pattern, before_prn, re.IGNORECASE)
            if match:
                month_str = match.group(1).lower()[:3]
                month = MONTH_NAMES.get(month_str)
                day = int(match.group(2))
                year = int(match.group(3))
                if month and 2000 <= year <= 2100:
                    logger.debug(f"PRNewswire pattern 3 matched: {year}-{month}-{day}")
                    return datetime(year, month, day)
        
        # BusinessWire pattern: Usually starts with location and date
        # Example: "SAN FRANCISCO--(BUSINESS WIRE)--December 15, 2024--"
        bw_pattern = r'BUSINESS\s*WIRE[^-]*--?\s*(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})'
        match = re.search(bw_pattern, content_start, re.IGNORECASE)
        if match:
            month_str = match.group(1).lower()
            month = MONTH_NAMES.get(month_str)
            day = int(match.group(2))
            year = int(match.group(3))
            if month and 2000 <= year <= 2100:
                return datetime(year, month, day)
        
        # GlobeNewswire pattern
        # Example: "December 15, 2024 09:00 ET"
        gn_pattern = r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})\s+\d{1,2}:\d{2}\s*(ET|PT|CT|MT)'
        match = re.search(gn_pattern, content_start, re.IGNORECASE)
        if match:
            month_str = match.group(1).lower()
            month = MONTH_NAMES.get(month_str)
            day = int(match.group(2))
            year = int(match.group(3))
            if month and 2000 <= year <= 2100:
                return datetime(year, month, day)
        
        # Generic date patterns (most specific first)
        # Pattern: "Month DD, YYYY"
        generic_pattern = r'\b(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?\s+(\d{1,2}),?\s+(\d{4})\b'
        match = re.search(generic_pattern, content_start, re.IGNORECASE)
        if match:
            month_str = match.group(1).lower()[:3]
            month = MONTH_NAMES.get(month_str)
            day = int(match.group(2))
            year = int(match.group(3))
            if month and 2000 <= year <= 2100 and 1 <= day <= 31:
                return datetime(year, month, day)
        
        # Pattern: "DD Month YYYY" (European style)
        euro_pattern = r'\b(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})\b'
        match = re.search(euro_pattern, content_start, re.IGNORECASE)
        if match:
            day = int(match.group(1))
            month_str = match.group(2).lower()
            month = MONTH_NAMES.get(month_str)
            year = int(match.group(3))
            if month and 2000 <= year <= 2100 and 1 <= day <= 31:
                return datetime(year, month, day)
                
        # ISO format: YYYY-MM-DD
        iso_pattern = r'\b(\d{4})-(\d{2})-(\d{2})\b'
        match = re.search(iso_pattern, content_start)
        if match:
            year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
            if 2000 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31:
                return datetime(year, month, day)
                
    except (ValueError, IndexError) as e:
        logger.debug(f"Could not extract date from content: {e}")
        
    return None


def extract_publication_date(
    url: str = None,
    content: str = None,
    api_date: str = None,
    fallback: datetime = None,
    fetch_jsonld: bool = True
) -> Optional[datetime]:
    """
    Best-effort extraction of publication date from multiple sources.
    
    Priority order:
    1. API-provided date (if valid and parseable)
    2. URL pattern extraction
    3. Content extraction
    4. JSON-LD metadata from page HTML (for PRNewswire and other supported sites)
    5. Fallback (if provided, otherwise None)
    
    Args:
        url: Article/PR URL
        content: Full text content
        api_date: Date string from API (e.g., Tavily published_date)
        fallback: Fallback datetime if nothing else works (None = return None on failure)
        fetch_jsonld: If True, fetch raw HTML to extract JSON-LD metadata as last resort
        
    Returns:
        Best available datetime, or None if extraction failed and no fallback provided
    """
    # 1. Try API-provided date first
    if api_date:
        try:
            # Handle various ISO formats
            cleaned = api_date.replace("Z", "+00:00")
            parsed = datetime.fromisoformat(cleaned)
            # Sanity check: should be within reasonable range
            if parsed.year >= 2000:
                logger.debug(f"Using API-provided date: {parsed}")
                return parsed
        except (ValueError, AttributeError):
            pass
    
    # 2. Try URL extraction
    if url:
        url_date = extract_date_from_url(url)
        if url_date:
            logger.debug(f"Extracted date from URL: {url_date}")
            return url_date
    
    # 3. Try content extraction
    if content:
        # Determine source hint from URL
        source_hint = None
        if url:
            if 'prnewswire' in url.lower():
                source_hint = 'prnewswire'
            elif 'businesswire' in url.lower():
                source_hint = 'businesswire'
            elif 'globenewswire' in url.lower():
                source_hint = 'globenewswire'
                
        content_date = extract_date_from_content(content, source_hint)
        if content_date:
            logger.debug(f"Extracted date from content: {content_date}")
            return content_date
    
    # 4. Try JSON-LD extraction by fetching raw HTML
    # Many news sites include datePublished in JSON-LD structured data
    # This is slower (requires HTTP fetch) but very reliable when present
    if fetch_jsonld and url:
        url_lower = url.lower()
        # List of domains known to have reliable JSON-LD datePublished
        # This is expanded from just PRNewswire to cover more news sources
        jsonld_domains = [
            'prnewswire.com',
            'businesswire.com',
            'globenewswire.com',
            'compositesworld.com',
            'reuters.com',
            'cnbc.com',
            'bloomberg.com',
            'wsj.com',
            'nytimes.com',
            'theguardian.com',
            'bbc.com',
            'cnn.com',
            'forbes.com',
            'techcrunch.com',
            'yahoo.com',
            'marketwatch.com',
            'seekingalpha.com',
            'investopedia.com',
            # Industry-specific
            'windpowermonthly.com',
            'compositesmanufacturingmagazine.com',
            'plasticsnews.com',
            'reinforcedplastics.com',
            'jec-world.events',
            'sae.org',
            'asme.org',
        ]
        
        # Check if URL matches any known JSON-LD domain
        should_try_jsonld = any(domain in url_lower for domain in jsonld_domains)
        
        # Also try JSON-LD for any URL if other methods failed (last resort)
        # But only for non-social-media/non-generic sites
        skip_domains = ['twitter.com', 'facebook.com', 'linkedin.com', 'instagram.com', 
                        'youtube.com', 'reddit.com', 'wikipedia.org', 'google.com']
        is_skippable = any(domain in url_lower for domain in skip_domains)
        
        if should_try_jsonld or not is_skippable:
            logger.debug(f"Attempting JSON-LD extraction for URL: {url[:80]}")
            jsonld_date = extract_date_from_jsonld(url)
            if jsonld_date:
                logger.info(f"Extracted datePublished from JSON-LD: {jsonld_date}")
                return jsonld_date
    
    # 5. Fallback - if no fallback provided, return None to signal extraction failure
    if fallback is None:
        logger.warning(f"Could not extract publication date from URL or content, returning None. URL: {url[:100] if url else 'N/A'}")
        return None
    
    logger.warning(f"Could not extract publication date from URL or content, using fallback: {fallback}. URL: {url[:100] if url else 'N/A'}")
    return fallback


def parse_rss_date(entry) -> Optional[datetime]:
    """
    Parse date from RSS feed entry with multiple fallback strategies.
    
    Args:
        entry: feedparser entry object
        
    Returns:
        datetime if found, None otherwise
    """
    # Try published_parsed first
    if hasattr(entry, 'published_parsed') and entry.published_parsed:
        try:
            return datetime(*entry.published_parsed[:6])
        except (TypeError, ValueError):
            pass
    
    # Try updated_parsed
    if hasattr(entry, 'updated_parsed') and entry.updated_parsed:
        try:
            return datetime(*entry.updated_parsed[:6])
        except (TypeError, ValueError):
            pass
    
    # Try parsing published string
    if hasattr(entry, 'published') and entry.published:
        try:
            # Common RSS date formats
            for fmt in [
                "%a, %d %b %Y %H:%M:%S %z",
                "%a, %d %b %Y %H:%M:%S %Z",
                "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%d %H:%M:%S",
            ]:
                try:
                    return datetime.strptime(entry.published, fmt)
                except ValueError:
                    continue
        except Exception:
            pass
            
    return None
