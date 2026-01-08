"""
Exa Pipeline API endpoints - Prospect discovery and contact search powered by Exa.ai.

This is the SALES PIPELINE (exa_pipeline) - for finding prospects and contacts.
NOT to be confused with the DATA INGESTION pipeline (ingestion_pipeline.py).

Enhanced with Logo.dev integration for company logos.
Enhanced with Apollo.io integration for company enrichment and contact discovery.
"""

from typing import Optional, List
import time
import uuid
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.services.exa_service import exa_service
from app.services.logo_service import logo_service
from app.services.exa_websets_service import exa_websets_service, get_all_websets
from app.services.apollo_service import apollo_service
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


# ============================================================================
# Request/Response Models (Legacy - kept for backward compatibility)
# ============================================================================

class ProspectResult(BaseModel):
    """A prospect/company result (legacy)."""
    title: str
    url: str
    description: str
    score: Optional[float] = None
    published_date: Optional[str] = None
    highlights: Optional[List[str]] = None


class ContactResult(BaseModel):
    """A contact/person result (legacy)."""
    name: str
    url: str
    snippet: str
    title: Optional[str] = None
    company: Optional[str] = None


# ============================================================================
# Enhanced Request/Response Models (with logo support)
# ============================================================================

class EnhancedProspectResult(BaseModel):
    """Enhanced prospect/company result with domain and logo."""
    title: str
    url: str
    description: str
    domain: str
    logo_url: Optional[str] = None
    score: Optional[float] = None
    published_date: Optional[str] = None
    highlights: Optional[List[str]] = None
    company_name: Optional[str] = None
    apollo_enrichment: Optional[dict] = None


class EnhancedContactResult(BaseModel):
    """Enhanced contact result with company logo."""
    name: str
    url: str
    snippet: str
    title: Optional[str] = None
    company: Optional[str] = None
    company_domain: Optional[str] = None
    logo_url: Optional[str] = None
    location: Optional[str] = None
    score: Optional[float] = None


class EnhancedTriggerEventResult(BaseModel):
    """Enhanced trigger event with company extraction."""
    title: str
    url: str
    summary: str
    source_domain: str
    published_date: Optional[str] = None
    event_type: Optional[str] = None
    highlights: Optional[List[str]] = None
    mentioned_company: Optional[str] = None
    mentioned_company_domain: Optional[str] = None
    logo_url: Optional[str] = None


# ============================================================================
# Request Models
# ============================================================================

class FindSimilarRequest(BaseModel):
    """Request to find similar companies."""
    reference_url: str = Field(..., description="URL of reference company to find similar to")
    num_results: int = Field(25, ge=1, le=100, description="Number of results")
    exclude_source: bool = Field(True, description="Exclude the reference company from results")


class SearchCompaniesRequest(BaseModel):
    """Request to search companies by description."""
    query: str = Field(..., description="Natural language search query")
    num_results: int = Field(25, ge=1, le=100, description="Number of results")
    include_domains: Optional[List[str]] = Field(None, description="Only search these domains")
    exclude_domains: Optional[List[str]] = Field(None, description="Exclude these domains")


class FindContactsRequest(BaseModel):
    """Request to find decision makers."""
    role: str = Field(..., description="Job title or role to search for")
    industry: Optional[str] = Field(None, description="Industry focus")
    company: Optional[str] = Field(None, description="Specific company name")
    num_results: int = Field(10, ge=1, le=50, description="Number of results")


class FindTriggerEventsRequest(BaseModel):
    """Request to find trigger events (news signals)."""
    topic: str = Field(..., description="Topic to search for (e.g., 'composites manufacturing expansion')")
    days_back: int = Field(30, ge=1, le=90, description="How many days back to search")
    num_results: int = Field(25, ge=1, le=100, description="Number of results")


# ============================================================================
# Response Models
# ============================================================================

class ProspectSearchResponse(BaseModel):
    """Response for prospect/company searches (legacy)."""
    count: int
    results: List[ProspectResult]
    query_type: str  # "similar" or "search"


class ContactSearchResponse(BaseModel):
    """Response for contact searches (legacy)."""
    count: int
    results: List[ContactResult]


class EnhancedProspectSearchResponse(BaseModel):
    """Enhanced response for prospect/company searches."""
    count: int
    results: List[EnhancedProspectResult]
    query_type: str  # "similar" or "search"


class EnhancedContactSearchResponse(BaseModel):
    """Enhanced response for contact searches."""
    count: int
    results: List[EnhancedContactResult]


