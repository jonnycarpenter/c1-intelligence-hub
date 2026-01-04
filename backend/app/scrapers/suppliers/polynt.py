"""
Polynt-Reichhold Datasheet Scraper
==================================

Scrapes technical datasheets from Polynt-Reichhold Group.

Site structure:
- WordPress-based site
- PDFs in /wp-content/uploads/ directories
- Product pages with embedded PDF links

Products:
- Unsaturated polyester resins
- Vinyl ester resins
- Gel coats
- SMC/BMC compounds
"""

import re
import asyncio
import logging
from typing import List

import httpx
from bs4 import BeautifulSoup

from app.scrapers.base_scraper import BaseDatasheetScraper, DatasheetInfo
from app.scrapers.config import MaterialCategory

logger = logging.getLogger(__name__)


class PolyntScraper(BaseDatasheetScraper):
    """Scraper for Polynt-Reichhold datasheets."""
    
    SUPPLIER_NAME = "Polynt-Reichhold"
    SUPPLIER_ID = "polynt"
    BASE_URL = "https://www.polynt.com"
    
    # Known PDF URLs to seed
    KNOWN_PDFS = [
        "https://www.polynt.com/wp-content/uploads/2020/06/Brochure-Polynt-Reichhold-Compounds-Carbon-Fiber.pdf",
        "https://www.polynt.com/wp-content/uploads/2019/02/Brochure-Polynt-Reichhold-Compounds-BMC-SMC.pdf",
    ]
    
    # Product pages to crawl
    PRODUCT_PAGES = [
        "https://www.polynt.com/composites/",
        "https://www.polynt.com/composites/unsaturated-polyester-resins/",
        "https://www.polynt.com/composites/vinyl-ester-resins/",
        "https://www.polynt.com/composites/gel-coats/",
        "https://www.polynt.com/composites/compounds/",
        "https://www.polynt.com/composites/specialty-resins/",
        "https://www.polynt.com/resources/",
    ]
    
    async def discover_datasheets(self, client: httpx.AsyncClient) -> List[DatasheetInfo]:
        """Crawl Polynt's website for datasheets."""
        datasheets = []
        seen_urls = set()
        
        # Add known PDFs first
        for pdf_url in self.KNOWN_PDFS:
            if pdf_url in seen_urls:
                continue
            seen_urls.add(pdf_url)
            
            title = self._extract_title_from_url(pdf_url)
            datasheets.append(DatasheetInfo(
                url=pdf_url,
                title=title,
                supplier_name=self.SUPPLIER_NAME,
                filename=self._safe_filename(title),
                product_name=title,
                product_family=self._extract_product_family(pdf_url, title),
                material_category=self._categorize_polynt_material(title),
                industries=["marine", "construction", "automotive", "industrial"],
                metadata={"source": "known_pdf"}
            ))
        
        # Crawl product pages
        for page_url in self.PRODUCT_PAGES:
            try:
                await asyncio.sleep(self.config.request_delay)
                
                response = await client.get(page_url, timeout=30.0)
                if response.status_code != 200:
                    logger.warning(f"Failed to fetch {page_url}: {response.status_code}")
                    continue
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Find PDF links
                for link in soup.find_all('a', href=re.compile(r'\.pdf$', re.I)):
                    href = link.get('href', '')
                    
                    url = self._make_absolute_url(href)
                    
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)
                    
                    # Get title
                    title = link.get_text(strip=True)
                    if not title or len(title) < 3:
                        title = self._extract_title_from_url(href)
                    
                    # Extract product info
                    product_name = self._extract_product_name(href, title)
                    product_family = self._extract_product_family(href, title)
                    
                    # Categorize
                    category_text = f"{title} {href} {page_url}"
                    material_category = self._categorize_polynt_material(category_text)
                    industries = self._guess_industries(category_text + " resin polyester")
                    
                    datasheets.append(DatasheetInfo(
                        url=url,
                        title=title,
                        supplier_name=self.SUPPLIER_NAME,
                        filename=self._safe_filename(title),
                        product_name=product_name,
                        product_family=product_family,
                        material_category=material_category,
                        industries=industries,
                        metadata={"source_page": page_url}
                    ))
                
            except Exception as e:
                logger.error(f"Error crawling {page_url}: {e}")
                continue
        
        logger.info(f"Polynt: Found {len(datasheets)} unique datasheets")
        return datasheets
    
    def _extract_title_from_url(self, url: str) -> str:
        """Extract readable title from URL."""
        filename = url.split('/')[-1]
        filename = re.sub(r'\.pdf$', '', filename, flags=re.I)
        title = filename.replace('-', ' ').replace('_', ' ')
        # Clean up WordPress upload patterns
        title = re.sub(r'Brochure\s+Polynt\s+Reichhold\s*', '', title, flags=re.I)
        return title.strip() or "Polynt Datasheet"
    
    def _extract_product_name(self, url: str, title: str) -> str:
        """Extract product identifier."""
        combined = f"{url} {title}"
        
        # Common Polynt product patterns
        # Resin codes like POLYLITE, DION, etc.
        match = re.search(r'\b(POLYLITE|DION|DERAKANE|AROPOL|NORPOL)\s*[\w\-]*', combined, re.I)
        if match:
            return match.group(0).strip()
        
        # Generic product codes
        match = re.search(r'\b([A-Z]{2,}\d{3,})\b', combined)
        if match:
            return match.group(1)
        
        return title.split()[0] if title else ""
    
    def _extract_product_family(self, url: str, title: str) -> str:
        """Extract product family."""
        combined = f"{url} {title}".lower()
        
        if "polyester" in combined or "polylite" in combined:
            return "Polyester Resins"
        if "vinyl" in combined or "derakane" in combined or "dion" in combined:
            return "Vinyl Ester Resins"
        if "gel coat" in combined or "gelcoat" in combined:
            return "Gel Coats"
        if "smc" in combined or "bmc" in combined or "compound" in combined:
            return "SMC/BMC Compounds"
        if "epoxy" in combined:
            return "Epoxy Resins"
        
        return "Resins"
    
    def _categorize_polynt_material(self, text: str) -> str:
        """Categorize Polynt material."""
        text = text.lower()
        
        if any(kw in text for kw in ["vinyl ester", "vinylester", "derakane", "dion"]):
            return MaterialCategory.RESIN_VINYLESTER.value
        if any(kw in text for kw in ["polyester", "polylite", "aropol"]):
            return MaterialCategory.RESIN_POLYESTER.value
        if "epoxy" in text:
            return MaterialCategory.RESIN_EPOXY.value
        if "gel coat" in text or "gelcoat" in text:
            return MaterialCategory.OTHER.value
        
        # Default for Polynt is polyester resin
        return MaterialCategory.RESIN_POLYESTER.value
