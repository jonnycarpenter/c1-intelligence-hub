"""
Base Datasheet Scraper
======================

Abstract base class for supplier-specific scrapers.
Provides common functionality for downloading, processing, and tracking datasheets.
"""

import re
import json
import asyncio
import hashlib
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Set, Tuple
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

import httpx

from app.scrapers.config import ScraperConfig, MaterialCategory, SupplierConfig
from app.scrapers.pdf_processor import PDFProcessor, ExtractedContent
from app.scrapers.bq_loader import DatasheetRecord

logger = logging.getLogger(__name__)


@dataclass
class DatasheetInfo:
    """Information about a discovered datasheet (before download)."""
    url: str
    title: str
    supplier_name: str
    filename: str
    product_name: Optional[str] = None
    product_family: Optional[str] = None
    material_category: str = "other"
    material_subcategory: Optional[str] = None
    industries: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def datasheet_id(self) -> str:
        """Generate unique ID from URL hash."""
        return hashlib.sha256(self.url.encode()).hexdigest()[:16]


@dataclass
class DownloadResult:
    """Result of a datasheet download attempt."""
    info: DatasheetInfo
    success: bool
    local_path: Optional[str] = None
    file_size: int = 0
    file_hash: str = ""
    extracted_content: Optional[ExtractedContent] = None
    error_message: Optional[str] = None
    download_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_record(self, scrape_run_id: str) -> Optional[DatasheetRecord]:
        """Convert to a BigQuery record."""
        if not self.success or not self.extracted_content:
            return None
        
        return DatasheetRecord(
            datasheet_id=self.info.datasheet_id,
            supplier_name=self.info.supplier_name,
            product_name=self.info.product_name,
            product_family=self.info.product_family,
            title=self.info.title,
            url=self.info.url,
            filename=self.info.filename,
            material_category=self.info.material_category,
            material_subcategory=self.info.material_subcategory,
            industries=self.info.industries,
            extracted_text=self.extracted_content.text,
            text_preview=self.extracted_content.text_preview,
            page_count=self.extracted_content.page_count,
            text_extraction_success=self.extracted_content.success,
            file_size_bytes=self.file_size,
            file_hash=self.file_hash,
            scrape_run_id=scrape_run_id,
            downloaded_at=self.download_time,
        )


@dataclass
class ScrapeStats:
    """Statistics from a scraping run."""
    supplier_name: str
    datasheets_discovered: int = 0
    datasheets_downloaded: int = 0
    datasheets_skipped: int = 0
    datasheets_failed: int = 0
    errors: List[Dict[str, str]] = field(default_factory=list)
    duration_seconds: float = 0.0
    
    @property
    def status(self) -> str:
        if self.datasheets_failed == 0 and self.datasheets_downloaded > 0:
            return "success"
        elif self.datasheets_downloaded > 0:
            return "partial"
        else:
            return "failed"
    
    def add_error(self, url: str, error_type: str, message: str):
        self.errors.append({
            "url": url,
            "error_type": error_type,
            "message": str(message)[:500],
        })


