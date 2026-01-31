# Deep Research Workflow

Multi-agent research pipeline for comprehensive industry intelligence reports.

## Overview

Deep Research is a **6-node** LangGraph workflow that orchestrates specialized agents to produce executive-ready research reports. It combines financial data, industry news, and visual assets into a single deliverable.

**Status: ✅ PRODUCTION READY** (January 16, 2026)

**Recent Changes (Session 105):**
- **Visual URL Hydration** - `_hydrate_visual_blocks()` injects `image_url` into blocks referencing `visual_id`
- **Citation Display Fix** - All citations shown (URL-linked and non-linked)
- **Quote Block Prompt** - Explicit required fields (`text`, `speaker`, `context`)

**Previous Changes (Session 76):**
- **Removed Category Agent** (sales intelligence) - Synthesizer now has full creative license
- **Fixed Visual Agent bug** - `visual.visuals` → `visual.supporting_visuals`
- **Enhanced Executive Quote Extraction** - Financial agent prioritizes verbatim CEO/CFO quotes
- **Frontend Compatibility** - Added null safety checks for optional `field_sales` field in `ResearchReport.tsx`

**Key Features:**
- Parallel execution of Financial + Industry + Visual agents (~60% faster)
- **Executive Quote Extraction** - Verbatim quotes from earnings calls ground insights
- Real-time SSE streaming with granular tool progress
- In-memory query caching (1-hour TTL)
- LangSmith observability for cost/latency tracking
- Pydantic schema validation at every node
- Comprehensive debug logging with `[NODE_NAME]` prefixes
- LLM timeout protection (90s per call) to prevent hangs

## File Organization

**Agent Nodes**: This folder (`app/agents/research/`) contains the individual agent implementations.

**LangGraph Workflow**: The LangGraph workflow definition lives in a separate folder:
- `app/graph/research_workflow.py` - Workflow graph with nodes, edges, and routing logic
- `app/graph/state.py` - Shared state definitions (if separate from agent state)
- `app/graph/workflow.py` - Any additional workflow utilities

## Pipeline Architecture

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

**Note:** Category Agent (sales intelligence with territory insights, product recommendations, sales plays) has been **removed** from the workflow. The Synthesizer now has full creative license to structure the report.

**Parallel Execution**: Financial, Industry, and Visual agents run simultaneously using LangGraph's `Send` API with custom reducer functions for state merging. Visual agent completes fastest (~10-15s) due to single BigQuery call vs multi-tool research agents (~30s).

### Reducer Architecture

Parallel execution requires careful state management. When multiple nodes return simultaneously, their outputs must be merged:

