
from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime

class PressRelease(BaseModel):
    id: str
    company_id: str
    company_name: str
    ticker: Optional[str]
    title: str
    url: str
    source: str
    published_date: Optional[datetime]
    full_text: str
    discovered_at: datetime
    word_count: int
    classification: Optional[dict] = None
    relevance_score: Optional[float] = None

class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str
    score: float
    published_date: Optional[str] = None
