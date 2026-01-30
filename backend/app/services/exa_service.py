"""
Exa.ai Service for Pipeline Prospect Discovery

Provides semantic search capabilities for:
- Finding similar companies (lookalike targeting)
- Searching companies by description
- Finding decision makers/contacts
- Detecting trigger events (expansions, funding, etc.)

Enhanced with Logo.dev integration for company logos.
"""

import os
import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field

from exa_py import Exa
from app.utils.logger import get_logger
from app.services.logo_service import (
    extract_domain,
    parse_company_from_linkedin,
    company_name_to_domain,
    extract_company_from_news,
    logo_service,
)

logger = get_logger(__name__)


# =============================================================================
# LEGACY DATACLASSES (kept for backward compatibility)
# =============================================================================

@dataclass
class ProspectResult:
    """A prospect/company result from Exa search."""
    title: str
    url: str
    description: str
    score: Optional[float] = None
    published_date: Optional[str] = None
    location: Optional[str] = None
    industry: Optional[str] = None
    highlights: Optional[List[str]] = None


@dataclass
class ContactResult:
    """A contact/person result from Exa search."""
    name: str
    url: str
    snippet: str
    title: Optional[str] = None
    company: Optional[str] = None


@dataclass
class TriggerEventResult:
    """A trigger event (news signal) from Exa search."""
    title: str
    url: str
    summary: str
    published_date: Optional[str] = None
    event_type: Optional[str] = None
    highlights: Optional[List[str]] = None


# =============================================================================
# ENHANCED DATACLASSES (with domain and logo support)
# =============================================================================

@dataclass
class EnhancedProspectResult:
    """Enhanced prospect/company result with domain and logo support."""
    title: str
    url: str
    description: str
    domain: str  # Extracted domain for logo lookup
    logo_url: Optional[str] = None  # Proxy URL for logo
    score: Optional[float] = None
    published_date: Optional[str] = None
    location: Optional[str] = None
    industry: Optional[str] = None
    highlights: Optional[List[str]] = None
    
    # Cleaned company name (from title parsing)
    company_name: Optional[str] = None
    
    # Pre-populated enrichment data
    apollo_enrichment: Optional[Dict[str, Any]] = None


@dataclass 
class EnhancedContactResult:
    """Enhanced contact/person result with company domain and logo."""
    name: str
    url: str
    snippet: str
    title: Optional[str] = None
    company: Optional[str] = None
    company_domain: Optional[str] = None  # Domain for logo lookup
    logo_url: Optional[str] = None  # Proxy URL for company logo
    location: Optional[str] = None
    score: Optional[float] = None


@dataclass
class EnhancedTriggerEventResult:
    """Enhanced trigger event with company extraction."""
    title: str
    url: str
    summary: str
    source_domain: str  # Domain of the news source
    published_date: Optional[str] = None
    event_type: Optional[str] = None
    highlights: Optional[List[str]] = None
    # Company mentioned in the news
    mentioned_company: Optional[str] = None
    mentioned_company_domain: Optional[str] = None
    logo_url: Optional[str] = None  # Logo of mentioned company


