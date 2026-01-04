"""
Datasheet Scraper Orchestrator
==============================

Main entry point for running the datasheet scraper.
Coordinates scraping across all suppliers and handles BigQuery loading.

Usage:
    # Run all suppliers
    python -m app.scrapers.orchestrator --all
    
    # Run specific supplier
    python -m app.scrapers.orchestrator --supplier hexcel
    
    # Test mode (3 datasheets per supplier)
    python -m app.scrapers.orchestrator --test
    
    # Manual trigger (as opposed to scheduled)
    python -m app.scrapers.orchestrator --all --run-type manual
"""

import os
import sys
import asyncio
import logging
import argparse
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from uuid import uuid4

from app.scrapers.config import (
    ScraperConfig,
    get_supplier_config,
    get_enabled_suppliers,
    SUPPLIERS,
)
from app.scrapers.suppliers import get_scraper_class, SCRAPER_REGISTRY
from app.scrapers.bq_loader import BigQueryLoader, DatasheetRecord, ScrapeRunRecord
from app.scrapers.base_scraper import DownloadResult, ScrapeStats

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ScraperOrchestrator:
    """
    Orchestrates the datasheet scraping process across multiple suppliers.
    """
    
    def __init__(self, config: ScraperConfig):
        self.config = config
        self.bq_loader = BigQueryLoader(config)
        self.run_id = f"scrape_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}"
    
    async def run_supplier(
        self,
        supplier_id: str,
        run_type: str = "manual",
    ) -> ScrapeStats:
        """
        Run the scraper for a single supplier.
        
        Args:
            supplier_id: Supplier identifier
            run_type: Type of run (scheduled, manual, backfill)
            
        Returns:
            ScrapeStats with results
        """
        supplier_config = get_supplier_config(supplier_id)
        scraper_class = get_scraper_class(supplier_id)
        
        if not scraper_class:
            logger.error(f"No scraper found for supplier: {supplier_id}")
            return ScrapeStats(
                supplier_name=supplier_id,
                errors=[{"error_type": "config_error", "message": "No scraper class found"}]
            )
        
        # Get existing file hashes for change detection
        existing_hashes = {}
        try:
            existing_hashes = self.bq_loader.get_existing_file_hashes(
                supplier_config.supplier_name if supplier_config else supplier_id
            )
            logger.info(f"Loaded {len(existing_hashes)} existing file hashes for change detection")
        except Exception as e:
            logger.warning(f"Could not load existing hashes: {e}")
        
        # Create and run scraper
        scraper = scraper_class(self.config, supplier_config)
        results, stats = await scraper.run(existing_hashes)
        
        # Convert results to BigQuery records
        records = []
        for result in results:
            record = result.to_record(self.run_id)
            if record:
                records.append(record)
        
        # Load to BigQuery
        if records:
            try:
                inserted = self.bq_loader.upsert_datasheets(records)
                stats.datasheets_indexed = inserted
                logger.info(f"Loaded {inserted} datasheets to BigQuery")
            except Exception as e:
                logger.error(f"BigQuery load failed: {e}")
                stats.add_error("", "bq_load_error", str(e))
        
        # Record the scrape run
        run_record = ScrapeRunRecord(
            run_id=self.run_id,
            run_date=datetime.now(timezone.utc),
            run_type=run_type,
            supplier_name=stats.supplier_name,
            datasheets_discovered=stats.datasheets_discovered,
            datasheets_downloaded=stats.datasheets_downloaded,
            datasheets_skipped=stats.datasheets_skipped,
            datasheets_failed=stats.datasheets_failed,
            errors=stats.errors,
            duration_seconds=stats.duration_seconds,
            status=stats.status,
        )
        
        try:
            self.bq_loader.insert_scrape_run(run_record)
        except Exception as e:
            logger.error(f"Failed to record scrape run: {e}")
        
        return stats
    
    async def run_all(
        self,
        supplier_ids: Optional[List[str]] = None,
        run_type: str = "manual",
    ) -> Dict[str, ScrapeStats]:
        """
        Run scrapers for multiple suppliers.
        
        Args:
            supplier_ids: List of supplier IDs (None = all enabled)
            run_type: Type of run
            
        Returns:
            Dict mapping supplier_id -> ScrapeStats
        """
        if supplier_ids is None:
            supplier_ids = [s.supplier_id for s in get_enabled_suppliers()]
        
        logger.info(f"Starting scrape run {self.run_id} for {len(supplier_ids)} suppliers")
        
        results = {}
        
        for supplier_id in supplier_ids:
            try:
                stats = await self.run_supplier(supplier_id, run_type)
                results[supplier_id] = stats
            except Exception as e:
                logger.error(f"Supplier {supplier_id} failed: {e}")
                results[supplier_id] = ScrapeStats(
                    supplier_name=supplier_id,
                    errors=[{"error_type": "fatal_error", "message": str(e)}]
                )
        
        return results
    
    def print_summary(self, results: Dict[str, ScrapeStats]):
        """Print a summary of scraping results."""
        print("\n" + "=" * 70)
        print("DATASHEET SCRAPER - RUN SUMMARY")
        print("=" * 70)
        print(f"Run ID: {self.run_id}")
        print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
        print("-" * 70)
        
        total_discovered = 0
        total_downloaded = 0
        total_skipped = 0
        total_failed = 0
        
        for supplier_id, stats in results.items():
            status_emoji = "✓" if stats.status == "success" else "⚠" if stats.status == "partial" else "✗"
            print(f"\n{status_emoji} {stats.supplier_name}")
            print(f"    Discovered:  {stats.datasheets_discovered:>5}")
            print(f"    Downloaded:  {stats.datasheets_downloaded:>5}")
            print(f"    Skipped:     {stats.datasheets_skipped:>5}")
            print(f"    Failed:      {stats.datasheets_failed:>5}")
            print(f"    Duration:    {stats.duration_seconds:>5.1f}s")
            
            if stats.errors:
                print(f"    Errors:      {len(stats.errors)}")
                for err in stats.errors[:3]:  # Show first 3
                    print(f"      - {err.get('error_type', 'unknown')}: {err.get('message', '')[:50]}")
            
            total_discovered += stats.datasheets_discovered
            total_downloaded += stats.datasheets_downloaded
            total_skipped += stats.datasheets_skipped
            total_failed += stats.datasheets_failed
        
        print("\n" + "-" * 70)
        print("TOTALS")
        print(f"    Discovered:  {total_discovered:>5}")
        print(f"    Downloaded:  {total_downloaded:>5}")
        print(f"    Skipped:     {total_skipped:>5}")
        print(f"    Failed:      {total_failed:>5}")
        print("=" * 70 + "\n")


