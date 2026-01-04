"""
Trigger a backfill ingestion run to recover missing days of data
"""
import requests
import json

# Cloud Run service URL
SERVICE_URL = "https://c1-hub-476410387076.us-central1.run.app"
ENDPOINT = f"{SERVICE_URL}/api/v1/scheduler/ingest"

# Backfill configuration
BACKFILL_DAYS = 5  # Recover the last 5 days since 12/29

payload = {
    "sources": ["tavily", "rss", "sec"],
    "backfill_days": BACKFILL_DAYS
}

print("=" * 80)
print("BACKFILL INGESTION TRIGGER")
print("=" * 80)
print(f"Target: {ENDPOINT}")
print(f"Backfill days: {BACKFILL_DAYS}")
print(f"Sources: {payload['sources']}")
print()
print("⚠️  NOTE: This endpoint requires OIDC authentication from Cloud Scheduler.")
print("   For manual backfill, use one of these methods:")
print()
print("   METHOD 1: Force-run the scheduler job with modified body (recommended)")
print("   1. Go to Cloud Console > Cloud Scheduler")
print("   2. Edit the 'daily-morning-ingest' job")
print("   3. Temporarily change body to: {\"sources\":[\"tavily\",\"rss\",\"sec\"],\"backfill_days\":5}")
print("   4. Click 'FORCE RUN'")
print(f"   5. Wait ~15-20 mins for completion")
print("   6. Reset body back to: {\"sources\":[\"tavily\",\"rss\",\"sec\"]}")
print()
print("   METHOD 2: Use gcloud with elevated permissions")
print(f"   gcloud run services proxy {SERVICE_URL.split('//')[1].split('.')[0]} --region us-central1")
print("   Then POST to the proxied endpoint")
print()
print("=" * 80)
