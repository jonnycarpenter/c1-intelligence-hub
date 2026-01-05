# Archive - Deprecated Scripts

⚠️ **DO NOT USE THESE SCRIPTS**

These are from the SQLite/ChromaDB era (before BigQuery migration).

## Deprecated Scripts

### From Session 16 (January 5, 2026) - database.py cleanup
These scripts imported the deleted `app/db/database.py` file:

- `verify_enhancements.py` - Weekly briefing prompt verification
- `test_pulse_api.py` - Pulse API endpoint testing
- `test_two_agent_pipeline.py` - Two-agent briefing pipeline testing
- `test_briefing.py` - Briefing generation testing
- `purge_and_backfill_exa.py` - Exa data purge/backfill (SQLite)
- `purge_data.py` - Data purge utility (SQLite DB_PATH)
- `load_companies.py` - Company loading trigger
- `debug_entities.py` - Entity debugging utility
- `backfill_tags.py` - Tag backfill (SQLite)
- `check_data_sources.py` - Data source comparison

### Original archives
- `check_sqlite_dates.py` - SQLite date checking (obsolete)
- `reindex_chromadb.py` - ChromaDB reindexing (obsolete)
- `sync_sqlite_to_bigquery.py` - Migration script (obsolete)

## Why Archived

The system now uses **BigQuery as the single source of truth**. These scripts reference deprecated data stores and will not work with the current architecture.

If you need similar functionality, see:
- `scripts/health/` - For data quality checks
- `scripts/monitoring/scheduler_report.py` - For comprehensive health reports
