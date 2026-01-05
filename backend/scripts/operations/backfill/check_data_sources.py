#!/usr/bin/env python3
"""
Check what data exists in SQLite vs BigQuery for pre-briefing generation.
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

async def check_data_sources():
    print("=" * 70)
    print("DATA SOURCE COMPARISON: SQLite vs BigQuery")
    print("=" * 70)
    
    # Check SQLite (what Agent 1 currently uses)
    print("\n--- SQLite (corpus_items table) ---")
    try:
        from app.db.database import get_db
        db = get_db()
        await db.initialize()
        
        # Get all articles
        all_items = await db.query_corpus(limit=5000)
        print(f"Total items in SQLite: {len(all_items)}")
        
        if all_items:
            dates = [a.published_at for a in all_items if a.published_at]
            if dates:
                print(f"Date range: {min(dates).date()} to {max(dates).date()}")
            
            # Group by month
            by_month = {}
            for a in all_items:
                if a.published_at:
                    key = a.published_at.strftime('%Y-%m')
                    by_month[key] = by_month.get(key, 0) + 1
            
            print("\nItems by month (SQLite):")
            for k in sorted(by_month.keys(), reverse=True)[:6]:
                print(f"  {k}: {by_month[k]}")
    except Exception as e:
        print(f"SQLite error: {e}")
    
    # Check BigQuery articles table
    print("\n--- BigQuery (articles table) ---")
    try:
        from google.cloud import bigquery
        project_id = os.environ.get('GCP_PROJECT_ID', 'gen-lang-client-0436975498')
        dataset_id = os.environ.get('GCP_DATASET_ID', 'c1_intelligence')
        
        client = bigquery.Client(project=project_id)
        
        # Count and date range
        query = f"""
            SELECT 
                COUNT(*) as total,
                MIN(published_at) as min_date,
                MAX(published_at) as max_date
            FROM `{project_id}.{dataset_id}.articles`
        """
        result = list(client.query(query).result())[0]
        print(f"Total articles in BigQuery: {result.total}")
        print(f"Date range: {result.min_date} to {result.max_date}")
        
        # By month
        query = f"""
            SELECT 
                FORMAT_TIMESTAMP('%Y-%m', published_at) as month,
                COUNT(*) as cnt
            FROM `{project_id}.{dataset_id}.articles`
            WHERE published_at IS NOT NULL
            GROUP BY month
            ORDER BY month DESC
            LIMIT 6
        """
        print("\nArticles by month (BigQuery):")
        for row in client.query(query).result():
            print(f"  {row.month}: {row.cnt}")
        
    except Exception as e:
        print(f"BigQuery error: {e}")
    
    # Check BigQuery digest_items table
    print("\n--- BigQuery (digest_items table) ---")
    try:
        query = f"""
            SELECT 
                COUNT(*) as total,
                MIN(published_at) as min_date,
                MAX(published_at) as max_date
            FROM `{project_id}.{dataset_id}.digest_items`
        """
        result = list(client.query(query).result())[0]
        print(f"Total digest_items in BigQuery: {result.total}")
        print(f"Date range: {result.min_date} to {result.max_date}")
        
        # By month
        query = f"""
            SELECT 
                FORMAT_TIMESTAMP('%Y-%m', published_at) as month,
                COUNT(*) as cnt
            FROM `{project_id}.{dataset_id}.digest_items`
            WHERE published_at IS NOT NULL
            GROUP BY month
            ORDER BY month DESC
            LIMIT 6
        """
        print("\nDigest items by month (BigQuery):")
        for row in client.query(query).result():
            print(f"  {row.month}: {row.cnt}")
            
    except Exception as e:
        print(f"BigQuery error: {e}")
    
    print("\n" + "=" * 70)
    print("CONCLUSION:")
    print("Agent 1 (PreBriefGenerator) uses: db.query_corpus() → SQLite corpus_items")
    print("This may not have all the data from BigQuery!")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(check_data_sources())
