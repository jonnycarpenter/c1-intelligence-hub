"""Check the latest briefing details."""
import asyncio
import json
from app.db.gcp_storage import BigQueryDataStorage, gcp_config


async def main():
    storage = BigQueryDataStorage(gcp_config)
    await storage.initialize()
    
    briefings = await storage.get_weekly_briefings(limit=1)
    if not briefings:
        print("No briefings found!")
        return
    
    b = briefings[0]
    print(f"Title: {b['briefing_title']}")
    print(f"Generated: {b['generated_at']}")
    print(f"BLUF: {b.get('bluf', 'NO BLUF')[:300]}...")
    print(f"\nSections: {len(b.get('sections', []))}")
    
    for i, section in enumerate(b.get('sections', []), 1):
        print(f"\nSection {i}: {section.get('header')}")
        headline = section.get('headline', {})
        print(f"  Headline: {headline.get('text', '')[:100]}...")
        print(f"  Sources: {len(section.get('source_articles', []))} articles")
        
        # Show first few citations
        for j, src in enumerate(section.get('source_articles', [])[:3], 1):
            print(f"    [{src.get('article_number')}] {src.get('source_name', 'Unknown')} - {src.get('title', '')[:50]}")


if __name__ == "__main__":
    asyncio.run(main())
