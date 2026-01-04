import requests
import subprocess
import json

# 1. Get a fresh Identity Token from gcloud
try:
    token = subprocess.check_output(
        ["gcloud", "auth", "print-identity-token"], 
        text=True
    ).strip()
except Exception as e:
    print(f"Error getting token: {e}")
    exit(1)

url = "https://c1-hub-476410387076.us-central1.run.app/api/v1/scheduler/ingest"

# 2. Send request with the token
# Cloud Run (Gatekeeper) validates the token.
# If valid, it passes the request to the app (stripping the header).
# The app (with new fix) trusts the request.
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {token}"
}

data = {
    "sources": ["tavily", "rss", "sec"],
    "max_articles": 200
}

try:
    print(f"Triggering ingestion at {url}...")
    response = requests.post(url, headers=headers, json=data)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Request failed: {e}")
