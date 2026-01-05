# Services Layer (`app/services/`)

> **Business Logic & Domain Services**

This directory contains service classes that implement business logic and orchestrate interactions between the API layer and data layer.

---

## Services

### `digest_service.py` - Intelligence Digest Service

**Purpose**: Manages the intelligence digest (news feed/DRUMBEAT) for the Pulse tab.

**Data Source**: ✅ **BigQuery** `digest_items` table (verified Jan 5, 2026)

**Key Features**:
- Queries classified articles from BigQuery
- LLM-generated executive summaries (Claude Sonnet 4.5)
- 15-minute cache TTL
- Filtering by category, priority, time range
- Coverage tracking (duplicate article detection)

**Usage**:
```python
from app.services.digest_service import get_digest_service

service = get_digest_service()
digest = await service.get_digest(hours=72)  # Last 3 days
```

**API Endpoints**:
- `GET /api/digest` - Get digest with optional filters
- `POST /api/digest/refresh` - Force cache refresh
- `GET /api/digest/item/{id}` - Get single item
- `GET /api/digest/stats` - Get statistics only

**Data Flow**:
```
Frontend (useDigest.ts)
    ↓
API (/api/digest)
    ↓
DigestService.get_digest()
    ↓
BigQueryDataStorage.get_digest_items()
    ↓
BigQuery: digest_items table
```

**Query Filters** (in `BigQueryDataStorage.get_digest_items()`):
- `published_at` within lookback window (default: 72 hours)
- `published_at` not in future (excludes bad date parsing)
- `published_at` not within 30 min of `classified_at` (excludes defaulted dates)
- `ingested_at >= '2025-12-28'` (data before this has unreliable dates)
- `confidence >= 0.3` (minimum classifier confidence)

**Cache Behavior**:
- TTL: 15 minutes
- Keyed by: `hours`, `categories`, `priorities`
- Clear cache: Call `refresh_digest()` or `trigger_ingestion()`

**Diagnostic Scripts**:
- `backend/check_digest_data.py` - Check raw BigQuery data
- `backend/check_digest_service.py` - Test service output

---

### `digest_classifier.py` - Content Classification

**Purpose**: Classifies articles into digest categories using LLM.

**Categories**:
- Priority (competitor, market, regulatory, product, c1_mention, general)
- Priority level (critical, high, medium, low)
- Entities (companies, materials, topics, industries)

**Used By**: Ingestion pipeline to populate `digest_items` table

---

## Adding a New Service

1. Create service class in this directory
2. Implement singleton pattern with `get_<service>_service()` factory
3. Add async initialization if needed
4. Document in this README
5. Add to `app/services/__init__.py` exports

---

## Related Documentation

- [Database Layer](../db/README.md) - BigQuery storage
- [API Routes](../api/routes/README.md) - REST endpoints
- [Ingestion Pipeline](../ingestion/README.md) - Data collection

---

*Last updated: January 5, 2026*
