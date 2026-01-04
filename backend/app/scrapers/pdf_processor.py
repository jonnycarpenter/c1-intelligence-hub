"""
PDF Processor
=============

Extracts text and tables from PDF datasheets.

Strategies:
1. pypdf - Primary text extraction (fast, handles most native PDFs)
2. pdfplumber - Table extraction and layout-aware text
3. OCR fallback - For scanned PDFs (optional, requires tesseract)
"""

import re
import logging
from pathlib import Path
from typing import Tuple, List, Dict, Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ExtractedContent:
    """Result of PDF text extraction."""
    text: str
    tables: List[Dict[str, Any]] = field(default_factory=list)
    page_count: int = 0
    success: bool = True
    method_used: str = "pypdf"
    error_message: Optional[str] = None
    
    @property
    def text_preview(self) -> str:
        """First 500 characters for display."""
        return self.text[:500] if self.text else ""
    
    @property
    def has_tables(self) -> bool:
        return len(self.tables) > 0


class PDFProcessor:
    """
    Multi-strategy PDF text extractor.
    
    Tries pypdf first, falls back to pdfplumber for better table handling,
    and optionally uses OCR for scanned documents.
    """
    
    def __init__(
        self,
        max_text_length: int = 100000,
        extract_tables: bool = True,
        enable_ocr: bool = False,
    ):
        self.max_text_length = max_text_length
        self.extract_tables = extract_tables
        self.enable_ocr = enable_ocr
        
        # Check available libraries
        self._pypdf_available = self._check_pypdf()
        self._pdfplumber_available = self._check_pdfplumber()
        self._ocr_available = self._check_ocr() if enable_ocr else False
        
        logger.info(
            f"PDFProcessor initialized: pypdf={self._pypdf_available}, "
            f"pdfplumber={self._pdfplumber_available}, ocr={self._ocr_available}"
        )
    
    def _check_pypdf(self) -> bool:
        try:
            import pypdf
            return True
        except ImportError:
            try:
                import PyPDF2
                return True
            except ImportError:
                return False
    
    def _check_pdfplumber(self) -> bool:
        try:
            import pdfplumber
            return True
        except ImportError:
            return False
    
    def _check_ocr(self) -> bool:
        try:
            import pytesseract
            import pdf2image
            # Quick check that tesseract is installed
            pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False
    
    def extract(self, pdf_path: Path) -> ExtractedContent:
        """
        Extract text and tables from a PDF file.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            ExtractedContent with text, tables, and metadata
        """
        pdf_path = Path(pdf_path)
        
        if not pdf_path.exists():
            return ExtractedContent(
                text="",
                success=False,
                error_message=f"File not found: {pdf_path}"
            )
        
        # Try pypdf first (fastest)
        if self._pypdf_available:
            result = self._extract_with_pypdf(pdf_path)
            if result.success and len(result.text.strip()) > 100:
                # If we need tables and got good text, try pdfplumber for tables only
                if self.extract_tables and self._pdfplumber_available:
                    tables = self._extract_tables_with_pdfplumber(pdf_path)
                    result.tables = tables
                return result
        
        # Try pdfplumber (better layout handling)
        if self._pdfplumber_available:
            result = self._extract_with_pdfplumber(pdf_path)
            if result.success and len(result.text.strip()) > 100:
                return result
        
        # OCR fallback for scanned PDFs
        if self._ocr_available and self.enable_ocr:
            result = self._extract_with_ocr(pdf_path)
            if result.success:
                return result
        
        # All methods failed
        return ExtractedContent(
            text="",
            success=False,
            error_message="All extraction methods failed or no text found"
        )
    
    def _extract_with_pypdf(self, pdf_path: Path) -> ExtractedContent:
        """Extract text using pypdf."""
        try:
            try:
                from pypdf import PdfReader
            except ImportError:
                from PyPDF2 import PdfReader
            
            text_parts = []
            
            with open(pdf_path, 'rb') as f:
                reader = PdfReader(f)
                page_count = len(reader.pages)
                
                for page_num, page in enumerate(reader.pages):
                    try:
                        page_text = page.extract_text()
                        if page_text:
                            text_parts.append(f"--- Page {page_num + 1} ---\n{page_text}")
                    except Exception as e:
                        logger.warning(f"Error extracting page {page_num}: {e}")
                        continue
            
            full_text = "\n\n".join(text_parts)
            
            # Truncate if too long
            if len(full_text) > self.max_text_length:
                full_text = full_text[:self.max_text_length] + "\n\n[Text truncated...]"
            
            # Clean up text
            full_text = self._clean_text(full_text)
            
            return ExtractedContent(
                text=full_text,
                page_count=page_count,
                success=True,
                method_used="pypdf"
            )
            
        except Exception as e:
            logger.error(f"pypdf extraction failed for {pdf_path}: {e}")
            return ExtractedContent(
                text="",
                success=False,
                method_used="pypdf",
                error_message=str(e)
            )
    
    def _extract_with_pdfplumber(self, pdf_path: Path) -> ExtractedContent:
        """Extract text and tables using pdfplumber."""
        try:
            import pdfplumber
            
            text_parts = []
            tables = []
            
            with pdfplumber.open(pdf_path) as pdf:
                page_count = len(pdf.pages)
                
                for page_num, page in enumerate(pdf.pages):
                    try:
                        # Extract text
                        page_text = page.extract_text()
                        if page_text:
                            text_parts.append(f"--- Page {page_num + 1} ---\n{page_text}")
                        
                        # Extract tables
                        if self.extract_tables:
                            page_tables = page.extract_tables()
                            for table_idx, table in enumerate(page_tables):
                                if table and len(table) > 1:  # Has header + data
                                    tables.append({
                                        "page": page_num + 1,
                                        "table_index": table_idx,
                                        "headers": table[0] if table else [],
                                        "rows": table[1:] if len(table) > 1 else [],
                                        "row_count": len(table) - 1,
                                    })
                    except Exception as e:
                        logger.warning(f"Error on page {page_num}: {e}")
                        continue
            
            full_text = "\n\n".join(text_parts)
            
            if len(full_text) > self.max_text_length:
                full_text = full_text[:self.max_text_length] + "\n\n[Text truncated...]"
            
            full_text = self._clean_text(full_text)
            
            return ExtractedContent(
                text=full_text,
                tables=tables,
                page_count=page_count,
                success=True,
                method_used="pdfplumber"
            )
            
        except Exception as e:
            logger.error(f"pdfplumber extraction failed for {pdf_path}: {e}")
            return ExtractedContent(
                text="",
                success=False,
                method_used="pdfplumber",
                error_message=str(e)
            )
    
    def _extract_tables_with_pdfplumber(self, pdf_path: Path) -> List[Dict[str, Any]]:
        """Extract only tables using pdfplumber."""
        try:
            import pdfplumber
            
            tables = []
            
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    try:
                        page_tables = page.extract_tables()
                        for table_idx, table in enumerate(page_tables):
                            if table and len(table) > 1:
                                tables.append({
                                    "page": page_num + 1,
                                    "table_index": table_idx,
                                    "headers": table[0] if table else [],
                                    "rows": table[1:] if len(table) > 1 else [],
                                    "row_count": len(table) - 1,
                                })
                    except Exception:
                        continue
            
            return tables
            
        except Exception as e:
            logger.warning(f"Table extraction failed: {e}")
            return []
    
    def _extract_with_ocr(self, pdf_path: Path) -> ExtractedContent:
        """Extract text using OCR (for scanned PDFs)."""
        try:
            import pytesseract
            from pdf2image import convert_from_path
            
            # Convert PDF pages to images
            images = convert_from_path(pdf_path, dpi=200)
            page_count = len(images)
            
            text_parts = []
            
            for page_num, image in enumerate(images):
                try:
                    page_text = pytesseract.image_to_string(image)
                    if page_text.strip():
                        text_parts.append(f"--- Page {page_num + 1} (OCR) ---\n{page_text}")
                except Exception as e:
                    logger.warning(f"OCR failed on page {page_num}: {e}")
                    continue
            
            full_text = "\n\n".join(text_parts)
            
            if len(full_text) > self.max_text_length:
                full_text = full_text[:self.max_text_length] + "\n\n[Text truncated...]"
            
            full_text = self._clean_text(full_text)
            
            return ExtractedContent(
                text=full_text,
                page_count=page_count,
                success=len(full_text.strip()) > 50,
                method_used="ocr"
            )
            
        except Exception as e:
            logger.error(f"OCR extraction failed for {pdf_path}: {e}")
            return ExtractedContent(
                text="",
                success=False,
                method_used="ocr",
                error_message=str(e)
            )
    
    def _clean_text(self, text: str) -> str:
        """Clean up extracted text."""
        # Remove excessive whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r' {2,}', ' ', text)
        
        # Remove common PDF artifacts
        text = re.sub(r'\x00', '', text)  # Null bytes
        text = re.sub(r'[\x01-\x08\x0b\x0c\x0e-\x1f]', '', text)  # Control chars
        
        return text.strip()


def extract_pdf_text(
    pdf_path: Path,
    max_length: int = 100000,
    extract_tables: bool = True,
    enable_ocr: bool = False,
) -> Tuple[str, bool]:
    """
    Convenience function to extract text from a PDF.
    
    Returns:
        Tuple of (extracted_text, success_bool)
    """
    processor = PDFProcessor(
        max_text_length=max_length,
        extract_tables=extract_tables,
        enable_ocr=enable_ocr,
    )
    result = processor.extract(pdf_path)
    return result.text, result.success
