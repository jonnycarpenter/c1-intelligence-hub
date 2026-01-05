"""Check digest data quality and what the frontend would receive."""
import asyncio
from app.services.digest_service import DigestService

async def main():
    service = DigestService()
    
    print("=== Testing Digest Service (what frontend receives) ===\n")
    
    # Get digest as the frontend would
    digest = await service.get_digest(hours=72)
    
    print(f"Generated at: {digest.generated_at}")
    print(f"Period: {digest.period_start} to {digest.period_end}")
    print(f"Total items: {digest.stats.total_items}")
    print(f"Summary: {digest.summary[:200]}...")
    
    print(f"\n=== Items Breakdown ===")
    print(f"By Category: {digest.stats.by_category}")
    print(f"By Priority: {digest.stats.by_priority}")
    
    if digest.items:
        print(f"\n=== First 5 Items ===")
        for i, item in enumerate(digest.items[:5], 1):
            print(f"\n{i}. {item.title[:80]}")
            print(f"   Category: {item.category}")
            print(f"   Priority: {item.priority}")
            print(f"   Published: {item.published_at}")
            print(f"   Sources: {len(item.sources)}")
            print(f"   Coverage: {item.coverage_count}")
    else:
        print("\n⚠️  NO ITEMS in digest!")
        
    # Check if filtering is working
    print("\n\n=== Testing Filters ===")
    from app.api.schemas import DigestCategory, Priority
    
    # Try filtering by priority
    high_priority = await service.get_digest(hours=72, priorities=[Priority.HIGH])
    print(f"High priority items: {high_priority.stats.total_items}")
    
    critical_priority = await service.get_digest(hours=72, priorities=[Priority.CRITICAL])
    print(f"Critical priority items: {critical_priority.stats.total_items}")

if __name__ == "__main__":
    asyncio.run(main())
