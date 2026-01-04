# Shared Utilities

Reusable utility modules used across ingestion, agents, and API layers.

## Modules

### Text Processing
- `chunking.py` - Semantic text chunking for embeddings (used by ingestion)
- `date_extraction.py` - Extract publication dates from article text
- `date_utils.py` - Date parsing and normalization helpers

### LLM Integration
- `resilient_llm.py` - Retry logic and error handling for LLM calls
- `streaming_callback.py` - Streaming response handlers for agents

### Data Quality
- `grounding.py` - Entity grounding and linking to knowledge base

### Infrastructure
- `logger.py` - Centralized logging configuration

## Usage Guidelines
- **Stateless functions only** - No class-based utilities
- **No external dependencies** - Utils should not import from `app.agents`, `app.api`, etc.
- **Well-tested** - Add unit tests for complex logic
