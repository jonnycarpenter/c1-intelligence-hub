
import asyncio
import logging
import sys
import os

# Ensure backend path is in sys.path
sys.path.append(os.getcwd())

from app.tools.earnings.client import APINinjaClient
from app.tools.earnings.collector import EarningsCollector

logging.basicConfig(level=logging.INFO)

def main():
    print("--- Testing Earnings Tool ---")
    
    # Check env
    api_key = os.getenv("API_NINJA_KEY")
    print(f"API Key present: {bool(api_key)}")
    
    client = APINinjaClient()
    collector = EarningsCollector(client)
    
    ticker = "HXL"
    print(f"Fetching earnings calendar for {ticker}...")
    events = client.get_earnings_calendar(ticker)
    print(f"Found {len(events)} events.")
    for e in events[:3]:
        print(f"  - {e.date.date()} | Est EPS: {e.estimated_eps}")
        
    print("\nFetching transcripts (via Collector)...")
    # This will likely be empty as per our stub implementation, but ensuring it runs
    transcripts = collector.collect_for_company("HXL", ticker)
    print(f"Found {len(transcripts)} transcripts.")

if __name__ == "__main__":
    main()
