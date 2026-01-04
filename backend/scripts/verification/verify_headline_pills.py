"""Verification script for Headline field and Pill formatting."""
import asyncio
import sys
import uuid
from datetime import datetime
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from app.services.digest_service import DigestService
from app.api.schemas import DigestItem, Priority as ApiPriority, DigestCategory
from app.models.corpus import Priority as CorpusPriority, ContentCategory

async def verify_formatting():
    print("=" * 60)
    print("Verifying Headline and Pill Formatting")
    print("=" * 60)
    
    service = DigestService()
    
    # test _format_pill
    print("\n[1] Testing _format_pill...")
    test_cases = {
        "supply_chain": "Supply Chain",
        "aerospace": "Aerospace",
        "market": "Market",
        "c1_mention": "C1 Mention",
        "defense_space": "Defense Space"
    }
    
    for input_str, expected in test_cases.items():
        result = service._format_pill(input_str)
        if result == expected:
            print(f"  ✓ '{input_str}' -> '{result}'")
        else:
            print(f"  ✗ '{input_str}' -> '{result}' (expected '{expected}')")

    # test DigestItem instantiation with formatted values
    print("\n[2] Testing DigestItem instantiation with formatted values...")
    try:
        raw_data = {
            "id": str(uuid.uuid4()),
            "title": "Old Catchy Title",
            "headline": "A Much Better Headline for Composites",
            "digest_summary": "Summary of the story.",
            "category": "supply_chain",
            "priority": "high",
            "published_at": datetime.now(),
            "ingested_at": datetime.now(),
            "companies": ["Solvay", "Hexcel"],
            "materials": ["Carbon Fiber"],
            "topics": ["sustainability"],
            "industries": ["aerospace", "defense_space"],
            "source_name": "Composites World",
            "url": "https://example.com"
        }
        
        # This simulates what _convert_to_digest_item does
        item = service._convert_to_digest_item(raw_data)
        
        print(f"  ✓ DigestItem created successfully")
        print(f"  - Headline: {item.headline}")
        print(f"  - Category: {item.category} (Type: {type(item.category)})")
        print(f"  - Priority: {item.priority} (Type: {type(item.priority)})")
        print(f"  - Industries: {item.entities.industries}")
        print(f"  - Topics: {item.entities.topics}")
        
        # Verify specific values
        if item.category == "Supply Chain":
             print("  ✓ Category correctly formatted as enum value 'Supply Chain'")
        else:
             print(f"  ✗ Category mismatch: {item.category}")
             
        if item.entities.industries == ["Aerospace", "Defense Space"]:
             print("  ✓ Industries correctly formatted")
        else:
             print(f"  ✗ Industries mismatch: {item.entities.industries}")

        if item.headline == "A Much Better Headline for Composites":
             print("  ✓ Headline correctly mapped")
        else:
             print(f"  ✗ Headline mismatch: {item.headline}")

    except Exception as e:
        print(f"  ✗ Error instantiating DigestItem: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 60)
    print("Verification Complete")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(verify_formatting())
