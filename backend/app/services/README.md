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
- `backend/scripts/testing/check_lowium_bug.py` - Check priority value distribution
- `backend/check_digest_data.py` - Check raw BigQuery data
- `backend/check_digest_service.py` - Test service output

**Data Quality** (verified Jan 5, 2026):
- Total items: 3,767
- Feed eligible: 94.9%
- Priority distribution: Healthy (high: 702, medium: 1,282, low: 1,783)
- Known issue: 12% of items have capitalized priority values (`Low` vs `low`) - low priority fix

---

### `digest_classifier.py` - Content Classification

**Purpose**: Classifies articles into digest categories using LLM.

**Categories**:
- Priority (competitor, market, regulatory, product, c1_mention, general)
- Priority level (critical, high, medium, low)
- Entities (companies, materials, topics, industries)

**Used By**: Ingestion pipeline to populate `digest_items` table

---

### `podcast_service.py` - Podcast Generation Service

**Purpose**: Generates AI podcast scripts and audio using ElevenLabs TTS.

**Key Features**:
- Script generation from content (conversational, professional, brief styles)
- Multi-speaker support (Host + Analyst voices)
- ElevenLabs TTS integration
- Audio file caching

**Voices**:
| Role | Name | Voice ID | Description |
|------|------|----------|-------------|
| Host | Rachel | `21m00Tcm4TlvDq8ikWAM` | Calm, professional |
| Analyst | Josh | `TxGEqnHWrfWFTfGW9XjX` | Conversational |

**API Endpoints**:
- `POST /api/podcast/script` - Generate podcast script from content
- `POST /api/podcast/audio` - Generate audio from script
- `GET /api/podcast/audio/{id}` - Retrieve generated audio file
- `GET /api/podcast/briefing/{id}` - Stream weekly briefing podcast from GCS
- `GET /api/podcast/voices` - List available voices

**Weekly Briefing Integration**:
The weekly executive briefing pipeline (`weekly_briefing.py`) uses ElevenLabs directly to generate podcast audio:
1. `_format_text_for_speech()` - Cleans text for TTS (removes citations, expands "$2.4B" → "2.4 billion dollars")
2. `_build_podcast_script()` - Creates natural narration with "net new" vs "continuing" phrasing
3. `_generate_podcast()` - Calls ElevenLabs API, uploads to GCS

**Storage**: GCS bucket `gen-lang-client-0436975498-c1-hub-data` in `/podcasts/{briefing_id}.mp3`

**Note**: GCS bucket has public access prevention, so podcasts are streamed through the backend API endpoint `/api/podcast/briefing/{id}`. This endpoint supports HTTP Range requests (206 Partial Content) for proper browser audio seeking.

**Configuration** (in `settings.py`):
```python
elevenlabs_api_key: str = ""
elevenlabs_voice_id: str = "21m00Tcm4TlvDq8ikWAM"  # Rachel
elevenlabs_model: str = "eleven_monolingual_v1"
elevenlabs_voice_stability: float = 0.5
elevenlabs_voice_similarity_boost: float = 0.75
```

---

### `memory_service.py` - Long-Term Memory System

**Purpose**: Provides organizational memory for the C1 Intelligence Hub.

**Data Source**: ✅ **BigQuery** `org_preferences` and `memory_log` tables

**Key Features**:
- Manual preferences (priority/blocked topics)
- Memory log (saved briefings and research exports)
- Vector search with Vertex AI embeddings
- Time-weighted scoring (newer = more relevant)
- Team-scoped context
- Cleanup of expired memories (60-day TTL)

> 📖 See [MEMORY_README.md](./MEMORY_README.md) for full architecture documentation.

**Key Functions**:
- `build_agent_context(query, user_team)` - Main entry point for agents
- `get_org_preferences(user_team)` - Get priority/blocked topics
- `get_relevant_memories(query, user_team)` - Vector search with scoring
- `save_to_memory_log(...)` - Save briefings/research

**API Endpoints**: `/api/memory/*` - See [Memory Routes](../api/routes/memory.py)

**Used By**: Ad-Hoc Briefing agent, Deep Research save feature

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

*Last updated: January 6, 2026*
