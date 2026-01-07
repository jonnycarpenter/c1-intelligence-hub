# Memory System Architecture

> **Status: ✅ Implemented & Integrated** (January 2026)
>
> Core memory system is fully functional with BigQuery storage, Vertex AI embeddings, and agent integration.

---

## Overview

The C1 Intelligence Hub memory system provides organizational memory that makes the AI feel like "part of the team":

1. **Manual Preferences** - Topics to prioritize or block from intelligence
2. **Memory Log** - Auto-saved briefings/research when users explicitly save them
3. **Time-Weighted Relevance** - Newer memories score higher, auto-cleanup after 60 days
4. **Team-Scoped Context** - Memories tagged by team for better relevance

**No user authentication required.** Memory is org-level with optional team filtering.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    MEMORY FLOW                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  LAYER 1: PREFERENCES (~100 tokens, always included)        │
│  └─ org_preferences table                                   │
│     ├─ Priorities: ["resin pricing", "AOC"]                 │
│     └─ Blocks: ["Acme Corp"] (0.3x penalty)                 │
│                                                             │
│  LAYER 2: MEMORIES (~200-500 tokens, retrieved by vector)   │
│  └─ memory_log table                                        │
│     ├─ Past briefings user saved                            │
│     └─ Research exports                                     │
│                                                             │
│  LAYER 3: AGENT INJECTION                                   │
│  └─ build_agent_context() → prompt addition                 │
│     └─ Injected into Ad-Hoc Briefing agent prompts          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Database Schema (BigQuery)

### Table 1: `org_preferences`

Stores manual user preferences. Small, always loaded into agent context.

| Column | Type | Description |
|--------|------|-------------|
| `preference_id` | STRING | Unique ID (e.g., `pref_abc123`) |
| `preference_type` | STRING | `'priority'` or `'block'` |
| `topic` | STRING | Entity/topic name |
| `description` | STRING | Optional human note |
| `scope` | STRING | `'org'` or `'team'` |
| `team` | STRING | Team name (null for org-wide) |
| `active` | BOOL | Whether active |
| `created_at` | TIMESTAMP | Creation time |
| `created_by` | STRING | Creator name |

### Table 2: `memory_log`

Stores saved briefings and research exports. Uses Vertex AI embeddings for vector search.

| Column | Type | Description |
|--------|------|-------------|
| `memory_id` | STRING | Unique ID |
| `source` | STRING | `'briefing'` or `'research_export'` |
| `title` | STRING | Display label |
| `content` | TEXT | Full text content |
| `query` | STRING | Original query (for research) |
| `entities` | ARRAY<STRING> | Extracted entities |
| `embedding` | ARRAY<FLOAT64> | Vertex AI embedding (768 dims) |
| `team` | STRING | Team that created it |
| `pinned` | BOOL | Pinned = never expires (max 10/team) |
| `expires_at` | TIMESTAMP | Auto-set to created_at + 60 days |
| `created_at` | TIMESTAMP | Creation time |
| `created_by` | STRING | Creator name |

---

## Core Files

### Backend

| File | Purpose |
|------|---------|
| [`memory_service.py`](./memory_service.py) | Core business logic for all memory operations |
| [`../api/routes/memory.py`](../api/routes/memory.py) | REST API endpoints |
| [`../agents/adhoc_briefing/agent.py`](../agents/adhoc_briefing/agent.py) | Agent that uses memory context |
| [`../../scripts/create_memory_tables.sql`](../../scripts/create_memory_tables.sql) | BigQuery table creation script |

### Frontend

| File | Purpose |
|------|---------|
| `components/memory/PreferencesPanel.tsx` | UI for managing priority/blocked topics |
| `components/memory/MemoryLog.tsx` | UI for viewing/managing saved memories |
| `components/research/ResearchReport.tsx` | Save to Memory button on research reports |
| `lib/api.ts` | API client methods |

---

## Key Functions in `memory_service.py`

### `build_agent_context(query, user_team)`

The main entry point for agents. Retrieves preferences + relevant memories and formats them for prompt injection.

```python
async def build_agent_context(query: str, user_team: str = None) -> AgentContext:
    """
    Returns:
        AgentContext with:
        - preferences: OrgPreferences object
        - relevant_memories: List of scored memories
        - prompt_addition: Formatted string to inject into prompt
        - proactive_intro: Optional "I remember when..." intro
    """
```

### `get_relevant_memories(query, user_team, limit)`

Vector search with time-weighted scoring:

```
final_score = base_similarity × time_decay × team_boost × block_penalty

Where:
- base_similarity: 1 - cosine_distance (0 to 1)
- time_decay: 1.0 → 0.3 over 60 days (linear)
- team_boost: 1.2× for same team
- block_penalty: 0.3× if matches blocked topic
```

### `save_to_memory_log(...)`

Saves a briefing or research export with auto-generated embeddings.

---

## API Endpoints

All endpoints are under `/api/memory/`:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/preferences` | GET | Get all preferences (org + team) |
| `/preferences` | POST | Add a preference |
| `/preferences/{id}` | DELETE | Remove a preference |
| `/log` | POST | Save to memory log |
| `/log` | GET | Get memory log entries |
| `/log/{id}` | DELETE | Delete a memory |
| `/{id}/pin` | PATCH | Toggle pin status |
| `/block` | POST | Block a topic |
| `/relevant` | GET | Get relevant memories for a query |
| `/context` | GET | Get full agent context |
| `/cleanup` | POST | Run expired memory cleanup (scheduled job) |

---

## Agent Integration

### Ad-Hoc Briefing (Implemented ✅)

The Ad-Hoc Briefing agent calls `build_agent_context()` at the start of each request:

```python
# In generate_briefing():
memory_context = await build_agent_context(question, user_team)
memory_prompt_addition = memory_context.prompt_addition

# Injected into the full prompt
full_prompt = f"""{context_string}

{memory_prompt_addition}

{search_context}
...
"""
```

The `X-User-Team` header is passed from the frontend to scope context by team.

### Deep Research (Save Only)

Research reports can be saved to memory via the "Save to Memory" button in the Executive Summary header.

### Pipeline Agent (Not Yet Integrated)

Could be added later if there's value in remembering prospecting patterns.

---

## Frontend Integration

### Preferences Panel

Located at: **Data & Preferences → Preferences tab**

Users can:
- Add priority topics (boosted in results)
- Add blocked topics (0.3× penalty)
- Scope to org-wide or team-specific
- Remove preferences

### Memory Log

Located at: **Data & Preferences → Memory tab**

Users can:
- View all saved memories
- Search/filter memories
- Pin important memories (max 10/team, never expire)
- Delete memories
- See expiration countdown

### Save to Memory Button

Located in the **Research Report** Executive Summary header (for Deep Research).

States:
- Idle: "Save to Memory" with bookmark icon
- Saving: Spinner with "Saving..."
- Saved: Green checkmark
- Error: Red (auto-resets after 3s)

---

## Memory Lifecycle

```
┌─────────────────────────────────────────────────────────────┐
│                    MEMORY LIFECYCLE                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Created ──► Active (0-60 days)                             │
│                │                                            │
│                ├──► Time-weighted scoring applies           │
│                │    (newer = higher relevance)              │
│                │                                            │
│                ├──► Day 60: Auto-deleted by cleanup job     │
│                │    (unless pinned)                         │
│                │                                            │
│                └──► Pinned: Never expires                   │
│                     (max 10 per team)                       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Teams

From C1 org structure:
1. Sales East
2. Sales West
3. Marketing
4. Product/Supplier
5. All Others (default)

Team is set via `localStorage.getItem('userTeam')` and passed as `X-User-Team` header.

---

## Configuration

Environment variables:
- `GCP_PROJECT_ID` - Google Cloud project
- `GCP_DATASET_ID` - BigQuery dataset (contains `org_preferences` and `memory_log` tables)
- `JOB_SECRET_KEY` - Secret for scheduled cleanup job

---

## Scheduled Jobs

### Memory Cleanup

Runs daily to delete expired, unpinned memories:

```yaml
# Cloud Scheduler
name: memory-cleanup
schedule: "0 3 * * *"  # Daily at 3 AM CST
uri: ${SERVICE_URL}/api/memory/cleanup
```

---

## Testing

### Manual Testing

1. **Preferences Test**:
   - Add a priority topic in Data & Preferences → Preferences
   - Ask related question on Pulse tab
   - Verify the topic is emphasized in response

2. **Save to Memory Test**:
   - Run a Deep Research query
   - Click "Save to Memory" button
   - Check Data & Preferences → Memory tab

3. **Context Injection Test**:
   - Check backend logs for "Injecting memory context into ad-hoc briefing"
   - Verify character count in logs

---

## Related Documentation

- [Services README](./README.md) - Other services in this directory
- [API Routes](../api/routes/README.md) - All API endpoints
- [Ad-Hoc Briefing Agent](../agents/adhoc_briefing/README.md) - Agent that uses memory

---

*Last updated: January 6, 2026*
