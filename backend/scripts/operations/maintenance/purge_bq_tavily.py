"""Purge Tavily-sourced data from BigQuery tables."""
from google.cloud import bigquery

PROJECT = "<GCP_PROJECT_ID>"
DATASET = "c1_intelligence"

client = bigquery.Client(project=PROJECT)

# Purge from digest_items
print("Purging press_release and web_news from digest_items...")
query1 = f"""
DELETE FROM `{PROJECT}.{DATASET}.digest_items` 
WHERE source_type IN ('press_release', 'web_news')
"""
client.query(query1).result()
print("Done with digest_items")

# Purge from articles table too
print("Purging press_release and web_news from articles...")
query2 = f"""
DELETE FROM `{PROJECT}.{DATASET}.articles` 
WHERE source_type IN ('press_release', 'web_news')
"""
try:
    client.query(query2).result()
    print("Done with articles")
except Exception as e:
    print(f"Articles table error (may not exist): {e}")

# Check remaining counts
print("\nRemaining counts in digest_items:")
query3 = f"""
SELECT source_type, COUNT(*) as count 
FROM `{PROJECT}.{DATASET}.digest_items` 
GROUP BY source_type 
ORDER BY count DESC
"""
for row in client.query(query3).result():
    print(f"  {row.source_type}: {row.count}")
