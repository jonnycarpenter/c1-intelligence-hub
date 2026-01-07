# C1 Intelligence Hub - Architecture Guide

> **For AI Agents**: Read this document before making structural changes to the codebase.

---

## Core Architectural Boundaries

### 1. Ingestion Layer (`app/tools/`)

**Purpose**: Data collection from external sources → BigQuery

**Characteristics**:
- Called by `IngestionOrchestrator` on scheduled intervals
- Writes to BigQuery tables (articles, press_releases, etc.)
- No LLM interaction - pure data collection
- Each collector follows: `collector.py`, `client.py`, `models.py` pattern

**Current Collectors**:
```
app/tools/
├── earnings/          # Earnings call transcripts (API Ninjas)
├── press_releases/    # Press releases (Exa)
├── sec_filings/       # SEC EDGAR filings
├── stocknews/         # Stock news (StockNews API)
└── stocknewsapi/      # Alternative news source
```

### 2. Agent Layer (`app/mcp/tools/`)

**Purpose**: Conversational agent tools exposed via MCP server

**Characteristics**:
- Called by LLM agents during user conversations
- Reads from BigQuery (never writes to primary tables)
- Exposed through `app/mcp/server.py` → `get_all_mcp_tools()`
- Can call external APIs for on-demand research

**Current Tools** (43 total):
```
app/mcp/tools/
├── corpus_query.py        # Query ingested articles (BigQuery)
├── data_management.py     # Company/material tracker CRUD
├── exa_search.py          # Web search via Exa.ai
├── stocknews_api.py       # On-demand news retrieval
├── google_trends.py       # Search trends analysis
├── product_intelligence.py # Product catalog queries
├── timeseries_data.py     # Historical data queries
├── api_ninja_earnings.py  # Earnings transcript search
├── visualization.py       # Chart generation
├── image_extraction.py    # Visual content search
├── document_extraction.py # PDF/document extraction
└── tavily_search.py       # Alternative web search
```

---

## Data Architecture

### BigQuery is the Single Source of Truth

```
┌─────────────────────────────────────────────────────────────┐
│                     BigQuery (Production)                    │
├─────────────────────────────────────────────────────────────┤
│  articles          - News articles with embeddings          │
│  press_releases    - Company press releases                 │
│  earnings_calls    - Earnings transcripts                   │
│  sec_filings       - SEC filing metadata                    │
│  user_preferences  - User configuration                     │
│  briefings         - Generated intelligence briefings       │
│  ingestion_runs    - Pipeline execution history             │
└─────────────────────────────────────────────────────────────┘
           ▲                                    ▲
           │                                    │
     [WRITE ONLY]                         [READ ONLY]
           │                                    │
    ┌──────┴──────┐                    ┌───────┴───────┐
    │  Ingestion   │                    │   MCP Agent   │
    │  Pipeline    │                    │    Tools      │
    │ (app/tools/) │                    │(app/mcp/tools)│
    └─────────────┘                    └───────────────┘
```

### What We DON'T Use (Deprecated)
- ❌ SQLite - Removed in Phase 2 (was `intelligence.db`)
- ❌ ChromaDB - Removed in Phase 2 (was `chroma_db/`)
- ❌ Local JSON caches - Use BigQuery instead

---

## Script Organization

### Active Script Directories

| Directory | Purpose | Example Scripts |
|-----------|---------|-----------------|
| `scripts/monitoring/` | Production health | `production_dashboard.py`, `scheduler_report.py` |
| `scripts/health/` | Diagnostics | `ingestion_health_check.py`, `check_config.py` |
| `scripts/operations/backfill/` | Data backfill | `backfill_industry_queries.py`, `backfill_sec_filings.py` |
| `scripts/operations/maintenance/` | Maintenance tasks | `fix_bad_timestamps.py`, `migrate_sqlite_to_bq.py` |
| `scripts/operations/triggers/` | Pipeline triggers | `manual_trigger_ingest.py`, `ingestion_pipeline.py` |
| `scripts/testing/` | Development tests | All `test_*.py` and `check_*.py` files |
| `scripts/verification/` | Post-deploy checks | `verify_backfill_results.py` |

### Deprecated (DO NOT USE)
- `scripts/archive/` - SQLite/ChromaDB era scripts

---

