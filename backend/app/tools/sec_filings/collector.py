
import logging
from datetime import datetime
from typing import List, Set
from app.config.settings import settings
from .sec_client import SECClient
from .extractor import SectionExtractor
from .models import SECFiling

logger = logging.getLogger(__name__)

class SECFilingCollector:
    def __init__(self, sec_client: SECClient = None, existing_ids: Set[str] = None):
        self.client = sec_client or SECClient()
        self.extractor = SectionExtractor(self.client)
        self.existing_ids = existing_ids or set()
    
    def collect_for_company(self, company_id: str, ticker: str, since: datetime = None) -> List[SECFiling]:
        if not ticker:
            return []
            
        # Default to standard forms if not configured
        form_types = getattr(settings, 'sec_filing_types', None) or ["10-K", "10-Q", "8-K"]
            
        try:
            metadatas = self.client.query_filings(
                ticker=ticker,
                form_types=form_types,
                filed_after=since,
                size=5
            )
        except Exception as e:
            logger.error(f"SEC Query failed for {ticker}: {e}")
            return []
        
        filings = []
        for meta in metadatas:
            if meta.accession_no in self.existing_ids:
                continue
                
            sections = None
            full_text = None
            
            # Logic: Extract sections for 10-K/Q, full text for 8-K
            if meta.form_type in ["10-K", "10-Q"]:
                try:
                    sections = self.extractor.extract_all_sections(meta.filing_url)
                except Exception as e:
                    logger.error(f"Extraction failed for {ticker} {meta.form_type}: {e}")
            elif meta.form_type == "8-K":
                full_text = self.client.download_filing(meta.filing_url)
            
            # Skip if nothing useful retrieved
            if not sections and not full_text:
                continue
                
            filing = SECFiling(
                id=meta.accession_no,
                company_id=company_id,
                ticker=meta.ticker,
                cik=meta.cik,
                company_name=meta.company_name,
                form_type=meta.form_type,
                filed_at=meta.filed_at,
                filing_url=meta.filing_url,
                sections=sections,
                full_text=full_text,
                collected_at=datetime.utcnow()
            )
            filings.append(filing)
            self.existing_ids.add(meta.accession_no)
            
        return filings
