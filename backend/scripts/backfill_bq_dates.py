"""
Backfill published_at dates for Tavily-sourced articles in BigQuery.

These articles (web_news, press_release) had incorrect dates where
published_at was set to ingestion time instead of actual publication date.

This script:
1. Queries articles with source_type in ('web_news', 'press_release')
2. Extracts actual publication dates from URL patterns and content
3. Updates the articles and digest_items tables in BigQuery
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from google.cloud import bigquery
from app.utils.date_extraction import extract_publication_date

PROJECT_ID = "gen-lang-client-0436975498"
DATASET = "c1_intelligence"

def backfill_bigquery_dates():
    """Backfill dates for Tavily-sourced articles in BigQuery."""
    client = bigquery.Client(project=PROJECT_ID)
    
    # Query articles that need backfilling
    query = f"""
    SELECT id, url, summary, source_type, published_at, fetched_at
    FROM `{PROJECT_ID}.{DATASET}.articles`
    WHERE source_type IN ('web_news', 'press_release')
    """
    
    print("Querying articles to backfill...")
    results = list(client.query(query))
    print(f"Found {len(results)} articles to process")
    
    updates = []
    skipped = 0
    fixed = 0
    
    for row in results:
        article_id = row.id
        url = row.url
        content = row.summary or ""
        
        # Extract the actual publication date
        extracted_date = extract_publication_date(
            url=url,
            content=content,
            api_date=None,
            fallback=None  # Don't fallback - we want to know if extraction failed
        )
        
        if extracted_date is None:
            # Couldn't extract date, keep original
            skipped += 1
            continue
        
        # Check if extracted date is different from current published_at
        current_date = row.published_at
        if current_date and abs((extracted_date - current_date).days) < 1:
            # Dates are close enough, skip
            skipped += 1
            continue
        
        updates.append({
            "id": article_id,
            "published_at": extracted_date.isoformat(),
            "url": url,
            "old_date": str(current_date),
            "new_date": extracted_date.strftime("%Y-%m-%d")
        })
        fixed += 1
    
    print(f"\nExtraction complete:")
    print(f"  - Articles to update: {fixed}")
    print(f"  - Skipped (no change): {skipped}")
    
    if not updates:
        print("No updates needed!")
        return
    
    # Show sample of changes
    print("\nSample changes:")
    for u in updates[:5]:
        print(f"  {u['url'][:60]}...")
        print(f"    {u['old_date']} -> {u['new_date']}")
    
    # Confirm before updating
    confirm = input(f"\nProceed with updating {len(updates)} articles? (y/n): ")
    if confirm.lower() != 'y':
        print("Aborted.")
        return
    
    # Update articles table
    print("\nUpdating articles table...")
    for update in updates:
        update_query = f"""
        UPDATE `{PROJECT_ID}.{DATASET}.articles`
        SET published_at = TIMESTAMP('{update['published_at']}')
        WHERE id = '{update['id']}'
        """
        client.query(update_query).result()
    print(f"  Updated {len(updates)} articles")
    
    # Update digest_items table (uses article_id foreign key)
    print("\nUpdating digest_items table...")
    for update in updates:
        update_query = f"""
        UPDATE `{PROJECT_ID}.{DATASET}.digest_items`
        SET published_at = TIMESTAMP('{update['published_at']}')
        WHERE article_id = '{update['id']}'
        """
        client.query(update_query).result()
    print(f"  Updated digest_items")
    
    print("\n✅ Backfill complete!")


if __name__ == "__main__":
    backfill_bigquery_dates()
