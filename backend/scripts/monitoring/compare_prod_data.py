"""
Compare BigQuery vs SQLite article counts since 12/29
"""
import sqlite3
from google.cloud import bigquery
from datetime import datetime

PROJECT_ID = "<GCP_PROJECT_ID>"
DATASET = "c1_intelligence"
CUTOFF_DATE = "2025-12-29"

print("=" * 80)
print("PRODUCTION DATA HEALTH CHECK")
print("=" * 80)
print(f"Comparing article counts since {CUTOFF_DATE}")
print()

# ============================================================================
# SQLite Local Database
# ============================================================================
print("[1] SQLite Local Database (c1_corpus.db)")
print("-" * 80)
try:
    conn = sqlite3.connect('data/c1_corpus.db')
    cursor = conn.cursor()
    
    # Total count
    cursor.execute("SELECT COUNT(*) FROM corpus_items")
    total = cursor.fetchone()[0]
    
    # Recent count
    cursor.execute(f"""
        SELECT COUNT(*) FROM corpus_items 
        WHERE ingested_at >= '{CUTOFF_DATE}'
    """)
    recent = cursor.fetchone()[0]
    
    # Daily breakdown
    cursor.execute(f"""
        SELECT DATE(ingested_at) as date, COUNT(*) as count
        FROM corpus_items
        WHERE ingested_at >= '{CUTOFF_DATE}'
        GROUP BY DATE(ingested_at)
        ORDER BY date
    """)
    daily_breakdown = cursor.fetchall()
    
    # Latest article
    cursor.execute("SELECT MAX(ingested_at) FROM corpus_items")
    latest = cursor.fetchone()[0]
    
    print(f"Total articles: {total}")
    print(f"Articles since {CUTOFF_DATE}: {recent}")
    print(f"Latest article: {latest}")
    print("\nDaily breakdown:")
    for date, count in daily_breakdown:
        print(f"  {date}: {count} articles")
    
    conn.close()
    
except Exception as e:
    print(f"ERROR: {e}")

print()

# ============================================================================
# BigQuery Production Database
# ============================================================================
print("[2] BigQuery Production Database (c1_intelligence.corpus_items)")
print("-" * 80)
try:
    client = bigquery.Client(project=PROJECT_ID)
    
    # Total count
    query = f"""
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN fetched_at >= '{CUTOFF_DATE}' THEN 1 END) as recent,
            MAX(fetched_at) as latest_fetch
        FROM `{PROJECT_ID}.{DATASET}.corpus_items`
    """
    result = list(client.query(query).result())[0]
    
    print(f"Total articles: {result.total}")
    print(f"Articles since {CUTOFF_DATE}: {result.recent}")
    print(f"Latest article: {result.latest_fetch}")
    
    # Daily breakdown
    daily_query = f"""
        SELECT 
            DATE(fetched_at) as date,
            COUNT(*) as count
        FROM `{PROJECT_ID}.{DATASET}.corpus_items`
        WHERE fetched_at >= '{CUTOFF_DATE}'
        GROUP BY DATE(fetched_at)
        ORDER BY date
    """
    daily_results = list(client.query(daily_query).result())
    
    print("\nDaily breakdown:")
    for row in daily_results:
        print(f"  {row.date}: {row.count} articles")
    
except Exception as e:
    print(f"ERROR: {e}")
    print("Note: You may need to run 'gcloud auth application-default login'")

print()
print("=" * 80)
print("ANALYSIS")
print("=" * 80)
print()
print("KEY QUESTIONS:")
print("1. Are the counts significantly different?")
print("   → If yes, production may not be syncing properly")
print()
print("2. When was the last article in each system?")
print("   → Helps identify if ingestion is actively running")
print()
print("3. Expected ingestion rate:")
print("   → 2x daily runs (8 AM, 8 PM Central)")
print("   → Max 150 articles/run = ~300 articles/day potential")
print("   → Actual rate: ~30-80 articles/run typical")
print()
print("4. Is 157 articles over 5 days good?")
print("   → 12/29 to 1/3 = ~5 days")
print("   → ~31 articles/day average")
print("   → This is BELOW expected if scheduler is running 2x daily")
print("   → Suggestion: Check Cloud Scheduler execution logs")
print()
