# Briefing Generators

This directory contains the AI-powered briefing generation system for the C1 Intelligence Hub.

## Architecture Overview

The weekly executive briefing uses a **2-agent pipeline**:

```
┌─────────────────────────────────────────────────────────────────┐
│                    Weekly Briefing Pipeline                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────┐          ┌────────────────────────┐        │
│  │   Agent 1       │          │        Agent 2         │        │
│  │   Pre-Brief     │ ──────►  │ Executive Synthesizer  │ ─────► │
│  │   Generator     │          │                        │        │
│  │                 │          │ • Historical context   │◄─┐     │
│  │   claude-sonnet │          │ • Voice enrichment     │  │     │
│  │   (fast, cheap) │          │ • Exa peripheral       │  │     │
│  └─────────────────┘          │ • Source linking       │  │     │
│         │                     │ • BLUF generation      │  │     │
│         │                     │                        │  │     │
│         │                     │   claude-opus-4-5      │  │     │
│         ▼                     │   (high quality)       │  │     │
│   pre_briefings table         └────────────────────────┘  │     │
│                                          │                │     │
│                                          ▼                │     │
│                               ┌──────────────────────┐    │     │
│                               │ Podcast Generation   │    │     │
│                               │ • Format for speech  │────┘     │
│                               │ • ElevenLabs TTS     │          │
│                               │ • Upload to GCS      │          │
│                               │                      │          │
│                               └──────────────────────┘          │
│                                          │                      │
│                                          ▼                      │
│                               weekly_briefings table            │
│                               + podcast.mp3 in GCS              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Files

| File | Purpose |
|------|---------|
| `pre_briefing.py` | **Agent 1** - Analyzes articles, produces structured observations with signal_types |
| `weekly_briefing.py` | **Agent 2** - Synthesizes pre-brief into executive briefing with sections |
| `bulletin_board.py` | **Priority Spotlight** - Generates 1-3 actionable bullets from HIGH/CRITICAL items |
| `briefing.py` | Legacy category-based briefings (MARKET, COMPETITOR, etc.) |
| `digest.py` | Digest item generation for the news feed |

## Weekly Briefing Output Format

Agent 2 produces briefings with this structure:

```json
{
  "id": "uuid",
  "briefing_type": "weekly_executive",
  "briefing_title": "Executive Briefing: Week of Jan 6",
  "bluf": "Single sentence high-level summary",
  "sections": [
    {
      "header": "Strategic Theme Header",
      "headline": {
        "text": "Critical development [[Company]] [1]",
        "status": "net_new",
        "companies_mentioned": ["Company"]
      },
      "insights": [...],
      "source_articles": [
        {
          "article_number": 1,
          "id": "article-uuid",
          "title": "Article Title",
          "url": "https://...",
          "source_name": "CompositesWorld",
          "published_at": "2026-01-05T..."
        }
      ],
      "companies_with_logos": [
        {"name": "Boeing", "domain": "boeing.com", "logo_url": "..."}
      ]
    }
  ],
  "key_topics_this_week": ["Topic 1", "Topic 2"],
  "overall_trend": "Detailed trend analysis",
  "podcast_url": "https://storage.googleapis.com/.../podcast.mp3",
  "podcast_duration_seconds": 245,
  "podcast_generated_at": "2026-01-06T..."
}
```

## Key Features

### Voice Enrichment (Session 93)

Before synthesis, Agent 2 pre-fetches **authoritative voice data** from three BigQuery sources to ground analysis in real quotes:

| Source | Table | Purpose |
|--------|-------|---------|
| SEC Filing Nuggets | `sec_filing_nuggets` | Legally mandated disclosures — competitive shifts, risk factors, forward guidance |
| Earnings Call Quotes | `earnings_quotes` | Executive quotes from Q&A sessions — management sentiment, market outlook |
| Industry Podcast Quotes | `podcast_quotes` | Practitioner insights — technology adoption, supply chain signals |

**How it works** (`_fetch_voice_enrichment()`):
1. Extracts topics and companies from Agent 1's pre-brief
2. Queries each BigQuery table with targeted keyword search (top 10 results each)
3. Formats into an `<enrichment_context>` block injected into the synthesis prompt
4. Agent 2 selectively weaves quotes into insights with clear attribution: `(SEC Filing)`, `(Earnings Call)`, `(Industry Podcast)`

**Guidelines for Agent 2**:
- Only include quotes that genuinely reinforce a strategic theme
- Do NOT force-fit quotes — if nothing is relevant, proceed without
- Attribute clearly: "As [Speaker], [Role] at [Company] noted in [Source]..."

Each enrichment fetch is wrapped in try/except so a single source failure doesn't break the pipeline.

### Podcast Generation
After Agent 2 completes, briefing text goes through a 3-step podcast pipeline:

1. **Scaffold** (`_build_podcast_dialogue()`) — Deterministic extraction of briefing content into host/analyst turns. Voice-enriched insights (containing SEC, earnings, or podcast attribution markers) get special handling with analyst delivery and host reactions.
2. **Naturalize** (`_naturalize_dialogue()`) — Claude Sonnet rewrites the scaffold into natural conversation with reactions, interjections, and varied energy. The LLM is instructed to preserve executive/expert quotes verbatim and deliver them naturally (e.g., "the CFO actually said, and I quote..."). Falls back to original scaffold on failure.
3. **TTS** (`_generate_podcast()`) — ElevenLabs Text-to-Dialogue API generates multi-voice audio

Result:
- Two voices: Host (Rachel) + Analyst (Josh)
- Storage: GCS `/podcasts/{briefing_id}.mp3`
- ~4-6 minutes for typical 3-section briefing


**Text Formatting** (`_format_text_for_speech()`):
- Removes citations: `[1]`, `[Exa:2]` → removed
- Removes company tags: `[[Boeing]]` → "Boeing"
- Expands currency: `$2.4B` → "2.4 billion dollars"
- Expands percentages: `40%` → "40 percent"

**Storage & Access**:
- GCS bucket: `gen-lang-client-0436975498-c1-hub-data`
- Path: `/podcasts/{briefing_id}.mp3`
- ⚠️ Bucket has **public access prevention** - cannot use direct GCS URLs
- Solution: Stream through backend API `/api/podcast/briefing/{briefing_id}`
- Endpoint supports HTTP Range requests (206 Partial Content) for browser audio seeking

**Configuration** (`settings.py`):
- `elevenlabs_api_key` - API key (stored in Secret Manager)
- `elevenlabs_voice_id` - Default: `21m00Tcm4TlvDq8ikWAM` (Rachel)
- `elevenlabs_model` - Default: `eleven_monolingual_v1`
- `elevenlabs_voice_stability` - Default: 0.5
- `elevenlabs_voice_similarity_boost` - Default: 0.75

### Source Article Linking
Citations like `[1]`, `[2]` in text are linked to actual articles:
- Pre-brief citations: `[N]` → articles from Agent 1's analysis
- Exa citations: `[Exa:N]` → articles from peripheral intelligence search

**Frontend UX (Session 67 update)**:
- **Hover** on citation number → shows publication domain (e.g., `reuters.com`)
- **Click** citation → opens source URL in new tab
- **Sources Footer** → grouped by domain with citation numbers (e.g., `wsj.com [1, 3], compositeworld.com [2]`)

The `_extract_citation_numbers()` method parses these from section text.
The `_extract_domain()` method extracts publication domains from URLs.

### BLUF (Bottom Line Up Front)
A single-sentence executive summary displayed prominently at the top of the briefing.

### Inline Company Logos
`[[Company Name]]` tags in text are rendered with logos from Logo.dev.

**Applies to:** Section headlines, insight text, BLUF, and `overall_trend`.

### Entity Highlighting (Session 73)
For important non-company entities in `overall_trend`, use double curly braces:
- `{{UK LSIC}}` → renders as **bold text** (no logo)
- `{{recycled PET}}` → bold highlighting for materials/technologies
- `{{PCM}}` → bold highlighting for process acronyms

Use for: Industry initiatives, material technologies, process names, standards, certifications, key programs.

### Net New vs Continuing
Each insight is tagged:
- `net_new` - First appearance of this topic
- `continuing` - Topic from previous briefings with updates

### Exa Peripheral Search
Agent 2 can use `search_peripheral_intelligence()` to find adjacent signals:
- Validates high-conviction claims
- Fills gaps in coverage
- Up to 5 iterations (search loop with scratchpad notes across iterations)

### Week Date Calculation
Briefings always reference **this week's Monday** as the period_end date:
- `_get_this_weeks_monday()` calculates the most recent Monday at midnight UTC
- Ensures manual/off-schedule runs show consistent week dates
- Prevents date drift when running multiple times
- Convention: "Week of [Monday date]"

**Example**: Running on Wednesday, Jan 7, 2026:
- `period_end` = Monday, Jan 5, 2026 (this week's Monday)
- `period_start` = 14 days before (for pre-briefing analysis)
- Displayed as: "Week of Jan 5"

This ensures the briefing title remains consistent whether run on Monday morning (scheduled) or manually on other days.

**Forced Title Override (Session 72)**:
The LLM was found to sometimes ignore the `{period_end_short}` placeholder and generate wrong dates (e.g., "Week of Jan 12" when it should be "Week of Jan 5"). As a fix, the title is now **force-overridden** after LLM response:
```python
# Title is always: "Weekly Briefing: Week of {target_monday_formatted}"
# LLM-generated title is ignored
```

### Citation Cleanup
The `_clean_citation_text()` method normalizes citations before final output:
- `[37]` → renumbered to sequential `[1]`, `[2]`, etc.
- `[Exa:6]` → same renumbering (Exa prefix stripped)
- `[37, Exa:6]` → split and renumbered (handles mixed citations)
- Final output contains only clean `[N]` references

**Session 72 Fix**: Previously, comma-separated mixed citations like `[37, Exa:6]` weren't properly processed. The regex now parses each bracket's contents, splitting on commas.

### Backfilling Historical Briefings
To rebuild historical context chain (needed for net_new vs continuing classification):

```bash
cd backend

