"""Walkthrough API - Generate platform walkthrough audio using ElevenLabs."""

import uuid
import time
import asyncio
import hashlib
from typing import Optional
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.config.settings import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()

# ElevenLabs API configuration
ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1"

# Narrator voice - professional, warm, clear
# Rachel: calm & professional (default host voice)
NARRATOR_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"


# =============================================================================
# Walkthrough Script - Tab-by-tab platform tour
# =============================================================================

WALKTHROUGH_SCRIPT = [
    {
        "section": "intro",
        "text": (
            "Welcome to the Composites Industry Intelligence Hub. "
            "This is a two-minute walkthrough of the platform, covering each tab "
            "and the data powering it. Let's dive in."
        ),
    },
    {
        "section": "the_brief",
        "text": (
            "The Brief is your weekly executive overview. Every Monday, two AI agents "
            "analyze hundreds of articles from the past fourteen days. The first agent "
            "identifies key themes and signals. The second synthesizes them into a "
            "structured briefing with a Bottom Line Up Front, strategic priority themes, "
            "and source citations. You can also hit play on the podcast for an audio "
            "version. This tab pulls from the weekly briefings table in BigQuery, "
            "which stores the AI-generated output, and links back to the original "
            "articles and digest items collected by the ingestion pipeline."
        ),
    },
    {
        "section": "discovery",
        "text": (
            "Discovery is your open-ended research interface. It shows all ingested "
            "articles from the past thirty days, grouped by category: market moves, "
            "supply chain, regulatory, competitor activity, and more. You can filter, "
            "search, and ask the AI assistant anything. It searches across all digest "
            "items, articles, and embeddings stored in BigQuery to surface the "
            "information you need."
        ),
    },
    {
        "section": "deep_research",
        "text": (
            "Deep Research lets you launch a comprehensive analysis on any topic. "
            "When you enter a query, a multi-agent workflow kicks off. A groomer agent "
            "refines your question, then parallel research agents search your internal "
            "corpus, financial data via Exa, and the broader web simultaneously. "
            "A synthesizer agent combines everything into a structured report with "
            "citations. The whole process takes about sixty to ninety seconds, and "
            "reports are saved to BigQuery for future reference."
        ),
    },
    {
        "section": "core_industries",
        "text": (
            "Core Industries gives you a ninety-day narrative timeline for each "
            "end-market: aerospace, automotive, wind energy, construction, marine, "
            "and others. The AI generates a storyline from article volume, sentiment "
            "shifts, and key events across each month. This tab pulls from "
            "digest items and article tags in BigQuery, grouped by industry."
        ),
    },
    {
        "section": "supply_network",
        "text": (
            "Supply Network visualizes supplier and customer relationships across "
            "the composites industry as an interactive graph. You can drill into "
            "any company to see shipment data, intelligence snippets, and "
            "network connections. This tab pulls from US Customs import records "
            "via ImportYeti and enriches them with company metadata."
        ),
    },
    {
        "section": "architecture_evals",
        "text": (
            "Under How It Works, the Architecture tab shows how the entire platform "
            "is built, from ingestion pipeline to agent workflows. You can click any "
            "node to view the actual prompts powering each AI agent. The AI Quality "
            "tab tracks evaluation metrics, token costs, and user feedback across "
            "all AI-generated content. These pull from the eval results and token "
            "usage tables in BigQuery."
        ),
    },
    {
        "section": "tracked_entities",
        "text": (
            "Finally, Tracked Entities lets you manage the companies, industries, "
            "and topics the platform monitors. This is the data layer that feeds "
            "the entire ingestion pipeline, controlling what the system watches for."
        ),
    },
    {
        "section": "closing",
        "text": (
            "That's your walkthrough of the Intelligence Hub. "
            "Every tab is powered by AI agents running on top of BigQuery, "
            "with data refreshed daily through automated pipelines. "
            "Click the Guide button in the header anytime to ask questions. Enjoy exploring."
        ),
    },
]


def get_full_script_text() -> str:
    """Get the complete walkthrough script as a single string."""
    return " ".join(section["text"] for section in WALKTHROUGH_SCRIPT)


def get_script_hash() -> str:
    """Get a hash of the script to use as a cache key."""
    full_text = get_full_script_text()
    return hashlib.md5(full_text.encode()).hexdigest()[:12]


# =============================================================================
# Audio cache (GCS for production, local for dev)
# =============================================================================

_audio_cache_dir = Path(settings.base_dir) / "audio_cache" / "walkthrough"
_audio_cache_dir.mkdir(parents=True, exist_ok=True)


def _get_cached_audio_path() -> Optional[Path]:
    """Check if a cached walkthrough audio file exists."""
    script_hash = get_script_hash()
    cached_path = _audio_cache_dir / f"walkthrough_{script_hash}.mp3"
    if cached_path.exists():
        return cached_path
    return None


