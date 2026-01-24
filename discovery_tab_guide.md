# Discovery Tab - AI Agent Recreation Guide

> **One-Shot Difficulty Rating: 65/100**
> 
> A capable AI agent could recreate this in 2-3 iterations. The feature is well-structured with clear patterns, but the combination of streaming SSE, tool-use agentic chat, and multiple interconnected components adds complexity.

## Overview

The Discovery tab is the primary market intelligence exploration view in the CPG Intelligence Hub. It provides:
1. **Two-column layout** - Category list (left) + Detail panel (right)
2. **AdHocBriefing input** - Simple "Ask about this week's news..." bar at top (same UX as Need to Know tab)
3. **Category cards** - Click to view DigestCards in detail panel
4. **AI Summary** - Click AI Summary button to see thematic analysis in detail panel
5. **Entity pivot** - Click entity pills on DigestCards to auto-populate the question input

### Data Configuration (Updated Jan 17, 2026)

| Parameter | Value | Description |
|-----------|-------|-------------|
| Time Window | 720 hours (30 days) | How far back to fetch articles |
| Max Items | 500 | Up from 100; ensures comprehensive coverage |
| Priorities | Critical, High, Medium | Excludes Low priority (noise reduction) |
| Confidence | ≥ 0.3 | Minimum classifier confidence |

---

## Architecture Diagram (Updated Jan 24, 2026)

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          DISCOVERY TAB                                    │
├──────────────────────────────────────────────────────────────────────────┤
│  [Live Intelligence]  Good afternoon, Team                                │
│                       We've analyzed X signals • Y critical               │
├──────────────────────────────────────────────────────────────────────────┤
│  💬 Ask about this week's news...                               [Send]   │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  BY CATEGORY (30 days)          │   DETAIL PANEL                         │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━   │   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━     │
│  ┌─────────────────────────┐   │                                         │
│  │ Competitor Moves [12] → │   │   "Select a category"                   │
│  │             [AI Summary]│   │   Click a category to view articles,    │
│  └─────────────────────────┘   │   or click AI Summary for thematic      │
│  ┌─────────────────────────┐   │   analysis                              │
│  │ Market Dynamics [8] →   │   │                                         │
│  │             [AI Summary]│   │   ── OR when category selected ──       │
│  └─────────────────────────┘   │                                         │
│  ┌─────────────────────────┐   │   [DigestCard]                          │
│  │ Product News [5] →      │   │   [DigestCard]                          │
│  │             [AI Summary]│   │   [DigestCard]                          │
│  └─────────────────────────┘   │                                         │
│  ...                           │   ── OR when AI Summary selected ──     │
│                                │                                         │
│                                │   ┌─────────────────────────────────┐   │
│                                │   │ 🌟 Strategic Themes (dark)       │   │
│                                │   │ Theme 1: Title + insight         │   │
│                                │   │ Theme 2: Title + insight         │   │
│                                │   │ 🎯 One-off summary               │   │
│                                │   └─────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## File Structure (Updated Jan 24, 2026)

```
frontend/src/
├── components/
│   ├── feed/
│   │   ├── DiscoveryView.tsx      # Main container with CategoryRow + DetailPanel
│   │   └── index.ts               # Exports
│   ├── dashboard/
│   │   └── AdHocBriefing.tsx      # Shared "Ask about..." input (used on Need to Know + Discovery)
│   ├── digest/
│   │   └── DigestCard.tsx         # Article card (175 lines)
│   └── ui/
│       └── Badge.tsx              # PriorityBadge, CategoryBadge, EntityPill
├── hooks/
│   ├── useFeed.ts                 # Feed data fetching (137 lines)
│   └── useBriefing.ts             # Ad-hoc briefing hook (shared)
├── lib/
│   ├── api.ts                     # FastAPI client
│   └── utils.ts                   # formatRelativeTime, formatCategoryLabel
└── types/
    └── index.ts                   # DigestItem, DigestStats, etc.

api/routers/
├── discovery.py                   # Streaming chat + AI Summary endpoint
└── articles.py                    # Article list/feed endpoints

backend/app/ingestion/generators/
└── discovery_summary.py           # LLM thematic analysis generator
```

---

## Component Specifications

