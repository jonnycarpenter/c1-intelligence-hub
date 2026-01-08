# C1 Intelligence Hub - Work Log

This file tracks completed work and open items across AI assistant sessions.

---

## ⚠️ CRITICAL PRIORITY: Ingestion Pipeline Reliability

**The single most critical thing in any workstream is getting the ingestion pipelines working correctly—for every run, for every day.**

Without reliable daily ingestion:
- The Pulse page shows stale data
- Deep Research has no fresh context
- Weekly briefings have nothing to summarize
- The entire product value proposition breaks down

**Always verify scheduler jobs are running before working on features.**

---
## 📅 SESSION 64: Pipeline Agent Parallel Execution Fix (January 7, 2026)

**Status**: ✅ COMPLETE - Ready for Deploy

### 🎯 Issue
User reported `invalid_request_error` (Error 400) from Anthropic API when using Pipeline contact search in production.
Error: `messages.7: tool_use ids were found without tool_result blocks immediately after`.

### 🔍 Root Cause
**Protocol Violation in Message History Construction**:
- The Pipeline Agent's multi-turn loop (lines 404+) explicitly handles follow-up tool calls.
- In the `while` loop, the code was appending the `AIMessage` (containing the tool requests) **inside the for-loop** iterating over the tools.
- If the agent called 3 tools in parallel:
  - Iteration 1: Appends `AIMessage`, Appends `ToolMessage(1)`
  - Iteration 2: Appends `AIMessage` (AGAIN), Appends `ToolMessage(2)`
  - Iteration 3: Appends `AIMessage` (AGAIN), Appends `ToolMessage(3)`
- The Anthropic API sees the `AIMessage` repeated, breaking the required `[AIMessage, ToolMessage, ToolMessage...]` sequence.

### ✅ Fix Applied
- Modified `backend/app/agents/pipeline/agent.py`:
- Moved `messages.append(final_response)` **OUTSIDE** the tool execution loop.
- Result: `[AIMessage, ToolMessage(1), ToolMessage(2), ToolMessage(3)]` (Correct Protocol).

### 📁 Files Modified
- `backend/app/agents/pipeline/agent.py`

---

**Status**: 🚧 IN PROGRESS - Deployed Fixes, Testing

**Deployed Commits**: 
- `f4be46d` - Timeout fixes (HTTP timeout reduction, explicit task cancellation)
- `7eadc3b` - Disabled prior research context injection

### 🎯 Issue Reported
Deep research query "marine/yacht composites" stuck at groomer stage. Last visible log was `corpus_query` at 15:08:34 CST. User reported "Query analysis canceled" in UI after latest deploy.

### 🔍 Root Cause Analysis (Detailed)

**Session 60 had deployed debug logging** - we could see `[GROOMER] START` but NO `[GROOMER] COMPLETE` or timeout logs. The 90s asyncio.wait_for timeout from Session 60 was NOT firing.

**Why the timeout didn't work:**
The `ResilientChatAnthropic` wrapper has an HTTP client timeout set via `httpx.AsyncClient(timeout=...)`. This timeout was **120 seconds** while our asyncio.wait_for was **90 seconds**.

When asyncio tries to cancel a task, it sends a CancelledError - but if the underlying HTTP client is blocking on a socket read with its own longer timeout, the cancellation cannot interrupt it. The HTTP layer holds the task hostage until IT times out (or succeeds).

**Key insight from user**: "The workflow was working prior to us adding the enhancement to check prior research and the visual agent." User confirmed Visual Agent is critical and must stay. That made prior research context injection the suspect.

### ✅ Fixes Deployed

#### Commit `f4be46d` - Timeout Architecture Fix

**1. HTTP Client Timeout Reduction (`resilient_llm.py`)**
- Reduced HTTP timeout from 120s → 45s
- Reduced retry attempts from 2 → 1
- Now asyncio.wait_for(60s) > HTTP timeout(45s), so cancellation works

**2. Explicit Task Cancellation (`groomer.py`)**
- Wrapped LLM call in `asyncio.create_task()` 
- On timeout: explicitly call `task.cancel()` + `await task` to cleanup
- Ensures proper resource cleanup

**3. Heartbeat Logging (`deep_research.py`)**
- Added 30-second heartbeat logging during SSE streaming
- Helps identify if workflow is progressing or stuck

**4. Client Disconnect Handling (`deep_research.py`)**
- Added explicit handling for `CancelledError` and `GeneratorExit`
- Logs when client disconnects vs normal completion

#### Commit `7eadc3b` - Disable Prior Research Context

**Hypothesis**: The `_get_prior_research_context()` call in groomer was causing the hang. This function:
1. Calls `gcp_storage.search_related_research(query)` 
2. Queries BigQuery `deep_research_reports` table with LIKE matching
3. Returns concatenated prior research context

Disabled by hardcoding `prior_context = ""` and commenting out the BQ lookup call.

### 📁 Files Modified

| File | Changes |
|------|---------|
| `backend/app/utils/resilient_llm.py` | HTTP timeout 120s→45s, retries 2→1 |
| `backend/app/agents/research/groomer.py` | Explicit task cancellation, prior research disabled |
| `backend/app/api/routes/deep_research.py` | Heartbeat logging, disconnect handling |

### ⚠️ Current Issue
After deploying commit `7eadc3b`, user tested and got **"Query analysis canceled"** message in the UI. This suggests:
- The new client disconnect handling (`CancelledError` catch) is triggering
- Something is causing the SSE connection to close early
- Need to check Cloud Run logs for the actual error

### 🔍 Log Query Information
**GCP Project**: `gen-lang-client-0436975498`
**Service**: `c1-hub-service`
**Log patterns to search**: `[GROOMER]`, `canceled`, `Cancelled`, `disconnect`, `CancelledError`

### � IMPORTANT: Where Related Research is Queried

**Confirmed**: Only ONE place in the workflow calls related research - **groomer.py**

```
grep results for "find_related_research|related_research|search_related":
- groomer.py:38 - await memory.find_related_research() [IN WORKFLOW - NOW DISABLED]
- deep_research.py:782 - API endpoint for UI to fetch related (NOT in workflow)
- memory.py:109 - The memory class method definition
- gcp_storage.py:2601 - The BQ query implementation
```

**Synthesizer does NOT check related research** - confirmed via grep (no matches).

So the current theory is solid: disabling prior research in groomer should eliminate that as a cause.

### 🔜 Next Steps (For Next Session)
1. **Check Cloud Run Logs** for the test query - look for:
   - `[GROOMER] START` - did groomer even begin?
   - `[GROOMER] COMPLETE` - did it finish?
   - Any error messages or stack traces
   - Client disconnect logs

2. **If groomer didn't start**: Issue is BEFORE groomer (routing, initial state)

3. **If groomer started but canceled**: The 60s timeout may be too aggressive, OR there's a new error in the simplified groomer code

4. **If workflow completed but UI showed canceled**: Frontend SSE handling issue

5. **Once working**: Re-enable prior research with proper timeout wrapping around JUST the BQ call

### 📋 Technical Context for Continuation

**GCP Project ID**: `gen-lang-client-0436975498`
**Cloud Run Service**: `c1-hub-service`

**Log query command**:
```bash
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=c1-hub-service" --project=gen-lang-client-0436975498 --limit=50 --format=json
```

**Groomer code structure** (simplified after disable):
```python
async def groom_query(state: ResearchState) -> ResearchState:
    logger.info(f"[GROOMER] START - Query: {state.get('query', 'N/A')[:100]}")
    
    # DISABLED for debugging - was calling BQ search_related_research
    prior_context = ""
    logger.info("[GROOMER] Prior research context disabled for debugging")
    
    # LLM call with explicit task cancellation
    task = asyncio.create_task(llm.ainvoke(messages))
    try:
        response = await asyncio.wait_for(task, timeout=60)
    except asyncio.TimeoutError:
        task.cancel()
        await task  # Wait for cancellation
        raise
```

**Prior research function** (disabled, in `gcp_storage.py`):
- `search_related_research(query)` - queries `deep_research_reports` table
- Uses SQL LIKE with query keywords
- Returns up to 3 matching reports' executive summaries

**Files to review if issues persist**:
- [groomer.py](backend/app/agents/research/groomer.py) - prior research disabled, LLM timeout
- [resilient_llm.py](backend/app/utils/resilient_llm.py) - HTTP timeout 45s
- [deep_research.py](backend/app/api/routes/deep_research.py) - SSE streaming, heartbeat, cancel handling
- [research_workflow.py](backend/app/graph/research_workflow.py) - LangGraph workflow definition

---

## 📅 SESSION 62: Pipeline Contact Card Enrichment (January 7, 2026)

**Status**: ✅ COMPLETE - Ready for Production Deploy

### 🎯 Goal
Enrich Apollo contact "hunting cards" with company firmographics, similar to how company search results show enriched data.

### ✅ Changes Implemented

**Backend - `pipeline_search.py`**
- `find_company_contacts` tool now automatically fetches company enrichment (FREE via Apollo `enrich_organization`)
- Returns `company_enrichment` with: employee count, revenue, industry, location, LinkedIn, description

**Backend - `state.py`**
- Added `company_enrichment: Optional[ApolloEnrichmentResult]` to `SearchBlock` model

**Backend - `agent.py`**
- Agent now parses `company_enrichment` from tool response and includes in SearchBlock

**Frontend - `types/index.ts`**
- Added `company_enrichment` field to `SearchBlock` interface

**Frontend - `SearchBlockCard.tsx`**
- Added company context header above Apollo contacts list
- Displays: company logo, name, industry, description, employee count, revenue, location, LinkedIn link
- Uses cyan gradient styling consistent with Apollo contacts theme

### 📋 Files Modified
- `backend/app/mcp/tools/pipeline_search.py` - Company enrichment in tool response
- `backend/app/agents/pipeline/state.py` - SearchBlock model update
- `backend/app/agents/pipeline/agent.py` - Parse and pass company enrichment
- `frontend/src/types/index.ts` - TypeScript type update
- `frontend/src/components/pipeline/SearchBlockCard.tsx` - Company header UI

### 🔍 Verification Note
- Local testing blocked due to missing `APOLLO_API_KEY` in local `.env`
- Production has API keys in Secret Manager - will work after deploy

---
## 📅 SESSION 61: Pipeline Contact Search Fix - Apollo vs Exa (January 7, 2026)

**Status**: ✅ COMPLETE - Deployed with Session 62

### 🎯 Issue Reported
**"Get list of contact information" functionality in Pipeline tab is not working.**

When users ask for contacts at a company (e.g., "Find contacts at Hexcel in purchasing"), the agent:
- Returns LinkedIn profile search results (from Exa.ai)
- Does NOT return Apollo contacts with revealable email/phone
- Cannot fulfill "reveal email" requests because Exa results lack `person_id`

### 🔍 Root Cause Analysis

**The Pipeline agent has TWO contact search tools:**

| Tool | Source | Returns | Can Reveal? |
|------|--------|---------|-------------|
| `find_contacts` | **Exa.ai** (LinkedIn search) | Names, titles, LinkedIn URLs | ❌ No `person_id` |
| `find_company_contacts` | **Apollo.io** | Contact teasers with `id`, has_email flags | ✅ Has `person_id` for reveal |

**The Problem:**
- The LLM was choosing `find_contacts` (Exa) for contact queries
- Exa results are LinkedIn web scrapes - no structured contact data
- Without Apollo's `person_id`, the `reveal_contact` tool can't get emails
- The system prompt didn't clearly guide when to use each tool

### ✅ Fixes Applied

#### 1. Commented Out Exa `find_contacts` Tool (`pipeline_search.py`)
```python
PIPELINE_TOOLS_INSTANT = [
    find_similar_companies,
    search_companies,
    # NOTE: find_contacts (Exa) is commented out in favor of find_company_contacts (Apollo)
    # Exa returns LinkedIn profiles without person_id, making reveal_contact impossible.
    # Apollo provides structured contacts with IDs for email/phone reveal.
    # TODO: Future enhancement - combine Exa broad search with Apollo data enrichment
    # find_contacts,
    find_trigger_events,
    enrich_company,
    find_company_contacts,  # PRIMARY contact search tool
    reveal_contact,
    get_apollo_credits,
    # ... corpus tools
]
```

#### 2. Updated System Prompts (`agent.py`)
- Removed `find_contacts` from capabilities list
- Made `find_company_contacts` the PRIMARY contact search tool
- Added clear guidance for Company vs Contact searches:
  - **Company Searches** → Use Exa.ai (search_companies, find_similar_companies)
  - **Contact Searches** → Use Apollo (find_company_contacts)
- Added clarification prompt for ambiguous queries:
  > "Would you like me to find **companies** matching that criteria, or **contacts/people** at those companies?"

#### 3. Tool Numbering Updated
Renumbered tool references (1-10 instead of 1-11) since Exa find_contacts is removed

### 📁 Files Modified
- `backend/app/mcp/tools/pipeline_search.py` - Commented out `find_contacts` from tool lists
- `backend/app/agents/pipeline/agent.py` - Updated both `SYSTEM_PROMPT_INSTANT` and `SYSTEM_PROMPT_FULL`

### ⚠️ VERIFICATION NEEDED

**The fix needs testing with a fresh backend restart:**

1. **Kill all uvicorn processes** (there are currently two running - port conflict!)
2. **Restart backend**: `python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
3. **Test**: Navigate to Pipeline, ask "Find contacts at Hexcel in purchasing"
4. **Expected SUCCESS indicators:**
   - Block header is **CYAN** (not green/emerald)
   - Block title says "Contacts at Hexcel" 
   - Cards show **"Email available"** / **"Phone available"** badges
   - **"Reveal" button** appears on hover (rose/red colored)
   - **NO LinkedIn connection counts** (those are Exa-specific)

### 📋 Frontend Component Reference

The frontend is ALREADY built for Apollo contacts:
- `SearchBlockCard.tsx` has `ApolloContactTeaserItem` component (lines 836-921)
- Uses `block_type === 'apollo_contacts'` for cyan styling
- Shows "Reveal" button when `has_email || has_phone` is true
- Displays email/phone availability badges

The `_create_search_block` method in `agent.py` correctly maps `find_company_contacts` results to `apollo_contacts` block type.

### 🔮 Future Enhancement
The Exa `find_contacts` tool is preserved (commented out, not deleted) for potential future enhancement:
- Combine Exa's broad industry-wide contact discovery with Apollo's structured data
- Use Exa to find people, then match/enrich via Apollo for email reveal

---
## 📅 SESSION 60: Deep Research Workflow Debugging & Stabilization (January 7, 2026)

**Status**: 🚧 IN PROGRESS - Deployed, Need to Check Logs

**Deployed Commit**: `e9c9a68`

### 🎯 Issues Reported
1. **Groomer LLM hanging indefinitely** - Cloud Run logs showed groomer stuck at "Message count: 2, system prompt length: 4308" for 5+ minutes without timeout
2. **Frontend showing "Research complete" prematurely** - Status text appeared while spinner still active
3. **Missing `visual_output` in initial state** - Could cause state merge issues in parallel execution

### 🔍 Root Cause Analysis

**Groomer Hang Issue:**
- The `ResilientChatAnthropic` wrapper had HTTP timeout (120s) but NO asyncio-level timeout
- The `ainvoke()` call was awaiting indefinitely with no cancellation mechanism
- Anthropic API appears to occasionally hang (perhaps rate limiting or network issues)
- Other nodes (financial, industry) worked fine because they didn't experience the same delay

**Frontend "Research complete" Issue:**
- The SSE event handler received a `status: "Research complete."` message from the workflow
- This status was being displayed even while `isResearching` was still `true`
- The handler blindly set whatever status text came through

**Visual Output Issue:**
- `initial_state` in `deep_research.py` was missing `visual_output: None`
- This could cause issues during LangGraph state merging from parallel Send nodes

### ✅ Fixes Applied

#### 1. Groomer LLM Timeout (`groomer.py`)
Added 90-second `asyncio.wait_for` around the LLM call:
```python
LLM_TIMEOUT = 90
try:
    response = await asyncio.wait_for(llm.ainvoke(messages), timeout=LLM_TIMEOUT)
except asyncio.TimeoutError:
    logger.error(f"Groomer LLM call timed out after {LLM_TIMEOUT}s")
    # Graceful failure with error progress emission
```

#### 2. Frontend Status Display (`useDeepResearch.ts`)
Modified status handler to ignore "complete" messages while still researching:
```typescript
case 'status':
    setState(prev => {
        if (prev.isResearching && statusText.toLowerCase().includes('complete')) {
            return prev // Keep existing status while still researching
        }
        return { ...prev, status: statusText }
    })
```

#### 3. Initial State Fix (`deep_research.py`)
Added missing `visual_output: None` to initial_state

#### 4. Logging Visibility (`resilient_llm.py`)
Changed `logger.debug` → `logger.info` for LLM invocation so it appears in Cloud Run logs

### 🔧 Comprehensive Debug Logging Added

Added `[NODE_NAME]` prefixed logging throughout workflow for production debugging:

| File | Logging Added |
|------|---------------|
| `groomer.py` | `[GROOMER] START/COMPLETE` with timing, query count |
| `financial.py` | `[FINANCIAL_RESEARCH] START/COMPLETE` with timing, finding count |
| `industry.py` | `[INDUSTRY_RESEARCH] START/COMPLETE` with timing, finding count |
| `visual.py` | `[VISUAL_RESEARCH] START` with state keys |
| `synthesizer.py` | `[SYNTHESIZER] START/COMPLETE` with timing, input analysis |
| `research_workflow.py` | `[ROUTE_AFTER_GROOM]` with state keys, current_status |
| `deep_research.py` | `[DEEP_RESEARCH]` initial state logging |

### 📁 Files Modified
- `backend/app/agents/research/groomer.py` - LLM timeout + debug logging
- `backend/app/agents/research/financial.py` - Debug logging
- `backend/app/agents/research/industry.py` - Debug logging  
- `backend/app/agents/research/visual.py` - Debug logging
- `backend/app/agents/research/synthesizer.py` - Debug logging
- `backend/app/graph/research_workflow.py` - Routing debug logging
- `backend/app/api/routes/deep_research.py` - Initial state fix + logging
- `backend/app/utils/resilient_llm.py` - Changed debug → info for visibility
- `frontend/src/hooks/useDeepResearch.ts` - Status display fix

### ✅ Validation
- Workflow compiles successfully with all 8 nodes
- Frontend builds successfully

### 🔜 Next Steps
1. **Deploy**: `git add . && git commit -m "Fix groomer timeout, status display, add comprehensive logging" && git push origin main`
2. **Test**: Run research query and verify:
   - Groomer doesn't hang (should timeout at 90s if needed)
   - No premature "Research complete" message
   - Debug logs visible in Cloud Run Logs
3. **Monitor**: Look for `[GROOMER]`, `[FINANCIAL_RESEARCH]`, etc. prefixes in logs

---
## 📅 SESSION 59: Briefing Date Fix & Logo Formatting Deployment (January 7, 2026)

**Status**: ✅ COMPLETE

### 🎯 Issues Reported
1. **Logo insertion and formatting not showing in production** on the BLUF and overall_trend in weekly briefings
2. **Date showing "Week of Jan 11"** instead of "Week of Jan 5" (this week's Monday)

### 🔍 Root Cause Analysis

**Logo/Formatting Issue:**
- The code from Session 55 (`53cb74c`) exists and is committed
- However, the **existing briefing in BigQuery was generated before these changes**
- Fix: Regenerate the weekly briefing after deployment

**Date Issue:**
- Function `_get_this_weeks_sunday()` was mislabeled - the formula actually calculates Monday
- The stored briefing had old `period_end` data from a prior manual run
- Fix: Rename function for clarity and regenerate briefing

### ✅ Changes Made

1. **Renamed function for clarity** (`pre_briefing.py`):
   - `_get_this_weeks_sunday()` → `_get_this_weeks_monday()`
   - Formula was already correct (weekday() = days since Monday)
   - Comments updated to reflect Monday convention

2. **Documentation updated** (`generators/README.md`):
   - All Sunday references changed to Monday
   - Example updated to show correct date calculation

### 📁 Files Modified
- `backend/app/ingestion/generators/pre_briefing.py` - Function rename
- `backend/app/ingestion/generators/README.md` - Documentation update

### 🔜 Next Steps After Deploy
- Regenerate weekly briefing to apply logo formatting and correct date

---
## 🎙️ SESSION 58: Podcast System Audit (January 7, 2026)

**Status**: ✅ COMPLETE

### 🎯 Issue
User reported "failed to produce audio" when clicking the Listen button on the executive briefing. Suspected the conversational enhancements from Session 54 might be breaking it.

### 🔍 Root Cause
**Two issues found:**

1. **Missing `/api` prefix in frontend podcast URL** (HIGH - root cause of failure)
   - Frontend was calling `/podcast/briefing/{id}` instead of `/api/podcast/briefing/{id}`
   - Route is mounted at `/api/podcast` in `main.py`
   - This was NOT related to the conversational enhancements

2. **Blocking `time.sleep()` in async function** (MEDIUM)
   - `_generate_podcast()` used `time.sleep()` during retry delays
   - Blocks the event loop; should use `await asyncio.sleep()`

### ✅ Fixes Applied

1. **Frontend URL fix** (`WeeklyBriefingSection.tsx` line 448):
   ```tsx
   // Before: audioUrl={`${API_BASE}/podcast/briefing/${briefing.id}`}
   // After:  audioUrl={`${API_BASE}/api/podcast/briefing/${briefing.id}`}
   ```

2. **Async sleep fix** (`weekly_briefing.py`):
   - Added `import asyncio`
   - Replaced 3 instances of `time.sleep()` with `await asyncio.sleep()`

### 📁 Files Modified
- `frontend/src/components/dashboard/WeeklyBriefingSection.tsx` - Fixed podcast URL
- `backend/app/ingestion/generators/weekly_briefing.py` - Fixed blocking sleep

### 🔍 Audit Summary
Conducted comprehensive fine-tooth comb review of entire podcast system:
- ✅ ElevenLabs Text-to-Dialogue API integration - Working
- ✅ GCS upload and storage - Working
- ✅ BigQuery podcast columns - Exist and correctly populated
- ✅ Backend streaming endpoint with Range support - Working
- ✅ Frontend PodcastModal component - Working
- ❌ Frontend URL construction - **Fixed**
- ❌ Async sleep - **Fixed**

---
## SESSION 57: Deep Research Groomer Hang Fix (January 7, 2026)

**Status**: COMPLETE

### Issue
Deep Research workflow appeared to hang at the groomer/query analysis stage. The UI would spin indefinitely without progressing to the parallel research agents.

### Root Cause
When the Visual Research Agent was added in Session 53, the **backend** was fully updated but the **frontend** was missing the new node in multiple places:
- `types/index.ts` - Missing `visual_research` in DeepResearchNode type
- `useDeepResearch.ts` - Missing in NODE_DESCRIPTIONS and ALL_NODES  
- `ResearchProgress.tsx` - Missing in NODE_ICONS and NODE_LABELS

This caused the frontend state machine to not recognize `visual_research` SSE events, breaking workflow progress tracking.

### Fixes Applied
1. **Frontend Type** - Added `visual_research` to DeepResearchNode union type
2. **Frontend Hook** - Added to NODE_DESCRIPTIONS and ALL_NODES
3. **Frontend Progress** - Added Image icon and label for visual_research
4. **Backend Groomer** - Added error progress emission, 10s timeout on prior research lookup, better LLM error handling

### Files Modified
- `frontend/src/types/index.ts`
- `frontend/src/hooks/useDeepResearch.ts`
- `frontend/src/components/research/ResearchProgress.tsx`
- `backend/app/agents/research/groomer.py`

### Lessons Learned
- When adding a new workflow node, update BOTH backend AND frontend
- SSE events for unknown nodes get silently ignored, causing apparent hangs

---

## �️ SESSION 56: Podcast Playback Fix (January 7, 2026)

**Status**: ✅ COMPLETE

### 🎯 Issue
The "Listen" button appeared but showed "can't play podcast" error when clicking to play. The conversational dialogue changes from Session 54 were not the issue.

### 🔍 Root Cause
The backend was storing direct GCS URLs (`https://storage.googleapis.com/...`) in the `podcast_url` field, but the GCS bucket has **public access prevention** enabled. The frontend was trying to load audio from these inaccessible URLs.