def _save_audio_cache(audio_data: bytes) -> Path:
    """Save generated audio to cache."""
    script_hash = get_script_hash()
    cached_path = _audio_cache_dir / f"walkthrough_{script_hash}.mp3"
    with open(cached_path, "wb") as f:
        f.write(audio_data)
    logger.info(f"[WALKTHROUGH] Cached audio: {cached_path} ({len(audio_data)} bytes)")
    return cached_path


# =============================================================================
# ElevenLabs TTS generation
# =============================================================================

async def _generate_section_audio(
    client: httpx.AsyncClient,
    text: str,
    api_key: str,
    voice_id: str = NARRATOR_VOICE_ID,
) -> bytes:
    """Generate audio for a single script section using ElevenLabs."""
    url = f"{ELEVENLABS_API_URL}/text-to-speech/{voice_id}"

    response = await client.post(
        url,
        headers={
            "xi-api-key": api_key,
            "Content-Type": "application/json",
        },
        json={
            "text": text,
            "model_id": settings.elevenlabs_model,
            "voice_settings": {
                "stability": 0.6,  # Slightly more stable for narration
                "similarity_boost": 0.75,
            },
        },
        timeout=60.0,
    )

    response.raise_for_status()
    return response.content


async def generate_walkthrough_audio() -> bytes:
    """
    Generate the full walkthrough audio by synthesizing each section
    and concatenating the results.

    Returns:
        MP3 audio bytes
    """
    api_key = settings.elevenlabs_api_key
    if not api_key:
        raise ValueError("ELEVENLABS_API_KEY not configured")

    start_time = time.time()
    logger.info(f"[WALKTHROUGH] Generating audio for {len(WALKTHROUGH_SCRIPT)} sections")

    audio_segments: list[bytes] = []

    async with httpx.AsyncClient() as client:
        for i, section in enumerate(WALKTHROUGH_SCRIPT):
            section_start = time.time()
            logger.info(f"[WALKTHROUGH] Generating section {i+1}/{len(WALKTHROUGH_SCRIPT)}: {section['section']}")

            audio_data = await _generate_section_audio(
                client=client,
                text=section["text"],
                api_key=api_key,
            )
            audio_segments.append(audio_data)

            elapsed = time.time() - section_start
            logger.info(f"[WALKTHROUGH] Section '{section['section']}' COMPLETE: {elapsed:.1f}s, {len(audio_data)} bytes")

            # Small delay to avoid rate limits
            if i < len(WALKTHROUGH_SCRIPT) - 1:
                await asyncio.sleep(0.3)

    # Concatenate all audio segments
    combined = b"".join(audio_segments)
    total_elapsed = time.time() - start_time
    logger.info(f"[WALKTHROUGH] Audio generation COMPLETE: {total_elapsed:.1f}s, {len(combined)} bytes total")

    return combined


# =============================================================================
# GCS storage helpers
# =============================================================================

async def _upload_to_gcs(audio_data: bytes) -> Optional[str]:
    """Upload walkthrough audio to GCS. Returns the blob path or None."""
    try:
        from google.cloud import storage as gcs

        client = gcs.Client(project=settings.gcp_project_id)
        bucket = client.bucket(settings.gcs_bucket_name)
        script_hash = get_script_hash()
        blob_path = f"walkthrough/walkthrough_{script_hash}.mp3"
        blob = bucket.blob(blob_path)

        blob.upload_from_string(audio_data, content_type="audio/mpeg")
        logger.info(f"[WALKTHROUGH] Uploaded to GCS: {blob_path}")
        return blob_path
    except Exception as e:
        logger.warning(f"[WALKTHROUGH] GCS upload failed (will use local cache): {e}")
        return None


async def _get_gcs_audio(script_hash: str) -> Optional[bytes]:
    """Try to fetch walkthrough audio from GCS."""
    try:
        from google.cloud import storage as gcs

        client = gcs.Client(project=settings.gcp_project_id)
        bucket = client.bucket(settings.gcs_bucket_name)
        blob_path = f"walkthrough/walkthrough_{script_hash}.mp3"
        blob = bucket.blob(blob_path)

        if blob.exists():
            logger.info(f"[WALKTHROUGH] Found in GCS: {blob_path}")
            return blob.download_as_bytes()
    except Exception as e:
        logger.debug(f"[WALKTHROUGH] GCS fetch failed: {e}")
    return None


# =============================================================================
# API Endpoints
# =============================================================================

class WalkthroughScriptResponse(BaseModel):
    """Response with the walkthrough script text."""
    sections: list[dict]
    total_word_count: int
    estimated_duration_seconds: int


class WalkthroughStatusResponse(BaseModel):
    """Response with walkthrough audio availability."""
    available: bool
    audio_url: Optional[str] = None
    estimated_duration_seconds: int = 120
    script_hash: str


