# C1 Intelligence Hub - AI Agent Instructions

## Session Continuity

**At end of session**: Update `WORKLOG.md` with:
1. What was completed
2. What's still in progress
3. Open items / next steps
4. Any key technical context discovered

**At start of session**: Read `WORKLOG.md` for recent context.

**⚠️ Parallel Development Warning**: The user may be working in multiple IDEs/agents simultaneously. Before pushing:
1. Run `git pull origin master` to get latest changes
2. Check for merge conflicts, especially in frontend components
3. If conflicts exist, coordinate with user before resolving

## Before Making Structural Changes

Read these files first:
- `.agent/CODING_RULES.md` - Mandatory rules
- `.agent/ARCHITECTURE.md` - System design decisions
- `WORKLOG.md` - Recent work and open items

## Critical Rules (TL;DR)

1. **BigQuery ONLY** - Never add SQLite, ChromaDB, or local databases
2. **Tool locations are fixed**:
   - Agent tools → `app/mcp/tools/`
   - Ingestion tools → `app/tools/`
   - Scripts → `scripts/{monitoring,health,operations}/`
3. **Update READMEs** when adding new modules
4. **Add comprehensive debug logging** when building new features:
   - **Module prefixes**: Use `[MODULE_NAME]` for Cloud Run filtering (e.g., `[PIPELINE_AGENT]`, `[ADHOC_AGENT]`)
   - **START/COMPLETE pairs**: Log timing for all async operations
     ```python
     start_time = time.time()
     logger.info(f"[MODULE] Operation START: params")
     # ... operation ...
     elapsed = time.time() - start_time
     logger.info(f"[MODULE] Operation COMPLETE: {elapsed:.2f}s, result_summary")
     ```
   - **LLM timeout protection**: Wrap all LLM calls with `asyncio.wait_for(timeout=120.0)`
     ```python
     try:
         response = await asyncio.wait_for(
             llm.ainvoke(messages),
             timeout=120.0
         )
         logger.info(f"[MODULE] LLM call COMPLETE: {elapsed:.2f}s")
     except asyncio.TimeoutError:
         logger.error(f"[MODULE] LLM call TIMEOUT: exceeded 120s")
         raise Exception("User-friendly timeout message")
     ```
   - **Tool execution tracking**: Log START/COMPLETE/FAILED for each tool call
   - **Enhanced error context**: Include error type, message, stack trace (`exc_info=True`), and elapsed time
   - **Examples**: See `backend/app/agents/pipeline/agent.py` and `backend/app/agents/adhoc_briefing/agent.py`
5. **SSE streaming best practices** (CRITICAL - Session 65 bug fix):
   - **NEVER** use `asyncio.wait_for()` on a shared async iterator without `asyncio.shield()`
   - Timeout cancellation propagates to the underlying task, killing LLM calls
   - Pattern: `await asyncio.wait_for(asyncio.shield(task), timeout=X)`
   - See `app/api/routes/deep_research.py` for correct SSE event loop implementation
5. **Test before committing**:
   ```bash
   cd backend
   python -c "from app.mcp.server import get_all_mcp_tools; print(len(get_all_mcp_tools()))"
   ```

## Deployment

**CI/CD Pipeline**: Git push to `master` → GitHub → Cloud Build Trigger → Cloud Run

**Region**: `us-central1` (always)

**Production Deployment** (via git, PowerShell):
```powershell
git add -A; git commit -m "Description of changes"; git push origin master
# Cloud Build trigger auto-deploys to Cloud Run (~3-5 min)
```

**Manual Deploy** (if needed, PowerShell):
```powershell
gcloud builds submit --config=cloudbuild.yaml --region=us-central1 --project=gen-lang-client-0436975498
```

**Trigger Briefing Generation** (PowerShell):
```powershell
Invoke-RestMethod -Uri "https://c1-hub-4iz75bvpyq-uc.a.run.app/api/v1/scheduler/briefing" -Method POST -ContentType "application/json" -Body '{}'
```

**Cloud Run URL**: `https://c1-hub-4iz75bvpyq-uc.a.run.app`
**Service Name**: `c1-hub`

### Adding New Secrets

