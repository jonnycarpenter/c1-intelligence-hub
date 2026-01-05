# Pipeline Tab Documentation

## Overview

The Pipeline tab is an AI-powered sales prospecting engine that combines neural search (Exa.ai), firmographic enrichment (Apollo.io), and BigQuery intelligence corpus to help users discover qualified prospects, find decision makers, and identify buying signals.

## Architecture

### Frontend
- **Hook**: `frontend/src/hooks/usePipeline.ts` - State management for Pipeline interactions
- **Dashboard**: `frontend/src/components/pipeline/PipelineDashboard.tsx` - Main UI
- **Results Display**: `frontend/src/components/pipeline/SearchBlockCard.tsx` - Prospect/contact cards

### Backend
- **Agent**: `backend/app/agents/pipeline/agent.py` - Claude Sonnet 4.5 orchestrator
- **MCP Tools**: `backend/app/mcp/tools/pipeline_search.py` - Tool definitions
- **Services**:
  - `backend/app/services/exa_service.py` - Exa.ai integration
  - `backend/app/services/apollo_service.py` - Apollo.io integration
  - Logo.dev for company branding

### Data Sources
- **Exa.ai**: Neural search for companies, contacts, trigger events
- **Apollo.io**: Firmographic enrichment, contact discovery (free tier)
- **BigQuery corpus**: `article_chunk_embeddings` for news intelligence

---

## Agent Capabilities

### Two Modes

**Instant Mode** (~350ms):
- Quick discovery searches
- 11 tools available
- Real-time results

**Full Mode** (1-5 minutes):
- Comprehensive list building with websets
- Requires user "CONFIRM" for expensive operations
- 12 tools available

### Tools Available

#### Exa.ai Search (Creates SearchBlocks)
1. `find_similar_companies` - Lookalike targeting
2. `search_companies` - Natural language company search
3. `find_contacts` - Decision maker discovery
4. `find_trigger_events` - Expansion/funding/contract signals
5. `build_company_webset` - Deep enrichment (Full mode only)

#### Apollo.io Enrichment (Creates SearchBlocks for contacts)
6. `enrich_company` - FREE firmographics (employees, revenue, tech stack)
7. `find_company_contacts` - FREE contact discovery by department
8. `reveal_contact` - COSTS 1 CREDIT (verified email/phone)
9. `get_apollo_credits` - Check usage

#### BigQuery Corpus (Chat insights only)
10. `query_corpus` - Semantic search across article_chunk_embeddings
11. `get_entity_mentions` - Company news from corpus
12. `get_competitor_activity` - Competitor intelligence

---

## Critical UX Pattern: SearchBlocks vs Chat Insights

### Tools That Create SearchBlocks (Results Panel)

**When**: User wants to DISCOVER/FIND prospects
- "Find companies similar to X"
- "Search for aerospace suppliers"  
- "Who are purchasing managers at Boeing?"

**Tools**: Exa.ai search, Apollo contact search

**Result**: Prospect/contact cards appear in results panel

### Tools That Provide Chat Insights Only

**When**: User wants INTELLIGENCE about known topics
- "What's in the news about X?"
- "Any recent activity from competitors?"
- "Tell me about carbon fiber supply issues"

**Tools**: Corpus tools (query_corpus, get_entity_mentions, get_competitor_activity)

**Result**: Agent responds conversationally (NO SearchBlocks)

**Empty Results**: Agent can say "No recent intel found in last [timeframe]"

---

## Example Workflows

### 1. Basic Company Search
```
User: "Find aerospace composites manufacturers"
Agent: Uses search_companies() → SearchBlocks displayed
```

### 2. Lookalike Search with Enrichment
```
User: "Find companies similar to Hexcel"
Agent: 
1. find_similar_companies("hexcel.com")
2. Auto-enriches with Apollo firmographics
Result: SearchBlocks with employee count, revenue, industry
```

### 3. Contact Discovery
```
User: "Find purchasing managers at aerospace suppliers"
Agent: Uses find_contacts() → Contact SearchBlocks displayed
```

### 4. Intelligence Query (Chat Only)
```
User: "What's in the news about carbon fiber?"
Agent: Uses query_corpus() → Chat response with intel summaries
```

### 5. Combined Prospecting + Intelligence
```
User: "Find composites manufacturers and tell me which have been in the news"
Agent:
1. search_companies() → SearchBlocks
2. get_entity_mentions() for results → Chat: "3 companies have recent news: ..."
```

---

## API Keys Required

Configure in Secret Manager / environment:
- `EXA_API_KEY` - Exa.ai neural search
- `APOLLO_API_KEY` - Apollo.io enrichment/contacts
- `LOGO_DEV_TOKEN` - Company logo fetching

---

## Testing

### Local Testing
```bash
cd backend
python scripts/testing/test_pipeline_agent.py --query "Find companies similar to hexcel.com"
```

### Production Testing
Navigate to Pipeline tab and test:
1. **Search**: "Find aerospace suppliers" → Verify SearchBlocks
2. **Insights**: "What's in the news about composites?" → Verify chat response
3. **Apollo**: Click "Enrich with Apollo" → Verify enrichment displays
4. **Combined**: "Find suppliers + check news" → Verify both

---

## Troubleshooting

### Issue: Agent doesn't respond
- Check that `ANTHROPIC_API_KEY` is configured
- Verify MCP tools import correctly
- Check Cloud Run logs for errors

### Issue: No SearchBlocks appear
- Verify Exa.ai API key is valid
- Check that query uses search tools (not corpus tools)
- Review agent response for errors

### Issue: Apollo enrichment not displaying
- Check `APOLLO_API_KEY` is configured
- Verify Apollo credits available
- Check browser console for frontend errors

### Issue: Corpus tools return no results
- Normal! Agent should say "No recent intel found"
- Verify BigQuery vector store is populated
- Check `article_chunk_embeddings` has recent data

---

## Recent Updates (Jan 2026)

### BigQuery Corpus Integration
- Added 3 corpus tools to Pipeline agent
- Enables news intelligence alongside prospecting
- Corpus results stay in chat (don't create SearchBlocks)

### Apollo Button Fix
- Fixed `enrichProspect` export in usePipeline hook
- "Enrich with Apollo" button now functional

---

## Related Documentation

- **Sales Prospecting Pipeline KI**: Knowledge item with comprehensive architecture docs
- **Corpus Query Tools**: See `backend/app/mcp/tools/corpus_query.py`
- **Agent Implementation**: See `backend/app/agents/pipeline/agent.py`
