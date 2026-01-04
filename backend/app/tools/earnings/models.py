
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime


class TranscriptSection(BaseModel):
    """A single speaker section from the earnings call transcript."""
    speaker: str
    role: Optional[str] = None
    company: Optional[str] = None
    text: str


class Participant(BaseModel):
    """Participant in an earnings call (executive, analyst, operator)."""
    name: str
    role: Optional[str] = None
    company: Optional[str] = None


class EarningsTranscript(BaseModel):
    id: str  # Composite key usually: ticker_quarter_year
    ticker: str
    company_name: str
    quarter: int
    year: int
    date: datetime
    content: str  # Full transcript text
    
    # Structured participant data (richer than flat strings)
    participants: Optional[List[Participant]] = None
    
    # Speaker-attributed transcript sections (who said what)
    transcript_split: Optional[List[TranscriptSection]] = None
    
    # Timing metadata
    earnings_timing: Optional[str] = None  # "before_market", "after_market"
    cik: Optional[str] = None  # SEC CIK identifier for cross-referencing
    timestamp: Optional[int] = None  # Unix timestamp of the call
    
    # Legacy/computed fields
    sentiment: Optional[Dict] = None
    url: Optional[str] = None
    collected_at: datetime
    
class EarningsEvent(BaseModel):
    ticker: str
    date: datetime
    quarter: Optional[int]
    year: Optional[int]
    estimated_eps: Optional[float]
    actual_eps: Optional[float]
    revenue_estimate: Optional[float]
    revenue_actual: Optional[float]
