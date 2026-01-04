"""
StockNewsAPI Collector for composites industry intelligence.

Collects news from:
1. Ticker-based searches (composites companies + OEMs)
2. Keyword searches (materials, processes, applications)
3. Press releases for tracked companies
"""

import logging
from datetime import datetime, timedelta
from typing import List, Set, Dict, Any, Optional

from .client import StockNewsAPIClient
from .models import StockNewsArticle

logger = logging.getLogger(__name__)


class StockNewsCollector:
    """
    Collector for StockNewsAPI that follows composites industry focus.
    
    Ticker Tiers:
    - Tier 1: Composites Industry Core (OC, HXL, TRYIY, etc.)
    - Tier 2: Aerospace OEMs (BA, EADSY, RTX, etc.)
    - Tier 3: Wind Energy (VWDRY, GEV, etc.)
    - Tier 4+: Other verticals as needed
    
    API Budget: 50,000 calls/month
    """
    
    # Composites industry core tickers (Tier 1)
    TIER_1_COMPOSITES = [
        "OC",       # Owens Corning
        "HXL",      # Hexcel
        "TRYIY",    # Toray
        "HUN",      # Huntsman
        "ASH",      # Ashland
        "BASFY",    # BASF
        "DD",       # DuPont
        "MMM",      # 3M
        "EVKIY",    # Evonik
        "SXYAY",    # Sika
        "MTLHY",    # Mitsubishi Chemical
        "TINLY",    # Teijin
        "SOLVY",    # Solvay
        "SPR",      # Spirit AeroSystems
        "TPIC",     # TPI Composites
        "MKFG",     # Markforged
    ]
    
    # Aerospace OEM tickers (Tier 2)
    AEROSPACE_TICKERS = [
        "BA",       # Boeing
        "EADSY",    # Airbus
        "ERJ",      # Embraer
        "RTX",      # RTX (Raytheon)
        "NOC",      # Northrop Grumman
        "LMT",      # Lockheed Martin
        "GD",       # General Dynamics
        "GE",       # GE Aerospace
        "SAFRY",    # Safran
        "RYCEY",    # Rolls-Royce
        "TXT",      # Textron
    ]
    
    # Wind energy tickers (Tier 3)
    WIND_TICKERS = [
        "VWDRY",    # Vestas
        "GEV",      # GE Vernova
    ]
    
    # Material keywords for keyword searches
    MATERIAL_KEYWORDS = [
        "carbon fiber",
        "fiberglass",
        "composites",
        "prepreg",
        "epoxy resin",
        "CFRP",
        "thermoplastic composites",
    ]
    
    # Private companies to search by name
    PRIVATE_COMPANY_KEYWORDS = [
        "Hexion",
        "LM Wind Power",
    ]
    
    def __init__(self, api_key: str = None, existing_urls: Set[str] = None):
        self.client = StockNewsAPIClient(api_key=api_key)
        self.existing_urls = existing_urls or set()
    
    def _filter_duplicates(self, articles: List[StockNewsArticle]) -> List[StockNewsArticle]:
        """Filter out already-seen articles by URL."""
        unique = []
        for article in articles:
            if article.news_url not in self.existing_urls:
                unique.append(article)
                self.existing_urls.add(article.news_url)
        return unique
    
    def collect_ticker_news(
        self,
        tickers: List[str] = None,
        days: int = 3,
        items_per_batch: int = 50,
        batch_size: int = 5
    ) -> List[StockNewsArticle]:
        """
        Collect news for ticker list.
        
        Args:
            tickers: List of tickers (defaults to Tier 1 + Tier 2)
            days: Lookback period
            items_per_batch: Items to fetch per API call
            batch_size: Number of tickers per API call (max ~10)
        
        Returns:
            List of StockNewsArticle objects
        """
        if tickers is None:
            tickers = self.TIER_1_COMPOSITES + self.AEROSPACE_TICKERS + self.WIND_TICKERS
        
        all_articles = []
        
        # Batch tickers to avoid URL length issues
        for i in range(0, len(tickers), batch_size):
            batch = tickers[i:i + batch_size]
            
            try:
                result = self.client.search_by_tickers(
                    tickers=batch,
                    items=items_per_batch,
                    days=days,
                    article_type="article",
                    sort_by="rank"
                )
                
                unique = self._filter_duplicates(result.articles)
                all_articles.extend(unique)
                
                logger.info(f"Fetched {len(result.articles)} articles for tickers {batch}, {len(unique)} unique")
                
            except Exception as e:
                logger.error(f"Failed to fetch news for tickers {batch}: {e}")
        
        return all_articles
    
    def collect_keyword_news(
        self,
        keywords: List[str] = None,
        days: int = 3,
        items_per_keyword: int = 30
    ) -> List[StockNewsArticle]:
        """
        Collect news by keyword search.
        
        Args:
            keywords: List of search terms (defaults to material keywords)
            days: Lookback period
            items_per_keyword: Items to fetch per keyword
        
        Returns:
            List of StockNewsArticle objects
        """
        if keywords is None:
            keywords = self.MATERIAL_KEYWORDS + self.PRIVATE_COMPANY_KEYWORDS
        
        all_articles = []
        
        for keyword in keywords:
            try:
                result = self.client.search_by_keyword(
                    keyword=keyword,
                    items=items_per_keyword,
                    days=days,
                    article_type="article"
                )
                
                unique = self._filter_duplicates(result.articles)
                all_articles.extend(unique)
                
                logger.info(f"Fetched {len(result.articles)} articles for keyword '{keyword}', {len(unique)} unique")
                
            except Exception as e:
                logger.error(f"Failed to fetch news for keyword '{keyword}': {e}")
        
        return all_articles
    
    def collect_press_releases(
        self,
        tickers: List[str] = None,
        days: int = 3,
        items: int = 50
    ) -> List[StockNewsArticle]:
        """
        Collect press releases for tracked tickers.
        
        Args:
            tickers: List of tickers (defaults to Tier 1 composites)
            days: Lookback period
            items: Number of results
        
        Returns:
            List of StockNewsArticle objects (press releases only)
        """
        if tickers is None:
            tickers = self.TIER_1_COMPOSITES
        
        try:
            result = self.client.get_press_releases(
                tickers=tickers,
                items=items,
                days=days
            )
            
            unique = self._filter_duplicates(result.articles)
            logger.info(f"Fetched {len(result.articles)} press releases, {len(unique)} unique")
            return unique
            
        except Exception as e:
            logger.error(f"Failed to fetch press releases: {e}")
            return []
    
    def collect_all(
        self,
        days: int = 3,
        include_keywords: bool = True,
        include_press_releases: bool = True,
        custom_tickers: List[str] = None
    ) -> List[StockNewsArticle]:
        """
        Run full collection across all sources.
        
        This is the main entry point for scheduled ingestion.
        
        Args:
            days: Lookback period
            include_keywords: Whether to include keyword searches
            include_press_releases: Whether to include PR-specific search
            custom_tickers: Override default ticker list
        
        Returns:
            Deduplicated list of all collected articles
        """
        logger.info(f"Starting StockNewsAPI collection (days={days})")
        
        all_articles = []
        
        # 1. Ticker-based news (main source)
        ticker_articles = self.collect_ticker_news(
            tickers=custom_tickers,
            days=days
        )
        all_articles.extend(ticker_articles)
        
        # 2. Keyword-based news (material/process coverage)
        if include_keywords:
            keyword_articles = self.collect_keyword_news(days=days)
            all_articles.extend(keyword_articles)
        
        # 3. Press releases (company announcements)
        if include_press_releases:
            pr_articles = self.collect_press_releases(days=days)
            all_articles.extend(pr_articles)
        
        logger.info(f"StockNewsAPI collection complete: {len(all_articles)} total articles")
        
        return all_articles
    
    def collect_for_companies(
        self,
        companies: List[Dict[str, Any]],
        days: int = 3
    ) -> List[StockNewsArticle]:
        """
        Collect news for a list of company dicts (matching orchestrator format).
        
        Args:
            companies: List of company dicts with 'ticker', 'name', 'id' keys
            days: Lookback period
        
        Returns:
            List of StockNewsArticle objects with company_id metadata
        """
        # Extract tickers from companies
        tickers = []
        ticker_to_company = {}
        
        for comp in companies:
            ticker = comp.get("ticker") or comp.get("stock_ticker")
            if ticker and ticker.lower() != "private":
                tickers.append(ticker)
                ticker_to_company[ticker.upper()] = comp
        
        if not tickers:
            logger.warning("No valid tickers found in company list")
            return []
        
        # Collect news for these tickers
        articles = self.collect_ticker_news(tickers=tickers, days=days)
        
        # Enrich articles with company metadata
        for article in articles:
            for ticker in article.tickers:
                ticker_upper = ticker.upper()
                if ticker_upper in ticker_to_company:
                    comp = ticker_to_company[ticker_upper]
                    article.model_extra = {
                        "company_id": comp.get("id"),
                        "company_name": comp.get("name"),
                        "matched_ticker": ticker
                    }
                    break
        
        return articles
