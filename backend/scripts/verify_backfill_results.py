"""
Quick BigQuery verification of backfill results
"""
from google.cloud import bigquery

PROJECT_ID = "gen-lang-client-0436975498"
DATASET = "c1_intelligence"

client = bigquery.Client(project=PROJECT_ID)

print("=" * 80)
print("BACKFILL VERIFICATION - BIGQUERY DATA CHECK")
print("=" * 80)
print()

# 1. Check articles by day
print("📊 ARTICLES INGESTED (Last 7 Days):")
print("-" * 80)
query1 = f"""
SELECT 
    DATE(created_at) as date,
    COUNT(*) as total_count,
    COUNTIF(relevance_score > 0.6) as high_relevance_count
FROM `{PROJECT_ID}.{DATASET}.articles`
WHERE DATE(created_at) >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
GROUP BY date
ORDER BY date DESC
"""
for row in client.query(query1).result():
    print(f"  {row.date}: {row.total_count} articles ({row.high_relevance_count} high-relevance)")

# 2. Check digest items
print()
print("📝 DIGEST ITEMS (Last 7 Days):")
print("-" * 80)
query2 = f"""
SELECT 
    DATE(created_at) as date,
    COUNT(*) as digest_count
FROM `{PROJECT_ID}.{DATASET}.digest_items`
WHERE DATE(created_at) >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
GROUP BY date
ORDER BY date DESC
"""
for row in client.query(query2).result():
    print(f"  {row.date}: {row.digest_count} digest items")

# 3. Check vector embeddings
print()
print("🔍 VECTOR EMBEDDINGS (Last 7 Days):")
print("-" * 80)
query3 = f"""
SELECT 
    DATE(created_at) as date,
    COUNT(*) as chunk_count
FROM `{PROJECT_ID}.{DATASET}.article_chunk_embeddings`
WHERE DATE(created_at) >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
GROUP BY date
ORDER BY date DESC
"""
for row in client.query(query3).result():
    print(f"  {row.date}: {row.chunk_count} chunks")

# 4. Check article images
print()
print("🖼️  ARTICLE IMAGES (Last 7 Days):")
print("-" * 80)
query4 = f"""
SELECT 
    COUNT(*) as total_images,
    MIN(created_at) as first_created,
    MAX(created_at) as last_created
FROM `{PROJECT_ID}.{DATASET}.article_images`
WHERE DATE(created_at) >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
"""
result = list(client.query(query4).result())
if result:
    row = result[0]
    print(f"  Total Images: {row.total_images}")
    if row.total_images > 0:
        print(f"  First Image: {row.first_created}")
        print(f"  Last Image: {row.last_created}")
    else:
        print()
        print("  ⚠️  NO IMAGES EXTRACTED")
        print()
        print("  This is EXPECTED if:")
        print("    1. No articles exceeded relevance_score > 0.6 threshold")
        print("    2. Image extraction was skipped during backfill mode")
        print()
        # Check if we have any high-relevance articles
        check_query = f"""
        SELECT COUNT(*) as high_rel_count
        FROM `{PROJECT_ID}.{DATASET}.articles`
        WHERE DATE(created_at) >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
        AND relevance_score > 0.6
        """
        high_rel = list(client.query(check_query).result())[0].high_rel_count
        print(f"  📌 High-relevance articles available: {high_rel}")
        if high_rel > 0:
            print("     → Image extraction SHOULD have run - check orchestrator logic")
        else:
            print("     → No high-relevance articles, image skip is CORRECT")

print()
print("=" * 80)
print("VERIFICATION COMPLETE")
print("=" * 80)