### 1. DiscoveryView (`DiscoveryView.tsx`)

**Purpose**: Main container orchestrating the Discovery tab layout.

**Props**:
```typescript
interface DiscoveryViewProps {
  items: DigestItem[]           // All articles (30-day window)
  stats: DigestStats | null     // Aggregated statistics
  isLoading: boolean
  error: Error | null
  onSelectArticle?: (id: string) => void
}

// Ref handle for external control
interface DiscoveryViewRef {
  openAssistant: () => void
}
```

**State**:
- `isAssistantOpen: boolean` - Controls left panel visibility

**Layout**:
- Flex container with optional left panel (380px when open)
- Main content area with header + 2-column grid
- Uses `forwardRef` to expose `openAssistant()` method

**Key Logic**:
```typescript
// Dynamic greeting based on time of day
const getGreeting = () => {
  const hour = new Date().getHours()
  if (hour < 12) return 'Good morning'
  if (hour < 18) return 'Good afternoon'
  return 'Good evening'
}

// Category grouping for left column
const groupedByCategory = groupByCategory(items)

// Sort categories by: 1) high-priority count desc, 2) category priority
const sortedCategories = Array.from(groupedByCategory.entries()).sort(...)

// Right column: filter for high/critical + last 72h (client-side from fetched items)
const latestHighPriority = items.filter(
  item => isHighPriority(item.priority) &&
          isWithin72Hours(item.published_at)
)
```

**Data Fetching Configuration** (in `page.tsx`):
```typescript
// Discovery tab configuration
const digestConfig = activeMode === 'discovery'
  ? { hours: 720, limit: 500, priorities: ['Critical', 'High', 'Medium'] }
  : { hours: activeMode === 'pulse' ? 168 : 24, limit: 100 }
```

---

### 2. DiscoveryAssistant (`DiscoveryAssistant.tsx`)

**Purpose**: AI chat panel with streaming responses and tool access.

**Props**:
```typescript
interface DiscoveryAssistantProps {
  isOpen: boolean
  onClose: () => void
}
```

**Features**:
- Dark header with sparkles icon
- Empty state with quick suggestion chips
- Message bubbles (user = teal, assistant = gray)
- Source badges showing which tools were used (Corpus, Web, Podcast)
- Auto-scroll to bottom on new messages
- Loading indicator while streaming

**Quick Suggestions**:
```typescript
const SUGGESTIONS = [
  { label: "What's trending?", query: "What are the top trends..." },
  { label: "Competitor moves", query: "Show me recent competitor activity..." },
  { label: "Health trends", query: "What's happening with health and wellness..." },
  { label: "Retail signals", query: "Any notable retail or distribution news?" },
]
```

---

### 3. useDiscoveryChat Hook (`useDiscoveryChat.ts`)

**Purpose**: Manages chat state and SSE streaming connection.

**Interface**:
```typescript
interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  isStreaming?: boolean
  sourcesUsed?: string[]  // ['corpus_search', 'exa_search', 'podcast_insights']
}

function useDiscoveryChat(): {
  messages: ChatMessage[]
  isLoading: boolean
  error: string | null
  sendMessage: (text: string) => void
  clearChat: () => void
}
```

**SSE Event Types**:
```typescript
// Streaming response events from backend
{ type: 'chunk', text: string }        // Partial text
{ type: 'tool_call', tool: string }    // Tool being invoked
{ type: 'complete', sources_used: string[] }  // Final
{ type: 'error', message: string }     // Error
```

**Implementation Pattern**:
```typescript
// Use fetch with ReadableStream for POST + SSE (EventSource doesn't support POST)
fetch('/api/discovery/chat/stream', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ query, history: last10Messages })
}).then(async response => {
  const reader = response.body?.getReader()
  const decoder = new TextDecoder()
  
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    
    const chunk = decoder.decode(value, { stream: true })
    // Parse SSE lines: "data: {...}\n\n"
    for (const line of chunk.split('\n')) {
      if (line.startsWith('data: ')) {
        const data = JSON.parse(line.slice(6))
        // Handle event types...
      }
    }
  }
})
```

---

### 4. CategoryAccordion (`CategoryAccordion.tsx`)

**Purpose**: Collapsible drawer for a single category's articles.

