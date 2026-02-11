#!/usr/bin/env python3
"""
Backfill Earnings Call Transcripts

Triggers earnings transcript collection for tracked companies via the scheduler API.
Use this script to backfill earnings data after adding new companies or for historical data.

Usage:
    python scripts/operations/backfill/backfill_earnings.py --days 93
    python scripts/operations/backfill/backfill_earnings.py --days 93 --local
    python scripts/operations/backfill/backfill_earnings.py --days 93 --dry-run
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
    
    # Fallback
    return os.getenv("C1_HUB_URL", "https://<CLOUD_RUN_URL>")


def backfill_earnings(days: int, local: bool = False, dry_run: bool = False):
    """Trigger earnings transcripts backfill"""
    url = get_service_url(local)
    endpoint = f"{url}/api/v1/scheduler/ingest"
    
    payload = {
        "backfill_days": days,
        "sources": ["earnings"]
    }
    
    print(f"Earnings Transcripts Backfill")
    print(f"=" * 50)
    print(f"Target: {url}")
    print(f"Days: {days}")
    print(f"Payload: {payload}")
    print()
    print(f"Note: 93 days will capture Q3 2025 earnings.")
    print(f"      This processes all companies with tickers in BigQuery.")
    print()
    
    if dry_run:
        print("DRY RUN - not executing")
        return
    
    print("Triggering backfill...")
    print("Note: This may take 30-45 minutes depending on company count.")
    print()
    
    try:
        # Long timeout for earnings - lots of companies to process
        with httpx.Client(timeout=2700.0) as client:  # 45 min timeout
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
            print(f"  Records Collected: {result.get('records_collected', 'N/A')}")
            print(f"  Message: {result.get('message', 'N/A')}")
            
            records = result.get('records_collected', 0)
            if records > 0:
                print()
                print(f"✅ Earnings backfill completed! ({records} transcripts)")
            else:
                print()
                print("⚠️ No earnings transcripts collected. Check logs for details.")
                print("   gcloud logging read \"textPayload:Earnings\" --limit=50 --freshness=30m")
                
    except httpx.TimeoutException:
        print("❌ Request timed out. The backfill may still be running.")
        print("   Check logs: gcloud logging read \"textPayload:Earnings\" --limit=50 --freshness=45m")
    except httpx.HTTPStatusError as e:
        print(f"❌ HTTP Error: {e.response.status_code}")
        print(f"   Response: {e.response.text[:500]}")
    except Exception as e:
        print(f"❌ Error: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Backfill earnings call transcripts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Backfill Q3 2025 (93 days)
  python scripts/operations/backfill/backfill_earnings.py --days 93
  
  # Test locally
  python scripts/operations/backfill/backfill_earnings.py --days 7 --local
  
  # Dry run to see what would happen
  python scripts/operations/backfill/backfill_earnings.py --days 93 --dry-run
        """
    )
    parser.add_argument("--days", type=int, required=True, help="Number of days to backfill")
    parser.add_argument("--local", action="store_true", help="Target localhost instead of Cloud Run")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without executing")
    
    args = parser.parse_args()
    backfill_earnings(args.days, args.local, args.dry_run)


if __name__ == "__main__":
    main()
