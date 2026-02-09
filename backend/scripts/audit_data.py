"""Quick data audit for narratives backfill planning."""
from google.cloud import bigquery

client = bigquery.Client(project='gen-lang-client-0436975498')

# 1. Total articles from Nov 1
q1 = """
SELECT 
  COUNT(*) as total,
  COUNTIF(full_text IS NOT NULL AND full_text != '') as has_full_text,
  COUNTIF(full_text IS NULL OR full_text = '') as no_full_text,
  MIN(published_at) as earliest,
  MAX(published_at) as latest
FROM `gen-lang-client-0436975498.c1_intelligence.articles`
WHERE published_at >= '2025-11-01'
"""
print('=== ARTICLES TABLE (Nov 1+) ===')
for row in client.query(q1):
    print(f'Total: {row.total}')
    print(f'Has full_text: {row.has_full_text}')
    print(f'No full_text: {row.no_full_text}')
    print(f'Range: {row.earliest} to {row.latest}')

# 2. Digest items from Nov 1
q2 = """
SELECT 
  COUNT(*) as total,
  COUNTIF(materials IS NOT NULL AND materials != '[]' AND materials != '') as has_materials,
  COUNTIF(industries IS NOT NULL AND industries != '[]' AND industries != '') as has_industries,
  COUNTIF(companies IS NOT NULL AND companies != '[]' AND companies != '') as has_companies,
  COUNTIF(headline IS NOT NULL AND headline != '') as has_headline,
  COUNTIF(digest_summary IS NOT NULL AND digest_summary != '') as has_summary,
  MIN(published_at) as earliest,
  MAX(published_at) as latest
FROM `gen-lang-client-0436975498.c1_intelligence.digest_items`
WHERE published_at >= '2025-11-01'
"""
print()
print('=== DIGEST_ITEMS TABLE (Nov 1+) ===')
for row in client.query(q2):
    print(f'Total: {row.total}')
    print(f'Has materials: {row.has_materials}')
    print(f'Has industries: {row.has_industries}')
    print(f'Has companies: {row.has_companies}')
    print(f'Has headline: {row.has_headline}')
    print(f'Has summary: {row.has_summary}')
    print(f'Range: {row.earliest} to {row.latest}')

# 3. Monthly breakdown  
q3 = """
SELECT 
  FORMAT_TIMESTAMP('%Y-%m', published_at) as month,
  COUNT(*) as count,
  COUNTIF(materials IS NOT NULL AND materials != '[]' AND materials != '') as has_materials,
  COUNTIF(industries IS NOT NULL AND industries != '[]' AND industries != '') as has_industries
FROM `gen-lang-client-0436975498.c1_intelligence.digest_items`
WHERE published_at >= '2025-11-01'
GROUP BY month
ORDER BY month
"""
print()
print('=== DIGEST_ITEMS MONTHLY BREAKDOWN ===')
for row in client.query(q3):
    print(f'{row.month}: {row.count} items, materials={row.has_materials}, industries={row.has_industries}')

# 4. Article_tags table check
q4 = """
SELECT COUNT(*) as total, COUNT(DISTINCT article_id) as unique_articles,
  COUNTIF(tag_type = 'company') as company_tags,
  COUNTIF(tag_type = 'material') as material_tags,
  COUNTIF(tag_type = 'market') as market_tags,
  COUNTIF(tag_type = 'theme') as theme_tags,
  COUNTIF(tag_type = 'geography') as geo_tags
FROM `gen-lang-client-0436975498.c1_intelligence.article_tags`
"""
print()
print('=== ARTICLE_TAGS TABLE ===')
for row in client.query(q4):
    print(f'Total tags: {row.total}, Unique articles: {row.unique_articles}')
    print(f'Companies: {row.company_tags}, Materials: {row.material_tags}, Markets: {row.market_tags}')
    print(f'Themes: {row.theme_tags}, Geography: {row.geo_tags}')

# 5. Check if digest_items and articles can be joined
q5 = """
SELECT 
  COUNT(DISTINCT d.id) as digest_count,
  COUNT(DISTINCT a.id) as matching_articles
FROM `gen-lang-client-0436975498.c1_intelligence.digest_items` d
LEFT JOIN `gen-lang-client-0436975498.c1_intelligence.articles` a
  ON d.url = a.url
WHERE d.published_at >= '2025-11-01'
"""
print()
print('=== JOIN CHECK (digest_items ↔ articles via URL) ===')
for row in client.query(q5):
    print(f'Digest items: {row.digest_count}')
    print(f'Matching articles (by URL): {row.matching_articles}')

# 6. Sample a few digest items to see what they look like
q6 = """
SELECT id, title, category, companies, materials, industries, 
  LENGTH(digest_summary) as summary_len,
  published_at
FROM `gen-lang-client-0436975498.c1_intelligence.digest_items`
WHERE published_at >= '2025-11-01' AND published_at < '2025-12-01'
ORDER BY published_at DESC
LIMIT 5
"""
print()
print('=== SAMPLE NOV 2025 DIGEST ITEMS ===')
for row in client.query(q6):
    print(f'  [{row.category}] {row.title[:80]}')
    print(f'    companies={row.companies}, materials={row.materials}, industries={row.industries}')
    print(f'    summary_len={row.summary_len}, published={row.published_at}')
    print()
