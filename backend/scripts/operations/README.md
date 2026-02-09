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

**Backfill earnings quote extraction** (Q3 2025+):
```bash
python scripts/operations/backfill_earnings_quotes.py              # Default: up to 50 transcripts
python scripts/operations/backfill_earnings_quotes.py --limit 20   # Limit batch size
python scripts/operations/backfill_earnings_quotes.py --stats      # Show extraction stats
python scripts/operations/backfill_earnings_quotes.py --dry-run    # Preview without extracting
```

**Backfill SEC filing nugget extraction**:
```bash
python scripts/operations/backfill_sec_nuggets.py              # Default: up to 50 filings
python scripts/operations/backfill_sec_nuggets.py --limit 20   # Limit batch size
python scripts/operations/backfill_sec_nuggets.py --stats      # Show extraction stats
python scripts/operations/backfill_sec_nuggets.py --dry-run    # Preview without extracting
```
