import asyncio
import os
import sys

# Ensure we can import from app
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# FORCE ENV VARS for BigQuery/GCP
os.environ["GCP_PROJECT_ID"] = "gen-lang-client-0436975498"
# Using the bucket name found in service_config.yaml
os.environ["GCS_BUCKET_NAME"] = "gen-lang-client-0436975498-c1-hub-data" 
os.environ["GCP_DATASET_ID"] = "c1_intelligence" 

# Needed for imports to work
from app.ingestion.generators.weekly_briefing import WeeklyBriefingGenerator
from app.utils.logger import get_logger

logger = get_logger(__name__)

async def main():
    print("Initializing WeeklyBriefingGenerator with FORCED GCP Config...")
    print(f"Project: {os.environ['GCP_PROJECT_ID']}")
    print(f"Bucket: {os.environ['GCS_BUCKET_NAME']}")
    
    agent2 = WeeklyBriefingGenerator()
    
    # Verify BQ Storage init
    bq = await agent2._get_bq_storage()
    if bq:
        print("✅ BigQuery Storage initialized successfully.")
    else:
        print("❌ Failed to initialize BigQuery Storage.")
        return

    print("Triggering generation (fetching latest Pre-Brief from BQ)...")
    result = await agent2.generate()
    
    if result:
        print(f"✅ Briefing generated: {result.get('briefing_title')}")
        print(f"ID: {result.get('id')}")
        print("Data should now be in BigQuery.")
    else:
        print("❌ Generation failed.")

if __name__ == "__main__":
    asyncio.run(main())
