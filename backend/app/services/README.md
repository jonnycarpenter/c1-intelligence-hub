# Services Layer (`app/services/`)

> **Business Logic & Domain Services**

This directory contains service classes that implement business logic and orchestrate interactions between the API layer and data layer.

---

## Services

### `api_partner_health.py` - API Partner Health Checks

**Purpose**: Lightweight connectivity checks for ingestion data partners.

**Partners**:
- Exa (web search, press releases)
- Tavily (web search)
- SEC API (sec-api.io)
- FMP (Financial Modeling Prep)
- StockNewsAPI
- API Ninjas (earnings calendar)

**Usage**:
```python
from app.services.api_partner_health import check_api_partners

results = await check_api_partners()
```

---

### `digest_service.py` - Intelligence Digest Service

**Purpose**: Manages the intelligence digest (news feed/DRUMBEAT) for the Pulse and Discovery tabs.

**Data Source**: ✅ **BigQuery** `digest_items` table (verified Jan 5, 2026)

**Key Features**:
- Queries classified articles from BigQuery
- LLM-generated executive summaries (Claude Sonnet 4.5)
- 15-minute cache TTL
- Filtering by category, priority, time range
- **Configurable limit** (default 100, max 1000) - Added Jan 17, 2026
- Coverage tracking (duplicate article detection)

**Usage**:
```python
from app.services.digest_service import get_digest_service

service = get_digest_service()

# Default (100 items, 72h)
digest = await service.get_digest(hours=72)

# Discovery tab (500 items, 30 days, medium+ priority)
digest = await service.get_digest(hours=720, limit=500, priorities=[...])
```

**API Endpoints**:
- `GET /api/digest` - Get digest with optional filters
  - `?hours=72` - Time window (default 72)
  - `?limit=100` - Max items (default 100, max 1000)
  - `?categories=...` - Comma-separated categories
  - `?priorities=...` - Comma-separated priorities (Critical,High,Medium,Low)
- `POST /api/digest/refresh` - Force cache refresh
- `GET /api/digest/item/{id}` - Get single item
- `GET /api/digest/stats` - Get statistics only

**Data Flow**:
```
Frontend (useDigest.ts)
    ↓
API (/api/digest?hours=720&limit=500&priorities=Critical,High,Medium)
    ↓
DigestService.get_digest(hours, categories, priorities, limit)
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
- **Priorities filter** (optional) - e.g., exclude Low priority

**Cache Behavior**:
- TTL: 15 minutes
- Keyed by: `hours`, `categories`, `priorities`, `limit`
- Clear cache: Call `refresh_digest()` or `trigger_ingestion()`

**Tab-Specific Configuration** (in `page.tsx`):
| Tab | Hours | Limit | Priorities |
|-----|-------|-------|------------|
| Discovery | 720 (30d) | 500 | Critical, High, Medium |
| Pulse | 168 (7d) | 100 | All |

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
The weekly executive briefing pipeline (`weekly_briefing.py`) generates a **conversational two-voice podcast** using ElevenLabs **Text-to-Dialogue API**:
1. `_format_text_for_speech()` - Cleans text for TTS (removes citations, expands "$2.4B" → "2.4 billion dollars")
2. `_build_podcast_dialogue()` - Creates dialogue turns between Host (Rachel) and Analyst (Josh)
3. `_generate_podcast()` - **Single API call** to `/v1/text-to-dialogue` with all turns, uploads to GCS

**Dialogue Format**:
- **Host (Rachel)**: Opens briefing, introduces sections, transitions, closes
- **Analyst (Josh)**: Delivers content - BLUF, headlines, insights, trends
- Natural back-and-forth creates an engaging listen vs monotone narration

**Text-to-Dialogue API** (as of Jan 7, 2026):
- Model: `eleven_v3` (required by dialogue endpoint)
- Single API call handles all speaker transitions smoothly
- Better audio quality than concatenating individual TTS calls
- Uses `httpx` directly (ElevenLabs Python SDK doesn't support this endpoint yet)

**Storage**: GCS bucket `gen-lang-client-0436975498-c1-hub-data` in `/podcasts/{briefing_id}.mp3`

**Note**: GCS bucket has public access prevention, so podcasts are streamed through the backend API endpoint `/api/podcast/briefing/{id}`. This endpoint supports HTTP Range requests (206 Partial Content) for proper browser audio seeking.

**Configuration** (in `settings.py`):
```python
elevenlabs_api_key: str = ""
elevenlabs_host_voice_id: str = "21m00Tcm4TlvDq8ikWAM"  # Rachel
elevenlabs_analyst_voice_id: str = "TxGEqnHWrfWFTfGW9XjX"  # Josh
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

*Last updated: January 17, 2026*