When adding a new API key/secret:
1. Create in Secret Manager (no trailing newlines!):
   ```powershell
   $key = "your-key-value"
   $key | gcloud secrets create SECRET_NAME --data-file=- --project=gen-lang-client-0436975498
   ```
2. Add to `cloudbuild.yaml` in the `--set-secrets` line
3. Add to `backend/app/config/settings.py` 
4. Commit and push - Cloud Build will mount the secret


## Key Files

| Purpose | Location |
|---------|----------|
| MCP tool registration | `app/mcp/server.py` |
| Ingestion orchestrator | `app/ingestion/orchestrator.py` |
| BigQuery storage | `app/db/gcp_storage.py` |
| **Vector store (semantic search)** | `app/db/bq_vector_store.py` |
| Deduplication service | `app/ingestion/processing/deduplication.py` |
| Environment config | `app/config/settings.py` |
| **Resilient LLM wrapper** | `app/utils/resilient_llm.py` |
| **Ad-hoc briefing session manager** | `app/agents/adhoc_briefing/session_manager.py` |
| **Pre-Brief Generator (Agent 1)** | `app/ingestion/generators/pre_briefing.py` |
| **Weekly Briefing Generator (Agent 2)** | `app/ingestion/generators/weekly_briefing.py` |
| **Deep Research workflow** | `app/graph/research_workflow.py` |
| **Deep Research agents** | `app/agents/research/*.py` |
| **Deep Research state schemas** | `app/agents/research/state.py` |
| **Deep Research progress** | `app/agents/research/progress.py` |
| **Deep Research memory (Phase 4)** | `app/agents/research/memory.py` |
| **Deep Research API route** | `app/api/routes/deep_research.py` |
| **Visual Research agent (Phase 6)** | `app/agents/research/visual.py` *(to create)* |
| **Corpus visuals search tool** | `app/mcp/tools/corpus_visuals.py` *(to create)* |
| **Article images table** | BigQuery `article_images` - classified images from ingestion |
| **Podcast streaming endpoint** | `app/api/routes/podcast.py` |
| **Podcast generation (weekly)** | `app/ingestion/generators/weekly_briefing.py` *(uses ElevenLabs Text-to-Dialogue API)* |

## README Documentation Index

**At end of session**: Update relevant READMEs based on work done.

| README | Purpose | Update When... |
|--------|---------|----------------|
| `README.md` (root) | Project overview, setup, deployment | Major features, setup changes |
| `CLAUDE.md` (this file) | AI agent instructions, session context | Every session, new patterns |
| `backend/app/db/README.md` | Database layer (BigQuery) | Adding tables, changing storage |
| `backend/app/services/README.md` | Business logic services (digest, etc.) | Adding/modifying services |
| `backend/app/mcp/tools/README.md` | MCP agent tools | Adding/modifying agent tools |
| `backend/app/tools/README.md` | Ingestion data collectors | Adding/modifying data sources |
| `backend/app/utils/README.md` | Shared utilities | Adding utility modules |
| `backend/app/ingestion/generators/README.md` | Briefing generators (2-agent pipeline) | Briefing logic changes |
| **`backend/app/agents/research/README.md`** | **Deep Research workflow (7-node, parallel)** | **Modifying research pipeline** |
| `frontend/README.md` | Frontend architecture, components, hooks | Adding/modifying frontend features |
| `backend/scripts/README.md` | Script directory index | Adding new scripts |
| `backend/scripts/monitoring/README.md` | Production monitoring scripts | Adding monitoring scripts |
| `backend/scripts/health/README.md` | Health check scripts | Adding health checks |
| `backend/scripts/operations/README.md` | Data operations (backfills, maintenance) | Adding operations scripts |
| `backend/scripts/testing/README.md` | Ad-hoc test scripts | Adding test scripts |
| `backend/scripts/verification/README.md` | Post-deployment verification | Adding verification scripts |
| `backend/scripts/archive/README.md` | Deprecated scripts (DO NOT USE) | Moving scripts to archive |
| `deploy/README.md` | GCP deployment configuration | Infra/deployment changes |

## Weekly Briefing Pipeline (2-Agent Architecture)

The weekly "Need to Know" executive briefing uses a 2-agent pipeline with podcast generation:

