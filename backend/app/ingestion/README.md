# Ingestion Pipeline

The data ingestion system for C1 Intelligence Hub. Collects, deduplicates, enriches, classifies, and stores articles from multiple sources into BigQuery.

> ⚠️ **CRITICAL**: Reliable ingestion is the foundation of the entire product. Without daily ingestion, the Pulse page goes stale, Deep Research has no context, and briefings have nothing to summarize.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         INGESTION ORCHESTRATOR                               │
│                         (orchestrator.py)                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────────┐   │
│  │  DATA COLLECTORS │  │   PROCESSING     │  │      STORAGE             │   │
│  │  (app/tools/)    │  │   PIPELINE       │  │                          │   │
│  │                  │  │                  │  │                          │   │
│  │  • RSS Feeds     │  │  1. Dedup        │  │  BigQuery Tables:        │   │
│  │  • Exa.ai (91)   │──▶│  2. Scraper     │──▶│  • articles              │   │
│  │  • Tavily (145)  │  │  3. Classifier   │  │  • digest_items          │   │
│  │  • SEC EDGAR     │  │  4. Entity Link  │  │  • article_chunk_embeddings │
│  │  • FMP News      │  │  5. Image Enrich │  │  • ingestion_events      │   │
│  │  • StockNews     │  │                  │  │  • freight_rates         │   │
│  │  • Drewry (WCI)  │  │                  │  │                          │   │
│  │  • Earnings      │  │                  │  │                          │   │
│  │  • Press Releases│  │                  │  │                          │   │
│  └──────────────────┘  └──────────────────┘  └──────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## ⏰ Cloud Scheduler Jobs (Production)

**GCP Project**: `gen-lang-client-0436975498`  
**Region**: `us-central1`  
**Canonical Definition**: [deploy/scheduler/deploy_jobs.ps1](../../../deploy/scheduler/deploy_jobs.ps1)

### Current Jobs (as of January 6, 2026)

| Job | Schedule (CST) | Schedule (UTC) | Timeout | Sources | Purpose |
|-----|----------------|----------------|---------|---------|---------|
| `ingest-flash-update` | Every 4 hours | Every 4 hours | 10 min | rss, freight | Fast RSS + freight updates |
| `ingest-exa` | 2:00 AM | 8:00 AM | 20 min | exa_queries, press_releases | Exa 91 queries + press releases |
| `ingest-tavily` | 2:20 AM | 8:20 AM | 25 min | tavily_queries | Tavily 145 queries |
| `ingest-financial` | 2:45 AM | 8:45 AM | 30 min | sec, earnings, fmp_news, stocknews | Financial data sources |
| `weekly-executive-briefing` | Mon 8:30 AM | Mon 14:30 | 15 min | (triggers briefing) | Weekly "Need to Know" report |

**Why Split By Search Engine?**
- Cloud Scheduler has a 30-minute maximum timeout
- Combined Exa+Tavily (236 queries) was taking 25-35 min, often exceeding timeout
- Splitting by search engine keeps each job well under 30 min
- 20-minute buffer between Exa and Tavily, 25-minute buffer before Financial
- All daily ingestion completes by ~3:15 AM CST (plenty of buffer before workday)

### The 10 Data Sources (Split Across Jobs)

| Source Key | Description | API/Method | BQ source_type |
|------------|-------------|------------|----------------|
| `exa_queries` | Exa 91 industry queries + per-company news | Exa neural search | `web_news_exa` |
| `tavily_queries` | Tavily 145 broadening queries | Tavily crawl | `web_news_tavily` |
| `industry_queries` | **Legacy** - runs both Exa + Tavily | Both | `web_news_exa`, `web_news_tavily` |
| `rss` | 14 industry RSS feeds | Feed parsing | `rss` |
| `sec` | SEC EDGAR filings (10-K, 10-Q, 8-K) | sec-api.io | `sec_filing` |
| `earnings` | Earnings call transcripts | API Ninja | `earnings_transcript` |
| `stocknews` | StockNews API articles | StockNews API | `stocknewsapi` |
| `fmp_news` | FMP Premium news (Benzinga, etc.) | FMP API | `premium_news` |
| `freight` | Drewry WCI freight rates | Web scraper | (stored in `freight_rates` table) |
| `press_releases` | Company press releases | Exa search | `web_news_exa` |

