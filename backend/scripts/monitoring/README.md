# Monitoring Scripts

Production monitoring and diagnostics for C1 Intelligence Hub.

## Scripts

| Script | Purpose |
|--------|---------|
| `production_dashboard.py` | **PRIMARY** - Unified dashboard (health check + optional logs) |
| `scheduler_report.py` | Detailed Cloud Run log analysis |
| `compare_prod_data.py` | Compare production vs local data |
| `query_bq_detailed.py` | Detailed BigQuery queries for ad-hoc analysis |

## Daily Use

### Quick Check (30 seconds)
```bash
python scripts/monitoring/production_dashboard.py
```
Runs BigQuery health check showing:
- Cloud Scheduler job status
- Table statistics (articles, digest_items, embeddings)
- Daily article counts by source
- Pipeline completeness

### Detailed Analysis (3-5 minutes)
```bash
python scripts/monitoring/production_dashboard.py --detailed
```
Adds Cloud Run log analysis for:
- Source-by-source execution stats
- Error breakdowns
- Timing information

### Custom Lookback
```bash
python scripts/monitoring/production_dashboard.py --days 14
python scripts/monitoring/production_dashboard.py --detailed --days 3
```

## Data Sources Tracked

The health check monitors these ingestion sources:
- RSS feeds (14 industry feeds)
- SEC filings (10-K, 10-Q, 8-K)
- Earnings transcripts (API Ninja)
- FMP Premium News (Benzinga, Seeking Alpha)
- StockNews API
- Exa.ai web search (91 queries)
- Tavily web search (145 queries)
- Drewry WCI freight rates

For full ingestion pipeline documentation, see: `app/ingestion/README.md`

## Digest Data Quality Checks

### Check Priority Distribution
```bash
python scripts/testing/check_lowium_bug.py
```
Shows priority value distribution and identifies any malformed values.

**Last verified**: Jan 5, 2026
- Total items: 3,767
- Priority distribution: Healthy
- Known issue: 12% capitalized values (low priority)

---

*Last updated: January 5, 2026*