```
Agent 1 (Pre-Brief)              Agent 2 (Synthesis)           Podcast Generation
claude-sonnet-4-5                 claude-opus-4-5              ElevenLabs TTS
        │                               │                            │
        ▼                               ▼                            ▼
┌─────────────────┐            ┌─────────────────┐         ┌─────────────────┐
│ Analyze 50 most │            │ Compare against │         │ Convert to      │
│ recent articles │ ────────►  │ historical ctx  │ ─────►  │ natural speech  │
│ from 14 days    │            │ + Exa search    │         │ Upload to GCS   │
└─────────────────┘            └─────────────────┘         └─────────────────┘
        │                               │                            │
        ▼                               ▼                            ▼
  Pre-Brief JSON              Final Briefing JSON           podcast.mp3
  (observations,              (sections, BLUF,              (4-6 min audio)
   signal_types)               source_articles)
```

**Podcast Features**:
- Natural "net new" vs "continuing" phrasing
- Text formatting: "$2.4B" → "2.4 billion dollars"
- Voice: Rachel (professional, clear)
- Storage: GCS `/podcasts/{briefing_id}.mp3`
- Frontend: Audio player with play/pause, seek, volume controls

**Key Features:**
- **Source Articles**: Each section includes `source_articles[]` with clickable links
- **BLUF**: "Bottom Line Up Front" single-sentence summary
- **Inline Logos**: `[[Company Name]]` tags render with Logo.dev images
- **Net New vs Continuing**: Badges show if topic is new or continuing from prior weeks
- **Exa Peripheral Search**: Agent 2 can search for adjacent intelligence
- **Forced Title Override** (Session 72): Title always uses calculated date, LLM-generated title ignored
- **Citation Cleanup**: `[N, Exa:M]` patterns normalized to sequential `[1]`, `[2]`, etc.

**Schedule**: Monday 8:30 AM CST via Cloud Scheduler (`weekly-executive-briefing` job)

**Backfill Scripts** (for rebuilding historical context):
```bash
cd backend
python scripts/operations/backfill_briefings.py           # All weeks
python scripts/operations/backfill_briefings.py --week 1  # Single week
python scripts/operations/backfill_briefings.py --verify  # Check results
```

## Key BigQuery Tables

| Table | Purpose |
|-------|---------|
| `articles` | Raw articles (source of truth) |
| `article_chunk_embeddings` | **Vector store** - Vertex AI embeddings for semantic search |
| `digest_items` | Classified articles with summaries |
| `article_tags` | Normalized tags for trending analytics |
| `companies` | Tracked companies (tickers, names) |
| `deep_research_reports` | **Saved Deep Research reports (Phase 4)** |
| `article_images` | **Classified images from articles** - image_type, chart_type, topics, companies, industries, relevance_score. Used by Visual Research agent (Phase 6) |

## Don't Touch (Bug Fix Protected)

These files have critical bug fixes - be careful editing:
- `app/db/gcp_storage.py` - feed_eligible logic, dedup methods
- `app/models/corpus.py` - feed_eligible field

## LLM Models & Resilience

### Primary Models (Anthropic)
| Use Case | Model | Location |
|----------|-------|----------|
| Deep Research agents | `claude-sonnet-4-5` | `app/agents/research/*.py` |
| Weekly Briefing synthesis | `claude-opus-4-5` | `app/ingestion/generators/weekly_briefing.py` |
| Deep Research groomer | `claude-haiku-4-5` | `app/agents/research/groomer.py` |
| Vision/Image extraction | `claude-sonnet-4-5` | `app/mcp/tools/image_extraction.py` |
| Pre-briefing generation | `claude-sonnet-4-5` | `app/ingestion/generators/pre_briefing.py` |
| Digest generation | `claude-sonnet-4-5` | `app/ingestion/generators/digest.py` |
| Classification | `claude-sonnet-4-5` | `app/ingestion/classifier.py` |

### Fallback Models (OpenAI) - Credit Safety Net
OpenAI is ONLY used as a fallback when Anthropic fails (e.g., credit exhaustion):

| Anthropic Model | OpenAI Fallback |
|-----------------|-----------------|
| `claude-sonnet-4-5` | `gpt-4o` |
| `claude-opus-4-5` | `gpt-4o` |
| `claude-haiku-4-5` | `gpt-4o-mini` |
| `claude-3-5-haiku-20241022` (legacy) | `gpt-4o-mini` |

