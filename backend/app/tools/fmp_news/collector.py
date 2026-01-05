"""FMP Premium News Collector

Collects premium stock news from FMP for tracked companies.
Uses the BigQuery companies table to get ticker symbols.

Data Type: premium_news
"""

import logging
from datetime import datetime, timedelta
from typing import List, Set, Optional

from app.config.settings import settings
from app.db.gcp_storage import get_data_storage
from .client import FMPNewsClient
from .models import FMPNewsArticle

logger = logging.getLogger(__name__)

# Batch size for API calls (FMP handles multiple tickers per call)
TICKER_BATCH_SIZE = 10


class FMPNewsCollector:
    """Collector for FMP premium stock news.
    
    Fetches tickers from BigQuery companies table, then queries
    FMP's stock news API for company-specific premium news.
    """
    
    def __init__(self, api_key: str = None):
        self.client = FMPNewsClient(api_key=api_key)
        self._seen_urls: Set[str] = set()
        self._tickers_cache: Optional[List[str]] = None
    
    async def get_tickers_from_bigquery(self) -> List[str]:
        """Fetch stock tickers from the BigQuery companies table.
        
        Returns:
            List of ticker symbols (e.g., ['AAPL', 'HXL', 'TORAY'])
        """
        if self._tickers_cache is not None:
            return self._tickers_cache
        
        try:
            storage = get_data_storage()
            companies = await storage.get_companies()
            
            # Extract tickers, filtering out None/empty
            tickers = [
                c.get("ticker") 
                for c in companies 
                if c.get("ticker") and c.get("ticker").strip()
            ]
            
            self._tickers_cache = tickers
            logger.info(f"FMP: Loaded {len(tickers)} tickers from BigQuery")
            return tickers
            
        except Exception as e:
            logger.error(f"Failed to fetch tickers from BigQuery: {e}")
            return []
    
    async def collect_latest(
        self,
        max_articles: int = 200,
        max_age_hours: int = 72,
        tickers: List[str] = None,
    ) -> List[FMPNewsArticle]:
        """
        Collect latest stock news from FMP for tracked companies.
        
        Args:
            max_articles: Maximum articles to collect
            max_age_hours: Maximum article age in hours (72 = 3 days)
            tickers: Optional list of tickers. If None, fetches from BigQuery.
            
        Returns:
            List of FMPNewsArticle objects filtered by age
        """
        # Get tickers from BigQuery if not provided
        if tickers is None:
            tickers = await self.get_tickers_from_bigquery()
        
        if not tickers:
            logger.warning("FMP: No tickers available, skipping collection")
            return []
        
        logger.info(f"FMP: Collecting up to {max_articles} articles for {len(tickers)} tickers (max age: {max_age_hours}h)")
        
        # Calculate time boundary
        min_date = datetime.utcnow() - timedelta(hours=max_age_hours)
        
        # Batch tickers to avoid overwhelming the API
        all_articles = []
        
        for i in range(0, len(tickers), TICKER_BATCH_SIZE):
            batch = tickers[i:i + TICKER_BATCH_SIZE]
            
            # Calculate articles per batch
            remaining = max_articles - len(all_articles)
            if remaining <= 0:
                break
            
            batch_articles = self.client.get_news_paginated(
                symbols=batch,
                max_articles=min(remaining, 50),  # Cap per batch
                max_pages=2,
            )
            
            all_articles.extend(batch_articles)
            logger.debug(f"FMP batch {i//TICKER_BATCH_SIZE + 1}: {len(batch_articles)} articles for {','.join(batch)}")
        
        # Filter by age and deduplicate
        filtered = []
        for article in all_articles:
            # Skip if no URL
            if not article.url:
                continue
                
            # Skip already seen
            if article.url in self._seen_urls:
                continue
            
            # Filter by publication date
            if article.published_at and article.published_at < min_date:
                continue
            
            self._seen_urls.add(article.url)
            filtered.append(article)
            
            if len(filtered) >= max_articles:
                break
        
        # Log source breakdown
        publisher_counts = {}
        for article in filtered:
            pub = article.publisher or "unknown"
            publisher_counts[pub] = publisher_counts.get(pub, 0) + 1
        
        logger.info(f"FMP: Collected {len(filtered)} articles from {len(publisher_counts)} publishers")
        if publisher_counts:
            top = sorted(publisher_counts.items(), key=lambda x: x[1], reverse=True)[:5]
            logger.info(f"FMP top publishers: {dict(top)}")
        
        return filtered
    
    @property
    def api_call_count(self) -> int:
        """Return total API calls made."""
        return self.client.api_call_count
    
    def reset_cache(self):
        """Reset caches (for testing or fresh runs)."""
        self._seen_urls.clear()
        self._tickers_cache = None
