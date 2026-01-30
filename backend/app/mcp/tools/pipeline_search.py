"""
Pipeline Search Tools - Prospect Discovery powered by Exa.ai + Logo.dev

These tools enable the Pipeline agent to:
- Find similar companies (lookalike targeting)
- Search companies by description
- Find decision makers/contacts
- Detect trigger events (expansions, funding, etc.)

All results include domain extraction and logo URLs for rich UI display.
"""

from typing import Optional, List, Literal
import json
import asyncio
from langchain_core.tools import tool

from app.services.exa_service import exa_service
from app.services.exa_websets_service import exa_websets_service
from app.services.apollo_service import apollo_service
from app.utils.logger import get_logger

# Import corpus query tools for BigQuery intelligence integration
from app.mcp.tools.corpus_query import (
    query_corpus,
    get_entity_mentions,
    get_competitor_activity,
)

logger = get_logger(__name__)


def _format_prospect_results(results) -> List[dict]:
    """Format enhanced prospect results for tool output."""
    return [
        {
            "title": r.title,
            "company_name": r.company_name,
            "url": r.url,
            "domain": r.domain,
            "logo_url": r.logo_url,
            "description": r.description[:300] + "..." if len(r.description) > 300 else r.description,
            "score": r.score,
            "published_date": r.published_date,
            "apollo_enrichment": r.apollo_enrichment,
        }
        for r in results
    ]


def _format_contact_results(results) -> List[dict]:
    """Format enhanced contact results for tool output."""
    return [
        {
            "name": r.name,
            "title": r.title,
            "company": r.company,
            "company_domain": r.company_domain,
            "logo_url": r.logo_url,
            "url": r.url,
            "snippet": r.snippet[:200] + "..." if len(r.snippet) > 200 else r.snippet,
            "location": r.location,
            "score": r.score,
        }
        for r in results
    ]


def _format_trigger_results(results) -> List[dict]:
    """Format enhanced trigger event results for tool output."""
    return [
        {
            "title": r.title,
            "url": r.url,
            "summary": r.summary[:300] + "..." if len(r.summary) > 300 else r.summary,
            "source_domain": r.source_domain,
            "published_date": r.published_date,
            "event_type": r.event_type,
            "mentioned_company": r.mentioned_company,
            "mentioned_company_domain": r.mentioned_company_domain,
            "logo_url": r.logo_url,
        }
        for r in results
    ]


@tool
async def find_similar_companies(
    reference: str,
    num_results: int = 25,
    # Post-enrichment filter parameters (optional)
    filter_min_revenue: Optional[int] = None,
    filter_max_revenue: Optional[int] = None,
    filter_min_employees: Optional[int] = None,
    filter_max_employees: Optional[int] = None,
    filter_states: Optional[List[str]] = None,
    filter_countries: Optional[List[str]] = None,
    filter_industries: Optional[List[str]] = None,
) -> str:
    """
    Find companies similar to a reference company (URL or name) with optional filtering.
    
    This is the highest-value prospecting tool - automated lookalike targeting.
    Given a website URL or Name of a known good customer, find similar companies.
    Results are enriched with Apollo firmographics, then optional filters are applied.
    
    Args:
        reference: Website URL or Company Name of a reference company (e.g., "hexcel.com", "Hexcel", "Boeing")
        num_results: Number of similar companies to find (default 25, max 100)
        
        # POST-ENRICHMENT FILTERS (applied after Apollo enrichment):
        filter_min_revenue: Minimum annual revenue in USD (e.g., 50000000 for $50M+)
        filter_max_revenue: Maximum annual revenue in USD
        filter_min_employees: Minimum employee count (e.g., 200)
        filter_max_employees: Maximum employee count (e.g., 500)
        filter_states: US states to include (e.g., ["Florida", "Texas"])
        filter_countries: Countries to include (e.g., ["United States"])
        filter_industries: Industries to match (e.g., ["Manufacturing", "Aerospace"])
    
    Returns:
        JSON list of similar companies with domains and logo URLs for display.
        If filters applied, includes filter metadata and expansion suggestions.
    
    Example queries this tool answers:
    - "Find companies similar to compositesone.com"
    - "Who are Hexcel's competitors in Florida?" → filter_states=["Florida"]
    - "Find lookalikes for Boeing with >$100M revenue" → filter_min_revenue=100000000
    """
    from app.agents.pipeline.filters import CompanyFilters, apply_filters
    
    logger.info(f"Tool find_similar_companies: reference={reference}, num_results={num_results}")
    
    # Build filters if any are specified
    filters = CompanyFilters(
        min_revenue=filter_min_revenue,
        max_revenue=filter_max_revenue,
        min_employees=filter_min_employees,
        max_employees=filter_max_employees,
        states=filter_states,
        countries=filter_countries,
        industries=filter_industries,
    )
    has_filters = not filters.is_empty()
    
    if has_filters:
        logger.info(f"[Pipeline Tool] Filters specified for similar companies: {filters.to_description()}")
    
    try:
        # Use the enhanced similarity search which supports names/URLs and Apollo enrichment
        results = await exa_service.find_similar_companies_enhanced(
            reference=reference,
            num_results=num_results
        )
        
        formatted = _format_prospect_results(results)
        
        # Apply post-enrichment filters if specified
        if has_filters:
            filter_result = apply_filters(formatted, filters)
            
            response = {
                "block_type": "similar_companies",
                "title": f"Companies similar to {reference}",
                "query_context": reference,
                "prospects": filter_result.passed,
                "result_count": filter_result.filtered_count,
                # Filter metadata for agent feedback
                "filter_metadata": {
                    "filters_applied": filters.to_description(),
                    "original_count": filter_result.original_count,
                    "filtered_count": filter_result.filtered_count,
                    "filter_impact": filter_result.get_filter_impact_summary(),
                    "expansion_suggestions": filter_result.get_expansion_suggestions(),
                },
            }
            
            # If sparse results, add prominent warning for agent
            if filter_result.filtered_count < 5 and filter_result.original_count > filter_result.filtered_count:
                response["sparse_results_warning"] = (
                    f"Only {filter_result.filtered_count} of {filter_result.original_count} similar companies "
                    f"matched all filters. Consider suggesting filter relaxation to user."
                )
            
            return json.dumps(response, indent=2)
        
        return json.dumps({
            "block_type": "similar_companies",
            "title": f"Companies similar to {reference}",
            "query_context": reference,
            "prospects": formatted,
            "result_count": len(formatted)
        }, indent=2)
        
    except Exception as e:
        logger.error(f"Error in find_similar_companies tool: {e}")
        return json.dumps({
            "status": "error",
            "error": str(e),
            "query_type": "similar_companies",
        })


