import sqlite3
from datetime import datetime

conn = sqlite3.connect('data/c1_corpus.db')
cursor = conn.cursor()

# Count articles since 12/29
cursor.execute("""
    SELECT COUNT(*) 
    FROM corpus_items 
    WHERE ingested_at >= '2025-12-29'
""")
recent_count = cursor.fetchone()[0]

# Total count
cursor.execute("SELECT COUNT(*) FROM corpus_items")
total_count = cursor.fetchone()[0]

# Daily breakdown since 12/29
cursor.execute("""
    SELECT DATE(ingested_at) as date, COUNT(*) as count
    FROM corpus_items
    WHERE ingested_at >= '2025-12-29'
    GROUP BY DATE(ingested_at)
    ORDER BY date
""")
daily = cursor.fetchall()

print(f"=== SQLite Local Database (c1_corpus.db) ===")
print(f"Total articles: {total_count}")
print(f"Articles since 12/29: {recent_count}")
print(f"\nDaily breakdown:")
for row in daily:
    print(f"  {row[0]}: {row[1]} articles")

# Get latest ingested_at
cursor.execute("SELECT MAX(ingested_at) FROM corpus_items")
latest = cursor.fetchone()[0]
print(f"\nLatest article ingested: {latest}")

conn.close()
