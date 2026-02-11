"""Check for items with 'Lowium' priority bug."""
import asyncio
from app.db.gcp_storage import get_storage


async def check_lowium():
    storage = await get_storage()
    
    # Query for Lowium priority items
    query = """
    SELECT id, title, priority, source_type, published_at, classified_at
    FROM `<GCP_PROJECT_ID>.c1_intelligence.digest_items`
    WHERE priority = "Lowium"
    ORDER BY classified_at DESC
    LIMIT 20
    """
    
    result = storage.client.query(query)
    rows = list(result)
    
    print(f"\n🔍 Found {len(rows)} items with priority='Lowium'\n")
    
    if rows:
        for row in rows:
            print(f"ID: {row.id}")
            print(f"Title: {row.title[:80]}")
            print(f"Priority: {row.priority}")
            print(f"Source: {row.source_type}")
            print(f"Published: {row.published_at}")
            print(f"Classified: {row.classified_at}")
            print("-" * 80)
    
    # Also check what valid priorities exist
    priority_query = """
    SELECT priority, COUNT(*) as count
    FROM `<GCP_PROJECT_ID>.c1_intelligence.digest_items`
    GROUP BY priority
    ORDER BY count DESC
    """
    
    priority_result = storage.client.query(priority_query)
    priority_rows = list(priority_result)
    
    print(f"\n📊 Priority Distribution:\n")
    for row in priority_rows:
        print(f"  {row.priority}: {row.count}")
    
    return rows


if __name__ == "__main__":
    asyncio.run(check_lowium())
