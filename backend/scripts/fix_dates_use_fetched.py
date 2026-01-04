"""
Fix articles where date extraction failed by using fetched_at as fallback.

The date_extraction module can't extract dates from:
- Zacks, Benzinga, SeekingAlpha, Barrons (no date in URL or content)
- RSS feeds where published_at was set incorrectly

For these, fetched_at is a reasonable approximation since articles
are typically fetched within hours of publication.
"""
import sqlite3
from datetime import datetime

DB_PATH = "data/c1_timeseries.db"

def fix_dates():
    conn = sqlite3.connect(DB_PATH)
    
    # Find all articles where published_at == the bad timestamps (today's date)
    # These are articles where extraction failed and fell back to datetime.utcnow()
    today = datetime.utcnow().date().isoformat()
    
    print("=== Checking for articles with today's date that were fetched earlier ===")
    
    cur = conn.execute("""
        SELECT id, url, source_type, published_at, fetched_at
        FROM articles
        WHERE date(published_at) = ?
          AND date(fetched_at) != date(published_at)
    """, (today,))
    
    articles = cur.fetchall()
    print(f"Found {len(articles)} articles with mismatched pub/fetch dates")
    
    if not articles:
        print("No articles need fixing!")
        conn.close()
        return
    
    # Show breakdown by source type
    cur = conn.execute("""
        SELECT source_type, COUNT(*) as cnt
        FROM articles
        WHERE date(published_at) = ?
          AND date(fetched_at) != date(published_at)
        GROUP BY 1
        ORDER BY 2 DESC
    """, (today,))
    
    print("\n=== Breakdown by source_type ===")
    for r in cur.fetchall():
        print(f"  {r[0]:20} : {r[1]}")
    
    # Show sample
    print("\n=== Sample articles ===")
    for article in articles[:5]:
        article_id, url, source_type, pub_at, fetch_at = article
        print(f"\n  URL: {url[:60]}...")
        print(f"  Source: {source_type}")
        print(f"  Published: {pub_at}")
        print(f"  Fetched: {fetch_at}")
        print(f"  Will change to: {fetch_at}")
    
    # Confirm
    confirm = input(f"\nUpdate {len(articles)} articles to use fetched_at? (y/n): ")
    if confirm.lower() != 'y':
        print("Aborted.")
        conn.close()
        return
    
    # Update articles: set published_at = fetched_at
    print("\nUpdating articles...")
    conn.execute("""
        UPDATE articles
        SET published_at = fetched_at
        WHERE date(published_at) = ?
          AND date(fetched_at) != date(published_at)
    """, (today,))
    conn.commit()
    print(f"Updated {len(articles)} articles")
    
    # Update digest_items too
    print("\nUpdating digest_items...")
    conn.execute("""
        UPDATE digest_items
        SET published_at = (
            SELECT a.fetched_at 
            FROM articles a 
            WHERE a.id = digest_items.article_id
        )
        WHERE article_id IN (
            SELECT id FROM articles 
            WHERE date(published_at) = date(fetched_at)
        )
    """)
    conn.commit()
    print("Updated digest_items")
    
    # Verify
    print("\n=== Verification ===")
    cur = conn.execute("""
        SELECT date(published_at) as pub, COUNT(*) as cnt
        FROM articles
        GROUP BY 1
        ORDER BY 1 DESC
        LIMIT 10
    """)
    print("Date distribution after fix:")
    for r in cur.fetchall():
        print(f"  {r[0]} : {r[1]}")
    
    conn.close()
    print("\n✅ Fix complete!")


if __name__ == "__main__":
    fix_dates()
