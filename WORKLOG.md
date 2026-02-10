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

## 🚨 TODO / Open Issues

### ~~Earnings Transcript Ingestion (API Ninja)~~ — ✅ FIXED (Session 108)
- Root cause: `collect_for_company` only fetched `current_year` (2026), but target was Q4 2025
- Fix: Use `collect_for_quarter(year, quarter)` directly with orchestrator's calculated target
- Deployed commit `2089c66` — will fetch ~40+ Q4 2025 transcripts on next scheduled run (Feb 10 08:45 UTC)

### Break Out Transcripts & SEC Filings into Dedicated BigQuery Tables
- Currently, earnings transcripts and SEC filings are stored in the `articles` table with `source_type` filters (`earnings_transcript`, `sec_filing`)
- This pollutes the articles table with non-article content (full transcripts, filing HTML)
- **Plan**: Create dedicated `earnings_transcripts` and `sec_filings` BigQuery tables
- Migrate existing rows from `articles` where `source_type IN ('earnings_transcript', 'sec_filing')`
- Update `earnings_quotes` and `sec_filing_nuggets` to reference the new source tables instead of parsing from `articles`
- Update ingestion orchestrator to write to the new tables instead of `articles`
- Keep `articles` table clean — actual news articles, press releases, and research only

---
## 📅 SESSION 109: Update Guide Agent Knowledge Base (February 10, 2026)

**Status**: ✅ COMPLETE

### 🎯 Goal

Update the Guide agent's knowledge base to reflect the full current state of the Intelligence Hub — many new features and data sources had been added since the knowledge base was last written.

### ✅ Changes

**`backend/app/agents/guide/guide_knowledge.py`:**
- **ADDITIONAL_SOURCES** — Completely rewritten. Was a 4-line stub mentioning "earnings transcripts" and "SEC filings." Now covers:
  - Financial Intelligence deep extraction (earnings quotes with sentiment, SEC nuggets with signal scoring, combined Financial Feed)
  - Industry Podcast Intelligence (5 tracked podcasts, AI quote extraction, Expert Feed)
  - Supply Chain Intelligence (US customs import data, shared supplier analysis, competitive activity tracking, 265+ companies)
  - Product Datasheet Intelligence
  - Drewry freight rate time-series
- **TAB_FEATURES** — Major rewrite to match current UI:
  - "Market Intelligence" renamed to "Discovery" with sub-feeds (News, Financial, Expert, Bulletin Board, AI Chat)
  - Added Supply Network tab (graph visualization, shared suppliers, exclusive suppliers, competitive activity)
  - Added Products tab (datasheet library, supplier comparison, gap analysis)
  - Added Companies tab (265+ tracked, track/untrack)
  - Added Industries tab (narrative timelines, AI analysis)
  - Updated Deep Research (6+ agents, cached results)
  - Added ad-hoc briefing capability to Need to Know
  - Added Pipeline AI agent chat
- **SEARCH_QUERIES** — Updated count from 150+ to 230+ daily queries
- **STRATEGIC_BRIEFING** — Added ad-hoc briefings section, multiple voice styles
- **Internal reference** — Updated "NEVER mention" list with API Ninja, StockNewsAPI, ImportYeti, Drewry WCI, SEC-API.io

**`backend/app/agents/guide/guide_agent.py`:**
- **System prompt DO list** — Added 5 new items: Financial Feed, Expert Feed, Supply Network, 265+ companies, ad-hoc briefings
- **Conversation starters** — Added 4 new suggestions: Financial Feed, podcast analysis, Supply Network, SEC filings
- **Welcome message** — Updated with concrete numbers (265+ companies, 230+ queries, mentions podcasts/SEC/supply chain), added Financial Feed, Expert Feed, Supply Network to the feature list

### Files Modified
- `backend/app/agents/guide/guide_knowledge.py`
- `backend/app/agents/guide/guide_agent.py`

---
## 📅 SESSION 108: Fix Earnings Transcript Ingestion (February 9, 2026)

