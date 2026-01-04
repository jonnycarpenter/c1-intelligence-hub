"""Check articles with bad published_at dates."""
import sqlite3

conn = sqlite3.connect('data/c1_timeseries.db')

total = conn.execute('SELECT COUNT(*) FROM articles').fetchone()[0]

print(f"Total articles: {total}")

print("\n=== Date distribution (top 15) ===")
cur = conn.execute("""
    SELECT DATE(published_at) as pub_date, COUNT(*) as cnt 
    FROM articles 
    GROUP BY 1 
    ORDER BY 1 DESC 
    LIMIT 15
""")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]}")

print("\n=== Articles on 12/23 - breakdown ===")
cur = conn.execute("""
    SELECT 
        CASE 
            WHEN published_at LIKE '2025-12-23T04:08:%' THEN 'bad_batch_import'
            WHEN published_at LIKE '2025-12-23T00:00:00%' THEN 'midnight_maybe_ok'
            ELSE 'other_time'
        END as date_type,
        COUNT(*) as cnt
    FROM articles 
    WHERE DATE(published_at) = '2025-12-23'
    GROUP BY 1
""")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]}")

print("\n=== Bad batch import articles by source_type ===")
cur = conn.execute("""
    SELECT source_type, COUNT(*) as cnt 
    FROM articles 
    WHERE published_at LIKE '2025-12-23T04:08:%'
    GROUP BY source_type 
    ORDER BY cnt DESC
""")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]}")

print("\n=== These bad articles were fetched on these dates ===")
cur = conn.execute("""
    SELECT DATE(fetched_at) as fetch_date, COUNT(*) as cnt 
    FROM articles 
    WHERE published_at LIKE '2025-12-23T04:08:%'
    GROUP BY 1
    ORDER BY 1
""")
for row in cur.fetchall():
    print(f"  Fetched {row[0]}: {row[1]} articles")

conn.close()

print("\n=== Bad dates by source_type ===")
cur = conn.execute("""
    SELECT source_type, COUNT(*) as cnt 
    FROM articles 
    WHERE published_at LIKE '2025-12-23T04:08:06%'
    GROUP BY source_type 
    ORDER BY cnt DESC
""")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]}")

print("\n=== These articles have fetched_at dates we can use instead ===")
cur = conn.execute("""
    SELECT source_type, DATE(fetched_at) as fetch_date, COUNT(*) as cnt 
    FROM articles 
    WHERE published_at LIKE '2025-12-23T04:08:06%'
    GROUP BY source_type, DATE(fetched_at)
    ORDER BY source_type, fetch_date
""")
for row in cur.fetchall():
    print(f"  {row[0]} | fetched {row[1]} | {row[2]} articles")

conn.close()