## Decision Records (ADRs)

### ADR-001: BigQuery as Single Source of Truth
**Date**: December 2025  
**Status**: Accepted  
**Context**: Originally used SQLite for local dev and ChromaDB for embeddings  
**Decision**: Migrate all data to BigQuery, remove local databases  
**Rationale**: Simpler architecture, no sync issues, native vector search  

### ADR-002: Unified Agent (No Personas)
**Date**: January 2026  
**Status**: Accepted  
**Context**: Had 3 agent personas (industry_watcher, market_scout, product_maven)  
**Decision**: Remove persona-based tool filtering, single agent gets all tools  
**Rationale**: Personas added complexity without clear user benefit  

### ADR-003: Tool Directory Separation
**Date**: December 2025  
**Status**: Accepted  
**Context**: Tools were mixed between ingestion and agent use  
**Decision**: `app/tools/` for ingestion only, `app/mcp/tools/` for agents only  
**Rationale**: Clear responsibility boundaries, easier to maintain  

### ADR-004: No New Local Databases
**Date**: January 2026  
**Status**: Accepted  
**Context**: Phase 2 cleanup removed SQLite and ChromaDB  
**Decision**: Never add new SQLite, ChromaDB, or similar local databases  
**Rationale**: BigQuery handles all data needs, local DBs cause sync issues  

### ADR-005: Hardcoded GCP Configuration Defaults
**Date**: January 4, 2026  
**Status**: Accepted  
**Context**: Data was being lost to SQLite fallback when GCS_BUCKET_NAME env var was missing  
**Decision**: Hardcode production GCP defaults in `gcp_storage.py` and `settings.py`  
**Rationale**: Prevents silent fallback to SQLite; system always uses BigQuery even if env vars missing  
**Values**: `project_id=gen-lang-client-0436975498`, `bucket=gen-lang-client-0436975498-c1-hub-data`  

### ADR-006: Consolidated Script Organization
**Date**: January 6, 2026  
**Status**: Accepted  
**Context**: Test and check scripts scattered across root and backend directories  
**Decision**: Move all test/check scripts to `backend/scripts/testing/`, organize operations into subdirectories  
**Rationale**: Cleaner root directory, easier discoverability, follows established script structure  
**Impact**: 40+ scripts moved, `backend/scripts/README.md` updated with comprehensive index  

### ADR-007: OpenAI as Fallback LLM Provider
**Date**: January 6, 2026  
**Status**: Accepted  
**Context**: System relies entirely on Anthropic (Claude) for LLM calls. Credit exhaustion causes complete failure.  
**Decision**: Add OpenAI as a fallback provider that automatically activates when Anthropic fails  
**Rationale**: Provides resilience against credit outages without changing primary models  
**Implementation**:
- `app/utils/resilient_llm.py` - Cross-provider wrapper with automatic fallback
- `ResilientChatAnthropic` for LangChain code, `ResilientAsyncClient` for raw SDK
- Model mapping: claude-sonnet-4-5 → gpt-4o, claude-opus-4-5 → gpt-4o, haiku → gpt-4o-mini
- OpenAI is ONLY used as fallback - never primary
**Impact**: Added `langchain-openai>=0.2.0` and `openai>=1.54.0` to requirements  
**Env Var**: `OPENAI_API_KEY` (optional, enables fallback)

### ADR-008: Split Cloud Scheduler Jobs by Search Engine
**Date**: January 6, 2026 (Updated v2)  
**Status**: Accepted  
**Context**: 
- Cloud Scheduler max timeout is 30 minutes (hard limit)
- Original `ingest-web-search` job ran 236 queries (91 Exa + 145 Tavily) taking 25-35 min
- Job would timeout even though data was successfully ingested
- Liveness probe failures during long-running ingestion caused instance restarts

**Decision**: Split web search by search engine into separate jobs:

| Job | Schedule (CST) | Sources | Timeout |
|-----|----------------|---------|---------|
| `ingest-flash-update` | Every 4h | rss, freight | 10 min |
| `ingest-exa` | 2:00 AM | exa_queries, press_releases | 20 min |
| `ingest-tavily` | 2:20 AM | tavily_queries | 25 min |
| `ingest-financial` | 2:45 AM | sec, earnings, fmp_news, stocknews | 30 min |
| `weekly-executive-briefing` | Mon 8:30 AM | (triggers briefing) | 15 min |