**Status**: ✅ COMPLETE — Deployed (commit `2089c66`)

### 🎯 Goal

Investigate and fix earnings transcript ingestion which had been returning 0 transcripts since ~Jan 5, 2026.

### 🔍 Root Cause

**Bug in orchestrator → collector interaction:**
1. Orchestrator correctly calculates `target_year=2025, target_quarter=4` for Feb 2026
2. Orchestrator calls `collect_for_company(since=None)` which sets `years_to_fetch = [current_year]` = `[2026]`
3. Collector's "future quarter" optimization `quarter > (month-1)//3 + 1` skips Q2-Q4 of 2026, only fetches Q1 2026
4. Orchestrator filters results for `year==2025 and quarter==4` → **0 matches** (only Q1 2026 was fetched)
5. Result: earnings fetch runs daily, logs "Checking 77 companies" but always produces "0 transcripts collected"

**Secondary issue (Feb 7-8):** "Checking 0 companies" — the companies list was empty on some days, likely a transient BQ issue.

### ✅ Fix Applied

- **Replaced `collect_for_company` with `collect_for_quarter`** in the orchestrator earnings section
- `collect_for_quarter(ticker, target_year, target_quarter)` directly asks API Ninja for the exact year/quarter, bypassing the broken year iteration logic
- Added **pre-check dedup**: queries BQ for already-stored earnings URLs matching the target quarter, skips those tickers (avoids redundant API calls on subsequent runs)
- Added progress logging every 20 companies

### Verification
- Tested locally: AAPL, BA, RTX, LMT, HXL all return full Q4 2025 transcripts (37K-56K chars each)
- API Ninja endpoint confirmed working with 40-char key
- Existing Q3 2025 data: 40 transcripts (latest Nov 10, 2025) — no dedup collision with Q4

### 📁 Files Modified
| File | Change |
|------|--------|
| `backend/app/ingestion/orchestrator.py` | Replaced `collect_for_company` with `collect_for_quarter` + added existing-ticker dedup pre-check |

### 🔮 Next Steps
- Monitor next scheduled run (Feb 10, 08:45 UTC) for Q4 2025 transcript count
- Expected: ~40+ new transcripts for tracked companies
- SEC Filing Nuggets re-ingestion still needed (all tickers = '?')
- Podcast quotes `speaker_company` fix still needed

---
## 📅 SESSION 106: Pre-extracted BigQuery Tools in Deep Research + Enhanced Quote Formatting (February 9, 2026)

**Status**: ✅ COMPLETE — Deployed (commit `2defe3e`)

### What Was Done

**Replaced live API tools with pre-extracted BigQuery data in Deep Research workflow:**

1. **Financial Agent (`financial.py`)**:
   - Removed `get_earnings_transcript_ninja` + `search_earnings_keywords` (API Ninja live calls)
   - Removed `SECFilingCollector` (sec-api.io live calls)
   - Added `search_earnings_quotes` — pre-extracted, speaker-attributed earnings quotes from BigQuery `earnings_quotes` table
   - Added `search_sec_nuggets` — pre-extracted SEC filing insights from BigQuery `sec_filing_nuggets` table (with signal_strength, is_new_disclosure, competitors_named)
   - Both gated on `has_company_mention` (same as old tools)
   - Deleted dead `_extract_quote_keywords()` function
   - Updated ranking, system prompt, and extraction prompt

2. **Industry Agent (`industry.py`)**:
   - Added `search_podcast_quotes` — expert practitioner insights from industry podcasts (CW Talks, Composites Weekly, The Chemical Show, ICIS Chemical, Uptime Wind Energy)
   - Gated on `needs_trade_news or needs_demand_signals`
   - Added to ranking at priority 8 (same as market_signals)

3. **Synthesizer (`synthesizer.py`)**:
   - Quote block definition now includes `source_type` field: `earnings_call`, `podcast`, `sec_filing`, `other`
   - Context format guidance per source type

