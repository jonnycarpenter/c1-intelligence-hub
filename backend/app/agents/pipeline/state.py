"""
Pipeline Agent State - TypedDict state for pipeline prospect discovery workflow.
"""

from typing import TypedDict, List, Optional, Annotated, Literal
from pydantic import BaseModel, Field
from operator import add


# ============================================================================
# Pydantic Models for Structured Output
# ============================================================================

class ProspectResult(BaseModel):
    """A single prospect company result."""
    title: str = Field(description="Page title or company name")
    company_name: Optional[str] = Field(default=None, description="Extracted company name")
    url: str = Field(description="Source URL")
    domain: Optional[str] = Field(default=None, description="Company domain for logo lookup")
    logo_url: Optional[str] = Field(default=None, description="Logo.dev URL for company logo")
    description: str = Field(description="Brief description or snippet")
    score: Optional[float] = Field(default=None, description="Relevance score")
    apollo_enrichment: Optional[dict] = Field(default=None, description="Pre-populated enrichment data")
    published_date: Optional[str] = Field(default=None, description="Publish date")


class ContactResult(BaseModel):
    """A single contact/decision maker result."""
    name: str = Field(description="Person's name")
    title: Optional[str] = Field(default=None, description="Job title")
    company: Optional[str] = Field(default=None, description="Company name")
    company_domain: Optional[str] = Field(default=None, description="Company domain for logo")
    logo_url: Optional[str] = Field(default=None, description="Logo.dev URL")
    url: str = Field(description="Profile URL (LinkedIn, etc.)")
    snippet: str = Field(description="Context snippet")


class TriggerEventResult(BaseModel):
    """A single trigger event result."""
    title: str = Field(description="Event/article title")
    url: str = Field(description="Source URL")
    summary: str = Field(description="Event summary")
    event_type: str = Field(description="Type: expansion, funding, contract, etc.")
    mentioned_company: Optional[str] = Field(default=None, description="Company mentioned")
    mentioned_company_domain: Optional[str] = Field(default=None, description="Company domain")
    logo_url: Optional[str] = Field(default=None, description="Logo.dev URL")
    published_date: Optional[str] = Field(default=None, description="When published")


# ============================================================================
# Apollo.io Result Models
# ============================================================================

class ApolloEnrichmentResult(BaseModel):
    """Enriched company data from Apollo.io."""
    # Identity
    name: str = Field(description="Company name")
    domain: str = Field(description="Company domain")
    description: Optional[str] = Field(default=None, description="Company description")
    logo_url: Optional[str] = Field(default=None, description="Company logo URL")
    
    # Firmographics
    employee_count: Optional[int] = Field(default=None, description="Number of employees")
    founded_year: Optional[int] = Field(default=None, description="Year founded")
    industry: Optional[str] = Field(default=None, description="Industry classification")
    annual_revenue: Optional[float] = Field(default=None, description="Annual revenue in USD")
    revenue_printed: Optional[str] = Field(default=None, description="Revenue formatted")
    
    # Location
    city: Optional[str] = Field(default=None, description="City")
    state: Optional[str] = Field(default=None, description="State")
    country: Optional[str] = Field(default=None, description="Country")
    headquarters: Optional[str] = Field(default=None, description="City, State, Country")
    
    # Contact & Web
    phone: Optional[str] = Field(default=None, description="Company phone")
    linkedin_url: Optional[str] = Field(default=None, description="LinkedIn profile")
    
    # Tech & Classification
    technologies: List[str] = Field(default_factory=list, description="Tech stack")
    keywords: List[str] = Field(default_factory=list, description="Keywords/tags")
    supply_chain_matches: List[str] = Field(default_factory=list, description="Matching supply chain terms")
    linkedin_url: Optional[str] = Field(default=None, description="LinkedIn profile")
    website_url: Optional[str] = Field(default=None, description="Company website")
    
    # Stock info
    ticker: Optional[str] = Field(default=None, description="Stock ticker")


class ApolloContactTeaserResult(BaseModel):
    """Contact preview from Apollo.io (FREE - no credits used)."""
    id: str = Field(description="Apollo person ID - use for reveal")
    first_name: str = Field(description="First name")
    last_name_preview: Optional[str] = Field(default=None, description="Last name (obfuscated in teaser)")
    name_display: Optional[str] = Field(default=None, description="Display name")
    title: Optional[str] = Field(default=None, description="Job title")
    seniority: Optional[str] = Field(default=None, description="Seniority level")
    department: Optional[str] = Field(default=None, description="Department")
    company_name: Optional[str] = Field(default=None, description="Company name")
    company_domain: Optional[str] = Field(default=None, description="Company domain for logo")
    logo_url: Optional[str] = Field(default=None, description="Company logo URL")
    has_email: bool = Field(default=False, description="Can reveal email?")
    has_phone: bool = Field(default=False, description="Can reveal phone?")
    linkedin_url: Optional[str] = Field(default=None, description="LinkedIn profile URL")
    location: Optional[str] = Field(default=None, description="City, State")


