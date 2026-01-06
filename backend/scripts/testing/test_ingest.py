
import asyncio
import os
import logging
from datetime import date
from dotenv import load_dotenv

# Add backend to path
import sys
sys.path.append(os.path.join(os.getcwd(), 'backend'))

load_dotenv(os.path.join(os.getcwd(), 'backend', '.env'))

from app.ingestion.importyeti.collector import ImportYetiCollector
from app.ingestion.importyeti.client import ImportYetiClient
from app.ingestion.importyeti.bigquery_store import ImportYetiBigQueryStore
from app.ingestion.importyeti.config import TrackedSupplier

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run_test_ingest():
    print("Initializing test ingestion...")
    
    # 1. Initialize Components
    client = ImportYetiClient()
    store = ImportYetiBigQueryStore()
    
    # Initialize BigQuery
    print("Initializing BigQuery...")
    try:
        await store.initialize()
    except Exception as e:
        print(f"Failed to init BigQuery: {e}")
        # Proceeding might fail if tables don't exist, but let's try
        
    
    # 2. Mock Tracked Suppliers (Just one for testing)
    test_supplier = TrackedSupplier(
        name="Jushi Group",
        company_id="test_jushi_001",
        tier="raw_material",
        importyeti_key="jushi-group",
        products="Fiberglass"
    )
    
    tracked_suppliers = {"jushi-group": test_supplier}
    
    # 3. Initialize Collector with limited scope
    collector = ImportYetiCollector(
        tracked_suppliers=tracked_suppliers,
        tracked_oems={} # No OEMs for this test
    )
    
    # 4. Run Collection
    print("Running collection for Jushi Group...")
    result = await collector.run_full_collection(
        include_oems=False,
        include_products=False,
        max_suppliers=1
    )
    
    print(f"Collection complete!")
    print(f"Suppliers: {len(result.suppliers)}")
    print(f"Relationships: {len(result.supplier_customers)}")
    print(f"Errors: {result.stats.errors}")
    
    # 5. Store Results
    if result.suppliers:
        print("Storing results to BigQuery...")
        await store.store_suppliers(result.suppliers)
        await store.store_supplier_customers(result.supplier_customers)
        print("Storage complete.")
    else:
        print("No suppliers collected, skipping storage.")

if __name__ == "__main__":
    asyncio.run(run_test_ingest())
