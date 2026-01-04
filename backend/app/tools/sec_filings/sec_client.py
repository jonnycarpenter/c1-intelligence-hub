
import httpx
import time
import logging
from typing import List, Optional
from datetime import datetime
from app.config.settings import settings
from .models import FilingMetadata

logger = logging.getLogger(__name__)

class SECClient:
    QUERY_URL = "https://api.sec-api.io"
    EXTRACTOR_URL = "https://api.sec-api.io/extractor"
    RENDER_URL = "https://archive.sec-api.io"
    
    # Rate limiting: SEC API has limits per minute
    MIN_REQUEST_INTERVAL = 0.5  # 500ms between requests to avoid rate limits
    
    def __init__(self, api_key: str = None):
        self.api_key = (api_key or settings.sec_api_key or "").strip()
        if self.api_key == "PLACEHOLDER":
             self.api_key = "" # Treat as missing
        self.client = httpx.Client(timeout=60.0)
        self._last_request_time = 0
        logger.info(f"SEC Client initialized, API key present: {bool(self.api_key)}")
    
    def _rate_limit(self):
        """Enforce minimum interval between API requests"""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.MIN_REQUEST_INTERVAL:
            time.sleep(self.MIN_REQUEST_INTERVAL - elapsed)
        self._last_request_time = time.time()
    
    def query_filings(
        self,
        ticker: str = None,
        cik: str = None,
        form_types: List[str] = None,
        filed_after: datetime = None,
        filed_before: datetime = None,
        size: int = 50
    ) -> List[FilingMetadata]:
        if not self.api_key:
            return []
        
        query_parts = []
        if ticker: query_parts.append(f'ticker:{ticker}')
        if cik: query_parts.append(f'cik:{cik}')
        if form_types:
            types_str = " OR ".join([f'"{t}"' for t in form_types])
            query_parts.append(f'formType:({types_str})')
        if filed_after:
            after_str = filed_after.strftime("%Y-%m-%d")
            query_parts.append(f'filedAt:[{after_str} TO *]')
        
        query = " AND ".join(query_parts) if query_parts else "formType:\"10-K\""
        
        payload = {
            "query": query,
            "from": "0",
            "size": str(size),
            "sort": [{"filedAt": {"order": "desc"}}]
        }
        
        # Retry with exponential backoff for rate limits
        max_retries = 3
        for attempt in range(max_retries):
            self._rate_limit()
            try:
                response = self.client.post(
                    self.QUERY_URL,
                    json=payload,
                    headers={"Authorization": self.api_key}
                )
                if response.status_code == 429:
                    wait_time = (2 ** attempt) * 2  # 2, 4, 8 seconds
                    logger.warning(f"SEC API rate limit hit, waiting {wait_time}s before retry {attempt + 1}/{max_retries}")
                    time.sleep(wait_time)
                    continue
                response.raise_for_status()
                break
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429 and attempt < max_retries - 1:
                    wait_time = (2 ** attempt) * 2
                    logger.warning(f"SEC API rate limit hit, waiting {wait_time}s before retry {attempt + 1}/{max_retries}")
                    time.sleep(wait_time)
                    continue
                raise
        else:
            logger.error(f"SEC API rate limit exceeded after {max_retries} retries")
            return []
        
        data = response.json()
        filings = []
        for item in data.get("filings", []):
            try:
                filed_at = datetime.fromisoformat(item.get("filedAt", "").replace("Z", "+00:00"))
            except:
                filed_at = datetime.utcnow()
                
            filings.append(FilingMetadata(
                accession_no=item.get("accessionNo", ""),
                cik=item.get("cik", ""),
                ticker=item.get("ticker", ""),
                company_name=item.get("companyName", ""),
                form_type=item.get("formType", ""),
                filed_at=filed_at,
                filing_url=item.get("linkToFilingDetails", "")
            ))
        return filings

    def extract_section(self, filing_url: str, section: str) -> Optional[str]:
        params = {
            "url": filing_url,
            "item": section,
            "type": "text",
            "token": self.api_key
        }
        try:
            self._rate_limit()
            response = self.client.get(self.EXTRACTOR_URL, params=params)
            if response.status_code == 200:
                return response.text
            elif response.status_code == 429:
                logger.warning(f"SEC Extractor API rate limit hit for {section}")
                time.sleep(2)  # Brief wait, then return None
        except Exception as e:
            logger.debug(f"SEC extract_section failed: {e}")
            return None
        return None

    def download_filing(self, filing_url: str) -> Optional[str]:
        # Convert to archive URL using the format required by sec-api.io
        # Remove "ix?doc=/" and the standard SEC archives path prefix
        import re
        filename = re.sub(r"ix\?doc=/", "", filing_url)
        filename = re.sub(r"https://www.sec.gov/Archives/edgar/data", "", filename)
        
        # Construct URL with token as query parameter
        archive_url = f"{self.RENDER_URL}{filename}?token={self.api_key}"
        
        try:
            # Note: Authorization header is not used for this endpoint, token is in URL
            response = self.client.get(archive_url)
            if response.status_code == 200:
                return response.text
        except Exception:
            return None
        return None

    def close(self):
        self.client.close()
