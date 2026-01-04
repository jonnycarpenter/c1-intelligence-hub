"""
SQLite Database Layer for Corpus Storage
=========================================

Handles storage and retrieval of:
- Corpus items (ingested content)
- Digests (pre-computed summaries)
- Ingestion statistics
- Entity tracking

Uses aiosqlite for async operations.
"""

import os
import json
import sqlite3
import aiosqlite
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from pathlib import Path

from app.models.corpus import (
    CorpusItem,
    ContentSource,
    EntityMention,
    ContentCategory,
    Priority,
    Industry,
    Digest,
    DigestItem,
    DigestStats,
    IngestionStats,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Database path - configurable via environment for Cloud Run with GCS mount
DB_DIR = Path(os.getenv("DATA_DIR", str(Path(__file__).parent.parent.parent / "data")))
DB_PATH = Path(os.getenv("SQLITE_DB_PATH", str(DB_DIR / "c1_corpus.db")))


class Database:
    """
    SQLite database for corpus storage.
    
    Provides async methods for:
    - Adding/querying corpus items
    - Managing digests
    - Deduplication checking
    - Entity management
    """
    
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._initialized = False
    
    async def initialize(self):
        """Initialize database and create tables."""
        if self._initialized:
            return
        
        # Ensure data directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        async with aiosqlite.connect(self.db_path) as db:
            await self._create_tables(db)
            await db.commit()
        
        self._initialized = True
        logger.info(f"Database initialized at {self.db_path}")
    
    async def _create_tables(self, db: aiosqlite.Connection):
        """Create database tables."""
        
        # Corpus items table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS corpus_items (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                summary TEXT,
                full_text TEXT,
                url TEXT UNIQUE,
                
                -- Source
                source_name TEXT,
                source_url TEXT,
                source_type TEXT,
                
                -- Classification
                primary_category TEXT,
                categories TEXT,  -- JSON array
                industries TEXT,  -- JSON array
                priority TEXT,
                relevance_score REAL,
                
                -- Entities
                entity_mentions TEXT,  -- JSON array
                companies_mentioned TEXT,  -- JSON array
                materials_mentioned TEXT,  -- JSON array
                
                -- Metadata
                sentiment TEXT,
                confidence REAL,
                content_hash TEXT,
                
                -- Timestamps
                published_at TEXT,
                ingested_at TEXT,
                
                -- Indexes
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes for common queries
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_corpus_published 
            ON corpus_items(published_at DESC)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_corpus_priority 
            ON corpus_items(priority)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_corpus_category 
            ON corpus_items(primary_category)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_corpus_url 
            ON corpus_items(url)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_corpus_hash 
            ON corpus_items(content_hash)
        """)
        
        # Digests table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS digests (
                id TEXT PRIMARY KEY,
                period_start TEXT,
                period_end TEXT,
                hours_covered INTEGER,
                executive_summary TEXT,
                items TEXT,  -- JSON array
                stats TEXT,  -- JSON object
                generated_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Ingestion stats table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS ingestion_runs (
                id TEXT PRIMARY KEY,
                started_at TEXT,
                completed_at TEXT,
                status TEXT,
                rss_articles_fetched INTEGER DEFAULT 0,
                fmp_articles_fetched INTEGER DEFAULT 0,
                articles_enriched INTEGER DEFAULT 0,
                articles_classified INTEGER DEFAULT 0,
                duplicates_skipped INTEGER DEFAULT 0,
                articles_stored INTEGER DEFAULT 0,
                errors TEXT,  -- JSON array
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # URL cache for deduplication
        await db.execute("""
            CREATE TABLE IF NOT EXISTS url_cache (
                url_normalized TEXT PRIMARY KEY,
                corpus_item_id TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Briefing summaries table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS briefing_summaries (
                id TEXT PRIMARY KEY,
                category TEXT,
                headline TEXT,
                summary TEXT,
                key_insights TEXT, -- JSON array
                trend_signal TEXT,
                attention_flag TEXT,
                attention_reason TEXT,
                article_ids TEXT, -- JSON array
                period_start TEXT,
                period_end TEXT,
                generated_at TEXT,
                model TEXT
            )
        """)
        
        # Index for latest briefings
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_briefing_latest 
            ON briefing_summaries(category, generated_at DESC)
        """)
        
        # Weekly executive briefings table (new dynamic section format)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS weekly_briefings (
                id TEXT PRIMARY KEY,
                briefing_type TEXT,
                briefing_title TEXT,
                sections TEXT, -- JSON array of sections
                all_companies_mentioned TEXT, -- JSON array with logos
                key_topics_this_week TEXT, -- JSON array
                overall_trend TEXT,
                period_start TEXT,
                period_end TEXT,
                generated_at TEXT,
                model TEXT,
                article_count INTEGER,
                article_ids TEXT, -- JSON array
                quarter TEXT,
                week_of_year INTEGER
            )
        """)
        
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_weekly_briefing_latest 
            ON weekly_briefings(generated_at DESC)
        """)
        
        # Ad hoc briefings table (user-generated quick briefings)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS adhoc_briefings (
                id TEXT PRIMARY KEY,
                question TEXT NOT NULL,
                answer TEXT,
                sources_used TEXT, -- JSON array
                confidence TEXT,
                suggest_deep_research INTEGER,
                related_topics TEXT, -- JSON array
                context_used TEXT, -- JSON object
                search_results_count INTEGER,
                follow_up_count INTEGER,
                generated_at TEXT,
                model TEXT,
                user_id TEXT
            )
        """)
        
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_adhoc_briefing_latest 
            ON adhoc_briefings(generated_at DESC)
        """)
        
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_adhoc_briefing_user 
            ON adhoc_briefings(user_id, generated_at DESC)
        """)
        
        # Pre-briefings table (intermediate Agent 1 output)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS pre_briefings (
                id TEXT PRIMARY KEY,
                briefing_type TEXT,
                data TEXT, -- JSON structure with raw interpretations
                period_start TEXT,
                period_end TEXT,
                generated_at TEXT,
                model TEXT,
                article_count INTEGER,
                article_ids TEXT -- JSON array
            )
        """)
        
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_pre_briefing_latest 
            ON pre_briefings(generated_at DESC)
        """)
    
    # ========================================================================
    # Corpus Item Operations
    # ========================================================================
    
    async def add_corpus_item(self, item: CorpusItem) -> str:
        """Add a corpus item to the database."""
        await self.initialize()
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO corpus_items (
                    id, title, summary, full_text, url,
                    source_name, source_url, source_type,
                    primary_category, categories, industries, priority, relevance_score,
                    entity_mentions, companies_mentioned, materials_mentioned,
                    sentiment, confidence, content_hash,
                    published_at, ingested_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                item.id,
                item.title,
                item.summary,
                item.full_text,
                item.url,
                item.source.name,
                item.source.url,
                item.source.source_type,
                item.primary_category.value,
                json.dumps([c.value for c in item.categories]),
                json.dumps([i.value for i in item.industries]),
                item.priority.value,
                item.relevance_score,
                json.dumps([m.model_dump() for m in item.entity_mentions]),
                json.dumps(item.companies_mentioned),
                json.dumps(item.materials_mentioned),
                item.sentiment,
                item.confidence,
                item.content_hash,
                item.published_at.isoformat() if item.published_at else None,
                item.ingested_at.isoformat() if item.ingested_at else None,
            ))
            
            # Update URL cache
            await db.execute("""
                INSERT OR REPLACE INTO url_cache (url_normalized, corpus_item_id)
                VALUES (?, ?)
            """, (self._normalize_url(item.url), item.id))
            
            await db.commit()
        
        return item.id
    
    async def get_corpus_item(self, item_id: str) -> Optional[CorpusItem]:
        """Get a corpus item by ID."""
        await self.initialize()
        
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM corpus_items WHERE id = ?", (item_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return self._row_to_corpus_item(row)
        return None
    
    async def query_corpus(
        self,
        hours: Optional[int] = None,
        categories: Optional[List[ContentCategory]] = None,
        priorities: Optional[List[Priority]] = None,
        industries: Optional[List[Industry]] = None,
        entity_name: Optional[str] = None,
        search_text: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[CorpusItem]:
        """
        Query corpus items with filters.
        
        Args:
            hours: Only items from last N hours
            categories: Filter by categories
            priorities: Filter by priorities
            industries: Filter by industries
            entity_name: Filter by entity mention
            search_text: Full-text search in title/summary
            limit: Max items to return
            offset: Pagination offset
        """
        await self.initialize()
        
        conditions = []
        params = []
        
        if hours:
            cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
            conditions.append("published_at >= ?")
            params.append(cutoff)
        
        if categories:
            cat_values = [c.value for c in categories]
            placeholders = ",".join(["?" for _ in cat_values])
            conditions.append(f"primary_category IN ({placeholders})")
            params.extend(cat_values)
        
        if priorities:
            pri_values = [p.value for p in priorities]
            placeholders = ",".join(["?" for _ in pri_values])
            conditions.append(f"priority IN ({placeholders})")
            params.extend(pri_values)
        
        if entity_name:
            conditions.append("(companies_mentioned LIKE ? OR entity_mentions LIKE ?)")
            params.append(f"%{entity_name}%")
            params.append(f"%{entity_name}%")
        
        if search_text:
            conditions.append("(title LIKE ? OR summary LIKE ?)")
            params.append(f"%{search_text}%")
            params.append(f"%{search_text}%")
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        query = f"""
            SELECT * FROM corpus_items 
            WHERE {where_clause}
            ORDER BY published_at DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])
        
        items = []
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(query, params) as cursor:
                async for row in cursor:
                    items.append(self._row_to_corpus_item(row))
        
        return items
    
    async def get_articles_by_ids(self, article_ids: List[str]) -> List[Dict[str, Any]]:
        """Get articles by their IDs."""
        if not article_ids:
            return []
            
        await self.initialize()
        
        placeholders = ",".join("?" * len(article_ids))
        query = f"SELECT * FROM corpus_items WHERE id IN ({placeholders})"
        
        articles = []
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(query, article_ids) as cursor:
                async for row in cursor:
                    # Basic conversion to dict, might need more detail for full CorpusItem
                    articles.append(dict(row))
        return articles
    
    async def get_corpus_stats(self) -> Dict[str, Any]:
        """Get corpus statistics."""
        await self.initialize()
        
        async with aiosqlite.connect(self.db_path) as db:
            # Total count
            async with db.execute("SELECT COUNT(*) FROM corpus_items") as cursor:
                total = (await cursor.fetchone())[0]
            
            # By category
            async with db.execute("""
                SELECT primary_category, COUNT(*) 
                FROM corpus_items 
                GROUP BY primary_category
            """) as cursor:
                by_category = {row[0]: row[1] async for row in cursor}
            
            # By priority
            async with db.execute("""
                SELECT priority, COUNT(*) 
                FROM corpus_items 
                GROUP BY priority
            """) as cursor:
                by_priority = {row[0]: row[1] async for row in cursor}
            
            # Recent (last 24h)
            cutoff = (datetime.utcnow() - timedelta(hours=24)).isoformat()
            async with db.execute(
                "SELECT COUNT(*) FROM corpus_items WHERE published_at >= ?",
                (cutoff,)
            ) as cursor:
                last_24h = (await cursor.fetchone())[0]
        
        return {
            "total_items": total,
            "by_category": by_category,
            "by_priority": by_priority,
            "last_24h": last_24h,
        }
    
    # ========================================================================
    # Deduplication
    # ========================================================================
    
    async def check_duplicate(self, url: str) -> Optional[str]:
        """Check if URL already exists. Returns corpus_item_id if duplicate."""
        await self.initialize()
        
        normalized = self._normalize_url(url)
        
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT corpus_item_id FROM url_cache WHERE url_normalized = ?",
                (normalized,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return row[0]
        return None
    
    async def check_content_hash(self, content_hash: str) -> Optional[str]:
        """Check if content hash exists. Returns corpus_item_id if duplicate."""
        await self.initialize()
        
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT id FROM corpus_items WHERE content_hash = ?",
                (content_hash,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return row[0]
        return None
    
    def _normalize_url(self, url: str) -> str:
        """Normalize URL for deduplication."""
        import re
        url = url.lower()
        url = re.sub(r'^https?://', '', url)
        url = re.sub(r'^www\.', '', url)
        url = url.rstrip('/')
        url = url.split('?')[0]
        return url
    
    # ========================================================================
    # Digest Operations
    # ========================================================================
    
    async def save_digest(self, digest: Digest):
        """Save a digest to the database."""
        await self.initialize()
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO digests (
                    id, period_start, period_end, hours_covered,
                    executive_summary, items, stats, generated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                digest.id,
                digest.period_start.isoformat(),
                digest.period_end.isoformat(),
                digest.hours_covered,
                digest.executive_summary,
                json.dumps([i.model_dump() for i in digest.items], default=str),
                json.dumps(digest.stats.model_dump()),
                digest.generated_at.isoformat(),
            ))
            await db.commit()
    
    async def get_latest_digest(self) -> Optional[Digest]:
        """Get the most recent digest."""
        await self.initialize()
        
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT * FROM digests 
                ORDER BY generated_at DESC 
                LIMIT 1
            """) as cursor:
                row = await cursor.fetchone()
                if row:
                    return self._row_to_digest(row)
        return None
    
    # ========================================================================
    # Briefing Operations
    # ========================================================================
    
    async def save_briefing(self, briefing_data: Dict[str, Any]):
        """Save a briefing summary to the database."""
        await self.initialize()
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO briefing_summaries (
                    id, category, headline, summary, key_insights,
                    trend_signal, attention_flag, attention_reason,
                    article_ids, period_start, period_end, generated_at, model
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                briefing_data['id'],
                briefing_data['category'],
                briefing_data['headline'],
                briefing_data['summary'],
                json.dumps(briefing_data['key_insights']),
                briefing_data['trend_signal'],
                briefing_data['attention_flag'],
                briefing_data['attention_reason'],
                json.dumps(briefing_data['article_ids']),
                briefing_data['period_start'].isoformat() if isinstance(briefing_data['period_start'], datetime) else briefing_data['period_start'],
                briefing_data['period_end'].isoformat() if isinstance(briefing_data['period_end'], datetime) else briefing_data['period_end'],
                briefing_data['generated_at'].isoformat() if isinstance(briefing_data['generated_at'], datetime) else briefing_data['generated_at'],
                briefing_data['model'],
            ))
            await db.commit()
    
    async def get_latest_briefings(self, limit_per_category: int = 1) -> List[Dict[str, Any]]:
        """Get the latest briefing for each category."""
        await self.initialize()
        
        briefings = []
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            # Get latest for each category using a subquery
            query = """
                SELECT * FROM briefing_summaries b1
                WHERE generated_at = (
                    SELECT MAX(generated_at) 
                    FROM briefing_summaries b2 
                    WHERE b1.category = b2.category
                )
                ORDER BY category ASC
            """
            async with db.execute(query) as cursor:
                async for row in cursor:
                    briefing = dict(row)
                    briefing['key_insights'] = json.loads(briefing['key_insights'] or '[]')
                    briefing['article_ids'] = json.loads(briefing['article_ids'] or '[]')
                    briefings.append(briefing)
        
        return briefings

    # ========================================================================
    # Weekly Executive Briefings (New Dynamic Format)
    # ========================================================================
    
    async def save_weekly_briefing(self, briefing_data: Dict[str, Any]) -> bool:
        """Save a weekly executive briefing."""
        await self.initialize()
        
        generated_at = briefing_data.get('generated_at')
        if hasattr(generated_at, 'isoformat'):
            generated_at = generated_at.isoformat()
        
        period_start = briefing_data.get('period_start')
        if hasattr(period_start, 'isoformat'):
            period_start = period_start.isoformat()
            
        period_end = briefing_data.get('period_end')
        if hasattr(period_end, 'isoformat'):
            period_end = period_end.isoformat()
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO weekly_briefings (
                    id, briefing_type, briefing_title, sections,
                    all_companies_mentioned, key_topics_this_week, overall_trend,
                    period_start, period_end, generated_at, model,
                    article_count, article_ids, quarter, week_of_year
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                briefing_data['id'],
                briefing_data.get('briefing_type', 'weekly_executive'),
                briefing_data.get('briefing_title', ''),
                json.dumps(briefing_data.get('sections', [])),
                json.dumps(briefing_data.get('all_companies_mentioned', [])),
                json.dumps(briefing_data.get('key_topics_this_week', [])),
                briefing_data.get('overall_trend', ''),
                period_start,
                period_end,
                generated_at,
                briefing_data.get('model', ''),
                briefing_data.get('article_count', 0),
                json.dumps(briefing_data.get('article_ids', [])),
                briefing_data.get('quarter', ''),
                briefing_data.get('week_of_year', 0),
            ))
            await db.commit()
        
        logger.info(f"Stored weekly briefing {briefing_data['id']} in SQLite")
        return True
    
    async def get_latest_weekly_briefing(self) -> Optional[Dict[str, Any]]:
        """Get the most recent weekly executive briefing."""
        await self.initialize()
        
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT * FROM weekly_briefings 
                ORDER BY generated_at DESC 
                LIMIT 1
            """) as cursor:
                row = await cursor.fetchone()
                if row:
                    briefing = dict(row)
                    for json_field in ['sections', 'all_companies_mentioned', 'key_topics_this_week', 'article_ids']:
                        if briefing.get(json_field):
                            try:
                                briefing[json_field] = json.loads(briefing[json_field])
                            except (json.JSONDecodeError, TypeError):
                                briefing[json_field] = []
                    return briefing
        return None
    
    async def get_weekly_briefing_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get historical weekly briefings."""
        await self.initialize()
        
        briefings = []
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT * FROM weekly_briefings 
                ORDER BY generated_at DESC 
                LIMIT ?
            """, (limit,)) as cursor:
                async for row in cursor:
                    briefing = dict(row)
                    for json_field in ['sections', 'all_companies_mentioned', 'key_topics_this_week', 'article_ids']:
                        if briefing.get(json_field):
                            try:
                                briefing[json_field] = json.loads(briefing[json_field])
                            except (json.JSONDecodeError, TypeError):
                                briefing[json_field] = []
                    briefings.append(briefing)
        
        return briefings

    # ========================================================================
    # Ad Hoc Briefings
    # ========================================================================
    
    async def save_adhoc_briefing(self, briefing_data: Dict[str, Any]) -> bool:
        """Save an ad hoc briefing."""
        await self.initialize()
        
        generated_at = briefing_data.get('generated_at')
        if hasattr(generated_at, 'isoformat'):
            generated_at = generated_at.isoformat()
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO adhoc_briefings (
                    id, question, answer, sources_used, confidence,
                    suggest_deep_research, related_topics, context_used,
                    search_results_count, follow_up_count, generated_at,
                    model, user_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                briefing_data['id'],
                briefing_data.get('question', ''),
                briefing_data.get('answer', ''),
                json.dumps(briefing_data.get('sources_used', [])),
                briefing_data.get('confidence', 'medium'),
                1 if briefing_data.get('suggest_deep_research', False) else 0,
                json.dumps(briefing_data.get('related_topics', [])),
                json.dumps(briefing_data.get('context_used', {})),
                briefing_data.get('search_results_count', 0),
                briefing_data.get('follow_up_count', 0),
                generated_at,
                briefing_data.get('model', ''),
                briefing_data.get('user_id'),
            ))
            await db.commit()
        
        logger.info(f"Stored ad hoc briefing {briefing_data['id']} in SQLite")
        return True
    
    async def get_adhoc_briefing_history(self, limit: int = 20, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get ad hoc briefing history."""
        await self.initialize()
        
        briefings = []
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            if user_id:
                query = """
                    SELECT * FROM adhoc_briefings 
                    WHERE user_id = ?
                    ORDER BY generated_at DESC 
                    LIMIT ?
                """
                params = (user_id, limit)
            else:
                query = """
                    SELECT * FROM adhoc_briefings 
                    ORDER BY generated_at DESC 
                    LIMIT ?
                """
                params = (limit,)
            
            async with db.execute(query, params) as cursor:
                async for row in cursor:
                    briefing = dict(row)
                    briefing['suggest_deep_research'] = bool(briefing.get('suggest_deep_research', 0))
                    for json_field in ['sources_used', 'related_topics']:
                        if briefing.get(json_field):
                            try:
                                briefing[json_field] = json.loads(briefing[json_field])
                            except (json.JSONDecodeError, TypeError):
                                briefing[json_field] = []
                    if briefing.get('context_used'):
                        try:
                            briefing['context_used'] = json.loads(briefing['context_used'])
                        except (json.JSONDecodeError, TypeError):
                            briefing['context_used'] = {}
                    briefings.append(briefing)
        
        return briefings
    
    # ========================================================================
    # Ingestion Stats
    # ========================================================================
    
    async def save_ingestion_stats(self, stats: IngestionStats):
        """Save ingestion run statistics."""
        await self.initialize()
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO ingestion_runs (
                    id, started_at, completed_at, status,
                    rss_articles_fetched, fmp_articles_fetched,
                    articles_enriched, articles_classified,
                    duplicates_skipped, articles_stored, errors
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                stats.id,
                stats.started_at.isoformat(),
                stats.completed_at.isoformat() if stats.completed_at else None,
                stats.status,
                stats.rss_articles_fetched,
                0,  # fmp_articles_fetched - deprecated, always 0
                stats.articles_enriched,
                stats.articles_classified,
                stats.duplicates_skipped,
                stats.articles_stored,
                json.dumps(stats.errors),
            ))
            await db.commit()
    
    async def get_latest_ingestion(self) -> Optional[IngestionStats]:
        """Get the most recent ingestion run stats."""
        await self.initialize()
        
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT * FROM ingestion_runs 
                ORDER BY started_at DESC 
                LIMIT 1
            """) as cursor:
                row = await cursor.fetchone()
                if row:
                    return self._row_to_ingestion_stats(row)
        return None
    
    # ========================================================================
    # Pre-Briefing Operations (Agent 1 Intermediate Output)
    # ========================================================================
    
    async def save_pre_briefing(self, briefing_data: Dict[str, Any]) -> bool:
        """Save a pre-briefing record."""
        import json
        await self.initialize()
        
        generated_at = briefing_data.get('generated_at')
        if hasattr(generated_at, 'isoformat'):
            generated_at = generated_at.isoformat()
        
        period_start = briefing_data.get('period_start')
        if hasattr(period_start, 'isoformat'):
            period_start = period_start.isoformat()
            
        period_end = briefing_data.get('period_end')
        if hasattr(period_end, 'isoformat'):
            period_end = period_end.isoformat()
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO pre_briefings (
                    id, briefing_type, data, period_start, period_end,
                    generated_at, model, article_count, article_ids
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                briefing_data['id'],
                briefing_data.get('briefing_type', 'pre_briefing'),
                json.dumps(briefing_data.get('data', {})),
                period_start,
                period_end,
                generated_at,
                briefing_data.get('model', ''),
                briefing_data.get('article_count', 0),
                json.dumps(briefing_data.get('article_ids', [])),
            ))
            await db.commit()
        
        logger.info(f"Stored pre-briefing {briefing_data['id']} in SQLite")
        return True
    
    async def get_latest_pre_briefing(self) -> Optional[Dict[str, Any]]:
        """Get the most recent pre-briefing."""
        import json
        await self.initialize()
        
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT * FROM pre_briefings 
                ORDER BY generated_at DESC 
                LIMIT 1
            """) as cursor:
                row = await cursor.fetchone()
                if row:
                    briefing = dict(row)
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
        return None
    
    # ========================================================================
    # Entity Management (from CSVs)
    # ========================================================================
    
    async def list_entities(
        self, 
        entity_type: Optional[str] = None,
        priority_only: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get tracked entities from CSV files.
        
        This loads from the existing CSV files rather than a database table,
        maintaining compatibility with the current data management approach.
        """
        import csv
        from app.config.settings import settings
        
        entities = []
        
        if entity_type in (None, "competitor", "oem", "material_manufacturer"):
            # Load companies
            if settings.companies_file.exists():
                with open(settings.companies_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        company_type = row.get('type', 'competitor').lower()
                        if entity_type and company_type != entity_type:
                            continue
                        if priority_only and row.get('priority', '').lower() != 'high':
                            continue
                        
                        # Handle different column names (master list uses 'company', 'stock_ticker')
                        name = row.get('name') or row.get('company')
                        ticker = row.get('ticker') or row.get('stock_ticker')
                        
                        if not name:
                            continue

                        entities.append({
                            "id": (ticker or name).lower().replace(' ', '_'),
                            "name": name,
                            "type": company_type,
                            "ticker": ticker,
                            "aliases": row.get('aliases', '').split(';') if row.get('aliases') else [],
                        })
        
        if entity_type in (None, "material"):
            # Load materials
            if settings.materials_file.exists():
                with open(settings.materials_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        # Handle potential column name differences
                        name = row.get('name') or row.get('material')
                        if not name:
                            continue
                            
                        entities.append({
                            "id": name.lower().replace(' ', '_'),
                            "name": name,
                            "type": "material",
                            "aliases": row.get('aliases', '').split(';') if row.get('aliases') else [],
                        })
        
        return entities
    
    async def get_tracked_tickers(self) -> List[str]:
        """Get all tracked tickers from companies."""
        entities = await self.list_entities()
        return [e['ticker'] for e in entities if e.get('ticker')]
    
    # ========================================================================
    # Conversion Helpers
    # ========================================================================
    
    def _normalize_category(self, value: str) -> ContentCategory:
        """Normalize category value to handle legacy lowercase entries."""
        if not value:
            return ContentCategory.GENERAL
        # Try direct match first
        try:
            return ContentCategory(value)
        except ValueError:
            pass
        # Try case-insensitive match
        value_lower = value.lower()
        for cat in ContentCategory:
            if cat.value.lower() == value_lower:
                return cat
        # Default fallback
        return ContentCategory.GENERAL
    
    def _normalize_industry(self, value: str) -> Optional[Industry]:
        """Normalize industry value to handle legacy lowercase entries."""
        if not value:
            return None
        # Try direct match first
        try:
            return Industry(value)
        except ValueError:
            pass
        # Try case-insensitive match
        value_lower = value.lower()
        for ind in Industry:
            if ind.value.lower() == value_lower:
                return ind
        return None
    
    def _normalize_priority(self, value: str) -> Priority:
        """Normalize priority value to handle legacy lowercase entries."""
        if not value:
            return Priority.LOW
        # Try direct match first
        try:
            return Priority(value)
        except ValueError:
            pass
        # Try case-insensitive match
        value_lower = value.lower()
        for pri in Priority:
            if pri.value.lower() == value_lower:
                return pri
        # Default fallback
        return Priority.LOW
    
    def _row_to_corpus_item(self, row: aiosqlite.Row) -> CorpusItem:
        """Convert database row to CorpusItem."""
        # Parse categories with case-insensitive matching for legacy data
        raw_categories = json.loads(row['categories'] or '[]')
        categories = [self._normalize_category(c) for c in raw_categories]
        categories = [c for c in categories if c is not None]
        
        # Parse industries with case-insensitive matching
        raw_industries = json.loads(row['industries'] or '[]')
        industries = [self._normalize_industry(i) for i in raw_industries]
        industries = [i for i in industries if i is not None]
        
        return CorpusItem(
            id=row['id'],
            title=row['title'],
            summary=row['summary'] or "",
            full_text=row['full_text'],
            url=row['url'],
            source=ContentSource(
                name=row['source_name'] or "",
                url=row['source_url'] or row['url'],
                source_type=row['source_type'] or "rss",
            ),
            primary_category=self._normalize_category(row['primary_category']),
            categories=categories,
            industries=industries,
            priority=self._normalize_priority(row['priority']),
            relevance_score=row['relevance_score'] or 0.5,
            entity_mentions=[EntityMention(**m) for m in json.loads(row['entity_mentions'] or '[]')],
            companies_mentioned=json.loads(row['companies_mentioned'] or '[]'),
            materials_mentioned=json.loads(row['materials_mentioned'] or '[]'),
            sentiment=row['sentiment'] or "neutral",
            confidence=row['confidence'] or 0.7,
            content_hash=row['content_hash'],
            published_at=datetime.fromisoformat(row['published_at']) if row['published_at'] else datetime.utcnow(),
            ingested_at=datetime.fromisoformat(row['ingested_at']) if row['ingested_at'] else datetime.utcnow(),
        )
    
    def _row_to_digest(self, row: aiosqlite.Row) -> Digest:
        """Convert database row to Digest."""
        items_data = json.loads(row['items'] or '[]')
        stats_data = json.loads(row['stats'] or '{}')
        
        return Digest(
            id=row['id'],
            period_start=datetime.fromisoformat(row['period_start']),
            period_end=datetime.fromisoformat(row['period_end']),
            hours_covered=row['hours_covered'],
            executive_summary=row['executive_summary'] or "",
            items=[DigestItem(**i) for i in items_data],
            stats=DigestStats(**stats_data),
            generated_at=datetime.fromisoformat(row['generated_at']),
        )
    
    def _row_to_ingestion_stats(self, row: aiosqlite.Row) -> IngestionStats:
        """Convert database row to IngestionStats."""
        return IngestionStats(
            id=row['id'],
            started_at=datetime.fromisoformat(row['started_at']),
            completed_at=datetime.fromisoformat(row['completed_at']) if row['completed_at'] else None,
            status=row['status'],
            rss_articles_fetched=row['rss_articles_fetched'],
            articles_enriched=row['articles_enriched'],
            articles_classified=row['articles_classified'],
            duplicates_skipped=row['duplicates_skipped'],
            articles_stored=row['articles_stored'],
            errors=json.loads(row['errors'] or '[]'),
        )


# Singleton instance
_db_instance: Optional[Database] = None


def get_db() -> Database:
    """Get the database singleton instance."""
    global _db_instance
    if _db_instance is None:
        _db_instance = Database()
    return _db_instance