class ExaService:
    """Service for interacting with Exa.ai API for prospect discovery."""
    
    def __init__(self):
        self.api_key = os.getenv("EXA_API_KEY")
        if not self.api_key:
            logger.warning("EXA_API_KEY not found in environment variables")
            self.client = None
        else:
            self.client = Exa(self.api_key)
            logger.info("Exa.ai client initialized")
            
        # Initialize Apollo service for pre-enrichment
        from app.services.apollo_service import apollo_service
        self.apollo = apollo_service
        
        # Load master lists for supply chain matching (will be loaded async on first use)
        self.supply_chain_terms = []
        self._terms_loaded = False

    async def _load_supply_chain_terms(self) -> List[str]:
        """Load materials and industries from BigQuery storage for tagging."""
        if self._terms_loaded:
            return self.supply_chain_terms
        
        terms = set()
        try:
            from app.db.gcp_storage import get_storage
            
            storage = await get_storage()
            
            # Get materials
            materials = await storage.get_materials()
            for mat in materials:
                terms.add(mat['name'])
                # Add examples too
                examples = mat.get('examples', '')
                if examples:
                    terms.update([e.strip() for e in examples.split('|')])
            
            # Get industries
            industries = await storage.get_industries()
            for ind in industries:
                terms.add(ind['name'])
                
            # Filter out very short or generic terms
            self.supply_chain_terms = [t for t in terms if len(t) > 3]
            self._terms_loaded = True
            logger.info(f"Loaded {len(self.supply_chain_terms)} supply chain terms from BigQuery")
        except Exception as e:
            logger.error(f"Error loading supply chain terms from BigQuery: {e}")
            # Fallback to defaults if storage not available
            self.supply_chain_terms = ["Carbon Fiber", "Resin", "Epoxy", "Aerospace", "Composite"]
            self._terms_loaded = True
        
        return self.supply_chain_terms
    
    def _check_client(self) -> None:
        """Check if client is available, raise error if not."""
        if not self.client:
            raise ValueError("Exa.ai API key not configured. Set EXA_API_KEY environment variable.")
    
    async def find_similar_companies(
        self,
        reference_url: str,
        num_results: int = 25,
        exclude_source: bool = True
    ) -> List[ProspectResult]:
        """
        Find companies similar to a reference company.
        
        This is the highest-value feature - automated lookalike targeting.
        Given a URL of a known good customer, find similar companies.
        
        Args:
            reference_url: Website URL of a known customer/prospect
            num_results: How many similar companies to find (max 100)
            exclude_source: Exclude the reference company from results
        
        Returns:
            List of similar company results with URLs and descriptions
        """
        self._check_client()
        
        logger.info(f"Finding similar companies to: {reference_url}")
        
        try:
            response = self.client.find_similar_and_contents(
                url=reference_url,
                num_results=num_results,
                exclude_source_domain=exclude_source,
                text={"max_characters": 500}
            )
            
            results = []
            for r in response.results:
                results.append(ProspectResult(
                    title=r.title or "",
                    url=r.url,
                    description=getattr(r, 'text', '') or "",
                    score=getattr(r, 'score', None),
                    highlights=getattr(r, 'highlights', None)
                ))
            
            logger.info(f"Found {len(results)} similar companies")
            return results
            
        except Exception as e:
            logger.error(f"Error finding similar companies: {e}")
            raise
    
    async def search_companies(
        self,
        query: str,
        num_results: int = 25,
        include_domains: Optional[List[str]] = None,
        exclude_domains: Optional[List[str]] = None
    ) -> List[ProspectResult]:
        """
        Semantic search for companies using natural language.
        
        Args:
            query: Natural language description (e.g., "fiberglass boat manufacturers in Florida")
            num_results: Number of results
            include_domains: Only search these domains
            exclude_domains: Exclude these domains from results
        
        Returns:
            List of matching companies
        """
        self._check_client()
        
        logger.info(f"Searching companies: {query}")
        
        try:
            kwargs = {
                "query": query,
                "category": "company",
                "num_results": num_results,
                "text": {"max_characters": 500}
            }
            
            if include_domains:
                kwargs["include_domains"] = include_domains
            if exclude_domains:
                kwargs["exclude_domains"] = exclude_domains
            
            response = self.client.search_and_contents(**kwargs)
            
            results = []
            for r in response.results:
                results.append(ProspectResult(
                    title=r.title or "",
                    url=r.url,
                    description=getattr(r, 'text', '') or "",
                    score=getattr(r, 'score', None),
                    published_date=getattr(r, 'publishedDate', None),
                    highlights=getattr(r, 'highlights', None)
                ))
            
            logger.info(f"Found {len(results)} companies")
            return results
            
        except Exception as e:
            logger.error(f"Error searching companies: {e}")
            raise
    
    async def find_decision_makers(
        self,
        role: str,
        industry: Optional[str] = None,
        company: Optional[str] = None,
        num_results: int = 10
    ) -> List[ContactResult]:
        """
        Find LinkedIn profiles and decision makers by role.
        
        Args:
            role: Job title or role (e.g., "VP of Operations", "Purchasing Manager")
            industry: Optional industry focus
            company: Optional specific company
            num_results: Number of results
        
        Returns:
            List of people/profile results
        """
        self._check_client()
        
        # Build query
        query_parts = [role]
        if company:
            query_parts.append(f"at {company}")
        elif industry:
            query_parts.append(f"at {industry} companies")
        
        query = " ".join(query_parts)
        logger.info(f"Finding decision makers: {query}")
        
        try:
            response = self.client.search_and_contents(
                query=query,
                category="people",
                num_results=num_results,
                text={"max_characters": 300}
            )
            
            results = []
            for r in response.results:
                results.append(ContactResult(
                    name=r.title or "",
                    url=r.url,
                    snippet=getattr(r, 'text', '') or "",
                ))
            
            logger.info(f"Found {len(results)} contacts")
            return results
            
        except Exception as e:
            logger.error(f"Error finding decision makers: {e}")
            raise
    
    async def find_trigger_events(
        self,
        topic: str,
        days_back: int = 30,
        num_results: int = 25
    ) -> List[TriggerEventResult]:
        """
        Find recent news/signals about companies or industry.
        
        Trigger events include: expansions, funding, new facilities, 
        leadership changes, contract awards.
        
        Args:
            topic: What to search for (e.g., "composites manufacturing expansion")
            days_back: How many days back to look
            num_results: Number of results
        
        Returns:
            List of news items with company mentions
        """
        self._check_client()
        
        logger.info(f"Finding trigger events: {topic} (last {days_back} days)")
        
        try:
            date_filter = (
                datetime.now() - timedelta(days=days_back)
            ).strftime("%Y-%m-%dT00:00:00.000Z")
            
            response = self.client.search_and_contents(
                query=topic,
                category="news",
                num_results=num_results,
                start_published_date=date_filter,
                text={"max_characters": 600},
                highlights=True
            )
            
            results = []
            for r in response.results:
                # Try to infer event type from content
                event_type = self._infer_event_type(r.title or "", getattr(r, 'text', '') or "")
                
                results.append(TriggerEventResult(
                    title=r.title or "",
                    url=r.url,
                    summary=getattr(r, 'text', '') or "",
                    published_date=getattr(r, 'publishedDate', None),
                    event_type=event_type,
                    highlights=getattr(r, 'highlights', [])
                ))
            
            logger.info(f"Found {len(results)} trigger events")
            return results
            
        except Exception as e:
            logger.error(f"Error finding trigger events: {e}")
            raise
    
    def _infer_event_type(self, title: str, text: str) -> str:
        """Infer the type of trigger event from the content."""
        content = (title + " " + text).lower()
        
        if any(word in content for word in ["expansion", "expand", "new facility", "new plant"]):
            return "expansion"
        elif any(word in content for word in ["funding", "investment", "raise", "series"]):
            return "funding"
        elif any(word in content for word in ["contract", "award", "deal", "wins"]):
            return "contract"
        elif any(word in content for word in ["hire", "appoint", "ceo", "cfo", "leadership"]):
            return "leadership"
        elif any(word in content for word in ["acquisition", "acquire", "merger", "m&a"]):
            return "m&a"
        elif any(word in content for word in ["modernization", "upgrade", "automation"]):
            return "modernization"
        else:
            return "news"
    
    async def deep_search(
        self,
        query: str,
        additional_queries: Optional[List[str]] = None,
        num_results: int = 25
    ) -> List[ProspectResult]:
        """
        Deep search with query expansion for complex queries.
        
        This is slower (~3-5 sec) but more thorough.
        
        Args:
            query: Main search query
            additional_queries: Optional variations to expand coverage
            num_results: Number of results
        
        Returns:
            Comprehensive list of results
        """
        self._check_client()
        
        logger.info(f"Deep search: {query}")
        
        try:
            kwargs = {
                "query": query,
                "type": "auto",  # Let Exa decide best approach
                "num_results": num_results,
                "text": {"max_characters": 500},
                "highlights": True
            }
            
            response = self.client.search_and_contents(**kwargs)
            
            results = []
            for r in response.results:
                results.append(ProspectResult(
                    title=r.title or "",
                    url=r.url,
                    description=getattr(r, 'text', '') or "",
                    score=getattr(r, 'score', None),
                    highlights=getattr(r, 'highlights', None)
                ))
            
            logger.info(f"Deep search found {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"Error in deep search: {e}")
            raise
    
    async def enrich_urls(self, urls: List[str]) -> List[Dict[str, Any]]:
        """
        Get detailed content from a list of URLs.
        
        Args:
            urls: List of company website URLs
        
        Returns:
            List of enriched company data
        """
        self._check_client()
        
        logger.info(f"Enriching {len(urls)} URLs")
        
        try:
            response = self.client.get_contents(
                ids=urls,
                text={"max_characters": 2000},
                highlights=True
            )
            
            results = []
            for r in response.results:
                results.append({
                    "url": r.url,
                    "title": r.title,
                    "content": getattr(r, 'text', ''),
                    "highlights": getattr(r, 'highlights', [])
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Error enriching URLs: {e}")
            raise
    
    # =========================================================================
    # ENHANCED METHODS (with domain extraction and logo support)
    # =========================================================================
    
    def _clean_company_name(self, title: str) -> str:
        """Extract clean company name from page title."""
        if not title:
            return ""
        
        # Common separators in page titles
        # "Composites One - Leading Distributor" -> "Composites One"
        # "Hexcel Corporation | Advanced Composites" -> "Hexcel Corporation"
        for sep in [" - ", " | ", " – ", " — "]:
            if sep in title:
                title = title.split(sep)[0]
        
        return title.strip()
    
    async def find_similar_companies_enhanced(
        self,
        reference: str,
        num_results: int = 25,
        exclude_source: bool = True
    ) -> List[EnhancedProspectResult]:
        """
        Find companies similar to a reference (URL or company name).
        
        Uses Apollo.io to enrich the reference company and build a smarter
        search query for Exa's neural search.
        
        Args:
            reference: Website URL or company name
            num_results: How many similar companies to find (max 100)
            exclude_source: Exclude the reference company from results
        
        Returns:
            List of enhanced results with domain and logo_url
        """
        self._check_client()
        
        logger.info(f"[Enhanced] Finding similar companies to: {reference}")
        
        try:
            # 1. Resolve domain and clean name
            reference_url = ""
            domain = ""
            company_name = reference
            
            if reference.startswith(("http://", "https://")) or "." in reference:
                reference_url = reference if "://" in reference else f"https://{reference}"
                domain = extract_domain(reference_url)
            else:
                # It's a name, resolve to domain using heuristic or search
                domain = company_name_to_domain(reference)
                if not domain:
                    # Fallback: search Exa for the company to get its URL
                    search_res = await self.search_companies(reference, num_results=1)
                    if search_res:
                        reference_url = search_res[0].url
                        domain = extract_domain(reference_url)
                        company_name = self._clean_company_name(search_res[0].title)
            
            # 2. Try to enrich with Apollo for better search context
            apollo_data = None
            if domain:
                try:
                    from app.services.apollo_service import apollo_service
                    apollo_data = await apollo_service.enrich_organization(domain)
                except Exception as e:
                    logger.warning(f"Apollo enrichment failed for {domain}: {e}")

            # 3. Build neural search query
            if apollo_data:
                # Use Apollo description, industry, and keywords for a rich search query
                industry = apollo_data.industry or "company"
                keywords = ", ".join(apollo_data.keywords[:5]) if apollo_data.keywords else ""
                description = apollo_data.description or ""
                
                query = f"Companies similar to {apollo_data.name} ({domain}), which is a {industry} "
                if keywords:
                    query += f"focused on {keywords}. "
                if description:
                    # Truncate description if too long
                    clean_desc = description[:300].strip()
                    query += f"Description: {clean_desc}"
                
                logger.info(f"[Enhanced] Using Apollo-enriched query: {query[:100]}...")
                
                # Perform neural search with the enriched query
                response = self.client.search_and_contents(
                    query=query,
                    num_results=num_results + 5, # Fetch slightly more for filtering
                    type="neural",
                    use_autoprompt=True,
                    text={"max_characters": 500}
                )
            else:
                # Fallback: use Exa's native find_similar if we only have a URL
                if reference_url:
                    logger.info(f"[Enhanced] Falling back to Exa find_similar for {reference_url}")
                    response = self.client.find_similar_and_contents(
                        url=reference_url,
                        num_results=num_results,
                        exclude_source_domain=exclude_source,
                        text={"max_characters": 500}
                    )
                else:
                    # Last resort: just search for "companies like {name}"
                    logger.info(f"[Enhanced] Falling back to basic search for companies like {reference}")
                    response = self.client.search_and_contents(
                        query=f"Companies like {reference}",
                        num_results=num_results,
                        use_autoprompt=True,
                        text={"max_characters": 500}
                    )
            
            # 4. Process and enhance results
            results = []
            source_domain = domain if domain else ""
            
            for r in response.results:
                res_domain = extract_domain(r.url)
                
                # Exclude source if requested
                if exclude_source and res_domain == source_domain:
                    continue
                
                res_company_name = self._clean_company_name(r.title or "")
                
                results.append(EnhancedProspectResult(
                    title=r.title or "",
                    url=r.url,
                    description=getattr(r, 'text', '') or "",
                    domain=res_domain,
                    logo_url=logo_service.get_logo_url(res_domain) if res_domain else None,
                    score=getattr(r, 'score', None),
                    published_date=getattr(r, 'publishedDate', None),
                    highlights=getattr(r, 'highlights', None),
                    company_name=res_company_name,
                ))
            
            # Trim to requested num_results
            final_results = results[:num_results]
            
            # 5. Pre-enrich with Apollo in parallel
            final_results = await self._enrich_results_with_apollo(final_results)
            
            logger.info(f"[Enhanced] Found {len(final_results)} similar companies (pre-enriched)")
            return final_results
            
        except Exception as e:
            logger.error(f"Error finding similar companies: {e}")
            raise
    
    async def search_companies_enhanced(
        self,
        query: str,
        num_results: int = 25,
        include_domains: Optional[List[str]] = None,
        exclude_domains: Optional[List[str]] = None
    ) -> List[EnhancedProspectResult]:
        """
        Semantic search for companies (enhanced with logos).
        
        Args:
            query: Natural language description
            num_results: Number of results
            include_domains: Only search these domains
            exclude_domains: Exclude these domains from results
        
        Returns:
            List of enhanced results with domain and logo_url
        """
        self._check_client()
        
        logger.info(f"[Enhanced] Searching companies: {query}")
        
        try:
            kwargs = {
                "query": query,
                "category": "company",
                "num_results": num_results,
                "text": {"max_characters": 500}
            }
            
            if include_domains:
                kwargs["include_domains"] = include_domains
            if exclude_domains:
                kwargs["exclude_domains"] = exclude_domains
            
            response = self.client.search_and_contents(**kwargs)
            
            results = []
            for r in response.results:
                domain = extract_domain(r.url)
                company_name = self._clean_company_name(r.title or "")
                
                results.append(EnhancedProspectResult(
                    title=r.title or "",
                    url=r.url,
                    description=getattr(r, 'text', '') or "",
                    domain=domain,
                    logo_url=logo_service.get_logo_url(domain) if domain else None,
                    score=getattr(r, 'score', None),
                    published_date=getattr(r, 'publishedDate', None),
                    highlights=getattr(r, 'highlights', None),
                    company_name=company_name,
                ))
            
            # 5. Pre-enrich with Apollo in parallel
            enrich_results = await self._enrich_results_with_apollo(results)
            
            logger.info(f"[Enhanced] Found {len(enrich_results)} companies (pre-enriched)")
            return enrich_results
            
        except Exception as e:
            logger.error(f"Error searching companies: {e}")
            raise
    
    async def find_decision_makers_enhanced(
        self,
        role: str,
        industry: Optional[str] = None,
        company: Optional[str] = None,
        num_results: int = 10
    ) -> List[EnhancedContactResult]:
        """
        Find LinkedIn profiles and decision makers (enhanced with company logos).
        
        Args:
            role: Job title or role (e.g., "VP of Operations")
            industry: Optional industry focus
            company: Optional specific company
            num_results: Number of results
        
        Returns:
            List of enhanced contact results with company logos
        """
        self._check_client()
        
        # Build query
        query_parts = [role]
        if company:
            query_parts.append(f"at {company}")
        elif industry:
            query_parts.append(f"at {industry} companies")
        
        query = " ".join(query_parts)
        logger.info(f"[Enhanced] Finding decision makers: {query}")
        
        try:
            response = self.client.search_and_contents(
                query=query,
                category="people",
                num_results=num_results,
                text={"max_characters": 300}
            )
            
            results = []
            for r in response.results:
                text = getattr(r, 'text', '') or ""
                title = r.title or ""
                
                # Parse company info from LinkedIn data
                company_name, company_domain = parse_company_from_linkedin(title, text)
                
                # Extract person's name from title
                name = title.split(" - ")[0].split(" | ")[0].strip() if title else ""
                
                # Try to extract job title
                job_title = None
                if " - " in title:
                    parts = title.split(" - ")
                    if len(parts) >= 2:
                        job_title = parts[1].split("|")[0].strip()
                
                results.append(EnhancedContactResult(
                    name=name,
                    url=r.url,
                    snippet=text,
                    title=job_title,
                    company=company_name,
                    company_domain=company_domain,
                    logo_url=logo_service.get_logo_url(company_domain) if company_domain else None,
                    score=getattr(r, 'score', None),
                ))
            
            logger.info(f"[Enhanced] Found {len(results)} contacts")
            return results
            
        except Exception as e:
            logger.error(f"Error finding decision makers: {e}")
            raise
    
    async def find_trigger_events_enhanced(
        self,
        topic: str,
        days_back: int = 30,
        num_results: int = 25
    ) -> List[EnhancedTriggerEventResult]:
        """
        Find recent news/signals (enhanced with company extraction).
        
        Args:
            topic: What to search for
            days_back: How many days back to look
            num_results: Number of results
        
        Returns:
            List of enhanced trigger events with company logos
        """
        self._check_client()
        
        logger.info(f"[Enhanced] Finding trigger events: {topic} (last {days_back} days)")
        
        try:
            date_filter = (
                datetime.now() - timedelta(days=days_back)
            ).strftime("%Y-%m-%dT00:00:00.000Z")
            
            response = self.client.search_and_contents(
                query=topic,
                category="news",
                num_results=num_results,
                start_published_date=date_filter,
                text={"max_characters": 600},
                highlights=True
            )
            
            results = []
            for r in response.results:
                title = r.title or ""
                text = getattr(r, 'text', '') or ""
                
                # Extract source domain
                source_domain = extract_domain(r.url)
                
                # Try to extract mentioned company
                mentioned_domain = extract_company_from_news(title, text)
                mentioned_company = None
                if mentioned_domain:
                    # Reverse lookup - this is approximate
                    mentioned_company = mentioned_domain.replace(".com", "").title()
                
                # Infer event type
                event_type = self._infer_event_type(title, text)
                
                results.append(EnhancedTriggerEventResult(
                    title=title,
                    url=r.url,
                    summary=text,
                    source_domain=source_domain,
                    published_date=getattr(r, 'publishedDate', None),
                    event_type=event_type,
                    highlights=getattr(r, 'highlights', []),
                    mentioned_company=mentioned_company,
                    mentioned_company_domain=mentioned_domain,
                    logo_url=logo_service.get_logo_url(mentioned_domain) if mentioned_domain else None,
                ))
            
            logger.info(f"[Enhanced] Found {len(results)} trigger events")
            return results
            
        except Exception as e:
            logger.error(f"Error finding trigger events: {e}")
            raise

    async def _enrich_results_with_apollo(self, results: List[EnhancedProspectResult]) -> List[EnhancedProspectResult]:
        """Enrich a list of results with Apollo firmographics in parallel."""
        if not results:
            return results
            
        logger.info(f"[Apollo] Pre-enriching {len(results)} search results")
        
        async def enrich_one(result: EnhancedProspectResult):
            if not result.domain:
                return
            
            try:
                # Get enrichment from Apollo
                org = await self.apollo.enrich_organization(result.domain)
                if org:
                    # Convert dataclass to dict for frontend
                    org_dict = {
                        "name": org.name,
                        "domain": org.domain,
                        "description": org.description,
                        "employee_count": org.employee_count,
                        "annual_revenue": org.annual_revenue,
                        "revenue_printed": org.revenue_printed,
                        "founded_year": org.founded_year,
                        "logo_url": org.logo_url,
                        "industry": org.industry,
                        "city": org.city,
                        "state": org.state,
                        "country": org.country,
                        "technologies": org.technologies,
                        "keywords": org.keywords,
                        "linkedin_url": org.linkedin_url,
                        # Extended firmographics
                        "sic_codes": org.sic_codes,
                        "naics_codes": org.naics_codes,
                        "retail_location_count": org.retail_location_count,
                        "suborganizations": org.suborganizations[:10] if org.suborganizations else [],
                    }
                    
                    # Add supply chain matches
                    org_dict["supply_chain_matches"] = await self._find_supply_chain_matches(org)
                    
                    result.apollo_enrichment = org_dict
            except Exception as e:
                logger.error(f"Error enriching {result.domain}: {e}")

        # Run all enrichments in parallel
        await asyncio.gather(*[enrich_one(r) for r in results])
        return results

    async def _find_supply_chain_matches(self, org: Any) -> List[str]:
        """Find matching terms between Apollo data and our master supply chain lists."""
        # Ensure terms are loaded
        await self._load_supply_chain_terms()
        
        matches = set()
        
        # Check keywords and technologies against our master list
        all_apollo_terms = set(org.keywords) | set(org.technologies)
        if org.industry:
            all_apollo_terms.add(org.industry)
            
        # Case-insensitive comparison
        for apollo_term in all_apollo_terms:
            apollo_term_lower = apollo_term.lower()
            for master_term in self.supply_chain_terms:
                if master_term.lower() in apollo_term_lower or apollo_term_lower in master_term.lower():
                    matches.add(master_term)
                    
        # Limit to top 5 most relevant matches
        return sorted(list(matches))[:5]


# Singleton instance
exa_service = ExaService()
