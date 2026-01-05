# C1 Intelligence Hub - Work Log

This file tracks completed work and open items across AI assistant sessions.

---

## Session 9 (January 5, 2026)

### ✅ Completed

1. **Comprehensive Code Review of Briefing Workflow**
   - Reviewed the 2-agent pipeline: PreBriefGenerator (Agent 1) → WeeklyBriefingGenerator (Agent 2)
   - Agent 1 (claude-sonnet-4-5): Analyzes 50 articles from last 14 days, produces structured observations with signal_type
   - Agent 2 (claude-opus-4-5): Synthesizes with Exa.ai peripheral search, produces strategic briefing sections
   - Identified 6 improvement areas (see Open Items below)

2. **Cloud Scheduler Jobs Fixed (AGAIN)** 🚨
   - All 6 scheduler jobs were pointing to DEAD URL: `c1-intelligence-hub-285931707029.us-central1.run.app`
   - The correct URL is: `https://c1-hub-4iz75bvpyq-uc.a.run.app`
   - Updated all jobs with correct URL and OIDC audience
   - Jobs affected: `weekly-executive-briefing`, `ingest-deep-dive`, `ingest-flash-update`, `daily-evening-ingest`, `weekly-data-cleanup`, `weekly-corpus-refresh`

3. **Logo.dev Integration Fixed** ✅
   - **Root Cause**: `LOGO_DEV_TOKEN` secret in Secret Manager had trailing carriage return (`\r`)
   - This caused: `Invalid non-printable ASCII character in URL, '\r' at position 86`
   - **Fix**: Created clean version 3 of secret without `\r`, forced Cloud Run revision update
   - All logo domains now return 200 with valid PNG bytes
   - Tested: `airbus.com`, `boeing.com`, `compositesone.com`, `spiritaero.com`, `hexcel.com` all working

4. **cloudbuild.yaml Updated**
   - Added `LOGO_DEV_TOKEN=LOGO_DEV_TOKEN:latest` to `--set-secrets` line
   - Future git-push deployments will now include the logo token

### 📋 Open Items / To Do (from Code Review)

| Priority | Issue | Description |
|----------|-------|-------------|
| 🟡 Medium | **Source Articles Not Linked** | `source_articles` field in briefing sections is not populated - citations `[1]`, `[2]` reference articles but no clickable links |
| 🟡 Medium | **Historical Context Too Sparse** | Agent 2 only gets topic list from previous briefings, not actual headlines - limits narrative continuity |
| 🟡 Medium | **BLUF Not Rendered** | Agent generates `bluf` field but frontend doesn't display it |
| 🟡 Medium | **Ad-hoc Briefing Stateless** | `AdHocBriefingAgent.follow_up_count` resets each request - can't track multi-turn conversations |
| 🟢 Low | **Convert to Native Claude Tools** | Currently uses custom JSON format for tool calls - could use native Anthropic tool use |
| 🟢 Low | **Domain Resolution Heuristics** | `company_name_to_domain()` guesses domains - could add more known mappings or use lookup API |

### 🔧 Infrastructure Notes

- **Cloud Run Service**: `c1-hub` at `https://c1-hub-4iz75bvpyq-uc.a.run.app`
- **Cloud Build Trigger**: GitHub push to `main` triggers build (configured in GCP Console)
- **Secrets in Secret Manager**: ANTHROPIC_API_KEY, FMP_API_KEY, API_NINJA_KEY, TAVILY_API_KEY, EXA_API_KEY, LOGO_DEV_TOKEN (now clean)

---

## Session 8 (January 5, 2026)

### ✅ Completed

1. **DRUMBEAT Feed Fix - JSON Parsing Error** 🎉
   - **Root Cause**: `companies`, `industries`, `materials`, `topics` fields in BigQuery had inconsistent formats:
     - Some rows stored as JSON arrays: `'["Tesla", "Boeing"]'`
     - Other rows stored as comma-separated strings: `'Tesla, Boeing'`
   - The code used `json.loads()` which crashed on comma-separated strings
   - **Fix**: Added `_safe_parse_list()` helper function that handles both formats
   - Applied fix to `get_digest_items()` and 4 other methods in [gcp_storage.py](backend/app/db/gcp_storage.py)
   - **Result**: Digest items now load correctly (644 items in last 7 days)

2. **Deployment Cleanup**
   - Deleted duplicate `deploy/cloudbuild.yaml` - consolidated to root `cloudbuild.yaml`
   - Updated `CLAUDE.md` with correct deployment instructions and Cloud Run URL
   - **Correct Cloud Run URL**: `https://c1-hub-4iz75bvpyq-uc.a.run.app`
   - **Service Name**: `c1-hub` (NOT `c1-intelligence-hub`)

3. **FMP Premium News Backfill Script**
   - Created `backend/scripts/operations/backfill/backfill_premium_news.py`
   - Uses `/api/v1/scheduler/ingest` with `sources: ["fmp_news"]`

