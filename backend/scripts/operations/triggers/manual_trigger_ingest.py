"""
Emergency manual ingestion trigger
Run this to manually trigger an ingestion run if scheduler is broken
"""
import requests
import json
from datetime import datetime

# Cloud Run service URL
SERVICE_URL = "https://c1-intelligence-hub-286921258186.us-central1.run.app"
ENDPOINT = f"{SERVICE_URL}/api/v1/scheduler/ingest"

# Request body matching scheduler config
payload = {
    "sources": ["industry_queries", "rss", "sec"],
    "max_articles": 150
}

print("=" * 80)
print("MANUAL INGESTION TRIGGER")
print("=" * 80)
print(f"Target: {ENDPOINT}")
print(f"Payload: {json.dumps(payload, indent=2)}")
print()
print("Triggering ingestion run...")
print()

try:
    # Note: This will require authentication
    # You may need to add authorization headers
    response = requests.post(
        ENDPOINT,
        json=payload,
        timeout=1800  # 30 minute timeout like scheduler
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
    
    if response.status_code == 200:
        print("\n✅ Ingestion triggered successfully!")
    else:
        print("\n❌ Ingestion trigger failed!")
        print("This endpoint may require authentication.")
        print("Try using gcloud to generate an identity token:")
        print(f"  gcloud auth print-identity-token")
        
except Exception as e:
    print(f"❌ Error: {e}")
    print("\nNote: This endpoint requires authentication.")
    print("Manual trigger via Cloud Console may be easier:")
    print("  1. Go to Cloud Scheduler")
    print("  2. Click 'orchestrator-ingestion-morning' job")
    print("  3. Click 'FORCE RUN' button")

print()
print("=" * 80)
