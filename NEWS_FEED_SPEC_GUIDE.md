# News Feed UI Specification Guide

A focused guide for implementing the masonry layout and frontend filtering for the intelligence news feed.

---

## Table of Contents

1. [Overview](#overview)
2. [Component Architecture](#component-architecture)
3. [Types & Interfaces](#types--interfaces)
4. [Data Fetching Hook](#data-fetching-hook)
5. [IntelligenceFeed Component](#intelligencefeed-component)
   - [Filter State Management](#filter-state-management)
   - [Deriving Filter Options](#deriving-filter-options)
   - [Filtering Logic](#filtering-logic)
   - [Sorting Logic](#sorting-logic)
   - [Shuffle Feature](#shuffle-feature)
6. [Masonry Layout](#masonry-layout)
7. [Filter Toolbar UI](#filter-toolbar-ui)
8. [Implementation Checklist](#implementation-checklist)

---

## Overview

The News Feed UI provides:

- **CSS Columns Masonry Layout**: Responsive multi-column grid that adapts to content height
- **Multi-dimensional Filtering**: Category, priority, source, company, time range
- **Flexible Sorting**: Newest, oldest, or by relevance score
- **Text Search**: Across title, headline, and summary
- **"Surprise Me" Shuffle**: Randomizes feed order for serendipitous discovery
- **Active Filter Pills**: Visual indicators of applied filters

---

## Component Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         page.tsx                                 │
│                    (calls useFeed hook)                          │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    IntelligenceFeed                              │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                   Filter Toolbar                             ││
│  │  [Search] [Category▼] [Priority▼] [Source▼] [Company▼]      ││
│  │  [Time▼] [Surprise Me] [Sort▼]                               ││
│  │  "Showing X of Y signals" [active filter pills]              ││
│  └─────────────────────────────────────────────────────────────┘│
│  ┌─────────────────────────────────────────────────────────────┐│
│  │               Masonry Grid (CSS Columns)                     ││
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐                     ││
│  │  │DigestCard│ │DigestCard│ │DigestCard│                     ││
│  │  │          │ │(featured)│ │          │                     ││
│  │  └──────────┘ └──────────┘ └──────────┘                     ││
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐                     ││
│  │  │DigestCard│ │DigestCard│ │DigestCard│                     ││
│  │  └──────────┘ └──────────┘ └──────────┘                     ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

---

## Types & Interfaces

```typescript
// types/index.ts

export type Priority = 'critical' | 'high' | 'medium' | 'low'

export type Category = string  // Your domain-specific categories

export interface DigestItem {
  id: string
  title: string
  headline: string | null       // AI-generated punchy headline
  summary: string | null        // AI summary for display
  url: string
  source_name: string
  source_type: string
  published_at: string | null   // ISO date string
  primary_category: Category
  priority: Priority | string
  relevance_score: number       // 0.0 - 1.0
  hero_image_url: string | null
  companies: string[]           // Extracted company mentions
  brands: string[]
  sentiment: 'positive' | 'negative' | 'neutral' | null
}

export interface DigestStats {
  total: number
  by_category: Record<string, number>  // category -> count
  by_priority: Record<string, number>  // priority -> count
  by_source: Record<string, number>    // source_name -> count
  avg_relevance: number
}
```

---

## Data Fetching Hook

```typescript
// hooks/useFeed.ts
'use client'

import { useState, useEffect, useCallback } from 'react'
import { api } from '@/lib/api'
import type { DigestItem, DigestStats } from '@/types'

interface UseFeedOptions {
  hours?: number              // Time window (default: 72)
  limit?: number              // Max articles (default: 50)
  autoRefresh?: boolean       // Enable polling
  refreshInterval?: number    // Poll interval in ms
}

interface UseFeedResult {
  items: DigestItem[]
  stats: DigestStats | null
  isLoading: boolean
  error: Error | null
  refresh: () => Promise<void>
}

export function useFeed(options: UseFeedOptions = {}): UseFeedResult {
  const {
    hours = 72,
    limit = 50,
    autoRefresh = false,
    refreshInterval = 5 * 60 * 1000,  // 5 minutes
  } = options

  const [items, setItems] = useState<DigestItem[]>([])
  const [stats, setStats] = useState<DigestStats | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)

  const fetchData = useCallback(async () => {
    try {
      setIsLoading(true)
      setError(null)

      // Fetch feed and stats in parallel
      const [feedResponse, statsResponse] = await Promise.all([
        api.getFeed({ hours, limit }),
        api.getStats(hours),
      ])

      setItems(feedResponse.articles.map(transformArticle))
      setStats(statsResponse)
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Failed to fetch'))
    } finally {
      setIsLoading(false)
    }
  }, [hours, limit])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  // Optional auto-refresh
  useEffect(() => {
    if (!autoRefresh) return
    const interval = setInterval(fetchData, refreshInterval)
    return () => clearInterval(interval)
  }, [autoRefresh, refreshInterval, fetchData])

  return { items, stats, isLoading, error, refresh: fetchData }
}

// Transform API response to frontend type
function transformArticle(article: any): DigestItem {
  return {
    id: article.id,
    title: article.title,
    headline: article.headline,
    summary: article.ai_summary || article.digest_summary,
    url: article.url,
    source_name: article.source_name,
    source_type: article.source_type,
    published_at: article.published_at,
    primary_category: article.primary_category,
    priority: article.digest_priority || article.priority,
    relevance_score: article.relevance_score,
    hero_image_url: article.hero_image_url,
    companies: article.companies || [],
    brands: article.brands || [],
    sentiment: null,
  }
}
```

---

## IntelligenceFeed Component

### Filter State Management

All filtering happens client-side for instant responsiveness:

```typescript
// Filter state declarations
const [searchQuery, setSearchQuery] = useState('')
const [selectedCategory, setSelectedCategory] = useState<string>('all')
const [selectedPriority, setSelectedPriority] = useState<string>('all')
const [selectedSource, setSelectedSource] = useState<string>('all')
const [selectedCompany, setSelectedCompany] = useState<string>('all')
const [timeRange, setTimeRange] = useState<string>('all')
const [sortBy, setSortBy] = useState<'newest' | 'oldest' | 'relevance'>('newest')

// Shuffle state
const [isShuffled, setIsShuffled] = useState(false)
const [shuffledOrder, setShuffledOrder] = useState<string[]>([])
```

### Deriving Filter Options

Dynamically derive available options from the data:

```typescript
// Sources: prefer stats if available, fallback to items
const availableSources = useMemo(() => {
  if (stats?.by_source) {
    return Object.keys(stats.by_source).sort()
  }
  const sources = new Set(items.map(item => item.source_name))
  return Array.from(sources).sort()
}, [items, stats])

// Categories: same pattern
const availableCategories = useMemo(() => {
  if (stats?.by_category) {
    return Object.keys(stats.by_category).sort()
  }
  const cats = new Set(items.map(item => item.primary_category))
  return Array.from(cats).sort()
}, [items, stats])

// Companies: top 50 by frequency (for performance)
const availableCompanies = useMemo(() => {
  const companyCounts = new Map<string, number>()
  items.forEach(item => {
    item.companies?.forEach(c => {
      companyCounts.set(c, (companyCounts.get(c) || 0) + 1)
    })
  })
  return Array.from(companyCounts.entries())
    .sort((a, b) => b[1] - a[1])  // Sort by frequency descending
    .slice(0, 50)                  // Top 50 only
    .map(([name]) => name)
    .sort()                        // Then alphabetical
}, [items])
```

### Filtering Logic

Apply all filters in a single `useMemo`:

```typescript
const filteredItems = useMemo(() => {
  let result = items.filter(item => {
    // 1. Text search (title, headline, summary)
    const matchesSearch = searchQuery === '' ||
      item.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.headline?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.summary?.toLowerCase().includes(searchQuery.toLowerCase())

    // 2. Category filter
    const matchesCategory = selectedCategory === 'all' || 
      item.primary_category === selectedCategory

    // 3. Priority filter
    const matchesPriority = selectedPriority === 'all' || 
      item.priority === selectedPriority

    // 4. Source filter
    const matchesSource = selectedSource === 'all' || 
      item.source_name === selectedSource

    // 5. Company filter (checks if company is in array)
    const matchesCompany = selectedCompany === 'all' || 
      (item.companies && item.companies.includes(selectedCompany))

    // 6. Time range filter
    let matchesTime = true
    if (timeRange !== 'all' && item.published_at) {
      const date = new Date(item.published_at)
      const now = new Date()
      const diffTime = Math.abs(now.getTime() - date.getTime())
      const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24))

      if (timeRange === 'today') matchesTime = diffDays <= 1
      if (timeRange === 'week') matchesTime = diffDays <= 7
      if (timeRange === 'month') matchesTime = diffDays <= 30
    }

    return matchesSearch && matchesCategory && matchesPriority && 
           matchesSource && matchesCompany && matchesTime
  })

  // Apply sorting (see next section)
  // ...

  return result
}, [items, searchQuery, selectedCategory, selectedPriority, 
    selectedSource, selectedCompany, timeRange, sortBy, 
    isShuffled, shuffledOrder])
```

### Sorting Logic

Three sort modes plus shuffle override:

```typescript
// Inside the filteredItems useMemo, after filtering:

if (isShuffled && shuffledOrder.length > 0) {
  // Shuffle mode: sort by pre-computed shuffled order
  result = result.sort((a, b) => {
    const indexA = shuffledOrder.indexOf(a.id)
    const indexB = shuffledOrder.indexOf(b.id)
    // Items not in shuffle order go to end
    if (indexA === -1) return 1
    if (indexB === -1) return -1
    return indexA - indexB
  })
} else {
  // Standard sorting
  result = result.sort((a, b) => {
    if (sortBy === 'newest') {
      const dateA = a.published_at ? new Date(a.published_at).getTime() : 0
      const dateB = b.published_at ? new Date(b.published_at).getTime() : 0
      return dateB - dateA  // Descending (newest first)
    }
    if (sortBy === 'oldest') {
      const dateA = a.published_at ? new Date(a.published_at).getTime() : 0
      const dateB = b.published_at ? new Date(b.published_at).getTime() : 0
      return dateA - dateB  // Ascending (oldest first)
    }
    // relevance
    return b.relevance_score - a.relevance_score  // Descending
  })
}
```

### Shuffle Feature

"Surprise Me" randomizes the feed for serendipitous discovery:

```typescript
const handleShuffle = () => {
  // Fisher-Yates shuffle of all item IDs
  const allIds = items.map(i => i.id)
  for (let i = allIds.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [allIds[i], allIds[j]] = [allIds[j], allIds[i]];
  }
  setShuffledOrder(allIds)
  setIsShuffled(true)
}

// Clear filters resets shuffle too
const clearFilters = () => {
  setSearchQuery('')
  setSelectedCategory('all')
  setSelectedPriority('all')
  setSelectedSource('all')
  setSelectedCompany('all')
  setTimeRange('all')
  setIsShuffled(false)
  setShuffledOrder([])
}

// Detect if any filters are active (for showing "Clear filters" button)
const hasFilters = searchQuery !== '' || 
  selectedCategory !== 'all' || 
  selectedPriority !== 'all' || 
  selectedSource !== 'all' || 
  selectedCompany !== 'all' || 
  timeRange !== 'all' || 
  isShuffled
```

---

## Masonry Layout

Use CSS `columns` for a simple, performant masonry grid:

```tsx
{/* Masonry Grid Container */}
<div className="flex-1 overflow-y-auto p-4 md:p-6">
  <div className="max-w-7xl mx-auto">
    {isLoading ? (
      // Loading skeleton
      <div className="columns-1 md:columns-2 xl:columns-3 gap-4">
        {[1, 2, 3, 4, 5, 6].map(i => (
          <div 
            key={i} 
            className="h-40 bg-white/50 rounded-2xl border animate-pulse mb-4 break-inside-avoid" 
          />
        ))}
      </div>
    ) : filteredItems.length > 0 ? (
      // Masonry grid with cards
      <div className="columns-1 md:columns-2 xl:columns-3 gap-4">
        {filteredItems.map((item, index) => {
          // Optional: feature one item for visual variety
          const isFeatured = filteredItems.length > 5 && index === 1
          
          return (
            <DigestCard
              key={item.id}
              item={item}
              onSelect={onSelectArticle}
              featured={isFeatured}
              className="shadow-sm"
            />
          )
        })}
      </div>
    ) : (
      // Empty state
      <div className="text-center py-20 bg-white rounded-3xl border border-dashed">
        <h3 className="text-lg font-semibold mb-2">No signals match your filters</h3>
        <p className="text-gray-500 mb-6">
          Try adjusting your search query or filters.
        </p>
        <button onClick={clearFilters} className="px-6 py-2 bg-gray-900 text-white rounded-xl">
          Clear All Filters
        </button>
      </div>
    )}
  </div>
</div>
```

**Key CSS classes for masonry:**

```css
/* The container uses CSS columns */
.columns-1 { column-count: 1; }
.md\:columns-2 { column-count: 2; }  /* 2 columns at md breakpoint */
.xl\:columns-3 { column-count: 3; }  /* 3 columns at xl breakpoint */
.gap-4 { column-gap: 1rem; }

/* Each card must have break-inside-avoid */
.break-inside-avoid { break-inside: avoid; }

/* Cards need margin-bottom (not gap) for vertical spacing */
.mb-4 { margin-bottom: 1rem; }
```

**DigestCard requirements:**

```tsx
<div className="... mb-4 break-inside-avoid">
  {/* Card content */}
</div>
```

---

## Filter Toolbar UI

Complete toolbar with all filter controls:

```tsx
<div className="shrink-0 p-4 border-b bg-white shadow-sm space-y-4">
  {/* Row 1: Search + Filters */}
  <div className="flex flex-wrap items-center gap-3">
    
    {/* Search Input */}
    <div className="relative flex-1 min-w-[200px]">
      <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={16} />
      <input
        type="text"
        placeholder="Search signals..."
        value={searchQuery}
        onChange={(e) => setSearchQuery(e.target.value)}
        className="w-full pl-10 pr-4 py-2 bg-gray-50 border rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20"
      />
    </div>

    {/* Category Filter */}
    <div className="flex items-center gap-2 bg-gray-50 border rounded-xl px-3 py-1.5">
      <Layers size={14} className="text-gray-400" />
      <select
        value={selectedCategory}
        onChange={(e) => setSelectedCategory(e.target.value)}
        className="bg-transparent text-sm font-medium focus:outline-none cursor-pointer"
      >
        <option value="all">All Categories</option>
        {availableCategories.map(cat => (
          <option key={cat} value={cat}>{cat.replace(/_/g, ' ')}</option>
        ))}
      </select>
    </div>

    {/* Priority Filter */}
    <div className="flex items-center gap-2 bg-gray-50 border rounded-xl px-3 py-1.5">
      <ShieldAlert size={14} className="text-gray-400" />
      <select
        value={selectedPriority}
        onChange={(e) => setSelectedPriority(e.target.value)}
        className="bg-transparent text-sm font-medium focus:outline-none cursor-pointer"
      >
        <option value="all">All Priorities</option>
        <option value="critical">Critical</option>
        <option value="high">High</option>
        <option value="medium">Medium</option>
        <option value="low">Low</option>
      </select>
    </div>

    {/* Source Filter */}
    <div className="flex items-center gap-2 bg-gray-50 border rounded-xl px-3 py-1.5">
      <Globe size={14} className="text-gray-400" />
      <select
        value={selectedSource}
        onChange={(e) => setSelectedSource(e.target.value)}
        className="bg-transparent text-sm font-medium focus:outline-none cursor-pointer max-w-[150px]"
      >
        <option value="all">All Sources</option>
        {availableSources.map(src => (
          <option key={src} value={src}>{src}</option>
        ))}
      </select>
    </div>

    {/* Company Filter */}
    <div className="flex items-center gap-2 bg-gray-50 border rounded-xl px-3 py-1.5">
      <Briefcase size={14} className="text-gray-400" />
      <select
        value={selectedCompany}
        onChange={(e) => setSelectedCompany(e.target.value)}
        className="bg-transparent text-sm font-medium focus:outline-none cursor-pointer max-w-[150px]"
      >
        <option value="all">All Companies</option>
        {availableCompanies.map(comp => (
          <option key={comp} value={comp}>{comp}</option>
        ))}
      </select>
    </div>

    {/* Time Range Filter */}
    <div className="flex items-center gap-2 bg-gray-50 border rounded-xl px-3 py-1.5">
      <Calendar size={14} className="text-gray-400" />
      <select
        value={timeRange}
        onChange={(e) => setTimeRange(e.target.value)}
        className="bg-transparent text-sm font-medium focus:outline-none cursor-pointer"
      >
        <option value="all">Any Time</option>
        <option value="today">Today</option>
        <option value="week">Last 7 Days</option>
        <option value="month">Last 30 Days</option>
      </select>
    </div>

    {/* Surprise Me Button */}
    <button
      onClick={handleShuffle}
      className={`flex items-center gap-2 px-3 py-1.5 rounded-xl border transition-all ${
        isShuffled
          ? "bg-violet-50 border-violet-200 text-violet-600"
          : "bg-gray-50 border-gray-200 text-gray-600 hover:bg-gray-100"
      }`}
    >
      <Shuffle size={14} />
      <span className="text-sm font-medium">Surprise Me</span>
    </button>

    {/* Sort Dropdown (pushed to right) */}
    <div className="flex items-center gap-2 bg-gray-50 border rounded-xl px-3 py-1.5 ml-auto">
      <ArrowUpDown size={14} className="text-gray-400" />
      <select
        value={sortBy}
        onChange={(e) => {
          setSortBy(e.target.value as any)
          setIsShuffled(false)  // Disable shuffle when sort changes
        }}
        className="bg-transparent text-sm font-medium focus:outline-none cursor-pointer"
      >
        <option value="newest">Newest First</option>
        <option value="oldest">Oldest First</option>
        <option value="relevance">Highly Relevant</option>
      </select>
    </div>
  </div>

  {/* Row 2: Results count + Active filter pills */}
  <div className="flex items-center justify-between pt-1">
    {/* Left: Count + Clear button */}
    <div className="flex items-center gap-2 text-xs text-gray-500">
      <span>
        Showing <b>{filteredItems.length}</b> of {items.length} signals
        {isShuffled && <span className="ml-1 text-violet-500 font-medium">(Shuffled)</span>}
      </span>
      {hasFilters && (
        <button
          onClick={clearFilters}
          className="flex items-center gap-1 text-blue-600 hover:underline font-medium ml-2"
        >
          <X size={12} />
          Clear filters
        </button>
      )}
    </div>

    {/* Right: Active filter pills */}
    <div className="flex gap-2">
      {selectedCategory !== 'all' && (
        <span className="px-2 py-0.5 bg-blue-500/10 text-blue-600 rounded-md text-[10px] font-bold uppercase">
          {selectedCategory.replace(/_/g, ' ')}
        </span>
      )}
      {selectedPriority !== 'all' && (
        <span className="px-2 py-0.5 bg-orange-500/10 text-orange-600 rounded-md text-[10px] font-bold uppercase">
          Priority: {selectedPriority}
        </span>
      )}
      {selectedSource !== 'all' && (
        <span className="px-2 py-0.5 bg-green-500/10 text-green-600 rounded-md text-[10px] font-bold uppercase">
          {selectedSource}
        </span>
      )}
      {selectedCompany !== 'all' && (
        <span className="px-2 py-0.5 bg-indigo-500/10 text-indigo-600 rounded-md text-[10px] font-bold uppercase">
          {selectedCompany}
        </span>
      )}
      {timeRange !== 'all' && (
        <span className="px-2 py-0.5 bg-amber-500/10 text-amber-600 rounded-md text-[10px] font-bold uppercase">
          {timeRange === 'week' ? 'Last 7 Days' : timeRange === 'month' ? 'Last 30 Days' : 'Today'}
        </span>
      )}
    </div>
  </div>
</div>
```

---

## Implementation Checklist

### Types
- [ ] `DigestItem` interface with all display fields
- [ ] `DigestStats` interface for filter option counts
- [ ] `Priority` and `Category` type definitions

### Data Hook (`useFeed`)
- [ ] Fetch articles and stats in parallel
- [ ] Transform API response to `DigestItem[]`
- [ ] Handle loading and error states
- [ ] Optional auto-refresh polling

### Filter State
- [ ] `searchQuery` - text search string
- [ ] `selectedCategory` - 'all' or category name
- [ ] `selectedPriority` - 'all' or priority level
- [ ] `selectedSource` - 'all' or source name
- [ ] `selectedCompany` - 'all' or company name
- [ ] `timeRange` - 'all', 'today', 'week', 'month'
- [ ] `sortBy` - 'newest', 'oldest', 'relevance'
- [ ] `isShuffled` + `shuffledOrder` for shuffle mode

### Derived Data (`useMemo`)
- [ ] `availableCategories` from stats or items
- [ ] `availableSources` from stats or items
- [ ] `availableCompanies` top 50 by frequency
- [ ] `filteredItems` with all filters + sorting applied
- [ ] `hasFilters` boolean for clear button visibility

### Masonry Layout
- [ ] CSS columns container: `columns-1 md:columns-2 xl:columns-3 gap-4`
- [ ] Cards with `mb-4 break-inside-avoid`
- [ ] Loading skeleton with same column layout
- [ ] Empty state with clear filters CTA

### Filter Toolbar
- [ ] Search input with icon
- [ ] Category dropdown (derived options)
- [ ] Priority dropdown (static options)
- [ ] Source dropdown (derived options)
- [ ] Company dropdown (derived top 50)
- [ ] Time range dropdown (static options)
- [ ] Surprise Me shuffle button
- [ ] Sort dropdown (disables shuffle on change)
- [ ] Results count display
- [ ] Active filter pills
- [ ] Clear filters button

---

*This guide covers the frontend filtering and masonry layout implementation. The backend pipeline and DigestCard component are assumed to already exist.*
