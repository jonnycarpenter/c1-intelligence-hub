import asyncio
import os
import shutil
from pathlib import Path
from app.db.gcp_storage import gcp_config
from app.db.gcp_storage import gcp_config
from app.db.database import DB_PATH
from app.config.settings import settings # Loads .env
from app.utils.logger import get_logger

# Setup logging
logger = get_logger(__name__)

async def purge_sqlite():
    """Delete the SQLite database file."""
    if DB_PATH.exists():
        logger.info(f"Removing local database: {DB_PATH}")
        try:
            os.remove(DB_PATH)
            logger.info("Local database removed.")
        except Exception as e:
            logger.error(f"Error removing local database: {e}")
    else:
        logger.info("No local database found.")

async def purge_bigquery():
    """Truncate BigQuery tables."""
    if not gcp_config.is_configured:
        logger.info("GCP not configured, skipping BigQuery purge.")
        return

    from google.cloud import bigquery
    client = bigquery.Client(project=gcp_config.project_id)
    dataset_id = gcp_config.full_dataset_id
    
    tables_to_purge = [
        "articles",
        "digest_items",
        "article_tags",
        "research_reports",
        "article_embeddings", # If used
        "ingestion_runs"
    ]

    logger.info(f"Purging BigQuery tables in {dataset_id}...")

    for table_name in tables_to_purge:
        table_id = f"{dataset_id}.{table_name}"
        try:
            # Check if table exists
            client.get_table(table_id)
            
            # Truncate (using DELETE WHERE TRUE as TRUNCATE is not always supported/same in all contexts, 
            # but DELETE is safer for standard tables)
            query = f"DELETE FROM `{table_id}` WHERE TRUE"
            job = client.query(query)
            job.result()
            logger.info(f"Cleared table: {table_name}")
            
        except Exception as e:
            if "Not found" in str(e):
                logger.info(f"Table not found (skipping): {table_name}")
            else:
                logger.error(f"Error purging {table_name}: {e}")

async def main():
    logger.info("Starting system-wide data purge...")
    
    # 1. Purge Local SQLite (Critical for deduplication reset)
    await purge_sqlite()
    
    # 2. Purge BigQuery
    await purge_bigquery()
    
    logger.info("Purge complete. Ready for clean backfill.")

if __name__ == "__main__":
    asyncio.run(main())
