"""
Backfill SEC Filing Nugget Extraction
======================================

Processes existing SEC filings in BigQuery and extracts strategic intelligence
nuggets using Claude Haiku. Only processes filings that haven't been extracted yet.

Usage:
    cd backend
    python scripts/operations/backfill_sec_nuggets.py              # Default: up to 50 filings
    python scripts/operations/backfill_sec_nuggets.py --limit 20   # Limit batch size
    python scripts/operations/backfill_sec_nuggets.py --stats      # Show current stats
    python scripts/operations/backfill_sec_nuggets.py --dry-run    # Preview without extracting
"""

import asyncio
import argparse
import logging
import sys
import time
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.db.gcp_storage import get_storage
from app.ingestion.sec_filings.nugget_extractor import SecNuggetExtractor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("backfill_sec_nuggets")


async def show_stats():
    """Show current SEC nugget extraction stats."""
    storage = await get_storage()
    stats = await storage.get_sec_filing_nugget_stats()

    if not stats or not stats.get("total_nuggets"):
        print("\n  No SEC filing nuggets extracted yet.")
        return

    print(f"\n  SEC Filing Nugget Extraction Stats")
    print(f"{'='*50}")
    print(f"  Total nuggets:          {stats.get('total_nuggets', 0):,}")
    print(f"  Filings processed:      {stats.get('filings_processed', 0)}")
    print(f"  Unique tickers:         {stats.get('unique_tickers', 0)}")
    print(f"  Actionable nuggets:     {stats.get('actionable_nuggets', 0):,}")
    print(f"  New disclosures:        {stats.get('new_disclosures', 0):,}")
    print(f"  Avg relevance:          {stats.get('avg_relevance', 0):.2f}")
    print(f"  Earliest extraction:    {stats.get('earliest_extraction', 'N/A')}")
    print(f"  Latest extraction:      {stats.get('latest_extraction', 'N/A')}")
    print()


async def run_backfill(limit: int = 50, dry_run: bool = False, batch_size: int = 3):
    """Run the SEC filing nugget extraction backfill."""
    storage = await get_storage()
    extractor = SecNuggetExtractor()

    # Get pending filings
    logger.info(f"Fetching SEC filings pending nugget extraction (limit={limit})...")
    pending = await storage.get_filings_for_nugget_extraction(limit=limit)

    if not pending:
        print("\n  No SEC filings pending nugget extraction. All caught up!")
        return

    print(f"\n  Found {len(pending)} filings pending extraction:")
    for f in pending:
        ticker = f.get("ticker") or "?"
        company = f.get("company_name", "?")
        filing_type = f.get("filing_type", "?")
        content_len = len(f.get("full_text", ""))
        print(f"  - {company} ({ticker}) {filing_type} ({content_len:,} chars)")

    if dry_run:
        print("\n  DRY RUN - no extraction performed.")
        return

    print(f"\n  Starting extraction (batch_size={batch_size})...")

    total_nuggets = 0
    total_actionable = 0
    total_new = 0
    total_stored = 0
    failed = []

    # Process in batches (SEC filings are large, go slower)
    for batch_start in range(0, len(pending), batch_size):
        batch = pending[batch_start:batch_start + batch_size]
        batch_num = batch_start // batch_size + 1
        total_batches = (len(pending) + batch_size - 1) // batch_size

        print(f"\n--- Batch {batch_num}/{total_batches} ---")

        for filing in batch:
            ticker = filing.get("ticker") or "?"
            company = filing.get("company_name", "?")
            filing_type = filing.get("filing_type", "?")

            start_time = time.time()

            try:
                # Build filing_data dict for the extractor
                filing_data = {
                    "id": filing.get("id"),
                    "ticker": ticker,
                    "company_name": company,
                    "filing_type": filing_type,
                    "full_text": filing.get("full_text", ""),
                    "filing_date": str(filing.get("published_at", "Unknown")),
                }

                result = await extractor.extract_nuggets(filing_data)
                elapsed = time.time() - start_time

                if result.success and result.nuggets:
                    # Convert to BQ rows
                    bq_rows = [n.to_bq_row() for n in result.nuggets]
                    stored = await storage.store_sec_filing_nuggets(bq_rows)

                    total_nuggets += result.total_nuggets
                    total_actionable += result.actionable_count
                    total_new += result.new_disclosure_count
                    total_stored += stored

                    print(
                        f"  > {company} ({ticker}) {filing_type}: "
                        f"{result.total_nuggets} nuggets ({result.actionable_count} actionable, "
                        f"{result.new_disclosure_count} new) in {elapsed:.1f}s - stored {stored}"
                    )

                    # Show top nugget types
                    if result.nuggets_by_type:
                        top_types = sorted(result.nuggets_by_type.items(), key=lambda x: x[1], reverse=True)[:3]
                        type_str = ", ".join(f"{t}:{c}" for t, c in top_types)
                        print(f"    Types: {type_str}")
                else:
                    error_msg = result.error_message or "No nuggets extracted"
                    print(f"  ! {company} ({ticker}) {filing_type}: {error_msg} ({elapsed:.1f}s)")
                    if not result.success:
                        failed.append(f"{company} ({ticker}) {filing_type}: {error_msg}")

            except Exception as e:
                elapsed = time.time() - start_time
                print(f"  X {company} ({ticker}) {filing_type}: ERROR - {e} ({elapsed:.1f}s)")
                failed.append(f"{company} ({ticker}) {filing_type}: {str(e)}")

        # Rate limit between batches (SEC filings are large, longer pause)
        if batch_start + batch_size < len(pending):
            logger.info("Pausing 3s between batches...")
            await asyncio.sleep(3)

    # Summary
    print(f"\n{'='*50}")
    print(f"  BACKFILL COMPLETE")
    print(f"{'='*50}")
    print(f"  Filings processed:      {len(pending)}")
    print(f"  Total nuggets extracted: {total_nuggets}")
    print(f"  Actionable nuggets:      {total_actionable}")
    print(f"  New disclosures:         {total_new}")
    print(f"  Nuggets stored in BQ:    {total_stored}")
    print(f"  Failed:                  {len(failed)}")

    if failed:
        print(f"\n  Failures:")
        for f in failed:
            print(f"  - {f}")


def main():
    parser = argparse.ArgumentParser(description="Backfill SEC filing nugget extraction")
    parser.add_argument("--limit", type=int, default=50, help="Max filings to process")
    parser.add_argument("--batch-size", type=int, default=3, help="Filings per batch (SEC filings are large)")
    parser.add_argument("--stats", action="store_true", help="Show current stats and exit")
    parser.add_argument("--dry-run", action="store_true", help="Preview without extracting")

    args = parser.parse_args()

    if args.stats:
        asyncio.run(show_stats())
    else:
        asyncio.run(run_backfill(
            limit=args.limit,
            dry_run=args.dry_run,
            batch_size=args.batch_size,
        ))


if __name__ == "__main__":
    main()
