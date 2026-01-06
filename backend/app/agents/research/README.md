# Deep Research Workflow

Multi-agent research pipeline for comprehensive industry intelligence reports.

## Overview

Deep Research is a 7-node LangGraph workflow that orchestrates specialized agents to produce executive-ready research reports. It combines financial data, industry news, and sales intelligence into a single deliverable.

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
┌─────────────┐     │    │  Research   │   │
│   Groomer   │─────┤    └─────────────┘   │    ┌─────────────┐
│   (Query)   │     │                      ├───►│ Synthesizer │
└─────────────┘     │    ┌─────────────┐   │    │  (Report)   │
                    └───►│  Industry   │───┘    └──────┬──────┘
                         │  Research   │               │
                         └─────────────┘               ▼
                                              ┌─────────────┐
                                              │  Category   │
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

**Parallel Execution**: Financial and Industry agents run simultaneously using LangGraph's `Send` API with custom reducer functions for state merging.

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

**Model**: `claude-sonnet-4-5` (configurable via `settings.deep_research_groomer_model`)

### 2. Financial Research (`financial.py`)
**Purpose**: Financial data and corporate intelligence

**Tools Used**:
- `get_earnings_transcript_ninja` - Earnings call transcripts
- `query_corpus` - Pre-ingested financial articles
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

### 4. Synthesizer (`synthesizer.py`)
**Purpose**: Merge findings into executive-ready report

- Deduplicates overlapping findings
- Connects financial reality with market activity
- Structures content into thematic sections
- Creates executive summary with key metrics
- Generates field sales implications

**Output**: `SynthesisAgentOutput` with full report structure

### 5. Category Agent (`category.py`) *(Phase 2)*
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

### 6. Validator (`validator.py`) *(Phase 2)*
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
    final_report: Annotated[Optional[SynthesisAgentOutput], _keep_last]
    category_output: Annotated[Optional[CategoryAgentOutput], _keep_last]
    validator_output: Annotated[Optional[ValidatorOutput], _keep_last]
    current_status: Annotated[str, _keep_last]
    
    # Merged from parallel branches
    errors: Annotated[List[Dict[str, Any]], _merge_errors]
```

**Why Annotated?** LangGraph's `Send` API for parallel execution passes full state to each branch. When branches return, their states must be merged. Without reducers, duplicate keys cause `InvalidUpdateError`.

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

### Query Caching

Reports are cached in-memory by query hash:
- TTL: 1 hour
- Cache key: SHA256 of normalized (lowercase, trimmed) query
- Endpoints: `GET /cache/stats`, `DELETE /cache/clear`

## Files

| File | Purpose | Key Features |
|------|---------|--------------|
| `groomer.py` | Query grooming node | Explicit JSON schema, empty message filtering |
| `financial.py` | Financial research node | SEC filings, earnings, explicit JSON schema |
| `industry.py` | Industry research node | Exa search, Google Trends, explicit JSON schema |
| `synthesizer.py` | Report synthesis node | Merges outputs, executive summary, explicit JSON schema |
| `category.py` | Sales intelligence node | Territory insights, product recommendations |
| `validator.py` | Citation verification node | URL validation, unsubstantiated claim detection |
| `state.py` | Pydantic schemas and TypedDict state | **Reducer annotations for parallel execution** |
| `progress.py` | Progress callback infrastructure | SSE event emission |
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

### Phase 4 (Planned)
- [ ] Memory/context integration (avoid redundant fetches)
- [ ] BigQuery persistence for user-saved reports (table: `research_reports`)
- [ ] Frontend integration for `tool_progress` SSE events

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