**Props**:
```typescript
interface CategoryAccordionProps {
  category: string              // e.g., 'competitor_move'
  items: DigestItem[]           // Articles in this category
  highPriorityCount: number     // Count of high/critical items
  onSelectArticle?: (id: string) => void
  onQuickFilter?: (query: string) => void
  defaultOpen?: boolean
}
```

**Features**:
- Colored left border per category
- Icon + label + counts ("8 high • 24 total")
- Fire badge (🔥) for categories with high-priority items
- Expandable content with DigestCards
- "Show all X more →" button (capped at 15 initially)
- Items sorted by priority first, then recency

**Category Colors**:
```typescript
const categoryColors = {
  competitor_move: { border: 'border-l-rose-500', bg: 'bg-rose-50' },
  market_dynamics: { border: 'border-l-blue-500', bg: 'bg-blue-50' },
  health_regulatory: { border: 'border-l-amber-500', bg: 'bg-amber-50' },
  // ... etc
}
```

---

### 5. DigestCard (`DigestCard.tsx`)

**Purpose**: Article preview card with priority indicator and entity pills.

**Props**:
```typescript
interface DigestCardProps {
  item: DigestItem
  onSelect?: (id: string) => void
  onQuickFilter?: (query: string) => void  // Called when entity pill clicked
  compact?: boolean
  className?: string
}
```

**Features**:
- Gradient priority bar at top (critical=magenta→red, high=yellow→orange, etc.)
- Category + Priority badges
- Title with LogoText (auto-detects company names and shows logos)
- Expandable summary with "Read more"
- Entity pills (companies=blue, brands=magenta) - clickable for quick pivot
- Source link + relevance score

---

### 6. Backend: Discovery Router (`api/routers/discovery.py`)

**Endpoint**: `POST /api/discovery/chat/stream`

**Request**:
```python
class DiscoveryChatRequest(BaseModel):
    query: str
    history: List[ChatMessage] = []  # Last 10 messages for context
```

**Response**: Server-Sent Events (SSE) stream

**Tools Available**:
```python
TOOLS = [
    {
        "name": "corpus_search",
        "description": "Search article database (last 30 days only)",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "default": 5},
                "category": {"type": "string", "enum": [...]}
            },
            "required": ["query"]
        }
    },
    {
        "name": "exa_search",
        "description": "Search live web for real-time news",
        # ... similar schema
    },
    {
        "name": "podcast_insights",
        "description": "Find practitioner quotes from podcast transcripts",
        # ... similar schema
    }
]
```

**System Prompt Key Points**:
- Only has access to last 30 days of data
- Should redirect users to "Deep Research" tab for historical queries
- Use corpus_search first, then exa_search if insufficient
- Add podcast quotes to ground/legitimize findings
- Concise, actionable responses with source citations

**Implementation Flow**:
```python
async def generate():
    client = get_resilient_async_client()
    messages = build_messages_with_history(request)
    
    for iteration in range(5):  # Max 5 tool loops
        response = await client.messages_create(
            model="claude-3-5-haiku-20241022",
            tools=TOOLS,
            messages=messages,
        )
        
        tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
        
        if tool_use_blocks:
            # Execute tools, stream progress events
            yield f"data: {json.dumps({'type': 'tool_call', 'tool': name})}\n\n"
            result = await execute_tool(name, input)
            # Add to messages and continue loop
        else:
            # No more tools - stream final text in chunks
            for chunk in chunks(final_text, 20):
                yield f"data: {json.dumps({'type': 'chunk', 'text': chunk})}\n\n"
            yield f"data: {json.dumps({'type': 'complete', 'sources_used': tools_used})}\n\n"
            return

    return StreamingResponse(generate(), media_type="text/event-stream")
```

---

## Data Types

```typescript
// Core article type
interface DigestItem {
  id: string
  title: string
  headline: string | null
  summary: string | null
  url: string
  source_name: string
  published_at: string | null
  primary_category: Category
  segment_topics: string[]
  consumer_segments: string[]
  priority: 'critical' | 'high' | 'medium' | 'low'
  relevance_score: number  // 0-1
  hero_image_url: string | null
  companies: string[]
  brands: string[]
  key_entities: string[]
  sentiment: 'positive' | 'negative' | 'neutral' | null
}

// Statistics for header
interface DigestStats {
  total: number
  by_category: Record<string, number>
  by_priority: Record<string, number>
  by_source: Record<string, number>
  avg_relevance: number
}

// Categories (10 total)
type Category =
  | 'sprite_direct' | 'competitor_move' | 'market_dynamics'
  | 'marketing_campaign' | 'retail_distribution' | 'health_regulatory'
  | 'earnings_financial' | 'supply_ingredient' | 'packaging' | 'consumer_trends'
```

