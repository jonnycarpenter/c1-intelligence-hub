
import asyncio
import logging
import sys
from datetime import datetime

# Add empty SEC_API_KEY check or mocked run if key missing
from app.config.settings import settings

# Setup simple logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)

async def test_pr_tool():
    logger.info("--- Testing Press Release Tool ---")
    if not settings.tavily_api_key:
        logger.warning("No Tavily API Key found. Skipping PR Test.")
        return

    from app.tools.press_releases.collector import PressReleaseCollector
    
    collector = PressReleaseCollector()
    
    # Test for Hexcel
    company = {"id": "HXL", "name": "Hexcel Corporation", "ticker": "HXL"}
    logger.info(f"Collecting PRs for {company['name']}...")
    
    results = collector.collect_for_company(company['id'], company['name'], company['ticker'])
    
    logger.info(f"Found {len(results)} press releases.")
    for pr in results[:3]:
        logger.info(f"- {pr.title} ({pr.url}) Source: {pr.source}")

async def test_sec_tool():
    logger.info("\n--- Testing SEC Filing Tool ---")
    if not settings.sec_api_key:
        logger.warning("No SEC API Key found. Skipping SEC Test.")
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

async def main():
    logger.info("Starting Tool Verification...")
    await test_pr_tool()
    await test_sec_tool()
    logger.info("Verification Complete.")

if __name__ == "__main__":
    # Ensure current directory is in python path
    import os
    sys.path.append(os.getcwd())
    asyncio.run(main())
