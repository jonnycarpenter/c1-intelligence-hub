"""API request/response schemas for the new architecture."""

from datetime import datetime
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field
from enum import Enum


# ============================================
# Enums
# ============================================

class WorkflowMode(str, Enum):
    """Workflow modes (replaces tabs/agents)."""
    PULSE = "pulse"
    RESEARCH = "research"
    PRODUCTS = "products"
    COMPANIES = "companies"
    INDUSTRIES = "industries"
    DATA_PREFERENCES = "data-preferences"


class Priority(str, Enum):
    """Priority levels for digest items."""
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class DigestCategory(str, Enum):
    """Categories for digest items - aligned with ContentCategory from corpus."""
    MARKET = "Market"
    SUPPLY_CHAIN = "Supply Chain"
    REGULATORY = "Regulatory"
    COMPETITOR = "Competitor"
    PRODUCT = "Product"
    EARNINGS = "Earnings"
    PARTNERSHIP = "Partnership"
    EXPANSION = "Expansion"
    C1_MENTION = "C1 Mention"
    LOGISTICS = "Logistics"
    GENERAL = "General"
    # Legacy categories for backward compatibility
    PRICING = "Pricing"
    PRIORITY = "Priority"


class ExportFormat(str, Enum):
    """Report export formats."""
    PDF = "pdf"
    DOCX = "docx"
    PPTX = "pptx"


class PodcastStyle(str, Enum):
    """Podcast generation styles."""
    CONVERSATIONAL = "conversational"
    PROFESSIONAL = "professional"
    BRIEF = "brief"


class ThinkingEventType(str, Enum):
    """Types of agent thinking/tracing events."""
    THINKING_START = "thinking_start"
    THINKING_TOKEN = "thinking_token"
    THINKING_END = "thinking_end"
    TOOL_START = "tool_start"
    TOOL_END = "tool_end"
    TOOL_ERROR = "tool_error"
    STEP_START = "step_start"
    AGENT_ACTION = "agent_action"
    AGENT_FINISH = "agent_finish"
    STATUS = "status"
    ROUTING = "routing"
    CONTENT = "content"
    ERROR = "error"
    COMPLETE = "complete"


# ============================================
# Chat Schemas
# ============================================

class ChatContext(BaseModel):
    """Optional context for chat requests."""
    companies: Optional[List[str]] = None
    materials: Optional[List[str]] = None
    timeframe: Optional[str] = None


class ChatRequest(BaseModel):
    """Chat request model (new architecture)."""
    message: str
    mode: WorkflowMode
    conversation_id: Optional[str] = None
    context: Optional[ChatContext] = None


class Source(BaseModel):
    """Source reference for responses."""
    title: str
    url: str
    published_at: Optional[str] = None
    domain: Optional[str] = None


class MessageMetadata(BaseModel):
    """Metadata for chat messages."""
    tools_used: Optional[List[str]] = None
    tokens_used: Optional[int] = None
    duration: Optional[float] = None


class ThinkingEvent(BaseModel):
    """Agent thinking/tracing event for live feed."""
    type: ThinkingEventType
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: Optional[Dict[str, Any]] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ChatMessage(BaseModel):
    """Chat message model."""
    id: str
    role: Literal["user", "assistant"]
    content: str
    timestamp: datetime
    sources: Optional[List[Source]] = None
    is_streaming: Optional[bool] = False
    is_error: Optional[bool] = False
    metadata: Optional[MessageMetadata] = None


class ChatResponse(BaseModel):
    """Chat response model."""
    message: ChatMessage
    conversation_id: str


# ============================================
# Digest Schemas
# ============================================

class DigestRequest(BaseModel):
    """Digest filter request."""
    hours: Optional[int] = 72  # Default to last 72 hours
    categories: Optional[List[DigestCategory]] = None
    priorities: Optional[List[Priority]] = None


class DigestEntities(BaseModel):
    """Entities extracted from digest item."""
    companies: Optional[List[str]] = None
    materials: Optional[List[str]] = None
    topics: Optional[List[str]] = None
    industries: Optional[List[str]] = None


class DigestItem(BaseModel):
    """Individual digest item."""
    id: str
    title: str
    headline: Optional[str] = None
    summary: str
    category: DigestCategory
    priority: Priority
    sources: List[Source]  # All sources that covered this story
    entities: DigestEntities
    published_at: datetime
    ingested_at: datetime
    coverage_count: int = 1  # How many sources covered this story (virality indicator)


class DigestStats(BaseModel):
    """Statistics for the digest."""
    total_items: int
    by_category: Dict[str, int]
    by_priority: Dict[str, int]


class Digest(BaseModel):
    """Full digest response."""
    id: str
    generated_at: datetime
    period_start: datetime
    period_end: datetime
    stats: DigestStats
    items: List[DigestItem]
    summary: Optional[str] = None


# ============================================
# Podcast Schemas
# ============================================

class PodcastRequest(BaseModel):
    """Podcast generation request."""
    content: str
    title: Optional[str] = None
    style: PodcastStyle = PodcastStyle.CONVERSATIONAL


class PodcastSpeaker(BaseModel):
    """Podcast speaker definition."""
    name: str
    voice_id: str


class PodcastSegment(BaseModel):
    """Podcast script segment."""
    speaker: str
    text: str


class PodcastScript(BaseModel):
    """Full podcast script."""
    speakers: List[PodcastSpeaker]
    segments: List[PodcastSegment]


class PodcastScriptResponse(BaseModel):
    """Response from script generation."""
    script: PodcastScript
    estimated_duration: int  # seconds


class PodcastAudioRequest(BaseModel):
    """Request to generate audio from script."""
    script: PodcastScript


class PodcastAudioResponse(BaseModel):
    """Response with generated audio."""
    audio_url: str
    duration: int  # seconds


# ============================================
# Report Export Schemas
# ============================================

class ReportExportItem(BaseModel):
    """Item to include in report export."""
    content: str
    source: str
    title: Optional[str] = None


class ReportExportRequest(BaseModel):
    """Report export request."""
    format: ExportFormat
    items: List[ReportExportItem]
    title: Optional[str] = "Intelligence Report"


# ============================================
# Legacy Compatibility (for transition)
# ============================================

class LegacyChatRequest(BaseModel):
    """Legacy chat request (for backwards compatibility)."""
    message: str
    tab: str  # market, financial, product, hub
    session_id: Optional[str] = None
    
    def to_new_format(self) -> ChatRequest:
        """Convert to new format."""
        tab_to_mode = {
            "market": WorkflowMode.PULSE,
            "financial": WorkflowMode.RESEARCH,
            "product": WorkflowMode.PRODUCTS,
            "hub": WorkflowMode.PULSE,  # Default hub queries to pulse
        }
        return ChatRequest(
            message=self.message,
            mode=tab_to_mode.get(self.tab, WorkflowMode.PULSE),
            conversation_id=self.session_id,
        )