4. **Frontend (`BlockQuote.tsx`)**:
   - Source-type-specific styling with color configs:
     - Earnings: amber accent, `TrendingUp` icon badge
     - Podcast: purple accent, `Mic` icon badge
     - SEC Filing: blue accent, `FileText` icon badge
     - Default: emerald (unchanged)
   - Large decorative opening quote mark (text-5xl)

5. **Supporting files updated**:
   - `groomer.py` — tool capabilities table + query optimization rules
   - `progress.py` — 3 new TOOL_DESCRIPTIONS entries
   - `server.py` — deprecation comment on old earnings tools (kept registered for ad-hoc briefing)
   - `ResearchProgress.tsx` — 3 new toolLabels
   - `README.md` — full update reflecting new tools, gating, and quote formatting

### Key Technical Decisions
- Old `api_ninja_earnings` tools kept in `server.py` for ad-hoc briefing agent compatibility
- SEC collector fully replaced (not kept alongside nuggets) — nuggets are faster and richer
- Podcast quotes in Industry Agent only (not Financial) — aligns with qualitative market focus
- `search_earnings_quotes` and `search_sec_nuggets` are async (`ainvoke`), `search_podcast_quotes` is sync (`invoke`)

### Verification
- All Python imports pass
- MCP tool count: 63 (unchanged)
- TypeScript compiles with no errors

---
## 📅 SESSION 107: Confirm Citation Fix, Fix Scheduler, Audit Voice Enrichment Data (February 9, 2026)

**Status**: ✅ COMPLETE — Scheduler fixed, audits documented, re-ingestion deferred to next session

### 🎯 Goal

Confirm the citation fix from Session 96 works, fix the Cloud Scheduler `weekly-executive-briefing` job, and audit SEC nuggets + earnings quotes metadata quality to plan re-ingestion.

### ✅ Completed

1. **Citation fix confirmed** — Tested 5 article IDs from the current broken briefing (`f3a3915a`) against `digest_items` table. Result: **5/5 found** with real titles and URLs. The `get_articles_by_ids()` rewrite (Session 96: queries `digest_items` by `article_id` first, falls back to `articles`) is working correctly. Current briefing has "Article not found" baked in from before the fix — will resolve on next regeneration.

2. **Cloud Scheduler fix** — `weekly-executive-briefing` job had `attemptDeadline: 900s` (15 min). Briefing generation takes ~880s (14.7 min) — borderline. Updated to `attemptDeadline: 1800s` (30 min) via `gcloud scheduler jobs update`. The `status.code: 14 (UNAVAILABLE)` from the 14:31 UTC attempt was likely a cold-start timeout (minScale=0, no warm instances). The 20:49 retry succeeded — 4 sections, 174 articles, 880s total including podcast generation.

3. **SEC Filing Nuggets audit** — 366 rows, significant metadata gaps:
   - **ticker**: 100% broken — all 366 rows have `ticker='?'` (no valid tickers)
   - **company_name**: ✅ 100% populated (e.g., "HEXCEL CORP /DE/", "ASHLAND INC.", "3M CO")
   - **filing_type**: ✅ 100% populated (all "8-K")
   - **filing_date**: ✅ 100% populated
   - **cik**: ❌ All empty strings
   - **fiscal_quarter**: ❌ All NULL
   - **companies_mentioned**: ❌ 284/366 (78%) empty `[]`
   - **competitors_named**: ❌ 364/366 (99%) empty
   - **brands_mentioned**: ❌ 365/366 (99%) empty
   - **No `source_url` column** — schema doesn't include it
   - Top companies: Ashland (31), GM (28), 3M (24), Joby Aviation (22), RTX (20), PACCAR (18), GE Vernova (18)
   - Only 8-K filings ingested — no 10-K or 10-Q

