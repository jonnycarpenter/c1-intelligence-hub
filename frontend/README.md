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
│   │   ├── PodcastModal.tsx
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
│   ├── supply-network/    # Supply Network tab
│   │   ├── SupplyNetworkDashboard.tsx  # Main container (Directory + Network Map)
│   │   ├── CompanyCard.tsx             # Directory card with Logo.dev logos
│   │   ├── CompanyDrilldown.tsx        # Suppliers/Customers toggle + intel panel
│   │   ├── IntelligencePanel.tsx       # Earnings, SEC, articles sidebar
│   │   ├── NetworkGraph.tsx            # Force-directed graph (canvas)
│   │   ├── DetailPanel.tsx             # Network map sidebar
│   │   └── SupplyChainSearch.tsx       # NL search with SSE
│   └── research/          # Deep Research tab (Pipeline-style layout)
│       ├── ResearchDashboard.tsx  # Main container with integrated chat
│       ├── ResearchCanvas.tsx     # Legacy section display
│       ├── ResearchProgress.tsx
│       ├── SavedReportsPanel.tsx
│       └── ResearchReport.tsx
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

### Research Tab (Session 42 Redesign)
- **ResearchDashboard** - Pipeline-style layout: 400px emerald chat on left, results on right
- **SavedReportsPanel** - Accessed via button in results header (upper-right)
- **ResearchProgress** - Real-time progress visualization during research
- **ResearchReport** - Renders completed research reports
  - **Clickable Citations** (Session 75): Section citations render as pill-style badges showing domain (e.g., `compositesworld.com`) with links to full source URL
  - **Company Logos** (Session 75): Companies mentioned in research display in Executive Summary with Logo.dev integration (fallback to initials)

### Pulse Tab
- **PulseDashboard** - Weekly briefing + ad-hoc briefing layout
- **WeeklyBriefingSection** - Renders briefing with expandable sections + 🎧 Listen button
- **PodcastModal** - Dark-theme modal for podcast playback (skip ±15s, volume, progress, download)
- **AdHocBriefing** - On-demand question interface
- **EntityAggregator** - Compact summary stats (5 aggregations) with expandable drawer showing filterable entity pills

### Data & Preferences Tab
- **DataPreferencesDashboard** - Tabbed interface forsettings
- **PreferencesPanel** - Manage priority/blocked topics

### Pipeline Tab (Session 50 Enhancement)
- **PipelineDashboard** - "Pulse-style" layout with floating cards and slate-200 background
- **SearchBlockCard** - Renders search results with alternating row colors (zebra striping) for readability

### Supply Network Tab (Session 94+)
- **SupplyNetworkDashboard** - Two sub-tabs: Directory (card grid) and Network Map (force graph)
- **CompanyCard** - Directory cards with Logo.dev logos, entity badges (C1/Competitor), supplier counts, shipment stats
- **CompanyDrilldown** - Full detail view with Suppliers/Customers toggle, supplier table, intelligence panel
- **IntelligencePanel** - Collapsible sections for earnings quotes, SEC nuggets, and recent articles
- **NetworkGraph** - `react-force-graph-2d` canvas visualization with zoom controls and legend
- **DetailPanel** - Network map sidebar for node drill-down
- **SupplyChainSearch** - Agent-powered natural language search with SSE streaming

### Discovery Tab (Session 87 Refactor)
- **DiscoveryView** - Two-column layout: category list (left) + detail panel (right)
- **CategoryRow** - Clickable category with name, item count, urgent badge, and AI Summary button
- **DetailPanel** - Shows either DigestCards (when category clicked) or AI Summary (glassmorphism dark theme)
- **AdHocBriefing** - Shared component at top for "Ask about this week's news..." input
- **Entity pivot** - Click entity pill on DigestCard → auto-populates question input
- **Summary caching** - AI Summaries cached in useRef Map to avoid redundant API calls

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

## Animations & UX (Session 106)

### Core Libraries
- **Framer Motion**: Main animation library for page transitions and component interactions.
- `src/components/ui/motion-wrapper.tsx`: Reusable wrapper for page entry animations.

### Interactions
- **Active Pill**: Sidebar uses `layoutId` for smooth "floating" tab transitions.
- **Staggered Entry**: DiscoveryView and FullFeedView use `staggerChildren` for cascaded content loading.
- **Thinking Authenticity**: `TypewriterEffect` component for "Market Pulse" to simulate AI reasoning.
