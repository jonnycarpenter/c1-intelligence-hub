from typing import Dict, Any, List, Optional
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from app.agents.research.state import DeepResearchState, ResearchBrief, QueryStatus
from app.agents.research.memory import get_research_memory
from app.agents.research.progress import emit_progress_sync, ToolProgress
from app.config.settings import settings
from app.utils.resilient_llm import create_resilient_llm_with_gemini_fallback
import json
import re
import logging
import asyncio

logger = logging.getLogger(__name__)


def _clean_and_repair_json(content: str) -> str:
    """
    Clean and repair common LLM JSON formatting issues.

    Handles:
    - Trailing commas before closing brackets/braces
    - Unclosed strings, arrays, objects
    - Text/commentary after the JSON object
    - Leading text before the JSON object
    """
    # Strip whitespace
    content = content.strip()

    # Find the actual JSON object boundaries
    # Look for the first '{' and the last '}'
    first_brace = content.find('{')
    if first_brace == -1:
        return content  # No JSON object found

    # Track brace depth to find the matching closing brace
    depth = 0
    in_string = False
    last_brace = -1
    i = first_brace
    while i < len(content):
        char = content[i]
        if char == '"' and (i == 0 or content[i-1] != '\\'):
            in_string = not in_string
        elif not in_string:
            if char == '{':
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0:
                    last_brace = i
                    break
        i += 1

    if last_brace > first_brace:
        # Found complete JSON object - extract it
        content = content[first_brace:last_brace + 1]
    else:
        # JSON object is unclosed - take from first brace and try to repair
        content = content[first_brace:]

        # Close unclosed strings
        if in_string:
            content += '"'

        # Close unclosed arrays and objects
        open_brackets = content.count('[') - content.count(']')
        open_braces = content.count('{') - content.count('}')
        content += ']' * max(0, open_brackets)
        content += '}' * max(0, open_braces)

    # Fix trailing commas: ,] or ,} (with optional whitespace)
    content = re.sub(r',\s*([}\]])', r'\1', content)

    return content

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

**⚠️ CRITICAL - DEFAULT TO "ready" STATUS**
You should almost NEVER ask for clarification. Set status="ready" in 95%+ of cases.

**BEFORE asking ANY clarifying question:**
1. Review conversation_history for prior Q&A exchanges
2. If you see an AIMessage (your question) + HumanMessage (their answer), that topic is RESOLVED
3. NEVER ask the same or similar question again - use the answer from history
4. If the user has already provided ANY context, incorporate it - don't ask again
5. If you asked about timeframe before, use a sensible default (e.g., "past 6 months")

**ONLY ask for clarification if ALL of these are true:**
1. The query is genuinely ambiguous AND
2. Different interpretations would lead to COMPLETELY different research AND  
3. You have NOT asked a similar question before AND
4. There is no reasonable default assumption

**Do NOT ask clarifying questions for:**
- Queries that are reasonably clear (most queries!)
- Minor ambiguities you can resolve with sensible defaults
- Timeframe questions - just assume "past 6-12 months" for recent, "past 2-3 years" for trends
- Scope questions - cover the most relevant aspects comprehensively
- Anything where asking would feel pedantic or annoying

**HARD RULES:**
- Maximum 1 clarifying question per research session
- If you've already asked a question and got an answer, proceed with status="ready"
- When in doubt, proceed with research using sensible defaults
- Format questions as plain sentences (no bullet points or markdown)

## Query Augmentation Strategy

### For the Financial Agent (searches SEC filings, earnings calls, 10-K/10-Q)
Generate 4-6 queries optimized for financial document search:
- Include relevant public company names and tickers
- Use financial terminology (revenue, margins, guidance, outlook, headwinds)
- Reference specific filing types when relevant
- Think about what executives would say in earnings calls
- Ensure query DIVERSITY — don't generate overlapping queries

### For the Industry Agent (searches web, press releases, RSS feeds, trade publications)
Generate 4-6 queries optimized for industry news and trade coverage:
- Use technical/trade terminology
- Include trade publication names for better results
- Think about how journalists and analysts write about these topics
- Consider geographic and end-market angles
- Ensure query DIVERSITY — cover different facets of the topic

