"""
GCP Storage Layer for Production Data
======================================

Provides BigQuery and GCS integration for:
- Time-series data storage (freight rates, commodity prices, BDI)
- Document/article storage in GCS
- Structured queries across historical data

Environment Detection:
- LOCAL: Falls back to SQLite + local files
- GCP: Uses BigQuery + GCS

Required Environment Variables (production):
- GCP_PROJECT_ID: Your GCP project
- GCP_DATASET_ID: BigQuery dataset (default: c1_intelligence)
- GCS_BUCKET_NAME: GCS bucket for documents
- GOOGLE_APPLICATION_CREDENTIALS: Path to service account key (or use workload identity)
"""

import os
import json
import uuid
from datetime import datetime, date
from typing import Optional, List, Dict, Any, Literal
from dataclasses import dataclass, field, asdict
from enum import Enum

from app.utils.logger import get_logger

logger = get_logger(__name__)


def _safe_parse_list(value: Any) -> List[str]:
    """
    Safely parse a value that could be:
    - None or empty string -> []
    - A JSON array string like '["a", "b"]' -> ['a', 'b']
    - A comma-separated string like 'a, b, c' -> ['a', 'b', 'c']
    - Already a list -> return as-is
    """
    if not value:
        return []
    
    # Already a list (e.g., from SQLite JSON deserialization)
    if isinstance(value, list):
        return value
    
    # Try JSON first
    if isinstance(value, str):
        value = value.strip()
        if value.startswith('['):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                pass
        
        # Fall back to comma-separated parsing
        if value:
            return [item.strip() for item in value.split(',') if item.strip()]
    
    return []


# =============================================================================
# Configuration
# =============================================================================
# Set via environment variables: GCP_PROJECT_ID, GCS_BUCKET_NAME
# =============================================================================
_DEFAULT_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "")
_DEFAULT_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME", "")

@dataclass
class GCPConfig:
    """GCP configuration settings."""
    # Hardcoded production defaults ensure BigQuery is ALWAYS used
    project_id: str = field(default_factory=lambda: os.getenv("GCP_PROJECT_ID", _DEFAULT_PROJECT_ID))
    dataset_id: str = field(default_factory=lambda: os.getenv("GCP_DATASET_ID", "c1_intelligence"))
    bucket_name: str = field(default_factory=lambda: os.getenv("GCS_BUCKET_NAME", _DEFAULT_BUCKET_NAME))
    location: str = field(default_factory=lambda: os.getenv("GCP_LOCATION", "us-central1"))
    
    @property
    def is_configured(self) -> bool:
        """Check if GCP is properly configured (always True with hardcoded defaults)."""
        return bool(self.project_id and self.bucket_name)
    
    @property
    def full_dataset_id(self) -> str:
        """Get full BigQuery dataset ID."""
        return f"{self.project_id}.{self.dataset_id}"


# Global config instance
gcp_config = GCPConfig()


# =============================================================================
# Data Models for Time-Series Storage
# =============================================================================

class DataSource(str, Enum):
    """Data source identifiers."""
    RSS_FEED = "rss_feed"           # RSS feed articles
    EARNINGS = "earnings_transcript" # Earnings call transcripts
    PRESS_RELEASE = "press_release" # Press releases (Exa.ai - clean publishedDate)
    SEC_FILING = "sec_filing"       # SEC filings (10-K, 10-Q, 8-K)
    WEB_NEWS = "web_news"           # Legacy/General web news
    WEB_NEWS_EXA = "web_news_exa"   # Exa.ai sourced news
    WEB_NEWS_TAVILY = "web_news_tavily" # Tavily sourced news


@dataclass
class FreightRateRecord:
    """A shipping/freight rate record."""
    lane: str                 # e.g., "Shanghai - Los Angeles"
    rate: float               # price in USD
    currency: str = "USD"
    unit: str = "40ft"        # container size
    change_pct: Optional[float] = None
    source: str = "drewry"    # drewry, xeneta, etc.
    as_of: datetime = field(default_factory=datetime.utcnow)
    fetched_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "lane": self.lane,
            "rate": self.rate,
            "currency": self.currency,
            "unit": self.unit,
            "change_pct": self.change_pct,
            "source": self.source,
            "as_of": self.as_of.isoformat(),
            "fetched_at": self.fetched_at.isoformat()
        }


@dataclass
class ArticleRecord:
    """A news/content article record."""
    id: str
    title: str
    url: str
    published_at: datetime
    source_name: str
    source_type: str          # rss_feed, web_news, sec_filing, press_release
    summary: Optional[str] = None
    full_text: Optional[str] = None
    category: Optional[str] = None
    topics: List[str] = field(default_factory=list)
    companies_mentioned: List[str] = field(default_factory=list)
    relevance_score: float = 0.5
    fetched_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "url": self.url,
            "published_at": self.published_at.isoformat(),
            "source_name": self.source_name,
            "source_type": self.source_type,
            "summary": self.summary,
            "full_text": self.full_text,
            "category": self.category,
            "topics": self.topics,
            "companies_mentioned": self.companies_mentioned,
            "relevance_score": self.relevance_score,
            "fetched_at": self.fetched_at.isoformat()
        }


# =============================================================================
# Storage Interface (Abstract)
# =============================================================================