@tool
async def search_companies(
    query: str,
    num_results: int = 25,
    include_domains: Optional[List[str]] = None,
    exclude_domains: Optional[List[str]] = None,
    # Post-enrichment filter parameters (optional)
    filter_min_revenue: Optional[int] = None,
    filter_max_revenue: Optional[int] = None,
    filter_min_employees: Optional[int] = None,
    filter_max_employees: Optional[int] = None,
    filter_states: Optional[List[str]] = None,
    filter_countries: Optional[List[str]] = None,
    filter_industries: Optional[List[str]] = None,
) -> str:
    """
    Search for companies using natural language descriptions with optional post-enrichment filtering.
    
    Semantic search that understands industry terms, locations, and company characteristics.
    Results are enriched with Apollo firmographics, then optional filters are applied.
    
    USE THIS TOOL for:
    - Broad semantic searches: "carbon fiber suppliers to automotive OEMs"
    - Discovery with refinement: search broadly, then filter by revenue/employees/location
    
    Args:
        query: Natural language description of companies to find
        num_results: Number of results (default 25, max 100)
        include_domains: Only search these domains (optional)
        exclude_domains: Exclude these domains from results (optional)
        
        # POST-ENRICHMENT FILTERS (applied after Apollo enrichment):
        filter_min_revenue: Minimum annual revenue in USD (e.g., 50000000 for $50M+)
        filter_max_revenue: Maximum annual revenue in USD
        filter_min_employees: Minimum employee count (e.g., 200)
        filter_max_employees: Maximum employee count (e.g., 500)
        filter_states: US states to include (e.g., ["Florida", "Texas"])
        filter_countries: Countries to include (e.g., ["United States"])
        filter_industries: Industries to match (e.g., ["Manufacturing", "Aerospace"])
    
    Returns:
        JSON with matching companies, filter metadata, and expansion suggestions if results are sparse.
    
    Example queries:
    - "carbon fiber suppliers" with filter_min_revenue=50000000 → $50M+ companies
    - "aerospace manufacturers" with filter_states=["Florida", "Texas"] → in those states
    - "composites companies" with filter_min_employees=200, filter_max_employees=1000 → mid-size
    """
    from app.agents.pipeline.filters import CompanyFilters, apply_filters
    
    logger.info(f"[Pipeline Tool] search_companies: {query}")
    
    # Build filters if any are specified
    filters = CompanyFilters(
        min_revenue=filter_min_revenue,
        max_revenue=filter_max_revenue,
        min_employees=filter_min_employees,
        max_employees=filter_max_employees,
        states=filter_states,
        countries=filter_countries,
        industries=filter_industries,
    )
    has_filters = not filters.is_empty()
    
    if has_filters:
        logger.info(f"[Pipeline Tool] Filters specified: {filters.to_description()}")
    
    try:
        results = await exa_service.search_companies_enhanced(
            query=query,
            num_results=min(num_results, 100),
            include_domains=include_domains,
            exclude_domains=exclude_domains,
        )
        
        formatted = _format_prospect_results(results)
        
        # Apply post-enrichment filters if specified
        if has_filters:
            filter_result = apply_filters(formatted, filters)
            
            response = {
                "status": "success",
                "query_type": "search_companies",
                "query": query,
                "count": filter_result.filtered_count,
                "results": filter_result.passed,
                # Filter metadata for agent feedback
                "filter_metadata": {
                    "filters_applied": filters.to_description(),
                    "original_count": filter_result.original_count,
                    "filtered_count": filter_result.filtered_count,
                    "filter_impact": filter_result.get_filter_impact_summary(),
                    "expansion_suggestions": filter_result.get_expansion_suggestions(),
                },
            }
            
            # If sparse results, add prominent warning for agent
            if filter_result.filtered_count < 5 and filter_result.original_count > filter_result.filtered_count:
                response["sparse_results_warning"] = (
                    f"Only {filter_result.filtered_count} of {filter_result.original_count} companies "
                    f"matched all filters. Consider suggesting filter relaxation to user."
                )
            
            return json.dumps(response, indent=2)
        
        # No filters - return as before
        return json.dumps({
            "status": "success",
            "query_type": "search_companies",
            "query": query,
            "count": len(formatted),
            "results": formatted,
        }, indent=2)
        
    except Exception as e:
        logger.error(f"Error in search_companies: {e}")
        return json.dumps({
            "status": "error",
            "error": str(e),
            "query_type": "search_companies",
        })


