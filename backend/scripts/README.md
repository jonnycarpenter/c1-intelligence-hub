# Scripts Directory

Operational scripts organized by purpose. **Use this index to find the right script for your task.**

---

## 📊 Monitoring (Production Diagnostics)

**Location**: `monitoring/`

| Script | Purpose | When to Use |
|--------|---------|-------------|
| `scheduler_report.py` | **PRIMARY** daily health report | Check ingestion pipeline health, view stats |
| `production_dashboard.py` | Production metrics dashboard | Monitor production deployment |
| `compare_prod_data.py` | Compare prod vs local data | Debug data discrepancies |
| `query_bq_detailed.py` | Detailed BigQuery queries | Ad-hoc data exploration |

**Most Common**: `python scripts/monitoring/scheduler_report.py`

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
- `backfill_bq_dates.py` - Backfill missing dates in BigQuery
- `backfill_bq_embeddings.py` - Regenerate embeddings
- `backfill_dates.py` - Backfill article dates
- `backfill_tags.py` - Backfill entity tags

### Maintenance (`operations/maintenance/`)
- `fix_bad_timestamps.py` - Fix malformed timestamps
- `purge_data.py` - Clean up old/bad data
- `seed_bigquery.py` - Initialize BigQuery tables

### Triggers (`operations/triggers/`)
- `manual_trigger_ingest.py` - Manually trigger ingestion
- `trigger_backfill.py` - Trigger backfill job
- `trigger_synthesis.py` - Trigger briefing synthesis
- `load_companies.py` - Load company data

---

## 🧪 Testing (Development Tests)

**Location**: `testing/`

Ad-hoc test scripts for development:
- `test_briefing.py` - Test briefing generation
- `test_earnings.py` - Test earnings collection
- `test_ingestion_new_tools.py` - Test new ingestion sources
- `test_pulse_api.py` - Test Pulse API endpoints
- `test_tools.py` - Test MCP tools

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

**Daily health check**:
```bash
python scripts/monitoring/scheduler_report.py
```

**Trigger manual ingestion**:
```bash
python scripts/operations/triggers/manual_trigger_ingest.py
```

**Backfill missing data**:
```bash
python scripts/operations/triggers/trigger_backfill.py
```

**Test after deployment**:
```bash
python scripts/verification/verify_enhancements.py
```
