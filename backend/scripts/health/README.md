# Health Check Scripts

Diagnostic scripts for checking system health and data quality.

## Scripts

- `ingestion_health_check.py` - **PRIMARY** comprehensive ingestion diagnostics
- `check_ingestion_history.py` - View ingestion run history
- `check_pipeline_health.py` - Pipeline status check
- `check_bad_dates.py` - Find articles with date issues
- `check_bad_timestamp.py` - Find timestamp parsing issues
- `check_config.py` - Verify configuration
- `check_db.py` - Database connectivity check
- `check_local_articles.py` - Check local article storage
- `check_sec_config.py` - Verify SEC API configuration

## Most Common

```bash
python scripts/health/ingestion_health_check.py
```
