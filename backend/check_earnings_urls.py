"""Quick script to check earnings URLs in BigQuery"""
from google.cloud import bigquery

client = bigquery.Client(project='gen-lang-client-0436975498', location='us-central1')

query = """
SELECT url, title, source_type 
FROM `gen-lang-client-0436975498.c1_hub_data.articles` 
WHERE source_type = 'earnings'
LIMIT 10
"""

print("Earnings articles in BigQuery:")
for row in client.query(query):
    url_display = row.url[:70] if row.url else "EMPTY"
    print(f"  URL: {url_display}")
