"""
ImportYeti CLI Entry Point
==========================

Run the ImportYeti supply chain ingestion pipeline from the command line.

Usage:
    # Check BigQuery table status
    python -m app.ingestion.importyeti.run_importyeti --stats-only

    # Resolve + company profiles only (~11 credits for C1 + 10 competitors)
    python -m app.ingestion.importyeti.run_importyeti --skip-suppliers

    # Single entity test
    python -m app.ingestion.importyeti.run_importyeti --single-company "Hexcel" --skip-suppliers

    # Full pipeline (all 4 phases)
    python -m app.ingestion.importyeti.run_importyeti

    # Initialize schema only (create tables/views without running pipeline)
    python -m app.ingestion.importyeti.run_importyeti --init-schema
"""

import sys
import logging
import argparse

from .config.settings import get_importyeti_api_key, LOG_FORMAT, LOG_LEVEL
from .bigquery_store import BigQueryStore


def main():
    parser = argparse.ArgumentParser(description="ImportYeti Supply Chain Ingestion")
    parser.add_argument(
        "--skip-suppliers", action="store_true",
        help="Skip Phase 3 (supplier profile lookups). Saves credits.",
    )
    parser.add_argument(
        "--single-company", type=str, default=None,
        help="Only process this one entity (by name from competitors.json).",
    )
    parser.add_argument(
        "--stats-only", action="store_true",
        help="Just print database stats and exit.",
    )
    parser.add_argument(
        "--init-schema", action="store_true",
        help="Initialize BigQuery tables/views and exit.",
    )
    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL),
        format=LOG_FORMAT,
        stream=sys.stderr,
    )
    logger = logging.getLogger("importyeti")

    # Stats-only mode
    if args.stats_only:
        db = BigQueryStore()
        stats = db.get_stats()
        print("\n=== ImportYeti Supply Chain Database Stats ===")
        for table, count in stats.items():
            if isinstance(count, dict):
                print(f"  {table}:")
                for k, v in count.items():
                    print(f"    - {k}: {v}")
            else:
                print(f"  {table}: {count}")
        print("==============================================\n")
        return

    # Init schema only
    if args.init_schema:
        db = BigQueryStore()
        db.initialize()
        print("BigQuery schema initialized successfully.")
        return

    # Full pipeline
    api_key = get_importyeti_api_key()
    if not api_key:
        logger.error(
            "No ImportYeti API key found. Set IMPORTYETI_API_KEY environment variable."
        )
        sys.exit(1)

    from .ingestion import IngestionPipeline

    pipeline = IngestionPipeline(api_key=api_key)

    pipeline.run(
        skip_supplier_details=args.skip_suppliers,
        single_company=args.single_company,
    )


if __name__ == "__main__":
    main()
