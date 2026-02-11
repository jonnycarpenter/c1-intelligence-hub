"""
Check BigQuery data completeness and backfill status
"""
from google.cloud import bigquery

PROJECT_ID = "<GCP_PROJECT_ID>"
DATASET = "c1_intelligence"

client = bigquery.Client(project=PROJECT_ID)

print("=" * 80)
print("PRODUCTION DATA HEALTH CHECK")
print("=" * 80)
print()

# Check articles vs digest_items parity
query = """
SELECT 
  'Articles' as table_name,
  COUNT(*) as count
FROM `<GCP_PROJECT_ID>.c1_intelligence.corpus_items`
WHERE fetched_at >= '2025-12-29'

UNION ALL

SELECT 
  'Digest Items' as table_name,
  COUNT(*) as count
FROM `<GCP_PROJECT_ID>.c1_intelligence.digest_items`
WHERE ingested_at >= '2025-12-29'
"""

results = list(client.query(query).result())

articles_count = next((r.count for r in results if r.table_name == 'Articles'), 0)
digest_count = next((r.count for r in results if r.table_name == 'Digest Items'), 0)

print("Articles since 12/29:", articles_count)
print("Digest items since 12/29:", digest_count)
print()

if articles_count == digest_count:
    print("✅ Pipeline is COMPLETE - all articles have digest items")
else:
    print(f"⚠️  Pipeline GAP: {articles_count - digest_count} articles missing digest classification")

print()
print("=" * 80)
