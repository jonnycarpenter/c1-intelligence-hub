"""
Backfill Earnings Quote Extraction
===================================

Processes existing earnings transcripts in BigQuery and extracts executive quotes
using Claude Haiku. Only processes transcripts that haven't been extracted yet.

Usage:
    cd backend
    python scripts/operations/backfill_earnings_quotes.py              # Default: up to 50 transcripts
    python scripts/operations/backfill_earnings_quotes.py --limit 20   # Limit batch size
    python scripts/operations/backfill_earnings_quotes.py --stats      # Show current stats
    python scripts/operations/backfill_earnings_quotes.py --dry-run    # Preview without extracting
"""

import asyncio
import argparse
import json
import logging
import sys
import time
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.db.gcp_storage import get_storage
from app.ingestion.earnings.quote_extractor import EarningsQuoteExtractor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("backfill_earnings_quotes")


async def show_stats():
    """Show current earnings quote extraction stats."""
    storage = await get_storage()
    stats = await storage.get_earnings_quote_stats()
    
    if not stats or not stats.get("total_quotes"):
        print("\n📊 No earnings quotes extracted yet.")
        return
    
    print(f"\n📊 Earnings Quote Extraction Stats")
    print(f"{'='*50}")
    print(f"  Total quotes:           {stats.get('total_quotes', 0):,}")
    print(f"  Transcripts processed:  {stats.get('transcripts_processed', 0)}")
    print(f"  Unique tickers:         {stats.get('unique_tickers', 0)}")
    print(f"  Quotable quotes:        {stats.get('quotable_quotes', 0):,}")
    print(f"  Avg relevance:          {stats.get('avg_relevance', 0):.2f}")
    print(f"  Earliest extraction:    {stats.get('earliest_extraction', 'N/A')}")
    print(f"  Latest extraction:      {stats.get('latest_extraction', 'N/A')}")
    print()


async def run_backfill(limit: int = 50, dry_run: bool = False, batch_size: int = 5):
    """Run the earnings quote extraction backfill."""
    storage = await get_storage()
    extractor = EarningsQuoteExtractor()
    
    # Get pending transcripts
    logger.info(f"Fetching transcripts pending quote extraction (limit={limit})...")
    pending = await storage.get_transcripts_for_quote_extraction(limit=limit)
    
    if not pending:
        print("\n✅ No transcripts pending quote extraction. All caught up!")
        return
    
    print(f"\n📋 Found {len(pending)} transcripts pending extraction:")
    for t in pending:
        ticker = t.get("ticker", "?")
        year = t.get("year", "?")
        quarter = t.get("quarter", "?")
        content_len = len(t.get("content", ""))
        print(f"  - {ticker} Q{quarter} {year} ({content_len:,} chars)")
    
    if dry_run:
        print("\n🔍 DRY RUN - no extraction performed.")
        return
    
    print(f"\n🚀 Starting extraction (batch_size={batch_size})...")
    
    total_quotes = 0
    total_quotable = 0
    total_stored = 0
    failed = []
    
    # Process in batches
    for batch_start in range(0, len(pending), batch_size):
        batch = pending[batch_start:batch_start + batch_size]
        batch_num = batch_start // batch_size + 1
        total_batches = (len(pending) + batch_size - 1) // batch_size
        
        print(f"\n--- Batch {batch_num}/{total_batches} ---")
        
        for transcript in batch:
            ticker = transcript.get("ticker", "?")
            year = transcript.get("year", 0)
            quarter = transcript.get("quarter", 0)
            
            start_time = time.time()
            
            try:
                result = await extractor.extract_quotes(transcript)
                elapsed = time.time() - start_time
                
                if result.success and result.quotes:
                    # Convert to BQ rows
                    bq_rows = [q.to_bq_row() for q in result.quotes]
                    stored = await storage.store_earnings_quotes(bq_rows)
                    
                    total_quotes += result.total_quotes
                    total_quotable += result.quotable_count
                    total_stored += stored
                    
                    print(
                        f"  ✓ {ticker} Q{quarter} {year}: "
                        f"{result.total_quotes} quotes ({result.quotable_count} quotable) "
                        f"in {elapsed:.1f}s — stored {stored}"
                    )
                    
                    # Show top quote types
                    if result.quotes_by_type:
                        top_types = sorted(result.quotes_by_type.items(), key=lambda x: x[1], reverse=True)[:3]
                        type_str = ", ".join(f"{t}:{c}" for t, c in top_types)
                        print(f"    Types: {type_str}")
                else:
                    error_msg = result.error_message or "No quotes extracted"
                    print(f"  ⚠ {ticker} Q{quarter} {year}: {error_msg} ({elapsed:.1f}s)")
                    if not result.success:
                        failed.append(f"{ticker} Q{quarter} {year}: {error_msg}")
                        
            except Exception as e:
                elapsed = time.time() - start_time
                print(f"  ✗ {ticker} Q{quarter} {year}: ERROR - {e} ({elapsed:.1f}s)")
                failed.append(f"{ticker} Q{quarter} {year}: {str(e)}")
        
        # Rate limit between batches
        if batch_start + batch_size < len(pending):
            logger.info("Pausing 2s between batches...")
            await asyncio.sleep(2)
    
    # Summary
    print(f"\n{'='*50}")
    print(f"📊 BACKFILL COMPLETE")
    print(f"{'='*50}")
    print(f"  Transcripts processed:  {len(pending)}")
    print(f"  Total quotes extracted: {total_quotes}")
    print(f"  Quotable quotes:        {total_quotable}")
    print(f"  Quotes stored in BQ:    {total_stored}")
    print(f"  Failed:                 {len(failed)}")
    
    if failed:
        print(f"\n⚠ Failures:")
        for f in failed:
            print(f"  - {f}")


def main():
    parser = argparse.ArgumentParser(description="Backfill earnings quote extraction")
    parser.add_argument("--limit", type=int, default=50, help="Max transcripts to process")
    parser.add_argument("--batch-size", type=int, default=5, help="Transcripts per batch")
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