async def run_scraper(
    suppliers: Optional[List[str]] = None,
    test_mode: bool = False,
    run_type: str = "manual",
) -> Dict[str, Any]:
    """
    Main entry point for running the scraper.
    
    Args:
        suppliers: List of supplier IDs (None = all)
        test_mode: Limit to 3 datasheets per supplier
        run_type: scheduled, manual, or backfill
        
    Returns:
        Summary dict with results
    """
    config = ScraperConfig(test_mode=test_mode)
    orchestrator = ScraperOrchestrator(config)
    
    # Check BigQuery tables exist
    try:
        if not orchestrator.bq_loader.ensure_tables_exist():
            logger.error("BigQuery tables not found. Run create_tables.sql first.")
            return {"error": "BigQuery tables not configured"}
    except Exception as e:
        logger.warning(f"Could not verify BigQuery tables: {e}")
    
    results = await orchestrator.run_all(suppliers, run_type)
    orchestrator.print_summary(results)
    
    return {
        "run_id": orchestrator.run_id,
        "suppliers": {k: {
            "status": v.status,
            "discovered": v.datasheets_discovered,
            "downloaded": v.datasheets_downloaded,
            "skipped": v.datasheets_skipped,
            "failed": v.datasheets_failed,
        } for k, v in results.items()},
        "total_downloaded": sum(s.datasheets_downloaded for s in results.values()),
    }


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="C1 Intelligence Hub - Datasheet Scraper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Scrape all suppliers
    python -m app.scrapers.orchestrator --all
    
    # Scrape specific supplier
    python -m app.scrapers.orchestrator --supplier hexcel
    
    # Test mode (3 datasheets per supplier)
    python -m app.scrapers.orchestrator --all --test
    
    # Scheduled run type
    python -m app.scrapers.orchestrator --all --run-type scheduled
    
Available suppliers: hexcel, owens_corning, toray, polynt, gurit
        """
    )
    
    parser.add_argument("--all", action="store_true", help="Scrape all enabled suppliers")
    parser.add_argument("--supplier", type=str, help="Scrape a specific supplier")
    parser.add_argument("--test", action="store_true", help="Test mode (3 datasheets per supplier)")
    parser.add_argument("--run-type", type=str, default="manual", 
                        choices=["scheduled", "manual", "backfill"],
                        help="Type of scrape run")
    parser.add_argument("--list", action="store_true", help="List available suppliers")
    
    args = parser.parse_args()
    
    if args.list:
        print("\nAvailable suppliers:")
        for supplier_id, config in SUPPLIERS.items():
            status = "✓ enabled" if config.is_enabled else "✗ disabled"
            print(f"  {supplier_id:20} {config.display_name:30} [{status}]")
        return
    
    if not args.all and not args.supplier:
        parser.print_help()
        print("\nError: Please specify --all or --supplier <name>")
        sys.exit(1)
    
    suppliers = None
    if args.supplier:
        suppliers = [args.supplier]
    
    print("\n" + "=" * 70)
    print("C1 DATASHEET SCRAPER")
    print("=" * 70)
    print(f"Suppliers: {', '.join(suppliers) if suppliers else 'all'}")
    print(f"Test mode: {args.test}")
    print(f"Run type: {args.run_type}")
    print("=" * 70 + "\n")
    
    result = asyncio.run(run_scraper(
        suppliers=suppliers,
        test_mode=args.test,
        run_type=args.run_type,
    ))
    
    if result.get("error"):
        print(f"\nError: {result['error']}")
        sys.exit(1)
    
    print(f"\nCompleted. Total downloaded: {result['total_downloaded']}")


if __name__ == "__main__":
    main()