@tool
async def find_contacts(
    role: str,
    industry: Optional[str] = None,
    company: Optional[str] = None,
    num_results: int = 15,
) -> str:
    """
    Find decision makers and contacts by job role.
    
    Searches LinkedIn profiles and professional pages to find people
    in specific roles at target companies or industries.
    
    Args:
        role: Job title or role to search for (e.g., "VP of Operations", "Purchasing Manager")
        industry: Industry focus (e.g., "aerospace", "composites manufacturing")
        company: Specific company name to search within
        num_results: Number of contacts to find (default 15, max 50)
    
    Returns:
        JSON list of contacts with company info and logo URLs.
    
    Example queries:
    - role="Purchasing Manager", industry="aerospace composites"
    - role="VP Operations", company="Spirit AeroSystems"
    - role="Supply Chain Director", industry="wind energy"
    """
    logger.info(f"[Pipeline Tool] find_contacts: role={role}, industry={industry}, company={company}")
    
    try:
        results = await exa_service.find_decision_makers_enhanced(
            role=role,
            industry=industry,
            company=company,
            num_results=min(num_results, 50),
        )
        
        formatted = _format_contact_results(results)
        
        return json.dumps({
            "status": "success",
            "query_type": "find_contacts",
            "role": role,
            "industry": industry,
            "company": company,
            "count": len(formatted),
            "results": formatted,
        }, indent=2)
        
    except Exception as e:
        logger.error(f"Error in find_contacts: {e}")
        return json.dumps({
            "status": "error",
            "error": str(e),
            "query_type": "find_contacts",
        })


@tool
async def find_trigger_events(
    topic: str,
    days_back: int = 30,
    num_results: int = 25,
) -> str:
    """
    Find recent news and trigger events about companies or industries.
    
    Trigger events are signals that indicate buying intent or opportunity:
    - Facility expansions
    - Funding announcements
    - New contracts/awards
    - Leadership changes
    - Acquisitions/mergers
    - Modernization initiatives
    
    Args:
        topic: What to search for (e.g., "composites manufacturing expansion", "aerospace facility investment")
        days_back: How many days back to search (default 30, max 90)
        num_results: Number of events to find (default 25, max 100)
    
    Returns:
        JSON list of trigger events with event type classification and company extraction.
    
    Example queries:
    - "composites manufacturing expansion"
    - "aerospace supplier contract award"
    - "carbon fiber plant investment"
    """
    logger.info(f"[Pipeline Tool] find_trigger_events: {topic} (last {days_back} days)")
    
    try:
        results = await exa_service.find_trigger_events_enhanced(
            topic=topic,
            days_back=min(days_back, 90),
            num_results=min(num_results, 100),
        )
        
        formatted = _format_trigger_results(results)
        
        return json.dumps({
            "status": "success",
            "query_type": "trigger_events",
            "topic": topic,
            "days_back": days_back,
            "count": len(formatted),
            "results": formatted,
        }, indent=2)
        
    except Exception as e:
        logger.error(f"Error in find_trigger_events: {e}")
        return json.dumps({
            "status": "error",
            "error": str(e),
            "query_type": "trigger_events",
        })


