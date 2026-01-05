# Production Monitoring Guide

## Quick Reference

### Daily Monitoring (30 seconds)
```bash
cd backend
python scripts/production_dashboard.py
```
**What it checks:**
- ✅ Are scheduler jobs running?
- ✅ Is data landing in BigQuery?
- ✅ Are all pipeline stages complete (articles → digests → embeddings)?
- ✅ Any data gaps in last 7 days?

### Deep Dive (3-5 minutes)
```bash
python scripts/production_dashboard.py --detailed
```
**Additional checks:**
- 🔬 Per-source breakdown (RSS, SEC, Earnings, Web, etc.)
- 🔬 API usage and errors
- 🔬 Classification quality
- 🔬 Image enrichment stats
- 🔬 Briefing generation success

### Custom Time Ranges
```bash
# Check last 14 days
python scripts/production_dashboard.py --days 14

# Deep analysis of last 3 days
python scripts/production_dashboard.py --detailed --days 3

# Specific run analysis
python scripts/production_dashboard.py --detailed --run morning
```

---

## Monitoring Architecture

### Three-Tier System

```
production_dashboard.py (Orchestrator)
│
├─► ingestion_health_check.py (Tier 1: Smoke Test)
│   └─ BigQuery data verification
│   └─ Scheduler status check
│   └─ Pipeline completeness
│
└─► scheduler_report.py (Tier 2: Forensics)
    └─ Cloud Run log analysis
    └─ Source-by-source stats
    └─ Error pattern detection
```

### When to Use Each Script

| Script | When to Run | Duration | Purpose |
|--------|-------------|----------|---------|
| `production_dashboard.py` | **Daily** | 30 sec | Quick health check |
| `production_dashboard.py --detailed` | **Weekly** or when issues arise | 3-5 min | Full diagnostic |
| `ingestion_health_check.py` | Standalone if dashboard fails | 30 sec | Fallback smoke test |
| `scheduler_report.py` | Manual forensics | 2-3 min | Deep log investigation |

---

## What Each Component Checks

### Health Check (ingestion_health_check.py)
**Catches:**
- ❌ Scheduler jobs not running (like your 5-day outage)
- ❌ No data landing in BigQuery
- ❌ Pipeline gaps (articles exist but no digests)
- ❌ Low daily volume

**Queries:**
- BigQuery tables directly (source of truth)
- Cloud Scheduler job status via gcloud
- Table record counts and daily breakdowns

### Detailed Report (scheduler_report.py)
**Catches:**
- ❌ Specific source failures (e.g., StockNewsAPI down)
- ❌ API quota issues
- ❌ Classification errors
- ❌ Individual company/industry query failures

**Analyzes:**
- Cloud Run logs (execution traces)
- Per-source article counts
- Error messages and patterns
- Performance metrics

---

## Interpreting Results

### ✅ Healthy System
```
Daily articles: 60-160 per day
Pipeline: Complete (articles = digests = embeddings)
Scheduler: Both jobs ENABLED, status code 0
Sources: 5-7 sources contributing daily
```

### ⚠️ Warning Signs
```
Daily articles: 30-60 per day
Pipeline: Partial (e.g., 100 articles, 95 digests)
Scheduler: Jobs ENABLED but status code != 0
Sources: < 5 sources contributing
```

### ❌ Critical Failures
```
Daily articles: < 30 per day or 0
Pipeline: Broken (articles exist, no digests)
Scheduler: Jobs FAILED or DISABLED
Sources: 0-2 sources contributing
```

---

## Troubleshooting Workflow

### Problem: "Low article count"
1. Run `production_dashboard.py --detailed`
2. Check "Source Fidelity" section
3. Identify which sources are failing
4. Check API keys/quotas for failed sources

### Problem: "Pipeline incomplete"
1. Check if digest_items < articles
2. Review classification errors in detailed report
3. Check Cloud Run logs for exceptions

### Problem: "Scheduler job failing"
1. Verify Cloud Run service URL matches scheduler config
2. Check service account permissions
3. Run manual test: `gcloud scheduler jobs run daily-morning-ingest`

---

## Maintenance

### Weekly Checklist
- [ ] Run `production_dashboard.py` - verify green
- [ ] Check avg articles/day >= 60
- [ ] Verify all 7 sources contributing
- [ ] Review any ⚠️ warnings

### Monthly Checklist
- [ ] Run `production_dashboard.py --detailed --days 30`
- [ ] Review API usage trends
- [ ] Check for error pattern changes
- [ ] Verify briefing generation success rate

---

## Recovery Procedures

### If scheduler jobs broken:
```bash
# Check jobs
gcloud scheduler jobs list --project gen-lang-client-0436975498 --location us-central1

# Manual trigger
gcloud scheduler jobs run daily-morning-ingest --location us-central1 --project gen-lang-client-0436975498

# Backfill (see backfill guide)
```

### If data gap detected:
```bash
# Run backfill scripts from backend directory
cd backend
python scripts/operations/backfill/backfill_sec_filings.py --days 6
python scripts/operations/backfill/backfill_press_releases.py --days 6
python scripts/operations/backfill/backfill_industry_queries.py --days 6
```

### If API keys missing from Cloud Run:
```bash
# Check which secrets are configured
gcloud run services describe c1-hub --region us-central1 --format="yaml(spec.template.spec.containers[0].env)"

# Add a missing secret (example for EXA_API_KEY)
gcloud run services update c1-hub --region us-central1 --update-secrets="EXA_API_KEY=EXA_API_KEY:latest"

# Verify secret exists in Secret Manager
gcloud secrets list --format="table(name)"
```

### If dashboard script fails:
```bash
# Fallback to individual components
python scripts/ingestion_health_check.py --days 7
python scripts/scheduler_report.py --run latest
```

---

## Future Enhancements (Planned)

- [ ] API quota tracking
- [ ] Data freshness verification
- [ ] Classification quality metrics
- [ ] Automated alerting
- [ ] Slack/email notifications
