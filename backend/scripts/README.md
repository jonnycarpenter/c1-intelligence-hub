# Scripts Directory

Operational scripts organized by purpose. **Use this index to find the right script for your task.**

---

## 📊 Monitoring (Production Diagnostics)

**Location**: `monitoring/`

| Script | Purpose | When to Use |
|--------|---------|-------------|
| `production_dashboard.py` | **PRIMARY** unified health dashboard | Daily monitoring (runs health check + optional log analysis) |
| `scheduler_report.py` | Cloud Run log analysis | Deep dive into scheduler execution logs |
| `compare_prod_data.py` | Compare prod vs local data | Debug data discrepancies |
| `query_bq_detailed.py` | Detailed BigQuery queries | Ad-hoc data exploration |

**Quick Check** (30 sec):
```bash
python scripts/monitoring/production_dashboard.py
```

**Full Analysis** (3-5 min):
```bash
python scripts/monitoring/production_dashboard.py --detailed
```

---

## 🏥 Health Checks (Diagnostics)

**Location**: `health/`

| Script | Purpose |
|--------|---------|
| `ingestion_health_check.py` | Comprehensive ingestion diagnostics |
| `check_ingestion_history.py` | View ingestion run history |
| `check_pipeline_health.py` | Pipeline status check |
| `check_bad_dates.py` | Find articles with date issues |
| `check_config.py` | Verify configuration |
| `check_db.py` | Database connectivity check |

**Most Common**: `python scripts/health/ingestion_health_check.py`

---

## ⚙️ Operations (Data Operations)

**Location**: `operations/`

### Backfill (`operations/backfill/`)
- `backfill_industry_queries.py` - **Backfill industry queries** (91 Exa + 145 Tavily)
- `backfill_sec_filings.py` - **Backfill SEC filings** (10-K, 10-Q, 8-K)
- `backfill_press_releases.py` - **Backfill press releases** via Exa.ai
- `backfill_digest_items.py` - **Backfill digest items**
- `backfill_bq_dates.py` - Backfill missing dates in BigQuery
- `backfill_bq_embeddings.py` - Regenerate embeddings
- `backfill_dates.py` - Backfill article dates
- `backfill_tags.py` - Backfill entity tags

**Source-specific backfills** (use after outages or API issues):
```bash
# Industry queries (236 queries: 91 Exa + 145 Tavily)
python scripts/operations/backfill/backfill_industry_queries.py --days 7

# SEC filings (rate-limited, ~1 req/sec)
python scripts/operations/backfill/backfill_sec_filings.py --days 7

# Press releases via Exa.ai (company-specific searches)
python scripts/operations/backfill/backfill_press_releases.py --days 7

# FMP Premium News (Benzinga, SeekingAlpha, Bloomberg, etc.)
python scripts/operations/backfill/backfill_premium_news.py --days 30
```

### Maintenance (`operations/maintenance/`)
- `fix_bad_timestamps.py` - Fix malformed timestamps
- `purge_data.py` - Clean up old/bad data
- `seed_bigquery.py` - Initialize BigQuery tables
- `migrate_sqlite_to_bq.py` - Migrate SQLite data to BigQuery (legacy)

### Triggers (`operations/triggers/`)
- `manual_trigger_ingest.py` - Manually trigger ingestion
- `trigger_ingest.py` - Trigger ingestion pipeline
- `ingestion_pipeline.py` - Main ingestion pipeline orchestrator
- `trigger_backfill.py` - Trigger backfill job
- `trigger_synthesis.py` - Trigger briefing synthesis
- `load_companies.py` - Load company data

---

## 🧪 Testing (Development Tests)

**Location**: `testing/`

Ad-hoc test scripts for development:

### General Tests
- `test_agent_direct.py` - Test agent behavior directly
- `test_deep_research.py` - Test deep research workflow
- `test_endpoints.py` - Test API endpoints
- `test_general.py` - General system tests
- `test_stream.py` - Test streaming functionality
- `test_sse_frontend.py` - Test server-sent events
- `test_trace.py` - Test LangSmith tracing
- `test_workflow.py` - Test workflow orchestration

