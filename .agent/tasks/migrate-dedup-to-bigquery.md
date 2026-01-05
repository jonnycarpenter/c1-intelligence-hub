# Task: Migrate Deduplication Service to BigQuery

**Priority**: HIGH  
**Created**: 2026-01-04  
**Status**: ✅ COMPLETED (2026-01-04)

## Summary

Successfully migrated `DeduplicationService` from SQLite to BigQuery:
1. Added `check_duplicate()` and `get_recent_articles_for_dedup()` to `gcp_storage.py`
2. Updated `DeduplicationService` to use BigQuery storage instead of SQLite
3. Updated `orchestrator.py` to initialize dedup without SQLite db param

**Remaining SQLite usage**: classifier/entity_linker still use `list_entities()` from SQLite.
This is a separate migration task - see "Clean Up Other SQLite References" below.

---

## Problem (RESOLVED)

The `DeduplicationService` in `app/ingestion/processing/deduplication.py` currently uses the **deprecated SQLite database** (`app/db/database.py`) for duplicate checking. This violates the "BigQuery ONLY" rule in `CODING_RULES.md`.

### Current SQLite References in Ingestion

| File | Line | Usage |
|------|------|-------|
| `orchestrator.py` | 107 | `self.db = get_db()` for DeduplicationService |
| `orchestrator.py` | 110 | `DeduplicationService(self.db)` |
| `deduplication.py` | 39 | `self.db = db` (SQLite) |
| `deduplication.py` | 47 | `self.db.query_corpus()` (SQLite) |
| `deduplication.py` | 64 | `self.db.check_duplicate()` (SQLite) |
| `pre_briefing.py` | 69 | `self.db = get_db()` |
| `briefing.py` | 88 | `self.db = get_db()` |
| `weekly_briefing.py` | 149 | `self.db = get_db()` |

## Solution

### 1. Add `check_duplicate` to BigQuery client

Add to `app/services/gcp_storage.py` or `app/db/bigquery_client.py`:

```python
async def check_duplicate(self, url: str) -> Optional[str]:
    """
    Check if URL already exists in articles table.
    Returns article_id if duplicate, None otherwise.
    """
    query = f"""
    SELECT id FROM `{self.project}.{self.dataset}.articles`
    WHERE url = @url
    LIMIT 1
    """
    params = [bigquery.ScalarQueryParameter("url", "STRING", url)]
    job_config = bigquery.QueryJobConfig(query_parameters=params)
    
    results = list(self.client.query(query, job_config=job_config).result())
    if results:
        return results[0].id
    return None

async def get_recent_urls_and_titles(self, hours: int = 168, limit: int = 1000) -> List[Dict]:
    """
    Get recent articles for dedup cache loading.
    """
    query = f"""
    SELECT id, url, title, published_at
    FROM `{self.project}.{self.dataset}.articles`
    WHERE published_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {hours} HOUR)
    ORDER BY published_at DESC
    LIMIT {limit}
    """
    results = self.client.query(query).result()
    return [{"id": r.id, "url": r.url, "title": r.title} for r in results]
```

### 2. Update DeduplicationService

Modify `app/ingestion/processing/deduplication.py`:

```python
# BEFORE
from app.db.database import Database

class DeduplicationService:
    def __init__(self, db: Database):
        self.db = db  # SQLite

# AFTER  
from app.services.gcp_storage import get_storage

class DeduplicationService:
    def __init__(self, storage=None):
        self.storage = storage  # BigQuery
    
    async def initialize(self):
        if not self.storage:
            self.storage = await get_storage()
```

### 3. Update Orchestrator

Modify `app/ingestion/orchestrator.py`:

```python
# REMOVE
from app.db.database import get_db
self.db = get_db()
self.dedup_service = DeduplicationService(self.db)

# REPLACE WITH
self.dedup_service = DeduplicationService()
await self.dedup_service.initialize()  # Uses BigQuery via gcp_storage
```

### 4. Clean Up Other SQLite References

After dedup migration, audit remaining SQLite usages in:
- `pre_briefing.py` - May need BigQuery migration
- `briefing.py` - May need BigQuery migration  
- `weekly_briefing.py` - May need BigQuery migration

## Testing

```bash
# After changes:
cd backend

# 1. Test import works
python -c "from app.ingestion.processing.deduplication import DeduplicationService; print('OK')"

# 2. Test dedup against BigQuery
python -c "
import asyncio
from app.ingestion.processing.deduplication import DeduplicationService
async def test():
    ds = DeduplicationService()
    await ds.initialize()
    print(f'Cache loaded: {len(ds._url_cache)} URLs')
asyncio.run(test())
"

# 3. Run ingestion test
python -c "from app.mcp.server import get_all_mcp_tools; print('OK')"
```

## Acceptance Criteria

- [ ] No `from app.db.database import` in ingestion code
- [ ] DeduplicationService uses BigQuery via `gcp_storage.py`
- [ ] `check_duplicate()` queries `articles` table in BigQuery
- [ ] `load_recent_cache()` queries BigQuery instead of SQLite
- [ ] All tests pass
- [ ] Deploy to Cloud Run and verify ingestion works

## Notes

- The SQLite `database.py` file can remain for now (other parts of codebase may still reference it)
- Focus on ingestion pipeline first - that's where dedup is critical
- Consider adding an index on `articles.url` in BigQuery if not exists
