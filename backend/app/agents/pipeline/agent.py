"""
Pipeline Agent - AI-powered prospect discovery orchestration.

This agent handles natural language queries for prospect/lead discovery:
- Understanding user intent
- Planning which searches to run
- Executing Exa.ai + Logo.dev tools
- Formatting results as SearchBlocks for the UI
"""

import json
import uuid
from typing import List, Dict, Any, Optional
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from app.utils.logger import get_logger
from app.config import settings
from app.utils.resilient_llm import create_resilient_llm_with_openai_fallback
from app.mcp.tools.pipeline_search import (
    PIPELINE_TOOLS_INSTANT,
    PIPELINE_TOOLS_FULL,
)
from .state import (
    PipelineAgentState,
    PipelineAgentResponse,
    SearchBlock,
    ProspectResult,
    ContactResult,
    TriggerEventResult,
    WebsetBlock,
    ApolloEnrichmentResult,
    ApolloContactTeaserResult,
    ApolloContactRevealedResult,
    ApolloCreditStatus,
)

logger = get_logger(__name__)

# ============================================================================
# System Prompt
# ============================================================================

# System prompt for Quick Search mode (instant results)
SYSTEM_PROMPT_INSTANT = """You are a Pipeline Agent - an expert sales prospecting assistant that helps users discover potential customers, find decision makers, and identify buying signals.

## Your Capabilities

You have access to powerful search and enrichment tools:

### Exa.ai Search Tools (Company Discovery):
1. **find_similar_companies** - Find companies similar to a reference company URL (lookalike targeting)
2. **search_companies** - Search for companies using natural language descriptions
3. **find_trigger_events** - Find recent news signals like expansions, funding, contracts

### Apollo.io Tools (Contacts & Enrichment):
4. **find_company_contacts** - Find decision makers at a specific company (FREE - no credits)
   - Returns: Contact teasers with name, title, seniority, has_email flag
   - Use department filter: "purchasing", "engineering", or "executive"
   - These contacts have IDs that allow email/phone reveal
5. **enrich_company** - Get detailed firmographics for a company by domain (FREE - no credits)
   - Returns: employee count, revenue, industry, tech stack, social profiles, location, stock info
6. **reveal_contact** - Get full contact email/phone (COSTS 1 CREDIT - use wisely!)
   - Requires person_id from find_company_contacts results
   - Returns verified email, phone, employment history
7. **get_apollo_credits** - Check credit usage and remaining balance

### BigQuery Corpus Intelligence Tools:
8. **query_corpus** - Search pre-ingested news corpus for company mentions, triggers, market signals
9. **get_entity_mentions** - Get recent news about a specific company from the corpus
10. **get_competitor_activity** - Get competitor intelligence from pre-ingested sources

**CRITICAL - Corpus Tools are CHAT-ONLY**:
- Corpus tools provide intelligence insights that you share in the CHAT MESSAGE
- DO NOT create SearchBlocks from corpus results - they stay in the conversation
- If no recent intel found, say: "No recent news/intel in the last [timeframe] for [topic]"

## IMPORTANT: Company Search vs Contact Search

**CLARIFY if the user's intent is ambiguous.** Ask:
"Would you like me to find **companies** matching that criteria, or **contacts/people** at those companies?"

**COMPANY SEARCHES** - Use Exa.ai tools:
- "Find aerospace suppliers" → search_companies
- "Find companies like Hexcel" → find_similar_companies
- "Who makes carbon fiber parts?" → search_companies

**CONTACT SEARCHES** - Use Apollo tools:
- "Find contacts at Hexcel in purchasing" → find_company_contacts(company_name="Hexcel", department="purchasing")
- "Who is the purchasing manager at Boeing?" → find_company_contacts(company_name="Boeing", department="purchasing")
- "Get me decision makers at this company" → find_company_contacts

**COMBINED WORKFLOW** (most common):
1. User asks broad question → Clarify: companies or contacts?
2. If companies: search_companies → show results
3. If contacts at a known company: find_company_contacts → show contacts with "Reveal" button
4. User can then reveal specific contacts for email (costs 1 credit)

## Tool Selection Best Practices

**When to Create SearchBlocks (Results Panel) vs Chat Insights**:

**CREATE SEARCHBLOCKS** when user wants to:
- Find/discover NEW companies → Use Exa.ai (find_similar_companies, search_companies)
- Find contacts at a SPECIFIC company → Use Apollo (find_company_contacts)
- Find trigger events → Use Exa.ai (find_trigger_events)

**PROVIDE CHAT INSIGHTS ONLY** when user wants:
- Intelligence about known companies/topics
- "What's in the news about X?"
- "Any recent activity from competitors?"
- Use: Corpus tools (query_corpus, get_entity_mentions, get_competitor_activity)

**Apollo Best Practices**:
- Use **find_company_contacts** for ANY contact search - it provides revealable contacts
- Use **enrich_company** when you have a specific target company to get detailed firmographics
- Only use **reveal_contact** when user explicitly wants verified email - it costs credits!
- Always check **get_apollo_credits** before revealing multiple contacts

## Your Workflow

1. **Understand** - Parse what the user is looking for
2. **Clarify if needed** - Ask "companies or contacts?" if ambiguous
3. **Plan** - Decide which tool(s) to use and with what parameters
4. **Execute** - Call the tools to gather results
5. **Present** - Summarize findings and suggest next steps

## Guidelines

- Always explain what you're searching for before executing
- Use specific, targeted queries for better results
- For lookalikes, get a reference URL (user can provide company name, you derive URL)
- Combine multiple search types when it helps (e.g., find companies + enrich them + check corpus for news)
- For comprehensive prospecting: search_companies → enrich_company → get_entity_mentions
- Suggest follow-up questions to help users refine their search
- Results come with company logos - the UI will display them automatically
- When enriching companies, the Apollo data complements Exa.ai search results

## Response Format

After tool execution, provide:
1. A concise summary of what you found
2. The search results (SearchBlocks - handled automatically)
3. 2-3 suggested follow-up questions

## Example Interactions

**COMPANY SEARCH Examples**:

User: "Find me composites manufacturers in the Pacific Northwest"
You: Search for companies matching that description → SearchBlocks displayed

User: "Who are companies like Hexcel?"
You: Run lookalike search against hexcel.com → SearchBlocks displayed

**CONTACT SEARCH Examples**:

User: "Find contacts at Hexcel in purchasing"
You: Use find_company_contacts(company_name="Hexcel", department="purchasing") → Contact cards displayed with "Reveal" button

User: "Who is in charge of procurement at Boeing?"
You: Use find_company_contacts(company_name="Boeing", department="purchasing") → Contact cards displayed

User: "Get me the email for John Smith" (after seeing contact cards)
You: Use reveal_contact(person_id="...", contact_name="John Smith") → Revealed contact with email

**COMBINED Examples**:

User: "Find purchasing managers at aerospace suppliers"
You: Ask clarification - "I can help with that! Would you like me to:
1. **Search for aerospace supplier companies** first, then you can pick one to find contacts at
2. **Find purchasing contacts at a specific company** you already have in mind?

Which approach works better for you?"

**INSIGHTS Examples (Chat Response Only)**:

User: "What's in the news about carbon fiber supply chains?"
You: Use query_corpus() → Respond: "Here's what I found in recent intel: [summary of 3-5 articles]"

User: "Any recent activity from Hexcel?"
You: Use get_entity_mentions("Hexcel") → Respond conversationally with findings (or "No recent intel in the last 30 days for Hexcel")
"""