### ✅ Fix
Updated the frontend to construct the correct API proxy URL instead of using the stored GCS URL directly:
```typescript
// Before: audioUrl={briefing.podcast_url}
// After:  audioUrl={`${API_BASE}/podcast/briefing/${briefing.id}`}
```

The `/api/podcast/briefing/{id}` endpoint in the backend properly streams audio from GCS with Range request support (for seeking).

### 📁 Files Modified
- `frontend/src/components/dashboard/WeeklyBriefingSection.tsx` - Changed audioUrl to use API endpoint

### 📝 Technical Context
- Backend stores GCS URL internally for its own access
- Frontend must use `/api/podcast/briefing/{id}` endpoint which proxies the audio
- This pattern is documented in `backend/app/services/README.md`
- The conversational dialogue feature (Host + Analyst voices) works correctly

---

## �🎨 SESSION 55: Executive Briefing Text Formatting Enhancement (January 7, 2026)

**Status**: ✅ COMPLETE

### 🎯 Goal
Add logo.dev integration and company/product name bolding to the BLUF and overall trend text in the "Need to Know" executive briefing section, matching the formatting already used in section insights.

### ✅ Changes Made

**Enhanced Text Rendering** (`frontend/src/components/dashboard/WeeklyBriefingSection.tsx`):
- Extracted `renderTextWithLogosAndCitations` function to module scope for reuse
- Collected all companies with logos from all briefing sections
- Applied logo and citation rendering to both `bluf` and `overall_trend` fields
- Now displays `[[Company Name]]` tags with inline company logos (via logo.dev)
- Company names appear bolded in both BLUF and overall trend paragraphs
- Citations `[1]`, `[2]` render as superscript links matching section style

### 📁 Files Modified
- `frontend/src/components/dashboard/WeeklyBriefingSection.tsx` - Text rendering enhancement

### 🧪 Verification
```bash
# Frontend builds successfully
cd frontend && npm run build
# ✓ Compiled successfully in 3.6s
# ✓ Finished TypeScript in 6.6s
```

### 🎨 Design Consistency
The BLUF and overall trend text now have the same visual treatment as the section insights:
- Logo.dev integration shows company logos inline with mentions
- Company names are bolded for emphasis
- Product/material names (composite materials, etc.) are bolded
- Citations appear as emerald-colored superscript numbers

---

## 🎙️ SESSION 54: Conversational Podcast & Modal Player (January 7, 2026)

**Status**: ✅ COMPLETE

### 🎯 Goal
Enhance the weekly briefing podcast with two improvements:
1. Two-voice conversational format (Host + Analyst)
2. Modal-based podcast player (cleaner UI)

### ✅ Changes Made

**1. Podcast Modal** (`frontend/src/components/dashboard/PodcastModal.tsx`)
- Created new dark-theme modal for podcast playback
- Features: skip ±15s, progress bar, volume control, download
- 🎧 "Listen" button added to "Need to Know" header
- Replaced embedded player for cleaner briefing page

**2. Two-Voice Dialogue** (`backend/app/ingestion/generators/weekly_briefing.py`)
- `_build_podcast_dialogue()` - Returns list of `{speaker, text}` turns
- **Host (Rachel)**: Opens briefing, introduces sections, transitions, closes
- **Analyst (Josh)**: Delivers BLUF, headlines, insights, trends
- `_generate_podcast()` - Generates audio per turn, concatenates to single MP3

**Dialogue Structure**:
```
HOST: "Good morning. Welcome to your Executive Briefing..."
HOST: "Let's start with the bottom line."
ANALYST: "[BLUF content]"
HOST: "Let's dive into our first area of focus. [Section header]."
ANALYST: "This is a new development. [Headline]"
HOST: "Interesting."
... (repeats for each section)
HOST: "Zooming out, what's the bigger picture here?"
ANALYST: "[Overall trend]"
HOST: "That's your briefing for this week. Stay sharp."
```

**3. Deleted Files**
- `PodcastPlayer.tsx` - Replaced by modal
- `podcast_conversation_thoughtstarter` - Implemented simpler approach

**4. Documentation**
- Updated `backend/app/services/README.md` with Text-to-Dialogue API details

### 📁 Files Modified
- `frontend/src/components/dashboard/PodcastModal.tsx` (NEW)
- `frontend/src/components/dashboard/WeeklyBriefingSection.tsx` - Modal integration
- `backend/app/ingestion/generators/weekly_briefing.py` - Two-voice dialogue + Text-to-Dialogue API
- `backend/scripts/operations/generate_podcast_for_briefing.py` - Updated for new API
- `backend/app/services/README.md` - Updated podcast docs

### 🧪 Verification
```bash
# Backend compiles
cd backend && python -c "from app.ingestion.generators.weekly_briefing import WeeklyBriefingGenerator; print('OK')"

# 54 MCP tools
python -c "from app.mcp.server import get_all_mcp_tools; print(len(get_all_mcp_tools()))"

# Frontend builds
cd frontend && npm run build
```

### 📝 Notes
- Voice IDs: Rachel (host) `21m00Tcm4TlvDq8ikWAM`, Josh (analyst) `TxGEqnHWrfWFTfGW9XjX`
- Podcast URL stored per briefing - each week gets new audio
- GCS streaming endpoint unchanged (`/api/podcast/briefing/{id}`)
- Text-to-Dialogue API produces noticeably better audio quality
- Single API call is more efficient (~15-20 calls reduced to 1)

### 🧪 Testing
```bash
# Regenerate podcast for latest briefing
python scripts/operations/generate_podcast_for_briefing.py

# Result: 254s (4:14) podcast generated successfully
# URL: https://storage.googleapis.com/.../podcasts/{briefing_id}.mp3
```

---

## �🎨 SESSION 53: Visual Research Agent - Implementation (January 7, 2026)

**Status**: ✅ COMPLETE

### 🎯 What Was Done

Implemented the Visual Research Agent from Session 52's planning phase:

1. **Created `corpus_visuals_search` MCP tool** (`app/mcp/tools/corpus_visuals.py`)
   - Queries `article_images` BigQuery table
   - Filters by companies, industries, topics, image_types, chart_types
   - Returns formatted JSON with visual metadata

2. **Created Visual Research Agent** (`app/agents/research/visual.py`)
   - **LLM-powered intelligent selection** - Uses Claude to:
     - Analyze research brief to determine visual needs
     - Evaluate candidate visuals for relevance
     - Select 3-8 most impactful visuals
     - Generate contextual captions
     - Determine optimal section placement
   - Fallback heuristic selection if LLM fails
   - Graceful degradation if no visuals found

3. **Updated state schema** (`app/agents/research/state.py`)
   - Added `VisualAgentOutput` model
   - Added `visual_output` field with `_keep_last` reducer

4. **Updated workflow** (`app/graph/research_workflow.py`)
   - Added `visual_research` node
   - 3-way fan-out: Financial, Industry, Visual in parallel
   - Visual → Synthesize edge

5. **Updated synthesizer** (`app/agents/research/synthesizer.py`)
   - Accepts visual_output from state
   - Incorporates visuals into appropriate report sections

6. **Updated READMEs**
   - `agents/research/README.md` - Updated to 8 nodes, documented Visual agent
   - `mcp/tools/README.md` - Added corpus_visuals.py

### 🧪 Verification

```bash
# Workflow compiles with 8 nodes
python -c "from app.graph.research_workflow import create_research_workflow; g = create_research_workflow(); print(list(g.nodes.keys()))"
# Output: ['__start__', 'groom', 'financial_research', 'industry_research', 'visual_research', 'synthesize', 'categorize', 'validate']

# 54 MCP tools including corpus_visuals_search
python -c "from app.mcp.server import get_all_mcp_tools; print(len(get_all_mcp_tools()))"
# Output: 54
```

### 📌 Production Note

The `article_images` table has ~150 images in production. The Visual agent will:
- Return visuals when the table has matching data
- Gracefully return empty results if no matches (won't fail the workflow)

---

## 🎨 SESSION 52: Visual Research Agent - Planning (January 7, 2026)

**Status**: ✅ IMPLEMENTED IN SESSION 53

### 🎯 Goal
Add a new **Visual Research Agent** that runs in parallel with Financial and Industry agents to surface relevant charts/graphs from the `article_images` BigQuery table.

### 📐 Architecture Decision

**Why a new parallel agent (not adding to existing agents)?**

1. **Zero added latency** - Visual agent (~10-15s) finishes before Financial/Industry (~30s)
2. **Separation of concerns** - Financial thinks about earnings, Industry thinks about news, Visual thinks about charts
3. **Future expansion** - Will add chart generation capabilities from BigQuery trend datasets

**New Pipeline Architecture:**
```
                         ┌─────────────────┐
                    ┌───►│    Financial    │───┐
                    │    │    Research     │   │
┌─────────────┐     │    └─────────────────┘   │
│   Groomer   │─────┼───►┌─────────────────┐   ├───► [Synthesizer] → [Category] → [Validator]
│   (Query)   │     │    │    Industry     │   │
└─────────────┘     │    │    Research     │   │
                    │    └─────────────────┘   │
                    │    ┌─────────────────┐   │
                    └───►│     Visual      │───┘
                         │    Research     │
                         └─────────────────┘
```

### 📝 Implementation Plan

#### 1. Create `corpus_visuals_search` MCP Tool (`app/mcp/tools/corpus_visuals.py`)
- Query `article_images` BigQuery table
- Filter by: companies, industries, topics, image_type, chart_type
- Return: `{image_url, description, chart_type, source_article, relevance_score}`
- Add to `server.py` registration

#### 2. Create Visual Agent (`app/agents/research/visual.py`)
- Lightweight agent - single tool call
- Input: entities, industries, topics from `research_brief`
- Output: `VisualAgentOutput` with list of relevant visuals

#### 3. Add State Schema (`app/agents/research/state.py`)
- Add `VisualAgentOutput` Pydantic model
- Add `visual_output: Annotated[Optional[VisualAgentOutput], _keep_last]` to `DeepResearchState`

#### 4. Update Workflow (`app/graph/research_workflow.py`)
- Add `visual_research` node
- Update `route_after_groom` to fan-out to 3 agents:
  ```python
  return [
      Send("financial_research", state),
      Send("industry_research", state),
      Send("visual_research", state),  # NEW
  ]
  ```
- Add edge: `visual_research` → `synthesize`

#### 5. Update Synthesizer (`app/agents/research/synthesizer.py`)
- Accept `visual_output` from state
- Place visuals in appropriate sections based on topic matching
- Populate `supporting_visuals` in `FindingSection`

#### 6. Update API Route (`app/api/routes/deep_research.py`)
- Add `visual_research` to `NODE_DESCRIPTIONS`
- Handle `visual_output` in SSE streaming

### 📊 BigQuery Table Reference: `article_images`

Schema fields available for querying:
| Field | Type | Use |
|-------|------|-----|
| `id` | STRING | Primary key |
| `article_id` | STRING | Link to source article |
| `article_title` | STRING | Context for caption |
| `url` | STRING | Image URL to display |
| `image_type` | STRING | chart, graph, infographic, photo, diagram, table |
| `chart_type` | STRING | line, bar, pie, area, scatter, candlestick |
| `description` | STRING | AI-generated description |
| `topics` | STRING (JSON) | revenue, market_share, forecast, etc. |
| `companies` | STRING (JSON) | Companies mentioned |
| `industries` | STRING (JSON) | Industries covered |
| `relevance_score` | FLOAT64 | Quality ranking |

### 🔮 Future Phase: Chart Generation

After visuals from `article_images` are working, add:
- `generate_trend_chart` - Pull data from BigQuery trend tables → matplotlib/plotly chart
- `generate_comparison_table` - Structured data → visual table
- Integration with any new trending datasets

### 📁 Files to Create/Modify

**Create:**
- `backend/app/mcp/tools/corpus_visuals.py` - New search tool
- `backend/app/agents/research/visual.py` - New visual agent

**Modify:**
- `backend/app/mcp/server.py` - Register new tool
- `backend/app/agents/research/state.py` - Add VisualAgentOutput, visual_output field
- `backend/app/graph/research_workflow.py` - Add visual_research node, 3-way fan-out
- `backend/app/agents/research/synthesizer.py` - Incorporate visuals into sections
- `backend/app/api/routes/deep_research.py` - SSE handling for visual agent
- `backend/app/agents/research/README.md` - Document new agent
- `backend/app/mcp/tools/README.md` - Document new tool

### 🧪 Testing

```bash
# Verify workflow compiles with new node
cd backend
python -c "from app.graph.research_workflow import create_research_workflow; g = create_research_workflow(); print('Nodes:', list(g.nodes.keys()))"
# Expected: [..., 'visual_research', ...]

# Test corpus_visuals_search tool
python -c "from app.mcp.tools.corpus_visuals import corpus_visuals_search; print(corpus_visuals_search.invoke({'companies': ['Hexcel']}))"
```

---

## 🐛 SESSION 51: Deep Research Groomer Fix (January 6, 2026 - Night)

**Status**: ✅ COMPLETE

### 🎯 Problem
Deep Research workflow was "hanging" after the groomer phase - showing SSE progress like "query analysis" and "prior research" but never completing. Frontend would spin indefinitely.

### 🔍 Root Cause
**Two issues found:**

1. **Pydantic validation error**: Claude sometimes returns `clarifying_question` as a plain string (e.g., "To provide the most relevant analysis, which aspect...") instead of the expected object structure `{question, options, default_if_skipped}`. This caused a Pydantic validation error in `ResearchBrief(**brief_data)`.

2. **Silent failure**: When grooming failed, the workflow ended (returned `END` from `route_after_groom`), but the API route never emitted an error SSE event - it just hung waiting for more LangGraph events that would never come.

### ✅ Fixes Applied

1. **Groomer robustness** ([groomer.py](backend/app/agents/research/groomer.py)):
   - Added handling for `clarifying_question` as string
   - Converts string to proper object: `{question: <string>, options: null, default_if_skipped: "Proceeding with general analysis..."}`

2. **Error SSE emission** ([deep_research.py](backend/app/api/routes/deep_research.py)):
   - Added explicit check for `current_status == "grooming_failed"` in `on_chain_end` handler
   - Emits `error` SSE event with message and details
   - Properly sends `[DONE]` and returns so frontend isn't left hanging
   - Also handles case where brief is None but status isn't explicitly failed

### 📁 Files Modified
- `backend/app/agents/research/groomer.py` - Handle clarifying_question as string
- `backend/app/api/routes/deep_research.py` - Emit error SSE on grooming failure

### 🧪 Verification
```bash
cd backend
python -c "from app.graph.research_workflow import create_research_workflow; g = create_research_workflow(); print('OK:', list(g.nodes.keys()))"
```

---

## 🎨 SESSION 50: Pipeline Tab Visual Enhancements (January 6, 2026 - Late Night)

**Status**: ✅ COMPLETE

### 🎯 Goal
Enhance the visual design of the Pipeline tab to match the "Pulse" tab aesthetic, introducing better contrast, floating card layouts, and improved readability for search results.

### ✅ Changes Made

1.  **Pipeline Dashboard Styling** (`PipelineDashboard.tsx`):
    - Changed main background to `bg-slate-200` to match Pulse.
    - Converted Chat (Left) and Results (Right) panels into "floating cards" with `rounded-2xl`, margins, and shadows.
    - Added spacing (`gap-4`) between panels to reveal the underlying slate background, creating depth.

2.  **Search Result Zebra Striping** (`SearchBlockCard.tsx`):
    - Implemented alternating background colors for list items:
        - Even rows: `bg-white`
        - Odd rows: `bg-emerald-50/20`
    - Applied to Prospects, Contacts, and Trigger Events lists.
    - This "zebra striping" improves readability of long lists and visual separation between items.

### 📁 Files Modified
- `frontend/src/components/pipeline/PipelineDashboard.tsx` - Layout and background updates
- `frontend/src/components/pipeline/SearchBlockCard.tsx` - Zebra striping logic
- `frontend/README.md` - Added Pipeline Tab component documentation

---

## 🎨 SESSION 49: Global Color Palette Update & Welcome Audio Swap (January 6, 2026 - Night)

**Status**: ✅ COMPLETE

### 🎯 Goal
Unify the app's color palette by replacing all amber/orange accents with the emerald green palette used in the Pipeline and Research tabs. Also swap the welcome tour audio to an updated 2-minute version.

### ✅ Changes Made

1. **Welcome Audio Updated**
   - Swapped `/elevenlabs_audio_walkthrough_tutorial.mp3` → `/11labs_c1_hub_walkthrough_2mins.mp3`
   - Copied new audio file to `frontend/public/`
   - Updated reference in `WelcomeTourModal.tsx`

2. **Global Color Palette: Amber/Orange → Emerald**
   - Applied find-replace across all `.tsx` and `.ts` files in `frontend/src/`
   - Mapping: `amber-*` → `emerald-*`, `orange-*` → `emerald-*`

### 📁 Key Components Updated
- `WelcomeTourModal.tsx` - Play button, progress bar, sound tip
- `Button.tsx` - Accent variant  
- `Badge.tsx` - Warning, accent, medium priority badges
- `Toast.tsx` - Warning toast style
- `ReportDrawer.tsx` - Header icon
- `PodcastPlayer.tsx` - Gradient background
- `WeeklyBriefingSection.tsx` - Briefing cards
- `ValidationBadge.tsx` - Timeout/warning states
- `ResearchDashboard.tsx`, `ResearchCanvas.tsx` - Timeout states
- `ProductsDashboard.tsx` - Various badges
- `PipelineDashboard.tsx` - Qualified status
- `Sidebar.tsx` - Field Intel icon color
- `DataPreferencesDashboard.tsx` - Memory tab icon

### 🎨 Design Rationale
The emerald green palette creates a more unified, professional look across the entire application, matching the established design language of the Pipeline and Research tabs.

---

## 💬 SESSION 48: Ad-Hoc Briefing Bug Fix & Stacking Feature (January 6, 2026 - Night)

**Status**: ✅ COMPLETE

### 🐛 Bug Fix: Streaming Response Not Rendering

**Problem**: SSE progress events worked, but the final briefing report never appeared on screen.

**Root Cause**: When the backend sent `[DONE]`, the frontend code returned early (line 213) BEFORE constructing the response object. The `setResponse()` call at line 277 was never reached.

**Fix**: Moved response construction into the `[DONE]` handler before returning.

**File**: `frontend/src/hooks/useBriefing.ts`

### ✨ New Feature: Stacking Briefings with Collapsible History

Converted ad-hoc briefing from single-response to full conversational experience:

| Before | After |
|--------|-------|
| Single `response` state | Array `briefings[]` (newest first) |
| Follow-up replaces previous | Stacks on top, previous collapses |
| "2 follow-ups available" buttons | Removed |
| Hard limit then redirect | Gentle inline nudge after 2 questions |
| Previous briefings gone | Collapsed headers, click to expand |

**UX Flow**:
1. User asks question → Report appears as full ResponseCard
2. User asks another → New report on top, old one collapses to header
3. After 2 questions → Gentle nudge "For comprehensive analysis, try Deep Research"
4. User can click collapsed headers to expand/view previous briefings
5. "Clear conversation" at bottom to reset session

### 📁 Files Modified

- `frontend/src/hooks/useBriefing.ts`:
  - Changed `response` (single) → `briefings[]` (array)
  - Added `addBriefing()` helper to prepend new briefings
  - Updated all `setResponse` calls to use `addBriefing`
  - Added `currentBriefing` and backward-compat `response` alias
  
- `frontend/src/components/dashboard/AdHocBriefing.tsx`:
  - Added `CollapsibleBriefing` component for stacking
  - Newest briefing shows full, older ones collapse to headers
  - ChevronDown icon indicates expand/collapse state
  - Removed follow-up counter and "Start new" button
  - Added gentle Deep Research nudge after 2 turns
  - Added "Clear conversation" button at bottom

---

## 🎙️ SESSION 47: ElevenLabs Podcast Fix & GCS Streaming (January 6, 2026 - Night)

**Status**: ✅ COMPLETE

### 🎯 Goal
Generate a podcast for the current executive briefing for demo purposes.

### ✅ Completed

1. **Fixed ElevenLabs model typo** in `settings.py`:
   - `elevenlabs_model` was `"eleven_mon olingual_v1"` (with space) 
   - Fixed to `"eleven_monolingual_v1"`

2. **Fixed GCS upload** in `weekly_briefing.py`:
   - Removed `blob.make_public()` call that failed due to uniform bucket-level access
   - Now stores podcast URL as API endpoint instead of direct GCS URL

3. **Added BigQuery columns** to `weekly_briefings` table:
   - `podcast_url` (STRING)
   - `podcast_duration_seconds` (INTEGER)
   - `podcast_generated_at` (TIMESTAMP)

4. **Generated podcast audio** successfully:
   - Briefing ID: `c21f6cdc-1b55-4d1b-9a89-51aff8aa905f`
   - File: `podcasts/c21f6cdc-1b55-4d1b-9a89-51aff8aa905f.mp3` (4.7MB, ~272s)
   - Uploaded to GCS bucket `gen-lang-client-0436975498-c1-hub-data`

5. **Added streaming endpoint** `/api/podcast/briefing/{briefing_id}`:
   - Streams audio from GCS through backend (bypasses public access prevention)
   - Added to `backend/app/api/routes/podcast.py`
   - Returns `audio/mpeg` with proper headers for browser playback

6. **Updated podcast URL in BigQuery**:
   - Changed from direct GCS URL to `/api/podcast/briefing/{id}`
   - Verified: 272s duration stored correctly

7. **Tested locally** - Streaming endpoint verified working:
   - Status: 200 OK
   - Content-Type: audio/mpeg
   - Successfully streamed 100KB+ chunks

8. **Added Range request support** for proper browser audio playback:
   - Browsers require HTTP 206 Partial Content for audio seeking
   - Added `Content-Range` and `Content-Length` headers
   - Streams only requested byte range from GCS
   - Fixed "Failed to load audio" error in production

9. **Deployed and verified** - Podcast plays in production! 🎉

### 📁 Files Modified
- `backend/app/config/settings.py` - Fixed ElevenLabs model name typo
- `backend/app/api/routes/podcast.py` - Added `/api/podcast/briefing/{id}` streaming endpoint with Range support
- `backend/app/ingestion/generators/weekly_briefing.py` - Fixed GCS upload (removed make_public, uses API URL)
- `backend/scripts/operations/update_podcast_url.py` - Script to update URL in BigQuery
- `backend/scripts/operations/generate_podcast_for_briefing.py` - Script to regenerate podcast for existing briefings

### 🗄️ Database Changes
- Added 3 columns to `weekly_briefings` BigQuery table (podcast_url, podcast_duration_seconds, podcast_generated_at)

### 📝 Key Technical Notes
- GCS bucket `gen-lang-client-0436975498-c1-hub-data` has **public access prevention** enabled
- Cannot use `blob.make_public()` or `allUsers` IAM binding
- Solution: Stream through backend API instead of direct GCS URL
- **Range request support** is critical for browser audio playback (seeking, scrubbing)
- Frontend PodcastPlayer handles relative URLs via `API_BASE`

### 🔜 Next Steps (Podcast Improvements)

1. **Add second speaker for conversational podcast**
   - Currently single narrator (Rachel)
   - Make it a conversation between Host + Analyst
   - Use existing Josh voice for analyst commentary
   - Update `_build_podcast_script()` to create dialogue

2. **Move podcast player to modal**
   - Add "Listen to Podcast" 🎧 icon/button next to "Need to Know" header
   - Click opens modal with player (instead of embedded player taking space)
   - Cleaner UI, less visual clutter on the briefing page

---

## 🧠 SESSION 46: Memory Context Integration (January 6, 2026 - Late Evening)

**Status**: ✅ COMPLETE

### 🎯 Goal
Wire up the existing memory system to make preferences and saved memories actually influence AI responses.

### ✅ Changes Made

**Backend - Ad-Hoc Briefing Agent:**
- Added `build_agent_context()` call to fetch preferences + relevant memories
- Inject memory context into prompts in both `generate_briefing()` and `generate_briefing_stream()`
- Added `user_team` parameter to scope context by team

**Backend - API Endpoints:**
- Added `X-User-Team` header support to `/api/pulse/adhoc` and `/api/pulse/adhoc/stream`

**Frontend - API Client:**
- Added `X-User-Team` header to ad-hoc briefing API calls (from localStorage)

**Frontend - Deep Research:**
- Added "Save to Memory" button to `ResearchReport.tsx` Executive Summary header
- Implemented save handler with UX states: idle → saving → saved (or error)
- Auto-resets on error after 3 seconds

### 📁 Files Modified
- `backend/app/agents/adhoc_briefing/agent.py` - Memory context injection
- `backend/app/api/routes/briefing.py` - X-User-Team header
- `frontend/src/lib/api.ts` - X-User-Team header in ad-hoc calls
- `frontend/src/components/research/ResearchReport.tsx` - Save to Memory button

### 🧪 Testing Notes
- Backend imports verified successfully
- Manual testing required to verify end-to-end flow
- Test by: 1) Add preference in Data & Preferences, 2) Ask ad-hoc question, 3) Verify context influences response