### API Endpoint

```
POST /api/v1/scheduler/ingest
Content-Type: application/json

{
  "sources": ["exa_queries", "tavily_queries", "rss", "sec", "earnings", "stocknews", "fmp_news", "freight", "press_releases"],
  "backfill_days": null
}
```

### ⚠️ Critical Configuration Notes

1. **Cloud Scheduler max timeout is 30 minutes (1800s)**
   - `ingest-deep-dive` uses the full 30 min
   - If ingestion exceeds 30 min, consider splitting into multiple jobs

2. **JSON body escaping for PowerShell → gcloud**:
   ```powershell
   # CORRECT: Use escaped quotes
   --message-body='{\"sources\": [\"rss\", \"stocknews\"]}'
   
   # WRONG: Unescaped quotes fail silently
   --message-body='{"sources": ["rss", "stocknews"]}'
   ```

3. **Always use `--update-headers` for job updates** (not `--headers`)

### Manual Trigger Commands

```powershell
# Test with single source (verify SDK fix works)
$body = '{"sources": ["rss"]}'
Invoke-RestMethod -Uri "https://c1-hub-4iz75bvpyq-uc.a.run.app/api/v1/scheduler/ingest" `
  -Method Post -Body $body -ContentType "application/json" -TimeoutSec 300

# Test Exa queries only (~15 min)
$body = '{"sources": ["exa_queries", "press_releases"]}'
Invoke-RestMethod -Uri "https://c1-hub-4iz75bvpyq-uc.a.run.app/api/v1/scheduler/ingest" `
  -Method Post -Body $body -ContentType "application/json" -TimeoutSec 1200

# Test Tavily queries only (~18 min)
$body = '{"sources": ["tavily_queries"]}'
Invoke-RestMethod -Uri "https://c1-hub-4iz75bvpyq-uc.a.run.app/api/v1/scheduler/ingest" `
  -Method Post -Body $body -ContentType "application/json" -TimeoutSec 1500

# Full ingestion (all sources) - takes 30-40 minutes total
$body = '{"sources": ["exa_queries", "tavily_queries", "rss", "sec", "earnings", "stocknews", "fmp_news", "freight", "press_releases"]}'
Invoke-RestMethod -Uri "https://c1-hub-4iz75bvpyq-uc.a.run.app/api/v1/scheduler/ingest" `
  -Method Post -Body $body -ContentType "application/json" -TimeoutSec 2400
```

### Job Management Commands

```powershell
# List all scheduler jobs
gcloud scheduler jobs list --location=us-central1 --project=gen-lang-client-0436975498

# Check job status
gcloud scheduler jobs describe ingest-exa --location=us-central1 --project=gen-lang-client-0436975498
gcloud scheduler jobs describe ingest-tavily --location=us-central1 --project=gen-lang-client-0436975498

# Pause a job (for maintenance)
gcloud scheduler jobs pause ingest-exa --location=us-central1 --project=gen-lang-client-0436975498

# Resume a job
gcloud scheduler jobs resume ingest-exa --location=us-central1 --project=gen-lang-client-0436975498

# Force-run a job now
gcloud scheduler jobs run ingest-exa --location=us-central1 --project=gen-lang-client-0436975498
```

### Deleted/Legacy Jobs (DO NOT RECREATE)

| Job Name | Reason for Removal |
|----------|-------------------|
| `ingest-web-search` | Split into `ingest-exa` + `ingest-tavily` (Jan 6, 2026) |
| `ingest-deep-dive` | Split into separate jobs (Jan 2026) |
| `daily-evening-ingest` | Redundant - subset of sources |
| `weekly-corpus-refresh` | Stub - did nothing (BigQuery has no periodic reindex) |
| `weekly-data-cleanup` | Stub - did nothing |
| `daily-morning-ingest` | Legacy - replaced by split jobs |
| `orchestrator-ingestion-morning` | Legacy naming |
| `orchestrator-ingestion-evening` | Legacy naming |

## Key Configuration

| Parameter | Value | Location |
|-----------|-------|----------|
| **Lookback Window** | 2 days | `orchestrator.py:207` |
| **Classifier Concurrency** | 10 concurrent | `classifier.py:295` |
| **Classifier Sleep** | 0.2s between calls | `classifier.py:303` |
| **Embedding Batch Size** | 5 chunks | `bq_vector_store.py:545` |
| **Insert Batch Size** | 5 rows | `bq_vector_store.py:607` |