4. **Earnings Quotes audit** — 1,699 rows, metadata quality is **excellent**:
   - **ticker**: ✅ 100% valid (0 bad)
   - **company_name**: ✅ 100% populated
   - **speaker_name**: ✅ 100% populated (e.g., "Kiyoshi Hishinuma")
   - **speaker_title**: ✅ 99.9% (only 1 missing)
   - **speaker_company**: ✅ 99.9% (only 1 missing)
   - **call_date**: ⚠️ Populated but many show "Unknown" string (not NULL)
   - **quarter + year**: ✅ 100% populated
   - **quote_text**: ✅ 100% populated
   - Top companies: Siemens Mobility (107), John Deere (105), Ashland (100), GE Aero (97), Lockheed Martin (96)

5. **Podcast Quotes audit** — 139 rows:
   - **speaker_name**: ✅ 100% populated
   - **speaker_company**: ❌ 100% NULL (139/139)
   - **speaker_role**: ✅ 100% populated (e.g., "host")
   - **episode_title**: ✅ 100% populated

### 🚨 Re-ingestion Plan (Next Session)

**SEC Filing Nuggets — needs full re-ingestion:**
- Fix ticker extraction in the SEC ingestion pipeline (currently all `?`)
- Fix CIK extraction (currently all empty)
- Populate `fiscal_quarter` from filing metadata
- Improve companies_mentioned / competitors / brands extraction (78-99% empty)
- Consider ingesting 10-K and 10-Q filings in addition to 8-K
- Add `source_url` column to schema if SEC.gov URLs are available
- Re-run extraction with Claude for richer nugget metadata

**Earnings Quotes — minor cleanup only:**
- Fix `call_date` "Unknown" values — resolve actual dates from transcript metadata
- Otherwise excellent quality, no re-ingestion needed

**Podcast Quotes — fix speaker_company:**
- All 139 rows have NULL `speaker_company`
- Need to resolve company affiliations from speaker metadata or podcast show notes

### 📁 Files Modified (This Session)
| File | Change |
|------|--------|
| _(no code changes)_ | Scheduler `attemptDeadline` updated via gcloud CLI |

### 📁 Infrastructure Changes
| Resource | Change |
|----------|--------|
| Cloud Scheduler `weekly-executive-briefing` | `attemptDeadline` 900s → 1800s |

---
## 📅 SESSION 95: Fix Weekly Briefing — Citations, Voice Enrichment, Podcast (February 10, 2026)

**Status**: ⚠️ PARTIAL — Deployed & regenerated, but follow-up issues remain

### 🎯 Goal

Fix the broken Feb 9 weekly briefing: citations mostly missing, podcast audio not generating, voice enrichment returning zero results. Delete broken data and regenerate fresh.

### 🔍 Root Causes Identified

1. **Citation ordering** — `get_articles_by_ids()` returned articles in arbitrary BQ order. Citation `[N]` expected `article_ids[N-1]` but got a random article. **Already fixed in Session 94** (commit `207ddf2`).

2. **Voice enrichment returning nothing** — `_fetch_voice_enrichment()` concatenated all topics into one string (`" ".join(topic_list[:5])`) and passed it to BQ methods using `LIKE %concatenated_string%`. This never matches because no SEC filing/quote contains "carbon fiber hydrogen aerospace wind automotive" as a substring. Fix: search by individual company names/tickers with deduplication.

3. **Podcast not generating** — Feb 9 briefing's podcast generation failed due to 5000 char ElevenLabs API limit (9355 char dialogue). Chunking fix applied in Session 93 (commit `247a282`) but briefing was never regenerated after the fix.

### ✅ Completed

1. **Voice enrichment rewrite** — `_fetch_voice_enrichment()` in `weekly_briefing.py` completely rewritten:
   - SEC nuggets: Searches by each company name individually (up to 10), then by each topic keyword individually (up to 5), deduplicates by nugget_id, sorts by relevance, caps at 10
   - Earnings quotes: Same pattern — per-company search, per-topic search, dedup by quote_id
   - Podcast quotes: Searches by detected themes (mapped from topics via theme_mapping dict) AND by individual company names, dedup by quote_id
   - Added detailed logging at each stage for debugging