@tool
async def build_company_webset(
    query: str,
    name: str,
    max_results: int = 100,
) -> str:
    """
    Build a comprehensive, enriched company list using Exa Websets.
    
    ⚠️ IMPORTANT: This is a FULL LIST operation that:
    - Takes 1-5 minutes to complete (async background job)
    - Costs more than instant searches
    - Returns deeply enriched results (employee count, funding, location, LinkedIn)
    
    Only use this tool when the user explicitly requests a "full list" or 
    has confirmed they want comprehensive results. The user MUST type "CONFIRM"
    in their message to authorize this operation.
    
    For quick discovery, use search_companies or find_similar_companies instead.
    
    Args:
        query: Natural language description of companies to find
        name: A short name/label for this webset (e.g., "Aerospace composites suppliers")
        max_results: Maximum companies to find (default 100)
    
    Returns:
        JSON with webset_id for polling status, or error if not confirmed.
    
    Example usage (only after user CONFIRM):
    - query="composite materials manufacturers in the United States with aerospace certifications"
    - query="fiberglass boat builders with more than 50 employees"
    """
    logger.info(f"[Pipeline Tool] build_company_webset: {name} - {query}")
    
    try:
        webset_id = await exa_websets_service.create_company_webset(
            query=query,
            name=name,
            max_results=min(max_results, 500),
            enrichments=["employee_count", "funding", "location", "linkedin"]
        )
        
        if webset_id:
            return json.dumps({
                "status": "success",
                "query_type": "webset_created",
                "webset_id": webset_id,
                "name": name,
                "query": query,
                "max_results": max_results,
                "message": f"Webset '{name}' is now building. This typically takes 1-5 minutes. The UI will poll for status automatically.",
                "note": "Results will include employee count, funding info, location, and LinkedIn URLs."
            }, indent=2)
        else:
            return json.dumps({
                "status": "error",
                "error": "Failed to create webset - check EXA_API_KEY configuration",
                "query_type": "webset_created",
            })
        
    except Exception as e:
        logger.error(f"Error in build_company_webset: {e}")
        return json.dumps({
            "status": "error",
            "error": str(e),
            "query_type": "webset_created",
        })


# =============================================================================
# APOLLO.IO TOOLS
# =============================================================================

@tool
async def enrich_company(
    domain: str,
) -> str:
    """
    Get detailed company information from Apollo.io.
    
    This provides rich firmographic data including:
    - Employee count, revenue, founded year
    - Industry, location, address
    - Tech stack, keywords
    - Social profiles (LinkedIn, Twitter)
    - Stock ticker (if public)
    
    This is FREE and doesn't consume credits.
    
    Args:
        domain: Company domain (e.g., "hexcel.com", "boeing.com")
    
    Returns:
        JSON with comprehensive company data.
    
    Example:
    - enrich_company("hexcel.com") → employee count, revenue, industry, etc.
    """
    logger.info(f"[Pipeline Tool] enrich_company: {domain}")
    
    try:
        org = await apollo_service.enrich_organization(domain)
        
        if not org:
            return json.dumps({
                "status": "not_found",
                "domain": domain,
                "message": f"No company data found for {domain}",
            })
        
        return json.dumps({
            "status": "success",
            "query_type": "company_enrichment",
            "domain": domain,
            "company": {
                "name": org.name,
                "domain": org.domain,
                "description": org.description,
                "logo_url": org.logo_url,
                "employee_count": org.employee_count,
                "founded_year": org.founded_year,
                "industry": org.industry,
                "revenue_printed": org.revenue_printed,
                "annual_revenue": org.annual_revenue,
                "city": org.city,
                "state": org.state,
                "country": org.country,
                "address": org.raw_address,
                "phone": org.phone,
                "website": org.website_url,
                "linkedin_url": org.linkedin_url,
                "twitter_url": org.twitter_url,
                "ticker": org.ticker,
                "exchange": org.exchange,
                "technologies": org.technologies[:10] if org.technologies else [],
                "keywords": org.keywords[:10] if org.keywords else [],
                "sic_codes": org.sic_codes,
                "naics_codes": org.naics_codes,
                "retail_location_count": org.retail_location_count,
                "suborganizations": org.suborganizations[:10] if org.suborganizations else [],
            },
        }, indent=2)
        
    except Exception as e:
        logger.error(f"Error in enrich_company: {e}")
        return json.dumps({
            "status": "error",
            "error": str(e),
            "domain": domain,
        })


