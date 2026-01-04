"""
Gurit Datasheet Scraper
=======================

Scrapes technical datasheets from Gurit Holding AG.

Site structure:
- Product pages with PDF links
- PDFs managed via bsk-pdf-manager WordPress plugin
- Large catalog PDFs covering multiple products

Products:
- Prepregs (wind, marine, automotive)
- Structural core materials (PVC, PET foam, balsa)
- Structural adhesives
- Composite tooling
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


class GuritScraper(BaseDatasheetScraper):
    """Scraper for Gurit datasheets."""
    
    SUPPLIER_NAME = "Gurit"
    SUPPLIER_ID = "gurit"
    BASE_URL = "https://www.gurit.com"
    
    # Known catalog PDFs
    KNOWN_PDFS = [
        "https://www.gurit.com/wp-content/uploads/bsk-pdf-manager/2023/11/EMEA-Catalogue-November-2023-1.pdf",
    ]
    
    # Product pages to crawl
    PRODUCT_PAGES = [
        "https://www.gurit.com/products/",
        "https://www.gurit.com/products/prepregs/",
        "https://www.gurit.com/products/structural-core/",
        "https://www.gurit.com/products/formulated-products/",
        "https://www.gurit.com/products/composite-tooling/",
        "https://www.gurit.com/resources/",
        "https://www.gurit.com/resources/datasheets/",
    ]
    
    # Specific product family pages
    PRODUCT_FAMILY_PAGES = [
        # Prepregs
        "https://www.gurit.com/products/prepregs/wind-energy/",
        "https://www.gurit.com/products/prepregs/marine/",
        "https://www.gurit.com/products/prepregs/transportation/",
        # Core materials
        "https://www.gurit.com/products/structural-core/corecell/",
        "https://www.gurit.com/products/structural-core/pvc-foam/",
        "https://www.gurit.com/products/structural-core/balsa/",
        # Adhesives
        "https://www.gurit.com/products/formulated-products/structural-adhesives/",
    ]
    
    async def discover_datasheets(self, client: httpx.AsyncClient) -> List[DatasheetInfo]:
        """Crawl Gurit's website for datasheets."""
        datasheets = []
        seen_urls = set()
        
        # Add known catalog PDFs
        for pdf_url in self.KNOWN_PDFS:
            if pdf_url in seen_urls:
                continue
            seen_urls.add(pdf_url)
            
            title = self._extract_title_from_url(pdf_url)
            datasheets.append(DatasheetInfo(
                url=pdf_url,
                title=f"Gurit {title}",
                supplier_name=self.SUPPLIER_NAME,
                filename=self._safe_filename(title),
                product_name="Product Catalog",
                product_family="Catalog",
                material_category=MaterialCategory.OTHER.value,
                industries=["wind_energy", "marine", "transportation"],
                metadata={"source": "known_pdf", "document_type": "catalog"}
            ))
        
        # Crawl all product pages
        all_pages = self.PRODUCT_PAGES + self.PRODUCT_FAMILY_PAGES
        
        for page_url in all_pages:
            try:
                await asyncio.sleep(self.config.request_delay)
                
                response = await client.get(page_url, timeout=30.0)
                if response.status_code != 200:
                    logger.warning(f"Failed to fetch {page_url}: {response.status_code}")
                    continue
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Find PDF links
                for link in soup.find_all('a', href=re.compile(r'\.pdf', re.I)):
                    href = link.get('href', '')
                    
                    if not href:
                        continue
                    
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
                    product_family = self._extract_product_family(href, title, page_url)
                    
                    # Categorize based on URL path and title
                    category_text = f"{title} {href} {page_url}"
                    material_category = self._categorize_gurit_material(category_text)
                    industries = self._guess_gurit_industries(category_text)
                    
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
        
        logger.info(f"Gurit: Found {len(datasheets)} unique datasheets")
        return datasheets
    
    def _extract_title_from_url(self, url: str) -> str:
        """Extract readable title from URL."""
        filename = url.split('/')[-1]
        filename = re.sub(r'\.pdf$', '', filename, flags=re.I)
        # Clean up WordPress BSK PDF manager patterns
        filename = re.sub(r'^[\d\-]+', '', filename)
        title = filename.replace('-', ' ').replace('_', ' ')
        return title.strip() or "Gurit Datasheet"
    
    def _extract_product_name(self, url: str, title: str) -> str:
        """Extract product identifier."""
        combined = f"{url} {title}"
        
        # Gurit product names
        # Prepregs: SPRINT, SPARPREG, SE 84, etc.
        match = re.search(r'\b(SPRINT|SPARPREG|SE\s*\d+|WE\s*\d+|PRIME)\b', combined, re.I)
        if match:
            return match.group(0).upper().strip()
        
        # Core materials: Corecell, Balsaflex, etc.
        match = re.search(r'\b(CORECELL|BALSAFLEX|KERDYN|PVC\s*\d+)\b', combined, re.I)
        if match:
            return match.group(0).strip()
        
        # Adhesives: SPABOND, etc.
        match = re.search(r'\b(SPABOND|AMPREG|SP\s*\d+)\b', combined, re.I)
        if match:
            return match.group(0).strip()
        
        return title.split()[0] if title else ""
    
    def _extract_product_family(self, url: str, title: str, page_url: str = "") -> str:
        """Extract product family."""
        combined = f"{url} {title} {page_url}".lower()
        
        # Prepregs
        if "prepreg" in combined:
            if "wind" in combined:
                return "Wind Energy Prepregs"
            if "marine" in combined:
                return "Marine Prepregs"
            if "transport" in combined or "auto" in combined:
                return "Transportation Prepregs"
            return "Prepregs"
        
        # Core materials
        if "corecell" in combined:
            return "Corecell"
        if "balsa" in combined:
            return "Balsaflex"
        if "core" in combined or "foam" in combined:
            return "Structural Core"
        
        # Adhesives
        if "adhesive" in combined or "spabond" in combined:
            return "Structural Adhesives"
        
        # Tooling
        if "tooling" in combined:
            return "Composite Tooling"
        
        return ""
    
    def _categorize_gurit_material(self, text: str) -> str:
        """Categorize Gurit material."""
        text = text.lower()
        
        if "prepreg" in text:
            return MaterialCategory.PREPREG.value
        if "corecell" in text or "pvc foam" in text or "pet foam" in text:
            return MaterialCategory.CORE_FOAM.value
        if "balsa" in text:
            return MaterialCategory.CORE_BALSA.value
        if "honeycomb" in text:
            return MaterialCategory.CORE_HONEYCOMB.value
        if "adhesive" in text:
            return MaterialCategory.ADHESIVE.value
        if "epoxy" in text or "resin" in text:
            return MaterialCategory.RESIN_EPOXY.value
        if "tooling" in text:
            return MaterialCategory.TOOLING.value
        
        return MaterialCategory.OTHER.value
    
    def _guess_gurit_industries(self, text: str) -> List[str]:
        """Guess industries for Gurit products."""
        text = text.lower()
        industries = []
        
        if "wind" in text or "blade" in text or "turbine" in text:
            industries.append("wind_energy")
        if "marine" in text or "boat" in text or "yacht" in text:
            industries.append("marine")
        if "transport" in text or "auto" in text or "vehicle" in text:
            industries.append("automotive")
        if "aero" in text or "aircraft" in text:
            industries.append("aerospace")
        if "rail" in text or "train" in text:
            industries.append("rail")
        
        return industries if industries else ["wind_energy", "marine", "transportation"]
