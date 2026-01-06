"""
Migrate data from SQLite (c1_corpus.db in GCS) to BigQuery.

This script:
1. Reads corpus_items from SQLite
2. Transforms them to digest_items format  
3. Inserts into BigQuery (with deduplication by URL)
"""
import sqlite3
import json
import hashlib
from datetime import datetime
from pathlib import Path
from google.cloud import bigquery

# Configuration
PROJECT_ID = "gen-lang-client-0436975498"
DATASET_ID = "c1_intelligence"
TABLE_ID = "digest_items"
SQLITE_PATH = Path("data/c1_corpus.db")

def parse_datetime(dt_str: str) -> datetime | None:
    """Parse various datetime formats."""
    if not dt_str:
        return None
    
    formats = [
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(dt_str, fmt)
        except ValueError:
            continue
    
    # Try ISO format as fallback
    try:
        return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
    except:
        return None

def get_existing_urls(client: bigquery.Client) -> set:
    """Get all existing URLs from BigQuery to avoid duplicates."""
    query = f"""
        SELECT DISTINCT url 
        FROM `{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}`
        WHERE url IS NOT NULL
    """
    result = client.query(query).result()
    return {row.url for row in result}

def read_sqlite_items(db_path: Path) -> list[dict]:
    """Read all corpus_items from SQLite."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM corpus_items")
    items = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return items

def transform_to_digest_item(item: dict) -> dict:
    """Transform SQLite corpus_item to BigQuery digest_item format.
    
    BigQuery schema requires:
    - id, article_id, title (REQUIRED strings)
    - category, priority (REQUIRED strings)
    - classified_at, ingested_at (REQUIRED timestamps)
    - companies, materials, topics, industries are STRINGS (not arrays)
    """
    
    # Parse published_at
    published_at = parse_datetime(item.get("published_at"))
    if not published_at:
        published_at = datetime.utcnow()
    
    # Parse ingested_at
    ingested_at = parse_datetime(item.get("ingested_at"))
    if not ingested_at:
        ingested_at = datetime.utcnow()
    
    # Generate ID if missing
    item_id = item.get("id")
    if not item_id:
        item_id = hashlib.sha256(item.get("url", "").encode()).hexdigest()[:16]
    
    # Parse JSON fields and convert to comma-separated strings
    def safe_json_loads(val):
        if not val:
            return []
        if isinstance(val, list):
            return val
        try:
            return json.loads(val)
        except:
            return []
    
    def to_comma_string(val):
        items = safe_json_loads(val)
        if not items:
            return None
        return ", ".join(str(x) for x in items[:10])
    
    categories = safe_json_loads(item.get("categories"))
    primary_category = item.get("primary_category") or (categories[0] if categories else "general")
    
    return {
        "id": item_id,
        "article_id": item_id,  # Same as id for migrated items
        "title": item.get("title", "Untitled"),
        "url": item.get("url", ""),
        "source_name": item.get("source_name", ""),
        "source_type": item.get("source_type", "unknown"),
        "published_at": published_at.isoformat() if published_at else None,
        "ingested_at": ingested_at.isoformat() if ingested_at else datetime.utcnow().isoformat(),
        "classified_at": ingested_at.isoformat() if ingested_at else datetime.utcnow().isoformat(),
        "category": primary_category,
        "priority": item.get("priority", "medium") or "medium",
        "digest_summary": item.get("summary", ""),
        "original_summary": item.get("summary", ""),
        "companies": to_comma_string(item.get("companies_mentioned")),
        "materials": to_comma_string(item.get("materials_mentioned")),
        "industries": to_comma_string(item.get("industries")),
        "topics": to_comma_string(item.get("categories")),
        "relevance_score": float(item.get("relevance_score", 0.5) or 0.5),
        "confidence": 0.8,  # Default confidence for migrated items
        "classifier_model": "migration_v1",
    }

def main():
    print(f"=== SQLite to BigQuery Migration ===")
    print(f"Source: {SQLITE_PATH}")
    print(f"Target: {PROJECT_ID}.{DATASET_ID}.{TABLE_ID}")
    print()
    
    if not SQLITE_PATH.exists():
        print(f"ERROR: SQLite database not found at {SQLITE_PATH}")
        print("Run: gsutil cp gs://gen-lang-client-0436975498-c1-hub-data/c1_corpus.db data/")
        return
    
    # Read SQLite items
    print("Reading SQLite items...")
    sqlite_items = read_sqlite_items(SQLITE_PATH)
    print(f"  Found {len(sqlite_items)} items in SQLite")
    
    # Connect to BigQuery
    print("\nConnecting to BigQuery...")
    client = bigquery.Client(project=PROJECT_ID)
    
    # Get existing URLs
    print("Fetching existing URLs from BigQuery...")
    existing_urls = get_existing_urls(client)
    print(f"  Found {len(existing_urls)} existing URLs in BigQuery")
    
    # Filter and transform
    print("\nTransforming and filtering items...")
    items_to_insert = []
    skipped = 0
    
    for item in sqlite_items:
        url = item.get("url")
        if url and url in existing_urls:
            skipped += 1
            continue
        
        transformed = transform_to_digest_item(item)
        items_to_insert.append(transformed)
    
    print(f"  {len(items_to_insert)} new items to insert")
    print(f"  {skipped} items already exist (skipped)")
    
    if not items_to_insert:
        print("\nNo new items to insert. Done!")
        return
    
    # Insert into BigQuery in batches
    print(f"\nInserting into BigQuery...")
    table_ref = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"
    
    batch_size = 100
    total_inserted = 0
    errors = []
    
    for i in range(0, len(items_to_insert), batch_size):
        batch = items_to_insert[i:i + batch_size]
        try:
            result = client.insert_rows_json(table_ref, batch)
            if result:
                errors.extend(result)
                print(f"  Batch {i//batch_size + 1}: {len(result)} errors")
            else:
                total_inserted += len(batch)
                print(f"  Batch {i//batch_size + 1}: {len(batch)} rows inserted")
        except Exception as e:
            print(f"  Batch {i//batch_size + 1}: ERROR - {e}")
            errors.append(str(e))
    
    print(f"\n=== Migration Complete ===")
    print(f"  Inserted: {total_inserted} rows")
    print(f"  Skipped (duplicates): {skipped}")
    print(f"  Errors: {len(errors)}")
    
    if errors:
        print("\nFirst 5 errors:")
        for e in errors[:5]:
            print(f"  - {e}")

if __name__ == "__main__":
    main()
