# Industry Narratives Tab Documentation

## Overview

The Industry Narratives tab provides a 90-day timeline view of how news narratives evolve across composites end-markets. It combines data-driven monthly breakdowns with on-demand LLM narrative synthesis that weaves together article trends, executive earnings commentary, and SEC filing disclosures into a cohesive story arc.

## Architecture

### Frontend
- **Hook**: `frontend/src/hooks/useIndustryNarratives.ts` — State management for industries, timeline, and narrative generation
- **Dashboard**: `frontend/src/components/industries/IndustriesDashboard.tsx` — Main timeline UI with month columns
- **API Client**: `frontend/src/lib/api.ts` — `getIndustryNarrativesList()`, `getIndustryTimeline()`, `getIndustryArticles()`, `generateIndustryNarrative()`

### Backend
- **Routes**: `backend/app/api/routes/industry_narratives.py` — 4 endpoints (3 GET + 1 POST)
- **Data Source**: BigQuery `digest_items` table — classified articles with JSON array columns (`industries`, `companies`, `themes`, `geography`)
- **Enrichment**: BigQuery `earnings_quotes` and `sec_filing_nuggets` tables via `BigQueryDataStorage`
- **LLM**: Claude Sonnet 4.6 via `get_resilient_async_client()` with OpenAI fallback

---

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/industry-narratives/industries` | Curated industry list with 90-day article counts and trends |
| GET | `/api/industry-narratives/{industry}/timeline` | Monthly aggregated data with MoM deltas |
| POST | `/api/industry-narratives/{industry}/narrative` | On-demand LLM narrative synthesis |
| GET | `/api/industry-narratives/{industry}/articles` | Paginated article drill-down with filters |

### Industry Slugs

Industries are referenced by URL slug (e.g., `aerospace`, `defense_space`). The `_resolve_industry_name()` helper converts slugs back to display names.

### Curated Industries (Top 10)

1. Aerospace
2. Transportation
3. Automotive
4. Defense Space
5. Infrastructure
6. Construction
7. Industrial
8. Marine
9. Wind
10. Sporting Goods

---

## Phase 1: Data-Driven Timeline

### GET `/industries`

Returns curated industries with article counts and trend direction (up/down/flat based on last 2 months).

### GET `/{industry}/timeline`

Monthly breakdown with:
- **Article count** + delta vs prior month
- **Event types** with MoM deltas (e.g., earnings, market_shift, regulatory_change)
- **Top companies** (top 10) with MoM deltas
- **Top themes** (top 10) with MoM deltas
- **Geographies** (top 5)
- **Sentiment distribution** (positive/neutral/negative)
- **Top articles** (top 5 by relevance score)

### GET `/{industry}/articles`

Paginated article drill-down with optional filters: `month`, `event_type`, `theme`, `sentiment`.

---

## Phase 2: LLM Narrative Synthesis

### POST `/{industry}/narrative`

On-demand generation triggered by "Generate Narrative" button in the UI. Produces a cohesive story arc — not just theme summaries.

### Data Flow

```
User clicks "Generate Narrative" for Aerospace
        │
        ▼
1. Reuse timeline data (calls get_industry_timeline internally)
   → Extract top 8 companies across all months
        │
        ▼
2. Parallel enrichment queries (asyncio.gather)
   ├─ earnings_quotes: search by each of top 8 companies
   └─ sec_filing_nuggets: search by each of top 8 companies
   → Deduplicate by ID, sort by relevance, cap at 10 each
        │
        ▼
3. Build prompt with:
   ├─ Compressed monthly data (counts, deltas, top 5 companies/themes/events)
   └─ Enrichment context (formatted earnings quotes + SEC nuggets)
        │
        ▼
4. Claude Sonnet 4.6 call (~8-15s)
   → industry_narrative (3-5 sentences)
   → monthly_narratives[] (2-3 sentences each)
   → key_insight (1 sentence)
        │
        ▼
5. Frontend renders:
   ├─ Purple gradient banner (90-day arc + key insight)
   └─ Per-month narrative cards inside each MonthColumn