@tool
async def find_company_contacts(
    company_name: Optional[str] = None,
    company_domain: Optional[str] = None,
    titles: Optional[List[str]] = None,
    department: Optional[str] = None,
    seniorities: Optional[List[str]] = None,
    num_results: int = 10,
) -> str:
    """
    Find decision makers at a specific company using Apollo.io.
    
    Returns FULLY REVEALED contact profiles including:
    - Full name (first and last), title, seniority
    - Verified email address and phone number
    - LinkedIn profile link
    - Location (city, state, country)
    
    Also includes company enrichment (firmographics) for context.
    
    Args:
        company_name: Company name (e.g., "Hexcel Corporation")
        company_domain: Company domain (e.g., "hexcel.com") - more accurate than name
        titles: Specific job titles (e.g., ["Purchasing Manager", "VP Supply Chain"])
        department: Department filter - "purchasing", "engineering", or "executive"
        seniorities: Seniority levels (e.g., ["director", "vp", "c_suite"])
        num_results: Number of contacts to find (max 25)
    
    Returns:
        JSON with fully revealed contact profiles and company firmographics.
    
    Example:
    - find_company_contacts(company_domain="hexcel.com", department="purchasing")
    - find_company_contacts(company_name="Boeing", titles=["Materials Manager"])
    """
    logger.info(f"[Pipeline Tool] find_company_contacts: {company_name or company_domain}")
    
    try:
        # Step 1: Search for contacts (teaser data)
        contacts = await apollo_service.search_contacts(
            organization_name=company_name,
            organization_domain=company_domain,
            titles=titles,
            department=department,
            seniorities=seniorities,
            per_page=min(num_results, 25),
        )
        
        # Step 2: Auto-reveal each contact to get full data (email, phone, full name)
        revealed_contacts = []
        for c in contacts:
            try:
                revealed = await apollo_service.reveal_contact(c.id)
                if revealed:
                    revealed_contacts.append({
                        "id": revealed.id,
                        "name": revealed.name,
                        "first_name": revealed.first_name,
                        "last_name": revealed.last_name,
                        "title": revealed.title,
                        "seniority": revealed.seniority,
                        "departments": c.departments,  # Keep from teaser (reveal doesn't include)
                        "company": revealed.company_name or c.company_name,
                        "company_domain": revealed.company_domain or c.company_domain,
                        "email": revealed.email,
                        "email_status": revealed.email_status,
                        "phone": revealed.phone,
                        "city": revealed.city or c.city,
                        "state": revealed.state or c.state,
                        "country": revealed.country or c.country,
                        "linkedin_url": revealed.linkedin_url or c.linkedin_url,
                        "photo_url": revealed.photo_url,
                        "is_revealed": True,
                    })
                    logger.info(f"[Pipeline Tool] Auto-revealed contact: {revealed.name}")
                else:
                    # Fallback to teaser data if reveal fails
                    revealed_contacts.append({
                        "id": c.id,
                        "name": f"{c.first_name} {c.last_name_obfuscated or ''}".strip(),
                        "first_name": c.first_name,
                        "last_name": c.last_name_obfuscated,
                        "title": c.title,
                        "seniority": c.seniority,
                        "departments": c.departments,
                        "company": c.company_name,
                        "company_domain": c.company_domain,
                        "email": None,
                        "phone": None,
                        "city": c.city,
                        "state": c.state,
                        "country": c.country,
                        "linkedin_url": c.linkedin_url,
                        "is_revealed": False,
                    })
            except Exception as e:
                logger.warning(f"[Pipeline Tool] Failed to reveal contact {c.id}: {e}")
                # Fallback to teaser data
                revealed_contacts.append({
                    "id": c.id,
                    "name": f"{c.first_name} {c.last_name_obfuscated or ''}".strip(),
                    "first_name": c.first_name,
                    "last_name": c.last_name_obfuscated,
                    "title": c.title,
                    "seniority": c.seniority,
                    "departments": c.departments,
                    "company": c.company_name,
                    "company_domain": c.company_domain,
                    "email": None,
                    "phone": None,
                    "city": c.city,
                    "state": c.state,
                    "country": c.country,
                    "linkedin_url": c.linkedin_url,
                    "is_revealed": False,
                })
        
        # Step 3: Fetch company enrichment (FREE - no credits) for context
        company_enrichment = None
        enrich_domain = company_domain
        if not enrich_domain and contacts and contacts[0].company_domain:
            enrich_domain = contacts[0].company_domain
        
        if enrich_domain:
            try:
                org = await apollo_service.enrich_organization(enrich_domain)
                if org:
                    company_enrichment = {
                        "name": org.name,
                        "domain": org.domain,
                        "description": org.description,
                        "logo_url": org.logo_url,
                        "employee_count": org.employee_count,
                        "founded_year": org.founded_year,
                        "industry": org.industry,
                        "revenue_printed": org.revenue_printed,
                        "city": org.city,
                        "state": org.state,
                        "country": org.country,
                        "linkedin_url": org.linkedin_url,
                        "technologies": org.technologies[:5] if org.technologies else [],
                        "keywords": org.keywords[:5] if org.keywords else [],
                    }
                    logger.info(f"[Pipeline Tool] Company enrichment loaded for {enrich_domain}")
            except Exception as e:
                logger.warning(f"[Pipeline Tool] Company enrichment failed for {enrich_domain}: {e}")
        
        revealed_count = sum(1 for c in revealed_contacts if c.get("is_revealed"))
        logger.info(f"[Pipeline Tool] find_company_contacts complete: {len(revealed_contacts)} contacts, {revealed_count} revealed")
        
        return json.dumps({
            "status": "success",
            "query_type": "apollo_contacts",
            "company": company_name or company_domain,
            "count": len(revealed_contacts),
            "revealed_count": revealed_count,
            "results": revealed_contacts,
            "company_enrichment": company_enrichment,
        }, indent=2)
        
    except Exception as e:
        logger.error(f"Error in find_company_contacts: {e}")
        return json.dumps({
            "status": "error",
            "error": str(e),
            "query_type": "apollo_contacts",
        })


