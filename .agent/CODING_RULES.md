# C1 Intelligence Hub - Coding Rules

> **For AI Agents**: These are MANDATORY rules. Violating them will break the codebase.

---

## 🚫 NEVER DO

### 1. NEVER Create Tool Directories Outside Designated Locations

```
❌ WRONG:
   app/new_tools/           # NO - tools go in mcp/tools or tools/
   app/agents/tools/        # NO - agents don't have their own tools
   backend/tools/           # NO - tools are in app/

✅ CORRECT:
   app/mcp/tools/           # Agent tools (for conversations)
   app/tools/               # Ingestion tools (for data collection)
```

### 2. NEVER Add SQLite or ChromaDB Dependencies

```python
# ❌ NEVER DO THIS
import sqlite3
from chromadb import Client

# These were removed in Phase 2 cleanup (January 2026)
# BigQuery is the ONLY database
```

### 3. NEVER Create New Local Database Files

```
❌ FORBIDDEN FILES:
   *.db
   *.sqlite
   *.sqlite3
   chroma_db/
   
# BigQuery is the single source of truth
# See ADR-001 in ARCHITECTURE.md
```

### 4. NEVER Duplicate Existing Functionality

Before creating anything new, check:
- `app/mcp/tools/README.md` - Existing agent tools
- `app/tools/README.md` - Existing ingestion collectors  
- `scripts/README.md` - Existing scripts

---

## ✅ ALWAYS DO

### 1. ALWAYS Check README Files First

```bash
# Before adding new modules, read:
cat backend/app/mcp/tools/README.md    # Agent tools
cat backend/app/tools/README.md        # Ingestion tools
cat backend/scripts/README.md          # Scripts
```

### 2. ALWAYS Use Existing Scripts for Health Checks

```bash
# Daily health check
python backend/scripts/monitoring/scheduler_report.py

# Ingestion diagnostics
python backend/scripts/health/ingestion_health_check.py

# Don't create new health check scripts - use these!
```

### 3. ALWAYS Update READMEs When Adding New Modules

When you add a new file, update the appropriate README:
- New agent tool → `app/mcp/tools/README.md`
- New collector → `app/tools/README.md`
- New script → `scripts/README.md`

### 4. ALWAYS Use BigQuery for Data Storage

```python
# ✅ CORRECT
from app.db.bigquery_client import BigQueryClient

client = BigQueryClient()
results = client.query("SELECT * FROM articles")
```

---

## Where to Add New Functionality

### Agent Tool (for conversations)
```
Location: app/mcp/tools/{tool_name}.py

Steps:
1. Create tool file with @tool decorator
2. Import in app/mcp/server.py
3. Add to get_all_mcp_tools() list
4. Update app/mcp/tools/README.md
```

### Ingestion Collector (for data collection)
```
Location: app/tools/{source_name}/

Steps:
1. Create directory with collector.py, client.py, models.py
2. Implement collect_for_company() method
3. Register in app/ingestion/orchestrator.py
4. Update app/tools/README.md
```

### Script (for operations/monitoring)
```
Location: scripts/{category}/

Categories:
- monitoring/    → Production health checks
- health/        → Diagnostics
- operations/    → Data operations (backfill, maintenance)
- testing/       → Development tests
- verification/  → Post-deploy checks

Steps:
1. Create script in appropriate category
2. Update scripts/README.md
```

### Configuration
```
Location: app/config/settings.py

Add new env vars to Settings class
Document in README.md
```

---

## Code Style Rules

### 1. Tool Function Pattern

```python
from langchain_core.tools import tool

@tool
def my_new_tool(query: str, limit: int = 10) -> str:
    """
    Short description of what the tool does.
    
    Args:
        query: The search query
        limit: Maximum results to return
        
    Returns:
        JSON string with results
    """
    # Implementation
    return json.dumps(results)
```

### 2. Import Organization

```python
# Standard library
import json
from datetime import datetime
from typing import List, Optional

# Third party
from langchain_core.tools import tool
from google.cloud import bigquery

# Local imports
from app.db.bigquery_client import BigQueryClient
from app.utils.logger import get_logger
```

### 3. Error Handling

```python
from app.utils.logger import get_logger

logger = get_logger(__name__)

@tool
def my_tool(query: str) -> str:
    try:
        # Implementation
        return json.dumps({"status": "success", "data": results})
    except Exception as e:
        logger.error(f"Tool error: {e}")
        return json.dumps({"status": "error", "message": str(e)})
```

---

## Testing Requirements

### Before Committing

```bash
# 1. Check for import errors
cd backend
python -c "from app.mcp.server import get_all_mcp_tools; print(f'Loaded {len(get_all_mcp_tools())} tools')"

# 2. Run health check
python scripts/monitoring/scheduler_report.py

# 3. Run ingestion health check
python scripts/health/ingestion_health_check.py
```

### After Major Changes

```bash
# Run full test suite
pytest backend/

# Or specific tests
pytest backend/test_workflow.py
```

---

## Key Contacts

- **BigQuery Issues**: Check `app/db/bigquery_client.py`
- **Ingestion Pipeline**: Check `app/ingestion/orchestrator.py`
- **MCP Tools**: Check `app/mcp/server.py`
- **Environment Config**: Check `app/config/settings.py`

---

## Quick Reference: File Locations

| Need to... | Look in... |
|------------|------------|
| Add agent tool | `app/mcp/tools/` |
| Add data collector | `app/tools/` |
| Query BigQuery | `app/db/bigquery_client.py` |
| Check health | `scripts/monitoring/` |
| Debug ingestion | `scripts/health/` |
| Run backfill | `scripts/operations/backfill/` |
| Test features | `scripts/testing/` |

---

*Last updated: January 2026 (Phase 3 Consolidation)*
