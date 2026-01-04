"""Test the Pulse tab API endpoints."""
import asyncio
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from app.db.database import get_db
from app.services.digest_service import DigestService


async def test_apis():
    print("=" * 60)
    print("Testing Pulse Tab APIs")
    print("=" * 60)
    
    # Test 1: Get digest data (for left column - news feed)
    print("\n[1] Testing Digest API (news feed)...")
    digest_service = DigestService()
    
    try:
        # Get digest for 7 days (168 hours)
        digest = await digest_service.get_digest(hours=168)
        print(f"✓ Digest retrieved: {len(digest.items)} items")
        print(f"  - Period: {digest.period_start} to {digest.period_end}")
        print(f"  - Stats: {digest.stats}")
        
        if digest.items:
            print(f"\n  Sample items:")
            for item in digest.items[:3]:
                print(f"    - [{item.category}] {item.title[:50]}...")
        else:
            print("  ⚠ No digest items found!")
    except Exception as e:
        print(f"✗ Error getting digest: {e}")
    
    # Test 2: Get briefing summaries (for right column - executive summary)
    print("\n[2] Testing Briefing Summaries API (30-day executive summary)...")
    db = get_db()
    
    try:
        briefings = await db.get_latest_briefings()
        print(f"✓ Briefings retrieved: {len(briefings)} categories")
        
        for b in briefings:
            print(f"\n  Category: {b['category']}")
            print(f"  Headline: {b['headline'][:60]}...")
            print(f"  Generated: {b['generated_at']}")
            print(f"  Trend: {b['trend_signal']}, Attention: {b['attention_flag']}")
    except Exception as e:
        print(f"✗ Error getting briefings: {e}")
    
    print("\n" + "=" * 60)
    print("Test Complete")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_apis())