```python
# state.py - Reducer functions for parallel state merge
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

**Field Annotations:**
- `user_query`, `conversation_history`, `research_brief` → `_keep_first` (set early, never change)
- `financial_output`, `industry_output`, `final_report`, etc. → `_keep_last` (each node updates its field)
- `errors` → `_merge_errors` (combine from parallel branches)

## Nodes

### 1. Groomer (`groomer.py`)
**Purpose**: Query interpretation and sub-query generation

- Clarifies ambiguous user queries
- Generates targeted sub-queries for Financial and Industry agents
- Identifies entities to track (companies, products, materials)
- Sets research timeframe and scope
- **Context Injection**: Receives prior related research to skip redundant questions

**Context Injection Flow:**
```python
# Before LLM call, groomer fetches related prior research
prior_context = await _get_prior_research_context(user_query)
# Context injected into system prompt if found
system_content = f"{GROOMER_SYSTEM_PROMPT}\n\n{prior_context}"
```

**Model**: `claude-haiku-4-5` (configurable via `settings.deep_research_groomer_model`)

### 2. Financial Research (`financial.py`)
**Purpose**: Financial data and corporate intelligence

**Conditional External API Gating:**
External earnings API is only called when user mentions specific companies:

| Query Type | Corpus Query | SEC Filings | External Earnings API |
|------------|--------------|-------------|----------------------|
| "Wind energy trends" | ✅ | ✅ | ❌ |
| "Deep dive on Hexcel" | ✅ | ✅ | ✅ |
| "Who's growing in aerospace?" | ✅ | ✅ | ✅ (if companies found) |

This gating saves API costs on generic industry queries while still providing corpus data (40+ pre-ingested transcripts).

**Tools Used**:
- `get_earnings_transcript_ninja` - Earnings call transcripts (**conditional - only if company mentioned**)
- `query_corpus` - Pre-ingested financial articles (**always runs**)
- `get_company_news` - Recent company news by ticker
- `get_press_releases` - Official announcements
- `get_analyst_ratings` - Upgrades, downgrades, price targets
- `get_sentiment_summary` - Aggregated news sentiment
- SEC filings (10-K, 10-Q, 8-K)

**Output**: `FinancialAgentOutput` with findings, citations, metrics

### 3. Industry Research (`industry.py`)
**Purpose**: Market intelligence and competitive landscape

**Tools Used**:
- `news_search` / `web_search` - Exa.ai semantic search
- `query_corpus` - Pre-ingested industry articles
- `get_market_signals` - Aggregated market indicators
- `get_google_trends` - Demand signal validation
- `get_freight_rates` - Supply chain cost data

**Output**: `IndustryAgentOutput` with findings, demand signals, competitive shifts

### 4. Visual Research (`visual.py`)
**Purpose**: Surface relevant charts, graphs, and visual data from pre-classified image corpus using LLM reasoning

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

**Model**: Same as Financial agent (`settings.deep_research_financial_model`)

**Tools Used**:
- `corpus_visuals_search` - Query `article_images` BigQuery table

**Query Strategy:**
- Match by companies (from research_brief.entities)
- Match by industries (from research_brief.industries)
- Match by topics (revenue, market_share, forecast, etc.)
- Filter by image_type (chart, graph, infographic)
- LLM ranks and selects from candidates

**Graceful Degradation:**
If LLM selection fails, falls back to heuristic selection based on relevance scores.

**Output**: `VisualAgentOutput` with:
- List of `SupportingVisual` objects
- Each visual includes: image_url, description, chart_type, source_article, relevance_score

**BigQuery Table Reference:**
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

### 5. Synthesizer (`synthesizer.py`)
**Purpose**: Merge findings into a dynamic, block-based executive report

**Synthesizer V3: Block-Based Narrative (Session 78):**
The Synthesizer agent has been upgraded from generating flat text to designing a rich, component-based layout. Instead of rigid sections, the agent constructs the report using a library of UI blocks:

**Available Output Blocks:**
- **`paragraph`**: Standard text analysis with inline citation pills
- **`metric_grid`**: A horizontal row of key comparison metrics (e.g., Revenue $1.2B | YoY +12%)
- **`visual_split`**: A high-impact side-by-side layout pairing analysis text with a specific chart from the Visual agent
- **`quote`**: A styled, verbatim callout for CEO/CFO quotes that ground the narrative

**Key Features:**
- **Visual Agency**: The agent explicitly chooses *where* to place visuals using the `visual_split` block, integrating them into the narrative flow rather than appending them as an afterthought.
- **Graceful Degradation**: If no visuals are available, the agent falls back to text and metric grids to maintain a high-quality "text-only" presentation.
- **Citation Robustness**: Every block type supports strict citation verification, rendered as clickable pills in the UI.

**Brevity-First Design:**
- **12-word max headlines** - Lead with the insight
- **2-3 sections max** - Ruthlessly prioritize
- **blocks** - Mix of text, data, and visuals

**Output**: `SynthesisAgentOutput` with `blocks` list per section instead of `content` string.

### 6. Validator (`validator.py`)
**Purpose**: Citation verification and quality gate

**Checks**:
- Citation completeness (every claim has a source)
- Citation quality (URLs, dates, proper attribution)
- Unsubstantiated claims detection
- Confidence level alignment with data quality

**Output**: `ValidatorOutput` with:
- `validation_passed` boolean
- Citation issues (missing URLs, date mismatches)
- Confidence adjustments
- Warnings

## State Schema

Defined in `state.py` with reducer annotations for parallel execution:

```python
class DeepResearchState(TypedDict):
    # Immutable fields (set early, never change)
    user_query: Annotated[str, _keep_first]
    conversation_history: Annotated[List[BaseMessage], _keep_first]
    research_brief: Annotated[Optional[ResearchBrief], _keep_first]
    clarification_count: Annotated[int, _keep_first]
    
    # Mutable outputs (each agent updates its own field)
    financial_output: Annotated[Optional[FinancialAgentOutput], _keep_last]
    industry_output: Annotated[Optional[IndustryAgentOutput], _keep_last]
    visual_output: Annotated[Optional[VisualAgentOutput], _keep_last]  # NEW - Phase 6
    final_report: Annotated[Optional[SynthesisAgentOutput], _keep_last]
    category_output: Annotated[Optional[CategoryAgentOutput], _keep_last]
    validator_output: Annotated[Optional[ValidatorOutput], _keep_last]
    current_status: Annotated[str, _keep_last]
    
    # Merged from parallel branches
    errors: Annotated[List[Dict[str, Any]], _merge_errors]
