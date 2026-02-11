"""
Scraper Configuration
=====================

Centralized configuration for the datasheet scraper module.
"""

import os
from dataclasses import dataclass, field
from typing import Optional, List
from pathlib import Path
from enum import Enum


class MaterialCategory(str, Enum):
    """Categories for composite materials."""
    CARBON_FIBER = "carbon_fiber"
    GLASS_FIBER = "glass_fiber"
    ARAMID_FIBER = "aramid_fiber"
    PREPREG = "prepreg"
    RESIN_EPOXY = "resin_epoxy"
    RESIN_POLYESTER = "resin_polyester"
    RESIN_VINYLESTER = "resin_vinylester"
    RESIN_PHENOLIC = "resin_phenolic"
    CORE_HONEYCOMB = "core_honeycomb"
    CORE_FOAM = "core_foam"
    CORE_BALSA = "core_balsa"
    ADHESIVE = "adhesive"
    FABRIC = "fabric"
    TOOLING = "tooling"
    OTHER = "other"


@dataclass
class ScraperConfig:
    """Configuration for the datasheet scraper."""
    
    # Download settings
    download_dir: str = "./downloads/datasheets"
    max_concurrent_downloads: int = 5
    request_delay: float = 1.5  # Seconds between requests (be nice to servers)
    timeout: float = 60.0  # Request timeout in seconds
    max_retries: int = 3
    retry_delay: float = 5.0  # Seconds between retries
    
    # User agent (identify ourselves)
    user_agent: str = "C1IntelligenceHub/2.0 (Datasheet Indexer)"
    
    # PDF settings
    max_pdf_size_mb: int = 50  # Skip PDFs larger than this
    max_text_length: int = 100000  # Max characters to extract per PDF
    extract_tables: bool = True  # Use pdfplumber for table extraction
    
    # BigQuery settings
    gcp_project: str = field(default_factory=lambda: os.getenv("GCP_PROJECT_ID", ""))
    bq_dataset: str = "c1_intelligence"
    bq_datasheets_table: str = "datasheets"
    bq_scrape_runs_table: str = "datasheet_scrape_runs"
    bq_suppliers_table: str = "datasheet_suppliers"
    
    # Scraping limits
    max_datasheets_per_supplier: Optional[int] = None  # None = no limit
    test_mode: bool = False  # If True, limits to 3 per supplier
    
    # Feature flags
    enable_ocr: bool = False  # OCR fallback for scanned PDFs
    enable_playwright: bool = False  # For JS-heavy sites
    
    def __post_init__(self):
        """Ensure download directory exists."""
        Path(self.download_dir).mkdir(parents=True, exist_ok=True)
        
        if self.test_mode:
            self.max_datasheets_per_supplier = 3


@dataclass
class SupplierConfig:
    """Configuration for a specific supplier."""
    supplier_id: str
    supplier_name: str
    display_name: str
    website: str
    datasheet_index_url: str
    scraper_class: str
    is_enabled: bool = True
    requires_javascript: bool = False
    primary_materials: List[str] = field(default_factory=list)
    primary_industries: List[str] = field(default_factory=list)
    notes: str = ""


# Pre-configured suppliers
SUPPLIERS = {
    "hexcel": SupplierConfig(
        supplier_id="hexcel",
        supplier_name="Hexcel",
        display_name="Hexcel Corporation",
        website="https://www.hexcel.com",
        datasheet_index_url="https://www.hexcel.com/Resources/DataSheets/",
        scraper_class="HexcelScraper",
        primary_materials=["carbon_fiber", "prepreg", "core_honeycomb", "adhesive"],
        primary_industries=["aerospace", "defense", "space"],
    ),
    "owens_corning": SupplierConfig(
        supplier_id="owens_corning",
        supplier_name="Owens Corning",
        display_name="Owens Corning Composites",
        website="https://www.owenscorning.com",
        datasheet_index_url="https://www.owenscorning.com/en-us/composites/resources-support/technical-resources",
        scraper_class="OwensScorningScraper",
        primary_materials=["glass_fiber", "fabric"],
        primary_industries=["marine", "construction", "wind_energy", "automotive"],
    ),
    "toray": SupplierConfig(
        supplier_id="toray",
        supplier_name="Toray",
        display_name="Toray Composite Materials America",
        website="https://www.toraytac.com",
        datasheet_index_url="https://www.toraytac.com/resources/datasheets",
        scraper_class="TorayScraper",
        primary_materials=["carbon_fiber", "prepreg"],
        primary_industries=["aerospace", "automotive", "sports"],
    ),
    "polynt": SupplierConfig(
        supplier_id="polynt",
        supplier_name="Polynt-Reichhold",
        display_name="Polynt-Reichhold Group",
        website="https://www.polynt.com",
        datasheet_index_url="https://www.polynt.com/composites/",
        scraper_class="PolyntScraper",
        primary_materials=["resin_polyester", "resin_vinylester"],
        primary_industries=["marine", "construction", "transportation"],
    ),
    "gurit": SupplierConfig(
        supplier_id="gurit",
        supplier_name="Gurit",
        display_name="Gurit Holding AG",
        website="https://www.gurit.com",
        datasheet_index_url="https://www.gurit.com/products/",
        scraper_class="GuritScraper",
        primary_materials=["prepreg", "core_foam", "adhesive"],
        primary_industries=["wind_energy", "marine", "transportation"],
    ),
}


def get_supplier_config(supplier_id: str) -> Optional[SupplierConfig]:
    """Get configuration for a specific supplier."""
    return SUPPLIERS.get(supplier_id.lower().replace(" ", "_").replace("-", "_"))


def get_all_suppliers() -> List[SupplierConfig]:
    """Get all configured suppliers."""
    return list(SUPPLIERS.values())


def get_enabled_suppliers() -> List[SupplierConfig]:
    """Get all enabled suppliers."""
    return [s for s in SUPPLIERS.values() if s.is_enabled]