class ApolloContactRevealedResult(BaseModel):
    """Full contact details from Apollo.io (COSTS 1 CREDIT)."""
    id: str = Field(description="Apollo person ID")
    name: str = Field(description="Full name")
    first_name: str = Field(description="First name")
    last_name: str = Field(description="Last name")
    title: Optional[str] = Field(default=None, description="Job title")
    seniority: Optional[str] = Field(default=None, description="Seniority level")
    photo_url: Optional[str] = Field(default=None, description="Profile photo")
    
    # The good stuff
    email: Optional[str] = Field(default=None, description="Verified email address")
    email_status: Optional[str] = Field(default=None, description="Email verification status")
    phone: Optional[str] = Field(default=None, description="Direct phone number")
    linkedin_url: Optional[str] = Field(default=None, description="LinkedIn URL")
    
    # Company info
    company_name: Optional[str] = Field(default=None, description="Current company")
    company_domain: Optional[str] = Field(default=None, description="Company domain")
    logo_url: Optional[str] = Field(default=None, description="Company logo")
    
    # Location
    location: Optional[str] = Field(default=None, description="City, State, Country")


class ApolloCreditStatus(BaseModel):
    """Apollo.io credit usage status."""
    used: int = Field(description="Credits used this period")
    remaining: int = Field(description="Credits remaining")
    limit: int = Field(description="Total monthly limit")
    reset_date: str = Field(description="When credits reset")
    utilization: str = Field(description="Usage percentage")
    can_reveal: bool = Field(description="Have credits available?")


class WebsetBlock(BaseModel):
    """
    A block representing a webset that's building or completed.
    Used for async full list building with enrichments.
    """
    webset_id: str = Field(description="Exa webset ID for polling")
    name: str = Field(description="Display name for the webset")
    status: Literal["running", "completed", "failed"] = Field(description="Current status")
    total_count: int = Field(default=0, description="Number of results when complete")
    query_description: Optional[str] = Field(default=None, description="What was searched for")


class SearchBlock(BaseModel):
    """
    A single search block containing one type of search results.
    Multiple SearchBlocks stack in the UI to show all results from a query.
    """
    id: str = Field(description="Unique ID for this block (uuid)")
    block_type: Literal[
        "similar_companies", 
        "search_companies", 
        "contacts", 
        "trigger_events", 
        "webset_building",
        "apollo_enrichment",
        "apollo_contacts",
        "apollo_contact_revealed",
        "apollo_credits",
    ] = Field(description="Type of search performed")
    title: str = Field(description="Human-readable title for the block")
    query_context: str = Field(description="What the user asked for (for reference)")
    
    # Results - only one will be populated based on block_type
    prospects: Optional[List[ProspectResult]] = Field(default=None, description="For similar_companies and search_companies")
    contacts: Optional[List[ContactResult]] = Field(default=None, description="For contacts search")
    trigger_events: Optional[List[TriggerEventResult]] = Field(default=None, description="For trigger events")
    
    # Apollo.io results
    apollo_enrichment: Optional[ApolloEnrichmentResult] = Field(default=None, description="For apollo_enrichment")
    apollo_contacts: Optional[List[ApolloContactTeaserResult]] = Field(default=None, description="For apollo_contacts")
    apollo_contact_revealed: Optional[ApolloContactRevealedResult] = Field(default=None, description="For apollo_contact_revealed")
    apollo_credits: Optional[ApolloCreditStatus] = Field(default=None, description="For apollo_credits")
    
    # Webset fields (for block_type="webset_building")
    webset_id: Optional[str] = Field(default=None, description="Webset ID for polling status")
    webset_name: Optional[str] = Field(default=None, description="Display name for the webset")
    webset_status: Optional[Literal["running", "completed", "failed"]] = Field(default=None, description="Webset build status")
    
    # Metadata
    result_count: int = Field(default=0, description="Number of results")
    is_expanded: bool = Field(default=True, description="UI expansion state")


class PipelineAgentResponse(BaseModel):
    """
    The structured response from the Pipeline agent.
    Contains a message and any search blocks to display.
    """
    message: str = Field(description="Agent's response message to the user")
    search_blocks: List[SearchBlock] = Field(default_factory=list, description="Search result blocks to display")
    suggested_followups: List[str] = Field(default_factory=list, description="Suggested next questions")
    requires_confirmation: bool = Field(default=False, description="If True, agent needs user to confirm before searching")
    confirmation_prompt: Optional[str] = Field(default=None, description="What to ask user for confirmation")


# ============================================================================
# TypedDict State for LangGraph
# ============================================================================

class PipelineAgentState(TypedDict):
    """State passed through the Pipeline agent graph."""
    
    # User input
    user_query: str
    
    # Conversation context
    conversation_history: Annotated[List[dict], add]  # Appends messages
    
    # Agent's plan and execution
    plan: Optional[str]  # What the agent intends to do
    requires_confirmation: bool
    user_confirmed: bool
    
    # Tool execution results (raw)
    tool_results: List[dict]
    
    # Final structured output
    response: Optional[PipelineAgentResponse]
    
    # Error handling
    error: Optional[str]


def create_initial_state(user_query: str) -> PipelineAgentState:
    """Create initial state for a new Pipeline agent invocation."""
    return PipelineAgentState(
        user_query=user_query,
        conversation_history=[],
        plan=None,
        requires_confirmation=False,
        user_confirmed=False,
        tool_results=[],
        response=None,
        error=None,
    )
