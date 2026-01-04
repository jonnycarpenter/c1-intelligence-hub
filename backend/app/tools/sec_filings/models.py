
from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime

class SECFiling(BaseModel):
    id: str  # Accession number
    company_id: str
    ticker: str
    cik: str
    company_name: str
    form_type: str
    filed_at: datetime
    period_of_report: Optional[datetime] = None
    fiscal_year: Optional[int] = None
    fiscal_quarter: Optional[int] = None
    filing_url: str
    sections: Optional[Dict[str, str]] = None
    full_text: Optional[str] = None
    collected_at: datetime
    classification: Optional[dict] = None
    key_insights: Optional[List[str]] = None

class FilingMetadata(BaseModel):
    accession_no: str
    cik: str
    ticker: str
    company_name: str
    form_type: str
    filed_at: datetime
    filing_url: str
