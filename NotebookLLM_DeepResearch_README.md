# Deep Research Multi-Agent Workflow - Complete Technical Overview

This document provides a comprehensive end-to-end overview of the C1 Intelligence Hub's Deep Research system, covering both backend multi-agent orchestration and frontend real-time rendering implementation.

## Table of Contents
1. [System Architecture](#system-architecture)
2. [Backend: 6-Node LangGraph Workflow](#backend-6-node-langgraph-workflow)
3. [Backend: Parallel Execution & State Management](#backend-parallel-execution--state-management)
4. [Backend: Agent Implementations](#backend-agent-implementations)
5. [Backend: Memory & Caching](#backend-memory--caching)
6. [Backend: SSE Streaming](#backend-sse-streaming)
7. [Frontend: Data Flow](#frontend-data-flow)
8. [Frontend: Component Architecture](#frontend-component-architecture)
9. [Frontend: Real-Time Progress Visualization](#frontend-real-time-progress-visualization)
10. [Frontend: Report Rendering](#frontend-report-rendering)
11. [Configuration & Observability](#configuration--observability)

---

## System Architecture

The Deep Research system is a **multi-agent parallel research pipeline** that combines financial data, industry intelligence, and visual assets into executive-ready reports. It uses LangGraph for orchestration, Server-Sent Events (SSE) for real-time streaming, and React for dynamic frontend rendering.

### High-Level Data Flow

```
┌────────────────────┐
│  User Query Input  │ "What's the outlook for aerospace composites?"
└─────────┬──────────┘
          │
          ▼
┌────────────────────┐
│  Groomer Agent     │ claude-haiku-4-5
│  (Query Analysis)  │ • Clarifies ambiguous queries
│                    │ • Generates sub-queries
│                    │ • Injects prior research context
└─────────┬──────────┘
          │
          ├──────────────────┬──────────────────┬──────────────────┐
          │                  │                  │                  │
          ▼                  ▼                  ▼                  ▼
┌───────────────┐  ┌───────────────┐  ┌───────────────┐  (Parallel)
│  Financial    │  │  Industry     │  │  Visual       │
│  Research     │  │  Research     │  │  Research     │
│               │  │               │  │               │
│ claude-sonnet │  │ claude-sonnet │  │ claude-sonnet │
│    ~30s       │  │    ~30s       │  │    ~15s       │
└───────┬───────┘  └───────┬───────┘  └───────┬───────┘
        │                  │                  │
        └──────────────────┴──────────────────┘
                           │
                           ▼
                 ┌───────────────────┐
                 │  Synthesizer      │ claude-sonnet-4-5
                 │  (Report Builder) │ • Merges findings
                 │                   │ • Enriches with logos
                 │                   │ • Places visuals
                 │                   │ • Creates executive summary
                 └─────────┬─────────┘
                           │
                           ▼
                 ┌───────────────────┐
                 │  Validator        │ claude-sonnet-4-5
                 │  (QA Gate)        │ • Citation verification
                 │                   │ • Quality checks
                 └─────────┬─────────┘
                           │
                           ▼
           ┌───────────────────────────┐
           │  BigQuery + In-Memory     │
           │  (Storage + Cache)        │
           └────────────┬──────────────┘
                        │
                        ▼
           ┌───────────────────────────┐
           │  SSE Stream → Frontend    │
           │  Real-time progress       │
           └────────────┬──────────────┘
                        │
                        ▼
           ┌───────────────────────────┐
           │  ResearchReport Component │
           │  • Executive summary      │
           │  • Section cards          │
           │  • Company logos          │
           │  • Clickable citations    │
           └───────────────────────────┘
```

---

## Backend: 6-Node LangGraph Workflow

### Architecture Diagram

```
                         ┌─────────────┐
                    ┌───►│  Financial  │───┐
                    │    │  Research   │   │
┌─────────────┐     │    └─────────────┘   │    ┌─────────────┐
│   Groomer   │─────┼───►┌─────────────┐   ├───►│ Synthesizer │
│   (Query)   │     │    │  Industry   │   │    │  (Report)   │
└─────────────┘     │    │  Research   │   │    └──────┬──────┘
                    │    └─────────────┘   │           │
                    │    ┌─────────────┐   │           ▼
                    └───►│   Visual    │───┘    ┌─────────────┐
                         │  Research   │        │  Validator  │
                         └─────────────┘        │  (QA Gate)  │
                                                └──────┬──────┘
                                                       │
                                                       ▼
                                                [Final Report]
```

**Key Features:**
- **Parallel Execution:** Financial + Industry + Visual agents run simultaneously (~60% faster)
- **State Reducers:** Custom merge functions prevent `InvalidUpdateError` during parallel node returns
- **LLM Timeout Protection:** 90-second timeout on all LLM calls to prevent hangs
- **Real-Time SSE Streaming:** Granular tool progress emitted via async queue (100ms polling)
- **Two-Tier Caching:** In-memory (1h TTL) + BigQuery (24h TTL)
- **LangSmith Observability:** Full tracing for cost/latency monitoring

---

## Backend: Parallel Execution & State Management

### The Parallel Execution Challenge

When Financial, Industry, and Visual agents run simultaneously, they all return partial state updates. Without careful state management, LangGraph raises `InvalidUpdateError: Can receive only one value per step`.

### Reducer Architecture

**File:** `backend/app/agents/research/state.py`

```python
def _keep_first(a, b):
    """Keep original value (immutable fields like user_query)."""
    if a is not None and a != "":
        return a
    return b

def _keep_last(a, b):
    """Keep latest value (mutable outputs like financial_output)."""
    return b if b is not None else a

def _merge_errors(a, b):
    """Combine error lists from parallel branches."""
    return (a or []) + (b or [])
```

### State Schema with Annotations

```python
class DeepResearchState(TypedDict):
    # Immutable fields (set once, never change)
    user_query: Annotated[str, _keep_first]
    conversation_history: Annotated[List[BaseMessage], _keep_first]
    research_brief: Annotated[Optional[ResearchBrief], _keep_first]
    
    # Mutable outputs (each agent updates its own field)
    financial_output: Annotated[Optional[FinancialAgentOutput], _keep_last]
    industry_output: Annotated[Optional[IndustryAgentOutput], _keep_last]
    visual_output: Annotated[Optional[VisualAgentOutput], _keep_last]
    final_report: Annotated[Optional[SynthesisAgentOutput], _keep_last]
    validator_output: Annotated[Optional[ValidatorOutput], _keep_last]
    
    # Merged from parallel branches
    errors: Annotated[List[Dict[str, Any]], _merge_errors]
```

**Why Annotated?** LangGraph's `Send` API for parallel execution passes full state to each branch. When branches return, their states must be merged. Without reducers, duplicate keys cause `InvalidUpdateError`.

### Workflow Routing with Send API

**File:** `backend/app/graph/research_workflow.py`

```python
def route_after_groom(state: DeepResearchState):
    """Fan out to 3 parallel agents after grooming"""
    if state["current_status"] == "grooming_complete":
        # Send creates 3 parallel branches
        return [
            Send("financial_research", state),
            Send("industry_research", state),
            Send("visual_research", state),
        ]
    # ... error handling
```

Each `Send` invocation spawns an independent branch. When all branches complete, LangGraph merges their outputs using the reducer functions.

---

## Backend: Agent Implementations

### 1. Groomer Agent
**File:** `backend/app/agents/research/groomer.py`  
**Model:** `claude-haiku-4-5`  
**Purpose:** Query interpretation and context injection

**Responsibilities:**
1. **Clarify Ambiguous Queries:** If query lacks specificity, ask clarifying questions
2. **Generate Sub-Queries:** Create targeted financial and industry research queries
3. **Entity Extraction:** Identify companies, materials, products to track
4. **Context Injection:** Fetch prior related research to avoid redundant questions

**Context Injection Flow:**
```python
# Before LLM call, groomer fetches related prior research
prior_context = await memory.find_related_research(
    query=user_query,
    companies=["Hexcel", "Toray"],
    industries=["aerospace"]
)
# Context injected into system prompt if found
system_content = f"{GROOMER_SYSTEM_PROMPT}\n\n{prior_context}"
```

**Output Schema:**
```python
class ResearchBrief(BaseModel):
    financial_queries: List[str]  # For Financial agent
    industry_queries: List[str]   # For Industry agent
    entities: List[str]            # Companies to track
    timeframe: str                 # "Q4 2025", "Last 6 months", etc.
    scope: str                     # Breadth of research
```

**LLM Timeout Protection:**
```python
LLM_TIMEOUT = 90  # seconds
try:
    response = await asyncio.wait_for(llm.ainvoke(messages), timeout=LLM_TIMEOUT)
except asyncio.TimeoutError:
    logger.error(f"Groomer LLM call timed out after {LLM_TIMEOUT}s")
    state["current_status"] = "grooming_failed"
```

---

### 2. Financial Research Agent
**File:** `backend/app/agents/research/financial.py`  
**Model:** `claude-sonnet-4-5`  
**Purpose:** Financial data and corporate intelligence

**Tools Used:**
- `query_corpus` - Pre-ingested financial articles (40+ earnings transcripts) **[always runs]**
- `get_earnings_transcript_ninja` - External earnings call API **[conditional - only if company mentioned]**
- `get_company_news` - Recent company news by ticker
- `get_press_releases` - Official announcements
- `get_analyst_ratings` - Upgrades, downgrades, price targets
- `get_sentiment_summary` - Aggregated news sentiment
- SEC filings (10-K, 10-Q, 8-K)

**Conditional External API Gating:**
External earnings API is only called when user mentions specific companies:

| Query Type | Corpus Query | SEC Filings | External Earnings API |
|------------|--------------|-------------|----------------------|
| "Wind energy trends" | ✅ | ✅ | ❌ |
| "Deep dive on Hexcel" | ✅ | ✅ | ✅ |
| "Who's growing in aerospace?" | ✅ | ✅ | ✅ (if companies found) |

This gating saves API costs on generic industry queries while still providing corpus data.

**Executive Quote Extraction (Session 76 Enhancement):**
The Financial agent now prioritizes verbatim CEO/CFO quotes from earnings calls to ground insights:

```python
# System prompt includes:
"""
When analyzing earnings transcripts:
1. Extract VERBATIM quotes from C-suite executives
2. Prioritize forward-looking statements
3. Include speaker attribution (e.g., "CEO John Smith stated:")
"""
```

**Output Schema:**
```python
class FinancialAgentOutput(BaseModel):
    findings: List[str]           # Key financial insights
    citations: List[Citation]     # Source references
    key_metrics: List[Metric]     # Revenue, growth rates, margins
    executive_quotes: List[Quote] # NEW - Verbatim quotes from transcripts
```

---

### 3. Industry Research Agent
**File:** `backend/app/agents/research/industry.py`  
**Model:** `claude-sonnet-4-5`  
**Purpose:** Market intelligence and competitive landscape

**Tools Used:**
- `news_search` / `web_search` - Exa.ai semantic search
- `query_corpus` - Pre-ingested industry articles
- `get_market_signals` - Aggregated market indicators
- `get_google_trends` - Demand signal validation
- `get_freight_rates` - Supply chain cost data

**Output Schema:**
```python
class IndustryAgentOutput(BaseModel):
    findings: List[str]
    demand_signals: List[str]     # Market trend indicators
    competitive_shifts: List[str] # New entrants, M&A, partnerships
    citations: List[Citation]
```

---

### 4. Visual Research Agent
**File:** `backend/app/agents/research/visual.py`  
**Model:** `claude-sonnet-4-5`  
**Purpose:** Surface relevant charts/graphs from pre-classified image corpus using LLM reasoning

**Why a Separate Parallel Agent?**
1. **Zero added latency** - BigQuery queries + LLM ranking (~15-20s) often finishes before Financial/Industry (~30s)
2. **Separation of concerns** - Financial thinks earnings, Industry thinks news, Visual thinks charts
3. **Future expansion** - Will add chart generation from BigQuery trend datasets

**LLM-Powered Selection:**
Unlike simple database lookups, the Visual agent uses LLM reasoning to:
1. Analyze the research brief to identify visual needs
2. Evaluate candidate visuals for relevance and quality
3. Select 3-8 most impactful visuals per report
4. Generate contextual captions tied to research findings
5. Determine optimal section placement

**Tools Used:**
- `corpus_visuals_search` - Query `article_images` BigQuery table

**Query Strategy:**
```python
# Match by companies (from research_brief.entities)
# Match by industries (from research_brief.industries)
# Match by topics (revenue, market_share, forecast, etc.)
# Filter by image_type (chart, graph, infographic)
# LLM ranks and selects from candidates
```

**BigQuery Table Schema:**
```sql
SELECT id, url, description, image_type, chart_type, 
       companies, industries, topics, relevance_score,
       article_title, article_url
FROM `article_images`
WHERE companies LIKE '%Hexcel%' 
   OR industries LIKE '%aerospace%'
   AND image_type IN ('chart', 'graph', 'infographic')
ORDER BY relevance_score DESC
LIMIT 10
```

**Output Schema:**
```python
class VisualAgentOutput(BaseModel):
    supporting_visuals: List[SupportingVisual]  # Selected visuals
    search_summary: str                         # What was searched for
    total_found: int                            # Matches before filtering

class SupportingVisual(BaseModel):
    image_url: str
    description: str
    chart_type: str          # "bar_chart", "line_graph", etc.
    source_article: str
    relevance_score: float
```

**Graceful Degradation:**
If LLM selection fails, falls back to heuristic selection based on relevance scores.

---

### 5. Synthesizer Agent
**File:** `backend/app/agents/research/synthesizer.py`  
**Model:** `claude-sonnet-4-5`  
**Purpose:** Merge findings into BRIEF, executive-ready report

**Brevity-First Design (Session 66 Refactor):**
- **12-word max headlines** - Lead with the insight
- **2-3 sections max** - Ruthlessly prioritize
- **2-3 sentences per section** - No filler paragraphs
- **3-4 key points** - One sentence each
- **2-3 key metrics** - Just `label` + `value`

**Key Features:**
1. **Deduplication:** Removes overlapping findings from Financial + Industry agents
2. **Context Integration:** Connects financial data with market trends (one sentence is enough)
3. **Executive Summary:** Punchy summary with actionable metrics
4. **Visual Placement:** Inserts relevant visuals into appropriate report sections
5. **Company Logo Enrichment (Session 75):** Extracts entities, enriches with Logo.dev URLs via `_enrich_companies_with_logos()`
6. **Clickable Citations:** Section citations include `source_url` for frontend rendering

**Anti-Patterns (LLM is instructed to avoid):**
- ❌ "It's worth noting..." / "Interestingly..." filler
- ❌ More than 3 thematic sections
- ❌ Paragraphs >4 sentences
- ❌ Tables with <3 rows
- ❌ Repeating info across sections

**Planning Scratchpad (Session 70):**
Before synthesis, the agent generates a structured planning scratchpad via `_generate_planning_scratchpad()`:

| Section | Purpose |
|---------|---------|
| **Content Inventory** | Counts findings, visuals, and demand signals available |
| **Date Analysis** | Checks publication dates, flags stale content (>6 months), respects user timeframe |
| **Entity Coverage** | Verifies requested entities appear in findings, identifies gaps |
| **Data Quality** | Assesses whether both financial and industry data are present |

Example scratchpad output:
```
=== CONTENT INVENTORY ===
[INVENTORY] Financial findings: 8
[INVENTORY] Industry findings: 12
[INVENTORY] Visuals available: 3
=== DATE ANALYSIS ===
[DATE CHECK] Financial: 8 items, oldest: 2025-10-15, newest: 2026-01-05
[DATE WARN] Industry: 2 items are >6 months old - consider as historical context only
[TIMEFRAME] User requested: Q4 2025
[TIMEFRAME] Prioritize content matching this period; older content is context only
=== ENTITY COVERAGE ===
[ENTITIES] Mentioned in findings: Hexcel, Toray, Boeing, Airbus
[COVERAGE] All requested entities covered
=== DATA QUALITY ===
[QUALITY] Both financial and industry data available
```

**Company Logo Enrichment:**
```python
def _enrich_companies_with_logos(companies: List[str]) -> List[CompanyWithLogo]:
    """
    Resolve company names to domains and logo URLs
    Uses logo.dev API via backend proxy
    """
    enriched = []
    for company_name in companies:
        domain = _resolve_domain(company_name)  # "Boeing" -> "boeing.com"
        logo_url = f"https://logo.dev/{domain}" if domain else None
        enriched.append({
            "name": company_name,
            "domain": domain,
            "logo_url": logo_url
        })
    return enriched
```

**Output Schema:**
```python
class SynthesisAgentOutput(BaseModel):
    executive_summary: ExecutiveSummary
    sections: List[ReportSection]
    companies_with_logos: List[CompanyWithLogo]  # NEW - Session 75
    overall_confidence: str  # "high", "medium", "low"

class ReportSection(BaseModel):
    section_title: str
    content: str  # Markdown formatted
    citations: List[Citation]  # NEW - includes source_url
    tables: List[Table]
    supporting_visuals: List[SupportingVisual]  # Placed by Synthesizer
```

---

### 6. Validator Agent
**File:** `backend/app/agents/research/validator.py`  
**Model:** `claude-sonnet-4-5`  
**Purpose:** Citation verification and quality gate

**Checks:**
- **Citation completeness:** Every claim has a source
- **Citation quality:** URLs, dates, proper attribution
- **Unsubstantiated claims:** Flags assertions without evidence
- **Confidence alignment:** Ensures confidence level matches data quality

**Output Schema:**
```python
class ValidatorOutput(BaseModel):
    validation_passed: bool
    citation_issues: List[str]        # Missing URLs, date mismatches
    confidence_adjustments: List[str] # Recommended confidence changes
    warnings: List[str]
```

---

## Backend: Memory & Caching

### Research Memory Service
**File:** `backend/app/agents/research/memory.py`  
**Purpose:** Context integration and report persistence

### Two-Tier Caching Strategy

**Tier 1: In-Memory Cache**
- **TTL:** 1 hour
- **Cache key:** SHA256 of normalized (lowercase, trimmed) query
- **Fastest retrieval** for recent/repeated queries
- **Endpoints:** `GET /cache/stats`, `DELETE /cache/clear`

**Tier 2: BigQuery Persistence**
- **TTL:** 24 hours (configurable)
- **Table:** `deep_research_reports`
- **Survives** server restarts
- **Enables:** Report history and search
- **Endpoints:** `GET /reports`, `GET /reports/{id}`, `GET /reports/search/related`

### BigQuery Schema: `deep_research_reports`

| Column | Type | Description |
|--------|------|-------------|
| `id` | STRING | UUID |
| `query` | STRING | Original user query |
| `query_hash` | STRING | SHA256 for cache lookups |
| `report_data` | JSON | Full report JSON |
| `companies` | ARRAY<STRING> | Extracted company names |
| `industries` | ARRAY<STRING> | Industry tags |
| `topics` | ARRAY<STRING> | Topic tags |
| `overall_confidence` | STRING | "high", "medium", "low" |
| `created_at` | TIMESTAMP | Report generation time |
| `ttl_expires_at` | TIMESTAMP | Cache expiration (24h default) |

### Memory Service API

```python
from app.agents.research.memory import get_research_memory

memory = await get_research_memory()

# Check for cached report
cached = await memory.get_cached_report(query)

# Find related past research for context
related = await memory.find_related_research(
    query=query,
    companies=["Hexcel", "Toray"],
    industries=["aerospace"]
)

# Store completed report
await memory.store_report(report_id, query, state)
```

### Saved Reports API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/research/reports` | GET | List saved reports (paginated) |
| `/api/research/reports/{id}` | GET | Get full report by ID |
| `/api/research/reports/search/related` | GET | Find related past research |

---

## Backend: SSE Streaming

### Real-Time Progress Emissions
**File:** `backend/app/agents/research/progress.py`

Agents emit real-time progress via async queue:

```python
from app.agents.research.progress import emit_progress_sync, ToolProgress

# In agent code
emit_progress_sync(ToolProgress(
    tool_name="sec_filings",
    message="Fetching SEC 10-K for Hexcel",
    ticker="HXL",
    status="running"
))
```

### SSE Event Loop (Session 42 Fix)
**File:** `backend/app/api/routes/deep_research.py`

**Critical Bug Fix:**
- Progress events are collected via `ProgressCollector` async queue
- API route polls the queue every **100ms** using `asyncio.wait_for` timeout
- Events stream immediately instead of waiting for LangGraph lifecycle events
- Parallel agents (Financial + Industry) emit progress without blocking each other

**WRONG - Cancels workflow:**
```python
# This cancels the LLM task when timeout fires!
event = await asyncio.wait_for(event_iterator.__anext__(), timeout=0.1)
```

**CORRECT - Protects from cancellation:**
```python
if pending_task is None:
    pending_task = asyncio.create_task(event_iterator.__anext__())
event = await asyncio.wait_for(asyncio.shield(pending_task), timeout=0.5)
```

### SSE Event Types

| Event Type | Content | Frontend Action |
|------------|---------|-----------------|
| `status` | `{message: string}` | Update status text |
| `cache_hit` | `{query_hash, message}` | Show "Loading cached report" |
| `node_start` | `{node, description, parallel_with?}` | Mark node as running, show icon animation |
| `node_complete` | `{node}` | Mark node as completed, show checkmark |
| `tool_progress` | `{tool, message, ticker?, status}` | Add to live activity feed |
| `clarification` | `{question, options, default_if_skipped}` | Show clarification modal |
| `report` | `{executive_summary, sections, ...}` | Render final report, stop loading |
| `validation` | `{validation_passed, issues, warnings}` | Show validation badge |
| `timeout` | `{elapsed_seconds, completed_nodes, active_nodes}` | Show timeout UI with retry option |
| `error` | `{message}` | Show error state, mark running nodes as errored |

### State Accumulation Pattern

During parallel execution, each node returns partial state. The API route maintains `accumulated_state` to merge outputs from all nodes:

```python
accumulated_state = {}

async for event in workflow.astream_events(initial_state):
    if event["event"] == "on_chain_end":
        node_name = event["name"]
        partial_state = event["data"]["output"]
        
        # Merge partial state into accumulated state
        for key, value in partial_state.items():
            if value is not None:
                accumulated_state[key] = value

# Ensures final_report is captured even when parallel branches complete asynchronously
```

---

## Frontend: Data Flow

### 1. Initial Request
**Component:** `ResearchCanvas.tsx` (Research tab)  
**Hook:** `useDeepResearch.ts`

```typescript
const { startDeepResearch, report, nodeStatuses, toolProgress, isResearching } = useDeepResearch()

// User submits query
await startDeepResearch("What's the outlook for aerospace composites?")

// Hook internally POSTs to:
const response = await fetch('/api/research/deep/run', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, history }),
})
```

### 2. SSE Stream Consumption

```typescript
const reader = response.body?.getReader()
const decoder = new TextDecoder()
let buffer = ''

while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n\n')
    buffer = lines.pop() || ''

    for (const line of lines) {
        if (line.startsWith('data: ')) {
            const dataStr = line.replace('data: ', '').trim()
            if (dataStr === '[DONE]') break

            const data = JSON.parse(dataStr)
            handleSSEEvent(data, setState)  // Update React state
        }
    }
}
```

### 3. Type Definitions
**File:** `frontend/src/types/index.ts`

```typescript
interface DeepResearchReport {
    query: string
    executive_summary: ExecutiveSummary
    sections: ReportSection[]
    field_sales?: FieldSales          // Optional - nullable
    companies_with_logos: CompanyWithLogo[]
    overall_confidence: string
}

interface ExecutiveSummary {
    headline: string
    key_points: string[]
    key_metrics: Metric[]
}

interface ReportSection {
    section_title: string
    content: string  // Markdown
    citations: Citation[]
    tables: Table[]
    supporting_visuals: SupportingVisual[]
}

interface Citation {
    source_type?: string
    source_title: string
    source_url?: string | null  // NEW - clickable link
    source_date?: string | null
}

interface CompanyWithLogo {
    name: string
    domain?: string
    logo_url?: string
}

interface SupportingVisual {
    image_url: string
    description: string
    chart_type: string
    source_article: string
    relevance_score: number
}

type DeepResearchNode = 
    | 'groom' 
    | 'financial_research' 
    | 'industry_research' 
    | 'visual_research'
    | 'synthesize' 
    | 'validate'

interface NodeStatus {
    node: DeepResearchNode
    status: 'pending' | 'running' | 'completed' | 'error' | 'timeout'
    description: string
    startTime?: Date
    endTime?: Date
    parallel_with?: string[]  // For indicating parallel execution
}

interface ToolProgressEvent {
    tool: string        // e.g., "get_earnings_transcript_ninja"
    message: string     // e.g., "Fetching SEC 10-K for Hexcel"
    ticker?: string     // e.g., "HXL"
    status: 'running' | 'completed' | 'error'
}
```

### 4. Rendering Pipeline

```
useDeepResearch (hook)
    ├── Maintains state: nodeStatuses, toolProgress, report, isResearching
    ├── Consumes SSE stream
    └── Updates React state on each event

ResearchCanvas (main container)
    ├── {isResearching && <ResearchProgress />}  // Shows during workflow
    ├── {report && <ResearchReport />}           // Shows when complete
    └── {error && <ErrorState />}

ResearchProgress
    ├── Node pipeline visualization (6 circles with connectors)
    ├── Parallel execution indicator (bracket between Financial/Industry)
    └── Live activity feed (last 5 tool progress events)

ResearchReport
    ├── Executive Summary card
    │   ├── Headline
    │   ├── Key metrics (3 stat boxes)
    │   ├── Key points (bullet list)
    │   └── Company logos with initials fallback
    ├── Section cards (2-3 sections)
    │   ├── Section title + icon
    │   ├── Markdown content (ReactMarkdown)
    │   ├── Tables (if present)
    │   ├── Supporting visuals (if present)
    │   └── Clickable citation pills (grouped by domain)
    └── Field Sales Implications (if present)
        ├── Offensive angles grid
        ├── Defensive watch-outs grid
        └── Questions to explore
```

---

## Frontend: Component Architecture

### ResearchProgress Component
**File:** `frontend/src/components/research/ResearchProgress.tsx`  
**Purpose:** Real-time visualization of workflow progress

**Props:**
- `nodeStatuses`: NodeStatus[] - Current state of all 6 nodes
- `toolProgress`: ToolProgressEvent[] - Last 20 tool executions
- `activeNode`: DeepResearchNode | null - Currently running node
- `isCacheHit`: boolean - Whether report was loaded from cache

**Visual Structure:**
```
┌─────────────────────────────────────────────────────────┐
│ ⚡ Deep Research in Progress        ⚡ Parallel execution │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Query      Financial   Industry   Visual   Synthesis  │
│  Analysis   Research    Research   Research            │
│     ↓          ↓           ↓          ↓         ↓      │
│    [✓]       [↻]        [↻]        [✓]       [ ]      │
│              └───────────┘                              │
│            (Parallel bracket)                           │
│                                                         │
├─────────────────────────────────────────────────────────┤
│ ● Live Activity                                         │
│ • Earnings Transcript (HXL) Fetching Q4 2025 call      │
│ • Corpus Search Analyzing aerospace articles           │
│ • SEC Filings Retrieved 10-K for Hexcel Corp          │
└─────────────────────────────────────────────────────────┘
```

**Node Status Indicators:**
- **Pending:** Gray circle with icon
- **Running:** Emerald circle with spinner, pulsing ring
- **Completed:** Green circle with checkmark
- **Error:** Red circle with alert icon
- **Timeout:** Orange circle (special state)

**Parallel Execution Indicator:**
When Financial and Industry are both `status === 'running'`, a blue bracket appears above them with label "⚡ Parallel execution"

**Live Activity Feed:**
- Shows last 5 tool progress events
- Most recent at top (reverse order)
- Each event shows: colored dot (running/completed/error), tool label, ticker (if applicable), message
- Truncates long messages with ellipsis
- Opacity gradient (latest 100%, older 60%)

---

### ResearchReport Component
**File:** `frontend/src/components/research/ResearchReport.tsx`  
**Purpose:** Render final research report

**Props:**
- `report`: DeepResearchReport

**Section Breakdown:**

#### 1. Executive Summary Card
```tsx
<section className="bg-white rounded-2xl border border-slate-200 shadow-sm">
    <div className="bg-slate-900 px-6 py-4">
        <LayoutDashboard /> Executive Summary
        <button onClick={handleSaveToMemory}>Save to Memory</button>
    </div>
    <div className="p-6">
        <h1>{executive_summary.headline}</h1>
        {/* Key Metrics - 3 stat boxes */}
        <div className="grid grid-cols-3 gap-4">
            {executive_summary.key_metrics.map(metric => (
                <div className="bg-slate-50 rounded-xl p-4 text-center">
                    <p className="text-xs uppercase">{metric.label}</p>
                    <p className="text-xl font-bold">{metric.value}</p>
                </div>
            ))}
        </div>
        {/* Key Points - bullet list */}
        <div className="space-y-2">
            {executive_summary.key_points.map(point => (
                <div className="flex gap-3">
                    <div className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                    <p>{point}</p>
                </div>
            ))}
        </div>
        {/* Company Logos */}
        {companies_with_logos.map(company => (
            <div className="inline-flex items-center gap-2">
                <CompanyLogo company={company} />
                <span>{company.name}</span>
            </div>
        ))}
    </div>
</section>
```

#### 2. Section Cards
```tsx
{sections.map(section => (
    <section className="bg-white rounded-2xl border">
        <div className="bg-slate-50 px-6 py-3 border-b">
            <FileText /> {section.section_title}
        </div>
        <div className="p-6">
            {/* Markdown Content */}
            <ReactMarkdown>{section.content}</ReactMarkdown>
            
            {/* Tables (if present) */}
            {section.tables.map(table => (
                <table>
                    <thead>
                        <tr>{table.columns.map(col => <th>{col}</th>)}</tr>
                    </thead>
                    <tbody>
                        {table.rows.map(row => (
                            <tr>{table.columns.map(col => <td>{row[col]}</td>)}</tr>
                        ))}
                    </tbody>
                </table>
            ))}
            
            {/* Supporting Visuals (if present) */}
            {section.supporting_visuals.map(visual => (
                <div className="mt-4">
                    <img src={visual.image_url} alt={visual.description} />
                    <p className="text-xs text-slate-500">{visual.description}</p>
                    <span className="text-xs">Source: {visual.source_article}</span>
                </div>
            ))}
            
            {/* Clickable Citations */}
            <CitationList citations={section.citations} />
        </div>
    </section>
))}
```

#### 3. CitationList Component
**Purpose:** Render clickable citation pills grouped by domain

```tsx
function CitationList({ citations }: { citations: Citation[] }) {
    const linkedCitations = citations.filter(c => c.source_url)
    if (linkedCitations.length === 0) return null

    return (
        <div className="mt-4 pt-4 border-t border-slate-100">
            <p className="text-xs font-medium text-slate-500">
                <ExternalLink size={12} /> Sources
            </p>
            <div className="flex flex-wrap gap-2">
                {linkedCitations.map((citation, idx) => {
                    const domain = extractDomain(citation.source_url!)
                    return (
                        <a
                            href={citation.source_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-slate-50 hover:bg-slate-100 border rounded-lg text-xs"
                            title={citation.source_title}
                        >
                            <span className="font-medium">{domain}</span>
                            <ExternalLink size={10} />
                        </a>
                    )
                })}
            </div>
        </div>
    )
}
```

**Example Render:**
```
SOURCES
[reuters.com 🔗] [wsj.com 🔗] [sec.gov 🔗]
```

#### 4. CompanyLogo Component
**Purpose:** Render company logo with fallback to initials

```tsx
function CompanyLogo({ company }: { company: CompanyWithLogo }) {
    const [imageError, setImageError] = useState(false)
    
    // Use logo.dev API via our backend proxy
    const logoUrl = company.domain
        ? `${API_BASE}/api/pipeline/logo/${company.domain}`
        : null

    if (!logoUrl || imageError) {
        // Fallback to initials
        const initials = company.name
            .split(' ')
            .map(w => w[0])
            .slice(0, 2)
            .join('')
            .toUpperCase()

        return (
            <div className="w-6 h-6 rounded bg-slate-200 text-[9px] font-bold">
                {initials}
            </div>
        )
    }

    return <img src={logoUrl} onError={() => setImageError(true)} />
}
```

**Example:**
- Boeing → `[BA]` or `[boeing logo image]`
- Hexcel Corporation → `[HE]` or `[hexcel logo image]`

#### 5. Field Sales Implications (Optional)
**Note:** This section only renders if `field_sales` exists AND has non-empty arrays (Session 76 null safety)

```tsx
{field_sales && (
    field_sales.offensive_angles?.length > 0 || 
    field_sales.defensive_angles?.length > 0
) && (
    <section className="bg-emerald-50 rounded-2xl border border-emerald-100">
        <div className="bg-emerald-600 px-6 py-4">
            <Target /> Field Sales Implications
        </div>
        <div className="p-6 grid grid-cols-2 gap-8">
            {/* Offensive Angles */}
            <div>
                <h4><TrendingUp /> Offensive Angles</h4>
                {field_sales.offensive_angles.map(angle => (
                    <div className="bg-white rounded-xl p-4 border">
                        <p className="font-semibold">{angle.angle}</p>
                        <p className="text-xs italic">Target: {angle.target_segment}</p>
                    </div>
                ))}
            </div>
            {/* Defensive Watch-outs */}
            <div>
                <h4><ShieldCheck /> Defensive Watch-outs</h4>
                {field_sales.defensive_angles.map(angle => (
                    <div className="bg-white rounded-xl p-4 border">
                        <p className="font-semibold">{angle.risk}</p>
                        <p className="text-xs italic">Mitigation: {angle.mitigation}</p>
                    </div>
                ))}
            </div>
        </div>
        {/* Questions to Explore */}
        {field_sales.questions_to_explore?.length > 0 && (
            <div className="bg-emerald-100/50 p-6 border-t">
                <h4><HelpCircle /> Questions to Explore</h4>
                <div className="grid grid-cols-2 gap-3">
                    {field_sales.questions_to_explore.map(q => (
                        <div className="flex gap-2">
                            <ChevronRight size={14} className="text-emerald-500" />
                            <p className="text-sm">{q}</p>
                        </div>
                    ))}
                </div>
            </div>
        )}
    </section>
)}
```

---

## Frontend: Real-Time Progress Visualization

### Node Status State Management

**Hook:** `useDeepResearch.ts`

```typescript
const initialState: DeepResearchState = {
    nodeStatuses: [
        { node: 'groom', status: 'pending', description: 'Analyzing your query...' },
        { node: 'financial_research', status: 'pending', description: 'Researching financial data' },
        { node: 'industry_research', status: 'pending', description: 'Researching industry intelligence' },
        { node: 'visual_research', status: 'pending', description: 'Searching for relevant visuals' },
        { node: 'synthesize', status: 'pending', description: 'Synthesizing findings into report' },
        { node: 'validate', status: 'pending', description: 'Verifying citations and sources' },
    ],
    toolProgress: [],
    activeNode: null,
}
```

### SSE Event Handlers

#### `node_start` Event
```typescript
case 'node_start':
    setState(prev => ({
        ...prev,
        activeNode: data.content.node,
        status: data.content.description,
        nodeStatuses: prev.nodeStatuses.map(ns =>
            ns.node === data.content.node
                ? { 
                    ...ns, 
                    status: 'running', 
                    startTime: new Date(),
                    parallel_with: data.content.parallel_with,  // NEW - indicates parallel execution
                }
                : ns
        ),
    }))
    break
```

**Backend emits:**
```python
# For financial_research node
yield {
    "type": "node_start",
    "content": {
        "node": "financial_research",
        "description": "Researching financial data",
        "parallel_with": ["industry_research", "visual_research"]  # Indicates parallel execution
    }
}
```

#### `node_complete` Event
```typescript
case 'node_complete':
    setState(prev => ({
        ...prev,
        nodeStatuses: prev.nodeStatuses.map(ns =>
            ns.node === data.content.node
                ? { ...ns, status: 'completed', endTime: new Date() }
                : ns
        ),
    }))
    break
```

#### `tool_progress` Event
```typescript
case 'tool_progress':
    setState(prev => ({
        ...prev,
        toolProgress: [
            ...prev.toolProgress.slice(-19),  // Keep last 20 events
            {
                tool: data.content.tool,
                message: data.content.message,
                ticker: data.content.ticker,
                status: data.content.status || 'running',
            },
        ],
    }))
    break
```

**Backend emits:**
```python
emit_progress_sync(ToolProgress(
    tool_name="get_earnings_transcript_ninja",
    message="Fetching Q4 2025 earnings call",
    ticker="HXL",
    status="running"
))
```

### Parallel Execution Detection

**Frontend Logic:**
```typescript
const parallelNodes = useMemo(() => {
    const financial = nodeStatuses.find(n => n.node === 'financial_research')
    const industry = nodeStatuses.find(n => n.node === 'industry_research')
    return financial?.status === 'running' && industry?.status === 'running'
}, [nodeStatuses])

// Render parallel bracket if true
{parallelNodes && (
    <span className="ml-auto text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full">
        ⚡ Parallel execution
    </span>
)}
```

### Tool Name Formatting

```typescript
function formatToolName(name: string): string {
    const toolLabels: Record<string, string> = {
        'get_earnings_transcript_ninja': 'Earnings Transcript',
        'query_corpus': 'Corpus Search',
        'get_company_news': 'Company News',
        'get_press_releases': 'Press Releases',
        'get_analyst_ratings': 'Analyst Ratings',
        'get_sentiment_summary': 'Sentiment Analysis',
        'sec_filings': 'SEC Filings',
        'news_search': 'News Search',
        'web_search': 'Web Search',
        'get_market_signals': 'Market Signals',
        'get_google_trends': 'Google Trends',
        'get_freight_rates': 'Freight Rates',
        // ... etc
    }
    return toolLabels[name] || name.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
}
```

**Example:**
- Input: `get_earnings_transcript_ninja`
- Output: `Earnings Transcript`

---

## Configuration & Observability

### Backend Configuration
**File:** `backend/app/config/settings.py`

```python
# LLM Models
deep_research_groomer_model = "claude-haiku-4-5"
deep_research_financial_model = "claude-sonnet-4-5"
deep_research_industry_model = "claude-sonnet-4-5"
deep_research_synthesizer_model = "claude-sonnet-4-5"
deep_research_validator_model = "claude-sonnet-4-5"

# Timeout Settings
deep_research_workflow_timeout = 300  # 5 minutes total workflow timeout
deep_research_tool_timeout = 60       # 60 seconds per external tool call
deep_research_llm_timeout = 90        # 90 seconds for LLM extraction calls

# Cache Settings
deep_research_memory_cache_ttl = 3600      # 1 hour in-memory cache
deep_research_bigquery_cache_ttl = 86400   # 24 hours BigQuery cache
```

### LangSmith Observability

**Environment Variables:**
```bash
LANGCHAIN_API_KEY=lsv2_pt_xxx
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=c1-intelligence-hub-prod
```

**What's Traced:**
- **Run name:** `DeepResearch: {query preview}`
- **Tags:** `deep_research`, `production`
- **Metadata:** `run_id`, `query_hash`, `timestamp`, `query_length`

**Key Metrics to Monitor:**

| Metric | What to Watch |
|--------|---------------|
| **Latency** | Financial/Industry nodes (parallel) should complete in ~30s each |
| **Token Usage** | ~10-15k tokens per research run (6 LLM calls) |
| **Error Rate** | Failed tool calls, citation validation issues |
| **Cache Hits** | High hit rate = good query normalization |

**Observability Endpoint:**
```bash
GET /api/deep-research/observability/status
# Returns LangSmith config status, active traces, recent errors
```

### Debug Logging

**Log Prefixes for Cloud Run Filtering:**

| Prefix | Node | What's Logged |
|--------|------|---------------|
| `[GROOMER]` | Query Grooming | START/COMPLETE timing, query count, financial/industry queries generated |
| `[FINANCIAL_RESEARCH]` | Financial Agent | START/COMPLETE timing, finding count, state keys |
| `[INDUSTRY_RESEARCH]` | Industry Agent | START/COMPLETE timing, finding count, state keys |
| `[VISUAL_RESEARCH]` | Visual Agent | START timing, state keys, visual selection |
| `[SYNTHESIZER]` | Synthesizer | START/COMPLETE timing, input analysis, section count |
| `[ROUTE_AFTER_GROOM]` | Workflow Router | Routing decision, state keys, current_status |
| `[DEEP_RESEARCH]` | API Route | Initial state, workflow start, SSE streaming |

**Example Log Output:**
```
[GROOMER] START - query: What's the outlook for aerospace compos...
[GROOMER] State keys: ['user_query', 'conversation_history', 'research_brief', ...]
[GROOMER] COMPLETE in 12.3s - status: QueryStatus.READY
[GROOMER] Financial queries: 4, Industry queries: 5
[ROUTE_AFTER_GROOM] State keys: ['user_query', 'research_brief', ...]
[ROUTE_AFTER_GROOM] current_status: grooming_complete
[FINANCIAL_RESEARCH] START - query: What's the outlook for aerospace compos...
[INDUSTRY_RESEARCH] START - query: What's the outlook for aerospace compos...
[VISUAL_RESEARCH] START - query: What's the outlook for aerospace compos...
[FINANCIAL_RESEARCH] COMPLETE in 28.4s - 8 findings
[VISUAL_RESEARCH] COMPLETE in 16.2s - 3 visuals selected
[INDUSTRY_RESEARCH] COMPLETE in 31.1s - 12 findings
[SYNTHESIZER] START - merging 28 total findings
[SYNTHESIZER] COMPLETE in 18.7s - 3 sections generated
[VALIDATOR] START - checking 14 citations
[VALIDATOR] COMPLETE in 7.2s - validation_passed: true
```

**Cloud Run Log Filtering:**
```bash
# Filter by node in Cloud Run Logs
gcloud logging read 'resource.type="cloud_run_revision" AND textPayload=~"\[GROOMER\]"' --limit=50

# Filter all research workflow logs
gcloud logging read 'resource.type="cloud_run_revision" AND textPayload=~"\[(GROOMER|FINANCIAL_RESEARCH|INDUSTRY_RESEARCH|SYNTHESIZER)\]"' --limit=100
```

---

## Performance Characteristics

### Backend Timing
- **Groomer:** ~10-15 seconds (query analysis)
- **Financial Research:** ~25-35 seconds (parallel)
- **Industry Research:** ~25-35 seconds (parallel)
- **Visual Research:** ~15-20 seconds (parallel, completes first)
- **Synthesizer:** ~15-20 seconds (merging findings)
- **Validator:** ~5-10 seconds (citation checks)
- **Total Pipeline:** ~60-90 seconds end-to-end (with parallel execution)

**Without Parallel Execution:** ~120-150 seconds (60% slower)

### Frontend Rendering
- **Initial SSE Connection:** ~100-200ms
- **First `node_start` Event:** ~10-15 seconds (groomer completion)
- **Tool Progress Event Rate:** ~2-5 events/second during active research
- **Report Render:** ~50-100ms (React component)
- **Logo Resolution:** ~100-300ms per logo (cached by browser after first load)

### Data Sizes
- **Research Brief JSON:** ~1-2 KB
- **Agent Output JSON:** ~5-10 KB each
- **Final Report JSON:** ~20-40 KB
- **SSE Stream Total:** ~50-100 KB (all events combined)

---

## Troubleshooting

### Common Backend Issues

**`InvalidUpdateError: Can receive only one value per step`**
- **Cause:** State field missing reducer annotation for parallel execution
- **Fix:** Add `Annotated[Type, reducer_function]` to field in `state.py`

**Pydantic validation errors (missing fields)**
- **Cause:** LLM output doesn't match schema
- **Fix:** Add explicit JSON schema to the extraction prompt (see `financial.py`, `synthesizer.py`)

**Anthropic API error: empty message content**
- **Cause:** Empty messages in conversation history
- **Fix:** Filter messages before LLM call (see `groomer.py`)

**"Query analysis was cancelled" immediately**
- **Cause:** SSE event loop cancellation bug (Session 65)
- **Root Cause:** `asyncio.wait_for(event_iterator.__anext__(), timeout=0.1)` cancels the LLM task when timeout fires
- **Fix:** Always use `asyncio.shield()` when polling an async iterator (see `deep_research.py` lines 355-420)

**Research hangs/times out**
- **Cause:** External API (SEC, StockNews, Exa) is slow or unresponsive
- **Symptoms:** Frontend shows "Research timed out" after 5 minutes
- **Fix:** Check `timeoutInfo.active_nodes` to identify stuck stage, adjust `deep_research_workflow_timeout` if needed

### Common Frontend Issues

**Node progress not updating**
- **Cause:** SSE stream not being consumed properly
- **Fix:** Check browser Network tab for SSE connection, verify `data:` prefix in stream

**Logos not displaying**
- **Cause:** Backend proxy not resolving domains correctly
- **Fix:** Verify `LOGO_DEV_TOKEN` secret is mounted, check `companies_with_logos` array in API response

**Citations not clickable**
- **Cause:** `source_url` field missing in `Citation` objects
- **Fix:** Verify Synthesizer is populating `source_url` in citation schema

**Parallel execution indicator not showing**
- **Cause:** Both Financial and Industry nodes not marked as `running` simultaneously
- **Fix:** Check `node_start` SSE events have `parallel_with` field

**Report renders with missing field_sales section**
- **Cause:** Expected - field_sales is optional (Session 76 null safety)
- **Fix:** Verify `field_sales` exists and has non-empty arrays before rendering

---

## Key Implementation Files

### Backend
| File | Purpose |
|------|---------|
| `app/graph/research_workflow.py` | LangGraph workflow definition with Send API for parallel fan-out |
| `app/agents/research/groomer.py` | Query grooming node with context injection |
| `app/agents/research/financial.py` | Financial research node with conditional earnings API |
| `app/agents/research/industry.py` | Industry research node |
| `app/agents/research/visual.py` | Visual research node with LLM-powered selection |
| `app/agents/research/synthesizer.py` | Report synthesis node with logo enrichment |
| `app/agents/research/validator.py` | Citation verification node |
| `app/agents/research/state.py` | Pydantic schemas and TypedDict state with reducer annotations |
| `app/agents/research/progress.py` | SSE event emission infrastructure |
| `app/agents/research/memory.py` | Research memory service with two-tier caching |
| `app/api/routes/deep_research.py` | SSE streaming endpoint with asyncio.shield protection |

### Frontend
| File | Purpose |
|------|---------|
| `hooks/useDeepResearch.ts` | SSE stream consumption and state management |
| `components/research/ResearchCanvas.tsx` | Main research tab container |
| `components/research/ResearchProgress.tsx` | Real-time progress visualization |
| `components/research/ResearchReport.tsx` | Final report renderer |
| `types/index.ts` | TypeScript type definitions |

---

## Roadmap

### Phase 7 (Planned)
- **Chart Generation** - Generate visuals from BigQuery trend data
  - `generate_trend_chart` tool (matplotlib/plotly)
  - `generate_comparison_table` tool
- Frontend: Tool Health dashboard (API status, latency, success rates)
- Frontend: Saved Reports history view
- Semantic search on past reports (query embeddings)

---

## Glossary

- **Groomer:** Query interpretation agent that generates sub-queries and injects prior research context
- **Parallel Execution:** Simultaneous execution of Financial, Industry, and Visual agents using LangGraph's Send API
- **State Reducer:** Function that merges partial state updates from parallel agent branches
- **SSE (Server-Sent Events):** One-way streaming protocol for real-time progress updates
- **Tool Progress:** Granular execution events emitted by agents during tool calls
- **Node Status:** Current state of workflow node (pending, running, completed, error, timeout)
- **Research Memory:** Two-tier caching system (in-memory + BigQuery) for report persistence
- **Context Injection:** Groomer receives prior related research to avoid redundant clarifying questions
- **Logo Enrichment:** Synthesizer resolves company names to domains and fetches logo URLs via logo.dev
- **Clickable Citations:** Section citations include source_url for frontend rendering as domain pills
- **Planning Scratchpad:** Synthesizer's pre-generation analysis of content inventory, date ranges, entity coverage
- **Conditional API Gating:** Financial agent only calls external earnings API when companies are mentioned
- **Executive Quote Extraction:** Financial agent prioritizes verbatim CEO/CFO quotes from earnings calls
- **Visual Research:** LLM-powered agent that selects relevant charts/graphs from pre-classified image corpus
- **Brevity-First Design:** Synthesizer's strict constraints (12-word headlines, 2-3 sections, 2-3 sentences max)
