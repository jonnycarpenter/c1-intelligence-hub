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
from app.db.gcp_storage import get_storage

storage = await get_storage()  # Returns BigQueryDataStorage
await storage.store_articles([...])
```

**Deduplication Methods** (added January 4, 2026):
```python
# Check if URL already exists in BigQuery articles table
article_id = await storage.check_duplicate(url)  # Returns article_id or None

# Load recent articles for in-memory dedup cache
recent = await storage.get_recent_articles_for_dedup(hours=168, limit=2000)
```

**JSON Parsing Helper** (added January 5, 2026):
```python
# _safe_parse_list() handles inconsistent BigQuery field formats:
# - JSON arrays: '["Tesla", "Boeing"]'
# - Comma-separated strings: 'Tesla, Boeing'
# Used by get_digest_items(), get_weekly_briefing(), etc.
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
- ✅ **Deduplication** - Migrated to BigQuery (January 4, 2026)
- ⏳ Still used by classifier/entity_linker for `list_entities()`
- ⏳ Still used by briefing generators for briefing storage
- New code should use `gcp_storage.py` only

**Remaining SQLite Usage** (to be migrated):
- `list_entities()` - Used by ContentClassifier and EntityLinker
- `briefing_summaries` - To be migrated
- `weekly_briefings` - To be migrated
- `pre_briefings` - To be migrated

**Already Migrated to BigQuery**:
- `corpus_items` → `digest_items` table
- `check_duplicate()` → `gcp_storage.py` (for deduplication)

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

### Core Content Tables

| Table | Purpose | Written By |
|-------|---------|------------|
| `articles` | Raw articles (title, content, URL, source_type) | Ingestion pipeline |
| `article_chunk_embeddings` | **Vector store** - chunked text + Vertex AI embeddings for semantic search | `bq_vector_store.py` |
| `digest_items` | Classified articles with summaries, categories, priorities | Ingestion pipeline |
| `article_tags` | Normalized tags (companies, materials, topics) for trending analytics | Ingestion pipeline |
| `article_images` | Extracted images with vision analysis | Image enricher |

### Briefings & Reports

| Table | Purpose | Written By |
|-------|---------|------------|
| `briefings` | Scheduled briefings (weekly, quarterly) | Briefing generators |
| `pre_briefings` | Pre-generated briefing content | Briefing generators |
| `weekly_briefings` | Weekly intelligence summaries | Briefing generators |
| `adhoc_briefings` | On-demand user-requested briefings | Agent tools |
| `research_reports` | Long-form research reports | Agent tools |

### Reference Data

| Table | Purpose | Written By |
|-------|---------|------------|
| `companies` | Tracked companies (ticker, name, sector) | Admin/setup |
| `materials` | Materials taxonomy | Admin/setup |
| `industries` | Industry classifications | Admin/setup |
| `commodity_prices` | Historical commodity pricing | Price fetcher |
| `freight_rates` | Drewry freight rate indices | Freight scraper |

### ImportYeti Supply Chain (`iy_*` tables)

| Table | Purpose |
|-------|---------|
| `iy_companies` | ImportYeti company profiles |
| `iy_suppliers` | Supplier records |
| `iy_company_suppliers` | Company-supplier relationships |
| `iy_supplier_customers` | Supplier customer lists |
| `iy_shipment_trends` | Shipment volume trends |
| `iy_concentration_metrics` | Supply chain concentration analysis |
| `iy_competitor_overlap` | Competitor supplier overlap |
| `iy_change_events` | Supply chain change detection |
| `iy_snapshots` | Point-in-time snapshots |
| `iy_product_market` | Product/market classifications |

### Datasheets

| Table | Purpose |
|-------|---------|
| `datasheets` | Technical datasheets (PDFs) |
| `datasheet_suppliers` | Datasheet supplier metadata |
| `datasheet_scrape_runs` | Scraping job history |

### User & System

| Table | Purpose |
|-------|---------|
| `user_preferences` | User settings and preferences |
| `org_preferences` | Organization-level settings |
| `memory_log` | Agent memory/context storage |
| `ingestion_events` | Pipeline execution logs |

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
