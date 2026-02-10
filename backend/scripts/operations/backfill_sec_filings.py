"""
Backfill SEC Filings to Dedicated Table
=========================================

Pulls SEC filings (10-K, 10-Q, 8-K) from SEC-API.io for all US-listed companies
in the master company list and stores them in the dedicated `sec_filings` BigQuery table.

This table provides proper metadata (ticker, CIK, form_type, sections) that was
previously lost when filings were stored in the generic articles table.

Usage:
    cd backend
    python scripts/operations/backfill_sec_filings.py                    # Default: since Q3 2025
    python scripts/operations/backfill_sec_filings.py --since 2025-07-01 # Custom start date
    python scripts/operations/backfill_sec_filings.py --tickers HXL,RPM  # Specific tickers only
    python scripts/operations/backfill_sec_filings.py --dry-run          # Preview without storing
    python scripts/operations/backfill_sec_filings.py --stats            # Show current stats
"""

import asyncio
import argparse
import csv
import json
import logging
import sys
import os
import time
from datetime import datetime
from typing import List, Dict, Any, Optional

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("backfill_sec_filings")


def get_us_tickers(filter_tickers: Optional[List[str]] = None) -> List[Dict[str, str]]:
    """Get US-listed companies with stock tickers from master company list.
    
    Returns list of dicts with company_id, company, stock_ticker.
    Skips companies without tickers or with non-US exchange suffixes (.DE, .SW, etc.)
    """
    csv_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "app", "resources", "master_company_list.csv"
    )
    
    companies = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ticker = (row.get("stock_ticker") or "").strip()
            if not ticker or ticker.lower() == "private":
                continue
            # Skip non-US exchanges (have dots: SGL.DE, GURN.SW, etc.)
            # Also skip OTC/pink sheets with Y suffix (TRYIY, MTLHY) — these won't have SEC filings
            if "." in ticker:
                continue
            if ticker.endswith("Y") and len(ticker) == 5:
                # Likely ADR ticker — still has SEC filings via 20-F/6-K, skip for now
                continue
            
            if filter_tickers and ticker.upper() not in [t.upper() for t in filter_tickers]:
                continue
            
            companies.append({
                "company_id": row.get("company_id", ""),
                "company": row.get("company", ""),
                "stock_ticker": ticker,
            })
    
    return companies


def filing_to_bq_row(filing, company_id: str) -> Dict[str, Any]:
    """Convert an SECFiling object to a BigQuery row dict for sec_filings table."""
    # Serialize sections dict to JSON
    sections_json = None
    if filing.sections:
        sections_json = json.dumps(filing.sections)
    
    # Format filed_at as ISO string for BQ
    filed_at = None
    if filing.filed_at:
        if hasattr(filing.filed_at, 'isoformat'):
            filed_at = filing.filed_at.isoformat()
        else:
            filed_at = str(filing.filed_at)
    
    collected_at = datetime.utcnow().isoformat()
    if filing.collected_at:
        if hasattr(filing.collected_at, 'isoformat'):
            collected_at = filing.collected_at.isoformat()
    
    return {
        "filing_id": filing.id,  # accession number
        "company_id": company_id,
        "ticker": filing.ticker,
        "cik": filing.cik,
        "company_name": filing.company_name,
        "form_type": filing.form_type,
        "filed_at": filed_at,
        "filing_url": filing.filing_url,
        "sections_json": sections_json,
        "full_text": filing.full_text,
        "collected_at": collected_at,
    }


async def run_backfill(args):
    """Main backfill logic."""
    from app.db.gcp_storage import BigQueryDataStorage
    from app.tools.sec_filings.collector import SECFilingCollector
    
    store = BigQueryDataStorage()
    await store.initialize()
    
    # Stats mode
    if args.stats:
        stats = await store.get_sec_filing_stats()
        print("\n=== SEC Filings Table Stats ===")
        for k, v in stats.items():
            print(f"  {k}: {v}")
        
        nugget_stats = await store.get_sec_filing_nugget_stats()
        print("\n=== SEC Nuggets Stats ===")
        for k, v in nugget_stats.items():
            print(f"  {k}: {v}")
        return
    
    # Get companies to process
    filter_tickers = None
    if args.tickers:
        filter_tickers = [t.strip() for t in args.tickers.split(",")]
    
    companies = get_us_tickers(filter_tickers=filter_tickers)
    print(f"\n=== SEC Filing Backfill ===")
    print(f"Companies to process: {len(companies)}")
    print(f"Since: {args.since}")
    print(f"Dry run: {args.dry_run}")
    print()
    
    if not companies:
        print("No companies found with US tickers.")
        return
    
    # Get existing filing IDs to skip duplicates
    existing_ids = await store.get_sec_filing_ids()
    print(f"Existing filings in BQ: {len(existing_ids)}")
    
    # Parse since date
    since_date = datetime.strptime(args.since, "%Y-%m-%d")
    
    # Create collector with existing IDs for dedup
    collector = SECFilingCollector(existing_ids=existing_ids)
    
    total_collected = 0
    total_stored = 0
    errors = []
    
    for i, company in enumerate(companies):
        ticker = company["stock_ticker"]
        company_id = company["company_id"]
        company_name = company["company"]
        
        print(f"\n[{i+1}/{len(companies)}] {company_name} ({ticker})...")
        
        try:
            filings = collector.collect_for_company(
                company_id=company_id,
                ticker=ticker,
                since=since_date,
            )
            
            if not filings:
                print(f"  No new filings found")
                continue
            
            print(f"  Found {len(filings)} filing(s)")
            total_collected += len(filings)
            
            for f in filings:
                sections_info = ""
                if f.sections:
                    sections_info = f" sections=[{', '.join(f.sections.keys())}]"
                elif f.full_text:
                    sections_info = f" full_text={len(f.full_text):,} chars"
                print(f"    {f.form_type} filed {f.filed_at.strftime('%Y-%m-%d') if f.filed_at else '?'}{sections_info}")
            
            if not args.dry_run:
                bq_rows = [filing_to_bq_row(f, company_id) for f in filings]
                stored = await store.store_sec_filings(bq_rows)
                total_stored += stored
                print(f"  Stored {stored} filing(s) to BigQuery")
            
        except Exception as e:
            err_msg = f"{ticker}: {e}"
            errors.append(err_msg)
            logger.error(f"  ERROR: {e}")
        
        # Small delay between companies to be nice to SEC-API
        time.sleep(0.2)
    
    print(f"\n=== Backfill Complete ===")
    print(f"Companies processed: {len(companies)}")
    print(f"Filings collected: {total_collected}")
    if not args.dry_run:
        print(f"Filings stored: {total_stored}")
    else:
        print(f"(Dry run — nothing stored)")
    
    if errors:
        print(f"\nErrors ({len(errors)}):")
        for e in errors:
            print(f"  - {e}")


def main():
    parser = argparse.ArgumentParser(description="Backfill SEC filings to dedicated BigQuery table")
    parser.add_argument("--since", default="2025-07-01", help="Start date for filing lookup (YYYY-MM-DD)")
    parser.add_argument("--tickers", default=None, help="Comma-separated list of tickers (default: all US-listed)")
    parser.add_argument("--dry-run", action="store_true", help="Preview without storing to BigQuery")
    parser.add_argument("--stats", action="store_true", help="Show current stats and exit")
    
    args = parser.parse_args()
    asyncio.run(run_backfill(args))


if __name__ == "__main__":
    main()