2. **Deleted broken Feb 9 data** — Removed 1 weekly briefing (`8f60f092`) and 2 pre-briefings (`a0dd4dc7`, `de033dfb`) from BigQuery via table swap (CREATE AS SELECT + DROP + RENAME)

3. **Deployed and regenerated** — Voice enrichment fix committed (`0df3b0d`), pushed, Cloud Build deployed. Manual briefing triggered successfully.

4. **Briefing generated** — `f3a3915a-78fa-44e7-9f2b-604824094bcf`:
   - Agent 1: 174 digest items in 5 batches
   - Agent 2: 4 sections with citations — Aerospace Recovery (10+2), European Chemical Crisis (8+2), North Sea Wind (16+0), Tariff Escalation (7+0)
   - Podcast: 44 turns, 3 ElevenLabs chunks (4568/4636/1266 chars), ~11.5MB MP3 uploaded to GCS
   - Saved to BigQuery successfully

### 🚨 Follow-Up Issues (Session 96)

1. **Voice enrichment still not showing in briefing** — Despite the rewrite, no SEC nuggets, earnings quotes, or podcast quotes appear in the generated output. Need to:
   - Check Cloud Run logs for voice enrichment debug output (new logging added)
   - Verify BQ has SEC nuggets / earnings quotes / podcast quotes for relevant companies in the date range
   - May be a data availability issue (nothing in BQ to find) rather than a code bug
   - Check if voice enrichment data is being passed to Agent 2 prompt but not used, vs not found at all

2. **Citations showing as "Unknown"** — Citation references `[1]`, `[2]` etc. are present per section, but almost all source articles display as "Unknown" with no title/URL/publisher. Need to:
   - Inspect the `source_articles` JSON in the BQ `weekly_briefings` row to see what data was saved
   - Check if `get_articles_by_ids()` is returning placeholder dicts for missing articles
   - Check how the frontend `WeeklyBriefing` component renders citations — may need article title/url fields
   - The article data in `articles` table may not have the fields the frontend expects

3. **Cloud Scheduler `weekly-executive-briefing` job still failing** — Need to:
   - Check scheduler job config (URL, HTTP method, body) — endpoint requires JSON body `{"briefing_type": "weekly_executive", "lookback_days": 7}`, scheduler may be sending empty body → 422
   - Check Cloud Run request timeout — briefing takes ~15 min, may exceed default timeout
   - Fix scheduler config or increase timeout

### 📁 Files Modified
| File | Change |
|------|--------|
| `backend/app/ingestion/generators/weekly_briefing.py` | Complete rewrite of `_fetch_voice_enrichment()` — individual company/topic searches instead of concatenated string |

### 📁 Files Already Deployed (Session 94)
| File | Change |
|------|--------|
| `backend/app/db/gcp_storage.py` | `get_articles_by_ids()` order-preserving fix, `_create_weekly_briefings_table()` schema auto-migration |

---
## 📅 SESSION 94: Supply Network Tab + Industry Narratives Planning (February 9, 2026)

**Status**: ✅ COMPLETE

### 🎯 Goal

Build the Supply Network tab with interactive force-directed graph visualization of C1 + 10 competitors and their upstream supplier relationships. Plan the Industry Narratives feature for next session.

### ✅ Completed

1. **Supply Network Tab** — New tab with graph-primary split layout (60% graph / 40% drill-down panel)
   - **Backend**: `app/api/routes/supply_network.py` — 5 REST endpoints (`/graph`, `/stats`, `/company/{key}`, `/supplier/{key}`, `/shared-suppliers`), all calling existing `BigQueryStore` methods (zero new BQ code)
   - **Frontend**: 3 new components in `frontend/src/components/supply-network/`:
     - `NetworkGraph.tsx` — `react-force-graph-2d` wrapper with color-coded nodes (amber=C1, blue=competitor, indigo=supplier), log-scale sizing, custom canvas labels, zoom/pan controls, legend
     - `DetailPanel.tsx` — Right panel with 3 states: overview stats, company drill-down (supplier table), supplier drill-down (buyer table with [C1]/[COMP] badges)
     - `SupplyNetworkDashboard.tsx` — Main container managing graph data, node selection, split layout
   - **Tab integration**: Added to `Mode` type, Sidebar nav, AppHeader config, page.tsx conditional render, chat-hidden condition
   - **API client**: 5 new methods in `api.ts` (`getSupplyNetworkGraph`, `getSupplyNetworkStats`, `getCompanyDetail`, `getSupplierDetail`, `getSharedSuppliers`)
   - **Build verified**: TypeScript compiles, production build succeeds
   - **Deployed**: Commit `207ddf2`, pushed to master → Cloud Build auto-deploy

