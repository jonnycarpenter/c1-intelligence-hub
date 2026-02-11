"""
Cleanup Old ImportYeti BigQuery Tables
=======================================

Drops the 10 legacy iy_* tables from the old ImportYeti ingestion pipeline.
These were replaced by the new 4-table schema (iy_companies, iy_suppliers,
iy_edges, iy_ingestion_log) plus 5 analytical views.

Old tables to drop:
  - iy_snapshots
  - iy_suppliers  (replaced by new iy_suppliers with different schema)
  - iy_companies  (replaced by new iy_companies with different schema)
  - iy_supplier_customers
  - iy_company_suppliers
  - iy_product_market
  - iy_shipment_trends
  - iy_concentration_metrics
  - iy_competitor_overlap
  - iy_change_events

Usage:
    cd backend
    python scripts/operations/cleanup_old_iy_tables.py
    python scripts/operations/cleanup_old_iy_tables.py --dry-run
"""

import argparse
import sys
from google.cloud import bigquery

GCP_PROJECT_ID = "<GCP_PROJECT_ID>"
BQ_DATASET = "c1_intelligence"

OLD_TABLES = [
    "iy_snapshots",
    "iy_suppliers",
    "iy_companies",
    "iy_supplier_customers",
    "iy_company_suppliers",
    "iy_product_market",
    "iy_shipment_trends",
    "iy_concentration_metrics",
    "iy_competitor_overlap",
    "iy_change_events",
]


def main():
    parser = argparse.ArgumentParser(description="Drop old ImportYeti tables from BigQuery")
    parser.add_argument("--dry-run", action="store_true", help="List tables without dropping")
    args = parser.parse_args()

    client = bigquery.Client(project=GCP_PROJECT_ID)

    # Check which old tables actually exist
    dataset_ref = f"{GCP_PROJECT_ID}.{BQ_DATASET}"
    existing_tables = set()
    for table in client.list_tables(dataset_ref):
        existing_tables.add(table.table_id)

    print(f"\n{'DRY RUN - ' if args.dry_run else ''}Checking old ImportYeti tables in {dataset_ref}:")
    print("=" * 60)

    found = []
    for table_name in OLD_TABLES:
        if table_name in existing_tables:
            found.append(table_name)
            print(f"  FOUND: {table_name}")
        else:
            print(f"  (not found): {table_name}")

    if not found:
        print("\nNo old tables found. Nothing to clean up.")
        return

    print(f"\n{len(found)} old table(s) to drop.")

    if args.dry_run:
        print("\nDry run complete. Use without --dry-run to actually drop tables.")
        return

    # Confirm before dropping
    confirm = input(f"\nDrop {len(found)} tables? Type 'yes' to confirm: ")
    if confirm.strip().lower() != "yes":
        print("Aborted.")
        sys.exit(1)

    for table_name in found:
        table_ref = f"{dataset_ref}.{table_name}"
        try:
            client.delete_table(table_ref, not_found_ok=True)
            print(f"  DROPPED: {table_name}")
        except Exception as e:
            print(f"  ERROR dropping {table_name}: {e}")

    print(f"\nDone. Dropped {len(found)} old ImportYeti tables.")


if __name__ == "__main__":
    main()