```

**Why Annotated?** LangGraph's `Send` API for parallel execution passes full state to each branch. When branches return, their states must be merged. Without reducers, duplicate keys cause `InvalidUpdateError`.

**Visual Output Schema:**
```python
class VisualAgentOutput(BaseModel):
    """Output from Visual Research agent."""
    visuals: List[SupportingVisual] = []  # Uses existing SupportingVisual model
    search_summary: str  # What was searched for
    total_found: int  # Total matches before filtering
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/research/start` | POST | Start deep research workflow |
| `/api/research/stream/{id}` | GET | Stream research progress (SSE) |

## Configuration

Model settings in `backend/app/config/settings.py`:

```python
deep_research_groomer_model = "claude-haiku-4-5"
deep_research_financial_model = "claude-sonnet-4-5"
deep_research_industry_model = "claude-sonnet-4-5"
deep_research_synthesizer_model = "claude-sonnet-4-5"
deep_research_category_model = "claude-sonnet-4-5"
deep_research_validator_model = "claude-sonnet-4-5"
```

### Timeout Configuration

```python
# Timeout settings (in seconds)
deep_research_workflow_timeout = 300  # 5 minutes total workflow timeout
deep_research_tool_timeout = 60       # 60 seconds per external tool call
deep_research_llm_timeout = 120       # 120 seconds for LLM extraction calls
```

**Timeout Behavior:**
- Workflow timeout is monitored during event streaming
- If exceeded, a `timeout` SSE event is emitted with details about completed/active nodes
- Frontend displays a user-friendly timeout message with retry option
- Individual tool timeouts can be applied using the `sync_tool_with_timeout` decorator from `app/utils/retry.py`

### Extended Thinking Configuration

Claude's Extended Thinking feature provides transparency into the model's reasoning process during report synthesis. When enabled, users can see how Claude analyzed and connected the research findings.

```python
# Extended Thinking settings
deep_research_thinking_enabled = True   # Enable Claude's extended thinking
deep_research_thinking_budget_tokens = 10000  # Token budget (min 1024, affects latency)
```

**How It Works:**
1. Synthesizer agent calls Claude with `thinking: { type: "enabled", budget_tokens: N }`
2. Claude performs extended reasoning internally before generating the report
3. A summarized version of the thinking process is returned (Claude 4 models return summaries, not full thinking)
4. Thinking content is streamed via SSE `thinking` event and included in the `thinking_content` field of the report
5. Frontend displays thinking in a collapsible "Claude's Reasoning Process" section

**Key Considerations:**
- Extended thinking adds latency (~10-30s depending on budget)
- Temperature/top_k parameters are not compatible with extended thinking
- Thinking budget must be less than max_tokens (16000 by default)
- OpenAI fallback does NOT support extended thinking (gracefully degrades)

**Documentation:** https://platform.claude.com/docs/en/build-with-claude/extended-thinking

## Streaming & Caching

### Progress Emissions

Agents emit real-time progress via `progress.py`:

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

**Real-Time SSE Streaming** (Session 42 Fix):
- Progress events are collected via `ProgressCollector` async queue
- API route polls the queue every **100ms** using `asyncio.wait_for` timeout
- Events stream immediately instead of waiting for LangGraph lifecycle events
- Parallel agents (Financial + Industry) emit progress without blocking each other

**State Accumulation**:
- During parallel execution, each node returns partial state
- The API route maintains `accumulated_state` to merge outputs from all nodes
- Ensures `final_report` is captured even when parallel branches complete asynchronously

### Two-Tier Caching (Phase 4)

Reports use a two-tier caching strategy:

**Tier 1: In-Memory Cache**
- TTL: 1 hour
- Cache key: SHA256 of normalized (lowercase, trimmed) query
- Fastest retrieval for recent/repeated queries
- Endpoints: `GET /cache/stats`, `DELETE /cache/clear`

**Tier 2: BigQuery Persistence**
- TTL: 24 hours (configurable)
- Table: `deep_research_reports`
- Survives server restarts
- Enables report history and search
- Endpoints: `GET /reports`, `GET /reports/{id}`, `GET /reports/search/related`

### Research Memory Service

The `memory.py` module provides context integration:

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

### Saved Reports API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/research/reports` | GET | List saved reports (paginated) |
| `/api/research/reports/{id}` | GET | Get full report by ID |
| `/api/research/reports/search/related` | GET | Find related past research |

