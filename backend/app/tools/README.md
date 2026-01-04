# Ingestion Data Collectors

⚠️ **This directory is for DATA INGESTION ONLY**

## Purpose
These modules are used by the `IngestionOrchestrator` to collect raw data from external sources and store it in BigQuery.

## NOT for Agent Tools
If you are building a tool for conversational agents, use `app/mcp/tools/` instead.

## Architecture
Each collector follows the pattern:
- `collector.py` - Main collection logic called by orchestrator
- `client.py` - API client wrapper
- `models.py` - Pydantic models for data validation

## Current Collectors
- `earnings/` - Earnings call transcripts (API Ninjas)
- `press_releases/` - Press releases (Exa, Tavily)
- `sec_filings/` - SEC filings (SEC EDGAR API)
- `stocknews/` - Stock news (StockNews API)
- `stocknewsapi/` - Alternative stock news source

## Adding New Collectors
1. Create subdirectory: `app/tools/{source_name}/`
2. Implement `collector.py` with `collect_for_company()` method
3. Register in `app/ingestion/orchestrator.py`
4. Update this README
