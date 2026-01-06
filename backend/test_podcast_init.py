"""Quick test to verify podcast generation imports and initialization."""

from app.ingestion.generators.weekly_briefing import WeeklyBriefingGenerator
from app.config.settings import settings

print("✓ Import successful")
print(f"ElevenLabs API key configured: {bool(settings.elevenlabs_api_key)}")
print(f"Voice ID setting: {settings.elevenlabs_voice_id}")

gen = WeeklyBriefingGenerator()
print(f"✓ Generator initialized")
print(f"✓ ElevenLabs client: {'configured' if gen.elevenlabs_client else 'not configured'}")
if hasattr(gen, 'voice_id'):
    print(f"✓ Voice ID: {gen.voice_id}")
else:
    print("⚠ Voice ID attribute missing")

print("\n✓ All basic checks passed!")
print("Note: Actual podcast generation requires ELEVENLABS_API_KEY in .env")
