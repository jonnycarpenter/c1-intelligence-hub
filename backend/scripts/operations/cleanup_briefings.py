"""
Cleanup briefings from BigQuery.
Deletes all pre_briefings and specific weekly_briefings.
"""
from google.cloud import bigquery

def main():
    c = bigquery.Client()
    project = "gen-lang-client-0436975498"
    dataset = "c1_intelligence"
    
    # Delete ALL pre_briefings
    print("=== DELETING ALL PRE_BRIEFINGS ===")
    delete_pre = f"""
    DELETE FROM `{project}.{dataset}.pre_briefings`
    WHERE TRUE
    """
    job = c.query(delete_pre)
    job.result()
    print(f"Deleted {job.num_dml_affected_rows} pre_briefings")
    
    # Delete specific weekly_briefings
    print("\n=== DELETING SPECIFIC WEEKLY_BRIEFINGS ===")
    ids_to_delete = [
        '8e78a220-e184-4958-9b2b-0bf39b9ea132',
        'd57497db-3fd7-43f2-bae8-3e25f2e3d795',
        '4578589c-8799-428b-b93c-1b37f74c22c4',
        '83ad971d-65bb-4f79-b4a7-8992d8ffe553',
        '88e08470-bb5a-40a9-a86d-c2f89c601f43',
        'b1b11b20-aeb4-4ebe-a27a-d02fafd405cb',
    ]
    
    # Build the IN clause
    ids_str = ", ".join([f"'{id}'" for id in ids_to_delete])
    delete_weekly = f"""
    DELETE FROM `{project}.{dataset}.weekly_briefings`
    WHERE id IN ({ids_str})
    """
    job = c.query(delete_weekly)
    job.result()
    print(f"Deleted {job.num_dml_affected_rows} weekly_briefings")
    
    # Verify remaining
    print("\n=== REMAINING DATA ===")
    pre_count = list(c.query(f"SELECT COUNT(*) as cnt FROM `{project}.{dataset}.pre_briefings`").result())[0].cnt
    weekly_count = list(c.query(f"SELECT COUNT(*) as cnt FROM `{project}.{dataset}.weekly_briefings`").result())[0].cnt
    print(f"Pre-briefings remaining: {pre_count}")
    print(f"Weekly briefings remaining: {weekly_count}")
    
    # Show remaining weekly briefings
    if weekly_count > 0:
        print("\nRemaining weekly briefings (the good one for demo):")
        rows = list(c.query(f"SELECT id, briefing_title, generated_at FROM `{project}.{dataset}.weekly_briefings` ORDER BY generated_at DESC").result())
        for r in rows:
            print(f"  {r.id}: {r.briefing_title}")

if __name__ == "__main__":
    main()
