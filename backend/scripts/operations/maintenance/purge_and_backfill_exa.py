"""
Selective Purge and Backfill Script for Exa.ai Migration

This script:
1. Purges ONLY web_news and press_release source types from:
   - BigQuery articles table  
   - BigQuery digest_items table
   - BigQuery vector store

2. Runs a backfill from December 1, 2025 using the new Exa.ai client
   (which provides clean publishedDate values)

3. Does NOT touch: SEC filings, RSS feeds, earnings transcripts

NOTE: SQLite and ChromaDB have been removed - BigQuery is the only data store.

Usage:
    python scripts/purge_and_backfill_exa.py --purge-only     # Just purge, no backfill
    python scripts/purge_and_backfill_exa.py --backfill-only  # Just backfill (assumes purged)
    python scripts/purge_and_backfill_exa.py                  # Full purge + backfill
"""

import asyncio
import argparse
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.database import Database, DB_PATH
from app.db.gcp_storage import gcp_config, get_storage
from app.config.settings import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Source types that were using Tavily (now Exa)
TAVILY_SOURCE_TYPES = ["web_news", "press_release"]

# Backfill start date
BACKFILL_START = datetime(2025, 12, 1)


async def purge_sqlite_selective():
    """Purge only web_news and press_release from SQLite."""
    if not DB_PATH.exists():
        logger.info("No SQLite database found, skipping SQLite purge.")
        return 0
    
    import aiosqlite
    
    deleted_count = 0
    async with aiosqlite.connect(DB_PATH) as db:
        # Count before
        cursor = await db.execute(
            "SELECT COUNT(*) FROM corpus_items WHERE source_type IN (?, ?)",
            TAVILY_SOURCE_TYPES
        )
        count_before = (await cursor.fetchone())[0]
        logger.info(f"Found {count_before} items with source_type in {TAVILY_SOURCE_TYPES}")
        
        # Delete from corpus_items
        await db.execute(
            "DELETE FROM corpus_items WHERE source_type IN (?, ?)",
            TAVILY_SOURCE_TYPES
        )
        
        # Also clean url_cache for these items
        await db.execute("""
            DELETE FROM url_cache 
            WHERE corpus_item_id IN (
                SELECT id FROM corpus_items WHERE source_type IN (?, ?)
            )
        """, TAVILY_SOURCE_TYPES)
        
        await db.commit()
        
        # Count after
        cursor = await db.execute(
            "SELECT COUNT(*) FROM corpus_items WHERE source_type IN (?, ?)",
            TAVILY_SOURCE_TYPES
        )
        count_after = (await cursor.fetchone())[0]
        deleted_count = count_before - count_after
        
        logger.info(f"Deleted {deleted_count} items from SQLite corpus_items")
    
    return deleted_count


async def purge_bigquery_selective():
    """Purge only web_news and press_release from BigQuery tables."""
    if not gcp_config.is_configured:
        logger.info("GCP not configured, skipping BigQuery purge.")
        return
    
    from google.cloud import bigquery
    client = bigquery.Client(project=gcp_config.project_id)
    dataset_id = gcp_config.full_dataset_id
    
    # Tables and their source_type column names
    tables_to_purge = {
        "articles": "source_type",
        "digest_items": "source_type",
    }
    
    source_types_str = ", ".join([f"'{s}'" for s in TAVILY_SOURCE_TYPES])
    
    for table_name, column_name in tables_to_purge.items():
        table_id = f"{dataset_id}.{table_name}"
        try:
            # Check if table exists
            client.get_table(table_id)
            
            # Count before
            count_query = f"SELECT COUNT(*) as cnt FROM `{table_id}` WHERE {column_name} IN ({source_types_str})"
            count_result = client.query(count_query).result()
            count_before = list(count_result)[0].cnt
            
            logger.info(f"Found {count_before} rows in {table_name} with source_type in {TAVILY_SOURCE_TYPES}")
            
            # Delete
            delete_query = f"DELETE FROM `{table_id}` WHERE {column_name} IN ({source_types_str})"
            job = client.query(delete_query)
            job.result()
            
            logger.info(f"Purged {table_name}: removed rows with source_type in {TAVILY_SOURCE_TYPES}")
            
        except Exception as e:
            if "Not found" in str(e):
                logger.info(f"Table not found (skipping): {table_name}")
            else:
                logger.error(f"Error purging {table_name}: {e}")


async def purge_chromadb_selective():
    """Purge only web_news and press_release from ChromaDB."""
    try:
        from app.db.vector_store import get_production_vector_store
        
        vector_store = await get_production_vector_store()
        
        if not vector_store.is_available:
            logger.warning("ChromaDB not available, skipping purge")
            return
        
        # ChromaDB deletion by metadata filter
        # We need to query for IDs first, then delete by IDs
        for source_type in TAVILY_SOURCE_TYPES:
            try:
                # Query for items with this source type (use _collection not collection)
                results = vector_store._collection.get(
                    where={"source_type": source_type},
                    include=["metadatas"]
                )
                
                ids_to_delete = results.get("ids", [])
                if ids_to_delete:
                    vector_store._collection.delete(ids=ids_to_delete)
                    logger.info(f"Deleted {len(ids_to_delete)} items from ChromaDB with source_type={source_type}")
                else:
                    logger.info(f"No items found in ChromaDB with source_type={source_type}")
                    
            except Exception as e:
                logger.warning(f"Error querying ChromaDB for {source_type}: {e}")
                
    except Exception as e:
        logger.error(f"Error connecting to ChromaDB: {e}")