@tool
async def reveal_contact(
    person_id: str,
    contact_name: Optional[str] = None,
) -> str:
    """
    Reveal full contact details including verified email.
    
    NOTE: Contacts from find_company_contacts are automatically revealed.
    This tool is only needed for edge cases where auto-reveal failed.
    
    Args:
        person_id: Apollo person ID from find_company_contacts results
        contact_name: Optional name for logging
    
    Returns:
        JSON with full contact profile including email and employment history.
    
    Example:
    - reveal_contact("55bee9937369641588940b00", "Cameron V.")
    """
    logger.info(f"[Pipeline Tool] reveal_contact: {person_id} ({contact_name or 'unknown'})")
    
    # Check credit availability
    if not apollo_service.can_reveal():
        credits = apollo_service.get_credit_status()
        return json.dumps({
            "status": "error",
            "error": "Monthly credit limit reached",
            "credits": credits,
            "query_type": "apollo_reveal",
        })
    
    try:
        contact = await apollo_service.reveal_contact(person_id)
        
        if not contact:
            return json.dumps({
                "status": "not_found",
                "person_id": person_id,
                "message": "Contact not found or reveal failed",
                "query_type": "apollo_reveal",
            })
        
        credits = apollo_service.get_credit_status()
        
        return json.dumps({
            "status": "success",
            "query_type": "apollo_reveal",
            "credits_remaining": credits["remaining"],
            "contact": {
                "id": contact.id,
                "name": contact.name,
                "first_name": contact.first_name,
                "last_name": contact.last_name,
                "title": contact.title,
                "seniority": contact.seniority,
                "email": contact.email,
                "email_status": contact.email_status,
                "phone": contact.phone,
                "linkedin_url": contact.linkedin_url,
                "twitter_url": contact.twitter_url,
                "photo_url": contact.photo_url,
                "city": contact.city,
                "state": contact.state,
                "country": contact.country,
                "timezone": contact.timezone,
                "employment_history": contact.employment_history[:5],
                "company": {
                    "name": contact.company_name,
                    "domain": contact.company_domain,
                    "industry": contact.company_industry,
                    "employee_count": contact.company_employee_count,
                    "revenue": contact.company_revenue_printed,
                    "phone": contact.company_phone,
                    "linkedin_url": contact.company_linkedin_url,
                },
            },
        }, indent=2)
        
    except Exception as e:
        logger.error(f"Error in reveal_contact: {e}")
        return json.dumps({
            "status": "error",
            "error": str(e),
            "query_type": "apollo_reveal",
        })