@router.get("/script")
async def get_walkthrough_script() -> WalkthroughScriptResponse:
    """Get the walkthrough script text (for display or regeneration)."""
    full_text = get_full_script_text()
    word_count = len(full_text.split())
    estimated_duration = int((word_count / 150) * 60)  # ~150 words/min

    return WalkthroughScriptResponse(
        sections=WALKTHROUGH_SCRIPT,
        total_word_count=word_count,
        estimated_duration_seconds=estimated_duration,
    )


@router.get("/status")
async def get_walkthrough_status() -> WalkthroughStatusResponse:
    """Check if walkthrough audio is available (cached)."""
    script_hash = get_script_hash()

    # Check local cache
    cached = _get_cached_audio_path()
    if cached:
        return WalkthroughStatusResponse(
            available=True,
            audio_url=f"/api/walkthrough/audio/{script_hash}",
            script_hash=script_hash,
        )

    # Check GCS
    gcs_audio = await _get_gcs_audio(script_hash)
    if gcs_audio:
        # Cache locally too
        _save_audio_cache(gcs_audio)
        return WalkthroughStatusResponse(
            available=True,
            audio_url=f"/api/walkthrough/audio/{script_hash}",
            script_hash=script_hash,
        )

    # Not available yet
    full_text = get_full_script_text()
    word_count = len(full_text.split())
    estimated_duration = int((word_count / 150) * 60)

    return WalkthroughStatusResponse(
        available=False,
        script_hash=script_hash,
        estimated_duration_seconds=estimated_duration,
    )


@router.post("/generate")
async def generate_walkthrough():
    """
    Generate the walkthrough audio using ElevenLabs.

    This endpoint generates audio for the full platform walkthrough script.
    The result is cached locally and in GCS so subsequent requests are instant.
    """
    if not settings.elevenlabs_api_key:
        raise HTTPException(
            status_code=503,
            detail="ElevenLabs API key not configured. Walkthrough audio generation is unavailable.",
        )

    # Check if already cached
    cached = _get_cached_audio_path()
    if cached:
        script_hash = get_script_hash()
        return {
            "status": "ready",
            "audio_url": f"/api/walkthrough/audio/{script_hash}",
            "message": "Walkthrough audio already generated.",
        }

    try:
        audio_data = await generate_walkthrough_audio()

        # Save locally
        _save_audio_cache(audio_data)

        # Upload to GCS (fire and forget, non-blocking)
        try:
            await _upload_to_gcs(audio_data)
        except Exception:
            pass

        script_hash = get_script_hash()
        return {
            "status": "ready",
            "audio_url": f"/api/walkthrough/audio/{script_hash}",
            "message": f"Walkthrough audio generated successfully ({len(audio_data)} bytes).",
        }

    except Exception as e:
        logger.error(f"[WALKTHROUGH] Generation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate walkthrough audio: {str(e)}",
        )


@router.get("/audio/{audio_id}")
async def stream_walkthrough_audio(audio_id: str, request: Request):
    """
    Stream the walkthrough audio file.

    Supports Range requests for proper seeking in browsers.
    First checks local cache, then GCS.
    """
    logger.info(f"[WALKTHROUGH] Audio stream request: {audio_id}")

    # Try local cache first
    cached_path = _audio_cache_dir / f"walkthrough_{audio_id}.mp3"
    if not cached_path.exists():
        # Try GCS
        gcs_audio = await _get_gcs_audio(audio_id)
        if gcs_audio:
            _save_audio_cache(gcs_audio)
        else:
            raise HTTPException(status_code=404, detail="Walkthrough audio not found. Generate it first via POST /api/walkthrough/generate")

    # Read file
    audio_data = cached_path.read_bytes()
    file_size = len(audio_data)

    # Parse Range header for seeking support
    range_header = request.headers.get("range")
    start = 0
    end = file_size - 1

    if range_header:
        range_spec = range_header.replace("bytes=", "")
        if "-" in range_spec:
            parts = range_spec.split("-")
            if parts[0]:
                start = int(parts[0])
            if parts[1]:
                end = int(parts[1])

    if start >= file_size:
        raise HTTPException(status_code=416, detail="Range not satisfiable")
    end = min(end, file_size - 1)
    content_length = end - start + 1

    def generate():
        yield audio_data[start:end + 1]

    headers = {
        "Content-Disposition": 'inline; filename="walkthrough.mp3"',
        "Accept-Ranges": "bytes",
        "Content-Length": str(content_length),
        "Content-Range": f"bytes {start}-{end}/{file_size}",
    }

    status_code = 206 if range_header else 200

    return StreamingResponse(
        generate(),
        status_code=status_code,
        media_type="audio/mpeg",
        headers=headers,
    )
