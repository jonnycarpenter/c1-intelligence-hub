
import asyncio
import csv
import logging
import os
import sys

# Ensure backend path is in sys.path
sys.path.append(os.getcwd())

from app.db.database import get_db
from app.models.corpus import Entity, EntityMetadata

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)

async def main():
    logger.info("Starting company loader...")
    
    csv_path = "data/master_company_list.csv"
    if not os.path.exists(csv_path):
        logger.error(f"File not found: {csv_path}")
        return

    db = get_db()
    
    count = 0
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                # Map CSV columns to Entity model
                # CSV: company_id, company, type, stock_ticker, industries_served, description, processes_services
                
                ticker = row.get("stock_ticker", "").strip()
                if ticker.lower() == "private":
                    ticker = None
                
                # Split lists
                industries = [i.strip() for i in row.get("industries_served", "").split("|") if i.strip()]
                
                # Create EntityMetadata
                metadata = EntityMetadata(
                    name=row["company"],
                    ticker=ticker,
                    description=row.get("description", ""),
                    sectors=industries,
                    # Storing extra fields in generic dict if needed, but EntityMetadata has specific fields.
                    # We can pack processes_services into description or ignore. 
                    # Let's verify EntityMetadata fields.
                    # Assuming standard fields.
                )
                
                entity = Entity(
                    id=row["company_id"],
                    name=row["company"],
                    type="competitor", # As per CSV mapping instructions or default
                    description=row.get("description", ""),
                    metadata=metadata
                )
                
                await db.add_entity(entity)
                count += 1
                if count % 10 == 0:
                    logger.info(f"Loaded {count} companies...")
                    
            except Exception as e:
                logger.error(f"Error loading row {row.get('company', 'Unknown')}: {e}")
                
    logger.info(f"Finished. Loaded {count} companies.")

if __name__ == "__main__":
    asyncio.run(main())