## Processing Pipeline

1. **Deduplication** (`processing/deduplication.py`)
   - URL-based + content-hash dedup
   - Caches recent articles in memory
   - Persists to BigQuery for cross-run dedup

2. **Web Scraping** (`processing/scraper.py`)
   - Enriches articles with full text
   - Handles paywalls gracefully (403s expected)
   - Limits: 50 articles/run (200 for backfill)

3. **Classification** (`processing/classifier.py`)
   - Claude claude-sonnet-4-5 for high accuracy
   - 10 concurrent calls, 0.2s throttle
   - Outputs: category, priority, relevance, summary
   - **Uses `resilient_llm.py`** for Anthropic + OpenAI fallback

4. **Entity Linking** (`processing/linker.py`)
   - Links to tracked companies from BigQuery
   - Adds company metadata (ticker, type)

5. **Image Enrichment** (optional)
   - Tavily image search
   - Claude vision classification
   - Limit: 20 articles/run

## Feed Eligibility

Articles are **always stored** in BigQuery regardless of date. The `feed_eligible` flag controls visibility in the Drumbeat feed:

```python
feed_eligible = (
    article.published_at is not None AND
    article.published_at <= now AND           # Not future date
    article.published_at >= tier2_since       # Within lookback window
)
```

## Running Ingestion Locally

```python
# Full ingestion
from app.ingestion.orchestrator import IngestionOrchestrator, IngestionConfig
import asyncio

o = IngestionOrchestrator(IngestionConfig())
asyncio.run(o.run_full_ingestion())

# Specific sources only
asyncio.run(o.run_full_ingestion(sources=['rss', 'fmp_news']))

# Backfill mode (override lookback)
asyncio.run(o.run_full_ingestion(backfill_days=5))
```

## Directory Structure

```
ingestion/
├── orchestrator.py      # Main pipeline coordinator
├── config.py            # RSS feeds, keywords, entity lists
├── industry_queries.py  # 236 Exa/Tavily search queries
├── classifier.py        # Legacy (use processing/classifier.py)
├── fetchers/            # RSS fetcher
├── freight/             # Drewry WCI scraper
├── generators/          # Briefing generators (Agent 1 & 2)
├── importyeti/          # ImportYeti integration
└── processing/          # Core processing pipeline
    ├── classifier.py    # Claude-based classification
    ├── deduplication.py # URL + content dedup
    ├── linker.py        # Entity linking
    ├── scraper.py       # Web scraping/enrichment
    └── image_enrichment.py
```

## Performance (Jan 2026 Tuning)

| Metric | Before | After |
|--------|--------|-------|
| Lookback | 3 days | 2 days |
| Articles/run | 400-600 | 250-400 |
| Classification time | ~25 min | ~7-10 min |
| Total run time | ~35-40 min | ~15-20 min |

## Source Score Boost

The classifier applies a relevance score boost based on source quality tier. This helps prioritize articles from authoritative composites and business sources.

| Tier | Boost | Sources |
|------|-------|---------|
| **Tier 1: Core Composites** | +0.15 | CompositesWorld, JEC Composites, Composites Manufacturing, composites.media |
| **Tier 2: Premium Business** | +0.10 | Reuters, WSJ, Barron's, Financial Times, Bloomberg |
| **Tier 3: Quality Sector** | +0.05 | Aviation Week, Defense News, FreightWaves, Supply Chain Dive, Seeking Alpha, Flight Global, CNBC, Manufacturing Dive, Plastics News |

**How it works:**
1. Claude assigns base `relevance_score` (0.0-1.0)
2. Source boost is applied based on partial name matching
3. Final score is capped at 1.0

**Example:** An article from CompositesWorld with base score 0.7 → final score 0.85

See `processing/classifier.py` for the full `SOURCE_SCORE_BOOSTS` dictionary.

## Blocked Sources

Articles from low-quality or irrelevant sources are filtered out entirely before classification (saves API costs and improves signal quality).

| Category | Examples | Reason |
|----------|----------|--------|
| **Aggregators** | TradingView, Morningstar, GuruFocus | Repackaged content |
| **Social/Noise** | Wikipedia, YouTube, LinkedIn, Reddit, Twitter | Not news sources |
| **E-commerce** | Amazon, eBay, Alibaba | Not news |
| **AI Search** | Perplexity | Not primary sources |
| **Paywalled Teasers** | GrandViewResearch, MarketsAndMarkets, Mordor Intelligence, etc. | Just subscription prompts |