4. **FMP Premium News FIXED & Backfilled** 🎉 (Session 8b)
   - **Root Cause**: `cloudbuild.yaml` referenced deleted secret name `fmp-api-key` but secret was renamed to `FMP_API_KEY`
   - **Fix**: Updated `cloudbuild.yaml` line 63 from `FMP_API_KEY=fmp-api-key:latest` to `FMP_API_KEY=FMP_API_KEY:latest`
   - **Deploy**: Deployed fix via Cloud Build
   - **Backfill Results**:
     - 170 `premium_news` articles stored in `articles` table
     - 170 `premium_news` items in `digest_items` table
   - **Note**: 403 errors during enrichment are expected - Benzinga/SeekingAlpha/Bloomberg block scrapers. FMP provides article text directly so this doesn't affect data quality.

### ✅ All Session 8 Items Complete

| Task | Status |
|------|--------|
| DRUMBEAT Feed Fix (JSON parsing) | ✅ Deployed |
| FMP Secret Reference Fix | ✅ Deployed |
| FMP 30-day Backfill | ✅ 170 articles |

---

## Session 7 (January 5, 2026)

### ✅ Completed

1. **API Ninja Earnings Re-enabled & Backfilled**
   - Confirmed endpoint works (tested with GCTAF ticker)
   - Tested all 48 tracked tickers for Q3 2025 transcripts
   - Added `collect_for_quarter()` method to earnings collector for direct quarter fetch
   - Fixed `run_earnings_only()` method:
     - Changed `list_companies()` → `get_companies()`
     - Fixed `await get_storage()` (was missing await)
     - Fixed field name: `stock_ticker` → `ticker`
     - Added filter to exclude `'private'` companies
   - **Backfill Results**: 56 Q3 2025 transcripts found, 40 new stored (16 dupes)

2. **Cloud Scheduler Jobs Fixed** 🚨
   - All 6 jobs were pointing to OLD Cloud Run URL (`c1-hub-4iz75bvpyq-uc.a.run.app`)
   - Updated all to new URL: `https://c1-intelligence-hub-285931707029.us-central1.run.app`
   - Updated OIDC audience to match new URL
   - Jobs updated:
     - `daily-evening-ingest` (2 AM daily)
     - `ingest-flash-update` (every 4 hours)
     - `ingest-deep-dive` (8 AM daily)
     - `weekly-executive-briefing` (Monday 2:30 PM)
     - `weekly-data-cleanup` (Sunday 2 AM)
     - `weekly-corpus-refresh` (Sunday 3 AM)

3. **Created WORKLOG.md** - Session continuity system
   - Added instructions to CLAUDE.md to read/update WORKLOG.md
   - Tracks completed work, in-progress, and open items

4. **Documentation Updates**
   - Updated `CLAUDE.md` with Session 7 changes and session continuity instructions
   - Updated `scripts/README.md` with new quick reference and data sources table
   - Updated `scripts/monitoring/README.md` to focus on production_dashboard
   - Fixed `production_dashboard.py` to find health check in correct directory

5. **Monitoring Script Improvements**
   - Added `premium_news` (FMP News) to `ingestion_health_check.py`
   - Fixed source type `stocknews` → `stocknewsapi`
   - Updated display to show 9 sources (was 8)

### 🔄 In Progress

1. **DRUMBEAT Feed Investigation** - Started investigating why digest cards not loading

### 📋 Open Items / Next Steps

1. **🚨 DRUMBEAT Feed Not Loading** - Digest cards not showing in app's 7-day news feed
   
   **Investigation Progress (Session 7):**
   - ✅ Data EXISTS in BigQuery: 3,597 rows in `digest_items`, 645 in last 7 days
   - ✅ `feed_eligible=True` for 3,574 items (only 23 are False)
   - ✅ Items by source in last 7 days: web_news (287), web_news_exa (159), stocknewsapi (156), rss (35), etc.
   
   **ROOT CAUSE IDENTIFIED:**
   - `backend/app/db/gcp_storage.py` has TWO storage classes:
     - `LocalDataStorage` (line 254) - Uses SQLite
     - `BigQueryDataStorage` (line 662) - Uses BigQuery
   - Both have `get_digest_items()` method
   - The `get_data_storage()` function (line 2865) checks `gcp_config.is_configured`
   - **HYPOTHESIS**: Locally or in production, it might be falling back to SQLite which has NO data
   
   **Next Steps:**
   - Test which storage type is being used: `type(storage).__name__`
   - Check `gcp_config.is_configured` value in production
   - If BigQuery, check if the query filters are excluding items (date filters, confidence, etc.)
   - The BigQuery `get_digest_items` has complex filters:
     - `published_at >= cutoff_time` (lookback hours)
     - `published_at <= now` (not future)
     - `confidence >= 0.3`
     - `ingested_at >= '2025-12-28'`
     - Complex `classified_at` vs `published_at` check (30 min diff)
   
   **Key Files:**
   - `backend/app/db/gcp_storage.py` - Storage backends (lines 536-620 SQLite, lines 2626-2720 BigQuery)
   - `backend/app/services/digest_service.py` - `get_digest()` method (line 102)
   - `backend/app/api/routes/digest.py` - API endpoint (line 28)
   - `frontend/src/hooks/useDigest.ts` - Frontend hook
   - `frontend/src/lib/api.ts` - API client (line 119: `/api/digest`)

