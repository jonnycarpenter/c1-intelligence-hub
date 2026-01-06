# C1 Intelligence Hub - Frontend

Next.js 16 React application with TypeScript and Tailwind CSS.

## Architecture

```
src/
├── app/                    # Next.js App Router
│   └── page.tsx           # Main page (all tabs)
├── components/
│   ├── chat/              # ChatInterface, message rendering
│   ├── dashboard/         # Pulse tab components
│   │   ├── PulseDashboard.tsx
│   │   ├── WeeklyBriefingSection.tsx
│   │   ├── PodcastPlayer.tsx
│   │   ├── AdHocBriefing.tsx
│   │   └── EntityAggregator.tsx
│   ├── data-preferences/  # Settings & preferences tab
│   │   └── DataPreferencesDashboard.tsx
│   ├── layout/            # App shell
│   │   ├── Sidebar.tsx
│   │   └── AppHeader.tsx
│   ├── memory/            # Long-term memory components
│   │   └── PreferencesPanel.tsx
│   ├── pipeline/          # Pipeline tab
│   │   └── PipelineDashboard.tsx
│   ├── products/          # Products tab
│   ├── report/            # Report drawer
│   └── research/          # Deep Research tab
│       ├── ResearchDashboard.tsx
│       ├── ResearchCanvas.tsx
│       ├── ResearchSidebar.tsx
│       ├── ResearchProgress.tsx
│       ├── SavedReportsPanel.tsx
│       └── DeepResearchReport.tsx
├── hooks/
│   ├── useDeepResearch.ts  # Deep research SSE + state
│   ├── useDigest.ts        # Digest data fetching
│   └── useStreamingChat.ts # Chat streaming
├── lib/
│   ├── api.ts              # API client (all backend calls)
│   └── utils.ts            # cn() helper, etc.
└── types/
    ├── index.ts            # Core types
    └── briefing.ts         # Briefing-specific types
```

## Key Components

### Research Tab
- **ResearchDashboard** - Main container, manages state between sidebar and canvas
- **ResearchSidebar** - Templates, recent searches, saved reports section
- **ResearchCanvas** - Displays research sections and deep research results
- **SavedReportsPanel** - Browse/search saved reports (sidebar section or full view)
- **ResearchProgress** - Real-time progress visualization during research
- **DeepResearchReport** - Renders completed research reports

### Pulse Tab
- **PulseDashboard** - Weekly briefing + ad-hoc briefing layout
- **WeeklyBriefingSection** - Renders briefing with expandable sections
- **PodcastPlayer** - Audio player for briefing podcasts
- **AdHocBriefing** - On-demand question interface
- **EntityAggregator** - Heat map visualization of entities

### Data & Preferences Tab
- **DataPreferencesDashboard** - Tabbed interface for settings
- **PreferencesPanel** - Manage priority/blocked topics

## Custom Hooks

### `useDeepResearch`
Manages deep research workflow state and SSE streaming:
- `startDeepResearch(query, context)` - Initiates research
- `cancelResearch()` - Aborts in-progress research
- `nodeStatuses` - Progress of each workflow node
- `toolProgress` - Real-time tool execution events
- `report` - Final research report when complete

### `useDigest`
Fetches digest items and stats from backend:
- `items` - Digest items array
- `stats` - Category/priority statistics
- `isLoading`, `error` - Loading state
- `refresh()` - Refetch data

### `useStreamingChat`
Manages chat interface with streaming responses:
- `messages` - Chat message history
- `sendMessage(content, mode)` - Send user message
- `isStreaming` - Currently streaming response
- `streamingState` - Products, companies extracted from response

## API Client (`lib/api.ts`)

All backend communication goes through the singleton `api` object:

```typescript
import { api } from '@/lib/api'

// Digest
await api.getDigestItems({ hours: 168 })

// Research
await api.getSavedReports({ limit: 20 })
await api.getSavedReportById(reportId)
await api.searchRelatedReports({ query, companies, industries })

// Preferences
await api.getPreferences()
await api.addPreference({ preference_type, value, scope, team })
await api.removePreference(preferenceId)

// Memory
await api.saveToMemory({ type, question, answer, tags })
await api.getMemoryLog({ limit, offset })
```

## Development

```bash
npm install
npm run dev     # Start dev server at http://localhost:3000
npm run build   # Production build
npm run lint    # ESLint check
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `NEXT_PUBLIC_API_URL` | Backend API URL (default: `http://localhost:8000`) |

In production, the frontend is built as static files and served by the FastAPI backend.

## Styling

- **Tailwind CSS** with custom config in `tailwind.config.ts`
- **Utility function**: `cn()` from `lib/utils.ts` for conditional classes
- **Icons**: Lucide React icons

## Type System

Core types are in `types/index.ts`:
- `Mode` - Tab identifiers
- `DigestItem`, `ReportItem` - Data types
- `ResearchSection`, `RecentSearch` - Research state
- `NodeStatus`, `ToolProgressEvent` - Progress tracking
- `DeepResearchReport` - Full report structure
