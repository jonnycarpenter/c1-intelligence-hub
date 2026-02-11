"""Inspect the latest weekly briefing data in BigQuery."""
import json
from google.cloud import bigquery

c = bigquery.Client(project='<GCP_PROJECT_ID>')

# Get latest briefing
r = list(c.query("""
    SELECT sections, article_ids
    FROM `<GCP_PROJECT_ID>.c1_intelligence.weekly_briefings`
    WHERE id = 'f3a3915a-78fa-44e7-9f2b-604824094bcf' LIMIT 1
"""))

if not r:
    print("No briefing found")
    exit()

sections = json.loads(r[0].sections) if r[0].sections else []
article_ids = json.loads(r[0].article_ids) if r[0].article_ids else []

print(f"Total sections: {len(sections)}")
print(f"Total article_ids: {len(article_ids)}")
print()

for i, s in enumerate(sections):
    headline = s.get('headline', {})
    if isinstance(headline, dict):
        title = headline.get('text', '?')
    else:
        title = str(headline)
    sa = s.get('source_articles', [])
    print(f"Section {i}: {title[:60]} | source_articles: {len(sa)}")
    for a in sa[:5]:
        num = a.get('article_number', '?')
        title_a = a.get('title', '?')[:50]
        url = a.get('url', '?')[:60]
        source = a.get('source_name', '?')
        print(f"  [{num}] title={title_a} | source={source} | url={url}")
    print()

# Check how many article_ids are actually in the articles table
if article_ids:
    placeholders = ", ".join([f"'{aid}'" for aid in article_ids[:20]])
    check = list(c.query(f"""
        SELECT id, title, url 
        FROM `<GCP_PROJECT_ID>.c1_intelligence.articles`
        WHERE id IN ({placeholders})
    """))
    found_ids = {row.id for row in check}
    missing = [aid for aid in article_ids[:20] if aid not in found_ids]
    print(f"\nArticle lookup: {len(check)} found out of {min(20, len(article_ids))} checked")
    if missing:
        print(f"Missing IDs: {missing[:5]}")
    for row in check[:5]:
        print(f"  Found: {row.id[:12]}... title={row.title[:50] if row.title else 'None'} url={row.url[:60] if row.url else 'None'}")
