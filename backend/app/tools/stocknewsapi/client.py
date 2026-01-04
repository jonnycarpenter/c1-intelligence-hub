"""StockNewsAPI client for fetching news articles."""

import os
import time
import logging
import requests
from email.utils import parsedate_to_datetime
from typing import Optional, List
from datetime import datetime

from .models import StockNewsArticle, StockNewsSearchResult

logger = logging.getLogger(__name__)


class StockNewsAPIClient:
    """
    Client for StockNewsAPI.
    
    API Base URL: https://stocknewsapi.com/api/v1
    Premium plan: 50,000 monthly API calls
    
    Rate limiting: Recommended 1 second between calls
    """
    
    BASE_URL = "https://stocknewsapi.com/api/v1"
    
    # Source tier classification for quality weighting
    PREMIUM_SOURCES = [
        "bloomberg", "reuters", "wsj", "wall street journal", 
        "cnbc", "financial times", "barron's", "ft.com"
    ]
    STANDARD_SOURCES = [
        "motley fool", "seeking alpha", "zacks", "benzinga", 
        "fox business", "the street", "marketwatch", "yahoo finance"
    ]
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("STOCKNEWS_API_KEY", "")
        if not self.api_key:
            logger.warning("StockNewsAPI key not configured")
        
        self.session = requests.Session()
        self.last_request_time = 0
        self.min_request_interval = 1.0  # 1 second between requests
    
    def _rate_limit(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            time.sleep(self.min_request_interval - elapsed)
        self.last_request_time = time.time()
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse RFC 2822 date format from StockNewsAPI."""
        if not date_str:
            return None
        try:
            # RFC 2822 format: "Mon, 30 Dec 2024 10:30:00 -0500"
            return parsedate_to_datetime(date_str)
        except Exception as e:
            logger.warning(f"Failed to parse date '{date_str}': {e}")
            return None
    
    def _get_source_tier(self, source_name: str) -> str:
        """Classify source by quality tier."""
        source_lower = source_name.lower()
        
        if any(p in source_lower for p in self.PREMIUM_SOURCES):
            return "premium"
        elif any(s in source_lower for s in self.STANDARD_SOURCES):
            return "standard"
        return "aggregator"
    
    def _parse_article(self, data: dict) -> StockNewsArticle:
        """Parse raw API response into StockNewsArticle model."""
        return StockNewsArticle(
            news_id=data.get("news_id", data.get("id", "")),
            title=data.get("title", ""),
            text=data.get("text", ""),
            source_name=data.get("source_name", ""),
            news_url=data.get("news_url", ""),
            image_url=data.get("image_url"),
            published_at=self._parse_date(data.get("date")),
            tickers=data.get("tickers", []),
            sentiment=data.get("sentiment"),
            article_type=data.get("type", "article"),
            rank_score=data.get("rankscore"),
            source_tier=self._get_source_tier(data.get("source_name", ""))
        )
    
    def _make_request(self, endpoint: str, params: dict) -> List[dict]:
        """Make API request with rate limiting."""
        if not self.api_key:
            logger.error("StockNewsAPI key not configured")
            return []
        
        params["token"] = self.api_key
        
        self._rate_limit()
        
        try:
            url = f"{self.BASE_URL}{endpoint}" if endpoint else self.BASE_URL
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            # API returns {"data": [...]} for most endpoints
            if isinstance(data, dict) and "data" in data:
                return data["data"]
            elif isinstance(data, list):
                return data
            else:
                logger.warning(f"Unexpected response format: {type(data)}")
                return []
                
        except requests.exceptions.RequestException as e:
            logger.error(f"StockNewsAPI request failed: {e}")
            return []
        except Exception as e:
            logger.error(f"StockNewsAPI error: {e}")
            return []
    
    def search_by_tickers(
        self,
        tickers: List[str],
        items: int = 50,
        days: int = 3,
        article_type: str = "article",
        sort_by: str = "rank",
        sentiment: str = None
    ) -> StockNewsSearchResult:
        """
        Search news by ticker symbols.
        
        Args:
            tickers: List of stock tickers (max ~10 per call)
            items: Number of results (max 100)
            days: Lookback period
            article_type: 'article' or 'video' or None for both
            sort_by: 'rank' for relevance, 'latest' for date
            sentiment: Filter by 'positive', 'negative', or 'neutral'
        """
        if not tickers:
            return StockNewsSearchResult(query_type="ticker", query="")
        
        params = {
            "tickers": ",".join(tickers),
            "items": min(items, 100),
            "days": days,
            "sortby": sort_by,
            "extra": "rankscore,id"
        }
        
        if article_type:
            params["type"] = article_type
        if sentiment:
            params["sentiment"] = sentiment
        
        raw_data = self._make_request("", params)
        articles = [self._parse_article(d) for d in raw_data]
        
        return StockNewsSearchResult(
            articles=articles,
            total_results=len(articles),
            query_type="ticker",
            query=",".join(tickers)
        )
    
    def search_by_keyword(
        self,
        keyword: str,
        items: int = 50,
        days: int = 3,
        article_type: str = "article"
    ) -> StockNewsSearchResult:
        """
        Search news by keyword/phrase.
        
        Args:
            keyword: Search term (e.g., "carbon fiber")
            items: Number of results (max 100)
            days: Lookback period
            article_type: 'article' or 'video' or None for both
        """
        if not keyword:
            return StockNewsSearchResult(query_type="keyword", query="")
        
        params = {
            "search": keyword,
            "items": min(items, 100),
            "days": days
        }
        
        if article_type:
            params["type"] = article_type
        
        raw_data = self._make_request("/category", params)
        articles = [self._parse_article(d) for d in raw_data]
        
        return StockNewsSearchResult(
            articles=articles,
            total_results=len(articles),
            query_type="keyword",
            query=keyword
        )
    
    def get_press_releases(
        self,
        tickers: List[str],
        items: int = 50,
        days: int = 3
    ) -> StockNewsSearchResult:
        """
        Get press releases for specific tickers.
        
        Args:
            tickers: List of stock tickers
            items: Number of results (max 100)
            days: Lookback period
        """
        if not tickers:
            return StockNewsSearchResult(query_type="press_release", query="")
        
        params = {
            "tickers": ",".join(tickers),
            "items": min(items, 100),
            "days": days,
            "topic": "pressreleases"
        }
        
        raw_data = self._make_request("", params)
        articles = [self._parse_article(d) for d in raw_data]
        
        return StockNewsSearchResult(
            articles=articles,
            total_results=len(articles),
            query_type="press_release",
            query=",".join(tickers)
        )
    
    def get_analyst_ratings(
        self,
        tickers: List[str] = None,
        items: int = 50
    ) -> StockNewsSearchResult:
        """
        Get analyst upgrades/downgrades.
        
        Args:
            tickers: Optional list of tickers to filter
            items: Number of results
        """
        params = {"items": min(items, 100)}
        
        if tickers:
            params["tickers"] = ",".join(tickers)
        
        raw_data = self._make_request("/stat/updown", params)
        articles = [self._parse_article(d) for d in raw_data]
        
        return StockNewsSearchResult(
            articles=articles,
            total_results=len(articles),
            query_type="analyst_rating",
            query=",".join(tickers) if tickers else "all"
        )