## Files

| File | Purpose | Key Features |
|------|---------|--------------|
| `groomer.py` | Query grooming node | Explicit JSON schema, empty message filtering, **context injection** |
| `financial.py` | Financial research node | SEC filings, earnings, explicit JSON schema, **conditional earnings API** |
| `industry.py` | Industry research node | Exa search, Google Trends, explicit JSON schema |
| `synthesizer.py` | Report synthesis node | Merges outputs, executive summary, explicit JSON schema |
| `category.py` | Sales intelligence node | Territory insights, product recommendations |
| `validator.py` | Citation verification node | URL validation, unsubstantiated claim detection |
| `state.py` | Pydantic schemas and TypedDict state | **Reducer annotations for parallel execution** |
| `progress.py` | Progress callback infrastructure | SSE event emission |
| `memory.py` | **Research memory service (Phase 4)** | BigQuery persistence, related research search |

**LangGraph Workflow Files** (in `app/graph/` folder):

| File | Purpose | Key Features |
|------|---------|---------------|
| `research_workflow.py` | LangGraph workflow definition | `Send` API for parallel fan-out, node routing |
| `workflow.py` | Workflow utilities | Helper functions for graph operations |

## Testing

### Quick Validation

```bash
# Verify workflow compiles
cd backend
python -c "from app.graph.research_workflow import create_research_workflow; g = create_research_workflow(); print('OK:', list(g.nodes.keys()))"
```

### Full Workflow Test

```bash
# Run parallel execution test
cd backend
python test_parallel_fix.py
```

Expected output:
```
[groom] Status: grooming_complete → Research brief generated
[financial_research] Status: financial_research_complete → Financial output ready
[industry_research] Status: industry_research_complete → Industry output ready
[synthesize] Status: synthesis_complete → Final report synthesized!
[categorize] Status: category_complete → Category output ready
[validate] Status: validation_complete → Validation complete
✓ Workflow completed without InvalidUpdateError!
```

### API Test

```bash
# Start server
cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# In another terminal
python test_trace.py
```

## Example Usage

```python
from app.graph.research_workflow import research_workflow

# Initialize state
initial_state = {
    "user_query": "What's the outlook for carbon fiber in aerospace?",
    "conversation_history": [],
    "research_brief": None,
    "clarification_count": 0,
    "financial_output": None,
    "industry_output": None,
    "final_report": None,
    "category_output": None,
    "validator_output": None,
    "current_status": "starting",
    "errors": [],
}

# Run workflow
result = await research_workflow.ainvoke(initial_state)

# Access outputs
report = result["final_report"]
sales_intel = result["category_output"]
validation = result["validator_output"]
```

## Roadmap

### Phase 2 ✅ (Completed)
- Category Agent for sales intelligence
- Validator Agent for citation verification
- Datasheet query tools

### Phase 3 ✅ (Completed - January 5, 2026)
- [x] Parallel execution of Financial + Industry agents (LangGraph `Send` API)
- [x] **State merge reducers** (`_keep_first`, `_keep_last`, `_merge_errors`)
- [x] **Explicit JSON schemas** in all extraction prompts (fixes Pydantic validation)
- [x] Streaming granularity (`ToolProgress` callbacks, 14 emission points)
- [x] Report caching by query hash (in-memory, 1-hour TTL)
- [x] Progress module (`progress.py`) for cross-context event emission
- [x] LangSmith observability integration (trace costs, latency, errors)
- [x] Empty message filtering in groomer (prevents Anthropic API errors)

