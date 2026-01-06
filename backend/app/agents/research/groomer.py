from typing import Dict, Any, List
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from app.agents.research.state import DeepResearchState, ResearchBrief, QueryStatus
from app.config.settings import settings
import json
import logging

logger = logging.getLogger(__name__)

# System prompt is derived from query_input_agent.md
GROOMER_SYSTEM_PROMPT = """
You are a Query Grooming Agent for a composites industry intelligence platform called the C1 Intelligence Hub. Your job is to take a user's research question and prepare it for downstream research agents.

## Your Responsibilities

1. INTERPRET the user's intent — what are they actually trying to learn?
2. DECIDE if clarification is needed — only ask if the answer would significantly change the research approach
3. AUGMENT the query — generate optimized searches for the Financial Agent and Industry Agent
4. ENRICH with context — provide domain knowledge that helps research agents succeed

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
    """
    llm = ChatAnthropic(
        model=settings.deep_research_groomer_model,
        anthropic_api_key=settings.anthropic_api_key,
        temperature=0,
    )
    
    # Build messages from state
    messages = [SystemMessage(content=GROOMER_SYSTEM_PROMPT)]
    
    # Filter conversation history to only include messages with non-empty content
    # This prevents Anthropic API errors about empty message content
    history = state.get("conversation_history") or []
    for msg in history:
        if msg and hasattr(msg, 'content') and msg.content:
            messages.append(msg)
    
    # Ensure user query is not empty
    user_query = state.get("user_query", "").strip()
    if not user_query:
        logger.error("Empty user_query in state")
        return {
            **state,
            "current_status": "grooming_failed",
            "errors": state.get("errors", []) + [{"node": "groomer", "error": "Empty user query"}],
        }
    
    messages.append(HumanMessage(content=user_query))
    
    # Force JSON output if possible or just parse
    logger.info(f"Calling groomer LLM for query: {state['user_query'][:50]}...")
    response = await llm.ainvoke(messages)
    logger.info(f"Groomer LLM response received, length: {len(response.content)}")
    
    try:
        # Extract JSON from response content (handling potential markdown)
        content = response.content
        logger.debug(f"Raw groomer response: {content[:500]}...")
        
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
            
        brief_data = json.loads(content)
        research_brief = ResearchBrief(**brief_data)
        
        state["research_brief"] = research_brief
        logger.info(f"Research brief created with status: {research_brief.status}")
        
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
    except Exception as e:
        import traceback
        error_info = traceback.format_exc()
        logger.error(f"Groomer error: {e}")
        logger.error(error_info)
        state["errors"].append({"node": "groomer", "error": str(e), "trace": error_info})
        state["current_status"] = "grooming_failed"
        
    return state