---

## Styling System

**CSS Variables** (globals.css):
```css
:root {
  --chalk-yellow: #FFDE4D;
  --chalk-magenta: #F472B6;
  --chalk-teal: #2DD4BF;
  --chalk-blue: #60A5FA;
  --chalk-coral: #FF7E6B;
  --chalkboard: #1A1A1A;
  --chalkboard-light: #2D2D2D;
  --slate: #4A4A4A;
  --light-gray: #F5F5F5;
}
```

**Typography**:
- Headlines: Montserrat, 600-700 weight
- Body: Open Sans, 400 weight

**Component Patterns**:
- Cards: `bg-white rounded-2xl border border-gray-100`
- Hover lift: `hover:-translate-y-1 hover:shadow-[0_8px_30px_rgb(0,0,0,0.06)]`
- Priority glow: `hover:ring-1 hover:ring-[var(--chalk-magenta)]/30`
- Glassmorphism header: `bg-gradient-to-r from-slate-900 to-slate-800`

---

## API Endpoints Required

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/articles` | GET | List articles with filters (hours, limit, category, priority) |
| `/api/articles/feed` | GET | Feed-eligible articles sorted by digest_priority |
| `/api/stats` | GET | Aggregated statistics for a time window |
| `/api/discovery/chat/stream` | POST | Streaming AI chat with tool access |

---

## Key Integration Points

1. **Main Page Integration** (`page.tsx`):
   - Uses `useFeed({ hours: 720, limit: 500, source: 'articles' })` for 30-day view
   - Passes `discoveryViewRef` for keyboard shortcut (`/` to open assistant)
   - Handles `selectedArticleId` for article detail panel

2. **Keyboard Shortcuts**:
   - `/` - Open assistant (anywhere in app)
   - `Escape` - Close article panel

3. **Quick Pivot Flow**:
   - User clicks entity pill (company/brand) in DigestCard
   - `onQuickFilter(entityName)` called
   - Opens assistant and could trigger search

---

## Phased Recreation Plan (Multi-Session)

> **Strategy**: Each session is self-contained. Complete one, commit, then start a fresh context window for the next. Each session produces testable output.

---

### 🟢 SESSION 1: Foundation (Types + Styling)
**Goal**: Establish all types and styling infrastructure. No logic yet.

**Files to Create**:
```
frontend/src/types/index.ts
frontend/src/lib/utils.ts
frontend/src/app/globals.css (add CSS variables)
```

**Checklist**:
- [ ] Create `DigestItem` interface with all fields (id, title, headline, summary, url, source_name, published_at, primary_category, segment_topics, consumer_segments, priority, relevance_score, hero_image_url, companies, brands, key_entities, sentiment)
- [ ] Create `DigestStats` interface (total, by_category, by_priority, by_source, avg_relevance)
- [ ] Create `Category` type union (10 categories)
- [ ] Create `Priority` type union ('critical' | 'high' | 'medium' | 'low')
- [ ] Add `formatRelativeTime(isoString)` → "2h ago", "3d ago"
- [ ] Add `formatCategoryLabel(category)` → "Competitor Moves"
- [ ] Add `cn()` helper (clsx + tailwind-merge)
- [ ] Add CSS variables to globals.css (chalk-teal, chalk-magenta, chalk-yellow, chalkboard, slate, light-gray)
- [ ] Add typography rules (Montserrat for headings, Open Sans for body)

**Verification**: TypeScript compiles with no errors. Import types in a test file.

**Commit Message**: `feat: add Discovery tab types and styling foundation`

---

### 🟡 SESSION 2: UI Components (Stateless)
**Goal**: Build all presentational components. Test with hardcoded mock data.

**Files to Create**:
```
frontend/src/components/ui/Badge.tsx
frontend/src/components/digest/DigestCard.tsx
frontend/src/components/feed/CategoryAccordion.tsx
```

**Checklist**:
- [ ] Create `PriorityBadge` - dot + label, colors by priority level
- [ ] Create `CategoryBadge` - colored pill with formatted label
- [ ] Create `EntityPill` - company (blue) vs brand (magenta) styling
- [ ] Create `DigestCard` with:
  - [ ] Priority gradient bar at top
  - [ ] Category + Priority badges
  - [ ] Title (headline or title fallback)
  - [ ] Expandable summary with "Read more"
  - [ ] Entity pills (companies + brands, max 3 each)
  - [ ] Source link + relevance score
  - [ ] Hover lift effect + priority glow
- [ ] Create `CategoryAccordion` with:
  - [ ] Colored left border by category
  - [ ] Header: icon + label + counts ("8 high • 24 total")
  - [ ] Fire badge (🔥) when highPriorityCount > 0
  - [ ] Collapsible content area
  - [ ] "Show all X more →" button (cap at 15 initially)
  - [ ] Items sorted by priority, then recency

**Verification**: Render components with mock `DigestItem[]` data. All visual states work.

**Commit Message**: `feat: add Discovery tab UI components (Badge, DigestCard, CategoryAccordion)`

---

### 🟠 SESSION 3: Data Hooks
**Goal**: Connect to backend APIs. No UI changes, just data fetching.

**Files to Create**:
```
frontend/src/lib/api.ts (add article endpoints)
frontend/src/hooks/useFeed.ts
frontend/src/hooks/useDiscoveryChat.ts
```

**Checklist**:
- [ ] Add API client functions:
  - [ ] `api.getArticles({ hours, limit, priority })` → ArticleListResponse
  - [ ] `api.getFeed({ hours, limit })` → ArticleListResponse
  - [ ] `api.getStats(hours)` → StatsResponse
- [ ] Create `useFeed` hook:
  - [ ] Accept options: `{ hours, limit, priority, source, autoRefresh }`
  - [ ] Return: `{ items, stats, isLoading, error, refresh }`
  - [ ] Transform API response to `DigestItem[]` format
  - [ ] Fetch feed + stats in parallel
- [ ] Create `useDiscoveryChat` hook:
  - [ ] State: `messages: ChatMessage[]`, `isLoading`, `error`
  - [ ] `sendMessage(text)` - POST to /api/discovery/chat/stream
  - [ ] Parse SSE events: chunk, tool_call, complete, error
  - [ ] Accumulate chunks into current message
  - [ ] Track `sourcesUsed` from complete event
  - [ ] `clearChat()` to reset state

**Verification**: Console.log hook outputs. Data flows correctly from API.

**Commit Message**: `feat: add Discovery tab data hooks (useFeed, useDiscoveryChat)`

---

### 🔴 SESSION 4: Main View + Assistant
**Goal**: Assemble everything into the final Discovery tab.

**Files to Create**:
```
frontend/src/components/feed/DiscoveryAssistant.tsx
frontend/src/components/feed/DiscoveryView.tsx
frontend/src/components/feed/index.ts
```

**Checklist**:
- [ ] Create `DiscoveryAssistant` panel:
  - [ ] Dark header with Sparkles icon
  - [ ] Empty state with 4 suggestion chips
  - [ ] Message list (user=teal, assistant=gray bubbles)
  - [ ] Source badges (Corpus, Web, Podcast) on assistant messages
  - [ ] Input field with send button
  - [ ] Loading state with spinner
  - [ ] Auto-scroll to bottom on new messages
- [ ] Create `DiscoveryView` container:
  - [ ] State: `isAssistantOpen`
  - [ ] Expose `openAssistant()` via forwardRef
  - [ ] Header section:
    - [ ] "Live Intelligence" badge with ping dot
    - [ ] Dynamic greeting (Good morning/afternoon/evening)
    - [ ] Stats summary ("We've analyzed X signals")
    - [ ] "Ask AI" toggle button
  - [ ] Two-column grid layout:
    - [ ] LEFT: CategoryAccordions from `groupByCategory(items)`
    - [ ] RIGHT: latestHighPriority (72h + high/critical + relevance≥0.3)
  - [ ] Empty state for right column when no high-priority items
- [ ] Wire up `onQuickFilter` from DigestCard → open assistant
- [ ] Export from index.ts

**Verification**: Full Discovery tab renders. Categories display. Assistant opens/closes. Chat works end-to-end.

**Commit Message**: `feat: complete Discovery tab view and AI assistant`

---

### 🟣 SESSION 5: Backend API (If Needed)
**Goal**: Implement the streaming chat endpoint with tool access.

**Files to Create**:
```
api/routers/discovery.py
api/mcp/tools/corpus_search.py (if not exists)
```

**Checklist**:
- [ ] Create `DiscoveryChatRequest` model (query, history)
- [ ] Create `DiscoveryChatResponse` model (message, sources_used)
- [ ] Define `DISCOVERY_ASSISTANT_SYSTEM_PROMPT`:
  - [ ] 30-day data window rule
  - [ ] Tool usage strategy (corpus first, then exa, add podcast quotes)
  - [ ] Redirect to Deep Research for historical queries
- [ ] Define `TOOLS` list:
  - [ ] corpus_search (query, limit, category)
  - [ ] exa_search (query, days_back, limit)
  - [ ] podcast_insights (query, guest_companies, limit)
- [ ] Implement `execute_tool(name, input)` dispatcher
- [ ] Create `/chat/stream` endpoint:
  - [ ] Build messages with history (last 10)
  - [ ] Tool loop (max 5 iterations)
  - [ ] Yield SSE events: tool_call, chunk, complete, error
  - [ ] Return `StreamingResponse(media_type="text/event-stream")`
- [ ] Register router in main.py

**Verification**: cURL the endpoint. SSE events stream correctly. Tools execute.

**Commit Message**: `feat: add Discovery assistant streaming API endpoint`

---

## Quick Reference: Session Dependencies

```
SESSION 1 (Foundation) ──────────────────────────────┐
     │                                               │
     ▼                                               │
