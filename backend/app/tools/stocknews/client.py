"""
StockNewsAPI HTTP Client
========================

API Documentation: https://stocknewsapi.com/documentation
Plan: Premium ($49.99/month) - 50,000 calls/month
"""

import logging
import time
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import List, Optional, Dict, Any
import httpx

from app.config.settings import settings
from .models import StockNewsArticle

logger = logging.getLogger(__name__)

# API Configuration
BASE_URL = "https://stocknewsapi.com/api/v1"
DEFAULT_ITEMS = 50
MAX_ITEMS = 100
RATE_LIMIT_DELAY = 1.0  # 1 second between calls


class StockNewsClient:
    """
    HTTP client for StockNewsAPI.
    
    Supports:
    - Ticker-based news queries
    - Keyword/phrase search
    - Press releases
    - Analyst ratings
    - Sentiment data
    """
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or settings.stocknews_api_key
        if not self.api_key:
            logger.warning("StockNewsAPI key not configured")
        
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
        """
        Parse StockNewsAPI date format (RFC 2822).
        Example: "Mon, 30 Dec 2024 10:30:00 -0500"
        
        Returns datetime in UTC (naive) to match existing pipeline.
        """
        if not date_str:
            return None
        
        try:
            # parsedate_to_datetime handles RFC 2822 format
            dt = parsedate_to_datetime(date_str)
            # Convert to UTC and make naive (to match existing pipeline convention)
            return dt.astimezone().replace(tzinfo=None)
        except Exception as e:
            logger.warning(f"Failed to parse date '{date_str}': {e}")
            return None
    
    def _parse_article(self, data: Dict[str, Any], search_query: str = None, search_type: str = "ticker") -> StockNewsArticle:
        """Parse API response into StockNewsArticle model."""
        return StockNewsArticle(
            news_id=data.get("news_id", data.get("id", "")),
            title=data.get("title", ""),
            text=data.get("text", ""),
            source_name=data.get("source_name", ""),
            url=data.get("news_url", ""),
            image_url=data.get("image_url"),
            published_at=self._parse_date(data.get("date")),
            tickers=data.get("tickers", []),
            sentiment=data.get("sentiment", "Neutral"),
            article_type=data.get("type", "article"),
            rank_score=data.get("rankscore"),
            search_query=search_query,
            search_type=search_type,
            raw_data=data,
        )
    
    def get_company_news(
        self,
        tickers: List[str],
        days: int = 3,
        items: int = DEFAULT_ITEMS,
        sentiment: Optional[str] = None,
    ) -> List[StockNewsArticle]:
        """
        Fetch news for specific company tickers.
        
        Args:
            tickers: List of stock symbols (e.g., ["HXL", "BA", "OC"])
            days: Days to look back (1-365)
            items: Number of articles (1-100)
            sentiment: Optional filter - "positive", "negative", or "neutral"
        
        Returns:
            List of StockNewsArticle objects
        """
        if not self.api_key:
            logger.error("StockNewsAPI key not configured")
            return []
        
        if not tickers:
            return []
        
        # Build query params
        params = {
            "tickers": ",".join(tickers[:10]),  # API limit ~10 tickers per call
            "items": min(items, MAX_ITEMS),
            "days": days,
            "type": "article",  # Skip video content
            "sortby": "rank",
            "extra": "rankscore,id",
            "token": self.api_key,
        }
        
        if sentiment:
            params["sentiment"] = sentiment
        
        self._rate_limit()
        
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.get(BASE_URL, params=params)
                response.raise_for_status()
                data = response.json()
            
            articles = []
            for item in data.get("data", []):
                article = self._parse_article(item, search_query=",".join(tickers), search_type="ticker")
                articles.append(article)
            
            logger.info(f"StockNewsAPI: {len(articles)} articles for tickers {tickers[:3]}...")
            return articles
            
        except httpx.HTTPStatusError as e:
            logger.error(f"StockNewsAPI HTTP error: {e.response.status_code} - {e.response.text[:200]}")
            return []
        except Exception as e:
            logger.error(f"StockNewsAPI error: {e}")
            return []
    
    def search_keyword(
        self,
        keyword: str,
        days: int = 3,
        items: int = DEFAULT_ITEMS,
    ) -> List[StockNewsArticle]:
        """
        Search news by keyword or phrase.
        
        Use for:
        - Industry terms (e.g., "carbon fiber", "wind turbine")
        - Private company names (e.g., "SpaceX", "Hexion")
        - Material/process terms (e.g., "prepreg", "composites")
        
        Args:
            keyword: Search term
            days: Days to look back (note: alltickers section ignores this param)
            items: Number of articles (1-100)
        """
        if not self.api_key:
            logger.error("StockNewsAPI key not configured")
            return []
        
        # The /category endpoint requires 'section' parameter
        # Use 'alltickers' section which allows keyword search across all stock news
        # Note: 'alltickers' section doesn't support sortby or days params
        params = {
            "section": "alltickers",
            "search": keyword,
            "items": min(items, MAX_ITEMS),
            "type": "article",
            "token": self.api_key,
        }
        
        self._rate_limit()
        
        try:
            url = f"{BASE_URL}/category"
            with httpx.Client(timeout=30.0) as client:
                response = client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
            
            articles = []
            for item in data.get("data", []):
                article = self._parse_article(item, search_query=keyword, search_type="keyword")
                articles.append(article)
            
            logger.info(f"StockNewsAPI: {len(articles)} articles for keyword '{keyword}'")
            return articles
            
        except httpx.HTTPStatusError as e:
            logger.error(f"StockNewsAPI HTTP error: {e.response.status_code} - {e.response.text[:200]}")
            return []
        except Exception as e:
            logger.error(f"StockNewsAPI error: {e}")
            return []
    
    def get_press_releases(
        self,
        tickers: List[str],
        days: int = 30,
        items: int = DEFAULT_ITEMS,
    ) -> List[StockNewsArticle]:
        """
        Fetch official press releases for companies.
        
        Includes: Earnings announcements, M&A activity, leadership changes,
        product launches, partnership announcements.
        """
        if not self.api_key:
            return []
        
        params = {
            "tickers": ",".join(tickers[:10]),
            "items": min(items, MAX_ITEMS),
            "days": days,
            "type": "article",
            "topic": "pressreleases",
            "token": self.api_key,
        }
        
        self._rate_limit()
        
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.get(BASE_URL, params=params)
                response.raise_for_status()
                data = response.json()
            
            articles = []
            for item in data.get("data", []):
                article = self._parse_article(item, search_query=",".join(tickers), search_type="press_release")
                articles.append(article)
            
            logger.info(f"StockNewsAPI: {len(articles)} press releases for {tickers[:3]}...")
            return articles
            
        except Exception as e:
            logger.error(f"StockNewsAPI press releases error: {e}")
            return []
    
    def get_analyst_ratings(
        self,
        tickers: Optional[List[str]] = None,
        items: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Fetch analyst upgrades, downgrades, and price target changes.
        
        Returns raw dict since schema differs from articles.
        """
        if not self.api_key:
            return []
        
        params = {
            "items": min(items, MAX_ITEMS),
            "token": self.api_key,
        }
        
        if tickers:
            params["tickers"] = ",".join(tickers[:10])
        
        self._rate_limit()
        
        try:
            url = f"{BASE_URL}/stat/updown"
            with httpx.Client(timeout=30.0) as client:
                response = client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
            
            return data.get("data", [])
            
        except Exception as e:
            logger.error(f"StockNewsAPI analyst ratings error: {e}")
            return []
    
    @property
    def call_count(self) -> int:
        """Return total API calls made by this client instance."""
        return self._call_count