## AGENT TOOL CAPABILITIES

Understanding what tools each agent has helps you craft better queries:

### Financial Agent Tools
| Tool | Requires | Best For |
|------|----------|----------|
| `search_earnings_quotes` | Company ticker | Pre-extracted earnings quotes, speaker-attributed, classified by type/sentiment |
| `search_sec_nuggets` | Company ticker | Pre-extracted SEC filing insights, competitive disclosures, risk factors |
| `query_corpus` (earnings) | Search query | Pre-ingested financial data, historical context |
| `get_company_news` | Ticker list | Recent news for specific public companies |
| `get_press_releases` | Ticker list | Official company announcements |
| `get_analyst_ratings` | Ticker list | Analyst views, price targets, ratings changes |
| `get_sentiment_summary` | Single ticker | Aggregated news sentiment score |

### Industry Agent Tools
| Tool | Requires | Best For |
|------|----------|----------|
| `news_search` (Exa) | Search query | Semantic news search, recent coverage |
| `web_search` (Exa) | Query + domains | Trade publication deep searches |
| `query_corpus` | Search query | Pre-ingested industry intelligence |
| `search_podcast_quotes` | Search query | Expert insights from industry podcasts (CW Talks, Composites Weekly, etc.) |
| `get_google_trends` | Keywords (1-5) | Demand signal validation, interest over time |
| `search_news_keyword` | Keyword | Broader keyword-based news (private companies) |
| `get_freight_rates` | Lane | Logistics/supply chain cost data |
| `get_trending_headlines` | - | Major market events of the day |

### Visual Agent Tools  
| Tool | Requires | Best For |
|------|----------|----------|
| `corpus_visuals_search` | Companies/industries | Charts, graphs, visual assets from articles |

## QUERY OPTIMIZATION RULES

Based on the user's query, ensure you:
- **Ticker/Public Company mentioned** → Include in `entities_to_track` to activate earnings quotes + SEC nuggets tools
- **Outlook/Guidance/Forecast** → Financial Agent will prioritize pre-extracted earnings quotes
- **Trends/Demand/Interest** → Industry Agent will use Google Trends validation
- **Supply Chain/Logistics** → Industry Agent will check freight rate data
- **Industry trend/materials** → Industry Agent will search podcast quotes for expert practitioner perspectives
- **Private company mentioned** → Industry Agent uses keyword search (not ticker-based)

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

def _count_prior_clarifications(history: list) -> int:
    """
    Count how many clarification exchanges have already occurred in the conversation.
    
    A clarification exchange is an AIMessage (the groomer asking a question) 
    followed by a HumanMessage (the user's answer).
    
    Returns:
        Number of completed clarification exchanges
    """
    if not history:
        return 0
    
    clarification_count = 0
    i = 0
    while i < len(history) - 1:
        msg = history[i]
        next_msg = history[i + 1]
        
        # AIMessage followed by HumanMessage = one clarification exchange
        if (hasattr(msg, '__class__') and msg.__class__.__name__ == 'AIMessage' and
            hasattr(next_msg, '__class__') and next_msg.__class__.__name__ == 'HumanMessage'):
            clarification_count += 1
            i += 2  # Skip both messages
        else:
            i += 1
    
    return clarification_count


