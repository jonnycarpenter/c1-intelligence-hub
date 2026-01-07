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
) -> str:
    """
    Find companies similar to a reference company (URL or name).
    
    This is the highest-value prospecting tool - automated lookalike targeting.
    Given a website URL or Name of a known good customer, find similar companies.
    
    Args:
        reference: Website URL or Company Name of a reference company (e.g., "hexcel.com", "Hexcel", "Boeing")
        num_results: Number of similar companies to find (default 25, max 100)
    
    Returns:
        JSON list of similar companies with domains and logo URLs for display.
    
    Example queries this tool answers:
    - "Find companies similar to compositesone.com"
    - "Who are Hexcel's competitors?"
    - "Find lookalikes for our best customer Boeing"
    """
    logger.info(f"Tool find_similar_companies: reference={reference}, num_results={num_results}")
    
    try:
        # Use the enhanced similarity search which supports names/URLs and Apollo enrichment
        results = await exa_service.find_similar_companies_enhanced(
            reference=reference,
            num_results=num_results
        )
        
        formatted = _format_prospect_results(results)
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
) -> str:
    """
    Search for companies using natural language descriptions.
    
    Semantic search that understands industry terms, locations, and company characteristics.
    
    Args:
        query: Natural language description of companies to find
        num_results: Number of results (default 25, max 100)
        include_domains: Only search these domains (optional)
        exclude_domains: Exclude these domains from results (optional)
    
    Returns:
        JSON list of matching companies with domains and logo URLs.
    
    Example queries:
    - "fiberglass boat manufacturers in Florida"
    - "carbon fiber suppliers to automotive OEMs"
    - "composites manufacturers with aerospace certifications"
    - "wind turbine blade manufacturers in the midwest"
    """
    logger.info(f"[Pipeline Tool] search_companies: {query}")
    
    try:
        results = await exa_service.search_companies_enhanced(
            query=query,
            num_results=min(num_results, 100),
            include_domains=include_domains,
            exclude_domains=exclude_domains,
        )
        
        formatted = _format_prospect_results(results)
        
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
    
    This returns contact TEASERS (preview data) - no credits consumed.
    Shows first name, obfuscated last name, title, and whether email is available.
    Use reveal_contact to get full details (costs 1 credit).
    
    Args:
        company_name: Company name (e.g., "Hexcel Corporation")
        company_domain: Company domain (e.g., "hexcel.com") - more accurate than name
        titles: Specific job titles (e.g., ["Purchasing Manager", "VP Supply Chain"])
        department: Department filter - "purchasing", "engineering", or "executive"
        seniorities: Seniority levels (e.g., ["director", "vp", "c_suite"])
        num_results: Number of contacts to find (max 25)
    
    Returns:
        JSON list of contact teasers with has_email flag.
    
    Example:
    - find_company_contacts(company_domain="hexcel.com", department="purchasing")
    - find_company_contacts(company_name="Boeing", titles=["Materials Manager"])
    """
    logger.info(f"[Pipeline Tool] find_company_contacts: {company_name or company_domain}")
    
    try:
        contacts = await apollo_service.search_contacts(
            organization_name=company_name,
            organization_domain=company_domain,
            titles=titles,
            department=department,
            seniorities=seniorities,
            per_page=min(num_results, 25),
        )
        
        formatted = [
            {
                "id": c.id,
                "name": f"{c.first_name} {c.last_name_obfuscated or ''}".strip(),
                "first_name": c.first_name,
                "title": c.title,
                "seniority": c.seniority,
                "company": c.company_name,
                "company_domain": c.company_domain,
                "has_email": c.has_email,
                "has_phone": c.has_phone,
                "city": c.city,
                "state": c.state,
                "country": c.country,
                "linkedin_url": c.linkedin_url,
            }
            for c in contacts
        ]
        
        return json.dumps({
            "status": "success",
            "query_type": "apollo_contacts",
            "company": company_name or company_domain,
            "count": len(formatted),
            "results": formatted,
            "note": "These are contact previews. Use reveal_contact with the ID to get full email (costs 1 credit).",
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
    
    ⚠️ COSTS 1 CREDIT - always confirm with user before using!
    
    Before calling this, you MUST:
    1. Tell the user this costs 1 credit
    2. Show them remaining credits
    3. Get their explicit approval
    
    Args:
        person_id: Apollo person ID from find_company_contacts results
        contact_name: Optional name for logging/confirmation
    
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
    # Exa.ai search tools (company discovery)
    find_similar_companies,
    search_companies,
    # NOTE: find_contacts (Exa) is commented out in favor of find_company_contacts (Apollo)
    # Exa returns LinkedIn profiles without person_id, making reveal_contact impossible.
    # Apollo provides structured contacts with IDs for email/phone reveal.
    # TODO: Future enhancement - combine Exa broad search with Apollo data enrichment
    # find_contacts,
    find_trigger_events,
    # Apollo.io enrichment tools (contacts + company data)
    enrich_company,
    find_company_contacts,  # PRIMARY contact search tool - returns revealable contacts
    reveal_contact,
    get_apollo_credits,
    # BigQuery corpus tools (intelligence integration)
    query_corpus,
    get_entity_mentions,
    get_competitor_activity,
]

PIPELINE_TOOLS_FULL = [
    # Exa.ai search tools (company discovery)
    find_similar_companies,
    search_companies,
    # NOTE: find_contacts (Exa) commented out - see note in PIPELINE_TOOLS_INSTANT
    # find_contacts,
    find_trigger_events,
    build_company_webset,
    # Apollo.io enrichment tools (contacts + company data)
    enrich_company,
    find_company_contacts,  # PRIMARY contact search tool - returns revealable contacts
    reveal_contact,
    get_apollo_credits,
    # BigQuery corpus tools (intelligence integration)
    query_corpus,
    get_entity_mentions,
    get_competitor_activity,
]

# Default: instant tools only (full list requires explicit mode)
PIPELINE_TOOLS = PIPELINE_TOOLS_INSTANT
