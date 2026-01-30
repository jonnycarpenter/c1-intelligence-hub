'use client'

import React, { useState, useMemo, useImperativeHandle, forwardRef, useCallback, useRef } from 'react'
import {
  ChevronRight,
  TrendingUp,
  Radio,
  Flame,
  Sparkles,
  Loader2,
  X,
  Zap,
  Target,
  Layers,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import DigestCard from '@/components/digest/DigestCard'
import AdHocBriefing from '@/components/dashboard/AdHocBriefing'
import { api } from '@/lib/api'
import BulletinBoard from './BulletinBoard'
import type { DigestItem, DigestStats, Category, Priority, DiscoverySummaryResponse } from '@/types'

// =============================================================================
// Types
// =============================================================================

export interface DiscoveryViewProps {
  items: DigestItem[]           // All articles (30-day window)
  stats: DigestStats | null     // Aggregated statistics
  isLoading: boolean
  error: Error | null
  onSelectArticle?: (id: string) => void
}

export interface DiscoveryViewRef {
  openAssistant: () => void
}

type DetailMode = 'cards' | 'summary' | null

// =============================================================================
// Helper Functions
// =============================================================================

function getGreeting(): string {
  const hour = new Date().getHours()
  if (hour < 12) return 'Good morning'
  if (hour < 18) return 'Good afternoon'
  return 'Good evening'
}

function isHighPriority(priority: Priority): boolean {
  const p = priority?.toLowerCase()
  return p === 'critical' || p === 'high'
}

function groupByCategory(items: DigestItem[]): Map<Category, DigestItem[]> {
  const grouped = new Map<Category, DigestItem[]>()

  for (const item of items) {
    const category = item.category
    if (!grouped.has(category)) {
      grouped.set(category, [])
    }
    grouped.get(category)!.push(item)
  }

  return grouped
}

// Category display configuration
const CATEGORY_CONFIG: Record<string, { label: string; color: string; bgLight: string }> = {
  'Competitor': { label: 'Competitor Moves', color: 'border-l-rose-500', bgLight: 'bg-rose-50' },
  'Market': { label: 'Market Dynamics', color: 'border-l-blue-500', bgLight: 'bg-blue-50' },
  'Regulatory': { label: 'Health & Regulatory', color: 'border-l-amber-500', bgLight: 'bg-amber-50' },
  'Product': { label: 'Product News', color: 'border-l-cyan-500', bgLight: 'bg-cyan-50' },
  'Earnings': { label: 'Earnings & Financial', color: 'border-l-emerald-500', bgLight: 'bg-emerald-50' },
  'Partnership': { label: 'Partnerships', color: 'border-l-violet-500', bgLight: 'bg-violet-50' },
  'Expansion': { label: 'Expansion & Investment', color: 'border-l-teal-500', bgLight: 'bg-teal-50' },
  'Supply Chain': { label: 'Supply Chain', color: 'border-l-orange-500', bgLight: 'bg-orange-50' },
  'Logistics': { label: 'Logistics', color: 'border-l-yellow-500', bgLight: 'bg-yellow-50' },
  'C1 Mention': { label: 'C1 Mentions', color: 'border-l-pink-500', bgLight: 'bg-pink-50' },
  'General': { label: 'General', color: 'border-l-slate-400', bgLight: 'bg-slate-50' },
  // Legacy lowercase
  'market': { label: 'Market Dynamics', color: 'border-l-blue-500', bgLight: 'bg-blue-50' },
  'supply-chain': { label: 'Supply Chain', color: 'border-l-orange-500', bgLight: 'bg-orange-50' },
  'regulatory': { label: 'Health & Regulatory', color: 'border-l-amber-500', bgLight: 'bg-amber-50' },
  'competitor': { label: 'Competitor Moves', color: 'border-l-rose-500', bgLight: 'bg-rose-50' },
  'pricing': { label: 'Pricing & Financial', color: 'border-l-emerald-500', bgLight: 'bg-emerald-50' },
  'product': { label: 'Product News', color: 'border-l-cyan-500', bgLight: 'bg-cyan-50' },
  'industry': { label: 'Industry Trends', color: 'border-l-indigo-500', bgLight: 'bg-indigo-50' },
}

const CATEGORY_PRIORITY: Record<string, number> = {
  'C1 Mention': 0, 'Competitor': 1, 'Market': 2, 'Regulatory': 3, 'Earnings': 4,
  'Partnership': 5, 'Expansion': 6, 'Supply Chain': 7, 'Logistics': 8, 'Product': 9, 'General': 10,
  'competitor': 1, 'market': 2, 'regulatory': 3, 'pricing': 4, 'supply-chain': 7, 'product': 9, 'industry': 10,
}

// =============================================================================
// Category Row Component (simplified - no inline expansion)
// =============================================================================

interface CategoryRowProps {
  category: Category
  items: DigestItem[]
  isSelected: boolean
  selectedMode: DetailMode
  onSelectCategory: (category: Category) => void
  onShowSummary: (category: Category) => void
}

function CategoryRow({
  category,
  items,
  isSelected,
  selectedMode,
  onSelectCategory,
  onShowSummary,
}: CategoryRowProps) {
  const config = CATEGORY_CONFIG[category] || {
    label: category,
    color: 'border-l-slate-400',
    bgLight: 'bg-slate-50'
  }

  const highPriorityCount = items.filter(i => isHighPriority(i.priority)).length

  return (
    <div className={cn(
      "border-l-4 rounded-r-lg bg-white shadow-sm overflow-hidden transition-all duration-200",
      config.color,
      isSelected && "ring-2 ring-teal-500/30 shadow-md"
    )}>
      <div className="flex items-center justify-between p-4">
        {/* Left: Category info - click to show cards */}
        <button
          onClick={() => onSelectCategory(category)}
          className={cn(
            "flex items-center gap-3 hover:opacity-80 transition-opacity",
            isSelected && selectedMode === 'cards' && "text-teal-700"
          )}
        >
          <span className={cn(
            "font-semibold",
            isSelected && selectedMode === 'cards' ? "text-teal-700" : "text-slate-800"
          )}>
            {config.label}
          </span>
          {highPriorityCount > 0 && (
            <span className="flex items-center gap-1 text-xs font-medium text-amber-600">
              <Flame size={12} />
              {highPriorityCount} urgent
            </span>
          )}
          <span className="text-sm text-slate-400">{items.length} items</span>
          <ChevronRight size={16} className={cn(
            "text-slate-400 transition-transform",
            isSelected && selectedMode === 'cards' && "text-teal-500 rotate-90"
          )} />
        </button>

        {/* Right: AI Summary button */}
        <button
          onClick={(e) => {
            e.stopPropagation()
            onShowSummary(category)
          }}
          className={cn(
            "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-bold uppercase tracking-wider transition-all border shadow-sm",
            isSelected && selectedMode === 'summary'
              ? "bg-gradient-to-r from-teal-500 to-emerald-500 text-white border-white/20 ring-2 ring-teal-500/20 shadow-lg scale-105"
              : "bg-white text-teal-600 border-teal-500/30 hover:bg-teal-50 hover:border-teal-500/50 active:scale-95"
          )}
        >
          <Sparkles
            size={12}
            className={cn(
              isSelected && selectedMode === 'summary' ? "text-white" : "text-teal-500"
            )}
          />
          AI Summary
        </button>
      </div>
    </div>
  )
}

// =============================================================================
// Detail Panel Component (right side - shows cards or summary)
// =============================================================================

interface DetailPanelProps {
  category: Category | null
  items: DigestItem[]
  mode: DetailMode
  summary: DiscoverySummaryResponse | null
  isLoadingSummary: boolean
  onClose: () => void
  onQuickFilter: (query: string) => void
}

function DetailPanel({
  category,
  items,
  mode,
  summary,
  isLoadingSummary,
  onClose,
  onQuickFilter
}: DetailPanelProps) {
  const config = category ? CATEGORY_CONFIG[category] || { label: category, color: 'border-l-slate-400', bgLight: 'bg-slate-50' } : null

  // Sort items for display
  const sortedItems = useMemo(() => {
    return [...items].sort((a, b) => {
      const priorityOrder: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 }
      // Normalize priorities to lowercase for consistent lookup (backend sends Title Case)
      const aPriority = priorityOrder[a.priority?.toLowerCase()] ?? 4
      const bPriority = priorityOrder[b.priority?.toLowerCase()] ?? 4
      if (aPriority !== bPriority) return aPriority - bPriority
      return new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
    })
  }, [items])

  // Empty state
  if (!category || !mode) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-slate-400 p-8">
        <div className="p-4 bg-slate-100 rounded-full mb-4">
          <Layers size={32} className="text-slate-300" />
        </div>
        <p className="font-medium text-slate-500 mb-1">Select a category</p>
        <p className="text-sm text-center">Click a category to view articles, or click AI Summary for thematic analysis</p>
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="shrink-0 flex items-center justify-between px-4 py-3 border-b border-slate-200 bg-slate-50">
        <div className="flex items-center gap-2">
          {mode === 'summary' ? (
            <Sparkles size={16} className="text-teal-500" />
          ) : (
            <TrendingUp size={16} className="text-slate-500" />
          )}
          <h2 className="text-sm font-semibold text-slate-700">
            {config?.label} {mode === 'summary' ? '— AI Summary' : `(${items.length} articles)`}
          </h2>
        </div>
        <button
          onClick={onClose}
          className="p-1.5 hover:bg-slate-200 rounded-lg transition-colors"
        >
          <X size={16} className="text-slate-400" />
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto scrollbar-thin scrollbar-thumb-slate-300">
        {mode === 'summary' ? (
          // AI Summary View
          <div className="p-4">
            {isLoadingSummary ? (
              <div className="flex flex-col items-center justify-center py-16 space-y-4">
                <div className="relative">
                  <Loader2 size={32} className="animate-spin text-teal-500 opacity-80" />
                  <Sparkles size={14} className="absolute -top-1 -right-1 text-yellow-400 animate-pulse" />
                </div>
                <div className="text-center space-y-1">
                  <p className="text-sm font-bold tracking-tight text-slate-700">Synthesizing {config?.label} Insights</p>
                  <p className="text-[10px] uppercase tracking-widest text-slate-400 font-bold">LLM Thematic Analysis</p>
                </div>
              </div>
            ) : summary ? (
              <div className="bg-slate-900/95 text-white rounded-xl p-6 shadow-2xl border border-white/10 relative overflow-hidden">
                {/* Ambient background glows */}
                <div className="absolute -top-24 -right-24 w-48 h-48 bg-teal-500/20 rounded-full blur-3xl pointer-events-none" />
                <div className="absolute -bottom-24 -left-24 w-48 h-48 bg-blue-500/20 rounded-full blur-3xl pointer-events-none" />

                <div className="space-y-6 relative z-10">
                  {/* Header */}
                  <div className="space-y-0.5">
                    <div className="flex items-center gap-2">
                      <Sparkles size={14} className="text-yellow-400" />
                      <h4 className="text-sm font-bold tracking-tight uppercase">
                        {config?.label} — Strategic Themes
                      </h4>
                    </div>
                    <p className="text-[10px] uppercase tracking-widest opacity-60 font-black">
                      {summary.period_label} • {summary.article_count} Signals Processed
                    </p>
                  </div>

                  {/* Theme Cards */}
                  {summary.themes.length > 0 && (
                    <div className="space-y-3">
                      {summary.themes.map((theme, idx) => (
                        <div
                          key={idx}
                          className="group p-4 rounded-xl bg-white/5 border border-white/10 hover:bg-white/10 hover:border-white/20 transition-all duration-300"
                        >
                          <div className="flex items-start gap-3">
                            <div className="w-8 h-8 shrink-0 flex items-center justify-center rounded-lg bg-gradient-to-br from-white/10 to-white/5 border border-white/10 group-hover:from-teal-500/20 group-hover:to-blue-500/20 transition-colors">
                              {idx === 0 ? (
                                <TrendingUp size={16} className="text-teal-400" />
                              ) : (
                                <Zap size={16} className="text-blue-400" />
                              )}
                            </div>
                            <div className="space-y-1">
                              <h5 className="text-sm font-bold leading-tight group-hover:text-teal-400 transition-colors">
                                {theme.title}
                              </h5>
                              <p className="text-xs leading-relaxed opacity-70 font-medium italic">
                                &quot;{theme.content}&quot;
                              </p>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* One-off Summary Footer */}
                  <div className="pt-4 border-t border-white/10">
                    <div className="flex items-start gap-2">
                      <Target size={14} className="text-pink-400 shrink-0 mt-0.5" />
                      <p className="text-[11px] font-bold opacity-80 italic leading-snug">
                        {summary.one_off_summary}
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-center py-16 text-slate-500">
                <p className="text-sm italic">Failed to generate summary. Please try again.</p>
              </div>
            )}
          </div>
        ) : (
          // Cards View
          <div className="p-4 space-y-3">
            {sortedItems.map((item) => (
              <DigestCard key={item.id} item={item} onQuickFilter={onQuickFilter} />
            ))}
            {sortedItems.length === 0 && (
              <div className="text-center py-12 text-slate-500">
                <p>No articles in this category.</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

// =============================================================================
// Main Component
// =============================================================================

const DiscoveryView = forwardRef<DiscoveryViewRef, DiscoveryViewProps>(
  function DiscoveryView({ items, stats, isLoading, error, onSelectArticle }, ref) {
    // Detail panel state
    const [selectedCategory, setSelectedCategory] = useState<Category | null>(null)
    const [detailMode, setDetailMode] = useState<DetailMode>(null)
    const [summary, setSummary] = useState<DiscoverySummaryResponse | null>(null)
    const [isLoadingSummary, setIsLoadingSummary] = useState(false)

    // Cache for summaries
    const summaryCache = useRef<Map<string, DiscoverySummaryResponse>>(new Map())

    // AdHocBriefing initial query from entity clicks
    const [assistantQuery, setAssistantQuery] = useState<string | undefined>(undefined)

    useImperativeHandle(ref, () => ({
      openAssistant: () => { }
    }))

    // Handle entity click -> populate assistant
    const handleQuickFilter = useCallback((query: string) => {
      setAssistantQuery(`Tell me more about ${query}`)
    }, [])

    // Group and sort categories
    const groupedByCategory = useMemo(() => groupByCategory(items), [items])

    const sortedCategories = useMemo(() => {
      return Array.from(groupedByCategory.entries())
        .sort(([catA, itemsA], [catB, itemsB]) => {
          const highCountA = itemsA.filter(i => isHighPriority(i.priority)).length
          const highCountB = itemsB.filter(i => isHighPriority(i.priority)).length
          if (highCountA !== highCountB) return highCountB - highCountA
          return (CATEGORY_PRIORITY[catA] ?? 10) - (CATEGORY_PRIORITY[catB] ?? 10)
        })
    }, [groupedByCategory])

    // Get items for selected category
    const selectedItems = useMemo(() => {
      if (!selectedCategory) return []
      return groupedByCategory.get(selectedCategory) || []
    }, [selectedCategory, groupedByCategory])

    // Calculate stats
    const totalItems = items.length
    const criticalCount = items.filter(i => i.priority === 'critical').length
    const highCount = items.filter(i => i.priority === 'high').length

    // Handle category selection (show cards)
    const handleSelectCategory = useCallback((category: Category) => {
      if (selectedCategory === category && detailMode === 'cards') {
        // Toggle off if already selected
        setSelectedCategory(null)
        setDetailMode(null)
      } else {
        setSelectedCategory(category)
        setDetailMode('cards')
        setSummary(null) // Clear summary when switching to cards
      }
    }, [selectedCategory, detailMode])

    // Handle AI Summary request
    const handleShowSummary = useCallback(async (category: Category) => {
      if (selectedCategory === category && detailMode === 'summary') {
        // Toggle off
        setSelectedCategory(null)
        setDetailMode(null)
        return
      }

      setSelectedCategory(category)
      setDetailMode('summary')

      // Check cache first
      const cached = summaryCache.current.get(category)
      if (cached) {
        setSummary(cached)
        return
      }

      // Fetch summary
      setIsLoadingSummary(true)
      setSummary(null)

      try {
        const data = await api.getDiscoverySummary(category)
        setSummary(data)
        summaryCache.current.set(category, data) // Cache it
      } catch (err) {
        console.error('Failed to fetch summary:', err)
        setSummary(null)
      } finally {
        setIsLoadingSummary(false)
      }
    }, [selectedCategory, detailMode])

    // Close detail panel
    const handleCloseDetail = useCallback(() => {
      setSelectedCategory(null)
      setDetailMode(null)
    }, [])

    return (
      <div className="h-full flex flex-col overflow-hidden bg-slate-200 p-4 gap-4">
        {/* Main Content Area */}
        <div className="flex-1 flex flex-col min-w-0 overflow-hidden bg-white rounded-2xl shadow-sm border border-slate-100/60">
          {/* Header */}
          <div className="shrink-0 px-6 py-4 bg-white border-b border-slate-200">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-1.5 px-2.5 py-1 bg-emerald-100 text-emerald-700 rounded-full">
                  <Radio size={12} className="animate-pulse" />
                  <span className="text-xs font-semibold">Live Intelligence</span>
                </div>
                <div>
                  <h1 className="text-xl font-bold text-slate-800">{getGreeting()}, Team</h1>
                  <p className="text-sm text-slate-500">
                    We've analyzed <span className="font-medium text-slate-700">{totalItems}</span> signals
                    {criticalCount > 0 && (
                      <span className="ml-1">
                        • <span className="text-red-600 font-medium">{criticalCount} critical</span>
                      </span>
                    )}
                    {highCount > 0 && (
                      <span className="ml-1">
                        • <span className="text-emerald-600 font-medium">{highCount} high priority</span>
                      </span>
                    )}
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Priority Spotlight - AI-generated guidance */}
          <div className="shrink-0 px-6 py-3 border-b border-slate-100">
            <BulletinBoard />
          </div>

          {/* Ask about the feed */}
          <div className="shrink-0 px-6 py-3 border-b border-slate-100">
            <AdHocBriefing compact initialQuery={assistantQuery} />
          </div>

          {/* Loading state */}
          {isLoading && (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center">
                <div className="animate-spin w-8 h-8 border-2 border-teal-500 border-t-transparent rounded-full mx-auto mb-3" />
                <p className="text-slate-500">Loading intelligence feed...</p>
              </div>
            </div>
          )}

          {/* Error state */}
          {error && (
            <div className="flex-1 flex items-center justify-center p-6">
              <div className="text-center bg-red-50 text-red-700 rounded-xl p-6 max-w-md">
                <p className="font-medium mb-1">Failed to load data</p>
                <p className="text-sm">{error.message}</p>
              </div>
            </div>
          )}

          {/* Main 2-column grid */}
          {!isLoading && !error && (
            <div className="flex-1 overflow-hidden p-6">
              <div className="h-full flex gap-6">
                {/* Left Column: Category List */}
                <div className="w-[400px] shrink-0 overflow-y-auto pr-2 scrollbar-thin scrollbar-thumb-slate-300">
                  <div className="flex items-center gap-2 mb-4">
                    <TrendingUp size={16} className="text-slate-500" />
                    <h2 className="text-sm font-semibold text-slate-600 uppercase tracking-wide">
                      By Category (30 days)
                    </h2>
                  </div>

                  <div className="space-y-2">
                    {sortedCategories.map(([category, categoryItems]) => (
                      <CategoryRow
                        key={category}
                        category={category}
                        items={categoryItems}
                        isSelected={selectedCategory === category}
                        selectedMode={selectedCategory === category ? detailMode : null}
                        onSelectCategory={handleSelectCategory}
                        onShowSummary={handleShowSummary}
                      />
                    ))}

                    {sortedCategories.length === 0 && (
                      <div className="text-center py-12 text-slate-500">
                        <p>No articles found in the last 30 days.</p>
                      </div>
                    )}
                  </div>
                </div>

                {/* Right Column: Detail Panel */}
                <div className="flex-1 border-l border-slate-200 pl-6">
                  <DetailPanel
                    category={selectedCategory}
                    items={selectedItems}
                    mode={detailMode}
                    summary={summary}
                    isLoadingSummary={isLoadingSummary}
                    onClose={handleCloseDetail}
                    onQuickFilter={handleQuickFilter}
                  />
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    )
  }
)

export default DiscoveryView
