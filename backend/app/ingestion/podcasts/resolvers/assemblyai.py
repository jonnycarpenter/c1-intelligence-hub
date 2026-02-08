"""
AssemblyAI Transcript Resolver
==============================

Speech-to-text transcription with speaker diarization.
PAID - ~$0.37 per hour of audio.

Features:
- Speaker diarization (identifies different speakers)
- Auto-chapters (topic segmentation)
- Entity detection (names, companies, etc.)
- Retry logic with exponential backoff
- Extended HTTP timeouts for long episodes
"""

import time
import asyncio
from typing import Optional

import httpx

from app.utils.logger import get_logger
from app.config.settings import settings
from ..models import PodcastEpisode, TranscriptResult, TranscriptSource
from .base import TranscriptResolver, ResolutionResult

logger = get_logger(__name__)

HTTP_TIMEOUT = httpx.Timeout(connect=30.0, read=300.0, write=30.0, pool=30.0)
MAX_RETRIES = 3
INITIAL_BACKOFF_SECONDS = 5
MAX_BACKOFF_SECONDS = 60


class AssemblyAIResolver(TranscriptResolver):
    """
    Resolve transcripts using AssemblyAI.
    Paid fallback with speaker diarization (~$0.37/hr).
    """

    COST_PER_HOUR = 0.37
    DEFAULT_EPISODE_MINUTES = 45

    def __init__(self, api_key: Optional[str] = None, max_retries: int = MAX_RETRIES):
        self.api_key = api_key or settings.assemblyai_api_key
        self.max_retries = max_retries
        self._client_configured = False

    def _ensure_client(self):
        if not self._client_configured and self.api_key:
            try:
                import assemblyai as aai
                aai.settings.api_key = self.api_key
                aai.settings.http_timeout = HTTP_TIMEOUT
                self._client_configured = True
                logger.info("[ASSEMBLYAI] Client configured with extended timeouts")
            except ImportError:
                logger.error("[ASSEMBLYAI] assemblyai package not installed")

    @property
    def name(self) -> str:
        return "assemblyai"

    @property
    def is_paid(self) -> bool:
        return True

    async def resolve(self, episode: PodcastEpisode) -> ResolutionResult:
        start_time = time.time()

        if not self.api_key:
            return ResolutionResult(success=False, error_message="ASSEMBLYAI_API_KEY not configured")

        try:
            import assemblyai as aai
        except ImportError:
            return ResolutionResult(success=False, error_message="assemblyai package not installed")

        self._ensure_client()

        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                result = await self._attempt_transcription(episode, aai, attempt)
                if result.success:
                    return result
                if "error:" in (result.error_message or "").lower():
                    return result
                last_error = result.error_message
            except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.PoolTimeout) as e:
                last_error = f"HTTP timeout: {type(e).__name__}"
                logger.warning(
                    f"[ASSEMBLYAI] Attempt {attempt}/{self.max_retries} timed out: {e}"
                )
            except Exception as e:
                last_error = str(e)
                logger.warning(
                    f"[ASSEMBLYAI] Attempt {attempt}/{self.max_retries} failed: {e}"
                )

            if attempt < self.max_retries:
                backoff = min(INITIAL_BACKOFF_SECONDS * (2 ** (attempt - 1)), MAX_BACKOFF_SECONDS)
                logger.info(f"[ASSEMBLYAI] Waiting {backoff}s before retry...")
                await asyncio.sleep(backoff)

        processing_time = time.time() - start_time
        logger.error(
            f"[ASSEMBLYAI] All {self.max_retries} attempts failed for {episode.title[:50]}"
        )
        return ResolutionResult(
            success=False,
            error_message=f"All {self.max_retries} attempts failed. Last: {last_error}",
            processing_time_seconds=processing_time,
        )

    async def _attempt_transcription(self, episode: PodcastEpisode, aai, attempt: int) -> ResolutionResult:
        start_time = time.time()

        config = aai.TranscriptionConfig(
            speaker_labels=True,
            auto_chapters=True,
            entity_detection=True,
        )

        logger.info(
            f"[ASSEMBLYAI] Starting transcription attempt {attempt} for: {episode.title[:50]}..."
        )

        loop = asyncio.get_event_loop()
        transcript_result = await loop.run_in_executor(
            None,
            self._transcribe_sync,
            episode.audio_url,
            config,
        )

        if transcript_result.status == aai.TranscriptStatus.error:
            return ResolutionResult(
                success=False,
                error_message=f"AssemblyAI error: {transcript_result.error}",
            )

        duration_hours = (transcript_result.audio_duration or 0) / 3600
        cost = round(duration_hours * self.COST_PER_HOUR, 4)

        # Convert to our format
        segments = []
        if transcript_result.utterances:
            for utt in transcript_result.utterances:
                segments.append({
                    "speaker": f"Speaker {utt.speaker}",
                    "speaker_id": str(utt.speaker),
                    "start_ms": utt.start,
                    "end_ms": utt.end,
                    "text": utt.text,
                    "confidence": utt.confidence,
                })

        transcript = TranscriptResult(
            full_text=transcript_result.text or "",
            source=TranscriptSource.ASSEMBLYAI,
            has_speaker_labels=bool(segments),
            word_count=len((transcript_result.text or "").split()),
            confidence=transcript_result.confidence,
            cost_usd=cost,
            segments=segments,
        )

        processing_time = time.time() - start_time
        logger.info(
            f"[ASSEMBLYAI] Completed in {processing_time:.1f}s, "
            f"cost=${cost:.4f}, {len(segments)} speaker segments"
        )

        return ResolutionResult(
            success=True,
            transcript=transcript,
            cost_usd=cost,
            processing_time_seconds=processing_time,
        )

    def _transcribe_sync(self, audio_url: str, config):
        import assemblyai as aai
        transcriber = aai.Transcriber()
        return transcriber.transcribe(audio_url, config=config)

    def estimate_cost(self, episode: PodcastEpisode) -> float:
        if episode.audio_duration_seconds:
            return round((episode.audio_duration_seconds / 3600) * self.COST_PER_HOUR, 4)
        return round((self.DEFAULT_EPISODE_MINUTES / 60) * self.COST_PER_HOUR, 4)

    def can_handle(self, episode: PodcastEpisode) -> bool:
        return episode.audio_url is not None and bool(self.api_key)
