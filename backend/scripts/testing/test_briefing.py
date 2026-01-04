import asyncio
import logging
import sys
from pathlib import Path

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent))

from app.ingestion.orchestrator import IngestionOrchestrator, IngestionConfig
from app.db.database import get_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_briefing_generation():
    logger.info("Starting briefing generation test...")
    
    # Initialize orchestrator with IngestionConfig
    config = IngestionConfig()
    orchestrator = IngestionOrchestrator(config)
    await orchestrator.initialize()
    
    # Generate briefings for categories
    logger.info("Generating briefings...")
    briefings = await orchestrator.briefing_generator.generate_all_categories(days=30)
    
    logger.info(f"Generated {len(briefings)} briefings.")
    for b in briefings:
        logger.info(f"Category: {b['category']}")
        logger.info(f"Headline: {b['headline']}")
        logger.info("-" * 20)
    
    # Test retrieval
    logger.info("Testing retrieval from DB...")
    db = get_db()
    latest = await db.get_latest_briefings()
    logger.info(f"Retrieved {len(latest)} briefings from database.")
    
    if len(latest) > 0:
        logger.info("Verification SUCCESSful")
    else:
        logger.warning("No briefings found in DB. Generation might have skipped due to lack of articles.")

if __name__ == "__main__":
    asyncio.run(test_briefing_generation())
