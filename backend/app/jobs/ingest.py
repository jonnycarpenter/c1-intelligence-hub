"""
Cloud Run Job Entry Point
=========================

This script is the entry point for the C1 Intelligence Hub ingestion job.
It is designed to be run as a containerized job in Google Cloud Run.

Usage:
    python -m app.jobs.ingest --full
    python -m app.jobs.ingest --backfill 60
"""

import asyncio
import logging
import argparse
import sys
from app.ingestion.orchestrator import IngestionOrchestrator, IngestionConfig
from app.utils.logger import setup_logging

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

async def main():
    parser = argparse.ArgumentParser(description="C1 Intelligence Hub Ingestion Job")
    parser.add_argument("--full", action="store_true", help="Run full ingestion pipeline")
    parser.add_argument("--backfill", type=int, help="Number of days to backfill (e.g. 60)")
    parser.add_argument("--dry-run", action="store_true", help="Run without saving to DB")
    
    args = parser.parse_args()
    
    if not (args.full or args.backfill):
        parser.print_help()
        sys.exit(1)
        
    logger.info("Starting ingestion job...")
    if args.backfill:
        logger.info(f"Backfill mode: {args.backfill} days")
    
    config = IngestionConfig()
    orchestrator = IngestionOrchestrator(config)
    
    # Initialize
    await orchestrator.initialize()
    
    # Run
    if args.backfill:
        stats = await orchestrator.run_full_ingestion(backfill_days=args.backfill)
    else:
        stats = await orchestrator.run_full_ingestion()
        
    # Report
    print(f"\n{'='*50}")
    print("INGESTION JOB COMPLETE")
    print(f"{'='*50}")
    print(f"Status: {stats.status}")
    print(f"Duration: {stats.duration_seconds:.1f}s")
    print(f"Articles Fetched: {stats.rss_articles_fetched}")
    print(f"Articles Stored: {stats.articles_stored}")
    if stats.errors:
        print(f"Errors ({len(stats.errors)}):")
        for err in stats.errors[:5]:
            print(f"  - {err}")
            
    if stats.status == "failed":
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