### Using Resilient LLM Wrappers

**For LangChain code:**
```python
from app.utils.resilient_llm import create_resilient_llm_with_openai_fallback
from app.config.settings import settings

llm = create_resilient_llm_with_openai_fallback(
    primary_model="claude-sonnet-4-5",
    anthropic_api_key=settings.anthropic_api_key,
    openai_api_key=settings.openai_api_key,
)
```

**For raw SDK async code:**
```python
from app.utils.resilient_llm import get_resilient_async_client

client = get_resilient_async_client(
    anthropic_api_key=settings.anthropic_api_key,
    openai_api_key=settings.openai_api_key,
)
response = await client.messages_create(model="claude-sonnet-4-5", ...)
```

> **Note**: The `OPENAI_API_KEY` environment variable must be set for fallback to work.
> See `app/utils/resilient_llm.py` for implementation details.

## Recent Changes (January 7, 2026)

### Session 52 - Visual Research Agent (READY TO IMPLEMENT)
- **New Feature**: Adding Visual Research Agent to Deep Research workflow
- **Architecture**: 3-way parallel fan-out (Financial + Industry + Visual)
- **Goal**: Surface relevant charts/graphs from `article_images` BigQuery table
- **Zero Added Latency**: Visual agent (~10-15s) finishes before other agents (~30s)
- **Files to Create**:
  - `app/mcp/tools/corpus_visuals.py` - `corpus_visuals_search` tool
  - `app/agents/research/visual.py` - Visual Research agent
- **Files to Modify**:
  - `app/agents/research/state.py` - Add `VisualAgentOutput`, `visual_output` field
  - `app/graph/research_workflow.py` - Add `visual_research` node, 3-way fan-out
  - `app/agents/research/synthesizer.py` - Place visuals in report sections
  - `app/api/routes/deep_research.py` - SSE handling for visual_research
  - `app/mcp/server.py` - Register new tool
- **See**: `WORKLOG.md` Session 52 for detailed implementation plan

### Session 51 - Deep Research Groomer Fix ✅
- **Bug Fix**: Deep Research was "hanging" after groomer phase
- **Root Cause**: Claude returned `clarifying_question` as string instead of object → Pydantic validation error
- **Fix 1**: `groomer.py` - Convert string to `{question, options, default_if_skipped}` object
- **Fix 2**: `deep_research.py` - Check for `grooming_failed` status, emit error SSE event, send `[DONE]`

## Recent Changes (January 6, 2026)

### Session 48 - Ad-Hoc Briefing Conversational UX ✅
- **Bug Fix**: Streaming response not rendering (early return before setting response)
- **Stacking Briefings**: `briefings[]` array replaces single `response`
- **Collapsible History**: Older briefings collapse to headers, click to expand
- **Removed Follow-up Limits**: No more "2 follow-ups available" buttons
- **Gentle Deep Research Nudge**: Shows after 2 questions instead of hard redirect
- **New Component**: `CollapsibleBriefing` handles expand/collapse UX
- **Files Modified**: `useBriefing.ts`, `AdHocBriefing.tsx`

### Session 41 - Ad-Hoc Briefing SSE Progress Events ✅
- **Streaming Progress Events**: Real-time feedback during research phases
  - Knowledge Base → Advanced Web Search → Stock Market News → Analysis
- **Backend**: `StreamingAdHocBriefingAgent.generate_briefing_stream()` emits `progress` SSE events
- **Frontend Hook**: `progressSteps` state in `useBriefing.ts`
- **Frontend Display**: `ProgressStepDisplay` component with step icons, checkmarks, article counts
- **Files Modified**: `agent.py`, `useBriefing.ts`, `AdHocBriefing.tsx`

### Session 32 - Long-term Memory UI Components ✅
- **PreferencesPanel**: New component for managing priority/blocked topics (`frontend/src/components/memory/PreferencesPanel.tsx`)
- **SavedReportsPanel**: Browse saved Deep Research reports with search, expand/collapse, actions (`frontend/src/components/research/SavedReportsPanel.tsx`)
- **ResearchSidebar**: Added "Saved Reports" section with 5 most recent reports, "View All" opens full panel
- **API Methods**: Added `getPreferences()`, `addPreference()`, `removePreference()`, `getSavedReports()`, `getSavedReportById()`, `searchRelatedReports()` to `frontend/src/lib/api.ts`
- **Integration**: PreferencesPanel in Data & Preferences tab, SavedReportsPanel accessible from Research sidebar