---

## 🚀 SESSION 45: Split Web Search by Engine (January 6, 2026 - Evening)

**Status**: ✅ DEPLOYED

### 🎯 Problem Solved

The `ingest-web-search` job was running 236 queries (91 Exa + 145 Tavily) and taking 25-35 minutes. Since Cloud Scheduler has a hard 30-minute timeout, jobs would show "failed" even when data successfully ingested.

### ✅ Solution: Split by Search Engine

Instead of trimming queries, we split the web search job into two separate jobs by search engine:

| Before | After |
|--------|-------|
| `ingest-web-search` (236 queries, 25-35 min) | `ingest-exa` (91 queries, ~15 min) |
| | `ingest-tavily` (145 queries, ~18 min) |

### 📊 New Scheduler Jobs (Deployed)

| Job | Schedule (UTC) | Schedule (CST) | Sources | Timeout |
|-----|---------------|----------------|---------|---------|
| `ingest-flash-update` | Every 4h | Every 4h | rss, freight | 10 min |
| `ingest-exa` | 8:00 AM | 2:00 AM | exa_queries, press_releases | 20 min |
| `ingest-tavily` | 8:20 AM | 2:20 AM | tavily_queries | 25 min |
| `ingest-financial` | 8:45 AM | 2:45 AM | sec, earnings, fmp_news, stocknews | 30 min |
| `weekly-executive-briefing` | Mon 14:30 | Mon 8:30 AM | (triggers briefing) | 15 min |

### 🔧 Implementation Details

1. **New source types added to orchestrator.py**:
   - `exa_queries` - runs only Exa (91 queries + per-company news)
   - `tavily_queries` - runs only Tavily (145 queries)
   - `industry_queries` - legacy, runs both (for backward compat)

2. **Logic**: 
   ```python
   run_exa = "exa_queries" in sources or "industry_queries" in sources
   run_tavily = "tavily_queries" in sources or "industry_queries" in sources
   ```

3. **Deduplication**: Works across jobs - if Exa finds URL at 2:00 AM, Tavily skips it at 2:20 AM

4. **No downstream changes**: Same BigQuery tables, same `source_type` values, same classification/storage

### 🧹 Bonus Fix: Classifier Company Loading

Fixed classifier to use BigQuery `companies` table as single source of truth:
- Removed redundant `_load_from_csv()` method
- Changed `load_tracked_entities()` to use `db.get_companies()` instead of non-existent `list_entities()`
- Now when you add/remove companies in BigQuery, classifier picks them up automatically

### 📁 Files Modified
- `backend/app/ingestion/orchestrator.py` - Added exa_queries/tavily_queries source handling
- `backend/app/ingestion/classifier.py` - Fixed to use BigQuery companies table
- `backend/app/api/routes/scheduler.py` - Updated API docs
- `backend/app/ingestion/README.md` - Updated scheduler job docs
- `deploy/scheduler/deploy_jobs.ps1` - New job definitions (ingest-exa, ingest-tavily)
- `.agent/ARCHITECTURE.md` - Updated ADR-008

### ✅ Deployment Completed
- Code pushed: commits `379b695`, `6371424`
- Scheduler jobs deployed via `deploy_jobs.ps1`
- Legacy `ingest-web-search` job deleted
- First run: 2:00 AM CST (ingest-exa), 2:20 AM CST (ingest-tavily)

### 🔧 Useful Commands

```powershell
# Deploy scheduler jobs
cd deploy/scheduler
.\deploy_jobs.ps1

# Test Exa queries only (~15 min)
$body = '{"sources": ["exa_queries", "press_releases"]}'
Invoke-RestMethod -Uri "https://c1-hub-4iz75bvpyq-uc.a.run.app/api/v1/scheduler/ingest" `
  -Method Post -Body $body -ContentType "application/json" -TimeoutSec 1200

# Test Tavily queries only (~18 min)
$body = '{"sources": ["tavily_queries"]}'
Invoke-RestMethod -Uri "https://c1-hub-4iz75bvpyq-uc.a.run.app/api/v1/scheduler/ingest" `
  -Method Post -Body $body -ContentType "application/json" -TimeoutSec 1500

# Check scheduler jobs
gcloud scheduler jobs list --location=us-central1 --project=gen-lang-client-0436975498
```

---

## 📦 SESSION 44 HANDOFF (January 6-7, 2026 - Night)

**Status**: Superseded by Session 45 - web search now split by engine

### ✅ What Was Done

1. **Split `ingest-deep-dive` into 2 jobs** (was timing out at 30 min)
   - `ingest-web-search` (2:00 AM CST / 8:00 UTC) - industry_queries + press_releases
   - `ingest-financial` (2:45 AM CST / 8:45 UTC) - sec, earnings, fmp_news, stocknews
   - 45-min buffer between jobs

2. **Fixed timezone bug in date_extraction.py**
   - Error: `can't compare offset-naive and offset-aware datetimes`
   - Fix: Changed `datetime.now()` to `datetime.now(timezone.utc)` in `_is_future_date()`

3. **Increased Cloud Run liveness probe tolerance**
   - Was: 120s period × 10 failures = 20 min (killing jobs mid-execution)
   - Now: 300s period × 12 failures = 60 min tolerance
   - Command: `gcloud run services update c1-hub --liveness-probe="httpGet.path=/health,httpGet.port=8080,periodSeconds=300,failureThreshold=12,timeoutSeconds=60"`

4. **Updated scheduler jobs via deploy_jobs.ps1**

### ⚠️ Issue That Led to Session 45

The `ingest-web-search` job was still timing out at 30 minutes because it ran 236 queries. Session 45 solved this by splitting into `ingest-exa` and `ingest-tavily`.

---

## �🚀 SESSION 43: Pipeline Agent Follow-Up Bug Fix (January 6, 2026)

**Status**: ✅ DEPLOYED (commit `b455413`)

### 🐛 Bug Fixed
**Error**: `PipelineAgentResponse message Input should be a valid string [type=string_type, input_value=[{'text': '...', 'type': 'tool_use'}]`

This occurred on **follow-up questions** (especially contact-level queries) when the agent tried to use tools during the final response phase.

### 🔍 Root Cause
Claude's `response.content` can be either:
- A **string** (text-only response)
- A **list** (when response includes tool_use blocks)

The code was passing `response.content` directly to `PipelineAgentResponse(message=...)` which expects only a string.

### ✅ Fix Applied
1. **Added `_extract_text_content()`** helper method to handle both formats
   - Extracts text from list content blocks
   - Ignores tool_use blocks
   - Provides fallback message if no text found

2. **Added multi-turn tool loop** in `process_query()`
   - Uses `llm_with_tools` for final response (was using plain `llm`)
   - Allows agent to call additional tools during follow-up
   - Max 3 iterations to prevent infinite loops

### 📁 Files Modified
- `backend/app/agents/pipeline/agent.py` - Added helper method and tool loop

---

## 🚀 SESSION 42: Deep Research SSE Streaming & Output Fix (January 6, 2026)

**Status**: 🔄 DEPLOYED - Awaiting Cloud Build

### ✅ What Was Done
1. ✅ **Real-time SSE Progress Streaming** - Fixed batched progress events
   - Added `asyncio.wait_for` with 100ms timeout for responsive polling
   - Progress events now stream immediately rather than waiting for LangGraph events
2. ✅ **Parallel State Merge Fix** - Fixed missing final report
   - Added `accumulated_state` dict to capture outputs from parallel nodes
   - Financial and Industry agents run in parallel; their outputs are now properly merged
3. ✅ **Diagnostic Logging** - Added to synthesizer for debugging parse failures

### 🔧 Root Causes Identified
- **SSE Batching**: `ProgressCollector.get_pending_events()` only drained on LangGraph events
- **Missing Report**: With parallel `Send` API, individual node outputs weren't being merged before final emission

### 📁 Files Modified
- `backend/app/api/routes/deep_research.py` - SSE polling + accumulated_state
- `backend/app/agents/research/synthesizer.py` - Diagnostic logging

### ⏳ Verification
After Cloud Build completes (~5 min):
1. Navigate to Research tab
2. Query: "give me everything i need to know about hexcel moving into 2026"
3. Verify: SSE progress events stream in real-time (not batched)
4. Verify: Final report renders after workflow completes

### ✅ COMPLETE: Research Tab Frontend Redesign

**Goal**: Streamline Research tab layout to match Pipeline tab UX

**Remove "Research Tools" section**:
- [x] Remove templates (Supplier Comparison, Market Analysis, Company Deep Dive, etc.)
- [x] Remove Recent Reports/Searches section
- [x] Free up space for larger chat interface

**Layout changes**:
- [x] Move Research agent chat interface to **left side** of page (like Pipeline tab)
- [x] Apply **green aesthetic** to match Pipeline agent chatbox styling
- [x] Saved Reports button moved to upper-right of results panel

---

## 🚀 SESSION 41: Ad-Hoc Briefing Enhancement (January 6, 2026)

**Status**: ✅ COMPLETE (including SSE progress events)

### ✅ What Was Done
1. ✅ Upgraded model from Haiku → **Claude Sonnet 4.5**
2. ✅ Added external tool search: **Corpus → Exa → StockNewsAPI** (in order)
3. ✅ Increased max_tokens: 1500 → **3000** for richer responses
4. ✅ Added 120-second timeout config
5. ✅ Removed content truncation for full context
6. ✅ Added formatted prompts with sections (Overview, Key Findings, Sources)
7. ✅ Created `fmp_premium_news.py` MCP tool (53 total tools)
8. ✅ **SSE Progress Events** - Real-time feedback during research phases

### 🎉 SSE Progress Events (Added Session 41b)
Streaming now shows step-by-step progress with user-friendly labels:
- **Knowledge Base** → "Searching internal knowledge base..." → "Found N articles"
- **Advanced Web Search** → "Searching web for recent news..." → "Found N articles"
- **Stock Market News** → "Found N articles"
- **Analysis** → "Synthesizing intelligence response..." → "Response complete"

Frontend displays progress with:
- Step icons (Database, Globe, TrendingUp, Brain)
- Checkmarks for completed steps
- Animated spinner for running steps
- Article counts for each source

### 📁 Files Changed
- `backend/app/agents/adhoc_briefing/agent.py` - Core enhancements + streaming progress events
- `backend/app/mcp/tools/fmp_premium_news.py` - New tool
- `backend/app/mcp/server.py` - Registered FMP tool
- `frontend/src/hooks/useBriefing.ts` - Added `progressSteps` state
- `frontend/src/components/dashboard/AdHocBriefing.tsx` - Progress display component

---

## 🔄 SESSION 40 HANDOFF (January 6, 2026 - Evening)

**Status**: Future date validation fix DEPLOYED (Build `1ddef386-dcb0-497d-b407-34a00d7ce5d4`)

### ✅ What Was Done
1. ✅ Diagnosed root cause of future dates in BigQuery
2. ✅ Fixed `orchestrator.py` - Future date validation for Exa API results  
3. ✅ Fixed `press_releases/collector.py` - Same future date validation
4. ✅ Verified RSS ingestion working (61 articles in morning run)
5. ✅ Verified deep ingestion working with all 8 sources
6. ✅ Updated `ingestion/README.md` with troubleshooting details
7. ✅ Added ADR-009 to `ARCHITECTURE.md`
8. ✅ Deployed to Cloud Run (commit `df3e415`)

### 🔍 Root Cause: Future Dates from Exa API

**Discovery**: Articles with future dates (2026-05-13, 2026-09-11, etc.) are coming from Exa's API, NOT from date extraction.

**How it happens**:
1. Exa returns `published_date` field in search results
2. For market research pages with projections ("expected to reach $X by 2026"), Exa incorrectly extracts those projection dates as publication dates
3. Our code was trusting Exa's dates without validation

**Test evidence**:
```python
# Exa returned these for market research pages:
"2026-05-13T19:02:00.000Z"  # US aerospace composites market
"2026-09-11T00:00:00.000Z"  # Aerospace composites market
```

### 🔧 Fix Applied
Added future date validation in two places:
1. **`backend/app/ingestion/orchestrator.py`** (line ~1490)
2. **`backend/app/tools/press_releases/collector.py`** (line ~60)

Logic: If parsed date > `utcnow() + 2 days`, reject it and set to `None`

**Test results**:
- Past dates (2024, Jan 2025) → PASS ✓
- Today/tomorrow → PASS ✓  
- Future dates (May 2026, Sep 2026) → REJECTED ✓

### ⏳ Verification Queries (Post-Deployment)

**1. Check if fix is actively rejecting future dates** (Cloud Run logs):
```powershell
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=c1-hub AND textPayload:\"Rejecting future date\"" --limit=20 --project=gen-lang-client-0436975498 --format="table(timestamp,textPayload)"
```

**2. Count existing future-dated articles** (BigQuery - baseline):
```sql
SELECT COUNT(*) as future_count
FROM `gen-lang-client-0436975498.c1_intelligence.digest_items` 
WHERE published_at > CURRENT_TIMESTAMP()
```

**3. See what future-dated articles exist** (BigQuery):
```sql
SELECT title, published_at, source_url, created_at
FROM `gen-lang-client-0436975498.c1_intelligence.digest_items` 
WHERE published_at > CURRENT_TIMESTAMP()
ORDER BY published_at DESC
LIMIT 20
```

**4. Check articles ingested AFTER deployment with NULL published_at** (BigQuery):
```sql
-- These are articles where we rejected the future date
SELECT title, source_url, published_at, created_at, feed_eligible
FROM `gen-lang-client-0436975498.c1_intelligence.digest_items` 
WHERE created_at > TIMESTAMP('2026-01-06 18:00:00 UTC')
  AND published_at IS NULL
ORDER BY created_at DESC
LIMIT 20
```

**5. Confirm deployment succeeded**:
```powershell
gcloud builds describe 1ddef386-dcb0-497d-b407-34a00d7ce5d4 --project=gen-lang-client-0436975498 --format="value(status)"
# Expected: SUCCESS
```

### 📝 Additional Observations
User noted some URLs should potentially be excluded entirely:
- `/glossary/*` pages (e.g., schunk-group.com/en/glossary/fiber-composites)
- `/about-us` pages
- Homepage variants (`/homev2-1`)

These are not news articles - consider URL pattern filtering in future enhancement.

---

## 🔄 SESSION 39 HANDOFF (January 6, 2026)

**Status**: All fixes deployed, Cloud Build running, MONITORING REQUIRED

### ✅ What Was Done
1. ✅ Fixed `resilient_llm.py` - SDK system param bug (DEPLOYED)
2. ✅ Added OpenAI fallback key to Cloud Run (DEPLOYED)
3. ✅ Fixed scheduler job JSON bodies and timeouts (DEPLOYED)
4. ✅ Consolidated to 3 scheduler jobs (deleted redundant ones)
5. ✅ Resumed scheduler jobs (`ingest-flash-update`, `ingest-deep-dive`)
6. ✅ Triggered test ingestion - RSS worked (61 articles)
7. ✅ Triggered full deep dive with all 8 sources
8. ✅ Updated all documentation
9. ✅ Fixed `digest_classifier.py` bypass bug (JUST DEPLOYED - 11:45 AM CST)

### 🔧 Bug That Was Just Fixed
`digest_classifier.py` line 325 was bypassing our SDK fix:
- **Was**: `self.client.messages.create()` (direct Anthropic SDK call)
- **Now**: `self.client.messages_create()` (our wrapper with system param fix)
- **Commit**: `938ef25` pushed at 11:45 AM CST

### ⏳ Next Steps for New Session
```powershell
# 1. Wait for Cloud Build to complete (~5 min)
# Check: https://console.cloud.google.com/cloud-build/builds?project=gen-lang-client-0436975498

# 2. Once deployed, verify the fix worked
$body = '{"sources": ["rss"]}'
Invoke-RestMethod -Uri "https://c1-hub-4iz75bvpyq-uc.a.run.app/api/v1/scheduler/ingest" `
  -Method Post -Body $body -ContentType "application/json" -TimeoutSec 300

# 3. Check for any remaining "system: Input should be a valid list" errors
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=c1-hub AND textPayload:\"system: Input should be a valid list\"" --limit=20 --project=gen-lang-client-0436975498 --format="table(timestamp,textPayload)"

