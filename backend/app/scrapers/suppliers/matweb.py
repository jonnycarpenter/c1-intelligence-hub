"""
MatWeb Datasheet Scraper
========================

Scrapes technical datasheets from MatWeb.com - a centralized materials database.
MatWeb has structured property data for materials from many manufacturers.

This scraper can pull data for multiple suppliers:
- Toray Industries (387 materials)
- Owens Corning (22 materials)
- And many others

Note: MatWeb provides HTML datasheets (not PDFs), but with excellent structured data.
"""

import re
import asyncio
import logging
from typing import List, Dict, Optional
from urllib.parse import urljoin, quote

import httpx
from bs4 import BeautifulSoup

from app.scrapers.base_scraper import BaseDatasheetScraper, DatasheetInfo
from app.scrapers.config import ScraperConfig, MaterialCategory

logger = logging.getLogger(__name__)


# MatWeb manufacturer IDs and material counts (as of Jan 2026)
MATWEB_MANUFACTURERS = {
    "toray": {
        "manID": "1109",
        "manname": "Toray+Industires",  # Note: their typo
        "display_name": "Toray Industries",
        "material_count": 387,
    },
    "owens_corning": {
        "manID": "113",
        "manname": "Owens+Corning",
        "display_name": "Owens Corning",
        "material_count": 22,
    },
    "hexcel": {
        "manID": "358",  # Need to verify
        "manname": "Hexcel",
        "display_name": "Hexcel Corporation",
        "material_count": 50,  # Estimate
    },
    "gurit": {
        "manID": "291",  # Need to verify
        "manname": "Gurit",
        "display_name": "Gurit",
        "material_count": 20,  # Estimate
    },
}


