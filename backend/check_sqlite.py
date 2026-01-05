"""Check contents of the SQLite database from GCS."""
import sqlite3
from pathlib import Path

db_path = Path("data/c1_corpus.db")

if not db_path.exists():
    print(f"Database not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [t[0] for t in cursor.fetchall()]
print(f"Tables: {tables}")

# Check counts for each table
for table in tables:
    cursor.execute(f"SELECT COUNT(*) FROM {table}")
    count = cursor.fetchone()[0]
    print(f"  {table}: {count} rows")

# If corpus_items exists, show date range
if "corpus_items" in tables:
    # First get schema
    cursor.execute("PRAGMA table_info(corpus_items)")
    cols = [c[1] for c in cursor.fetchall()]
    print(f"\n--- corpus_items columns ---")
    print(f"  {cols[:10]}...")  # First 10 columns
    
    # Find date column
    date_col = None
    for c in ["published_date", "published_at", "created_at", "ingested_at"]:
        if c in cols:
            date_col = c
            break
    
    if date_col:
        print(f"\n--- corpus_items date range ({date_col}) ---")
        cursor.execute(f"SELECT MIN({date_col}), MAX({date_col}), COUNT(*) FROM corpus_items")
        row = cursor.fetchone()
        print(f"  {row[0]} to {row[1]} ({row[2]} items)")
    
    # Group by source type
    print("\n--- By source type ---")
    cursor.execute("SELECT source_type, COUNT(*) as cnt FROM corpus_items GROUP BY source_type ORDER BY cnt DESC")
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]}")

# If digest_items exists, show date range
if "digest_items" in tables:
    print("\n--- digest_items date range ---")
    cursor.execute("SELECT MIN(published_at), MAX(published_at), COUNT(*) FROM digest_items")
    row = cursor.fetchone()
    print(f"  Published: {row[0]} to {row[1]} ({row[2]} items)")

conn.close()
