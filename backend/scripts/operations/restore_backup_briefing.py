"""
Restore Backup Briefing Script
==============================

Restores the "good" weekly_briefing from the backup JSON file.
Use this if the backfill process fails and you need the demo briefing.
"""

import json
from datetime import datetime
from google.cloud import bigquery

BACKUP_FILE = "backup_good_briefing.json"

def main():
    print(f"\n=== Restoring briefing from {BACKUP_FILE} ===")
    
    # Load backup
    with open(BACKUP_FILE, 'r', encoding='utf-8') as f:
        row = json.load(f)
    
    print(f"Loaded briefing: {row.get('briefing_title')}")
    print(f"ID: {row.get('id')}")
    
    client = bigquery.Client()
    table_id = "gen-lang-client-0436975498.c1_intelligence.weekly_briefings"
    
    # Check if it already exists
    check_query = f"SELECT id FROM `{table_id}` WHERE id = '{row['id']}'"
    existing = list(client.query(check_query).result())
    
    if existing:
        print(f"WARNING: Briefing {row['id']} already exists! Skipping insert.")
        return
    
    # Insert the row
    table = client.get_table(table_id)
    
    # Convert ISO strings back to datetime for BigQuery
    for field in ['generated_at', 'period_start', 'period_end', 'podcast_generated_at']:
        if row.get(field) and isinstance(row[field], str):
            try:
                row[field] = datetime.fromisoformat(row[field].replace('Z', '+00:00'))
            except:
                pass
    
    errors = client.insert_rows_json(table_id, [row])
    
    if errors:
        print(f"ERROR inserting row: {errors}")
    else:
        print(f"SUCCESS: Restored briefing {row['id']}")
    
    # Verify
    verify = list(client.query(f"SELECT id, briefing_title FROM `{table_id}` WHERE id = '{row['id']}'").result())
    if verify:
        print(f"Verified: {verify[0].briefing_title}")
    else:
        print("WARNING: Verification query returned no results")


if __name__ == "__main__":
    main()
