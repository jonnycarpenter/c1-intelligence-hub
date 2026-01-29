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
import time
import asyncio
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

# System prompt for Quick Search mode (instant results) - COMPANY SEARCH ONLY
SYSTEM_PROMPT_INSTANT = """You are a Pipeline Agent - an expert sales prospecting assistant that helps users discover potential customers and identify buying signals.

## Your Capabilities

You have access to powerful company search and enrichment tools:

### Exa.ai Search Tools (Semantic/Broad Company Discovery):
1. **find_similar_companies** - Find companies similar to a reference company URL (lookalike targeting)
2. **search_companies** - Search for companies using natural language descriptions (BROAD semantic search)
3. **find_trigger_events** - Find recent news signals like expansions, funding, contracts

### Apollo.io Tools (Company Enrichment & Filtered Search):
4. **search_companies_filtered** - Search with STRUCTURED firmographic filters
   - Use when user specifies: location (state/country), employee count ranges, revenue thresholds, or industries
   - Example: "aerospace companies in Florida with >500 employees"
   - Returns: Full company firmographics (employees, revenue, industry, tech stack, location)
5. **enrich_company** - Get detailed firmographics for a company by domain
   - Returns: employee count, revenue, industry, tech stack, social profiles, location, stock info

### BigQuery Corpus Intelligence Tools:
6. **query_corpus** - Search pre-ingested news corpus for company mentions, triggers, market signals
7. **get_entity_mentions** - Get recent news about a specific company from the corpus
8. **get_competitor_activity** - Get competitor intelligence from pre-ingested sources

**CRITICAL - Corpus Tools are CHAT-ONLY**:
- Corpus tools provide intelligence insights that you share in the CHAT MESSAGE
- DO NOT create SearchBlocks from corpus results - they stay in the conversation
- If no recent intel found, say: "No recent news/intel in the last [timeframe] for [topic]"

## IMPORTANT: Contact Search Coming Soon

**If the user asks for contacts, people, decision makers, purchasing managers, engineers, or any person-level search:**

Respond with: "Contact-level search is coming soon! For now, I can help you find companies matching your criteria - would you like me to search for [relevant companies based on their query]?"

Examples:
- "Find purchasing managers at aerospace companies" → "Contact-level search is coming soon! I can find aerospace companies for you - want me to search for those?"
- "Who is the VP of Operations at Hexcel?" → "Contact-level search is coming soon! I can show you detailed company information for Hexcel if that helps."

## CRITICAL: Tool Selection Guide

### Company Search Tool Selection

| User Intent | Tool | Why |
|-------------|------|-----|
| Broad semantic search (no specific filters) | `search_companies` (Exa) | Neural search understands intent |
| Find lookalikes to a known company | `find_similar_companies` (Exa) | Automated lookalike targeting |
| **Location filter** ("companies in Florida") | `search_companies_filtered` (Apollo) | Structured geo filter |
| **Employee count** ("companies with >500 employees") | `search_companies_filtered` (Apollo) | Structured size filter |
| **Revenue threshold** ("companies with >$100M revenue") | `search_companies_filtered` (Apollo) | Structured revenue filter |
| **Industry + location combo** | `search_companies_filtered` (Apollo) | Multiple structured filters |

**EXAMPLES - search_companies (Exa) for BROAD/SEMANTIC queries:**
- "Find aerospace suppliers" → search_companies (semantic understanding)
- "Who makes carbon fiber parts?" → search_companies (semantic understanding)
- "Find companies like Hexcel" → find_similar_companies (lookalike)
- "Wind turbine blade manufacturers" → search_companies (semantic understanding)

**EXAMPLES - search_companies WITH POST-ENRICHMENT FILTERS (RECOMMENDED for complex queries):**
When the user wants semantic discovery PLUS firmographic filtering, use search_companies with filter parameters:
- "Carbon fiber suppliers with >$50M revenue" → search_companies(query="carbon fiber suppliers", filter_min_revenue=50000000)
- "Aerospace manufacturers in Florida or Texas" → search_companies(query="aerospace manufacturers", filter_states=["Florida", "Texas"])
- "Composites companies with 200-500 employees" → search_companies(query="composites companies", filter_min_employees=200, filter_max_employees=500)
- "Find companies like Hexcel in California" → find_similar_companies(reference="hexcel.com", filter_states=["California"])

**EXAMPLES - search_companies_filtered (Apollo) for PURE STRUCTURED filters (no semantic search):**
Use this when user ONLY cares about firmographic criteria, no semantic context needed:
- "Companies in Florida with 500+ employees" → search_companies_filtered(states=["Florida"], employee_ranges=["501,1000", "1001,5000"])
- "Manufacturing companies with >$100M revenue" → search_companies_filtered(keywords=["manufacturing"], min_revenue=100000000)

## CRITICAL: Handling Sparse Filter Results

When filters are applied, the tool returns `filter_metadata` including:
- `original_count`: Companies found before filtering
- `filtered_count`: Companies that passed all filters
- `filter_impact`: Which filters excluded the most companies
- `expansion_suggestions`: Recommendations for relaxing filters

**If filtered results are sparse (<5 companies), you MUST:**
1. Show the filtered results that DO match
2. Inform the user: "I found X companies matching all criteria, but Y more were found before filtering."
3. Offer specific suggestions to expand results based on `expansion_suggestions`

**DO NOT** silently return sparse results without explanation. Always help the user understand their options.

## CRITICAL: Always Show Results First

**When in doubt whether to ask a clarifying question OR show results → SHOW RESULTS FIRST.**

The user interface has TWO parts:
- **Results Panel (right side)** - Displays SearchBlocks with company cards automatically from your tool calls
- **Chat (left side)** - Your conversational responses

**KEY BEHAVIOR**: When the user asks to find/search/discover companies:
1. **ALWAYS call the appropriate search tool** - Don't just chat about what you could do
2. **Tool output automatically creates SearchBlocks** - The results panel populates from your tool calls
3. **Keep your chat message brief** - Just acknowledge you found results, don't repeat them all in chat
4. **Then offer follow-up questions** - After results are shown, suggest next steps

**WRONG** (what NOT to do):
```
User: "Find me wind energy companies in Florida"
You: "I can help with that! Here's what I found:
- NextEra Energy (6,100 employees)
- Florida Power & Light (9,500 employees)
... [lists 25 companies in chat]"
```

**RIGHT** (what TO do):
```
User: "Find me wind energy companies in Florida"
You: [calls search_companies_filtered or search_companies tool]
Chat: "Found 25 wind energy companies in Florida - you can see them in the results panel. 
The list includes major players like NextEra Energy and FPL, plus specialized firms.
Would you like me to filter by company size or get more details on any of these?"
```

## Guidelines

- **Call tools immediately** for any search/find/discover request - don't just describe
- Use specific, targeted queries for better results
- For lookalikes, get a reference URL (user can provide company name, you derive URL)
- Combine multiple search types when it helps (e.g., find companies + enrich them + check corpus for news)
- For comprehensive prospecting: search_companies → enrich_company → get_entity_mentions
- Suggest follow-up questions to help users refine their search
- Results come with company logos - the UI will display them automatically

## Response Format

After tool execution, provide:
1. **Brief acknowledgment** - "Found X companies" (1-2 sentences)
2. **Quick highlight** - Mention 2-3 notable results if relevant
3. **Suggested next steps** - 2-3 follow-up options (filter, enrich, find similar, get news)

**DO NOT** list all results in chat - they're already visible in the results panel.

## Example Interactions

**COMPANY SEARCH Examples** (Always call tool, brief chat response):

User: "Find me composites manufacturers in the Pacific Northwest"
You: [call search_companies(query="composites manufacturers Pacific Northwest")]
Chat: "Found 18 composites manufacturers in the Pacific Northwest. Notable players include [2-3 names]. Want me to filter by company size or get detailed info on any?"

User: "Who are companies like Hexcel?"
You: [call find_similar_companies(reference="hexcel.com")]
Chat: "Found 25 companies similar to Hexcel - check out the results panel. Includes competitors like Toray and Solvay, plus smaller specialty players."

User: "Find wind energy companies in Florida"
You: [call search_companies_filtered(states=["Florida"], keywords=["wind energy", "renewable energy"])]
Chat: "Found 25 wind energy companies in Florida. Range from major players like NextEra Energy to specialized consultants. Would you like more details on any of these?"

**INSIGHTS Examples (Chat Response Only - NO SearchBlocks)**:

User: "What's in the news about carbon fiber supply chains?"
You: [call query_corpus()] → Respond conversationally with findings (this stays in chat only)

User: "Any recent activity from Hexcel?"
You: [call get_entity_mentions("Hexcel")] → Respond conversationally (or "No recent intel in the last 30 days for Hexcel")
"""

