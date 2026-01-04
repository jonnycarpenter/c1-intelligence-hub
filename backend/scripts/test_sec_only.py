
import asyncio
import logging
import sys
from datetime import datetime
from app.config.settings import settings

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)

async def test_sec_tool():
    logger.info("--- Testing SEC Filing Tool ---")
    if not settings.sec_api_key:
        logger.warning("No SEC API Key found in settings.")
        return

    from app.tools.sec_filings.collector import SECFilingCollector
    
    collector = SECFilingCollector()
    
    ticker = "HXL"
    logger.info(f"Collecting SEC filings for {ticker}...")
    
    results = collector.collect_for_company("HXL", ticker)
    
    logger.info(f"Found {len(results)} filings.")
    for filing in results[:3]:
        logger.info(f"- {filing.form_type} ({filing.filed_at}) URL: {filing.filing_url}")
        if filing.sections:
            logger.info(f"  Sections extracted: {list(filing.sections.keys())}")
        if filing.full_text:
            logger.info(f"  Full text extracted (Length: {len(filing.full_text)})")

if __name__ == "__main__":
    import os
    sys.path.append(os.getcwd())
    asyncio.run(test_sec_tool())
