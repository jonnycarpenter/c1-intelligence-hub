# C1 Intelligence Hub - AI Agent Instructions

## Session Continuity

**At end of session**: Update `WORKLOG.md` with:
1. What was completed
2. What's still in progress
3. Open items / next steps
4. Any key technical context discovered

**At start of session**: Read `WORKLOG.md` for recent context.

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
4. **Test before committing**:
   ```bash
   cd backend
   python -c "from app.mcp.server import get_all_mcp_tools; print(len(get_all_mcp_tools()))"
   ```

## Deployment

**CI/CD Pipeline**: Git push to `main` → GitHub → Cloud Build Trigger → Cloud Run

**Region**: `us-central1` (always)

**Production Deployment** (preferred - via git):
```bash
git add .
git commit -m "Description of changes"
git push origin main
# Cloud Build trigger auto-deploys to Cloud Run
```

**Manual Deploy** (if needed):
```bash
gcloud builds submit --config=cloudbuild.yaml --region=us-central1 --project=gen-lang-client-0436975498
```

**Cloud Run URL**: `https://c1-hub-4iz75bvpyq-uc.a.run.app`
**Service Name**: `c1-hub`

### Adding New Secrets

When adding a new API key/secret:
1. Create in Secret Manager (no trailing newlines!):
   ```bash
   echo -n "your-key-value" | gcloud secrets create SECRET_NAME --data-file=- --project=gen-lang-client-0436975498
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
| **Ad-hoc briefing session manager** | `app/agents/adhoc_briefing/session_manager.py` |
| **Pre-Brief Generator (Agent 1)** | `app/ingestion/generators/pre_briefing.py` |
| **Weekly Briefing Generator (Agent 2)** | `app/ingestion/generators/weekly_briefing.py` |

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
| `backend/scripts/README.md` | Script directory index | Adding new scripts |
| `backend/scripts/monitoring/README.md` | Production monitoring scripts | Adding monitoring scripts |
| `backend/scripts/health/README.md` | Health check scripts | Adding health checks |
| `backend/scripts/operations/README.md` | Data operations (backfills, maintenance) | Adding operations scripts |
| `backend/scripts/testing/README.md` | Ad-hoc test scripts | Adding test scripts |
| `backend/scripts/verification/README.md` | Post-deployment verification | Adding verification scripts |
| `backend/scripts/archive/README.md` | Deprecated scripts (DO NOT USE) | Moving scripts to archive |
| `deploy/README.md` | GCP deployment configuration | Infra/deployment changes |

## Weekly Briefing Pipeline (2-Agent Architecture)

The weekly "Need to Know" executive briefing uses a 2-agent pipeline:

```
Agent 1 (Pre-Brief)              Agent 2 (Synthesis)
claude-sonnet-4-5                 claude-opus-4-5
        │                               │
        ▼                               ▼
┌─────────────────┐            ┌─────────────────┐
│ Analyze 50 most │            │ Compare against │
│ recent articles │ ────────►  │ historical ctx  │
│ from 14 days    │            │ + Exa search    │
└─────────────────┘            └─────────────────┘
        │                               │
        ▼                               ▼
  Pre-Brief JSON              Final Briefing JSON
  (observations,              (sections, BLUF,
   signal_types)               source_articles)
```

**Key Features:**
- **Source Articles**: Each section includes `source_articles[]` with clickable links
- **BLUF**: "Bottom Line Up Front" single-sentence summary
- **Inline Logos**: `[[Company Name]]` tags render with Logo.dev images
- **Net New vs Continuing**: Badges show if topic is new or continuing from prior weeks
- **Exa Peripheral Search**: Agent 2 can search for adjacent intelligence

**Schedule**: Monday 8:30 AM CST via Cloud Scheduler (`weekly-executive-briefing` job)

## Key BigQuery Tables

| Table | Purpose |
|-------|---------|
| `articles` | Raw articles (source of truth) |
| `article_chunk_embeddings` | **Vector store** - Vertex AI embeddings for semantic search |
| `digest_items` | Classified articles with summaries |
| `article_tags` | Normalized tags for trending analytics |
| `companies` | Tracked companies (tickers, names) |

## Don't Touch (Bug Fix Protected)

These files have critical bug fixes - be careful editing:
- `app/db/gcp_storage.py` - feed_eligible logic, dedup methods
- `app/models/corpus.py` - feed_eligible field

## Recent Changes (January 5, 2026)

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
