#!/usr/bin/env python3
"""Check existing briefings in BigQuery."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from google.cloud import bigquery

def check_existing():
    client = bigquery.Client(project='<GCP_PROJECT_ID>')
    
    # Check weekly briefings
    print('=== WEEKLY BRIEFINGS ===')
    query = """
        SELECT id, briefing_title, period_start, period_end, generated_at, bluf
        FROM `<GCP_PROJECT_ID>.c1_intelligence.weekly_briefings`
        ORDER BY generated_at DESC
        LIMIT 5
    """
    rows = list(client.query(query).result())
    if not rows:
        print("No weekly briefings found.")
    for row in rows:
        print(f'{row.generated_at.strftime("%Y-%m-%d")}: {row.briefing_title}')
        print(f'  Period: {row.period_start} to {row.period_end}')
        bluf_preview = row.bluf[:80] + "..." if row.bluf else "(none)"
        print(f'  BLUF: {bluf_preview}')
        print()
    
    # Check pre-briefings
    print('=== PRE-BRIEFINGS ===')
    query2 = """
        SELECT id, period_start, period_end, generated_at, article_count
        FROM `<GCP_PROJECT_ID>.c1_intelligence.pre_briefings`
        ORDER BY generated_at DESC
        LIMIT 5
    """
    rows2 = list(client.query(query2).result())
    if not rows2:
        print("No pre-briefings found.")
    for row in rows2:
        print(f'{row.generated_at.strftime("%Y-%m-%d")}: Period {row.period_start} to {row.period_end} ({row.article_count} articles)')
    
    # Check article date range
    print('\n=== ARTICLE DATE RANGE ===')
    query3 = """
        SELECT 
            MIN(published_at) as earliest,
            MAX(published_at) as latest,
            COUNT(*) as total
        FROM `<GCP_PROJECT_ID>.c1_intelligence.articles`
    """
    for row in client.query(query3).result():
        print(f'Articles: {row.total} total')
        print(f'Date range: {row.earliest} to {row.latest}')

if __name__ == "__main__":
    check_existing()
