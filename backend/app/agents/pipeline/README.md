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
- 12 tools available
- Real-time results

**Full Mode** (1-5 minutes):
- Comprehensive list building with websets
- Requires user "CONFIRM" for expensive operations
- 13 tools available

### Tools Available

#### Exa.ai Search (Creates SearchBlocks - Semantic/Broad)
1. `find_similar_companies` - Lookalike targeting
2. `search_companies` - Natural language company search (BROAD/SEMANTIC)
3. `find_trigger_events` - Expansion/funding/contract signals
4. `build_company_webset` - Deep enrichment (Full mode only)

> **Note:** `find_contacts` (Exa) is deprecated for contact search. Use `find_company_contacts` (Apollo) instead for revealable email/phone data.

#### Apollo.io Tools (Creates SearchBlocks for contacts & filtered companies)
5. `search_companies_filtered` - **NEW** Structured firmographic search (FREE - no credits)
   - Use when user specifies: location (state/country), employee count, revenue, industries
   - Example: "aerospace companies in Florida with >500 employees"
   - Returns full firmographics (employees, revenue, industry, tech stack, location)
6. `enrich_company` - FREE firmographics (employees, revenue, tech stack)
7. `find_company_contacts` - PRIMARY contact search tool (FREE teasers + FREE company enrichment)
   - Returns contact previews with `person_id` for reveal
   - **Auto-includes company firmographics** (employee count, revenue, industry, location)
   - Frontend displays company context header above contacts
8. `reveal_contact` - COSTS 1 CREDIT (verified email/phone)
9. `get_apollo_credits` - Check usage

#### BigQuery Corpus (Chat insights only)
10. `query_corpus` - Semantic search across article_chunk_embeddings
11. `get_entity_mentions` - Company news from corpus
12. `get_competitor_activity` - Competitor intelligence

---

## Tool Selection Guide

| User Intent | Tool | Why |
|-------------|------|-----|
| Broad semantic search ("aerospace suppliers") | `search_companies` (Exa) | Neural search understands intent |
| Find lookalikes ("companies like Hexcel") | `find_similar_companies` (Exa) | Automated lookalike targeting |
| **Location filter** ("companies in Florida") | `search_companies_filtered` (Apollo) | Structured geo filter |
| **Employee count** ("companies with >500 employees") | `search_companies_filtered` (Apollo) | Structured size filter |
| **Revenue threshold** ("companies with >$100M revenue") | `search_companies_filtered` (Apollo) | Structured revenue filter |
| Contact search ("purchasing managers at Boeing") | `find_company_contacts` (Apollo) | Returns revealable contacts |

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

## Contact Search UX Flow

### User Request
"Find contacts at Hexcel in purchasing"

### Agent Processing
1. Uses `find_company_contacts` (Apollo) with department="purchasing"
2. Automatically fetches company enrichment (FREE)
3. Returns SearchBlock with `apollo_contacts` + `company_enrichment`

### Frontend Display
**Company Context Header:**
- Company logo, name, industry badge
- Description (1-line preview)
- Key metrics: employees, revenue, location
- LinkedIn link

**Contact Cards (below header):**
- Name, title, seniority badge
- "Email available" / "Phone available" badges
- "Reveal" button (costs 1 credit on click)
- LinkedIn link

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

### 3. Contact Discovery (Apollo - Recommended)
```
User: "Find purchasing managers at Hexcel"
Agent: Uses find_company_contacts(company_name="Hexcel", department="purchasing")
Result: 
- Company header with Hexcel firmographics
- Contact cards with has_email/has_phone flags
- Reveal button to get verified contact info
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
2. **Contacts**: "Find purchasing managers at Boeing" → Verify company header + contact cards
3. **Insights**: "What's in the news about composites?" → Verify chat response
4. **Apollo Enrich**: Click "Enrich with Apollo" → Verify enrichment displays
5. **Reveal**: Hover contact → Click "Reveal" → Verify email/phone displayed

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

### Issue: Contact search returns no results
- Check `APOLLO_API_KEY` is valid and has credits
- Try searching by domain instead of company name
- Verify the company exists in Apollo's database

### Issue: Company header not showing on contact results
- Ensure `company_enrichment` is present in SearchBlock
- Check that Apollo could enrich the company domain
- Frontend gracefully degrades if enrichment unavailable

### Issue: Corpus tools return no results
- Normal! Agent should say "No recent intel found"
- Verify BigQuery vector store is populated
- Check `article_chunk_embeddings` has recent data

---

## Recent Updates (Jan 2026)

### Session 62: Contact Card Enrichment
- `find_company_contacts` now auto-fetches FREE company firmographics
- Frontend displays company context header (logo, name, employees, revenue, industry)
- Contact cards appear below company header with reveal capability

### Session 61: Apollo Contact Search Fix
- Deprecated Exa.ai `find_contacts` tool (returns LinkedIn profiles without `person_id`)
- Made Apollo `find_company_contacts` the PRIMARY contact search tool
- Contacts now have `person_id` for email/phone reveal functionality

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
- **Apollo Service**: See `backend/app/services/apollo_service.py`
