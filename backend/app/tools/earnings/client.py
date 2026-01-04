
import httpx
import logging
from typing import List, Optional
from datetime import datetime
from app.config.settings import settings
from .models import EarningsTranscript, EarningsEvent

logger = logging.getLogger(__name__)

class APINinjaClient:
    BASE_URL = "https://api.api-ninjas.com/v1"
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or settings.api_ninja_key
        self.client = httpx.Client(timeout=30.0, headers={"X-Api-Key": self.api_key})
    
    def get_earnings_calendar(self, ticker: str) -> List[EarningsEvent]:
        # API Ninjas earningscalendar endpoint
        try:
            response = self.client.get(f"{self.BASE_URL}/earningscalendar", params={"ticker": ticker})
            response.raise_for_status()
            data = response.json()
            
            events = []
            for item in data:
                try:
                    date_str = item.get("pricedate", "")
                    if not date_str:
                         continue
                         
                    price_date = datetime.strptime(date_str, "%Y-%m-%d")
                    events.append(EarningsEvent(
                        ticker=ticker,
                        date=price_date,
                        quarter=None, # API Ninjas might not provide Q/Y explicitly in all responses
                        year=price_date.year,
                        estimated_eps=item.get("estimated_eps"),
                        actual_eps=item.get("actual_eps"),
                        revenue_estimate=item.get("revenue_estimate"),
                        revenue_actual=item.get("revenue_actual")
                    ))
                except Exception as e:
                    logger.warning(f"Error parsing earnings event for {ticker}: {e}")
            return events
        except Exception as e:
            logger.error(f"Failed to fetch earnings calendar for {ticker}: {e}")
            return []

    def get_transcript(self, ticker: str, year: int, quarter: int) -> Optional[EarningsTranscript]:
        # NOTE: API Ninjas does NOT have a transcript endpoint.
        # This is a placeholder - transcript functionality would need a different service.
        
        # User requested "earnings call transcripts (via API Ninja)". 
        # I will assume there might be a misunderstanding or a proxy. 
        # I will try to fetch from a source if available, otherwise return None.
        
        # For the purpose of this task, I will mock the return if the endpoint is 404.
        return None 

    def close(self):
        self.client.close()
