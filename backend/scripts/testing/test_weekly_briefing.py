"""
Test script to debug weekly briefing generation.
"""
import asyncio
import sys
import json
from pathlib import Path
from datetime import datetime

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

async def test_pre_brief_retrieval():
    """Test that we can retrieve the latest pre-brief."""
    from app.db.gcp_storage import BigQueryDataStorage, gcp_config
    
    print("=" * 60)
    print("Test 1: Retrieve Latest Pre-Brief")
    print("=" * 60)
    
    bq_storage = BigQueryDataStorage(gcp_config)
    await bq_storage.initialize()
    
    pre_brief = await bq_storage.get_latest_pre_briefing()
    
    if pre_brief:
        print(f"✅ Found pre-brief: {pre_brief['id']}")
        print(f"   Period: {pre_brief.get('period_start')} to {pre_brief.get('period_end')}")
        print(f"   Articles: {pre_brief.get('article_count')}")
        
        data = pre_brief.get('data', {})
        observations = data.get('observations', [])
        print(f"   Observations: {len(observations)}")
        
        if observations:
            print(f"\n   Sample observation:")
            obs = observations[0]
            print(f"     Category: {obs.get('category')}")
            print(f"     Summary: {obs.get('summary', '')[:100]}...")
        
        return pre_brief
    else:
        print("❌ No pre-brief found!")
        return None

async def test_historical_context():
    """Test historical context retrieval."""
    from app.ingestion.generators.weekly_briefing import WeeklyBriefingGenerator
    
    print("\n" + "=" * 60)
    print("Test 2: Historical Context")
    print("=" * 60)
    
    generator = WeeklyBriefingGenerator()
    context = await generator._get_historical_context(limit=2)
    
    print(f"Historical context ({len(context)} chars):")
    print(context[:1000] + "..." if len(context) > 1000 else context)

async def test_weekly_briefing_direct():
    """Test weekly briefing generation with verbose logging."""
    from app.ingestion.generators.weekly_briefing import WeeklyBriefingGenerator
    
    print("\n" + "=" * 60)
    print("Test 3: Generate Weekly Briefing (Verbose)")
    print("=" * 60)
    
    generator = WeeklyBriefingGenerator()
    
    # Get the latest pre-brief
    pre_brief = await generator._get_latest_pre_brief()
    
    if not pre_brief:
        print("❌ No pre-brief available")
        return None
    
    print(f"✅ Using pre-brief: {pre_brief['id']}")
    print(f"   Generated at: {pre_brief.get('generated_at')}")
    
    # Generate the briefing
    print("\n   Generating weekly briefing...")
    result = await generator.generate(pre_brief=pre_brief)
    
    if result:
        print(f"\n✅ Generated weekly briefing: {result['id']}")
        print(f"   BLUF: {result.get('bluf', 'N/A')[:100]}...")
        print(f"   Sections: {len(result.get('sections', []))}")
        
        for i, section in enumerate(result.get('sections', []), 1):
            headline = section.get('headline', {})
            header = section.get('header', 'Unknown')
            headline_text = headline.get('text', 'No headline') if isinstance(headline, dict) else str(headline)
            print(f"\n   Section {i}: {header}")
            print(f"     Headline: {headline_text[:80]}...")
        
        return result
    else:
        print("❌ Failed to generate weekly briefing")
        return None

async def check_bigquery_weekly_briefing():
    """Check what's actually in the BigQuery weekly_briefings table."""
    from google.cloud import bigquery
    from app.db.gcp_storage import gcp_config
    
    print("\n" + "=" * 60)
    print("Test 4: Check BigQuery Weekly Briefings Table")
    print("=" * 60)
    
    client = bigquery.Client(project=gcp_config.project_id)
    
    query = f"""
    SELECT id, briefing_title, bluf, 
           JSON_QUERY(data, '$.sections') as sections_json,
           generated_at
    FROM `{gcp_config.full_dataset_id}.weekly_briefings`
    ORDER BY generated_at DESC
    LIMIT 1
    """
    
    results = list(client.query(query).result())
    
    if results:
        row = results[0]
        print(f"✅ Latest weekly briefing in BQ:")
        print(f"   ID: {row.id}")
        print(f"   Title: {row.briefing_title}")
        print(f"   BLUF: {row.bluf[:100] if row.bluf else 'N/A'}...")
        print(f"   Generated: {row.generated_at}")
        
        # Parse sections
        if row.sections_json:
            sections = json.loads(row.sections_json)
            print(f"   Sections from raw JSON: {len(sections)}")
    else:
        print("❌ No weekly briefings in BigQuery")

async def main():
    print("🔍 WEEKLY BRIEFING DEBUG TEST")
    print("=" * 60)
    
    # Test 1: Pre-brief retrieval
    pre_brief = await test_pre_brief_retrieval()
    
    # Test 2: Historical context
    await test_historical_context()
    
    # Test 4: Check what's in BigQuery
    await check_bigquery_weekly_briefing()
    
    # Test 3: Generate a new weekly briefing
    # Commenting out to avoid extra cost - uncomment to test
    # await test_weekly_briefing_direct()

if __name__ == "__main__":
    asyncio.run(main())