class DataStorageInterface:
    """
    Abstract interface for data storage.
    Implemented by both local (SQLite) and GCP (BigQuery) backends.
    """
    
    async def initialize(self):
        """Initialize storage (create tables, etc.)"""
        raise NotImplementedError
    
    # Articles
    async def store_articles(self, records: List[ArticleRecord]) -> int:
        """Store article records."""
        raise NotImplementedError
    
    async def get_articles(
        self,
        source_type: Optional[str] = None,
        category: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        search_query: Optional[str] = None,
        limit: int = 50,
    ) -> List[ArticleRecord]:
        """Query articles with filters."""
        raise NotImplementedError
    
    # Digest items (classified articles)
    async def store_digest_items(self, items: List[Dict[str, Any]]) -> int:
        """Store classified digest items."""
        raise NotImplementedError
    
    async def get_digest_items(
        self,
        hours: int = 72,
        categories: Optional[List[str]] = None,
        priorities: Optional[List[str]] = None,
        min_confidence: float = 0.0,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Query digest items with filters."""
        raise NotImplementedError
    
    async def get_digest_stats(self, hours: int = 72) -> Dict[str, Any]:
        """Get statistics for digest items."""
        raise NotImplementedError

    async def get_companies(self) -> List[Dict[str, Any]]:
        """Get tracked companies."""
        raise NotImplementedError
    
    async def get_materials(self) -> List[Dict[str, Any]]:
        """Get materials/processes list."""
        raise NotImplementedError
    
    async def get_industries(self) -> List[Dict[str, Any]]:
        """Get industries list."""
        raise NotImplementedError

    # Deduplication
    async def check_duplicate(self, url: str) -> Optional[str]:
        """
        Check if URL already exists in articles table.
        Returns article_id if duplicate, None otherwise.
        """
        raise NotImplementedError
    
    async def get_recent_articles_for_dedup(self, hours: int = 168, limit: int = 2000) -> List[Dict[str, Any]]:
        """
        Get recent articles for deduplication cache loading.
        Returns list of dicts with id, url, title.
        """
        raise NotImplementedError

    # Freight Rates
    async def store_freight_rates(self, records: List[FreightRateRecord]) -> int:
        """Store freight rate records."""
        raise NotImplementedError
    
    async def get_freight_rates(
        self,
        lane: Optional[str] = None,
        source: Optional[str] = None,
        start_date: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[FreightRateRecord]:
        """Query freight rates."""
        raise NotImplementedError

    # Ingestion Logging
    async def log_ingestion_event(
        self,
        run_id: str,
        event_type: str,
        job_type: str = "manual",
        status: Optional[str] = None,
        metrics: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Log an ingestion lifecycle event."""
        # Optional implementation, explicitly not raising error to be safe
        return False


# =============================================================================
# Local Storage Implementation (SQLite)
# =============================================================================

class LocalDataStorage(DataStorageInterface):
    """
    DEPRECATED: Local SQLite storage - NOT USED IN PRODUCTION.
    
    BigQuery is the ONLY storage backend. This class exists only for
    backwards compatibility and should never be instantiated.
    
    If you see this class being used, it's a bug - check that
    GCP_PROJECT_ID and GCS_BUCKET_NAME are set correctly.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        from pathlib import Path
        
        if db_path:
            self.db_path = Path(db_path)
        else:
            data_dir = Path(os.getenv("DATA_DIR", str(Path(__file__).parent.parent.parent / "data")))
            self.db_path = data_dir / "c1_timeseries.db"
        
        self._initialized = False

    async def get_companies(self) -> List[Dict[str, Any]]:
        """Get tracked companies from local storage (not implemented for SQLite yet)."""
        return []
    
    async def get_materials(self) -> List[Dict[str, Any]]:
        """Get materials from local storage (not implemented for SQLite yet)."""
        return []
    
    async def get_industries(self) -> List[Dict[str, Any]]:
        """Get industries from local storage (not implemented for SQLite yet)."""
        return []
    
    async def initialize(self):
        """Create time-series tables."""
        if self._initialized:
            return
        
        import aiosqlite
        
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        async with aiosqlite.connect(self.db_path) as db:
            # Articles table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS articles (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    url TEXT UNIQUE,
                    published_at TEXT,
                    source_name TEXT,
                    source_type TEXT,
                    summary TEXT,
                    full_text TEXT,
                    category TEXT,
                    topics TEXT,
                    companies_mentioned TEXT,
                    relevance_score REAL,
                    fetched_at TEXT NOT NULL
                )
            """)
            
            # Create indexes
            await db.execute("CREATE INDEX IF NOT EXISTS idx_articles_published ON articles(published_at)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_articles_source ON articles(source_type)")
            
            await db.commit()
        
        self._initialized = True
        logger.info(f"Local time-series database initialized at {self.db_path}")
    
    async def store_articles(self, records: List[ArticleRecord]) -> int:
        """Store articles with upsert."""
        import aiosqlite
        
        if not records:
            return 0
        
        stored = 0
        async with aiosqlite.connect(self.db_path) as db:
            for r in records:
                try:
                    await db.execute("""
                        INSERT OR REPLACE INTO articles
                        (id, title, url, published_at, source_name, source_type,
                         summary, full_text, category, topics, companies_mentioned,
                         relevance_score, fetched_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        r.id, r.title, r.url, r.published_at.isoformat(),
                        r.source_name, r.source_type, r.summary, r.full_text,
                        r.category, json.dumps(r.topics), json.dumps(r.companies_mentioned),
                        r.relevance_score, r.fetched_at.isoformat()
                    ))
                    stored += 1
                except Exception as e:
                    logger.error(f"Error storing article: {e}")
            
            await db.commit()
        
        logger.info(f"Stored {stored} article records")
        return stored
    
    async def get_articles(
        self,
        source_type: Optional[str] = None,
        category: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        search_query: Optional[str] = None,
        limit: int = 50,
    ) -> List[ArticleRecord]:
        """Query articles."""
        import aiosqlite
        
        query = "SELECT * FROM articles WHERE 1=1"
        params = []
        
        if source_type:
            query += " AND source_type = ?"
            params.append(source_type)
        if category:
            query += " AND category = ?"
            params.append(category)
        if start_date:
            query += " AND published_at >= ?"
            params.append(start_date.isoformat())
        if end_date:
            query += " AND published_at <= ?"
            params.append(end_date.isoformat())
        if search_query:
            query += " AND (title LIKE ? OR summary LIKE ?)"
            params.extend([f"%{search_query}%", f"%{search_query}%"])
        
        query += " ORDER BY published_at DESC LIMIT ?"
        params.append(limit)
        
        records = []
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(query, params) as cursor:
                async for row in cursor:
                    records.append(ArticleRecord(
                        id=row["id"],
                        title=row["title"],
                        url=row["url"] or "",
                        published_at=datetime.fromisoformat(row["published_at"]) if row["published_at"] else datetime.utcnow(),
                        source_name=row["source_name"] or "",
                        source_type=row["source_type"] or "",
                        summary=row["summary"],
                        full_text=row["full_text"],
                        category=row["category"],
                        topics=json.loads(row["topics"]) if row["topics"] else [],
                        companies_mentioned=json.loads(row["companies_mentioned"]) if row["companies_mentioned"] else [],
                        relevance_score=row["relevance_score"] or 0.5,
                        fetched_at=datetime.fromisoformat(row["fetched_at"]),
                    ))
        
        return records
    
    # =========================================================================
    # Digest Items Storage (Local SQLite)
    # =========================================================================
    
    async def store_digest_items(self, items: List[Dict[str, Any]]) -> int:
        """Store classified digest items in SQLite."""
        import aiosqlite
        import uuid
        
        if not items:
            return 0
        
        # Ensure digest_items table exists with coverage tracking columns
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS digest_items (
                    id TEXT PRIMARY KEY,
                    article_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    headline TEXT,
                    url TEXT,
                    published_at TEXT,
                    source_name TEXT,
                    source_type TEXT,
                    category TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    digest_summary TEXT,
                    original_summary TEXT,
                    companies TEXT,
                    materials TEXT,
                    topics TEXT,
                    industries TEXT,
                    relevance_score REAL,
                    confidence REAL,
                    coverage_count INTEGER DEFAULT 1,
                    duplicate_sources TEXT,
                    all_urls TEXT,
                    classifier_model TEXT,
                    classified_at TEXT NOT NULL,
                    ingested_at TEXT NOT NULL
                )
            """)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_digest_published ON digest_items(published_at)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_digest_category ON digest_items(category)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_digest_priority ON digest_items(priority)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_digest_coverage ON digest_items(coverage_count)")
            
            # Add new columns if they don't exist (for migration)
            try:
                await db.execute("ALTER TABLE digest_items ADD COLUMN headline TEXT")
            except Exception:
                pass
            try:
                await db.execute("ALTER TABLE digest_items ADD COLUMN coverage_count INTEGER DEFAULT 1")
            except Exception:
                pass  # Column already exists
            try:
                await db.execute("ALTER TABLE digest_items ADD COLUMN duplicate_sources TEXT")
            except Exception:
                pass
            try:
                await db.execute("ALTER TABLE digest_items ADD COLUMN all_urls TEXT")
            except Exception:
                pass
            try:
                await db.execute("ALTER TABLE digest_items ADD COLUMN industries TEXT")
            except Exception:
                pass
            try:
                await db.execute("ALTER TABLE digest_items ADD COLUMN feed_eligible INTEGER DEFAULT 1")
            except Exception:
                pass
            
            now = datetime.utcnow().isoformat()
            stored = 0
            
            for item in items:
                try:
                    await db.execute("""
                        INSERT OR REPLACE INTO digest_items
                        (id, article_id, title, headline, url, published_at, source_name, source_type,
                         category, priority, digest_summary, original_summary, companies,
                         materials, topics, industries, relevance_score, confidence, coverage_count,
                         duplicate_sources, all_urls, classifier_model, classified_at, ingested_at, feed_eligible)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        str(uuid.uuid4()),
                        item.get("article_id", ""),
                        item.get("title", ""),
                        item.get("headline", ""),
                        item.get("url", ""),
                        item.get("published_at"),
                        item.get("source_name", ""),
                        item.get("source_type", ""),
                        item.get("category", "market"),
                        item.get("priority", "medium"),
                        item.get("digest_summary", ""),
                        item.get("original_summary", ""),
                        json.dumps(item.get("companies", [])),
                        json.dumps(item.get("materials", [])),
                        json.dumps(item.get("topics", [])),
                        json.dumps(item.get("industries", [])),
                        item.get("relevance_score", 0.5),
                        item.get("confidence", 0.0),
                        item.get("coverage_count", 1),
                        json.dumps(item.get("duplicate_sources", [])),
                        json.dumps(item.get("all_urls", [])),
                        item.get("classifier_model", ""),
                        item.get("classified_at", now),
                        now,
                        1 if item.get("feed_eligible", True) else 0,
                    ))
                    stored += 1
                except Exception as e:
                    logger.error(f"Error storing digest item: {e}")
            
            await db.commit()
        
        logger.info(f"Stored {stored} digest items in SQLite")
        return stored
    
    async def get_digest_items(
        self,
        hours: int = 72,
        categories: Optional[List[str]] = None,
        priorities: Optional[List[str]] = None,
        min_confidence: float = 0.0,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Query digest items from SQLite."""
        import aiosqlite
        from datetime import timedelta
        
        # Cutoff for minimum published date (3 days back from now)
        three_days_ago = (datetime.utcnow() - timedelta(days=3)).isoformat()
        now_iso = datetime.utcnow().isoformat()
        
        # Filter criteria:
        # 1. published_at must be within last 3 days (fresh content only)
        # 2. published_at must NOT be in the future (reject bad date parsing)
        # 3. published_at must NOT be within 30 minutes of classified_at (indicates defaulted/guessed date)
        # 4. ingested_at must be >= 2025-12-28 (data before this has unreliable published_at dates)
        query = """
            SELECT * FROM digest_items
            WHERE published_at >= ?
            AND published_at <= ?
            AND confidence >= ?
            AND ingested_at >= '2025-12-28T00:00:00'
            AND (
                classified_at IS NULL 
                OR published_at IS NULL
                OR ABS(strftime('%s', classified_at) - strftime('%s', published_at)) > 1800
            )
        """
        params = [three_days_ago, now_iso, min_confidence]
        
        if categories:
            placeholders = ", ".join("?" * len(categories))
            query += f" AND LOWER(category) IN ({placeholders})"
            params.extend([c.lower() for c in categories])
        
        if priorities:
            placeholders = ", ".join("?" * len(priorities))
            query += f" AND LOWER(priority) IN ({placeholders})"
            params.extend([p.lower() for p in priorities])
        
        query += """
            ORDER BY 
                CASE LOWER(priority)
                    WHEN 'critical' THEN 1
                    WHEN 'high' THEN 2
                    WHEN 'medium' THEN 3
                    WHEN 'low' THEN 4
                END,
                published_at DESC
            LIMIT ?
        """
        params.append(limit)
        
        items = []
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(query, params) as cursor:
                async for row in cursor:
                    items.append({
                        "id": row["id"],
                        "article_id": row["article_id"],
                        "title": row["title"],
                        "headline": row["headline"] if "headline" in row.keys() else None,
                        "url": row["url"],
                        "published_at": row["published_at"],
                        "source_name": row["source_name"],
                        "source_type": row["source_type"],
                        "category": row["category"],
                        "priority": row["priority"],
                        "digest_summary": row["digest_summary"],
                        "original_summary": row["original_summary"],
                        "companies": json.loads(row["companies"]) if row["companies"] else [],
                        "materials": json.loads(row["materials"]) if row["materials"] else [],
                        "topics": json.loads(row["topics"]) if row["topics"] else [],
                        "industries": json.loads(row["industries"]) if row["industries"] else [],
                        "relevance_score": row["relevance_score"],
                        "confidence": row["confidence"],
                        "classified_at": row["classified_at"],
                    })
        
        return items
    
    async def get_digest_stats(self, hours: int = 72) -> Dict[str, Any]:
        """Get statistics for digest items."""
        import aiosqlite
        from datetime import timedelta
        
        cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
        
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("""
                SELECT
                    COUNT(*) as total_items,
                    SUM(CASE WHEN priority = 'critical' THEN 1 ELSE 0 END) as critical_count,
                    SUM(CASE WHEN priority = 'high' THEN 1 ELSE 0 END) as high_count,
                    SUM(CASE WHEN priority = 'medium' THEN 1 ELSE 0 END) as medium_count,
                    SUM(CASE WHEN priority = 'low' THEN 1 ELSE 0 END) as low_count,
                    COUNT(DISTINCT category) as category_count
                FROM digest_items
                WHERE published_at >= ?
            """, (cutoff,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return {
                        "total_items": row[0] or 0,
                        "by_priority": {
                            "critical": row[1] or 0,
                            "high": row[2] or 0,
                            "medium": row[3] or 0,
                            "low": row[4] or 0,
                        },
                        "category_count": row[5] or 0,
                    }
        
        return {"total_items": 0, "by_priority": {}, "category_count": 0}


# =============================================================================
# BigQuery Storage Implementation (Production)
# =============================================================================

class BigQueryDataStorage(DataStorageInterface):
    """
    BigQuery storage for production.
    
    Benefits:
    - Serverless, auto-scaling
    - Native time-series analysis
    - Long-term storage optimized
    - Integrates with other GCP services
    """
    
    def __init__(self, config: GCPConfig = None):
        self.config = config or gcp_config
        self._client = None
        self._initialized = False
        
        # Simple in-memory cache for master data (1 hour TTL)
        self._cache = {}
        self._cache_ttl = 3600  # 1 hour
    
    @property
    def client(self):
        """Lazy-load BigQuery client."""
        if self._client is None:
            try:
                from google.cloud import bigquery
                self._client = bigquery.Client(project=self.config.project_id)
            except ImportError:
                raise ImportError("google-cloud-bigquery not installed. Run: pip install google-cloud-bigquery")
        return self._client
    
    async def initialize(self):
        """Create BigQuery dataset and tables."""
        if self._initialized:
            return
        
        from google.cloud import bigquery
        from google.cloud.exceptions import NotFound
        
        # Create dataset if not exists
        dataset_ref = self.client.dataset(self.config.dataset_id)
        try:
            self.client.get_dataset(dataset_ref)
            logger.info(f"BigQuery dataset {self.config.dataset_id} exists")
        except NotFound:
            dataset = bigquery.Dataset(dataset_ref)
            dataset.location = self.config.location
            self.client.create_dataset(dataset)
            logger.info(f"Created BigQuery dataset {self.config.dataset_id}")
        
        # Create tables
        await self._create_articles_table()
        await self._create_digest_items_table()
        await self._create_article_tags_table()
        await self._create_research_reports_table()
        await self._create_deep_research_reports_table()  # Phase 4: Deep research persistence
        await self._create_article_images_table()
        await self._create_briefings_table()
        await self._create_weekly_briefings_table()
        await self._create_adhoc_briefings_table()
        await self._create_freight_rates_table()
        await self._create_pre_briefings_table()
        await self._create_user_logins_table()
        await self._create_podcast_episodes_table()
        await self._create_podcast_quotes_table()
        await self._create_earnings_quotes_table()
        await self._create_sec_filing_nuggets_table()
        await self._create_sec_filings_table()
        await self._create_llm_token_usage_table()
        await self._create_eval_results_table()
        await self._create_user_feedback_table()

        self._initialized = True
        logger.info("BigQuery storage initialized")
    
    async def _create_articles_table(self):
        """Create articles table."""
        from google.cloud import bigquery
        
        table_id = f"{self.config.full_dataset_id}.articles"
        schema = [
            bigquery.SchemaField("id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("title", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("url", "STRING"),
            bigquery.SchemaField("published_at", "TIMESTAMP"),
            bigquery.SchemaField("source_name", "STRING"),
            bigquery.SchemaField("source_type", "STRING"),
            bigquery.SchemaField("summary", "STRING"),
            bigquery.SchemaField("category", "STRING"),
            bigquery.SchemaField("topics", "STRING"),  # JSON array
            bigquery.SchemaField("companies_mentioned", "STRING"),  # JSON array
            bigquery.SchemaField("relevance_score", "FLOAT64"),
            bigquery.SchemaField("fetched_at", "TIMESTAMP", mode="REQUIRED"),
            bigquery.SchemaField("metadata", "STRING"),  # JSON object
        ]
        
        table = bigquery.Table(table_id, schema=schema)
        table.time_partitioning = bigquery.TimePartitioning(
            field="published_at",
            type_=bigquery.TimePartitioningType.MONTH,
        )
        table.clustering_fields = ["source_type", "category"]
        
        try:
            self.client.create_table(table)
            logger.info(f"Created table {table_id}")
        except Exception as e:
            if "Already Exists" in str(e):
                logger.info(f"Table {table_id} already exists")
            else:
                raise
                
    async def get_articles_by_ids(self, article_ids: List[str]) -> List[Dict[str, Any]]:
        """Get articles by their IDs from BigQuery.
        
        IMPORTANT: Returns articles in the SAME ORDER as article_ids.
        This is critical for citation mapping — citation [N] must map to article_ids[N-1].
        Articles not found in BigQuery are represented as placeholder dicts with just the id.
        
        Lookup strategy:
        1. Primary: digest_items table (WHERE article_id IN ...) — this is where
           the pre-briefing pipeline stores article references
        2. Fallback: articles table (WHERE id IN ...) — legacy compatibility
        """
        if not article_ids:
            return []
        
        ids_str = ", ".join([f"'{aid}'" for aid in article_ids])
        articles_by_id = {}
        
        # Step 1: Look up in digest_items by article_id (primary source)
        # Pre-briefing stores digest_items.article_id values as article_ids
        digest_table = f"{self.config.full_dataset_id}.digest_items"
        try:
            query = f"""
                SELECT article_id, title, url, source_name, published_at, 
                       category, priority, digest_summary, original_summary,
                       companies, topics, headline
                FROM `{digest_table}` 
                WHERE article_id IN ({ids_str})
            """
            query_job = self.client.query(query)
            results = query_job.result()
            
            for row in results:
                row_dict = dict(row)
                aid = row_dict.get('article_id', '')
                if aid and aid not in articles_by_id:
                    # Map to standard article dict shape for compatibility
                    articles_by_id[aid] = {
                        'id': aid,
                        'title': row_dict.get('title') or row_dict.get('headline') or 'Unknown',
                        'url': row_dict.get('url', ''),
                        'source_name': row_dict.get('source_name', ''),
                        'published_at': row_dict.get('published_at'),
                        'category': row_dict.get('category', ''),
                        'priority': row_dict.get('priority', ''),
                        'summary': row_dict.get('digest_summary') or row_dict.get('original_summary') or '',
                        'companies': row_dict.get('companies', ''),
                        'topics': row_dict.get('topics', ''),
                        '_source_table': 'digest_items',
                    }
            
            logger.info(f"get_articles_by_ids: Found {len(articles_by_id)}/{len(article_ids)} in digest_items")
        except Exception as e:
            logger.warning(f"get_articles_by_ids: digest_items lookup failed: {e}")
        
        # Step 2: Fallback to articles table for any still missing
        missing_ids = [aid for aid in article_ids if aid not in articles_by_id]
        if missing_ids:
            articles_table = f"{self.config.full_dataset_id}.articles"
            try:
                missing_str = ", ".join([f"'{aid}'" for aid in missing_ids])
                query = f"SELECT * FROM `{articles_table}` WHERE id IN ({missing_str})"
                query_job = self.client.query(query)
                results = query_job.result()
                
                fallback_count = 0
                for row in results:
                    row_dict = dict(row)
                    aid = row_dict.get('id', '')
                    if aid:
                        row_dict['_source_table'] = 'articles'
                        articles_by_id[aid] = row_dict
                        fallback_count += 1
                
                if fallback_count > 0:
                    logger.info(f"get_articles_by_ids: Found {fallback_count} more in articles table (fallback)")
            except Exception as e:
                logger.warning(f"get_articles_by_ids: articles table fallback failed: {e}")
        
        # Return in the SAME ORDER as article_ids (critical for citation mapping)
        ordered_articles = []
        missing_count = 0
        for aid in article_ids:
            if aid in articles_by_id:
                ordered_articles.append(articles_by_id[aid])
            else:
                # Placeholder for missing articles — preserves positional indexing
                missing_count += 1
                ordered_articles.append({
                    'id': aid,
                    'title': 'Article not found',
                    'url': '',
                })
        
        if missing_count > 0:
            logger.warning(f"get_articles_by_ids: {missing_count}/{len(article_ids)} articles not found in ANY table")
        
        return ordered_articles
    
    async def _create_digest_items_table(self):
        """Create digest_items table for classified articles."""
        from google.cloud import bigquery
        
        table_id = f"{self.config.full_dataset_id}.digest_items"
        schema = [
            bigquery.SchemaField("id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("article_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("title", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("headline", "STRING"),
            bigquery.SchemaField("url", "STRING"),
            bigquery.SchemaField("published_at", "TIMESTAMP"),
            bigquery.SchemaField("source_name", "STRING"),
            bigquery.SchemaField("source_type", "STRING"),
            bigquery.SchemaField("category", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("priority", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("digest_summary", "STRING"),
            bigquery.SchemaField("original_summary", "STRING"),
            bigquery.SchemaField("companies", "STRING"),  # JSON array
            bigquery.SchemaField("materials", "STRING"),  # JSON array  
            bigquery.SchemaField("topics", "STRING"),  # JSON array
            bigquery.SchemaField("industries", "STRING"),  # JSON array - aerospace, wind, construction, marine, etc.
            bigquery.SchemaField("relevance_score", "FLOAT64"),
            bigquery.SchemaField("confidence", "FLOAT64"),
            # Coverage/Virality tracking
            bigquery.SchemaField("coverage_count", "INT64"),  # How many sources covered this story
            bigquery.SchemaField("duplicate_sources", "STRING"),  # JSON array of source names
            bigquery.SchemaField("all_urls", "STRING"),  # JSON array of all URLs
            bigquery.SchemaField("classifier_model", "STRING"),
            bigquery.SchemaField("classified_at", "TIMESTAMP", mode="REQUIRED"),
            bigquery.SchemaField("ingested_at", "TIMESTAMP", mode="REQUIRED"),
            bigquery.SchemaField("is_hero", "BOOL"),  # Flagged for hero/breaking section
            # Narrative enrichment fields (added Feb 2026)
            bigquery.SchemaField("event_type", "STRING"),  # acquisition, partnership, expansion, contract, etc.
            bigquery.SchemaField("sentiment", "STRING"),  # positive, negative, neutral
            bigquery.SchemaField("geography", "STRING"),  # JSON array of regions/countries
            bigquery.SchemaField("themes", "STRING"),  # JSON array of narrative themes (reshoring, sustainability, etc.)
            bigquery.SchemaField("narrative_enriched_at", "TIMESTAMP"),  # When narrative enrichment was applied
        ]
        
        table = bigquery.Table(table_id, schema=schema)
        table.time_partitioning = bigquery.TimePartitioning(
            field="published_at",
            type_=bigquery.TimePartitioningType.DAY,
        )
        table.clustering_fields = ["category", "priority"]
        
        try:
            self.client.create_table(table)
            logger.info(f"Created table {table_id}")
        except Exception as e:
            if "Already Exists" in str(e):
                logger.info(f"Table {table_id} already exists")
            else:
                raise
    
    async def _create_article_tags_table(self):
        """Create normalized article_tags table for clean analytics.
        
        This table enables:
        - Trending metrics by tag type (companies, materials, themes, territories)
        - Time-series analysis of tag frequency
        - Cross-tag correlation analysis
        - Efficient aggregation queries (no JSON parsing needed)
        
        Tag types:
        - company: Hexcel, Boeing, Spirit AeroSystems
        - material: PEEK, carbon fiber, epoxy resin  
        - market: aerospace, automotive, wind energy
        - theme: sustainability, reshoring, supply chain risk
        - topic: earnings, M&A, capacity expansion
        - geography: North America, EU, China
        - territory: East (US), Central (US), West (US), South (US), Canada, Non-US
        """
        from google.cloud import bigquery
        
        table_id = f"{self.config.full_dataset_id}.article_tags"
        schema = [
            bigquery.SchemaField("id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("article_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("tag", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("tag_normalized", "STRING"),  # Lowercase, trimmed for dedup
            bigquery.SchemaField("tag_type", "STRING", mode="REQUIRED"),  # company, material, market, theme, topic, geography, territory
            bigquery.SchemaField("confidence", "FLOAT64"),  # Classifier confidence for this tag
            bigquery.SchemaField("source", "STRING"),  # classifier, entity_linker, user (manual)
            bigquery.SchemaField("source_type", "STRING"),  # rss, tavily, sec - for filtering
            bigquery.SchemaField("article_published_at", "TIMESTAMP"),
            bigquery.SchemaField("classified_at", "TIMESTAMP", mode="REQUIRED"),
        ]
        
        table = bigquery.Table(table_id, schema=schema)
        table.time_partitioning = bigquery.TimePartitioning(
            field="classified_at",
            type_=bigquery.TimePartitioningType.DAY,
        )
        # Cluster by tag_type and tag_normalized for fast trending queries
        table.clustering_fields = ["tag_type", "tag_normalized"]
        
        try:
            self.client.create_table(table)
            logger.info(f"Created table {table_id}")
        except Exception as e:
            if "Already Exists" in str(e):
                logger.info(f"Table {table_id} already exists")
            else:
                raise
    
    async def store_article_tags(
        self,
        article_id: str,
        tags: List[dict],  # List of {"tag": str, "tag_type": str, "confidence": float}
        source: str = "classifier",
        source_type: str = "",
        article_published_at: Optional[datetime] = None,
    ) -> int:
        """Store tags for an article in BigQuery.
        
        Args:
            article_id: The article this tag belongs to
            tags: List of tag dicts with keys: tag, tag_type, confidence (optional)
            source: Where the tag came from (classifier, entity_linker, user)
            source_type: Article source type (rss, tavily, sec)
            article_published_at: When the article was published
            
        Returns:
            Number of tags stored
        """
        if not tags:
            return 0
            
        table_id = f"{self.config.full_dataset_id}.article_tags"
        now = datetime.utcnow().isoformat()
        
        rows = []
        for t in tags:
            tag_value = t.get("tag", "").strip()
            if not tag_value:
                continue
            rows.append({
                "id": str(uuid.uuid4()),
                "article_id": article_id,
                "tag": tag_value,
                "tag_normalized": tag_value.lower().strip(),
                "tag_type": t.get("tag_type", "topic"),
                "confidence": t.get("confidence", 0.8),
                "source": source,
                "source_type": source_type,
                "article_published_at": article_published_at.isoformat() if article_published_at else None,
                "classified_at": now,
            })
        
        if not rows:
            return 0
            
        errors = self.client.insert_rows_json(table_id, rows)
        stored = len(rows) - len(errors) if errors else len(rows)
        if errors:
            logger.error(f"BigQuery insert errors for article_tags: {errors[:3]}")
        return stored
    
    async def store_article_tags_batch(
        self,
        articles_tags: List[dict],  # List of {"article_id": str, "tags": [...], "source_type": str, ...}
    ) -> int:
        """Store tags for multiple articles in batch.
        
        Args:
            articles_tags: List of dicts with article_id, tags, source_type, article_published_at
            
        Returns:
            Total number of tags stored
        """
        if not articles_tags:
            return 0
            
        table_id = f"{self.config.full_dataset_id}.article_tags"
        now = datetime.utcnow().isoformat()
        
        rows = []
        for article in articles_tags:
            article_id = article.get("article_id", "")
            source_type = article.get("source_type", "")
            pub_at = article.get("article_published_at")
            pub_at_str = pub_at.isoformat() if isinstance(pub_at, datetime) else pub_at
            
            for t in article.get("tags", []):
                tag_value = t.get("tag", "").strip()
                if not tag_value:
                    continue
                rows.append({
                    "id": str(uuid.uuid4()),
                    "article_id": article_id,
                    "tag": tag_value,
                    "tag_normalized": tag_value.lower().strip(),
                    "tag_type": t.get("tag_type", "topic"),
                    "confidence": t.get("confidence", 0.8),
                    "source": t.get("source", "classifier"),
                    "source_type": source_type,
                    "article_published_at": pub_at_str,
                    "classified_at": now,
                })
        
        if not rows:
            return 0
            
        errors = self.client.insert_rows_json(table_id, rows)
        stored = len(rows) - len(errors) if errors else len(rows)
        if errors:
            logger.error(f"BigQuery batch insert errors for article_tags: {errors[:3]}")
        logger.info(f"Stored {stored}/{len(rows)} article tags in BigQuery")
        return stored
    
    async def get_trending_tags(
        self,
        tag_type: Optional[str] = None,  # Filter by type (company, material, etc.)
        days: int = 7,
        source_type: Optional[str] = None,
        limit: int = 20,
    ) -> List[dict]:
        """Get trending tags for dashboard metrics.
        
        Returns tags ordered by frequency over the time period.
        
        Args:
            tag_type: Filter to specific tag type (company, material, market, theme, topic, geography, territory)
            days: Number of days to look back
            source_type: Filter by article source (rss, tavily, sec)
            limit: Max results to return
        """
        query = f"""
            SELECT 
                tag,
                tag_type,
                COUNT(*) as count,
                COUNT(DISTINCT article_id) as article_count,
                AVG(confidence) as avg_confidence
            FROM `{self.config.full_dataset_id}.article_tags`
            WHERE classified_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {days} DAY)
        """
        if tag_type:
            query += f" AND tag_type = '{tag_type}'"
        if source_type:
            query += f" AND source_type = '{source_type}'"
        query += f"""
            GROUP BY tag, tag_type
            ORDER BY count DESC
            LIMIT {limit}
        """
        
        results = []
        for row in self.client.query(query):
            results.append({
                "tag": row.tag,
                "tag_type": row.tag_type,
                "count": row.count,
                "article_count": row.article_count,
                "avg_confidence": row.avg_confidence,
            })
        return results
    
    async def get_tag_time_series(
        self,
        tag: str,
        days: int = 30,
        granularity: str = "day",  # day, week
    ) -> List[dict]:
        """Get time series data for a specific tag.
        
        Useful for charting tag frequency over time.
        """
        date_trunc = "DATE" if granularity == "day" else "DATE_TRUNC(classified_at, WEEK)"
        
        query = f"""
            SELECT 
                {date_trunc}(classified_at) as period,
                COUNT(*) as count
            FROM `{self.config.full_dataset_id}.article_tags`
            WHERE tag_normalized = '{tag.lower().strip()}'
              AND classified_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {days} DAY)
            GROUP BY period
            ORDER BY period ASC
        """
        
        results = []
        for row in self.client.query(query):
            results.append({
                "period": row.period.isoformat() if row.period else None,
                "count": row.count,
            })
        return results
    
    async def get_tag_co_occurrences(
        self,
        tag: str,
        tag_type: Optional[str] = None,
        days: int = 7,
        limit: int = 10,
    ) -> List[dict]:
        """Get tags that frequently appear with the given tag.
        
        Useful for discovering related entities/themes.
        """
        query = f"""
            SELECT 
                t2.tag as related_tag,
                t2.tag_type as related_tag_type,
                COUNT(*) as co_occurrence_count
            FROM `{self.config.full_dataset_id}.article_tags` t1
            JOIN `{self.config.full_dataset_id}.article_tags` t2
              ON t1.article_id = t2.article_id
            WHERE t1.tag_normalized = '{tag.lower().strip()}'
              AND t2.tag_normalized != '{tag.lower().strip()}'
              AND t1.classified_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {days} DAY)
        """
        if tag_type:
            query += f" AND t2.tag_type = '{tag_type}'"
        query += f"""
            GROUP BY t2.tag, t2.tag_type
            ORDER BY co_occurrence_count DESC
            LIMIT {limit}
        """
        
        results = []
        for row in self.client.query(query):
            results.append({
                "related_tag": row.related_tag,
                "related_tag_type": row.related_tag_type,
                "co_occurrence_count": row.co_occurrence_count,
            })
        return results
    
    async def get_tag_summary(
        self,
        days: int = 7,
    ) -> dict:
        """Get summary stats for tags over a time period.
        
        Returns counts by tag_type, total unique tags, etc.
        """
        query = f"""
            SELECT 
                tag_type,
                COUNT(*) as tag_count,
                COUNT(DISTINCT tag_normalized) as unique_tags,
                COUNT(DISTINCT article_id) as article_count
            FROM `{self.config.full_dataset_id}.article_tags`
            WHERE classified_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {days} DAY)
            GROUP BY tag_type
            ORDER BY tag_count DESC
        """
        
        by_type = {}
        total_tags = 0
        total_unique = 0
        total_articles = set()
        
        for row in self.client.query(query):
            by_type[row.tag_type] = {
                "tag_count": row.tag_count,
                "unique_tags": row.unique_tags,
                "article_count": row.article_count,
            }
            total_tags += row.tag_count
            total_unique += row.unique_tags
        
        return {
            "total_tags": total_tags,
            "total_unique_tags": total_unique,
            "by_type": by_type,
            "period_days": days,
        }

    async def _create_research_reports_table(self):
        """Create research_reports table for storing agent-generated reports."""
        from google.cloud import bigquery
        
        table_id = f"{self.config.full_dataset_id}.research_reports"
        schema = [
            bigquery.SchemaField("id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("query", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("title", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("content", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("agent", "STRING"),  # Which agent generated (market_scout, etc.)
            bigquery.SchemaField("sources", "STRING"),  # JSON array of source URLs/titles
            bigquery.SchemaField("companies_mentioned", "STRING"),  # JSON array
            bigquery.SchemaField("materials_mentioned", "STRING"),  # JSON array
            bigquery.SchemaField("user_id", "STRING"),  # For multi-user support later
            bigquery.SchemaField("created_at", "TIMESTAMP", mode="REQUIRED"),
        ]
        
        table = bigquery.Table(table_id, schema=schema)
        table.time_partitioning = bigquery.TimePartitioning(
            field="created_at",
            type_=bigquery.TimePartitioningType.MONTH,
        )
        table.clustering_fields = ["agent"]
        
        try:
            self.client.create_table(table)
            logger.info(f"Created table {table_id}")
        except Exception as e:
            if "Already Exists" in str(e):
                logger.info(f"Table {table_id} already exists")
            else:
                raise

    async def _create_deep_research_reports_table(self):
        """Create deep_research_reports table for Phase 4 persistence.
        
        This table stores complete Deep Research reports for:
        - Persistent storage beyond in-memory cache (1-hour TTL)
        - User report history and retrieval
        - Memory/context integration (avoid redundant research)
        - Analytics on research patterns and tool usage
        
        Schema supports:
        - Full report serialization (JSON blob for flexibility)
        - Semantic search via query embedding
        - Entity extraction for related report discovery
        - Validation metadata for quality tracking
        """
        from google.cloud import bigquery
        
        table_id = f"{self.config.full_dataset_id}.deep_research_reports"
        schema = [
            # Identity
            bigquery.SchemaField("id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("query_hash", "STRING", mode="REQUIRED"),  # For dedup/cache lookup
            
            # User query
            bigquery.SchemaField("query", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("query_embedding", "FLOAT64", mode="REPEATED"),  # For semantic search
            
            # Report content (JSON blobs for flexibility)
            bigquery.SchemaField("research_brief", "STRING"),  # JSON: groomer output
            bigquery.SchemaField("financial_output", "STRING"),  # JSON: financial agent findings
            bigquery.SchemaField("industry_output", "STRING"),  # JSON: industry agent findings
            bigquery.SchemaField("final_report", "STRING"),  # JSON: synthesized report
            bigquery.SchemaField("category_output", "STRING"),  # JSON: sales intelligence
            bigquery.SchemaField("validator_output", "STRING"),  # JSON: validation results
            
            # Extracted entities (for search/memory)
            bigquery.SchemaField("companies", "STRING"),  # JSON array
            bigquery.SchemaField("industries", "STRING"),  # JSON array
            bigquery.SchemaField("topics", "STRING"),  # JSON array
            bigquery.SchemaField("products", "STRING"),  # JSON array
            
            # Report metadata
            bigquery.SchemaField("title", "STRING"),  # From executive summary headline
            bigquery.SchemaField("executive_summary", "STRING"),  # Key points text
            bigquery.SchemaField("data_completeness", "STRING"),  # complete, partial, limited
            bigquery.SchemaField("overall_confidence", "STRING"),  # high, medium, low
            bigquery.SchemaField("validation_passed", "BOOL"),
            bigquery.SchemaField("citation_count", "INT64"),
            bigquery.SchemaField("citation_issues_count", "INT64"),
            
            # Performance metrics
            bigquery.SchemaField("research_time_seconds", "FLOAT64"),
            bigquery.SchemaField("tools_used", "STRING"),  # JSON array
            bigquery.SchemaField("sources_count", "INT64"),
            
            # User/session context
            bigquery.SchemaField("user_id", "STRING"),  # For multi-user support
            bigquery.SchemaField("session_id", "STRING"),
            
            # Timestamps
            bigquery.SchemaField("created_at", "TIMESTAMP", mode="REQUIRED"),
            bigquery.SchemaField("expires_at", "TIMESTAMP"),  # Optional expiry for cleanup
        ]
        
        table = bigquery.Table(table_id, schema=schema)
        table.time_partitioning = bigquery.TimePartitioning(
            field="created_at",
            type_=bigquery.TimePartitioningType.MONTH,
        )
        table.clustering_fields = ["query_hash", "user_id"]
        
        try:
            self.client.create_table(table)
            logger.info(f"Created table {table_id}")
        except Exception as e:
            if "Already Exists" in str(e):
                logger.info(f"Table {table_id} already exists")
            else:
                raise

    async def _create_article_images_table(self):
        """Create article_images table for storing extracted charts/visualizations.
        
        This table stores images extracted from articles with AI classification:
        - Chart/graph type identification
        - OCR extracted text and data points
        - Topic/company/industry tagging
        - Quality and relevance scores
        
        Use cases:
        - Executive briefings with embedded visuals
        - Research tab chart displays
        - Visual trend tracking
        """
        from google.cloud import bigquery
        
        table_id = f"{self.config.full_dataset_id}.article_images"
        schema = [
            # Identity
            bigquery.SchemaField("id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("image_hash", "STRING"),  # For deduplication
            
            # Source reference
            bigquery.SchemaField("article_id", "STRING"),
            bigquery.SchemaField("article_title", "STRING"),
            bigquery.SchemaField("article_url", "STRING"),
            
            # Image data
            bigquery.SchemaField("url", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("source_domain", "STRING"),
            
            # AI Classification
            bigquery.SchemaField("image_type", "STRING"),  # chart, graph, infographic, photo, diagram, table
            bigquery.SchemaField("chart_type", "STRING"),  # line, bar, pie, area, scatter, candlestick, etc.
            
            # AI-generated content
            bigquery.SchemaField("description", "STRING"),  # Detailed description
            bigquery.SchemaField("alt_text", "STRING"),  # Short accessibility text
            
            # OCR extracted content
            bigquery.SchemaField("extracted_text", "STRING"),
            bigquery.SchemaField("extracted_data_points", "STRING"),  # JSON array of {label, value, unit}
            
            # Classification/tagging
            bigquery.SchemaField("topics", "STRING"),  # JSON array: revenue, market_share, forecast, etc.
            bigquery.SchemaField("companies", "STRING"),  # JSON array
            bigquery.SchemaField("industries", "STRING"),  # JSON array
            bigquery.SchemaField("time_period", "STRING"),  # e.g., "Q3 2024", "2020-2025"
            
            # Quality/relevance
            bigquery.SchemaField("relevance_score", "FLOAT64"),
            bigquery.SchemaField("quality_score", "FLOAT64"),
            
            # Metadata
            bigquery.SchemaField("width", "INT64"),
            bigquery.SchemaField("height", "INT64"),
            bigquery.SchemaField("format", "STRING"),  # png, jpg, svg, etc.
            
            # Timestamps
            bigquery.SchemaField("extracted_at", "TIMESTAMP", mode="REQUIRED"),
        ]
        
        table = bigquery.Table(table_id, schema=schema)
        table.time_partitioning = bigquery.TimePartitioning(
            field="extracted_at",
            type_=bigquery.TimePartitioningType.MONTH,
        )
        table.clustering_fields = ["image_type", "chart_type"]
        
        try:
            self.client.create_table(table)
            logger.info(f"Created table {table_id}")
        except Exception as e:
            if "Already Exists" in str(e):
                logger.info(f"Table {table_id} already exists")
            else:
                raise
    
    async def _create_briefings_table(self):
        """Create briefings table for executive Need-to-Know summaries.
        
        This table stores 30-day rolling briefings generated twice daily (8 AM, 8 PM CST).
        Each briefing captures:
        - Executive summary with citations
        - Full source article metadata for transparency
        - Entity extraction for quarterly trending analysis
        - Scheduler metadata for tracking refresh cadence
        
        Use cases:
        - Pulse tab Need-to-Know display with source citations
        - Quarterly trending reports (what topics/companies surfaced most)
        - Historical briefing comparison
        - Citation verification and source auditing
        """
        from google.cloud import bigquery
        
        table_id = f"{self.config.full_dataset_id}.briefings"
        schema = [
            # Identity
            bigquery.SchemaField("id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("category", "STRING", mode="REQUIRED"),  # MARKET, COMPETITOR, PRODUCT, REGULATORY, SUPPLY_CHAIN
            
            # Core briefing content
            bigquery.SchemaField("headline", "STRING"),
            bigquery.SchemaField("summary", "STRING"),
            bigquery.SchemaField("key_insights", "STRING"),  # JSON array of insight strings
            
            # Trend/attention signals
            bigquery.SchemaField("trend_signal", "STRING"),  # emerging, accelerating, stable, declining, mixed
            bigquery.SchemaField("attention_flag", "STRING"),  # high, medium, low
            bigquery.SchemaField("attention_reason", "STRING"),
            
            # Time window
            bigquery.SchemaField("period_start", "TIMESTAMP"),
            bigquery.SchemaField("period_end", "TIMESTAMP"),
            bigquery.SchemaField("generated_at", "TIMESTAMP", mode="REQUIRED"),
            
            # Model metadata
            bigquery.SchemaField("model", "STRING"),
            
            # === SOURCE TRACKING (for citations) ===
            bigquery.SchemaField("article_count", "INT64"),  # Total articles analyzed
            bigquery.SchemaField("article_ids", "STRING"),  # JSON array of article IDs
            # Full source details for citation display
            bigquery.SchemaField("source_articles", "STRING"),  # JSON array: [{id, title, url, source_name, published_at, summary}]
            # Source breakdown for analytics
            bigquery.SchemaField("sources_breakdown", "STRING"),  # JSON object: {source_name: count}
            
            # === ENTITY EXTRACTION (for quarterly trending) ===
            bigquery.SchemaField("companies_mentioned", "STRING"),  # JSON array with frequency: [{name, count, context}]
            bigquery.SchemaField("materials_mentioned", "STRING"),  # JSON array: [{name, count}]
            bigquery.SchemaField("topics_extracted", "STRING"),  # JSON array: themes/topics surfaced
            bigquery.SchemaField("key_figures", "STRING"),  # JSON array: [{figure, context, source}] - numbers, percentages, dollar amounts
            
            # === SCHEDULER METADATA ===
            bigquery.SchemaField("scheduler_run", "STRING"),  # "morning" (8 AM) or "evening" (8 PM)
            bigquery.SchemaField("quarter", "STRING"),  # "2025-Q1", "2025-Q4" for quarterly grouping
            bigquery.SchemaField("week_of_year", "INT64"),  # 1-52 for weekly trending
            bigquery.SchemaField("day_of_week", "STRING"),  # Monday, Tuesday, etc.
            
            # === QUALITY METRICS ===
            bigquery.SchemaField("avg_article_relevance", "FLOAT64"),  # Average relevance score of source articles
            bigquery.SchemaField("high_priority_count", "INT64"),  # Count of CRITICAL/HIGH priority articles used
        ]
        
        table = bigquery.Table(table_id, schema=schema)
        table.time_partitioning = bigquery.TimePartitioning(
            field="generated_at",
            type_=bigquery.TimePartitioningType.MONTH,
        )
        # Cluster by category and quarter for efficient trending queries
        table.clustering_fields = ["category", "quarter"]
        
        try:
            self.client.create_table(table)
            logger.info(f"Created table {table_id}")
        except Exception as e:
            if "Already Exists" in str(e):
                logger.info(f"Table {table_id} already exists")
            else:
                raise
    
    async def save_briefing(self, briefing_data: Dict[str, Any]) -> bool:
        """Save a briefing to BigQuery with full source tracking.
        
        Args:
            briefing_data: Dict containing:
                - id, category, headline, summary, key_insights
                - trend_signal, attention_flag, attention_reason
                - period_start, period_end, generated_at, model
                - article_ids, source_articles (full article details)
                - companies_mentioned, materials_mentioned, topics_extracted
                - key_figures, sources_breakdown
                - scheduler_run (morning/evening)
                
        Returns:
            True if successful, False otherwise
        """
        import json
        from datetime import datetime
        
        table_id = f"{self.config.full_dataset_id}.briefings"
        generated_at = briefing_data.get('generated_at', datetime.utcnow())
        if isinstance(generated_at, str):
            generated_at = datetime.fromisoformat(generated_at.replace('Z', '+00:00'))
        
        # Calculate quarter and week
        quarter = f"{generated_at.year}-Q{(generated_at.month - 1) // 3 + 1}"
        week_of_year = generated_at.isocalendar()[1]
        day_of_week = generated_at.strftime("%A")
        
        # Determine scheduler run based on hour (8 AM or 8 PM CST = 14:00 or 02:00 UTC)
        hour = generated_at.hour
        scheduler_run = briefing_data.get('scheduler_run', 'morning' if 6 <= hour < 18 else 'evening')
        
        def to_timestamp(val):
            if val is None:
                return None
            if isinstance(val, datetime):
                return val.isoformat()
            return val
        
        row = {
            "id": briefing_data['id'],
            "category": briefing_data['category'],
            "headline": briefing_data.get('headline', ''),
            "summary": briefing_data.get('summary', ''),
            "key_insights": json.dumps(briefing_data.get('key_insights', [])),
            "trend_signal": briefing_data.get('trend_signal', 'stable'),
            "attention_flag": briefing_data.get('attention_flag', 'low'),
            "attention_reason": briefing_data.get('attention_reason'),
            "period_start": to_timestamp(briefing_data.get('period_start')),
            "period_end": to_timestamp(briefing_data.get('period_end')),
            "generated_at": to_timestamp(generated_at),
            "model": briefing_data.get('model', ''),
            # Source tracking
            "article_count": briefing_data.get('article_count', len(briefing_data.get('article_ids', []))),
            "article_ids": json.dumps(briefing_data.get('article_ids', [])),
            "source_articles": json.dumps(briefing_data.get('source_articles', [])),
            "sources_breakdown": json.dumps(briefing_data.get('sources_breakdown', {})),
            # Entity extraction
            "companies_mentioned": json.dumps(briefing_data.get('companies_mentioned', [])),
            "materials_mentioned": json.dumps(briefing_data.get('materials_mentioned', [])),
            "topics_extracted": json.dumps(briefing_data.get('topics_extracted', [])),
            "key_figures": json.dumps(briefing_data.get('key_figures', [])),
            # Scheduler metadata
            "scheduler_run": scheduler_run,
            "quarter": quarter,
            "week_of_year": week_of_year,
            "day_of_week": day_of_week,
            # Quality metrics
            "avg_article_relevance": briefing_data.get('avg_article_relevance', 0.0),
            "high_priority_count": briefing_data.get('high_priority_count', 0),
        }
        
        try:
            errors = self.client.insert_rows_json(table_id, [row])
            if errors:
                logger.error(f"BigQuery insert error for briefing: {errors}")
                return False
            logger.info(f"Stored briefing {briefing_data['id']} for category {briefing_data['category']} in BigQuery")
            return True
        except Exception as e:
            logger.error(f"Error storing briefing in BigQuery: {e}")
            return False
    
    async def get_latest_briefings(self, limit_per_category: int = 1) -> List[Dict[str, Any]]:
        """Get the latest briefing for each category from BigQuery.
        
        Args:
            limit_per_category: Number of briefings per category (default 1 = latest only)
            
        Returns:
            List of briefing dicts with parsed JSON fields
        """
        import json
        
        table_id = f"{self.config.full_dataset_id}.briefings"
        
        # Use ROW_NUMBER to get latest N per category
        query = f"""
            WITH ranked AS (
                SELECT *,
                    ROW_NUMBER() OVER (PARTITION BY category ORDER BY generated_at DESC) as rn
                FROM `{table_id}`
            )
            SELECT * EXCEPT(rn)
            FROM ranked
            WHERE rn <= {limit_per_category}
            ORDER BY category, generated_at DESC
        """
        
        try:
            query_job = self.client.query(query)
            results = query_job.result()
            
            briefings = []
            for row in results:
                briefing = dict(row)
                # Parse JSON fields
                for json_field in ['key_insights', 'article_ids', 'source_articles', 'sources_breakdown',
                                   'companies_mentioned', 'materials_mentioned', 'topics_extracted', 'key_figures']:
                    if briefing.get(json_field):
                        try:
                            briefing[json_field] = json.loads(briefing[json_field])
                        except (json.JSONDecodeError, TypeError):
                            briefing[json_field] = [] if json_field != 'sources_breakdown' else {}
                briefings.append(briefing)
            
            return briefings
        except Exception as e:
            logger.error(f"Error fetching briefings from BigQuery: {e}")
            return []
    
    async def get_briefings_for_quarter(self, quarter: str, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all briefings for a specific quarter for trending analysis.
        
        Args:
            quarter: Quarter string like "2025-Q1"
            category: Optional category filter
            
        Returns:
            List of briefing dicts for the quarter
        """
        import json
        from google.cloud import bigquery
        
        table_id = f"{self.config.full_dataset_id}.briefings"
        
        query = f"""
            SELECT *
            FROM `{table_id}`
            WHERE quarter = @quarter
            {"AND category = @category" if category else ""}
            ORDER BY generated_at DESC
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("quarter", "STRING", quarter),
            ] + ([bigquery.ScalarQueryParameter("category", "STRING", category)] if category else [])
        )
        
        try:
            query_job = self.client.query(query, job_config=job_config)
            results = query_job.result()
            
            briefings = []
            for row in results:
                briefing = dict(row)
                # Parse JSON fields
                for json_field in ['key_insights', 'article_ids', 'source_articles', 'sources_breakdown',
                                   'companies_mentioned', 'materials_mentioned', 'topics_extracted', 'key_figures']:
                    if briefing.get(json_field):
                        try:
                            briefing[json_field] = json.loads(briefing[json_field])
                        except (json.JSONDecodeError, TypeError):
                            briefing[json_field] = [] if json_field != 'sources_breakdown' else {}
                briefings.append(briefing)
            
            return briefings
        except Exception as e:
            logger.error(f"Error fetching quarterly briefings from BigQuery: {e}")
            return []
    
    async def get_trending_from_briefings(
        self,
        quarter: str,
        entity_type: str = "companies"  # companies, materials, topics
    ) -> List[Dict[str, Any]]:
        """Aggregate trending entities from briefings for quarterly analysis.
        
        Args:
            quarter: Quarter string like "2025-Q1"
            entity_type: Type of entity to aggregate (companies, materials, topics)
            
        Returns:
            List of {name, total_mentions, categories_appeared, weeks_appeared}
        """
        # Get all briefings for the quarter
        briefings = await self.get_briefings_for_quarter(quarter)
        
        field_map = {
            "companies": "companies_mentioned",
            "materials": "materials_mentioned", 
            "topics": "topics_extracted"
        }
        field = field_map.get(entity_type, "companies_mentioned")
        
        # Aggregate mentions
        from collections import defaultdict
        aggregated = defaultdict(lambda: {
            "total_mentions": 0,
            "categories": set(),
            "weeks": set(),
            "contexts": []
        })
        
        for b in briefings:
            entities = b.get(field, [])
            category = b.get("category", "")
            week = b.get("week_of_year", 0)
            
            for entity in entities:
                # Handle both string and dict formats
                if isinstance(entity, dict):
                    name = entity.get("name", "")
                    count = entity.get("count", 1)
                    context = entity.get("context", "")
                else:
                    name = str(entity)
                    count = 1
                    context = ""
                
                if name:
                    aggregated[name]["total_mentions"] += count
                    aggregated[name]["categories"].add(category)
                    aggregated[name]["weeks"].add(week)
                    if context:
                        aggregated[name]["contexts"].append(context)
        
        # Convert to list and sort by mentions
        result = [
            {
                "name": name,
                "total_mentions": data["total_mentions"],
                "categories_appeared": list(data["categories"]),
                "weeks_appeared": len(data["weeks"]),
                "sample_contexts": data["contexts"][:3]  # Top 3 contexts
            }
            for name, data in aggregated.items()
        ]
        
        return sorted(result, key=lambda x: x["total_mentions"], reverse=True)

    # =========================================================================
    # Weekly Executive Briefing Methods (New Dynamic Format)
    # =========================================================================
    
    async def _create_weekly_briefings_table(self):
        """Create weekly_briefings table for the new dynamic section format."""
        from google.cloud import bigquery
        
        table_id = f"{self.config.full_dataset_id}.weekly_briefings"
        schema = [
            bigquery.SchemaField("id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("briefing_type", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("briefing_title", "STRING"),
            bigquery.SchemaField("bluf", "STRING"),  # Bottom Line Up Front - 1 sentence summary
            bigquery.SchemaField("sections", "STRING"),  # JSON array of sections
            bigquery.SchemaField("all_companies_mentioned", "STRING"),  # JSON array with logos
            bigquery.SchemaField("key_topics_this_week", "STRING"),  # JSON array
            bigquery.SchemaField("overall_trend", "STRING"),
            bigquery.SchemaField("period_start", "TIMESTAMP"),
            bigquery.SchemaField("period_end", "TIMESTAMP"),
            bigquery.SchemaField("generated_at", "TIMESTAMP", mode="REQUIRED"),
            bigquery.SchemaField("model", "STRING"),
            bigquery.SchemaField("article_count", "INT64"),
            bigquery.SchemaField("article_ids", "STRING"),  # JSON array
            bigquery.SchemaField("quarter", "STRING"),
            bigquery.SchemaField("week_of_year", "INT64"),
            # Podcast metadata (added Session 94)
            bigquery.SchemaField("podcast_url", "STRING"),
            bigquery.SchemaField("podcast_duration_seconds", "FLOAT64"),
            bigquery.SchemaField("podcast_generated_at", "TIMESTAMP"),
        ]
        
        table = bigquery.Table(table_id, schema=schema)
        table.time_partitioning = bigquery.TimePartitioning(
            field="generated_at",
            type_=bigquery.TimePartitioningType.MONTH,
        )
        table.clustering_fields = ["quarter", "week_of_year"]
        
        try:
            self.client.create_table(table)
            logger.info(f"Created table {table_id}")
        except Exception as e:
            if "Already Exists" in str(e):
                logger.info(f"Table {table_id} already exists")
                # Ensure podcast columns exist (schema migration for existing tables)
                try:
                    existing_table = self.client.get_table(table_id)
                    existing_field_names = {f.name for f in existing_table.schema}
                    new_fields = []
                    for field in schema:
                        if field.name not in existing_field_names:
                            new_fields.append(field)
                    if new_fields:
                        updated_schema = list(existing_table.schema) + new_fields
                        existing_table.schema = updated_schema
                        self.client.update_table(existing_table, ["schema"])
                        logger.info(f"Added {len(new_fields)} new columns to {table_id}: {[f.name for f in new_fields]}")
                except Exception as migrate_err:
                    logger.warning(f"Schema migration for {table_id} failed (non-fatal): {migrate_err}")
            else:
                raise
    
    async def save_weekly_briefing(self, briefing_data: Dict[str, Any]) -> bool:
        """Save a weekly executive briefing to BigQuery.
        
        Args:
            briefing_data: Dict containing the new dynamic section format
            
        Returns:
            True if successful, False otherwise
        """
        import json
        from datetime import datetime
        
        table_id = f"{self.config.full_dataset_id}.weekly_briefings"
        generated_at = briefing_data.get('generated_at', datetime.utcnow())
        if isinstance(generated_at, str):
            generated_at = datetime.fromisoformat(generated_at.replace('Z', '+00:00'))
        
        quarter = f"{generated_at.year}-Q{(generated_at.month - 1) // 3 + 1}"
        week_of_year = generated_at.isocalendar()[1]
        
        def to_timestamp(val):
            if val is None:
                return None
            if isinstance(val, datetime):
                return val.isoformat()
            return val
        
        row = {
            "id": briefing_data['id'],
            "briefing_type": briefing_data.get('briefing_type', 'weekly_executive'),
            "briefing_title": briefing_data.get('briefing_title', ''),
            "bluf": briefing_data.get('bluf', ''),
            "sections": json.dumps(briefing_data.get('sections', [])),
            "all_companies_mentioned": json.dumps(briefing_data.get('all_companies_mentioned', [])),
            "key_topics_this_week": json.dumps(briefing_data.get('key_topics_this_week', [])),
            "overall_trend": briefing_data.get('overall_trend', ''),
            "period_start": to_timestamp(briefing_data.get('period_start')),
            "period_end": to_timestamp(briefing_data.get('period_end')),
            "generated_at": to_timestamp(generated_at),
            "model": briefing_data.get('model', ''),
            "article_count": briefing_data.get('article_count', 0),
            "article_ids": json.dumps(briefing_data.get('article_ids', [])),
            "quarter": quarter,
            "week_of_year": week_of_year,
            # Podcast metadata
            "podcast_url": briefing_data.get('podcast_url'),
            "podcast_duration_seconds": briefing_data.get('podcast_duration_seconds'),
            "podcast_generated_at": to_timestamp(briefing_data.get('podcast_generated_at')),
        }
        
        try:
            logger.info(f"[BQ_SAVE] Inserting weekly briefing {row['id']} into {table_id}")
            logger.debug(f"[BQ_SAVE] Row keys: {list(row.keys())}")
            logger.debug(f"[BQ_SAVE] Sections length: {len(row.get('sections', ''))}")
            
            errors = self.client.insert_rows_json(table_id, [row])
            if errors:
                logger.error(f"[BQ_SAVE] FAILED - BigQuery insert errors for {row['id']}: {errors}")
                # Log the problematic row structure for debugging
                for key, val in row.items():
                    val_type = type(val).__name__
                    val_preview = str(val)[:100] if val else 'None'
                    logger.error(f"[BQ_SAVE]   {key}: {val_type} = {val_preview}")
                return False
            logger.info(f"[BQ_SAVE] SUCCESS - Stored weekly briefing {briefing_data['id']} in BigQuery")
            return True
        except Exception as e:
            logger.error(f"[BQ_SAVE] EXCEPTION storing weekly briefing: {e}", exc_info=True)
            return False
    
    async def get_latest_weekly_briefing(self) -> Optional[Dict[str, Any]]:
        """Get the most recent weekly executive briefing.
        
        Uses deduplication to prefer rows with podcast_url when duplicates exist.
        """
        import json
        
        table_id = f"{self.config.full_dataset_id}.weekly_briefings"
        
        # Deduplicate by id, preferring rows with podcast_url
        query = f"""
            WITH deduped AS (
                SELECT *,
                    ROW_NUMBER() OVER (
                        PARTITION BY id 
                        ORDER BY CASE WHEN podcast_url IS NOT NULL THEN 0 ELSE 1 END,
                                 generated_at DESC
                    ) as rn
                FROM `{table_id}`
            )
            SELECT * EXCEPT(rn)
            FROM deduped
            WHERE rn = 1
            ORDER BY generated_at DESC
            LIMIT 1
        """
        
        try:
            query_job = self.client.query(query)
            results = list(query_job.result())
            
            if not results:
                return None
            
            row = results[0]
            briefing = dict(row)
            
            # Ensure bluf is a string (not None)
            briefing['bluf'] = briefing.get('bluf') or ''
            
            # Parse JSON fields
            for json_field in ['sections', 'all_companies_mentioned', 'key_topics_this_week', 'article_ids']:
                if briefing.get(json_field):
                    try:
                        briefing[json_field] = json.loads(briefing[json_field])
                    except (json.JSONDecodeError, TypeError):
                        briefing[json_field] = []
            
            return briefing
        except Exception as e:
            logger.error(f"Error fetching weekly briefing from BigQuery: {e}")
            return None
    
    async def get_weekly_briefing_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get historical weekly briefings.
        
        Uses deduplication to prefer rows with podcast_url when duplicates exist.
        """
        import json
        
        table_id = f"{self.config.full_dataset_id}.weekly_briefings"
        
        # Deduplicate by id, preferring rows with podcast_url
        query = f"""
            WITH deduped AS (
                SELECT *,
                    ROW_NUMBER() OVER (
                        PARTITION BY id 
                        ORDER BY CASE WHEN podcast_url IS NOT NULL THEN 0 ELSE 1 END,
                                 generated_at DESC
                    ) as rn
                FROM `{table_id}`
            )
            SELECT * EXCEPT(rn)
            FROM deduped
            WHERE rn = 1
            ORDER BY generated_at DESC
            LIMIT {limit}
        """
        
        try:
            query_job = self.client.query(query)
            results = query_job.result()
            
            briefings = []
            for row in results:
                briefing = dict(row)
                # Ensure bluf is a string (not None)
                briefing['bluf'] = briefing.get('bluf') or ''
                for json_field in ['sections', 'all_companies_mentioned', 'key_topics_this_week', 'article_ids']:
                    if briefing.get(json_field):
                        try:
                            briefing[json_field] = json.loads(briefing[json_field])
                        except (json.JSONDecodeError, TypeError):
                            briefing[json_field] = []
                briefings.append(briefing)
            
            return briefings
        except Exception as e:
            logger.error(f"Error fetching weekly briefing history from BigQuery: {e}")
            return []

    # =========================================================================
    # Pre-Briefing Operations (Agent 1 Intermediate Output)
    # =========================================================================
    
    async def _create_pre_briefings_table(self):
        """Create pre_briefings table for Agent 1's raw output."""
        from google.cloud import bigquery
        
        table_id = f"{self.config.full_dataset_id}.pre_briefings"
        schema = [
            bigquery.SchemaField("id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("briefing_type", "STRING"),
            bigquery.SchemaField("data", "STRING"), # JSON structure
            bigquery.SchemaField("period_start", "TIMESTAMP"),
            bigquery.SchemaField("period_end", "TIMESTAMP"),
            bigquery.SchemaField("generated_at", "TIMESTAMP", mode="REQUIRED"),
            bigquery.SchemaField("model", "STRING"),
            bigquery.SchemaField("article_count", "INT64"),
            bigquery.SchemaField("article_ids", "STRING"), # JSON array
        ]
        
        table = bigquery.Table(table_id, schema=schema)
        table.time_partitioning = bigquery.TimePartitioning(
            field="generated_at",
            type_=bigquery.TimePartitioningType.MONTH,
        )
        
        try:
            self.client.create_table(table)
            logger.info(f"Created table {table_id}")
        except Exception as e:
            if "Already Exists" in str(e):
                logger.info(f"Table {table_id} already exists")
            else:
                raise
                
    async def save_pre_briefing(self, briefing_data: Dict[str, Any]) -> bool:
        """Save a pre-briefing record to BigQuery."""
        import json
        from datetime import datetime
        
        table_id = f"{self.config.full_dataset_id}.pre_briefings"
        
        def to_timestamp(val):
            if val is None:
                return None
            if isinstance(val, datetime):
                return val.isoformat()
            return val
            
        row = {
            "id": briefing_data['id'],
            "briefing_type": briefing_data.get('briefing_type', 'pre_briefing'),
            "data": json.dumps(briefing_data.get('data', {})),
            "period_start": to_timestamp(briefing_data.get('period_start')),
            "period_end": to_timestamp(briefing_data.get('period_end')),
            "generated_at": to_timestamp(briefing_data.get('generated_at', datetime.utcnow())),
            "model": briefing_data.get('model', ''),
            "article_count": briefing_data.get('article_count', 0),
            "article_ids": json.dumps(briefing_data.get('article_ids', [])),
        }
        
        try:
            errors = self.client.insert_rows_json(table_id, [row])
            if errors:
                logger.error(f"BigQuery insert error for pre-briefing: {errors}")
                return False
            logger.info(f"Stored pre-briefing {briefing_data['id']} in BigQuery")
            return True
        except Exception as e:
            logger.error(f"Error storing pre-briefing in BigQuery: {e}")
            return False
            
    async def get_latest_pre_briefing(self) -> Optional[Dict[str, Any]]:
        """Get the most recent pre-briefing from BigQuery."""
        import json
        
        table_id = f"{self.config.full_dataset_id}.pre_briefings"
        
        query = f"""
            SELECT *
            FROM `{table_id}`
            ORDER BY generated_at DESC
            LIMIT 1
        """
        
        try:
            query_job = self.client.query(query)
            results = list(query_job.result())
            
            if not results:
                return None
            
            row = results[0]
            briefing = dict(row)
            
            # Parse JSON fields
            if briefing.get('data'):
                try:
                    briefing['data'] = json.loads(briefing['data'])
                except (json.JSONDecodeError, TypeError):
                    briefing['data'] = {}
            if briefing.get('article_ids'):
                try:
                    briefing['article_ids'] = json.loads(briefing['article_ids'])
                except (json.JSONDecodeError, TypeError):
                    briefing['article_ids'] = []
            
            return briefing
        except Exception as e:
            logger.error(f"Error fetching latest pre-briefing from BigQuery: {e}")
            return None

    # =========================================================================
    # Ad Hoc Briefing Methods
    # =========================================================================
    
    async def _create_adhoc_briefings_table(self):
        """Create adhoc_briefings table for user-generated quick briefings."""
        from google.cloud import bigquery
        
        table_id = f"{self.config.full_dataset_id}.adhoc_briefings"
        schema = [
            bigquery.SchemaField("id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("question", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("answer", "STRING"),
            bigquery.SchemaField("sources_used", "STRING"),  # JSON array
            bigquery.SchemaField("confidence", "STRING"),
            bigquery.SchemaField("suggest_deep_research", "BOOL"),
            bigquery.SchemaField("related_topics", "STRING"),  # JSON array
            bigquery.SchemaField("context_used", "STRING"),  # JSON object
            bigquery.SchemaField("search_results_count", "INT64"),
            bigquery.SchemaField("follow_up_count", "INT64"),
            bigquery.SchemaField("generated_at", "TIMESTAMP", mode="REQUIRED"),
            bigquery.SchemaField("model", "STRING"),
            bigquery.SchemaField("user_id", "STRING"),  # For future user tracking
        ]
        
        table = bigquery.Table(table_id, schema=schema)
        table.time_partitioning = bigquery.TimePartitioning(
            field="generated_at",
            type_=bigquery.TimePartitioningType.MONTH,
        )
        
        try:
            self.client.create_table(table)
            logger.info(f"Created table {table_id}")
        except Exception as e:
            if "Already Exists" in str(e):
                logger.info(f"Table {table_id} already exists")
            else:
                raise
    
    async def save_adhoc_briefing(self, briefing_data: Dict[str, Any]) -> bool:
        """Save an ad hoc briefing to BigQuery.
        
        Args:
            briefing_data: Dict containing the ad hoc briefing response
            
        Returns:
            True if successful, False otherwise
        """
        import json
        from datetime import datetime
        
        table_id = f"{self.config.full_dataset_id}.adhoc_briefings"
        generated_at = briefing_data.get('generated_at', datetime.utcnow())
        if isinstance(generated_at, str):
            generated_at = datetime.fromisoformat(generated_at.replace('Z', '+00:00'))
        
        row = {
            "id": briefing_data['id'],
            "question": briefing_data.get('question', ''),
            "answer": briefing_data.get('answer', ''),
            "sources_used": json.dumps(briefing_data.get('sources_used', [])),
            "confidence": briefing_data.get('confidence', 'medium'),
            "suggest_deep_research": briefing_data.get('suggest_deep_research', False),
            "related_topics": json.dumps(briefing_data.get('related_topics', [])),
            "context_used": json.dumps(briefing_data.get('context_used', {})),
            "search_results_count": briefing_data.get('search_results_count', 0),
            "follow_up_count": briefing_data.get('follow_up_count', 0),
            "generated_at": generated_at.isoformat() if isinstance(generated_at, datetime) else generated_at,
            "model": briefing_data.get('model', ''),
            "user_id": briefing_data.get('user_id'),
        }
        
        try:
            errors = self.client.insert_rows_json(table_id, [row])
            if errors:
                logger.error(f"BigQuery insert error for ad hoc briefing: {errors}")
                return False
            logger.info(f"Stored ad hoc briefing {briefing_data['id']} in BigQuery")
            return True
        except Exception as e:
            logger.error(f"Error storing ad hoc briefing in BigQuery: {e}")
            return False
    
    async def get_adhoc_briefing_history(self, limit: int = 20, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get ad hoc briefing history."""
        import json
        from google.cloud import bigquery
        
        table_id = f"{self.config.full_dataset_id}.adhoc_briefings"
        
        query = f"""
            SELECT *
            FROM `{table_id}`
            {"WHERE user_id = @user_id" if user_id else ""}
            ORDER BY generated_at DESC
            LIMIT {limit}
        """
        
        job_config = None
        if user_id:
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("user_id", "STRING", user_id),
                ]
            )
        
        try:
            query_job = self.client.query(query, job_config=job_config)
            results = query_job.result()
            
            briefings = []
            for row in results:
                briefing = dict(row)
                for json_field in ['sources_used', 'related_topics', 'context_used']:
                    if briefing.get(json_field):
                        try:
                            briefing[json_field] = json.loads(briefing[json_field])
                        except (json.JSONDecodeError, TypeError):
                            briefing[json_field] = [] if json_field != 'context_used' else {}
                briefings.append(briefing)
            
            return briefings
        except Exception as e:
            logger.error(f"Error fetching ad hoc briefing history from BigQuery: {e}")
            return []

    async def _create_freight_rates_table(self):
        """Create freight_rates table for time-series shipping cost tracking."""
        from google.cloud import bigquery
        
        table_id = f"{self.config.full_dataset_id}.freight_rates"
        schema = [
            bigquery.SchemaField("lane", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("rate", "FLOAT64", mode="REQUIRED"),
            bigquery.SchemaField("currency", "STRING"),
            bigquery.SchemaField("unit", "STRING"),
            bigquery.SchemaField("change_pct", "FLOAT64"),
            bigquery.SchemaField("source", "STRING"),
            bigquery.SchemaField("as_of", "TIMESTAMP", mode="REQUIRED"),
            bigquery.SchemaField("fetched_at", "TIMESTAMP", mode="REQUIRED"),
        ]
        
        table = bigquery.Table(table_id, schema=schema)
        table.time_partitioning = bigquery.TimePartitioning(
            field="as_of",
            type_=bigquery.TimePartitioningType.MONTH,
        )
        table.clustering_fields = ["lane", "source"]
        
        try:
            self.client.create_table(table)
            logger.info(f"Created table {table_id}")
        except Exception as e:
            if "Already Exists" in str(e):
                logger.info(f"Table {table_id} already exists")
            else:
                raise

    async def store_freight_rates(self, records: List[FreightRateRecord]) -> int:
        """Store freight rates in BigQuery."""
        if not records:
            return 0
            
        table_id = f"{self.config.full_dataset_id}.freight_rates"
        rows = [r.to_dict() for r in records]
        
        errors = self.client.insert_rows_json(table_id, rows)
        if errors:
            logger.error(f"BigQuery insert errors for freight_rates: {errors[:3]}")
            
        stored = len(rows) - len(errors) if errors else len(rows)
        logger.info(f"Stored {stored}/{len(rows)} freight rates in BigQuery")
        return stored

    async def get_freight_rates(
        self,
        lane: Optional[str] = None,
        source: Optional[str] = None,
        start_date: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[FreightRateRecord]:
        """Query freight rates from BigQuery."""
        query = f"SELECT * FROM `{self.config.full_dataset_id}.freight_rates` WHERE 1=1"
        if lane:
            query += f" AND lane = '{lane}'"
        if source:
            query += f" AND source = '{source}'"
        if start_date:
            query += f" AND as_of >= '{start_date.isoformat()}'"
        
        query += f" ORDER BY as_of DESC LIMIT {limit}"
        
        rates = []
        for row in self.client.query(query):
            rates.append(FreightRateRecord(
                lane=row.lane,
                rate=row.rate,
                currency=row.currency or "USD",
                unit=row.unit or "40ft",
                change_pct=row.change_pct,
                source=row.source or "drewry",
                as_of=row.as_of,
                fetched_at=row.fetched_at,
            ))
        return rates

    async def _create_ingestion_events_table(self):
        """Create ingestion_events table for observability."""
        from google.cloud import bigquery
        
        table_id = f"{self.config.full_dataset_id}.ingestion_events"
        schema = [
            bigquery.SchemaField("run_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("event_type", "STRING", mode="REQUIRED"),  # STARTED, COMPLETED, FAILED
            bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED"),
            bigquery.SchemaField("job_type", "STRING"), # scheduled, manual, backfill
            bigquery.SchemaField("status", "STRING"),   # success, partial, error
            bigquery.SchemaField("metrics", "STRING"),  # JSON object
            bigquery.SchemaField("error_message", "STRING"),
            bigquery.SchemaField("metadata", "STRING"), # JSON details
        ]
        
        table = bigquery.Table(table_id, schema=schema)
        table.time_partitioning = bigquery.TimePartitioning(
            field="timestamp",
            type_=bigquery.TimePartitioningType.MONTH,
        )
        table.clustering_fields = ["run_id", "event_type"]
        
        try:
            self.client.create_table(table)
            logger.info(f"Created table {table_id}")
        except Exception as e:
            if "Already Exists" in str(e):
                logger.info(f"Table {table_id} already exists")
            else:
                raise

    async def log_ingestion_event(
        self,
        run_id: str,
        event_type: str,
        job_type: str = "manual",
        status: Optional[str] = None,
        metrics: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Log an ingestion event to BigQuery."""
        import json
        from datetime import datetime
        
        table_id = f"{self.config.full_dataset_id}.ingestion_events"
        
        row = {
            "run_id": run_id,
            "event_type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "job_type": job_type,
            "status": status,
            "metrics": json.dumps(metrics) if metrics else None,
            "error_message": error_message,
            "metadata": json.dumps(metadata) if metadata else None,
        }
        
        try:
            errors = self.client.insert_rows_json(table_id, [row])
            if errors:
                logger.error(f"BigQuery insert error for ingestion_event: {errors}")
                return False
            return True
        except Exception as e:
            logger.error(f"Error logging ingestion event: {e}")
            return False

    async def store_research_report(
        self,
        report_id: str,
        query: str,
        title: str,
        content: str,
        agent: str = "market_scout",
        sources: Optional[List[dict]] = None,
        companies: Optional[List[str]] = None,
        materials: Optional[List[str]] = None,
        user_id: Optional[str] = None,
    ) -> bool:
        """Store a research report in BigQuery."""
        import json
        
        table_id = f"{self.config.full_dataset_id}.research_reports"
        row = {
            "id": report_id,
            "query": query,
            "title": title,
            "content": content,
            "agent": agent,
            "sources": json.dumps(sources or []),
            "companies_mentioned": json.dumps(companies or []),
            "materials_mentioned": json.dumps(materials or []),
            "user_id": user_id or "default",
            "created_at": datetime.utcnow().isoformat(),
        }
        
        errors = self.client.insert_rows_json(table_id, [row])
        if errors:
            logger.error(f"BigQuery insert error for research report: {errors}")
            return False
        logger.info(f"Stored research report {report_id}: {title[:50]}")
        return True
    
    async def get_research_reports(
        self,
        user_id: Optional[str] = None,
        agent: Optional[str] = None,
        limit: int = 50,
    ) -> List[dict]:
        """Retrieve research reports from BigQuery."""
        import json
        
        query = f"SELECT * FROM `{self.config.full_dataset_id}.research_reports` WHERE 1=1"
        if user_id:
            query += f" AND user_id = '{user_id}'"
        if agent:
            query += f" AND agent = '{agent}'"
        query += f" ORDER BY created_at DESC LIMIT {limit}"
        
        reports = []
        for row in self.client.query(query):
            reports.append({
                "id": row.id,
                "query": row.query,
                "title": row.title,
                "content": row.content,
                "agent": row.agent,
                "sources": _safe_parse_list(row.sources),
                "companies_mentioned": _safe_parse_list(row.companies_mentioned),
                "materials_mentioned": _safe_parse_list(row.materials_mentioned),
                "user_id": row.user_id,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            })
        return reports

    # =========================================================================
    # Deep Research Reports Storage (Phase 4)
    # =========================================================================
    
    async def store_deep_research_report(
        self,
        report_id: str,
        query: str,
        query_hash: str,
        state: Dict[str, Any],
        query_embedding: Optional[List[float]] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> bool:
        """
        Store a completed Deep Research report in BigQuery.
        
        Args:
            report_id: Unique report identifier
            query: Original user query
            query_hash: Hash for deduplication/lookup
            state: Full workflow state with all outputs
            query_embedding: Optional embedding for semantic search
            user_id: Optional user identifier
            session_id: Optional session identifier
            
        Returns:
            True if stored successfully
        """
        table_id = f"{self.config.full_dataset_id}.deep_research_reports"
        
        # Extract entities and metadata from state
        final_report = state.get("final_report")
        category_output = state.get("category_output")
        validator_output = state.get("validator_output")
        research_brief = state.get("research_brief")
        
        # Extract companies, industries, topics from various outputs
        companies = set()
        industries = set()
        topics = set()
        products = set()
        
        if final_report:
            exec_summary = final_report.executive_summary if hasattr(final_report, 'executive_summary') else None
            if exec_summary and hasattr(exec_summary, 'key_points'):
                for point in exec_summary.key_points[:5]:  # Limit to prevent bloat
                    topics.add(point[:100])  # Truncate long points
        
        if research_brief:
            if hasattr(research_brief, 'entities_to_track'):
                for entity in (research_brief.entities_to_track or []):
                    companies.add(entity)
        
        if category_output:
            if hasattr(category_output, 'product_recommendations'):
                for rec in (category_output.product_recommendations or []):
                    if hasattr(rec, 'product_name'):
                        products.add(rec.product_name)
            if hasattr(category_output, 'territory_insights'):
                for territory, insight in (category_output.territory_insights or {}).items():
                    if hasattr(insight, 'priority_industries'):
                        industries.update(insight.priority_industries or [])
        
        # Safely serialize Pydantic models
        def safe_dump(obj):
            if obj is None:
                return None
            if hasattr(obj, 'model_dump'):
                return json.dumps(obj.model_dump())
            if hasattr(obj, 'dict'):
                return json.dumps(obj.dict())
            return json.dumps(obj)
        
        row = {
            "id": report_id,
            "query_hash": query_hash,
            "query": query,
            "query_embedding": query_embedding or [],
            "research_brief": safe_dump(research_brief),
            "financial_output": safe_dump(state.get("financial_output")),
            "industry_output": safe_dump(state.get("industry_output")),
            "final_report": safe_dump(final_report),
            "category_output": safe_dump(category_output),
            "validator_output": safe_dump(validator_output),
            "companies": json.dumps(list(companies)),
            "industries": json.dumps(list(industries)),
            "topics": json.dumps(list(topics)),
            "products": json.dumps(list(products)),
            "title": final_report.executive_summary.headline if final_report and hasattr(final_report, 'executive_summary') and final_report.executive_summary else query[:100],
            "executive_summary": " | ".join(final_report.executive_summary.key_points[:3]) if final_report and hasattr(final_report, 'executive_summary') and final_report.executive_summary else None,
            "data_completeness": final_report.data_completeness.value if final_report and hasattr(final_report, 'data_completeness') else None,
            "overall_confidence": final_report.overall_confidence.value if final_report and hasattr(final_report, 'overall_confidence') else None,
            "validation_passed": validator_output.validation_passed if validator_output and hasattr(validator_output, 'validation_passed') else None,
            "citation_count": validator_output.total_citations_checked if validator_output and hasattr(validator_output, 'total_citations_checked') else 0,
            "citation_issues_count": len(validator_output.citation_issues) if validator_output and hasattr(validator_output, 'citation_issues') else 0,
            "research_time_seconds": final_report.research_time_seconds if final_report and hasattr(final_report, 'research_time_seconds') else None,
            "tools_used": json.dumps([]),  # TODO: Track tools used
            "sources_count": len(final_report.sources_used) if final_report and hasattr(final_report, 'sources_used') else 0,
            "user_id": user_id or "default",
            "session_id": session_id,
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": None,  # No automatic expiry for now
        }
        
        try:
            errors = self.client.insert_rows_json(table_id, [row])
            if errors:
                logger.error(f"BigQuery insert error for deep research report: {errors}")
                return False
            logger.info(f"Stored deep research report {report_id}: {query[:50]}...")
            return True
        except Exception as e:
            logger.error(f"Error storing deep research report: {e}")
            return False
    
    async def get_deep_research_report_by_hash(
        self,
        query_hash: str,
        max_age_hours: int = 24,
    ) -> Optional[Dict[str, Any]]:
        """
        Get a deep research report by query hash.
        
        Used for cache lookup before running expensive workflow.
        
        Args:
            query_hash: Hash of normalized query
            max_age_hours: Only return reports newer than this (default 24h)
            
        Returns:
            Report dict or None if not found/expired
        """
        from datetime import timedelta
        
        cutoff = (datetime.utcnow() - timedelta(hours=max_age_hours)).isoformat()
        
        query = f"""
            SELECT *
            FROM `{self.config.full_dataset_id}.deep_research_reports`
            WHERE query_hash = @query_hash
              AND created_at >= @cutoff
            ORDER BY created_at DESC
            LIMIT 1
        """
        
        from google.cloud import bigquery
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("query_hash", "STRING", query_hash),
                bigquery.ScalarQueryParameter("cutoff", "STRING", cutoff),
            ]
        )
        
        try:
            result = list(self.client.query(query, job_config=job_config))
            if not result:
                return None
            
            row = result[0]
            return self._parse_deep_research_row(row)
        except Exception as e:
            logger.error(f"Error fetching deep research report by hash: {e}")
            return None
    
    async def get_deep_research_reports(
        self,
        user_id: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Get recent deep research reports.
        
        Args:
            user_id: Filter by user (optional)
            limit: Max reports to return
            offset: Pagination offset
            
        Returns:
            List of report summaries (not full content)
        """
        query = f"""
            SELECT 
                id, query_hash, query, title, executive_summary,
                data_completeness, overall_confidence, validation_passed,
                citation_count, research_time_seconds, sources_count,
                companies, industries, topics,
                user_id, created_at
            FROM `{self.config.full_dataset_id}.deep_research_reports`
            WHERE 1=1
        """
        
        if user_id:
            query += f" AND user_id = '{user_id}'"
        
        query += f" ORDER BY created_at DESC LIMIT {limit} OFFSET {offset}"
        
        reports = []
        try:
            for row in self.client.query(query):
                reports.append({
                    "id": row.id,
                    "query_hash": row.query_hash,
                    "query": row.query,
                    "title": row.title,
                    "executive_summary": row.executive_summary,
                    "data_completeness": row.data_completeness,
                    "overall_confidence": row.overall_confidence,
                    "validation_passed": row.validation_passed,
                    "citation_count": row.citation_count,
                    "research_time_seconds": row.research_time_seconds,
                    "sources_count": row.sources_count,
                    "companies": _safe_parse_list(row.companies),
                    "industries": _safe_parse_list(row.industries),
                    "topics": _safe_parse_list(row.topics),
                    "user_id": row.user_id,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                })
        except Exception as e:
            logger.error(f"Error fetching deep research reports: {e}")
        
        return reports
    
    async def get_deep_research_report_by_id(self, report_id: str) -> Optional[Dict[str, Any]]:
        """Get full deep research report by ID."""
        query = f"""
            SELECT *
            FROM `{self.config.full_dataset_id}.deep_research_reports`
            WHERE id = @report_id
            LIMIT 1
        """
        
        from google.cloud import bigquery
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("report_id", "STRING", report_id),
            ]
        )
        
        try:
            result = list(self.client.query(query, job_config=job_config))
            if not result:
                return None
            return self._parse_deep_research_row(result[0])
        except Exception as e:
            logger.error(f"Error fetching deep research report by ID: {e}")
            return None
    
    async def search_related_research(
        self,
        query: str,
        companies: Optional[List[str]] = None,
        industries: Optional[List[str]] = None,
        max_age_days: int = 90,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Search for related past research reports.
        
        Used for memory/context integration to avoid redundant research
        and surface relevant prior findings.
        
        Args:
            query: Current query for text matching
            companies: Companies to search for
            industries: Industries to filter by
            max_age_days: Only search within this window
            limit: Max results to return
            
        Returns:
            List of related report summaries
        """
        from datetime import timedelta
        
        cutoff = (datetime.utcnow() - timedelta(days=max_age_days)).isoformat()
        
        # Build WHERE clause for entity matching
        conditions = [f"created_at >= '{cutoff}'"]
        
        # Text search on query
        if query:
            # Escape single quotes in query
            escaped_query = query.replace("'", "\\'")
            conditions.append(f"LOWER(query) LIKE '%{escaped_query.lower()[:50]}%'")
        
        # Company matching (check if any requested company is in the stored array)
        if companies:
            company_conditions = []
            for company in companies[:5]:  # Limit to 5 companies
                escaped = company.replace("'", "\\'")
                company_conditions.append(f"LOWER(companies) LIKE '%{escaped.lower()}%'")
            if company_conditions:
                conditions.append(f"({' OR '.join(company_conditions)})")
        
        # Industry matching
        if industries:
            industry_conditions = []
            for industry in industries[:5]:
                escaped = industry.replace("'", "\\'")
                industry_conditions.append(f"LOWER(industries) LIKE '%{escaped.lower()}%'")
            if industry_conditions:
                conditions.append(f"({' OR '.join(industry_conditions)})")
        
        where_clause = " AND ".join(conditions)
        
        query_sql = f"""
            SELECT 
                id, query_hash, query, title, executive_summary,
                data_completeness, overall_confidence, validation_passed,
                companies, industries, topics,
                created_at
            FROM `{self.config.full_dataset_id}.deep_research_reports`
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT {limit}
        """
        
        reports = []
        try:
            for row in self.client.query(query_sql):
                reports.append({
                    "id": row.id,
                    "query_hash": row.query_hash,
                    "query": row.query,
                    "title": row.title,
                    "executive_summary": row.executive_summary,
                    "data_completeness": row.data_completeness,
                    "overall_confidence": row.overall_confidence,
                    "validation_passed": row.validation_passed,
                    "companies": _safe_parse_list(row.companies),
                    "industries": _safe_parse_list(row.industries),
                    "topics": _safe_parse_list(row.topics),
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                })
        except Exception as e:
            logger.error(f"Error searching related research: {e}")
        
        return reports
    
    def _parse_deep_research_row(self, row) -> Dict[str, Any]:
        """Parse a BigQuery row into a deep research report dict."""
        return {
            "id": row.id,
            "query_hash": row.query_hash,
            "query": row.query,
            "query_embedding": list(row.query_embedding) if row.query_embedding else None,
            "research_brief": json.loads(row.research_brief) if row.research_brief else None,
            "financial_output": json.loads(row.financial_output) if row.financial_output else None,
            "industry_output": json.loads(row.industry_output) if row.industry_output else None,
            "final_report": json.loads(row.final_report) if row.final_report else None,
            "category_output": json.loads(row.category_output) if row.category_output else None,
            "validator_output": json.loads(row.validator_output) if row.validator_output else None,
            "companies": _safe_parse_list(row.companies),
            "industries": _safe_parse_list(row.industries),
            "topics": _safe_parse_list(row.topics),
            "products": _safe_parse_list(row.products),
            "title": row.title,
            "executive_summary": row.executive_summary,
            "data_completeness": row.data_completeness,
            "overall_confidence": row.overall_confidence,
            "validation_passed": row.validation_passed,
            "citation_count": row.citation_count,
            "citation_issues_count": row.citation_issues_count,
            "research_time_seconds": row.research_time_seconds,
            "tools_used": _safe_parse_list(row.tools_used),
            "sources_count": row.sources_count,
            "user_id": row.user_id,
            "session_id": row.session_id,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "expires_at": row.expires_at.isoformat() if row.expires_at else None,
        }

    # =========================================================================
    # Article Images Storage
    # =========================================================================
    
    async def store_article_images(self, images: List[Dict[str, Any]]) -> int:
        """Store extracted article images in BigQuery.
        
        Args:
            images: List of ExtractedImage.to_dict() or equivalent dicts
            
        Returns:
            Number of images stored
        """
        if not images:
            return 0
        
        table_id = f"{self.config.full_dataset_id}.article_images"
        
        rows = []
        for img in images:
            rows.append({
                "id": img.get("id", str(uuid.uuid4())),
                "image_hash": img.get("image_hash", ""),
                "article_id": img.get("article_id"),
                "article_title": img.get("article_title"),
                "article_url": img.get("article_url"),
                "url": img.get("url", ""),
                "source_domain": img.get("source_domain", ""),
                "image_type": img.get("image_type", "unknown"),
                "chart_type": img.get("chart_type"),
                "description": img.get("description", ""),
                "alt_text": img.get("alt_text", ""),
                "extracted_text": img.get("extracted_text"),
                "extracted_data_points": json.dumps(img.get("extracted_data_points", [])),
                "topics": json.dumps(img.get("topics", [])),
                "companies": json.dumps(img.get("companies", [])),
                "industries": json.dumps(img.get("industries", [])),
                "time_period": img.get("time_period"),
                "relevance_score": img.get("relevance_score", 0.0),
                "quality_score": img.get("quality_score", 0.0),
                "width": img.get("width"),
                "height": img.get("height"),
                "format": img.get("format"),
                "extracted_at": img.get("extracted_at", datetime.utcnow().isoformat()),
            })
        
        errors = self.client.insert_rows_json(table_id, rows)
        stored = len(rows) - len(errors) if errors else len(rows)
        if errors:
            logger.error(f"BigQuery insert errors for article_images: {errors[:3]}")
        logger.info(f"Stored {stored}/{len(rows)} article images in BigQuery")
        return stored
    
    async def get_article_images(
        self,
        article_id: Optional[str] = None,
        image_type: Optional[str] = None,
        chart_type: Optional[str] = None,
        companies: Optional[List[str]] = None,
        industries: Optional[List[str]] = None,
        topics: Optional[List[str]] = None,
        min_relevance: float = 0.0,
        days: int = 30,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Query article images from BigQuery.
        
        Args:
            article_id: Filter by specific article
            image_type: Filter by type (chart, graph, infographic, etc.)
            chart_type: Filter by chart type (line, bar, pie, etc.)
            companies: Filter by companies mentioned (any match)
            industries: Filter by industries (any match)
            topics: Filter by topics (any match)
            min_relevance: Minimum relevance score
            days: Look back period
            limit: Max results
            
        Returns:
            List of image records
        """
        query = f"""
            SELECT * FROM `{self.config.full_dataset_id}.article_images`
            WHERE extracted_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {days} DAY)
              AND relevance_score >= {min_relevance}
        """
        
        if article_id:
            query += f" AND article_id = '{article_id}'"
        if image_type:
            query += f" AND image_type = '{image_type}'"
        if chart_type:
            query += f" AND chart_type = '{chart_type}'"
        
        # JSON array contains queries for companies/industries/topics
        if companies:
            conditions = " OR ".join([f"JSON_VALUE(companies, '$[{i}]') = '{c}'" for i, c in enumerate(companies[:5])])
            query += f" AND ({conditions})"
        if industries:
            conditions = " OR ".join([f"JSON_VALUE(industries, '$[{i}]') = '{ind}'" for i, ind in enumerate(industries[:5])])
            query += f" AND ({conditions})"
        if topics:
            conditions = " OR ".join([f"topics LIKE '%{t}%'" for t in topics[:5]])
            query += f" AND ({conditions})"
        
        query += f" ORDER BY relevance_score DESC, extracted_at DESC LIMIT {limit}"
        
        results = []
        for row in self.client.query(query):
            results.append({
                "id": row.id,
                "image_hash": row.image_hash,
                "article_id": row.article_id,
                "article_title": row.article_title,
                "article_url": row.article_url,
                "url": row.url,
                "source_domain": row.source_domain,
                "image_type": row.image_type,
                "chart_type": row.chart_type,
                "description": row.description,
                "alt_text": row.alt_text,
                "extracted_text": row.extracted_text,
                "extracted_data_points": _safe_parse_list(row.extracted_data_points),
                "topics": _safe_parse_list(row.topics),
                "companies": _safe_parse_list(row.companies),
                "industries": _safe_parse_list(row.industries),
                "time_period": row.time_period,
                "relevance_score": row.relevance_score,
                "quality_score": row.quality_score,
                "width": row.width,
                "height": row.height,
                "format": row.format,
                "extracted_at": row.extracted_at.isoformat() if row.extracted_at else None,
            })
        return results
    
    async def get_images_for_briefing(
        self,
        companies: Optional[List[str]] = None,
        industries: Optional[List[str]] = None,
        topics: Optional[List[str]] = None,
        days: int = 30,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get high-quality images suitable for executive briefings.
        
        Filters for charts/graphs with good relevance and quality scores.
        """
        return await self.get_article_images(
            image_type="chart",  # Focus on charts for briefings
            companies=companies,
            industries=industries,
            topics=topics,
            min_relevance=0.5,  # Higher quality threshold for briefings
            days=days,
            limit=limit,
        )
    
    async def get_images_by_topic(
        self,
        topic: str,
        chart_types: Optional[List[str]] = None,
        days: int = 30,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Get images related to a specific topic for research display.
        
        Args:
            topic: Topic to search for (e.g., "revenue", "market_share", "forecast")
            chart_types: Filter by specific chart types
            days: Look back period
            limit: Max results
        """
        query = f"""
            SELECT * FROM `{self.config.full_dataset_id}.article_images`
            WHERE extracted_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {days} DAY)
              AND topics LIKE '%{topic}%'
              AND relevance_score >= 0.3
        """
        
        if chart_types:
            types_str = "', '".join(chart_types)
            query += f" AND chart_type IN ('{types_str}')"
        
        query += f" ORDER BY relevance_score DESC LIMIT {limit}"
        
        results = []
        for row in self.client.query(query):
            results.append({
                "id": row.id,
                "url": row.url,
                "image_type": row.image_type,
                "chart_type": row.chart_type,
                "description": row.description,
                "alt_text": row.alt_text,
                "topics": _safe_parse_list(row.topics),
                "companies": _safe_parse_list(row.companies),
                "time_period": row.time_period,
                "relevance_score": row.relevance_score,
                "article_title": row.article_title,
                "article_url": row.article_url,
            })
        return results
    
    async def store_articles(self, records: List[ArticleRecord]) -> int:
        if not records:
            return 0
        
        import json
        table_id = f"{self.config.full_dataset_id}.articles"
        
        rows = []
        for r in records:
            row = r.to_dict()
            # Serialize complex types to JSON strings for BigQuery STRING columns
            row["topics"] = json.dumps(row["topics"])
            row["companies_mentioned"] = json.dumps(row["companies_mentioned"])
            rows.append(row)
            
        errors = self.client.insert_rows_json(table_id, rows)
        if errors:
            logger.error(f"BigQuery insert errors for articles: {errors[:5]}")  # Log first 5 errors
        stored = len(records) - len(errors) if errors else len(records)
        logger.info(f"Stored {stored}/{len(records)} articles in BigQuery")
        return stored
    
    async def get_articles(
        self,
        source_type: Optional[str] = None,
        category: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        search_query: Optional[str] = None,
        limit: int = 50,
    ) -> List[ArticleRecord]:
        query = f"SELECT * FROM `{self.config.full_dataset_id}.articles` WHERE 1=1"
        if source_type:
            query += f" AND source_type = '{source_type}'"
        if category:
            query += f" AND category = '{category}'"
        if start_date:
            query += f" AND published_at >= '{start_date.isoformat()}'"
        if end_date:
            query += f" AND published_at <= '{end_date.isoformat()}'"
        if search_query:
            query += f" AND (LOWER(title) LIKE '%{search_query.lower()}%' OR LOWER(summary) LIKE '%{search_query.lower()}%')"
        query += f" ORDER BY published_at DESC LIMIT {limit}"
        
        records = []
        for row in self.client.query(query):
            records.append(ArticleRecord(
                id=row.id,
                title=row.title,
                url=row.url or "",
                published_at=row.published_at,
                source_name=row.source_name or "",
                source_type=row.source_type or "",
                summary=row.summary,
                category=row.category,
                topics=_safe_parse_list(row.topics),
                companies_mentioned=_safe_parse_list(row.companies_mentioned),
                relevance_score=row.relevance_score or 0.5,
                fetched_at=row.fetched_at,
            ))
        return records
    
    # =========================================================================
    # Deduplication Methods
    # =========================================================================
    
    async def check_duplicate(self, url: str) -> Optional[str]:
        """
        Check if URL already exists in articles table.
        Returns article_id if duplicate, None otherwise.
        
        This is used by DeduplicationService to prevent storing duplicate content.
        """
        if not url:
            return None
            
        from google.cloud import bigquery
        
        table_id = f"{self.config.full_dataset_id}.articles"
        
        # Use parameterized query for safety
        query = f"""
        SELECT id FROM `{table_id}`
        WHERE url = @url
        LIMIT 1
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("url", "STRING", url)
            ]
        )
        
        try:
            results = list(self.client.query(query, job_config=job_config).result())
            if results:
                return results[0].id
            return None
        except Exception as e:
            logger.warning(f"Error checking duplicate for URL: {e}")
            return None
    
    async def get_recent_articles_for_dedup(self, hours: int = 168, limit: int = 2000) -> List[Dict[str, Any]]:
        """
        Get recent articles for deduplication cache loading.
        
        Returns list of dicts with id, url, title for building in-memory cache.
        Default: last 168 hours (7 days), up to 2000 articles.
        """
        table_id = f"{self.config.full_dataset_id}.articles"
        
        query = f"""
        SELECT id, url, title
        FROM `{table_id}`
        WHERE fetched_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {hours} HOUR)
        ORDER BY fetched_at DESC
        LIMIT {limit}
        """
        
        try:
            results = []
            for row in self.client.query(query).result():
                results.append({
                    "id": row.id,
                    "url": row.url or "",
                    "title": row.title or ""
                })
            logger.info(f"Loaded {len(results)} recent articles for dedup cache from BigQuery")
            return results
        except Exception as e:
            logger.error(f"Error loading dedup cache from BigQuery: {e}")
            return []
    
    # =========================================================================
    # Digest Items Storage (Classified Articles)
    # =========================================================================
    
    async def store_digest_items(self, items: List[Dict[str, Any]]) -> int:
        """
        Store classified digest items in BigQuery.
        
        Args:
            items: List of ClassifiedArticle.to_dict() objects
            
        Returns:
            Number of items stored
        """
        if not items:
            return 0
        
        import uuid
        
        table_id = f"{self.config.full_dataset_id}.digest_items"
        now = datetime.utcnow().isoformat()
        
        rows = []
        for item in items:
            rows.append({
                "id": str(uuid.uuid4()),
                "article_id": item.get("article_id", ""),
                "title": item.get("title", ""),
                "headline": item.get("headline", ""),
                "url": item.get("url", ""),
                "published_at": item.get("published_at"),
                "source_name": item.get("source_name", ""),
                "source_type": item.get("source_type", ""),
                "category": item.get("category", "market"),
                "priority": item.get("priority", "medium"),
                "digest_summary": item.get("digest_summary", ""),
                "original_summary": item.get("original_summary", ""),
                "companies": json.dumps(item.get("companies", [])),
                "materials": json.dumps(item.get("materials", [])),
                "topics": json.dumps(item.get("topics", [])),
                "industries": json.dumps(item.get("industries", [])),
                "relevance_score": item.get("relevance_score", 0.5),
                "confidence": item.get("confidence", 0.0),
                # Coverage/Virality tracking
                "coverage_count": item.get("coverage_count", 1),
                "duplicate_sources": json.dumps(item.get("duplicate_sources", [])),
                "all_urls": json.dumps(item.get("all_urls", [])),
                "classifier_model": item.get("classifier_model", ""),
                "classified_at": item.get("classified_at", now),
                "ingested_at": now,
                "feed_eligible": item.get("feed_eligible", True),
                "is_hero": item.get("is_hero", False),
                # Narrative enrichment fields
                "event_type": item.get("event_type", ""),
                "sentiment": item.get("sentiment", "neutral"),
                "geography": json.dumps(item.get("geography", [])),
                "themes": json.dumps(item.get("themes", [])),
                "narrative_enriched_at": item.get("narrative_enriched_at"),
            })
        
        errors = self.client.insert_rows_json(table_id, rows)
        if errors:
            logger.error(f"BigQuery insert errors for digest_items: {errors[:3]}")
        
        stored = len(rows) - len(errors) if errors else len(rows)
        logger.info(f"Stored {stored} digest items in BigQuery")
        return stored
    
    async def get_digest_items(
        self,
        hours: int = 72,
        categories: Optional[List[str]] = None,
        priorities: Optional[List[str]] = None,
        min_confidence: float = 0.0,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Query digest items from BigQuery.
        
        Args:
            hours: Look back this many hours (legacy param, now uses 3-day window)
            categories: Filter by categories (None = all)
            priorities: Filter by priorities (None = all)
            min_confidence: Minimum classifier confidence
            limit: Max items to return
            
        Returns:
            List of digest item dictionaries
        """
        from datetime import timedelta
        
        # Convert hours to a lookback window (e.g., 168 hours = 7 days for Pulse tab)
        lookback_hours = hours or 72  # Default to 72 hours (3 days)
        cutoff_time = (datetime.utcnow() - timedelta(hours=lookback_hours)).isoformat()
        now_iso = datetime.utcnow().isoformat()
        
        # Filter criteria:
        # 1. published_at must be within lookback window (fresh content only)
        # 2. published_at must NOT be in the future (reject bad date parsing)
        # 3. published_at must NOT be within 30 minutes of classified_at (indicates defaulted/guessed date)
        # 4. ingested_at must be >= 2025-12-28 (data before this has unreliable published_at dates)
        query = f"""
            SELECT * FROM `{self.config.full_dataset_id}.digest_items`
            WHERE published_at >= '{cutoff_time}'
            AND published_at <= '{now_iso}'
            AND confidence >= {min_confidence}
            AND ingested_at >= '2025-12-28T00:00:00'
            AND (
                classified_at IS NULL 
                OR published_at IS NULL
                OR ABS(TIMESTAMP_DIFF(classified_at, published_at, SECOND)) > 1800
            )
        """
        
        if categories:
            cats = "', '".join(c.lower() for c in categories)
            query += f" AND LOWER(category) IN ('{cats}')"
        
        if priorities:
            pris = "', '".join(p.lower() for p in priorities)
            query += f" AND LOWER(priority) IN ('{pris}')"
        
        query += f"""
            ORDER BY 
                CASE LOWER(priority)
                    WHEN 'critical' THEN 1
                    WHEN 'high' THEN 2
                    WHEN 'medium' THEN 3
                    WHEN 'low' THEN 4
                END,
                published_at DESC
            LIMIT {limit}
        """
        
        items = []
        for row in self.client.query(query):
            items.append({
                "id": row.id,
                "article_id": row.article_id,
                "title": row.title,
                "headline": getattr(row, "headline", None),
                "url": row.url,
                "published_at": row.published_at.isoformat() if row.published_at else None,
                "source_name": row.source_name,
                "source_type": row.source_type,
                "category": row.category,
                "priority": row.priority,
                "digest_summary": row.digest_summary,
                "original_summary": row.original_summary,
                "companies": _safe_parse_list(row.companies),
                "materials": _safe_parse_list(row.materials),
                "topics": _safe_parse_list(row.topics),
                "industries": _safe_parse_list(row.industries),
                "relevance_score": row.relevance_score,
                "confidence": row.confidence,
                "classified_at": row.classified_at.isoformat() if row.classified_at else None,
                # Coverage tracking fields
                "coverage_count": getattr(row, 'coverage_count', 1) or 1,
                "duplicate_sources": _safe_parse_list(getattr(row, 'duplicate_sources', None)),
                "all_urls": _safe_parse_list(getattr(row, 'all_urls', None)),
                "is_hero": getattr(row, 'is_hero', False) or False,
            })
        
        return items
    
    def _get_cached(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired."""
        if key in self._cache:
            data, timestamp = self._cache[key]
            if (datetime.utcnow().timestamp() - timestamp) < self._cache_ttl:
                return data
            else:
                del self._cache[key]
        return None
    
    def _set_cache(self, key: str, value: Any):
        """Set value in cache with timestamp."""
        self._cache[key] = (value, datetime.utcnow().timestamp())
    
    async def get_companies(self) -> List[Dict[str, Any]]:
        """Get list of companies from BigQuery (cached)."""
        cached = self._get_cached('companies')
        if cached is not None:
            return cached
        
        query = f"SELECT * FROM `{self.config.full_dataset_id}.companies`"
        
        companies = []
        try:
            for row in self.client.query(query):
                company_dict = {
                    "id": row.company_id,
                    "name": row.company,
                    "ticker": row.stock_ticker,
                    "type": row.type,
                    "industries": row.industries_served,
                    "description": row.description,
                    "processes_services": row.processes_services,
                }
                
                # Add new columns if they exist
                if hasattr(row, 'website'):
                    company_dict["website"] = row.website
                if hasattr(row, 'is_c1_supplier'):
                    company_dict["is_c1_supplier"] = row.is_c1_supplier
                if hasattr(row, 'supplier_categories'):
                    company_dict["supplier_categories"] = row.supplier_categories
                if hasattr(row, 'supplier_source'):
                    company_dict["supplier_source"] = row.supplier_source
                
                companies.append(company_dict)
        except Exception as e:
            logger.error(f"Error fetching companies from BigQuery: {e}")
            return []
        
        self._set_cache('companies', companies)
        return companies
    
    async def get_materials(self) -> List[Dict[str, Any]]:
        """Get list of materials from BigQuery (cached)."""
        cached = self._get_cached('materials')
        if cached is not None:
            return cached
        query = f"SELECT * FROM `{self.config.full_dataset_id}.materials`"
        
        materials = []
        try:
            for row in self.client.query(query):
                materials.append({
                    "id": row.material_proc_id,
                    "name": row.material_process_name,
                    "type": row.type,
                    "margin_tier": row.est_manufacturer_margin_tier,
                    "industries": row.industries_served,
                    "examples": row.examples
                })
        except Exception as e:
            logger.error(f"Error fetching materials from BigQuery: {e}")
            return []
        
        self._set_cache('materials', materials)
        return materials
    
    async def get_industries(self) -> List[Dict[str, Any]]:
        """Get list of industries from BigQuery (cached)."""
        cached = self._get_cached('industries')
        if cached is not None:
            return cached
        
        query = f"SELECT * FROM `{self.config.full_dataset_id}.industries`"
        
        industries = []
        try:
            for row in self.client.query(query):
                industries.append({
                    "name": row.industry,
                    "application": row.application,
                    "end_users": row.end_users,
                    "naics_code": row.naics_code,
                    "priority": row.industry_priority_flag,
                    "example_products": row.example_products
                })
        except Exception as e:
            logger.error(f"Error fetching industries from BigQuery: {e}")
            return []
        
        self._set_cache('industries', industries)
        return industries

    async def get_digest_stats(self, hours: int = 72) -> Dict[str, Any]:
        """Get statistics for digest items."""
        from datetime import timedelta
        
        cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
        
        query = f"""
            SELECT
                COUNT(*) as total_items,
                COUNTIF(priority = 'critical') as critical_count,
                COUNTIF(priority = 'high') as high_count,
                COUNTIF(priority = 'medium') as medium_count,
                COUNTIF(priority = 'low') as low_count,
                COUNT(DISTINCT category) as category_count
            FROM `{self.config.full_dataset_id}.digest_items`
            WHERE published_at >= '{cutoff}'
        """
        
        result = list(self.client.query(query))
        if result:
            row = result[0]
            return {
                "total_items": row.total_items,
                "by_priority": {
                    "critical": row.critical_count,
                    "high": row.high_count,
                    "medium": row.medium_count,
                    "low": row.low_count,
                },
                "category_count": row.category_count,
            }
        
        return {"total_items": 0, "by_priority": {}, "category_count": 0}

    # =========================================================================
    # User Login Tracking
    # =========================================================================
    
    async def _create_user_logins_table(self):
        """Create user_logins table for basic usage analytics.
        
        Records each login event (name, team, timestamp) to track
        engagement from C1 team members. Not for session tracking,
        just a signal of "they logged in".
        """
        from google.cloud import bigquery
        
        table_id = f"{self.config.full_dataset_id}.user_logins"
        schema = [
            bigquery.SchemaField("id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("user_name", "STRING"),  # What they entered
            bigquery.SchemaField("user_team", "STRING"),  # Sales East, Sales West, Marketing, etc.
            bigquery.SchemaField("logged_in_at", "TIMESTAMP", mode="REQUIRED"),
            bigquery.SchemaField("user_agent", "STRING"),  # Browser info for debugging
        ]
        
        table = bigquery.Table(table_id, schema=schema)
        table.time_partitioning = bigquery.TimePartitioning(
            field="logged_in_at",
            type_=bigquery.TimePartitioningType.MONTH,
        )
        table.clustering_fields = ["user_team"]
        
        try:
            self.client.create_table(table)
            logger.info(f"Created table {table_id}")
        except Exception as e:
            if "Already Exists" in str(e):
                logger.info(f"Table {table_id} already exists")
            else:
                raise
    
    async def log_user_login(
        self,
        user_name: str,
        user_team: str,
        user_agent: Optional[str] = None,
    ) -> bool:
        """Log a user login event to BigQuery.
        
        Called after successful password verification to track engagement.
        Fire-and-forget - failures should not block the login flow.
        
        Args:
            user_name: Name entered by user
            user_team: Team selection (Sales East, Sales West, etc.)
            user_agent: Browser user-agent string (optional)
            
        Returns:
            True if logged successfully, False otherwise
        """
        try:
            table_id = f"{self.config.full_dataset_id}.user_logins"
            
            row = {
                "id": str(uuid.uuid4()),
                "user_name": user_name.strip() if user_name else "Unknown",
                "user_team": user_team if user_team else "Unknown",
                "logged_in_at": datetime.utcnow().isoformat(),
                "user_agent": user_agent[:500] if user_agent else None,  # Truncate long UAs
            }
            
            errors = self.client.insert_rows_json(table_id, [row])
            if errors:
                logger.warning(f"[LOGIN_TRACKING] Failed to log login: {errors}")
                return False
            
            logger.info(f"[LOGIN_TRACKING] Logged login for '{user_name}' ({user_team})")
            return True
            
        except Exception as e:
            # Never fail the login flow due to tracking errors
            logger.warning(f"[LOGIN_TRACKING] Error logging login: {e}")
            return False


    # =========================================================================
    # Podcast Ingestion Tables
    # =========================================================================

    async def _create_podcast_episodes_table(self):
        """Create podcast_episodes table for episode metadata + transcripts."""
        from google.cloud import bigquery

        table_id = f"{self.config.full_dataset_id}.podcast_episodes"
        schema = [
            bigquery.SchemaField("id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("podcast_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("podcast_name", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("guid", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("title", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("description", "STRING"),
            bigquery.SchemaField("audio_url", "STRING"),
            bigquery.SchemaField("audio_duration_seconds", "INT64"),
            bigquery.SchemaField("website_url", "STRING"),
            bigquery.SchemaField("youtube_video_id", "STRING"),
            bigquery.SchemaField("published_at", "TIMESTAMP", mode="REQUIRED"),
            bigquery.SchemaField("transcript_text", "STRING"),
            bigquery.SchemaField("transcript_source", "STRING"),
            bigquery.SchemaField("transcript_has_speakers", "BOOLEAN"),
            bigquery.SchemaField("transcript_word_count", "INT64"),
            bigquery.SchemaField("transcript_cost_usd", "FLOAT64"),
            bigquery.SchemaField("guest_name", "STRING"),
            bigquery.SchemaField("guest_title", "STRING"),
            bigquery.SchemaField("guest_company", "STRING"),
            bigquery.SchemaField("quotes_extracted", "INT64"),
            bigquery.SchemaField("processing_status", "STRING"),
            bigquery.SchemaField("error_message", "STRING"),
            bigquery.SchemaField("ingested_at", "TIMESTAMP", mode="REQUIRED"),
        ]

        table = bigquery.Table(table_id, schema=schema)
        table.time_partitioning = bigquery.TimePartitioning(
            field="published_at",
            type_=bigquery.TimePartitioningType.MONTH,
        )
        table.clustering_fields = ["podcast_id"]

        try:
            self.client.create_table(table)
            logger.info(f"Created table {table_id}")
        except Exception as e:
            if "Already Exists" in str(e):
                logger.info(f"Table {table_id} already exists")
            else:
                raise

    async def _create_podcast_quotes_table(self):
        """Create podcast_quotes table for extracted speaker-attributed quotes."""
        from google.cloud import bigquery

        table_id = f"{self.config.full_dataset_id}.podcast_quotes"
        schema = [
            bigquery.SchemaField("id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("episode_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("podcast_name", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("episode_title", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("episode_url", "STRING"),
            bigquery.SchemaField("published_at", "TIMESTAMP", mode="REQUIRED"),
            bigquery.SchemaField("quote_text", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("context_summary", "STRING"),
            bigquery.SchemaField("speaker_name", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("speaker_role", "STRING"),
            bigquery.SchemaField("speaker_title", "STRING"),
            bigquery.SchemaField("speaker_company", "STRING"),
            bigquery.SchemaField("themes", "STRING"),  # JSON array
            bigquery.SchemaField("relevance_score", "FLOAT64"),
            bigquery.SchemaField("extraction_model", "STRING"),
            bigquery.SchemaField("extracted_at", "TIMESTAMP", mode="REQUIRED"),
        ]

        table = bigquery.Table(table_id, schema=schema)
        table.time_partitioning = bigquery.TimePartitioning(
            field="published_at",
            type_=bigquery.TimePartitioningType.MONTH,
        )
        table.clustering_fields = ["podcast_name"]

        try:
            self.client.create_table(table)
            logger.info(f"Created table {table_id}")
        except Exception as e:
            if "Already Exists" in str(e):
                logger.info(f"Table {table_id} already exists")
            else:
                raise

    async def store_podcast_episodes(self, episodes: List[Dict[str, Any]]) -> int:
        """Store podcast episode records in BigQuery."""
        if not episodes:
            return 0
        table_id = f"{self.config.full_dataset_id}.podcast_episodes"
        try:
            errors = self.client.insert_rows_json(table_id, episodes)
            if errors:
                logger.error(f"[PODCAST_STORAGE] Episode insert errors: {errors}")
                return len(episodes) - len(errors)
            logger.info(f"[PODCAST_STORAGE] Stored {len(episodes)} episode(s)")
            return len(episodes)
        except Exception as e:
            logger.error(f"[PODCAST_STORAGE] Failed to store episodes: {e}", exc_info=True)
            return 0

    async def store_podcast_quotes(self, quotes: List[Dict[str, Any]]) -> int:
        """Store podcast quote records in BigQuery."""
        if not quotes:
            return 0
        table_id = f"{self.config.full_dataset_id}.podcast_quotes"
        try:
            errors = self.client.insert_rows_json(table_id, quotes)
            if errors:
                logger.error(f"[PODCAST_STORAGE] Quote insert errors: {errors}")
                return len(quotes) - len(errors)
            logger.info(f"[PODCAST_STORAGE] Stored {len(quotes)} quote(s)")
            return len(quotes)
        except Exception as e:
            logger.error(f"[PODCAST_STORAGE] Failed to store quotes: {e}", exc_info=True)
            return 0

    async def check_episode_exists(self, guid: str) -> bool:
        """Check if an episode with this RSS GUID already exists."""
        try:
            query = f"""
                SELECT COUNT(*) as cnt
                FROM `{self.config.full_dataset_id}.podcast_episodes`
                WHERE guid = @guid
            """
            from google.cloud.bigquery import ScalarQueryParameter, QueryJobConfig
            job_config = QueryJobConfig(
                query_parameters=[ScalarQueryParameter("guid", "STRING", guid)]
            )
            result = self.client.query(query, job_config=job_config).result()
            for row in result:
                return row.cnt > 0
            return False
        except Exception as e:
            logger.warning(f"[PODCAST_STORAGE] Episode existence check failed: {e}")
            return False

    async def get_podcast_quotes(
        self,
        search_query: Optional[str] = None,
        themes: Optional[List[str]] = None,
        podcast_name: Optional[str] = None,
        speaker_name: Optional[str] = None,
        days: int = 90,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Query podcast quotes with filters."""
        try:
            conditions = [
                f"published_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {days} DAY)"
            ]
            params = []

            from google.cloud.bigquery import ScalarQueryParameter, QueryJobConfig

            if search_query:
                conditions.append(
                    "(LOWER(quote_text) LIKE @search_pattern "
                    "OR LOWER(context_summary) LIKE @search_pattern "
                    "OR LOWER(speaker_name) LIKE @search_pattern)"
                )
                params.append(ScalarQueryParameter("search_pattern", "STRING", f"%{search_query.lower()}%"))

            if podcast_name:
                conditions.append("LOWER(podcast_name) LIKE @podcast_pattern")
                params.append(ScalarQueryParameter("podcast_pattern", "STRING", f"%{podcast_name.lower()}%"))

            if speaker_name:
                conditions.append("LOWER(speaker_name) LIKE @speaker_pattern")
                params.append(ScalarQueryParameter("speaker_pattern", "STRING", f"%{speaker_name.lower()}%"))

            if themes:
                theme_conditions = []
                for i, theme in enumerate(themes):
                    param_name = f"theme_{i}"
                    theme_conditions.append(f"LOWER(themes) LIKE @{param_name}")
                    params.append(ScalarQueryParameter(param_name, "STRING", f"%{theme.lower()}%"))
                conditions.append(f"({' OR '.join(theme_conditions)})")

            where_clause = " AND ".join(conditions)

            query = f"""
                SELECT *
                FROM `{self.config.full_dataset_id}.podcast_quotes`
                WHERE {where_clause}
                ORDER BY relevance_score DESC, published_at DESC
                LIMIT {limit}
            """

            job_config = QueryJobConfig(query_parameters=params)
            rows = self.client.query(query, job_config=job_config).result()

            results = []
            for row in rows:
                results.append(dict(row))
            return results

        except Exception as e:
            logger.error(f"[PODCAST_STORAGE] Quote query failed: {e}", exc_info=True)
            return []

    # =========================================================================
    # Earnings Quotes (Executive Quote Extraction from Earnings Transcripts)
    # =========================================================================

    async def _create_earnings_quotes_table(self):
        """Create earnings_quotes table for extracted executive insights from earnings calls."""
        from google.cloud import bigquery

        table_id = f"{self.config.full_dataset_id}.earnings_quotes"
        schema = [
            bigquery.SchemaField("quote_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("transcript_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("quote_text", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("context_summary", "STRING"),
            bigquery.SchemaField("speaker_name", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("speaker_role", "STRING"),
            bigquery.SchemaField("speaker_title", "STRING"),
            bigquery.SchemaField("speaker_company", "STRING"),
            bigquery.SchemaField("speaker_firm", "STRING"),
            bigquery.SchemaField("quote_type", "STRING"),
            bigquery.SchemaField("themes", "STRING"),  # JSON array
            bigquery.SchemaField("sentiment", "STRING"),
            bigquery.SchemaField("confidence_level", "STRING"),
            bigquery.SchemaField("companies_mentioned", "STRING"),  # JSON array
            bigquery.SchemaField("brands_mentioned", "STRING"),  # JSON array
            bigquery.SchemaField("metrics_mentioned", "STRING"),  # JSON array
            bigquery.SchemaField("relevance_score", "FLOAT64"),
            bigquery.SchemaField("is_quotable", "BOOLEAN"),
            bigquery.SchemaField("quotability_reason", "STRING"),
            bigquery.SchemaField("business_segment", "STRING"),
            bigquery.SchemaField("ticker", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("company_name", "STRING"),
            bigquery.SchemaField("year", "INTEGER", mode="REQUIRED"),
            bigquery.SchemaField("quarter", "INTEGER", mode="REQUIRED"),
            bigquery.SchemaField("call_date", "STRING"),
            bigquery.SchemaField("call_section", "STRING"),
            bigquery.SchemaField("position_in_section", "INTEGER"),
            bigquery.SchemaField("extracted_at", "TIMESTAMP", mode="REQUIRED"),
            bigquery.SchemaField("extraction_model", "STRING"),
            bigquery.SchemaField("extraction_confidence", "FLOAT64"),
        ]

        table = bigquery.Table(table_id, schema=schema)
        table.time_partitioning = bigquery.TimePartitioning(
            field="extracted_at",
            type_=bigquery.TimePartitioningType.MONTH,
        )
        table.clustering_fields = ["ticker", "quote_type"]

        try:
            self.client.create_table(table)
            logger.info(f"Created table {table_id}")
        except Exception as e:
            if "Already Exists" in str(e):
                logger.info(f"Table {table_id} already exists")
            else:
                raise

    async def store_earnings_quotes(self, quotes: List[Dict[str, Any]]) -> int:
        """Store earnings quote records in BigQuery.
        
        Args:
            quotes: List of quote dicts (from ExtractedEarningsQuote.to_bq_row())
            
        Returns:
            Number of quotes stored successfully
        """
        if not quotes:
            return 0
        table_id = f"{self.config.full_dataset_id}.earnings_quotes"
        try:
            errors = self.client.insert_rows_json(table_id, quotes)
            if errors:
                logger.error(f"[EARNINGS_QUOTES] Insert errors: {errors[:3]}")
                return len(quotes) - len(errors)
            logger.info(f"[EARNINGS_QUOTES] Stored {len(quotes)} quote(s)")
            return len(quotes)
        except Exception as e:
            logger.error(f"[EARNINGS_QUOTES] Failed to store quotes: {e}", exc_info=True)
            return 0

    async def get_earnings_quotes(
        self,
        ticker: Optional[str] = None,
        search_query: Optional[str] = None,
        quote_type: Optional[str] = None,
        themes: Optional[List[str]] = None,
        speaker_role: Optional[str] = None,
        section: Optional[str] = None,
        year: Optional[int] = None,
        quarter: Optional[int] = None,
        quotable_only: bool = False,
        min_relevance: float = 0.0,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Query earnings quotes with flexible filters.
        
        Args:
            ticker: Filter by stock ticker
            search_query: Full-text search on quote_text, context_summary, companies_mentioned
            quote_type: Filter by quote type (guidance, competitive, analyst_pressure, etc.)
            themes: Filter by themes (any match)
            speaker_role: Filter by speaker role (ceo, cfo, analyst, etc.)
            section: Filter by call section (prepared_remarks, qa)
            year: Filter by fiscal year
            quarter: Filter by fiscal quarter
            quotable_only: Only return quotable quotes
            min_relevance: Minimum relevance score (0.0-1.0)
            limit: Max results
            
        Returns:
            List of quote dicts
        """
        try:
            conditions = []
            params = []

            from google.cloud.bigquery import ScalarQueryParameter, QueryJobConfig

            if ticker:
                conditions.append("UPPER(ticker) = @ticker")
                params.append(ScalarQueryParameter("ticker", "STRING", ticker.upper()))

            if search_query:
                conditions.append(
                    "(LOWER(quote_text) LIKE @search_pattern "
                    "OR LOWER(context_summary) LIKE @search_pattern "
                    "OR LOWER(companies_mentioned) LIKE @search_pattern "
                    "OR LOWER(speaker_name) LIKE @search_pattern "
                    "OR LOWER(company_name) LIKE @search_pattern "
                    "OR LOWER(speaker_company) LIKE @search_pattern)"
                )
                params.append(ScalarQueryParameter("search_pattern", "STRING", f"%{search_query.lower()}%"))

            if quote_type:
                conditions.append("quote_type = @quote_type")
                params.append(ScalarQueryParameter("quote_type", "STRING", quote_type.lower()))

            if speaker_role:
                conditions.append("speaker_role = @speaker_role")
                params.append(ScalarQueryParameter("speaker_role", "STRING", speaker_role.lower()))

            if section:
                conditions.append("call_section = @section")
                params.append(ScalarQueryParameter("section", "STRING", section.lower()))

            if year:
                conditions.append("year = @year")
                params.append(ScalarQueryParameter("year", "INT64", year))

            if quarter:
                conditions.append("quarter = @quarter")
                params.append(ScalarQueryParameter("quarter", "INT64", quarter))

            if quotable_only:
                conditions.append("is_quotable = TRUE")

            if min_relevance > 0.0:
                conditions.append("relevance_score >= @min_relevance")
                params.append(ScalarQueryParameter("min_relevance", "FLOAT64", min_relevance))

            if themes:
                theme_conditions = []
                for i, theme in enumerate(themes):
                    param_name = f"theme_{i}"
                    theme_conditions.append(f"LOWER(themes) LIKE @{param_name}")
                    params.append(ScalarQueryParameter(param_name, "STRING", f"%{theme.lower()}%"))
                conditions.append(f"({' OR '.join(theme_conditions)})")

            where_clause = " AND ".join(conditions) if conditions else "1=1"

            query = f"""
                SELECT *
                FROM `{self.config.full_dataset_id}.earnings_quotes`
                WHERE {where_clause}
                ORDER BY relevance_score DESC, year DESC, quarter DESC
                LIMIT {limit}
            """

            job_config = QueryJobConfig(query_parameters=params)
            rows = self.client.query(query, job_config=job_config).result()

            results = []
            for row in rows:
                results.append(dict(row))
            return results

        except Exception as e:
            logger.error(f"[EARNINGS_QUOTES] Query failed: {e}", exc_info=True)
            return []

    async def get_transcripts_for_quote_extraction(
        self,
        limit: int = 50,
        year_min: int = 2025,
        quarter_min: int = 3,
    ) -> List[Dict[str, Any]]:
        """Get earnings transcripts that haven't had quotes extracted yet.
        
        Queries articles with source_type='earnings_transcript' and checks
        which ones don't have entries in the earnings_quotes table yet.
        
        Args:
            limit: Max transcripts to return
            year_min: Minimum year to include (default 2025)
            quarter_min: Minimum quarter for year_min (default Q3)
            
        Returns:
            List of transcript dicts with id, ticker, company_name, year, quarter, content, participants
        """
        try:
            # URL format: earnings://TICKER/YEAR/Q# — parse ticker, year, quarter from URL
            # Title format: "Company Name Q# YEAR Earnings Call" — parse company name
            query = f"""
                WITH existing_extractions AS (
                    SELECT DISTINCT transcript_id
                    FROM `{self.config.full_dataset_id}.earnings_quotes`
                )
                SELECT 
                    a.id,
                    a.title,
                    a.url,
                    a.full_text,
                    a.source_name,
                    a.published_at,
                    a.companies_mentioned
                FROM `{self.config.full_dataset_id}.articles` a
                LEFT JOIN existing_extractions ee ON a.id = ee.transcript_id
                WHERE a.source_type = 'earnings_transcript'
                  AND ee.transcript_id IS NULL
                  AND a.full_text IS NOT NULL
                  AND LENGTH(a.full_text) > 1000
                ORDER BY a.published_at DESC
                LIMIT {limit}
            """
            rows = self.client.query(query).result()

            results = []
            for row in rows:
                row_dict = dict(row)
                
                # Parse ticker, year, quarter from URL (earnings://TICKER/YEAR/Q#)
                url = row_dict.get("url", "")
                ticker = ""
                year = 0
                quarter = 0
                if url.startswith("earnings://"):
                    parts = url.replace("earnings://", "").split("/")
                    if len(parts) >= 1:
                        ticker = parts[0]
                    if len(parts) >= 2:
                        try:
                            year = int(parts[1])
                        except (ValueError, TypeError):
                            pass
                    if len(parts) >= 3:
                        try:
                            quarter = int(parts[2].replace("Q", ""))
                        except (ValueError, TypeError):
                            pass
                elif "financialmodelingprep.com" in url:
                    # FMP URL format: .../earning_call_transcript/TICKER?quarter=Q&year=Y
                    import re as _re
                    ticker_match = _re.search(r'/earning_call_transcript/([^?]+)', url)
                    if ticker_match:
                        ticker = ticker_match.group(1)
                    quarter_match = _re.search(r'quarter=(\d+)', url)
                    if quarter_match:
                        quarter = int(quarter_match.group(1))
                    year_match = _re.search(r'year=(\d+)', url)
                    if year_match:
                        year = int(year_match.group(1))
                
                # Parse company name from title (e.g., "Rocket Lab Q3 2025 Earnings Call")
                title = row_dict.get("title", "")
                company_name = title.replace(f"Q{quarter} {year} Earnings Call", "").strip() if quarter and year else title
                
                # Fallback: try companies_mentioned
                if not company_name or company_name == title:
                    companies_str = row_dict.get("companies_mentioned", "[]")
                    try:
                        companies = json.loads(companies_str) if isinstance(companies_str, str) else companies_str
                        if companies:
                            company_name = companies[0]
                    except (json.JSONDecodeError, TypeError):
                        pass

                results.append({
                    "id": row_dict.get("id"),
                    "title": title,
                    "content": row_dict.get("full_text", ""),
                    "ticker": ticker,
                    "year": year,
                    "quarter": quarter,
                    "company_name": company_name,
                    "participants": [],  # Not stored in articles table; extractor handles transcript parsing
                    "published_at": row_dict.get("published_at"),
                })
            
            logger.info(f"[EARNINGS_QUOTES] Found {len(results)} transcripts pending quote extraction")
            return results

        except Exception as e:
            logger.error(f"[EARNINGS_QUOTES] Failed to get pending transcripts: {e}", exc_info=True)
            return []

    async def get_earnings_quote_stats(self) -> Dict[str, Any]:
        """Get statistics about extracted earnings quotes."""
        try:
            query = f"""
                SELECT 
                    COUNT(*) as total_quotes,
                    COUNT(DISTINCT transcript_id) as transcripts_processed,
                    COUNT(DISTINCT ticker) as unique_tickers,
                    COUNTIF(is_quotable) as quotable_quotes,
                    AVG(relevance_score) as avg_relevance,
                    MIN(extracted_at) as earliest_extraction,
                    MAX(extracted_at) as latest_extraction
                FROM `{self.config.full_dataset_id}.earnings_quotes`
            """
            rows = list(self.client.query(query).result())
            if rows:
                row = dict(rows[0])
                return row
            return {}
        except Exception as e:
            logger.error(f"[EARNINGS_QUOTES] Stats query failed: {e}")
            return {}

    # =========================================================================
    # SEC Filings (Dedicated filing storage with proper metadata)
    # =========================================================================

    async def _create_sec_filings_table(self):
        """Create sec_filings table for storing SEC filing data with full metadata.
        
        This table stores the actual SEC filing content (sections, full_text) alongside
        proper metadata (ticker, CIK, form_type) that was previously lost when filings
        were stored in the generic articles table. Used as the source for nugget extraction.
        """
        from google.cloud import bigquery

        table_id = f"{self.config.full_dataset_id}.sec_filings"
        schema = [
            bigquery.SchemaField("filing_id", "STRING", mode="REQUIRED"),  # accession number
            bigquery.SchemaField("company_id", "STRING"),
            bigquery.SchemaField("ticker", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("cik", "STRING"),
            bigquery.SchemaField("company_name", "STRING"),
            bigquery.SchemaField("form_type", "STRING", mode="REQUIRED"),  # 10-K, 10-Q, 8-K
            bigquery.SchemaField("filed_at", "TIMESTAMP"),
            bigquery.SchemaField("filing_url", "STRING"),
            bigquery.SchemaField("sections_json", "STRING"),  # JSON dict of section_name -> content
            bigquery.SchemaField("full_text", "STRING"),  # For 8-K or fallback
            bigquery.SchemaField("collected_at", "TIMESTAMP", mode="REQUIRED"),
        ]

        table = bigquery.Table(table_id, schema=schema)
        table.time_partitioning = bigquery.TimePartitioning(
            field="filed_at",
            type_=bigquery.TimePartitioningType.MONTH,
        )
        table.clustering_fields = ["ticker", "form_type"]

        try:
            self.client.create_table(table)
            logger.info(f"Created table {table_id}")
        except Exception as e:
            if "Already Exists" in str(e):
                logger.info(f"Table {table_id} already exists")
            else:
                raise

    async def store_sec_filings(self, filings: List[Dict[str, Any]]) -> int:
        """Store SEC filing records in BigQuery.
        
        Args:
            filings: List of filing dicts with keys matching sec_filings schema.
                     Expected keys: filing_id, company_id, ticker, cik, company_name,
                     form_type, filed_at, filing_url, sections_json, full_text, collected_at
        
        Returns:
            Number of filings stored successfully
        """
        if not filings:
            return 0
        table_id = f"{self.config.full_dataset_id}.sec_filings"
        try:
            errors = self.client.insert_rows_json(table_id, filings)
            if errors:
                logger.error(f"[SEC_FILINGS] Insert errors: {errors[:3]}")
                return len(filings) - len(errors)
            logger.info(f"[SEC_FILINGS] Stored {len(filings)} filing(s)")
            return len(filings)
        except Exception as e:
            logger.error(f"[SEC_FILINGS] Failed to store filings: {e}", exc_info=True)
            return 0

    async def get_sec_filing_ids(self) -> set:
        """Get set of all filing_ids already stored in sec_filings table.
        
        Used to skip duplicates during backfill/ingestion.
        """
        try:
            query = f"""
                SELECT DISTINCT filing_id
                FROM `{self.config.full_dataset_id}.sec_filings`
            """
            rows = self.client.query(query).result()
            return {row.filing_id for row in rows}
        except Exception as e:
            logger.error(f"[SEC_FILINGS] Failed to get existing filing IDs: {e}")
            return set()

    async def get_sec_filings_for_nugget_extraction(
        self,
        limit: int = 50,
        include_already_extracted: bool = False,
    ) -> List[Dict[str, Any]]:
        """Get SEC filings from the dedicated sec_filings table for nugget extraction.
        
        Args:
            limit: Max filings to return
            include_already_extracted: If True, return all filings (for re-extraction).
                                       If False, only return filings without existing nuggets.
        
        Returns:
            List of filing dicts ready for SecNuggetExtractor.extract_nuggets()
        """
        try:
            if include_already_extracted:
                query = f"""
                    SELECT
                        filing_id, ticker, cik, company_name, company_id,
                        form_type, filed_at, filing_url,
                        sections_json, full_text
                    FROM `{self.config.full_dataset_id}.sec_filings`
                    WHERE (full_text IS NOT NULL AND LENGTH(full_text) > 1000)
                       OR (sections_json IS NOT NULL AND LENGTH(sections_json) > 100)
                    ORDER BY filed_at DESC
                    LIMIT {limit}
                """
            else:
                query = f"""
                    WITH existing_extractions AS (
                        SELECT DISTINCT filing_id
                        FROM `{self.config.full_dataset_id}.sec_filing_nuggets`
                    )
                    SELECT
                        sf.filing_id, sf.ticker, sf.cik, sf.company_name, sf.company_id,
                        sf.form_type, sf.filed_at, sf.filing_url,
                        sf.sections_json, sf.full_text
                    FROM `{self.config.full_dataset_id}.sec_filings` sf
                    LEFT JOIN existing_extractions ee ON sf.filing_id = ee.filing_id
                    WHERE ee.filing_id IS NULL
                      AND ((sf.full_text IS NOT NULL AND LENGTH(sf.full_text) > 1000)
                           OR (sf.sections_json IS NOT NULL AND LENGTH(sf.sections_json) > 100))
                    ORDER BY sf.filed_at DESC
                    LIMIT {limit}
                """
            
            rows = self.client.query(query).result()
            results = []
            for row in rows:
                row_dict = dict(row)
                
                # Parse sections_json back to dict
                sections = {}
                sections_str = row_dict.get("sections_json", "{}")
                if sections_str:
                    try:
                        sections = json.loads(sections_str) if isinstance(sections_str, str) else (sections_str or {})
                    except (json.JSONDecodeError, TypeError):
                        sections = {}
                
                # Build filing_data dict compatible with SecNuggetExtractor.extract_nuggets()
                filing_date = row_dict.get("filed_at")
                if filing_date:
                    if hasattr(filing_date, 'isoformat'):
                        filing_date = filing_date.isoformat()
                    else:
                        filing_date = str(filing_date)
                
                results.append({
                    "id": row_dict.get("filing_id"),
                    "filing_id": row_dict.get("filing_id"),
                    "ticker": row_dict.get("ticker", ""),
                    "company_name": row_dict.get("company_name", ""),
                    "cik": row_dict.get("cik", ""),
                    "filing_type": row_dict.get("form_type", "10-K"),
                    "form_type": row_dict.get("form_type", "10-K"),
                    "sections": sections,
                    "sections_json": row_dict.get("sections_json", "{}"),
                    "full_text": row_dict.get("full_text", ""),
                    "filing_date": filing_date,
                    "url": row_dict.get("filing_url", ""),
                })
            
            logger.info(f"[SEC_FILINGS] Found {len(results)} filings for nugget extraction (include_extracted={include_already_extracted})")
            return results
        
        except Exception as e:
            logger.error(f"[SEC_FILINGS] Failed to get filings for extraction: {e}", exc_info=True)
            return []

    async def get_sec_filing_stats(self) -> Dict[str, Any]:
        """Get statistics about stored SEC filings."""
        try:
            query = f"""
                SELECT
                    COUNT(*) as total_filings,
                    COUNT(DISTINCT ticker) as unique_tickers,
                    COUNT(DISTINCT form_type) as unique_form_types,
                    MIN(filed_at) as earliest_filing,
                    MAX(filed_at) as latest_filing,
                    COUNTIF(sections_json IS NOT NULL AND LENGTH(sections_json) > 10) as filings_with_sections,
                    COUNTIF(full_text IS NOT NULL AND LENGTH(full_text) > 100) as filings_with_full_text
                FROM `{self.config.full_dataset_id}.sec_filings`
            """
            rows = list(self.client.query(query).result())
            if rows:
                return dict(rows[0])
            return {}
        except Exception as e:
            logger.error(f"[SEC_FILINGS] Stats query failed: {e}")
            return {}

    # =========================================================================
    # SEC Filing Nuggets (Strategic Insight Extraction from SEC Filings)
    # =========================================================================

    async def _create_sec_filing_nuggets_table(self):
        """Create sec_filing_nuggets table for extracted strategic insights from SEC filings."""
        from google.cloud import bigquery

        table_id = f"{self.config.full_dataset_id}.sec_filing_nuggets"
        schema = [
            bigquery.SchemaField("nugget_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("filing_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("nugget_text", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("context_text", "STRING"),
            bigquery.SchemaField("filing_type", "STRING"),
            bigquery.SchemaField("section", "STRING"),
            bigquery.SchemaField("nugget_type", "STRING"),
            bigquery.SchemaField("themes", "STRING"),  # JSON array
            bigquery.SchemaField("signal_strength", "STRING"),
            bigquery.SchemaField("companies_mentioned", "STRING"),  # JSON array
            bigquery.SchemaField("brands_mentioned", "STRING"),  # JSON array
            bigquery.SchemaField("competitors_named", "STRING"),  # JSON array
            bigquery.SchemaField("regulators_mentioned", "STRING"),  # JSON array
            bigquery.SchemaField("risk_level", "STRING"),
            bigquery.SchemaField("is_new_disclosure", "BOOLEAN"),
            bigquery.SchemaField("strategic_relevance", "STRING"),
            bigquery.SchemaField("relevance_score", "FLOAT64"),
            bigquery.SchemaField("is_actionable", "BOOLEAN"),
            bigquery.SchemaField("actionability_reason", "STRING"),
            bigquery.SchemaField("business_segment", "STRING"),
            bigquery.SchemaField("ticker", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("company_name", "STRING"),
            bigquery.SchemaField("cik", "STRING"),
            bigquery.SchemaField("fiscal_year", "INTEGER", mode="REQUIRED"),
            bigquery.SchemaField("fiscal_quarter", "INTEGER"),
            bigquery.SchemaField("filing_date", "STRING"),
            bigquery.SchemaField("extracted_at", "TIMESTAMP", mode="REQUIRED"),
            bigquery.SchemaField("extraction_model", "STRING"),
        ]

        table = bigquery.Table(table_id, schema=schema)
        table.time_partitioning = bigquery.TimePartitioning(
            field="extracted_at",
            type_=bigquery.TimePartitioningType.MONTH,
        )
        table.clustering_fields = ["ticker", "nugget_type"]

        try:
            self.client.create_table(table)
            logger.info(f"Created table {table_id}")
        except Exception as e:
            if "Already Exists" in str(e):
                logger.info(f"Table {table_id} already exists")
            else:
                raise

    # =========================================================================
    # Eval Suite Tables
    # =========================================================================

    async def _create_llm_token_usage_table(self):
        """Create llm_token_usage table for tracking LLM costs across the platform."""
        from google.cloud import bigquery

        table_id = f"{self.config.full_dataset_id}.llm_token_usage"
        schema = [
            bigquery.SchemaField("id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("model", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("provider", "STRING"),  # 'anthropic' or 'openai'
            bigquery.SchemaField("input_tokens", "INT64"),
            bigquery.SchemaField("output_tokens", "INT64"),
            bigquery.SchemaField("total_tokens", "INT64"),
            bigquery.SchemaField("estimated_cost_usd", "FLOAT64"),
            bigquery.SchemaField("caller", "STRING"),  # module that made the call
            bigquery.SchemaField("created_at", "TIMESTAMP", mode="REQUIRED"),
        ]

        table = bigquery.Table(table_id, schema=schema)
        table.time_partitioning = bigquery.TimePartitioning(
            field="created_at",
            type_=bigquery.TimePartitioningType.MONTH,
        )
        table.clustering_fields = ["caller", "model"]

        try:
            self.client.create_table(table)
            logger.info(f"Created table {table_id}")
        except Exception as e:
            if "Already Exists" in str(e):
                logger.info(f"Table {table_id} already exists")
            else:
                raise

    async def _create_eval_results_table(self):
        """Create eval_results table for LLM-as-judge evaluation scores."""
        from google.cloud import bigquery

        table_id = f"{self.config.full_dataset_id}.eval_results"
        schema = [
            bigquery.SchemaField("id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("report_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("report_type", "STRING"),  # 'deep_research' | 'weekly_briefing'
            bigquery.SchemaField("eval_model", "STRING"),
            bigquery.SchemaField("factual_grounding_score", "FLOAT64"),
            bigquery.SchemaField("factual_grounding_reasoning", "STRING"),
            bigquery.SchemaField("coherence_score", "FLOAT64"),
            bigquery.SchemaField("coherence_reasoning", "STRING"),
            bigquery.SchemaField("actionability_score", "FLOAT64"),
            bigquery.SchemaField("actionability_reasoning", "STRING"),
            bigquery.SchemaField("overall_score", "FLOAT64"),
            bigquery.SchemaField("overall_reasoning", "STRING"),
            bigquery.SchemaField("eval_time_seconds", "FLOAT64"),
            bigquery.SchemaField("created_at", "TIMESTAMP", mode="REQUIRED"),
        ]

        table = bigquery.Table(table_id, schema=schema)
        table.time_partitioning = bigquery.TimePartitioning(
            field="created_at",
            type_=bigquery.TimePartitioningType.MONTH,
        )
        table.clustering_fields = ["report_type"]

        try:
            self.client.create_table(table)
            logger.info(f"Created table {table_id}")
        except Exception as e:
            if "Already Exists" in str(e):
                logger.info(f"Table {table_id} already exists")
            else:
                raise

    async def _create_user_feedback_table(self):
        """Create user_feedback table for thumbs up/down on reports."""
        from google.cloud import bigquery

        table_id = f"{self.config.full_dataset_id}.user_feedback"
        schema = [
            bigquery.SchemaField("id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("report_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("report_type", "STRING", mode="REQUIRED"),  # 'deep_research' | 'weekly_briefing'
            bigquery.SchemaField("rating", "STRING", mode="REQUIRED"),  # 'positive' | 'negative'
            bigquery.SchemaField("comment", "STRING"),
            bigquery.SchemaField("section_id", "STRING"),
            bigquery.SchemaField("created_at", "TIMESTAMP", mode="REQUIRED"),
        ]

        table = bigquery.Table(table_id, schema=schema)
        table.time_partitioning = bigquery.TimePartitioning(
            field="created_at",
            type_=bigquery.TimePartitioningType.MONTH,
        )
        table.clustering_fields = ["report_type"]

        try:
            self.client.create_table(table)
            logger.info(f"Created table {table_id}")
        except Exception as e:
            if "Already Exists" in str(e):
                logger.info(f"Table {table_id} already exists")
            else:
                raise

    async def store_sec_filing_nuggets(self, nuggets: List[Dict[str, Any]]) -> int:
        """Store SEC filing nugget records in BigQuery.

        Args:
            nuggets: List of nugget dicts (from ExtractedSecNugget.to_bq_row())

        Returns:
            Number of nuggets stored successfully
        """
        if not nuggets:
            return 0
        table_id = f"{self.config.full_dataset_id}.sec_filing_nuggets"
        try:
            errors = self.client.insert_rows_json(table_id, nuggets)
            if errors:
                logger.error(f"[SEC_NUGGETS] Insert errors: {errors[:3]}")
                return len(nuggets) - len(errors)
            logger.info(f"[SEC_NUGGETS] Stored {len(nuggets)} nugget(s)")
            return len(nuggets)
        except Exception as e:
            logger.error(f"[SEC_NUGGETS] Failed to store nuggets: {e}", exc_info=True)
            return 0

    async def get_sec_filing_nuggets(
        self,
        ticker: Optional[str] = None,
        search_query: Optional[str] = None,
        nugget_type: Optional[str] = None,
        themes: Optional[List[str]] = None,
        section: Optional[str] = None,
        signal_strength: Optional[str] = None,
        fiscal_year: Optional[int] = None,
        actionable_only: bool = False,
        new_disclosures_only: bool = False,
        min_relevance: float = 0.0,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Query SEC filing nuggets with flexible filters.

        Args:
            ticker: Filter by stock ticker
            search_query: Full-text search on nugget_text, companies_mentioned, competitors_named
            nugget_type: Filter by nugget type (competitive_disclosure, risk_admission, etc.)
            themes: Filter by themes (any match)
            section: Filter by filing section (risk_factors, mda, etc.)
            signal_strength: Filter by signal strength (explicit, new, buried, etc.)
            fiscal_year: Filter by fiscal year
            actionable_only: Only return actionable nuggets
            new_disclosures_only: Only return new disclosures
            min_relevance: Minimum relevance score (0.0-1.0)
            limit: Max results

        Returns:
            List of nugget dicts
        """
        try:
            conditions = []
            params = []

            from google.cloud.bigquery import ScalarQueryParameter, QueryJobConfig

            if ticker:
                conditions.append("UPPER(ticker) = @ticker")
                params.append(ScalarQueryParameter("ticker", "STRING", ticker.upper()))

            if search_query:
                conditions.append(
                    "(LOWER(nugget_text) LIKE @search_pattern "
                    "OR LOWER(companies_mentioned) LIKE @search_pattern "
                    "OR LOWER(competitors_named) LIKE @search_pattern "
                    "OR LOWER(brands_mentioned) LIKE @search_pattern "
                    "OR LOWER(company_name) LIKE @search_pattern)"
                )
                params.append(ScalarQueryParameter("search_pattern", "STRING", f"%{search_query.lower()}%"))

            if nugget_type:
                conditions.append("nugget_type = @nugget_type")
                params.append(ScalarQueryParameter("nugget_type", "STRING", nugget_type.lower()))

            if section:
                conditions.append("section = @section")
                params.append(ScalarQueryParameter("section", "STRING", section.lower()))

            if signal_strength:
                conditions.append("signal_strength = @signal_strength")
                params.append(ScalarQueryParameter("signal_strength", "STRING", signal_strength.lower()))

            if fiscal_year:
                conditions.append("fiscal_year = @fiscal_year")
                params.append(ScalarQueryParameter("fiscal_year", "INT64", fiscal_year))

            if actionable_only:
                conditions.append("is_actionable = TRUE")

            if new_disclosures_only:
                conditions.append("is_new_disclosure = TRUE")

            if min_relevance > 0.0:
                conditions.append("relevance_score >= @min_relevance")
                params.append(ScalarQueryParameter("min_relevance", "FLOAT64", min_relevance))

            if themes:
                theme_conditions = []
                for i, theme in enumerate(themes):
                    param_name = f"theme_{i}"
                    theme_conditions.append(f"LOWER(themes) LIKE @{param_name}")
                    params.append(ScalarQueryParameter(param_name, "STRING", f"%{theme.lower()}%"))
                conditions.append(f"({' OR '.join(theme_conditions)})")

            where_clause = " AND ".join(conditions) if conditions else "1=1"

            query = f"""
                SELECT *
                FROM `{self.config.full_dataset_id}.sec_filing_nuggets`
                WHERE {where_clause}
                ORDER BY relevance_score DESC, fiscal_year DESC
                LIMIT {limit}
            """

            job_config = QueryJobConfig(query_parameters=params)
            rows = self.client.query(query, job_config=job_config).result()

            results = []
            for row in rows:
                results.append(dict(row))
            return results

        except Exception as e:
            logger.error(f"[SEC_NUGGETS] Query failed: {e}", exc_info=True)
            return []

    async def get_filings_for_nugget_extraction(
        self,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get SEC filings that haven't had nuggets extracted yet.
        
        DEPRECATED: Redirects to get_sec_filings_for_nugget_extraction() which reads
        from the dedicated sec_filings table instead of the articles table.
        """
        return await self.get_sec_filings_for_nugget_extraction(limit=limit, include_already_extracted=False)

    async def get_all_sec_filings_for_extraction(
        self,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        """Get ALL SEC filings for re-extraction.
        
        DEPRECATED: Redirects to get_sec_filings_for_nugget_extraction() which reads
        from the dedicated sec_filings table instead of the articles table.
        """
        return await self.get_sec_filings_for_nugget_extraction(limit=limit, include_already_extracted=True)

    async def delete_all_sec_filing_nuggets(self) -> int:
        """Delete ALL rows from sec_filing_nuggets table for re-extraction.

        Uses DML DELETE statement. Returns number of rows deleted.
        """
        try:
            query = f"""
                DELETE FROM `{self.config.full_dataset_id}.sec_filing_nuggets`
                WHERE TRUE
            """
            result = self.client.query(query).result()
            deleted = result.num_dml_affected_rows or 0
            logger.info(f"[SEC_NUGGETS] Deleted {deleted} existing nuggets for re-extraction")
            return deleted
        except Exception as e:
            logger.error(f"[SEC_NUGGETS] Failed to delete nuggets: {e}", exc_info=True)
            return 0

    async def get_sec_filing_nugget_stats(self) -> Dict[str, Any]:
        """Get statistics about extracted SEC filing nuggets."""
        try:
            query = f"""
                SELECT
                    COUNT(*) as total_nuggets,
                    COUNT(DISTINCT filing_id) as filings_processed,
                    COUNT(DISTINCT ticker) as unique_tickers,
                    COUNTIF(is_actionable) as actionable_nuggets,
                    COUNTIF(is_new_disclosure) as new_disclosures,
                    AVG(relevance_score) as avg_relevance,
                    MIN(extracted_at) as earliest_extraction,
                    MAX(extracted_at) as latest_extraction
                FROM `{self.config.full_dataset_id}.sec_filing_nuggets`
            """
            rows = list(self.client.query(query).result())
            if rows:
                return dict(rows[0])
            return {}
        except Exception as e:
            logger.error(f"[SEC_NUGGETS] Stats query failed: {e}")
            return {}

def get_data_storage() -> DataStorageInterface:
    """
    Get appropriate data storage backend.
    
    With hardcoded production defaults, this should ALWAYS return BigQueryDataStorage.
    LocalDataStorage (SQLite) should never be used in production.
    """
    logger.info(f"GCP Config: project_id={gcp_config.project_id}, bucket={gcp_config.bucket_name}, is_configured={gcp_config.is_configured}")
    
    if gcp_config.is_configured:
        logger.info("✅ Using BigQuery storage (GCP configured)")
        return BigQueryDataStorage(gcp_config)
    else:
        # This should NEVER happen with hardcoded defaults
        logger.critical("🚨 CRITICAL: Using local SQLite storage - DATA WILL NOT BE IN BIGQUERY!")
        logger.critical(f"🚨 GCP Config check failed: project_id='{gcp_config.project_id}', bucket='{gcp_config.bucket_name}'")
        return LocalDataStorage()


# Singleton instance
_storage_instance: Optional[DataStorageInterface] = None


async def get_storage() -> DataStorageInterface:
    """Get or create the storage singleton."""
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = get_data_storage()
        await _storage_instance.initialize()
        # Log storage type for verification
        storage_type = type(_storage_instance).__name__
        logger.info(f"Storage initialized: {storage_type}")
    return _storage_instance