SESSION 2 (UI Components) ───────────────────────────┤
     │                                               │
     ▼                                               │
SESSION 3 (Data Hooks) ──────────────────────────────┤
     │                                               │
     ▼                                               │
SESSION 4 (Main View) ◄──────────────────────────────┘
     │
     ▼
SESSION 5 (Backend) ← Can also run parallel to Sessions 2-4
```

**Total Estimated Effort**: 
- Session 1: ~30 min
- Session 2: ~1 hour
- Session 3: ~45 min
- Session 4: ~1 hour
- Session 5: ~1 hour (if backend doesn't exist)

---

## Common Pitfalls

1. **SSE with POST**: Standard `EventSource` doesn't support POST. Must use `fetch` with `response.body.getReader()`.

2. **Tool Loop Limit**: Always cap tool iterations (max 5) to prevent infinite loops.

3. **Time Window Filtering**: Discovery Assistant is HARDCODED to 30 days. UI filters 72h for "Latest Intelligence" column.

4. **Relevance Threshold**: Right column filters `relevance_score >= 0.3` to ensure quality.

5. **Message History**: Keep only last 10 messages in chat context to manage token limits.

6. **Typing Effect**: Stream chunks of ~20 chars with 20ms delay for natural feel.

---

## Testing Checklist

- [ ] Categories sort by high-priority count, then category priority
- [ ] "Latest Intelligence" only shows high/critical from last 72h
- [ ] Empty state appears when no high-priority items in 72h
- [ ] Assistant opens/closes correctly
- [ ] Chat messages stream with typing effect
- [ ] Tool badges (Corpus, Web, Podcast) appear after response
- [ ] Entity pill clicks open assistant
- [ ] DigestCard expand/collapse works
- [ ] "Show all X more" pagination in accordions
- [ ] `/` keyboard shortcut opens assistant
- [ ] Proper error handling for failed API calls

---

## Dependencies

**Frontend**:
- Next.js 16+ (App Router)
- Tailwind CSS 4.x with `@theme inline`
- lucide-react (icons)
- clsx + tailwind-merge

**Backend**:
- FastAPI
- Anthropic SDK (Claude 3.5 Haiku)
- ChromaDB or BigQuery embeddings store
- Exa.ai API (optional, for web search)

---

*Last Updated: January 2026*
