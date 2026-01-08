# Shared Utilities

Reusable utility modules used across ingestion, agents, and API layers.

## Modules

### Text Processing
- `chunking.py` - Semantic text chunking for embeddings (used by ingestion)
- `date_extraction.py` - Extract publication dates from article text
- `date_utils.py` - Date parsing and normalization helpers

### LLM Integration
- `resilient_llm.py` - **Resilient LLM wrapper with cross-provider fallback** (Anthropic → OpenAI)
- `streaming_callback.py` - Streaming response handlers for agents

### Data Quality
- `grounding.py` - Entity grounding and linking to knowledge base

### Infrastructure
- `logger.py` - Centralized logging configuration
- `retry.py` - Exponential backoff, rate-limit helpers, skip-on-failure wrapper, and in-memory tool metrics

## Resilient LLM Wrapper (`resilient_llm.py`)

Provides automatic fallback from Anthropic (Claude) to OpenAI (GPT) when the primary provider fails, protecting against credit exhaustion or API outages.

### Classes & Functions

| Export | Purpose |
|--------|---------|
| `ResilientChatAnthropic` | LangChain-compatible wrapper with fallback support |
| `ResilientAsyncClient` | Raw async SDK wrapper for ingestion/services |
| `create_resilient_llm_with_openai_fallback()` | Factory for LangChain code |
| `get_resilient_async_client()` | Factory for async SDK code |
| `OpenAIResponseAdapter` | Makes OpenAI responses look like Anthropic |

### Model Mapping

| Anthropic Model | OpenAI Fallback |
|-----------------|-----------------|
| `claude-sonnet-4-5` | `gpt-4o` |
| `claude-opus-4-5` | `gpt-4o` |
| `claude-haiku-4-5` | `gpt-4o-mini` |
| `claude-3-5-haiku-20241022` (legacy) | `gpt-4o-mini` |

### Quick Start

**LangChain agents/workflows:**
```python
from app.utils.resilient_llm import create_resilient_llm_with_openai_fallback
from app.config.settings import settings

llm = create_resilient_llm_with_openai_fallback(
    primary_model="claude-sonnet-4-5",
    anthropic_api_key=settings.anthropic_api_key,
    openai_api_key=settings.openai_api_key,
    temperature=0.3,
)
result = llm.invoke(messages)
```

**Async SDK code (ingestion, services):**
```python
from app.utils.resilient_llm import get_resilient_async_client
from app.config.settings import settings

client = get_resilient_async_client(
    anthropic_api_key=settings.anthropic_api_key,
    openai_api_key=settings.openai_api_key,
)
response = await client.messages_create(
    model="claude-sonnet-4-5",
    max_tokens=4096,
    messages=[{"role": "user", "content": "Hello"}],
)
print(response.content[0].text)
```

## Usage Guidelines
- **Stateless functions only** - No class-based utilities (except LLM wrappers)
- **No external dependencies** - Utils should not import from `app.agents`, `app.api`, etc.
- **Well-tested** - Add unit tests for complex logic
