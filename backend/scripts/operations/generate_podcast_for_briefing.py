"""
Generate podcast audio for an existing weekly briefing.

Usage:
    python scripts/operations/generate_podcast_for_briefing.py [briefing_id]
    
If no briefing_id is provided, generates podcast for the most recent briefing.
"""

import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.db.gcp_storage import BigQueryDataStorage
from app.ingestion.generators.weekly_briefing import WeeklyBriefingGenerator
from app.config.settings import settings


async def generate_podcast_for_briefing(briefing_id: str = None):
    """Generate podcast for an existing briefing."""
    
    storage = BigQueryDataStorage()
    
    # 1. Get the briefing
    if briefing_id:
        print(f"📋 Fetching briefing: {briefing_id}")
        # Get from history and find matching ID
        briefings = await storage.get_weekly_briefing_history(limit=20)
        briefing = next((b for b in briefings if b['id'] == briefing_id), None)
    else:
        print("📋 Fetching most recent briefing...")
        briefing = await storage.get_latest_weekly_briefing()
    
    if not briefing:
        print("❌ No briefings found!")
        return
    
    if not briefing:
        print(f"❌ Briefing not found!")
        return
    
    briefing_id = briefing['id']
    title = briefing.get('briefing_title', 'Executive Briefing')
    
    print(f"✅ Found briefing: {briefing_id}")
    print(f"   Title: {title}")
    print(f"   Sections: {len(briefing.get('sections', []))}")
    print(f"   Current podcast_url: {briefing.get('podcast_url', 'None')}")
    
    if briefing.get('podcast_url'):
        print(f"\n⚠️  This briefing already has a podcast!")
        response = input("   Regenerate anyway? (y/N): ").strip().lower()
        if response != 'y':
            print("   Skipping.")
            return
    
    # 2. Initialize generator (for podcast methods)
    print("\n🎙️ Initializing podcast generator...")
    generator = WeeklyBriefingGenerator()
    
    if not generator.elevenlabs_client:
        print("❌ ElevenLabs client not configured!")
        print("   Make sure ELEVENLABS_API_KEY is set in your environment.")
        return
    
    print(f"   Voice ID: {generator.voice_id}")
    print(f"   Model: {getattr(settings, 'elevenlabs_model', 'eleven_monolingual_v1')}")
    
    # 3. Generate podcast
    print("\n🎤 Generating podcast audio...")
    print("   (This may take 30-60 seconds for a typical briefing)")
    
    try:
        podcast_result = await generator._generate_podcast(briefing, briefing_id)
        
        if podcast_result:
            print(f"\n✅ Podcast generated successfully!")
            print(f"   URL: {podcast_result['podcast_url']}")
            print(f"   Duration: {podcast_result['podcast_duration_seconds']}s")
            
            # 4. Update briefing in BigQuery
            print("\n💾 Updating briefing in BigQuery...")
            
            # Merge podcast data into briefing
            updated_briefing = {**briefing, **podcast_result}
            
            # Re-save the briefing with podcast data
            await storage.save_weekly_briefing(updated_briefing)
            
            print("✅ Briefing updated with podcast URL!")
            print(f"\n🎧 Listen at: {podcast_result['podcast_url']}")
            
        else:
            print("❌ Podcast generation failed!")
            
    except Exception as e:
        print(f"❌ Error generating podcast: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    briefing_id = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(generate_podcast_for_briefing(briefing_id))
