# Ingestion Pipeline Fixes - January 4, 2026

## Executive Summary

Fixed critical bugs in the Cloud Scheduler ingestion pipeline that prevented data from flowing to BigQuery since December 29, 2025. Also corrected a philosophical error where articles without valid dates were being **discarded entirely** instead of just being **hidden from the Drumbeat feed**.

---

## Problems Identified

### 1. Critical Bug: Sources Parameter Not Passed to Orchestrator
**File**: `backend/app/api/scheduler.py` (line ~167)

**Issue**: The scheduler endpoint was calling `run_full_ingestion()` without passing the `sources` parameter from the request. This meant ALL scheduler jobs (flash, deep, briefing) were running ALL sources instead of their designated subset.

**Before**:
```python
stats = await orchestrator.run_full_ingestion(backfill_days=request.backfill_days)
```

**After**:
```python
stats = await orchestrator.run_full_ingestion(
    backfill_days=request.backfill_days,
    sources=request.sources
)
```

### 2. Critical Bug: NameError for Tier Date Variables
**File**: `backend/app/ingestion/orchestrator.py`

**Issue**: The variables `tier1_since`, `tier2_since`, and `search_num_days` were being defined AFTER they were used in source fetching. For the flash loop (which skips some sources), this caused a `NameError` crash because these variables were only defined inside conditional blocks for certain sources.

**Before**: Variables defined inside `if "tavily" in sources:` block (line ~280)

**After**: Variables defined at TOP of try block (line ~188), BEFORE any source fetching:
```python
# =====================================================================
# GLOBAL DATE SETUP - Must happen BEFORE any source fetching
# These variables are used by is_valid_date() filter for all sources
# =====================================================================
if backfill_days:
    tier1_since = datetime.utcnow() - timedelta(days=backfill_days)
    tier2_since = datetime.utcnow() - timedelta(days=backfill_days)
    search_num_days = backfill_days
else:
    tier1_since = datetime.utcnow() - timedelta(days=3)
    tier2_since = datetime.utcnow() - timedelta(days=3)
    search_num_days = 3
```

### 3. Health Check Bug: Wrong Table Name
**File**: `backend/scripts/ingestion_health_check.py`

**Issue**: Script was querying non-existent `corpus_items` table instead of `articles` table.

**Fixed**: Changed all references from `corpus_items` to `articles`.

---

## Philosophical Fix: Date Filtering Behavior

### The Problem
Previous behavior: Articles without a valid `published_at` date (or with dates outside the lookback window) were **completely discarded** and never stored in BigQuery.

**This was wrong**. The intent was to:
- **Store ALL articles** regardless of date
- Only **hide from Drumbeat feed** articles without valid dates

### The Solution

#### New `feed_eligible` Flag
Added a `feed_eligible` boolean field to `digest_items` table that controls visibility in the Drumbeat feed.

**Logic**:
```python
def is_feed_eligible(article) -> bool:
    """Check if article should appear in Drumbeat feed.
    
    Returns True if:
    - Has a valid published_at date
    - Date is not in the future (bad parsing)
    - Date is within the lookback window
    
    All articles are still STORED regardless of this flag.
    This only controls visibility in the Drumbeat/Pulse feed.
    """
    if not article.published_at:
        return False
    pub_date = _make_naive_utc(article.published_at)
    if pub_date > now_utc:
        return False  # Future date = bad parsing
    if pub_date < tier2_since:
        return False  # Outside lookback window
    return True
```

#### Files Modified

1. **`backend/app/ingestion/orchestrator.py`**
   - Added `is_feed_eligible()` function
   - Added `classify_date_status()` for logging
   - Added detailed date filter logging
   - Added `feed_eligible` field to ALL digest item creation points (4 locations)
   - **No longer filters out articles** - all articles flow to storage

2. **`backend/app/db/gcp_storage.py`**
   - Updated `store_digest_items()` to include `feed_eligible` field
   - Both BigQuery and SQLite versions updated

3. **`backend/app/models/corpus.py`**
   - `IngestionStats` already had date filter stats fields (added earlier)

4. **`backend/scripts/ingestion_health_check.py`**
   - Added new "DATE FILTER ANALYSIS" section
   - Shows feed_eligible vs filtered counts
   - Warns on high future date percentages

---

## BigQuery Schema Changes

### digest_items Table
Added new column:
```sql
ALTER TABLE <GCP_PROJECT_ID>.c1_intelligence.digest_items 
ADD COLUMN IF NOT EXISTS feed_eligible BOOLEAN;

ALTER TABLE <GCP_PROJECT_ID>.c1_intelligence.digest_items 
ALTER COLUMN feed_eligible SET DEFAULT TRUE;

UPDATE <GCP_PROJECT_ID>.c1_intelligence.digest_items 
SET feed_eligible = TRUE WHERE feed_eligible IS NULL;
```

