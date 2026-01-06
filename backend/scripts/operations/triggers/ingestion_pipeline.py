import os
import sys
import asyncio
import logging
import argparse

# Add backend to path so we can import from app
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from app.ingestion.orchestrator import IngestionOrchestrator, IngestionConfig
from app.utils.logger import get_logger

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = get_logger(__name__)

async def main():
    """Main entry point for running the ingestion pipeline"""
    parser = argparse.ArgumentParser(description="C1 Intelligence Hub Ingestion Pipeline")
    parser.add_argument("--full", action="store_true", help="Run full ingestion")
    parser.add_argument("--backfill", type=int, help="Number of days to backfill")
    parser.add_argument("--rss", action="store_true", help="Run RSS ingestion only")
    parser.add_argument("--digest", action="store_true", help="Generate digest only")
    parser.add_argument("--test", action="store_true", help="Run in test mode (no storage)")
    parser.add_argument("--financials-only", action="store_true", help="Backfill SEC filings and Earnings transcripts only")
    parser.add_argument("--earnings-only", action="store_true", help="Backfill Earnings transcripts only")
    
    args = parser.parse_args()
    
    config = IngestionConfig()
    logger.info(f"Config Check - SEC Key Present: {bool(config.sec_api_key)}")
    logger.info(f"Config Check - Tavily Key Present: {bool(config.tavily_api_key)}")
    orchestrator = IngestionOrchestrator(config)
    
    if args.earnings_only:
        # Targeted backfill for Earnings transcripts only
        logger.info("Running earnings-only backfill...")
        await orchestrator.initialize()
        stats = await orchestrator.run_earnings_only(backfill_days=args.backfill or 83)
        print(f"\n{'='*50}")
        print("EARNINGS BACKFILL COMPLETE")
        print(f"{'='*50}")
        print(f"Duration: {stats.duration_seconds:.1f}s")
        print(f"Earnings Transcripts: {getattr(stats, 'earnings_transcripts_fetched', 0)}")
        print(f"Duplicates Skipped: {stats.duplicates_skipped}")
        print(f"Articles Classified: {stats.articles_classified}")
        print(f"Articles Stored: {stats.articles_stored}")
        if stats.errors:
            print(f"Errors: {len(stats.errors)}")
            for err in stats.errors[:5]:
                print(f"  - {err}")
    
    elif args.financials_only:
        # Targeted backfill for SEC filings and Earnings transcripts only
        logger.info("Running financials-only backfill (SEC + Earnings)...")
        await orchestrator.initialize()
        stats = await orchestrator.run_financials_only(backfill_days=args.backfill or 83)
        print(f"\n{'='*50}")
        print("FINANCIALS BACKFILL COMPLETE")
        print(f"{'='*50}")
        print(f"Duration: {stats.duration_seconds:.1f}s")
        print(f"SEC Filings: {getattr(stats, 'sec_filings_fetched', 0)}")
        print(f"Earnings Transcripts: {getattr(stats, 'earnings_transcripts_fetched', 0)}")
        print(f"Duplicates Skipped: {stats.duplicates_skipped}")
        print(f"Articles Stored: {stats.articles_stored}")
        if stats.errors:
            print(f"Errors: {len(stats.errors)}")
            for err in stats.errors[:5]:
                print(f"  - {err}")
    
    elif args.full or args.backfill or (not args.rss and not args.digest):
        logger.info("Running full ingestion pipeline...")
        await orchestrator.initialize()
        stats = await orchestrator.run_full_ingestion(backfill_days=args.backfill)
        print(f"\n{'='*50}")
        print("INGESTION COMPLETE")
        print(f"{'='*50}")
        print(f"Duration: {stats.duration_seconds:.1f}s")
        print(f"RSS Articles: {stats.rss_articles_fetched}")
        print(f"PR Articles: {getattr(stats, 'pr_articles_fetched', 0)}")
        print(f"SEC Filings: {getattr(stats, 'sec_filings_fetched', 0)}")
        print(f"Earnings Transcripts: {getattr(stats, 'earnings_transcripts_fetched', 0)}")
        print(f"Duplicates Skipped: {stats.duplicates_skipped}")
        print(f"Articles Stored: {stats.articles_stored}")
        if stats.errors:
            print(f"Errors: {len(stats.errors)}")
            for err in stats.errors[:5]:
                print(f"  - {err}")
    
    elif args.rss:
        logger.info("Running RSS-only ingestion...")
        await orchestrator.initialize()
        stats = await orchestrator.run_rss_only()
        print(f"RSS ingestion complete: {stats.articles_stored} articles stored")
    
    elif args.digest:
        logger.info("Generating digest...")
        await orchestrator.initialize()
        digest = await orchestrator.run_digest_only()
        print(f"Digest generated: {len(digest.items)} items")
        print(f"Executive Summary: {digest.executive_summary[:200]}...")

if __name__ == "__main__":
    asyncio.run(main())
