#!/usr/bin/env python3
"""
Backfill SEC Filings

Triggers SEC filing collection for tracked companies via the scheduler API.
Use this script to backfill SEC data after outages or for new company additions.

Usage:
    python scripts/operations/backfill/backfill_sec_filings.py --days 7
    python scripts/operations/backfill/backfill_sec_filings.py --days 30 --local
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
    
    # Fallback - update if URL changes
    return os.getenv("C1_HUB_URL", "https://<CLOUD_RUN_URL>")


def backfill_sec(days: int, local: bool = False, dry_run: bool = False):
    """Trigger SEC filings backfill"""
    url = get_service_url(local)
    endpoint = f"{url}/api/v1/scheduler/ingest"
    
    payload = {
        "backfill_days": days,
        "sources": ["sec"]
    }
    
    print(f"SEC Filings Backfill")
    print(f"=" * 50)
    print(f"Target: {url}")
    print(f"Days: {days}")
    print(f"Payload: {payload}")
    print()
    
    if dry_run:
        print("DRY RUN - not executing")
        return
    
    print("Triggering backfill...")
    
    try:
        with httpx.Client(timeout=600.0) as client:
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
            print(f"  SEC Filings Fetched: {result.get('stats', {}).get('sec_filings_fetched', 'N/A')}")
            print(f"  Errors: {result.get('stats', {}).get('errors', [])}")
            
            if result.get('stats', {}).get('sec_filings_fetched', 0) > 0:
                print()
                print("✅ SEC backfill completed successfully!")
            else:
                print()
                print("⚠️ No SEC filings collected. Check logs for details.")
                
    except httpx.TimeoutException:
        print("❌ Request timed out. The backfill may still be running.")
        print("   Check logs: gcloud logging read \"textPayload:SEC\" --limit=50 --freshness=15m")
    except httpx.HTTPStatusError as e:
        print(f"❌ HTTP Error: {e.response.status_code}")
        print(f"   Response: {e.response.text[:500]}")
    except Exception as e:
        print(f"❌ Error: {e}")


def main():
    parser = argparse.ArgumentParser(description="Backfill SEC filings")
    parser.add_argument("--days", type=int, default=7, help="Number of days to backfill (default: 7)")
    parser.add_argument("--local", action="store_true", help="Use localhost:8000 instead of Cloud Run")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without executing")
    
    args = parser.parse_args()
    backfill_sec(args.days, args.local, args.dry_run)


if __name__ == "__main__":
    main()
