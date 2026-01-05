# Testing Scripts

Ad-hoc test scripts for development and debugging.

## Scripts

- `test_briefing.py` - Test briefing generation
- `test_earnings.py` - Test earnings collection
- `test_fmp_endpoints.py` - Test Financial Modeling Prep API
- `test_general.py` - General system tests
- `test_ingestion_new_tools.py` - Test new ingestion sources
- `test_press.py` - Test press release collection
- `test_pulse_api.py` - Test Pulse API endpoints
- `test_sec_only.py` - Test SEC filings collection
- `test_tools.py` - Test MCP tools
- `test_two_agent_pipeline.py` - Test briefing agent pipeline
- `test_prebriefing_bq.py` - Test pre-briefing BigQuery integration
- `check_lowium_bug.py` - Check digest priority value distribution

## Usage

These are development scripts - run as needed during feature development.

## Data Quality Checks

### Digest Priority Distribution
```bash
python scripts/testing/check_lowium_bug.py
```
Checks for malformed priority values and shows distribution across all digest items.

---

*Last updated: January 5, 2026*
