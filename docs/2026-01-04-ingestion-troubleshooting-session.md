# Ingestion Pipeline Troubleshooting Session - January 4, 2026

## Session Summary

This document captures the debugging session for the C1 Intelligence Hub ingestion pipeline. Use this to resume troubleshooting in a fresh context.

---

## 1. ORIGINAL PROBLEM

Data was not making it into BigQuery tables. Cloud Scheduler jobs were failing.

## 2. ROOT CAUSES IDENTIFIED & FIXED (Earlier Session)

### Bug #1: Sources Parameter Not Passed
**File:** `backend/app/api/routes/scheduler.py` (~line 167)
**Problem:** The `sources` parameter from the request wasn't being passed to `run_full_ingestion()`
**Fix:** Changed to include `sources=request.sources`

### Bug #2: Tier Dates NameError
**File:** `backend/app/ingestion/orchestrator.py`
**Problem:** `tier1_since` and `tier2_since` variables were used before being defined in the flash source loop
**Fix:** Moved tier date initialization to the TOP of the try block, before any source fetching

### Bug #3: feed_eligible Implementation
**Files:** `orchestrator.py`, `gcp_storage.py`
**Problem:** Articles without dates were being discarded entirely
**Solution:** Added `feed_eligible` BOOLEAN column to BigQuery `digest_items` table. ALL articles are now stored, but only `feed_eligible=True` ones appear in the Drumbeat feed.

**Commits:**
- `ef4a9a4` - Critical scheduler/orchestrator fixes
- `3a1970e` - feed_eligible implementation  
- `3cd6d1c` - Documentation

---

## 3. CURRENT SESSION WORK

### 3.1 Backfill Triggered

We triggered a 7-day backfill via:
```powershell
$body = @{backfill_days = 7; sources = @("rss", "tavily", "sec", "earnings", "stocknews", "freight", "press_releases")} | ConvertTo-Json
Invoke-RestMethod -Uri "https://c1-hub-4iz75bvpyq-uc.a.run.app/api/v1/scheduler/ingest" -Method POST -ContentType "application/json" -Body $body -TimeoutSec 900
```

**Note:** The Cloud Run URL changed from the old one. Current URL:
```
https://c1-hub-4iz75bvpyq-uc.a.run.app
```

You can get the current URL with:
```powershell
gcloud run services describe c1-hub --region us-central1 --format="value(status.url)"
```

### 3.2 Ingestion Progress Observed

The backfill IS running. We observed in logs:
- ✅ RSS: Fetched 67 articles from multiple feeds
- ✅ Earnings: Collecting for many companies (MMM, ACM, EADSY, etc.)
- ✅ Tavily: Running queries for materials, suppliers, OEMs, contracts
- ⚠️ SEC: Only ONE query attempted (CAT) - got 429 rate limit, then moved to next source
- ⚠️ Press Releases (Exa API): Returning 400 Bad Request errors

### 3.3 Date Extraction Working

The `feed_eligible` logic is working correctly:
- WARNING logs appear when dates can't be extracted (expected)
- Articles are NOT being discarded - they continue through pipeline
- Some dates ARE being extracted successfully via JSON-LD

---

## 4. OPEN ISSUE: SEC Filings Investigation

### 4.1 The Problem
SEC API subscription dashboard shows: **"Data volume used in January 2026 = 0 GB"**

Only ONE SEC query was attempted in the logs:
```
2026-01-04 23:17:03,291 - app.tools.sec_filings.collector - ERROR - SEC Query failed for CAT: Client error '429 Too Many Requests' for url 'https://api.sec-api.io'
```

Then it immediately jumped to Earnings without trying other companies.

### 4.2 What We Know

1. **SEC_IO_KEY IS configured in Cloud Run:**
   ```powershell
   gcloud run services describe c1-hub --region us-central1 --format="yaml(spec.template.spec.containers[0].env)"
   ```
   Shows: `SEC_IO_KEY` env var pointing to secret `SEC_IO_KEY`

