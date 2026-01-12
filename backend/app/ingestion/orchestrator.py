import os
import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from typing import List, Dict, Any
from urllib.parse import urlparse

from app.models.corpus import CorpusItem, ContentSource, EntityMention as EMModel


def _make_naive_utc(dt: datetime) -> datetime:
    """Convert a datetime to naive UTC for safe comparison."""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        # Convert to UTC then strip timezone
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt
from app.models.corpus import IngestionStats, Priority
from app.db.vector_store import get_production_vector_store
from app.db.bq_vector_store import get_bq_vector_store
from app.db.gcp_storage import get_storage
from app.config.settings import settings
from app.utils.grounding import load_companies
from app.utils.date_extraction import extract_publication_date

# Import new modules
from app.ingestion.fetchers import RSSFetcher
from app.ingestion.industry_queries import get_all_exa_queries_v2, get_all_tavily_queries_v2, IndustryQuery, SearchEngine
from app.tools.press_releases.tavily_client import TavilyClient
from app.ingestion.processing import WebScraper, ContentClassifier, EntityLinker, DeduplicationService, ImageEnrichmentService
from app.ingestion.generators import DigestGenerator, BriefingGenerator
from app.tools.press_releases.collector import PressReleaseCollector
from app.tools.sec_filings.collector import SECFilingCollector
from app.tools.stocknews.collector import StockNewsCollector
from app.tools.fmp_news.collector import FMPNewsCollector
from app.tools.earnings.collector import EarningsCollector
from app.models.corpus import RawArticle
from app.ingestion.freight.drewry_scraper import DrewryScraper

logger = logging.getLogger(__name__)

@dataclass
class IngestionConfig:
    """Configuration for the ingestion pipeline"""
    anthropic_api_key: str = field(default_factory=lambda: settings.anthropic_api_key or os.getenv("ANTHROPIC_API_KEY", ""))
    exa_api_key: str = field(default_factory=lambda: settings.exa_api_key or os.getenv("EXA_AI_API_KEY", ""))
    tavily_api_key: str = field(default_factory=lambda: settings.tavily_api_key or os.getenv("TAVILY_API_KEY", ""))  # Legacy, kept for reference
    sec_api_key: str = field(default_factory=lambda: settings.sec_api_key or os.getenv("SEC_IO_KEY", ""))
    api_ninja_key: str = field(default_factory=lambda: settings.api_ninja_key or os.getenv("API_NINJA_KEY", ""))
    stocknews_api_key: str = field(default_factory=lambda: settings.stocknews_api_key or os.getenv("STOCKNEWS_API_KEY", ""))
    fmp_api_key: str = field(default_factory=lambda: settings.fmp_api_key or os.getenv("FMP_API_KEY", ""))
    
    # Ingestion Settings
    max_articles_per_feed: int = 20
    max_article_age_days: int = 7
    
    # Classification
    classifier_model: str = "claude-sonnet-4-5"
    classifier_temperature: float = 0.1
    
    # Digest
    digest_hours: int = 72
    digest_max_items: int = 50
    digest_model: str = "claude-sonnet-4-5"
    
    # Image Enrichment
    enable_image_enrichment: bool = True
    max_images_per_article: int = 3
    enable_vision_classification: bool = True


