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
gcloud builds submit --config=cloudbuild.yaml --region=us-central1 --project=$GCP_PROJECT_ID
```

**Trigger Briefing Generation** (PowerShell):
```powershell
Invoke-RestMethod -Uri "https://<CLOUD_RUN_URL>/api/v1/scheduler/briefing" -Method POST -ContentType "application/json" -Body '{}'
```

**Cloud Run URL**: Set after first deployment via `gcloud run services describe c1-hub --region=us-central1`
**Service Name**: `c1-hub`

### Adding New Secrets

When adding a new API key/secret:
1. Create in Secret Manager (no trailing newlines!):
   ```powershell
   $key = "your-key-value"
   $key | gcloud secrets create SECRET_NAME --data-file=- --project=$GCP_PROJECT_ID
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
| **Visual Research agent** | `app/agents/research/visual.py` |
| **Corpus visuals search tool** | `app/mcp/tools/corpus_visuals.py` |
| **Article images table** | BigQuery `article_images` - classified images from ingestion |
| **Podcast streaming endpoint** | `app/api/routes/podcast.py` |
| **Podcast generation (weekly)** | `app/ingestion/generators/weekly_briefing.py` *(uses ElevenLabs Text-to-Dialogue API)* |
| **Pipeline agent** | `app/agents/pipeline/agent.py` |
| **Pipeline search tools** | `app/mcp/tools/pipeline_search.py` |
| **Pipeline filters (post-enrichment)** | `app/agents/pipeline/filters.py` |
| **Eval suite (token tracking)** | `app/evals/token_tracker.py` |
| **Eval suite (quality metrics)** | `app/evals/quality_metrics.py` |
| **Feedback API** | `app/api/routes/feedback.py` |

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
| **`backend/app/agents/pipeline/README.md`** | **Pipeline (sales prospecting) tab** | **Modifying pipeline tools/filters** |
| **`backend/app/evals/README.md`** | **Eval suite (token tracking, quality, feedback)** | **Adding eval components** |
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
- **LLM Naturalization**: Deterministic scaffold → Claude Sonnet rewrites into natural conversation
- Natural "net new" vs "continuing" phrasing
- Text formatting: "$2.4B" → "2.4 billion dollars", abbreviations expanded
- Voices: Host (Rachel) + Analyst (Josh) via Text-to-Dialogue API
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
| `llm_token_usage` | **Token/cost tracking** - per-call token counts, estimated cost, model, caller module |
| `eval_results` | **LLM-as-judge scores** - factual grounding, coherence, actionability ratings per report |
| `user_feedback` | **User feedback** - thumbs up/down ratings with optional comments on reports |

## Don't Touch (Bug Fix Protected)

These files have critical bug fixes - be careful editing:
- `app/db/gcp_storage.py` - feed_eligible logic, dedup methods
- `app/models/corpus.py` - feed_eligible field

## LLM Models & Resilience

### Primary Models (Anthropic)
| Use Case | Model | Location |
|----------|-------|----------|
| Deep Research agents | `claude-opus-4-5` | `app/agents/research/*.py` (groomer stays on haiku) |
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

## Development History

This project was built iteratively over 70+ AI-assisted coding sessions (Jan–Feb 2026). Key milestones:

- **Sessions 7–14**: Core data pipeline — BigQuery migration, ingestion tuning, digest system
- **Sessions 17–20**: Ad-hoc briefing session management, ingestion throughput optimization
- **Sessions 23–29**: Deep Research multi-agent workflow (LangGraph parallel execution, SSE streaming, BigQuery persistence)
- **Sessions 30–32**: Frontend UX polish, podcast generation, saved reports UI
- **Sessions 41–52**: Conversational UX, progress events, Visual Research agent
- **Sessions 60–72**: Interactive Architecture tab (React Flow), weekly briefing enhancements

See commit history for detailed changes.
