"""
Supplier-specific scrapers.

Each scraper implements the discover_datasheets() method
with custom logic for crawling that supplier's website.
"""

from app.scrapers.suppliers.hexcel import HexcelScraper
from app.scrapers.suppliers.owens_corning import OwensCorningScraper
from app.scrapers.suppliers.toray import TorayScraper
from app.scrapers.suppliers.polynt import PolyntScraper
from app.scrapers.suppliers.gurit import GuritScraper
from app.scrapers.suppliers.matweb import MatWebScraper, TorayMatWebScraper, OwensCorningMatWebScraper

# Registry of all available scrapers
# Note: Toray and Owens Corning sites have WAF protection, so we use MatWeb as primary source
SCRAPER_REGISTRY = {
    "hexcel": HexcelScraper,
    "owens_corning": OwensCorningMatWebScraper,  # Using MatWeb - site has Sucuri WAF
    "owenscorning": OwensCorningMatWebScraper,
    "toray": TorayMatWebScraper,  # Using MatWeb - site has Sucuri WAF
    "polynt": PolyntScraper,
    "polynt_reichhold": PolyntScraper,
    "gurit": GuritScraper,
    # MatWeb scrapers (alternative sources)
    "matweb": MatWebScraper,
    "toray_matweb": TorayMatWebScraper,
    "owens_corning_matweb": OwensCorningMatWebScraper,
}


def get_scraper_class(supplier_id: str):
    """Get the scraper class for a supplier."""
    key = supplier_id.lower().replace(" ", "_").replace("-", "_")
    return SCRAPER_REGISTRY.get(key)


__all__ = [
    "HexcelScraper",
    "OwensCorningScraper",
    "TorayScraper",
    "PolyntScraper",
    "GuritScraper",
    "MatWebScraper",
    "TorayMatWebScraper",
    "OwensCorningMatWebScraper",
    "SCRAPER_REGISTRY",
    "get_scraper_class",
]