# Backfill all 3 historical weeks
python scripts/operations/backfill_briefings.py

# Single week only (1=oldest, 3=newest)
python scripts/operations/backfill_briefings.py --week 1

# Verify results
python scripts/operations/backfill_briefings.py --verify

# Include podcast generation
python scripts/operations/backfill_briefings.py --with-podcast
```

**Backfill Order** (chronological, establishes context chain):
1. Week 1: period_end = Dec 22 (Dec 8-22 articles)
2. Week 2: period_end = Dec 29 (Dec 15-29 articles)  
3. Week 3: period_end = Jan 5 (Dec 22-Jan 5 articles)

Each week's Agent 2 looks at previous `weekly_briefings` for historical context.

## Schedule

| Job | Schedule | Description |
|-----|----------|-------------|
| `weekly-executive-briefing` | Monday 8:30 AM CST | Full 2-agent pipeline |

## Usage

### Generate Briefing Manually

```python
from app.ingestion.generators.weekly_briefing import generate_weekly_briefing

# Runs both Agent 1 and Agent 2
briefing = await generate_weekly_briefing()
```

### Generate Pre-Brief Only

```python
from app.ingestion.generators.pre_briefing import PreBriefGenerator

agent1 = PreBriefGenerator()
pre_brief = await agent1.generate_pre_brief(days=14)
```

### Trigger via API

```bash
# POST to scheduler endpoint
curl -X POST https://c1-hub-4iz75bvpyq-uc.a.run.app/api/v1/scheduler/briefing
```

## Storage

Both pre-briefs and final briefings are stored in BigQuery:
- `pre_briefings` - Agent 1 intermediate output
- `weekly_briefings` - Agent 2 final output

See `backend/app/db/gcp_storage.py` for schema details.

## Troubleshooting

### Testing Locally

```bash
cd backend