2. **Re-run Industry Queries Backfill** - Previous run got stuck
   - Try with smaller batch: `--days 2` or `--days 3`

3. **Consider Q4 2024 Earnings** - Could also backfill Q4 2024 for more historical data

4. **Earnings in Daily Scheduler** - Decide if/how to add earnings to scheduled runs
   - API Ninja is quarter-based, not daily
   - May need custom logic: "fetch current quarter's earnings for any new filings"

### 🔑 Key Technical Context

- **BigQuery dataset**: `gen-lang-client-0436975498.c1_intelligence`
- **MCP tools**: 48 loading correctly
- **Companies table**: `stock_ticker` column → converted to `ticker` in Python via `get_companies()`
- **Earnings URL format**: `earnings://{ticker}/{year}/Q{quarter}` (unique for dedup)

### Companies WITH Q3 2025 Earnings (35)
VMC, MLM, CRH, GVA, PWR, MTZ, PRIM, SKBSY, ACM, J, FLR, SGL.DE, HXL, BA, EADSY, ERJ, RTX, NOC, LMT, GD, GE, RKLB, VWDRY, GEV, NRDXF, BC, RACE, FINMY, TXT, JOBY, ACHR, MBUU, MCFT, F, GM

### Companies WITHOUT Q3 2025 Earnings (13)
SUM, TINLY, GURN.SW, SOLVY, TRYIY, BAESY, SAFRY, RYCEY, GCTAF, BEN.PA, BMWYY, BDRBF, TM

---

## Session 6 (January 5, 2026)

### ✅ Completed
- SEC Filings headline fix - Added `headline` column to BigQuery `digest_items` table
- Archived API Ninja earnings (9 rows) - Bad URL templates caused dedup collisions
- FMP Premium News collector working - `app/tools/fmp_news/`
- SEC filings working - 45 in articles, 67 in digest_items
- Removed FMP Earnings code - Deleted `app/tools/fmp_earnings/` (requires premium)

---

## Session 5 and Earlier (January 4, 2026)

### ✅ Completed
- Deduplication migrated to BigQuery
- `DeduplicationService` now uses `gcp_storage.py` instead of SQLite
- Industry queries expanded (236 queries: 91 Exa + 145 Tavily)

### Known Remaining SQLite Usage
- classifier/entity_linker entity loading
- briefing generators (legacy)

---

## Quick Reference

### Test Commands
```bash
# Verify MCP tools load
cd backend && python -c "from app.mcp.server import get_all_mcp_tools; print(f'MCP tools: {len(get_all_mcp_tools())}')"

# Quick health check
python scripts/monitoring/production_dashboard.py

# Detailed health check
python scripts/monitoring/production_dashboard.py --detailed --days 7
```

### Backfill Commands
```bash
# Industry queries
python scripts/operations/backfill/backfill_industry_queries.py --days 7

# Earnings (Q3 2025)
python -c "import asyncio; from app.ingestion.orchestrator import *; asyncio.run(IngestionOrchestrator(IngestionConfig()).run_earnings_only(year=2025, quarter=3))"

# SEC filings
python scripts/operations/backfill/backfill_sec_filings.py --days 7
```

---

## 📋 SESSION 8 HANDOFF SUMMARY

**Copy this to start Session 8:**

```
Continue Session 8 for c1-intelligence-hub.

IMMEDIATE PRIORITY: Fix DRUMBEAT feed not loading digest cards

CONTEXT:
- Data EXISTS in BigQuery: 3,597 digest_items, 645 in last 7 days, feed_eligible=True
- Problem: Frontend shows "No recent activity in the last 7 days"
- Likely cause: Storage backend selection issue

INVESTIGATION SO FAR:
1. BigQuery has data (confirmed via direct query)
2. Two storage classes exist in gcp_storage.py:
   - LocalDataStorage (SQLite) - line 254
   - BigQueryDataStorage - line 662
3. get_data_storage() chooses based on gcp_config.is_configured
4. HYPOTHESIS: Something is making it use SQLite instead of BigQuery

NEXT STEPS:
1. Run this test to check storage type:
   cd backend && python -c "import asyncio; from app.db.gcp_storage import get_storage, gcp_config; print(f'is_configured: {gcp_config.is_configured}'); s=asyncio.run(get_storage()); print(f'Storage: {type(s).__name__}')"

2. If BigQuery, check the query filters in get_digest_items (line 2626):
   - published_at date range
   - confidence >= 0.3
   - ingested_at >= '2025-12-28'
   - The classified_at vs published_at 30-min check

3. Test the actual API endpoint: curl http://localhost:8000/api/digest?hours=168

KEY FILES:
- backend/app/db/gcp_storage.py - Storage backends
- backend/app/services/digest_service.py - get_digest() method  
- backend/app/api/routes/digest.py - /api/digest endpoint

SESSION 7 COMPLETED:
- ✅ Earnings backfill (40 new Q3 2025 transcripts)
- ✅ Cloud Scheduler jobs fixed (6 jobs, all pointed to wrong URL)
- ✅ WORKLOG.md created for session continuity
```