### Session 31 - Podcast Generation for Weekly Briefings ✅
- **ElevenLabs TTS Integration**: Weekly briefings now generate audio podcasts
- **Backend**: `_format_text_for_speech()`, `_build_podcast_script()`, `_generate_podcast()` in `weekly_briefing.py`
- **Frontend**: `PodcastPlayer.tsx` with play/pause, seek, volume, download
- **Storage**: GCS bucket `/podcasts/{briefing_id}.mp3`

### Session 30 - Frontend UX Enhancements ✅
- Hidden chatbox on Products, Field Intel, Data & Preferences tabs
- Pipeline tab: Updated seed questions, auto-submit on click
- Sidebar: Text logo instead of PNG
- Pulse tab: Removed helper text, adjusted spacing

### Session 29 - Phase 4: BigQuery Persistence & Memory Integration ✅
- Added `deep_research_reports` BigQuery table for persistent report storage
- Created `ResearchMemory` service (`app/agents/research/memory.py`) for two-tier caching and context integration
- Two-tier cache: in-memory (1h TTL) + BigQuery (24h TTL)
- New API endpoints: `GET /api/research/reports`, `GET /api/research/reports/{id}`, `GET /api/research/reports/search/related`
- Automatic persistence of completed reports with SSE event `report_saved`
- **Context Injection**: Groomer now receives prior related research to avoid redundant clarifying questions
- **Conditional Earnings API**: External earnings API only called when user mentions specific companies (corpus always runs)

### Session 28 - API Reliability & Tool Health ✅
- Added centralized retry utilities with exponential backoff, rate-limit handling, and default skipping for non-critical tools (`app/utils/retry.py`).
- Wrapped StockNewsAPI tools (news, keyword search, press releases, analyst ratings) with retries, metrics, and skip-on-failure so research flow degrades gracefully.
- Wrapped Google Trends tool with rate-limit-aware retry and metrics.
- Added tool health endpoint `GET /api/research/tools/health` returning success rates, latency, and recent errors for instrumented tools.
- Note: StockNewsAPI key must be set via `STOCKNEWS_API_KEY` in Cloud Run env (now configured).

### Session 26 - Pulse UX Enhancements ✅
- **Visual Dimensionality**: Added `slate-50` background to "Need to Know" column in Pulse dashboard for better separation.
- **Entity Aggregator Revamp**: implemented "Heat Map" visualization for entity pills (opacity scales with frequency), replaced text labels with icons, and integrated counts.
- **Component Polish**: Updated `AdHocBriefing` loading state to match card metaphor.
- **Files Modified**: `PulseDashboard.tsx`, `EntityAggregator.tsx`, `AdHocBriefing.tsx`

### Session 25 - Deep Research Workflow Fixed! 🎉
- **Parallel Execution Working**: Fixed `InvalidUpdateError` by adding reducer annotations to ALL `DeepResearchState` fields
- **Reducers Added**: `_keep_first()` for immutable fields, `_keep_last()` for outputs, `_merge_errors()` for error lists
- **JSON Schemas Fixed**: Added explicit schemas to Financial, Industry, and Synthesizer extraction prompts
- **Empty Message Bug Fixed**: Groomer now filters empty messages before Anthropic API call
- **Files Modified**: `state.py`, `groomer.py`, `financial.py`, `industry.py`, `synthesizer.py`
- **Result**: Full workflow runs end-to-end (Groomer → Financial/Industry parallel → Synthesizer → Category → Validator)

### Session 24 - LangSmith Testing & Parallel Bug Discovery
- **LangSmith Verified**: Traces sending to `c1-intelligence-hub-prod` project
- **Groomer Infinite Loop Fixed**: Removed `"groom"` loop-back from routing
- **Groomer JSON Schema Added**: Explicit `ResearchBrief` schema in prompt
- **Bug Identified**: `InvalidUpdateError` in parallel state merge (fixed in Session 25)