async def query_grooming_node(state: DeepResearchState) -> DeepResearchState:
    """
    Main grooming logic. Calls Claude to interpret the query and generate a brief.
    
    Includes context injection from prior research to help the groomer:
    - Reference related past findings
    - Avoid redundant clarifying questions
    - Generate more targeted search queries
    
    IMPORTANT: Enforces max 1 clarifying question per session. If a clarification
    has already been asked and answered, the groomer will force status="ready"
    and proceed with research using sensible defaults.
    """
    import time
    from datetime import datetime
    start_time = time.time()
    start_timestamp = datetime.now().isoformat()
    logger.info(f"[GROOMER] START at {start_timestamp} - query: {state.get('user_query', '')[:50]}...")
    logger.info(f"[GROOMER] State keys: {list(state.keys())}")
    
    # =========================================================================
    # ENFORCEMENT: Max 1 clarifying question per session
    # Count prior clarifications from conversation history
    # =========================================================================
    history = state.get("conversation_history") or []
    prior_clarifications = _count_prior_clarifications(history)
    logger.info(f"[GROOMER] Prior clarifications detected: {prior_clarifications}")
    
    llm = create_resilient_llm_with_gemini_fallback(
        primary_model=settings.deep_research_groomer_model,
        anthropic_api_key=settings.anthropic_api_key,
        gemini_api_key=settings.gemini_api_key,
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
    # Context Injection: Fetch related prior research (DISABLED for debugging)
    # This was causing workflow hangs - disabled until root cause identified
    # Re-enabled: Prior research context injection (10s timeout + error handling built in)
    emit_progress_sync(ToolProgress(
        tool_name="prior_research",
        message="Checking for related prior research...",
        status="running"
    ))
    prior_context = await _get_prior_research_context(user_query)
    if prior_context:
        logger.info(f"[GROOMER] Prior research context injected: {len(prior_context)} chars")
    else:
        logger.info("[GROOMER] No prior research context found")
    
    # Build system prompt with optional prior context
    system_content = GROOMER_SYSTEM_PROMPT
    if prior_context:
        system_content = f"{GROOMER_SYSTEM_PROMPT}\n\n{prior_context}"
        logger.info("Injected prior research context into groomer prompt")
    
    # Add context hint when user has answered a clarifying question
    # This helps the LLM understand it should now proceed with the clarified info
    if prior_clarifications >= 1:
        system_content += """

## USER HAS ALREADY ANSWERED A CLARIFYING QUESTION
The user has already provided answers to clarifying questions. 
You MUST now set status="ready" and generate the research plan using their clarified information.
Do NOT ask any more questions. Proceed with research immediately.
Remember: Your response MUST be valid JSON matching the schema above."""
        logger.info("[GROOMER] Added clarification-answered context hint to prompt")
    
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
    
    # LLM call timeout (60 seconds) - reduced from 90s for faster failure detection
    # The Anthropic SDK has its own 120s HTTP timeout, but we want to fail faster
    LLM_TIMEOUT = 60
    
    try:
        logger.info(f"[GROOMER] LLM AWAIT START - timeout={LLM_TIMEOUT}s")
        
        # Create the task explicitly so we can track its state
        llm_task = asyncio.create_task(llm.ainvoke(messages))
        
        try:
            response = await asyncio.wait_for(llm_task, timeout=LLM_TIMEOUT)
            logger.info(f"[GROOMER] LLM AWAIT COMPLETE - response length: {len(response.content)}")
        except asyncio.TimeoutError:
            # Explicitly cancel the task to ensure cleanup
            logger.error(f"[GROOMER] TIMEOUT after {LLM_TIMEOUT}s - cancelling task")
            llm_task.cancel()
            try:
                await llm_task
            except asyncio.CancelledError:
                logger.info("[GROOMER] Task successfully cancelled after timeout")
            raise  # Re-raise the TimeoutError
            
    except asyncio.TimeoutError:
        logger.error(f"[GROOMER] LLM call timed out after {LLM_TIMEOUT}s")
        state["errors"].append({"node": "groomer", "error": f"LLM call timed out after {LLM_TIMEOUT} seconds"})
        state["current_status"] = "grooming_failed"
        emit_progress_sync(ToolProgress(
            tool_name="query_analysis",
            message=f"Query analysis timed out after {LLM_TIMEOUT}s - please try again",
            status="error"
        ))
        return state
    except asyncio.CancelledError:
        elapsed = time.time() - start_time
        logger.error(f"[GROOMER] LLM task was cancelled externally after {elapsed:.1f}s")
        state["errors"].append({"node": "groomer", "error": f"LLM call was cancelled after {elapsed:.1f}s"})
        state["current_status"] = "grooming_failed"
        emit_progress_sync(ToolProgress(
            tool_name="query_analysis",
            message="Query analysis was cancelled",
            status="error"
        ))
        return state
    except Exception as llm_error:
        logger.error(f"[GROOMER] LLM call failed: {type(llm_error).__name__}: {llm_error}")
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
    
    # =========================================================================
    # PARSE LLM RESPONSE WITH REPAIR + RETRY
    # Haiku sometimes produces malformed JSON (trailing commas, unclosed
    # brackets, commentary after closing brace). We:
    #   1. Extract JSON from markdown fences if present
    #   2. Try json.loads() directly
    #   3. On failure, apply _clean_and_repair_json() and retry parse
    #   4. If repair also fails, retry the LLM call once (Haiku is fast/cheap)
    # =========================================================================

    def _extract_json_content(raw_content: str) -> str:
        """Extract JSON from markdown fences or return raw content."""
        if not raw_content or not raw_content.strip():
            return ""
        c = raw_content
        if "```json" in c:
            c = c.split("```json")[1].split("```")[0].strip()
        elif "```" in c:
            c = c.split("```")[1].split("```")[0].strip()
        return c.strip()

    def _try_parse_groomer_json(raw_content: str) -> dict:
        """
        Try to parse JSON from LLM response with repair fallback.
        Raises json.JSONDecodeError if both direct parse and repair fail.
        """
        content = _extract_json_content(raw_content)
        if not content:
            raise json.JSONDecodeError("Empty content after extraction", "", 0)

        # Attempt 1: Direct parse
        try:
            return json.loads(content)
        except json.JSONDecodeError as first_err:
            logger.warning(f"[GROOMER] Direct JSON parse failed: {first_err}, attempting repair")

        # Attempt 2: Clean and repair common issues
        repaired = _clean_and_repair_json(content)
        try:
            result = json.loads(repaired)
            logger.info("[GROOMER] JSON repair successful")
            return result
        except json.JSONDecodeError:
            # Also try repairing the raw content (in case markdown extraction was wrong)
            repaired_raw = _clean_and_repair_json(raw_content)
            try:
                result = json.loads(repaired_raw)
                logger.info("[GROOMER] JSON repair (from raw content) successful")
                return result
            except json.JSONDecodeError as final_err:
                raise final_err

    brief_data = None

    try:
        content = response.content
        logger.info(f"[GROOMER] Raw response length: {len(content)} chars")
        logger.debug(f"Raw groomer response: {content[:500]}...")

        # Validate response is not empty
        if not content or not content.strip():
            logger.error("[GROOMER] LLM returned empty response")
            state["errors"].append({"node": "groomer", "error": "LLM returned empty response - please try again"})
            state["current_status"] = "grooming_failed"
            emit_progress_sync(ToolProgress(
                tool_name="query_analysis",
                message="LLM returned empty response - please try again",
                status="error"
            ))
            return state

        brief_data = _try_parse_groomer_json(content)

    except json.JSONDecodeError as e:
        # =====================================================================
        # RETRY: Re-invoke LLM once on JSON parse failure (Haiku is fast/cheap)
        # =====================================================================
        logger.warning(f"[GROOMER] JSON parse failed after repair, retrying LLM call: {e}")
        logger.warning(f"[GROOMER] Failed response (first 1000 chars): {response.content[:1000]}")

        try:
            emit_progress_sync(ToolProgress(
                tool_name="query_analysis",
                message="Re-analyzing query...",
                status="running"
            ))
            retry_response = await asyncio.wait_for(llm.ainvoke(messages), timeout=LLM_TIMEOUT)
            retry_content = retry_response.content
            logger.info(f"[GROOMER] Retry response length: {len(retry_content)} chars")

            brief_data = _try_parse_groomer_json(retry_content)
            logger.info("[GROOMER] Retry parse successful")

        except json.JSONDecodeError as retry_err:
            logger.error(f"[GROOMER] Retry also failed to parse JSON: {retry_err}")
            logger.error(f"[GROOMER] Retry response: {retry_content[:1000]}")
            state["errors"].append({"node": "groomer", "error": f"JSON parse error (after retry): {str(retry_err)}", "response": retry_content[:500]})
            state["current_status"] = "grooming_failed"
            emit_progress_sync(ToolProgress(
                tool_name="query_analysis",
                message=f"Failed to parse query plan: {str(retry_err)[:100]}",
                status="error"
            ))
            return state
        except (asyncio.TimeoutError, asyncio.CancelledError, Exception) as retry_llm_err:
            logger.error(f"[GROOMER] Retry LLM call failed: {type(retry_llm_err).__name__}: {retry_llm_err}")
            state["errors"].append({"node": "groomer", "error": f"JSON parse error: {str(e)} (retry failed: {str(retry_llm_err)})"})
            state["current_status"] = "grooming_failed"
            emit_progress_sync(ToolProgress(
                tool_name="query_analysis",
                message=f"Failed to parse query plan: {str(e)[:100]}",
                status="error"
            ))
            return state
    except Exception as e:
        import traceback
        error_info = traceback.format_exc()
        logger.error(f"Groomer error: {e}")
        logger.error(error_info)
        state["errors"].append({"node": "groomer", "error": str(e), "trace": error_info})
        state["current_status"] = "grooming_failed"
        emit_progress_sync(ToolProgress(
            tool_name="query_analysis",
            message=f"Query analysis failed: {str(e)[:100]}",
            status="error"
        ))
        return state

    # =========================================================================
    # POST-PARSE: Validate and build ResearchBrief
    # =========================================================================
    try:
        # Handle case where LLM returns clarifying_question as string instead of object
        if brief_data.get("clarifying_question") and isinstance(brief_data["clarifying_question"], str):
            logger.warning("LLM returned clarifying_question as string, converting to object")
            brief_data["clarifying_question"] = {
                "question": brief_data["clarifying_question"],
                "options": None,
                "default_if_skipped": "Proceeding with general analysis covering all aspects."
            }

        research_brief = ResearchBrief(**brief_data)

        # =====================================================================
        # ENFORCEMENT: Max 1 clarifying question per session
        # If we've already asked a clarification, force status to READY
        # =====================================================================
        if research_brief.status == QueryStatus.NEEDS_CLARIFICATION and prior_clarifications >= 1:
            logger.warning(f"[GROOMER] ENFORCEMENT: Already had {prior_clarifications} clarification(s), forcing status=READY")
            research_brief.status = QueryStatus.READY
            research_brief.clarifying_question = None
            emit_progress_sync(ToolProgress(
                tool_name="query_analysis",
                message="Proceeding with research (clarification limit reached)",
                status="complete"
            ))

        state["research_brief"] = research_brief
        elapsed = time.time() - start_time
        logger.info(f"[GROOMER] COMPLETE in {elapsed:.1f}s - status: {research_brief.status}")
        logger.info(f"[GROOMER] Financial queries: {len(research_brief.financial_agent_queries or [])}, Industry queries: {len(research_brief.industry_agent_queries or [])}")

        # Build agent reasoning summary for frontend display
        fin_queries = research_brief.financial_agent_queries or []
        ind_queries = research_brief.industry_agent_queries or []
        entities = research_brief.entities_to_track or []
        reasoning_parts = [
            f"**Query Interpretation**: {research_brief.clarified_intent or 'N/A'}",
            f"**Timeframe**: {research_brief.timeframe or 'Recent'}",
            f"**Entities to Track**: {', '.join(entities) if entities else 'None identified'}",
            f"**Domain Context**: {(research_brief.domain_context or 'N/A')[:200]}",
            "",
            f"**Financial Queries** ({len(fin_queries)}):",
            *[f"- {q}" for q in fin_queries],
            "",
            f"**Industry Queries** ({len(ind_queries)}):",
            *[f"- {q}" for q in ind_queries],
        ]
        state["agent_reasoning"] = {"groom": "\n".join(reasoning_parts)}

        if research_brief.status == QueryStatus.NEEDS_CLARIFICATION:
            state["clarification_count"] += 1
            state["current_status"] = "awaiting_clarification"
            state["last_clarification"] = research_brief.clarifying_question
        else:
            state["current_status"] = "grooming_complete"

    except Exception as e:
        import traceback
        error_info = traceback.format_exc()
        logger.error(f"Groomer validation error: {e}")
        logger.error(error_info)
        state["errors"].append({"node": "groomer", "error": str(e), "trace": error_info})
        state["current_status"] = "grooming_failed"
        emit_progress_sync(ToolProgress(
            tool_name="query_analysis",
            message=f"Query analysis failed: {str(e)[:100]}",
            status="error"
        ))

    return state
