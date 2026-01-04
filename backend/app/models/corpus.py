"""
Corpus and Ingestion Data Models
================================

Pydantic models for corpus items, digests, and ingestion tracking.
These models are used both for API responses and SQLite storage.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum
import uuid


# ============================================================================
# Enums
# ============================================================================

class ContentCategory(str, Enum):
    """Categories for corpus content."""
    COMPETITOR = "Competitor"
    MARKET = "Market"
    REGULATORY = "Regulatory"
    PRODUCT = "Product"
    EARNINGS = "Earnings"
    PARTNERSHIP = "Partnership"
    EXPANSION = "Expansion"
    SUPPLY_CHAIN = "Supply Chain"
    LOGISTICS = "Logistics"
    C1_MENTION = "C1 Mention"
    GENERAL = "General"


class Priority(str, Enum):
    """Priority levels."""
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class Industry(str, Enum):
    """Industry verticals for composites classification."""
    AEROSPACE = "Aerospace"
    WIND = "Wind"
    CONSTRUCTION = "Construction"
    MARINE = "Marine"
    AUTOMOTIVE = "Automotive"
    INFRASTRUCTURE = "Infrastructure"
    TRANSPORTATION = "Transportation"
    SPORTING_GOODS = "Sporting Goods"
    DEFENSE_SPACE = "Defense Space"
    # Legacy values for backwards compatibility
    WIND_ENERGY = "Wind Energy"
    DEFENSE = "Defense"
    INDUSTRIAL = "Industrial"


# ============================================================================
# Source Models
# ============================================================================

class ContentSource(BaseModel):
    """Source information for corpus content."""
    name: str
    url: str
    source_type: str = "rss"  # rss_feed, web_news, sec_filing, press_release
    published_at: Optional[datetime] = None
    
    class Config:
        json_encoders = {datetime: lambda v: v.isoformat() if v else None}


# ============================================================================
# Entity Models
# ============================================================================

class EntityMention(BaseModel):
    """A tracked entity mentioned in content."""
    entity_id: str
    entity_name: str
    entity_type: str  # competitor, oem, material, supplier
    confidence: float = 1.0
    context: Optional[str] = None  # Surrounding text snippet


# ============================================================================
# Corpus Item (Main Content Model)
# ============================================================================

class CorpusItem(BaseModel):
    """
    A single piece of content in the intelligence corpus.
    
    This is the core data model for stored intelligence content.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    
    # Core content
    title: str
    summary: str
    full_text: Optional[str] = None
    url: str
    
    # Source info
    source: ContentSource
    
    # Classification
    categories: List[ContentCategory] = Field(default_factory=list)
    primary_category: ContentCategory = ContentCategory.GENERAL
    industries: List[Industry] = Field(default_factory=list)
    priority: Priority = Priority.LOW
    relevance_score: float = 0.5  # 0-1
    
    # Entities
    entity_mentions: List[EntityMention] = Field(default_factory=list)
    companies_mentioned: List[str] = Field(default_factory=list)
    materials_mentioned: List[str] = Field(default_factory=list)
    
    # Metadata
    sentiment: str = "neutral"  # positive, negative, neutral
    confidence: float = 0.7  # Classification confidence
    metadata: Dict[str, Any] = Field(default_factory=dict)  # Source-specific metadata
    
    # Timestamps
    published_at: datetime = Field(default_factory=datetime.utcnow)
    ingested_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Deduplication
    content_hash: Optional[str] = None
    
    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


# ============================================================================
# Digest Models
# ============================================================================

class DigestItem(BaseModel):
    """A single item in a digest summary."""
    corpus_item_id: str
    title: str
    headline: str = ""
    summary: str
    category: str
    priority: str
    source_name: str
    source_url: str
    published_at: datetime
    entity_mentions: List[str] = Field(default_factory=list)
    
    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class DigestStats(BaseModel):
    """Statistics for a digest."""
    total_items: int = 0
    by_category: Dict[str, int] = Field(default_factory=dict)
    by_priority: Dict[str, int] = Field(default_factory=dict)
    unique_entities: int = 0
    sources_count: int = 0


class Digest(BaseModel):
    """
    A pre-computed intelligence digest.
    
    Generated periodically (e.g., every 6 hours) to provide
    quick summaries without re-querying the corpus.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    
    # Time period
    period_start: datetime
    period_end: datetime
    hours_covered: int
    
    # Content
    executive_summary: str
    items: List[DigestItem] = Field(default_factory=list)
    stats: DigestStats = Field(default_factory=DigestStats)
    
    # Metadata
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


# ============================================================================
# Ingestion Tracking
# ============================================================================

class IngestionStats(BaseModel):
    """Statistics from an ingestion run."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    
    # Counts
    rss_articles_fetched: int = 0
    pr_articles_fetched: int = 0
    sec_filings_fetched: int = 0
    earnings_transcripts_fetched: int = 0
    web_articles_fetched: int = 0  # General web search (Exa industry queries + per-company)
    stocknews_articles_fetched: int = 0  # StockNewsAPI premium financial news
    articles_enriched: int = 0
    articles_classified: int = 0
    duplicates_skipped: int = 0
    articles_stored: int = 0
    images_extracted: int = 0  # Charts/graphs extracted from articles
    
    # Status
    status: str = "running"  # running, completed, failed
    errors: List[str] = Field(default_factory=list)
    
    @property
    def duration_seconds(self) -> float:
        if self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return 0.0
    
    @property
    def total_articles_fetched(self) -> int:
        """Total articles fetched from all sources."""
        return (
            self.rss_articles_fetched + 
            self.pr_articles_fetched + 
            self.sec_filings_fetched +
            self.web_articles_fetched +
            self.stocknews_articles_fetched
        )
    
    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


# ============================================================================
# Raw Article (Pre-processing)
# ============================================================================

class RawArticle(BaseModel):
    """Raw article data before classification."""
    title: str
    url: str
    summary: str
    full_text: Optional[str] = None
    published_at: Optional[datetime] = None
    source_name: str = ""
    source_type: str = "rss"
    raw_data: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        json_encoders = {datetime: lambda v: v.isoformat() if v else None}


# ============================================================================
# Classification Result
# ============================================================================

class ClassificationResult(BaseModel):
    """Result from content classification."""
    categories: List[ContentCategory] = Field(default_factory=list)
    primary_category: ContentCategory = ContentCategory.GENERAL
    industries: List[Industry] = Field(default_factory=list)
    priority: Priority = Priority.LOW
    relevance_score: float = 0.5
    headline: str = ""
    summary: str = ""
    key_entities: List[str] = Field(default_factory=list)  # Legacy - kept for backwards compat
    companies: List[str] = Field(default_factory=list)  # Extracted company names
    materials: List[str] = Field(default_factory=list)  # Extracted material names
    sentiment: str = "neutral"
    confidence: float = 0.7
