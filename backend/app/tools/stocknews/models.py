"""
StockNewsAPI Data Models
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any


@dataclass
class StockNewsArticle:
    """A news article from StockNewsAPI."""
    
    # Core identifiers
    news_id: str  # StockNewsAPI internal ID for dedup
    
    # Content
    title: str
    text: str  # Article body/snippet
    
    # Source info
    source_name: str
    url: str
    image_url: Optional[str] = None
    
    # Publication date (parsed from RFC 2822 format)
    published_at: Optional[datetime] = None
    
    # Metadata
    tickers: List[str] = field(default_factory=list)
    sentiment: str = "neutral"  # Positive/Negative/Neutral
    article_type: str = "article"  # article or video
    rank_score: Optional[int] = None  # Importance ranking (0-100)
    
    # Search context (for keyword searches)
    search_query: Optional[str] = None
    search_type: str = "ticker"  # ticker or keyword
    
    # Raw API response for debugging
    raw_data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "news_id": self.news_id,
            "title": self.title,
            "text": self.text,
            "source_name": self.source_name,
            "url": self.url,
            "image_url": self.image_url,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "tickers": self.tickers,
            "sentiment": self.sentiment,
            "article_type": self.article_type,
            "rank_score": self.rank_score,
            "search_query": self.search_query,
            "search_type": self.search_type,
        }


# Source tier classification for premium source selection
PREMIUM_SOURCES = [
    "bloomberg", "reuters", "wsj", "wall street journal", 
    "cnbc", "financial times", "barron's", "barrons"
]

STANDARD_SOURCES = [
    "motley fool", "seeking alpha", "zacks", "benzinga", 
    "fox business", "the street", "yahoo finance", "marketwatch"
]


def get_source_tier(source_name: str) -> str:
    """
    Classify source into tiers for quality weighting.
    
    Returns:
        "premium", "standard", or "aggregator"
    """
    source_lower = source_name.lower()
    
    if any(p in source_lower for p in PREMIUM_SOURCES):
        return "premium"
    elif any(s in source_lower for s in STANDARD_SOURCES):
        return "standard"
    return "aggregator"


def get_source_priority(source_name: str) -> int:
    """
    Get numeric priority for source ranking (lower = better).
    Used when selecting "best" source from duplicates.
    """
    tier = get_source_tier(source_name)
    if tier == "premium":
        return 1
    elif tier == "standard":
        return 2
    return 3
