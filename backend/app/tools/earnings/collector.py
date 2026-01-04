
import logging
import uuid
import httpx
from datetime import datetime
from typing import List, Optional
from app.config.settings import settings
from .models import EarningsTranscript, Participant, TranscriptSection

logger = logging.getLogger(__name__)

class EarningsCollector:
    """
    Collector for Earnings Call Transcripts using API Ninjas.
    """
    def __init__(self, client=None):
        # client arg kept for compatibility but ignored in favor of direct httpx
        self.api_key = settings.api_ninja_key
        self.base_url = settings.api_ninja_base_url or "https://api.api-ninjas.com/v1"
        
        if not self.api_key:
            logger.warning("API_NINJA_KEY not set. Earnings collection will fail.")

    def collect_for_company(self, company_id: str, ticker: str, since: datetime = None, company_name: str = "") -> List[EarningsTranscript]:
        """
        Collect earnings transcripts for a company.
        
        Args:
            company_id: Internal company ID
            ticker: Stock ticker
            since: Filter for transcripts after this date (approximate based on quarter)
            company_name: Name of the company
            
        Returns:
            List of EarningsTranscript objects
        """
        if not ticker or not self.api_key:
            return []
            
        logger.info(f"Collecting earnings for {ticker}...")
        
        # API Ninjas doesn't support "since" date filtering directly, it takes year/quarter.
        # We will fetch the most recent transcript, and maybe the previous one if 'since' is far back.
        # For now, let's fetch the current year and previous year if needed.
        
        current_year = datetime.utcnow().year
        years_to_fetch = [current_year]
        if since and since.year < current_year:
            years_to_fetch.append(current_year - 1)
            
        transcripts = []
        
        # We'll try to fetch the last 4 quarters to be safe, or iterate by year
        # API Ninjas returns a specific transcript for Ticker + Year + Quarter.
        # It doesn't seem to have a "list all" endpoint easily.
        # Strategy: Try to fetch Q1-Q4 for the relevant years.
        
        for year in years_to_fetch:
            for quarter in range(1, 5):
                # Optimization: Don't fetch future quarters
                if year == current_year and quarter > (datetime.utcnow().month - 1) // 3 + 1:
                    continue
                    
                try:
                    transcript_data = self._fetch_transcript(ticker, year, quarter)
                    if transcript_data:
                        # Check date if available
                        transcript_date_str = transcript_data.get("date")
                        if transcript_date_str:
                            try:
                                transcript_date = datetime.strptime(transcript_date_str, "%Y-%m-%d")
                                if since and transcript_date < since:
                                    continue
                            except ValueError:
                                pass # Keep if date parse fails
                        
                        # Process participants as structured data (Participant objects)
                        raw_participants = transcript_data.get("participants", [])
                        processed_participants = []
                        if isinstance(raw_participants, list):
                            for p in raw_participants:
                                if isinstance(p, dict):
                                    processed_participants.append(Participant(
                                        name=p.get('name', ''),
                                        role=p.get('role') or None,
                                        company=p.get('company') or None,
                                    ))
                                elif isinstance(p, str):
                                    # Legacy string format - convert to Participant
                                    processed_participants.append(Participant(name=p))
                        
                        # Process transcript_split for speaker attribution
                        raw_split = transcript_data.get("transcript_split", [])
                        processed_sections = []
                        if isinstance(raw_split, list):
                            for section in raw_split:
                                if isinstance(section, dict) and section.get("text"):
                                    processed_sections.append(TranscriptSection(
                                        speaker=section.get('speaker', 'Unknown'),
                                        role=section.get('role') or None,
                                        company=section.get('company') or None,
                                        text=section.get('text', ''),
                                    ))
                        
                        # Parse the date
                        call_date = datetime.utcnow()  # Fallback
                        if transcript_data.get("date"):
                            try:
                                call_date = datetime.strptime(transcript_data.get("date"), "%Y-%m-%d")
                            except:
                                pass
                        
                        # Create EarningsTranscript object with all rich data
                        transcript = EarningsTranscript(
                            id=str(uuid.uuid4()),
                            company_name=company_name or ticker,
                            ticker=ticker,
                            year=year,
                            quarter=quarter,
                            date=call_date,
                            content=transcript_data.get("transcript", ""),
                            participants=processed_participants if processed_participants else None,
                            transcript_split=processed_sections if processed_sections else None,
                            earnings_timing=transcript_data.get("earnings_timing"),  # before_market, after_market
                            cik=transcript_data.get("cik"),  # SEC CIK identifier
                            timestamp=transcript_data.get("timestamp"),  # Unix timestamp
                            collected_at=datetime.utcnow()
                        )

                        transcripts.append(transcript)
                        
                except Exception as e:
                    logger.error(f"Failed to fetch earnings for {ticker} Q{quarter} {year}: {e}")
                    
        return transcripts

    def _fetch_transcript(self, ticker: str, year: int, quarter: int) -> Optional[dict]:
        """Fetch a single transcript from API Ninjas"""
        url = f"{self.base_url}/earningstranscript"
        params = {
            "ticker": ticker,
            "year": year,
            "quarter": quarter
        }
        headers = {"X-Api-Key": self.api_key}
        
        try:
            with httpx.Client(timeout=30) as client:
                response = client.get(url, params=params, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    if data and "transcript" in data:
                        return data
                elif response.status_code == 400:
                    # Likely no transcript for this quarter yet
                    return None
                else:
                    logger.warning(f"API Ninjas error {response.status_code}: {response.text}")
                    return None
        except Exception as e:
            logger.error(f"Request error: {e}")
            return None
        return None
        
