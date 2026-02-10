"""
Backfill SEC Filing Nugget Extraction
======================================

Processes SEC filings from the dedicated sec_filings BigQuery table and extracts
strategic intelligence nuggets using Claude Sonnet 4.5.

Reads from: sec_filings table (with proper ticker, CIK, form_type, sections)
Writes to:  sec_filing_nuggets table

Modes:
  Default:     Process only filings not yet extracted
  --reextract: Delete ALL existing nuggets and re-extract from scratch
               (use when upgrading models or fixing metadata issues)

Usage:
    cd backend
    python scripts/operations/backfill_sec_nuggets.py              # Default: up to 50 filings
    python scripts/operations/backfill_sec_nuggets.py --limit 20   # Limit batch size
    python scripts/operations/backfill_sec_nuggets.py --reextract  # Delete old + re-extract all
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("backfill_sec_nuggets")


async def run_backfill(args):
    """Main nugget extraction backfill."""
    from app.db.gcp_storage import BigQueryDataStorage
    from app.ingestion.sec_filings.nugget_extractor import SecNuggetExtractor

    store = BigQueryDataStorage()
    await store.initialize()

    # Stats mode
    if args.stats:
        filing_stats = await store.get_sec_filing_stats()
        print("\n=== SEC Filings Table ===")
        for k, v in filing_stats.items():
            print(f"  {k}: {v}")

        nugget_stats = await store.get_sec_filing_nugget_stats()
        print("\n=== SEC Filing Nuggets ===")
        for k, v in nugget_stats.items():
            print(f"  {k}: {v}")
        return

    # Re-extract mode: delete old nuggets first
    if args.reextract:
        print("\n⚠️  RE-EXTRACT MODE: Deleting ALL existing nuggets...")
        deleted = await store.delete_all_sec_filing_nuggets()
        print(f"  Deleted {deleted} existing nuggets")

    # Get filings from dedicated sec_filings table
    include_extracted = args.reextract
    filings = await store.get_sec_filings_for_nugget_extraction(
        limit=args.limit,
        include_already_extracted=include_extracted,
    )

    print(f"\n=== Nugget Extraction Backfill ===")
    print(f"Filings to process: {len(filings)}")
    print(f"Mode: {'re-extract ALL' if args.reextract else 'new filings only'}")
    print(f"Model: claude-sonnet-4-5")
    print(f"Dry run: {args.dry_run}")
    print()

    if not filings:
        print("No filings to process.")
        return

    extractor = SecNuggetExtractor()
    total_nuggets = 0
    total_stored = 0
    errors = []

    for i, filing_data in enumerate(filings):
        ticker = filing_data.get("ticker", "?")
        form_type = filing_data.get("filing_type", "?")
        company = filing_data.get("company_name", "?")

        print(f"\n[{i+1}/{len(filings)}] {company} ({ticker}) - {form_type}...")

        if args.dry_run:
            content_len = len(filing_data.get("full_text", "") or "")
            sections = filing_data.get("sections", {})
            if sections:
                content_len = sum(len(v) for v in sections.values())
            print(f"  Content: {content_len:,} chars, sections: {list(sections.keys()) if sections else 'none'}")
            continue

        try:
            result = await extractor.extract_nuggets(filing_data)

            if result.success and result.nuggets:
                bq_rows = [n.to_bq_row() for n in result.nuggets]
                stored = await store.store_sec_filing_nuggets(bq_rows)
                total_nuggets += len(result.nuggets)
                total_stored += stored
                print(
                    f"  ✅ {len(result.nuggets)} nuggets extracted, {stored} stored "
                    f"({result.actionable_count} actionable, {result.new_disclosure_count} new)"
                )
            elif result.error_message:
                print(f"  ❌ Error: {result.error_message}")
                errors.append(f"{ticker} {form_type}: {result.error_message}")
            else:
                print(f"  ⚠️  No nuggets extracted")

        except Exception as e:
            err_msg = f"{ticker} {form_type}: {e}"
            errors.append(err_msg)
            logger.error(f"  ERROR: {e}")

        # Rate limit between extractions (LLM calls)
        if not args.dry_run:
            time.sleep(1.0)

    print(f"\n=== Extraction Complete ===")
    print(f"Filings processed: {len(filings)}")
    print(f"Total nuggets: {total_nuggets}")
    if not args.dry_run:
        print(f"Total stored: {total_stored}")
    else:
        print("(Dry run — nothing extracted)")

    if errors:
        print(f"\nErrors ({len(errors)}):")
        for e in errors:
            print(f"  - {e}")


def main():
    parser = argparse.ArgumentParser(description="Backfill SEC filing nugget extraction")
    parser.add_argument("--limit", type=int, default=50, help="Max filings to process")
    parser.add_argument("--reextract", action="store_true", help="Delete all nuggets and re-extract")
    parser.add_argument("--dry-run", action="store_true", help="Preview without extracting")
    parser.add_argument("--stats", action="store_true", help="Show current stats and exit")

    args = parser.parse_args()
    asyncio.run(run_backfill(args))


if __name__ == "__main__":
    main()
