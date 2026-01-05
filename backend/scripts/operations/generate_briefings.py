"""
Generate Historical Pre-Briefings and Weekly Briefing
=====================================================

This script:
1. Deletes existing pre_briefings and weekly_briefings
2. Generates 3 pre-briefings for historical periods
3. Generates 1 weekly briefing using all pre-briefings

Periods:
- Period 1: Dec 22, 2025 - Jan 4, 2026 (current)
- Period 2: Dec 8-21, 2025 (historical)
- Period 3: Nov 24 - Dec 7, 2025 (historical)
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

async def delete_existing_briefings():
    """Delete all existing pre-briefings and weekly briefings."""
    from google.cloud import bigquery
    from app.db.gcp_storage import gcp_config
    
    client = bigquery.Client(project=gcp_config.project_id)
    
    print("=" * 60)
    print("Step 1: Deleting Existing Briefings")
    print("=" * 60)
    
    # Delete pre-briefings
    pre_query = f"DELETE FROM `{gcp_config.full_dataset_id}.pre_briefings` WHERE 1=1"
    try:
        result = client.query(pre_query).result()
        print(f"✅ Deleted all pre_briefings")
    except Exception as e:
        print(f"⚠️ Error deleting pre_briefings: {e}")
    
    # Delete weekly briefings
    weekly_query = f"DELETE FROM `{gcp_config.full_dataset_id}.weekly_briefings` WHERE 1=1"
    try:
        result = client.query(weekly_query).result()
        print(f"✅ Deleted all weekly_briefings")
    except Exception as e:
        print(f"⚠️ Error deleting weekly_briefings: {e}")

async def generate_pre_briefings():
    """Generate pre-briefings for all 3 periods."""
    from app.ingestion.generators.pre_briefing import PreBriefGenerator
    
    print("\n" + "=" * 60)
    print("Step 2: Generating Pre-Briefings")
    print("=" * 60)
    
    periods = [
        ("Period 3: Nov 24 - Dec 7, 2025", datetime(2025, 11, 24), datetime(2025, 12, 7, 23, 59, 59)),
        ("Period 2: Dec 8-21, 2025", datetime(2025, 12, 8), datetime(2025, 12, 21, 23, 59, 59)),
        ("Period 1: Dec 22 - Jan 4, 2026", datetime(2025, 12, 22), datetime(2026, 1, 4, 23, 59, 59)),
    ]
    
    generator = PreBriefGenerator()
    results = []
    
    for name, start_date, end_date in periods:
        print(f"\n📋 Generating {name}...")
        print(f"   Date range: {start_date.date()} to {end_date.date()}")
        
        try:
            result = await generator.generate_pre_brief(
                start_date=start_date,
                end_date=end_date
            )
            
            if result:
                obs_count = len(result.get('data', {}).get('observations', []))
                print(f"   ✅ Generated pre-brief: {result['id']}")
                print(f"   📊 Observations: {obs_count}")
                print(f"   📰 Articles analyzed: {result.get('article_count', 0)}")
                results.append(result)
            else:
                print(f"   ❌ Failed to generate pre-brief")
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    return results

async def generate_weekly_briefing():
    """Generate weekly briefing using all pre-briefings."""
    from app.ingestion.generators.weekly_briefing import WeeklyBriefingGenerator
    
    print("\n" + "=" * 60)
    print("Step 3: Generating Weekly Briefing")
    print("=" * 60)
    
    try:
        generator = WeeklyBriefingGenerator()
        result = await generator.generate()
        
        if result:
            # Note: sections is at top level, not inside 'data'
            sections = result.get('sections', [])
            bluf = result.get('bluf', 'N/A')
            print(f"✅ Generated weekly briefing: {result['id']}")
            print(f"📊 Sections: {len(sections)}")
            print(f"📝 BLUF: {bluf[:100]}..." if bluf else "📝 BLUF: None")
            
            for i, section in enumerate(sections, 1):
                headline = section.get('headline', {})
                header = section.get('header', 'Unknown')
                headline_text = headline.get('text', 'No headline')[:50] if isinstance(headline, dict) else str(headline)[:50]
                status = headline.get('status', 'unknown') if isinstance(headline, dict) else 'unknown'
                print(f"   {i}. [{status.upper()}] {header}: {headline_text}...")
            
            return result
        else:
            print("❌ Failed to generate weekly briefing")
            return None
    except Exception as e:
        print(f"❌ Error generating weekly briefing: {e}")
        import traceback
        traceback.print_exc()
        return None

async def verify_results():
    """Verify briefings were created in BigQuery."""
    from google.cloud import bigquery
    from app.db.gcp_storage import gcp_config
    
    print("\n" + "=" * 60)
    print("Step 4: Verification")
    print("=" * 60)
    
    client = bigquery.Client(project=gcp_config.project_id)
    
    # Count pre-briefings
    pre_query = f"SELECT COUNT(*) as cnt FROM `{gcp_config.full_dataset_id}.pre_briefings`"
    pre_count = list(client.query(pre_query).result())[0].cnt
    print(f"📋 Pre-briefings in BigQuery: {pre_count}")
    
    # Count weekly briefings
    weekly_query = f"SELECT COUNT(*) as cnt FROM `{gcp_config.full_dataset_id}.weekly_briefings`"
    weekly_count = list(client.query(weekly_query).result())[0].cnt
    print(f"📰 Weekly briefings in BigQuery: {weekly_count}")
    
    # List pre-briefings
    list_query = f"""
    SELECT id, period_start, period_end, article_count 
    FROM `{gcp_config.full_dataset_id}.pre_briefings`
    ORDER BY period_start ASC
    """
    print("\nPre-briefings:")
    for row in client.query(list_query).result():
        print(f"  {row.period_start} to {row.period_end}: {row.article_count} articles")

async def main():
    print("\n" + "=" * 60)
    print("🚀 BRIEFING GENERATION SCRIPT")
    print("=" * 60)
    print(f"Started at: {datetime.now()}")
    
    # Step 1: Delete existing
    await delete_existing_briefings()
    
    # Step 2: Generate pre-briefings
    pre_briefings = await generate_pre_briefings()
    
    if len(pre_briefings) < 3:
        print("\n⚠️ Warning: Not all pre-briefings generated successfully")
        print("   Proceeding with weekly briefing anyway...")
    
    # Step 3: Generate weekly briefing
    weekly = await generate_weekly_briefing()
    
    # Step 4: Verify
    await verify_results()
    
    print("\n" + "=" * 60)
    print(f"🎉 Completed at: {datetime.now()}")
    print("=" * 60)
    
    return pre_briefings, weekly

if __name__ == "__main__":
    asyncio.run(main())
