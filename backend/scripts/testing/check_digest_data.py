"""Quick script to check digest_items table data."""
import asyncio
from datetime import datetime, timedelta
from app.db.gcp_storage import get_storage

async def main():
    storage = await get_storage()
    print(f"Storage type: {type(storage).__name__}")
    
    # Check total digest items
    try:
        items = await storage.get_digest_items(hours=72, limit=10)
        print(f"\n=== Digest Items (last 72 hours) ===")
        print(f"Total items returned: {len(items)}")
        
        if items:
            print("\nFirst 3 items:")
            for i, item in enumerate(items[:3], 1):
                print(f"\n{i}. {item.get('title', 'No title')}")
                print(f"   Published: {item.get('published_at')}")
                print(f"   Classified: {item.get('classified_at')}")
                print(f"   Category: {item.get('category')}")
                print(f"   Priority: {item.get('priority')}")
        else:
            print("\n⚠️  NO ITEMS FOUND in the last 72 hours!")
            
            # Check if there are ANY items at all
            all_items = await storage.get_digest_items(hours=24*365, limit=5)
            if all_items:
                print(f"\nBut found {len(all_items)} items when looking back 1 year:")
                for item in all_items[:3]:
                    print(f"  - {item.get('title')} (published: {item.get('published_at')})")
            else:
                print("\n❌ NO DIGEST ITEMS FOUND AT ALL in the digest_items table!")
                
    except Exception as e:
        print(f"Error querying digest items: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