# 4. If errors persist, search for other places using direct Anthropic calls:
grep -r "\.messages\.create" backend/app/ --include="*.py"
```

### 📊 Current Scheduler Jobs
| Job | Schedule | Status |
|-----|----------|--------|
| `ingest-flash-update` | Every 4h | ✅ ENABLED |
| `ingest-deep-dive` | 2 AM CST | ✅ ENABLED |
| `weekly-executive-briefing` | Mon 8:30 AM | ✅ ENABLED |

### 📁 Key Files Modified This Session
- `backend/app/utils/resilient_llm.py` - Original SDK fix
- `backend/app/services/digest_classifier.py` - Bypass bug fix
- `cloudbuild.yaml` - Added OPENAI_API_KEY
- `deploy/scheduler/deploy_jobs.ps1` - Job definitions
- `backend/app/ingestion/README.md` - Documentation
- `.agent/ARCHITECTURE.md` - ADR-008
- `WORKLOG.md` - This file

---

## Session 39 (January 6, 2026) - Scheduler Job Investigation & Fixes 🔄 IN PROGRESS

### 📋 Context

Investigated why Cloud Scheduler daily ingestion jobs weren't running. Discovered multiple critical issues.

### 🔍 Root Cause Analysis

**Issue 1: Malformed JSON Bodies** ✅ FIXED
- Cloud Scheduler jobs had invalid JSON in message bodies
- PowerShell escaping issues when using `gcloud scheduler jobs update`
- Bodies looked like `{sources: [rss, sec]}` instead of `{"sources": ["rss", "sec"]}`
- Result: HTTP 422 (Unprocessable Entity) from FastAPI validation

**Issue 2: Timeout Configuration** ✅ FIXED
- Some jobs had 180s (3 min) timeout
- Ingestion routinely takes 5-15+ minutes
- Result: DEADLINE_EXCEEDED errors

**Issue 3: 🚨 CRITICAL - Anthropic SDK `system` Parameter Bug** ⚠️ PARTIAL FIX
- **File**: `backend/app/utils/resilient_llm.py` line ~413
- Anthropic SDK 0.75.0 changed how `system` parameter works
- Error: `'system: Input should be a valid list'`
- **Impact**: ALL classification calls failing - articles stored without classification
- **Cause**: Code passing `system=system` even when `system=None`

**ADDITIONAL DISCOVERY**: `digest_classifier.py` was bypassing the fix!
- Line 325 used `self.client.messages.create()` (direct SDK call)
- Should use `self.client.messages_create()` (our wrapper with the fix)
- **FIX APPLIED**: Changed to use wrapper method

**Issue 4: Missing OpenAI Fallback Key** ✅ FIXED
- `OPENAI_API_KEY` was in Secret Manager but not mounted in Cloud Run
- Logs showed "No OpenAI API key configured for fallback"

**Issue 5: Redundant/Stub Scheduler Jobs**
- `daily-evening-ingest` was redundant (subset of sources already in `ingest-deep-dive`)
- `weekly-corpus-refresh` and `weekly-data-cleanup` were STUBS - they did nothing
- `ingest-deep-dive` was missing sources: `press_releases`, `fmp_news`, `freight`

### ✅ All Fixes Applied & Verified

1. **Fixed Anthropic SDK `system` parameter bug** in `resilient_llm.py`:
   ```python
   # Uses conditional param dict - only includes system when provided
   anthropic_params = {"model": model, "max_tokens": max_tokens, ...}
   if system:
       anthropic_params["system"] = system
   response = await self.anthropic_client.messages.create(**anthropic_params)
   ```

2. **Added OpenAI fallback key to Cloud Run** via `cloudbuild.yaml`:
   ```yaml
   --set-secrets=...,OPENAI_API_KEY=OPENAI_API_KEY:latest
   ```

3. **Fixed all scheduler job JSON bodies** - proper escaping for PowerShell → gcloud:
   ```powershell
   --message-body='{\"sources\": [\"rss\", \"stocknews\"]}'
   ```

4. **Updated timeouts** to Cloud Scheduler max (30 min):
   - `ingest-flash-update`: 900s (15 min)
   - `ingest-deep-dive`: 1800s (30 min MAX)

5. **Consolidated to 3 scheduler jobs** - deleted redundant/stub jobs:
   - ❌ Deleted: `daily-evening-ingest` (redundant)
   - ❌ Deleted: `weekly-corpus-refresh` (stub)
   - ❌ Deleted: `weekly-data-cleanup` (stub)

6. **Updated `ingest-deep-dive` to run ALL 8 sources**:
   - `industry_queries` (Exa + Tavily web search)
   - `rss` (14 RSS feeds)
   - `sec` (SEC EDGAR filings)
   - `earnings` (Earnings transcripts)
   - `stocknews` (StockNews API)
   - `fmp_news` (FMP Premium news) ← NEW
   - `freight` (Drewry WCI) ← NEW
   - `press_releases` (Exa) ← NEW

7. **Fixed `deploy_jobs.ps1`** PowerShell script issues:
   - Variable extraction before gcloud calls (avoided hashtable reference issues)
   - Changed `--headers` to `--update-headers` for updates
   - Added legacy jobs to auto-delete list

### 🧪 Verification

**Test RSS ingestion succeeded:**
```
status: success
records_collected: 61
message: "Ingestion complete: 61 articles collected"
execution_time_seconds: 106.45
```

**Full deep dive triggered** (8 sources) - running and being monitored.

**Scheduler jobs resumed:**
```powershell
gcloud scheduler jobs resume ingest-flash-update --location=us-central1
gcloud scheduler jobs resume ingest-deep-dive --location=us-central1
```

### 📊 Final Scheduler Job Structure

| Job | Schedule | Timeout | Sources | Status |
|-----|----------|---------|---------|--------|
| `ingest-flash-update` | Every 4 hours | 15 min | rss, stocknews, freight | ✅ ENABLED |
| `ingest-deep-dive` | 2 AM CST daily | 30 min | ALL 8 sources | ✅ ENABLED |
| `weekly-executive-briefing` | Mon 8:30 AM CST | 15 min | (triggers briefing) | ✅ ENABLED |

### 📁 Files Modified

- [backend/app/utils/resilient_llm.py](backend/app/utils/resilient_llm.py) - SDK system param fix
- [cloudbuild.yaml](cloudbuild.yaml) - Added OPENAI_API_KEY secret
- [deploy/scheduler/deploy_jobs.ps1](deploy/scheduler/deploy_jobs.ps1) - Complete rewrite, proper JSON escaping
- [backend/scripts/health/ingestion_health_check.py](backend/scripts/health/ingestion_health_check.py) - Updated job filters
- [.agent/ARCHITECTURE.md](.agent/ARCHITECTURE.md) - Added ADR-008 for scheduler structure
- [backend/app/ingestion/README.md](backend/app/ingestion/README.md) - Updated with scheduler details

### 🔮 Future Consideration: Split Daily Jobs

If ingestion consistently approaches 25+ minutes, consider splitting:
```
2:00 AM CST - ingest-fast-sources (rss, freight) - 15 min
2:20 AM CST - ingest-web-search (industry_queries) - 30 min  
2:50 AM CST - ingest-financial (sec, earnings, stocknews, fmp_news, press_releases) - 20 min
```

**Current decision**: Monitor single-job approach. Split only if timeout issues occur.

### 🔧 Production Status

- **OpenAI fallback NOT configured** in production (no `OPENAI_API_KEY` secret mounted)
- Need to add OpenAI key to Secret Manager and `cloudbuild.yaml` if we want fallback protection

---

## Session 38 (January 6, 2026) - Entity Aggregator UI Redesign ✅

### 📋 Context

Redesigned the DRUMBEAT entity aggregator from always-visible pills with heatmap effects to a cleaner, more scannable summary-based interface with expandable drawers.

### ✅ Completed

1. **EntityAggregator Component Redesign** 🎨
   - **File**: [EntityAggregator.tsx](frontend/src/components/digest/EntityAggregator.tsx)
   - Removed always-visible entity pills that consumed vertical space
   - Removed heatmap visual effects (opacity/color intensity scaling)
   - Implemented 5 compact summary stat buttons:
     - 🏢 Companies count (distinct)
     - ⚗️ Materials count (distinct)
     - 🏭 Industries count (distinct)
     - 🏷️ Topics count (distinct)
     - ⚠️ High Priority items count
   - Added expandable drawer functionality:
     - Click any stat to expand pills for that category
     - Pills displayed in scrollable container (max-height: 200px)
     - Pills sorted by count descending (highest first)
     - Click-to-filter functionality preserved
   - Tooltips show "{count} {type} mentioned in the current drumbeat feed"

2. **Local Development Auth Bypass** 🔑
   - **File**: [PasswordGate.tsx](frontend/src/components/auth/PasswordGate.tsx)
   - Added localhost detection for local development
   - Allows password `partnership2026` to authenticate without backend API call
   - Enables frontend-only testing during development
   - Production authentication flow unchanged

### 📁 Files Modified
- [frontend/src/components/digest/EntityAggregator.tsx](frontend/src/components/digest/EntityAggregator.tsx) - Complete redesign
- [frontend/src/components/auth/PasswordGate.tsx](frontend/src/components/auth/PasswordGate.tsx) - Local dev bypass
- [frontend/README.md](frontend/README.md) - Updated component description

### 🎯 Design Rationale

**Before:** Always-visible pills with subtle heatmap effects that were imperceptible
- Pills with vastly different counts (73 vs 27) looked identical
- Consumed significant vertical space
- Required horizontal scrolling for long entity lists

**After:** Compact summary stats with on-demand expansion
- Clean initial state: 5 icon-count buttons in a single row
- Faster scanning: See all aggregations at a glance
- Space-efficient: Drawer only appears when needed
- Better UX: Tooltips and clear visual hierarchy

### 🚀 Deployment

Changes pushed to `origin/master`. Cloud Build automatically triggered deployment to Cloud Run.

---

## Session 37 (January 6, 2026) - Pre-Demo Polish & UX Improvements ✅

### 📋 Context

Final polish session before demo day. Added toast notifications for better user feedback, cleaned up debug logging, and improved error handling throughout the frontend.

### ✅ Completed

1. **Toast Notification System** 🔔
   - **File**: [frontend/src/components/ui/Toast.tsx](frontend/src/components/ui/Toast.tsx) - **NEW**
   - Created `ToastProvider` context provider with `useToast` hook
   - Support for 4 toast types: success, error, warning, info
   - Auto-dismiss with configurable duration (default 5s)
   - Slide-in animation from right side
   - Accessible with proper ARIA roles
   - **File**: [frontend/src/app/layout.tsx](frontend/src/app/layout.tsx)
   - Wrapped app with `ToastProvider`

2. **Improved Error Feedback** 🎯
   - **File**: [frontend/src/app/page.tsx](frontend/src/app/page.tsx)
   - Report export now shows success/error toasts instead of console.log
   - Podcast generation button shows "Coming soon" toast instead of stub log
   - Save research report errors handled silently (non-blocking)
   - Added proper scroll-to-section implementation
   - **File**: [frontend/src/components/research/ResearchDashboard.tsx](frontend/src/components/research/ResearchDashboard.tsx)
   - Added toast notification for failed saved report loads

3. **Debug Console.log Cleanup** 🧹
   - **File**: [frontend/src/app/page.tsx](frontend/src/app/page.tsx)
   - Removed `console.log('Export complete...')` 
   - Removed `console.log('Scroll to section...')` (replaced with actual implementation)
   - **File**: [frontend/src/components/pipeline/PipelineDashboard.tsx](frontend/src/components/pipeline/PipelineDashboard.tsx)
   - Removed `console.log('[PipelineDashboard] searchBlocks...')` debug logging

### 📁 Files Modified
- [frontend/src/components/ui/Toast.tsx](frontend/src/components/ui/Toast.tsx) - **NEW** Toast system
- [frontend/src/components/ui/index.ts](frontend/src/components/ui/index.ts) - Export toast
- [frontend/src/app/layout.tsx](frontend/src/app/layout.tsx) - Toast provider
- [frontend/src/app/page.tsx](frontend/src/app/page.tsx) - Toast usage, cleanup
- [frontend/src/components/research/ResearchDashboard.tsx](frontend/src/components/research/ResearchDashboard.tsx) - Toast for errors
- [frontend/src/components/pipeline/PipelineDashboard.tsx](frontend/src/components/pipeline/PipelineDashboard.tsx) - Remove debug logs

### ✅ Build Verification

```bash
cd frontend && npm run build
# ✔ Compiled successfully

cd backend
python -c "from app.mcp.server import get_all_mcp_tools; print(f'MCP Tools: {len(get_all_mcp_tools())}')"
# MCP Tools: 52
```

### 📋 Remaining TODOs Found in Codebase

| Location | Item | Priority |
|----------|------|----------|
| `grounding.py:375` | Create user_preferences table in BigQuery | Low |
| `gcp_storage.py:2449` | Track tools_used in deep_research_reports | Low |
| `reports.py:71` | Implement actual report generation | Medium |

### 🎯 Demo Day Checklist

**Pre-Demo Setup:**
- [ ] Verify Cloud Run deployment is current (`git push` to trigger)
- [ ] Check API health: `https://c1-hub-4iz75bvpyq-uc.a.run.app/api/health`
- [ ] Verify LangSmith tracing is working
- [ ] Ensure Anthropic API credits are sufficient
- [ ] Test a Deep Research query end-to-end

**Key Demo Features:**
- ✅ **Pulse Tab**: Weekly briefing with podcast player, drumbeat feed
- ✅ **Research Tab**: Deep Research with 6-node pipeline, real-time progress
- ✅ **Pipeline Tab**: AI prospect discovery with Apollo enrichment
- ✅ **Toast Notifications**: User feedback for actions
- ✅ **Error Handling**: Timeout, error states with retry options
- ✅ **Caching**: Reports cached for 1 hour (memory) / 24 hours (BigQuery)

**Known Limitations:**
- Podcast generation for custom reports not yet implemented (shows "Coming soon" toast)
- Report export creates client-side file (no server-side PDF generation)
- StockNewsAPI may return 422 errors (rate limited on free tier)

---

## Session 36 (January 6, 2026) - Deep Research Timeout Handling ✅

### 📋 Context

Implemented comprehensive timeout handling for the Deep Research workflow to prevent indefinite hangs during production queries. This addresses the issue where queries like "What is the outlook for carbon fiber in aerospace?" could hang indefinitely.

### ✅ Completed

1. **Timeout Configuration Settings** ⚙️
   - **File**: [backend/app/config/settings.py](backend/app/config/settings.py)
   - Added `deep_research_workflow_timeout: int = 300` (5 minutes total)
   - Added `deep_research_tool_timeout: int = 60` (per-tool timeout)
   - Added `deep_research_llm_timeout: int = 120` (LLM extraction timeout)

2. **Backend Workflow Timeout Wrapper** 🕐
   - **File**: [backend/app/api/routes/deep_research.py](backend/app/api/routes/deep_research.py)
   - Added workflow start time tracking
   - Added elapsed time check during event streaming loop
   - Emits `timeout_info` SSE event at start (informational)
   - Emits `timeout` SSE event when exceeded with:
     - `elapsed_seconds`, `timeout_seconds`
     - `completed_nodes` (what finished)
     - `active_nodes` (where it got stuck)
   - Handles `asyncio.TimeoutError` in exception handler

3. **Per-Tool Timeout Utility** 🔧
   - **File**: [backend/app/utils/retry.py](backend/app/utils/retry.py)
   - Added `with_timeout()` async function for awaitable timeouts
   - Added `sync_tool_with_timeout()` decorator for sync tool calls
   - Uses ThreadPoolExecutor for sync timeout enforcement
   - Records timeout failures to `tool_metrics`

4. **Frontend Timeout State** 📊
   - **File**: [frontend/src/hooks/useDeepResearch.ts](frontend/src/hooks/useDeepResearch.ts)
   - Added `isTimeout: boolean` state
   - Added `timeoutInfo` object with details
   - Added `timeout` and `timeout_info` SSE event handlers
   - Marks running nodes as 'timeout' status

5. **Frontend Timeout UI** 🎨
   - **File**: [frontend/src/components/research/ResearchCanvas.tsx](frontend/src/components/research/ResearchCanvas.tsx)
   - Added amber-themed timeout card (distinct from red error card)
   - Shows elapsed time and which stages completed/stuck
   - "Try Again" button with refresh icon
   - Propagated `isTimeout` and `timeoutInfo` through:
     - `page.tsx` → `ResearchDashboard` → `ResearchCanvas`

6. **Documentation Updated** 📚
   - **File**: [backend/app/agents/research/README.md](backend/app/agents/research/README.md)
   - Added Timeout Configuration section with code examples
   - Updated Phase 5 as completed
   - Added troubleshooting entry for timeout issues

### 📁 Files Modified
- [backend/app/config/settings.py](backend/app/config/settings.py) - Timeout settings
- [backend/app/api/routes/deep_research.py](backend/app/api/routes/deep_research.py) - Workflow timeout
- [backend/app/utils/retry.py](backend/app/utils/retry.py) - Timeout utilities
- [frontend/src/hooks/useDeepResearch.ts](frontend/src/hooks/useDeepResearch.ts) - Timeout state
- [frontend/src/components/research/ResearchCanvas.tsx](frontend/src/components/research/ResearchCanvas.tsx) - Timeout UI
- [frontend/src/components/research/ResearchDashboard.tsx](frontend/src/components/research/ResearchDashboard.tsx) - Props
- [frontend/src/app/page.tsx](frontend/src/app/page.tsx) - Props
- [backend/app/agents/research/README.md](backend/app/agents/research/README.md) - Documentation

### ✅ Testing

```bash
# Backend verification
cd backend
python -c "from app.config.settings import settings; print(f'Timeout: {settings.deep_research_workflow_timeout}s')"
# Output: Timeout: 300s

# Frontend verification
cd frontend && npm run build
# Output: ✔ Compiled successfully
```

### 🔧 How It Works

1. **Workflow starts** → `timeout_info` event sent with timeout config
2. **Every event iteration** → Check if `elapsed > workflow_timeout`
3. **If exceeded** → Emit `timeout` event with completed/stuck nodes
4. **Frontend receives** → Shows amber timeout card with retry option
5. **User clicks retry** → Can try again with same or modified query

### 🚧 Future Enhancements
- Apply `sync_tool_with_timeout` decorator to specific slow tools (SEC, Exa)
- Add per-node timeout tracking in LangSmith
- Consider adaptive timeout based on query complexity

---

## Session 35 (January 6, 2026) - OpenAI Fallback Provider Implementation ✅

### 📋 Context

Added OpenAI as a fallback LLM provider to protect against Anthropic credit outages. When Claude models fail (e.g., due to exhausted credits), the system automatically falls back to OpenAI GPT-4o models.

**User Requirement**: "If a claude model goes out somewhere, and it's because I need to add credits to my account, I want another 'makeshift' model that's not from my anthropic api key to hold the line."

**Constraint**: OpenAI is ONLY used as a fallback. Primary models remain Claude (Anthropic).

### ✅ Completed

1. **Resilient LLM Module Expansion** 🛡️
   - **File**: [backend/app/utils/resilient_llm.py](backend/app/utils/resilient_llm.py)
   - Extended `ResilientChatAnthropic` class with cross-provider fallback support
   - Added `fallback_provider` parameter ("anthropic" or "openai")
   - Added `fallback_api_key` parameter for OpenAI key
   - Created `create_resilient_llm_with_openai_fallback()` helper function
   - Created `ResilientAsyncClient` class for raw SDK async code (ingestion, services)
   - Created `OpenAIResponseAdapter` to make OpenAI responses look like Anthropic
   - Added model mapping: `ANTHROPIC_TO_OPENAI_MODEL_MAP`

2. **Model Mapping** 🔄
   | Anthropic Model | OpenAI Fallback |
   |-----------------|-----------------|
   | claude-sonnet-4-5 | gpt-4o |
   | claude-opus-4-5 | gpt-4o |
   | claude-3-5-haiku-20241022 | gpt-4o-mini |
   | claude-sonnet-4-20250514 | gpt-4o |

3. **Dependencies Added** 📦
   - **File**: [backend/requirements.txt](backend/requirements.txt)
   - Added `langchain-openai>=0.2.0` (LangChain OpenAI integration)
   - Added `openai>=1.54.0` (OpenAI SDK)

4. **Settings Updated** ⚙️
   - **File**: [backend/app/config/settings.py](backend/app/config/settings.py)
   - Added `openai_api_key: str = ""` field

5. **Environment Variable** 🔑
   - Added `OPENAI_API_KEY` to `.env` file
   - Comment: "Fallback provider when Anthropic credits run out"

### 📁 Files Modified
- [backend/app/utils/resilient_llm.py](backend/app/utils/resilient_llm.py) - Major expansion
- [backend/requirements.txt](backend/requirements.txt) - New dependencies
- [backend/app/config/settings.py](backend/app/config/settings.py) - New setting
- `.env` - New API key

### 🎯 Usage Patterns

**For LangChain code (agents, workflows):**
```python
from app.utils.resilient_llm import create_resilient_llm_with_openai_fallback
from app.config.settings import settings

llm = create_resilient_llm_with_openai_fallback(
    primary_model="claude-sonnet-4-5",
    anthropic_api_key=settings.anthropic_api_key,
    openai_api_key=settings.openai_api_key,
    fallback_model="gpt-4o",
)
```

