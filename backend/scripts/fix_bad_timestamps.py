"""
Fix the 502 articles with bad 2025-12-23T04:08:06 timestamp.

These articles had date extraction fail and fell back to datetime.utcnow()
which happened to be 2025-12-23T04:08:06 when the script ran.

Strategy:
1. For articles with extractable dates (URL patterns), extract and update
2. For articles without extractable dates, use fetched_at as a fallback
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
from datetime import datetime
from app.utils.date_extraction import extract_publication_date

DB_PATH = "data/c1_timeseries.db"
BAD_TIMESTAMP = "2025-12-23T04:08:06"

def fix_bad_dates():
    conn = sqlite3.connect(DB_PATH)
    
    # Get all articles with the bad timestamp
    cur = conn.execute("""
        SELECT id, url, summary, source_type, fetched_at 
        FROM articles 
        WHERE published_at LIKE ?
    """, (f"%{BAD_TIMESTAMP}%",))
    
    articles = cur.fetchall()
    print(f"Found {len(articles)} articles with bad timestamp")
    
    extracted_count = 0
    fallback_count = 0
    updates = []
    
    for article_id, url, summary, source_type, fetched_at in articles:
        # Try to extract the real publication date
        extracted_date = extract_publication_date(
            url=url,
            content=summary or "",
            api_date=None,
            fallback=None  # Don't use fallback - we want to know if extraction worked
        )
        
        if extracted_date:
            new_date = extracted_date.isoformat()
            extracted_count += 1
        else:
            # Fallback to fetched_at date (better than wrong date)
            new_date = fetched_at
            fallback_count += 1
        
        updates.append((new_date, article_id))
    
    print(f"\nResults:")
    print(f"  Extracted from URL/content: {extracted_count}")
    print(f"  Fallback to fetched_at: {fallback_count}")
    
    # Show sample of changes
    print("\n=== Sample changes ===")
    sample_cur = conn.execute("""
        SELECT id, url, published_at, fetched_at 
        FROM articles 
        WHERE published_at LIKE ?
        LIMIT 5
    """, (f"%{BAD_TIMESTAMP}%",))
    
    for row in sample_cur.fetchall():
        article_id = row[0]
        url = row[1]
        old_pub = row[2]
        fetched = row[3]
        
        # Find the new date for this article
        new_date = next((u[0] for u in updates if u[1] == article_id), None)
        
        print(f"\n  URL: {url[:60]}...")
        print(f"  Old published_at: {old_pub}")
        print(f"  New published_at: {new_date}")
        print(f"  Fetched_at: {fetched}")
    
    # Confirm
    confirm = input(f"\nUpdate {len(updates)} articles? (y/n): ")
    if confirm.lower() != 'y':
        print("Aborted.")
        conn.close()
        return
    
    # Apply updates
    print("\nUpdating SQLite...")
    conn.executemany("""
        UPDATE articles SET published_at = ? WHERE id = ?
    """, updates)
    conn.commit()
    print(f"Updated {len(updates)} articles in SQLite")
    
    # Also update digest_items
    print("\nUpdating digest_items...")
    for new_date, article_id in updates:
        conn.execute("""
            UPDATE digest_items SET published_at = ? WHERE article_id = ?
        """, (new_date, article_id))
    conn.commit()
    print("Updated digest_items")
    
    # Verify
    cur = conn.execute("""
        SELECT COUNT(*) FROM articles WHERE published_at LIKE ?
    """, (f"%{BAD_TIMESTAMP}%",))
    remaining = cur.fetchone()[0]
    print(f"\nArticles still with bad timestamp: {remaining}")
    
    conn.close()
    print("\n✅ SQLite fix complete!")
    print("\nNext steps:")
    print("1. Re-sync to BigQuery: python scripts/sync_sqlite_to_bigquery.py")
    print("2. Update article_tags dates in BigQuery")


if __name__ == "__main__":
    fix_bad_dates()
