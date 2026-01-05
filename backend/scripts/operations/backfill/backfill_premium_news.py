#!/usr/bin/env python3
"""
Backfill FMP Premium News

Triggers premium stock news collection from FMP API for tracked companies.
Uses the BigQuery companies table tickers.

Data Type: premium_news (source: fmp_news)

Usage:
    python scripts/operations/backfill/backfill_premium_news.py --days 7
    python scripts/operations/backfill/backfill_premium_news.py --days 30 --local
    python scripts/operations/backfill/backfill_premium_news.py --days 7 --dry-run
"""

import argparse
import httpx
import os
import sys
from pathlib import Path

# Add backend to path for local imports
backend_path = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(backend_path))


def get_service_url(local: bool = False) -> str:
    """Get the Cloud Run service URL or localhost"""
    if local:
        return "http://localhost:8000"
    
    # Try to get from gcloud
    try:
        import subprocess
        result = subprocess.run(
            ["gcloud", "run", "services", "describe", "c1-hub", 
             "--region", "us-central1", "--format", "value(status.url)"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception as e:
        print(f"Warning: Could not get Cloud Run URL: {e}")
    
    # Fallback - updated URL
    return os.getenv("C1_HUB_URL", "https://c1-hub-4iz75bvpyq-uc.a.run.app")


def backfill_premium_news(days: int, local: bool = False, dry_run: bool = False):
    """Trigger FMP premium news backfill"""
    url = get_service_url(local)
    endpoint = f"{url}/api/v1/scheduler/ingest"
    
    payload = {
        "backfill_days": days,
        "sources": ["fmp_news"]  # Source name in orchestrator
    }
    
    print(f"FMP Premium News Backfill")
    print(f"=" * 50)
    print(f"Target: {url}")
    print(f"Days: {days}")
    print(f"Payload: {payload}")
    print()
    print(f"Note: FMP provides premium stock news for tracked company tickers.")
    print(f"      Data is stored as source_type='premium_news'")
    print(f"      Fetches from BigQuery companies table tickers.")
    print()
    
    if dry_run:
        print("DRY RUN - not executing")
        return
    
    print("Triggering backfill...")
    
    try:
        with httpx.Client(timeout=600.0) as client:  # 10 min timeout
            response = client.post(
                endpoint,
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            
            result = response.json()
            print()
            print("Response:")
            print(f"  Status: {result.get('status', 'unknown')}")
            print(f"  Message: {result.get('message', 'No message')}")
            
            if "stats" in result:
                stats = result["stats"]
                print()
                print("Stats:")
                if "premium_news_articles_fetched" in stats:
                    print(f"  Premium News Fetched: {stats['premium_news_articles_fetched']}")
                if "articles_stored" in stats:
                    print(f"  Articles Stored: {stats['articles_stored']}")
                if "digest_items_created" in stats:
                    print(f"  Digest Items: {stats['digest_items_created']}")
                if "duplicates_skipped" in stats:
                    print(f"  Duplicates Skipped: {stats['duplicates_skipped']}")
                    
    except httpx.TimeoutException:
        print("\nTimeout - the backfill is likely still running on Cloud Run.")
        print("Check the GCP Console logs for progress.")
    except httpx.HTTPStatusError as e:
        print(f"\nHTTP Error: {e.response.status_code}")
        print(f"Response: {e.response.text}")
    except Exception as e:
        print(f"\nError: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Backfill FMP Premium News",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Backfill last 7 days from Cloud Run
    python scripts/operations/backfill/backfill_premium_news.py --days 7
    
    # Backfill last 14 days from local server
    python scripts/operations/backfill/backfill_premium_news.py --days 14 --local
    
    # Preview without executing
    python scripts/operations/backfill/backfill_premium_news.py --days 7 --dry-run
"""
    )
    
    parser.add_argument(
        "--days", 
        type=int, 
        default=7,
        help="Number of days to backfill (default: 7)"
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Target localhost:8000 instead of Cloud Run"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be executed without making API call"
    )
    
    args = parser.parse_args()
    backfill_premium_news(args.days, args.local, args.dry_run)


if __name__ == "__main__":
    main()
