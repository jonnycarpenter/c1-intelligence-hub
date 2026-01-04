"""
StockNewsAPI Collector for Ingestion Pipeline
==============================================

Collects financial news from StockNewsAPI and prepares it for 
the ingestion pipeline. Integrates with orchestrator.py.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Set, Optional
import pandas as pd

from app.config.settings import settings
from app.utils.grounding import load_companies
from .client import StockNewsClient
from .models import StockNewsArticle, get_source_priority

logger = logging.getLogger(__name__)

# Keyword lists for industry/material searches
MATERIAL_KEYWORDS = [
    "carbon fiber",
    "fiberglass",
    "composites",
    "prepreg",
    "epoxy resin",
    "aramid",
    "kevlar",
    "glass fiber",
    "CFRP",
    "FRP",
    "thermoplastic composites",
]

PROCESS_KEYWORDS = [
    "pultrusion",
    "RTM",
    "resin transfer molding",
    "infusion",
    "autoclave",
    "filament winding",
    "automated fiber placement",
]

APPLICATION_KEYWORDS = [
    "wind turbine blade",
    "aerospace composites",
    "lightweight materials",
    "composite manufacturing",
    "carbon fiber automotive",
]

PRIVATE_COMPANY_KEYWORDS = [
    "Hexion",
    "Polynt-Reichhold",
    "Vectorply",
    "3A Composites",
    "Composites One",
    "LM Wind Power",
    "Correct Craft",
    "Bechtel",
    "Sierra Nevada Corporation",
]


class StockNewsCollector:
    """
    Collector for StockNewsAPI data.
    
    Integrates with the orchestrator's ingestion pipeline,
    returning data in a format compatible with RawArticle conversion.
    """
    
    def __init__(self, api_key: str = None):
        self.client = StockNewsClient(api_key=api_key)
        self._seen_urls: Set[str] = set()
        self._seen_news_ids: Set[str] = set()
    
    def _get_tickers_from_master_list(self) -> List[str]:
        """
        Load tickers from the master company list CSV.
        Filters out 'private' entries.
        """
        try:
            df = load_companies()
            if df.empty or 'stock_ticker' not in df.columns:
                logger.warning("Master company list empty or missing stock_ticker column")
                return []
            
            tickers = df['stock_ticker'].dropna().tolist()
            # Filter out 'private' entries
            tickers = [t.strip() for t in tickers if t and str(t).lower() != 'private']
            
            logger.info(f"Loaded {len(tickers)} tickers from master company list")
            return tickers
            
        except Exception as e:
            logger.error(f"Error loading master company list: {e}")
            return []
    
    def _batch_tickers(self, tickers: List[str], batch_size: int = 5) -> List[List[str]]:
        """Split tickers into batches for API calls."""
        return [tickers[i:i + batch_size] for i in range(0, len(tickers), batch_size)]
    
    def _is_duplicate(self, article: StockNewsArticle) -> bool:
        """Check if we've already seen this article (by URL or news_id)."""
        if article.url in self._seen_urls:
            return True
        if article.news_id and article.news_id in self._seen_news_ids:
            return True
        return False
    
    def _mark_seen(self, article: StockNewsArticle):
        """Mark article as seen for deduplication."""
        self._seen_urls.add(article.url)
        if article.news_id:
            self._seen_news_ids.add(article.news_id)
    
    def collect_ticker_news(
        self,
        tickers: List[str] = None,
        days: int = 3,
        items_per_batch: int = 50,
    ) -> List[StockNewsArticle]:
        """
        Collect news for all tracked tickers.
        
        Args:
            tickers: List of tickers (defaults to master company list)
            days: Lookback period in days
            items_per_batch: Max articles per API call
        
        Returns:
            List of StockNewsArticle objects
        """
        if tickers is None:
            tickers = self._get_tickers_from_master_list()
        
        if not tickers:
            logger.warning("No tickers to query")
            return []
        
        all_articles = []
        batches = self._batch_tickers(tickers, batch_size=5)
        
        logger.info(f"StockNews: Querying {len(tickers)} tickers in {len(batches)} batches...")
        
        for batch in batches:
            try:
                articles = self.client.get_company_news(
                    tickers=batch,
                    days=days,
                    items=items_per_batch,
                )
                
                for article in articles:
                    if not self._is_duplicate(article):
                        all_articles.append(article)
                        self._mark_seen(article)
                        
            except Exception as e:
                logger.error(f"Error fetching news for batch {batch}: {e}")
        
        logger.info(f"StockNews: Collected {len(all_articles)} unique articles from ticker queries")
        return all_articles
    
    def collect_keyword_news(
        self,
        keywords: List[str] = None,
        days: int = 3,
        items_per_keyword: int = 20,
    ) -> List[StockNewsArticle]:
        """
        Collect news using keyword searches.
        
        Useful for:
        - Private companies (SpaceX, Hexion)
        - Industry terms (carbon fiber, composites)
        - Material searches (prepreg, epoxy)
        
        Args:
            keywords: List of search terms (defaults to built-in lists)
            days: Lookback period (3 days to match orchestrator)
            items_per_keyword: Max articles per keyword
        """
        if keywords is None:
            keywords = MATERIAL_KEYWORDS + PROCESS_KEYWORDS + APPLICATION_KEYWORDS + PRIVATE_COMPANY_KEYWORDS
        
        all_articles = []
        
        logger.info(f"StockNews: Searching {len(keywords)} keywords...")
        
        for keyword in keywords:
            try:
                articles = self.client.search_keyword(
                    keyword=keyword,
                    days=days,
                    items=items_per_keyword,
                )
                
                for article in articles:
                    if not self._is_duplicate(article):
                        all_articles.append(article)
                        self._mark_seen(article)
                        
            except Exception as e:
                logger.error(f"Error searching keyword '{keyword}': {e}")
        
        logger.info(f"StockNews: Collected {len(all_articles)} unique articles from keyword queries")
        return all_articles
    
    def collect_all(
        self,
        days: int = 3,
        include_keywords: bool = True,
    ) -> List[StockNewsArticle]:
        """
        Run full collection: ticker news + keyword searches.
        
        Args:
            days: Lookback period for all queries
            include_keywords: Whether to also run keyword searches
        
        Returns:
            Combined list of unique articles
        """
        # Reset dedup caches for fresh run
        self._seen_urls.clear()
        self._seen_news_ids.clear()
        
        all_articles = []
        
        # 1. Ticker-based news (primary)
        ticker_articles = self.collect_ticker_news(days=days)
        all_articles.extend(ticker_articles)
        
        # 2. Keyword searches (secondary)
        if include_keywords:
            keyword_articles = self.collect_keyword_news(days=days)
            all_articles.extend(keyword_articles)
        
        logger.info(f"StockNews: Total collection: {len(all_articles)} unique articles")
        logger.info(f"StockNews: API calls used: {self.client.call_count}")
        
        return all_articles
    
    @property
    def api_call_count(self) -> int:
        """Total API calls made."""
        return self.client.call_count


