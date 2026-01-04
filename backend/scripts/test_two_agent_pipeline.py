
import asyncio
import os
import sys
import json
import io
from datetime import datetime, timedelta
from pathlib import Path

# Force UTF-8 for Windows console
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent))

from app.ingestion.generators.pre_briefing import PreBriefGenerator
from app.ingestion.generators.weekly_briefing import WeeklyBriefingGenerator, generate_weekly_briefing
from app.db.database import get_db
import logging

# Configure logging
logging.basicConfig(level=logging.INFO) # Changed from DEBUG
logging.getLogger("aiosqlite").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("anthropic").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

async def test_pipeline():
    print("=== Starting Two-Agent Briefing Pipeline Test ===")
    
    db = get_db()
    await db.initialize()
    
    # Run Agent 1 directly for debugging if needed, or stick to pipeline
    from app.ingestion.generators.pre_briefing import PreBriefGenerator
    
    # Verify Agent 1 independently first
    print("\nStep 0: Verifying Agent 1 (Pre-Brief) independently...")
    agent1 = PreBriefGenerator()
    pre_brief = await agent1.generate_pre_brief(days=14)
    if not pre_brief:
        print("CRITICAL: Agent 1 failed to generate pre-brief. check logs above for 'Raw problematic JSON'.")
        # Explicitly check for articles if Agent 1 failed
        articles = await db.query_corpus(hours=14*24, limit=1)
        print(f"Sanity check: Articles found in last 14 days? {'Yes' if articles else 'No'}")
        return
    
    print(f"Agent 1 Succeeded! Observations count: {len(pre_brief.get('data', {}).get('observations', []))}")
    
    # 1. Verify we have some articles to work with
    articles = await db.query_corpus(hours=14*24, limit=10)
    print(f"Found {len(articles)} articles in last 14 days.")
    
    if not articles:
        print("WARNING: No articles found. Agent 1 might produce empty results.")
    
    # 2. Run the orchestrated pipeline
    print("\nStep 1 & 2: Running Pipeline (Agent 1 -> Agent 2)...")
    start_time = datetime.utcnow()
    briefing = await generate_weekly_briefing()
    end_time = datetime.utcnow()
    
    if not briefing:
        print("FAILED: No briefing generated.")
        return
    
    print(f"\nSUCCESS: Briefing generated in {(end_time - start_time).total_seconds():.1f}s")
    print(f"Title: {briefing.get('briefing_title')}")
    print(f"BLUF: {briefing.get('bluf')}")
    print(f"Sections: {len(briefing.get('sections', []))}")
    
    # 3. Verify Pre-Brief was stored
    print("\nVerifying Pre-Brief storage...")
    pre_brief = await db.get_latest_pre_briefing()
    if pre_brief:
        print(f"Found latest pre-brief generated at: {pre_brief.get('generated_at')}")
        print(f"Article count in pre-brief: {pre_brief.get('article_count')}")
    else:
        print("WARNING: Pre-brief not found in database.")
        
    # 4. Print Sections for visual check
    print("\n--- Briefing Sections ---")
    for i, section in enumerate(briefing.get("sections", [])):
        print(f"\nSection {i+1}: {section.get('header')}")
        headline = section.get('headline', {})
        print(f"Headline: {headline.get('text')}")
        print(f"Conviction: {headline.get('conviction_score')} | Signal: {headline.get('signal_type')}")
        for j, insight in enumerate(section.get('insights', [])):
            print(f"  - Insight {j+1}: {insight.get('text')[:100]}...")
            print(f"    Signal: {insight.get('signal_type')}")

    print("\n=== Test Complete ===")

if __name__ == "__main__":
    asyncio.run(test_pipeline())