**Result**: 2,866 existing records backfilled to `feed_eligible = TRUE`

---

## Logging Improvements

### New Date Filter Logging Output
```
📊 DATE FILTER ANALYSIS (lookback=3 days):
   Total articles collected: 150
   ├─ Feed eligible:  120 (will appear in Drumbeat)
   ├─ No date:        15 (stored, hidden from feed)
   ├─ Future date:    5 (stored, bad date parsing)
   └─ Old date:       10 (stored, outside window)
```

### Health Check New Section
```
📅 DATE FILTER ANALYSIS (Drumbeat Feed Eligibility)
--------------------------------------------------------------------------------
   Total digest items (last 7 days): 634
   ├─ Feed eligible (shown in Drumbeat):  634
   ├─ Filtered out (stored but hidden):   0
   ├─ Null feed_eligible status:          0
   └─ Date issues:
      ├─ No published_at date:  0
      └─ Future date (bad parse): 114
   ⚠️  18.0% of articles have future dates - date extraction bugs!
```

---

## Git Commits

### Commit 1: `ef4a9a4`
```
fix: critical scheduler bugs - sources param + tier dates

- Pass sources parameter from scheduler request to orchestrator
- Move tier date variables to top of try block (before source fetching)
- Fix health check to query 'articles' table instead of 'corpus_items'
- Fix scheduler filter pattern in health check
```

### Commit 2: `3a1970e`
```
feat: add feed_eligible flag for Drumbeat feed visibility

- Stop rejecting articles without dates - ALL articles now stored
- Add feed_eligible flag to digest_items (controls Drumbeat display)
- Add date filter logging with visibility stats
- Update health check with date filter analysis section
- BigQuery digest_items table updated with feed_eligible column

Key change: Articles without valid dates are stored but hidden from
Drumbeat feed rather than being discarded entirely.
```

---

## Architecture Understanding

### Cloud Scheduler Jobs (3-Job Architecture)

| Job | Schedule | Sources | Purpose |
|-----|----------|---------|---------|
| `ingest-flash-update` | Every 4 hours | `rss`, `stocknews`, `freight` | Quick pulse check |
| `ingest-deep-dive` | Daily 2AM CST | ALL sources including `tavily`, `sec`, `earnings`, `press_releases` | Comprehensive daily |
| `weekly-executive-briefing` | Mondays 8:30AM CST | N/A (uses existing data) | Generate weekly report |

### Data Flow
```
Cloud Scheduler → POST /api/v1/scheduler/ingest
                         ↓
              scheduler.py (passes sources param)
                         ↓
              orchestrator.run_full_ingestion(sources=...)
                         ↓
    ┌────────────────────┴────────────────────┐
    ↓                                         ↓
articles table                          digest_items table
(ALL articles stored)                   (with feed_eligible flag)
    ↓                                         ↓
article_chunk_embeddings              Drumbeat Feed UI
(vector search)                       (filters by feed_eligible=TRUE)
```

### Key Tables in BigQuery

| Table | Records | Purpose |
|-------|---------|---------|
| `articles` | 2,086 | Raw article storage |
| `digest_items` | 2,866 | Classified items for UI |
| `article_chunk_embeddings` | 21,204 | Vector embeddings for search |
| `companies` | 263 | Master company list (155 C1 suppliers) |
| `materials` | 49 | Materials taxonomy |
| `industries` | 15 | Industry taxonomy |

---

## Current State (as of Jan 4, 2026)

- **Last successful ingestion**: December 29, 2025 (6 days ago)
- **Scheduler jobs status**: Failing with status code 9 (the bugs we fixed)
- **Future date articles**: 114 (18%) - indicates date extraction bugs to investigate
- **Ready for**: Backfill of missing days (Dec 29 - Jan 4)

---

## Remaining Work

### Before Backfill
1. **Deploy** the fixes to Cloud Run
2. Verify scheduler jobs start succeeding

### Backfill Strategy
Missing window: Dec 29, 2025 → Jan 4, 2026 (6 days)

Options:
1. API trigger: `POST /api/v1/scheduler/ingest` with `backfill_days: 7`
2. Manual: Run orchestrator locally with `backfill_days=7`

### Future Improvements to Consider
1. Investigate date extraction bugs (18% future dates)
2. Add more date extraction patterns for problematic sources
3. Consider adding `date_extraction_method` field for debugging
4. Frontend: Use `feed_eligible` flag to filter Drumbeat display

---

## File Reference

| File | Changes |
|------|---------|
| `backend/app/api/scheduler.py` | Pass `sources` param to orchestrator |
| `backend/app/ingestion/orchestrator.py` | Move tier dates, add feed_eligible, date logging |
| `backend/app/db/gcp_storage.py` | Add feed_eligible to store_digest_items |
| `backend/app/models/corpus.py` | IngestionStats date filter fields |
| `backend/scripts/ingestion_health_check.py` | Fix table name, add date filter section |
