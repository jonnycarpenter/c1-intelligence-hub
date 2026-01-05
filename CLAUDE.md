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
| **Pre-Brief Generator (Agent 1)** | `app/ingestion/generators/pre_briefing.py` |
| **Weekly Briefing Generator (Agent 2)** | `app/ingestion/generators/weekly_briefing.py` |

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
