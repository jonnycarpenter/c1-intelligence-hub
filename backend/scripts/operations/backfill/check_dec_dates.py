#!/usr/bin/env python3
from google.cloud import bigquery
client = bigquery.Client(project='<GCP_PROJECT_ID>')
dataset = '<GCP_PROJECT_ID>.c1_intelligence'

query = f"""
    SELECT 
        DATE(published_at) as pub_date,
        COUNT(*) as cnt
    FROM `{dataset}.articles`
    WHERE published_at >= '2025-12-01' AND published_at <= '2026-01-06'
    GROUP BY pub_date
    ORDER BY pub_date DESC
"""
print('Articles by date (Dec 2025 - Jan 5, 2026):')
for row in client.query(query).result():
    print(f'  {row.pub_date}: {row.cnt}')