# System prompt for Full List mode (with websets) - COMPANY SEARCH ONLY
SYSTEM_PROMPT_FULL = """You are a Pipeline Agent - an expert sales prospecting assistant that helps users discover potential customers and identify buying signals.

## Your Capabilities

You are in FULL LIST MODE, which means you have access to:

### Exa.ai Instant Search Tools (~350ms response):
1. **find_similar_companies** - Find companies similar to a reference company URL
2. **search_companies** - Search for companies using natural language descriptions (BROAD semantic search)
3. **find_trigger_events** - Find recent news signals

### Exa.ai Full List Building Tool (1-5 minutes, enriched results):
4. **build_company_webset** - Build a comprehensive, deeply enriched company list

### Apollo.io Tools (Company Enrichment & Filtered Search):
5. **search_companies_filtered** - Search with STRUCTURED firmographic filters (FREE - no credits)
   - Use when user specifies: location (state/country), employee count ranges, revenue thresholds, or industries
   - Example: "aerospace companies in Florida with >500 employees"
   - Returns: Full company firmographics (employees, revenue, industry, tech stack, location)
6. **enrich_company** - Get detailed firmographics for a company by domain (FREE - no credits)
   - Returns: employee count, revenue, industry, tech stack, social profiles, location, stock info
7. **get_apollo_credits** - Check credit usage and remaining balance

### BigQuery Corpus Intelligence Tools:
8. **query_corpus** - Search pre-ingested news corpus for company mentions, triggers, market signals
9. **get_entity_mentions** - Get recent news about a specific company from the corpus
10. **get_competitor_activity** - Get competitor intelligence from pre-ingested sources

**CRITICAL - Corpus Tools are CHAT-ONLY**:
- Corpus tools provide intelligence insights that you share in the CHAT MESSAGE
- DO NOT create SearchBlocks from corpus results - they stay in the conversation
- If no recent intel found, say: "No recent news/intel in the last [timeframe] for [topic]"

## IMPORTANT: Contact Search Coming Soon

**If the user asks for contacts, people, decision makers, purchasing managers, engineers, or any person-level search:**

Respond with: "Contact-level search is coming soon! For now, I can help you find companies matching your criteria - would you like me to search for [relevant companies based on their query]?"

## Tool Selection Best Practices

**Company Search Tool Selection**:
| User Intent | Tool | Why |
|-------------|------|-----|
| Broad semantic search (no specific filters) | `search_companies` (Exa) | Neural search understands intent |
| Find lookalikes to a known company | `find_similar_companies` (Exa) | Automated lookalike targeting |
| **Location filter** ("companies in Florida") | `search_companies_filtered` (Apollo) | Structured geo filter |
| **Employee count** ("companies with >500 employees") | `search_companies_filtered` (Apollo) | Structured size filter |
| **Revenue threshold** ("companies with >$100M revenue") | `search_companies_filtered` (Apollo) | Structured revenue filter |

**Apollo Best Practices**:
- Use **search_companies_filtered** when user specifies location, employee count, or revenue filters
- Use **enrich_company** when you have a specific target company to get detailed firmographics

**Corpus Intelligence Best Practices**:
- Use **get_entity_mentions** to check if webset companies have recent news/triggers
- Use **query_corpus** to filter companies by recent activity before building websets
- Use **get_competitor_activity** to qualify targets before full enrichment

## CRITICAL: build_company_webset Usage

The `build_company_webset` tool creates detailed, verified lists:
- Takes 1-5 minutes to complete (async background job)
- Returns deeply enriched results

If a user asks for a "full list" or "comprehensive list", you can build it:

"I'll build you a comprehensive, enriched company list that includes:
- Employee count
- Funding information  
- Location/headquarters
- LinkedIn profiles

This takes 1-5 minutes - results will appear when ready."

## Your Workflow

1. **Understand** - Parse what the user is looking for
2. **Check Mode** - Is this a quick discovery or comprehensive list building?
3. **Confirm if needed** - For full lists, require explicit CONFIRM
4. **Execute** - Call the appropriate tools
5. **Present** - Brief summary + follow-up suggestions (results appear automatically in panel)

## CRITICAL: Always Show Results First

**When in doubt whether to ask a clarifying question OR show results → SHOW RESULTS FIRST.**

The user interface has TWO parts:
- **Results Panel (right side)** - Displays SearchBlocks with company cards automatically from your tool calls
- **Chat (left side)** - Your conversational responses

**KEY BEHAVIOR**: When the user asks to find/search/discover companies:
1. **ALWAYS call the appropriate search tool** - Don't just chat about what you could do
2. **Tool output automatically creates SearchBlocks** - The results panel populates from your tool calls
3. **Keep your chat message brief** - Just acknowledge you found results, don't repeat them all in chat
4. **Then offer follow-up questions** - After results are shown, suggest next steps

## Guidelines

- **Call tools immediately** for any search/find/discover request - don't just describe
- For quick discovery: Use instant tools (find_similar_companies, search_companies, etc.)
- For comprehensive lists: User must say CONFIRM before you call build_company_webset
- Never call build_company_webset without explicit CONFIRM from the user
- When a webset is created, explain that the UI will poll for status automatically
- Results come with company logos - the UI will display them automatically

## Response Format

After tool execution:
1. **Brief acknowledgment** - "Found X companies" (1-2 sentences)
2. **Quick highlight** - Mention 2-3 notable results if relevant
3. For websets: Explain that results will appear when ready (1-5 minutes)
4. **Suggested next steps** - 2-3 follow-up options

**DO NOT** list all results in chat - they're already visible in the results panel.
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
        request_start = time.time()
        history_len = len(conversation_history) if conversation_history else 0
        query_preview = user_query[:100] + ("..." if len(user_query) > 100 else "")
        
        logger.info(
            f"[PIPELINE_AGENT] Query START: mode={self.mode}, "
            f"query='{query_preview}', history_len={history_len}"
        )
        
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
            logger.info(f"[PIPELINE_AGENT] Built message history: {len(messages)} messages")
            
            # Initial LLM call with tools (with timeout protection)
            llm_start = time.time()
            logger.info(f"[PIPELINE_AGENT] LLM call START: message_count={len(messages)}")
            
            try:
                response = await asyncio.wait_for(
                    self.llm_with_tools.ainvoke(messages),
                    timeout=120.0  # 2 minutes
                )
                llm_elapsed = time.time() - llm_start
                logger.info(
                    f"[PIPELINE_AGENT] LLM call COMPLETE: {llm_elapsed:.2f}s, "
                    f"has_tool_calls={bool(response.tool_calls)}, "
                    f"tool_count={len(response.tool_calls) if response.tool_calls else 0}"
                )
            except asyncio.TimeoutError:
                llm_elapsed = time.time() - llm_start
                logger.error(f"[PIPELINE_AGENT] LLM call TIMEOUT: exceeded 120s (elapsed: {llm_elapsed:.2f}s)")
                raise Exception(
                    "Request timed out while waiting for AI response (120s limit). "
                    "This may be due to high API load or network issues. Please try again."
                )
            
            # Collect search blocks from tool calls
            search_blocks: List[SearchBlock] = []
            tool_messages = []
            
            # Execute any tool calls
            if response.tool_calls:
                logger.info(f"[PIPELINE_AGENT] Executing {len(response.tool_calls)} tool calls")
                
                for idx, tool_call in enumerate(response.tool_calls, 1):
                    tool_name = tool_call["name"]
                    tool_args = tool_call["args"]
                    tool_args_preview = json.dumps(tool_args, default=str)[:200]
                    
                    logger.info(
                        f"[PIPELINE_AGENT] Tool {idx}/{len(response.tool_calls)} START: "
                        f"{tool_name}, args={tool_args_preview}"
                    )
                    
                    if tool_name in self.tools:
                        # Execute the tool with timing
                        tool_start = time.time()
                        try:
                            tool_result = await self.tools[tool_name].ainvoke(tool_args)
                            tool_elapsed = time.time() - tool_start
                            logger.info(
                                f"[PIPELINE_AGENT] Tool {idx}/{len(response.tool_calls)} COMPLETE: "
                                f"{tool_name}, {tool_elapsed:.2f}s, result_len={len(str(tool_result))}"
                            )
                        except Exception as tool_error:
                            tool_elapsed = time.time() - tool_start
                            logger.error(
                                f"[PIPELINE_AGENT] Tool {idx}/{len(response.tool_calls)} FAILED: "
                                f"{tool_name}, {tool_elapsed:.2f}s, error={str(tool_error)}",
                                exc_info=True
                            )
                            # Re-raise to let outer handler deal with it
                            raise
                        
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
                            logger.info(
                                f"[PIPELINE_AGENT] SearchBlock created: type={search_block.block_type}, "
                                f"result_count={search_block.result_count}"
                            )
                        else:
                            logger.warning(f"[PIPELINE_AGENT] SearchBlock creation returned None for {tool_name}")
                
                # Get final response with tool results
                messages.append(response)
                for tm in tool_messages:
                    from langchain_core.messages import ToolMessage
                    messages.append(ToolMessage(
                        content=tm["result"],
                        tool_call_id=tm["tool_call_id"],
                    ))
                
                # Get agent's summary response (with timeout)
                summary_start = time.time()
                logger.info(f"[PIPELINE_AGENT] Summary LLM call START")
                
                try:
                    final_response = await asyncio.wait_for(
                        self.llm_with_tools.ainvoke(messages),
                        timeout=120.0
                    )
                    summary_elapsed = time.time() - summary_start
                    logger.info(f"[PIPELINE_AGENT] Summary LLM call COMPLETE: {summary_elapsed:.2f}s")
                except asyncio.TimeoutError:
                    summary_elapsed = time.time() - summary_start
                    logger.error(f"[PIPELINE_AGENT] Summary LLM call TIMEOUT: {summary_elapsed:.2f}s")
                    raise Exception("Request timed out while generating summary response.")
                
                # Handle if agent wants to call more tools (multi-turn loop)
                max_iterations = 3  # Prevent infinite loops
                iteration = 0
                
                while final_response.tool_calls and iteration < max_iterations:
                    iteration += 1
                    logger.info(
                        f"[PIPELINE_AGENT] Multi-turn iteration {iteration}/{max_iterations}: "
                        f"{len(final_response.tool_calls)} additional tool calls"
                    )
                    
                    # Append the AIMessage ONCE before processing its tool calls
                    messages.append(final_response)
                    
                    for idx, tool_call in enumerate(final_response.tool_calls, 1):
                        tool_name = tool_call["name"]
                        tool_args = tool_call["args"]
                        tool_args_preview = json.dumps(tool_args, default=str)[:200]
                        
                        logger.info(
                            f"[PIPELINE_AGENT] Follow-up tool {idx} START: {tool_name}, args={tool_args_preview}"
                        )
                        
                        if tool_name in self.tools:
                            tool_start = time.time()
                            try:
                                tool_result = await self.tools[tool_name].ainvoke(tool_args)
                                tool_elapsed = time.time() - tool_start
                                logger.info(
                                    f"[PIPELINE_AGENT] Follow-up tool {idx} COMPLETE: "
                                    f"{tool_name}, {tool_elapsed:.2f}s"
                                )
                            except Exception as tool_error:
                                tool_elapsed = time.time() - tool_start
                                logger.error(
                                    f"[PIPELINE_AGENT] Follow-up tool {idx} FAILED: "
                                    f"{tool_name}, {tool_elapsed:.2f}s, error={str(tool_error)}",
                                    exc_info=True
                                )
                                raise
                            
                            from langchain_core.messages import ToolMessage
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
                                logger.info(
                                    f"[PIPELINE_AGENT] Follow-up SearchBlock created: "
                                    f"type={search_block.block_type}"
                                )
                    
                    # Get next response (with timeout)
                    followup_start = time.time()
                    try:
                        final_response = await asyncio.wait_for(
                            self.llm_with_tools.ainvoke(messages),
                            timeout=120.0
                        )
                        followup_elapsed = time.time() - followup_start
                        logger.info(
                            f"[PIPELINE_AGENT] Follow-up LLM call COMPLETE: {followup_elapsed:.2f}s"
                        )
                    except asyncio.TimeoutError:
                        followup_elapsed = time.time() - followup_start
                        logger.error(
                            f"[PIPELINE_AGENT] Follow-up LLM call TIMEOUT: {followup_elapsed:.2f}s"
                        )
                        raise Exception("Request timed out during follow-up processing.")
                
                if iteration >= max_iterations and final_response.tool_calls:
                    logger.warning(
                        f"[PIPELINE_AGENT] Multi-turn loop terminated: reached max iterations ({max_iterations})"
                    )
                
                response_text = self._extract_text_content(final_response.content)
            else:
                # No tool calls - just a conversational response
                logger.info(f"[PIPELINE_AGENT] No tool calls, extracting direct response")
                response_text = self._extract_text_content(response.content)
            
            # Generate suggested follow-ups
            suggested_followups = self._generate_followups(user_query, search_blocks)
            
            total_elapsed = time.time() - request_start
            logger.info(
                f"[PIPELINE_AGENT] Query COMPLETE: {total_elapsed:.2f}s, "
                f"{len(search_blocks)} blocks, response_len={len(response_text)}, "
                f"{len(suggested_followups)} followups"
            )
            
            return PipelineAgentResponse(
                message=response_text,
                search_blocks=search_blocks,
                suggested_followups=suggested_followups,
                requires_confirmation=False,
            )
            
        except Exception as e:
            total_elapsed = time.time() - request_start
            logger.error(
                f"[PIPELINE_AGENT] Query FAILED: {total_elapsed:.2f}s, "
                f"error_type={type(e).__name__}, error={str(e)}",
                exc_info=True
            )
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
                error_msg = result_data.get('error', 'Unknown error')
                logger.warning(
                    f"[PIPELINE_AGENT] SearchBlock skipped: {tool_name} returned error status: {error_msg}"
                )
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
            
            elif tool_name == "search_companies_filtered":
                # Apollo filtered search - returns rich firmographic data
                # Map to ProspectResult format for consistent UI rendering
                filters_applied = result_data.get("filters_applied", [])
                filter_desc = ", ".join(filters_applied) if filters_applied else "filtered search"
                
                prospects = []
                for r in results:
                    # Build a URL from domain or linkedin
                    domain = r.get("domain", "")
                    url = r.get("website") or r.get("linkedin_url") or (f"https://{domain}" if domain else "")
                    
                    prospects.append(ProspectResult(
                        title=r.get("company_name", "Unknown Company"),
                        company_name=r.get("company_name"),
                        url=url,
                        domain=domain,
                        logo_url=r.get("logo_url"),
                        description=r.get("description", ""),
                        score=None,  # No relevance score for filtered search
                        apollo_enrichment=r.get("apollo_enrichment"),
                        published_date=None,
                    ))
                
                return SearchBlock(
                    id=block_id,
                    block_type="search_companies",  # Reuse existing UI component
                    title=result_data.get("title", f"Companies ({filter_desc})"),
                    query_context=user_query,
                    prospects=prospects,
                    result_count=len(prospects),
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
                    sic_codes=company_data.get("sic_codes", []),
                    naics_codes=company_data.get("naics_codes", []),
                    retail_location_count=company_data.get("retail_location_count"),
                    suborganizations=[s.get("name") for s in company_data.get("suborganizations", []) if s.get("name")],
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
                
                # Parse company enrichment if available (FREE firmographics)
                company_enrichment = None
                enrichment_data = result_data.get("company_enrichment")
                if enrichment_data:
                    company_enrichment = ApolloEnrichmentResult(
                        name=enrichment_data.get("name", ""),
                        domain=enrichment_data.get("domain", ""),
                        description=enrichment_data.get("description"),
                        logo_url=enrichment_data.get("logo_url"),
                        employee_count=enrichment_data.get("employee_count"),
                        founded_year=enrichment_data.get("founded_year"),
                        industry=enrichment_data.get("industry"),
                        revenue_printed=enrichment_data.get("revenue_printed"),
                        city=enrichment_data.get("city"),
                        state=enrichment_data.get("state"),
                        country=enrichment_data.get("country"),
                        linkedin_url=enrichment_data.get("linkedin_url"),
                        technologies=enrichment_data.get("technologies", []),
                        keywords=enrichment_data.get("keywords", []),
                    )
                
                return SearchBlock(
                    id=block_id,
                    block_type="apollo_contacts",
                    title=f"Contacts at {company}",
                    query_context=user_query,
                    apollo_contacts=contacts,
                    company_enrichment=company_enrichment,  # NEW: Include firmographics
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
            
            elif tool_name == "find_contacts_at_companies":
                # New composite tool - returns companies with their contacts
                if not results:
                    return None
                
                # Parse each company's contacts
                all_contacts = []
                for company_result in results:
                    company_name = company_result.get("company_name", "Unknown")
                    company_domain = company_result.get("domain")
                    
                    for contact_data in company_result.get("contacts", []):
                        location_parts = [contact_data.get("city"), contact_data.get("state")]
                        location = ", ".join([p for p in location_parts if p]) or None
                        
                        contact = ApolloContactTeaserResult(
                            id=contact_data.get("id", ""),
                            first_name=contact_data.get("first_name", ""),
                            last_name=contact_data.get("last_name"),
                            last_name_preview=contact_data.get("last_name"),
                            name=contact_data.get("name"),
                            name_display=contact_data.get("name"),
                            title=contact_data.get("title"),
                            seniority=contact_data.get("seniority"),
                            departments=contact_data.get("departments", []),
                            company_name=company_name,
                            company_domain=company_domain,
                            has_email=bool(contact_data.get("email")),
                            has_phone=bool(contact_data.get("phone")),
                            email=contact_data.get("email"),
                            email_status=contact_data.get("email_status"),
                            phone=contact_data.get("phone"),
                            location=location,
                            city=contact_data.get("city"),
                            state=contact_data.get("state"),
                            country=contact_data.get("country"),
                            linkedin_url=contact_data.get("linkedin_url"),
                            photo_url=contact_data.get("photo_url"),
                            logo_url=company_result.get("logo_url"),
                            last_updated=contact_data.get("last_updated"),
                            is_revealed=contact_data.get("is_revealed", False),
                        )
                        all_contacts.append(contact)
                
                # Build title from filters
                title = result_data.get("title", f"Contacts at {len(results)} companies")
                
                return SearchBlock(
                    id=block_id,
                    block_type="apollo_contacts",  # Reuse existing block type
                    title=title,
                    query_context=user_query,
                    apollo_contacts=all_contacts,
                    result_count=len(all_contacts),
                )
            
            return None
            
        except Exception as e:
            logger.error(
                f"[PIPELINE_AGENT] SearchBlock creation FAILED: tool={tool_name}, "
                f"error_type={type(e).__name__}, error={str(e)}",
                exc_info=True
            )
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
                followups.append("Reveal the top contact's email")
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
# Force rebuild for pipeline fix