class EnhancedTriggerEventSearchResponse(BaseModel):
    """Enhanced response for trigger event searches."""
    count: int
    results: List[EnhancedTriggerEventResult]


# ============================================================================
# Logo Proxy Endpoint
# ============================================================================

@router.get("/logo/{domain}")
async def get_company_logo(domain: str):
    """
    Proxy endpoint for fetching company logos from Logo.dev.
    
    This keeps the API token server-side and adds caching headers.
    
    Args:
        domain: Company domain (e.g., "gulfstream.com")
    
    Returns:
        PNG image of company logo, or 404 if not found
    """
    logger.debug(f"GET /pipeline/logo/{domain}")
    
    try:
        logo_bytes = await logo_service.fetch_logo(domain)
        
        if logo_bytes:
            return Response(
                content=logo_bytes,
                media_type="image/png",
                headers={
                    # Cache logos for 7 days (they rarely change)
                    "Cache-Control": "public, max-age=604800, immutable",
                    "X-Logo-Domain": domain,
                }
            )
        else:
            # Return 404 - frontend will show fallback
            raise HTTPException(status_code=404, detail=f"Logo not found for {domain}")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching logo for {domain}: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching logo: {str(e)}")


# ============================================================================
# Legacy Endpoints (backward compatible)
# ============================================================================