@tool
async def search_companies_filtered(
    keywords: Optional[List[str]] = None,
    states: Optional[List[str]] = None,
    countries: Optional[List[str]] = None,
    employee_ranges: Optional[List[str]] = None,
    min_revenue: Optional[int] = None,
    max_revenue: Optional[int] = None,
    industries: Optional[List[str]] = None,
    num_results: int = 25,
) -> str:
    """
    Search for companies with structured firmographic filters using Apollo.io.
    
    ⚠️ USE THIS TOOL when the user specifies:
    - Geographic requirements (state, country) - "companies in Florida"
    - Company size by employee count - "companies with 200-500 employees"
    - Revenue thresholds - "companies with >$100M revenue"
    - Industry categories - "aerospace companies"
    
    For broad semantic searches WITHOUT specific filters, use search_companies (Exa) instead.
    
    This is FREE and doesn't consume credits.
    
    Args:
        keywords: Keywords to search (e.g., ["aerospace", "composites", "manufacturing"])
        states: US state names (e.g., ["Florida", "California", "Texas"])
        countries: Country names (e.g., ["United States", "Canada"])
        employee_ranges: Employee count ranges. Options:
            "1,10" (1-10 employees)
            "11,50" (11-50 employees)  
            "51,200" (51-200 employees)
            "201,500" (201-500 employees)
            "501,1000" (501-1000 employees)
            "1001,5000" (1001-5000 employees)
            "5001,10000" (5001-10000 employees)
            "10001+" (10000+ employees)
        min_revenue: Minimum annual revenue in USD (e.g., 10000000 for $10M, 100000000 for $100M)
        max_revenue: Maximum annual revenue in USD (None for no upper limit)
        industries: Industry filters (e.g., ["Manufacturing", "Aerospace & Defense", "Automotive"])
        num_results: Number of companies to return (max 25)
    
    Returns:
        JSON with matching companies including full firmographics.
    
    Examples:
    - "aerospace companies in Florida" → keywords=["aerospace"], states=["Florida"]
    - "manufacturers with >500 employees" → keywords=["manufacturing"], employee_ranges=["501,1000", "1001,5000", "5001,10000", "10001+"]
    - "composites suppliers with $50M+ revenue" → keywords=["composites"], min_revenue=50000000
    """
    logger.info(f"[Pipeline Tool] search_companies_filtered: keywords={keywords}, states={states}, "
               f"employees={employee_ranges}, min_revenue={min_revenue}, industries={industries}")
    
    try:
        organizations = await apollo_service.search_organizations(
            q_keywords=keywords,
            states=states,
            countries=countries,
            employee_ranges=employee_ranges,
            revenue_range_min=min_revenue,
            revenue_range_max=max_revenue,
            industries=industries,
            per_page=min(num_results, 25),
        )
        
        # Format results for display
        formatted = []
        
        # Secondary enrichment pass: get full profile data for each result
        # Apollo's /search endpoint returns sparse data; /enrich has full details
        async def enrich_single(org):
            """Fetch full enrichment data for a single org."""
            if not org.domain:
                return None
            try:
                enriched = await apollo_service.enrich_organization(org.domain)
                return enriched
            except Exception as e:
                logger.warning(f"[Pipeline] Secondary enrichment failed for {org.domain}: {e}")
                return None
        
        # Run enrichments in parallel
        enriched_orgs = await asyncio.gather(*[enrich_single(org) for org in organizations])
        
        for i, org in enumerate(organizations):
            # Use enriched data if available, fall back to search data
            enriched = enriched_orgs[i]
            
            # Build apollo_enrichment from the richer source
            if enriched:
                apollo_enrichment = {
                    "name": enriched.name or org.name,
                    "domain": enriched.domain or org.domain,
                    "description": enriched.description or org.description,
                    "logo_url": enriched.logo_url or org.logo_url or (f"https://logo.clearbit.com/{org.domain}" if org.domain else None),
                    "employee_count": enriched.employee_count or org.employee_count,
                    "founded_year": enriched.founded_year or org.founded_year,
                    "revenue_printed": enriched.revenue_printed or org.revenue_printed,
                    "annual_revenue": enriched.annual_revenue or org.annual_revenue,
                    "industry": enriched.industry or org.industry,
                    "city": enriched.city or org.city,
                    "state": enriched.state or org.state,
                    "country": enriched.country or org.country,
                    "linkedin_url": enriched.linkedin_url or org.linkedin_url,
                    "technologies": (enriched.technologies[:15] if enriched.technologies else []) or (org.technologies[:10] if org.technologies else []),
                    "keywords": (enriched.keywords[:10] if enriched.keywords else []) or (org.keywords[:10] if org.keywords else []),
                    "sic_codes": enriched.sic_codes or org.sic_codes or [],
                    "naics_codes": enriched.naics_codes or org.naics_codes or [],
                    "retail_location_count": enriched.retail_location_count or org.retail_location_count,
                    "suborganizations": (enriched.suborganizations[:10] if enriched.suborganizations else []) or ([s.get("name") if isinstance(s, dict) else s for s in (org.suborganizations or [])][:10]),
                }
            else:
                # Fall back to search-only data
                apollo_enrichment = {
                    "name": org.name,
                    "domain": org.domain,
                    "description": org.description,
                    "logo_url": org.logo_url or (f"https://logo.clearbit.com/{org.domain}" if org.domain else None),
                    "employee_count": org.employee_count,
                    "founded_year": org.founded_year,
                    "revenue_printed": org.revenue_printed,
                    "annual_revenue": org.annual_revenue,
                    "industry": org.industry,
                    "city": org.city,
                    "state": org.state,
                    "country": org.country,
                    "linkedin_url": org.linkedin_url,
                    "technologies": org.technologies[:10] if org.technologies else [],
                    "keywords": org.keywords[:10] if org.keywords else [],
                    "sic_codes": org.sic_codes or [],
                    "naics_codes": org.naics_codes or [],
                    "retail_location_count": org.retail_location_count,
                    "suborganizations": [s.get("name") if isinstance(s, dict) else s for s in (org.suborganizations or [])][:10],
                }
            
            formatted.append({
                "company_name": org.name,
                "domain": org.domain,
                "description": apollo_enrichment["description"] or "",
                "logo_url": apollo_enrichment["logo_url"],
                "employee_count": org.employee_count,
                "founded_year": apollo_enrichment["founded_year"],
                "industry": org.industry,
                "revenue_printed": org.revenue_printed,
                "annual_revenue": org.annual_revenue,
                "city": org.city,
                "state": org.state,
                "country": org.country,
                "address": org.raw_address,
                "phone": org.phone,
                "website": org.website_url,
                "linkedin_url": org.linkedin_url,
                "technologies": apollo_enrichment["technologies"][:5],
                "keywords": apollo_enrichment["keywords"][:5],
                # Full apollo_enrichment for profile drawer rendering
                "apollo_enrichment": apollo_enrichment,
            })

        
        # Build filter description for UI
        filters_applied = []
        if keywords:
            filters_applied.append(f"keywords: {', '.join(keywords)}")
        if states:
            filters_applied.append(f"states: {', '.join(states)}")
        if countries:
            filters_applied.append(f"countries: {', '.join(countries)}")
        if employee_ranges:
            filters_applied.append(f"employees: {', '.join(employee_ranges)}")
        if min_revenue:
            filters_applied.append(f"min revenue: ${min_revenue:,}")
        if max_revenue:
            filters_applied.append(f"max revenue: ${max_revenue:,}")
        if industries:
            filters_applied.append(f"industries: {', '.join(industries)}")
        
        return json.dumps({
            "status": "success",
            "query_type": "filtered_company_search",
            "filters_applied": filters_applied,
            "count": len(formatted),
            "results": formatted,
            "block_type": "filtered_companies",
            "title": f"Companies matching filters ({len(formatted)} results)",
            "note": "Results include full firmographic data from Apollo.io (FREE - no credits used)",
        }, indent=2)
        
    except Exception as e:
        logger.error(f"Error in search_companies_filtered: {e}", exc_info=True)
        return json.dumps({
            "status": "error",
            "error": str(e),
            "query_type": "filtered_company_search",
        })


