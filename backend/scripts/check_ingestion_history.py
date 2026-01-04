"""Check ingestion run history and data pipeline status."""
import sqlite3
import os
from datetime import datetime, timedelta

db_path = 'data/c1_corpus.db'

if not os.path.exists(db_path):
    print(f"ERROR: Database not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cur = conn.cursor()

print("=" * 70)
print("INGESTION PIPELINE STATUS CHECK")
print("=" * 70)

# Check ingestion runs
print("\n[1] INGESTION RUNS HISTORY")
print("-" * 50)
try:
    cur.execute("""
        SELECT id, started_at, completed_at, status, 
               rss_articles_fetched,
               articles_enriched, articles_stored, duplicates_skipped
        FROM ingestion_runs 
        ORDER BY started_at DESC 
        LIMIT 10
    """)
    runs = cur.fetchall()
    
    if runs:
        for run in runs:
            run_id, started, completed, status, rss, enriched, stored, dupes = run
            print(f"\nRun ID: {run_id[:8]}...")
            print(f"  Started: {started}")
            print(f"  Completed: {completed or 'N/A'}")
            print(f"  Status: {status}")
            print(f"  RSS Fetched: {rss}")
            print(f"  Enriched: {enriched}, Stored: {stored}, Duplicates: {dupes}")
    else:
        print("  No ingestion runs found!")
except sqlite3.OperationalError as e:
    print(f"  Table may not exist: {e}")

# Check article counts by date
print("\n\n[2] ARTICLES BY DATE (last 14 days)")
print("-" * 50)
try:
    cur.execute("""
        SELECT DATE(published_at) as pub_date, COUNT(*) as count
        FROM corpus_items
        WHERE published_at >= datetime('now', '-14 days')
        GROUP BY DATE(published_at)
        ORDER BY pub_date DESC
    """)
    dates = cur.fetchall()
    
    if dates:
        for date, count in dates:
            print(f"  {date}: {count} articles")
    else:
        print("  No recent articles found!")
        
    # Also check total
    cur.execute("SELECT COUNT(*) FROM corpus_items")
    total = cur.fetchone()[0]
    print(f"\n  Total articles in corpus: {total}")
except sqlite3.OperationalError as e:
    print(f"  Error: {e}")

# Check digest generation history
print("\n\n[3] DIGEST GENERATION HISTORY")
print("-" * 50)
try:
    cur.execute("""
        SELECT id, generated_at, period_start, period_end
        FROM digests 
        ORDER BY generated_at DESC 
        LIMIT 5
    """)
    digests = cur.fetchall()
    
    if digests:
        for d in digests:
            print(f"  {d[1]} - Period: {d[2]} to {d[3]}")
    else:
        print("  No digest records found!")
except sqlite3.OperationalError as e:
    print(f"  Table may not exist: {e}")

# Check briefing generation
print("\n\n[4] BRIEFING GENERATION HISTORY")
print("-" * 50)
try:
    cur.execute("""
        SELECT category, generated_at, headline
        FROM briefing_summaries 
        ORDER BY generated_at DESC 
        LIMIT 10
    """)
    briefings = cur.fetchall()
    
    if briefings:
        for b in briefings:
            print(f"  [{b[0]}] {b[1]}")
            print(f"    {b[2][:60]}...")
    else:
        print("  No briefing records found!")
except sqlite3.OperationalError as e:
    print(f"  Table may not exist: {e}")

# Summary
print("\n\n" + "=" * 70)
print("DIAGNOSIS")
print("=" * 70)

# Determine if pipeline is running
try:
    cur.execute("""
        SELECT started_at FROM ingestion_runs 
        ORDER BY started_at DESC LIMIT 1
    """)
    last_run = cur.fetchone()
    
    if last_run:
        last_run_time = datetime.fromisoformat(last_run[0].replace('Z', '+00:00').replace('+00:00', ''))
        days_since = (datetime.now() - last_run_time).days
        
        if days_since > 1:
            print(f"\n⚠️  ALERT: Last ingestion was {days_since} days ago!")
            print("   The scheduled pipeline may not be running.")
        else:
            print(f"\n✓ Pipeline appears active (last run: {last_run[0]})")
    else:
        print("\n⚠️  No ingestion runs recorded - pipeline may never have run!")
except Exception as e:
    print(f"\nCould not determine pipeline status: {e}")

conn.close()
