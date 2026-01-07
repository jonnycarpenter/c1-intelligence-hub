# Ad-Hoc Briefing Agent (Enhanced)

On-demand AI briefings using **Claude Sonnet 4.5** with multi-source intelligence search.

## Files

| File | Purpose |
|------|---------|
| `agent.py` | `AdHocBriefingAgent` + `StreamingAdHocBriefingAgent` |
| `session_manager.py` | Session state management for follow-up tracking |

## v2 Enhancements (January 2026)

| Feature | Before (v1) | After (v2) |
|---------|-------------|------------|
| Model | Claude Haiku | **Claude Sonnet 4.5** |
| Max tokens | 1500 | **3000** |
| Context | Truncated (500 chars) | Full content |
| Tools | Corpus only | **Corpus + Exa + StockNews + FMP** |
| Formatting | Plain text | **Sections, bold, URL citations** |
| Timeout | ~10 seconds | **120 seconds** |
| Streaming | Text only | **SSE progress events** |

## Data Sources

The agent searches in this order:
1. **Internal Corpus** (BigQuery vector store) - always searched first
2. **Exa.ai** - Neural news search with reliable dates
3. **StockNewsAPI** - Financial/stock-specific news
4. **FMP Premium** - Bloomberg, Benzinga, WSJ coverage

## SSE Progress Events

The streaming endpoint emits progress events for real-time feedback:

| Step | Label | Messages |
|------|-------|----------|
| `corpus_search` | Knowledge Base | "Searching..." → "Found N articles" |
| `exa_search` | Advanced Web Search | "Searching..." → "Found N articles" |
| `stocknews_search` | Stock Market News | "Found N articles" |
| `synthesis` | Analysis | "Synthesizing..." → "Response complete" |

**Event Format:**
```json
{
  "type": "progress",
  "step": "corpus_search",
  "label": "Knowledge Base",
  "message": "Found 8 relevant articles",
  "status": "complete",
  "count": 8
}
```

## Conversational UX (v2.1)

The ad-hoc briefing is now fully conversational with collapsible history:

- **Stacking Briefings**: Each new question adds a briefing to the stack (newest on top)
- **Collapsible History**: Older briefings collapse to header; click to expand
- **No Limits**: Users can ask unlimited questions in a session
- **Gentle Nudge**: After 2 questions, shows "For comprehensive analysis, try Deep Research"
- **Clear Option**: "Clear conversation" button at bottom to reset

### Frontend Components

**CollapsibleBriefing Component**:
- Index 0 (newest): Always shows full ResponseCard
- Index > 0 (older): Shows collapsed header with question + confidence badge
- Click header → expands to show full ResponseCard
- ChevronDown icon rotates to indicate state

**Frontend State** (`useAdHocBriefing` hook):
- `briefings[]`: Array of all briefings (newest first)
- `currentBriefing`: Most recent briefing (backward compat alias)
- `followUpCount`: Number of questions asked this session

## Response Format

Briefings include structured sections:
- **Overview**: Executive summary with bold key insights
- **Key Findings**: Bulleted insights with `[Source](url)` citations
- **Market Context**: Broader implications (when applicable)
- **Sources**: Numbered list with URLs

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/briefing/adhoc` | POST | Generate briefing |
| `/api/briefing/adhoc/stream` | POST | Streaming with progress events |
| `/api/briefing/adhoc/session/{id}` | GET/DELETE | Session management |