@router.post("/similar", response_model=ProspectSearchResponse)
async def find_similar_companies(request: FindSimilarRequest):
    """
    Find companies similar to a reference company (legacy endpoint).
    
    Use /v2/similar for enhanced results with logos.
    """
    logger.info(f"POST /pipeline/similar: url={request.reference_url}, num_results={request.num_results}")
    
    try:
        results = await exa_service.find_similar_companies(
            reference_url=request.reference_url,
            num_results=request.num_results,
            exclude_source=request.exclude_source
        )
        
        return ProspectSearchResponse(
            count=len(results),
            results=[
                ProspectResult(
                    title=r.title,
                    url=r.url,
                    description=r.description,
                    score=r.score,
                    highlights=r.highlights
                )
                for r in results
            ],
            query_type="similar"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error finding similar companies: {e}")
        raise HTTPException(status_code=500, detail=f"Error finding similar companies: {str(e)}")


@router.post("/search", response_model=ProspectSearchResponse)
async def search_companies(request: SearchCompaniesRequest):
    """
    Search for companies using natural language descriptions.
    
    Examples:
    - "fiberglass boat manufacturers in Florida"
    - "carbon fiber suppliers automotive OEM"
    - "composites manufacturers aerospace defense"
    """
    logger.info(f"POST /pipeline/search: query={request.query}, num_results={request.num_results}")
    
    try:
        results = await exa_service.search_companies(
            query=request.query,
            num_results=request.num_results,
            include_domains=request.include_domains,
            exclude_domains=request.exclude_domains
        )
        
        return ProspectSearchResponse(
            count=len(results),
            results=[
                ProspectResult(
                    title=r.title,
                    url=r.url,
                    description=r.description,
                    score=r.score,
                    published_date=r.published_date,
                    highlights=r.highlights
                )
                for r in results
            ],
            query_type="search"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error searching companies: {e}")
        raise HTTPException(status_code=500, detail=f"Error searching companies: {str(e)}")


@router.post("/contacts", response_model=ContactSearchResponse)
async def find_contacts(request: FindContactsRequest):
    """
    Find decision makers and contacts by role.
    
    Examples:
    - role="VP Operations", industry="composites manufacturing"
    - role="Purchasing Manager", company="Boeing"
    """
    logger.info(f"POST /pipeline/contacts: role={request.role}, industry={request.industry}, company={request.company}")
    
    try:
        results = await exa_service.find_decision_makers(
            role=request.role,
            industry=request.industry,
            company=request.company,
            num_results=request.num_results
        )
        
        return ContactSearchResponse(
            count=len(results),
            results=[
                ContactResult(
                    name=r.name,
                    url=r.url,
                    snippet=r.snippet,
                    title=r.title,
                    company=r.company
                )
                for r in results
            ]
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error finding contacts: {e}")
        raise HTTPException(status_code=500, detail=f"Error finding contacts: {str(e)}")


@router.get("/health")
async def pipeline_health():
    """Check if Pipeline/Exa service is available."""
    has_exa_key = exa_service.client is not None
    has_logo_key = logo_service.token is not None
    
    return {
        "status": "ok" if has_exa_key else "degraded",
        "exa_configured": has_exa_key,
        "logo_dev_configured": has_logo_key,
        "message": "Pipeline services configured" if has_exa_key else "EXA_API_KEY not set"
    }


# ============================================================================
# Enhanced Endpoints (v2 - with logos)
# ============================================================================

@router.post("/v2/similar", response_model=EnhancedProspectSearchResponse)
async def find_similar_companies_v2(request: FindSimilarRequest):
    """
    Find companies similar to a reference company (enhanced with logos).
    
    This is the highest-value feature - automated lookalike targeting.
    Given a URL of a known good customer, find similar companies.
    
    Returns enhanced results with:
    - domain: Extracted domain for each company
    - logo_url: Proxy URL for company logo
    - company_name: Cleaned company name
    """
    logger.info(f"POST /pipeline/v2/similar: url={request.reference_url}, num_results={request.num_results}")
    
    try:
        results = await exa_service.find_similar_companies_enhanced(
            reference_url=request.reference_url,
            num_results=request.num_results,
            exclude_source=request.exclude_source
        )
        
        return EnhancedProspectSearchResponse(
            count=len(results),
            results=[
                EnhancedProspectResult(
                    title=r.title,
                    url=r.url,
                    description=r.description,
                    domain=r.domain,
                    logo_url=r.logo_url,
                    score=r.score,
                    published_date=r.published_date,
                    highlights=r.highlights,
                    company_name=r.company_name,
                    apollo_enrichment=r.apollo_enrichment,
                )
                for r in results
            ],
            query_type="similar"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error finding similar companies: {e}")
        raise HTTPException(status_code=500, detail=f"Error finding similar companies: {str(e)}")


@router.post("/v2/search", response_model=EnhancedProspectSearchResponse)
async def search_companies_v2(request: SearchCompaniesRequest):
    """
    Search for companies using natural language (enhanced with logos).
    
    Examples:
    - "fiberglass boat manufacturers in Florida"
    - "carbon fiber suppliers automotive OEM"
    - "composites manufacturers aerospace defense"
    """
    logger.info(f"POST /pipeline/v2/search: query={request.query}, num_results={request.num_results}")
    
    try:
        results = await exa_service.search_companies_enhanced(
            query=request.query,
            num_results=request.num_results,
            include_domains=request.include_domains,
            exclude_domains=request.exclude_domains
        )
        
        return EnhancedProspectSearchResponse(
            count=len(results),
            results=[
                EnhancedProspectResult(
                    title=r.title,
                    url=r.url,
                    description=r.description,
                    domain=r.domain,
                    logo_url=r.logo_url,
                    score=r.score,
                    published_date=r.published_date,
                    highlights=r.highlights,
                    company_name=r.company_name,
                    apollo_enrichment=r.apollo_enrichment,
                )
                for r in results
            ],
            query_type="search"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error searching companies: {e}")
        raise HTTPException(status_code=500, detail=f"Error searching companies: {str(e)}")


@router.post("/v2/contacts", response_model=EnhancedContactSearchResponse)
async def find_contacts_v2(request: FindContactsRequest):
    """
    Find decision makers and contacts (enhanced with company logos).
    
    Examples:
    - role="VP Operations", industry="composites manufacturing"
    - role="Purchasing Manager", company="Boeing"
    """
    logger.info(f"POST /pipeline/v2/contacts: role={request.role}, industry={request.industry}, company={request.company}")
    
    try:
        results = await exa_service.find_decision_makers_enhanced(
            role=request.role,
            industry=request.industry,
            company=request.company,
            num_results=request.num_results
        )
        
        return EnhancedContactSearchResponse(
            count=len(results),
            results=[
                EnhancedContactResult(
                    name=r.name,
                    url=r.url,
                    snippet=r.snippet,
                    title=r.title,
                    company=r.company,
                    company_domain=r.company_domain,
                    logo_url=r.logo_url,
                    location=r.location,
                    score=r.score,
                )
                for r in results
            ]
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error finding contacts: {e}")
        raise HTTPException(status_code=500, detail=f"Error finding contacts: {str(e)}")


@router.post("/v2/triggers", response_model=EnhancedTriggerEventSearchResponse)
async def find_trigger_events_v2(request: FindTriggerEventsRequest):
    """
    Find trigger events / news signals (enhanced with company extraction).
    
    Trigger events include: expansions, funding, new facilities, 
    leadership changes, contract awards.
    
    Examples:
    - "composites manufacturing expansion"
    - "aerospace facility investment"
    - "carbon fiber production contract"
    """
    logger.info(f"POST /pipeline/v2/triggers: topic={request.topic}, days_back={request.days_back}")
    
    try:
        results = await exa_service.find_trigger_events_enhanced(
            topic=request.topic,
            days_back=request.days_back,
            num_results=request.num_results
        )
        
        return EnhancedTriggerEventSearchResponse(
            count=len(results),
            results=[
                EnhancedTriggerEventResult(
                    title=r.title,
                    url=r.url,
                    summary=r.summary,
                    source_domain=r.source_domain,
                    published_date=r.published_date,
                    event_type=r.event_type,
                    highlights=r.highlights,
                    mentioned_company=r.mentioned_company,
                    mentioned_company_domain=r.mentioned_company_domain,
                    logo_url=r.logo_url,
                )
                for r in results
            ]
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error finding trigger events: {e}")
        raise HTTPException(status_code=500, detail=f"Error finding trigger events: {str(e)}")


# ============================================================================
# Agent Chat Endpoint
# ============================================================================

class AgentChatRequest(BaseModel):
    """Request for agent-powered pipeline chat."""
    message: str = Field(..., description="User's natural language query")
    conversation_history: Optional[List[dict]] = Field(
        default=None,
        description="Previous conversation messages for context"
    )
    mode: Optional[str] = Field(
        default="instant",
        description="Search mode: 'instant' for quick search, 'full' for comprehensive lists with websets"
    )


class SearchBlockResponse(BaseModel):
    """A single search block in the agent response."""
    id: str
    block_type: str  # similar_companies, search_companies, contacts, trigger_events, webset_building
    title: str
    query_context: str
    prospects: Optional[List[EnhancedProspectResult]] = None
    contacts: Optional[List[EnhancedContactResult]] = None
    trigger_events: Optional[List[EnhancedTriggerEventResult]] = None
    # Webset fields
    webset_id: Optional[str] = None
    webset_name: Optional[str] = None
    webset_status: Optional[str] = None
    result_count: int
    is_expanded: bool = True


class AgentChatResponse(BaseModel):
    """Response from the Pipeline agent."""
    message: str = Field(..., description="Agent's response message")
    search_blocks: List[SearchBlockResponse] = Field(
        default_factory=list,
        description="Search result blocks to display in the UI"
    )
    suggested_followups: List[str] = Field(
        default_factory=list,
        description="Suggested follow-up questions"
    )
    requires_confirmation: bool = Field(
        default=False,
        description="Whether agent needs user confirmation before searching"
    )
    confirmation_prompt: Optional[str] = Field(
        default=None,
        description="What to ask user for confirmation"
    )


@router.post("/agent/chat", response_model=AgentChatResponse)
async def agent_chat(request: AgentChatRequest):
    """
    Agent-powered pipeline chat endpoint.
    
    Send natural language queries to the Pipeline Agent, which will:
    1. Understand your intent
    2. Execute appropriate searches (similar companies, search, contacts, triggers)
    3. Return structured results as SearchBlocks for the UI
    
    Examples:
    - "Find companies similar to hexcel.com"
    - "Search for composites manufacturers in the Pacific Northwest"
    - "Find purchasing managers at aerospace suppliers"
    - "What composites companies are expanding?"
    
    The agent maintains conversation context for follow-up questions.
    """
    request_start = time.time()
    request_id = str(uuid.uuid4())[:8]  # Short ID for log filtering
    history_len = len(request.conversation_history) if request.conversation_history else 0
    message_preview = request.message[:100] + ("..." if len(request.message) > 100 else "")
    
    logger.info(
        f"[PIPELINE_API] Request {request_id} START: message='{message_preview}', "
        f"mode={request.mode}, history_len={history_len}"
    )
    
    try:
        from app.agents.pipeline import get_pipeline_agent
        
        # Get agent for the requested mode
        agent_init_start = time.time()
        agent = get_pipeline_agent(request.mode or "instant")
        agent_init_elapsed = time.time() - agent_init_start
        logger.info(
            f"[PIPELINE_API] Request {request_id}: agent initialized, mode={request.mode}, "
            f"{agent_init_elapsed:.3f}s"
        )
        
        # Process the query through the agent
        agent_exec_start = time.time()
        logger.info(f"[PIPELINE_API] Request {request_id}: calling agent.process_query")
        
        response = await agent.process_query(
            user_query=request.message,
            conversation_history=request.conversation_history,
        )
        
        agent_exec_elapsed = time.time() - agent_exec_start
        logger.info(
            f"[PIPELINE_API] Request {request_id}: agent.process_query COMPLETE, "
            f"{agent_exec_elapsed:.2f}s, {len(response.search_blocks)} blocks returned"
        )
        
        # Convert internal SearchBlock models to response models
        convert_start = time.time()
        search_blocks_response = []
        for idx, block in enumerate(response.search_blocks, 1):
            # Convert prospect results if present
            prospects = None
            if block.prospects:
                prospects = [
                    EnhancedProspectResult(
                        title=p.title,
                        url=p.url,
                        description=p.description,
                        domain=p.domain or "",
                        logo_url=p.logo_url,
                        company_name=p.company_name,
                        score=p.score,
                        published_date=p.published_date,
                        apollo_enrichment=p.apollo_enrichment,
                    )
                    for p in block.prospects
                ]
            
            # Convert contact results if present
            contacts = None
            if block.contacts:
                contacts = [
                    EnhancedContactResult(
                        name=c.name,
                        url=c.url,
                        snippet=c.snippet,
                        title=c.title,
                        company=c.company,
                        company_domain=c.company_domain,
                        logo_url=c.logo_url,
                    )
                    for c in block.contacts
                ]
            
            # Convert trigger event results if present
            trigger_events = None
            if block.trigger_events:
                trigger_events = [
                    EnhancedTriggerEventResult(
                        title=t.title,
                        url=t.url,
                        summary=t.summary,
                        source_domain=t.mentioned_company_domain or "",
                        event_type=t.event_type,
                        mentioned_company=t.mentioned_company,
                        mentioned_company_domain=t.mentioned_company_domain,
                        logo_url=t.logo_url,
                        published_date=t.published_date,
                    )
                    for t in block.trigger_events
                ]
            
            search_blocks_response.append(SearchBlockResponse(
                id=block.id,
                block_type=block.block_type,
                title=block.title,
                query_context=block.query_context,
                prospects=prospects,
                contacts=contacts,
                trigger_events=trigger_events,
                webset_id=block.webset_id,
                webset_name=block.webset_name,
                webset_status=block.webset_status,
                result_count=block.result_count,
                is_expanded=block.is_expanded,
            ))
        
        convert_elapsed = time.time() - convert_start
        logger.info(
            f"[PIPELINE_API] Request {request_id}: converted {len(search_blocks_response)} blocks, "
            f"{convert_elapsed:.3f}s"
        )
        
        total_elapsed = time.time() - request_start
        logger.info(
            f"[PIPELINE_API] Request {request_id} COMPLETE: {total_elapsed:.2f}s total, "
            f"message_len={len(response.message)}, blocks={len(search_blocks_response)}, "
            f"followups={len(response.suggested_followups)}"
        )
        
        return AgentChatResponse(
            message=response.message,
            search_blocks=search_blocks_response,
            suggested_followups=response.suggested_followups,
            requires_confirmation=response.requires_confirmation,
            confirmation_prompt=response.confirmation_prompt,
        )
        
    except Exception as e:
        total_elapsed = time.time() - request_start
        logger.error(
            f"[PIPELINE_API] Request {request_id} FAILED: {total_elapsed:.2f}s, "
            f"error_type={type(e).__name__}, error={str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Error processing your request: {str(e)}"
        )


# ============================================================================
# Webset Endpoints (Full List Mode)
# ============================================================================

class WebsetStatusResponse(BaseModel):
    """Response for webset status polling."""
    webset_id: str
    status: str  # "running", "completed", "failed", "idle"
    progress: Optional[int] = None
    total_items: Optional[int] = None
    completed_items: Optional[int] = None
    created_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None


class WebsetItemResponse(BaseModel):
    """A single item from a webset."""
    url: str
    title: Optional[str] = None
    description: Optional[str] = None
    domain: Optional[str] = None
    logo_url: Optional[str] = None
    employee_count: Optional[str] = None
    funding_info: Optional[str] = None
    location: Optional[str] = None
    linkedin_url: Optional[str] = None
    relevance_score: Optional[float] = None


class WebsetResultsResponse(BaseModel):
    """Response for webset results."""
    webset_id: str
    name: str
    status: str
    total_count: int
    items: List[WebsetItemResponse]
    query_description: Optional[str] = None
    created_at: Optional[str] = None


class WebsetListItem(BaseModel):
    """Summary of a webset for listing."""
    webset_id: str
    name: str
    query_description: Optional[str] = None
    status: str
    total_count: int
    created_at: Optional[str] = None
    completed_at: Optional[str] = None


@router.get("/webset/{webset_id}/status", response_model=WebsetStatusResponse)
async def get_webset_status(webset_id: str):
    """
    Poll the status of a webset building job.
    
    Use this endpoint to check if a webset is still building,
    completed, or failed. Frontend should poll every 5-10 seconds
    while status is "running".
    
    Args:
        webset_id: The webset ID returned from build_company_webset tool
    
    Returns:
        Current status of the webset
    """
    logger.info(f"GET /pipeline/webset/{webset_id}/status")
    
    try:
        status = await exa_websets_service.get_webset_status(webset_id)
        
        if status:
            return WebsetStatusResponse(
                webset_id=status.webset_id,
                status=status.status,
                progress=status.progress,
                total_items=status.total_items,
                completed_items=status.completed_items,
                created_at=status.created_at,
                completed_at=status.completed_at,
                error_message=status.error_message,
            )
        else:
            raise HTTPException(status_code=404, detail=f"Webset {webset_id} not found")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting webset status: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting webset status: {str(e)}")


@router.get("/webset/{webset_id}/results", response_model=WebsetResultsResponse)
async def get_webset_results(webset_id: str):
    """
    Get the results of a completed webset.
    
    Returns all items with enrichments (employee count, funding, location, etc).
    Only call this after status shows "completed".
    
    Args:
        webset_id: The webset ID to fetch results for
    
    Returns:
        Full webset results with all enrichment data
    """
    logger.info(f"GET /pipeline/webset/{webset_id}/results")
    
    try:
        result = await exa_websets_service.get_webset_results(webset_id)
        
        if result:
            items = [
                WebsetItemResponse(
                    url=item.url,
                    title=item.title,
                    description=item.description,
                    domain=item.domain,
                    logo_url=item.logo_url,
                    employee_count=item.employee_count,
                    funding_info=item.funding_info,
                    location=item.location,
                    linkedin_url=item.linkedin_url,
                    relevance_score=item.relevance_score,
                )
                for item in result.items
            ]
            
            return WebsetResultsResponse(
                webset_id=result.webset_id,
                name=result.name,
                status=result.status,
                total_count=result.total_count,
                items=items,
                query_description=result.query_description,
                created_at=result.created_at,
            )
        else:
            raise HTTPException(status_code=404, detail=f"Webset {webset_id} not found or results not available")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting webset results: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting webset results: {str(e)}")


@router.get("/websets", response_model=List[WebsetListItem])
async def list_websets():
    """
    List all websets (recent 50).
    
    Returns summary info for each webset including status.
    Use webset_id from this list to fetch full results.
    """
    logger.info("GET /pipeline/websets")
    
    try:
        websets = get_all_websets()
        
        return [
            WebsetListItem(
                webset_id=w["webset_id"],
                name=w["name"],
                query_description=w.get("query_description"),
                status=w["status"],
                total_count=w.get("total_count", 0),
                created_at=w.get("created_at"),
                completed_at=w.get("completed_at"),
            )
            for w in websets
        ]
        
    except Exception as e:
        logger.error(f"Error listing websets: {e}")
        raise HTTPException(status_code=500, detail=f"Error listing websets: {str(e)}")


# ============================================================================
# Apollo.io Endpoints - Company Enrichment & Contact Discovery
# ============================================================================

class ApolloOrganizationResponse(BaseModel):
    """Company enrichment data from Apollo.io."""
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
    revenue_printed: Optional[str] = None
    
    # Location
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    address: Optional[str] = None
    
    # Contact
    phone: Optional[str] = None
    website_url: Optional[str] = None
    
    # Social
    linkedin_url: Optional[str] = None
    twitter_url: Optional[str] = None
    facebook_url: Optional[str] = None
    
    # Stock
    ticker: Optional[str] = None
    exchange: Optional[str] = None
    
    # Tech & Keywords
    technologies: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    
    # Industry Codes
    sic_codes: List[str] = Field(default_factory=list)
    naics_codes: List[str] = Field(default_factory=list)


class ApolloContactTeaserResponse(BaseModel):
    """Contact teaser (preview) from Apollo - no credits used."""
    id: str
    first_name: str
    last_name_obfuscated: Optional[str] = None
    name: Optional[str] = None  # Computed: first + obfuscated last
    title: Optional[str] = None
    seniority: Optional[str] = None
    company_name: Optional[str] = None
    company_domain: Optional[str] = None
    has_email: bool = False
    has_phone: bool = False
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    linkedin_url: Optional[str] = None


class ApolloContactRevealedResponse(BaseModel):
    """Full contact details from Apollo - costs 1 credit."""
    id: str
    name: str
    first_name: str
    last_name: str
    title: Optional[str] = None
    seniority: Optional[str] = None
    photo_url: Optional[str] = None
    
    # Contact Info - the valuable stuff!
    email: Optional[str] = None
    email_status: Optional[str] = None
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    twitter_url: Optional[str] = None
    
    # Location
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    timezone: Optional[str] = None
    
    # Employment History
    employment_history: List[dict] = Field(default_factory=list)
    
    # Current Company
    company_name: Optional[str] = None
    company_domain: Optional[str] = None
    company_industry: Optional[str] = None
    company_employee_count: Optional[int] = None
    company_revenue: Optional[str] = None


class ApolloContactSearchRequest(BaseModel):
    """Request to search for contacts at a company."""
    company_name: Optional[str] = Field(None, description="Company name (e.g., 'Hexcel Corporation')")
    company_domain: Optional[str] = Field(None, description="Company domain (e.g., 'hexcel.com') - more accurate")
    titles: Optional[List[str]] = Field(None, description="Specific job titles to search")
    department: Optional[str] = Field(None, description="Department filter: 'purchasing', 'engineering', or 'executive'")
    seniorities: Optional[List[str]] = Field(None, description="Seniority levels like 'director', 'vp', 'c_suite'")
    num_results: int = Field(10, ge=1, le=25, description="Number of results (max 25)")


class ApolloContactSearchResponse(BaseModel):
    """Response for contact search."""
    count: int
    company: Optional[str] = None
    results: List[ApolloContactTeaserResponse]
    note: str = "These are contact previews. Use /apollo/reveal to get full email (costs 1 credit)."


class ApolloRevealRequest(BaseModel):
    """Request to reveal contact details."""
    person_id: str = Field(..., description="Apollo person ID from contact search results")


class ApolloCreditStatusResponse(BaseModel):
    """Apollo credit usage status."""
    used: int
    remaining: int
    limit: int
    reset_date: str
    utilization: str
    can_reveal: bool


@router.get("/apollo/enrich/{domain}", response_model=ApolloOrganizationResponse)
async def enrich_company(domain: str):
    """
    Get comprehensive company data from Apollo.io.
    
    This is FREE and doesn't consume credits.
    Returns firmographics, location, tech stack, social profiles, and more.
    
    Args:
        domain: Company domain (e.g., "hexcel.com", "boeing.com")
    
    Returns:
        Enriched company data
    """
    logger.info(f"GET /pipeline/apollo/enrich/{domain}")
    
    try:
        org = await apollo_service.enrich_organization(domain)
        
        if not org:
            raise HTTPException(status_code=404, detail=f"No company data found for {domain}")
        
        return ApolloOrganizationResponse(
            name=org.name,
            domain=org.domain,
            description=org.description,
            logo_url=org.logo_url,
            employee_count=org.employee_count,
            founded_year=org.founded_year,
            industry=org.industry,
            annual_revenue=org.annual_revenue,
            revenue_printed=org.revenue_printed,
            city=org.city,
            state=org.state,
            country=org.country,
            address=org.raw_address,
            phone=org.phone,
            website_url=org.website_url,
            linkedin_url=org.linkedin_url,
            twitter_url=org.twitter_url,
            facebook_url=org.facebook_url,
            ticker=org.ticker,
            exchange=org.exchange,
            technologies=org.technologies or [],
            keywords=org.keywords or [],
            sic_codes=org.sic_codes or [],
            naics_codes=org.naics_codes or [],
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error enriching company {domain}: {e}")
        raise HTTPException(status_code=500, detail=f"Error enriching company: {str(e)}")


@router.post("/apollo/contacts", response_model=ApolloContactSearchResponse)
async def search_contacts(request: ApolloContactSearchRequest):
    """
    Find decision makers at a company.
    
    This is FREE and doesn't consume credits.
    Returns contact TEASERS (preview data) - use /apollo/reveal to get full details.
    
    Examples:
    - Search by domain: {"company_domain": "hexcel.com", "department": "purchasing"}
    - Search by name: {"company_name": "Boeing", "titles": ["Materials Manager"]}
    """
    logger.info(f"POST /pipeline/apollo/contacts: {request.company_name or request.company_domain}")
    
    if not request.company_name and not request.company_domain:
        raise HTTPException(
            status_code=400,
            detail="Either company_name or company_domain must be provided"
        )
    
    try:
        contacts = await apollo_service.search_contacts(
            organization_name=request.company_name,
            organization_domain=request.company_domain,
            titles=request.titles,
            department=request.department,
            seniorities=request.seniorities,
            per_page=request.num_results,
        )
        
        results = [
            ApolloContactTeaserResponse(
                id=c.id,
                first_name=c.first_name,
                last_name_obfuscated=c.last_name_obfuscated,
                name=f"{c.first_name} {c.last_name_obfuscated or ''}".strip(),
                title=c.title,
                seniority=c.seniority,
                company_name=c.company_name,
                company_domain=c.company_domain,
                has_email=c.has_email,
                has_phone=c.has_phone,
                city=c.city,
                state=c.state,
                country=c.country,
                linkedin_url=c.linkedin_url,
            )
            for c in contacts
        ]
        
        return ApolloContactSearchResponse(
            count=len(results),
            company=request.company_name or request.company_domain,
            results=results,
        )
        
    except Exception as e:
        logger.error(f"Error searching contacts: {e}")
        raise HTTPException(status_code=500, detail=f"Error searching contacts: {str(e)}")


@router.post("/apollo/reveal", response_model=ApolloContactRevealedResponse)
async def reveal_contact(request: ApolloRevealRequest):
    """
    Reveal full contact details including verified email.
    
    ⚠️ COSTS 1 CREDIT - use judiciously!
    
    Check /apollo/credits first to see remaining balance.
    
    Args:
        person_id: Apollo person ID from contact search results
    
    Returns:
        Full contact profile with email, phone, and employment history
    """
    logger.info(f"POST /pipeline/apollo/reveal: {request.person_id}")
    
    # Check credit availability
    if not apollo_service.can_reveal():
        credits = apollo_service.get_credit_status()
        raise HTTPException(
            status_code=429,
            detail=f"Monthly credit limit reached. Resets: {credits['reset_date']}"
        )
    
    try:
        contact = await apollo_service.reveal_contact(request.person_id)
        
        if not contact:
            raise HTTPException(status_code=404, detail="Contact not found or reveal failed")
        
        return ApolloContactRevealedResponse(
            id=contact.id,
            name=contact.name,
            first_name=contact.first_name,
            last_name=contact.last_name,
            title=contact.title,
            seniority=contact.seniority,
            photo_url=contact.photo_url,
            email=contact.email,
            email_status=contact.email_status,
            phone=contact.phone,
            linkedin_url=contact.linkedin_url,
            twitter_url=contact.twitter_url,
            city=contact.city,
            state=contact.state,
            country=contact.country,
            timezone=contact.timezone,
            employment_history=contact.employment_history or [],
            company_name=contact.company_name,
            company_domain=contact.company_domain,
            company_industry=contact.company_industry,
            company_employee_count=contact.company_employee_count,
            company_revenue=contact.company_revenue_printed,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error revealing contact: {e}")
        raise HTTPException(status_code=500, detail=f"Error revealing contact: {str(e)}")


@router.get("/apollo/credits", response_model=ApolloCreditStatusResponse)
async def get_apollo_credits():
    """
    Check Apollo.io credit usage and remaining balance.
    
    Use this before revealing contacts to check credit availability.
    Plan: 2,500 credits/month at $60/mo.
    """
    logger.info("GET /pipeline/apollo/credits")
    
    try:
        credits = apollo_service.get_credit_status()
        return ApolloCreditStatusResponse(
            used=credits["used"],
            remaining=credits["remaining"],
            limit=credits["limit"],
            reset_date=credits["reset_date"],
            utilization=credits["utilization"],
            can_reveal=apollo_service.can_reveal(),
        )
    except Exception as e:
        logger.error(f"Error getting credit status: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting credit status: {str(e)}")


@router.get("/apollo/health")
async def apollo_health():
    """Check if Apollo.io service is configured and available."""
    has_key = bool(apollo_service.api_key)
    credits = apollo_service.get_credit_status() if has_key else None
    
    return {
        "status": "ok" if has_key else "not_configured",
        "apollo_configured": has_key,
        "credits": credits,
        "message": "Apollo.io service ready" if has_key else "APOLLO_API_KEY not set"
    }
