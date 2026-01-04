"""Investigate the 2025-12-23T04:08:06 timestamp issue."""
import sqlite3

conn = sqlite3.connect('data/c1_timeseries.db')

# Count articles with the suspicious timestamp
cur = conn.execute("""
    SELECT COUNT(*) 
    FROM articles 
    WHERE published_at LIKE '%2025-12-23T04:08:06%'
""")
print(f"Articles with 2025-12-23T04:08:06 timestamp: {cur.fetchone()[0]}")

# Count by source type
print("\n=== Breakdown by source_type ===")
cur = conn.execute("""
    SELECT source_type, COUNT(*) as cnt 
    FROM articles 
    WHERE published_at LIKE '%2025-12-23T04:08:06%'
    GROUP BY 1 
    ORDER BY 2 DESC
""")
for r in cur.fetchall():
    print(f"  {r[0]:20} : {r[1]}")

# Check distinct fetched_at dates for these articles
print("\n=== Fetched_at dates for these articles ===")
cur = conn.execute("""
    SELECT date(fetched_at) as fetch_date, COUNT(*) as cnt 
    FROM articles 
    WHERE published_at LIKE '%2025-12-23T04:08:06%'
    GROUP BY 1 
    ORDER BY 1 DESC
""")
for r in cur.fetchall():
    print(f"  {r[0]} : {r[1]}")

# Sample URLs from prnewswire (should have date in URL)
print("\n=== Sample PRNewswire URLs (should have dates) ===")
cur = conn.execute("""
    SELECT url 
    FROM articles 
    WHERE published_at LIKE '%2025-12-23T04:08:06%'
      AND url LIKE '%prnewswire%'
    LIMIT 10
""")
for r in cur.fetchall():
    print(f"  {r[0]}")

conn.close()
