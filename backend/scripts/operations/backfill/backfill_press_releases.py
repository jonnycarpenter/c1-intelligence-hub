#!/usr/bin/env python3
"""
Backfill Press Releases (Exa.ai)

Triggers press release collection via the scheduler API.
Uses Exa.ai for semantic search across PR newswire sites.

Usage:
    python scripts/operations/backfill/backfill_press_releases.py --days 7
    python scripts/operations/backfill/backfill_press_releases.py --days 30 --local
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
    
    # Fallback - you may need to update this
    return os.getenv("C1_HUB_URL", "https://c1-hub-<GCP_PROJECT_NUMBER>.us-central1.run.app")


def backfill_press_releases(days: int, local: bool = False, dry_run: bool = False):
    """Trigger press releases backfill via Exa.ai"""
    url = get_service_url(local)
    endpoint = f"{url}/api/v1/scheduler/ingest"
    
    payload = {
        "backfill_days": days,
        "sources": ["press_releases"]
    }
    
    print(f"Press Releases Backfill (Exa.ai)")
    print(f"=" * 50)
    print(f"Target: {url}")
    print(f"Days: {days}")
    print(f"Payload: {payload}")
    print()
    
    if dry_run:
        print("DRY RUN - not executing")
        return
    
    print("Triggering backfill...")
    print("Note: This queries Exa.ai for each tracked company.")
    print()
    
    try:
        with httpx.Client(timeout=900.0) as client:  # 15 min timeout for many companies
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
            print(f"  PR Articles Fetched: {result.get('stats', {}).get('pr_articles_fetched', 'N/A')}")
            print(f"  Errors: {result.get('stats', {}).get('errors', [])}")
            
            pr_count = result.get('stats', {}).get('pr_articles_fetched', 0)
            if pr_count > 0:
                print()
                print(f"✅ Press releases backfill completed! ({pr_count} articles)")
            else:
                print()
                print("⚠️ No press releases collected. Possible issues:")
                print("   - Check EXA_API_KEY is configured in Cloud Run")
                print("   - Verify key: gcloud run services describe c1-hub --region us-central1 --format='yaml(spec.template.spec.containers[0].env)' | findstr EXA")
                
    except httpx.TimeoutException:
        print("❌ Request timed out. The backfill may still be running.")
        print("   Check logs: gcloud logging read \"textPayload:press\\|Exa\" --limit=50 --freshness=20m")
    except httpx.HTTPStatusError as e:
        print(f"❌ HTTP Error: {e.response.status_code}")
        print(f"   Response: {e.response.text[:500]}")
        if e.response.status_code == 400:
            print()
            print("   400 errors often indicate missing API key.")
            print("   Verify EXA_API_KEY is set in Cloud Run environment.")
    except Exception as e:
        print(f"❌ Error: {e}")


def main():
    parser = argparse.ArgumentParser(description="Backfill press releases via Exa.ai")
    parser.add_argument("--days", type=int, default=7, help="Number of days to backfill (default: 7)")
    parser.add_argument("--local", action="store_true", help="Use localhost:8000 instead of Cloud Run")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without executing")
    
    args = parser.parse_args()
    backfill_press_releases(args.days, args.local, args.dry_run)


if __name__ == "__main__":
    main()
