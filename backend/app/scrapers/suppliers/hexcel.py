"""
Hexcel Datasheet Scraper
========================

Scrapes technical datasheets from Hexcel Corporation.

Site structure:
- Main index at https://www.hexcel.com/Resources/DataSheets/
- Nested category pages (Carbon-Fiber, Prepregs, Honeycomb, etc.)
- Direct PDF links

Products:
- HexTow carbon fibers (AS4, IM7, etc.)
- HexPly prepregs
- HexWeb honeycomb cores
- Redux adhesives
"""

import re
import asyncio
import logging
from typing import List

import httpx
from bs4 import BeautifulSoup

from app.scrapers.base_scraper import BaseDatasheetScraper, DatasheetInfo
from app.scrapers.config import ScraperConfig, SupplierConfig

logger = logging.getLogger(__name__)


class HexcelScraper(BaseDatasheetScraper):
    """Scraper for Hexcel datasheets."""
    
    SUPPLIER_NAME = "Hexcel"
    SUPPLIER_ID = "hexcel"
    BASE_URL = "https://www.hexcel.com"
    DATASHEET_INDEX = "https://www.hexcel.com/Resources/DataSheets/"
    
    # Known category pages to crawl (no trailing slashes!)
    CATEGORY_PAGES = [
        "/Resources/DataSheets/Carbon-Fiber",
        "/Resources/DataSheets/Prepreg",
        "/Resources/DataSheets/Honeycomb",
        "/Resources/DataSheets/AdhesivesDataSheets",
        "/Resources/DataSheets/Reinforcements",
        "/Resources/DataSheets/ResinsDataSheets",
        "/Resources/DataSheets/HexMC-Molding-Compound",
        "/Resources/DataSheets/Tooling-Materials",
        "/Resources/DataSheets/MultiaxialReinforcements",
    ]
    
    async def discover_datasheets(self, client: httpx.AsyncClient) -> List[DatasheetInfo]:
        """Crawl Hexcel's datasheet pages to find all PDFs."""
        datasheets = []
        seen_urls = set()
        
        # Start with main index
        pages_to_crawl = [self.DATASHEET_INDEX] + [
            self._make_absolute_url(p) for p in self.CATEGORY_PAGES
        ]
        
        for page_url in pages_to_crawl:
            try:
                await asyncio.sleep(self.config.request_delay)
                
                response = await client.get(page_url, timeout=30.0)
                if response.status_code != 200:
                    logger.warning(f"Failed to fetch {page_url}: {response.status_code}")
                    continue
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Find all PDF links
                for link in soup.find_all('a', href=True):
                    href = link.get('href', '')
                    
                    # Look for PDF files or datasheet pages
                    if not ('.pdf' in href.lower() or 'datasheet' in href.lower()):
                        continue
                    
                    # Skip non-PDF datasheet pages (they link to PDFs)
                    if 'datasheet' in href.lower() and '.pdf' not in href.lower():
                        # This might be a category page, skip
                        continue
                    
                    url = self._make_absolute_url(href)
                    
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)
                    
                    # Get title
                    title = link.get_text(strip=True)
                    if not title or len(title) < 3:
                        # Try to extract from URL
                        title = self._extract_title_from_url(href)
                    
                    # Extract product info
                    product_name = self._extract_product_name(href, title)
                    product_family = self._extract_product_family(href, title)
                    
                    # Categorize
                    category_text = f"{title} {href} {page_url}"
                    material_category = self._categorize_material(category_text)
                    industries = self._guess_industries(category_text)
                    
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
        
        logger.info(f"Hexcel: Found {len(datasheets)} unique datasheets")
        return datasheets
    
    def _extract_title_from_url(self, url: str) -> str:
        """Extract a readable title from URL path."""
        # Get filename without extension
        filename = url.split('/')[-1]
        filename = re.sub(r'\.pdf$', '', filename, flags=re.I)
        # Replace separators with spaces
        title = filename.replace('-', ' ').replace('_', ' ')
        return title.strip() or "Hexcel Datasheet"
    
    def _extract_product_name(self, url: str, title: str) -> str:
        """Extract product identifier from URL or title."""
        combined = f"{url} {title}"
        
        # HexTow fibers (AS4, IM7, etc.)
        match = re.search(r'(AS\d+|IM\d+|HM\d+)', combined, re.I)
        if match:
            return match.group(1).upper()
        
        # HexPly prepregs
        match = re.search(r'(HexPly[®\s]*[\w\d\-]+)', combined, re.I)
        if match:
            return match.group(1).strip()
        
        # HexWeb honeycomb
        match = re.search(r'(HexWeb[®\s]*[\w\d\-]+)', combined, re.I)
        if match:
            return match.group(1).strip()
        
        # Generic product codes
        match = re.search(r'([A-Z]{2,}\d{3,})', combined)
        if match:
            return match.group(1)
        
        return title.split()[0] if title else ""
    
    def _extract_product_family(self, url: str, title: str) -> str:
        """Extract product family (HexTow, HexPly, etc.)."""
        combined = f"{url} {title}".lower()
        
        if "hextow" in combined:
            return "HexTow"
        if "hexply" in combined:
            return "HexPly"
        if "hexweb" in combined:
            return "HexWeb"
        if "redux" in combined:
            return "Redux"
        if "hexforce" in combined:
            return "HexForce"
        if "hexmc" in combined:
            return "HexMC"
        
        # Infer from category in URL
        if "carbon-fiber" in combined:
            return "HexTow"
        if "prepreg" in combined:
            return "HexPly"
        if "honeycomb" in combined:
            return "HexWeb"
        if "adhesive" in combined:
            return "Redux"
        
        return ""
