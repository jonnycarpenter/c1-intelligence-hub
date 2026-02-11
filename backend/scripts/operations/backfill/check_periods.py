#!/usr/bin/env python3
"""Check article counts for the 3 pre-briefing periods."""

from google.cloud import bigquery

client = bigquery.Client(project='<GCP_PROJECT_ID>')
dataset = '<GCP_PROJECT_ID>.c1_intelligence'

periods = [
    ('12/22/25 - 1/4/26', '2025-12-22', '2026-01-05'),
    ('12/8/25 - 12/21/25', '2025-12-08', '2025-12-22'),
    ('11/24/25 - 12/7/25', '2025-11-24', '2025-12-08'),
]

print('BigQuery ARTICLES by period:')
print('=' * 50)
for name, start, end in periods:
    query = f"""
        SELECT COUNT(*) as cnt
        FROM `{dataset}.articles`
        WHERE published_at >= '{start}' AND published_at < '{end}'
    """
    result = list(client.query(query).result())[0]
    print(f'{name}: {result.cnt} articles')

print()
print('BigQuery DIGEST_ITEMS by period:')
print('=' * 50)
for name, start, end in periods:
    query = f"""
        SELECT COUNT(*) as cnt
        FROM `{dataset}.digest_items`
        WHERE published_at >= '{start}' AND published_at < '{end}'
    """
    result = list(client.query(query).result())[0]
    print(f'{name}: {result.cnt} items')

print()
print('What dates actually have data?')
print('=' * 50)
query = f"""
    SELECT 
        DATE(published_at) as pub_date,
        COUNT(*) as cnt
    FROM `{dataset}.articles`
    WHERE published_at >= '2025-11-01'
    GROUP BY pub_date
    ORDER BY pub_date DESC
    LIMIT 20
"""
print("Articles by date (Nov 2025+):")
for row in client.query(query).result():
    print(f"  {row.pub_date}: {row.cnt}")
