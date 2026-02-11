"""
Backup and Cleanup Briefings Script
====================================

1. Exports the "good" weekly_briefing to a backup JSON file
2. Deletes ALL pre_briefings
3. Deletes ALL weekly_briefings

The backup can be re-inserted if needed.
"""

import json
import sys
from google.cloud import bigquery

GOOD_BRIEFING_ID = "c21f6cdc-1b55-4d1b-9a89-51aff8aa905f"
BACKUP_FILE = "backup_good_briefing.json"

def main():
    client = bigquery.Client()
    
    # Step 1: Export the good briefing
    print(f"\n=== Step 1: Exporting briefing {GOOD_BRIEFING_ID} ===")
    
    query = f"""
        SELECT *
        FROM `<GCP_PROJECT_ID>.c1_intelligence.weekly_briefings`
        WHERE id = '{GOOD_BRIEFING_ID}'
    """
    
    results = list(client.query(query).result())
    if not results:
        print(f"ERROR: Briefing {GOOD_BRIEFING_ID} not found!")
        sys.exit(1)
    
    row = dict(results[0])
    
    # Convert datetime objects for JSON serialization
    serializable_row = {}
    for k, v in row.items():
        if hasattr(v, 'isoformat'):
            serializable_row[k] = v.isoformat()
        else:
            serializable_row[k] = v
    
    with open(BACKUP_FILE, 'w', encoding='utf-8') as f:
        json.dump(serializable_row, f, indent=2, default=str)
    
    print(f"SUCCESS: Exported to {BACKUP_FILE}")
    print(f"  Title: {serializable_row.get('briefing_title')}")
    print(f"  Generated: {serializable_row.get('generated_at')}")
    
    # Step 2: Delete all pre_briefings
    print(f"\n=== Step 2: Deleting ALL pre_briefings ===")
    
    count_query = "SELECT COUNT(*) as cnt FROM `<GCP_PROJECT_ID>.c1_intelligence.pre_briefings`"
    count_result = list(client.query(count_query).result())
    pre_count = count_result[0].cnt if count_result else 0
    print(f"Found {pre_count} pre_briefings to delete")
    
    if pre_count > 0:
        delete_query = "DELETE FROM `<GCP_PROJECT_ID>.c1_intelligence.pre_briefings` WHERE TRUE"
        client.query(delete_query).result()
        print(f"DELETED {pre_count} pre_briefings")
    
    # Step 3: Delete all weekly_briefings
    print(f"\n=== Step 3: Deleting ALL weekly_briefings ===")
    
    count_query = "SELECT COUNT(*) as cnt FROM `<GCP_PROJECT_ID>.c1_intelligence.weekly_briefings`"
    count_result = list(client.query(count_query).result())
    weekly_count = count_result[0].cnt if count_result else 0
    print(f"Found {weekly_count} weekly_briefings to delete")
    
    if weekly_count > 0:
        delete_query = "DELETE FROM `<GCP_PROJECT_ID>.c1_intelligence.weekly_briefings` WHERE TRUE"
        client.query(delete_query).result()
        print(f"DELETED {weekly_count} weekly_briefings")
    
    # Verify cleanup
    print(f"\n=== Verification ===")
    
    pre_verify = list(client.query("SELECT COUNT(*) as cnt FROM `<GCP_PROJECT_ID>.c1_intelligence.pre_briefings`").result())
    weekly_verify = list(client.query("SELECT COUNT(*) as cnt FROM `<GCP_PROJECT_ID>.c1_intelligence.weekly_briefings`").result())
    
    print(f"pre_briefings remaining: {pre_verify[0].cnt}")
    print(f"weekly_briefings remaining: {weekly_verify[0].cnt}")
    
    print(f"\n=== COMPLETE ===")
    print(f"Backup saved to: {BACKUP_FILE}")
    print(f"To restore if needed, run: python scripts/operations/restore_backup_briefing.py")


if __name__ == "__main__":
    main()
