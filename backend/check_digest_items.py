"""Check digest_items table status."""
from google.cloud import bigquery

client = bigquery.Client(project='gen-lang-client-0436975498')

# Check schema
print("=== digest_items schema ===")
query = """
SELECT column_name, data_type
FROM c1_intelligence.INFORMATION_SCHEMA.COLUMNS
WHERE table_name = 'digest_items'
"""
for row in client.query(query).result():
    print(f"  {row.column_name}: {row.data_type}")

# Check stats
print("\n=== digest_items stats ===")
query = """
SELECT 
    COUNT(*) as total_rows,
    COUNT(DISTINCT article_id) as unique_articles,
    MIN(ingested_at) as earliest,
    MAX(ingested_at) as latest
FROM c1_intelligence.digest_items
"""
for row in client.query(query).result():
    print(f"  Total rows: {row.total_rows}")
    print(f"  Unique articles: {row.unique_articles}")
    print(f"  Date range: {row.earliest} to {row.latest}")

# Check if migrated articles are in digest_items
print("\n=== Migrated articles in digest_items? ===")
query = """
SELECT 
    a.id,
    a.title,
    a.fetched_at,
    d.article_id IS NOT NULL as in_digest
FROM c1_intelligence.articles a
LEFT JOIN c1_intelligence.digest_items d ON a.id = d.article_id
WHERE a.fetched_at >= TIMESTAMP('2025-12-29')
  AND a.fetched_at < TIMESTAMP('2026-01-04')
ORDER BY a.fetched_at DESC
LIMIT 20
"""
in_digest = 0
not_in_digest = 0
for row in client.query(query).result():
    status = "✓" if row.in_digest else "✗"
    print(f"  {status} {row.fetched_at.strftime('%m/%d %H:%M')} - {row.title[:60]}")
    if row.in_digest:
        in_digest += 1
    else:
        not_in_digest += 1

print(f"\n  In digest: {in_digest}, Not in digest: {not_in_digest}")