### Phase 4 ✅ (Completed - January 5, 2026)
- [x] Memory/context integration - Groomer receives prior research context
- [x] BigQuery persistence - `deep_research_reports` table with 24h TTL
- [x] Saved Reports API - `GET /reports`, `GET /reports/{id}`, `GET /reports/search/related`
- [x] Context injection - Related research surfaced to groomer prompt
- [x] Conditional earnings API - Only fetches external transcripts when companies mentioned

### Phase 5 ✅ (Completed - January 6, 2026)
- [x] Workflow-level timeout handling (5 minute default)
- [x] Timeout configuration in settings.py
- [x] SSE `timeout` event with completed/active node details
- [x] Frontend timeout UI with retry option
- [x] Per-tool timeout utility (`sync_tool_with_timeout` decorator)

### Phase 6 (Complete - Visual Agent + Report Enrichments)
- [x] **Visual Research Agent** - Parallel agent for charts/graphs
  - [x] Create `corpus_visuals_search` MCP tool (`app/mcp/tools/corpus_visuals.py`)
  - [x] Create Visual agent (`app/agents/research/visual.py`)
  - [x] Add `VisualAgentOutput` to state schema
  - [x] Update workflow for 3-way parallel fan-out
  - [ ] Update Synthesizer to place visuals in sections (pending: visual data pass-through)
  - [x] Add SSE streaming for visual_research node
- [x] **Company Logo Enrichment** (Session 75)
  - [x] Add `CompanyWithLogo` model to state.py
  - [x] Add `_enrich_companies_with_logos()` to synthesizer.py
  - [x] Add `companies_with_logos` to `SynthesisAgentOutput`
- [x] **Clickable Citations** (Session 75)
  - [x] Frontend renders `source_url` as clickable domain links
  - [x] Citations displayed as pill-style badges under each section

### Phase 7 (Complete - Citation Enforcement for User Verification)
- [x] **Citation Enforcement** (Session 77)
  - [x] Add `key_point_citations` field to `ExecutiveSummary` model in state.py
  - [x] Update synthesizer prompt with explicit citation requirements
  - [x] Add citation enforcement logic in post-processing (flag missing citations)
  - [x] Frontend: Inline citation badges next to each key point
  - [x] Frontend: Sources & References footer section with all sources_used
  - [x] Frontend: Data gaps warning display

### Phase 8 (Planned)
- [ ] **Chart Generation** - Generate visuals from BigQuery trend data
  - [ ] `generate_trend_chart` tool (matplotlib/plotly)
  - [ ] `generate_comparison_table` tool
- [ ] Frontend: Tool Health dashboard (API status, latency, success rates)
- [ ] Frontend: Saved Reports history view
- [ ] Semantic search on past reports (query embeddings)

## Debug Logging

Comprehensive debug logging is built into every node for production debugging. All log messages use a consistent `[NODE_NAME]` prefix for easy filtering in Cloud Run Logs.

### Log Prefixes

| Prefix | Node | What's Logged |
|--------|------|---------------|
| `[GROOMER]` | Query Grooming | START/COMPLETE timing, query count, financial/industry queries generated |
| `[FINANCIAL_RESEARCH]` | Financial Agent | START/COMPLETE timing, finding count, state keys |
| `[INDUSTRY_RESEARCH]` | Industry Agent | START/COMPLETE timing, finding count, state keys |
| `[VISUAL_RESEARCH]` | Visual Agent | START timing, state keys |
| `[SYNTHESIZER]` | Synthesizer | START/COMPLETE timing, input analysis, section count |
| `[ROUTE_AFTER_GROOM]` | Workflow Router | Routing decision, state keys, current_status |
| `[DEEP_RESEARCH]` | API Route | Initial state, workflow start |

### Example Log Output

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
```

### Cloud Run Log Filtering

```bash
# Filter by node in Cloud Run Logs
gcloud logging read 'resource.type="cloud_run_revision" AND textPayload=~"\[GROOMER\]"' --limit=50