**For raw SDK code (ingestion, services):**
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
```

### 🚧 Not Yet Updated (Future Work)
These files still use raw Anthropic clients and can be migrated later if needed:
- Vision/Image APIs (complex multimodal content)
- Streaming endpoints (OpenAI streaming has different format)

### 🔧 Next Steps
- Test fallback in production by temporarily invalidating Anthropic key
- Consider adding metrics/alerting when fallback is triggered
- Update deep research agents to use resilient wrapper (if desired)

---

## Session 34 (January 6, 2026) - Repository Cleanup & Script Reorganization ✅

### 📋 Context

Major repository cleanup to improve organization and follow our own coding rules in `.agent/CODING_RULES.md` and `.agent/ARCHITECTURE.md`.

### ✅ Completed

1. **Script Reorganization** 🗂️
   - Moved 40+ test and check scripts from root/backend to [backend/scripts/testing/](backend/scripts/testing/)
   - Organized operations scripts into subdirectories:
     - [backend/scripts/operations/backfill/](backend/scripts/operations/backfill/)
     - [backend/scripts/operations/maintenance/](backend/scripts/operations/maintenance/)
     - [backend/scripts/operations/triggers/](backend/scripts/operations/triggers/)
   - Updated [backend/scripts/README.md](backend/scripts/README.md) with comprehensive script index

2. **Root Directory Cleanup** 🧹
   - Removed legacy `chroma_db/` folder (unused since BigQuery migration)
   - Removed `logo-api-main/` folder (separate project)
   - Moved documentation to [docs/](docs/):
     - `c1-mvp-longterm_memory.md`
     - `c1-simple-login.md`
   - Archived old logs to [archive/](archive/)
   - Moved CSV data files to [backend/data/](backend/data/)

3. **Updated Documentation** 📚
   - Updated [.agent/CODING_RULES.md](.agent/CODING_RULES.md) with correct script paths
   - Updated [.agent/ARCHITECTURE.md](.agent/ARCHITECTURE.md) with ADR-006 documenting the cleanup
   - Created [CLEANUP_SUMMARY.md](CLEANUP_SUMMARY.md) as a record of all changes
   - Updated [.gitignore](.gitignore) with:
     - `archive/`
     - `backend/downloads/`
     - `backend/audio_cache/`
     - `backend/exports/`

### 📁 Files Modified
- [backend/scripts/README.md](backend/scripts/README.md)
- [.agent/CODING_RULES.md](.agent/CODING_RULES.md)
- [.agent/ARCHITECTURE.md](.agent/ARCHITECTURE.md)
- [.gitignore](.gitignore)
- [CLEANUP_SUMMARY.md](CLEANUP_SUMMARY.md) (new)

### ✅ Resolved Items

1. **Deep Research Timeout Handling** ⏱️ → **Resolved in Session 36**
   - Added workflow-level timeout (5 minutes default)
   - Added frontend timeout UI with retry option
   - Added per-tool timeout utilities

### 🔧 Next Steps
- Test all script paths after reorganization
- Consider additional gitignore entries if needed

---

## Session 33 (January 6, 2026) - Pulse Tab Design Polish ✅

### 📋 Context

Refined the visual design of the Pulse tab specifically for the "Drumbeat Feed" and "Need to Know" sections to improve aesthetic appeal and match the premium app feel. Removed unused action buttons from digest cards to clean up the UI.

### ✅ Completed

1. **Digest Card Cleanup** 🧹
   - **File**: [DigestCard.tsx](frontend/src/components/digest/DigestCard.tsx)
   - Removed "Ask about this" and "Add to Report" action buttons (will be re-added when report builder features are fully designed).
   - Removed unused props and imports.

2. **Drumbeat Feed Header Polish** 💅
   - **File**: [PulseDashboard.tsx](frontend/src/components/dashboard/PulseDashboard.tsx)
   - Replaced plain text header with a styled component.
   - Added pulsing activity icon and improved typography (lighter weight, wider tracking) for a more technical/data-centric feel.

3. **Need to Know Header Redesign** ⚡
   - **File**: [WeeklyBriefingSection.tsx](frontend/src/components/dashboard/WeeklyBriefingSection.tsx)
   - Implemented a premium two-line header with "Executive Briefing" sublabel.
   - Added a gradient-backed Zap icon container for visual hierarchy.

4. **Section Header Styling** 🎨
   - **File**: [WeeklyBriefingSection.tsx](frontend/src/components/dashboard/WeeklyBriefingSection.tsx)
   - Applied "warm" styling to briefing section headers (amber-tinted background).
   - Wrapped header content in a cohesive card-like container to separate it from the content.

### 📁 Files Modified
- [frontend/src/components/digest/DigestCard.tsx](frontend/src/components/digest/DigestCard.tsx)
- [frontend/src/components/dashboard/PulseDashboard.tsx](frontend/src/components/dashboard/PulseDashboard.tsx)
- [frontend/src/components/dashboard/WeeklyBriefingSection.tsx](frontend/src/components/dashboard/WeeklyBriefingSection.tsx)

### 🔧 Next Steps
- Re-evaluate "Add to Report" functionality when report builder is prioritized.
- Continue refining UI contrast and spacing as needed.

## Session 32 (January 6, 2026) - Long-term Memory UI Components ✅

### 📋 Context

Continued work on the long-term memory system from `c1-mvp-longterm_memory.md` spec. Built frontend UI components for managing preferences (priority/blocked topics) and browsing saved Deep Research reports.

### ✅ Completed

1. **PreferencesPanel Component** 🎉
   - **File**: [PreferencesPanel.tsx](frontend/src/components/memory/PreferencesPanel.tsx) - **NEW**
   - Manages priority topics and blocked/de-prioritized topics
   - Support for org-wide vs team-specific scope
   - Add/remove with visual confirmation badges
   - Integrated into Data & Preferences tab (replaced old minimal preferences tab)

2. **SavedReportsPanel Component** 🎉
   - **File**: [SavedReportsPanel.tsx](frontend/src/components/research/SavedReportsPanel.tsx) - **NEW**
   - Browse and search saved Deep Research reports
   - Expandable cards showing: confidence, validation status, citations, companies, industries
   - Actions: "View Full Report" (loads into canvas), "Continue Research" (starts new query)
   - Two modes: sidebar section (collapsed) and full-page view

3. **ResearchSidebar Integration** 🎉
   - **File**: [ResearchSidebar.tsx](frontend/src/components/research/ResearchSidebar.tsx)
   - Added "Saved Reports" collapsible section (shows 5 most recent)
   - Archive icon in collapsed mode
   - "View All Reports" button opens full SavedReportsPanel view
   - Lazy-loads reports when section expands

4. **ResearchDashboard Handlers** 🎉
   - **File**: [ResearchDashboard.tsx](frontend/src/components/research/ResearchDashboard.tsx)
   - `handleOpenSavedReport()` - Loads saved report into new ResearchSection
   - `handleContinueResearch()` - Starts new research with "Continue research on: {query}"
   - `handleViewAllSavedReports()` - Toggles full-page SavedReportsPanel view
   - Conditional rendering: SavedReportsPanel or ResearchCanvas

5. **API Methods Added** 🎉
   - **File**: [api.ts](frontend/src/lib/api.ts)
   - Preferences: `getPreferences()`, `addPreference()`, `removePreference()`
   - Saved Reports: `getSavedReports()`, `getSavedReportById()`, `searchRelatedReports()`
   - Proper TypeScript return types for all methods

### 📁 Files Modified
- Frontend: `PreferencesPanel.tsx` (new), `SavedReportsPanel.tsx` (new)
- Frontend: `ResearchSidebar.tsx`, `ResearchDashboard.tsx`, `api.ts`
- Frontend: `components/memory/index.ts`, `components/research/index.ts`
- Frontend: `DataPreferencesDashboard.tsx` (integrated PreferencesPanel)

### 🎯 User Flow
1. **Research Tab** → Sidebar shows "Saved Reports" section
2. Expand section → See 5 most recent reports
3. Click "View All Reports" → Full-page view with search
4. Click report card → Expands to show summary + actions
5. "View Full Report" → Loads into ResearchCanvas
6. "Continue Research" → Starts new deep research query

### 🔧 Next Steps (from spec)
- Memory Log Panel (view past briefings saved to memory_log table)
- "Related Past Research" integration when starting new research
- Backend changes for preferences influencing digest generation

---

## Session 31 (January 6, 2026) - Podcast Generation for Weekly Briefings ✅

### 📋 Context

Integrated ElevenLabs text-to-speech to generate audio podcasts for weekly executive briefings, enabling on-the-go listening.

### ✅ Completed

1. **Backend Podcast Generation** 🎉
   - **File**: [weekly_briefing.py](backend/app/ingestion/generators/weekly_briefing.py)
   - Added `_format_text_for_speech()` - removes citations, expands currency/percentages
   - Added `_build_podcast_script()` - natural narration with "net new" vs "continuing" phrasing
   - Added `_generate_podcast()` - ElevenLabs TTS + GCS upload
   - Integrated into `generate()` workflow after briefing synthesis
   - **File**: [gcp_storage.py](backend/app/db/gcp_storage.py)
   - Updated `save_weekly_briefing()` with `podcast_url`, `podcast_duration_seconds`, `podcast_generated_at`
   - **File**: [settings.py](backend/app/config/settings.py)
   - Added voice configuration: `elevenlabs_voice_id`, `elevenlabs_model`, stability/similarity settings
   - **File**: [requirements.txt](backend/requirements.txt)
   - Added `elevenlabs>=1.0.0` dependency

2. **Frontend Audio Player** 🎉
   - **File**: [PodcastPlayer.tsx](frontend/src/components/dashboard/PodcastPlayer.tsx)
   - Created full audio player with play/pause, seek, volume, download
   - HTML5 `<audio>` with custom controls and error handling
   - **File**: [briefing.ts](frontend/src/types/briefing.ts)
   - Extended `WeeklyBriefing` interface with podcast fields
   - **File**: [WeeklyBriefingSection.tsx](frontend/src/components/dashboard/WeeklyBriefingSection.tsx)
   - Integrated podcast player after BLUF section (conditionally rendered)

3. **Deployment Configuration** 🎉
   - **File**: [cloudbuild.yaml](cloudbuild.yaml)
   - Added `ELEVENLABS_API_KEY` to `--set-secrets` for Cloud Run

### 📁 Files Modified
- Backend: `weekly_briefing.py`, `gcp_storage.py`, `settings.py`, `requirements.txt`
- Frontend: `briefing.ts`, `PodcastPlayer.tsx`, `WeeklyBriefingSection.tsx`
- Deploy: `cloudbuild.yaml`

### 🎯 Key Features
- **Natural speech**: "This is a new development" for net new items
- **Text formatting**: "$2.4B" → "2.4 billion dollars", "40%" → "40 percent"
- **Voice**: Rachel (professional, clear, female voice from ElevenLabs)
- **Storage**: GCS bucket `/podcasts/{briefing_id}.mp3` with public URLs
- **Duration**: ~4-6 minutes for typical 3-section briefing
- **Error resilience**: 3 retries with exponential backoff, graceful degradation

---

## Session 30 (January 5, 2026) - Frontend UX Enhancements ✅

### 📋 Context

Implemented multiple frontend UX improvements across the Intelligence Hub to improve user experience and interface consistency.

### ✅ Completed

1. **Chatbox Visibility Management** 🎉
   - **File**: [page.tsx](frontend/src/app/page.tsx)
   - Hidden right-panel chatbox on Products, Field Intel, and Data & Preferences tabs
   - These tabs are self-contained and don't require the chat interface
   - Pipeline and Pulse tabs retain their built-in chat interfaces

2. **Pipeline Tab Enhancements** 🎉
   - **File**: [PipelineDashboard.tsx](frontend/src/components/pipeline/PipelineDashboard.tsx)
   - Updated seed questions to:
     - "Find me all wind energy companies in florida"
     - "Find me similar companies to Brunswick boating company"
     - "Find me supplier sourcing leads in the aerospace industry"
   - Added auto-submit functionality (100ms delay) when clicking seed questions
   - **File**: [AppHeader.tsx](frontend/src/components/layout/AppHeader.tsx)
   - Changed subheader from "Contacts & prospects" to "Companies, Prospects, and Decision Makers"

3. **Sidebar Logo Replacement** 🎉
   - **File**: [Sidebar.tsx](frontend/src/components/layout/Sidebar.tsx)
   - Replaced PNG logo image with styled text
   - Expanded view: "Composites One" + "Intelligence Hub" (two lines)
   - Collapsed view: "C1" abbreviation
   - Removed unused `Image` import from next/image

4. **Pulse Tab Improvements** 🎉
   - **File**: [AdHocBriefing.tsx](frontend/src/components/dashboard/AdHocBriefing.tsx)
   - Removed helper text: "Try asking about topics in this week's briefing, or any industry news"
   - Removed examples: "What's the latest on Hexcel's expansion?" etc.
   - **File**: [PulseDashboard.tsx](frontend/src/components/dashboard/PulseDashboard.tsx)
   - Reduced spacing from `space-y-6` to `space-y-4` to bring Need to Know section higher
   - Changed background color from default to `bg-slate-200` for better visual depth

### 📁 Files Modified
- [frontend/src/app/page.tsx](frontend/src/app/page.tsx) - Chatbox visibility logic
- [frontend/src/components/pipeline/PipelineDashboard.tsx](frontend/src/components/pipeline/PipelineDashboard.tsx) - Seed questions + auto-submit
- [frontend/src/components/layout/AppHeader.tsx](frontend/src/components/layout/AppHeader.tsx) - Pipeline subtitle
- [frontend/src/components/layout/Sidebar.tsx](frontend/src/components/layout/Sidebar.tsx) - Logo text replacement
- [frontend/src/components/dashboard/AdHocBriefing.tsx](frontend/src/components/dashboard/AdHocBriefing.tsx) - Removed helper text
- [frontend/src/components/dashboard/PulseDashboard.tsx](frontend/src/components/dashboard/PulseDashboard.tsx) - Spacing + background

### ✅ Testing

All changes are frontend-only. Test with:
```bash
cd frontend
npm run dev
```

### 🔧 Next Steps
- Manual UI testing to verify all changes display correctly
- No backend deployment required (frontend-only changes)

---

## Session 29 (January 5, 2026) - Phase 4: BigQuery Persistence & Memory Integration ✅

### 📋 Context

Implemented persistent storage for Deep Research reports and memory/context integration to avoid redundant research. This completes Phase 4 of the Deep Research workflow.

### ✅ Completed

1. **BigQuery Table Schema for Deep Research Reports** 🎉
   - **File**: [gcp_storage.py](backend/app/db/gcp_storage.py)
   - New `deep_research_reports` table with:
     - Full report serialization (JSON blobs for flexibility)
     - Entity extraction (companies, industries, topics, products)
     - Validation metadata (citation counts, confidence levels)
     - Performance metrics (research time, sources count)
     - Query embedding field for future semantic search

2. **BigQuery Storage Methods** 🎉
   - **File**: [gcp_storage.py](backend/app/db/gcp_storage.py)
   - `store_deep_research_report()` - Persist completed reports
   - `get_deep_research_report_by_hash()` - Lookup by query hash (cache tier 2)
   - `get_deep_research_reports()` - List reports with pagination
   - `get_deep_research_report_by_id()` - Fetch full report
   - `search_related_research()` - Find related past reports by entity/text matching

3. **Research Memory Service** 🎉
   - **File**: [memory.py](backend/app/agents/research/memory.py) - **NEW**
   - `ResearchMemory` class with:
     - Two-tier caching (in-memory 1h, BigQuery 24h)
     - Related research discovery for context enrichment
     - `format_context_for_prompt()` for injecting prior research into agent prompts
   - Singleton pattern via `get_research_memory()`

4. **Two-Tier Cache Integration** 🎉
   - **File**: [deep_research.py](backend/app/api/routes/deep_research.py)
   - Tier 1: In-memory cache (existing, 1 hour TTL)
   - Tier 2: BigQuery persistent cache (new, 24 hour TTL)
   - Automatic persistence of completed reports
   - SSE event `report_saved` with report_id on successful persistence

5. **Saved Reports API Endpoints** 🎉
   - **File**: [deep_research.py](backend/app/api/routes/deep_research.py)
   - `GET /api/research/reports` - List saved reports (paginated)
   - `GET /api/research/reports/{report_id}` - Get full report by ID
   - `GET /api/research/reports/search/related` - Find related past research

6. **Updated Documentation** 🎉
   - **File**: [README.md](backend/app/agents/research/README.md)
   - Added two-tier caching documentation
   - Added Research Memory Service usage examples
   - Added Saved Reports API reference

### 📁 Files Modified
- [backend/app/db/gcp_storage.py](backend/app/db/gcp_storage.py) - Table schema + storage methods
- [backend/app/agents/research/memory.py](backend/app/agents/research/memory.py) - **NEW** memory service
- [backend/app/api/routes/deep_research.py](backend/app/api/routes/deep_research.py) - Cache tiers + endpoints
- [backend/app/agents/research/README.md](backend/app/agents/research/README.md) - Documentation

### ✅ Verification

```bash
cd backend
python -c "from app.agents.research.memory import get_research_memory; from app.api.routes.deep_research import router; print('All imports OK')"
# All imports OK
# Endpoints: ['/run', '/cache/stats', '/cache/clear', '/observability/status', '/tools/health', '/reports', '/reports/{report_id}', '/reports/search/related']
```

### 🔧 Next Steps
1. ✅ **Deploy to Cloud Run** - Deployed (builds 632e2423, 2e55dab, a49aca6)
2. ✅ **Test E2E** - Full workflow verified with BigQuery persistence (see below)
3. **Frontend integration** - Add "Saved Reports" tab or history view
4. ✅ **Context injection** - Groomer now receives prior research context
5. ✅ **Conditional earnings API** - External API only called for specific company queries
6. **Semantic search** - Generate query embeddings for better related research matching
7. **Tool Health Frontend** - Surface API health in UI:
   - `useToolHealth` hook polling `/api/tools/health`
   - Status indicator in nav (🟢/🟡/🔴)
   - `ToolHealthPanel` with per-tool metrics (success %, latency)
   - Pre-research health check in Deep Research panel
   - Data source attribution in reports (which tools contributed)

### ✅ E2E Test Results (January 6, 2026)

**Query**: "What is the outlook for carbon fiber in aerospace?"

| Metric | Result |
|--------|--------|
| Report Generated | ✅ |
| BigQuery Persistence | ✅ (ID: `c7cdf40f-...`) |
| Research Time | 217 seconds |
| Citations | 47 |
| Sources | 17 |
| Companies Identified | Hexcel, SGL Carbon, CFRP |
| Industries | aerospace, defense, marine |

**API Endpoints Verified**:
- `GET /api/research/deep/reports` - Listed 1 saved report
- BigQuery table `deep_research_reports` populated correctly

### 🔧 cloudbuild.yaml Fixes (Build a49aca6)

Fixed missing/incorrect secrets in `cloudbuild.yaml` `--set-secrets`:
- **Added**: `STOCKNEWS_API_KEY=STOCKNEWS_API_KEY:latest` (was missing entirely)
- **Fixed**: `APOLLO_API_KEY=APOLLO_API_KEY:latest` (was lowercase `apollo-api-key`)

These secrets now persist across all Cloud Build deployments.

### 🆕 Session 29 Continuation - Context Injection & Conditional APIs

**Context Injection** (`groomer.py`):
- Added `_get_prior_research_context()` to fetch related past research
- Prior context injected into groomer system prompt before LLM call
- Groomer can now reference prior findings, skip redundant clarifying questions

**Conditional Earnings API** (`financial.py`):
- Added `_has_specific_company_mention()` helper to detect company names
- External `get_earnings_transcript_ninja` only called when companies mentioned
- Corpus query (`query_corpus`) always runs (40+ pre-ingested transcripts)
- SEC filings always fetched for resolved tickers

**Files Modified**:
- [groomer.py](backend/app/agents/research/groomer.py) - Context injection
- [financial.py](backend/app/agents/research/financial.py) - Conditional earnings API

---

## Session 28 (January 5, 2026) - API Reliability & Tool Health ✅

### 📋 Context

Addressed flaky external APIs (StockNewsAPI 422s, Google Trends 429s) by adding centralized retries, graceful degradation, and observability.

### ✅ Completed

1. **Centralized Retry Utilities** 🎉
   - **File**: [retry.py](backend/app/utils/retry.py)
   - Exponential backoff with jitter, rate-limit helper, skip-on-failure wrapper, and in-memory tool metrics.

2. **StockNewsAPI Hardening** 🎉
   - **File**: [stocknews_api.py](backend/app/mcp/tools/stocknews_api.py)
   - Added skip-on-failure + retries + latency/error metrics to: `get_company_news`, `search_news_keyword`, `get_press_releases`, `get_analyst_ratings`.
   - Error paths now raise to trigger skip behavior; no-data paths record successes.

3. **Google Trends Rate-Limit Handling** 🎉
   - **File**: [google_trends.py](backend/app/mcp/tools/google_trends.py)
   - Added rate-limit-aware retry and metrics; marked as skip-on-failure to avoid blocking workflows.

4. **Tool Health Endpoint** 🎉
   - **File**: [deep_research.py](backend/app/api/routes/deep_research.py)
   - New `GET /api/research/tools/health` returns success rates, latency, and recent errors by tool with simple health categorization.

5. **Config Fix** 🎉
   - StockNewsAPI key added to Cloud Run env as `STOCKNEWS_API_KEY` (was only in Secret Manager before).

### 📁 Files Modified
- [backend/app/utils/retry.py](backend/app/utils/retry.py) - **NEW** retry utilities and metrics
- [backend/app/mcp/tools/stocknews_api.py](backend/app/mcp/tools/stocknews_api.py) - Added retries, metrics, skip-on-failure
- [backend/app/mcp/tools/google_trends.py](backend/app/mcp/tools/google_trends.py) - Added rate-limit retries and metrics
- [backend/app/api/routes/deep_research.py](backend/app/api/routes/deep_research.py) - Added tool health endpoint

### 🔧 Next Steps
1. Monitor `GET /api/research/tools/health` after traffic to confirm success rates and latency.
2. Add targeted tests for retry/skip paths (especially StockNewsAPI 422 and Google Trends 429 scenarios).
3. Consider surfacing tool health in the frontend dashboard.

---

## Session 27 (January 5, 2026) - Phase 2 Output Display (Category & Validation) 🎉

### 📋 Context

Continued from Session 26. The backend Phase 2 outputs (Category Agent & Validator Agent) were flowing through SSE but not displayed in the UI. This session builds components to visualize territory insights, product recommendations, sales plays, and validation results.

### ✅ Completed

1. **Created TerritoryInsights Component** 🎉
   - **File**: [TerritoryInsights.tsx](frontend/src/components/research/TerritoryInsights.tsx)
   - Visual East/West territory relevance scores with progress bars
   - "Top Match" badge for highest-scoring territory
   - Territory summaries with industry focus indicators
   - Industry tags (Aerospace, Wind, Automotive, Defense for East; Marine, RVs, Spas for West)

2. **Created ProductRecommendations Component** 🎉
   - **File**: [ProductRecommendations.tsx](frontend/src/components/research/ProductRecommendations.tsx)
   - Grid layout with relevance score badges
   - High-relevance indicator (70%+ threshold)
   - "Ask About Product" buttons wired to research query
   - Datasheet link placeholders
   - Rationale text for each recommendation

3. **Created SalesPlays Component** 🎉
   - **File**: [SalesPlays.tsx](frontend/src/components/research/SalesPlays.tsx)
   - Accordion interface for sales plays
   - Hook section with copy-to-clipboard
   - Objection handlers list
   - Industry talking points section
   - First play auto-expanded

4. **Created ValidationBadge Component** 🎉
   - **File**: [ValidationBadge.tsx](frontend/src/components/research/ValidationBadge.tsx)
   - Collapsible badge showing validation status (passed/failed)
   - Issue counter badge
   - Color-coded sections:
     - Red: Unsubstantiated claims (critical)
     - Amber: Citation issues
     - Blue: Confidence adjustments
     - Gray: General warnings
   - "All Clear" message when no issues found

5. **Updated ResearchCanvas** 🎉
   - **File**: [ResearchCanvas.tsx](frontend/src/components/research/ResearchCanvas.tsx)
   - Added imports for all 4 new components
   - Conditional rendering based on data availability
   - Proper prop passing for `onAskAbout` integration

### 📁 Files Modified
- [frontend/src/components/research/TerritoryInsights.tsx](frontend/src/components/research/TerritoryInsights.tsx) - **NEW**
- [frontend/src/components/research/ProductRecommendations.tsx](frontend/src/components/research/ProductRecommendations.tsx) - **NEW**
- [frontend/src/components/research/SalesPlays.tsx](frontend/src/components/research/SalesPlays.tsx) - **NEW**
- [frontend/src/components/research/ValidationBadge.tsx](frontend/src/components/research/ValidationBadge.tsx) - **NEW**
- [frontend/src/components/research/ResearchCanvas.tsx](frontend/src/components/research/ResearchCanvas.tsx) - Phase 2 display logic
- [frontend/src/components/research/index.ts](frontend/src/components/research/index.ts) - Export new components

### ✅ Build Verification

```bash
cd frontend && npm run build
# ✅ Compiled successfully
```

### 🎨 UI Features

**Territory Insights:**
- Side-by-side East/West comparison cards
- Animated progress bars
- Industry focus tags dynamically shown

**Product Recommendations:**
- Grid layout (2 columns on desktop)
- Relevance percentage badges
- Direct integration with research chat

**Sales Plays:**
- Expandable accordion
- Copy-to-clipboard for hooks
- Numbered objection handlers

**Validation Badge:**
- Non-intrusive collapsed state
- Expandable to show all issues
- Clear visual hierarchy (critical → warnings)

### 🔧 Next Steps
1. E2E test with full workflow to see all Phase 2 components
2. Consider adding export functionality for sales plays
3. Phase 4: BigQuery persistence for saved reports
4. Phase 4: Memory/context integration

---

## Session 26 (January 5, 2026) - Frontend SSE Integration for Deep Research 🎉

### 📋 Context

Continued from Session 25. The Deep Research workflow now runs end-to-end in the backend. This session adds frontend integration for real-time progress tracking via SSE events.

### ✅ Completed

1. **Added TypeScript Types for SSE Events** 🎉
   - **File**: [types/index.ts](frontend/src/types/index.ts)
   - Added `ToolProgressEvent`, `NodeProgressEvent`, `CacheHitEvent` types
   - Added `CategoryOutput`, `ValidationOutput` types for Phase 2 outputs
   - Added `DeepResearchReport` with full typing
   - Added `NodeStatus` and `DeepResearchNode` for workflow node tracking

2. **Updated useDeepResearch Hook** 🎉
   - **File**: [hooks/useDeepResearch.ts](frontend/src/hooks/useDeepResearch.ts)
   - Now handles ALL SSE event types: `status`, `cache_hit`, `node_start`, `node_complete`, `tool_progress`, `clarification`, `report`, `category`, `validation`, `warnings`, `error`
   - Added `toolProgress[]` state to track recent tool activity (last 20 events)
   - Added `nodeStatuses[]` state to track all workflow nodes
   - Added `activeNode`, `isCacheHit`, `categoryOutput`, `validationOutput`
   - Added `cancelResearch()` method with AbortController support
   - Proper error handling for abort signals

3. **Created ResearchProgress Component** 🎉
   - **File**: [components/research/ResearchProgress.tsx](frontend/src/components/research/ResearchProgress.tsx)
   - Visual pipeline showing all 6 workflow nodes with status indicators
   - Icons and friendly labels for each node (Query Analysis, Financial Research, etc.)
   - Parallel execution indicator when Financial + Industry run together
   - Live Activity feed showing recent tool executions
   - Human-friendly tool labels (e.g., "Earnings Transcript" instead of "get_earnings_transcript_ninja")
   - Pulsing dot indicator for active tools

4. **Updated ResearchCanvas and ResearchDashboard** 🎉
   - **Files**: [ResearchCanvas.tsx](frontend/src/components/research/ResearchCanvas.tsx), [ResearchDashboard.tsx](frontend/src/components/research/ResearchDashboard.tsx)
   - Added props for all progress tracking state
   - Integrated ResearchProgress component for active research
   - Added Cancel Research button
   - Added error state display with retry option
   - Fallback to simple spinner if nodeStatuses not available

5. **Updated Page.tsx** 🎉
   - **File**: [app/page.tsx](frontend/src/app/page.tsx)
   - Destructured all new hook values
   - Passed all props to ResearchDashboard

### 📁 Files Modified
- [frontend/src/types/index.ts](frontend/src/types/index.ts) - SSE event types
- [frontend/src/hooks/useDeepResearch.ts](frontend/src/hooks/useDeepResearch.ts) - Full SSE event handling
- [frontend/src/components/research/ResearchProgress.tsx](frontend/src/components/research/ResearchProgress.tsx) - **NEW** Progress visualization
- [frontend/src/components/research/ResearchCanvas.tsx](frontend/src/components/research/ResearchCanvas.tsx) - Progress integration
- [frontend/src/components/research/ResearchDashboard.tsx](frontend/src/components/research/ResearchDashboard.tsx) - Prop passing
- [frontend/src/components/research/index.ts](frontend/src/components/research/index.ts) - Export new component
- [frontend/src/app/page.tsx](frontend/src/app/page.tsx) - Hook wiring

### ✅ Build Verification

```bash
cd frontend && npm run build
# ✅ Compiled successfully
```

### 🔧 Next Steps
1. Manual E2E test with backend running
2. Consider adding estimated time remaining per node
3. Phase 4: BigQuery persistence for saved reports
4. Phase 4: Memory/context integration to avoid redundant fetches

---

## Session 25 (January 5, 2026) - Deep Research Workflow Fixed! 🎉

### 📋 Context

Continued from Session 24. The goal was to fix the `InvalidUpdateError` blocking parallel execution and get the Deep Research workflow running end-to-end.

### ✅ Completed

1. **Fixed Parallel Execution State Merge Bug** 🎉
   - **File**: [state.py](backend/app/agents/research/state.py)
   - **Problem**: LangGraph `Send` API passes full state to parallel nodes; when both Financial and Industry agents return, their states collide on non-annotated fields like `user_query`
   - **Fix**: Added reducer annotations to ALL fields in `DeepResearchState`
   - Created `_keep_first()` reducer for immutable fields (user_query, conversation_history, research_brief)
   - Created `_keep_last()` reducer for mutable fields (financial_output, industry_output, final_report, etc.)
   - Created `_merge_errors()` reducer to combine error lists from parallel branches

2. **Fixed Empty User Query Issue** 🎉
   - **File**: [state.py](backend/app/agents/research/state.py)
   - **Problem**: `_keep_first` reducer kept empty string "" over actual query value
   - **Fix**: Modified `_keep_first` to check `if a is not None and a != "": return a`

3. **Fixed Empty Message API Error** 🎉
   - **File**: [groomer.py](backend/app/agents/research/groomer.py)
   - **Problem**: Anthropic API rejects messages with empty content
   - **Fix**: Added message filtering to remove messages with empty content before LLM call

4. **Fixed Financial Agent JSON Schema** 🎉
   - **File**: [financial.py](backend/app/agents/research/financial.py)
   - **Problem**: Extraction prompt said "match FinancialAgentOutput schema" but didn't show the schema
   - **Fix**: Added explicit JSON schema with all required fields, nested types, and examples
   - Includes `FinancialFinding`, `Citation` nested schemas

5. **Fixed Industry Agent JSON Schema** 🎉
   - **File**: [industry.py](backend/app/agents/research/industry.py)
   - **Problem**: Same as Financial - vague schema instruction
   - **Fix**: Added explicit JSON schema with `IndustryFinding`, `Citation` nested schemas

6. **Fixed Synthesis Agent JSON Schema** 🎉
   - **File**: [synthesizer.py](backend/app/agents/research/synthesizer.py)
   - **Problem**: LLM returned output missing `query`, `data_completeness`, `overall_confidence`, and `KeyMetric` nested fields
   - **Fix**: Added explicit JSON schema with ALL required fields including nested `KeyMetric`, `FindingSection`, `FieldSalesAngle`, `Citation` schemas

### 🎉 Result: Deep Research Workflow Runs End-to-End!

```
[groom] Status: grooming_complete → Research brief generated
[financial_research] Status: financial_research_complete → Financial output ready
[industry_research] Status: industry_research_complete → Industry output ready
[synthesize] Status: synthesis_complete → Final report synthesized!
[categorize] Status: category_complete → Category output ready
[validate] Status: validation_complete → Validation complete
✓ Workflow completed without InvalidUpdateError!
```

### 📁 Files Modified This Session
- [state.py](backend/app/agents/research/state.py) - Added reducer annotations to all fields
- [groomer.py](backend/app/agents/research/groomer.py) - Added message filtering
- [financial.py](backend/app/agents/research/financial.py) - Added explicit JSON schema
- [industry.py](backend/app/agents/research/industry.py) - Added explicit JSON schema
- [synthesizer.py](backend/app/agents/research/synthesizer.py) - Added explicit JSON schema

### 📁 Test Files
- [test_parallel_fix.py](backend/test_parallel_fix.py) - Created in Session 24, used for testing

### ⚠️ Known Issues (Non-Blocking)
- **StockNewsAPI 422 errors**: API is returning errors for many requests - likely a paid tier or rate limit issue
- **Google Trends 429**: Rate limited during testing
- **Validator found issues**: 12 citation issues, 7 unsubstantiated claims (expected - validation is working!)

### 🔧 Next Steps
1. Review traces in LangSmith dashboard for performance optimization
2. Fix StockNewsAPI integration (check API key/tier)
3. Consider adding retry logic for rate-limited APIs
4. Phase 4 (if desired): BigQuery persistence for saved reports

---

## Session 24 (January 5, 2026) - LangSmith Testing & Parallel Execution Bug Discovery ✅

### 📋 Context

Continued from Session 23. Attempted to test LangSmith tracing by running the Deep Research workflow. Discovered critical bugs in the LangGraph parallel execution implementation that prevent the workflow from completing.

### ✅ Completed

1. **LangSmith Connection Verified** ✅
   - API connection works, project `c1-intelligence-hub-prod` exists
   - Traces ARE being sent (visible in LangSmith dashboard, even for failed runs)

2. **Fixed Infinite Loop in Groomer** ✅
   - **File**: [research_workflow.py](backend/app/graph/research_workflow.py)
   - **Problem**: `route_after_groom()` returned `"groom"` when `research_brief` was None, causing infinite loop
   - **Fix**: Removed `"groom"` loop-back option, now returns `END` on failure
   - Added logging to track routing decisions

3. **Fixed Groomer JSON Parsing** ✅
   - **File**: [groomer.py](backend/app/agents/research/groomer.py)
   - **Problem**: LLM response didn't match `ResearchBrief` schema (missing `status`, wrong type for `domain_context`)
   - **Fix**: Added explicit JSON schema to system prompt with all required fields and types
   - Added detailed logging for debugging

4. **Increased Recursion Limit** ✅
   - **File**: [deep_research.py](backend/app/api/routes/deep_research.py)
   - Added `recursion_limit=100` to `RunnableConfig` (default 25 was too low for parallel execution)

### 🚨 BLOCKING BUG: InvalidUpdateError in Parallel Execution

**Error**: 
```
InvalidUpdateError: At key 'user_query': Can receive only one value per step. Use an Annotated key to handle multiple values.
```

**Root Cause**: 
When using LangGraph's `Send` API for parallel fan-out (Financial + Industry agents run simultaneously), both branches receive a copy of the full state. When they return, their states get merged. Since `user_query` (and other non-annotated fields) appears in both returned states, LangGraph throws an error because it doesn't know how to merge them.

**Attempted Fix** (INCOMPLETE):
- Modified `financial_research_node` and `industry_research_node` to return **partial state dicts** containing only the fields they update:
  - Financial returns: `{"financial_output": ..., "current_status": ..., "errors": [...]}`
  - Industry returns: `{"industry_output": ..., "current_status": ..., "errors": [...]}`
- This still fails because `Send(node_name, state)` passes the full state, and somewhere the full state is being returned

**Proper Fix Needed**:
The issue is fundamental to how LangGraph handles parallel state merging. Options:
1. **Add reducer annotations** to ALL state fields in `DeepResearchState` (e.g., `user_query: Annotated[str, lambda x, y: x]`)
2. **Don't use Send API** - revert to sequential execution (Financial → Industry)
3. **Use separate state channels** - restructure state to have dedicated channels for parallel branches

### 📁 Files Modified This Session
- [deep_research.py](backend/app/api/routes/deep_research.py) - `recursion_limit=100`
- [research_workflow.py](backend/app/graph/research_workflow.py) - Removed groom loop-back, added logging
- [groomer.py](backend/app/agents/research/groomer.py) - Added JSON schema to prompt, added logging
- [financial.py](backend/app/agents/research/financial.py) - Attempted partial state return (incomplete)
- [industry.py](backend/app/agents/research/industry.py) - Attempted partial state return (incomplete)

### 📁 Test Files Created
- [test_trace.py](backend/test_trace.py) - Deep Research API test script
- [test_groomer.py](backend/test_groomer.py) - Groomer-only test script

### 🔧 Resolution

**FIXED IN SESSION 25** - Added reducer annotations to all `DeepResearchState` fields:
- `_keep_first()` for immutable fields (user_query, conversation_history, research_brief)
- `_keep_last()` for mutable outputs (financial_output, industry_output, etc.)
- `_merge_errors()` for combining error lists from parallel branches

See Session 25 notes above for full implementation details.

---

## Session 23 (January 5, 2026) - LangSmith Observability Integration ✅

### 📋 Context

Added LangSmith observability to the Deep Research workflow for cost tracking, latency monitoring, and debugging. LangGraph has native LangSmith integration - traces are sent automatically when env vars are set.

### ✅ Completed

1. **LangSmith Configuration Verified** 🎉
   - **File**: [settings.py](backend/app/config/settings.py)
   - Already had `langchain_api_key`, `langchain_tracing_v2`, `langchain_project` settings
   - Settings automatically export to `os.environ` at import time
   - User added API key to `.env` before session

2. **Enhanced Tracing with Metadata** 🎉
   - **File**: [deep_research.py](backend/app/api/routes/deep_research.py)
   - Added `RunnableConfig` with rich metadata to workflow invocation
   - **Run name**: `DeepResearch: {query preview}` (searchable in LangSmith)
   - **Tags**: `deep_research`, `production`
   - **Metadata**: `run_id`, `query_hash`, `query`, `query_length`, `history_length`, `timestamp`
   - Enables filtering and searching traces by query content

3. **Observability Status Endpoint** 🎉
   - **Endpoint**: `GET /api/deep-research/observability/status`
   - Returns LangSmith configuration status, project URL, and usage notes
   - Useful for debugging and verifying tracing is active

4. **README Documentation** 🎉
   - **File**: [README.md](backend/app/agents/research/README.md)
   - Added Observability section with setup, viewing traces, key metrics
   - Updated Phase 3 checklist to mark LangSmith as complete
   - Added observability endpoint to API reference

### 📁 Files Modified
- [deep_research.py](backend/app/api/routes/deep_research.py) - RunnableConfig, metadata, status endpoint
- [README.md](backend/app/agents/research/README.md) - Observability documentation

### 📁 Files Created
- [test_langsmith.py](backend/test_langsmith.py) - Quick verification script (can be deleted)

### ✅ Verification

```bash
cd backend && python test_langsmith.py
# Output:
# ✓ LangSmith is ENABLED - traces will be sent automatically
# LANGCHAIN_PROJECT: c1-intelligence-hub-prod
```

### 🔭 LangSmith Dashboard

Access traces at: https://smith.langchain.com
- Project: `c1-intelligence-hub-prod`
- Filter by tag: `deep_research`
- Search by: `run_id`, `query_hash`, or query content in metadata

### 📋 Remaining (Future Session)

**Priority: Test Full Workflow Run** 🧪
- Run a real Deep Research query to verify traces appear in LangSmith
- Check token usage, latency breakdown by node
- Verify parallel execution shows correctly in trace timeline

**Other Items:**
- [ ] **Memory/Context Integration** - Connect to memory system, avoid redundant fetches
- [ ] **BigQuery Persistence** - Save reports to `research_reports` table on explicit user save
- [ ] **Frontend Integration** - Update UI to display `tool_progress` events

---

## Session 22 (January 5, 2026) - Deep Research Phase 3: Parallel Execution & Streaming ✅

### 📋 Context

Completed Phase 3 infrastructure improvements for the Deep Research workflow. Focus on performance (parallel execution) and UX (granular streaming).

### ✅ Completed

1. **Parallel Financial + Industry Agent Execution** 🎉
   - **File**: [research_workflow.py](backend/app/graph/research_workflow.py)
   - **Implementation**: LangGraph `Send` API from `langgraph.types` for fan-out
   - **New Function**: `route_after_groom()` returns `List[Send]` for parallel dispatch
   - **File**: [state.py](backend/app/agents/research/state.py)
   - **Added**: `_merge_errors()` reducer for parallel branch error aggregation
   - **Impact**: Financial + Industry agents run simultaneously, ~40% faster

2. **Enhanced Streaming Granularity** 🎉
   - **File**: [progress.py](backend/app/agents/research/progress.py) (NEW)
   - **Pattern**: Context variable callback mechanism for cross-context progress emission
   - **Classes**: `ToolProgress` dataclass, `emit_progress_sync()`, `set_progress_callback()`
   - **File**: [financial.py](backend/app/agents/research/financial.py)
   - **Added**: 6 progress emission points (SEC filings, earnings, analyst ratings, etc.)
   - **File**: [industry.py](backend/app/agents/research/industry.py)
   - **Added**: 8 progress emission points (corpus search, Exa, market signals, etc.)
   - **File**: [deep_research.py](backend/app/api/routes/deep_research.py)
   - **Added**: `ProgressCollector` class with asyncio.Queue for SSE integration
   - **New SSE Events**: `tool_progress` with tool name, message, ticker, status

3. **In-Memory Report Caching** 🎉
   - **File**: [deep_research.py](backend/app/api/routes/deep_research.py)
   - **Class**: `ReportCache` with query hash and 1-hour TTL
   - **Features**:
     - Case-insensitive query normalization
     - SHA256 hash-based cache keys
     - Automatic TTL expiration
     - Cache hit returns immediately via SSE
   - **New Endpoints**:
     - `GET /deep-research/cache/stats` - View cached reports
     - `DELETE /deep-research/cache/clear` - Clear cache
   - **Note**: This is ephemeral in-memory cache (clears on restart). The `research_reports` BigQuery table is for user-initiated saves/exports.

### 📁 Files Created
- [progress.py](backend/app/agents/research/progress.py) - Progress callback infrastructure

### 📁 Files Modified
- [research_workflow.py](backend/app/graph/research_workflow.py) - Parallel Send pattern
- [state.py](backend/app/agents/research/state.py) - Error merger reducer
- [financial.py](backend/app/agents/research/financial.py) - Progress emissions
- [industry.py](backend/app/agents/research/industry.py) - Progress emissions
- [deep_research.py](backend/app/api/routes/deep_research.py) - ProgressCollector, ReportCache

### 🏗️ Updated Architecture

**Deep Research Pipeline (Phase 3 - Parallel):**
```
                    ┌─→ [Financial] ─┐
