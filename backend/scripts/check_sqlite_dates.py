"""Quick check of SQLite article dates for Tavily sources."""
import sqlite3

conn = sqlite3.connect('data/c1_timeseries.db')

print("=== Source Type Distribution ===")
cur = conn.execute('''
    SELECT source_type, COUNT(*) as cnt 
    FROM articles 
    GROUP BY source_type 
    ORDER BY cnt DESC
''')
for r in cur.fetchall():
    print(f"  {r[0]:20} : {r[1]}")

print("\n=== Tavily Sources: Date Comparison ===")
cur = conn.execute('''
    SELECT source_type, 
           date(published_at) as pub_date, 
           date(fetched_at) as fetch_date, 
           COUNT(*) as cnt 
    FROM articles 
    WHERE source_type IN ('web_news', 'press_release')
    GROUP BY 1,2,3 
    ORDER BY 2 DESC 
    LIMIT 30
''')
print(f"{'source_type':15} | {'pub_date':12} | {'fetch_date':12} | cnt")
print("-" * 55)
for r in cur.fetchall():
    match = "✅" if r[1] != r[2] else "⚠️ SAME"
    print(f"{r[0]:15} | {r[1]} | {r[2]} | {r[3]:4} {match}")

print("\n=== Tavily: Articles where pub_date == fetch_date ===")
cur = conn.execute('''
    SELECT COUNT(*) 
    FROM articles 
    WHERE source_type IN ('web_news', 'press_release')
      AND date(published_at) = date(fetched_at)
''')
same_date_count = cur.fetchone()[0]

cur = conn.execute('''
    SELECT COUNT(*) 
    FROM articles 
    WHERE source_type IN ('web_news', 'press_release')
''')
total_tavily = cur.fetchone()[0]

print(f"  Same date: {same_date_count} / {total_tavily} ({100*same_date_count/total_tavily:.1f}%)")

print("\n=== Sample of articles with same pub/fetch dates ===")
cur = conn.execute('''
    SELECT id, url, source_type, published_at, fetched_at
    FROM articles 
    WHERE source_type IN ('web_news', 'press_release')
      AND date(published_at) = date(fetched_at)
    LIMIT 5
''')
for r in cur.fetchall():
    print(f"\n  ID: {r[0][:8]}...")
    print(f"  URL: {r[1][:80]}...")
    print(f"  Type: {r[2]}")
    print(f"  Published: {r[3]}")
    print(f"  Fetched: {r[4]}")

conn.close()
