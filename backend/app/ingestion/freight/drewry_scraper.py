import re
import logging
import httpx
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class FreightRate:
    lane: str
    rate: float
    currency: str = "USD"
    unit: str = "40ft"
    change_pct: Optional[float] = None
    as_of: datetime = None

class DrewryScraper:
    """
    Scraper for Drewry World Container Index (WCI).
    Fetches the latest shipping rates for major global trade lanes.
    """
    
    URL = "https://www.drewry.co.uk/supply-chain-advisors/supply-chain-expertise/world-container-index-assessed-by-drewry"
    
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
    
    LANES = [
        "Composite Index",
        "Shanghai - Rotterdam",
        "Rotterdam - Shanghai",
        "Shanghai - Genoa",
        "Shanghai - Los Angeles",
        "Los Angeles - Shanghai",
        "Shanghai - New York",
        "New York - Rotterdam",
        "Rotterdam - New York",
    ]

    async def fetch_latest_rates(self) -> List[FreightRate]:
        """Fetch and parse the latest WCI rates."""
        try:
            logger.info(f"Fetching Drewry WCI from {self.URL}")
            async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
                response = await client.get(self.URL, headers=self.HEADERS)
                response.raise_for_status()
                
                return self.parse_html(response.text)
        except Exception as e:
            logger.error(f"Error fetching Drewry rates: {e}")
            return []

    def parse_html(self, html: str) -> List[FreightRate]:
        """Parse the HTML content from Drewry's WCI page."""
        soup = BeautifulSoup(html, 'html.parser')
        rates = []
        
        # 1. Try to find the assessment date
        as_of_date = datetime.utcnow()
        date_pattern = re.compile(r'detailed assessment for .*?, (\d{1,2} [A-Z][a-z]+ \d{4})')
        date_match = date_pattern.search(soup.get_text())
        if date_match:
            try:
                as_of_date = datetime.strptime(date_match.group(1).replace('Sept', 'Sep'), "%d %b %Y")
                logger.info(f"Detected assessment date: {as_of_date.date()}")
            except Exception as e:
                logger.warning(f"Failed to parse detected date {date_match.group(1)}: {e}")

        # 2. Extract rates from narrative text
        LANE_MAPPING = {
            "Shanghai–Rotterdam": "Shanghai - Rotterdam",
            "Shanghai to Rotterdam": "Shanghai - Rotterdam",
            "Rotterdam–Shanghai": "Rotterdam - Shanghai",
            "Rotterdam to Shanghai": "Rotterdam - Shanghai",
            "Shanghai–Genoa": "Shanghai - Genoa",
            "Shanghai to Genoa": "Shanghai - Genoa",
            "Shanghai–Los Angeles": "Shanghai - Los Angeles",
            "Shanghai to Los Angeles": "Shanghai - Los Angeles",
            "Los Angeles–Shanghai": "Los Angeles - Shanghai",
            "Los Angeles to Shanghai": "Los Angeles - Shanghai",
            "Shanghai–New York": "Shanghai - New York",
            "Shanghai to New York": "Shanghai - New York",
            "New York–Rotterdam": "New York - Rotterdam",
            "New York to Rotterdam": "New York - Rotterdam",
            "Rotterdam–New York": "Rotterdam - New York",
            "Rotterdam to New York": "Rotterdam - New York",
            "Composite Index": "Composite Index",
            "World Container Index": "Composite Index",
        }

        processed_lanes = set()
        all_text = soup.get_text(separator=' ', strip=True)
        
        # Regex for rates and changes
        rate_pattern = re.compile(r'\$([\d,]+)')
        change_pattern = re.compile(r'([\d\.]+)\s*%')

        # Strategy: For each canonical lane, find the best match in the text
        for variation, canonical in LANE_MAPPING.items():
            if canonical in processed_lanes:
                continue
                
            # Find the position of the lane name
            lane_idx = all_text.find(variation)
            if lane_idx == -1:
                continue
            
            # Look at a window of text after the lane name (up to 150 chars)
            window = all_text[lane_idx:lane_idx + 150]
            
            rate_match = rate_pattern.search(window)
            if rate_match:
                try:
                    rate_val = float(rate_match.group(1).replace(',', ''))
                    
                    change_val = None
                    change_match = change_pattern.search(window)
                    if change_match:
                        change_val = float(change_match.group(1))
                        # Check for directional words in the window
                        lower_w = window.lower()
                        if any(word in lower_w for word in ['fell', 'dropped', 'decrease', 'down', 'fallen', 'negative', 'decline']):
                            change_val = -change_val
                    elif "held steady" in window.lower() or "unchanged" in window.lower():
                        change_val = 0.0
                    
                    rates.append(FreightRate(
                        lane=canonical,
                        rate=rate_val,
                        change_pct=change_val,
                        as_of=as_of_date
                    ))
                    processed_lanes.add(canonical)
                except Exception:
                    continue
            elif "held steady" in window.lower() or "unchanged" in window.lower():
                # If no rate in window but "held steady", we might need the previous rate.
                # For now, we'll just skip it if we can't find the rate.
                pass

        if not rates:
            logger.warning("No rates extracted from Drewry WCI page.")
        else:
            logger.info(f"Extracted {len(rates)} rates from Drewry WCI")
            
        return rates
        
        if not rates:
            logger.warning("No rates extracted from Drewry WCI page. HTML structure might have changed.")
        else:
            logger.info(f"Extracted {len(rates)} rates from Drewry WCI")
            
        return rates

if __name__ == "__main__":
    # Test script
    import asyncio
    logging.basicConfig(level=logging.INFO)
    
    async def test():
        scraper = DrewryScraper()
        rates = await scraper.fetch_latest_rates()
        for r in rates:
            print(f"{r.lane}: ${r.rate} ({r.change_pct}% change)")
            
    asyncio.run(test())
