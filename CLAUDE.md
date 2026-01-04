# C1 Intelligence Hub - AI Agent Instructions

## Before Making Structural Changes

Read these files first:
- `.agent/CODING_RULES.md` - Mandatory rules
- `.agent/ARCHITECTURE.md` - System design decisions

## Critical Rules (TL;DR)

1. **BigQuery ONLY** - Never add SQLite, ChromaDB, or local databases
2. **Tool locations are fixed**:
   - Agent tools → `app/mcp/tools/`
   - Ingestion tools → `app/tools/`
   - Scripts → `scripts/{monitoring,health,operations}/`
3. **Update READMEs** when adding new modules
4. **Test before committing**:
   ```bash
   cd backend
   python -c "from app.mcp.server import get_all_mcp_tools; print(len(get_all_mcp_tools()))"
   python scripts/monitoring/scheduler_report.py
   ```

## Key Files

| Purpose | Location |
|---------|----------|
| MCP tool registration | `app/mcp/server.py` |
| Ingestion orchestrator | `app/ingestion/orchestrator.py` |
| BigQuery client | `app/db/bigquery_client.py` |
| Environment config | `app/config/settings.py` |

## Don't Touch (Bug Fix Protected)

These files have critical bug fixes - be careful editing:
- `app/services/gcp_storage.py` - feed_eligible logic
- `app/models/corpus.py` - feed_eligible field
