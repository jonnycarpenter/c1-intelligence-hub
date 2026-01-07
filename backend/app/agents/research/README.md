# Deep Research Workflow

Multi-agent research pipeline for comprehensive industry intelligence reports.

## Overview

Deep Research is an 8-node LangGraph workflow that orchestrates specialized agents to produce executive-ready research reports. It combines financial data, industry news, visual assets, and sales intelligence into a single deliverable.

**Status: ✅ PRODUCTION READY** (January 5, 2026)

**Key Features:**
- Parallel execution of Financial + Industry agents (~40% faster)
- Real-time SSE streaming with granular tool progress
- In-memory query caching (1-hour TTL)
- LangSmith observability for cost/latency tracking
- Pydantic schema validation at every node

## Pipeline Architecture

```
                         ┌─────────────┐
                    ┌───►│  Financial  │───┐
                    │    │  Research   │   │
┌─────────────┐     │    └─────────────┘   │
│   Groomer   │─────┼───►┌─────────────┐   │    ┌─────────────┐
│   (Query)   │     │    │  Industry   │   ├───►│ Synthesizer │
└─────────────┘     │    │  Research   │   │    │  (Report)   │
                    │    └─────────────┘   │    └──────┬──────┘
                    │    ┌─────────────┐   │           │
                    └───►│   Visual    │───┘           ▼
                         │  Research   │       ┌─────────────┐
                         └─────────────┘       │  Category   │
                                               │   (Sales)   │
                                               └──────┬──────┘
                                                      │
                                                      ▼
                                               ┌─────────────┐
                                               │  Validator  │
                                               │  (QA Gate)  │
                                               └──────┬──────┘
                                                      │
                                                      ▼
                                               [Final Report]
```

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

**Model**: `claude-sonnet-4-5` (configurable via `settings.deep_research_groomer_model`)

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
**Purpose**: Merge findings into executive-ready report

- Deduplicates overlapping findings
- Connects financial reality with market activity
- Structures content into thematic sections
- Creates executive summary with key metrics
- Generates field sales implications
- **Places relevant visuals** in appropriate report sections (from Visual agent output)

**Visual Integration:**
The synthesizer receives `visual_output` from the Visual agent and matches visuals to sections by topic. For example, a revenue growth chart is placed in the "Financial Performance" section, while a market share diagram goes in "Competitive Landscape".

**Output**: `SynthesisAgentOutput` with full report structure, including `supporting_visuals` per section

### 6. Category Agent (`category.py`) *(Phase 2)*
**Purpose**: Territory-specific sales intelligence

**Territory Focus**:
| Territory | Primary Industries |
|-----------|-------------------|
| **East** | Aerospace, Wind Energy, Automotive, Defense |
| **West** | Marine, RVs, Spas |

**Tools Used**:
- `query_datasheets` - Product spec sheet lookups
- `get_products_by_industry` - Industry-specific products
- `query_corpus` - Historical sales intelligence

**Output**: `CategoryAgentOutput` with:
- Territory insights (East/West relevance scores)
- Product recommendations
- Structured sales plays (hooks, objection handlers)
- Industry talking points

### 7. Validator (`validator.py`) *(Phase 2)*
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
deep_research_groomer_model = "claude-sonnet-4-5"
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
| `../graph/research_workflow.py` | LangGraph workflow definition | `Send` API for parallel fan-out |

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

### Phase 6 (In Progress - Visual Agent)
- [ ] **Visual Research Agent** - New parallel agent for charts/graphs
  - [ ] Create `corpus_visuals_search` MCP tool (`app/mcp/tools/corpus_visuals.py`)
  - [ ] Create Visual agent (`app/agents/research/visual.py`)
  - [ ] Add `VisualAgentOutput` to state schema
  - [ ] Update workflow for 3-way parallel fan-out
  - [ ] Update Synthesizer to place visuals in sections
  - [ ] Add SSE streaming for visual_research node

### Phase 7 (Planned)
- [ ] **Chart Generation** - Generate visuals from BigQuery trend data
  - [ ] `generate_trend_chart` tool (matplotlib/plotly)
  - [ ] `generate_comparison_table` tool
- [ ] Frontend: Tool Health dashboard (API status, latency, success rates)
- [ ] Frontend: Saved Reports history view
- [ ] Semantic search on past reports (query embeddings)

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
