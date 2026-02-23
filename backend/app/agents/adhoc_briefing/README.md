# Ad-Hoc Briefing Agent (Enhanced)

On-demand AI briefings using **Claude Sonnet 4.6** with multi-source intelligence search.

## Files

| File | Purpose |
|------|---------|
| `agent.py` | `AdHocBriefingAgent` + `StreamingAdHocBriefingAgent` |
| `session_manager.py` | Session state management for follow-up tracking |

## v2 Enhancements (January 2026)

| Feature | Before (v1) | After (v2) |
|---------|-------------|------------|
| Model | Claude Haiku | **Claude Sonnet 4.6** |
| Max tokens | 1500 | **3000** |
| Context | Truncated (500 chars) | Full content |
| Tools | Corpus only | **Corpus + Exa + StockNews + FMP** |
| Formatting | Plain text | **Sections, bold, URL citations** |
| Timeout | ~10 seconds | **120 seconds** |
| Streaming | Text only | **SSE progress events** |

## C1 Industry Context (Added Jan 30, 2026)

The agent's `SYSTEM_PROMPT` includes hardcoded context specific to Composites One (C1):

| Context Area | Contents |
|--------------|----------|
| **Company Identity** | "Composites One (C1), the largest composites distributor in North America" |
| **Competitors** | Hexcel, Toray, Solvay, Owens Corning, Huntsman, Gurit, Teijin, SGL Carbon, Mitsubishi Chemical |
| **Products** | Carbon fiber, fiberglass, resins (epoxy, polyester, vinyl ester), core materials, prepregs, ancillaries |
| **End Markets** | Aerospace, Automotive, Marine, Wind Energy, Infrastructure, Sporting Goods, Industrial |

This enables the agent to provide more relevant, strategic responses when users ask about competitors, products, or market developments.

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
- **Collapsible History**: ALL briefings are collapsible - click header to toggle
- **No Limits**: Users can ask unlimited questions in a session
- **Gentle Nudge**: After 2 questions, shows "For comprehensive analysis, try Deep Research"
- **Clear Option**: "Clear conversation" button at bottom to reset

### Frontend Components

**CollapsibleBriefing Component** (Updated Jan 30, 2026):
- **All briefings collapsible**: Every briefing can be collapsed, including the newest one
- When expanded: Shows ▲ button in header to collapse
- When collapsed: Shows compact question preview with confidence badge
- Click anywhere on collapsed bar to expand
- ChevronDown icon rotates to indicate state

**ResponseCard** (no longer used for first briefing - unified into CollapsibleBriefing)

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