### Session 23 - LangSmith Observability Integration ✅
- **LangSmith Config**: Added `RunnableConfig` with metadata to workflow invocation
- **Run Metadata**: `run_id`, `query_hash`, `timestamp`, tags for filtering
- **Observability Endpoint**: `GET /api/deep-research/observability/status`

### Session 27 - Phase 2 Output Display ✅
- **TerritoryInsights**: East/West relevance scores with visual progress bars
- **ProductRecommendations**: Grid with relevance badges, "Ask About" integration
- **SalesPlays**: Accordion with copy-to-clipboard hooks, objection handlers
- **ValidationBadge**: Collapsible validation status with issue breakdown
- **Files**: `TerritoryInsights.tsx`, `ProductRecommendations.tsx`, `SalesPlays.tsx`, `ValidationBadge.tsx`

### Session 26 - Frontend SSE Integration ✅
- **ResearchProgress Component**: Visual pipeline showing 6 workflow nodes with status indicators
- **Live Activity Feed**: Real-time tool execution display (last 20 events)
- **Parallel Execution Indicator**: Shows when Financial + Industry agents run together
- **Full SSE Support**: Handles `node_start`, `node_complete`, `tool_progress`, `category`, `validation`, `warnings`
- **Cancel Support**: AbortController-based request cancellation
- **Files**: `ResearchProgress.tsx`, `useDeepResearch.ts`, `types/index.ts`

### Session 20 - Ingestion Throughput Tuning ✅
- **Lookback Reduced**: 3 days → 2 days for daily scheduled runs (orchestrator.py)
- **Classifier Concurrency**: 3 → 10 concurrent Claude calls (classifier.py)
- **Classifier Sleep**: 0.5s → 0.2s between calls
- **Expected Impact**: ~30% fewer articles collected, classification ~3x faster
- **Rationale**: System designed for daily runs now; 2-day window provides 1-day overlap buffer

### Session 17 - Ad-Hoc Briefing Session Management ✅
- **Fixed Stateless Issue**: Ad-hoc briefing `follow_up_count` now persists across requests
- **Session Manager**: In-memory TTL cache (30-min expiry, max 1000 sessions) in `app/agents/adhoc_briefing/session_manager.py`
- **API Updates**: New endpoints for session info (`GET /adhoc/session/{id}`), deletion, and stats
- **Frontend Updates**: `useBriefing` hook tracks `sessionId` and `turnsRemaining`
- **Result**: "Max 2 follow-ups then redirect to Deep Research" logic now works correctly

### Session 14 - Digest System Investigation ✅
- **"Lowium" Bug**: Investigated and confirmed resolved (0 items found)
- **Priority Case Sensitivity**: Identified 12% capitalized values vs 88% lowercase (low priority issue)
- **Production Health**: Verified system healthy - 170 articles stored, 95.5% efficiency
- **Documentation**: Created comprehensive findings report and diagnostic script
- **Status**: Digest system confirmed working correctly, ready for production use

### Session 13b - Digest SQLite Cleanup ✅
- **Deleted Legacy SQLite**: Removed `app/db/database.py` (1,128 lines)
- **Cleaned Imports**: Updated `app/db/__init__.py` to remove `Database` and `get_db`
- **Removed ChromaDB**: Deleted `chromadb>=0.5.0` from `requirements.txt`
- **Verified Digest Flow**: Confirmed digest cards use BigQuery exclusively (no SQLite)
- **Preserved Exa Pipeline**: `exa_websets_service.py` SQLite intentionally kept (different use case)

### Session 13 - Agent 1 BigQuery Fix ✅ (READY TO DEPLOY)
- **Fixed**: PreBriefGenerator now queries BigQuery `articles` (3,308+ items) instead of SQLite (776 items)
- **Modified**: `_get_articles()` in [pre_briefing.py](backend/app/ingestion/generators/pre_briefing.py)
- **Added**: Custom date range support (`start_date`, `end_date` params) for historical pre-briefings
- **Generated**: 3 historical pre-briefings + 1 weekly briefing with proper net_new/continuing classification
- **Scripts Created**: `scripts/testing/test_prebriefing_bq.py`, `scripts/operations/generate_briefings.py`

