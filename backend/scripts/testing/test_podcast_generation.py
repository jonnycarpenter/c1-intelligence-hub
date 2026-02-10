"""
Test podcast generation for the latest weekly briefing.

This script fetches the latest briefing and attempts to generate a podcast for it.
Run from backend directory: python scripts/test_podcast_generation.py
"""

import asyncio
import os
import sys

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config.settings import settings
from app.db.gcp_storage import BigQueryDataStorage
from app.ingestion.generators.weekly_briefing import WeeklyBriefingGenerator
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def test_podcast():
    """Test podcast generation for the latest briefing."""
    
    print("\n" + "="*60)
    print("PODCAST GENERATION TEST")
    print("="*60)
    
    # Check ElevenLabs API key
    api_key = settings.elevenlabs_api_key
    if not api_key:
        print("\n❌ ERROR: ELEVENLABS_API_KEY not set!")
        print("   Set it in your .env file or environment")
        return
    
    print(f"\n✅ ElevenLabs API key found (length: {len(api_key)})")
    
    # Get latest briefing
    print("\n📥 Fetching latest briefing from BigQuery...")
    bq = BigQueryDataStorage()
    briefing = await bq.get_latest_weekly_briefing()
    
    if not briefing:
        print("❌ No briefing found in BigQuery!")
        return
    
    print(f"✅ Found briefing: {briefing.get('briefing_title', 'Unknown')}")
    print(f"   ID: {briefing.get('id')}")
    print(f"   Generated: {briefing.get('generated_at')}")
    print(f"   Current podcast_url: {briefing.get('podcast_url', 'None')}")
    
    # Initialize generator and try podcast
    print("\n🎙️  Attempting podcast generation...")
    generator = WeeklyBriefingGenerator()
    
    try:
        result = await generator._generate_podcast(briefing, briefing['id'])
        
        if result:
            print("\n✅ SUCCESS! Podcast generated:")
            print(f"   URL: {result.get('podcast_url')}")
            print(f"   Duration: {result.get('podcast_duration_seconds')}s")
            
            # Update the briefing in BigQuery with the podcast URL
            print("\n📤 Updating briefing with podcast URL...")
            briefing.update(result)
            success = await bq.save_weekly_briefing(briefing)
            if success:
                print("✅ Briefing updated with podcast!")
            else:
                print("❌ Failed to update briefing")
        else:
            print("\n❌ Podcast generation returned None")
            print("   Check the logs above for error details")
            
    except Exception as e:
        print(f"\n❌ Exception during podcast generation: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_podcast())