class IngestionOrchestrator:
    """
    Main orchestrator for the ingestion pipeline.
    """
    
    def __init__(self, config: IngestionConfig):
        self.config = config
        self.gcp_storage = None  # BigQuery storage (initialized in initialize())
        
        # Components
        self.rss_fetcher = RSSFetcher(config)
        self.pr_collector = PressReleaseCollector()
        self.sec_collector = SECFilingCollector()
        self.earnings_collector = EarningsCollector()  # API Ninja earnings transcripts
        self.stocknews_collector = StockNewsCollector(api_key=config.stocknews_api_key)
        self.fmp_news_collector = FMPNewsCollector(api_key=config.fmp_api_key)
        self.drewry_scraper = DrewryScraper()
        
        self.scraper = WebScraper()
        self.classifier = ContentClassifier(config)
        self.entity_linker = EntityLinker()
        self.image_enricher = None  # Initialized in initialize() method
        self.dedup_service = None
        self.vector_store = None
        self.digest_generator = None
        self.briefing_generator = None
        self.tavily_client = None
        
        self._initialized = False
    
    async def initialize(self):
        """Initialize all components"""
        logger.info("Initializing ingestion orchestrator...")
        
        # Deduplication Service - uses BigQuery
        self.dedup_service = DeduplicationService()  # Will auto-initialize with BigQuery storage
        
        # Briefing generator (doesn't need DB)
        self.briefing_generator = BriefingGenerator(self.config)
        
        # Initialize Tavily Client
        self.tavily_client = TavilyClient(api_key=self.config.tavily_api_key)
        
        # Load dedup cache from BigQuery
        await self.dedup_service.load_recent_cache()
        
        # GCP Storage for BigQuery operations (initialize early for entity loading)
        self.gcp_storage = await get_storage()
        
        # Load tracked entities from BigQuery
        await self.classifier.load_tracked_entities(self.gcp_storage)
        await self.entity_linker.load_entities(self.gcp_storage)
        
        # DigestGenerator - now uses BigQuery storage
        self.digest_generator = DigestGenerator(self.config, self.gcp_storage)
        
        # Image Enrichment Service (uses Tavily for image search + Claude for vision)
        if self.config.enable_image_enrichment:
            self.image_enricher = ImageEnrichmentService(
                tavily_api_key=self.config.tavily_api_key,
                anthropic_api_key=self.config.anthropic_api_key,
                max_images_per_article=self.config.max_images_per_article,
                enable_vision_classification=self.config.enable_vision_classification,
            )
            logger.info("Image enrichment service initialized")
        
        # Vector Store Initialization (BigQuery-backed)
        self.vector_store = await get_production_vector_store()
        
        # Note: self.gcp_storage already initialized above for entity loading
        
        self._initialized = True
        logger.info("Ingestion orchestrator initialized")
    
    async def run_full_ingestion(self, backfill_days: int = None, sources: List[str] = None) -> IngestionStats:
        """
        Run the ingestion pipeline with selective source filtering.
        
        Args:
            backfill_days: Number of days to backfill (optional)
            sources: List of sources to run. If None, runs ALL sources.
                     Options: "rss", "industry_queries", "exa_queries", "tavily_queries", "sec", "earnings", "stocknews", "fmp_news", "freight", "press_releases"
                     
                     Note: "industry_queries" runs both Exa + Tavily (legacy, for backcompat).
                           Use "exa_queries" and "tavily_queries" separately for scheduler jobs to avoid timeout.
        """
        if not self._initialized:
            await self.initialize()
        
        # Default to ALL sources if none provided
        if not sources:
            sources = ["rss", "exa_queries", "tavily_queries", "sec", "earnings", "stocknews", "fmp_news", "freight", "press_releases"]
            
        logger.info(f"Starting ingestion run with sources: {sources}")
        
        # Logging Setup
        run_id = str(uuid.uuid4())
        job_type = "backfill" if backfill_days else "scheduled"
        
        try:
            await self.gcp_storage.log_ingestion_event(
                run_id=run_id,
                event_type="STARTED",
                job_type=job_type,
                status="started",
                metadata={"backfill_days": backfill_days, "sources": sources}
            )
        except Exception as e:
            logger.warning(f"Failed to log ingestion start: {e}")

        stats = IngestionStats(started_at=datetime.utcnow())
        
        try:
            # Step 1: Fetch RSS
            if "rss" in sources:
                logger.info("Step 1: Fetching RSS feeds...")
                # For RSS, simple backfill usually doesn't work deep, but we pass parameter anyway
                rss_articles = await self.rss_fetcher.fetch_all_feeds(days_back=backfill_days)
                stats.rss_articles_fetched = len(rss_articles)
            else:
                rss_articles = []
                logger.info("Skipping RSS (not in sources)")
            
            # =====================================================================
            # GLOBAL DATE SETUP - Must happen BEFORE any source fetching
            # These variables are used by is_valid_date() filter for all sources
            # =====================================================================
            if backfill_days:
                # Backfill mode: use the specified days for both tiers
                tier1_since = datetime.utcnow() - timedelta(days=backfill_days)
                tier2_since = datetime.utcnow() - timedelta(days=backfill_days)
                search_num_days = backfill_days
                logger.info(f"Date filter: Backfill mode with {backfill_days} days lookback")
            else:
                # Normal run: 2-day lookback (1-day overlap buffer when running daily)
                tier1_since = datetime.utcnow() - timedelta(days=2)
                tier2_since = datetime.utcnow() - timedelta(days=2)
                search_num_days = 2
                logger.info(f"Date filter: Standard 2-day lookback")
            
            # Step 1b: Fetch Freight Rates (Drewry WCI)
            if "freight" in sources:
                logger.info("Step 1b: Fetching Drewry Freight Rates...")
                try:
                    freight_rates = await self.drewry_scraper.fetch_latest_rates()
                    if freight_rates:
                        from app.db.gcp_storage import FreightRateRecord
                        records = [
                            FreightRateRecord(
                                lane=r.lane,
                                rate=r.rate,
                                currency="USD",
                                unit="40ft",
                                change_pct=r.change_pct,
                                source="drewry_wci",
                                as_of=r.as_of,
                                fetched_at=r.fetched_at,
                            )
                            for r in freight_rates
                        ]
                        # Update stats if we add a field, for now just log
                        stored_rates = await self.gcp_storage.store_freight_rates(records)
                        logger.info(f"Stored {stored_rates} freight rates in BigQuery")
                except Exception as e:
                    logger.error(f"Error in freight rate ingestion: {e}")
                    stats.errors.append(f"Freight rates error: {str(e)[:100]}")
            else:
                logger.info("Skipping Freight Rates (not in sources)")
            
            # Step 2: Fetch Financial Data (PRs + SEC + Earnings) and Web Search
            logger.info("Step 2: Fetching Tiered Data...")
            
            companies = await self._get_tracked_companies()

            # 2a. Press Releases (Tavily) - Tier 2
            pr_items = []
            if "press_releases" in sources:
                logger.info(f"Fetching PRs (Since {tier2_since.date()})...")
                # Increase limit if backfilling
                pr_limit = 20 if backfill_days else None
                pr_items = self.pr_collector.collect_batch(companies, limit=pr_limit, num_days=backfill_days) 
                # Filter by date (normalize to naive UTC for comparison)
                pr_items = [pr for pr in pr_items if not pr.published_date or _make_naive_utc(pr.published_date) >= tier2_since]
                stats.pr_articles_fetched = len(pr_items)
            
            # 2b. SEC Filings - Tier 1
            sec_items = []
            if "sec" in sources and (self.config.sec_api_key or os.getenv("SEC_IO_KEY")):
                # Filter to companies with tickers for SEC queries
                sec_companies = [c for c in companies if c.get("ticker")]
                logger.info(f"Fetching SEC filings (Since {tier1_since.date()}) for {len(sec_companies)} companies...")
                for i, comp in enumerate(sec_companies):
                    try:
                        filings = self.sec_collector.collect_for_company(
                            company_id=comp["id"],
                            ticker=comp["ticker"],
                            since=tier1_since
                        )
                        sec_items.extend(filings)
                        if (i + 1) % 10 == 0:
                            logger.info(f"SEC progress: {i + 1}/{len(sec_companies)} companies processed")
                    except Exception as e:
                        logger.error(f"SEC fetch failed for {comp['ticker']}: {e}")
                logger.info(f"SEC: Completed all companies, {len(sec_items)} total filings found")
                stats.sec_filings_fetched = len(sec_items)
            
            # 2c. Earnings Transcripts (API Ninja) - Tier 1
            # Uses quarter-based fetching (not date-based) for reliability
            earnings_items = []
            if "earnings" in sources and self.config.api_ninja_key:
                logger.info("Fetching Earnings Transcripts (API Ninja)...")
                try:
                    # Determine which quarter to fetch based on current date
                    # Q3 2025 earnings calls happen in Oct-Nov 2025 (Q4 calendar)
                    now = datetime.utcnow()
                    # For backfill: get most recent completed quarter's earnings
                    # Q1 earnings in Apr-May, Q2 in Jul-Aug, Q3 in Oct-Nov, Q4 in Jan-Feb
                    if now.month >= 10:  # Oct-Dec: Q3 earnings available
                        target_year, target_quarter = now.year, 3
                    elif now.month >= 7:  # Jul-Sep: Q2 earnings available
                        target_year, target_quarter = now.year, 2
                    elif now.month >= 4:  # Apr-Jun: Q1 earnings available
                        target_year, target_quarter = now.year, 1
                    else:  # Jan-Mar: Q4 of previous year available
                        target_year, target_quarter = now.year - 1, 4
                    
                    logger.info(f"Targeting Q{target_quarter} {target_year} earnings transcripts")
                    
                    # Get companies with stock tickers
                    earnings_companies = [c for c in companies if c.get('stock_ticker')]
                    logger.info(f"Checking {len(earnings_companies)} companies for earnings transcripts...")
                    
                    for comp in earnings_companies:
                        try:
                            transcripts = self.earnings_collector.collect_for_company(
                                company_id=comp.get('id'),
                                ticker=comp['stock_ticker'],
                                company_name=comp.get('name', ''),
                                since=None  # We're using explicit quarter, not date filtering
                            )
                            # Filter to target quarter only (collector may return multiple)
                            for t in transcripts:
                                if t.year == target_year and t.quarter == target_quarter:
                                    earnings_items.append(self._convert_earnings_to_article(t))
                        except Exception as e:
                            logger.error(f"Earnings fetch failed for {comp.get('stock_ticker')}: {e}")
                    
                    stats.earnings_transcripts_fetched = len(earnings_items)
                    logger.info(f"Earnings: {len(earnings_items)} transcripts collected for Q{target_quarter} {target_year}")
                except Exception as e:
                    logger.error(f"Earnings collection failed: {e}")
                    stats.errors.append(f"Earnings error: {str(e)[:100]}")
            
            # 2e. StockNewsAPI Premium Financial News - Tier 2
            stocknews_items = []
            if "stocknews" in sources and (self.config.stocknews_api_key or os.getenv("STOCKNEWS_API_KEY")):
                logger.info(f"Fetching StockNewsAPI articles (Since {tier2_since.date()})...")
                try:
                    # Collect both ticker-based and keyword news
                    stocknews_raw = self.stocknews_collector.collect_all(
                        days=search_num_days,
                        include_keywords=True,
                    )
                    # Convert to RawArticle format
                    stocknews_items = [self._convert_stocknews_to_article(item) for item in stocknews_raw]
                    stats.stocknews_articles_fetched = len(stocknews_items)
                    logger.info(f"StockNewsAPI: {len(stocknews_items)} articles collected (API calls: {self.stocknews_collector.api_call_count})")
                except Exception as e:
                    logger.error(f"StockNewsAPI fetch failed: {e}")
                    stats.errors.append(f"StockNewsAPI error: {str(e)[:100]}")
            
            # 2e2. FMP Premium News (Benzinga, Seeking Alpha, etc.) - Tier 2
            premium_news_items = []
            if "fmp_news" in sources and (self.config.fmp_api_key or os.getenv("FMP_API_KEY")):
                logger.info(f"Fetching FMP Premium News (Since {tier2_since.date()})...")
                try:
                    # Collect premium news for tracked company tickers from BigQuery
                    fmp_raw = await self.fmp_news_collector.collect_latest(
                        max_articles=200,
                        max_age_hours=search_num_days * 24,
                    )
                    # Convert to RawArticle format with source_type="premium_news"
                    premium_news_items = [self._convert_fmp_to_article(item) for item in fmp_raw]
                    stats.premium_news_articles_fetched = len(premium_news_items)
                    logger.info(f"FMP Premium News: {len(premium_news_items)} articles (API calls: {self.fmp_news_collector.api_call_count})")
                except Exception as e:
                    logger.error(f"FMP Premium News fetch failed: {e}")
                    stats.errors.append(f"FMP error: {str(e)[:100]}")
            
            # 2f. General Web Search (Exa + Tavily) - Tier 2
            # Supports 3 modes:
            #   - "industry_queries" = run both Exa + Tavily (legacy, for backward compat)
            #   - "exa_queries" = run only Exa queries (~91 queries, ~12-15 min)
            #   - "tavily_queries" = run only Tavily queries (~145 queries, ~15-18 min)
            web_items = []
            
            # Determine which query sets to run
            run_exa = "exa_queries" in sources or "industry_queries" in sources
            run_tavily = "tavily_queries" in sources or "industry_queries" in sources
            
            if run_exa or run_tavily:
                logger.info(f"Fetching General Web News (Since {tier2_since.date()})...")
                logger.info(f"  Run Exa: {run_exa}, Run Tavily: {run_tavily}")
            
            # --- PART 1a: Exa Queries (High Quality) ---
            if run_exa:
                exa_queries = get_all_exa_queries_v2()
                logger.info(f"Running {len(exa_queries)} Exa critical queries...")
                
                for iq in exa_queries:
                    try:
                        # Use Exa (via pr_collector.client)
                        results = self.pr_collector.client.search(
                            query=iq.query,
                            max_results=iq.max_results,
                            search_depth=iq.search_depth,
                            include_domains=None,
                            num_days=search_num_days,
                            category=iq.exa_category or "news"
                        )
                        logger.info(f"Exa Query [{iq.category}]: '{iq.query[:40]}...' -> {len(results)} results")
                        for res in results:
                            industry_company = {
                                "id": None,
                                "name": f"Industry:{iq.category}",
                                "stock_ticker": None
                            }
                            article = self._convert_search_result_to_article(res, industry_company, search_engine="exa")
                            article.raw_data["industry_query"] = iq.query
                            article.raw_data["industry_category"] = iq.category
                            web_items.append(article)
                    except Exception as e:
                        logger.error(f"Exa query failed '{iq.query[:30]}...': {e}")

            # --- PART 1b: Tavily Queries (Broadening) ---
            if run_tavily:
                tavily_queries = get_all_tavily_queries_v2()
                logger.info(f"Running {len(tavily_queries)} Tavily monitoring queries...")
                
                for iq in tavily_queries:
                    try:
                        # Use Tavily Client
                        results = self.tavily_client.search(
                            query=iq.query,
                            max_results=iq.max_results,
                            search_depth=iq.search_depth,
                            include_domains=None
                        )
                        logger.info(f"Tavily Query [{iq.category}]: '{iq.query[:40]}...' -> {len(results)} results")
                        for res in results:
                            industry_company = {
                                "id": None,
                                "name": f"Industry:{iq.category}",
                                "stock_ticker": None
                            }
                            article = self._convert_search_result_to_article(res, industry_company, search_engine="tavily")
                            article.raw_data["industry_query"] = iq.query
                            article.raw_data["industry_category"] = iq.category
                            web_items.append(article)
                    except Exception as e:
                        logger.error(f"Tavily query failed '{iq.query[:30]}...': {e}")
                
            # --- PART 2: Per-Company Specific News (runs with Exa queries) ---
            if run_exa:
                company_web_count = 0
                for comp in companies:
                    query = f"{comp['name']} news"
                    try:
                        results = self.pr_collector.client.search(
                            query=query, 
                            max_results=3,  # Reduced since we have industry queries now
                            search_depth="basic", 
                            include_domains=None,
                            num_days=search_num_days,  # Filter by date at API level
                            category="news"  # Exa news category for better relevance
                        )
                        for res in results:
                            web_items.append(self._convert_search_result_to_article(res, comp, search_engine="exa"))
                            company_web_count += 1
                    except Exception as e:
                        logger.error(f"Web search failed for {comp['name']}: {e}")
                
                logger.info(f"Per-company queries returned {company_web_count} articles")
            
            # Log stats for web search (outside the if blocks so it captures both Exa and Tavily)
            if run_exa or run_tavily:
                logger.info(f"Total web news articles: {len(web_items)}")
                stats.web_articles_fetched = len(web_items)
            
            
            # Convert to RawArticle (StockNewsAPI items already converted above)
            converted_prs = [self._convert_pr_to_article(item) for item in pr_items]
            converted_sec = [self._convert_sec_to_article(item) for item in sec_items]
            converted_earnings = [self._convert_earnings_to_article(item) for item in earnings_items]
            
            # =================================================================
            # DATE FILTERING ANALYSIS (for visibility - we keep ALL articles)
            # The filter only affects what appears in Drumbeat feed, NOT storage
            # =================================================================
            now_utc = datetime.utcnow()
            
            def is_feed_eligible(article) -> bool:
                """Check if article should appear in Drumbeat feed.
                
                Returns True if:
                - Has a valid published_at date
                - Date is not in the future (bad parsing)
                - Date is within the lookback window
                
                All articles are still STORED regardless of this flag.
                This only controls visibility in the Drumbeat/Pulse feed.
                """
                if not article.published_at:
                    return False
                pub_date = _make_naive_utc(article.published_at)
                if pub_date > now_utc:
                    return False  # Future date = bad parsing
                if pub_date < tier2_since:
                    return False  # Outside lookback window
                return True
            
            def classify_date_status(article) -> str:
                """Classify article date status for logging/visibility."""
                if not article.published_at:
                    return "no_date"
                pub_date = _make_naive_utc(article.published_at)
                if pub_date > now_utc:
                    return "future_date"  # Bad parsing
                if pub_date < tier2_since:
                    return "old_date"     # Outside lookback window
                return "feed_eligible"    # Will appear in Drumbeat feed
            
            # Combine ALL articles (no filtering for storage)
            all_articles = (rss_articles + converted_prs + converted_sec + 
                           converted_earnings + web_items + stocknews_items + premium_news_items)
            
            # Build a map of article -> feed_eligible status for later use
            article_feed_status = {id(a): is_feed_eligible(a) for a in all_articles}
            
            # Log date filtering stats for visibility
            date_stats = {"no_date": 0, "future_date": 0, "old_date": 0, "feed_eligible": 0}
            for article in all_articles:
                status = classify_date_status(article)
                date_stats[status] += 1
            
            stats.articles_no_date = date_stats["no_date"]
            stats.articles_future_date = date_stats["future_date"]
            stats.articles_old_date = date_stats["old_date"]
            stats.articles_feed_eligible = date_stats["feed_eligible"]
            
            logger.info(f"📊 DATE FILTER ANALYSIS (lookback={search_num_days} days):")
            logger.info(f"   Total articles collected: {len(all_articles)}")
            logger.info(f"   ├─ Feed eligible:  {date_stats['feed_eligible']} (will appear in Drumbeat)")
            logger.info(f"   ├─ No date:        {date_stats['no_date']} (stored, hidden from feed)")
            logger.info(f"   ├─ Future date:    {date_stats['future_date']} (stored, bad date parsing)")
            logger.info(f"   └─ Old date:       {date_stats['old_date']} (stored, outside window)")
            
            logger.info(f"Total articles to process: {len(all_articles)}")
            
            if not all_articles:
                logger.info("No articles found in this run. Skipping processing.")
                stats.completed_at = datetime.utcnow()
                stats.status = "completed"
                return stats
            
            # Step 3: Deduplicate
            logger.info("Step 3: Deduplicating...")
            unique_articles = []
            for article in all_articles:
                is_dup, _ = await self.dedup_service.check_duplicate(article)
                if is_dup:
                    stats.duplicates_skipped += 1
                else:
                    unique_articles.append(article)
            
            logger.info(f"Unique articles after dedup: {len(unique_articles)}")
            
            # Step 4: Enrich
            logger.info("Step 4: Enriching articles...")
            limit = 200 if backfill_days else 50
            articles_to_enrich = unique_articles[:limit]
            enriched_articles = await self.scraper.enrich_articles(articles_to_enrich)
            stats.articles_enriched = len([a for a in enriched_articles if a.full_text])
            
            # Combine
            final_articles = enriched_articles + unique_articles[limit:]
            
            # Step 5: Classify
            logger.info("Step 5: Classifying content...")
            classified = await self.classifier.classify_batch(final_articles)
            stats.articles_classified = len(classified)
            
            # Step 5b: Image Enrichment
            all_extracted_images = []
            if self.image_enricher and self.config.enable_image_enrichment:
                logger.info("Step 5b: Extracting images from high-priority articles...")
                image_enrichment_limit = 20 if not backfill_days else 10
                articles_for_images = [
                    {
                        "id": str(uuid.uuid4()),
                        "title": article.title,
                        "url": article.url,
                        "summary": article.summary or "",
                        "companies": classification.companies or classification.key_entities,
                        "industries": [i.value for i in classification.industries] if classification.industries else [],
                    }
                    for article, classification in classified
                    if classification.relevance_score >= 0.6 or classification.priority.value == "high"
                ][:image_enrichment_limit]
                
                if articles_for_images:
                    try:
                        image_results = await self.image_enricher.enrich_articles_batch(
                            articles_for_images,
                            max_concurrent=3,
                        )
                        for article_id, images in image_results.items():
                            for img in images:
                                all_extracted_images.append(img.to_dict())
                        stats.images_extracted = len(all_extracted_images)
                    except Exception as e:
                        logger.error(f"Image enrichment error: {e}")
            
            # Step 6: Link & Store
            logger.info("Step 6: Linking and storing...")
            stored_count = 0
            vector_docs = []
            article_records = []
            digest_items_for_ui = [] # For Digest Feed (Drumbeat)
            
            for article, classification in classified:
                mentions = self.entity_linker.link_article(article)
                corpus_item = self._create_corpus_item(article, classification, mentions)
                
                try:
                    stored_count += 1
                    vector_docs.append(corpus_item)
                    article_records.append(self._create_article_record(article, classification))
                    
                    # Prepare Digest Item with feed_eligible flag
                    # feed_eligible determines if this shows in the Drumbeat feed
                    # ALL articles are stored regardless, but only feed_eligible ones display
                    article_id = str(uuid.uuid4())
                    digest_item = {
                        "article_id": article_id,
                        "title": article.title,
                        "url": article.url,
                        "published_at": article.published_at.isoformat() if article.published_at else None,
                        "source_name": article.source_name,
                        "source_type": article.source_type,
                        "category": classification.primary_category.value if classification.primary_category else "market",
                        "priority": classification.priority.value if classification.priority else "medium",
                        "digest_summary": classification.summary,
                        "original_summary": article.summary,
                        "companies": classification.companies or classification.key_entities,
                        "materials": classification.materials or [],
                        "topics": [c.value for c in classification.categories] if classification.categories else [],
                        "industries": [i.value for i in classification.industries] if classification.industries else [],
                        "relevance_score": classification.relevance_score,
                        "confidence": classification.confidence,
                        "classifier_model": self.config.classifier_model,
                        "classified_at": datetime.utcnow().isoformat(),
                        # Feed eligibility: True if article has valid date within lookback window
                        "feed_eligible": article_feed_status.get(id(article), False),
                    }
                    digest_items_for_ui.append(digest_item)
                    
                except Exception as e:
                    stats.errors.append(f"Storage prep error: {str(e)[:100]}")
            
            stats.articles_stored = stored_count
            
            # Step 6a: Store articles in BigQuery
            if article_records:
                try:
                    await self.gcp_storage.store_articles(article_records)
                except Exception as e:
                    logger.error(f"BQ articles storage error: {e}")
            
            # Step 6b: Store images
            if all_extracted_images:
                try:
                    await self.gcp_storage.store_article_images(all_extracted_images)
                except Exception as e:
                    logger.error(f"BQ images storage error: {e}")
            
            # Step 6c: Store digest items (Drumbeat Feed)
            if digest_items_for_ui:
                try:
                    await self.gcp_storage.store_digest_items(digest_items_for_ui)
                except Exception as e:
                    logger.error(f"BQ digest items storage error: {e}")

            # Step 7: Update vector stores
            try:
                count = await self.vector_store.add_items(vector_docs)
                logger.info(f"Added {count} items to vector store")
            except Exception as e:
                logger.error(f"Vector store error: {e}")
            
            # Step 8: Generate Digest (Drumbeat)
            # This generates the "feed cards" for the UI. We KEEP this as it's data-dependent.
            # We REMOVE the "Pulse Briefing" generation (Agent 1 & 2) as that is now a separate job.
            if not backfill_days or backfill_days <= 3:
                logger.info("Step 8: Generating digest feed (Drumbeat)...")
                await self.digest_generator.generate(hours=self.config.digest_hours)
                
                # NOTE: Briefing generation (Pulse - Need to Know) is now handled 
                # by a separate scheduled job calling /api/v1/scheduler/briefing
            
            stats.completed_at = datetime.utcnow()
            stats.status = "completed"
            
            # Log success
            try:
                await self.gcp_storage.log_ingestion_event(
                    run_id=run_id,
                    event_type="COMPLETED",
                    job_type=job_type,
                    status="success",
                    metrics={
                        "fetched": len(all_articles),
                        "stored": stats.articles_stored,
                        "errors": len(stats.errors)
                    }
                )
            except Exception as e:
                logger.warning(f"Failed to log ingestion completion: {e}")
                
            logger.info(f"Ingestion complete in {stats.duration_seconds:.1f}s")
            
        except Exception as e:
            logger.error(f"Ingestion error: {e}", exc_info=True)
            stats.errors.append(str(e))
            stats.status = "failed"
            stats.completed_at = datetime.utcnow()
            
            try:
                await self.gcp_storage.log_ingestion_event(
                    run_id=run_id,
                    event_type="FAILED",
                    job_type=job_type,
                    status="error",
                    error_message=str(e)
                )
            except Exception as e2:
                logger.warning(f"Failed to log ingestion failure: {e2}")
        
        return stats

    async def _get_tracked_tickers(self) -> List[str]:
        """Get tickers for all tracked entities from BigQuery/master company list"""
        tickers = []
        try:
            # First try BigQuery companies table
            companies = await self.gcp_storage.get_companies()
            for comp in companies:
                ticker = comp.get("ticker")
                if ticker and ticker.lower() != 'private':
                    tickers.append(ticker)
            
            # Fallback to master company list CSV if BigQuery is empty
            if not tickers:
                logger.info("No companies in BigQuery, loading from master company list")
                df = load_companies()
                if not df.empty and 'stock_ticker' in df.columns:
                    tickers = df['stock_ticker'].dropna().tolist()
                    # Filter out 'private' entries
                    tickers = [t for t in tickers if t and t.lower() != 'private']
                    logger.info(f"Loaded {len(tickers)} tickers from master company list")
        except Exception as e:
            logger.warning(f"Error loading tickers from BigQuery: {e}, falling back to CSV")
            try:
                df = load_companies()
                if not df.empty and 'stock_ticker' in df.columns:
                    tickers = df['stock_ticker'].dropna().tolist()
                    tickers = [t for t in tickers if t and t.lower() != 'private']
            except Exception as e2:
                logger.error(f"Could not load company list: {e2}")
        return list(set(tickers))

    def _create_corpus_item(self, article, classification, mentions):
        """Create a corpus item from processed article"""
        priority_boost = article.raw_data.get("priority_boost", 0)
        relevance = min(1.0, classification.relevance_score + priority_boost)
        
        priority = classification.priority
        if relevance >= 0.9 and priority == Priority.MEDIUM:
            priority = Priority.HIGH
        
        return CorpusItem(
            id=str(uuid.uuid4()),
            title=article.title,
            summary=classification.summary,
            full_text=article.full_text,
            url=article.url,
            source=ContentSource(
                name=article.source_name,
                url=article.url,
                source_type=article.source_type,
                published_at=article.published_at,
            ),
            categories=classification.categories,
            primary_category=classification.primary_category,
            priority=priority,
            relevance_score=relevance,
            entity_mentions=mentions,
            industries=classification.industries,
            companies_mentioned=classification.key_entities,
            published_at=article.published_at or datetime.utcnow(),  # Fallback handled earlier in pipeline
            ingested_at=datetime.utcnow(),  # Track when we ingested this
            metadata=article.raw_data or {},
        )

    def _create_article_record(self, article, classification):
        """Create an ArticleRecord for BigQuery articles table storage"""
        from app.db.gcp_storage import ArticleRecord
        
        return ArticleRecord(
            id=str(uuid.uuid4()),
            title=article.title,
            url=article.url,
            published_at=article.published_at or datetime.utcnow(),
            source_name=article.source_name,
            source_type=article.source_type,
            summary=article.summary,
            full_text=article.full_text,
            category=classification.primary_category.value if classification.primary_category else "general",
            topics=[c.value for c in classification.categories] if classification.categories else [],
            companies_mentioned=classification.key_entities or [],
            relevance_score=classification.relevance_score,
            fetched_at=datetime.utcnow(),
            # Note: metadata field removed - ArticleRecord doesn't support it and BQ table lacks the column
        )

    async def run_rss_only(self) -> IngestionStats:
        """Run RSS ingestion only (faster, for frequent runs)"""
        if not self._initialized:
            await self.initialize()
        
        stats = IngestionStats(started_at=datetime.utcnow())
        
        try:
            # Fetch RSS
            rss_articles = await self.rss_fetcher.fetch_all_feeds()
            stats.rss_articles_fetched = len(rss_articles)
            
            # Deduplicate
            unique_articles = []
            for article in rss_articles:
                is_dup, _ = await self.dedup_service.check_duplicate(article)
                if is_dup:
                    stats.duplicates_skipped += 1
                else:
                    unique_articles.append(article)
            
            # Classify and store
            classified = await self.classifier.classify_batch(unique_articles)
            stats.articles_classified = len(classified)
            
            stored_count = 0
            vector_docs = []
            article_records = []  # For BigQuery articles table
            
            for article, classification in classified:
                mentions = self.entity_linker.link_article(article)
                corpus_item = self._create_corpus_item(article, classification, mentions)
                
                try:
                    stored_count += 1
                    vector_docs.append(corpus_item)
                    
                    # Build ArticleRecord for BigQuery articles table
                    article_records.append(self._create_article_record(article, classification))
                except Exception as e:
                    stats.errors.append(str(e)[:100])
                    
            stats.articles_stored = stored_count
            
            # Store articles in BigQuery articles table
            logger.info("Storing articles in BigQuery...")
            if article_records:
                try:
                    bq_articles_stored = await self.gcp_storage.store_articles(article_records)
                    logger.info(f"Stored {bq_articles_stored} articles in BigQuery articles table")
                except Exception as e:
                    logger.error(f"BigQuery articles storage error: {e}")
                    stats.errors.append(f"BQ articles error: {str(e)[:100]}")
            
            # Store digest items for UI digest cards (BigQuery digest_items table)
            logger.info("Storing digest items in BigQuery...")
            digest_items_for_ui = []
            now_utc = datetime.utcnow()
            for article, classification in classified:
                # Determine feed eligibility based on date
                feed_eligible = True
                if article.published_at:
                    pub_date = _make_naive_utc(article.published_at)
                    if pub_date > now_utc:  # Future date = bad parsing
                        feed_eligible = False
                else:
                    feed_eligible = False  # No date = not feed eligible
                
                article_id = str(uuid.uuid4())
                digest_item = {
                    "article_id": article_id,
                    "title": article.title,
                    "url": article.url,
                    "published_at": article.published_at.isoformat() if article.published_at else None,
                    "source_name": article.source_name,
                    "source_type": article.source_type,
                    "category": classification.primary_category.value if classification.primary_category else "market",
                    "priority": classification.priority.value if classification.priority else "medium",
                    "digest_summary": classification.summary,
                    "original_summary": article.summary,
                    "companies": classification.companies or classification.key_entities,
                    "materials": classification.materials or [],
                    "topics": [c.value for c in classification.categories] if classification.categories else [],
                    "industries": [i.value for i in classification.industries] if classification.industries else [],
                    "relevance_score": classification.relevance_score,
                    "confidence": classification.confidence,
                    "classifier_model": self.config.classifier_model,
                    "classified_at": datetime.utcnow().isoformat(),
                    "feed_eligible": feed_eligible,
                }
                digest_items_for_ui.append(digest_item)
            
            if digest_items_for_ui:
                try:
                    stored_digest_items = await self.gcp_storage.store_digest_items(digest_items_for_ui)
                    logger.info(f"Stored {stored_digest_items} digest items in BigQuery digest_items table")
                except Exception as e:
                    logger.error(f"BigQuery digest_items storage error: {e}")
                    stats.errors.append(f"BQ digest_items error: {str(e)[:100]}")
            
            # Update vector store (Environment-aware)
            if vector_docs:
                try:
                    count = await self.vector_store.add_items(vector_docs)
                    logger.info(f"Added {count} items to vector store")
                except Exception as e:
                    logger.error(f"Vector store error: {e}")
                    stats.errors.append(f"Vector store error: {str(e)[:100]}")
            
            stats.completed_at = datetime.utcnow()
            stats.status = "completed"
            
        except Exception as e:
            stats.errors.append(str(e))
            stats.status = "failed"
            stats.completed_at = datetime.utcnow()
        
        return stats

    async def run_financials_only(self, backfill_days: int = 83) -> IngestionStats:
        """
        Run targeted backfill for SEC filings and Earnings transcripts only.
        Skips RSS, PR, and web search to save time and API costs.
        """
        if not self._initialized:
            await self.initialize()
        
        stats = IngestionStats(started_at=datetime.utcnow())
        
        try:
            # Get tracked companies
            companies = await self._get_tracked_companies()
            logger.info(f"Loaded {len(companies)} companies for financials backfill")
            
            # Calculate date range - backfill to Oct 1, 2025 for Tier 1 data
            tier1_since = datetime(2025, 10, 1)
            if backfill_days:
                tier1_since = datetime.utcnow() - timedelta(days=backfill_days)
            
            # 1. SEC Filings
            sec_items = []
            if self.config.sec_api_key or os.getenv("SEC_IO_KEY"):
                logger.info(f"Fetching SEC filings (Since {tier1_since.date()})...")
                for comp in companies:
                    if not comp.get("ticker"): 
                        continue
                    try:
                        filings = self.sec_collector.collect_for_company(
                            company_id=comp["id"],
                            ticker=comp["ticker"],
                            since=tier1_since
                        )
                        sec_items.extend(filings)
                    except Exception as e:
                        logger.error(f"SEC fetch failed for {comp['ticker']}: {e}")
                stats.sec_filings_fetched = len(sec_items)
                logger.info(f"Collected {len(sec_items)} SEC filings")
            
            # NOTE: Earnings transcripts disabled - FMP requires premium subscription (402 error)
            # TODO: Re-enable when FMP premium acquired or API Ninja URL dedup issue fixed
            
            # Convert to RawArticle format
            converted_sec = [self._convert_sec_to_article(item) for item in sec_items]
            
            all_articles = converted_sec
            logger.info(f"Total financial articles to process: {len(all_articles)}")
            
            # Deduplicate
            logger.info("Deduplicating...")
            unique_articles = []
            for article in all_articles:
                is_dup, _ = await self.dedup_service.check_duplicate(article)
                if is_dup:
                    stats.duplicates_skipped += 1
                else:
                    unique_articles.append(article)
            
            logger.info(f"Unique articles after dedup: {len(unique_articles)}")
            
            # Classify
            logger.info("Classifying content...")
            classified = await self.classifier.classify_batch(unique_articles)
            stats.articles_classified = len(classified)
            
            # Store
            logger.info("Linking entities and storing...")
            stored_count = 0
            vector_docs = []
            article_records = []  # For BigQuery articles table
            
            for article, classification in classified:
                mentions = self.entity_linker.link_article(article)
                corpus_item = self._create_corpus_item(article, classification, mentions)
                
                try:
                    stored_count += 1
                    vector_docs.append(corpus_item)
                    
                    # Build ArticleRecord for BigQuery articles table
                    article_records.append(self._create_article_record(article, classification))
                except Exception as e:
                    stats.errors.append(f"Storage error: {str(e)[:100]}")
            
            stats.articles_stored = stored_count
            
            # Store articles in BigQuery articles table
            logger.info("Storing articles in BigQuery...")
            if article_records:
                try:
                    bq_articles_stored = await self.gcp_storage.store_articles(article_records)
                    logger.info(f"Stored {bq_articles_stored} articles in BigQuery articles table")
                except Exception as e:
                    logger.error(f"BigQuery articles storage error: {e}")
                    stats.errors.append(f"BQ articles error: {str(e)[:100]}")
            
            # Store digest items for UI digest cards (BigQuery digest_items table)
            logger.info("Storing digest items in BigQuery...")
            digest_items_for_ui = []
            now_utc = datetime.utcnow()
            for article, classification in classified:
                # Determine feed eligibility based on date
                feed_eligible = True
                if article.published_at:
                    pub_date = _make_naive_utc(article.published_at)
                    if pub_date > now_utc:  # Future date = bad parsing
                        feed_eligible = False
                else:
                    feed_eligible = False  # No date = not feed eligible
                
                article_id = str(uuid.uuid4())
                digest_item = {
                    "article_id": article_id,
                    "title": article.title,
                    "url": article.url,
                    "published_at": article.published_at.isoformat() if article.published_at else None,
                    "source_name": article.source_name,
                    "source_type": article.source_type,
                    "category": classification.primary_category.value if classification.primary_category else "market",
                    "priority": classification.priority.value if classification.priority else "medium",
                    "digest_summary": classification.summary,
                    "original_summary": article.summary,
                    "companies": classification.companies or classification.key_entities,
                    "materials": classification.materials or [],
                    "topics": [c.value for c in classification.categories] if classification.categories else [],
                    "industries": [i.value for i in classification.industries] if classification.industries else [],
                    "relevance_score": classification.relevance_score,
                    "confidence": classification.confidence,
                    "classifier_model": self.config.classifier_model,
                    "classified_at": datetime.utcnow().isoformat(),
                    "feed_eligible": feed_eligible,
                }
                digest_items_for_ui.append(digest_item)
            
            if digest_items_for_ui:
                try:
                    stored_digest_items = await self.gcp_storage.store_digest_items(digest_items_for_ui)
                    logger.info(f"Stored {stored_digest_items} digest items in BigQuery digest_items table")
                except Exception as e:
                    logger.error(f"BigQuery digest_items storage error: {e}")
                    stats.errors.append(f"BQ digest_items error: {str(e)[:100]}")
            
            # Update vector store (BigQuery)
            if vector_docs:
                await self.vector_store.add_items(vector_docs)
            
            stats.completed_at = datetime.utcnow()
            stats.status = "completed"
            logger.info(f"Financials backfill complete in {stats.duration_seconds:.1f}s")
            
        except Exception as e:
            logger.error(f"Financials backfill error: {e}", exc_info=True)
            stats.errors.append(str(e))
            stats.status = "failed"
            stats.completed_at = datetime.utcnow()
        
        return stats

    async def run_earnings_only(self, year: int = None, quarter: int = None) -> IngestionStats:
        """
        Run targeted backfill for Earnings transcripts only.
        
        Uses API Ninja earnings transcripts with quarter-based fetching.
        
        Args:
            year: Target year (e.g., 2025). Defaults to current year.
            quarter: Target quarter (1-4). Defaults to most recent completed quarter.
        """
        stats = IngestionStats(started_at=datetime.utcnow())
        
        if not self._initialized:
            await self.initialize()
        
        try:
            # Determine target quarter if not specified
            now = datetime.utcnow()
            if year is None:
                year = now.year
            if quarter is None:
                # Default to most recent completed quarter's earnings
                if now.month >= 10:
                    quarter = 3
                elif now.month >= 7:
                    quarter = 2
                elif now.month >= 4:
                    quarter = 1
                else:
                    quarter = 4
                    year = year - 1
            
            logger.info(f"Running earnings backfill for Q{quarter} {year}")
            
            # Get companies with stock tickers from BigQuery companies table
            storage = await get_storage()
            companies_raw = await storage.get_companies()
            # Filter to public companies (have ticker, not 'private')
            companies = [c for c in companies_raw if c.get('ticker') and c.get('ticker') != 'private']
            logger.info(f"Found {len(companies)} public companies with stock tickers")
            
            earnings_items = []
            for comp in companies:
                ticker = comp['ticker']
                try:
                    # Use collect_for_quarter to fetch the specific quarter directly
                    transcript = self.earnings_collector.collect_for_quarter(
                        ticker=ticker,
                        year=year,
                        quarter=quarter,
                        company_name=comp.get('name', '')
                    )
                    if transcript:
                        earnings_items.append(self._convert_earnings_to_article(transcript))
                        logger.info(f"  ✓ {ticker}: Q{quarter} {year} transcript found")
                except Exception as e:
                    logger.debug(f"  X {ticker}: {e}")
            
            stats.earnings_transcripts_fetched = len(earnings_items)
            logger.info(f"Collected {len(earnings_items)} earnings transcripts")
            
            if earnings_items:
                # Deduplicate
                unique_items = []
                for item in earnings_items:
                    is_dup, _ = await self.dedup_service.check_duplicate(item)
                    if is_dup:
                        stats.duplicates_skipped += 1
                    else:
                        unique_items.append(item)
                
                logger.info(f"After dedup: {len(unique_items)} new transcripts (skipped {stats.duplicates_skipped} dupes)")
                
                if unique_items:
                    # Classify
                    classified = await self.classifier.classify_batch(unique_items)
                    stats.articles_classified = len(classified)
                    
                    # Store in BigQuery articles table
                    article_records = []
                    for article, classification in classified:
                        article_records.append(self._create_article_record(article, classification))
                    
                    if article_records:
                        bq_articles_stored = await self.gcp_storage.store_articles(article_records)
                        logger.info(f"Stored {bq_articles_stored} articles in BigQuery")
                    
                    # Store digest items for UI
                    digest_items = []
                    now_utc = datetime.utcnow()
                    for article, classification in classified:
                        article_id = str(uuid.uuid4())
                        # Determine feed_eligible based on date
                        feed_eligible = True
                        if article.published_at:
                            pub_date = _make_naive_utc(article.published_at)
                            if pub_date > now_utc:  # Future date = bad parsing
                                feed_eligible = False
                        else:
                            feed_eligible = False
                        
                        digest_item = {
                            "article_id": article_id,
                            "title": article.title,
                            "headline": article.title,  # Use title as headline for SEC/earnings
                            "url": article.url,
                            "published_at": article.published_at.isoformat() if article.published_at else None,
                            "source_name": article.source_name,
                            "source_type": article.source_type,
                            "category": classification.primary_category.value if classification.primary_category else "financial",
                            "priority": classification.priority.value if classification.priority else "high",
                            "digest_summary": classification.summary,
                            "original_summary": article.summary,
                            "companies": classification.companies or classification.key_entities,
                            "materials": classification.materials or [],
                            "topics": [c.value for c in classification.categories] if classification.categories else [],
                            "industries": [i.value for i in classification.industries] if classification.industries else [],
                            "relevance_score": classification.relevance_score,
                            "confidence": classification.confidence,
                            "classifier_model": self.config.classifier_model,
                            "classified_at": now_utc.isoformat(),
                            "feed_eligible": feed_eligible,
                        }
                        digest_items.append(digest_item)
                    
                    if digest_items:
                        digest_stored = await self.gcp_storage.store_digest_items(digest_items)
                        logger.info(f"Stored {digest_stored} digest items in BigQuery")
                    
                    logger.info(f"Stored {len(classified)} earnings transcripts")
            
            stats.status = "completed"
            stats.completed_at = datetime.utcnow()
            
        except Exception as e:
            logger.error(f"Earnings backfill error: {e}", exc_info=True)
            stats.errors.append(str(e))
            stats.status = "failed"
            stats.completed_at = datetime.utcnow()
        
        return stats
    
    async def run_digest_only(self) -> Any:
        """Generate digest only (no ingestion)"""
        if not self._initialized:
            await self.initialize()
        
        return await self.digest_generator.generate(hours=self.config.digest_hours)

    async def get_status(self) -> Dict[str, Any]:
        """Get current status of the orchestrator components"""
        if not self._initialized:
             return {
                 "initialized": False,
                 "entity_count": 0,
                 "dedup_cache_size": 0,
                 "corpus_stats": {},
                 "latest_ingestion": None
             }
        
        # Get stats from BigQuery storage
        try:
            corpus_stats = await self.gcp_storage.get_digest_stats(hours=72)
        except Exception as e:
            logger.warning(f"Could not get corpus stats: {e}")
            corpus_stats = {}
        
        latest_run = None  # Latest ingestion tracking moved to BigQuery logs
        
        return {
            "initialized": True,
            "entity_count": len(self.entity_linker._entities) if self.entity_linker else 0,
            "dedup_cache_size": len(self.dedup_service._url_cache) if self.dedup_service else 0,
            "corpus_stats": corpus_stats,
            "latest_ingestion": latest_run.model_dump() if latest_run else None
        }


    async def _get_tracked_companies(self) -> List[Dict]:
        """Get full company details from CSV and database"""
        companies_map = {}
        try:
            # 1. Load from BigQuery companies table (primary source)
            bq_companies = await self.gcp_storage.get_companies()
            for comp in bq_companies:
                ticker = comp.get("ticker")
                if ticker:
                    companies_map[ticker] = {
                        "id": comp.get("id"),
                        "name": comp.get("name"),
                        "ticker": ticker
                    }
            
            # 2. Merge with CSV companies (backup source)
            csv_companies = self._load_companies_from_csv()
            for comp in csv_companies:
                ticker = comp.get("ticker")
                if ticker and ticker not in companies_map:
                    companies_map[ticker] = comp
            
            companies = list(companies_map.values())
            logger.info(f"Total tracked companies for ingestion: {len(companies)}")
            return companies
                
        except Exception as e:
            logger.error(f"Error getting tracked companies from BigQuery: {e}")
            # Fallback to just CSV if BigQuery fails
            return self._load_companies_from_csv()
    
    def _load_companies_from_csv(self) -> List[Dict]:
        """Load companies from master CSV file"""
        try:
            df = load_companies()
            if df.empty:
                logger.error("Master company list is empty")
                return []
            
            companies = []
            for _, row in df.iterrows():
                ticker = row.get('stock_ticker', '')
                # Skip private companies (no ticker for financial data)
                if ticker and str(ticker).lower() != 'private':
                    companies.append({
                        "id": row.get('company_id', ''),
                        "name": row.get('company', ''),
                        "ticker": ticker
                    })
            
            logger.info(f"Loaded {len(companies)} companies from master list")
            return companies
        except Exception as e:
            logger.error(f"Could not load master company list: {e}")
            return []

    def _convert_pr_to_article(self, pr) -> RawArticle:
        # NOTE: Keep published_date as-is (even if None) to allow proper date filtering
        # Do NOT fallback to discovered_at as that causes old articles to appear new
        return RawArticle(
            title=pr.title,
            url=pr.url,
            summary=(pr.full_text[:1000] + "...") if pr.full_text else "",
            full_text=pr.full_text,
            published_at=pr.published_date,  # Keep None if extraction failed
            source_name=pr.source,
            source_type="press_release",
            raw_data={
                "ticker": pr.ticker,
                "company_id": pr.company_id,
                "word_count": pr.word_count
            }
        )

    # Section display names for SEC filings
    SEC_SECTION_DISPLAY_NAMES = {
        "1": "1 Business",
        "1A": "1A Risk Factors",
        "7": "7 MD&A",
        "7A": "7A Market Risk Disclosures",
        "business": "1 Business",
        "risk_factors": "1A Risk Factors",
        "mda": "7 MD&A",
        "market_risk_disclosures": "7A Market Risk Disclosures",
    }

    def _convert_sec_to_article(self, filing) -> RawArticle:
        # Construct summary/text
        text_parts = []
        section_names = []
        
        if filing.full_text:
            text_parts.append(filing.full_text)
        elif filing.sections:
            for name, content in filing.sections.items():
                text_parts.append(f"=== {name.upper()} ===\n{content}")
                # Track section names for source_name
                display_name = self.SEC_SECTION_DISPLAY_NAMES.get(name, name)
                section_names.append(display_name)
        
        full_text = "\n\n".join(text_parts)
        summary = f"SEC Filing {filing.form_type} for {filing.company_name} ({filing.ticker})"
        if full_text:
            summary += "\n" + full_text[:800] + "..."
        
        # Build source_name: "SEC - 1A Risk Factors" or "SEC - 1A Risk Factors, 7 MD&A" for multiple
        if section_names:
            source_name = f"SEC - {', '.join(section_names)}"
        else:
            source_name = f"SEC - {filing.form_type}"
            
        return RawArticle(
            title=f"{filing.company_name} - {filing.form_type}",
            url=filing.filing_url,
            summary=summary,
            full_text=full_text,
            published_at=filing.filed_at,
            source_name=source_name,
            source_type="sec_filing",
            raw_data={
                "accession_no": filing.id,
                "cik": filing.cik,
                "form_type": filing.form_type,
                "ticker": filing.ticker
            }
        )

    def _convert_earnings_to_article(self, transcript) -> RawArticle:
        """Convert an EarningsTranscript (FMP or legacy API Ninja) to RawArticle.
        
        Supports both FMPEarningsTranscript and legacy EarningsTranscript models.
        FMP model uses @property ticker -> symbol alias for compatibility.
        """
        # Convert Participant objects to dicts for JSON serialization (if available)
        participants_data = None
        if hasattr(transcript, 'participants') and transcript.participants:
            participants_data = [
                p.model_dump() if hasattr(p, 'model_dump') else (p.to_dict() if hasattr(p, 'to_dict') else p)
                for p in transcript.participants
            ]
        
        # Convert TranscriptSection objects to dicts for JSON serialization (if available)
        transcript_split_data = None
        if hasattr(transcript, 'transcript_split') and transcript.transcript_split:
            transcript_split_data = [
                s.model_dump() if hasattr(s, 'model_dump') else (s.to_dict() if hasattr(s, 'to_dict') else s)
                for s in transcript.transcript_split
            ]
        
        # Use FMP's real URL if available, otherwise generate a unique ID URL
        # FMP provides: https://financialmodelingprep.com/api/v3/earning_call_transcript/{ticker}?quarter={q}&year={y}
        earnings_url = transcript.url or f"earnings://{transcript.ticker}/{transcript.year}/Q{transcript.quarter}"
        
        # Get company name with fallback
        company_name = getattr(transcript, 'company_name', '') or transcript.ticker
        
        return RawArticle(
            title=f"{company_name} Q{transcript.quarter} {transcript.year} Earnings Call",
            url=earnings_url,
            summary=transcript.content[:1000] + "..." if len(transcript.content) > 1000 else transcript.content,
            full_text=transcript.content,
            published_at=transcript.date,
            source_name=f"Earnings - Q{transcript.quarter} {transcript.year}",
            source_type="earnings_transcript",  # Consistent source type
            raw_data={
                "ticker": transcript.ticker,
                "quarter": transcript.quarter,
                "year": transcript.year,
                "participants": participants_data,
                "transcript_split": transcript_split_data,
                "earnings_timing": getattr(transcript, 'earnings_timing', None),
                "cik": getattr(transcript, 'cik', None),
                "timestamp": getattr(transcript, 'timestamp', None),
                "sentiment": getattr(transcript, 'sentiment', None),
                "source_api": "fmp",  # Track which API provided this
            }
        )

    def _convert_stocknews_to_article(self, article) -> RawArticle:
        """Convert a StockNewsArticle to RawArticle for the pipeline."""
        from app.tools.stocknews.models import StockNewsArticle
        
        return RawArticle(
            title=article.title,
            url=article.url,
            summary=article.text[:1000] + "..." if len(article.text) > 1000 else article.text,
            full_text=article.text,
            published_at=article.published_at,
            source_name=article.source_name,
            source_type="stocknewsapi",  # Distinct source type for tracking
            raw_data={
                "news_id": article.news_id,
                "tickers": article.tickers,
                "sentiment": article.sentiment,
                "rank_score": article.rank_score,
                "search_query": article.search_query,
                "search_type": article.search_type,
                "image_url": article.image_url,
            }
        )

    def _convert_fmp_to_article(self, article) -> RawArticle:
        """Convert an FMPNewsArticle to RawArticle for the pipeline.
        
        Uses source_type='premium_news' to distinguish FMP premium content
        (Benzinga, Seeking Alpha, etc.) from other sources.
        """
        return RawArticle(
            title=article.title,
            url=article.url,
            summary=article.text[:1000] + "..." if len(article.text) > 1000 else article.text,
            full_text=article.text,
            published_at=article.published_at,
            source_name=article.publisher,  # e.g., "Benzinga", "Seeking Alpha"
            source_type="premium_news",  # Distinct source type for FMP premium content
            raw_data={
                "symbol": article.symbol,
                "site": article.site,
                "image_url": article.image_url,
            }
        )

    def _convert_search_result_to_article(self, result, company: Dict[str, Any], search_engine: str = None) -> RawArticle:
        """Convert an Exa SearchResult to RawArticle, extracting domain as source_name"""
        # Determine source_type based on engine
        source_type = "web_news"
        if search_engine == "exa":
            source_type = "web_news_exa"
        elif search_engine == "tavily":
            source_type = "web_news_tavily"

        # Extract domain from URL (e.g., "reuters.com" from "https://www.reuters.com/...")
        try:
            parsed = urlparse(result.url)
            domain = parsed.netloc.lower()
            # Remove 'www.' prefix if present
            if domain.startswith('www.'):
                domain = domain[4:]
            source_name = domain
        except Exception:
            source_name = "web"
        
        # Exa provides clean publishedDate - use it directly when available
        # Fall back to extract_publication_date only if Exa date is missing
        # IMPORTANT: Validate dates are not in the future (Exa sometimes extracts 
        # future projection dates from content like "expected to reach X by 2026")
        api_date = getattr(result, 'published_date', None)
        published_at = None
        max_future_days = 2  # Allow small buffer for timezone differences
        
        if api_date:
            # Exa returns ISO format dates - parse them directly
            try:
                if isinstance(api_date, str):
                    # Handle ISO format: "2025-01-15T00:00:00.000Z"
                    published_at = datetime.fromisoformat(api_date.replace('Z', '+00:00'))
                else:
                    published_at = api_date
                
                # Validate: reject future dates (Exa sometimes returns these incorrectly)
                if published_at:
                    # Make naive for comparison
                    if hasattr(published_at, 'tzinfo') and published_at.tzinfo is not None:
                        check_date = published_at.replace(tzinfo=None)
                    else:
                        check_date = published_at
                    max_valid_date = datetime.utcnow() + timedelta(days=max_future_days)
                    if check_date > max_valid_date:
                        logger.debug(
                            f"Rejecting future date {published_at} from Exa for {result.url[:60]}... "
                            f"(likely a market projection date, not publication date)"
                        )
                        published_at = None
            except Exception:
                # Fallback to extraction if parsing fails
                published_at = extract_publication_date(
                    url=result.url,
                    content=result.snippet,
                    api_date=api_date,
                    fallback=None
                )
        else:
            # No API date - try extraction (but likely won't find one)
            published_at = extract_publication_date(
                url=result.url,
                content=result.snippet,
                api_date=None,
                fallback=None  # No fallback - let downstream filtering handle None dates
            )
        
        return RawArticle(
            title=result.title,
            url=result.url,
            summary=result.snippet,
            full_text=result.snippet,  # Web search only returns snippet
            published_at=published_at,
            source_name=source_name,
            source_type=source_type,
            raw_data={
                "company_id": company.get("id"),
                "company_name": company.get("name"),
                "ticker": company.get("stock_ticker"),
                "relevance_score": result.score,
                "search_engine": search_engine
            }
        )

# Singleton instance
_orchestrator_instance = None

def get_orchestrator() -> IngestionOrchestrator:
    """Get global orchestrator instance"""
    global _orchestrator_instance
    if _orchestrator_instance is None:
        config = IngestionConfig()
        _orchestrator_instance = IngestionOrchestrator(config)
    return _orchestrator_instance