2. **Secret exists and has value:**
   ```powershell
   gcloud secrets versions access latest --secret=SEC_IO_KEY
   ```
   Returns a valid API key

3. **Settings loads key correctly:**
   File: `backend/app/config/settings.py` line 87:
   ```python
   sec_api_key: str = Field(validation_alias=AliasChoices("SEC_IO_KEY", "SEC_IO_API_KEY"), default="")
   ```

4. **SEC Client silently returns empty if no key:**
   File: `backend/app/tools/sec_filings/sec_client.py` lines 27-28:
   ```python
   if not self.api_key:
       return []
   ```

5. **Companies with real tickers:**
   - 263 total companies in BigQuery
   - 78 have real stock tickers (not "private")
   - Companies are loaded from BigQuery in production via `load_companies()` in `backend/app/utils/grounding.py`
   - The orchestrator filters out `private` tickers

6. **CAT (Caterpillar) is the 16th company alphabetically** - so it's NOT the first one in the loop

### 4.3 Unresolved Questions

1. **Why did only CAT get queried?** The loop should continue through all companies even if one fails.
2. **Why 429 on first request?** Rate limiting usually happens after multiple requests, not the first one.
3. **Is the API key actually being loaded into settings?** The 429 suggests it IS (invalid key = 401, not 429).

### 4.4 Code Locations for SEC

- **Collector:** `backend/app/tools/sec_filings/collector.py`
- **Client:** `backend/app/tools/sec_filings/sec_client.py`
- **Orchestrator SEC loop:** `backend/app/ingestion/orchestrator.py` lines 249-265
- **Settings:** `backend/app/config/settings.py` line 87
- **Company loading:** `backend/app/utils/grounding.py` line 38 `load_companies()`

### 4.5 Suggested Next Steps

1. **Add more logging** to SEC collector to see exactly what's happening:
   ```python
   logger.info(f"SEC: Processing company {ticker} ({company_id})")
   ```

2. **Check if settings.sec_api_key is actually populated** at runtime:
   ```python
   logger.info(f"SEC API key present: {bool(self.config.sec_api_key)}")
   ```

3. **Test SEC API manually** with the key:
   ```powershell
   $key = (gcloud secrets versions access latest --secret=SEC_IO_KEY)
   Invoke-RestMethod -Uri "https://api.sec-api.io" -Method POST -Headers @{Authorization=$key} -ContentType "application/json" -Body '{"query":"ticker:AAPL","size":"1"}'
   ```

---

## 5. 🚨 CRITICAL: EXA.AI API KEY NOT CONFIGURED

**This is the most important issue to fix!** Exa.ai is described as "the most important source across all data source types" but the API key is completely missing from Cloud Run.

### 5.1 The Problem

All press release queries are failing with 400 Bad Request:
```
app.tools.press_releases.collector - ERROR - Search failed for Wacker: Client error '400 Bad Request' for url 'https://api.exa.ai/search'
```

### 5.2 Root Cause

**EXA_API_KEY is NOT set in Cloud Run environment variables!**

Verified by running:
```powershell
gcloud run services describe c1-hub --region us-central1 --format="yaml(spec.template.spec.containers[0].env)" 2>&1 | findstr -i "exa"
# Returns nothing - key is missing!
```

### 5.3 Settings Configuration

File: `backend/app/config/settings.py` line 40:
```python
exa_api_key: str = Field(validation_alias=AliasChoices("EXA_API_KEY", "EXA_AI_API_KEY"), default="")
```

The code expects either `EXA_API_KEY` or `EXA_AI_API_KEY` env var.

### 5.4 Files Using Exa.ai

- `backend/app/tools/press_releases/exa_client.py` - Main client
- `backend/app/services/exa_service.py` - Prospect discovery service
- `backend/app/services/exa_websets_service.py` - Websets service
- `backend/app/ingestion/orchestrator.py` - Uses `config.exa_api_key`

### 5.5 FIX REQUIRED

