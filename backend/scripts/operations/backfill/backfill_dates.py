"""
Backfill Published Dates
========================

Fixes published_at dates in existing articles and digest_items
by re-extracting from URLs and content.

Run from backend directory:
    python scripts/backfill_dates.py
"""

import asyncio
import sqlite3
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from app.utils.date_extraction import extract_publication_date

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Database paths
TIMESERIES_DB = os.path.join(os.path.dirname(__file__), '..', 'data', 'c1_timeseries.db')


def backfill_articles(conn):
    """Backfill published_at in articles table."""
    cursor = conn.cursor()
    
    # Get all articles
    cursor.execute("SELECT id, url, full_text, source_type, published_at FROM articles")
    articles = cursor.fetchall()
    
    logger.info(f"Processing {len(articles)} articles...")
    
    updated = 0
    for article_id, url, full_text, source_type, current_date in articles:
        # Skip if already has a reasonable date (not from today's ingestion batch)
        # We assume dates clustered within same hour are "ingestion dates"
        
        # Extract date
        new_date = extract_publication_date(
            url=url,
            content=full_text,
            api_date=None,
            fallback=None  # Don't fallback - keep original if can't extract
        )
        
        if new_date and new_date != current_date:
            cursor.execute(
                "UPDATE articles SET published_at = ? WHERE id = ?",
                (new_date.isoformat(), article_id)
            )
            updated += 1
    
    conn.commit()
    logger.info(f"Updated {updated} articles with extracted dates")
    return updated


def backfill_digest_items(conn):
    """Backfill published_at in digest_items table."""
    cursor = conn.cursor()
    
    # Get all digest items
    cursor.execute("SELECT id, url, original_summary, source_type, published_at FROM digest_items")
    items = cursor.fetchall()
    
    logger.info(f"Processing {len(items)} digest items...")
    
    updated = 0
    for item_id, url, summary, source_type, current_date in items:
        # Extract date from URL and summary (we don't have full_text in digest_items)
        new_date = extract_publication_date(
            url=url,
            content=summary,
            api_date=None,
            fallback=None
        )
        
        if new_date and new_date != current_date:
            cursor.execute(
                "UPDATE digest_items SET published_at = ? WHERE id = ?",
                (new_date.isoformat(), item_id)
            )
            updated += 1
    
    conn.commit()
    logger.info(f"Updated {updated} digest items with extracted dates")
    return updated


def main():
    logger.info("Starting date backfill...")
    start = datetime.now()
    
    # Check if database exists
    if not os.path.exists(TIMESERIES_DB):
        logger.error(f"Database not found: {TIMESERIES_DB}")
        return
    
    conn = sqlite3.connect(TIMESERIES_DB)
    
    try:
        articles_updated = backfill_articles(conn)
        digest_updated = backfill_digest_items(conn)
        
        elapsed = (datetime.now() - start).total_seconds()
        logger.info(f"Backfill complete in {elapsed:.1f}s")
        logger.info(f"Total: {articles_updated} articles, {digest_updated} digest items updated")
        
    finally:
        conn.close()


if __name__ == "__main__":
    main()
