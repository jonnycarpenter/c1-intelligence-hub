"""
Podcast Ingestion Data Models
==============================

Pydantic models for podcast episodes, quotes, and transcripts.
Adapted for C1 Intelligence Hub (composites industry focus).
"""

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class QuoteTheme(str, Enum):
    """C1 Composites Industry quote theme taxonomy (16 themes)."""
    FIBER_MATERIALS = "fiber_materials"
    RESIN_SYSTEMS = "resin_systems"
    MANUFACTURING_PROCESSES = "manufacturing_processes"
    WIND_ENERGY = "wind_energy"
    AEROSPACE_COMPOSITES = "aerospace_composites"
    AUTOMOTIVE_COMPOSITES = "automotive_composites"
    INFRASTRUCTURE = "infrastructure"
    MARINE_COMPOSITES = "marine_composites"
    SUSTAINABILITY = "sustainability"
    REGULATORY = "regulatory"
    SUPPLY_CHAIN = "supply_chain"
    MARKET_DYNAMICS = "market_dynamics"
    INNOVATION = "innovation"
    WORKFORCE = "workforce"
    PRICING = "pricing"
    COMPETITIVE = "competitive"


class SpeakerRole(str, Enum):
    HOST = "host"
    GUEST = "guest"
    UNKNOWN = "unknown"


class TranscriptSource(str, Enum):
    """Where the transcript came from."""
    SITE_SCRAPE = "site_scrape"
    YOUTUBE_AUTO = "youtube_auto"
    YOUTUBE_MANUAL = "youtube_manual"
    ASSEMBLYAI = "assemblyai"


class ProcessingStatus(str, Enum):
    DISCOVERED = "discovered"
    TRANSCRIBED = "transcribed"
    EXTRACTED = "extracted"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Podcast Feed Config
# ---------------------------------------------------------------------------

class PodcastFeed(BaseModel):
    """Configuration for a podcast feed."""
    id: str
    name: str
    rss_url: Optional[str] = None
    website_url: Optional[str] = None
    description: Optional[str] = None
    publisher: Optional[str] = None
    has_site_transcripts: bool = False
    has_youtube_versions: bool = False
    default_hosts: List[str] = Field(default_factory=list)
    resolution_override: Optional[Dict[str, Any]] = None
    priority: str = "tier1"
    avg_duration_minutes: int = 45


# ---------------------------------------------------------------------------
# Episode (discovered from RSS)
# ---------------------------------------------------------------------------

class PodcastEpisode(BaseModel):
    """An episode discovered from RSS."""
    id: str
    podcast_id: str
    guid: str
    title: str
    description: Optional[str] = None
    audio_url: Optional[str] = None
    audio_duration_seconds: Optional[int] = None
    website_url: Optional[str] = None
    youtube_video_id: Optional[str] = None
    published_at: datetime
    guest_name: Optional[str] = None
    guest_title: Optional[str] = None
    guest_company: Optional[str] = None


# ---------------------------------------------------------------------------
# Transcript Result (internal, not stored directly)
# ---------------------------------------------------------------------------

class TranscriptResult(BaseModel):
    """Result of transcript resolution (internal use)."""
    full_text: str
    source: TranscriptSource
    has_speaker_labels: bool = False
    word_count: int = 0
    confidence: Optional[float] = None
    cost_usd: float = 0.0
    segments: List[Dict[str, Any]] = Field(default_factory=list)
    speaker_mapping: Dict[str, str] = Field(default_factory=dict)

    @property
    def formatted_text(self) -> str:
        """Get speaker-labeled text if segments exist, otherwise raw text."""
        if not self.has_speaker_labels or not self.segments:
            return self.full_text

        lines = []
        current_speaker = None
        for seg in self.segments:
            speaker = self.speaker_mapping.get(seg.get("speaker", ""), seg.get("speaker", "Unknown"))
            text = seg.get("text", "")
            if speaker == current_speaker and lines:
                lines[-1] = f"{lines[-1]} {text}"
            else:
                lines.append(f"{speaker}: {text}")
                current_speaker = speaker
        return "\n\n".join(lines)


# ---------------------------------------------------------------------------
# BigQuery Records
# ---------------------------------------------------------------------------

class PodcastEpisodeRecord(BaseModel):
    """Record for BigQuery podcast_episodes table."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    podcast_id: str
    podcast_name: str
    guid: str
    title: str
    description: Optional[str] = None
    audio_url: Optional[str] = None
    audio_duration_seconds: Optional[int] = None
    website_url: Optional[str] = None
    youtube_video_id: Optional[str] = None
    published_at: datetime
    transcript_text: Optional[str] = None
    transcript_source: Optional[str] = None
    transcript_has_speakers: bool = False
    transcript_word_count: int = 0
    transcript_cost_usd: float = 0.0
    guest_name: Optional[str] = None
    guest_title: Optional[str] = None
    guest_company: Optional[str] = None
    quotes_extracted: int = 0
    processing_status: str = ProcessingStatus.DISCOVERED.value
    error_message: Optional[str] = None
    ingested_at: datetime = Field(default_factory=datetime.utcnow)

    def to_bq_dict(self) -> Dict[str, Any]:
        """Convert to dict for BigQuery insert_rows_json."""
        d = self.model_dump()
        d["published_at"] = self.published_at.isoformat()
        d["ingested_at"] = self.ingested_at.isoformat()
        return d


class PodcastQuoteRecord(BaseModel):
    """Record for BigQuery podcast_quotes table."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    episode_id: str
    podcast_name: str
    episode_title: str
    episode_url: Optional[str] = None
    published_at: datetime
    quote_text: str
    context_summary: Optional[str] = None
    speaker_name: str
    speaker_role: str = SpeakerRole.UNKNOWN.value
    speaker_title: Optional[str] = None
    speaker_company: Optional[str] = None
    themes: List[str] = Field(default_factory=list)
    relevance_score: float = 0.5
    extraction_model: str = "claude-sonnet-4-5"
    extracted_at: datetime = Field(default_factory=datetime.utcnow)

    def to_bq_dict(self) -> Dict[str, Any]:
        """Convert to dict for BigQuery insert_rows_json."""
        import json
        d = self.model_dump()
        d["published_at"] = self.published_at.isoformat()
        d["extracted_at"] = self.extracted_at.isoformat()
        d["themes"] = json.dumps(d["themes"])  # Store as JSON string
        return d