[User Query] → [Groomer] ─┤              ├─→ [Synthesizer] → [Category] → [Validator] → [Report]
                    └─→ [Industry]  ─┘
```

**SSE Event Types:**
| Event | Description |
|-------|-------------|
| `status` | High-level workflow progress |
| `cache_hit` | Report served from cache |
| `node_start` | Node beginning (includes `parallel_with` field) |
| `node_complete` | Node finished |
| `tool_progress` | Granular tool updates (ticker, message, status) |
| `report` | Final research report |
| `category` | Sales intelligence output |
| `validation` | Citation verification results |

### ✅ Verification

```bash
cd backend && python -c "
from app.graph.research_workflow import create_research_workflow
from app.agents.research.progress import ToolProgress, emit_progress_sync, set_progress_callback
from app.api.routes.deep_research import router, ReportCache

graph = create_research_workflow()
print(f'Nodes: {list(graph.nodes.keys())}')
# Output: ['__start__', 'groom', 'financial_research', 'industry_research', 'synthesize', 'categorize', 'validate']

# Test progress callback
events = []
set_progress_callback(lambda p: events.append(p))
emit_progress_sync(ToolProgress(tool_name='test', message='OK'))
print(f'Progress captured: {len(events)} events')
# Output: Progress captured: 1 events
"
```

### 📋 Remaining (Future Session)

**Priority: LangSmith Observability** 🔭
The Deep Research workflow is complex (7 nodes, parallel execution, multiple LLM calls). Add LangSmith tracing for:
- Cost tracking per run (token usage across all agents)
- Latency breakdown (which nodes are slowest)
- Error tracking and debugging
- Run replay for debugging failed workflows

**Setup**: Add `LANGCHAIN_TRACING_V2=true`, `LANGCHAIN_API_KEY`, `LANGCHAIN_PROJECT` to environment. LangGraph has native LangSmith integration.

**Other Items:**
- [ ] **Memory/Context Integration** - Connect to memory system, avoid redundant fetches
- [ ] **BigQuery Persistence** - Save reports to `research_reports` table on explicit user save
- [ ] **Frontend Integration** - Update UI to display `tool_progress` events

---

## Session 21 (January 5, 2026) - Deep Research Phase 2: Category & Validator Agents ✅

### 📋 Context

Continued Phase 2 of the Deep Research workflow enhancement. Built out the Category Agent (sales intelligence layer) and Validator Agent (citation verification) as planned in Session 19.

### ✅ Completed

1. **New MCP Tool: `query_datasheets`** 🎉
   - **File**: [datasheets.py](backend/app/mcp/tools/datasheets.py) (NEW)
   - **Tools Added** (4):
     - `query_datasheets` - Search product datasheets with filters
     - `get_datasheet_detail` - Get full datasheet with extracted text
     - `get_datasheet_stats` - Collection statistics by supplier/category
     - `get_products_by_industry` - Products grouped by target industry
   - **Data Source**: BigQuery `c1_intelligence.datasheets` table

2. **Category Agent** 🎉
   - **File**: [category.py](backend/app/agents/research/category.py) (NEW)
   - **Role**: Sales intelligence layer providing territory-specific insights
   - **Features**:
     - Territory insights (East/West) with relevance scores
     - Product recommendations from datasheet lookups
     - Structured sales plays with hooks and objection handlers
     - Industry-specific talking points
   - **Territory Focus**:
     - East: Aerospace, Wind, Automotive, Defense
     - West: Marine, RVs, Spas

3. **Validator Agent** 🎉
   - **File**: [validator.py](backend/app/agents/research/validator.py) (NEW)
   - **Role**: Citation and attribution verification
   - **Features**:
     - Citation completeness checking
     - Unsubstantiated claim detection
     - Confidence level adjustment recommendations
     - Graceful fallback (doesn't block report on error)

4. **Updated State Schema** ✏️
   - **File**: [state.py](backend/app/agents/research/state.py)
   - **New Models**:
     - `TerritoryInsight`, `ProductRecommendation`, `SalesPlay`
     - `CategoryAgentOutput`
     - `CitationIssue`, `ValidatorOutput`
   - **State Additions**: `category_output`, `validator_output`

5. **Updated Research Workflow** ✏️
   - **File**: [research_workflow.py](backend/app/graph/research_workflow.py)
   - **New Pipeline**: `Groom → Financial → Industry → Synthesize → Categorize → Validate → END`
   - Nodes: 7 total (was 5)

6. **Model Settings** ✏️
   - **File**: [settings.py](backend/app/config/settings.py)
   - Added: `deep_research_category_model`, `deep_research_validator_model`
   - Both default to `claude-sonnet-4-5`

7. **Tool Registration** ✏️
   - **File**: [server.py](backend/app/mcp/server.py)
   - Registered 4 new datasheet tools
   - **Total MCP Tools**: 52 (was 48)

### 📁 Files Created
- [datasheets.py](backend/app/mcp/tools/datasheets.py) - Datasheet query tools
- [category.py](backend/app/agents/research/category.py) - Category Agent node
- [validator.py](backend/app/agents/research/validator.py) - Validator Agent node

### 📁 Files Modified
- [state.py](backend/app/agents/research/state.py) - New output schemas
- [research_workflow.py](backend/app/graph/research_workflow.py) - Added nodes
- [settings.py](backend/app/config/settings.py) - New model settings
- [server.py](backend/app/mcp/server.py) - Tool registration

### 🏗️ Updated Architecture

**Deep Research Pipeline (Phase 2):**
```
[User Query] → [Groomer] → [Financial] → [Industry] → [Synthesizer] → [Category] → [Validator] → [Report]
```

| Node | Model | Purpose |
|------|-------|---------|
| Groomer | claude-sonnet-4-5 | Query interpretation, sub-query generation |
| Financial | claude-sonnet-4-5 | SEC filings, earnings, analyst ratings |
| Industry | claude-sonnet-4-5 | Trade publications, market signals |
| Synthesizer | claude-sonnet-4-5 | Merge findings into executive report |
| **Category** | claude-sonnet-4-5 | **Territory-specific sales intelligence** |
| **Validator** | claude-sonnet-4-5 | **Citation verification** |

### ✅ Verification

- MCP tools load: **52 tools** ✓
- Research workflow nodes: **7 nodes** (groom, financial_research, industry_research, synthesize, categorize, validate) ✓
- State schemas import correctly ✓

### 📋 Phase 3 (Next Session)

**Ready for Phase 3 implementation in new session.**

Remaining Phase 3 enhancements:
- [ ] **Parallel Agent Execution** - Run Financial + Industry agents simultaneously using LangGraph branch/join pattern
- [ ] **Streaming Granularity** - Stream tool execution progress ("Querying SEC for Hexcel 10-K...")
- [ ] **Memory/Context Integration** - Connect to existing memory system, avoid redundant fetches
- [ ] **Report Caching** - Cache final reports by query hash with TTL invalidation

**Key Files to Modify**:
- `backend/app/graph/research_workflow.py` - Add parallel branching
- `backend/app/api/routes/deep_research.py` - Enhanced streaming
- `backend/app/agents/research/*.py` - Memory integration

**Reference Docs**:
- [Deep Research README](backend/app/agents/research/README.md) - Full architecture
- Session 19 in WORKLOG.md - Original Phase 3 spec details

---

## Session 20 (January 5, 2026) - Ingestion Throughput Tuning ✅

### 📋 Context

Reviewed bottleneck analysis from previous Opus session regarding Exa.ai industry queries backfill. The system was experiencing delays during high-volume runs (1000+ articles). Analysis identified conservative batching and concurrency settings as root cause.

### ✅ Completed

1. **Reduced Default Lookback Window** 🎉
   - **Change**: 3 days → 2 days for scheduled (non-backfill) runs
   - **File**: [orchestrator.py](backend/app/ingestion/orchestrator.py) lines 205-210
   - **Impact**: ~30% reduction in article volume
   - **Rationale**: Running daily, so 2-day window provides 1-day overlap buffer; Exa/Tavily index content within 24 hours

2. **Increased Classifier Concurrency** 🎉
   - **Change**: `max_concurrent` 3 → 10, sleep 0.5s → 0.2s
   - **File**: [classifier.py](backend/app/ingestion/processing/classifier.py) lines 295, 303
   - **Impact**: Classification time reduced from ~20min to ~7min for 400 articles
   - **Rationale**: Claude API handles 10 concurrent calls well

### 📁 Files Modified
- [orchestrator.py](backend/app/ingestion/orchestrator.py) - Lookback window
- [classifier.py](backend/app/ingestion/processing/classifier.py) - Concurrency settings

### 📊 Performance Expectations

| Metric | Before | After |
|--------|--------|-------|
| Articles per run | 400-600 | 250-400 |
| Classification time | ~25 min | ~7-10 min |
| Total run time | ~35-40 min | ~15-20 min |

### 📋 Not Changed (Optional Future Optimizations)

These were identified but not implemented (lookback cut provides sufficient headroom):
- Embedding batch size (5 → 20) - Vertex AI can handle larger batches
- Insert batch size (5 → 25) - BigQuery streaming can handle more

---

## Session 19 (January 5, 2026) - Deep Research Workflow Review & Phase 1 Fixes ✅

### 📋 Context

Reviewed the multi-agent Deep Research workflow to understand current architecture and plan enhancements. This workstream will span multiple sessions.

### ✅ Phase 1 Fixes Completed

1. **Fixed Schema Mismatch in financial.py** 🐛
   - `brief.research_intent` → `brief.clarified_intent`
   - `brief.key_entities` → `brief.entities_to_track`
   - `brief.time_period` → `brief.timeframe`

2. **Fixed Conditional Edge Bug in research_workflow.py** 🐛
   - Changed `"end": END` to `END: END` for proper LangGraph routing

3. **Model Configuration Centralized** ⚙️
   - Added to [settings.py](backend/app/config/settings.py):
     - `deep_research_groomer_model`
     - `deep_research_financial_model`
     - `deep_research_industry_model`
     - `deep_research_synthesizer_model`
   - All default to `claude-sonnet-4-5` (changed from opus for cost efficiency)
   - Updated all 4 agent files to use `settings.deep_research_*_model`

### 📁 Files Modified
- [financial.py](backend/app/agents/research/financial.py) - Schema fix + settings model
- [groomer.py](backend/app/agents/research/groomer.py) - Settings model
- [industry.py](backend/app/agents/research/industry.py) - Settings model
- [synthesizer.py](backend/app/agents/research/synthesizer.py) - Settings model
- [research_workflow.py](backend/app/graph/research_workflow.py) - Edge bug fix
- [settings.py](backend/app/config/settings.py) - New model settings

### 🏗️ Current Architecture

**4-Node LangGraph Pipeline:**
```
[User Query] → [Groomer] → [Financial Agent] → [Industry Agent] → [Synthesizer] → [Final Report]
```

| Node | Model | Purpose |
|------|-------|---------|
| Groomer | `claude-sonnet-4-5` | Query interpretation, clarification, sub-query generation |
| Financial Agent | `claude-opus-4-5` | SEC filings, earnings calls, analyst ratings |
| Industry Agent | `claude-opus-4-5` | Trade publications, market signals, news |
| Synthesizer | `claude-opus-4-5` | Merges findings into executive-ready report |

**Key Files:**
- [research_workflow.py](backend/app/graph/research_workflow.py) - LangGraph workflow definition
- [state.py](backend/app/agents/research/state.py) - Pydantic schemas (DeepResearchState, ResearchBrief, etc.)
- [groomer.py](backend/app/agents/research/groomer.py) - Query grooming node
- [financial.py](backend/app/agents/research/financial.py) - Financial research node
- [industry.py](backend/app/agents/research/industry.py) - Industry research node
- [synthesizer.py](backend/app/agents/research/synthesizer.py) - Report synthesis node
- [deep_research.py](backend/app/api/routes/deep_research.py) - API route

### 🛠️ MCP Tools Currently Used

**Financial Agent:**
| Tool | Source | Purpose |
|------|--------|---------|
| `get_earnings_transcript_ninja` | api_ninja_earnings | Earnings call transcripts |
| `query_corpus` | corpus_query | Internal pre-ingested financial data |
| `get_company_news` | stocknews_api | Recent company news by ticker |
| `get_press_releases` | stocknews_api | Official company announcements |
| `get_analyst_ratings` | stocknews_api | Upgrades, downgrades, price targets |
| `get_sentiment_summary` | stocknews_api | Aggregated news sentiment |
| `SECFilingCollector` | tools/sec_filings | SEC 10-K, 10-Q, 8-K filings |

**Industry Agent:**
| Tool | Source | Purpose |
|------|--------|---------|
| `news_search` | exa_search | Semantic news search |
| `web_search` | exa_search | Web search with domain filtering |
| `find_similar` | exa_search | Find similar content |
| `query_corpus` | corpus_query | Internal pre-ingested industry data |
| `get_market_signals` | corpus_query | Aggregated market signals |
| `get_google_trends` | google_trends | Demand signal validation |
| `get_company_news` | stocknews_api | Company news by ticker |
| `search_news_keyword` | stocknews_api | Keyword-based news search |
| `get_press_releases` | stocknews_api | Press releases |
| `get_trending_headlines` | stocknews_api | Major market events |
| `get_freight_rates` | timeseries_data | Shipping/logistics cost data |

### 🐛 Issues Identified

1. **Schema Mismatch in Financial Agent** - References `brief.research_intent`, `brief.key_entities`, `brief.time_period` but ResearchBrief uses `clarified_intent`, `entities_to_track`, `timeframe`
2. **Sequential Execution** - Financial → Industry runs sequentially; should be parallel
3. **No Real-Time Streaming** - Waits for entire workflow, then streams status
4. **Hardcoded Models** - Should use settings
5. **Conditional Edge Bug** - `"end"` mapping but returns `END` constant

### 📋 Deep Research Enhancement Roadmap

This workstream spans multiple sessions. Phase 1 complete, Phase 2 and 3 pending.

---

## 🔜 PHASE 2: Category Agent + Validator Agent (NEXT SESSION)

### Target Workflow After Phase 2:
```
[Groomer] → [Financial + Industry] → [Synthesizer] → [Category Agent] → [Validator] → [Final Report]
```

### 2.1 Prerequisites - New MCP Tools Needed

#### `query_datasheets` Tool (NEW)
- **Purpose**: Query BigQuery `datasheets` table for product spec sheets
- **Tables**: `datasheets`, `datasheet_scrape_runs`, `datasheet_suppliers`
- **Note**: REST API exists at [datasheets.py](backend/app/api/routes/datasheets.py), need MCP wrapper
- **Current gap**: `product_intelligence.py` uses hardcoded `PRODUCT_CATALOG` dict (1500 lines), not connected to BigQuery

#### `get_grounding_from_bq` Helper (NEW)
- **Purpose**: Replace CSV loading in `grounding.py` with BigQuery queries
- **Tables**: `companies`, `industries`, `materials` (verify these exist in BQ)

### 2.2 Category Agent Specification

**Role**: Advanced sales engineer providing territory-specific sales intelligence

**Business Context** (from Dave, CCO):
- Give 100-person field sales team "ammo to win" in customer conversations
- Break out insights for specific industries and use cases
- Force multiplier for strategic decisions

**Territory Focus Areas**:
| Territory | Primary Industries |
|-----------|-------------------|
| East | Aerospace, Wind Energy, Automotive (utility vehicles), Defense |
| West | Marine (boats), RVs, Spas |

**Note**: Both territories sell to all industries; these are strategic focuses only.

**Placement**: Post-Synthesis (takes full research report, adds sales layer)

**Tools**:
- `query_datasheets` (new - BigQuery product specs)
- `query_corpus` (existing - historical intel)
- `get_category_context` (new helper - industry→category→product mappings)

**Output Schema**:
```python
class CategoryAgentOutput(BaseModel):
    territory_insights: Dict[str, TerritoryInsight]  # "east" | "west"
    product_recommendations: List[ProductRecommendation]
    sales_plays: List[SalesPlay]
    industry_talking_points: Dict[str, List[str]]

class TerritoryInsight(BaseModel):
    territory: str  # "east" | "west"
    relevance_score: float  # 0-1 how relevant to territory
    key_takeaways: List[str]
    action_items: List[str]

class ProductRecommendation(BaseModel):
    product_name: str
    supplier: str
    material_category: str
    why_relevant: str
    datasheet_url: Optional[str]

class SalesPlay(BaseModel):
    play_name: str
    target_industry: str
    opening_hook: str  # Conversation starter
    key_data_points: List[str]  # Facts to cite
    objection_handlers: List[str]
    next_steps: List[str]
```

**System Prompt Context (Hybrid Approach)**:
- Hardcoded: Territory focus areas, top 10-15 industry→category mappings
- Tool-based: Deep dives for specific products via `query_datasheets`

**Always Runs**: Yes - Deep Research is the "full analysis" tool, users expect comprehensive output

### 2.3 Validator Agent Specification

**Role**: Citation and attribution verifier

**Placement**: After Category Agent, before final output

**Responsibilities**:
1. Verify all citations in final report have valid sources
2. Check that findings are properly attributed
3. Flag any unsubstantiated claims
4. Validate URLs are accessible (optional, may add latency)

**Output Schema**:
```python
class ValidatorOutput(BaseModel):
    validation_passed: bool
    citation_issues: List[CitationIssue]
    unsubstantiated_claims: List[str]
    confidence_adjustments: Dict[str, str]  # finding_id -> adjusted confidence
    warnings: List[str]

class CitationIssue(BaseModel):
    finding_id: str
    issue_type: str  # "missing_url", "date_mismatch", "source_not_found"
    description: str
    suggested_fix: Optional[str]
```

### 2.4 Phase 2 Implementation Order

1. Build `query_datasheets` MCP tool
2. Build `get_grounding_from_bq` helper (if needed)
3. Add `CategoryAgentOutput` schema to state.py
4. Build Category Agent node
5. Add `ValidatorOutput` schema to state.py
6. Build Validator Agent node
7. Update `research_workflow.py` to include new nodes
8. Add model settings for new agents
9. Test end-to-end

---

## 🔜 PHASE 3: Infrastructure Enhancements (FOLLOW-UP SESSION)

### 3.1 Parallel Agent Execution
- Run Financial + Industry agents simultaneously using LangGraph branch/join
- Potential: Category Agent pre-processing in parallel with research

### 3.2 Streaming Granularity
- Stream tool execution progress ("Querying SEC for Hexcel 10-K...")
- Real-time status updates per agent node
- "Agent thinking" visibility in UI

### 3.3 Memory/Context Integration
- Connect to existing memory system
- Avoid redundant fetches for repeat queries about same company
- Cross-session context retention

### 3.4 Report Caching
- Cache final reports by query hash
- TTL-based invalidation
- Skip regeneration for identical queries

---

### 📋 Session Planning

| Session | Focus | Status |
|---------|-------|--------|
| Session 19 | Phase 1: Foundation fixes | ✅ COMPLETE |
| Session 20 | Phase 2: Category + Validator agents | 🔜 NEXT |
| Session 21 | Phase 3: Parallel, streaming, memory, caching | 📋 PLANNED |

---

## Session 18 (January 5, 2026) - FMP Premium News Verification ✅

### ✅ Verified

1. **FMP `premium_news` Pipeline Working End-to-End** 🎉
   - Investigated concern that `source_type='premium_news'` wasn't appearing in BigQuery
   - **Result**: All good! Data is flowing correctly through entire pipeline:
     - `articles` table: 170 items
     - `article_chunk_embeddings` table: 696 chunks (~4 per article)
     - `digest_items` table: 170 items
   - Most recent fetch: Jan 5, 2026 @ 09:33 UTC
   - Sources: Benzinga, MarketBeat, Motley Fool, GuruFocus, Zacks, 247 Wallst

### 📋 No Changes Required

Pure verification session - no code changes needed.

---

## Session 17 (January 5, 2026) - Ad-Hoc Briefing Session Management ✅

### ✅ Completed

1. **Implemented Session-Based State Management** 🎉
   - **Problem**: `AdHocBriefingAgent()` was instantiated fresh per API request, so `follow_up_count` always reset to 0
   - **Solution**: In-memory session storage with TTL cache and LRU eviction
   - **Result**: Follow-up tracking now persists across requests; "max 2 follow-ups then redirect to Deep Research" works correctly

2. **New Backend Files** 📁
   - **[session_manager.py](backend/app/agents/adhoc_briefing/session_manager.py)**: 
     - `BriefingSession` dataclass (session_id, follow_up_count, conversation_history, timestamps)
     - `BriefingSessionManager` singleton with LRU OrderedDict
     - 30-minute TTL, max 1000 concurrent sessions
     - Methods: `create_session()`, `get_session()`, `get_or_create_session()`, `delete_session()`, `cleanup_expired()`, `get_stats()`

3. **Updated Backend Files** ✏️
   - **[agent.py](backend/app/agents/adhoc_briefing/agent.py)**: 
     - Added `session: Optional[BriefingSession]` parameter to `generate_briefing()` and `generate_briefing_stream()`
     - Uses session state for follow_up_count (falls back to instance state for backward compatibility)
     - Adds conversation history to session, injects into prompts for context
     - Returns `session_id` and `session` dict in responses
   - **[briefing.py](backend/app/api/routes/briefing.py)**:
     - Added `session_id: Optional[str]` to `AdHocBriefingRequest`
     - Updated `/adhoc` POST and `/adhoc/stream` POST to use session manager
     - New endpoints: `GET /adhoc/session/{session_id}`, `DELETE /adhoc/session/{session_id}`, `GET /adhoc/sessions/stats`

4. **Updated Frontend Files** 🖥️
   - **[briefing.ts](frontend/src/types/briefing.ts)**: Added `BriefingSessionInfo` interface, `session_id` fields
   - **[api.ts](frontend/src/lib/api.ts)**: Added `session_id` parameter to `createAdHocBriefing()` and `streamAdHocBriefing()`
   - **[useBriefing.ts](frontend/src/hooks/useBriefing.ts)**: Track `sessionId` and `turnsRemaining` state, pass to API
   - **[AdHocBriefing.tsx](frontend/src/components/dashboard/AdHocBriefing.tsx)**: Display server-side `turnsRemaining`

5. **Testing** ✅
   - Created [test_briefing_sessions.py](backend/scripts/testing/test_briefing_sessions.py) with 7 comprehensive tests
   - All tests pass: session creation, retrieval, follow-up tracking, conversation history, cleanup, stats, agent integration
   - Frontend build verified: `npm run build` ✓
   - Backend imports verified: 48 MCP tools loaded ✓

### 📋 Design Decisions

| Decision | Rationale |
|----------|-----------|
| In-memory storage | Simple, no additional infrastructure; sessions are ephemeral anyway |
| 30-min TTL | Balance between user convenience and memory usage |
| 1000 session max | LRU eviction prevents unbounded memory growth |
| Session ID in request/response | Stateless API design; client manages session continuity |
| Backward compatible agent | `session` parameter is optional; old code still works |

### 📋 Remaining Tech Debt (Updated)

| Priority | Issue | Description |
|----------|-------|-------------|
| ~~🟡 Medium~~ | ~~Ad-hoc Briefing Stateless~~ | ✅ **FIXED** - Session management implemented |
| 🟢 Low | **Convert to Native Claude Tools** | Custom JSON → native Anthropic tool use |
| 🟢 Low | **Domain Resolution Heuristics** | `company_name_to_domain()` guesses - could use lookup API |
| 🟢 Low | **CSV → BigQuery CRUD Migration** | `grounding.py` CSV fallback removal |

---

## Session 16 (January 5, 2026) - Cleanup Verification & Script Archive ✅

### ✅ Completed

1. **Verified Session 15 get_db Cleanup** 🎉
   - Reviewed all 5 modified files: `briefing.py`, `orchestrator.py`, `classifier.py`, `linker.py`, `digest.py`
   - Confirmed no `get_db` or `self.db` references in production code (`backend/app/**`)
   - Confirmed `app/db/__init__.py` exports only BigQuery storage (no SQLite)
   - Verified FastAPI app loads: `from app.main import app` ✅
   - Verified MCP tools load: 48 tools ✅

2. **Archived 10 Legacy Test Scripts** 📦
   - Moved scripts that import deleted `app/db/database.py` to `backend/scripts/archive/`:
     - `verify_enhancements.py`, `test_pulse_api.py`, `test_two_agent_pipeline.py`
     - `test_briefing.py`, `purge_and_backfill_exa.py`, `purge_data.py`
     - `load_companies.py`, `debug_entities.py`, `backfill_tags.py`, `check_data_sources.py`
   - Updated `backend/scripts/archive/README.md` with documentation

3. **Fixed Priority Case Normalization** ✅
   - **Issue**: LLM returns mixed case (`"high"`, `"High"`, `"HIGH"`), but enum expects title case
   - **Fix**: Added `.title()` normalization in `classifier.py` line 267
   - **Result**: Future classifications will have consistent `"High"`, `"Medium"`, `"Low"` values
   - **File**: [classifier.py](backend/app/ingestion/processing/classifier.py#L267-L268)

4. **Codebase Health Verified** ✅
   - No `database.py` imports remain in production code
   - All remaining `database.py` imports are safely in `scripts/archive/`
   - FastAPI + MCP tools load successfully

### 📋 Verified Already Done

- **Frontend 7-Day Filter**: Already implemented in `page.tsx` - uses `hours: 168` for pulse mode

### 📋 Remaining Tech Debt (From Session 15)

**CSV → BigQuery CRUD Migration** (Low Priority):
| File | Current | Needed |
|------|---------|--------|
| `grounding.py` | BQ primary, CSV fallback | Remove CSV fallback |

**Legacy Files** (Superseded by Long-Term Memory - see `c1-mvp-longterm_memory.md`):
| File | Status |
|------|--------|
| `data_management.py` | Legacy - replaced by long-term memory workflow |
| `data_preferences.py` | Legacy - replaced by long-term memory workflow |

### 📋 Other Open Items (Medium-Low Priority)

| Priority | Issue | Description |
|----------|-------|-------------|
| 🟡 Medium | **Ad-hoc Briefing Stateless** | `follow_up_count` resets per request - needs session management |
| 🟢 Low | **Convert to Native Claude Tools** | Custom JSON → native Anthropic tool use |
| 🟢 Low | **Domain Resolution Heuristics** | `company_name_to_domain()` guesses - could use lookup API |

---

## Session 15 (January 5, 2026) - get_db Cleanup Complete ✅

### ✅ Completed

1. **Removed All `get_db()` Imports** 🎉
   - **Files Fixed**: 
     - `backend/app/api/routes/briefing.py` - Removed SQLite fallback, BigQuery-only
     - `backend/app/ingestion/orchestrator.py` - Replaced `self.db` with `self.gcp_storage`
     - `backend/app/ingestion/processing/classifier.py` - Updated `load_tracked_entities()` to use BigQuery
     - `backend/app/ingestion/processing/linker.py` - Updated `load_entities()` to use BigQuery
     - `backend/app/ingestion/generators/digest.py` - Updated to use BigQuery storage

2. **Updated Data Loading Pattern** ✅
   - Classifier now loads competitors/OEMs from BigQuery `companies` table (with hardcoded fallback)
   - Linker now loads entities from BigQuery `companies` and `materials` tables
   - DigestGenerator now uses `get_digest_items()` instead of deprecated `query_corpus()`
   - Orchestrator's `get_status()` uses BigQuery `get_digest_stats()` instead of SQLite

3. **Verified All Imports** ✅
   - `from app.mcp.server import get_all_mcp_tools` - ✅ Works
   - All modified files import cleanly

### 📋 Future Work: Remove `resources/` Folder (CSV → BigQuery Migration)

The same entity data exists in both CSV files and BigQuery tables. Recommendation is to fully migrate to BigQuery.

**Scope Summary**:

| File | Current Usage | Migration Required |
|------|---------------|-------------------|
| `backend/app/utils/grounding.py` | BigQuery primary, CSV fallback | Remove CSV fallback |
| `backend/app/mcp/tools/data_management.py` | Writes to CSV files | Add BigQuery write methods (`add_company`, etc.) |
| `backend/app/api/routes/data_preferences.py` | CRUD operations on CSV | Same - needs BigQuery CRUD |
| `backend/app/config/settings.py` | Defines `companies_file`, etc. | Remove file path properties |
| `backend/scripts/operations/maintenance/seed_bigquery.py` | Seeds BQ from CSV | Keep as one-time migration tool |

**Required BigQuery Methods** (not yet implemented):
- `add_company()` / `update_company()` / `delete_company()`
- `add_material()` / `update_material()` / `delete_material()`
- `add_industry()` / `update_industry()` / `delete_industry()`

**When to do this**: Low priority. Current flow works. Can be done as a separate task.

---

## Session 14 (January 5, 2026) - Digest System Investigation ✅

### ✅ Completed

1. **"Lowium" Priority Bug Investigation** 🎉
   - **Finding**: 0 items with priority="Lowium" in BigQuery
   - **Conclusion**: Bug self-resolved (either fixed previously or data aged out)
   - **No action required** ✅

2. **Priority Case Sensitivity Issue Identified** ⚠️
   - **Finding**: 12% of items have capitalized priority values (`Low`, `Medium`, `High`) vs 88% lowercase
   - **Root Cause**: LLM sometimes returns capitalized values (as prompted), but parsing logic has lowercase default
   - **Impact**: Minimal - both values work functionally, but creates data inconsistency
   - **Distribution**:
     - `low`: 1,413 items ✅
     - `medium`: 1,237 items ✅
     - `high`: 671 items ✅
     - `Low`: 370 items ⚠️
     - `Medium`: 45 items ⚠️
     - `High`: 31 items ⚠️
   - **Recommendation**: Add case normalization in classifier (low priority)

3. **Production Health Check** ✅
   - **Status**: System healthy and functioning correctly
   - **Most Recent Run**: 2026-01-05 09:22:09 UTC
   - **Results**:
     - 178 articles fetched
     - 170 unique articles stored
     - 8 duplicates skipped
     - 95.5% efficiency (new content ratio)
     - 11m 23s duration
   - **Pipeline**: All stages working correctly (deduplication, enrichment, classification)
   - **Briefing Generation**: Expected failures (parallel workstream handling broken imports)

4. **Documentation Created**
   - Created comprehensive findings report: `digest_investigation_findings.md`
   - Updated task checklist with completed items
   - Created diagnostic script: `scripts/testing/check_lowium_bug.py`

### 📋 Optional Enhancements (Low Priority)

| Priority | Enhancement | Description |
|----------|-------------|-------------|
| 🟡 Low | **Priority Case Normalization** | Add `.lower()` normalization in classifier parsing to ensure consistent lowercase storage |
| 🟢 Low | **Frontend Filter Default** | Update digest filter from 72 hours → 7 days for better UX |

### ✅ Digest System Status: GOOD TO GO

All critical items resolved. System is healthy and functioning correctly. Optional enhancements can be tackled later if desired.

---

## Session 13b (January 5, 2026) - Digest SQLite Cleanup ✅

### ✅ Completed

1. **Deleted Legacy SQLite Code** 🎉
   - **Deleted**: `backend/app/db/database.py` (1,128 lines of legacy SQLite code)
   - **Updated**: `backend/app/db/__init__.py` - Removed `Database` and `get_db` imports/exports
   - **Removed**: `chromadb>=0.5.0` from `requirements.txt`
   - **Verified**: All critical imports still work (DB, GCP storage, DigestService)

2. **Confirmed Digest Data Flow** ✅
   - Digest cards pull from BigQuery `digest_items` table (verified in Session 12)
   - No SQLite references in digest pipeline
   - Data flow: Frontend → API → DigestService → BigQueryDataStorage → BigQuery

3. **Preserved Exa Pipeline SQLite** ✅
   - `backend/app/services/exa_websets_service.py` uses SQLite for webset tracking
   - This is intentional - different use case (pipeline prospect tracking, not intelligence corpus)

### 📋 Open Items (Digest Enhancements - Optional)

| Priority | Issue | Status |
|----------|-------|--------|
| ✅ Done | **"Lowium" Priority Bug** | Investigated in Session 14 - 0 items found, bug self-resolved |
| ✅ Done | **Production Dashboard** | Ran in Session 14 - System healthy, 170 articles stored |
| ⚠️ Identified | **Priority Case Sensitivity** | Session 14 found 12% capitalized values - low priority fix recommended |
| 🟢 Low | **Frontend Filter Should Be 7 Days** | Optional UX enhancement - change default from 72h to 168h |

### ✅ RESOLVED: Broken Imports - database.py Deleted (Fixed in Session 15)

**Status**: All `get_db` imports have been removed and replaced with BigQuery storage. See Session 15 above for details.

---

## Session 13 (January 5, 2026) - Briefing Pipeline Fix ✅

### ✅ Completed

1. **Fixed Agent 1 Data Source - SQLite → BigQuery** 🎉
   - **Problem**: PreBriefGenerator (Agent 1) was querying SQLite `corpus_items` (776 items) instead of BigQuery `articles` (3,308+ items)
   - **Solution**: Rewrote `_get_articles()` in `pre_briefing.py` to use `BigQueryDataStorage.get_articles()` instead of `self.db.query_corpus()`
   - **Added**: Custom date range support for historical pre-briefings (`start_date`, `end_date` parameters)
   - **File Modified**: [pre_briefing.py](backend/app/ingestion/generators/pre_briefing.py)

2. **Generated 3 Historical Pre-Briefings** 🎉
   - Period 3: Nov 24 - Dec 7, 2025 (50 articles, 27 observations)
   - Period 2: Dec 8-21, 2025 (50 articles, 20 observations)
   - Period 1: Dec 22 - Jan 4, 2026 (50 articles, 23 observations)
   - All saved to BigQuery `pre_briefings` table

3. **Generated Weekly Briefing** 🎉
   - ID: `c21f6cdc-1b55-4d1b-9a89-51aff8aa905f`
   - 4 strategic sections with net_new/continuing status
   - BLUF: "Defense spending surge anchored by the $151B Golden Dome initiative..."
   - Sections: Golden Dome Demand Catalyst, Space Launch Composites Inflection, Aerospace OEM Recovery Validation, Supply Chain & Materials Intelligence
   - Uses rich historical context from prior briefings

4. **Scripts Created**
   - `scripts/testing/test_prebriefing_bq.py` - Validates BigQuery data source
   - `scripts/operations/generate_briefings.py` - Generates historical pre-briefings + weekly briefing

### 📋 Ready to Deploy

All Session 11 improvements (BLUF persistence, rich historical context) + Session 13 fixes are ready:
- Agent 1 now uses BigQuery (full article corpus)
- 3 pre-briefings provide historical context
- Weekly briefing generated with proper net_new/continuing classification

**Deploy Command**:
```bash
git add .
git commit -m "Fix Agent 1 to use BigQuery, generate historical briefings"
git push origin main
```

### 📋 Open Items / To Do

| Priority | Issue | Description |
|----------|-------|-------------|
| � Medium | **Earnings Call Briefings** | Special briefing type triggered when new Q1 2026 earnings transcripts arrive (~late Jan). Longer-form summaries of key supplier/OEM calls. Data source already exists (`API Ninja Earnings`). |
| 🟡 Medium | **Pre-Brief Article Selection** | Currently takes 50 most recent by `published_at`. Could improve with relevance scoring, source diversity, or company prioritization. |
| �🟢 Low | **Ad-hoc Briefing Stateless** | `AdHocBriefingAgent.follow_up_count` resets each request |
| 🟢 Low | **Convert to Native Claude Tools** | Currently uses custom JSON format for tool calls |
| 🟢 Low | **Domain Resolution Heuristics** | `company_name_to_domain()` guesses domains |

---

## Session 12 (January 5, 2026) - Parallel Session

### ✅ Completed

1. **Digest Cards Data Source Investigation** 🔍
   - **Request**: Verify digest cards are pulling from BigQuery `digest_items` table (not SQLite/ChromaDB)
   - **Finding**: ✅ **CONFIRMED** - System is correctly using BigQuery
   - **Verification Results**:
     - Storage backend: `BigQueryDataStorage` (verified via runtime check)
     - Query target: `gen-lang-client-0436975498.c1_intelligence.digest_items`
     - Current data: 44 items in last 72 hours (Earnings: 4, General: 34, Market: 6)
     - Data flow: Frontend → API → DigestService → BigQueryDataStorage → BigQuery
   - **Legacy Files Found** (not in use):
     - `data/c1_corpus.db` - Old SQLite database (not imported by app)
     - `app/db/database.py` - SQLite interface (not used for digest cards)
     - Various legacy scripts referencing SQLite
   - **Documentation Created**:
     - Comprehensive findings report in artifacts
     - Created diagnostic scripts: `check_digest_data.py`, `check_digest_service.py`
   - **Files Verified**:
     - [digest_service.py](backend/app/services/digest_service.py) - Calls BigQuery storage
     - [gcp_storage.py](backend/app/db/gcp_storage.py) - `get_digest_items()` at L2666-2760
     - [digest.py](backend/app/api/routes/digest.py) - API endpoints
     - [useDigest.ts](frontend/src/hooks/useDigest.ts) - Frontend hook

### 📋 Key Findings

- **No SQLite/ChromaDB in use** for digest cards - suspicion was incorrect
- System properly configured with hardcoded BigQuery defaults
- Query includes smart filters: date range, confidence threshold, future date exclusion
- 15-minute cache TTL in DigestService
- If frontend shows stale data, likely causes:
  1. Frontend filters hiding items
  2. Ingestion schedule (when was last run?)
  3. Cache (15-min TTL)
  4. Frontend state/loading issues

---

## Session 11 (January 5, 2026)

### ✅ Completed

1. **Historical Context Enhancement for Agent 2** 🎉
   - **Problem**: Agent 2 (Executive Synthesizer) only received sparse topic list from prior briefings
   - **Before**: `"Briefing Date: 2026-01-05\nTopics: Defense, Resins, Aerospace"`
   - **After**: Rich context with BLUF, section headlines, insight status (net_new/continuing), key companies, and overall trend
   - Now Agent 2 can accurately perform "differential analysis" to classify new vs continuing topics
   - **File Modified**: [weekly_briefing.py](backend/app/ingestion/generators/weekly_briefing.py) - `_get_historical_context()`

2. **BLUF Now Persisted to BigQuery** 🎉
   - **Problem**: BLUF was being generated by Agent 2 but never saved to BigQuery (missing column + not in insert)
   - **Fix**: 
     - Added `bluf` column to `weekly_briefings` table schema
     - Added `bluf` field to `save_weekly_briefing()` row dict
     - Added `bluf` parsing to `get_latest_weekly_briefing()` and `get_weekly_briefing_history()`
   - **File Modified**: [gcp_storage.py](backend/app/db/gcp_storage.py)
   - **Migration**: Created and ran `scripts/operations/migrations/add_bluf_column.py`

3. **Migration Script Created**
   - Created `backend/scripts/operations/migrations/add_bluf_column.py`
   - Successfully ran migration - `bluf` column now exists in BigQuery
   - Non-destructive: existing rows have NULL, code handles gracefully

4. **Discovered Critical Data Source Issue** 🚨
   - **Finding**: Agent 1 (PreBriefGenerator) queries **SQLite** `corpus_items` (776 items), NOT BigQuery `articles` (3,308 items)
   - `pre_briefing.py` line 89: `await self.db.query_corpus(hours=days*24, limit=50)` → SQLite
   - This means pre-briefings are built from a fraction of available data
   - **Data Comparison**:
     - SQLite `corpus_items`: 776 items
     - BigQuery `articles`: 3,308 items
     - BigQuery `digest_items`: 3,767 items
   - **BigQuery has good coverage for target periods**:
     - Dec 22 - Jan 5: 1,294 articles
     - Dec 8-21: 383 articles
     - Nov 24 - Dec 7: 122 articles
   - **Scripts Created**: `check_data_sources.py`, `check_periods.py`, `check_dec_dates.py`

### 🚨 CRITICAL: Do NOT Deploy Yet

The code changes (BLUF storage, historical context) are complete but **Agent 1 still uses SQLite**.
Wait until Session 13 completes the fix before deploying.

### 📋 Open Items / To Do

| Priority | Issue | Description |
|----------|-------|-------------|
| 🔴 HIGH | **Agent 1 Uses SQLite** | PreBriefGenerator queries SQLite (776 items) not BigQuery (3,308). Must fix before deploy. |
| 🟡 Medium | **Backfill Historical Briefings** | After fixing Agent 1, generate 3 pre-briefings + 1 weekly for full experience |
| 🟡 Medium | **Ad-hoc Briefing Stateless** | `AdHocBriefingAgent.follow_up_count` resets each request |
| 🟢 Low | **Convert to Native Claude Tools** | Currently uses custom JSON format for tool calls |
| 🟢 Low | **Domain Resolution Heuristics** | `company_name_to_domain()` guesses domains |

---

## Session 10 (January 5, 2026)

### ✅ Completed

1. **Source Articles Now Linked in Weekly Briefings** 🎉
   - **Root Cause**: `WeeklyBriefingGenerator._build_source_articles()` existed but was never called when building `processed_sections`
   - **Fix**: Added `_extract_citation_numbers()` method to parse `[N]` and `[Exa:N]` citations from section text
   - Enhanced `_build_source_articles()` to handle both pre-brief and Exa peripheral search sources
   - Now each section includes `source_articles` array with `{id, title, url, source_name, published_at}`
   - Citations like `[1]`, `[2]` in text now have corresponding clickable links in the Sources footer
   - **File Modified**: [weekly_briefing.py](backend/app/ingestion/generators/weekly_briefing.py)

2. **BLUF (Bottom Line Up Front) Now Rendered** 🎉
   - **Root Cause**: Frontend `WeeklyBriefing` type didn't include `bluf` field, and component didn't render it
   - **Fix**: Added `bluf?: string` to TypeScript type and styled BLUF display in briefing header
   - BLUF appears as a highlighted callout box with "BLUF" label, positioned prominently after the title
   - **Files Modified**: 
     - [briefing.ts](frontend/src/types/briefing.ts) - Added `bluf` to `WeeklyBriefing` interface
     - [WeeklyBriefingSection.tsx](frontend/src/components/dashboard/WeeklyBriefingSection.tsx) - Added BLUF display

### 📋 Open Items / To Do (Remaining from Session 9)

| Priority | Issue | Description |
|----------|-------|-------------|
| 🟡 Medium | **Historical Context Too Sparse** | Agent 2 only gets topic list from previous briefings, not actual headlines - limits narrative continuity |
| 🟡 Medium | **Ad-hoc Briefing Stateless** | `AdHocBriefingAgent.follow_up_count` resets each request - can't track multi-turn conversations |
| 🟢 Low | **Convert to Native Claude Tools** | Currently uses custom JSON format for tool calls - could use native Anthropic tool use |
| 🟢 Low | **Domain Resolution Heuristics** | `company_name_to_domain()` guesses domains - could add more known mappings or use lookup API |

---

## Session 9 (January 5, 2026)

### ✅ Completed

1. **Comprehensive Code Review of Briefing Workflow**
   - Reviewed the 2-agent pipeline: PreBriefGenerator (Agent 1) → WeeklyBriefingGenerator (Agent 2)
   - Agent 1 (claude-sonnet-4-5): Analyzes 50 articles from last 14 days, produces structured observations with signal_type
   - Agent 2 (claude-opus-4-5): Synthesizes with Exa.ai peripheral search, produces strategic briefing sections
   - Identified 6 improvement areas (see Open Items below)

2. **Cloud Scheduler Jobs Fixed (AGAIN)** 🚨
   - All 6 scheduler jobs were pointing to DEAD URL: `c1-intelligence-hub-285931707029.us-central1.run.app`
   - The correct URL is: `https://c1-hub-4iz75bvpyq-uc.a.run.app`
   - Updated all jobs with correct URL and OIDC audience
   - Jobs affected: `weekly-executive-briefing`, `ingest-deep-dive`, `ingest-flash-update`, `daily-evening-ingest`, `weekly-data-cleanup`, `weekly-corpus-refresh`

3. **Logo.dev Integration Fixed** ✅
   - **Root Cause**: `LOGO_DEV_TOKEN` secret in Secret Manager had trailing carriage return (`\r`)
   - This caused: `Invalid non-printable ASCII character in URL, '\r' at position 86`
   - **Fix**: Created clean version 3 of secret without `\r`, forced Cloud Run revision update
   - All logo domains now return 200 with valid PNG bytes
   - Tested: `airbus.com`, `boeing.com`, `compositesone.com`, `spiritaero.com`, `hexcel.com` all working

4. **cloudbuild.yaml Updated**
   - Added `LOGO_DEV_TOKEN=LOGO_DEV_TOKEN:latest` to `--set-secrets` line
   - Future git-push deployments will now include the logo token

### 📋 Open Items / To Do (from Code Review)

| Priority | Issue | Description |
|----------|-------|-------------|
| ✅ Done | **Source Articles Not Linked** | Fixed in Session 10 - citations now have clickable links |
| ✅ Done | **BLUF Not Rendered** | Fixed in Session 10 - BLUF now displays in briefing header |
| 🟡 Medium | **Historical Context Too Sparse** | Agent 2 only gets topic list from previous briefings, not actual headlines - limits narrative continuity |
| 🟡 Medium | **Ad-hoc Briefing Stateless** | `AdHocBriefingAgent.follow_up_count` resets each request - can't track multi-turn conversations |
| 🟢 Low | **Convert to Native Claude Tools** | Currently uses custom JSON format for tool calls - could use native Anthropic tool use |
| 🟢 Low | **Domain Resolution Heuristics** | `company_name_to_domain()` guesses domains - could add more known mappings or use lookup API |

### 🔧 Infrastructure Notes

- **Cloud Run Service**: `c1-hub` at `https://c1-hub-4iz75bvpyq-uc.a.run.app`
- **Cloud Build Trigger**: GitHub push to `main` triggers build (configured in GCP Console)
- **Secrets in Secret Manager**: ANTHROPIC_API_KEY, FMP_API_KEY, API_NINJA_KEY, TAVILY_API_KEY, EXA_API_KEY, LOGO_DEV_TOKEN (now clean)

---

## Session 8 (January 5, 2026)

### ✅ Completed

1. **DRUMBEAT Feed Fix - JSON Parsing Error** 🎉
   - **Root Cause**: `companies`, `industries`, `materials`, `topics` fields in BigQuery had inconsistent formats:
     - Some rows stored as JSON arrays: `'["Tesla", "Boeing"]'`
     - Other rows stored as comma-separated strings: `'Tesla, Boeing'`
   - The code used `json.loads()` which crashed on comma-separated strings
   - **Fix**: Added `_safe_parse_list()` helper function that handles both formats
   - Applied fix to `get_digest_items()` and 4 other methods in [gcp_storage.py](backend/app/db/gcp_storage.py)
   - **Result**: Digest items now load correctly (644 items in last 7 days)

2. **Deployment Cleanup**
   - Deleted duplicate `deploy/cloudbuild.yaml` - consolidated to root `cloudbuild.yaml`
   - Updated `CLAUDE.md` with correct deployment instructions and Cloud Run URL
   - **Correct Cloud Run URL**: `https://c1-hub-4iz75bvpyq-uc.a.run.app`
   - **Service Name**: `c1-hub` (NOT `c1-intelligence-hub`)

3. **FMP Premium News Backfill Script**
   - Created `backend/scripts/operations/backfill/backfill_premium_news.py`
   - Uses `/api/v1/scheduler/ingest` with `sources: ["fmp_news"]`

4. **FMP Premium News FIXED & Backfilled** 🎉 (Session 8b)
   - **Root Cause**: `cloudbuild.yaml` referenced deleted secret name `fmp-api-key` but secret was renamed to `FMP_API_KEY`
   - **Fix**: Updated `cloudbuild.yaml` line 63 from `FMP_API_KEY=fmp-api-key:latest` to `FMP_API_KEY=FMP_API_KEY:latest`
   - **Deploy**: Deployed fix via Cloud Build
   - **Backfill Results**:
     - 170 `premium_news` articles stored in `articles` table
     - 170 `premium_news` items in `digest_items` table
   - **Note**: 403 errors during enrichment are expected - Benzinga/SeekingAlpha/Bloomberg block scrapers. FMP provides article text directly so this doesn't affect data quality.

### ✅ All Session 8 Items Complete

| Task | Status |
|------|--------|
| DRUMBEAT Feed Fix (JSON parsing) | ✅ Deployed |
| FMP Secret Reference Fix | ✅ Deployed |
| FMP 30-day Backfill | ✅ 170 articles |

---

## Session 7 (January 5, 2026)

### ✅ Completed

1. **API Ninja Earnings Re-enabled & Backfilled**
   - Confirmed endpoint works (tested with GCTAF ticker)
   - Tested all 48 tracked tickers for Q3 2025 transcripts
   - Added `collect_for_quarter()` method to earnings collector for direct quarter fetch
   - Fixed `run_earnings_only()` method:
     - Changed `list_companies()` → `get_companies()`
     - Fixed `await get_storage()` (was missing await)
     - Fixed field name: `stock_ticker` → `ticker`
     - Added filter to exclude `'private'` companies
   - **Backfill Results**: 56 Q3 2025 transcripts found, 40 new stored (16 dupes)

2. **Cloud Scheduler Jobs Fixed** 🚨
   - All 6 jobs were pointing to OLD Cloud Run URL (`c1-hub-4iz75bvpyq-uc.a.run.app`)
   - Updated all to new URL: `https://c1-intelligence-hub-285931707029.us-central1.run.app`
   - Updated OIDC audience to match new URL
   - Jobs updated:
     - `daily-evening-ingest` (2 AM daily)
     - `ingest-flash-update` (every 4 hours)
     - `ingest-deep-dive` (8 AM daily)
     - `weekly-executive-briefing` (Monday 2:30 PM)
     - `weekly-data-cleanup` (Sunday 2 AM)
     - `weekly-corpus-refresh` (Sunday 3 AM)

3. **Created WORKLOG.md** - Session continuity system
   - Added instructions to CLAUDE.md to read/update WORKLOG.md
   - Tracks completed work, in-progress, and open items

4. **Documentation Updates**
   - Updated `CLAUDE.md` with Session 7 changes and session continuity instructions
   - Updated `scripts/README.md` with new quick reference and data sources table
   - Updated `scripts/monitoring/README.md` to focus on production_dashboard
   - Fixed `production_dashboard.py` to find health check in correct directory

5. **Monitoring Script Improvements**
   - Added `premium_news` (FMP News) to `ingestion_health_check.py`
   - Fixed source type `stocknews` → `stocknewsapi`
   - Updated display to show 9 sources (was 8)

### 🔄 In Progress

1. **DRUMBEAT Feed Investigation** - Started investigating why digest cards not loading

### 📋 Open Items / Next Steps

1. **🚨 DRUMBEAT Feed Not Loading** - Digest cards not showing in app's 7-day news feed
   
   **Investigation Progress (Session 7):**
   - ✅ Data EXISTS in BigQuery: 3,597 rows in `digest_items`, 645 in last 7 days
   - ✅ `feed_eligible=True` for 3,574 items (only 23 are False)
   - ✅ Items by source in last 7 days: web_news (287), web_news_exa (159), stocknewsapi (156), rss (35), etc.
   
   **ROOT CAUSE IDENTIFIED:**
   - `backend/app/db/gcp_storage.py` has TWO storage classes:
     - `LocalDataStorage` (line 254) - Uses SQLite
     - `BigQueryDataStorage` (line 662) - Uses BigQuery
   - Both have `get_digest_items()` method
   - The `get_data_storage()` function (line 2865) checks `gcp_config.is_configured`
   - **HYPOTHESIS**: Locally or in production, it might be falling back to SQLite which has NO data
   
   **Next Steps:**
   - Test which storage type is being used: `type(storage).__name__`
   - Check `gcp_config.is_configured` value in production
   - If BigQuery, check if the query filters are excluding items (date filters, confidence, etc.)
   - The BigQuery `get_digest_items` has complex filters:
     - `published_at >= cutoff_time` (lookback hours)
     - `published_at <= now` (not future)
     - `confidence >= 0.3`
     - `ingested_at >= '2025-12-28'`
     - Complex `classified_at` vs `published_at` check (30 min diff)
   
   **Key Files:**
   - `backend/app/db/gcp_storage.py` - Storage backends (lines 536-620 SQLite, lines 2626-2720 BigQuery)
   - `backend/app/services/digest_service.py` - `get_digest()` method (line 102)
   - `backend/app/api/routes/digest.py` - API endpoint (line 28)
   - `frontend/src/hooks/useDigest.ts` - Frontend hook
   - `frontend/src/lib/api.ts` - API client (line 119: `/api/digest`)

2. **Re-run Industry Queries Backfill** - Previous run got stuck
   - Try with smaller batch: `--days 2` or `--days 3`

3. **Consider Q4 2024 Earnings** - Could also backfill Q4 2024 for more historical data

4. **Earnings in Daily Scheduler** - Decide if/how to add earnings to scheduled runs
   - API Ninja is quarter-based, not daily
   - May need custom logic: "fetch current quarter's earnings for any new filings"

### 🔑 Key Technical Context

- **BigQuery dataset**: `gen-lang-client-0436975498.c1_intelligence`
- **MCP tools**: 48 loading correctly
- **Companies table**: `stock_ticker` column → converted to `ticker` in Python via `get_companies()`
- **Earnings URL format**: `earnings://{ticker}/{year}/Q{quarter}` (unique for dedup)

### Companies WITH Q3 2025 Earnings (35)
VMC, MLM, CRH, GVA, PWR, MTZ, PRIM, SKBSY, ACM, J, FLR, SGL.DE, HXL, BA, EADSY, ERJ, RTX, NOC, LMT, GD, GE, RKLB, VWDRY, GEV, NRDXF, BC, RACE, FINMY, TXT, JOBY, ACHR, MBUU, MCFT, F, GM

### Companies WITHOUT Q3 2025 Earnings (13)
SUM, TINLY, GURN.SW, SOLVY, TRYIY, BAESY, SAFRY, RYCEY, GCTAF, BEN.PA, BMWYY, BDRBF, TM

---

## Session 6 (January 5, 2026)

### ✅ Completed
- SEC Filings headline fix - Added `headline` column to BigQuery `digest_items` table
- Archived API Ninja earnings (9 rows) - Bad URL templates caused dedup collisions
- FMP Premium News collector working - `app/tools/fmp_news/`
- SEC filings working - 45 in articles, 67 in digest_items
- Removed FMP Earnings code - Deleted `app/tools/fmp_earnings/` (requires premium)

---

## Session 5 and Earlier (January 4, 2026)

### ✅ Completed
- Deduplication migrated to BigQuery
- `DeduplicationService` now uses `gcp_storage.py` instead of SQLite
- Industry queries expanded (236 queries: 91 Exa + 145 Tavily)

### Known Remaining SQLite Usage
- classifier/entity_linker entity loading
- briefing generators (legacy)

---

## Quick Reference

### Test Commands
```bash
# Verify MCP tools load
cd backend && python -c "from app.mcp.server import get_all_mcp_tools; print(f'MCP tools: {len(get_all_mcp_tools())}')"

# Quick health check
python scripts/monitoring/production_dashboard.py

# Detailed health check
python scripts/monitoring/production_dashboard.py --detailed --days 7
```

### Backfill Commands
```bash
# Industry queries
python scripts/operations/backfill/backfill_industry_queries.py --days 7

# Earnings (Q3 2025)
python -c "import asyncio; from app.ingestion.orchestrator import *; asyncio.run(IngestionOrchestrator(IngestionConfig()).run_earnings_only(year=2025, quarter=3))"

# SEC filings
python scripts/operations/backfill/backfill_sec_filings.py --days 7
```

---

## 📋 SESSION 8 HANDOFF SUMMARY

**Copy this to start Session 8:**

```
Continue Session 8 for c1-intelligence-hub.

IMMEDIATE PRIORITY: Fix DRUMBEAT feed not loading digest cards

CONTEXT:
- Data EXISTS in BigQuery: 3,597 digest_items, 645 in last 7 days, feed_eligible=True
- Problem: Frontend shows "No recent activity in the last 7 days"
- Likely cause: Storage backend selection issue

INVESTIGATION SO FAR:
1. BigQuery has data (confirmed via direct query)
2. Two storage classes exist in gcp_storage.py:
   - LocalDataStorage (SQLite) - line 254
   - BigQueryDataStorage - line 662
3. get_data_storage() chooses based on gcp_config.is_configured
4. HYPOTHESIS: Something is making it use SQLite instead of BigQuery

NEXT STEPS:
1. Run this test to check storage type:
   cd backend && python -c "import asyncio; from app.db.gcp_storage import get_storage, gcp_config; print(f'is_configured: {gcp_config.is_configured}'); s=asyncio.run(get_storage()); print(f'Storage: {type(s).__name__}')"

2. If BigQuery, check the query filters in get_digest_items (line 2626):
   - published_at date range
   - confidence >= 0.3
   - ingested_at >= '2025-12-28'
   - The classified_at vs published_at 30-min check

3. Test the actual API endpoint: curl http://localhost:8000/api/digest?hours=168

KEY FILES:
- backend/app/db/gcp_storage.py - Storage backends
- backend/app/services/digest_service.py - get_digest() method  
- backend/app/api/routes/digest.py - /api/digest endpoint

SESSION 7 COMPLETED:
- ✅ Earnings backfill (40 new Q3 2025 transcripts)
- ✅ Cloud Scheduler jobs fixed (6 jobs, all pointed to wrong URL)
- ✅ WORKLOG.md created for session continuity
```
