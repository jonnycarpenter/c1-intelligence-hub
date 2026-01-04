"""
Toray Datasheet Scraper
=======================

Scrapes technical datasheets from Toray Composite Materials America (TorayTAC).

Site structure:
- Clean datasheet index at https://www.toraytac.com/resources/datasheets
- Well-organized by product category
- Direct PDF links

Products:
- Torayca carbon fibers (T300, T700, T800, M40J, etc.)
- Prepregs (unidirectional, woven)
- Torelina PPS resin
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


class TorayScraper(BaseDatasheetScraper):
    """Scraper for Toray (TorayTAC) datasheets."""
    
    SUPPLIER_NAME = "Toray"
    SUPPLIER_ID = "toray"
    BASE_URL = "https://www.toraytac.com"
    DATASHEET_INDEX = "https://www.toraytac.com/resources/datasheets"
    
    # Additional pages to crawl
    ADDITIONAL_PAGES = [
        "https://www.toraytac.com/products/carbon-fiber",
        "https://www.toraytac.com/products/prepreg",
        "https://www.toraytac.com/resources",
    ]
    
    async def discover_datasheets(self, client: httpx.AsyncClient) -> List[DatasheetInfo]:
        """Crawl Toray's datasheet index."""
        datasheets = []
        seen_urls = set()
        
        pages_to_crawl = [self.DATASHEET_INDEX] + self.ADDITIONAL_PAGES
        
        for page_url in pages_to_crawl:
            try:
                await asyncio.sleep(self.config.request_delay)
                
                response = await client.get(page_url, timeout=30.0)
                if response.status_code != 200:
                    logger.warning(f"Failed to fetch {page_url}: {response.status_code}")
                    continue
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Find all PDF links
                for link in soup.find_all('a', href=re.compile(r'\.pdf', re.I)):
                    href = link.get('href', '')
                    
                    url = self._make_absolute_url(href)
                    
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)
                    
                    # Get title
                    title = link.get_text(strip=True)
                    
                    # Try parent element if link text is empty
                    if not title or len(title) < 3:
                        parent = link.find_parent(['div', 'li', 'td', 'p'])
                        if parent:
                            title = parent.get_text(strip=True)
                    
                    if not title or len(title) < 3:
                        title = self._extract_title_from_url(href)
                    
                    # Clean up title
                    title = re.sub(r'\s+', ' ', title).strip()
                    if len(title) > 200:
                        title = title[:200]
                    
                    # Extract product info
                    product_name = self._extract_product_name(href, title)
                    product_family = self._extract_product_family(href, title)
                    
                    # Categorize
                    category_text = f"{title} {href}"
                    material_category = self._categorize_toray_material(category_text)
                    industries = self._guess_industries(category_text + " carbon fiber aerospace")
                    
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
        
        logger.info(f"Toray: Found {len(datasheets)} unique datasheets")
        return datasheets
    
    def _extract_title_from_url(self, url: str) -> str:
        """Extract readable title from URL."""
        filename = url.split('/')[-1]
        filename = re.sub(r'\.pdf$', '', filename, flags=re.I)
        title = filename.replace('-', ' ').replace('_', ' ')
        return title.strip() or "Toray Datasheet"
    
    def _extract_product_name(self, url: str, title: str) -> str:
        """Extract Toray product identifier."""
        combined = f"{url} {title}"
        
        # Torayca fiber designations (T300, T700S, T800H, M40J, etc.)
        match = re.search(r'\b([TM]\d{3,4}[A-Z]*)\b', combined, re.I)
        if match:
            return match.group(1).upper()
        
        # Prepreg designations
        match = re.search(r'\b(\d{4}[A-Z]?\-\d+)\b', combined)
        if match:
            return match.group(1)
        
        return title.split()[0] if title else ""
    
    def _extract_product_family(self, url: str, title: str) -> str:
        """Extract product family."""
        combined = f"{url} {title}".lower()
        
        if any(kw in combined for kw in ["t300", "t700", "t800", "t1000", "t1100"]):
            return "Torayca T-Series"
        if any(kw in combined for kw in ["m30", "m35", "m40", "m46", "m50", "m55", "m60"]):
            return "Torayca M-Series"
        if "prepreg" in combined:
            return "Toray Prepreg"
        if "torelina" in combined:
            return "Torelina PPS"
        
        # Infer from URL path
        if "carbon-fiber" in combined:
            return "Torayca"
        if "prepreg" in combined:
            return "Toray Prepreg"
        
        return "Torayca"
    
    def _categorize_toray_material(self, text: str) -> str:
        """Categorize Toray material."""
        text = text.lower()
        
        if "prepreg" in text:
            return MaterialCategory.PREPREG.value
        if "pps" in text or "torelina" in text:
            return MaterialCategory.OTHER.value
        if "fabric" in text or "woven" in text:
            return MaterialCategory.FABRIC.value
        
        # Default for Toray is carbon fiber
        return MaterialCategory.CARBON_FIBER.value
