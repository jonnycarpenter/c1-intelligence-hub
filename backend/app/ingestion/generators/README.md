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
│  │   claude-sonnet │          │ • Exa peripheral       │  │     │
│  │   (fast, cheap) │          │ • Source linking       │  │     │
│  └─────────────────┘          │ • BLUF generation      │  │     │
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

### Podcast Generation
After Agent 2 completes, briefing text is:
- Formatted for natural speech (currency/percentages expanded)
- Narrated with natural "net new" vs "continuing" phrasing
- Generated via ElevenLabs TTS (Rachel voice, `eleven_monolingual_v1` model)
- Uploaded to GCS `/podcasts/{briefing_id}.mp3`
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

The `_extract_citation_numbers()` method parses these from section text.

### BLUF (Bottom Line Up Front)
A single-sentence executive summary displayed prominently at the top of the briefing.

### Inline Company Logos
`[[Company Name]]` tags in text are rendered with logos from Logo.dev.

### Net New vs Continuing
Each insight is tagged:
- `net_new` - First appearance of this topic
- `continuing` - Topic from previous briefings with updates

### Exa Peripheral Search
Agent 2 can use `search_peripheral_intelligence()` to find adjacent signals:
- Validates high-conviction claims
- Fills gaps in coverage
- Limited to 3 searches per briefing

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
