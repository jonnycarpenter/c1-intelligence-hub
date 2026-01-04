"""
Logo.dev Service for Company Logo Fetching

Provides:
- Domain extraction from URLs and company names
- Logo proxy endpoint to keep API token server-side
- Company name to domain heuristics
"""

import os
import re
import httpx
from typing import Optional, Tuple
from urllib.parse import urlparse
from functools import lru_cache

# Import settings to get API keys
from app.config.settings import settings

from app.utils.logger import get_logger

logger = get_logger(__name__)


# =============================================================================
# DOMAIN EXTRACTION UTILITIES
# =============================================================================

def extract_domain(url: str) -> str:
    """
    Extract clean domain from URL.
    
    Examples:
        "https://www.gulfstream.com/about" -> "gulfstream.com"
        "compositesone.com" -> "compositesone.com"
        "http://www.example.co.uk/page" -> "example.co.uk"
    """
    if not url:
        return ""
    
    try:
        # Add protocol if missing
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
        
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path.split("/")[0]
        
        # Remove www. prefix
        if domain.startswith("www."):
            domain = domain[4:]
        
        # Remove port if present
        domain = domain.split(":")[0]
        
        return domain.lower().strip()
    except Exception as e:
        logger.debug(f"Error extracting domain from {url}: {e}")
        return ""


def parse_company_from_linkedin(title: str, text: str) -> Tuple[str, str]:
    """
    Extract company name and domain from LinkedIn profile data.
    
    LinkedIn titles are often formatted as:
    - "Name - Title - Company | LinkedIn"
    - "Name | Title at Company | LinkedIn"
    
    Returns:
        (company_name, company_domain)
    """
    company_name = ""
    company_domain = ""
    
    # Try title first: "Name - Title - Company | LinkedIn"
    if " - " in title:
        parts = title.split(" - ")
        if len(parts) >= 3:
            # Last part before LinkedIn
            company_part = parts[-1].split("|")[0].strip()
            if company_part.lower() != "linkedin":
                company_name = company_part
        elif len(parts) == 2:
            # Could be "Name - Title at Company"
            if " at " in parts[1]:
                company_name = parts[1].split(" at ")[-1].split("|")[0].strip()
    
    # Try "at Company" pattern in title
    if not company_name and " at " in title:
        company_name = title.split(" at ")[-1].split("|")[0].split("-")[0].strip()
    
    # Try to find company in text body
    if not company_name and text:
        # Look for "at Company" pattern
        at_pattern = re.search(r'\bat\s+([A-Z][A-Za-z\s&\-\.]+?)(?:\s+as|\s+where|\s+since|\s*[,.]|\s+\d)', text)
        if at_pattern:
            company_name = at_pattern.group(1).strip()
        
        # Look for "Company Name" followed by title indicators
        company_pattern = re.search(r'([A-Z][A-Za-z\s&\-\.]+?)\s*(?:\||[-–])\s*(?:Manager|Director|VP|President|CEO|CFO|CTO|Head)', text)
        if not company_name and company_pattern:
            company_name = company_pattern.group(1).strip()
    
    # Clean up company name
    if company_name:
        # Remove common suffixes that aren't helpful
        company_name = re.sub(r'\s*\|\s*LinkedIn.*$', '', company_name, flags=re.IGNORECASE)
        company_name = company_name.strip()
    
    # Derive domain from company name
    if company_name:
        company_domain = company_name_to_domain(company_name)
    
    return company_name, company_domain