### Session 12 - Digest Cards Data Source Verification ✅
- **Verified BigQuery Integration**: Confirmed digest cards ARE pulling from `digest_items` table (not SQLite/ChromaDB)
- **Storage Backend**: `BigQueryDataStorage` properly configured with hardcoded production defaults
- **Data Flow Validated**: Frontend → API → DigestService → BigQueryDataStorage → BigQuery
- **Current Status**: 44 items in last 72 hours being served correctly
- **Legacy Files Identified**: SQLite files exist but are NOT in use by the application
- **Diagnostic Scripts**: Created `check_digest_data.py` and `check_digest_service.py` for future debugging

### Session 11 - Historical Context Enhancement ✅
- **Historical Context Now Rich**: Agent 2 gets full context from prior briefings
  - Before: Just topic names ("Defense, Resins, Aerospace")
  - After: BLUF, section headlines with net_new/continuing status, key companies, overall trend
  - Enables accurate "differential analysis" for net_new vs continuing classification
  - Modified: `_get_historical_context()` in [weekly_briefing.py](backend/app/ingestion/generators/weekly_briefing.py)
- **BLUF Now Persisted**: Added `bluf` column to BigQuery `weekly_briefings` table
  - Added to schema, save method, and get methods in [gcp_storage.py](backend/app/db/gcp_storage.py)
  - Created migration script: `scripts/operations/migrations/add_bluf_column.py`

### Session 10 - Source Articles & BLUF ✅
- **Source Articles Now Linked**: Citations `[1]`, `[2]`, `[Exa:N]` in briefings now have clickable links
  - Added `_extract_citation_numbers()` to parse citations from text
  - Each section includes `source_articles[]` array for the frontend
- **BLUF Rendered**: "Bottom Line Up Front" now displays in briefing header
  - Added `bluf` field to TypeScript types
  - Styled callout in `WeeklyBriefingSection.tsx`
- **Documentation**: Added generators README, updated CLAUDE.md with pipeline docs

### Session 9 - Logo.dev Fix & Briefing Review ✅
- **Logo.dev Integration Fixed**: Secret had trailing `\r` causing URL parsing error. Recreated clean secret.
- **Cloud Scheduler Jobs Fixed (Again)**: All 6 jobs were pointing to dead URL. Updated to `https://c1-hub-4iz75bvpyq-uc.a.run.app`
- **cloudbuild.yaml Updated**: Added `LOGO_DEV_TOKEN` to `--set-secrets` for future deployments
- **Code Review of Briefing Pipeline**: Identified improvements for source articles, historical context, BLUF display

### Session 8 - DRUMBEAT Feed Fix + FMP Premium News ✅
- **DRUMBEAT Fix**: JSON parsing error in `gcp_storage.py` - added `_safe_parse_list()` helper for inconsistent formats
- **FMP Fix**: `cloudbuild.yaml` referenced deleted secret `fmp-api-key` → changed to `FMP_API_KEY`
- **FMP Backfill**: 170 premium news articles from Benzinga, SeekingAlpha, Bloomberg, etc.
- **Note**: 403 errors during enrichment are expected (premium sites block scrapers) - FMP provides article text directly

### Session 7 - Scheduler & Earnings ✅
- **Earnings Backfill Complete** - 56 Q3 2025 transcripts found, 40 new stored
- **Cloud Scheduler Jobs Fixed** - All 6 jobs updated with correct URLs
- **Created WORKLOG.md** - Session continuity tracking

### Key Technical Context
- **Cloud Run URL**: `https://c1-hub-4iz75bvpyq-uc.a.run.app` (Service: `c1-hub`)
- **BigQuery dataset**: `gen-lang-client-0436975498.c1_intelligence`
- **MCP tools**: 48 loading correctly
- **Working sources**: SEC filings, FMP News, StockNews, RSS, Tavily, API Ninja Earnings
- **Secrets in Secret Manager**: ANTHROPIC_API_KEY, FMP_API_KEY, API_NINJA_KEY, TAVILY_API_KEY, EXA_API_KEY, LOGO_DEV_TOKEN
- FMP Premium News collector working

### Previous (January 4, 2026)
- **Deduplication migrated to BigQuery** - `DeduplicationService` now uses `gcp_storage.py` instead of SQLite
- Remaining SQLite usage: classifier/entity_linker entity loading, briefing generators