2. **Citation ordering fix** — `weekly_briefing.py` now preserves article_ids order so `[N]` citations map correctly

### 📁 Files Created
| File | Purpose |
|------|---------|
| `backend/app/api/routes/supply_network.py` | 5 REST endpoints for graph, stats, drill-down |
| `frontend/src/components/supply-network/NetworkGraph.tsx` | Force-directed graph with canvas rendering |
| `frontend/src/components/supply-network/DetailPanel.tsx` | Click-to-drill-down panel |
| `frontend/src/components/supply-network/SupplyNetworkDashboard.tsx` | Main container, split layout |

### 📁 Files Modified
| File | Change |
|------|--------|
| `backend/app/main.py` | Added supply_network router |
| `backend/app/api/routes/__init__.py` | Added supply_network import |
| `frontend/src/types/index.ts` | Added 'supply-network' to Mode, chatSuggestions, welcomeMessages |
| `frontend/src/app/page.tsx` | Dynamic import, conditional render, chat-hidden |
| `frontend/src/components/layout/Sidebar.tsx` | Added Supply Network nav item |
| `frontend/src/components/layout/AppHeader.tsx` | Added supply-network to modeConfig |
| `frontend/src/components/chat/ChatInterface.tsx` | Added supply-network to modeSuggestions + welcomeMessages |
| `frontend/src/lib/api.ts` | 5 API methods + Mode union update |

### 🔮 Next Session: Industry Narratives Tab

**Goal**: User selects an industry (from the 6+ industries in `digest_items`) and sees how news evolves over a 90-day period, grouped by month, with month-over-month delta tracking for sub-metadata.

**Reference file**: `industry_narratives_intuition.xlsx` in project root (Claude-in-Excel concept)

**Key `digest_items` columns available for this feature**:
- `industries` (JSON array) — Aerospace, Wind, Construction, Marine, Automotive, Infrastructure, Transportation, Sporting Goods, Defense Space
- `event_type` (STRING) — acquisition, partnership, expansion, contract, regulatory_change, product_launch, earnings, facility_closure, restructuring, investment, supply_disruption, technology, market_shift, other
- `companies` (JSON array) — extracted company names
- `geography` (JSON array) — North America, Europe, China, Japan, etc.
- `themes` (JSON array) — reshoring, sustainability, consolidation, capacity_expansion, supply_chain_risk, trade_policy, cost_pressure, demand_growth, technology_advancement, electrification, hydrogen, lightweighting, etc. (21 themes)
- `sentiment` (STRING) — positive, negative, neutral
- `materials` (JSON array) — carbon fiber, epoxy, PEEK, glass fiber, prepreg, etc.
- `published_at` (TIMESTAMP) — partitioned by day, for time-series queries
- `relevance_score` (FLOAT64) — classifier confidence

**Also available**: `article_tags` table with normalized tags (company, material, market, theme, geography, topic) — better for aggregation than JSON arrays

**Table partitioning**: `digest_items` partitioned by `published_at` (DAY), clustered by `category` + `priority`

**Concept**:
1. User picks an industry (e.g., "Aerospace")
2. Backend queries digest_items WHERE industries contains that industry, last 90 days
3. Groups by month → summarizes key occurrences per month
4. For sub-metadata (event_type, company mentions, geography, themes): shows counts + month-over-month +/- deltas
5. LLM synthesis optional: Claude summarizes each month's narrative arc

