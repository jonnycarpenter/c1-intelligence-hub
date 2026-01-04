"""
Owens Corning Datasheet Scraper
===============================

Scrapes technical datasheets from Owens Corning Composites.

Site structure:
- Technical resource library with document filters
- Filter by document type: "data-sheets"
- API/AJAX may be used for filtering

Products:
- Glass fiber reinforcements (E-glass, S-glass)
- Chopped strand mat
- Woven rovings
- Multi-end rovings
"""

import re
import asyncio
import logging
from typing import List

import httpx
from bs4 import BeautifulSoup

from app.scrapers.base_scraper import BaseDatasheetScraper, DatasheetInfo
from app.scrapers.config import ScraperConfig, MaterialCategory

logger = logging.getLogger(__name__)


class OwensCorningScraper(BaseDatasheetScraper):
    """Scraper for Owens Corning datasheets."""
    
    SUPPLIER_NAME = "Owens Corning"
    SUPPLIER_ID = "owens_corning"
    BASE_URL = "https://www.owenscorning.com"
    
    # Technical resources pages
    RESOURCE_PAGES = [
        "https://www.owenscorning.com/en-us/composites/resources-support/technical-resources",
        "https://www.owenscorning.com/en-us/composites/resources-support/technical-resources?document_type=data-sheets",
        "https://www.owenscorning.com/en-us/composites/product",
    ]
    
    # Product category pages that may have datasheets
    PRODUCT_PAGES = [
        "https://www.owenscorning.com/en-us/composites/product/chopped-strand",
        "https://www.owenscorning.com/en-us/composites/product/continuous-filament-mat",
        "https://www.owenscorning.com/en-us/composites/product/multi-end-roving",
        "https://www.owenscorning.com/en-us/composites/product/single-end-roving",
        "https://www.owenscorning.com/en-us/composites/product/woven-roving",
    ]
    
    async def discover_datasheets(self, client: httpx.AsyncClient) -> List[DatasheetInfo]:
        """Crawl Owens Corning's technical resources."""
        datasheets = []
        seen_urls = set()
        
        all_pages = self.RESOURCE_PAGES + self.PRODUCT_PAGES
        
        for page_url in all_pages:
            try:
                await asyncio.sleep(self.config.request_delay)
                
                response = await client.get(page_url, timeout=30.0)
                if response.status_code != 200:
                    logger.warning(f"Failed to fetch {page_url}: {response.status_code}")
                    continue
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Find PDF links
                for link in soup.find_all('a', href=True):
                    href = link.get('href', '')
                    
                    if '.pdf' not in href.lower():
                        continue
                    
                    url = self._make_absolute_url(href)
                    
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)
                    
                    # Get title
                    title = link.get_text(strip=True)
                    if not title or len(title) < 3:
                        title = self._extract_title_from_url(href)
                    
                    # Filter for likely datasheets
                    combined_text = f"{title} {href}".lower()
                    is_datasheet = any(kw in combined_text for kw in [
                        'data', 'sheet', 'tds', 'technical', 'spec', 'product'
                    ])
                    
                    if not is_datasheet:
                        continue
                    
                    # Extract product info
                    product_name = self._extract_product_name(href, title)
                    product_family = self._extract_product_family(href, title)
                    
                    # Categorize - OC is primarily glass fiber
                    material_category = self._categorize_oc_material(combined_text)
                    industries = self._guess_industries(combined_text + " glass fiber composites")
                    
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
        
        logger.info(f"Owens Corning: Found {len(datasheets)} unique datasheets")
        return datasheets
    
    def _extract_title_from_url(self, url: str) -> str:
        """Extract readable title from URL."""
        filename = url.split('/')[-1]
        filename = re.sub(r'\.pdf$', '', filename, flags=re.I)
        title = filename.replace('-', ' ').replace('_', ' ')
        return title.strip() or "Owens Corning Datasheet"
    
    def _extract_product_name(self, url: str, title: str) -> str:
        """Extract product identifier."""
        combined = f"{url} {title}"
        
        # Product codes like SE1200, ME1000, etc.
        match = re.search(r'\b([A-Z]{2,3}\d{3,4}[A-Z]?)\b', combined)
        if match:
            return match.group(1)
        
        # Advantex products
        if "advantex" in combined.lower():
            return "Advantex"
        
        return title.split()[0] if title else ""
    
    def _extract_product_family(self, url: str, title: str) -> str:
        """Extract product family."""
        combined = f"{url} {title}".lower()
        
        if "chopped strand" in combined or "chopped" in combined:
            return "Chopped Strand"
        if "roving" in combined:
            if "multi" in combined:
                return "Multi-End Roving"
            if "single" in combined:
                return "Single-End Roving"
            if "woven" in combined:
                return "Woven Roving"
            return "Roving"
        if "mat" in combined:
            return "Continuous Filament Mat"
        if "advantex" in combined:
            return "Advantex"
        
        return ""
    
    def _categorize_oc_material(self, text: str) -> str:
        """Categorize OC material (mostly glass fiber variants)."""
        text = text.lower()
        
        # OC is primarily glass fiber
        if any(kw in text for kw in ["fabric", "woven", "cloth"]):
            return MaterialCategory.FABRIC.value
        
        # Default to glass fiber
        return MaterialCategory.GLASS_FIBER.value