def company_name_to_domain(company_name: str) -> str:
    """
    Convert company name to likely domain.
    
    Uses heuristics to handle common cases:
    - "Gulfstream Aerospace" -> "gulfstream.com"
    - "Spirit AeroSystems" -> "spiritaero.com" 
    - "General Electric" -> "ge.com" (known mapping)
    - "3M Company" -> "3m.com"
    """
    if not company_name:
        return ""
    
    # Known company name -> domain mappings for accuracy
    KNOWN_DOMAINS = {
        "general electric": "ge.com",
        "ge": "ge.com",
        "ibm": "ibm.com",
        "international business machines": "ibm.com",
        "3m": "3m.com",
        "3m company": "3m.com",
        "boeing": "boeing.com",
        "the boeing company": "boeing.com",
        "airbus": "airbus.com",
        "lockheed martin": "lockheedmartin.com",
        "northrop grumman": "northropgrumman.com",
        "raytheon": "rtx.com",
        "rtx": "rtx.com",
        "spirit aerosystems": "spiritaero.com",
        "gulfstream": "gulfstream.com",
        "gulfstream aerospace": "gulfstream.com",
        "textron": "textron.com",
        "honeywell": "honeywell.com",
        "hexcel": "hexcel.com",
        "hexcel corporation": "hexcel.com",
        "toray": "toray.com",
        "toray industries": "toray.com",
        "solvay": "solvay.com",
        "huntsman": "huntsman.com",
        "huntsman corporation": "huntsman.com",
        "owens corning": "owenscorning.com",
        "johns manville": "jm.com",
        "ppg": "ppg.com",
        "ppg industries": "ppg.com",
        "dupont": "dupont.com",
        "basf": "basf.com",
        "dow": "dow.com",
        "dow chemical": "dow.com",
        "composites one": "compositesone.com",
        "composites one llc": "compositesone.com",
    }
    
    # Check known mappings first
    name_lower = company_name.lower().strip()
    if name_lower in KNOWN_DOMAINS:
        return KNOWN_DOMAINS[name_lower]
    
    # Heuristic: Remove common suffixes and create domain
    clean_name = name_lower
    
    # Remove common corporate suffixes
    suffixes_to_remove = [
        r'\s*,?\s*inc\.?$',
        r'\s*,?\s*llc\.?$',
        r'\s*,?\s*ltd\.?$',
        r'\s*,?\s*corp\.?$',
        r'\s*,?\s*corporation$',
        r'\s*,?\s*company$',
        r'\s*,?\s*co\.?$',
        r'\s*,?\s*group$',
        r'\s*,?\s*holdings?$',
        r'\s*,?\s*international$',
        r'\s*,?\s*industries$',
        r'\s*,?\s*enterprises?$',
    ]
    
    for suffix in suffixes_to_remove:
        clean_name = re.sub(suffix, '', clean_name, flags=re.IGNORECASE)
    
    # Remove non-alphanumeric (keep only letters and numbers)
    domain_base = re.sub(r'[^a-z0-9]', '', clean_name)
    
    # Handle empty result
    if not domain_base:
        return ""
    
    return f"{domain_base}.com"


def extract_company_from_news(title: str, text: str) -> str:
    """
    Try to extract the main company mentioned in a news article.
    
    Returns the likely domain of the primary company mentioned.
    """
    combined = f"{title} {text}"
    
    # Patterns for company mentions in news
    patterns = [
        # "Company announces/expands/acquires..."
        r'([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*)\s+(?:announces?|expands?|acquires?|launches?|opens?|builds?|invests?)',
        # "Company Inc/Corp/LLC..."
        r'([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*)\s+(?:Inc|Corp|LLC|Ltd|Company)',
        # Leading company name at start
        r'^([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)?)\s+(?:to\s+|will\s+|has\s+|is\s+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, combined)
        if match:
            company = match.group(1).strip()
            # Filter out common false positives
            if company.lower() not in ['the', 'a', 'an', 'new', 'breaking', 'report', 'press', 'news']:
                return company_name_to_domain(company)
    
    return ""


# =============================================================================
# LOGO SERVICE
# =============================================================================

class LogoService:
    """Service for fetching company logos via Logo.dev."""
    
    def __init__(self):
        self.token = settings.logo_dev_token
        if not self.token:
            logger.warning("LOGO_DEV_TOKEN not found in environment variables")
        else:
            logger.info(f"Logo.dev service initialized with token: {self.token[:10]}...")
    
    def get_logo_url(self, domain: str, size: int = 128) -> Optional[str]:
        """
        Get the Logo.dev URL for a domain.
        
        This returns the URL that can be used by the frontend logo proxy.
        The actual token is added by the proxy endpoint.
        
        Args:
            domain: Company domain (e.g., "gulfstream.com")
            size: Logo size in pixels (default 128)
        
        Returns:
            Logo URL path for the proxy, or None if no domain
        """
        if not domain:
            return None
        
        # Clean the domain
        domain = extract_domain(domain) if "/" in domain else domain.lower().strip()
        
        if not domain:
            return None
        
        # Return the proxy path (frontend will call /api/pipeline/logo/{domain})
        return f"/api/pipeline/logo/{domain}"
    
    async def fetch_logo(self, domain: str) -> Optional[bytes]:
        """
        Fetch logo image bytes from Logo.dev.
        
        This is called by the proxy endpoint.
        
        Args:
            domain: Company domain
        
        Returns:
            Image bytes or None if not found
        """
        if not self.token:
            logger.error("Cannot fetch logo: LOGO_DEV_TOKEN not configured")
            return None
        
        if not domain:
            return None
        
        url = f"https://img.logo.dev/{domain}?token={self.token}&size=128&format=png"
        
        logger.info(f"Fetching logo from: https://img.logo.dev/{domain}?token=***&size=128&format=png")
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                
                logger.info(f"Logo.dev response for {domain}: status={response.status_code}, content-length={len(response.content)}")
                
                if response.status_code == 200:
                    return response.content
                else:
                    logger.warning(f"Logo.dev returned {response.status_code} for {domain}: {response.text[:200]}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error fetching logo for {domain}: {e}")
            return None


# Singleton instance
logo_service = LogoService()
