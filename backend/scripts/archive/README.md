# Archive - Deprecated Scripts

⚠️ **DO NOT USE THESE SCRIPTS**

These are from the SQLite/ChromaDB era (before BigQuery migration).

## Deprecated Scripts

- `check_sqlite_dates.py` - SQLite date checking (obsolete)
- `reindex_chromadb.py` - ChromaDB reindexing (obsolete)
- `sync_sqlite_to_bigquery.py` - Migration script (obsolete)

## Why Archived

The system now uses **BigQuery as the single source of truth**. These scripts reference deprecated data stores and will not work with the current architecture.

If you need similar functionality, see:
- `scripts/health/` - For data quality checks
- `scripts/monitoring/scheduler_report.py` - For comprehensive health reports