class MatWebScraper(BaseDatasheetScraper):
    """
    Scraper for MatWeb.com material property database.
    
    Unlike other scrapers that get PDFs, this scrapes structured HTML datasheets.
    The extracted text is well-structured with properties clearly labeled.
    """
    
    SUPPLIER_NAME = "MatWeb"
    SUPPLIER_ID = "matweb"
    BASE_URL = "https://www.matweb.com"
    
    def __init__(self, config: ScraperConfig, supplier_config=None, target_manufacturer: str = None):
        """
        Initialize MatWeb scraper.
        
        Args:
            config: Scraper configuration
            supplier_config: Optional supplier configuration (passed by orchestrator)
            target_manufacturer: Which manufacturer to scrape (e.g., 'toray', 'owens_corning')
                               If None, scrapes all known manufacturers
        """
        super().__init__(config, supplier_config)
        self.target_manufacturer = target_manufacturer
        
        if target_manufacturer and target_manufacturer in MATWEB_MANUFACTURERS:
            self.manufacturers = {target_manufacturer: MATWEB_MANUFACTURERS[target_manufacturer]}
        else:
            self.manufacturers = MATWEB_MANUFACTURERS
    
    async def discover_datasheets(self, client: httpx.AsyncClient) -> List[DatasheetInfo]:
        """Discover all material datasheets from MatWeb for target manufacturers."""
        datasheets = []
        seen_urls = set()
        
        for man_key, man_info in self.manufacturers.items():
            logger.info(f"Discovering materials for {man_info['display_name']} on MatWeb...")
            
            # Construct manufacturer materials URL
            list_url = (
                f"{self.BASE_URL}/search/GetMatlsByManufacturer.aspx"
                f"?navletter={man_info['manname'][0].upper()}"
                f"&manID={man_info['manID']}"
                f"&manname={man_info['manname']}"
            )
            
            try:
                await asyncio.sleep(self.config.request_delay)
                response = await client.get(list_url, timeout=30.0)
                
                if response.status_code != 200:
                    logger.warning(f"Failed to fetch MatWeb listing for {man_key}: {response.status_code}")
                    continue
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Find all material datasheet links
                # MatWeb uses links like: /search/datasheettext.aspx?matguid=xxx
                for link in soup.find_all('a', href=re.compile(r'datasheettext\.aspx\?matguid=')):
                    href = link.get('href', '')
                    url = urljoin(self.BASE_URL, href)
                    
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)
                    
                    # Get material name from link text
                    title = link.get_text(strip=True)
                    if not title or len(title) < 3:
                        continue
                    
                    # Clean up title
                    title = re.sub(r'\s+', ' ', title).strip()
                    
                    # Extract product info from title
                    product_name, product_family = self._parse_matweb_title(title, man_key)
                    material_category = self._categorize_matweb_material(title, man_key)
                    industries = self._guess_industries_matweb(title, man_key)
                    
                    # Use manufacturer name as supplier (not "MatWeb")
                    supplier_name = man_info['display_name']
                    
                    datasheets.append(DatasheetInfo(
                        url=url,
                        title=title,
                        supplier_name=supplier_name,
                        filename=self._safe_filename(title) + ".html",
                        product_name=product_name,
                        product_family=product_family,
                        material_category=material_category,
                        industries=industries,
                        metadata={"source": "matweb", "manufacturer_key": man_key}
                    ))
                
                logger.info(f"MatWeb: Found {len([d for d in datasheets if d.metadata.get('manufacturer_key') == man_key])} materials for {man_info['display_name']}")
                
            except Exception as e:
                logger.error(f"Error scraping MatWeb for {man_key}: {e}")
        
        logger.info(f"MatWeb: Found {len(datasheets)} total unique materials")
        return datasheets
    
    def _parse_matweb_title(self, title: str, manufacturer: str) -> tuple:
        """Extract product name and family from MatWeb material title."""
        # MatWeb titles are typically: "Manufacturer Product Name, Details"
        # e.g., "Toray Industires Torayca® T300 Carbon Fiber, 3000 Filament Tow"
        
        product_name = title
        product_family = None
        
        # Common patterns
        patterns = [
            # Toray patterns
            (r"Torayca®?\s+(T\d+[A-Z]*)", "Torayca"),
            (r"Torelina®?\s+(\S+)", "Torelina"),
            # Owens Corning patterns
            (r"Glass Fiber Reinforced (\w+)", "Glass Fiber Reinforced"),
            # Generic patterns
            (r"Carbon Fiber", "Carbon Fiber"),
            (r"Prepreg", "Prepreg"),
        ]
        
        for pattern, family in patterns:
            match = re.search(pattern, title, re.IGNORECASE)
            if match:
                product_family = family
                if match.groups():
                    product_name = match.group(1)
                break
        
        return product_name, product_family
    
    def _categorize_matweb_material(self, title: str, manufacturer: str) -> str:
        """Categorize MatWeb material based on title."""
        title_lower = title.lower()
        
        if "carbon fiber" in title_lower:
            return MaterialCategory.CARBON_FIBER.value
        if "glass fiber" in title_lower:
            return MaterialCategory.GLASS_FIBER.value
        if "aramid" in title_lower:
            return MaterialCategory.ARAMID_FIBER.value
        if "prepreg" in title_lower:
            return MaterialCategory.PREPREG.value
        if "epoxy" in title_lower:
            return MaterialCategory.RESIN_EPOXY.value
        if "polyester" in title_lower:
            return MaterialCategory.RESIN_POLYESTER.value
        if "vinylester" in title_lower or "vinyl ester" in title_lower:
            return MaterialCategory.RESIN_VINYLESTER.value
        if "honeycomb" in title_lower:
            return MaterialCategory.CORE_HONEYCOMB.value
        if "foam" in title_lower:
            return MaterialCategory.CORE_FOAM.value
        if "adhesive" in title_lower:
            return MaterialCategory.ADHESIVE.value
        if "fabric" in title_lower or "woven" in title_lower:
            return MaterialCategory.FABRIC.value
        
        # Manufacturer-specific defaults
        if manufacturer == "toray":
            return MaterialCategory.CARBON_FIBER.value
        if manufacturer == "owens_corning":
            return MaterialCategory.GLASS_FIBER.value
        
        return MaterialCategory.OTHER.value
    
    def _guess_industries_matweb(self, title: str, manufacturer: str) -> List[str]:
        """Guess industries based on MatWeb material properties."""
        industries = []
        title_lower = title.lower()
        
        # Keywords to industries mapping
        industry_keywords = {
            "aerospace": ["aerospace", "aircraft", "aviation", "space"],
            "automotive": ["automotive", "vehicle", "car"],
            "marine": ["marine", "boat", "ship", "naval"],
            "wind_energy": ["wind", "turbine", "blade"],
            "construction": ["construction", "building", "structural"],
            "sports": ["sports", "recreation", "bicycle", "ski"],
        }
        
        for industry, keywords in industry_keywords.items():
            if any(kw in title_lower for kw in keywords):
                industries.append(industry)
        
        # Default industries by manufacturer
        if not industries:
            if manufacturer == "toray":
                industries = ["aerospace", "automotive"]
            elif manufacturer == "owens_corning":
                industries = ["construction", "automotive"]
        
        return industries
    
    def _safe_filename(self, title: str) -> str:
        """Convert title to safe filename."""
        # Remove invalid characters
        safe = re.sub(r'[<>:"/\\|?*]', '', title)
        safe = re.sub(r'\s+', '_', safe)
        safe = safe[:100]  # Limit length
        return safe or "material"
    
    async def download_datasheet(
        self,
        info: DatasheetInfo,
        client: httpx.AsyncClient,
        existing_hashes: Dict[str, str] = None,
    ):
        """
        Download and process a MatWeb HTML datasheet.
        
        Overrides base class to handle HTML content instead of PDFs.
        """
        from app.scrapers.base_scraper import DownloadResult
        from app.scrapers.pdf_processor import ExtractedContent
        import hashlib
        from datetime import datetime, timezone
        from pathlib import Path
        
        existing_hashes = existing_hashes or {}
        
        try:
            # Download with retry
            response = await self._fetch_with_retry(client, info.url)
            
            if response is None:
                return DownloadResult(
                    info=info,
                    success=False,
                    error_message="Failed to download after retries"
                )
            
            content = response.text
            file_size = len(content.encode('utf-8'))
            
            # Calculate hash for change detection
            file_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
            
            # Check if content unchanged
            if info.datasheet_id in existing_hashes:
                if existing_hashes[info.datasheet_id] == file_hash:
                    return DownloadResult(
                        info=info,
                        success=False,
                        error_message="Content unchanged"
                    )
            
            # Parse HTML and extract text content
            soup = BeautifulSoup(content, 'html.parser')
            
            # Remove script and style elements
            for element in soup(['script', 'style', 'nav', 'footer', 'header']):
                element.decompose()
            
            # Find the main content area (MatWeb specific)
            main_content = soup.find('div', {'id': 'content'}) or soup.find('main') or soup.body
            
            if main_content:
                # Extract text with structure preserved
                extracted_text = self._extract_structured_text(main_content)
            else:
                extracted_text = soup.get_text(separator='\n', strip=True)
            
            # Clean up extracted text
            extracted_text = re.sub(r'\n{3,}', '\n\n', extracted_text)
            extracted_text = extracted_text[:self.config.max_text_length]
            
            # Save to disk
            safe_filename = self._safe_filename(info.filename or info.title)
            if not safe_filename.endswith('.html'):
                safe_filename += '.html'
            
            local_path = self.download_dir / safe_filename
            with open(local_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Track downloaded URL
            self.downloaded_urls.add(info.url)
            
            # Create extracted content (compatible with PDFProcessor's ExtractedContent)
            extracted_content = ExtractedContent(
                text=extracted_text,
                tables=[],
                page_count=1,  # HTML is single "page"
                success=True,
                method_used="html_parse",
                error_message=None
            )
            
            logger.info(f"Downloaded: {info.title} ({file_size / 1024:.1f}KB)")
            
            return DownloadResult(
                info=info,
                success=True,
                local_path=str(local_path),
                file_size=file_size,
                file_hash=file_hash,
                extracted_content=extracted_content,
            )
            
        except Exception as e:
            logger.error(f"Error downloading {info.url}: {e}")
            return DownloadResult(
                info=info,
                success=False,
                error_message=str(e)
            )
    
    def _extract_structured_text(self, element) -> str:
        """Extract text while preserving structure from MatWeb datasheets."""
        lines = []
        
        # MatWeb uses tables for property data
        for table in element.find_all('table'):
            for row in table.find_all('tr'):
                cells = row.find_all(['td', 'th'])
                if cells:
                    row_text = ' | '.join(cell.get_text(strip=True) for cell in cells)
                    if row_text.strip():
                        lines.append(row_text)
        
        # Also get paragraph text
        for p in element.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'li']):
            text = p.get_text(strip=True)
            if text and text not in '\n'.join(lines):
                lines.append(text)
        
        return '\n'.join(lines)


class TorayMatWebScraper(MatWebScraper):
    """Scraper for Toray materials via MatWeb."""
    
    SUPPLIER_NAME = "Toray"
    SUPPLIER_ID = "toray_matweb"
    
    def __init__(self, config: ScraperConfig, supplier_config=None):
        super().__init__(config, supplier_config, target_manufacturer="toray")


class OwensCorningMatWebScraper(MatWebScraper):
    """Scraper for Owens Corning materials via MatWeb."""
    
    SUPPLIER_NAME = "Owens Corning"
    SUPPLIER_ID = "owens_corning_matweb"
    
    def __init__(self, config: ScraperConfig, supplier_config=None):
        super().__init__(config, supplier_config, target_manufacturer="owens_corning")