**Option 1: Create new secret and add to Cloud Run**
```powershell
# Create the secret (replace with your actual key)
echo "YOUR_EXA_API_KEY_HERE" | gcloud secrets create exa-api-key --data-file=-

# Grant Cloud Run access
gcloud secrets add-iam-policy-binding exa-api-key --member="serviceAccount:645117817804-compute@developer.gserviceaccount.com" --role="roles/secretmanager.secretAccessor"

# Add to Cloud Run
gcloud run services update c1-hub --region us-central1 --update-secrets="EXA_API_KEY=exa-api-key:latest"
```

**Option 2: If secret already exists with different name**
```powershell
# List existing secrets to find it
gcloud secrets list | findstr -i exa

# Then add mapping
gcloud run services update c1-hub --region us-central1 --update-secrets="EXA_API_KEY=<secret-name>:latest"
```

### 5.6 Impact

Without Exa.ai:
- ❌ Press releases not being collected
- ❌ Web search for company news broken
- ❌ Prospect discovery features broken
- ❌ Significant gap in intelligence data

---

## 6. BIGQUERY TABLE STATUS

### Tables and Counts (as of session start)
| Table | Rows |
|-------|------|
| articles | 2,086 |
| digest_items | 2,866 |
| article_chunk_embeddings | 21,204 |
| companies | 263 |
| materials | 49 |
| industries | 15 |

### New Column Added
- `digest_items.feed_eligible` (BOOLEAN) - controls Drumbeat feed visibility

---

## 7. USEFUL COMMANDS

### Check Cloud Run Logs
```powershell
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=c1-hub" --limit=50 --format="value(textPayload)" --freshness=5m
```

### Filter logs for specific patterns
```powershell
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=c1-hub" --limit=200 --format="value(textPayload)" --freshness=30m 2>&1 | findstr "SEC Earnings"
```

### Check Cloud Run env vars
```powershell
gcloud run services describe c1-hub --region us-central1 --format="yaml(spec.template.spec.containers[0].env)"
```

### Trigger ingestion
```powershell
$body = @{backfill_days = 7; sources = @("rss", "tavily", "sec", "earnings")} | ConvertTo-Json
Invoke-RestMethod -Uri "https://c1-hub-4iz75bvpyq-uc.a.run.app/api/v1/scheduler/ingest" -Method POST -ContentType "application/json" -Body $body -TimeoutSec 900
```

### Query BigQuery
```powershell
bq query --nouse_legacy_sql "SELECT COUNT(*) FROM gen-lang-client-0436975498.c1_intelligence.articles"
```

---

## 8. CLOUD BUILD TRIGGER

User set up a Cloud Build trigger attached to the GitHub repo. This means:
- Pushes to master trigger automatic builds/deploys
- The Cloud Run URL may change between deployments
- Always verify current URL before API calls

---

## 9. KEY FILES REFERENCE

| Purpose | File |
|---------|------|
| Scheduler API | `backend/app/api/routes/scheduler.py` |
| Orchestrator | `backend/app/ingestion/orchestrator.py` |
| SEC Collector | `backend/app/tools/sec_filings/collector.py` |
| SEC Client | `backend/app/tools/sec_filings/sec_client.py` |
| Press Releases | `backend/app/tools/press_releases/collector.py` |
| GCP Storage | `backend/app/db/gcp_storage.py` |
| Settings | `backend/app/config/settings.py` |
| Company Loading | `backend/app/utils/grounding.py` |

---

## 10. SUMMARY OF SESSION STATUS

| Component | Status |
|-----------|--------|
| RSS Ingestion | ✅ Working |
| Tavily Web Search | ✅ Working |
| Earnings Transcripts | ✅ Working |
| SEC Filings | ❓ Needs investigation - only 1 query, 429 error |
| Press Releases | ❌ All failing with 400 |
| StockNews | Not yet observed in logs |
| feed_eligible flag | ✅ Implemented and working |
| Date extraction | ✅ Working (some dates found, some not - expected) |

**Priority:** Investigate why SEC only tried one company before moving on.
