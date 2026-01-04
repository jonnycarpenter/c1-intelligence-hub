
import asyncio
import logging
import sys
import os

sys.path.append(os.getcwd())

from app.db.database import get_db
from app.config.settings import settings

logging.basicConfig(level=logging.INFO)

async def main():
    print(f"Companies file: {settings.companies_file}")
    print(f"Exists: {settings.companies_file.exists()}")
    
    db = get_db()
    entities = await db.list_entities(entity_type=None)
    print(f"Entities found: {len(entities)}")
    for e in entities[:5]:
        print(f" - {e['name']} ({e['type']})")

if __name__ == "__main__":
    asyncio.run(main())