# System prompt for Full List mode (with websets)
SYSTEM_PROMPT_FULL = """You are a Pipeline Agent - an expert sales prospecting assistant that helps users discover potential customers, find decision makers, and identify buying signals.

## Your Capabilities

You are in FULL LIST MODE, which means you have access to:

### Exa.ai Instant Search Tools (~350ms response):
1. **find_similar_companies** - Find companies similar to a reference company URL
2. **search_companies** - Search for companies using natural language descriptions
3. **find_trigger_events** - Find recent news signals

### Exa.ai Full List Building Tool (1-5 minutes, enriched results):
4. **build_company_webset** - Build a comprehensive, deeply enriched company list

### Apollo.io Tools (Contacts & Enrichment):
5. **find_company_contacts** - Find decision makers at a specific company (FREE - no credits)
   - Returns: Contact teasers with name, title, seniority, has_email flag
   - Use department filter: "purchasing", "engineering", or "executive"
   - These contacts have IDs that allow email/phone reveal
6. **enrich_company** - Get detailed firmographics for a company by domain (FREE - no credits)
   - Returns: employee count, revenue, industry, tech stack, social profiles, location, stock info
7. **reveal_contact** - Get full contact email/phone (COSTS 1 CREDIT - use wisely!)
   - Requires person_id from find_company_contacts results
   - Returns verified email, phone, employment history
8. **get_apollo_credits** - Check credit usage and remaining balance

### BigQuery Corpus Intelligence Tools:
9. **query_corpus** - Search pre-ingested news corpus for company mentions, triggers, market signals
10. **get_entity_mentions** - Get recent news about a specific company from the corpus
11. **get_competitor_activity** - Get competitor intelligence from pre-ingested sources

**CRITICAL - Corpus Tools are CHAT-ONLY**:
- Corpus tools provide intelligence insights that you share in the CHAT MESSAGE
- DO NOT create SearchBlocks from corpus results - they stay in the conversation
- If no recent intel found, say: "No recent news/intel in the last [timeframe] for [topic]"

## Tool Selection Best Practices

**Apollo Best Practices**:
- Use **find_company_contacts** for ANY contact search - it provides revealable contacts
- Use **enrich_company** when you have a specific target company to get detailed firmographics
- Only use **reveal_contact** when user explicitly wants verified email - it costs credits!
- Always check **get_apollo_credits** before revealing multiple contacts

**Corpus Intelligence Best Practices**:
- Use **get_entity_mentions** to check if webset companies have recent news/triggers
- Use **query_corpus** to filter companies by recent activity before building expensive websets
- Use **get_competitor_activity** to qualify targets before full enrichment

## CRITICAL: build_company_webset Confirmation Flow

The `build_company_webset` tool creates detailed, verified lists but:
- Takes 1-5 minutes to complete
- Costs money (API credits)
- Should only be used when the user truly needs a comprehensive list

**YOU MUST NOT CALL build_company_webset UNLESS the user types "CONFIRM" in their message.**

If a user asks for a "full list" or "comprehensive list" but hasn't typed CONFIRM, respond with:

"I can build you a comprehensive, enriched company list that includes:
- Employee count
- Funding information  
- Location/headquarters
- LinkedIn profiles

However, this takes 1-5 minutes and uses more credits than instant search. If you're sure you need the full enriched list, please type **CONFIRM** in your next message and repeat your request.

If you just want quick results, I can do an instant search instead - just let me know!"

## Your Workflow

1. **Understand** - Parse what the user is looking for
2. **Check Mode** - Is this a quick discovery or comprehensive list building?
3. **Confirm if needed** - For full lists, require explicit CONFIRM
4. **Execute** - Call the appropriate tools
5. **Present** - Summarize findings and explain next steps (especially for websets that are building)

## Guidelines

- For quick discovery: Use instant tools (find_similar_companies, search_companies, etc.)
- For comprehensive lists: User must say CONFIRM before you call build_company_webset
- Never call build_company_webset without explicit CONFIRM from the user
- When a webset is created, explain that the UI will poll for status automatically
- Results come with company logos - the UI will display them automatically

## Response Format

After tool execution:
1. A concise summary of what you found/started
2. For websets: Explain that results will appear when ready (1-5 minutes)
3. 2-3 suggested follow-up questions
"""

