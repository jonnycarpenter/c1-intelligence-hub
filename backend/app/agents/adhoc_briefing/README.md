# Ad-Hoc Briefing Agent (Enhanced)

On-demand AI briefings using **Claude Sonnet 4.5** with multi-source intelligence search.

## Files

| File | Purpose |
|------|---------|
| `agent.py` | `AdHocBriefingAgent` - generates thorough briefings with external tools |
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

## Data Sources

The agent searches in this order:
1. **Internal Corpus** (BigQuery vector store) - always searched first
2. **Exa.ai** - Neural news search with reliable dates
3. **StockNewsAPI** - Financial/stock-specific news
4. **FMP Premium** - Bloomberg, Benzinga, WSJ coverage

## Session Management

- **TTL**: 30 minutes of inactivity
- **Max Sessions**: 1000 (LRU eviction)
- **Max Follow-ups**: 2 (then redirects to Deep Research)

## Response Format

Briefings now include structured sections:
- **Overview**: Executive summary with bold key insights
- **Key Findings**: Bulleted insights with `[Source](url)` citations
- **Market Context**: Broader implications (when applicable)
- **Sources**: Numbered list with URLs

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/briefing/adhoc` | POST | Generate briefing |
| `/api/briefing/adhoc/stream` | POST | Streaming variant |
| `/api/briefing/adhoc/session/{id}` | GET/DELETE | Session management |

## Model

Uses `claude-sonnet-4-5` with 120-second timeout for thorough responses.

After 2 follow-ups, redirects to Deep Research for comprehensive analysis.
