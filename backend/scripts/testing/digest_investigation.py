"""Investigate digest cards data gap issue."""
from google.cloud import bigquery

client = bigquery.Client(project='<GCP_PROJECT_ID>')

print("=" * 70)
print("DIGEST CARDS INVESTIGATION - Jan 5, 2026")
print("=" * 70)

print("\n=== 1. RECENT INGESTION COUNTS ===")
query1 = '''
SELECT 
    DATE(ingested_at) as ingest_date,
    COUNT(*) as total,
    SUM(CASE WHEN feed_eligible THEN 1 ELSE 0 END) as feed_eligible
FROM `<GCP_PROJECT_ID>.c1_intelligence.digest_items` 
WHERE ingested_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 5 DAY)
GROUP BY DATE(ingested_at)
ORDER BY ingest_date DESC
'''
for r in client.query(query1).result():
    print(f"  {r.ingest_date}: {r.total} total, {r.feed_eligible} feed-eligible")

print("\n=== 2. PUBLISHED DATE DISTRIBUTION (recently ingested items) ===")
query2 = '''
SELECT 
    DATE(published_at) as pub_date,
    COUNT(*) as count
FROM `<GCP_PROJECT_ID>.c1_intelligence.digest_items` 
WHERE ingested_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 3 DAY)
GROUP BY DATE(published_at)
ORDER BY pub_date DESC
LIMIT 20
'''
for r in client.query(query2).result():
    print(f"  {r.pub_date}: {r.count} items")

print("\n=== 3. PRIORITY DISTRIBUTION (feed_eligible, last 3 days ingested) ===")
query3 = '''
SELECT priority, COUNT(*) as count
FROM `<GCP_PROJECT_ID>.c1_intelligence.digest_items` 
WHERE ingested_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 3 DAY)
  AND feed_eligible = true
GROUP BY priority
ORDER BY count DESC
'''
for r in client.query(query3).result():
    print(f"  {r.priority}: {r.count}")

print("\n=== 4. MOST RECENT HIGH PRIORITY ARTICLES (by published_at) ===")
query4 = '''
SELECT 
    title, 
    CAST(published_at AS STRING) as pub,
    CAST(ingested_at AS STRING) as ing,
    source_type
FROM `<GCP_PROJECT_ID>.c1_intelligence.digest_items` 
WHERE LOWER(priority) = 'high'
  AND feed_eligible = true
ORDER BY published_at DESC
LIMIT 15
'''
for r in client.query(query4).result():
    print(f"  {r.pub[:10]} | {r.ing[:10]} | {r.source_type:15} | {r.title[:45]}")

print("\n=== 5. WHAT'S ACTUALLY MOST RECENT IN THE FEED? ===")
print("(feed_eligible=true, ordered by published_at DESC)")
query5 = '''
SELECT 
    title, 
    priority,
    CAST(published_at AS STRING) as pub,
    source_type
FROM `<GCP_PROJECT_ID>.c1_intelligence.digest_items` 
WHERE feed_eligible = true
ORDER BY published_at DESC
LIMIT 20
'''
for r in client.query(query5).result():
    print(f"  {r.pub[:10]} | {r.priority:8} | {r.source_type:15} | {r.title[:40]}")

print("\n=== 6. COUNT OF HIGH PRIORITY IN LAST 7 DAYS BY PUBLISHED_AT ===")
query6 = '''
SELECT 
    DATE(published_at) as pub_date,
    COUNT(*) as high_priority_count
FROM `<GCP_PROJECT_ID>.c1_intelligence.digest_items` 
WHERE LOWER(priority) = 'high'
  AND feed_eligible = true
  AND published_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
GROUP BY DATE(published_at)
ORDER BY pub_date DESC
'''
results = list(client.query(query6).result())
if results:
    for r in results:
        print(f"  {r.pub_date}: {r.high_priority_count} high-priority articles")
else:
    print("  NO HIGH PRIORITY ARTICLES in last 7 days!")