# Filter all research workflow logs
gcloud logging read 'resource.type="cloud_run_revision" AND textPayload=~"\[(GROOMER|FINANCIAL_RESEARCH|INDUSTRY_RESEARCH|SYNTHESIZER)\]"' --limit=100
```

## LLM Timeout Protection

Each LLM call has a 90-second `asyncio.wait_for` timeout to prevent indefinite hangs:

```python
# groomer.py example
LLM_TIMEOUT = 90
try:
    response = await asyncio.wait_for(llm.ainvoke(messages), timeout=LLM_TIMEOUT)
    logger.info(f"Groomer LLM response received, length: {len(response.content)}")
except asyncio.TimeoutError:
    logger.error(f"Groomer LLM call timed out after {LLM_TIMEOUT}s")
    state["errors"].append({"node": "groomer", "error": f"LLM call timed out after {LLM_TIMEOUT} seconds"})
    state["current_status"] = "grooming_failed"
```

**Why 90 seconds?**
- HTTP timeout (120s) wasn't being enforced at the asyncio task level
- Anthropic API can occasionally hang with no response
- 90s gives ample time for complex queries while preventing indefinite waits

## Troubleshooting

### Common Issues

**InvalidUpdateError: Can receive only one value per step**
- **Cause**: State field missing reducer annotation for parallel execution
- **Fix**: Add `Annotated[Type, reducer_function]` to field in `state.py`

**Pydantic validation errors (missing fields)**
- **Cause**: LLM output doesn't match schema
- **Fix**: Add explicit JSON schema to the extraction prompt (see `financial.py`, `industry.py`, `synthesizer.py`)

**Anthropic API error: empty message content**
- **Cause**: Empty messages in conversation history
- **Fix**: Filter messages before LLM call (see `groomer.py`)

**"Query analysis was cancelled" / "LLM call was cancelled" immediately**
- **Cause**: SSE event loop cancellation bug (Session 65)
- **Symptoms**: Research fails within ~100ms with cancelled error, despite groomer working locally
- **Root Cause**: `asyncio.wait_for(event_iterator.__anext__(), timeout=0.1)` cancels the LLM task when timeout fires
- **Fix**: Always use `asyncio.shield()` when polling an async iterator:
  ```python
  # WRONG - cancels workflow!
  event = await asyncio.wait_for(event_iterator.__anext__(), timeout=0.1)
  
  # CORRECT - protects from cancellation
  if pending_task is None:
      pending_task = asyncio.create_task(event_iterator.__anext__())
  event = await asyncio.wait_for(asyncio.shield(pending_task), timeout=0.5)
  ```
- **Files**: `app/api/routes/deep_research.py` lines 355-420

**Research hangs/times out**
- **Cause**: External API (SEC, StockNews, Exa) is slow or unresponsive
- **Symptoms**: Frontend shows "Research timed out" after 5 minutes
- **Fix**: 
  1. Check `timeoutInfo.active_nodes` to identify stuck stage
  2. Use `sync_tool_with_timeout` decorator for problematic tools
  3. Adjust `deep_research_workflow_timeout` in settings if needed
- **Monitoring**: View LangSmith traces to identify slow tool calls

## Observability (LangSmith)

LangSmith tracing is enabled for all Deep Research workflow runs.

### Configuration

Set in `.env`:
```bash
LANGCHAIN_API_KEY=lsv2_pt_xxx
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=c1-intelligence-hub-prod
```

### What's Traced

Every workflow run automatically sends:
- **Run name**: `DeepResearch: {query preview}`
- **Tags**: `deep_research`, `production`
- **Metadata**: `run_id`, `query_hash`, `timestamp`, `query_length`

### Viewing Traces

1. Visit [LangSmith Dashboard](https://smith.langchain.com)
2. Select project: `c1-intelligence-hub-prod`
3. Filter by tag: `deep_research`

### Key Metrics to Monitor

| Metric | What to Watch |
|--------|---------------|
| **Latency** | Financial/Industry nodes (parallel) should complete in ~30s each |
| **Token Usage** | ~10-15k tokens per research run (6 LLM calls) |
| **Error Rate** | Failed tool calls, citation validation issues |
| **Cache Hits** | High hit rate = good query normalization |

### Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/deep-research/observability/status` | Check LangSmith config status |
| `GET /api/deep-research/cache/stats` | View cached reports |