@tool
async def get_apollo_credits() -> str:
    """
    Check Apollo.io credit usage and remaining balance.
    
    Use this before revealing contacts to show the user their credit status.
    
    Returns:
        JSON with credit usage stats.
    """
    try:
        credits = apollo_service.get_credit_status()
        return json.dumps({
            "status": "success",
            "credits": credits,
            "can_reveal": apollo_service.can_reveal(),
        }, indent=2)
    except Exception as e:
        return json.dumps({
            "status": "error",
            "error": str(e),
        })


# Export all tools for the Pipeline agent
# Note: PIPELINE_TOOLS_INSTANT is for quick search mode
# PIPELINE_TOOLS_FULL includes webset building for full list mode
PIPELINE_TOOLS_INSTANT = [
    # Exa.ai search tools (company discovery - semantic/broad search)
    find_similar_companies,
    search_companies,
    find_trigger_events,
    # Apollo.io enrichment tools (contacts + company data)
    enrich_company,
    search_companies_filtered,  # Apollo org search with firmographic filters (location, employees, revenue)
    find_company_contacts,      # Contact search - returns enriched profiles with departments, freshness
    # BigQuery corpus tools (intelligence integration)
    query_corpus,
    get_entity_mentions,
    get_competitor_activity,
]

PIPELINE_TOOLS_FULL = [
    # Exa.ai search tools (company discovery - semantic/broad search)
    find_similar_companies,
    search_companies,
    find_trigger_events,
    build_company_webset,
    # Apollo.io enrichment tools (contacts + company data)
    enrich_company,
    search_companies_filtered,  # Apollo org search with firmographic filters (location, employees, revenue)
    find_company_contacts,      # Contact search - returns enriched profiles with departments, freshness
    # BigQuery corpus tools (intelligence integration)
    query_corpus,
    get_entity_mentions,
    get_competitor_activity,
]

# Default: instant tools only (full list requires explicit mode)
PIPELINE_TOOLS = PIPELINE_TOOLS_INSTANT
