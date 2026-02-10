"""
Cleanup briefings from BigQuery.
Deletes broken/duplicate briefings and their pre-briefings.

Usage: cd backend && python scripts/operations/cleanup_briefings.py
"""
from google.cloud import bigquery

def main():
    c = bigquery.Client(project="gen-lang-client-0436975498")
    project = "gen-lang-client-0436975498"
    dataset = "c1_intelligence"

    # Step 1: Delete broken Feb 9 weekly briefing (citations show "Article not found")
    print("=== Step 1: Delete broken Feb 9 weekly briefing (f3a3915a) ===")
    job = c.query(
        f"DELETE FROM `{project}.{dataset}.weekly_briefings` "
        f"WHERE id = 'f3a3915a-78fa-44e7-9f2b-604824094bcf'"
    )
    job.result()
    print(f"  Deleted {job.num_dml_affected_rows} row(s)")

    # Step 2: Delete Feb 9 pre-briefing (will be regenerated)
    print("\n=== Step 2: Delete Feb 9 pre-briefing (ac7e723d) ===")
    job = c.query(
        f"DELETE FROM `{project}.{dataset}.pre_briefings` "
        f"WHERE id = 'ac7e723d-940e-4b32-9dd3-7b2d4532f289'"
    )
    job.result()
    print(f"  Deleted {job.num_dml_affected_rows} row(s)")

    # Step 3: Remove duplicate Feb 2 row (the one without podcast_url)
    # Both rows share the same id, so we use CREATE AS SELECT + table swap
    print("\n=== Step 3: Remove duplicate Feb 2 row (no podcast) ===")
    c.query(
        f"CREATE OR REPLACE TABLE `{project}.{dataset}.weekly_briefings_clean` AS "
        f"SELECT * FROM `{project}.{dataset}.weekly_briefings` "
        f"WHERE NOT (id = '433a266e-acb1-4318-8f0c-6266d7e2792e' AND podcast_url IS NULL)"
    ).result()
    print("  Created clean table")

    c.query(f"DROP TABLE `{project}.{dataset}.weekly_briefings`").result()
    print("  Dropped old table")

    c.query(
        f"ALTER TABLE `{project}.{dataset}.weekly_briefings_clean` RENAME TO weekly_briefings"
    ).result()
    print("  Renamed clean table -> weekly_briefings")

    # Verify
    print("\n=== Verification ===")
    rows = list(c.query(
        f"SELECT id, briefing_title, generated_at, podcast_url IS NOT NULL as has_podcast "
        f"FROM `{project}.{dataset}.weekly_briefings` ORDER BY generated_at DESC LIMIT 8"
    ).result())
    for r in rows:
        print(f"  {r.id[:12]}... | {str(r.briefing_title)[:55]} | podcast={r.has_podcast}")

    total = list(c.query(
        f"SELECT COUNT(*) as cnt FROM `{project}.{dataset}.weekly_briefings`"
    ).result())
    print(f"\nTotal briefings remaining: {total[0].cnt}")
    print("Cleanup complete!")

if __name__ == "__main__":
    main()
