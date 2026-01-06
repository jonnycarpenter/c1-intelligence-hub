"""
Backfill digest_items from articles table.

This script finds articles that exist in the `articles` table but are missing
from `digest_items`, and creates the corresponding digest_items records.

This is a ONE-TIME backfill for historical data that was stored before the
digest_items population code was working correctly.

Usage:
    cd backend
    python backfill_digest_items.py [--dry-run]
"""

import asyncio
import argparse
import uuid
from datetime import datetime, timezone
from google.cloud import bigquery

# Configuration
PROJECT_ID = "gen-lang-client-0436975498"
DATASET = "c1_intelligence"

def get_missing_articles(client: bigquery.Client) -> list[dict]:
    """Query articles that don't have matching digest_items."""
    
    query = f"""
    SELECT 
        a.id as article_id,
        a.title,
        a.url,
        a.published_at,
        a.source_name,
        a.source_type,
        a.summary,
        a.category,
        a.topics,
        a.companies_mentioned,
        a.relevance_score,
        a.fetched_at
    FROM `{PROJECT_ID}.{DATASET}.articles` a
    LEFT JOIN `{PROJECT_ID}.{DATASET}.digest_items` d ON a.url = d.url
    WHERE d.url IS NULL
    ORDER BY a.fetched_at DESC
    """
    
    print("Querying for articles missing from digest_items...")
    result = client.query(query).result()
    
    articles = []
    for row in result:
        articles.append(dict(row))
    
    print(f"Found {len(articles)} articles missing from digest_items")
    return articles


def transform_to_digest_item(article: dict) -> dict:
    """Transform an article record into a digest_item record."""
    
    # BigQuery partition constraint: published_at must be within 3650 days (10 years) of today
    # Articles with dates older than ~2016 will fail to insert
    # For those, we use fetched_at as the published_at
    min_valid_date = datetime(2016, 1, 5, tzinfo=timezone.utc)
    
    # Determine feed_eligible based on published_at
    feed_eligible = False
    published_at = article.get("published_at")
    fetched_at = article.get("fetched_at")
    
    if published_at:
        pub_date = published_at
        # Make timezone-aware for comparison
        if pub_date.tzinfo is None:
            pub_date = pub_date.replace(tzinfo=timezone.utc)
        
        # Check if date is too old for partition
        if pub_date < min_valid_date:
            # Use fetched_at instead (which is recent)
            published_at = fetched_at
            feed_eligible = False  # Mark as not feed eligible since date is wrong
        else:
            now_utc = datetime.now(timezone.utc)
            # Feed eligible if date is in the past (not future = bad parsing)
            if pub_date <= now_utc:
                feed_eligible = True
    else:
        # No published_at, use fetched_at
        published_at = fetched_at
        feed_eligible = False
    
    # Map category to priority (simple heuristic)
    category = article.get("category", "market") or "market"
    relevance = article.get("relevance_score", 0.5) or 0.5
    
    if relevance >= 0.8:
        priority = "high"
    elif relevance >= 0.5:
        priority = "medium"
    else:
        priority = "low"
    
    # Parse topics - already stored as JSON string in articles table, pass through
    topics = article.get("topics", "")
    if topics is None:
        topics_str = ""
    elif isinstance(topics, list):
        # If it comes back as a list (parsed JSON), convert to JSON string
        import json
        topics_str = json.dumps(topics)
    else:
        # Already a string (JSON array like '["item1", "item2"]')
        topics_str = str(topics)
    
    # Parse companies_mentioned - already stored as JSON string in articles table
    companies = article.get("companies_mentioned", "")
    if companies is None:
        companies_str = ""
    elif isinstance(companies, list):
        import json
        companies_str = json.dumps(companies)
    else:
        companies_str = str(companies)
    
    now = datetime.now(timezone.utc)
    
    return {
        "id": str(uuid.uuid4()),  # Required: unique ID for this digest_item row
        "article_id": article.get("article_id", str(uuid.uuid4())),  # Reference to source article
        "title": article.get("title", "") or "Untitled",
        "url": article.get("url", ""),
        "published_at": published_at.isoformat() if published_at else None,
        "source_name": article.get("source_name", ""),
        "source_type": article.get("source_type", ""),
        "category": category,
        "priority": priority,
        "digest_summary": article.get("summary", ""),
        "original_summary": article.get("summary", ""),
        "companies": companies_str,  # STRING in BQ, not REPEATED
        "materials": "",  # STRING in BQ - not available in articles table
        "topics": topics_str,  # STRING in BQ, not REPEATED
        "industries": "",  # STRING in BQ - not available in articles table
        "relevance_score": float(relevance),
        "confidence": 0.8,  # Default confidence for backfilled items
        "classifier_model": "backfill",  # Mark as backfilled
        "classified_at": now.isoformat(),  # Required TIMESTAMP
        "ingested_at": now.isoformat(),  # Required TIMESTAMP
        "feed_eligible": feed_eligible,
        # Additional fields
        "coverage_count": 1,
        "duplicate_sources": "",
        "all_urls": "",
    }