def select_best_source(articles: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    From a group of duplicate articles, select the one from the best source.
    
    Uses source tier ranking:
    1. Premium (Bloomberg, Reuters, WSJ, CNBC, FT)
    2. Standard (Motley Fool, Seeking Alpha, Yahoo Finance)
    3. Aggregator (everything else)
    
    Args:
        articles: List of article dicts representing the same story
    
    Returns:
        The article dict from the best source, with:
        - coverage_count: total number of sources
        - duplicate_sources: list of other source names
        - all_urls: list of all source URLs
    """
    if not articles:
        return {}
    
    if len(articles) == 1:
        return articles[0]
    
    # Sort by source priority (lower is better)
    sorted_articles = sorted(
        articles,
        key=lambda a: get_source_priority(a.get("source_name", ""))
    )
    
    best = sorted_articles[0].copy()
    
    # Aggregate metadata
    all_sources = [a.get("source_name", "") for a in articles]
    all_urls = [a.get("url", "") for a in articles if a.get("url")]
    
    # Remove the primary source from duplicate list
    duplicate_sources = [s for s in all_sources if s != best.get("source_name")]
    
    best["coverage_count"] = len(articles)
    best["duplicate_sources"] = duplicate_sources
    best["all_urls"] = all_urls
    
    return best