# Test Agent 2 with latest pre-brief (generates and saves to BigQuery)
python scripts/testing/test_agent2_save.py

# Simple LLM connectivity test
python scripts/testing/test_llm_simple.py

# Check briefings in BigQuery
python -c "from google.cloud import bigquery; c = bigquery.Client(); \
  r = list(c.query('SELECT briefing_title, generated_at FROM \
  \`gen-lang-client-0436975498.c1_intelligence.weekly_briefings\` \
  ORDER BY generated_at DESC').result()); \
  [print(f'{x.generated_at}: {x.briefing_title}') for x in r]"
```

### Cloud Run Log Filters

Use these prefixes to filter logs in Cloud Run:

| Prefix | Purpose |
|--------|---------|
| `[BQ_SAVE]` | BigQuery save operations (success/failure) |
| `[SAVE]` | Briefing save path in `_save_briefing()` |
| `Agent 2:` | Executive synthesizer LLM calls and responses |

### Common Issues

**Briefing returns 200 but no row in BigQuery**
- Check logs for `[BQ_SAVE]` errors
- `_save_briefing()` now re-raises exceptions (previously swallowed)
- Look for schema mismatches or serialization errors

**Empty LLM response / JSON parse error**
- Anthropic API can occasionally return empty content
- Check for `stop_reason` in logs - should be `end_turn`
- If persistent, check API status or credits

**Pre-brief exists but Agent 2 fails**
- Verify pre-brief has valid `data` field with `observations`
- Check `article_count` > 0 and `article_ids` populated
