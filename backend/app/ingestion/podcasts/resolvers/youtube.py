"""
YouTube Transcript Resolver
===========================

Extract transcripts from YouTube videos using auto/manual captions.
FREE - no API costs (uses unofficial youtube_transcript_api).

NOTE: YouTube auto-captions do NOT include speaker diarization,
so transcripts from this resolver will typically fail the speaker
labels quality gate and fall back to AssemblyAI.
"""

import re
import time
from typing import Optional

from app.utils.logger import get_logger
from ..models import PodcastEpisode, TranscriptResult, TranscriptSource
from .base import TranscriptResolver, ResolutionResult

logger = get_logger(__name__)


class YouTubeTranscriptResolver(TranscriptResolver):
    """Resolve transcripts from YouTube videos. FREE."""

    @property
    def name(self) -> str:
        return "youtube_transcript"

    @property
    def is_paid(self) -> bool:
        return False

    async def resolve(self, episode: PodcastEpisode) -> ResolutionResult:
        start_time = time.time()
        video_id = self._get_video_id(episode)

        if not video_id:
            return ResolutionResult(success=False, error_message="No YouTube video ID available")

        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            from youtube_transcript_api._errors import NoTranscriptFound
        except ImportError:
            return ResolutionResult(success=False, error_message="youtube_transcript_api not installed")

        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

            source = TranscriptSource.YOUTUBE_AUTO
            transcript_data = None

            try:
                transcript_data = transcript_list.find_manually_created_transcript(
                    ['en', 'en-US', 'en-GB']
                ).fetch()
                source = TranscriptSource.YOUTUBE_MANUAL
                logger.info(f"[YOUTUBE] Found manual transcript for {video_id}")
            except NoTranscriptFound:
                try:
                    transcript_data = transcript_list.find_generated_transcript(
                        ['en', 'en-US', 'en-GB']
                    ).fetch()
                    logger.info(f"[YOUTUBE] Found auto-generated transcript for {video_id}")
                except NoTranscriptFound:
                    return ResolutionResult(success=False, error_message="No English transcript available")

            if not transcript_data:
                return ResolutionResult(success=False, error_message="Failed to fetch transcript data")

            # Build segments and full text
            segments = []
            full_text_parts = []
            for entry in transcript_data:
                start_ms = int(entry['start'] * 1000)
                duration_ms = int(entry.get('duration', 0) * 1000)
                segments.append({
                    "start_ms": start_ms,
                    "end_ms": start_ms + duration_ms,
                    "text": entry['text'].strip(),
                })
                full_text_parts.append(entry['text'].strip())

            full_text = ' '.join(full_text_parts)
            full_text = self._clean_youtube_text(full_text)

            transcript = TranscriptResult(
                full_text=full_text,
                source=source,
                has_speaker_labels=False,  # YouTube captions lack speaker diarization
                word_count=len(full_text.split()),
                cost_usd=0.0,
                segments=segments,
            )

            processing_time = time.time() - start_time
            logger.info(
                f"[YOUTUBE] Resolved transcript for {episode.title[:40]}... "
                f"({len(full_text)} chars, {processing_time:.1f}s)"
            )

            return ResolutionResult(
                success=True,
                transcript=transcript,
                cost_usd=0.0,
                processing_time_seconds=processing_time,
            )

        except Exception as e:
            logger.warning(f"[YOUTUBE] Resolution failed for {video_id}: {type(e).__name__} - {e}")
            return ResolutionResult(
                success=False,
                error_message=f"YouTube transcript error: {type(e).__name__} - {str(e)}",
            )

    def estimate_cost(self, episode: PodcastEpisode) -> float:
        return 0.0

    def can_handle(self, episode: PodcastEpisode) -> bool:
        return self._get_video_id(episode) is not None

    def _get_video_id(self, episode: PodcastEpisode) -> Optional[str]:
        if episode.youtube_video_id:
            return episode.youtube_video_id
        if episode.website_url and 'youtube' in episode.website_url.lower():
            return self._extract_video_id(episode.website_url)
        return None

    def _extract_video_id(self, url: str) -> Optional[str]:
        patterns = [
            r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([^&\n?#]+)',
            r'youtube\.com/v/([^&\n?#]+)',
            r'youtube\.com/live/([^&\n?#]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def _clean_youtube_text(self, text: str) -> str:
        text = re.sub(r'\[(?:Music|Applause|Laughter|Inaudible)\]', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\[.*?\]', '', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
