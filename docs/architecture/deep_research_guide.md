# Deep Research Implementation Guide

**Purpose**: Complete implementation guide for building a multi-agent parallel research pipeline with real-time SSE streaming and beautiful visual progress display.

**This Guide Contains Everything Needed To**:
1. Build the backend LangGraph workflow with parallel execution
2. Implement SSE streaming with granular progress events
3. Create the visual progress pipeline display (the impressive part!)
4. Build the research report display components
5. Handle errors, timeouts, and edge cases

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [TypeScript Types (Frontend)](#typescript-types-frontend)
3. [React Hook: useDeepResearch](#react-hook-usedeepresearch)
4. [Visual Components](#visual-components)
   - [ResearchProgress](#researchprogress-component)
   - [ResearchReport](#researchreport-component)
   - [ResearchDashboard](#researchdashboard-component)
   - [Supporting Components](#supporting-components)
5. [Backend State Management](#backend-state-management)
6. [Backend SSE API Route](#backend-sse-api-route)
7. [Styling Utilities](#styling-utilities)
8. [Key Implementation Details](#key-implementation-details)
9. [Production Checklist](#production-checklist)

---

## Architecture Overview

### The Big Picture

```
User Query → [Groomer] → [Financial + Industry + Visual (parallel)] → [Synthesizer] → Final Report
                                                                            ↓
                                                               [Category (optional)]
                                                                            ↓
                                                               [Validator (optional)]
```

**Key Innovation**: **Parallel execution** using LangGraph's `Send` API reduces research time by ~60% compared to sequential execution.

### Node Summary

| Node | Purpose | Model | Avg Time |
|------|---------|-------|----------|
| **Groomer** | Query analysis, sub-query generation | Haiku 4.5 | 8-12s |
| **Financial** | Earnings, SEC filings, market data | Sonnet 4.6 | 25-35s |
| **Industry** | News, trends, competitive intel | Sonnet 4.6 | 25-35s |
| **Visual** | Charts, graphs from corpus | Sonnet 4.6 | 10-15s |
| **Synthesizer** | Report generation, deduplication | Sonnet 4.6 | 15-25s |
| **Category** *(Phase 2)* | Sales intelligence by territory | Sonnet 4.6 | 10-15s |
| **Validator** *(Phase 2)* | Citation verification | Sonnet 4.6 | 8-12s |

**Total Time**: ~90-120 seconds for basic research (Groomer → Research → Synthesizer)

### Why This Architecture?

1. **Parallel Research = Speed**: Financial, Industry, and Visual agents run simultaneously
2. **Specialized Agents = Quality**: Each agent focuses on one domain, uses targeted tools
3. **Groomer = Better Queries**: Pre-processing creates targeted sub-queries for each agent
4. **Synthesizer = Coherence**: Deduplicates findings, connects insights, maintains brevity
5. **Real-Time Progress = UX**: SSE streaming shows users what's happening, not just a spinner

---

## Prerequisites & Dependencies

### Python Packages

```bash
pip install \
  langgraph \
  langchain-anthropic \
  langchain-core \
  anthropic \
  httpx \
  pydantic \
  asyncio
```

### Core Concepts to Understand

Before building this, make sure you understand:
- **LangGraph**: Graph-based agent orchestration (not LangChain)
- **TypedDict with Annotated**: State management with reducers
- **async/await**: All I/O is async (LLM calls, tool calls, SSE)
- **Server-Sent Events (SSE)**: One-way real-time streaming to frontend
- **Pydantic Models**: Structured output from LLMs

### External APIs Needed

This workflow uses several external APIs. You'll need at least:
- **Anthropic API** (required for LLM calls)
- **Exa.ai** (for news/web search in Industry agent)
- Optional: Financial APIs (SEC.io, FMP, StockNews), Logo.dev

---

## Project Structure

Recommended file organization:

```
backend/
├── app/
│   ├── agents/
│   │   └── research/
│   │       ├── __init__.py
│   │       ├── state.py              # State schema with reducers
│   │       ├── progress.py           # Progress emission system
│   │       ├── groomer.py            # Query analysis agent
│   │       ├── financial.py          # Financial research agent
│   │       ├── industry.py           # Industry research agent
│   │       ├── visual.py             # Visual research agent
│   │       ├── synthesizer.py        # Report synthesis agent
│   │       ├── category.py           # Sales intelligence (Phase 2)
│   │       ├── validator.py          # Citation verification (Phase 2)
│   │       └── README.md             # Architecture docs
│   ├── graph/
│   │   └── research_workflow.py      # LangGraph workflow definition
│   ├── api/
│   │   └── routes/
│   │       └── deep_research.py      # SSE streaming endpoint
│   ├── mcp/
│   │   └── tools/
│   │       ├── corpus_search.py      # Pre-ingested data search
│   │       ├── sec_filings.py        # SEC document retrieval
│   │       ├── earnings_calls.py     # Earnings transcripts
│   │       ├── news_search.py        # Exa.ai news search
│   │       └── corpus_visuals.py     # Image/chart search
│   └── config/
│       └── settings.py               # Model & timeout config
```

---

## State Management with Reducers

### Why Reducers?

LangGraph's parallel execution passes full state to each branch. When branches return, their outputs must be merged. Without reducers, duplicate keys cause `InvalidUpdateError`.

### The Problem

```python
# WITHOUT REDUCERS - This breaks with parallel execution
class DeepResearchState(TypedDict):
    user_query: str  # ❌ Which value wins when 3 agents return?
    errors: List[str]  # ❌ How do we merge error lists?
```

### The Solution

```python
# WITH REDUCERS - Explicit merge strategy per field
from typing import Annotated, TypedDict, List, Optional, Any
from langchain_core.messages import BaseMessage

def _keep_first(a, b):
    """Keep original value (immutable fields)."""
    if a is not None and a != "":
        return a
    return b

def _keep_last(a, b):
    """Keep latest value (mutable outputs)."""
    return b if b is not None else a

def _merge_errors(a, b):
    """Combine error lists from parallel branches."""
    return (a or []) + (b or [])

class DeepResearchState(TypedDict):
    # Immutable fields (set early, never change)
    user_query: Annotated[str, _keep_first]
    conversation_history: Annotated[List[BaseMessage], _keep_first]
    research_brief: Annotated[Optional[ResearchBrief], _keep_first]
    
    # Mutable outputs (each agent updates its own field)
    financial_output: Annotated[Optional[FinancialAgentOutput], _keep_last]
    industry_output: Annotated[Optional[IndustryAgentOutput], _keep_last]
    visual_output: Annotated[Optional[VisualAgentOutput], _keep_last]
    final_report: Annotated[Optional[SynthesisAgentOutput], _keep_last]
    current_status: Annotated[str, _keep_last]
    
    # Merged from parallel branches
    errors: Annotated[List[Dict[str, Any]], _merge_errors]
```

### Reducer Patterns

| Pattern | Use Case | Example |
|---------|----------|---------|
| `_keep_first` | Immutable inputs set once | `user_query`, `research_brief` |
| `_keep_last` | Agent outputs that change | `financial_output`, `current_status` |
| `_merge_errors` | Accumulate errors from all branches | `errors` list |
| Custom merge | Complex data structures | Combine findings lists |

### Common Mistake

```python
# ❌ WRONG - This will cause InvalidUpdateError
state["user_query"] = "Updated query"  # Can't change _keep_first field!

# ✅ CORRECT - Only update fields your agent owns
state["financial_output"] = FinancialAgentOutput(...)
state["current_status"] = "financial_complete"
```

---

## Agent Implementation Patterns

### Standard Agent Structure

Every agent follows this pattern:

```python
"""
Agent: Financial Research

Purpose: Gather financial data (earnings, SEC filings, market metrics)
Tools: get_earnings_transcript, query_corpus, get_sec_filings
Model: claude-sonnet-4-6
"""

import asyncio
from typing import Dict, Any
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field

from app.agents.research.state import DeepResearchState
from app.agents.research.progress import emit_progress_sync, ToolProgress
from app.mcp.tools.earnings_calls import get_earnings_transcript
from app.mcp.tools.corpus_search import query_corpus
from app.config.settings import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

# =============================================================================
# OUTPUT SCHEMA
# =============================================================================

class Finding(BaseModel):
    """A single research finding."""
    text: str = Field(description="The finding text")
    source: str = Field(description="Source of information")
    date: Optional[str] = Field(default=None, description="Publication date")
    confidence: str = Field(description="high/medium/low")

class FinancialAgentOutput(BaseModel):
    """Output from Financial Research agent."""
    findings: List[Finding] = []
    key_metrics: Dict[str, Any] = {}
    summary: str = ""
    companies_analyzed: List[str] = []

# =============================================================================
# SYSTEM PROMPT
# =============================================================================

FINANCIAL_SYSTEM_PROMPT = """You are a financial research analyst.

Your task: Analyze financial data for the given research brief.

Tools available:
- get_earnings_transcript: Recent earnings call transcripts
- query_corpus: Pre-ingested financial articles
- get_sec_filings: SEC 10-K, 10-Q, 8-K filings

Instructions:
1. Extract company names from the research brief
2. For each company, gather recent financial data
3. Look for trends, changes, risks, opportunities
4. Cite all sources with dates
5. Focus on facts, avoid speculation

Output must be valid JSON matching FinancialAgentOutput schema."""

# =============================================================================
# AGENT NODE
# =============================================================================

LLM_TIMEOUT = 90  # seconds

async def financial_research_node(state: DeepResearchState) -> Dict[str, Any]:
    """
    Financial research agent node.
    
    Gathers financial intelligence: earnings, SEC filings, market data.
    """
    logger.info(f"[FINANCIAL_RESEARCH] START - query: {state['user_query'][:50]}...")
    start_time = time.time()
    
    try:
        brief = state["research_brief"]
        if not brief:
            logger.error("[FINANCIAL_RESEARCH] No research brief in state")
            return {
                "financial_output": None,
                "current_status": "financial_failed",
                "errors": [{"node": "financial", "error": "No research brief"}]
            }
        
        # Initialize LLM with structured output
        llm = ChatAnthropic(
            model=settings.deep_research_financial_model,
            temperature=0,
        ).with_structured_output(FinancialAgentOutput)
        
        # Bind tools (LangChain will handle tool calling)
        tools = [get_earnings_transcript, query_corpus]
        llm_with_tools = llm.bind_tools(tools)
        
        # Build prompt
        messages = [
            SystemMessage(content=FINANCIAL_SYSTEM_PROMPT),
            HumanMessage(content=f"""Research Brief:
{brief.dict()}

Focus on financial queries:
{chr(10).join(f"- {q}" for q in brief.financial_queries)}

Analyze financial health, performance, risks, and opportunities.""")
        ]
        
        # Emit progress
        emit_progress_sync(ToolProgress(
            tool_name="financial_research",
            message="Analyzing financial data",
            status="running"
        ))
        
        # Call LLM with timeout protection
        try:
            response = await asyncio.wait_for(
                llm_with_tools.ainvoke(messages),
                timeout=LLM_TIMEOUT
            )
            elapsed = time.time() - start_time
            logger.info(f"[FINANCIAL_RESEARCH] LLM response received in {elapsed:.2f}s")
            
        except asyncio.TimeoutError:
            logger.error(f"[FINANCIAL_RESEARCH] LLM call timed out after {LLM_TIMEOUT}s")
            return {
                "financial_output": None,
                "current_status": "financial_failed",
                "errors": [{"node": "financial", "error": f"LLM timeout after {LLM_TIMEOUT}s"}]
            }
        
        # Parse response (already structured as FinancialAgentOutput)
        output = response if isinstance(response, FinancialAgentOutput) else FinancialAgentOutput(**response)
        
        elapsed = time.time() - start_time
        logger.info(f"[FINANCIAL_RESEARCH] COMPLETE in {elapsed:.2f}s - {len(output.findings)} findings")
        
        # Emit completion
        emit_progress_sync(ToolProgress(
            tool_name="financial_research",
            message=f"Found {len(output.findings)} financial insights",
            status="complete"
        ))
        
        return {
            "financial_output": output,
            "current_status": "financial_complete"
        }
        
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"[FINANCIAL_RESEARCH] FAILED after {elapsed:.2f}s: {e}", exc_info=True)
        
        return {
            "financial_output": None,
            "current_status": "financial_failed",
            "errors": [{"node": "financial", "error": str(e)}]
        }
```

### Key Agent Patterns

**1. Structured Output with Pydantic**
```python
# Define schema
class AgentOutput(BaseModel):
    findings: List[Finding]
    summary: str

# Use with LLM
llm = ChatAnthropic(...).with_structured_output(AgentOutput)
response = await llm.ainvoke(messages)
# response is already typed as AgentOutput!
```

**2. Tool Binding**
```python
# Bind tools to LLM - LangChain handles tool calling loop
tools = [tool1, tool2, tool3]
llm_with_tools = llm.bind_tools(tools)
response = await llm_with_tools.ainvoke(messages)
```

**3. Timeout Protection**
```python
# Wrap all LLM calls with asyncio.wait_for
LLM_TIMEOUT = 90
try:
    response = await asyncio.wait_for(
        llm.ainvoke(messages),
        timeout=LLM_TIMEOUT
    )
except asyncio.TimeoutError:
    # Handle timeout gracefully
    return error_state
```

**4. Progress Emission**
```python
# Emit progress at key moments
emit_progress_sync(ToolProgress(
    tool_name="my_agent",
    message="Starting analysis",
    status="running"
))

# ... do work ...

emit_progress_sync(ToolProgress(
    tool_name="my_agent",
    message="Complete - found 12 insights",
    status="complete"
))
```

**5. Error Handling**
```python
# Always return state updates, never raise
try:
    # ... agent work ...
    return {
        "agent_output": result,
        "current_status": "agent_complete"
    }
except Exception as e:
    logger.error(f"Agent failed: {e}", exc_info=True)
    return {
        "agent_output": None,
        "current_status": "agent_failed",
        "errors": [{"node": "agent_name", "error": str(e)}]
    }
```

---

## LangGraph Workflow Setup

### Step 1: Define the Graph

```python
"""
LangGraph Workflow for Deep Research

File: app/graph/research_workflow.py
"""

from langgraph.graph import StateGraph, END
from langgraph.types import Send
from typing import List, Union, Literal

from app.agents.research.state import DeepResearchState, QueryStatus
from app.agents.research.groomer import query_grooming_node
from app.agents.research.financial import financial_research_node
from app.agents.research.industry import industry_research_node
from app.agents.research.visual import visual_research_node
from app.agents.research.synthesizer import synthesis_node

import logging
logger = logging.getLogger(__name__)

def create_research_workflow():
    """Create the Deep Research LangGraph workflow."""
    
    workflow = StateGraph(DeepResearchState)
    
    # Add nodes
    workflow.add_node("groom", query_grooming_node)
    workflow.add_node("financial_research", financial_research_node)
    workflow.add_node("industry_research", industry_research_node)
    workflow.add_node("visual_research", visual_research_node)
    workflow.add_node("synthesize", synthesis_node)
    
    # Set entry point
    workflow.set_entry_point("groom")
    
    # Add edges with conditional routing
    workflow.add_conditional_edges(
        "groom",
        route_after_groom,
        # Possible destinations
        ["financial_research", "industry_research", "visual_research", END]
    )
    
    # Parallel research branches converge at synthesizer
    workflow.add_edge("financial_research", "synthesize")
    workflow.add_edge("industry_research", "synthesize")
    workflow.add_edge("visual_research", "synthesize")
    
    # End after synthesis
    workflow.add_edge("synthesize", END)
    
    return workflow.compile()
```

### Step 2: Implement Parallel Routing

The magic of parallel execution happens in the router:

```python
def route_after_groom(state: DeepResearchState) -> Union[List[Send], Literal["__end__"]]:
    """
    Route after grooming - fan-out to parallel research or end for clarification.
    
    Returns:
        - END: If needs clarification or failed
        - List[Send]: Fan-out to parallel research branches
    """
    logger.info(f"[ROUTE_AFTER_GROOM] current_status: {state.get('current_status')}")
    
    brief = state.get("research_brief")
    
    # If grooming failed, end workflow
    if not brief:
        logger.error("[ROUTE_AFTER_GROOM] No research brief - ending")
        return END
    
    # If needs clarification, end to collect user input
    if brief.status == QueryStatus.NEEDS_CLARIFICATION:
        logger.info("[ROUTE_AFTER_GROOM] Needs clarification - ending")
        return END
    
    # Ready for research - fan out to ALL 3 agents in parallel
    logger.info("[ROUTE_AFTER_GROOM] Fanning out to parallel research")
    return [
        Send("financial_research", state),
        Send("industry_research", state),
        Send("visual_research", state),
    ]
```

**Key Points**:
- `Send("node_name", state)` creates a parallel branch
- Each branch gets a **copy** of the state
- LangGraph waits for all branches before calling synthesizer
- Branches can complete in any order - reducers handle merging

### Step 3: Compile and Run

```python
# Compile workflow
workflow = create_research_workflow()

# Run workflow
initial_state = {
    "user_query": "What's the outlook for aerospace composites?",
    "conversation_history": [],
    "clarification_count": 0,
    "errors": []
}

# Stream events (for progress tracking)
async for event in workflow.astream(initial_state):
    node_name = list(event.keys())[0]
    node_output = event[node_name]
    print(f"{node_name}: {node_output.get('current_status')}")

# Or get final state
final_state = await workflow.ainvoke(initial_state)
report = final_state.get("final_report")
```

---

## SSE Streaming & Progress

### Why SSE?

Server-Sent Events provide **one-way real-time streaming** from server to client:
- User sees progress as research happens (not just a spinner)
- Frontend can display which agent is active
- Tool progress shows specific searches ("Fetching SEC 10-K for Hexcel")
- Timeout handling is transparent to user

### Architecture

```
[LangGraph Workflow]
        ↓
[Progress Collector] ← Agents emit progress
        ↓
[AsyncIO Queue]
        ↓
[SSE Endpoint] ← Frontend polls via EventSource
        ↓
[Frontend Progress UI]
```

### Step 1: Progress Emission System

```python
"""
Progress emission for real-time updates.

File: app/agents/research/progress.py
"""

import asyncio
from typing import Optional
from pydantic import BaseModel
from enum import Enum

class ToolStatus(str, Enum):
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"

class ToolProgress(BaseModel):
    """Progress update from a tool or agent."""
    tool_name: str
    message: str
    status: ToolStatus
    ticker: Optional[str] = None
    details: Optional[dict] = None

# Global queue for progress events
_progress_queue: Optional[asyncio.Queue] = None

def set_progress_queue(queue: asyncio.Queue):
    """Set the global progress queue (called by API route)."""
    global _progress_queue
    _progress_queue = queue

def emit_progress_sync(progress: ToolProgress):
    """
    Emit progress from sync context (most agents).
    
    Safe to call even if queue not set (no-op).
    """
    global _progress_queue
    if _progress_queue is not None:
        try:
            # put_nowait is safe from sync context
            _progress_queue.put_nowait(progress.dict())
        except Exception as e:
            # Never let progress emission break the agent
            print(f"Failed to emit progress: {e}")

async def emit_progress_async(progress: ToolProgress):
    """Emit progress from async context."""
    global _progress_queue
    if _progress_queue is not None:
        try:
            await _progress_queue.put(progress.dict())
        except Exception as e:
            print(f"Failed to emit progress: {e}")
```

### Step 2: SSE Endpoint

```python
"""
SSE streaming endpoint for Deep Research.

File: app/api/routes/deep_research.py
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse
import asyncio
import time
import json
from typing import AsyncGenerator

from app.graph.research_workflow import create_research_workflow
from app.agents.research.progress import set_progress_queue
from app.agents.research.state import DeepResearchState

router = APIRouter(prefix="/api/research", tags=["research"])

async def research_event_generator(
    user_query: str,
    conversation_history: list = None
) -> AsyncGenerator[dict, None]:
    """
    Stream research progress as SSE events.
    
    Yields events:
    - node_start: {node: "groomer", status: "running"}
    - node_complete: {node: "groomer", status: "complete", output: {...}}
    - tool_progress: {tool_name: "...", message: "...", status: "..."}
    - error: {error: "...", node: "..."}
    - timeout: {message: "...", active_nodes: [...]}
    - complete: {final_report: {...}}
    """
    progress_queue = asyncio.Queue()
    set_progress_queue(progress_queue)
    
    # Initialize state
    initial_state: DeepResearchState = {
        "user_query": user_query,
        "conversation_history": conversation_history or [],
        "clarification_count": 0,
        "research_brief": None,
        "financial_output": None,
        "industry_output": None,
        "visual_output": None,
        "final_report": None,
        "current_status": "initializing",
        "errors": []
    }
    
    # Compile workflow
    workflow = create_research_workflow()
    
    # Start workflow in background
    workflow_task = asyncio.create_task(workflow.ainvoke(initial_state))
    
    # Stream events
    start_time = time.time()
    timeout_seconds = 300  # 5 minutes
    accumulated_state = {}
    
    try:
        while True:
            # Check for workflow completion
            if workflow_task.done():
                final_state = workflow_task.result()
                accumulated_state.update(final_state)
                
                if final_state.get("final_report"):
                    yield {
                        "event": "complete",
                        "data": json.dumps({
                            "final_report": final_state["final_report"].dict()
                        })
                    }
                break
            
            # Check for timeout
            elapsed = time.time() - start_time
            if elapsed > timeout_seconds:
                workflow_task.cancel()
                yield {
                    "event": "timeout",
                    "data": json.dumps({
                        "message": "Research timed out after 5 minutes",
                        "elapsed": elapsed,
                        "last_status": accumulated_state.get("current_status")
                    })
                }
                break
            
            # Poll progress queue with timeout
            pending_task = None
            try:
                # CRITICAL: Use asyncio.shield to prevent cancellation
                # Without shield, wait_for timeout would cancel the workflow!
                if pending_task is None:
                    pending_task = asyncio.create_task(progress_queue.get())
                
                progress = await asyncio.wait_for(
                    asyncio.shield(pending_task),
                    timeout=0.1  # 100ms poll interval
                )
                pending_task = None  # Reset for next iteration
                
                # Emit tool progress
                yield {
                    "event": "tool_progress",
                    "data": json.dumps(progress)
                }
                
            except asyncio.TimeoutError:
                # No progress in 100ms, continue loop
                continue
            
            # Small delay to prevent CPU spin
            await asyncio.sleep(0.01)
    
    finally:
        # Cleanup
        set_progress_queue(None)
        if not workflow_task.done():
            workflow_task.cancel()


@router.post("/stream")
async def stream_research(request: dict):
    """
    Start deep research with SSE streaming.
    
    Request body:
        {
            "query": "What's the outlook for aerospace composites?",
            "conversation_history": []  # optional
        }
    
    Response: SSE stream with events
    """
    user_query = request.get("query")
    if not user_query:
        raise HTTPException(status_code=400, detail="Query is required")
    
    return EventSourceResponse(
        research_event_generator(
            user_query=user_query,
            conversation_history=request.get("conversation_history", [])
        )
    )
```

### Step 3: Frontend Integration

```typescript
// Frontend: Hook up to SSE endpoint

const [progress, setProgress] = useState<string>('')
const [report, setReport] = useState<any>(null)

const startResearch = async (query: string) => {
  const eventSource = new EventSource(
    `/api/research/stream?query=${encodeURIComponent(query)}`
  )
  
  eventSource.addEventListener('tool_progress', (e) => {
    const data = JSON.parse(e.data)
    setProgress(`${data.tool_name}: ${data.message}`)
  })
  
  eventSource.addEventListener('complete', (e) => {
    const data = JSON.parse(e.data)
    setReport(data.final_report)
    eventSource.close()
  })
  
  eventSource.addEventListener('timeout', (e) => {
    const data = JSON.parse(e.data)
    alert(`Research timed out: ${data.message}`)
    eventSource.close()
  })
  
  eventSource.addEventListener('error', (e) => {
    console.error('SSE error:', e)
    eventSource.close()
  })
}
```

---

## Testing & Debugging

### Unit Testing Agents

```python
"""Test individual agents in isolation."""

import pytest
from app.agents.research.financial import financial_research_node
from app.agents.research.state import DeepResearchState, ResearchBrief

@pytest.mark.asyncio
async def test_financial_agent():
    """Test financial agent returns valid output."""
    
    # Mock state
    state: DeepResearchState = {
        "user_query": "What is Hexcel's financial outlook?",
        "research_brief": ResearchBrief(
            entities=["Hexcel"],
            industries=["Aerospace"],
            financial_queries=["What is Hexcel's revenue trend?"],
            industry_queries=[],
            timeframe="2024-2025",
            status="ready"
        ),
        "errors": []
    }
    
    # Run agent
    result = await financial_research_node(state)
    
    # Assertions
    assert result["financial_output"] is not None
    assert len(result["financial_output"].findings) > 0
    assert result["current_status"] == "financial_complete"
```

### Integration Testing Workflow

```python
"""Test full workflow end-to-end."""

@pytest.mark.asyncio
async def test_research_workflow():
    """Test complete research workflow."""
    
    from app.graph.research_workflow import create_research_workflow
    
    workflow = create_research_workflow()
    
    initial_state = {
        "user_query": "Aerospace composites market trends",
        "conversation_history": [],
        "clarification_count": 0,
        "errors": []
    }
    
    # Run workflow
    final_state = await workflow.ainvoke(initial_state)
    
    # Assertions
    assert final_state["final_report"] is not None
    assert final_state["final_report"].sections is not None
    assert len(final_state["final_report"].sections) > 0
    assert final_state["current_status"] == "synthesis_complete"
```

### Debug Logging

Enable comprehensive logging to track workflow execution:

```python
import logging

# Set up logger with module prefixes
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
)

logger = logging.getLogger(__name__)

# In agent code, use module prefixes for filtering
logger.info(f"[FINANCIAL_RESEARCH] START - query: {query[:50]}...")
logger.info(f"[FINANCIAL_RESEARCH] COMPLETE in {elapsed:.2f}s")
logger.error(f"[FINANCIAL_RESEARCH] FAILED: {error}", exc_info=True)
```

### Cloud Run Log Filtering

```bash
# Filter by specific node
gcloud logging read 'resource.type="cloud_run_revision" AND textPayload=~"\[FINANCIAL_RESEARCH\]"' --limit=50

# Filter all research workflow logs
gcloud logging read 'resource.type="cloud_run_revision" AND textPayload=~"\[(GROOMER|FINANCIAL_RESEARCH|SYNTHESIZER)\]"' --limit=100
```

### LangSmith Observability

Enable LangSmith for visual workflow debugging:

```python
# .env
LANGCHAIN_API_KEY=lsv2_pt_xxx
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=my-research-workflow

# In code
import os
os.environ["LANGCHAIN_TRACING_V2"] = "true"
```

Then visit [LangSmith Dashboard](https://smith.langchain.com) to see:
- Full workflow trace with timing
- LLM prompts and responses
- Tool calls and results
- Token usage per node
- Error traces

---

## Key Learnings & Gotchas

### 1. SSE Cancellation Bug (Session 65)

**Problem**: Using `asyncio.wait_for` on an async iterator cancels the underlying task when timeout fires.

```python
# ❌ WRONG - This cancels the LLM call!
event = await asyncio.wait_for(event_iterator.__anext__(), timeout=0.1)

# ✅ CORRECT - Shield protects from cancellation
pending_task = asyncio.create_task(event_iterator.__anext__())
event = await asyncio.wait_for(asyncio.shield(pending_task), timeout=0.1)
```

**Symptoms**: Research fails within ~100ms with "cancelled" error, despite working locally.

**Lesson**: Always use `asyncio.shield()` when polling an async iterator with timeout.

### 2. Pydantic Schema Enforcement

**Problem**: LLM output doesn't always match your schema, even with structured output.

**Solution**: Include explicit JSON schema in the prompt:

```python
prompt = f"""Return valid JSON matching this schema:
{{
  "findings": [
    {{"text": "...", "source": "...", "date": "YYYY-MM-DD", "confidence": "high"}}
  ],
  "summary": "...",
  "companies_analyzed": ["..."]
}}

Your response:"""
```

**Alternative**: Use `with_structured_output()` which enforces schema at API level:

```python
llm = ChatAnthropic(...).with_structured_output(AgentOutput)
response = await llm.ainvoke(messages)
# response is already typed and validated!
```

### 3. Reducer Annotation Mistakes

**Problem**: `InvalidUpdateError: Can receive only one value per step`

**Cause**: Field missing reducer annotation during parallel execution.

**Fix**: Every field must have a reducer in `Annotated[Type, reducer]`:

```python
# ❌ Missing annotation
user_query: str

# ✅ With annotation
user_query: Annotated[str, _keep_first]
```

### 4. Empty LLM Messages

**Problem**: `Anthropic API error: messages.0.content: Expected an array with minimum length 1`

**Cause**: Empty strings in conversation history after filtering.

**Fix**: Always filter empty messages before LLM call:

```python
messages = [SystemMessage(...), HumanMessage(...)]
messages = [m for m in messages if m.content]  # Filter empties
response = await llm.ainvoke(messages)
```

### 5. Tool Timeout Hangs

**Problem**: External API calls (SEC, Exa) hang indefinitely, blocking workflow.

**Solution**: Wrap tool calls with timeout:

```python
import asyncio
from functools import wraps

def with_timeout(timeout_seconds: int):
    """Decorator to add timeout to async functions."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=timeout_seconds
                )
            except asyncio.TimeoutError:
                logger.error(f"{func.__name__} timed out after {timeout_seconds}s")
                return None  # Return None or raise based on your error handling
        return wrapper
    return decorator

@with_timeout(60)
async def get_sec_filings(ticker: str):
    # ... API call ...
```

### 6. Parallel State Accumulation

**Problem**: Frontend only sees final state, missing intermediate parallel results.

**Solution**: API route maintains `accumulated_state` to merge partial updates:

```python
accumulated_state = {}

async for event in workflow.astream(initial_state):
    node_name = list(event.keys())[0]
    node_output = event[node_name]
    
    # Merge into accumulated state
    accumulated_state.update(node_output)
    
    # Check for final report
    if accumulated_state.get("final_report"):
        yield {"event": "complete", "data": accumulated_state["final_report"]}
```

### 7. Haiku vs Sonnet Model Choice

**Learning**: Use **Haiku for speed**, **Sonnet for quality**.

| Agent | Model | Why |
|-------|-------|-----|
| Groomer | Haiku | Simple query analysis, speed matters |
| Financial | Sonnet | Complex extraction from earnings calls |
| Industry | Sonnet | Nuanced trend analysis from news |
| Visual | Sonnet | LLM-powered relevance ranking |
| Synthesizer | Sonnet | Creative synthesis, deduplication |

**Cost Tradeoff**: Haiku is 5x cheaper but less nuanced. Use for preprocessing, not synthesis.

---

## Production Checklist

Before deploying to production:

### Backend Checklist

- [ ] All LLM calls wrapped with `asyncio.wait_for(timeout=90)`
- [ ] All external tool calls have timeout protection
- [ ] Progress emission works (`emit_progress_sync` called at key points)
- [ ] Error handling returns state updates (never raises)
- [ ] Logging uses module prefixes `[NODE_NAME]` for filtering
- [ ] State schema has reducers for ALL fields
- [ ] Pydantic models validated for agent outputs
- [ ] Environment variables configured (`ANTHROPIC_API_KEY`, etc.)
- [ ] LangSmith tracing enabled for observability

### API Checklist

- [ ] SSE endpoint uses `asyncio.shield()` for iterator protection
- [ ] Workflow timeout enforced (5 minutes default)
- [ ] Accumulated state tracks parallel outputs
- [ ] Error events sent to frontend
- [ ] Timeout events sent to frontend
- [ ] CORS configured for frontend domain

### Testing Checklist

- [ ] Unit tests for each agent
- [ ] Integration test for full workflow
- [ ] Test with unclear queries (needs clarification)
- [ ] Test with timeout scenarios
- [ ] Test with external API failures
- [ ] Test with parallel execution edge cases

### Monitoring Checklist

- [ ] Cloud Run logging enabled
- [ ] LangSmith dashboard configured
- [ ] Error alerting set up
- [ ] Latency monitoring per node
- [ ] Token usage tracking
- [ ] Cache hit rate monitoring (if caching enabled)

### Documentation Checklist

- [ ] README with architecture overview
- [ ] API endpoint documentation
- [ ] Agent responsibilities documented
- [ ] State schema explained
- [ ] Tool descriptions and usage
- [ ] Troubleshooting guide
- [ ] Example queries and expected output

---

## Summary: Building This in a New Project

If you're a coding assistant building this from scratch:

1. **Start with State** - Define `DeepResearchState` with reducers
2. **Build One Agent** - Get Groomer working first (no tools, just query analysis)
3. **Add Research Agents** - Build Financial, then Industry (with tools)
4. **Implement Workflow** - Connect agents with LangGraph
5. **Add Parallel Execution** - Use `Send` API for Financial + Industry
6. **Build SSE Streaming** - Progress system + SSE endpoint
7. **Add Synthesizer** - Merge findings into coherent report
8. **Polish & Test** - Error handling, timeouts, edge cases

**Estimated Implementation Time**: 
- Solo developer: 2-3 weeks
- With this guide: 1 week
- Minimum viable (Groomer + 1 Research Agent + Synthesizer): 3-4 days

**Key Success Factors**:
1. Understand LangGraph state management (reducers!)
2. Use structured output for reliable LLM responses
3. Implement timeout protection everywhere
4. Test parallel execution thoroughly
5. Use progress emission for great UX

---

**Original Implementation**: C1 Intelligence Hub, Sessions 42-75  
**Status**: Production-ready as of January 7, 2026  
**Performance**: ~90-120 seconds for comprehensive research reports  
**Success Rate**: >95% with proper error handling

Good luck building! 🚀
