# Monitoring Scripts

Production monitoring and diagnostics.

## Scripts

- `scheduler_report.py` - **PRIMARY** daily health report with comprehensive stats
- `production_dashboard.py` - Production metrics dashboard
- `compare_prod_data.py` - Compare production vs local data
- `query_bq_detailed.py` - Detailed BigQuery queries for ad-hoc analysis

## Daily Use

```bash
python scripts/monitoring/scheduler_report.py
```

This is the main tool for checking ingestion pipeline health.
