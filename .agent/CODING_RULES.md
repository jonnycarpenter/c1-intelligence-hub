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

> **Migration Complete (January 5, 2026)**:
> `app/db/database.py` was deleted. All storage now uses BigQuery via `gcp_storage.py`.
> See `app/db/README.md` for the current architecture.

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
python scripts/monitoring/production_dashboard.py

# Detailed health check with logs
python scripts/monitoring/production_dashboard.py --detailed

# Ingestion diagnostics
python scripts/health/ingestion_health_check.py

# Don't create new health check scripts - use these!
```

### 3. ALWAYS Update READMEs When Adding New Modules

When you add a new file, update the appropriate README:
- New agent tool → `app/mcp/tools/README.md`
- New collector → `app/tools/README.md`
- New script → `scripts/README.md`

### 4. ALWAYS Use BigQuery for Data Storage

```python
# ✅ CORRECT - For article storage
from app.db.gcp_storage import get_data_storage

storage = get_data_storage()  # Returns BigQueryDataStorage
await storage.store_articles([...])

# ✅ CORRECT - For vector search
from app.db.vector_store import get_production_vector_store

vs = get_production_vector_store()  # Returns BigQuery vector store
results = await vs.similarity_search("query", k=10)
```

> **GCP defaults are hardcoded** in `gcp_storage.py` and `settings.py`.
> No env vars needed for production project/bucket.

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
- monitoring/              → Production health checks
- health/                  → Diagnostics
- operations/backfill/     → Data backfill operations
- operations/maintenance/  → Maintenance tasks
- operations/triggers/     → Pipeline triggers & orchestrators
- testing/                 → Development tests (test_*.py, check_*.py)
- verification/            → Post-deploy checks

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

### 4. Production Debug Logging (MANDATORY for User-Facing Features)

**Use module prefixes for Cloud Run filtering:**

```python
import time
import asyncio
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Use [MODULE_NAME] prefix for easy log filtering in production
async def process_request(request):
    start_time = time.time()
    request_id = str(uuid.uuid4())[:8]  # Short ID for correlation
    
    logger.info(
        f"[MODULE_NAME] Request {request_id} START: "
        f"param='{request_param}', mode={mode}"
    )
    
    try:
        # ... processing ...
        
        elapsed = time.time() - start_time
        logger.info(
            f"[MODULE_NAME] Request {request_id} COMPLETE: "
            f"{elapsed:.2f}s, results={result_count}"
        )
        return result
        
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(
            f"[MODULE_NAME] Request {request_id} FAILED: "
            f"{elapsed:.2f}s, error_type={type(e).__name__}, error={str(e)}",
            exc_info=True  # Include stack trace
        )
        raise
```

**LLM timeout protection (REQUIRED for all LLM calls):**

```python
# Wrap LLM calls with timeout to prevent hanging
try:
    response = await asyncio.wait_for(
        llm.ainvoke(messages),
        timeout=120.0  # 2 minutes max
    )
    logger.info(f"[MODULE_NAME] LLM call COMPLETE: {elapsed:.2f}s")
except asyncio.TimeoutError:
    logger.error(f"[MODULE_NAME] LLM call TIMEOUT: exceeded 120s")
    raise Exception("Request timed out waiting for AI response. Please try again.")
```

**Tool execution tracking:**

```python
# Log tool calls with START/COMPLETE/FAILED
tool_start = time.time()
logger.info(f"[MODULE_NAME] Tool START: {tool_name}, args={args_preview}")

try:
    result = await tool.execute(args)
    tool_elapsed = time.time() - tool_start
    logger.info(
        f"[MODULE_NAME] Tool COMPLETE: {tool_name}, "
        f"{tool_elapsed:.2f}s, result_len={len(result)}"
    )
except Exception as e:
    tool_elapsed = time.time() - tool_start
    logger.error(
        f"[MODULE_NAME] Tool FAILED: {tool_name}, "
        f"{tool_elapsed:.2f}s, error={str(e)}",
        exc_info=True
    )
    raise
```

**Real Examples:**
- See `backend/app/agents/pipeline/agent.py` - `[PIPELINE_AGENT]` prefix
- See `backend/app/api/routes/exa_pipeline.py` - `[PIPELINE_API]` prefix
- See `backend/app/agents/adhoc_briefing/agent.py` - `[ADHOC_AGENT]` prefix

**Production debugging:**
```bash
# Filter Cloud Run logs by module
gcloud logging read "resource.type=cloud_run_revision AND textPayload=~\"[PIPELINE_\"" --limit=50

# Find timeouts
gcloud logging read "resource.type=cloud_run_revision AND textPayload=~\"TIMEOUT\"" --limit=20
```
```

---

## Testing Requirements

### Before Committing

```bash
# 1. Check for import errors
cd backend
python -c "from app.mcp.server import get_all_mcp_tools; print(f'Loaded {len(get_all_mcp_tools())} tools')"

# 2. Run health check
python scripts/monitoring/production_dashboard.py

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
| Check prod health | `scripts/monitoring/` |
| Debug ingestion | `scripts/health/` |
| Run backfill | `scripts/operations/backfill/` |
| Maintenance tasks | `scripts/operations/maintenance/` |
| Trigger ingestion | `scripts/operations/triggers/` |
| Test features | `scripts/testing/` (all test_*.py and check_*.py files) |
| Verify deploys | `scripts/verification/` |

---

*Last updated: January 8, 2026 (Session 68 - Production Debug Logging Guidelines)*
