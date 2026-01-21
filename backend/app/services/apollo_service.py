"""
Apollo.io Service for Company Enrichment and Contact Discovery

Provides:
- Organization enrichment (FREE - no credits)
- People/contact search (FREE - no credits)
- People match/reveal (1 CREDIT per reveal)

Apollo replaces AbstractAPI and provides superior firmographic data plus contact intelligence.
"""

import os
import httpx
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import lru_cache

from app.config.settings import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class ApolloOrganization:
    """Enriched organization data from Apollo."""
    # Identity
    name: str
    domain: str
    description: Optional[str] = None
    logo_url: Optional[str] = None
    
    # Firmographics
    employee_count: Optional[int] = None
    founded_year: Optional[int] = None
    industry: Optional[str] = None
    annual_revenue: Optional[float] = None
    revenue_printed: Optional[str] = None  # e.g., "1.9B"
    
    # Location
    street_address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    raw_address: Optional[str] = None
    
    # Contact
    phone: Optional[str] = None
    website_url: Optional[str] = None
    
    # Social
    linkedin_url: Optional[str] = None
    twitter_url: Optional[str] = None
    facebook_url: Optional[str] = None
    
    # Stock (if public)
    ticker: Optional[str] = None
    exchange: Optional[str] = None
    
    # Tech & Keywords
    technologies: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    
    # Industry Codes
    sic_codes: List[str] = field(default_factory=list)
    naics_codes: List[str] = field(default_factory=list)
    
    # Additional Firmographics
    retail_location_count: Optional[int] = None
    suborganizations: List[str] = field(default_factory=list)


@dataclass
class ApolloContactTeaser:
    """Contact teaser (preview) from Apollo people search - no credits used."""
    id: str  # Needed for reveal
    first_name: str
    last_name: Optional[str] = None  # Full last name from Apollo API
    title: Optional[str] = None
    seniority: Optional[str] = None
    departments: List[str] = field(default_factory=list)  # e.g., ["purchasing", "operations"]
    company_name: Optional[str] = None
    company_domain: Optional[str] = None
    has_email: bool = False
    has_phone: bool = False
    has_city: bool = False
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    last_updated: Optional[str] = None
    linkedin_url: Optional[str] = None


@dataclass
class ApolloContactRevealed:
    """Full contact details from Apollo people match - costs 1 credit."""
    # Identity
    id: str
    name: str
    first_name: str
    last_name: str
    title: Optional[str] = None
    seniority: Optional[str] = None
    photo_url: Optional[str] = None
    
    # Contact Info
    email: Optional[str] = None
    email_status: Optional[str] = None  # "verified", "guessed", etc.
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    twitter_url: Optional[str] = None
    
    # Location
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    timezone: Optional[str] = None
    
    # Employment History
    employment_history: List[Dict[str, Any]] = field(default_factory=list)
    
    # Current Company (bundled enrichment)
    company_name: Optional[str] = None
    company_domain: Optional[str] = None
    company_industry: Optional[str] = None
    company_employee_count: Optional[int] = None
    company_revenue_printed: Optional[str] = None
    company_phone: Optional[str] = None
    company_linkedin_url: Optional[str] = None


# =============================================================================
# CREDIT TRACKER
# =============================================================================

class CreditTracker:
    """Track Apollo API credit usage."""
    
    def __init__(self, monthly_limit: int = 2500):
        self.monthly_limit = monthly_limit
        self.used = 0
        self.reset_date = self._next_reset()
    
    def _next_reset(self) -> datetime:
        """First of next month."""
        today = datetime.now()
        if today.month == 12:
            return datetime(today.year + 1, 1, 1)
        return datetime(today.year, today.month + 1, 1)
    
    def check_reset(self):
        """Reset counter if new month."""
        if datetime.now() >= self.reset_date:
            self.used = 0
            self.reset_date = self._next_reset()
    
    def can_reveal(self) -> bool:
        """Check if we have credits available."""
        self.check_reset()
        return self.used < self.monthly_limit
    
    def record_reveal(self):
        """Record a credit usage."""
        self.check_reset()
        self.used += 1
    
    def remaining(self) -> int:
        """Credits remaining this month."""
        self.check_reset()
        return self.monthly_limit - self.used
    
    def usage_report(self) -> dict:
        """Current usage stats."""
        self.check_reset()
        return {
            "used": self.used,
            "remaining": self.remaining(),
            "limit": self.monthly_limit,
            "reset_date": self.reset_date.isoformat(),
            "utilization": f"{(self.used / self.monthly_limit) * 100:.1f}%"
        }


