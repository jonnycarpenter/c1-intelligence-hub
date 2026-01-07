from typing import Dict, Any, List, Optional
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from app.agents.research.state import DeepResearchState, ResearchBrief, QueryStatus
from app.agents.research.memory import get_research_memory
from app.agents.research.progress import emit_progress_sync, ToolProgress
from app.config.settings import settings
from app.utils.resilient_llm import create_resilient_llm_with_openai_fallback
import json
import logging
import asyncio

logger = logging.getLogger(__name__)

# Timeout for prior research lookup (seconds)
PRIOR_RESEARCH_TIMEOUT = 10


async def _get_prior_research_context(query: str) -> str:
    """
    Fetch related prior research to inject into groomer prompt.
    
    This enables the groomer to:
    - Reference prior findings in the research brief
    - Avoid asking clarifying questions that were already answered
    - Generate more targeted queries based on past coverage
    
    Returns:
        Formatted context string, empty if no related research found
        
    Note: Has a timeout to prevent BigQuery delays from blocking workflow
    """
    try:
        # Wrap in timeout to prevent BigQuery delays from blocking the workflow
        async def _fetch():
            memory = await get_research_memory()
            
            # Find related research (entities not yet known, so just use query text)
            related = await memory.find_related_research(
                query=query,
                companies=None,  # Will be extracted after grooming
                industries=None,
            )
            
            if related:
                logger.info(f"Found {len(related)} related prior reports for context injection")
                return memory.format_context_for_prompt(related)
            
            return ""
        
        return await asyncio.wait_for(_fetch(), timeout=PRIOR_RESEARCH_TIMEOUT)
        
    except asyncio.TimeoutError:
        logger.warning(f"Prior research lookup timed out after {PRIOR_RESEARCH_TIMEOUT}s, proceeding without context")
        return ""
    except Exception as e:
        logger.warning(f"Failed to fetch prior research context: {e}")
        return ""

# System prompt is derived from query_input_agent.md
GROOMER_SYSTEM_PROMPT = """
You are a Query Grooming Agent for a composites industry intelligence platform called the C1 Intelligence Hub. Your job is to take a user's research question and prepare it for downstream research agents.

## Your Responsibilities

1. INTERPRET the user's intent — what are they actually trying to learn?
2. DECIDE if clarification is needed — only ask if the answer would significantly change the research approach
3. AUGMENT the query — generate optimized searches for the Financial Agent and Industry Agent
4. ENRICH with context — provide domain knowledge that helps research agents succeed
5. LEVERAGE prior research — if related research is provided, reference it in domain_context

## Using Prior Research Context

If a "Prior Research Context" section is provided below, use it to:
- Skip clarifying questions that prior research already answered
- Note in domain_context what was previously researched and when
- Generate queries that build on prior findings rather than duplicate them
- Identify gaps in prior coverage that new research should fill

## Clarification Rules

- Ask a clarifying question ONLY if:
  - Timeframe ambiguity would dramatically change results (e.g., "recent" could mean 1 week or 1 year)
  - Multiple valid interpretations exist (e.g., "carbon fiber" could mean material, companies, or applications)
  - Scope is unclear (e.g., "what's happening in aerospace" — which aspect?)
  
- Do NOT ask clarifying questions for:
  - Queries that are reasonably clear
  - Minor ambiguities you can resolve with sensible defaults
  - Anything where asking would feel pedantic

- Maximum 2 clarifying questions total, but prefer 0-1
- Always provide a default assumption if the user skips the question

## Query Augmentation Strategy

### For the Financial Agent (searches SEC filings, earnings calls, 10-K/10-Q)
Generate 3-5 queries optimized for financial document search:
- Include relevant public company names and tickers
- Use financial terminology (revenue, margins, guidance, outlook, headwinds)
- Reference specific filing types when relevant
- Think about what executives would say in earnings calls

### For the Industry Agent (searches web, press releases, RSS feeds, trade publications)
Generate 3-5 queries optimized for industry news and trade coverage:
- Use technical/trade terminology
- Include trade publication names for better results
- Think about how journalists and analysts write about these topics
- Consider geographic and end-market angles

## Composites Industry Domain Knowledge

### Key Public Companies (for Financial Agent queries)
- Hexcel Corporation (HXL)
- Toray Industries
- SGL Carbon
- Teijin Limited
- Mitsubishi Chemical
- Owens Corning (OC)
- Jushi Group
- BASF, Huntsman, Hexion
- Spirit AeroSystems, Albany International

### Key Materials & Terminology
- Carbon fiber, CFRP
- Fiberglass, glass fiber, GFRP
- Aramid, Kevlar
- Prepreg
- Resin systems (epoxy, polyester, vinyl ester, phenolic)
- Thermoset vs thermoplastic
- Autoclave vs out-of-autoclave
- PAN precursor

### Key End Markets
- Aerospace & defense
- Automotive (lightweighting, EVs)
- Wind energy (turbine blades)
- Marine
- Sporting goods
- Construction & infrastructure
- Pressure vessels (hydrogen storage)

## Output Format
ALWAYS respond with valid JSON matching this EXACT schema:

```json
{
  "status": "ready",  // REQUIRED: either "ready" or "needs_clarification"
  "clarifying_question": null,  // Only if status is "needs_clarification"
  "original_query": "the user's original query",
  "clarified_intent": "what the user is actually trying to learn",
  "timeframe": "e.g., 'past 6 months' or '2025-2026'",
  "financial_agent_queries": ["query 1", "query 2", "query 3"],
  "industry_agent_queries": ["query 1", "query 2", "query 3"],
  "entities_to_track": ["Company A", "Product B", "Material C"],
  "domain_context": "A single string with relevant domain knowledge for the research agents",
  "priority_sources": {"financial": ["10-K", "earnings calls"], "industry": ["CompositesWorld"]},
  "exclusions": ["topics to exclude"]
}
```

CRITICAL REQUIREMENTS:
1. "status" field is REQUIRED - must be "ready" or "needs_clarification"
2. "domain_context" must be a STRING, not an object
3. If query is reasonably clear, set status to "ready" and provide the queries
"""

