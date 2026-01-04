"""
Sync SQLite data to BigQuery.

This script:
1. Reads all articles from SQLite that don't exist in BigQuery
2. Reads all digest_items from SQLite that don't exist in BigQuery  
3. Inserts them into BigQuery tables

Run from backend directory:
    python scripts/sync_sqlite_to_bigquery.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import sqlite3
from datetime import datetime
from google.cloud import bigquery

PROJECT_ID = "gen-lang-client-0436975498"
DATASET = "c1_intelligence"
SQLITE_PATH = "data/c1_timeseries.db"


def get_existing_bq_ids(client: bigquery.Client, table: str) -> set:
    """Get all existing IDs from a BigQuery table."""
    query = f"SELECT id FROM `{PROJECT_ID}.{DATASET}.{table}`"
    results = client.query(query).result()
    return {row.id for row in results}


def get_existing_bq_article_ids(client: bigquery.Client) -> set:
    """Get all existing article_ids from digest_items table."""
    query = f"SELECT DISTINCT article_id FROM `{PROJECT_ID}.{DATASET}.digest_items`"
    results = client.query(query).result()
    return {row.article_id for row in results}


def sync_articles(client: bigquery.Client, conn: sqlite3.Connection) -> int:
    """Sync articles from SQLite to BigQuery."""
    print("\n=== Syncing Articles ===")
    
    # Get existing BQ article IDs
    existing_ids = get_existing_bq_ids(client, "articles")
    print(f"  BigQuery has {len(existing_ids)} articles")
    
    # Get all SQLite articles
    cursor = conn.execute("""
        SELECT id, title, url, published_at, source_name, source_type,
               summary, full_text, category, topics, companies_mentioned,
               relevance_score, fetched_at
        FROM articles
    """)
    
    sqlite_articles = cursor.fetchall()
    print(f"  SQLite has {len(sqlite_articles)} articles")
    
    # Filter to new articles only
    new_articles = []
    for row in sqlite_articles:
        if row[0] not in existing_ids:
            new_articles.append({
                "id": row[0],
                "title": row[1],
                "url": row[2],
                "published_at": row[3],
                "source_name": row[4],
                "source_type": row[5],
                "summary": row[6],
                "full_text": row[7],
                "category": row[8],
                "topics": row[9] if row[9] else "[]",
                "companies_mentioned": row[10] if row[10] else "[]",
                "relevance_score": row[11] or 0.5,
                "fetched_at": row[12],
                # Note: 'metadata' field removed - not in BQ schema
            })
    
    print(f"  New articles to sync: {len(new_articles)}")
    
    if not new_articles:
        print("  No new articles to sync")
        return 0
    
    # Insert in batches of 500
    table_id = f"{PROJECT_ID}.{DATASET}.articles"
    batch_size = 500
    total_inserted = 0
    
    for i in range(0, len(new_articles), batch_size):
        batch = new_articles[i:i + batch_size]
        errors = client.insert_rows_json(table_id, batch)
        inserted = len(batch) - len(errors) if errors else len(batch)
        total_inserted += inserted
        
        if errors:
            print(f"  Batch {i//batch_size + 1} errors: {errors[:2]}")
        else:
            print(f"  Batch {i//batch_size + 1}: Inserted {inserted} articles")
    
    print(f"  Total articles synced: {total_inserted}")
    return total_inserted


def sync_digest_items(client: bigquery.Client, conn: sqlite3.Connection) -> int:
    """Sync digest_items from SQLite to BigQuery."""
    print("\n=== Syncing Digest Items ===")
    
    # Get existing BQ digest_item article_ids
    existing_article_ids = get_existing_bq_article_ids(client)
    print(f"  BigQuery has digest items for {len(existing_article_ids)} articles")
    
    # Get all SQLite digest items - only from last 10 years (BQ partition limit)
    # BQ streaming only allows dates within 3650 days (10 years)
    cursor = conn.execute("""
        SELECT id, article_id, title, url, published_at, source_name, source_type,
               category, priority, digest_summary, original_summary,
               companies, materials, topics, relevance_score, confidence,
               coverage_count, duplicate_sources, all_urls,
               classifier_model, classified_at, ingested_at
        FROM digest_items
        WHERE published_at >= date('now', '-3600 days')
    """)
    
    sqlite_items = cursor.fetchall()
    print(f"  SQLite has {len(sqlite_items)} digest items (within date range)")
    
    # Filter to items where article_id doesn't exist in BQ
    new_items = []
    import uuid
    skipped_dates = 0
    
    for row in sqlite_items:
        article_id = row[1]
        published_at = row[4]
        
        # Extra safety: skip if published_at looks like it's from before 2020
        if published_at and published_at < "2020-01-01":
            skipped_dates += 1
            continue
            
        if article_id not in existing_article_ids:
            new_items.append({
                "id": str(uuid.uuid4()),  # Generate new UUID for BQ
                "article_id": article_id,
                "title": row[2],
                "url": row[3],
                "published_at": published_at,
                "source_name": row[5],
                "source_type": row[6],
                "category": row[7] or "market",
                "priority": row[8] or "medium",
                "digest_summary": row[9],
                "original_summary": row[10],
                "companies": row[11] if row[11] else "[]",
                "materials": row[12] if row[12] else "[]",
                "topics": row[13] if row[13] else "[]",
                "relevance_score": row[14] or 0.5,
                "confidence": row[15] or 0.0,
                "coverage_count": row[16] or 1,
                "duplicate_sources": row[17] if row[17] else "[]",
                "all_urls": row[18] if row[18] else "[]",
                "classifier_model": row[19] or "",
                "classified_at": row[20],
                "ingested_at": row[21] or datetime.utcnow().isoformat(),
            })
            existing_article_ids.add(article_id)  # Prevent duplicates in batch
    
    if skipped_dates > 0:
        print(f"  Skipped {skipped_dates} items with dates before 2020")
    print(f"  New digest items to sync: {len(new_items)}")
    
    if not new_items:
        print("  No new digest items to sync")
        return 0
    
    # Insert in batches of 500
    table_id = f"{PROJECT_ID}.{DATASET}.digest_items"
    batch_size = 500
    total_inserted = 0
    
    for i in range(0, len(new_items), batch_size):
        batch = new_items[i:i + batch_size]
        errors = client.insert_rows_json(table_id, batch)
        inserted = len(batch) - len(errors) if errors else len(batch)
        total_inserted += inserted
        
        if errors:
            print(f"  Batch {i//batch_size + 1} errors: {errors[:2]}")
        else:
            print(f"  Batch {i//batch_size + 1}: Inserted {inserted} digest items")
    
    print(f"  Total digest items synced: {total_inserted}")
    return total_inserted


def verify_sync(client: bigquery.Client, conn: sqlite3.Connection):
    """Verify sync results."""
    print("\n=== Verification ===")
    
    # SQLite counts
    sqlite_articles = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    sqlite_digests = conn.execute("SELECT COUNT(*) FROM digest_items").fetchone()[0]
    
    # BigQuery counts
    bq_articles = list(client.query(f"SELECT COUNT(*) as cnt FROM `{PROJECT_ID}.{DATASET}.articles`"))[0].cnt
    bq_digests = list(client.query(f"SELECT COUNT(*) as cnt FROM `{PROJECT_ID}.{DATASET}.digest_items`"))[0].cnt
    
    print(f"  SQLite articles:      {sqlite_articles}")
    print(f"  BigQuery articles:    {bq_articles}")
    print(f"  SQLite digest_items:  {sqlite_digests}")
    print(f"  BigQuery digest_items: {bq_digests}")
    
    if sqlite_articles == bq_articles and sqlite_digests == bq_digests:
        print("\n✅ Sync complete! Counts match.")
    else:
        print(f"\n⚠️  Counts don't match - diff articles: {sqlite_articles - bq_articles}, digest_items: {sqlite_digests - bq_digests}")


def main():
    print("=" * 60)
    print("SQLite to BigQuery Sync")
    print("=" * 60)
    
    # Connect to BigQuery
    client = bigquery.Client(project=PROJECT_ID)
    
    # Connect to SQLite
    conn = sqlite3.connect(SQLITE_PATH)
    
    try:
        # Show current state
        print("\n=== Current State ===")
        sqlite_articles = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        sqlite_digests = conn.execute("SELECT COUNT(*) FROM digest_items").fetchone()[0]
        bq_articles = list(client.query(f"SELECT COUNT(*) as cnt FROM `{PROJECT_ID}.{DATASET}.articles`"))[0].cnt
        bq_digests = list(client.query(f"SELECT COUNT(*) as cnt FROM `{PROJECT_ID}.{DATASET}.digest_items`"))[0].cnt
        
        print(f"  SQLite:   {sqlite_articles} articles, {sqlite_digests} digest items")
        print(f"  BigQuery: {bq_articles} articles, {bq_digests} digest items")
        print(f"  Delta:    {sqlite_articles - bq_articles} articles, {sqlite_digests - bq_digests} digest items")
        
        # Confirm
        response = input("\nProceed with sync? (y/n): ")
        if response.lower() != 'y':
            print("Aborted.")
            return
        
        # Sync articles first (digest_items depend on them)
        sync_articles(client, conn)
        
        # Sync digest items
        sync_digest_items(client, conn)
        
        # Verify
        verify_sync(client, conn)
        
    finally:
        conn.close()


if __name__ == "__main__":
    main()
