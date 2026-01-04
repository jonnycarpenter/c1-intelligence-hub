import asyncio
import logging
import sys
import os
from datetime import datetime

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.db.database import get_db
from app.db.gcp_storage import get_data_storage
from app.ingestion.orchestrator import get_orchestrator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def backfill_tags():
    """
    Backfill article_tags table in BigQuery from existing local corpus items.
    """
    logger.info("Starting article_tags backfill...")
    
    # Initialize components
    db = get_db()
    await db.initialize()
    
    # Force BigQuery storage for this script since we want to push to BQ
    from app.db.gcp_storage import BigQueryDataStorage, gcp_config
    
    # Manually inject project ID if missing (based on user's context)
    if not gcp_config.project_id:
        gcp_config.project_id = "gen-lang-client-0436975498"
        logger.info(f"Manually set GCP Project ID to {gcp_config.project_id}")

    if not gcp_config.is_configured:
        logger.warning("GCP not fully configured in environment, but attempting BigQuery storage anyway...")
    
    storage = BigQueryDataStorage(gcp_config)
    await storage.initialize()
    
    orchestrator = get_orchestrator()
    
    # Get all corpus items
    # We'll fetch in batches to be safe, though SQLite can handle it
    offset = 0
    batch_size = 100
    total_processed = 0
    
    while True:
        items = await db.query_corpus(limit=batch_size, offset=offset)
        if not items:
            break
            
        logger.info(f"Processing batch {offset} to {offset + len(items)}...")
        
        # Convert to tags
        articles_tags = []
        for item in items:
            try:
                # Use the orchestrator's logic to generate tags
                tags_data = orchestrator._corpus_item_to_article_tags(item)
                if tags_data and tags_data.get("tags"):
                    articles_tags.append(tags_data)
            except Exception as e:
                logger.error(f"Error converting item {item.id}: {e}")
        
        # Store to BigQuery
        if articles_tags:
            try:
                stored = await storage.store_article_tags_batch(articles_tags)
                logger.info(f"Stored {stored} tag sets to BigQuery")
                total_processed += stored
            except Exception as e:
                logger.error(f"Failed to store batch to BigQuery: {e}")
        
        offset += batch_size
    
    logger.info(f"Backfill complete. Total articles processed: {total_processed}")

if __name__ == "__main__":
    asyncio.run(backfill_tags())
