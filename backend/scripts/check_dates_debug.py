"""Check date distribution in SQLite."""
import sqlite3

conn = sqlite3.connect('data/c1_timeseries.db')

print("=== Articles by source_type for 2025-12-23 ===")
cur = conn.execute("""
    SELECT source_type, date(published_at) as pub, COUNT(*) as cnt 
    FROM articles 
    WHERE date(published_at) = '2025-12-23' 
    GROUP BY 1,2 
    ORDER BY 3 DESC
""")
for r in cur.fetchall():
    print(f"  {r[0]:20} | {r[1]} | {r[2]}")

print("\n=== Sample 12/23 press_release articles ===")
cur = conn.execute("""
    SELECT url, published_at, fetched_at
    FROM articles 
    WHERE date(published_at) = '2025-12-23' 
      AND source_type = 'press_release'
    LIMIT 10
""")
for r in cur.fetchall():
    print(f"  URL: {r[0][:70]}...")
    print(f"  Published: {r[1]}")
    print(f"  Fetched: {r[2]}")
    print()

print("\n=== Sample 12/23 web_news articles ===")
cur = conn.execute("""
    SELECT url, published_at, fetched_at
    FROM articles 
    WHERE date(published_at) = '2025-12-23' 
      AND source_type = 'web_news'
    LIMIT 10
""")
for r in cur.fetchall():
    print(f"  URL: {r[0][:70]}...")
    print(f"  Published: {r[1]}")
    print(f"  Fetched: {r[2]}")
    print()

conn.close()
