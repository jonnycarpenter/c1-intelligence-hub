# Weekly Executive Briefing System - Complete Technical Overview

This document provides a comprehensive end-to-end overview of the C1 Intelligence Hub's Weekly Briefing system, covering both backend generation logic and frontend rendering implementation.

## Table of Contents
1. [System Architecture](#system-architecture)
2. [Backend: 2-Agent Pipeline](#backend-2-agent-pipeline)
3. [Backend: Podcast Generation](#backend-podcast-generation)
4. [Backend: Data Storage](#backend-data-storage)
5. [Backend: API Endpoints](#backend-api-endpoints)
6. [Frontend: Data Flow](#frontend-data-flow)
7. [Frontend: Component Architecture](#frontend-component-architecture)
8. [Frontend: Text Rendering Engine](#frontend-text-rendering-engine)
9. [Frontend: Interactive Features](#frontend-interactive-features)
10. [Scheduling & Automation](#scheduling--automation)

---

## System Architecture

The weekly executive briefing system is a full-stack AI-powered intelligence product that:
- **Ingests** 50+ articles from the last 14 days
- **Analyzes** strategic patterns using a 2-agent LLM pipeline
- **Generates** podcast narration via ElevenLabs TTS
- **Renders** rich, interactive briefing cards in the frontend

### High-Level Data Flow

```
┌─────────────────────┐
│  BigQuery Articles  │ (Source of Truth: 3,000+ articles)
│   14-day lookback   │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│    Agent 1          │ claude-sonnet-4-5
│  Pre-Brief Gen      │ • Analyzes articles
│                     │ • Identifies signal_types
│                     │ • Detects patterns
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  pre_briefings      │ (BigQuery intermediate storage)
│  table              │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│    Agent 2          │ claude-opus-4-5
│  Executive Synth    │ • Compares to history
│                     │ • Exa peripheral search
│                     │ • Generates sections
│                     │ • Links citations
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Podcast Generation │ ElevenLabs TTS
│                     │ • Format text for speech
│                     │ • Generate MP3 audio
│                     │ • Upload to GCS
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ weekly_briefings    │ (BigQuery + GCS storage)
│ table + podcast.mp3 │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  API Endpoints      │ /api/briefing/latest
│                     │ /api/podcast/briefing/{id}
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Frontend React     │ WeeklyBriefingSection.tsx
│  Components         │ • Fetches latest briefing
│                     │ • Renders sections
│                     │ • Logo resolution
│                     │ • Citation linking
└─────────────────────┘
```

---

## Backend: 2-Agent Pipeline

### Agent 1: Pre-Brief Generator
**File:** `backend/app/ingestion/generators/pre_briefing.py`  
**Model:** `claude-sonnet-4-5` (fast, cost-effective)  
**Input:** Last 50 articles from 14-day window (from BigQuery `articles` table)  
**Output:** JSON pre-brief stored in `pre_briefings` table

**Responsibilities:**
1. **Article Analysis**: Reviews article summaries, metadata, entities
2. **Signal Detection**: Identifies strategic patterns (e.g., supply chain disruption, market expansion)
3. **Preliminary Observations**: Structured notes on key developments
4. **Signal Type Classification**: Tags each observation (market_shift, regulatory, competitive, etc.)

**Key Methods:**
- `_get_articles(start_date, end_date)`: Queries BigQuery for article window
- `generate_pre_brief(days=14)`: Main orchestration, calls LLM and saves result

**Output Schema:**
```json
{
  "id": "uuid",
  "period_start": "2026-01-01T00:00:00Z",
  "period_end": "2026-01-15T00:00:00Z",
  "article_count": 50,
  "article_ids": ["uuid1", "uuid2", ...],
  "data": {
    "observations": [
      {
        "theme": "Strategic Theme",
        "signal_type": "market_expansion",
        "details": "Observation text with [[Company Name]] and [1] citations"
      }
    ]
  }
}
```

---

### Agent 2: Executive Synthesizer
**File:** `backend/app/ingestion/generators/weekly_briefing.py`  
**Model:** `claude-opus-4-5` (highest quality reasoning)  
**Input:** Latest pre-brief + historical briefing context (from `weekly_briefings` table)  
**Output:** Final executive briefing with sections, BLUF, and citations

**Responsibilities:**
1. **Historical Context Integration**: Compares current pre-brief against prior 3 weeks to classify insights as:
   - `net_new`: First appearance of topic
   - `continuing`: Updates to ongoing topics
2. **Peripheral Intelligence Search**: Uses Exa search tool to fill gaps (limited to 3 searches)
3. **Section Generation**: Structures insights into thematic sections (e.g., "Aerospace Demand Signals")
4. **Citation Linking**: Maps `[N]` and `[Exa:M]` references to actual article URLs
5. **BLUF Creation**: Single-sentence "Bottom Line Up Front" executive summary
6. **Company Extraction**: Identifies companies mentioned in each section, resolves domains for logo.dev

**Key Methods:**
- `_get_historical_context()`: Fetches last 3 briefings with full BLUF, sections, and trends
- `_extract_citation_numbers(text)`: Parses `[1]`, `[Exa:2]` patterns from text
- `_clean_citation_text(text, pre_brief_article_ids, exa_article_ids)`: Renumbers citations to sequential `[1]`, `[2]`
- `_format_text_for_speech(text)`: Removes tags, expands currency/percentages for TTS
- `generate_weekly_briefing()`: Main orchestration

**Output Schema:**
```json
{
  "id": "uuid",
  "briefing_type": "weekly_executive",
  "briefing_title": "Weekly Briefing: Week of Jan 6",
  "bluf": "Single sentence executive summary",
  "period_start": "2026-01-01T00:00:00Z",
  "period_end": "2026-01-15T00:00:00Z",
  "article_count": 50,
  "sections": [
    {
      "header": "Aerospace Demand Signals",
      "headline": {
        "text": "[[Boeing]] secures $2.4B order for 737 MAX aircraft [1]",
        "status": "net_new",
        "companies_mentioned": ["Boeing"]
      },
      "insights": [
        {
          "text": "Production ramp expected to drive 40% increase in composite demand [2]",
          "status": "continuing"
        }
      ],
      "source_articles": [
        {
          "article_number": 1,
          "id": "article-uuid",
          "title": "Boeing Wins Major Order",
          "url": "https://reuters.com/...",
          "source_name": "Reuters",
          "published_at": "2026-01-05T..."
        }
      ],
      "companies_with_logos": [
        {
          "name": "Boeing",
          "domain": "boeing.com",
          "logo_url": "https://logo.dev/boeing.com"
        }
      ]
    }
  ],
  "key_topics_this_week": ["Aerospace", "Defense", "Supply Chain"],
  "overall_trend": "Longer analysis of macro patterns across sections",
  "podcast_url": "gs://bucket/podcasts/{briefing_id}.mp3",
  "podcast_duration_seconds": 245,
  "podcast_generated_at": "2026-01-15T..."
}
```

**Special Features:**
- **Forced Title Override (Session 72)**: LLM-generated title is ignored; always uses calculated Monday date
- **Citation Cleanup**: Handles mixed citations like `[37, Exa:6]` → renumbered to `[1]`, `[2]`
- **Entity Highlighting**: Double curly braces `{{UK LSIC}}` for non-company entities (rendered as bold)
- **Inline Logos**: `[[Company Name]]` tags trigger logo.dev resolution

---

## Backend: Podcast Generation

**File:** `backend/app/ingestion/generators/weekly_briefing.py`  
**Service:** ElevenLabs Text-to-Speech API  
**Voice:** Rachel (`21m00Tcm4TlvDq8ikWAM`)  
**Model:** `eleven_monolingual_v1`

### Text Formatting for Speech
**Method:** `_format_text_for_speech(text)`

**Transformations:**
1. Remove citations: `[1]`, `[Exa:2]` → removed
2. Remove company tags: `[[Boeing]]` → "Boeing"
3. Expand currency: `$2.4B` → "2.4 billion dollars"
4. Expand percentages: `40%` → "40 percent"
5. Natural phrasing: Inserts "net new" vs "continuing" language

**Example Input:**
```
[[Boeing]] secures $2.4B order for 737 MAX aircraft [1]. Production ramp expected to drive 40% increase [2].
```

**Example Output (for TTS):**
```
Boeing secures 2.4 billion dollars order for 737 MAX aircraft. Production ramp expected to drive 40 percent increase.
```

### Podcast Script Building
**Method:** `_build_podcast_script(briefing_data, pre_brief)`

**Structure:**
1. **Opening**: "This week's intelligence briefing for [date range]"
2. **BLUF Narration**: Reads bottom line
3. **Section Narration**: For each section:
   - Reads header
   - Reads headline with "This is a net new development" OR "This continues from prior weeks"
   - Reads 2-3 top insights
4. **Closing**: "This concludes the intelligence briefing"

**Duration:** ~4-6 minutes for typical 3-section briefing

### Storage & Streaming
- **GCS Bucket:** `gen-lang-client-0436975498-c1-hub-data`
- **Path:** `/podcasts/{briefing_id}.mp3`
- **Access Control:** Bucket has public access prevention
- **Solution:** Backend proxy endpoint with HTTP Range support (allows browser audio seeking)

---

## Backend: Data Storage

### BigQuery Tables

#### `pre_briefings`
| Column | Type | Description |
|--------|------|-------------|
| `id` | STRING | UUID |
| `period_start` | TIMESTAMP | Analysis window start |
| `period_end` | TIMESTAMP | Analysis window end |
| `article_count` | INT64 | Number of articles analyzed |
| `article_ids` | ARRAY\<STRING\> | UUIDs of source articles |
| `data` | JSON | Agent 1 output (observations, signal_types) |
| `generated_at` | TIMESTAMP | Creation timestamp |

#### `weekly_briefings`
| Column | Type | Description |
|--------|------|-------------|
| `id` | STRING | UUID |
| `briefing_type` | STRING | Always "weekly_executive" |
| `briefing_title` | STRING | "Weekly Briefing: Week of [date]" |
| `bluf` | STRING | Bottom Line Up Front summary |
| `period_start` | TIMESTAMP | Analysis window start |
| `period_end` | TIMESTAMP | This week's Monday at 00:00 UTC |
| `article_count` | INT64 | Number of articles analyzed |
| `data` | JSON | Sections, insights, citations, logos |
| `key_topics_this_week` | ARRAY\<STRING\> | Topic tags |
| `overall_trend` | STRING | Macro trend analysis |
| `podcast_url` | STRING | GCS path to MP3 |
| `podcast_duration_seconds` | INT64 | Audio duration |
| `podcast_generated_at` | TIMESTAMP | TTS completion time |
| `generated_at` | TIMESTAMP | Briefing creation timestamp |

### GCS Storage
- **Bucket:** `gen-lang-client-0436975498-c1-hub-data`
- **Podcast Path:** `/podcasts/{briefing_id}.mp3`
- **Access:** Private, served via backend proxy

---

## Backend: API Endpoints

### GET /api/briefing/latest
**Purpose:** Fetch the most recent weekly briefing  
**Response:** Full `weekly_briefings` JSON object  
**Frontend Hook:** `useBriefing.ts` calls this on component mount

### GET /api/podcast/briefing/{briefing_id}
**Purpose:** Stream podcast audio file  
**Features:**
- HTTP Range request support (206 Partial Content)
- Enables browser audio seeking
- Sets `Content-Type: audio/mpeg`
**Frontend Component:** `PodcastModal.tsx` consumes this

### POST /api/v1/scheduler/briefing
**Purpose:** Manually trigger briefing generation  
**Runs:** Full 2-agent pipeline + podcast generation  
**Used By:** Cloud Scheduler (Monday 8:30 AM CST)

---

## Frontend: Data Flow

### 1. Initial Load
**Component:** `PulseDashboard.tsx` (Pulse tab, left column)  
**Hook:** `useBriefing.ts`

```typescript
// On mount
const { briefing, isLoading } = useBriefing()

// Hook internally calls
const response = await fetch(`${API_BASE}/api/briefing/latest`)
const data = await response.json()
setBriefing(data)
```

### 2. Type Definitions
**File:** `frontend/src/types/briefing.ts`

```typescript
interface WeeklyBriefing {
  id: string
  briefing_type: string
  briefing_title: string
  bluf: string
  period_start: string
  period_end: string
  article_count: number
  sections: BriefingSection[]
  key_topics_this_week: string[]
  overall_trend: string
  podcast_url?: string
  podcast_duration_seconds?: number
}

interface BriefingSection {
  header: string
  headline: BriefingInsight
  insights: BriefingInsight[]
  source_articles: SourceArticle[]
  companies_with_logos: CompanyWithLogo[]
}

interface BriefingInsight {
  text: string
  status: 'net_new' | 'continuing'
  companies_mentioned?: string[]
}

interface SourceArticle {
  article_number: number | string // Can be number or "Exa:N"
  id: string
  title: string
  url: string
  source_name: string
  published_at: string
}

interface CompanyWithLogo {
  name: string
  domain: string
  logo_url?: string
}
```

### 3. Rendering Pipeline
```
WeeklyBriefingSection (root)
    ├── Header (Need to Know title, date range, podcast button)
    ├── Summary Card (BLUF + overall_trend)
    │   └── renderTextWithLogosAndCitations()
    ├── SectionCard[] (one per section)
    │   ├── Section Header (theme title + company logos)
    │   ├── Headline Insight (always visible)
    │   ├── Collapsible Insights (expandable tray)
    │   └── Sources Footer (grouped by domain)
    └── Key Topics Footer (topic badges)
```

---

## Frontend: Component Architecture

### WeeklyBriefingSection.tsx
**Path:** `frontend/src/components/dashboard/WeeklyBriefingSection.tsx`  
**Purpose:** Root component for rendering the entire briefing  
**Props:**
- `briefing`: WeeklyBriefing | null
- `isLoading`: boolean
- `onHistoryClick?`: () => void

**Render Logic:**
1. **Loading State:** 3 skeleton cards with animated pulse
2. **Empty State:** "No Weekly Briefing Yet" message
3. **Loaded State:**
   - Header with icon, title, date range, "Listen" button
   - BLUF card with collapsible `overall_trend`
   - Section cards (auto-expand first section)
   - Key topics footer

### SectionCard Component
**Purpose:** Renders individual thematic section  
**State:** `isExpanded` (default true for first section)

**Structure:**
```
┌─────────────────────────────────────────┐
│ Header: "Aerospace Demand Signals"     │ ← Section theme
│ [Boeing Logo] [Spirit Logo]            │ ← Company logos
├─────────────────────────────────────────┤
│ Headline: "Boeing secures $2.4B..."    │ ← Always visible
│ [Net New Badge]                         │
├─────────────────────────────────────────┤
│ • Insight 1 [Continuing Badge]         │ ← Collapsible tray
│ • Insight 2 [Net New Badge]            │   (expand/collapse button)
│ • Insight 3                             │
├─────────────────────────────────────────┤
│ SOURCES: reuters.com [1,3] wsj.com [2] │ ← Grouped citations
└─────────────────────────────────────────┘
```

**Collapsible Behavior:**
- **Collapsed:** Shows headline + "sneak peek" of first insight (faded, truncated)
- **Expanded:** Shows all insights in full
- **Toggle Button:** "Show N more insights" / "Hide insights"

### InsightItem Component
**Purpose:** Renders individual insight with status badge  
**Props:**
- `insight`: BriefingInsight
- `companiesWithLogos`: CompanyWithLogo[]
- `isHeadline`: boolean (larger font, no bullet)
- `isSneakPeek`: boolean (faded, truncated)

**Render:**
```
• Insight text with [[Company]] logos and [1] citations
  [Net New Badge]
```

### StatusBadge Component
**Purpose:** Visual indicator for insight novelty

**Net New Badge:**
```
┌────────────────┐
│ ⚡ NET NEW     │ (emerald-100 bg, emerald-700 text)
└────────────────┘
```

**Continuing Badge:**
```
┌────────────────┐
│ 🔄 CONTINUING  │ (slate-100 bg, slate-600 text)
└────────────────┘
```

### CompanyLogo Component
**Purpose:** Renders company logo with fallback to initials  
**Props:**
- `company`: CompanyWithLogo
- `size`: 'sm' | 'md' (default 'sm')

**Logo Resolution:**
1. **Backend Proxy:** `${API_BASE}/api/pipeline/logo/${company.domain}`
2. **Proxy Route:** `/api/pipeline/logo/:domain` → `logo.dev` API
3. **Fallback:** On image error, render initials in gray circle

**Example:**
```
[BA] ← Fallback initials for Boeing if logo fails
```

---

## Frontend: Text Rendering Engine

### renderTextWithLogosAndCitations()
**Purpose:** Parse and render special text markers in briefing content  
**Parameters:**
- `text`: string (raw text from backend)
- `companiesWithLogos`: CompanyWithLogo[] (section context)
- `sourceArticles?`: SourceArticle[] (for clickable citations)

### Supported Markers

#### 1. Citations: `[N]` or `[Exa:N]`
**Pattern:** `\[(?:Exa:)?\d+\]`  
**Rendering:**
- If `sourceArticles` provided → clickable superscript link
- Opens article URL in new tab
- Hover shows domain (e.g., `reuters.com`)
- Fallback: non-clickable superscript with tooltip

**Example:**
```
Input:  "Boeing secures order [1] for 737 MAX [Exa:2]"
Output: "Boeing secures order ¹ for 737 MAX ²"
         (¹ and ² are clickable, hover shows domains)
```

#### 2. Company Logos: `[[Company Name]]`
**Pattern:** `\[\[.*?\]\]`  
**Rendering:**
1. Extract company name
2. Find matching `CompanyWithLogo` object
3. Render bold company name + inline logo image
4. If no logo, render bold text only

**Example:**
```
Input:  "[[Boeing]] announces partnership"
Output: "Boeing [logo] announces partnership"
         (bold text + 20px logo image)
```

#### 3. Entity Highlights: `{{Entity}}`
**Pattern:** `\{\{.*?\}\}`  
**Rendering:** Bold text without logo (for industry terms, standards, materials)

**Example:**
```
Input:  "{{UK LSIC}} certification achieved"
Output: "UK LSIC certification achieved"
         (UK LSIC in semibold slate-800)
```

#### 4. Material Highlights: `{Material}`
**Pattern:** `\{[^{}]+\}`  
**Rendering:** Bold emerald-700 text (for materials/products from LLM)

**Example:**
```
Input:  "New {recycled PET} resin developed"
Output: "New recycled PET resin developed"
         (recycled PET in semibold emerald-700)
```

### Regex Split Strategy
```typescript
const parts = text.split(/(\[(?:Exa:)?\d+\]|\[\[.*?\]\]|\{\{.*?\}\}|\{[^{}]+\})/)
```

This regex creates an array alternating between:
- Plain text segments
- Special markers (citations, logos, entities)

Each marker is then replaced with its corresponding React component.

---

## Frontend: Interactive Features

### 1. Collapsible Overall Trend
**Location:** Summary card (below BLUF)  
**State:** `isOverallTrendExpanded`

**Collapsed:**
- Shows 2 lines with `line-clamp-2`
- Gradient fade at bottom
- Button: "Read full summary ▼"

**Expanded:**
- Shows full text
- Button: "Show less ▲"

### 2. Collapsible Section Insights
**Location:** Each SectionCard  
**State:** `isExpanded` (per section)

**Collapsed:**
- Shows headline only
- Shows faded "sneak peek" of first insight (truncated)
- Gradient fade effect
- Button: "Show N more insights ▼"

**Expanded:**
- Shows all insights with status badges
- Gray background tray (`slate-50/50`)
- Button: "Hide insights ▲"

### 3. Clickable Citations
**Behavior:**
- **Hover:** Tooltip shows publication domain (e.g., `wsj.com`)
- **Click:** Opens source article in new tab
- **Styling:** Emerald color (`text-emerald-600`), superscript, hover underline

### 4. Grouped Sources Footer
**Location:** Bottom of each SectionCard  
**Logic:**
```typescript
// Group articles by domain
const articlesByDomain = articles.reduce((acc, article) => {
  const domain = extractDomain(article.url)
  if (!acc[domain]) acc[domain] = []
  acc[domain].push(article)
  return acc
}, {})
```

**Render:**
```
SOURCES (5)
reuters.com [1, 3] wsj.com [2, 4] compositeworld.com [5]
```

**Interaction:**
- Clicking domain opens first article from that domain
- Hover shows all article titles from that domain (pipe-separated)

### 5. Podcast Modal
**Component:** `PodcastModal.tsx`  
**Trigger:** "Listen" button in briefing header  
**Features:**
- Play/pause control
- Seek bar (HTTP Range requests)
- Volume control
- Download button
- Displays duration in MM:SS format
- Modal overlay with close button

**Audio Source:**
```typescript
<audio src={`${API_BASE}/api/podcast/briefing/${briefing.id}`} />
```

### 6. Loading States
**Skeleton UI:**
- 3 animated pulse rectangles (400px height)
- Loading header with pulsing title and date
- Gray background (`slate-100`)

### 7. Empty State
**Displayed when:** `briefing === null`  
**Message:**
```
📫
No Weekly Briefing Yet
The weekly executive briefing will be generated every Monday at 8:30 AM CST
```

---

## Scheduling & Automation

### Cloud Scheduler Job
**Name:** `weekly-executive-briefing`  
**Schedule:** Monday 8:30 AM CST  
**Cron:** `30 14 * * 1` (14:30 UTC = 8:30 AM CST)  
**Target:** `https://c1-hub-4iz75bvpyq-uc.a.run.app/api/v1/scheduler/briefing`  
**Method:** POST  
**Execution:**
1. Triggers Agent 1 (pre-brief generation)
2. Waits for Agent 1 completion
3. Triggers Agent 2 (executive synthesis)
4. Generates podcast via ElevenLabs
5. Uploads MP3 to GCS
6. Saves briefing to BigQuery

### Week Date Calculation
**Method:** `_get_this_weeks_monday()`  
**Purpose:** Ensure consistent week dates regardless of run time

**Logic:**
```python
# Always use this week's Monday at 00:00 UTC
today = datetime.now(timezone.utc)
days_since_monday = today.weekday()  # Monday = 0
this_monday = today - timedelta(days=days_since_monday)
period_end = this_monday.replace(hour=0, minute=0, second=0, microsecond=0)
```

**Result:**
- Running on Monday, Jan 5 → period_end = Jan 5
- Running on Wednesday, Jan 7 → period_end = Jan 5 (same week's Monday)
- Title: "Weekly Briefing: Week of Jan 5"

### Manual Trigger
**PowerShell:**
```powershell
Invoke-RestMethod -Uri "https://c1-hub-4iz75bvpyq-uc.a.run.app/api/v1/scheduler/briefing" -Method POST -ContentType "application/json" -Body '{}'
```

**Use Cases:**
- Off-schedule generation for historical backfills
- Testing new prompt changes
- Regenerating after data corrections

---

## Historical Context & Backfilling

### Historical Context Integration
**Purpose:** Enable "net_new" vs "continuing" classification  
**Method:** `_get_historical_context()` in Agent 2

**Fetches:**
- Last 3 `weekly_briefings` from BigQuery
- For each: BLUF, section headers/headlines, status tags, overall_trend

**Agent 2 Prompt:**
```
You are synthesizing this week's briefing. Here are the prior 3 weeks for context:

Week of Dec 22:
- BLUF: "Defense sector expansion continues..."
- Aerospace Demand Signals (net_new): Boeing secures $1.2B order
- Supply Chain Risks (continuing): Port congestion persists

Week of Dec 29:
...

Based on this history, classify each insight as net_new or continuing.
```

### Backfill Script
**File:** `backend/scripts/operations/backfill_briefings.py`  
**Purpose:** Rebuild historical context chain for proper net_new/continuing classification

**Usage:**
```bash
# Backfill all 3 historical weeks
python scripts/operations/backfill_briefings.py

# Single week (1=oldest, 3=most recent)
python scripts/operations/backfill_briefings.py --week 1

# Verify results
python scripts/operations/backfill_briefings.py --verify

# Include podcast generation
python scripts/operations/backfill_briefings.py --with-podcast
```

**Chronological Order:**
1. Week 1: period_end = Dec 22 (analyzes Dec 8-22)
2. Week 2: period_end = Dec 29 (analyzes Dec 15-29, sees Week 1)
3. Week 3: period_end = Jan 5 (analyzes Dec 22-Jan 5, sees Weeks 1-2)

---

## Frontend Styling & Design System

### Color Palette
**Primary (Emerald):**
- `emerald-50`: Light background accents
- `emerald-100`: Card backgrounds, badges
- `emerald-200`: Borders
- `emerald-600`: Interactive elements (buttons, citations)
- `emerald-700`: Hover states

**Neutral (Slate):**
- `slate-50`: Section background trays
- `slate-100`: Borders, skeleton loaders
- `slate-400`: Helper text, timestamps
- `slate-600`: Body text
- `slate-900`: Headers, bold text

### Typography
**Headers:**
- Section headers: `text-sm font-bold uppercase tracking-wide`
- Briefing title: `text-lg font-bold`
- Main heading: `text-2xl font-extrabold tracking-tight`

**Body Text:**
- Headlines: `text-base font-semibold`
- Insights: `text-sm text-slate-700`
- Helper text: `text-xs text-slate-400`

**Citations:**
- `text-emerald-600 font-semibold`, superscript, hover underline

### Layout
**Spacing:**
- Section cards: `space-y-4` (16px vertical gap)
- Card padding: `p-5` (20px)
- Tray padding: `p-5`

**Borders:**
- Section cards: `border rounded-xl`
- First section: `border-emerald-200 ring-1 ring-emerald-50`
- Others: `border-slate-200`

**Shadows:**
- Default: `shadow-sm`
- Hover: `shadow-md` (transition 200ms)

---

## Troubleshooting

### Backend Issues

**No briefing generated despite 200 response:**
1. Check Cloud Run logs for `[BQ_SAVE]` errors
2. Verify BigQuery schema matches current model
3. Look for JSON serialization errors

**LLM returns empty response:**
1. Check `stop_reason` in logs (should be `end_turn`)
2. Verify Anthropic API credits
3. Check for rate limiting

**Podcast not generated:**
1. Verify `ELEVENLABS_API_KEY` in Secret Manager
2. Check GCS bucket permissions
3. Look for `[PODCAST_GENERATION]` logs

### Frontend Issues

**Logos not displaying:**
1. Check browser console for 404s on `/api/pipeline/logo/:domain`
2. Verify `LOGO_DEV_TOKEN` secret is mounted
3. Check `companies_with_logos` array in API response

**Citations not clickable:**
1. Verify `source_articles` array exists in section data
2. Check `article.url` is non-empty
3. Inspect browser console for React render errors

**Podcast not playing:**
1. Check audio element `src` URL in DevTools
2. Verify `/api/podcast/briefing/{id}` returns 200
3. Check `Content-Type: audio/mpeg` header
4. Test HTTP Range support (should return 206 on range request)

**Collapsible sections stuck:**
1. Check React state updates in WeeklyBriefingSection
2. Verify `isExpanded` toggle logic
3. Inspect button onClick handlers

---

## Configuration Reference

### Environment Variables (Backend)

```python
# settings.py
ANTHROPIC_API_KEY: str  # Claude models
OPENAI_API_KEY: str     # Fallback models
ELEVENLABS_API_KEY: str # Podcast generation
LOGO_DEV_TOKEN: str     # Company logos
```

### API Base URLs (Frontend)

```typescript
// lib/config.ts
export const API_BASE = process.env.NEXT_PUBLIC_API_URL || ''
// Development: http://localhost:8000
// Production: (empty, same-origin)
```

### BigQuery Configuration

```python
PROJECT_ID = "gen-lang-client-0436975498"
DATASET_ID = "c1_intelligence"
TABLES = {
    "articles": "articles",
    "pre_briefings": "pre_briefings",
    "weekly_briefings": "weekly_briefings"
}
```

### GCS Configuration

```python
BUCKET_NAME = "gen-lang-client-0436975498-c1-hub-data"
PODCAST_PATH_PREFIX = "podcasts/"
```

---

## Performance Characteristics

### Backend Timing
- **Agent 1 (Pre-Brief):** ~45-60 seconds (50 articles)
- **Agent 2 (Synthesis):** ~60-90 seconds (includes Exa searches)
- **Podcast Generation:** ~30-45 seconds (4-6 min audio)
- **Total Pipeline:** ~2.5-3 minutes end-to-end

### Frontend Load Times
- **API Fetch:** ~200-500ms (BigQuery retrieval)
- **Initial Render:** ~50-100ms (3 sections)
- **Logo Resolution:** ~100-300ms per logo (cached by browser)
- **Podcast Load:** ~1-2 seconds (streaming start, depends on file size)

### Data Sizes
- **Pre-Brief JSON:** ~10-20 KB
- **Final Briefing JSON:** ~30-50 KB
- **Podcast MP3:** ~2-4 MB (128 kbps, 4-6 min)

---

## Future Enhancements

### Planned Features
1. **Email Delivery:** Send briefing as formatted email on Monday mornings
2. **Briefing History View:** Timeline of past 12 weeks with search
3. **Custom Date Ranges:** User-selectable analysis windows
4. **Export to PDF:** Downloadable briefing report with company logos
5. **Multilingual Support:** Spanish/French translations via GPT-4
6. **Voice Selection:** User preference for podcast narrator (Rachel/Archer/etc.)
7. **Section Filtering:** Show/hide sections by topic
8. **Push Notifications:** Browser notifications when new briefing available

---

## Key Implementation Files

### Backend
| File | Purpose |
|------|---------|
| `app/ingestion/generators/pre_briefing.py` | Agent 1 - Pre-brief generation |
| `app/ingestion/generators/weekly_briefing.py` | Agent 2 - Executive synthesis + podcast |
| `app/db/gcp_storage.py` | BigQuery storage methods |
| `app/api/routes/briefing.py` | API endpoints for briefing retrieval |
| `app/api/routes/podcast.py` | Podcast streaming endpoint |
| `scripts/operations/backfill_briefings.py` | Historical context backfill utility |

### Frontend
| File | Purpose |
|------|---------|
| `components/dashboard/WeeklyBriefingSection.tsx` | Root briefing renderer |
| `components/dashboard/PodcastModal.tsx` | Audio player modal |
| `components/dashboard/PulseDashboard.tsx` | Pulse tab (hosts briefing) |
| `hooks/useBriefing.ts` | API data fetching hook |
| `types/briefing.ts` | TypeScript type definitions |
| `lib/api.ts` | API client methods |

---

## Glossary

- **BLUF:** Bottom Line Up Front - Single-sentence executive summary
- **Net New:** First appearance of a topic in briefing history
- **Continuing:** Updates to topics from prior weeks
- **Pre-Brief:** Agent 1 intermediate output (structured observations)
- **Section:** Thematic grouping of related insights (e.g., "Aerospace Demand")
- **Insight:** Individual data point or observation within a section
- **Citation:** `[N]` reference to source article
- **Exa Citation:** `[Exa:N]` reference to article from peripheral intelligence search
- **Company Tag:** `[[Company Name]]` marker for logo rendering
- **Entity Highlight:** `{{Entity}}` marker for bold non-company terms
- **Signal Type:** Classification of observation (market_shift, regulatory, etc.)
- **Peripheral Intelligence:** Exa search results to fill coverage gaps
