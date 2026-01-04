
import asyncio
import logging
import sys
import os

# Ensure backend path is in sys.path
sys.path.append(os.getcwd())

from app.ingestion.orchestrator import get_orchestrator
from app.config.settings import settings

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(name)s | %(message)s')

async def main():
    print("--- Starting Ingestion Integration Test ---")
    orchestrator = get_orchestrator()
    
    # Mock _get_tracked_companies to reduce load if needed, but let's try real first?
    # Actually, let's override it to just 1 company for speed.
    async def mock_get_companies():
        return [{"id": "HXL", "name": "Hexcel Corporation", "ticker": "HXL"}]
    
    # orchestrator._get_tracked_companies = mock_get_companies
    # Keeping default fallback (5 companies) is okay, but 1 is faster for verification.
    orchestrator._get_tracked_companies = mock_get_companies
    
    print("Running ingestion with 1 company (HXL)...")
    stats = await orchestrator.run_full_ingestion(backfill_days=1)
    
    print("\n--- Ingestion Stats ---")
    print(stats.model_dump_json(indent=2))
    
    if stats.status == "failed":
        print("Ingestion FAILED")
        sys.exit(1)
    else:
        print("Ingestion COMPLETED")

if __name__ == "__main__":
    asyncio.run(main())
