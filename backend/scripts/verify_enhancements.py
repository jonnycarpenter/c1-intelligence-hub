import asyncio
import os
import sys

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.ingestion.generators.weekly_briefing import WeeklyBriefingGenerator
from app.db.database import get_db

async def test_generation():
    print("Testing Weekly Briefing Generation with Inline Logos...")
    generator = WeeklyBriefingGenerator()
    
    # Mock some data or use actual recent articles
    # For a dry run, we'll just check the prompt expansion
    print(f"Using model: {generator.model}")
    
    # We can't easily run a full generation without real API keys and data,
    # but we can verify the prompt contains our new requirements.
    prompt = generator.WEEKLY_BRIEFING_PROMPT
    
    requirements = [
        "CREATE EXACTLY 4 SECTIONS",
        "INLINE LOGOS (CRITICAL)",
        "[[Company Name]]",
        "Suppliers and Competitors"
    ]
    
    all_passed = True
    for req in requirements:
        if req in prompt:
            print(f"✅ Found requirement: {req}")
        else:
            print(f"❌ Missing requirement: {req}")
            all_passed = False
            
    if all_passed:
        print("\nPrompt Verification PASSED")
    else:
        print("\nPrompt Verification FAILED")

if __name__ == "__main__":
    asyncio.run(test_generation())
