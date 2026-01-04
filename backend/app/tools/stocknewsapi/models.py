"""Data models for StockNewsAPI responses."""

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class StockNewsArticle(BaseModel):
    """Represents an article from StockNewsAPI."""
    
    # Core identifiers
    news_id: str  # Unique identifier for deduplication
    
    # Content
    title: str
    text: str  # Article body/snippet
    
    # Source info
    source_name: str  # Publisher (CNBC, Reuters, etc.)
    news_url: str  # Link to original article
    image_url: Optional[str] = None
    
    # Publication info
    published_at: Optional[datetime] = None  # Parsed from RFC 2822 date
    
    # Metadata
    tickers: List[str] = []  # Associated stock symbols
    sentiment: Optional[str] = None  # Positive/Negative/Neutral
    article_type: str = "article"  # article or video
    rank_score: Optional[int] = None  # Importance ranking (0-100)
    
    # Classification helpers
    source_tier: str = "standard"  # premium, standard, aggregator
    
    class Config:
        json_encoders = {datetime: lambda v: v.isoformat() if v else None}


class StockNewsSearchResult(BaseModel):
    """Container for search results."""
    
    articles: List[StockNewsArticle] = []
    total_results: int = 0
    query_type: str = "ticker"  # ticker, keyword, press_release
    query: str = ""