**Rationale**: 
- Each job stays well under 30-minute limit
- 20-minute buffer between Exa and Tavily, 25-minute buffer before Financial
- Exa runs first (higher quality queries), Tavily follows (broadening queries)
- All daily ingestion completes by ~3:15 AM CST (before workday)
- Better error isolation - know exactly which search engine failed
- Deduplication handles cross-job overlap (same URL from Exa at 2:00 AM gets skipped if Tavily finds it at 2:20 AM)

**Implementation**:
- Added `exa_queries` and `tavily_queries` as new source types in `orchestrator.py`
- Legacy `industry_queries` still works (runs both) for backward compatibility
- [deploy/scheduler/deploy_jobs.ps1](deploy/scheduler/deploy_jobs.ps1) - canonical job definitions
- Legacy `ingest-web-search` auto-deleted when deploy script runs

**Source Distribution**:
- **Exa Job**: exa_queries (91 queries), press_releases, per-company news
- **Tavily Job**: tavily_queries (145 broadening queries)
- **Financial Job**: sec, earnings, fmp_news, stocknews (48 API calls)
- **Flash Job**: rss (14 feeds), freight (Drewry WCI)

**Critical Bug Fixed (Jan 6, 2026)**:
Anthropic SDK 0.75.0 changed `system` parameter handling - passing `system=None` caused validation error. Fixed in `resilient_llm.py` by conditionally including parameter.

### ADR-009: Exa API Future Date Validation
**Date**: January 6, 2026  
**Status**: Accepted  
**Context**: Articles were appearing in BigQuery with impossible future dates (May 2026, Sep 2026). Investigation revealed Exa API was returning dates extracted from market projection content (e.g., "expected to reach $43B by 2026") as publication dates.

**Decision**: Add future date validation when parsing Exa API responses. Reject any date more than 2 days in the future.

**Rationale**: 
- Exa's date extraction is unreliable for market research pages
- Future dates break feed eligibility logic and confuse users
- 2-day buffer allows for timezone differences without accepting obviously wrong dates

**Implementation**:
- `app/ingestion/orchestrator.py` - `_convert_search_result_to_article()` method
- `app/tools/press_releases/collector.py` - `collect_for_company()` method
- Rejected dates set to `None` → article stored but `feed_eligible=False`

**Test Evidence**:
```python
# Exa returned these for market research pages:
"2026-05-13T19:02:00.000Z"  # US aerospace composites market
"2026-09-11T00:00:00.000Z"  # Aerospace composites market
# Both now correctly rejected
```

---

## Adding New Components

### New Ingestion Collector
1. Create `app/tools/{source_name}/`
2. Implement `collector.py` with `collect_for_company()` method
3. Register in `app/ingestion/orchestrator.py`
4. Add BigQuery table if needed
5. Update `app/tools/README.md`

### New Agent Tool
1. Create `app/mcp/tools/{tool_name}.py`
2. Implement as `@tool` decorated function
3. Import in `app/mcp/server.py`
4. Add to `get_all_mcp_tools()` return list
5. Update `app/mcp/tools/README.md`

### New Script
1. Determine category (monitoring, health, operations, testing, verification)
2. Create in appropriate `scripts/{category}/` directory
3. Update `scripts/README.md`

---

## Key Files Reference

| File | Purpose |
|------|---------|
| `app/mcp/server.py` | MCP tool registration - `get_all_mcp_tools()` |
| `app/ingestion/orchestrator.py` | Ingestion pipeline coordinator |
| `app/config/settings.py` | Environment configuration |
| `app/db/bigquery_client.py` | BigQuery connection |
| `app/db/gcp_storage.py` | BigQuery + GCS storage (hardcoded defaults) |
| `app/db/bq_vector_store.py` | Vector store with Vertex AI embeddings |
| `app/db/vector_store.py` | Thin wrapper → always returns BigQuery |
| `app/models/corpus.py` | Article model with feed_eligible field |
| `scripts/operations/maintenance/migrate_sqlite_to_bq.py` | Migration script for legacy SQLite data |
| `scripts/operations/triggers/ingestion_pipeline.py` | Main ingestion pipeline orchestrator |