### Ingestion & Data Tests
- `test_enrichment.py` - Test data enrichment
- `test_ingest.py` - Test ingestion pipeline
- `test_ingestion_new_tools.py` - Test new ingestion sources
- `test_bigquery_migration.py` - Test BigQuery migrations
- `test_parallel_fix.py` - Test parallel processing fixes

### Data Source Tests
- `test_api_ninja_tickers.py` - Test API Ninja integration
- `test_compositesworld.py` - Test CompositesWorld scraping
- `test_datasheets_api.py` - Test datasheets API
- `test_earnings.py` - Test earnings collection
- `test_fmp_endpoints.py` - Test Financial Modeling Prep endpoints
- `test_fmp_v4.py` - Test FMP v4 API
- `test_press.py` - Test press release collection
- `test_sec_only.py` - Test SEC filing collection
- `test_tavily_dates.py` - Test Tavily date extraction

### Briefing & Digest Tests
- `test_briefing_sessions.py` - Test briefing session management
- `test_podcast_init.py` - Test podcast initialization
- `test_prebriefing_bq.py` - Test pre-briefing generation
- `test_weekly_briefing.py` - Test weekly briefing generation

### MCP Tools Tests
- `test_tools.py` - Test MCP agent tools
- `all_tools_reference.py` - Reference of all available tools

### Health/Check Scripts
- `check_bq_status.py` - Check BigQuery status
- `check_db.py` - Check database connectivity
- `check_digest_data.py` - Check digest data
- `check_digest_items.py` - Check digest items
- `check_digest_service.py` - Check digest service
- `check_earnings_urls.py` - Check earnings URLs
- `check_lowium_bug.py` - **Check digest priority distribution** (data quality)
- `check_rss.py` - Check RSS feed health
- `check_sqlite.py` - Check SQLite (legacy)
- `check_sqlite_counts.py` - Check SQLite counts (legacy)

### Debug & Utility Scripts
- `debug_import.py` - Debug import issues
- `industry_queries_expanded_v2.py` - Industry query definitions
- `query_bq_temp.py` - Ad-hoc BigQuery queries

**Quick Commands**:
```bash
# Digest data quality check
python scripts/testing/check_lowium_bug.py

# Test briefing generation
python scripts/testing/test_briefing_sessions.py

# Test ingestion
python scripts/testing/test_ingest.py

# Check database health
python scripts/testing/check_db.py
```

---

## ✅ Verification (Post-Deploy Checks)

**Location**: `verification/`

Run after deployments to verify features:
- `verify_backfill_results.py` - Verify backfill completed
- `verify_enhancements.py` - Verify new features work
- `verify_headline_pills.py` - Verify UI pill formatting
- `verify_source_type.py` - Verify source classification

---

## 🗄️ Archive (Deprecated)

**Location**: `archive/`

**DO NOT USE** - These are from the SQLite/ChromaDB era:
- `check_sqlite_dates.py` ❌ SQLite (deprecated)
- `reindex_chromadb.py` ❌ ChromaDB (deprecated)
- `sync_sqlite_to_bigquery.py` ❌ Migration (deprecated)

---

## Quick Reference

**Daily health check** (recommended):
```bash
python scripts/monitoring/production_dashboard.py
```

**Backfill industry queries** (Exa + Tavily):
```bash
python scripts/operations/backfill/backfill_industry_queries.py --days 7
```

**Backfill earnings transcripts** (API Ninja - Q3 2025):
```bash
# Via orchestrator
python -c "import asyncio; from app.ingestion.orchestrator import *; asyncio.run(IngestionOrchestrator(IngestionConfig()).run_earnings_only(year=2025, quarter=3))"
```

**Trigger manual ingestion**:
```bash
python scripts/operations/triggers/manual_trigger_ingest.py
```

**Test after deployment**:
```bash
python scripts/verification/verify_enhancements.py
```

---

## Active Data Sources (Jan 2026)

| Source | Type | Coverage |
|--------|------|----------|
| RSS | Industry news feeds | Multiple composites/materials publications |
| SEC Filings | 10-K, 10-Q | ~50 tracked public companies |
| API Ninja Earnings | Q3 2025 transcripts | 35/48 companies (73% coverage) |
| FMP Premium News | Benzinga, Seeking Alpha | All tracked companies |
| StockNews API | Market news | Ticker-based queries |
| Exa.ai | Web search | 91 industry queries |
| Tavily | Web search | 145 industry queries |
