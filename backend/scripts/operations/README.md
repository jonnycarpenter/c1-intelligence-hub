# Operations Scripts

Data operations: backfills, maintenance, and manual triggers.

## Subdirectories

- `backfill/` - Backfill missing or incorrect data
- `maintenance/` - Data cleanup and fixes
- `triggers/` - Manual job triggers

## Common Operations

**Backfill missing days**:
```bash
python scripts/operations/triggers/trigger_backfill.py
```

**Manual ingestion**:
```bash
python scripts/operations/triggers/manual_trigger_ingest.py
```

**Fix bad data**:
```bash
python scripts/operations/maintenance/fix_bad_timestamps.py
```
