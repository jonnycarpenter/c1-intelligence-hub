# Database Layer (`app/db/`)

> **Single Source of Truth: BigQuery**

This directory contains the database abstraction layer for C1 Intelligence Hub.

---

## Current Architecture (January 2026)

```
app/db/
├── gcp_storage.py      # PRIMARY - BigQuery + GCS storage
├── bq_vector_store.py  # Vector store using Vertex AI embeddings
├── vector_store.py     # Thin wrapper → always returns BigQuery vector store
├── database.py         # ⚠️ DEPRECATED - Legacy SQLite (DO NOT USE for new code)
└── __init__.py         # Exports
```

### Production Storage: `gcp_storage.py`

The main storage layer with **hardcoded defaults** for production:

```python
# Defaults (hardcoded for reliability)
GCP_PROJECT_ID = "gen-lang-client-0436975498"
GCS_BUCKET = "gen-lang-client-0436975498-c1-hub-data"
BQ_DATASET = "c1_intelligence"
```

**Key Classes:**
- `BigQueryDataStorage` - Article storage to BigQuery
- `GCSBucketStorage` - File storage to GCS  
- `GCPConfig` - Configuration dataclass with hardcoded defaults
- `LocalDataStorage` - ⚠️ DEPRECATED fallback (prints warning if used)

**Factory Function:**
```python
from app.db.gcp_storage import get_data_storage

storage = get_data_storage()  # Returns BigQueryDataStorage
await storage.store_articles([...])
```

### Vector Store: `bq_vector_store.py`

BigQuery-native vector search using Vertex AI `text-embedding-005`:

```python
from app.db.bq_vector_store import BigQueryVectorStore

vs = BigQueryVectorStore()
results = await vs.similarity_search("carbon fiber composites", k=10)
```

### Wrapper: `vector_store.py`

Thin wrapper that **always** returns BigQuery vector store:

```python
from app.db.vector_store import get_production_vector_store

vs = get_production_vector_store()  # Always BigQuery
```

> **Note**: This file previously contained 582 lines of ChromaDB code. 
> It was replaced with a ~50-line wrapper in January 2026.

---

## ⚠️ Deprecated: `database.py`

This file still contains SQLite code for legacy compatibility but should **NOT** be used for new features.

**Status**: 
- Still imported by some generators for briefing storage
- Will be fully migrated to BigQuery in future cleanup
- New code should use `gcp_storage.py` only

**Legacy Tables** (in SQLite on GCS):
- `corpus_items` - Migrated to BigQuery `digest_items`
- `briefing_summaries` - To be migrated
- `weekly_briefings` - To be migrated
- `pre_briefings` - To be migrated

---

## Migration Scripts

### SQLite → BigQuery Migration

If you have data in the GCS-mounted SQLite database that needs migration:

```bash
# 1. Download SQLite from GCS
gsutil cp gs://gen-lang-client-0436975498-c1-hub-data/c1_corpus.db backend/data/

# 2. Run migration script
cd backend
python migrate_sqlite_to_bq.py
```

The script:
- Reads from `data/c1_corpus.db`
- Transforms to BigQuery schema
- Skips duplicates (by URL)
- Inserts into `digest_items` table

---

## BigQuery Tables

| Table | Purpose | Written By |
|-------|---------|------------|
| `digest_items` | Classified articles with summaries | Ingestion pipeline |
| `articles` | Raw articles with embeddings | Ingestion pipeline |
| `ingestion_events` | Pipeline execution logs | Orchestrator |
| `briefings` | Generated briefings | Briefing generators |
| `user_preferences` | User configuration | API |

---

## Configuration

Environment variables (optional - defaults are hardcoded):

```bash
GCP_PROJECT_ID=gen-lang-client-0436975498       # Default
GCS_BUCKET_NAME=gen-lang-client-0436975498-c1-hub-data  # Default
BIGQUERY_DATASET=c1_intelligence                 # Default
```

The hardcoded defaults ensure the system works even if env vars are missing.

---

*Last updated: January 4, 2026*