```

### Response Shape

```json
{
  "industry": "Aerospace",
  "industry_narrative": "Over the past 90 days...",
  "monthly_narratives": [
    {"month": "2025-12", "narrative": "December featured..."},
    {"month": "2026-01", "narrative": "January was marked by..."},
    {"month": "2026-02", "narrative": "February saw..."}
  ],
  "key_insight": "The most significant shift was...",
  "enrichment_sources_used": 14,
  "generated_at": "2026-02-09T14:30:00Z"
}
```

### Enrichment Sources

| Source | Table | Method | What It Provides |
|--------|-------|--------|-----------------|
| Earnings quotes | `earnings_quotes` | `bq_storage.get_earnings_quotes()` | Executive commentary from quarterly calls |
| SEC filings | `sec_filing_nuggets` | `bq_storage.get_sec_filing_nuggets()` | Regulatory disclosures, risk factors, material changes |

### LLM Prompt Design

The system prompt positions Claude as a composites industry analyst writing for C1's executive leadership. The prompt emphasizes:
- **Story over summary** — causality and connections, not theme lists
- **Inflection points** — what changed and why
- **Corroboration** — how articles, earnings quotes, and SEC filings confirm or contradict each other
- **Actionability** — specific takeaways for a composites distributor

---

## Frontend UI

### Industry Selector
Horizontal pill bar at the top. Each pill shows industry name, article count, and trend arrow. Active pill is purple.

### Summary Stats Bar
Shows Total Articles, Avg/Month, Trend direction, and the **Generate Narrative** button (purple with Sparkles icon).

### Narrative Banner
Only visible after generation. Purple gradient card with:
- 90-day narrative arc (3-5 sentences)
- Key insight callout
- Enrichment source count

### Monthly Columns
Each month renders as a card with:
1. **Month narrative** (if generated) — light purple card with Sparkles icon
2. Event types with deltas
3. Top companies with deltas
4. Themes as pills with counts and deltas
5. Geographies (collapsed by default)
6. Sentiment bar
7. Key articles (clickable)
8. "View all N articles" footer (opens article drawer)

### Article Drawer
Right-side slide-over panel showing paginated articles with title, summary, source, event type, and sentiment badge.

---

## Testing

### Backend
```bash
# Verify imports
cd backend
python -c "from app.api.routes.industry_narratives import router; print(f'Routes: {len(router.routes)}')"

# Test endpoint locally
curl http://localhost:8000/api/industry-narratives/industries
curl http://localhost:8000/api/industry-narratives/aerospace/timeline
curl -X POST http://localhost:8000/api/industry-narratives/aerospace/narrative
```

### Frontend
```bash
cd frontend
npx tsc --noEmit    # Type check
npm run build       # Production build
```

### Manual
1. Navigate to Industries tab
2. Select an industry (e.g., Aerospace)
3. Verify monthly columns load with data
4. Click "Generate Narrative"
5. Verify purple banner appears with narrative text
6. Verify per-month narrative cards appear in each column
7. Click "View all N articles" to test drawer

---

## Troubleshooting

### Issue: No industries appear
- Check BigQuery `digest_items` table has articles with `industries` JSON array
- Verify `CURATED_INDUSTRIES` list matches values in the data (case-insensitive)

### Issue: Narrative generation times out
- Default timeout is 120s; check Cloud Run logs for LLM call timing
- Verify `ANTHROPIC_API_KEY` is valid; fallback to OpenAI if needed
- Check enrichment queries aren't stalling (BigQuery connection)

### Issue: Empty enrichment (0 sources)
- Check `earnings_quotes` and `sec_filing_nuggets` tables have data
- Verify company names from timeline match what's in enrichment tables
- The endpoint still generates narratives without enrichment — just less detailed

### Issue: JSON parse failure (502)
- LLM occasionally returns malformed JSON; retry usually works
- Check logs for `Failed to parse LLM JSON` to see raw response
- The code strips markdown fences (```` ``` ````) but edge cases may occur

---

## Related Files

| File | Purpose |
|------|---------|
| `backend/app/api/routes/industry_narratives.py` | All 4 endpoints + enrichment logic + LLM prompt |
| `frontend/src/hooks/useIndustryNarratives.ts` | Hook with timeline + narrative state |
| `frontend/src/lib/api.ts` | API client methods |
| `frontend/src/components/industries/IndustriesDashboard.tsx` | Full dashboard UI |
| `backend/app/db/gcp_storage.py` | `BigQueryDataStorage` for enrichment queries |
| `backend/app/utils/resilient_llm.py` | `get_resilient_async_client()` with fallback |
