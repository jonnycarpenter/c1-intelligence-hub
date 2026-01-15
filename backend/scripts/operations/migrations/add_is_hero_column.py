"""
Migration: Add is_hero column to digest_items table
==================================================

Run this script to add the is_hero column to the BigQuery digest_items table.
This is required for the Enhanced Digest Feed feature.

Usage:
    cd backend
    python scripts/operations/migrations/add_is_hero_column.py
    
Or run the SQL directly in BigQuery Console:
    ALTER TABLE `gen-lang-client-0436975498.c1_intelligence.digest_items` 
    ADD COLUMN IF NOT EXISTS is_hero BOOL;
"""

import sys
sys.path.insert(0, '.')

from google.cloud import bigquery


def add_is_hero_column():
    """Add is_hero BOOL column to digest_items table."""
    client = bigquery.Client(project='gen-lang-client-0436975498')
    
    query = """
    ALTER TABLE `gen-lang-client-0436975498.c1_intelligence.digest_items` 
    ADD COLUMN IF NOT EXISTS is_hero BOOL
    """
    
    print("Running migration: Adding is_hero column to digest_items...")
    try:
        job = client.query(query)
        job.result()  # Wait for completion
        print("✓ SUCCESS: is_hero column added to digest_items table")
    except Exception as e:
        if "already exists" in str(e).lower():
            print("✓ Column already exists, no action needed")
        else:
            print(f"✗ ERROR: {e}")
            raise


if __name__ == "__main__":
    add_is_hero_column()