Blocked articles are logged but not classified or stored.

See `processing/classifier.py` for the full `BLOCKED_SOURCES` set.

---

## 🔧 Troubleshooting

### Common Issues & Fixes

| Symptom | Cause | Fix |
|---------|-------|-----|
| HTTP 422 from scheduler job | Malformed JSON body | Escape quotes: `'{\"sources\": [\"rss\"]}'` |
| DEADLINE_EXCEEDED | Timeout too short | Set to 1800s (30 min max) |
| "system: Input should be a valid list" | Anthropic SDK bug | Fixed in `resilient_llm.py` (Jan 2026) |
| Articles with future dates (2026+) | Exa API returns projection dates | Fixed in `orchestrator.py` - validates dates |
| Articles stored without classification | Classification failing silently | Check Cloud Run logs for errors |
| Job shows "PAUSED" state | Manually paused for maintenance | Resume with `gcloud scheduler jobs resume` |
| No articles from source X | Source disabled in job config | Check `sources` array in job body |

### Monitoring Commands

```powershell
# Check recent Cloud Run logs for errors
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=c1-hub AND severity>=ERROR" --limit=50 --project=gen-lang-client-0436975498

# Check scheduler job execution history
gcloud scheduler jobs describe ingest-web-search --location=us-central1 --format="yaml(state,lastAttemptTime,status)"
gcloud scheduler jobs describe ingest-financial --location=us-central1 --format="yaml(state,lastAttemptTime,status)"

# Query recent ingestion counts in BigQuery
bq query --use_legacy_sql=false "
SELECT DATE(fetched_at) as date, COUNT(*) as count, source_type
FROM \`gen-lang-client-0436975498.c1_intelligence.articles\`
WHERE fetched_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 3 DAY)
GROUP BY date, source_type
ORDER BY date DESC, count DESC
"
```

### Health Check Scripts

```bash
# Comprehensive health check
python backend/scripts/health/ingestion_health_check.py --days 7

# Production dashboard (includes log analysis)
python backend/scripts/monitoring/production_dashboard.py --detailed
```

### Critical Bug History (For Future Reference)

**January 6, 2026 - Exa API Future Date Validation**
- **Symptom**: Articles appearing with future dates (May 2026, Sep 2026) in BigQuery
- **Cause**: Exa API incorrectly extracts projection dates from market research pages (e.g., "expected to reach $X by 2026") as publication dates
- **Fix**: Added validation to reject dates > `utcnow() + 2 days` in orchestrator and press_releases collector
- **Files**: `orchestrator.py` (`_convert_search_result_to_article`), `app/tools/press_releases/collector.py`
- **Behavior**: Articles with rejected dates get `published_at=None` → stored but `feed_eligible=False`

**January 6, 2026 - Anthropic SDK `system` Parameter**
- **Symptom**: All classification calls failing with "system: Input should be a valid list"
- **Cause**: Anthropic SDK 0.75.0 rejects `system=None` parameter
- **Fix**: Conditionally include `system` in kwargs only when provided
- **File**: `backend/app/utils/resilient_llm.py` (see `messages_create` method)

**January 7, 2026 - Timezone Comparison Error**
- **Symptom**: `TypeError: can't compare offset-naive and offset-aware datetimes` during web search
- **Cause**: `_is_future_date()` used `datetime.now()` (naive) but Exa returns timezone-aware dates
- **Fix**: Changed to `datetime.now(timezone.utc)` in `date_extraction.py`
- **File**: `backend/app/utils/date_extraction.py`

**January 7, 2026 - Cloud Run Liveness Probe Killing Long Jobs**
- **Symptom**: Ingestion jobs killed mid-execution, scheduler shows code 14 (UNAVAILABLE)
- **Cause**: Liveness probe timeout was 20 min (10 × 2 min), jobs take 25-35 min
- **Fix**: Increased to 60 min tolerance: `periodSeconds=300, failureThreshold=12`
- **Command**: `gcloud run services update c1-hub --liveness-probe="httpGet.path=/health,..."`

---

*Last updated: January 7, 2026*