async def query_grooming_node(state: DeepResearchState) -> DeepResearchState:
    """
    Main grooming logic. Calls Claude to interpret the query and generate a brief.
    
    Includes context injection from prior research to help the groomer:
    - Reference related past findings
    - Avoid redundant clarifying questions
    - Generate more targeted search queries
    """
    import time
    start_time = time.time()
    logger.info(f"[GROOMER] START - query: {state.get('user_query', '')[:50]}...")
    logger.info(f"[GROOMER] State keys: {list(state.keys())}")
    
    llm = create_resilient_llm_with_openai_fallback(
        primary_model=settings.deep_research_groomer_model,
        anthropic_api_key=settings.anthropic_api_key,
        openai_api_key=settings.openai_api_key,
        temperature=0,
    )
    
    # Ensure user query is not empty
    user_query = state.get("user_query", "").strip()
    if not user_query:
        logger.error("Empty user_query in state")
        return {
            **state,
            "current_status": "grooming_failed",
            "errors": state.get("errors", []) + [{"node": "groomer", "error": "Empty user query"}],
        }
    
    # =========================================================================
    # Context Injection: Fetch related prior research
    # This enriches the groomer's understanding of what we've already researched
    # =========================================================================
    emit_progress_sync(ToolProgress(
        tool_name="prior_research",
        message="Checking for related prior research...",
        status="running"
    ))
    prior_context = await _get_prior_research_context(user_query)
    
    # Build system prompt with optional prior context
    system_content = GROOMER_SYSTEM_PROMPT
    if prior_context:
        system_content = f"{GROOMER_SYSTEM_PROMPT}\n\n{prior_context}"
        logger.info("Injected prior research context into groomer prompt")
        emit_progress_sync(ToolProgress(
            tool_name="prior_research",
            message="Found related prior research",
            status="complete"
        ))
    else:
        emit_progress_sync(ToolProgress(
            tool_name="prior_research",
            message="No related prior research found",
            status="complete"
        ))
    
    # Build messages from state
    messages = [SystemMessage(content=system_content)]
    
    # Filter conversation history to only include messages with non-empty content
    # This prevents Anthropic API errors about empty message content
    history = state.get("conversation_history") or []
    for msg in history:
        if msg and hasattr(msg, 'content') and msg.content:
            messages.append(msg)
    
    messages.append(HumanMessage(content=user_query))
    
    # Force JSON output if possible or just parse
    emit_progress_sync(ToolProgress(
        tool_name="query_analysis",
        message="Analyzing query and generating research plan...",
        status="running"
    ))
    logger.info(f"Calling groomer LLM for query: {state['user_query'][:50]}...")
    logger.info(f"Message count: {len(messages)}, system prompt length: {len(system_content)}")
    
    # LLM call timeout (90 seconds) to prevent indefinite hanging
    LLM_TIMEOUT = 90
    
    try:
        response = await asyncio.wait_for(llm.ainvoke(messages), timeout=LLM_TIMEOUT)
        logger.info(f"Groomer LLM response received, length: {len(response.content)}")
    except asyncio.TimeoutError:
        logger.error(f"Groomer LLM call timed out after {LLM_TIMEOUT}s")
        state["errors"].append({"node": "groomer", "error": f"LLM call timed out after {LLM_TIMEOUT} seconds"})
        state["current_status"] = "grooming_failed"
        emit_progress_sync(ToolProgress(
            tool_name="query_analysis",
            message=f"Query analysis timed out after {LLM_TIMEOUT}s - please try again",
            status="error"
        ))
        return state
    except Exception as llm_error:
        logger.error(f"LLM call failed with error: {type(llm_error).__name__}: {llm_error}")
        state["errors"].append({"node": "groomer", "error": f"LLM call failed: {str(llm_error)}"})
        state["current_status"] = "grooming_failed"
        emit_progress_sync(ToolProgress(
            tool_name="query_analysis",
            message=f"LLM call failed: {str(llm_error)[:100]}",
            status="error"
        ))
        return state
    emit_progress_sync(ToolProgress(
        tool_name="query_analysis",
        message="Research plan generated",
        status="complete"
    ))
    
    try:
        # Extract JSON from response content (handling potential markdown)
        content = response.content
        logger.debug(f"Raw groomer response: {content[:500]}...")
        
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
            
        brief_data = json.loads(content)
        
        # Handle case where LLM returns clarifying_question as string instead of object
        # This happens when LLM doesn't follow the exact schema
        if brief_data.get("clarifying_question") and isinstance(brief_data["clarifying_question"], str):
            logger.warning("LLM returned clarifying_question as string, converting to object")
            brief_data["clarifying_question"] = {
                "question": brief_data["clarifying_question"],
                "options": None,
                "default_if_skipped": "Proceeding with general analysis covering all aspects."
            }
        
        research_brief = ResearchBrief(**brief_data)
        
        state["research_brief"] = research_brief
        elapsed = time.time() - start_time
        logger.info(f"[GROOMER] COMPLETE in {elapsed:.1f}s - status: {research_brief.status}")
        logger.info(f"[GROOMER] Financial queries: {len(research_brief.financial_agent_queries or [])}, Industry queries: {len(research_brief.industry_agent_queries or [])}")
        
        if research_brief.status == QueryStatus.NEEDS_CLARIFICATION:
            state["clarification_count"] += 1
            state["current_status"] = "awaiting_clarification"
        else:
            state["current_status"] = "grooming_complete"
            
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse groomer JSON response: {e}")
        logger.error(f"Response content: {response.content[:1000]}")
        state["errors"].append({"node": "groomer", "error": f"JSON parse error: {str(e)}", "response": response.content[:500]})
        state["current_status"] = "grooming_failed"
        # Emit error progress so UI doesn't show spinner indefinitely
        emit_progress_sync(ToolProgress(
            tool_name="query_analysis",
            message=f"Failed to parse query plan: {str(e)[:100]}",
            status="error"
        ))
    except Exception as e:
        import traceback
        error_info = traceback.format_exc()
        logger.error(f"Groomer error: {e}")
        logger.error(error_info)
        state["errors"].append({"node": "groomer", "error": str(e), "trace": error_info})
        state["current_status"] = "grooming_failed"
        # Emit error progress so UI doesn't show spinner indefinitely
        emit_progress_sync(ToolProgress(
            tool_name="query_analysis",
            message=f"Query analysis failed: {str(e)[:100]}",
            status="error"
        ))
        
    return state