async def run_purge():
    """Run selective purge on all data stores."""
    logger.info("=" * 60)
    logger.info("SELECTIVE PURGE: Removing web_news and press_release data")
    logger.info("=" * 60)
    
    # 1. SQLite
    logger.info("\n--- Purging SQLite ---")
    await purge_sqlite_selective()
    
    # 2. BigQuery
    logger.info("\n--- Purging BigQuery ---")
    await purge_bigquery_selective()
    
    # 3. ChromaDB
    logger.info("\n--- Purging ChromaDB ---")
    await purge_chromadb_selective()
    
    logger.info("\n" + "=" * 60)
    logger.info("PURGE COMPLETE")
    logger.info("=" * 60)


async def run_backfill():
    """Run backfill from December 1, 2025 using Exa.ai."""
    logger.info("=" * 60)
    logger.info(f"BACKFILL: Running from {BACKFILL_START.date()} using Exa.ai")
    logger.info("=" * 60)
    
    # Calculate days back from today
    days_back = (datetime.utcnow() - BACKFILL_START).days
    logger.info(f"Backfill period: {days_back} days")
    
    # Import orchestrator
    from app.ingestion.orchestrator import IngestionOrchestrator, IngestionConfig
    
    config = IngestionConfig()
    logger.info(f"Exa API Key configured: {bool(config.exa_api_key)}")
    
    if not config.exa_api_key:
        logger.error("EXA_AI_API_KEY not configured! Cannot run backfill.")
        return
    
    orchestrator = IngestionOrchestrator(config)
    await orchestrator.initialize()
    
    # Run ingestion with backfill_days parameter
    # Note: This will fetch RSS, SEC, earnings too - but those won't be affected
    # by the Exa migration since they use their own APIs
    logger.info(f"Starting ingestion with backfill_days={days_back}...")
    
    stats = await orchestrator.run_full_ingestion(backfill_days=days_back)
    
    logger.info("\n" + "=" * 60)
    logger.info("BACKFILL COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Status: {stats.status}")
    logger.info(f"PR articles fetched: {stats.pr_articles_fetched}")
    logger.info(f"Web articles fetched: {stats.web_articles_fetched}")
    logger.info(f"Articles stored: {stats.articles_stored}")
    logger.info(f"Duplicates skipped: {stats.duplicates_skipped}")
    if stats.errors:
        logger.warning(f"Errors: {stats.errors[:5]}")  # Show first 5


async def verify_dates():
    """Verify that the new data has clean dates."""
    logger.info("\n--- Verifying Dates in New Data ---")
    
    import aiosqlite
    
    if not DB_PATH.exists():
        logger.info("No database to verify")
        return
    
    async with aiosqlite.connect(DB_PATH) as db:
        # Check web_news and press_release entries
        cursor = await db.execute("""
            SELECT 
                source_type,
                COUNT(*) as total,
                SUM(CASE WHEN published_at IS NOT NULL AND published_at != '' THEN 1 ELSE 0 END) as with_date,
                MIN(published_at) as oldest,
                MAX(published_at) as newest
            FROM corpus_items
            WHERE source_type IN ('web_news', 'press_release')
            GROUP BY source_type
        """)
        
        rows = await cursor.fetchall()
        
        if not rows:
            logger.info("No web_news or press_release entries found yet")
            return
        
        for row in rows:
            source_type, total, with_date, oldest, newest = row
            pct = (with_date / total * 100) if total > 0 else 0
            logger.info(f"\n{source_type}:")
            logger.info(f"  Total: {total}")
            logger.info(f"  With date: {with_date} ({pct:.1f}%)")
            logger.info(f"  Date range: {oldest} to {newest}")


async def main():
    parser = argparse.ArgumentParser(description="Purge and backfill for Exa.ai migration")
    parser.add_argument("--purge-only", action="store_true", help="Only run purge, no backfill")
    parser.add_argument("--backfill-only", action="store_true", help="Only run backfill, no purge")
    parser.add_argument("--verify-only", action="store_true", help="Only verify dates in existing data")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without doing it")
    
    args = parser.parse_args()
    
    if args.dry_run:
        logger.info("DRY RUN - showing what would be done:")
        logger.info(f"  - Would purge source_types: {TAVILY_SOURCE_TYPES}")
        logger.info(f"  - Would backfill from: {BACKFILL_START.date()}")
        logger.info(f"  - Days to backfill: {(datetime.utcnow() - BACKFILL_START).days}")
        return
    
    if args.verify_only:
        await verify_dates()
        return
    
    if args.purge_only:
        await run_purge()
        await verify_dates()
        return
    
    if args.backfill_only:
        await run_backfill()
        await verify_dates()
        return
    
    # Default: full purge + backfill
    await run_purge()
    await run_backfill()
    await verify_dates()


if __name__ == "__main__":
    asyncio.run(main())
