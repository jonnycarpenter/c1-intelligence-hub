# Verification Scripts

Post-deployment verification scripts.

## Scripts

- `verify_backfill_results.py` - Verify backfill completed successfully
- `verify_enhancements.py` - Verify new features work
- `verify_headline_pills.py` - Verify UI pill formatting
- `verify_industry_queries_load.py` - Verify industry queries loaded
- `verify_source_type.py` - Verify source classification

## Usage

Run after deployments to ensure features are working:

```bash
python scripts/verification/verify_enhancements.py
```
