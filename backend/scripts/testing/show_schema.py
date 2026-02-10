#!/usr/bin/env python3
"""Show SQLite schema."""
import sqlite3

conn = sqlite3.connect('data/c1_timeseries.db')

# Get tables
tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
print("TABLES:", tables)

# Show schema for each
for table in tables:
    print(f"\n=== {table} ===")
    cur = conn.execute(f"PRAGMA table_info({table})")
    for row in cur:
        print(f"  {row[1]}: {row[2]}")
    
    # Row count
    count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    print(f"  [Rows: {count}]")

conn.close()