class BaseDatasheetScraper(ABC):
    """
    Abstract base class for supplier-specific scrapers.
    
    Subclasses must implement:
    - discover_datasheets(): Find all datasheet URLs on the supplier's site
    
    The base class handles:
    - HTTP requests with retry logic
    - PDF downloading and processing
    - Rate limiting
    - Progress tracking
    """
    
    SUPPLIER_NAME: str = "Unknown"
    SUPPLIER_ID: str = "unknown"
    BASE_URL: str = ""
    
    def __init__(self, config: ScraperConfig, supplier_config: Optional[SupplierConfig] = None):
        self.config = config
        self.supplier_config = supplier_config
        
        # Set up download directory
        self.download_dir = Path(config.download_dir) / self.SUPPLIER_ID
        self.download_dir.mkdir(parents=True, exist_ok=True)
        
        # PDF processor
        self.pdf_processor = PDFProcessor(
            max_text_length=config.max_text_length,
            extract_tables=config.extract_tables,
            enable_ocr=config.enable_ocr,
        )
        
        # Track downloaded URLs to avoid duplicates
        self.downloaded_urls: Set[str] = set()
        self._load_download_history()
    
    def _load_download_history(self):
        """Load list of previously downloaded URLs."""
        history_file = self.download_dir / ".download_history.json"
        if history_file.exists():
            try:
                with open(history_file) as f:
                    self.downloaded_urls = set(json.load(f))
                logger.info(f"Loaded {len(self.downloaded_urls)} URLs from history for {self.SUPPLIER_NAME}")
            except Exception as e:
                logger.warning(f"Could not load download history: {e}")
    
    def _save_download_history(self):
        """Save download history to disk."""
        history_file = self.download_dir / ".download_history.json"
        try:
            with open(history_file, 'w') as f:
                json.dump(list(self.downloaded_urls), f)
        except Exception as e:
            logger.warning(f"Could not save download history: {e}")
    
    @abstractmethod
    async def discover_datasheets(self, client: httpx.AsyncClient) -> List[DatasheetInfo]:
        """
        Discover all available datasheets from the supplier's website.
        
        This method must be implemented by each supplier-specific scraper.
        
        Args:
            client: HTTP client for making requests
            
        Returns:
            List of DatasheetInfo objects describing found datasheets
        """
        raise NotImplementedError
    
    async def download_datasheet(
        self,
        info: DatasheetInfo,
        client: httpx.AsyncClient,
        existing_hashes: Dict[str, str] = None,
    ) -> DownloadResult:
        """
        Download and process a single datasheet PDF.
        
        Args:
            info: Datasheet information
            client: HTTP client
            existing_hashes: Map of datasheet_id -> file_hash for change detection
            
        Returns:
            DownloadResult with success status and extracted content
        """
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
            
            # Check content type
            content_type = response.headers.get("content-type", "")
            if "pdf" not in content_type.lower() and not info.url.lower().endswith(".pdf"):
                return DownloadResult(
                    info=info,
                    success=False,
                    error_message=f"Not a PDF: {content_type}"
                )
            
            content = response.content
            file_size = len(content)
            
            # Check file size
            if file_size > self.config.max_pdf_size_mb * 1024 * 1024:
                return DownloadResult(
                    info=info,
                    success=False,
                    error_message=f"File too large: {file_size / 1024 / 1024:.1f}MB"
                )
            
            # Calculate hash for change detection
            file_hash = hashlib.sha256(content).hexdigest()
            
            # Check if content unchanged (skip reprocessing)
            if info.datasheet_id in existing_hashes:
                if existing_hashes[info.datasheet_id] == file_hash:
                    logger.debug(f"Content unchanged, skipping: {info.title}")
                    return DownloadResult(
                        info=info,
                        success=False,  # Mark as skipped
                        error_message="Content unchanged"
                    )
            
            # Save to disk
            safe_filename = self._safe_filename(info.filename or info.title)
            if not safe_filename.endswith(".pdf"):
                safe_filename += ".pdf"
            
            local_path = self.download_dir / safe_filename
            
            # Handle duplicate filenames
            counter = 1
            while local_path.exists():
                stem = safe_filename.rsplit(".", 1)[0]
                local_path = self.download_dir / f"{stem}_{counter}.pdf"
                counter += 1
            
            local_path.write_bytes(content)
            
            # Extract text
            extracted = self.pdf_processor.extract(local_path)
            
            # Mark as downloaded
            self.downloaded_urls.add(info.url)
            
            logger.info(f"Downloaded: {info.title} ({file_size / 1024:.1f}KB)")
            
            return DownloadResult(
                info=info,
                success=True,
                local_path=str(local_path),
                file_size=file_size,
                file_hash=file_hash,
                extracted_content=extracted,
            )
            
        except Exception as e:
            logger.error(f"Error downloading {info.url}: {e}")
            return DownloadResult(
                info=info,
                success=False,
                error_message=str(e)
            )
    
    async def _fetch_with_retry(
        self,
        client: httpx.AsyncClient,
        url: str,
    ) -> Optional[httpx.Response]:
        """Fetch URL with retry logic."""
        for attempt in range(self.config.max_retries):
            try:
                response = await client.get(
                    url,
                    timeout=self.config.timeout,
                    follow_redirects=True,
                )
                response.raise_for_status()
                return response
                
            except httpx.HTTPStatusError as e:
                if e.response.status_code in (404, 403, 410):
                    # Don't retry client errors
                    logger.warning(f"HTTP {e.response.status_code} for {url}")
                    return None
                logger.warning(f"HTTP error (attempt {attempt + 1}): {e}")
                
            except httpx.RequestError as e:
                logger.warning(f"Request error (attempt {attempt + 1}): {e}")
            
            if attempt < self.config.max_retries - 1:
                await asyncio.sleep(self.config.retry_delay * (attempt + 1))
        
        return None
    
    async def run(
        self,
        existing_hashes: Dict[str, str] = None,
    ) -> Tuple[List[DownloadResult], ScrapeStats]:
        """
        Run the full scraping process for this supplier.
        
        Args:
            existing_hashes: Map of datasheet_id -> file_hash for change detection
            
        Returns:
            Tuple of (download_results, statistics)
        """
        start_time = datetime.now(timezone.utc)
        stats = ScrapeStats(supplier_name=self.SUPPLIER_NAME)
        results = []
        
        logger.info(f"Starting scrape for {self.SUPPLIER_NAME}...")
        
        async with httpx.AsyncClient(
            headers={"User-Agent": self.config.user_agent},
            follow_redirects=True,
        ) as client:
            
            # Discover datasheets
            try:
                datasheets = await self.discover_datasheets(client)
                stats.datasheets_discovered = len(datasheets)
                logger.info(f"Discovered {len(datasheets)} datasheets")
            except Exception as e:
                logger.error(f"Discovery failed: {e}")
                stats.add_error("", "discovery_error", str(e))
                stats.duration_seconds = (datetime.now(timezone.utc) - start_time).total_seconds()
                return results, stats
            
            # Apply limit if configured
            if self.config.max_datasheets_per_supplier:
                datasheets = datasheets[:self.config.max_datasheets_per_supplier]
                logger.info(f"Limited to {len(datasheets)} datasheets")
            
            # Download with concurrency control
            semaphore = asyncio.Semaphore(self.config.max_concurrent_downloads)
            
            async def download_with_limit(info: DatasheetInfo) -> DownloadResult:
                async with semaphore:
                    await asyncio.sleep(self.config.request_delay)
                    return await self.download_datasheet(info, client, existing_hashes)
            
            # Process all datasheets
            tasks = [download_with_limit(ds) for ds in datasheets]
            download_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for result in download_results:
                if isinstance(result, Exception):
                    stats.datasheets_failed += 1
                    stats.add_error("", "exception", str(result))
                elif isinstance(result, DownloadResult):
                    if result.success:
                        stats.datasheets_downloaded += 1
                        results.append(result)
                    elif result.error_message == "Content unchanged":
                        stats.datasheets_skipped += 1
                    else:
                        stats.datasheets_failed += 1
                        if result.error_message:
                            stats.add_error(result.info.url, "download_error", result.error_message)
        
        # Save download history
        self._save_download_history()
        
        stats.duration_seconds = (datetime.now(timezone.utc) - start_time).total_seconds()
        
        logger.info(
            f"Completed {self.SUPPLIER_NAME}: "
            f"{stats.datasheets_downloaded} downloaded, "
            f"{stats.datasheets_skipped} skipped, "
            f"{stats.datasheets_failed} failed "
            f"in {stats.duration_seconds:.1f}s"
        )
        
        return results, stats
    
    # =========================================================================
    # HELPER METHODS FOR SUBCLASSES
    # =========================================================================
    
    def _safe_filename(self, name: str) -> str:
        """Convert a string to a safe filename."""
        safe = re.sub(r'[<>:"/\\|?*]', '', name)
        safe = re.sub(r'\s+', '_', safe)
        safe = safe.strip('._')
        if len(safe) > 100:
            safe = safe[:100]
        return safe or "datasheet"
    
    def _categorize_material(self, text: str) -> str:
        """Guess material category from text."""
        text = text.lower()
        
        # Carbon fiber
        if any(kw in text for kw in ["carbon fiber", "carbon fibre", "cfrp", "t300", "t700", "t800", "im7", "as4"]):
            if "prepreg" in text:
                return MaterialCategory.PREPREG.value
            return MaterialCategory.CARBON_FIBER.value
        
        # Glass fiber
        if any(kw in text for kw in ["glass fiber", "glass fibre", "e-glass", "s-glass", "fiberglass"]):
            return MaterialCategory.GLASS_FIBER.value
        
        # Aramid
        if any(kw in text for kw in ["aramid", "kevlar", "twaron"]):
            return MaterialCategory.ARAMID_FIBER.value
        
        # Prepreg
        if "prepreg" in text:
            return MaterialCategory.PREPREG.value
        
        # Resins
        if any(kw in text for kw in ["epoxy", "epoxide"]):
            return MaterialCategory.RESIN_EPOXY.value
        if any(kw in text for kw in ["polyester", "orthophthalic", "isophthalic"]):
            return MaterialCategory.RESIN_POLYESTER.value
        if any(kw in text for kw in ["vinyl ester", "vinylester", "derakane"]):
            return MaterialCategory.RESIN_VINYLESTER.value
        if any(kw in text for kw in ["phenolic"]):
            return MaterialCategory.RESIN_PHENOLIC.value
        
        # Core materials
        if any(kw in text for kw in ["honeycomb", "hexweb", "nomex core"]):
            return MaterialCategory.CORE_HONEYCOMB.value
        if any(kw in text for kw in ["foam core", "pvc foam", "pet foam", "divinycell", "airex", "corecell"]):
            return MaterialCategory.CORE_FOAM.value
        if "balsa" in text:
            return MaterialCategory.CORE_BALSA.value
        
        # Adhesives
        if any(kw in text for kw in ["adhesive", "film adhesive", "paste adhesive"]):
            return MaterialCategory.ADHESIVE.value
        
        # Fabrics
        if any(kw in text for kw in ["fabric", "woven", "multiaxial", "unidirectional"]):
            return MaterialCategory.FABRIC.value
        
        return MaterialCategory.OTHER.value
    
    def _guess_industries(self, text: str) -> List[str]:
        """Guess applicable industries from text."""
        text = text.lower()
        industries = []
        
        industry_keywords = {
            "aerospace": ["aerospace", "aircraft", "aviation", "boeing", "airbus"],
            "automotive": ["automotive", "vehicle", "car", "ev", "electric vehicle"],
            "wind_energy": ["wind", "turbine", "blade", "renewable"],
            "marine": ["marine", "boat", "yacht", "ship", "naval"],
            "construction": ["construction", "building", "infrastructure"],
            "defense": ["defense", "defence", "military", "ballistic"],
            "sports": ["sports", "bicycle", "ski", "tennis", "golf"],
            "space": ["space", "satellite", "rocket", "launch vehicle"],
            "industrial": ["industrial", "pipe", "tank", "vessel"],
        }
        
        for industry, keywords in industry_keywords.items():
            if any(kw in text for kw in keywords):
                industries.append(industry)
        
        return industries if industries else ["general"]
    
    def _make_absolute_url(self, href: str, base_url: str = None) -> str:
        """Convert relative URL to absolute."""
        base = base_url or self.BASE_URL
        if href.startswith("http"):
            return href
        return urljoin(base, href)
