# Ad-Hoc Briefing Agent

On-demand AI briefings using Claude Haiku with real-time web search via Tavily.

## Files

| File | Purpose |
|------|---------|
| `agent.py` | `AdHocBriefingAgent` class - generates briefings with streaming support |
| `session_manager.py` | Session state management for follow-up tracking |
| `__init__.py` | Module exports |

## Session Management

The session manager provides stateful conversation tracking across HTTP requests:

```python
from app.agents.adhoc_briefing import get_session_manager, BriefingSession

# Get or create a session
manager = get_session_manager()
session = manager.get_or_create_session(session_id)  # None creates new

# Session tracks:
# - follow_up_count: Number of follow-up questions asked
# - conversation_history: List of (role, content) tuples
# - created_at, last_accessed: Timestamps
```

### Configuration

- **TTL**: 30 minutes of inactivity
- **Max Sessions**: 1000 (LRU eviction when exceeded)
- **Max Follow-ups**: 2 (then redirects to Deep Research)

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/briefing/adhoc` | POST | Generate briefing (include `session_id` for continuity) |
| `/api/briefing/adhoc/stream` | POST | Streaming variant |
| `/api/briefing/adhoc/session/{id}` | GET | Get session info |
| `/api/briefing/adhoc/session/{id}` | DELETE | End session |
| `/api/briefing/adhoc/sessions/stats` | GET | Manager statistics |

## Usage

### Basic (stateless)

```python
agent = AdHocBriefingAgent()
response = await agent.generate_briefing("What's new in carbon fiber?")
```

### With Session (stateful)

```python
from app.agents.adhoc_briefing import AdHocBriefingAgent, get_session_manager

manager = get_session_manager()
session = manager.create_session()

agent = AdHocBriefingAgent()
response = await agent.generate_briefing(
    question="What's new in carbon fiber?",
    session=session
)

# Follow-up (session tracks count)
response2 = await agent.generate_briefing(
    question="How does this affect pricing?",
    is_follow_up=True,
    session=session
)

# After 2 follow-ups, session.should_redirect_to_deep_research() returns True
```

## Model

Uses `claude-3-5-haiku-latest` for fast responses (~2-3 seconds).

For deeper analysis, users are redirected to Deep Research after 2 follow-ups.
