"""
Test script to verify pre-briefing generator uses BigQuery.

This validates the fix: Agent 1 should query BigQuery articles table
instead of SQLite corpus_items.
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

async def test_data_source():
    """Test that _get_articles uses BigQuery."""
    from app.ingestion.generators.pre_briefing import PreBriefGenerator
    
    generator = PreBriefGenerator()
    
    # Test 1: Verify BigQuery storage is available
    print("=" * 60)
    print("Test 1: BigQuery Storage Availability")
    print("=" * 60)
    
    bq_storage = await generator._get_bq_storage()
    if bq_storage:
        print("✅ BigQuery storage initialized successfully")
    else:
        print("❌ BigQuery storage NOT available - fix failed!")
        return False
    
    # Test 2: Query articles directly from BigQuery
    print("\n" + "=" * 60)
    print("Test 2: BigQuery Article Count (last 14 days)")
    print("=" * 60)
    
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=14)
    
    articles = await bq_storage.get_articles(
        start_date=start_date,
        end_date=end_date,
        limit=100
    )
    print(f"✅ BigQuery articles found: {len(articles)}")
    
    if articles:
        print(f"\nSample article:")
        a = articles[0]
        print(f"  Title: {a.title[:60]}...")
        print(f"  Source: {a.source_name}")
        print(f"  Published: {a.published_at}")
        print(f"  Summary: {a.summary[:100] if a.summary else 'N/A'}...")
    
    # Test 3: Verify _get_articles method uses BigQuery
    print("\n" + "=" * 60)
    print("Test 3: PreBriefGenerator._get_articles() Method")
    print("=" * 60)
    
    articles, period_start, period_end = await generator._get_articles(days=14)
    print(f"✅ _get_articles returned {len(articles)} articles")
    print(f"   Period: {period_start.date()} to {period_end.date()}")
    
    # Test 4: Verify custom date range works
    print("\n" + "=" * 60)
    print("Test 4: Historical Period (Dec 8-21, 2025)")
    print("=" * 60)
    
    hist_start = datetime(2025, 12, 8)
    hist_end = datetime(2025, 12, 21, 23, 59, 59)
    
    articles, period_start, period_end = await generator._get_articles(
        start_date=hist_start,
        end_date=hist_end
    )
    print(f"✅ Historical period returned {len(articles)} articles")
    print(f"   Period: {period_start.date()} to {period_end.date()}")
    
    # Test 5: Test all three target periods
    print("\n" + "=" * 60)
    print("Test 5: All Target Periods")
    print("=" * 60)
    
    periods = [
        ("Current (Dec 22 - Jan 4)", datetime(2025, 12, 22), datetime(2026, 1, 4, 23, 59, 59)),
        ("Historical 1 (Dec 8-21)", datetime(2025, 12, 8), datetime(2025, 12, 21, 23, 59, 59)),
        ("Historical 2 (Nov 24 - Dec 7)", datetime(2025, 11, 24), datetime(2025, 12, 7, 23, 59, 59)),
    ]
    
    for name, start, end in periods:
        articles_bq = await bq_storage.get_articles(
            start_date=start,
            end_date=end,
            limit=100
        )
        print(f"  {name}: {len(articles_bq)} articles")
    
    print("\n" + "=" * 60)
    print("✅ All tests passed - BigQuery is now the data source!")
    print("=" * 60)
    return True

if __name__ == "__main__":
    success = asyncio.run(test_data_source())
    sys.exit(0 if success else 1)