# Backwards compatibility - default to instant mode
SYSTEM_PROMPT = SYSTEM_PROMPT_INSTANT


# ============================================================================
# Agent Implementation
# ============================================================================

class PipelineAgent:
    """
    Pipeline Agent for prospect discovery.
    
    Uses Claude to understand user queries and orchestrate Exa.ai searches,
    returning structured SearchBlock results for the frontend.
    
    Supports two modes:
    - "instant" (default): Quick searches with immediate results
    - "full": Includes webset building for comprehensive, enriched lists
    """
    
    def __init__(self, mode: str = "instant"):
        """
        Initialize the Pipeline Agent.
        
        Args:
            mode: "instant" for quick search, "full" for comprehensive lists
        """
        self.mode = mode
        self.llm = create_resilient_llm_with_openai_fallback(
            primary_model="claude-sonnet-4-5",
            anthropic_api_key=settings.anthropic_api_key,
            openai_api_key=settings.openai_api_key,
            temperature=0,
            max_tokens=4096,
        )
        
        # Select tools and prompt based on mode
        if mode == "full":
            self.tools_list = PIPELINE_TOOLS_FULL
            self.system_prompt = SYSTEM_PROMPT_FULL
        else:
            self.tools_list = PIPELINE_TOOLS_INSTANT
            self.system_prompt = SYSTEM_PROMPT_INSTANT
        
        self.llm_with_tools = self.llm.bind_tools(self.tools_list)
        self.tools = {tool.name: tool for tool in self.tools_list}
        
    async def process_query(
        self,
        user_query: str,
        conversation_history: Optional[List[dict]] = None,
    ) -> PipelineAgentResponse:
        """
        Process a user query and return structured response with search results.
        
        Args:
            user_query: The user's natural language query
            conversation_history: Previous messages for context
            
        Returns:
            PipelineAgentResponse with message, search_blocks, and suggested_followups
        """
        logger.info(f"[Pipeline Agent] Processing query (mode={self.mode}): {user_query}")
        
        try:
            # Build message history
            messages = [SystemMessage(content=self.system_prompt)]
            
            if conversation_history:
                for msg in conversation_history:
                    if msg.get("role") == "user":
                        messages.append(HumanMessage(content=msg["content"]))
                    elif msg.get("role") == "assistant":
                        messages.append(AIMessage(content=msg["content"]))
            
            messages.append(HumanMessage(content=user_query))
            
            # Initial LLM call with tools
            response = await self.llm_with_tools.ainvoke(messages)
            
            # Collect search blocks from tool calls
            search_blocks: List[SearchBlock] = []
            tool_messages = []
            
            # Execute any tool calls
            if response.tool_calls:
                logger.info(f"[Pipeline Agent] Executing {len(response.tool_calls)} tool calls")
                
                for tool_call in response.tool_calls:
                    tool_name = tool_call["name"]
                    tool_args = tool_call["args"]
                    
                    logger.info(f"[Pipeline Agent] Calling {tool_name} with args: {tool_args}")
                    
                    if tool_name in self.tools:
                        # Execute the tool
                        tool_result = await self.tools[tool_name].ainvoke(tool_args)
                        tool_messages.append({
                            "tool_call_id": tool_call["id"],
                            "result": tool_result,
                        })
                        
                        # Parse result and create SearchBlock
                        search_block = self._create_search_block(
                            tool_name, tool_args, tool_result, user_query
                        )
                        if search_block:
                            search_blocks.append(search_block)
                
                # Get final response with tool results
                messages.append(response)
                for tm in tool_messages:
                    from langchain_core.messages import ToolMessage
                    messages.append(ToolMessage(
                        content=tm["result"],
                        tool_call_id=tm["tool_call_id"],
                    ))
                
                # Get agent's summary response
                final_response = await self.llm_with_tools.ainvoke(messages)
                
                # Handle if agent wants to call more tools (multi-turn loop)
                max_iterations = 3  # Prevent infinite loops
                iteration = 0
                
                while final_response.tool_calls and iteration < max_iterations:
                    iteration += 1
                    logger.info(f"[Pipeline Agent] Follow-up tool calls iteration {iteration}")
                    
                    for tool_call in final_response.tool_calls:
                        tool_name = tool_call["name"]
                        tool_args = tool_call["args"]
                        
                        logger.info(f"[Pipeline Agent] Calling {tool_name} with args: {tool_args}")
                        
                        if tool_name in self.tools:
                            tool_result = await self.tools[tool_name].ainvoke(tool_args)
                            
                            from langchain_core.messages import ToolMessage
                            messages.append(final_response)
                            messages.append(ToolMessage(
                                content=tool_result,
                                tool_call_id=tool_call["id"],
                            ))
                            
                            # Parse result and create SearchBlock
                            search_block = self._create_search_block(
                                tool_name, tool_args, tool_result, user_query
                            )
                            if search_block:
                                search_blocks.append(search_block)
                    
                    # Get next response
                    final_response = await self.llm_with_tools.ainvoke(messages)
                
                response_text = self._extract_text_content(final_response.content)
            else:
                # No tool calls - just a conversational response
                response_text = self._extract_text_content(response.content)
            
            # Generate suggested follow-ups
            suggested_followups = self._generate_followups(user_query, search_blocks)
            
            return PipelineAgentResponse(
                message=response_text,
                search_blocks=search_blocks,
                suggested_followups=suggested_followups,
                requires_confirmation=False,
            )
            
        except Exception as e:
            logger.error(f"[Pipeline Agent] Error: {e}", exc_info=True)
            return PipelineAgentResponse(
                message=f"I encountered an error while processing your request: {str(e)}. Please try rephrasing your query.",
                search_blocks=[],
                suggested_followups=[
                    "Find companies similar to [company URL]",
                    "Search for [industry] companies",
                    "Find [role] contacts in [industry]",
                ],
            )
    
    def _create_search_block(
        self,
        tool_name: str,
        tool_args: dict,
        tool_result: str,
        user_query: str,
    ) -> Optional[SearchBlock]:
        """Create a SearchBlock from tool execution results."""
        try:
            result_data = json.loads(tool_result)
            
            if result_data.get("status") != "success":
                logger.warning(f"Tool {tool_name} returned error: {result_data.get('error')}")
                return None
            
            results = result_data.get("results", [])
            if not results:
                return None
            
            block_id = str(uuid.uuid4())
            
            # Determine block type and create appropriate result objects
            if tool_name == "find_similar_companies":
                return SearchBlock(
                    id=block_id,
                    block_type="similar_companies",
                    title=f"Companies similar to {tool_args.get('reference_url', 'reference')}",
                    query_context=user_query,
                    prospects=[ProspectResult(**r) for r in results],
                    result_count=len(results),
                )
            
            elif tool_name == "search_companies":
                return SearchBlock(
                    id=block_id,
                    block_type="search_companies",
                    title=f"Companies matching: {tool_args.get('query', '')}",
                    query_context=user_query,
                    prospects=[ProspectResult(**r) for r in results],
                    result_count=len(results),
                )
            
            elif tool_name == "find_contacts":
                role = tool_args.get("role", "contacts")
                industry = tool_args.get("industry", "")
                company = tool_args.get("company", "")
                
                title_parts = [role]
                if company:
                    title_parts.append(f"at {company}")
                elif industry:
                    title_parts.append(f"in {industry}")
                
                return SearchBlock(
                    id=block_id,
                    block_type="contacts",
                    title=" ".join(title_parts),
                    query_context=user_query,
                    contacts=[ContactResult(**r) for r in results],
                    result_count=len(results),
                )
            
            elif tool_name == "find_trigger_events":
                return SearchBlock(
                    id=block_id,
                    block_type="trigger_events",
                    title=f"Trigger Events: {tool_args.get('topic', '')}",
                    query_context=user_query,
                    trigger_events=[TriggerEventResult(**r) for r in results],
                    result_count=len(results),
                )
            
            elif tool_name == "build_company_webset":
                # Webset is async - return a WebsetBlock with the webset_id
                return SearchBlock(
                    id=block_id,
                    block_type="webset_building",
                    title=f"Building: {result_data.get('name', 'Company List')}",
                    query_context=user_query,
                    webset_id=result_data.get("webset_id"),
                    webset_name=result_data.get("name"),
                    webset_status="running",
                    result_count=0,  # Will be updated when complete
                )
            
            # ==========================================
            # Apollo.io Tools
            # ==========================================
            
            elif tool_name == "enrich_company":
                company_data = result_data.get("company", {})
                if not company_data:
                    return None
                
                # Build headquarters string from location parts
                location_parts = [
                    company_data.get("city"),
                    company_data.get("state"),
                    company_data.get("country"),
                ]
                headquarters = ", ".join([p for p in location_parts if p])
                
                enrichment = ApolloEnrichmentResult(
                    name=company_data.get("name", "Unknown"),
                    domain=company_data.get("domain", tool_args.get("domain", "")),
                    description=company_data.get("description"),
                    logo_url=company_data.get("logo_url"),
                    employee_count=company_data.get("employee_count"),
                    founded_year=company_data.get("founded_year"),
                    industry=company_data.get("industry"),
                    annual_revenue=company_data.get("annual_revenue"),
                    revenue_printed=company_data.get("revenue_printed"),
                    headquarters=headquarters or None,
                    phone=company_data.get("phone"),
                    linkedin_url=company_data.get("linkedin_url"),
                    technologies=company_data.get("technologies", []),
                    keywords=company_data.get("keywords", []),
                    ticker=company_data.get("ticker"),
                )
                
                return SearchBlock(
                    id=block_id,
                    block_type="apollo_enrichment",
                    title=f"Company Profile: {enrichment.name}",
                    query_context=user_query,
                    apollo_enrichment=enrichment,
                    result_count=1,
                )
            
            elif tool_name == "find_company_contacts":
                if not results:
                    return None
                
                contacts = []
                for r in results:
                    # Build location from city/state
                    location_parts = [r.get("city"), r.get("state")]
                    location = ", ".join([p for p in location_parts if p]) or None
                    
                    contacts.append(ApolloContactTeaserResult(
                        id=r.get("id", ""),
                        first_name=r.get("first_name", r.get("name", "Unknown")),
                        last_name_preview=None,  # Not in teaser format
                        name_display=r.get("name"),
                        title=r.get("title"),
                        seniority=r.get("seniority"),
                        department=None,  # Could add from response if available
                        company_name=r.get("company"),
                        company_domain=r.get("company_domain"),
                        logo_url=None,  # Will be fetched by CompanyLogo component
                        has_email=r.get("has_email", False),
                        has_phone=r.get("has_phone", False),
                        linkedin_url=r.get("linkedin_url"),
                        location=location,
                    ))
                
                company = tool_args.get("company_name") or tool_args.get("company_domain") or "company"
                
                return SearchBlock(
                    id=block_id,
                    block_type="apollo_contacts",
                    title=f"Contacts at {company}",
                    query_context=user_query,
                    apollo_contacts=contacts,
                    result_count=len(contacts),
                )
            
            elif tool_name == "reveal_contact":
                contact_data = result_data.get("contact", {})
                if not contact_data:
                    return None
                
                company_info = contact_data.get("company", {})
                location_parts = [
                    contact_data.get("city"),
                    contact_data.get("state"),
                    contact_data.get("country"),
                ]
                location = ", ".join([p for p in location_parts if p]) or None
                
                revealed = ApolloContactRevealedResult(
                    id=contact_data.get("id", ""),
                    name=contact_data.get("name", "Unknown"),
                    first_name=contact_data.get("first_name", ""),
                    last_name=contact_data.get("last_name", ""),
                    title=contact_data.get("title"),
                    seniority=contact_data.get("seniority"),
                    photo_url=contact_data.get("photo_url"),
                    email=contact_data.get("email"),
                    email_status=contact_data.get("email_status"),
                    phone=contact_data.get("phone"),
                    linkedin_url=contact_data.get("linkedin_url"),
                    company_name=company_info.get("name"),
                    company_domain=company_info.get("domain"),
                    logo_url=None,  # Will be fetched by CompanyLogo
                    location=location,
                )
                
                return SearchBlock(
                    id=block_id,
                    block_type="apollo_contact_revealed",
                    title=f"Contact: {revealed.name}",
                    query_context=user_query,
                    apollo_contact_revealed=revealed,
                    result_count=1,
                )
            
            elif tool_name == "get_apollo_credits":
                credits_data = result_data.get("credits", {})
                if not credits_data:
                    return None
                
                credit_status = ApolloCreditStatus(
                    used=credits_data.get("used", 0),
                    remaining=credits_data.get("remaining", 0),
                    limit=credits_data.get("limit", 2500),
                    reset_date=credits_data.get("reset_date", ""),
                    utilization=credits_data.get("utilization", "0%"),
                    can_reveal=result_data.get("can_reveal", True),
                )
                
                return SearchBlock(
                    id=block_id,
                    block_type="apollo_credits",
                    title="Apollo Credit Status",
                    query_context=user_query,
                    apollo_credits=credit_status,
                    result_count=1,
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Error creating SearchBlock: {e}")
            return None
    
    def _extract_text_content(self, content) -> str:
        """
        Extract text content from LLM response.
        
        Claude/LangChain response.content can be:
        - A string (text-only response)
        - A list of blocks (when including tool_use blocks)
        
        This method handles both cases.
        """
        if isinstance(content, str):
            return content
        
        if isinstance(content, list):
            # Extract text from content blocks, ignoring tool_use blocks
            text_parts = []
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
                elif isinstance(block, str):
                    text_parts.append(block)
            
            if text_parts:
                return " ".join(text_parts)
            
            # Fallback: if no text found, return a helpful message
            return "I've processed your request. Please see the results above."
        
        # Fallback for unexpected types
        return str(content) if content else "Search completed."
    
    def _generate_followups(
        self,
        user_query: str,
        search_blocks: List[SearchBlock],
    ) -> List[str]:
        """Generate contextual follow-up suggestions."""
        followups = []
        
        for block in search_blocks:
            if block.block_type == "similar_companies":
                followups.append("Find decision makers at these companies")
                followups.append("Search for trigger events at these companies")
            elif block.block_type == "search_companies":
                followups.append("Find contacts at the top results")
                followups.append("Run a lookalike search on the most relevant company")
                followups.append("Enrich the top company with Apollo data")
            elif block.block_type == "contacts":
                followups.append("Find similar companies to reach more contacts")
                followups.append("Search for recent news about these companies")
            elif block.block_type == "trigger_events":
                followups.append("Find contacts at companies with recent activity")
                followups.append("Search for similar companies in this space")
            elif block.block_type == "apollo_enrichment":
                followups.append("Find purchasing contacts at this company")
                followups.append("Search for similar companies")
                followups.append("Find recent news about this company")
            elif block.block_type == "apollo_contacts":
                followups.append("Reveal the top contact's email (costs 1 credit)")
                followups.append("Enrich this company with firmographics")
                followups.append("Find similar companies to reach more contacts")
            elif block.block_type == "apollo_contact_revealed":
                followups.append("Find more contacts at this company")
                followups.append("Search for similar companies")
            elif block.block_type == "apollo_credits":
                followups.append("Find contacts at a company")
        
        # Default suggestions if no specific ones
        if not followups:
            followups = [
                "Find companies similar to [company URL]",
                "Search for [industry] manufacturers",
                "Find [role] contacts",
            ]
        
        # Limit to 3 unique suggestions
        return list(dict.fromkeys(followups))[:3]


# Agent instances for each mode
_agent_instant = None
_agent_full = None


def get_pipeline_agent(mode: str = "instant") -> PipelineAgent:
    """
    Get a Pipeline Agent instance for the specified mode.
    
    Args:
        mode: "instant" for quick search, "full" for comprehensive lists with websets
    
    Returns:
        PipelineAgent configured for the specified mode
    """
    global _agent_instant, _agent_full
    
    if mode == "full":
        if _agent_full is None:
            _agent_full = PipelineAgent(mode="full")
        return _agent_full
    else:
        if _agent_instant is None:
            _agent_instant = PipelineAgent(mode="instant")
        return _agent_instant


# Backwards compatibility - default instance
pipeline_agent = get_pipeline_agent("instant")
