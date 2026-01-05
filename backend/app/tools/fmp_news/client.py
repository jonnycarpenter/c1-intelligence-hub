"""FMP Stock News HTTP Client

API: https://financialmodelingprep.com/stable/news/stock
Endpoint verified: 2026-01-04

Premium sources: Benzinga, Seeking Alpha, Bloomberg, WSJ, etc.

Data Type: premium_news
"""

import logging
import time
from datetime import datetime
from typing import List, Optional
import httpx

from app.config.settings import settings
from .models import FMPNewsArticle

logger = logging.getLogger(__name__)

# API Configuration
BASE_URL = "https://financialmodelingprep.com/stable/news/stock"
DEFAULT_LIMIT = 50
MAX_LIMIT = 100  # API max per request
RATE_LIMIT_DELAY = 0.3  # 300ms between calls


class FMPNewsClient:
    """HTTP client for FMP Stock News API.
    
    Endpoint: /stable/news/stock
    Params: symbols (comma-separated), limit, page
    """
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or settings.fmp_api_key
        if not self.api_key:
            logger.warning("FMP API key not configured")
        
        self._last_call_time = 0.0
        self._call_count = 0
    
    def _rate_limit(self):
        """Enforce rate limiting between API calls."""
        elapsed = time.time() - self._last_call_time
        if elapsed < RATE_LIMIT_DELAY:
            time.sleep(RATE_LIMIT_DELAY - elapsed)
        self._last_call_time = time.time()
        self._call_count += 1
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse FMP date format: '2026-01-04 21:44:09'"""
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
        except Exception as e:
            logger.warning(f"Failed to parse date '{date_str}': {e}")
            return None
    
    def _parse_article(self, data: dict) -> FMPNewsArticle:
        """Parse API response into FMPNewsArticle model."""
        return FMPNewsArticle(
            title=data.get("title", ""),
            url=data.get("url", ""),
            text=data.get("text", ""),
            symbol=data.get("symbol", ""),
            publisher=data.get("publisher", ""),
            site=data.get("site", ""),
            published_at=self._parse_date(data.get("publishedDate")),
            image_url=data.get("image"),
        )
    
    def get_stock_news(
        self,
        symbols: List[str] = None,
        limit: int = DEFAULT_LIMIT,
        page: int = 0,
    ) -> List[FMPNewsArticle]:
        """
        Fetch stock news from FMP for specific symbols.
        
        Args:
            symbols: List of ticker symbols (e.g., ['AAPL', 'HXL'])
            limit: Number of articles per page (max 100)
            page: Page number (0-indexed)
            
        Returns:
            List of FMPNewsArticle objects
        """
        if not self.api_key:
            logger.error("FMP API key not configured - cannot fetch news")
            return []
        
        self._rate_limit()
        
        params = {
            "apikey": self.api_key,
            "limit": min(limit, MAX_LIMIT),
            "page": page,
        }
        
        # Add symbols if provided (comma-separated)
        if symbols:
            params["symbols"] = ",".join(symbols)
        
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.get(BASE_URL, params=params)
                response.raise_for_status()
                
                data = response.json()
                
                # Response is a list of articles
                if not isinstance(data, list):
                    logger.warning(f"Unexpected FMP response format: {type(data)}")
                    return []
                
                articles = [self._parse_article(item) for item in data]
                
                symbol_info = f" for {','.join(symbols[:3])}..." if symbols and len(symbols) > 3 else (f" for {','.join(symbols)}" if symbols else "")
                logger.debug(f"FMP: Fetched {len(articles)} articles{symbol_info} (page {page})")
                
                return articles
                
        except httpx.HTTPStatusError as e:
            logger.error(f"FMP API HTTP error: {e.response.status_code} - {e.response.text[:200]}")
            return []
        except Exception as e:
            logger.error(f"FMP API error: {e}")
            return []
    
    def get_news_paginated(
        self,
        symbols: List[str] = None,
        max_articles: int = 200,
        max_pages: int = 5,
    ) -> List[FMPNewsArticle]:
        """
        Fetch multiple pages of news up to max_articles.
        
        Args:
            symbols: List of ticker symbols to query
            max_articles: Maximum total articles to fetch
            max_pages: Maximum pages to fetch
            
        Returns:
            List of FMPNewsArticle objects (deduplicated by URL)
        """
        all_articles = []
        seen_urls = set()
        
        for page in range(max_pages):
            if len(all_articles) >= max_articles:
                break
                
            articles = self.get_stock_news(symbols=symbols, limit=MAX_LIMIT, page=page)
            
            if not articles:
                logger.debug(f"FMP: No more articles at page {page}")
                break
            
            # Deduplicate by URL
            for article in articles:
                if article.url and article.url not in seen_urls:
                    seen_urls.add(article.url)
                    all_articles.append(article)
            
            # Stop if we got fewer than expected
            if len(articles) < MAX_LIMIT:
                break
        
        return all_articles[:max_articles]
    
    @property
    def api_call_count(self) -> int:
        """Return total API calls made."""
        return self._call_count
