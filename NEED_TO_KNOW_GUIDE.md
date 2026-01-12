# Need to Know - Executive Briefing Component Guide

**For AI Coding Assistants**: This guide explains how to recreate the "Need to Know" executive briefing look, feel, and functionality in a different project.

---

## Table of Contents
1. [Overview](#overview)
2. [Visual Design & Styling](#visual-design--styling)
3. [Data Structure](#data-structure)
4. [Component Architecture](#component-architecture)
5. [Key Features](#key-features)
6. [API Integration](#api-integration)
7. [Implementation Checklist](#implementation-checklist)

---

## Overview

The **Need to Know** section is a sophisticated executive briefing system that displays weekly intelligence summaries with:
- **Dynamic sections** with agent-generated headers
- **Expandable/collapsible insights** with "sneak peek" functionality
- **Inline company logos** and citations
- **Status badges** (Net New vs. Continuing)
- **Podcast audio integration**
- **Rich source attribution** grouped by domain

---

## Visual Design & Styling

### Color Palette
```css
/* Primary Brand Color - Emerald (used throughout) */
--emerald-50: #f0fdf4
--emerald-100: #dcfce7
--emerald-200: #bbf7d0
--emerald-400: #4ade80
--emerald-500: #22c55e
--emerald-600: #16a34a
--emerald-700: #15803d

/* Supporting Colors */
--slate-50: #f8fafc   /* Background */
--slate-100: #f1f5f9  /* Borders, secondary surfaces */
--slate-200: #e2e8f0  /* Dividers */
--slate-400: #94a3b8  /* Secondary text */
--slate-600: #475569  /* Tertiary text */
--slate-700: #334155  /* Body text */
--slate-900: #0f172a  /* Headlines */

/* Status Colors */
--red-50 to --red-700    /* High priority/attention items */
--rose-50 to --rose-500  /* Attention flags */
```

### Typography Scale
```css
/* Headers */
.section-header {
  font-size: 0.875rem;      /* 14px - small caps */
  font-weight: 700;         /* bold */
  text-transform: uppercase;
  letter-spacing: 0.05em;   /* tracking-wide */
  color: theme(slate.900);
}

.briefing-title {
  font-size: 1.5rem;        /* 24px */
  font-weight: 800;         /* extrabold */
  letter-spacing: -0.025em; /* tracking-tight */
  color: theme(slate.900);
}

.headline {
  font-size: 1rem;          /* 16px */
  font-weight: 600;         /* semibold */
  color: theme(slate.900);
}

.insight-text {
  font-size: 0.875rem;      /* 14px */
  color: theme(slate.700);
  line-height: 1.625;       /* relaxed */
}

.metadata {
  font-size: 0.625rem;      /* 10px */
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.1em;    /* tracking-widest */
}
```

### Spacing System
```css
/* Card padding */
.card-main-padding: 1.25rem (20px)
.card-tray-padding: 1.25rem (20px)
.card-gap-between: 1rem (16px)

/* Section spacing */
.section-gap: 1rem (16px) between sections
.content-gap: 0.75rem (12px) between insights
.inline-gap: 0.5rem (8px) for inline elements
```

### Border & Shadow Design
```css
/* Card borders */
border: 1px solid theme(slate.200)
border-radius: 0.75rem (12px)

/* First card emphasis */
border: 1px solid theme(emerald.200)
ring: 1px solid theme(emerald.50)

/* Card shadows */
box-shadow: 0 1px 2px 0 rgb(0 0 0 / 0.05)  /* default */
box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1) /* hover */
transition: all 0.2s
```

---

## Data Structure

### Core TypeScript Interfaces

```typescript
// Company with logo
export interface CompanyWithLogo {
  name: string
  domain?: string
  logo_url?: string
}

// Individual insight with status badge
export interface BriefingInsight {
  text: string  // Text with inline citations [1], [2] and company tags [[Company Name]]
  status: 'net_new' | 'continuing'  // Determines badge color
  companies_mentioned: string[]
}

// Source article for citations
export interface SourceArticle {
  article_number: number | string  // Matches [N] in text
  id: string
  title: string
  url: string
  source_name: string
  source_type?: string
  published_at?: string
  summary?: string
  priority?: string
  relevance_score?: number
}

// Section card - the main building block
export interface BriefingSection {
  header: string  // Agent-generated (2-5 words, specific not generic)
  headline: BriefingInsight  // Always visible, bolded
  insights: BriefingInsight[]  // Shown in expandable tray
  source_articles: SourceArticle[]
  companies_with_logos: CompanyWithLogo[]
}

// Full weekly briefing
export interface WeeklyBriefing {
  id: string
  briefing_type: 'weekly_executive'
  briefing_title: string
  bluf?: string  // Bottom Line Up Front - single sentence summary
  sections: BriefingSection[]
  all_companies_mentioned: CompanyWithLogo[]
  key_topics_this_week: string[]
  overall_trend: string
  period_start: string  // ISO date
  period_end: string    // ISO date
  generated_at: string  // ISO date
  model: string
  article_count: number
  article_ids: string[]
  // Optional podcast fields
  podcast_url?: string
  podcast_duration_seconds?: number
  podcast_generated_at?: string
}
```

---

## Component Architecture

### File Structure
```
components/
├── dashboard/
│   ├── WeeklyBriefingSection.tsx   # Main component (539 lines)
│   ├── PodcastModal.tsx            # Audio player modal (317 lines)
│   └── PulseDashboard.tsx          # Parent container
├── ui/
│   ├── Badge.tsx                   # Reusable badge components
│   └── index.ts                    # UI exports
types/
└── briefing.ts                     # All TypeScript interfaces (173 lines)
lib/
├── api.ts                          # API client methods
├── utils.ts                        # cn() utility for className merging
└── config.ts                       # API_BASE configuration
```

### Component Hierarchy

```
WeeklyBriefingSection (Main Container)
├── Header Section
│   ├── Zap Icon + Title
│   ├── Podcast Button (conditional)
│   └── Date Range + History Link
├── BLUF Card (gradient emerald background)
│   ├── Briefing Title
│   ├── BLUF Box (white background)
│   └── Overall Trend + Stats
├── Section Cards (map over sections)
│   └── SectionCard
│       ├── Section Header (emerald background strip)
│       │   ├── Header Text
│       │   └── Company Logos (max 5 visible)
│       ├── Headline (InsightItem, always visible)
│       ├── Sneak Peek (when collapsed, faded)
│       ├── Expand/Collapse Button
│       ├── Insights Tray (expandable)
│       │   └── InsightItem (multiple, with bullets)
│       └── Sources Footer (grouped by domain)
├── Key Topics Footer (badges)
└── PodcastModal (conditional)
```

---

## Key Features

### 1. Status Badges

```tsx
function StatusBadge({ status }: { status: 'net_new' | 'continuing' }) {
  if (status === 'net_new') {
    return (
      <Badge className="bg-emerald-100 text-emerald-700 border-emerald-200 text-[10px] font-bold uppercase">
        <Sparkles size={10} className="mr-1" />
        Net New
      </Badge>
    )
  }
  return (
    <Badge className="bg-slate-100 text-slate-600 border-slate-200 text-[10px] font-medium uppercase">
      <RefreshCw size={10} className="mr-1" />
      Continuing
    </Badge>
  )
}
```

**Key Details:**
- Emerald color for "Net New" items (new intelligence)
- Gray color for "Continuing" items (ongoing situations)
- Icons: `Sparkles` for new, `RefreshCw` for continuing
- Font size: 10px with bold uppercase text

---

### 2. Company Logo Display

```tsx
function CompanyLogo({ company, size = 'sm' }: CompanyLogoProps) {
  const [imageError, setImageError] = useState(false)
  const sizeClasses = size === 'sm' ? 'w-5 h-5' : 'w-6 h-6'
  
  const logoUrl = company.domain
    ? `${API_BASE}/api/pipeline/logo/${company.domain}`
    : null
  
  if (!logoUrl || imageError) {
    // Fallback: Show initials
    const initials = company.name
      .split(' ')
      .map(w => w[0])
      .slice(0, 2)
      .join('')
      .toUpperCase()
    
    return (
      <div className={cn(sizeClasses, "rounded bg-slate-200 flex items-center justify-center text-[8px] font-bold text-slate-500")}>
        {initials}
      </div>
    )
  }
  
  return (
    <img
      src={logoUrl}
      alt={company.name}
      title={company.name}
      className={cn(sizeClasses, "rounded object-contain")}
      onError={() => setImageError(true)}
    />
  )
}
```

**Implementation Notes:**
- Uses backend proxy to fetch logos via logo.dev API
- Graceful fallback to initials (first 2 letters)
- Size variants: 20px (sm) or 24px (md)
- Error handling with `onError` callback

---

### 3. Text Rendering with Inline Elements

The most complex feature - handles three inline patterns:

**Pattern 1: Citations** `[1]`, `[2]`, `[Exa:3]`
```tsx
// Rendered as clickable superscript with hover showing domain
<a href={article.url} target="_blank" className="text-emerald-600 font-semibold">
  <sup>1</sup>
</a>
```

**Pattern 2: Company Logos** `[[Company Name]]`
```tsx
// Rendered as bold text + inline logo
<span className="inline-flex items-center gap-1.5">
  <span className="font-bold text-slate-900">Company Name</span>
  <CompanyLogo company={company} />
</span>
```

**Pattern 3: Entity Highlights** `{{Entity Name}}`
```tsx
// Rendered as bold text without logo
<span className="font-semibold text-slate-800">Entity Name</span>
```

**Full Implementation:**
```tsx
const renderTextWithLogosAndCitations = (
  text: string,
  companiesWithLogos: CompanyWithLogo[],
  sourceArticles?: SourceArticle[]
) => {
  // Regex splits on all three patterns
  const parts = text.split(/(\[(?:Exa:)?\d+\]|\[\[.*?\]\]|\{\{.*?\}\})/g)
  
  return parts.map((part, idx) => {
    // Citation handling
    if (/^\[(?:Exa:)?\d+\]$/.test(part)) {
      const numStr = part.replace(/[\[\]Exa:]/g, '')
      const num = parseInt(numStr, 10)
      const article = sourceArticles?.find(a => a.article_number === num)
      const domain = article?.url ? extractDomain(article.url) : null
      
      if (article?.url) {
        return (
          <a key={idx} href={article.url} target="_blank" rel="noopener noreferrer" 
             className="text-emerald-600 font-semibold ml-0.5 cursor-pointer hover:underline"
             title={domain || `Source ${num}`}>
            <sup>{numStr}</sup>
          </a>
        )
      }
      return <sup key={idx} className="text-emerald-600 font-semibold ml-0.5">{numStr}</sup>
    }
    
    // Company logo handling
    if (/^\[\[.*?\]\]$/.test(part)) {
      const companyName = part.replace(/[\[\]]/g, '')
      const company = companiesWithLogos.find(c => c.name === companyName)
      
      return (
        <span key={idx} className="inline-flex items-center gap-1.5 align-baseline">
          <span className="font-bold text-slate-900 mx-0.5">{companyName}</span>
          {company && (
            <span className="inline-block transform translate-y-0.5">
              <CompanyLogo company={company} size="sm" />
            </span>
          )}
        </span>
      )
    }
    
    // Entity highlight handling
    if (/^\{\{.*?\}\}$/.test(part)) {
      const entityName = part.replace(/[\{\}]/g, '')
      return <span key={idx} className="font-semibold text-slate-800">{entityName}</span>
    }
    
    return part
  })
}
```

---

### 4. Expandable Section Card

```tsx
function SectionCard({ section, isFirst = false }: SectionCardProps) {
  const [isExpanded, setIsExpanded] = useState(isFirst)  // Auto-expand first
  
  return (
    <div className={cn(
      "bg-white border rounded-xl overflow-hidden shadow-sm hover:shadow-md transition-all",
      isFirst ? "border-emerald-200 ring-1 ring-emerald-50" : "border-slate-200"
    )}>
      {/* Section Header with emerald background */}
      <div className="p-5">
        <div className="flex items-center justify-between mb-4 bg-emerald-400/10 p-3 rounded-lg border border-emerald-400/5">
          <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wide">
            {section.header}
          </h3>
          
          {/* Company logos (max 5 visible) */}
          <div className="flex items-center gap-1">
            {companies.slice(0, 5).map((company, idx) => (
              <CompanyLogo key={idx} company={company} size="sm" />
            ))}
            {companies.length > 5 && (
              <span className="text-[10px] text-slate-400 ml-1">
                +{companies.length - 5}
              </span>
            )}
          </div>
        </div>
        
        {/* Headline - Always Visible */}
        <InsightItem insight={section.headline} companiesWithLogos={companies} isHeadline={true} />
        
        {/* Sneak Peek - Visible When Collapsed */}
        {!isExpanded && insights.length > 0 && (
          <div className="mt-2 relative">
            <InsightItem insight={insights[0]} companiesWithLogos={companies} isSneakPeak={true} />
            {/* Fade gradient overlay */}
            <div className="absolute inset-x-0 bottom-0 h-8 bg-gradient-to-t from-white to-transparent" />
          </div>
        )}
        
        {/* Expand/Collapse Button */}
        <button onClick={() => setIsExpanded(!isExpanded)} 
                className="flex items-center gap-1 text-xs text-emerald-600 font-medium hover:text-emerald-700">
          {isExpanded ? (
            <><ChevronUp size={14} />Hide insights</>
          ) : (
            <><ChevronDown size={14} />Show {insights.length} more insight{insights.length > 1 ? 's' : ''}</>
          )}
        </button>
      </div>
      
      {/* Expandable Insights Tray */}
      {isExpanded && insights.length > 0 && (
        <div className="border-t border-slate-100 bg-slate-50/50 p-5 space-y-3">
          {insights.map((insight, idx) => (
            <InsightItem key={idx} insight={insight} companiesWithLogos={companies} />
          ))}
        </div>
      )}
      
      {/* Sources Footer - Grouped by Domain */}
      <div className="border-t border-slate-100 px-5 py-3 bg-slate-50">
        <div className="flex items-center gap-2 text-[10px] text-slate-400 uppercase">
          <span className="font-semibold">Sources</span>
          <span>({articles.length})</span>
        </div>
        <div className="flex flex-wrap gap-x-4 gap-y-1">
          {Object.entries(articlesByDomain).slice(0, 6).map(([domain, domainArticles]) => (
            <a key={domain} href={domainArticles[0].url} target="_blank"
               className="inline-flex items-center gap-1.5 text-xs text-slate-600 hover:text-emerald-600">
              <span className="font-medium">{domain}</span>
              <span className="text-slate-400">[{domainArticles.map(a => a.article_number).join(', ')}]</span>
              <ExternalLink size={10} />
            </a>
          ))}
        </div>
      </div>
    </div>
  )
}
```

**Key UX Features:**
- First section auto-expands (`isFirst` prop)
- Sneak peek shows truncated first insight when collapsed
- Fade-out gradient creates visual teaser
- Source grouping by domain reduces clutter
- Hover states on interactive elements

---

### 5. BLUF (Bottom Line Up Front) Card

```tsx
<div className="bg-gradient-to-r from-emerald-100 to-emerald-100 border border-emerald-200 rounded-xl p-4">
  <h3 className="text-lg font-bold text-slate-900">{briefing.briefing_title}</h3>
  
  {briefing.bluf && (
    <div className="mt-3 p-3 bg-white/60 rounded-lg border border-emerald-200/50">
      <div className="flex items-start gap-2">
        <span className="text-xs font-bold text-emerald-700 uppercase tracking-wider shrink-0">
          BLUF
        </span>
        <p className="text-sm font-medium text-slate-800 leading-relaxed">
          {renderTextWithLogosAndCitations(briefing.bluf, allCompaniesWithLogos)}
        </p>
      </div>
    </div>
  )}
  
  {briefing.overall_trend && (
    <p className="text-sm text-slate-600 mt-3">
      {renderTextWithLogosAndCitations(briefing.overall_trend, allCompaniesWithLogos)}
    </p>
  )}
  
  <div className="mt-3 flex items-center gap-4 text-xs text-slate-500">
    <span>{briefing.article_count} articles analyzed</span>
    <span>•</span>
    <span>{briefing.sections.length} key areas</span>
  </div>
</div>
```

**Design Notes:**
- Emerald gradient background for emphasis
- White semi-transparent box for BLUF text
- "BLUF" label in emerald uppercase
- Metadata line with bullet separator

---

### 6. Podcast Integration

```tsx
{/* Header Button */}
{briefing.podcast_url && (
  <button onClick={() => setIsPodcastModalOpen(true)}
          className="flex items-center gap-2 px-3 py-1.5 bg-emerald-100 hover:bg-emerald-200 text-emerald-700 rounded-lg border border-emerald-200/60">
    <Headphones size={16} />
    <span className="text-xs font-semibold">Listen</span>
  </button>
)}

{/* Modal Component */}
<PodcastModal
  isOpen={isPodcastModalOpen}
  onClose={() => setIsPodcastModalOpen(false)}
  audioUrl={`${API_BASE}/api/podcast/briefing/${briefing.id}`}
  duration={briefing.podcast_duration_seconds}
  title={briefing.briefing_title}
/>
```

**PodcastModal Features:**
- Native HTML5 `<audio>` element with custom controls
- Play/pause, seek, volume controls
- Skip forward/backward (15 seconds)
- Download button
- Escape key to close
- Body scroll lock when open
- Loading states and error handling

---

## API Integration

### API Client Methods

```typescript
// In lib/api.ts

class ApiClient {
  /**
   * Get the latest weekly executive briefing
   */
  async getWeeklyBriefing(): Promise<WeeklyBriefing | null> {
    const response = await fetch(`${this.baseUrl}/api/pulse/weekly`)
    if (!response.ok) {
      if (response.status === 404) return null  // No briefing yet
      throw new Error(`Failed to fetch weekly briefing: ${response.statusText}`)
    }
    return response.json()
  }

  /**
   * Get weekly briefing history
   */
  async getWeeklyBriefingHistory(limit: number = 10): Promise<WeeklyBriefing[]> {
    const response = await fetch(`${this.baseUrl}/api/pulse/weekly/history?limit=${limit}`)
    if (!response.ok) {
      throw new Error(`Failed to fetch briefing history: ${response.statusText}`)
    }
    return response.json()
  }
}
```

### React Hook Pattern

```typescript
// In hooks/useBriefing.ts or similar

export function useWeeklyBriefing() {
  const [briefing, setBriefing] = useState<WeeklyBriefing | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)

  useEffect(() => {
    const fetchBriefing = async () => {
      try {
        setIsLoading(true)
        const api = new ApiClient()
        const data = await api.getWeeklyBriefing()
        setBriefing(data)
        setError(null)
      } catch (err) {
        setError(err as Error)
      } finally {
        setIsLoading(false)
      }
    }

    fetchBriefing()
  }, [])

  return { briefing, isLoading, error }
}
```

### Backend API Contract

**Expected Backend Endpoints:**

```
GET /api/pulse/weekly
Response: WeeklyBriefing | null (404 if not found)

GET /api/pulse/weekly/history?limit=10
Response: WeeklyBriefing[]

GET /api/podcast/briefing/{briefing_id}
Response: Audio file stream (audio/mpeg)

GET /api/pipeline/logo/{domain}
Response: Image (proxied from logo.dev or similar)
```

---

## Implementation Checklist

### Phase 1: Core UI Components (Day 1-2)
- [ ] Create TypeScript interfaces in `types/briefing.ts`
- [ ] Set up Tailwind CSS with emerald color palette
- [ ] Create `Badge` component with variants
- [ ] Create `CompanyLogo` component with fallback to initials
- [ ] Implement `renderTextWithLogosAndCitations()` helper function
- [ ] Test inline rendering with sample data

### Phase 2: Section Cards (Day 2-3)
- [ ] Build `InsightItem` component (bullet, headline, sneak peek variants)
- [ ] Build `StatusBadge` component (Net New vs. Continuing)
- [ ] Build `SectionCard` with expand/collapse state
- [ ] Implement sneak peek with fade gradient
- [ ] Add source footer with domain grouping
- [ ] Test with multiple sections

### Phase 3: Main Container (Day 3-4)
- [ ] Create `WeeklyBriefingSection` main component
- [ ] Add header with icon, title, date range
- [ ] Build BLUF card with gradient background
- [ ] Map sections with `isFirst` auto-expand
- [ ] Add key topics footer
- [ ] Handle loading and empty states

### Phase 4: Advanced Features (Day 4-5)
- [ ] Integrate `PodcastModal` component
- [ ] Add podcast button in header (conditional)
- [ ] Connect to audio streaming endpoint
- [ ] Implement history timeline modal (optional)
- [ ] Add error boundaries and error states

### Phase 5: API & Data Integration (Day 5-6)
- [ ] Create API client methods
- [ ] Build React hook for data fetching
- [ ] Set up logo proxy endpoint
- [ ] Test with real backend data
- [ ] Add retry logic and timeout handling

### Phase 6: Polish & Testing (Day 6-7)
- [ ] Add hover states and transitions
- [ ] Test responsive behavior (though primarily desktop)
- [ ] Add loading skeletons with pulse animation
- [ ] Verify accessibility (keyboard nav, ARIA labels)
- [ ] Cross-browser testing
- [ ] Performance optimization (memoization, lazy loading)

---

## Critical Implementation Notes

### 1. Text Parsing Order Matters
The regex split must capture all three patterns in one pass:
```typescript
text.split(/(\[(?:Exa:)?\d+\]|\[\[.*?\]\]|\{\{.*?\}\})/g)
```
Test with: `"Check [[Boeing]] and [[Airbus]] [1] for updates {{Entity}} [2]"`

### 2. Logo API Proxy Required
Don't call logo.dev directly from frontend (CORS issues). Use backend proxy:
```
Frontend: /api/pipeline/logo/example.com
Backend: Proxies to logo.dev or Clearbit
```

### 3. First Section Auto-Expand
Pass `isFirst={idx === 0}` to first SectionCard for better UX:
```tsx
{sections.map((section, idx) => (
  <SectionCard key={idx} section={section} isFirst={idx === 0} />
))}
```

### 4. Source Grouping Algorithm
Group articles by domain to reduce clutter:
```typescript
const articlesByDomain = articles.reduce((acc, article) => {
  const domain = extractDomain(article.url)
  if (!acc[domain]) acc[domain] = []
  acc[domain].push(article)
  return acc
}, {} as Record<string, SourceArticle[]>)
```

### 5. Gradient Fade for Sneak Peek
Use absolute positioning with pointer-events-none:
```tsx
<div className="absolute inset-x-0 bottom-0 h-8 bg-gradient-to-t from-white to-transparent pointer-events-none" />
```

### 6. Utility Function for className Merging
Use `clsx` + `tailwind-merge` for conditional classes:
```typescript
// lib/utils.ts
import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
```

---

## Dependencies

```json
{
  "dependencies": {
    "react": "^18.x",
    "lucide-react": "^0.x",  // Icon library
    "clsx": "^2.x",
    "tailwind-merge": "^2.x"
  },
  "devDependencies": {
    "tailwindcss": "^3.x",
    "typescript": "^5.x",
    "@types/react": "^18.x"
  }
}
```

### Icon Usage (lucide-react)
```tsx
import {
  ChevronDown,
  ChevronUp,
  Zap,
  Sparkles,
  RefreshCw,
  ExternalLink,
  Clock,
  Headphones
} from 'lucide-react'
```

---

## Example Usage in Parent Component

```tsx
import WeeklyBriefingSection from './WeeklyBriefingSection'
import { useWeeklyBriefing } from '@/hooks'

export default function Dashboard() {
  const { briefing, isLoading, error } = useWeeklyBriefing()
  
  return (
    <div className="p-6 bg-slate-50">
      <WeeklyBriefingSection
        briefing={briefing}
        isLoading={isLoading}
        onHistoryClick={() => setHistoryOpen(true)}  // Optional
      />
    </div>
  )
}
```

---

## Sample Data Structure (for testing)

```json
{
  "id": "weekly_2026_01_01",
  "briefing_type": "weekly_executive",
  "briefing_title": "Aerospace Supply Chain Volatility Continues; New Materials Drive Innovation",
  "bluf": "Supply chain pressures persist for [[Boeing]] and [[Airbus]] [1], while emerging {{carbon fiber}} alternatives gain traction [2].",
  "sections": [
    {
      "header": "Supply Chain Disruptions",
      "headline": {
        "text": "[[Boeing]] production delays extend into Q2 due to {{titanium}} shortages [1] [2].",
        "status": "continuing",
        "companies_mentioned": ["Boeing"]
      },
      "insights": [
        {
          "text": "Suppliers report 6-8 week delays on critical fasteners [3].",
          "status": "net_new",
          "companies_mentioned": []
        },
        {
          "text": "[[Spirit AeroSystems]] seeks alternative {{aluminum}} suppliers [4].",
          "status": "net_new",
          "companies_mentioned": ["Spirit AeroSystems"]
        }
      ],
      "source_articles": [
        {
          "article_number": 1,
          "id": "art_001",
          "title": "Boeing Faces Extended Production Delays",
          "url": "https://aerospace.com/boeing-delays",
          "source_name": "Aerospace Weekly",
          "published_at": "2026-01-08T10:00:00Z"
        }
        // ... more articles
      ],
      "companies_with_logos": [
        {
          "name": "Boeing",
          "domain": "boeing.com"
        },
        {
          "name": "Spirit AeroSystems",
          "domain": "spiritaero.com"
        }
      ]
    }
    // ... more sections
  ],
  "all_companies_mentioned": [...],
  "key_topics_this_week": ["Supply Chain", "Carbon Fiber", "Production Delays"],
  "overall_trend": "Aerospace sector facing continued headwinds...",
  "period_start": "2025-12-30",
  "period_end": "2026-01-06",
  "generated_at": "2026-01-06T08:30:00Z",
  "model": "claude-3-5-sonnet-20241022",
  "article_count": 47,
  "article_ids": ["art_001", "art_002", ...],
  "podcast_url": "https://api.example.com/podcast/weekly_2026_01_01.mp3",
  "podcast_duration_seconds": 420
}
```

---

## Common Pitfalls to Avoid

1. **Don't skip the text parsing regex** - It's complex for a reason. Test thoroughly.
2. **Don't fetch logos from frontend** - Always proxy through backend.
3. **Don't forget loading states** - Skeleton screens prevent layout shift.
4. **Don't hardcode colors** - Use Tailwind theme tokens for consistency.
5. **Don't skip hover states** - Micro-interactions matter for polish.
6. **Don't forget empty states** - "No briefing yet" message is required.
7. **Don't overlook first-section auto-expand** - Critical for UX flow.
8. **Don't forget gradient fade on sneak peek** - Visual cue that there's more.

---

## Final Notes

This component took ~539 lines of TypeScript/React code to implement properly. The complexity comes from:
- Rich inline text rendering (logos, citations, entities)
- Graceful degradation (logo fallbacks, missing data)
- Polished animations and transitions
- Responsive state management (expand/collapse, modals)
- Robust error handling

**Time Estimate for Full Recreation:**
- Junior Developer: 5-7 days
- Mid-Level Developer: 3-4 days
- Senior Developer: 2-3 days

**Priority Features (MVP):**
1. Section cards with expand/collapse
2. Status badges and company logos
3. Citation rendering (can skip clickable links in v1)
4. BLUF card
5. Basic styling and spacing

**Can Defer to v2:**
- Podcast integration
- History timeline
- Sneak peek fade
- Advanced hover states
- Logo API optimization

---

## Questions for the AI Assistant?

When implementing this, ask yourself:
1. Does my backend return data in this exact structure?
2. Do I have a logo proxy endpoint?
3. Do I have the `cn()` utility and Tailwind configured?
4. Have I installed lucide-react for icons?
5. Do I need the podcast feature in v1?

**Good luck building! This design system is production-tested and scales well.**
