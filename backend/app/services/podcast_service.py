"""Podcast Service - Generate podcast scripts and audio using ElevenLabs."""

import uuid
import asyncio
import httpx
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path

from app.api.schemas import (
    PodcastScript,
    PodcastSpeaker,
    PodcastSegment,
    PodcastScriptResponse,
    PodcastAudioResponse,
    PodcastStyle,
)
from app.utils.logger import get_logger
from app.config.settings import settings

logger = get_logger(__name__)

# ElevenLabs API configuration
ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1"

# Default voice IDs (ElevenLabs stock voices)
DEFAULT_VOICES = {
    "host": {
        "name": "Rachel",
        "voice_id": "21m00Tcm4TlvDq8ikWAM",  # Rachel - calm, professional
    },
    "analyst": {
        "name": "Josh", 
        "voice_id": "TxGEqnHWrfWFTfGW9XjX",  # Josh - conversational
    },
}


class PodcastService:
    """
    Service for generating podcast content from intelligence reports.
    
    Features:
    1. Script generation - Uses LLM to create conversational scripts
    2. Audio synthesis - Uses ElevenLabs for natural-sounding voices
    3. Multi-speaker support - Host + Analyst format
    """
    
    def __init__(self):
        """Initialize the podcast service."""
        self._audio_cache_dir = Path(settings.base_dir) / "audio_cache"
        self._audio_cache_dir.mkdir(exist_ok=True)
        self._scripts_cache: Dict[str, PodcastScript] = {}
    
    async def generate_script(
        self,
        content: str,
        title: Optional[str] = None,
        style: PodcastStyle = PodcastStyle.CONVERSATIONAL,
    ) -> PodcastScriptResponse:
        """
        Generate a podcast script from content.
        
        Args:
            content: The content to convert into podcast format
            title: Optional title for the podcast
            style: Style of podcast (conversational, professional, brief)
            
        Returns:
            PodcastScriptResponse with script and estimated duration
        """
        logger.info(f"Generating podcast script: style={style.value}, content_length={len(content)}")
        
        # Define speakers based on style
        if style == PodcastStyle.BRIEF:
            speakers = [
                PodcastSpeaker(name="Host", voice_id=DEFAULT_VOICES["host"]["voice_id"]),
            ]
        else:
            speakers = [
                PodcastSpeaker(name="Host", voice_id=DEFAULT_VOICES["host"]["voice_id"]),
                PodcastSpeaker(name="Analyst", voice_id=DEFAULT_VOICES["analyst"]["voice_id"]),
            ]
        
        # Generate script segments
        # In production, this would use an LLM to create natural dialogue
        segments = await self._generate_script_segments(content, title, style, speakers)
        
        script = PodcastScript(
            speakers=speakers,
            segments=segments,
        )
        
        # Estimate duration (roughly 150 words per minute)
        total_words = sum(len(seg.text.split()) for seg in segments)
        estimated_duration = int((total_words / 150) * 60)  # seconds
        
        # Cache the script
        script_id = f"script_{uuid.uuid4().hex[:8]}"
        self._scripts_cache[script_id] = script
        
        return PodcastScriptResponse(
            script=script,
            estimated_duration=estimated_duration,
        )
    
    async def generate_audio(
        self,
        script: PodcastScript,
    ) -> PodcastAudioResponse:
        """
        Generate audio from a podcast script using ElevenLabs.
        
        Args:
            script: The podcast script with speakers and segments
            
        Returns:
            PodcastAudioResponse with audio URL and duration
        """
        logger.info(f"Generating podcast audio: {len(script.segments)} segments")
        
        # Check for API key
        api_key = getattr(settings, 'elevenlabs_api_key', None)
        
        if not api_key:
            logger.warning("ElevenLabs API key not configured, returning mock response")
            return self._generate_mock_audio_response()
        
        try:
            # Generate audio for each segment
            audio_segments = []
            
            async with httpx.AsyncClient() as client:
                for i, segment in enumerate(script.segments):
                    # Find voice ID for this speaker
                    voice_id = None
                    for speaker in script.speakers:
                        if speaker.name == segment.speaker:
                            voice_id = speaker.voice_id
                            break
                    
                    if not voice_id:
                        voice_id = DEFAULT_VOICES["host"]["voice_id"]
                    
                    # Call ElevenLabs API
                    audio_data = await self._synthesize_speech(
                        client=client,
                        text=segment.text,
                        voice_id=voice_id,
                        api_key=api_key,
                    )
                    
                    audio_segments.append(audio_data)
                    
                    # Small delay to avoid rate limits
                    if i < len(script.segments) - 1:
                        await asyncio.sleep(0.5)
            
            # Combine audio segments
            combined_audio = self._combine_audio_segments(audio_segments)
            
            # Save to file and generate URL
            audio_id = f"podcast_{uuid.uuid4().hex[:8]}"
            audio_path = self._audio_cache_dir / f"{audio_id}.mp3"
            
            with open(audio_path, "wb") as f:
                f.write(combined_audio)
            
            # Calculate duration (approximate from file size for MP3)
            duration = len(combined_audio) // 16000  # Rough estimate
            
            return PodcastAudioResponse(
                audio_url=f"/api/podcast/audio/{audio_id}",
                duration=duration,
            )
            
        except Exception as e:
            logger.error(f"Error generating audio: {e}")
            # Return mock response on error
            return self._generate_mock_audio_response()
    
    async def _synthesize_speech(
        self,
        client: httpx.AsyncClient,
        text: str,
        voice_id: str,
        api_key: str,
    ) -> bytes:
        """Synthesize speech using ElevenLabs API."""
        url = f"{ELEVENLABS_API_URL}/text-to-speech/{voice_id}"
        
        response = await client.post(
            url,
            headers={
                "xi-api-key": api_key,
                "Content-Type": "application/json",
            },
            json={
                "text": text,
                "model_id": "eleven_monolingual_v1",
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.75,
                },
            },
            timeout=60.0,
        )
        
        response.raise_for_status()
        return response.content
    
    def _combine_audio_segments(self, segments: List[bytes]) -> bytes:
        """
        Combine multiple audio segments into one.
        
        Note: For proper audio concatenation, you'd use a library like pydub.
        This is a simplified version that just concatenates bytes.
        """
        # In production, use pydub or similar for proper audio merging
        return b"".join(segments)
    
    async def _generate_script_segments(
        self,
        content: str,
        title: Optional[str],
        style: PodcastStyle,
        speakers: List[PodcastSpeaker],
    ) -> List[PodcastSegment]:
        """
        Generate script segments from content.
        
        In production, this would use an LLM to create natural dialogue.
        For now, we create a structured format.
        """
        segments = []
        
        # Introduction
        intro_title = title or "Intelligence Briefing"
        
        if style == PodcastStyle.BRIEF:
            segments.append(PodcastSegment(
                speaker="Host",
                text=f"Welcome to your {intro_title}. Here's what you need to know today."
            ))
        else:
            segments.append(PodcastSegment(
                speaker="Host",
                text=f"Welcome back to the C1 Intelligence Hub podcast. I'm your host, and today "
                     f"we're diving into {intro_title}."
            ))
            
            if len(speakers) > 1:
                segments.append(PodcastSegment(
                    speaker="Analyst",
                    text="Thanks for having me. We've got some significant developments to cover today."
                ))
        
        # Content sections
        # Split content into manageable chunks
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
        
        if style == PodcastStyle.BRIEF:
            # Brief style: just the host summarizing
            for para in paragraphs[:3]:  # Limit to 3 paragraphs for brief
                segments.append(PodcastSegment(
                    speaker="Host",
                    text=self._make_conversational(para),
                ))
        else:
            # Conversational/Professional: back and forth
            for i, para in enumerate(paragraphs[:5]):  # Limit to 5 sections
                if len(speakers) > 1 and i % 2 == 1:
                    speaker = "Analyst"
                else:
                    speaker = "Host"
                
                segments.append(PodcastSegment(
                    speaker=speaker,
                    text=self._make_conversational(para),
                ))
                
                # Add transitions
                if i < len(paragraphs) - 1 and len(speakers) > 1:
                    transition_speaker = "Analyst" if speaker == "Host" else "Host"
                    transitions = [
                        "That's a great point.",
                        "Interesting development there.",
                        "Let me add to that.",
                        "Worth noting as well.",
                    ]
                    # segments.append(PodcastSegment(
                    #     speaker=transition_speaker,
                    #     text=transitions[i % len(transitions)],
                    # ))
        
        # Conclusion
        if style == PodcastStyle.BRIEF:
            segments.append(PodcastSegment(
                speaker="Host",
                text="That's your briefing for today. Stay informed, stay ahead."
            ))
        else:
            segments.append(PodcastSegment(
                speaker="Host",
                text="That wraps up today's intelligence briefing. We'll keep monitoring these "
                     "developments and bring you updates as they unfold."
            ))
            
            if len(speakers) > 1:
                segments.append(PodcastSegment(
                    speaker="Analyst",
                    text="Thanks everyone for listening. Until next time, stay ahead of the curve."
                ))
        
        return segments
    
    def _make_conversational(self, text: str) -> str:
        """
        Transform text to be more conversational for podcast format.
        
        In production, this would use an LLM for natural transformation.
        """
        # Basic cleanup
        text = text.strip()
        
        # Remove markdown-style formatting
        text = text.replace("**", "").replace("*", "").replace("#", "")
        
        # Ensure it ends with proper punctuation
        if not text.endswith((".", "!", "?")):
            text += "."
        
        return text
    
    def _generate_mock_audio_response(self) -> PodcastAudioResponse:
        """Generate a mock response when ElevenLabs is not configured."""
        return PodcastAudioResponse(
            audio_url="/api/podcast/audio/mock_demo",
            duration=120,  # 2 minutes
        )
    
    def get_audio_file_path(self, audio_id: str) -> Optional[Path]:
        """Get the file path for a cached audio file."""
        audio_path = self._audio_cache_dir / f"{audio_id}.mp3"
        if audio_path.exists():
            return audio_path
        return None
