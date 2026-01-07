"""Podcast API endpoints - Generate AI podcasts from intelligence content."""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse

from app.api.schemas import (
    PodcastRequest,
    PodcastScriptResponse,
    PodcastAudioRequest,
    PodcastAudioResponse,
    PodcastStyle,
)
from app.services.podcast_service import PodcastService
from app.config.settings import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()

# Initialize podcast service
podcast_service = PodcastService()


@router.post("/script", response_model=PodcastScriptResponse)
async def generate_podcast_script(request: PodcastRequest) -> PodcastScriptResponse:
    """
    Generate a podcast script from content.
    
    Takes intelligence content and creates a conversational script
    suitable for audio generation. The script includes multiple speakers
    and natural transitions.
    
    Styles:
    - conversational: Natural back-and-forth between host and analyst
    - professional: More formal presentation style
    - brief: Quick summary format, single speaker
    """
    logger.info(f"Podcast script request: style={request.style}, content_length={len(request.content)}")
    
    if not request.content or len(request.content.strip()) < 50:
        raise HTTPException(
            status_code=400,
            detail="Content must be at least 50 characters for podcast generation"
        )
    
    try:
        response = await podcast_service.generate_script(
            content=request.content,
            title=request.title,
            style=request.style,
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error generating podcast script: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate podcast script")


@router.post("/audio", response_model=PodcastAudioResponse)
async def generate_podcast_audio(request: PodcastAudioRequest) -> PodcastAudioResponse:
    """
    Generate audio from a podcast script.
    
    Uses ElevenLabs to synthesize natural-sounding speech from the script.
    Each speaker is assigned a unique voice for natural conversation flow.
    
    Note: Requires ELEVENLABS_API_KEY to be configured. Without it,
    returns a mock response with a placeholder audio URL.
    """
    logger.info(f"Podcast audio request: {len(request.script.segments)} segments")
    
    if not request.script.segments:
        raise HTTPException(
            status_code=400,
            detail="Script must have at least one segment"
        )
    
    try:
        response = await podcast_service.generate_audio(script=request.script)
        return response
        
    except Exception as e:
        logger.error(f"Error generating podcast audio: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate podcast audio")


@router.get("/audio/{audio_id}")
async def get_podcast_audio(audio_id: str):
    """
    Retrieve a generated podcast audio file.
    
    Returns the MP3 file for the specified audio ID.
    Audio files are cached temporarily after generation.
    """
    logger.info(f"Podcast audio retrieval request: audio_id={audio_id}")
    
    # Handle mock demo audio
    if audio_id == "mock_demo":
        raise HTTPException(
            status_code=404,
            detail="Demo audio - ElevenLabs API key required for actual audio generation"
        )
    
    # Get audio file path
    audio_path = podcast_service.get_audio_file_path(audio_id)
    
    if not audio_path:
        raise HTTPException(status_code=404, detail="Audio file not found")
    
    return FileResponse(
        path=str(audio_path),
        media_type="audio/mpeg",
        filename=f"podcast_{audio_id}.mp3",
    )


@router.get("/voices")
async def list_available_voices():
    """
    List available voices for podcast generation.
    
    Returns the default voices used for host and analyst roles.
    In future versions, users may be able to select custom voices.
    """
    return {
        "voices": [
            {
                "role": "host",
                "name": "Rachel",
                "description": "Calm, professional voice suitable for hosting",
            },
            {
                "role": "analyst",
                "name": "Josh",
                "description": "Conversational voice for analyst commentary",
            },
        ],
        "note": "Voice customization coming in future updates",
    }


@router.get("/briefing/{briefing_id}")
async def get_briefing_podcast(briefing_id: str, request: Request):
    """
    Stream podcast audio for a weekly briefing from GCS.
    
    This endpoint proxies the audio file from GCS to work around
    bucket public access prevention. Supports Range requests for
    proper audio seeking in browsers.
    """
    logger.info(f"Streaming briefing podcast: {briefing_id}")
    
    try:
        from google.cloud import storage
        
        client = storage.Client(project=settings.gcp_project_id)
        bucket = client.bucket(settings.gcs_bucket_name)
        blob = bucket.blob(f"podcasts/{briefing_id}.mp3")
        
        if not blob.exists():
            raise HTTPException(status_code=404, detail="Podcast not found for this briefing")
        
        # Get file size
        blob.reload()
        file_size = blob.size
        
        # Parse Range header
        range_header = request.headers.get("range")
        start = 0
        end = file_size - 1
        
        if range_header:
            # Parse "bytes=start-end" format
            range_spec = range_header.replace("bytes=", "")
            if "-" in range_spec:
                parts = range_spec.split("-")
                if parts[0]:
                    start = int(parts[0])
                if parts[1]:
                    end = int(parts[1])
        
        # Ensure valid range
        if start >= file_size:
            raise HTTPException(status_code=416, detail="Range not satisfiable")
        end = min(end, file_size - 1)
        content_length = end - start + 1
        
        # Stream the requested range from GCS
        def generate():
            with blob.open("rb") as f:
                f.seek(start)
                remaining = content_length
                while remaining > 0:
                    chunk_size = min(8192, remaining)
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk
        
        headers = {
            "Content-Disposition": f'inline; filename="briefing_{briefing_id}.mp3"',
            "Accept-Ranges": "bytes",
            "Content-Length": str(content_length),
            "Content-Range": f"bytes {start}-{end}/{file_size}",
        }
        
        # Return 206 Partial Content for Range requests, 200 otherwise
        status_code = 206 if range_header else 200
        
        return StreamingResponse(
            generate(),
            status_code=status_code,
            media_type="audio/mpeg",
            headers=headers,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error streaming podcast: {e}")
        raise HTTPException(status_code=500, detail="Failed to stream podcast audio")