# =============================================================================
# APOLLO SERVICE
# =============================================================================

class ApolloService:
    """Service for interacting with Apollo.io API."""
    
    # Common title mappings for the composites industry
    BUYER_TITLES = [
        "Purchasing Manager",
        "Materials Manager",
        "Procurement Manager",
        "Supply Chain Manager",
        "VP Supply Chain",
        "Director of Procurement",
        "Buyer",
        "Strategic Sourcing Manager",
        "Commodity Manager",
    ]
    
    TECHNICAL_TITLES = [
        "Engineering Manager",
        "Materials Engineer",
        "Process Engineer",
        "VP Engineering",
        "Technical Director",
        "R&D Manager",
    ]
    
    EXECUTIVE_TITLES = [
        "CEO",
        "President",
        "COO",
        "General Manager",
        "VP Operations",
        "Plant Manager",
    ]
    
    def __init__(self):
        self.api_key = settings.apollo_api_key
        self.base_url = "https://api.apollo.io/api/v1"
        self.credits = CreditTracker(monthly_limit=2500)
        
        if not self.api_key:
            logger.warning("APOLLO_API_KEY not found - set in .env file")
        else:
            logger.info("Apollo.io service initialized")
    
    @property
    def headers(self) -> Dict[str, str]:
        """Get headers for Apollo API requests."""
        return {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "X-Api-Key": self.api_key,
        }
    
    def _check_configured(self) -> None:
        """Check if API key is configured."""
        if not self.api_key:
            raise ValueError("Apollo API key not configured. Set APOLLO_API_KEY environment variable.")
    
    # =========================================================================
    # Organization Enrichment (FREE)
    # =========================================================================
    
    async def enrich_organization(self, domain: str) -> Optional[ApolloOrganization]:
        """
        Get comprehensive company data from Apollo.
        
        This is FREE and doesn't consume credits.
        
        Args:
            domain: Company domain (e.g., "hexcel.com")
            
        Returns:
            ApolloOrganization with firmographics, or None if not found
        """
        self._check_configured()
        
        logger.info(f"[Apollo] Enriching organization: {domain}")
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/organizations/enrich",
                    headers=self.headers,
                    params={"domain": domain},
                    timeout=10.0,
                )
                
                if response.status_code != 200:
                    logger.warning(f"[Apollo] Enrich failed for {domain}: {response.status_code}")
                    return None
                
                data = response.json()
                org = data.get("organization", {})
                
                if not org:
                    return None
                
                return ApolloOrganization(
                    # Identity
                    name=org.get("name", ""),
                    domain=org.get("primary_domain", domain),
                    description=org.get("short_description"),
                    logo_url=org.get("logo_url"),
                    
                    # Firmographics
                    employee_count=org.get("estimated_num_employees"),
                    founded_year=org.get("founded_year"),
                    industry=org.get("industry"),
                    annual_revenue=org.get("annual_revenue"),
                    revenue_printed=org.get("annual_revenue_printed"),
                    
                    # Location
                    street_address=org.get("street_address"),
                    city=org.get("city"),
                    state=org.get("state"),
                    postal_code=org.get("postal_code"),
                    country=org.get("country"),
                    raw_address=org.get("raw_address"),
                    
                    # Contact
                    phone=org.get("phone"),
                    website_url=org.get("website_url"),
                    
                    # Social
                    linkedin_url=org.get("linkedin_url"),
                    twitter_url=org.get("twitter_url"),
                    facebook_url=org.get("facebook_url"),
                    
                    # Stock
                    ticker=org.get("publicly_traded_symbol"),
                    exchange=org.get("publicly_traded_exchange"),
                    
                    # Tech & Keywords
                    technologies=[t.get("name") for t in org.get("current_technologies", []) if t.get("name")],
                    keywords=org.get("keywords", [])[:20],
                    
                    # Codes
                    sic_codes=org.get("sic_codes", []),
                    naics_codes=org.get("naics_codes", []),
                    
                    # Additional Firmographics
                    retail_location_count=org.get("retail_location_count"),
                    suborganizations=[s.get("name") for s in org.get("suborganizations", []) if s.get("name")],
                )
                
        except Exception as e:
            logger.error(f"[Apollo] Error enriching {domain}: {e}")
            return None
    
    # =========================================================================
    # People Search (FREE)
    # =========================================================================
    
    async def search_contacts(
        self,
        organization_name: Optional[str] = None,
        organization_domain: Optional[str] = None,
        titles: Optional[List[str]] = None,
        seniorities: Optional[List[str]] = None,
        department: Optional[str] = None,
        per_page: int = 10,
    ) -> List[ApolloContactTeaser]:
        """
        Search for contacts at a company.
        
        This is FREE and doesn't consume credits (returns teasers only).
        
        Args:
            organization_name: Company name (e.g., "Hexcel")
            organization_domain: Company domain (e.g., "hexcel.com")
            titles: Specific job titles to search
            seniorities: Seniority levels (e.g., ["manager", "director", "vp"])
            department: Department filter - will be mapped to titles
            per_page: Number of results (max 25)
            
        Returns:
            List of contact teasers (no email, obfuscated name)
        """
        self._check_configured()
        
        logger.info(f"[Apollo] Searching contacts: org={organization_name or organization_domain}, titles={titles}")
        
        # Map department to titles if provided
        if department and not titles:
            dept_lower = department.lower()
            if "purchas" in dept_lower or "procur" in dept_lower or "supply" in dept_lower:
                titles = self.BUYER_TITLES
            elif "engineer" in dept_lower or "technical" in dept_lower or "r&d" in dept_lower:
                titles = self.TECHNICAL_TITLES
            elif "exec" in dept_lower or "c-" in dept_lower or "leadership" in dept_lower:
                titles = self.EXECUTIVE_TITLES
        
        try:
            payload: Dict[str, Any] = {
                "page": 1,
                "per_page": min(per_page, 25),
            }
            
            if organization_name:
                payload["q_organization_name"] = organization_name
            
            if organization_domain:
                payload["organization_domains"] = [organization_domain]
            
            if titles:
                payload["person_titles"] = titles
            
            if seniorities:
                payload["person_seniorities"] = seniorities
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/mixed_people/api_search",
                    headers=self.headers,
                    json=payload,
                    timeout=15.0,
                )
                
                if response.status_code != 200:
                    logger.warning(f"[Apollo] Contact search failed: {response.status_code}")
                    return []
                
                data = response.json()
                people = data.get("people", [])
                
                results = []
                for p in people:
                    org = p.get("organization", {})
                    # Extract departments - Apollo returns as list
                    departments = p.get("departments", [])
                    if isinstance(departments, str):
                        departments = [departments]
                    results.append(ApolloContactTeaser(
                        id=p.get("id", ""),
                        first_name=p.get("first_name", ""),
                        last_name=p.get("last_name"),
                        title=p.get("title"),
                        seniority=p.get("seniority"),
                        departments=departments,
                        company_name=org.get("name"),
                        company_domain=org.get("primary_domain"),
                        has_email=bool(p.get("email")),
                        has_phone=bool(p.get("phone_numbers")),
                        has_city=bool(p.get("city")),
                        city=p.get("city"),
                        state=p.get("state"),
                        country=p.get("country"),
                        last_updated=p.get("last_refreshed_at"),
                        linkedin_url=p.get("linkedin_url"),
                    ))
                
                logger.info(f"[Apollo] Found {len(results)} contacts")
                return results
                
        except Exception as e:
            logger.error(f"[Apollo] Error searching contacts: {e}")
            return []
    
    # =========================================================================
    # People Match / Reveal (1 CREDIT)
    # =========================================================================
    
    async def reveal_contact(self, person_id: str) -> Optional[ApolloContactRevealed]:
        """
        Reveal full contact details including email.
        
        ⚠️ COSTS 1 CREDIT - use judiciously!
        
        Args:
            person_id: Apollo person ID from search results
            
        Returns:
            Full contact profile with email, or None if failed
        """
        self._check_configured()
        
        if not self.credits.can_reveal():
            logger.warning("[Apollo] Credit limit reached - cannot reveal contact")
            return None
        
        logger.info(f"[Apollo] Revealing contact: {person_id}")
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/people/match",
                    headers=self.headers,
                    json={
                        "id": person_id,
                        "reveal_personal_emails": False,  # Stick to work emails
                    },
                    timeout=15.0,
                )
                
                if response.status_code != 200:
                    logger.warning(f"[Apollo] Reveal failed: {response.status_code}")
                    return None
                
                data = response.json()
                person = data.get("person", {})
                
                if not person:
                    return None
                
                # Record credit usage
                self.credits.record_reveal()
                
                org = person.get("organization", {})
                
                # Parse employment history
                employment_history = [
                    {
                        "company": e.get("organization_name"),
                        "title": e.get("title"),
                        "start_date": e.get("start_date"),
                        "end_date": e.get("end_date"),
                        "current": e.get("current", False),
                    }
                    for e in person.get("employment_history", [])
                ]
                
                return ApolloContactRevealed(
                    # Identity
                    id=person.get("id", ""),
                    name=person.get("name", ""),
                    first_name=person.get("first_name", ""),
                    last_name=person.get("last_name", ""),
                    title=person.get("title"),
                    seniority=person.get("seniority"),
                    photo_url=person.get("photo_url"),
                    
                    # Contact Info
                    email=person.get("email"),
                    email_status=person.get("email_status"),
                    phone=person.get("sanitized_phone") or (person.get("phone_numbers", [{}])[0].get("sanitized_number") if person.get("phone_numbers") else None),
                    linkedin_url=person.get("linkedin_url"),
                    twitter_url=person.get("twitter_url"),
                    
                    # Location
                    city=person.get("city"),
                    state=person.get("state"),
                    country=person.get("country"),
                    timezone=person.get("time_zone"),
                    
                    # Employment
                    employment_history=employment_history,
                    
                    # Company
                    company_name=org.get("name"),
                    company_domain=org.get("primary_domain"),
                    company_industry=org.get("industry"),
                    company_employee_count=org.get("estimated_num_employees"),
                    company_revenue_printed=org.get("annual_revenue_printed"),
                    company_phone=org.get("phone"),
                    company_linkedin_url=org.get("linkedin_url"),
                )
                
        except Exception as e:
            logger.error(f"[Apollo] Error revealing contact: {e}")
            return None
    
    # =========================================================================
    # Credit Management
    # =========================================================================
    
    def get_credit_status(self) -> dict:
        """Get current credit usage status."""
        return self.credits.usage_report()
    
    def can_reveal(self) -> bool:
        """Check if we have credits to reveal a contact."""
        return self.credits.can_reveal()
    
    # =========================================================================
    # Organization Search (FREE)
    # =========================================================================
    
    async def search_organizations(
        self,
        q_keywords: Optional[List[str]] = None,
        states: Optional[List[str]] = None,
        countries: Optional[List[str]] = None,
        employee_ranges: Optional[List[str]] = None,
        revenue_range_min: Optional[int] = None,
        revenue_range_max: Optional[int] = None,
        industries: Optional[List[str]] = None,
        per_page: int = 25,
        page: int = 1,
    ) -> List[ApolloOrganization]:
        """
        Search for organizations with structured firmographic filters.
        
        This is FREE and doesn't consume credits.
        
        Use this when users specify:
        - Geographic requirements (state, country)
        - Company size (employee count ranges)
        - Revenue thresholds
        - Industry categories
        
        Args:
            q_keywords: Keyword search terms (e.g., ["aerospace", "composites"])
            states: US state filters (e.g., ["Florida", "California", "Texas"])
            countries: Country filters (e.g., ["United States"])
            employee_ranges: Employee count ranges. Format: "min,max" or use constants:
                           "1,10", "11,50", "51,200", "201,500", "501,1000", "1001,5000", "5001,10000", "10001+"
            revenue_range_min: Minimum annual revenue in USD (e.g., 10000000 for $10M)
            revenue_range_max: Maximum annual revenue in USD (None for no upper limit)
            industries: Industry filters (e.g., ["Manufacturing", "Aerospace & Defense"])
            per_page: Results per page (max 25)
            page: Page number (1-indexed)
            
        Returns:
            List of ApolloOrganization objects matching the filters
        """
        self._check_configured()
        
        logger.info(f"[Apollo] Searching organizations: keywords={q_keywords}, states={states}, "
                   f"employees={employee_ranges}, revenue_min={revenue_range_min}, industries={industries}")
        
        try:
            payload: Dict[str, Any] = {
                "page": page,
                "per_page": min(per_page, 25),
            }
            
            # Keyword search
            if q_keywords:
                payload["q_organization_keyword_tags"] = q_keywords
            
            # Location filters
            if states or countries:
                locations = []
                if states:
                    for state in states:
                        # Apollo expects format like "Florida, United States"
                        country = "United States" if not countries else countries[0]
                        locations.append(f"{state}, {country}")
                elif countries:
                    locations = countries
                payload["organization_locations"] = locations
            
            # Employee range filter
            if employee_ranges:
                # Apollo format: ["1,10", "11,50", ...] 
                payload["organization_num_employees_ranges"] = employee_ranges
            
            # Revenue range filter
            if revenue_range_min is not None or revenue_range_max is not None:
                revenue_filter = {}
                if revenue_range_min is not None:
                    revenue_filter["min"] = revenue_range_min
                if revenue_range_max is not None:
                    revenue_filter["max"] = revenue_range_max
                payload["revenue_range"] = revenue_filter
            
            # Industry filter
            if industries:
                payload["organization_industry_tag_ids"] = industries
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/organizations/search",
                    headers=self.headers,
                    json=payload,
                    timeout=15.0,
                )
                
                if response.status_code != 200:
                    logger.warning(f"[Apollo] Organization search failed: {response.status_code} - {response.text[:200]}")
                    return []
                
                data = response.json()
                organizations = data.get("organizations", [])
                
                results = []
                for org in organizations:
                    results.append(ApolloOrganization(
                        # Identity
                        name=org.get("name", ""),
                        domain=org.get("primary_domain", ""),
                        description=org.get("short_description"),
                        logo_url=org.get("logo_url"),
                        
                        # Firmographics
                        employee_count=org.get("estimated_num_employees"),
                        founded_year=org.get("founded_year"),
                        industry=org.get("industry"),
                        annual_revenue=org.get("annual_revenue"),
                        revenue_printed=org.get("annual_revenue_printed"),
                        
                        # Location
                        street_address=org.get("street_address"),
                        city=org.get("city"),
                        state=org.get("state"),
                        postal_code=org.get("postal_code"),
                        country=org.get("country"),
                        raw_address=org.get("raw_address"),
                        
                        # Contact
                        phone=org.get("phone"),
                        website_url=org.get("website_url"),
                        
                        # Social
                        linkedin_url=org.get("linkedin_url"),
                        twitter_url=org.get("twitter_url"),
                        facebook_url=org.get("facebook_url"),
                        
                        # Stock
                        ticker=org.get("publicly_traded_symbol"),
                        exchange=org.get("publicly_traded_exchange"),
                        
                        # Tech & Keywords
                        technologies=[t.get("name") for t in org.get("current_technologies", []) if t.get("name")],
                        keywords=org.get("keywords", [])[:20],
                        
                        # Codes
                        sic_codes=org.get("sic_codes", []),
                        naics_codes=org.get("naics_codes", []),
                        
                        # Additional Firmographics
                        retail_location_count=org.get("retail_location_count"),
                        suborganizations=[s.get("name") for s in org.get("suborganizations", []) if s.get("name")],
                    ))
                
                logger.info(f"[Apollo] Found {len(results)} organizations matching filters")
                return results
                
        except Exception as e:
            logger.error(f"[Apollo] Error searching organizations: {e}", exc_info=True)
            return []


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

apollo_service = ApolloService()
