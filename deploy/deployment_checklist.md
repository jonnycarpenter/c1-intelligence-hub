# Production Deployment Checklist

> **Last Updated:** January 4, 2026

## New Features (Jan 2026)

### Login Gate ✅
- Password: `partnership2026` (set via `cloudbuild.yaml`)
- Team selection: Sales East, Sales West, Marketing, Product/Supplier, All Others
- User badge shows in header

### Long-Term Memory 🟡 (Partial)
- BigQuery tables created: `c1_intelligence.org_preferences`, `c1_intelligence.memory_log`
- Save to Memory button in Quick Brief (needs testing)
- Memory tab displays saved items
- **Not yet integrated:** Agent doesn't use memory context yet

---

## Pre-Deployment Verification

### ✅ Backfill Status
- [ ] Backfill ingestion completed successfully
- [ ] No errors in Cloud Run logs
- [ ] BigQuery data verified

### ✅ Scheduler Reset
- [ ] Run `.\deploy\reset_scheduler.ps1` to remove backfill_days parameter
- [ ] Verify scheduler jobs back to normal configuration

### ✅ Data Validation
- [ ] Run `python scripts/production_dashboard.py --days 7`
- [ ] Verify recovered data in BigQuery
- [ ] Check `corpus_items`, `digest_items`, `article_chunk_embeddings` tables

---

## Frontend Changes Included in This Deploy

### Error Handling & Stability Fixes

**1. Error Boundaries Added:**
- ✅ `frontend/src/app/error.tsx` - Page-level error boundary
- ✅ `frontend/src/app/global-error.tsx` - Root-level error boundary
- **Impact**: Catches client-side exceptions gracefully with retry UI

**2. Loading States for Dynamic Imports:**
- ✅ `ImportYetiDashboard.tsx` - Added loading fallbacks for SSR-disabled components
- **Impact**: Prevents React hydration mismatches

**3. Defensive Coding:**
- ✅ `FreightRatesChart.tsx` - Null safety and empty data handling
- ✅ `useDigest.ts` - Graceful handling of null/undefined digest data
- ✅ `config.ts` - SSR-safe API base URL configuration
- **Impact**: No crashes when data is missing or API fails

---

## Deployment Steps

### 1. Verify Backfill Complete (~15-20 min from start)
```powershell
# Check Cloud Run logs for completion
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=c1-hub AND textPayload:complete" `
  --limit 5 --project gen-lang-client-0436975498

# Verify data in BigQuery
cd backend
python scripts/production_dashboard.py --days 7
```

### 2. Reset Scheduler Configuration
```powershell
cd deploy
.\reset_scheduler.ps1
```

### 3. Build & Deploy
```powershell
cd ..
.\deploy\deploy.ps1
```

**Estimated Duration**: ~8-10 minutes
- Build: ~5-6 min
- Deploy: ~2-3 min
- Startup: ~30 sec

### 4. Post-Deployment Verification

**A. Service Health**
```bash
# Check service is running
gcloud run services describe c1-hub --region us-central1 --project gen-lang-client-0436975498

# Verify logs for startup errors
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=c1-hub" `
  --limit 10 --project gen-lang-client-0436975498
```

**B. Frontend Stability**
- [ ] Navigate to Trade Intelligence tab
- [ ] Verify Freight Rates chart loads without errors
- [ ] Check Logistics Intel news feed displays
- [ ] Test error boundary (intentionally trigger error if needed)
- [ ] Verify no "Application error: a client-side exception has occurred" message

**C. Pulse Tab**
- [ ] Verify digest cards visible with backfilled data
- [ ] Check "Need to Know" briefing (may be empty until next weekly generation)
- [ ] Test ad-hoc briefing ("Ask me anything")

**D. Login Gate**
- [ ] Verify password gate appears on first visit
- [ ] Test with password: `partnership2026`
- [ ] Verify team selection works
- [ ] Check user badge appears in header after login

**E. Memory Tab**
- [ ] Test saving a briefing to memory (bookmark icon)
- [ ] Verify Memory tab shows saved items
- [ ] Test pin/unpin functionality

**D. Data Integrity**
- [ ] Run `python scripts/production_dashboard.py --days 7`
- [ ] Verify article counts are normal (60-160/day)
- [ ] Check all sources contributing data

---

## Rollback Plan

**If deployment fails or errors persist:**

```powershell
# 1. Check current deployed revision
gcloud run services describe c1-hub --region us-central1 --project gen-lang-client-0436975498

# 2. Rollback to previous revision
gcloud run services update-traffic c1-hub `
  --to-revisions=PREVIOUS_REVISION=100 `
  --region us-central1 `
  --project gen-lang-client-0436975498
```

**Previous stable revision**: (Check Cloud Console for most recent working revision)

---

## Expected Outcomes

### ✅ **Backend Improvements**
1. Scheduler jobs running reliably with correct URL
2. 5 days of backfilled data recovered (~200-400 articles)
3. All 7 sources contributing to daily ingestion
4. Enhanced monitoring catches silent failures

### ✅ **Frontend Improvements**
1. Trade Intelligence tab loads without crashes
2. Error boundaries catch and display errors gracefully
3. No hydration mismatches from dynamic imports
4. Recharts components handle empty/null data

### ✅ **User Experience**
1. Pulse tab shows recovered articles
2. No blank screen errors
3. Retry button appears if errors occur
4. Smoother navigation between tabs

---

## Monitoring Post-Deploy

**First 24 Hours:**
- Run `production_dashboard.py` every 6 hours
- Check Cloud Run logs for errors
- Monitor scheduler job success rate
- Test all major UI flows

**First Week:**
- Daily dashboard runs
- Weekly briefing generation verification
- API performance monitoring
- User feedback on stability

---

## Notes

- **Backfill started**: ~11:10 AM CT (01/03/2026)
- **Expected completion**: ~11:25-11:30 AM CT
- **Frontend fixes**: Already committed, ready to deploy
- **No breaking changes**: All changes are additive stability improvements
