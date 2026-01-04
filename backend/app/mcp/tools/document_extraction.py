"""Document extraction tools for Product Maven agent."""

from typing import Optional, List
import httpx
from pathlib import Path
from langchain_core.tools import tool

from app.config.settings import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Downloads directory
DOWNLOADS_DIR = settings.base_dir / "downloads"
DOWNLOADS_DIR.mkdir(exist_ok=True)


@tool
def crawl_for_documents(
    url: str,
    file_types: Optional[List[str]] = None,
    filter_keywords: Optional[List[str]] = None,
) -> str:
    """
    Crawl a webpage to find PDF and document links.
    
    Use this to discover spec sheets, datasheets, and technical documents
    on competitor websites.
    
    Args:
        url: The webpage URL to crawl for documents
        file_types: Types of files to find (default: ['pdf', 'pptx', 'xlsx'])
        filter_keywords: Keywords to filter documents by (in filename or link text)
    
    Returns:
        JSON string with list of found document links
    """
    logger.info(f"Crawling for documents: {url}")
    
    file_types = file_types or ["pdf", "pptx", "xlsx"]
    
    try:
        with httpx.Client(timeout=30, follow_redirects=True) as client:
            response = client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (compatible; C1IntelHub/2.0)"
            })
            response.raise_for_status()
            html = response.text
        
        # Parse HTML to find document links
        from html.parser import HTMLParser
        
        class LinkParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.links = []
                
            def handle_starttag(self, tag, attrs):
                if tag == "a":
                    href = dict(attrs).get("href", "")
                    text = ""
                    for name, value in attrs:
                        if name == "title" or name == "aria-label":
                            text = value
                    self.links.append({"href": href, "text": text})
        
        parser = LinkParser()
        parser.feed(html)
        
        # Filter for document links
        documents = []
        for link in parser.links:
            href = link["href"].lower()
            
            # Check file type
            is_doc = any(f".{ft}" in href for ft in file_types)
            if not is_doc:
                continue
            
            # Check keywords if provided
            if filter_keywords:
                text_to_check = (link["href"] + " " + link["text"]).lower()
                if not any(kw.lower() in text_to_check for kw in filter_keywords):
                    continue
            
            # Resolve relative URLs
            full_url = link["href"]
            if not full_url.startswith("http"):
                from urllib.parse import urljoin
                full_url = urljoin(url, full_url)
            
            documents.append({
                "url": full_url,
                "filename": Path(full_url).name,
                "text": link["text"],
            })
        
        import json
        return json.dumps({
            "source_url": url,
            "documents_found": len(documents),
            "documents": documents[:20],  # Limit results
        }, indent=2)
        
    except Exception as e:
        logger.error(f"Document crawl error: {e}")
        return f'{{"error": "{str(e)}"}}'


@tool
def extract_pdf_content(
    url: str,
    pages: Optional[List[int]] = None,
) -> str:
    """
    Download and extract text content from a PDF document.
    
    Use this to read spec sheets, datasheets, and technical documents.
    
    Args:
        url: Direct URL to the PDF file
        pages: Specific page numbers to extract (1-indexed). If not provided, extracts all.
    
    Returns:
        JSON string with extracted text, tables, and metadata
    """
    logger.info(f"Extracting PDF content: {url}")
    
    try:
        # Download PDF
        with httpx.Client(timeout=60, follow_redirects=True) as client:
            response = client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (compatible; C1IntelHub/2.0)"
            })
            response.raise_for_status()
            pdf_bytes = response.content
        
        # Save temporarily
        filename = Path(url).name or "document.pdf"
        filepath = DOWNLOADS_DIR / filename
        filepath.write_bytes(pdf_bytes)
        
        # Extract content using pypdf
        try:
            from pypdf import PdfReader
            
            reader = PdfReader(filepath)
            total_pages = len(reader.pages)
            
            # Determine which pages to extract
            if pages:
                page_indices = [p - 1 for p in pages if 0 < p <= total_pages]
            else:
                page_indices = range(min(total_pages, 10))  # Limit to first 10 pages
            
            extracted_text = []
            for i in page_indices:
                page = reader.pages[i]
                text = page.extract_text()
                if text:
                    extracted_text.append({
                        "page": i + 1,
                        "text": text.strip()[:5000],  # Limit per page
                    })
            
            import json
            return json.dumps({
                "url": url,
                "filename": filename,
                "total_pages": total_pages,
                "pages_extracted": len(extracted_text),
                "content": extracted_text,
            }, indent=2)
            
        finally:
            # Clean up
            if filepath.exists():
                filepath.unlink()
        
    except Exception as e:
        logger.error(f"PDF extraction error: {e}")
        return f'{{"error": "{str(e)}"}}'
