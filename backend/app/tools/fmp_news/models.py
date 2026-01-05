"""FMP News Data Models

Data Type: premium_news (stored in BigQuery articles table)

Verified API Response Format (stable/news/stock):
{
    "symbol": "AAPL",
    "publishedDate": "2026-01-04 21:44:09",
    "publisher": "Benzinga",
    "title": "...",
    "image": "https://images.financialmodelingprep.com/news/...",
    "site": "feeds.benzinga.com",
    "text": "...",
    "url": "https://..."
}
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class FMPNewsArticle:
    """A news article from FMP Stock News API.
    
    Premium sources include: Benzinga, Seeking Alpha, Bloomberg, WSJ, etc.
    """
    
    # Core fields
    title: str
    url: str
    text: str  # Article content/summary
    
    # Source info
    symbol: str  # Stock ticker (e.g., "AAPL")
    publisher: str  # e.g., "Benzinga", "Seeking Alpha"
    site: str  # Domain (e.g., "feeds.benzinga.com")
    
    # Optional
    published_at: Optional[datetime] = None
    image_url: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "title": self.title,
            "url": self.url,
            "text": self.text,
            "symbol": self.symbol,
            "publisher": self.publisher,
            "site": self.site,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "image_url": self.image_url,
        }
