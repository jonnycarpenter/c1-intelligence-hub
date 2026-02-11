#!/usr/bin/env python3
"""
Backfill Industry Queries (Exa + Tavily)

Triggers the 236 industry queries:
- 91 high-value queries via Exa.ai
- 145 monitoring queries via Tavily

Usage:
    python scripts/operations/backfill/backfill_industry_queries.py --days 7
    python scripts/operations/backfill/backfill_industry_queries.py --days 30 --local
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


def backfill_industry_queries(days: int, local: bool = False, dry_run: bool = False):
    """Trigger industry queries backfill"""
    url = get_service_url(local)
    endpoint = f"{url}/api/v1/scheduler/ingest"
    
    payload = {
        "backfill_days": days,
        "sources": ["industry_queries"]
    }
    
    print(f"Industry Queries Backfill")
    print(f"=" * 50)
    print(f"Target: {url}")
    print(f"Days: {days}")
    print(f"Queries: 91 Exa + 145 Tavily = 236 total")
    print(f"Payload: {payload}")
    print()
    
    if dry_run:
        print("DRY RUN - not executing")
        return
    
    print("Triggering backfill...")
    print("Note: This runs 236 queries, may take 10-15 minutes.")
    print()
    
    try:
        with httpx.Client(timeout=900.0) as client:  # 15 min timeout
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
            print(f"  Web Articles Fetched: {result.get('stats', {}).get('web_articles_fetched', 'N/A')}")
            print(f"  Errors: {result.get('stats', {}).get('errors', [])}")
            
            web_count = result.get('stats', {}).get('web_articles_fetched', 0)
            if web_count > 0:
                print()
                print(f"✅ Industry queries backfill completed! ({web_count} articles)")
            else:
                print()
                print("⚠️ No articles collected. Check logs for details.")
                
    except httpx.TimeoutException:
        print("❌ Request timed out. The backfill may still be running.")
        print("   Check logs: gcloud logging read \"textPayload:Exa\\|Tavily\" --limit=50 --freshness=20m")
    except httpx.HTTPStatusError as e:
        print(f"❌ HTTP Error: {e.response.status_code}")
        print(f"   Response: {e.response.text[:500]}")
    except Exception as e:
        print(f"❌ Error: {e}")


def main():
    parser = argparse.ArgumentParser(description="Backfill industry queries (Exa + Tavily)")
    parser.add_argument("--days", type=int, default=7, help="Number of days to backfill (default: 7)")
    parser.add_argument("--local", action="store_true", help="Use localhost:8000 instead of Cloud Run")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without executing")
    
    args = parser.parse_args()
    backfill_industry_queries(args.days, args.local, args.dry_run)


if __name__ == "__main__":
    main()