def insert_digest_items(client: bigquery.Client, items: list[dict], dry_run: bool = False) -> int:
    """Insert digest_items into BigQuery."""
    
    if not items:
        print("No items to insert")
        return 0
    
    if dry_run:
        print(f"[DRY RUN] Would insert {len(items)} digest_items")
        # Show a sample
        print("\nSample item:")
        sample = items[0]
        for key in ["id", "title", "url", "category", "priority", "feed_eligible", "companies", "topics"]:
            print(f"  {key}: {sample.get(key)}")
        return len(items)
    
    table_id = f"{PROJECT_ID}.{DATASET}.digest_items"
    
    # Convert to rows for BigQuery - only include fields that exist in schema
    # Schema: id, article_id, title, url, published_at, source_name, source_type,
    #         category, priority, digest_summary, original_summary, companies,
    #         materials, topics, relevance_score, confidence, classifier_model,
    #         classified_at, ingested_at, coverage_count, duplicate_sources,
    #         all_urls, industries, feed_eligible
    rows = []
    for item in items:
        row = {
            "id": item["id"],
            "article_id": item["article_id"],
            "title": item["title"],
            "url": item["url"],
            "published_at": item["published_at"],
            "source_name": item["source_name"],
            "source_type": item["source_type"],
            "category": item["category"],
            "priority": item["priority"],
            "digest_summary": item["digest_summary"],
            "original_summary": item["original_summary"],
            "companies": item["companies"],
            "materials": item["materials"],
            "topics": item["topics"],
            "industries": item.get("industries", ""),
            "relevance_score": item["relevance_score"],
            "confidence": item["confidence"],
            "classifier_model": item["classifier_model"],
            "classified_at": item["classified_at"],
            "ingested_at": item["ingested_at"],
            "feed_eligible": item["feed_eligible"],
            "coverage_count": item.get("coverage_count", 1),
            "duplicate_sources": item.get("duplicate_sources", ""),
            "all_urls": item.get("all_urls", ""),
        }
        rows.append(row)
    
    print(f"Inserting {len(rows)} rows into {table_id}...")
    
    errors = client.insert_rows_json(table_id, rows)
    
    if errors:
        print(f"Encountered {len(errors)} errors during insert:")
        for error in errors[:5]:  # Show first 5 errors
            print(f"  {error}")
        return len(rows) - len(errors)
    
    print(f"Successfully inserted {len(rows)} digest_items")
    return len(rows)


def main():
    parser = argparse.ArgumentParser(description="Backfill digest_items from articles table")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without making changes")
    args = parser.parse_args()
    
    print("=" * 60)
    print("Digest Items Backfill Script")
    print("=" * 60)
    
    if args.dry_run:
        print("[DRY RUN MODE - No changes will be made]")
    
    print(f"\nProject: {PROJECT_ID}")
    print(f"Dataset: {DATASET}")
    print()
    
    # Initialize BigQuery client
    client = bigquery.Client(project=PROJECT_ID)
    
    # Get missing articles
    missing_articles = get_missing_articles(client)
    
    if not missing_articles:
        print("\nNo missing articles found. digest_items is up to date!")
        return
    
    # Show breakdown by date
    print("\nMissing articles by fetch date:")
    date_counts = {}
    for article in missing_articles:
        date = article.get("fetched_at")
        if date:
            date_str = date.strftime("%Y-%m-%d")
            date_counts[date_str] = date_counts.get(date_str, 0) + 1
    
    for date_str in sorted(date_counts.keys(), reverse=True):
        print(f"  {date_str}: {date_counts[date_str]} articles")
    
    # Transform to digest items
    print("\nTransforming articles to digest_items...")
    digest_items = [transform_to_digest_item(a) for a in missing_articles]
    
    # Count feed_eligible
    eligible_count = sum(1 for item in digest_items if item["feed_eligible"])
    print(f"  Feed eligible: {eligible_count}/{len(digest_items)}")
    
    # Insert
    print()
    inserted = insert_digest_items(client, digest_items, dry_run=args.dry_run)
    
    print()
    print("=" * 60)
    print(f"Backfill complete: {inserted} digest_items {'would be ' if args.dry_run else ''}created")
    print("=" * 60)


if __name__ == "__main__":
    main()
