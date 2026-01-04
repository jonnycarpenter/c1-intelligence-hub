"""
Query BigQuery for detailed article ingestion analysis
"""
from google.cloud import bigquery
from datetime import datetime

PROJECT_ID = "gen-lang-client-0436975498"
DATASET = "c1_intelligence"

client = bigquery.Client(project=PROJECT_ID)

print("=" * 80)
print("BIGQUERY PRODUCTION DATA ANALYSIS")
print("=" * 80)
print()

# ============================================================================
# Daily Article Breakdown
# ============================================================================
print("[1] Daily Article Ingestion Since 12/29")
print("-" * 80)

query = """
SELECT 
  DATE(fetched_at) as date,
  COUNT(*) as article_count,
  COUNT(DISTINCT source_name) as unique_sources,
  STRING_AGG(DISTINCT source_name ORDER BY source_name) as sources
FROM `gen-lang-client-0436975498.c1_intelligence.corpus_items`
WHERE fetched_at >= '2025-12-29'
GROUP BY DATE(fetched_at)
ORDER BY date DESC
"""

results = list(client.query(query).result())

if results:
    for row in results:
        print(f"\n{row.date}:")
        print(f"  Articles: {row.article_count}")
        print(f"  Sources: {row.unique_sources} ({row.sources})")
else:
    print("No results found!")

print()

# ============================================================================
# Pipeline Completeness Check
# ============================================================================
print("[2] Pipeline Completeness (Articles → Digest → Embeddings)")
print("-" * 80)

pipeline_query = """
WITH article_counts AS (
  SELECT COUNT(*) as articles
  FROM `gen-lang-client-0436975498.c1_intelligence.corpus_items`
  WHERE fetched_at >= '2025-12-29'
),
digest_counts AS (
  SELECT COUNT(*) as digests
  FROM `gen-lang-client-0436975498.c1_intelligence.digest_items`
  WHERE ingested_at >= '2025-12-29'
),
embedding_counts AS (
  SELECT COUNT(DISTINCT article_id) as embedded_articles
  FROM `gen-lang-client-0436975498.c1_intelligence.article_chunk_embeddings`
  WHERE published_at >= '2025-12-29'
)
SELECT 
  a.articles,
  d.digests,
  e.embedded_articles
FROM article_counts a
CROSS JOIN digest_counts d
CROSS JOIN embedding_counts e
"""

pipeline_result = list(client.query(pipeline_query).result())[0]

print(f"Articles (corpus_items):     {pipeline_result.articles}")
print(f"Digests (digest_items):      {pipeline_result.digests}")
print(f"Embeddings (unique articles): {pipeline_result.embedded_articles}")

if pipeline_result.articles == pipeline_result.digests == pipeline_result.embedded_articles:
    print("\n✅ Pipeline is COMPLETE - all articles processed through all stages")
else:
    print("\n⚠️  Pipeline has GAPS:")
    if pipeline_result.digests < pipeline_result.articles:
        print(f"   - {pipeline_result.articles - pipeline_result.digests} articles not classified")
    if pipeline_result.embedded_articles < pipeline_result.articles:
        print(f"   - {pipeline_result.articles - pipeline_result.embedded_articles} articles not embedded")

print()

# ============================================================================
# Source Breakdown
# ============================================================================
print("[3] Source Breakdown Since 12/29")
print("-" * 80)

source_query = """
SELECT 
  source_name,
  COUNT(*) as count,
  MIN(fetched_at) as first_fetch,
  MAX(fetched_at) as last_fetch
FROM `gen-lang-client-0436975498.c1_intelligence.corpus_items`
WHERE fetched_at >= '2025-12-29'
GROUP BY source_name
ORDER BY count DESC
"""

source_results = list(client.query(source_query).result())

for row in source_results:
    print(f"{row.source_name}: {row.count} articles")
    print(f"  First: {row.first_fetch}, Last: {row.last_fetch}")

print()
print("=" * 80)
