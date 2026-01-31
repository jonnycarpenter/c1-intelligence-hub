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
  LayoutGrid,
  Rows3,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import DigestCard from '@/components/digest/DigestCard'
import AdHocBriefing from '@/components/dashboard/AdHocBriefing'
import { api } from '@/lib/api'
import BulletinBoard from './BulletinBoard'
import FullFeedView from './FullFeedView'
import type { DigestItem, DigestStats, Category, Priority, DiscoverySummaryResponse } from '@/types'
import type { AdHocBriefingContext } from '@/types/briefing'

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
type SubTab = 'themes' | 'fullFeed'

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
// Category Row Component (aligned grid layout)
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
      "border-l-4 rounded-r-lg bg-white shadow-sm overflow-hidden transition-all duration-200 group",
      config.color,
      isSelected && "ring-2 ring-teal-500/30 shadow-md"
    )}>
      <div className="grid grid-cols-[200px_1fr_70px_120px] items-center p-2">
        {/* Label Column - Clickable */}
        <button
          onClick={() => onSelectCategory(category)}
          className="flex items-center gap-2 text-left hover:opacity-70 transition-opacity min-w-0"
        >
          <span className={cn(
            "font-bold truncate text-sm",
            isSelected && selectedMode === 'cards' ? "text-teal-700" : "text-slate-700"
          )}>
            {config.label}
          </span>
          <ChevronRight size={14} className={cn(
            "text-slate-300 transition-transform shrink-0",
            isSelected && selectedMode === 'cards' && "text-teal-500 rotate-90"
          )} />
        </button>

        {/* Priority Column - Clickable */}
        <button
          onClick={() => onSelectCategory(category)}
          className="flex items-center justify-start hover:opacity-70 transition-opacity"
        >
          {highPriorityCount > 0 ? (
            <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-amber-50 border border-amber-100 text-[10px] font-bold text-amber-600 uppercase tracking-wide">
              <Flame size={10} className="fill-amber-500 text-amber-500" />
              {highPriorityCount} High Priority
            </span>
          ) : <span />}
        </button>

        {/* Count Column - Clickable */}
        <button
          onClick={() => onSelectCategory(category)}
          className="text-right hover:opacity-70 transition-opacity"
        >
          <span className="text-xs font-semibold text-slate-400">{items.length} items</span>
        </button>

        {/* Action Column - AI Summary Button */}
        <div className="flex justify-end pl-2">
          <button
            onClick={(e) => {
              e.stopPropagation()
              onShowSummary(category)
            }}
            className={cn(
              "flex items-center justify-center gap-2 w-full py-1.5 rounded-md text-[10px] font-bold uppercase tracking-wider transition-all",
              isSelected && selectedMode === 'summary'
                ? "bg-teal-600 text-white shadow-lg ring-2 ring-teal-200"
                : "bg-slate-50 text-slate-600 hover:bg-teal-50 hover:text-teal-700 border border-slate-100 hover:border-teal-200"
            )}
          >
            <Sparkles
              size={12}
              className={cn(
                isSelected && selectedMode === 'summary' ? "text-yellow-300 fill-yellow-300" : "text-slate-400 group-hover:text-teal-500"
              )}
            />
            AI Summary
          </button>
        </div>
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
  // For enhanced empty state
  allItems?: DigestItem[]
  categoryCount?: number
}

function DetailPanel({
  category,
  items,
  mode,
  summary,
  isLoadingSummary,
  onClose,
  onQuickFilter,
  allItems = [],
  categoryCount = 0
}: DetailPanelProps) {
  const config = category ? CATEGORY_CONFIG[category] || { label: category, color: 'border-l-slate-400', bgLight: 'bg-slate-50' } : null

  // Get top 3 priority signals for empty state preview
  const topSignals = useMemo(() => {
    return [...allItems]
      .sort((a, b) => {
        const priorityOrder: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 }
        const aPriority = priorityOrder[a.priority?.toLowerCase()] ?? 4
        const bPriority = priorityOrder[b.priority?.toLowerCase()] ?? 4
        if (aPriority !== bPriority) return aPriority - bPriority
        return new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
      })
      .slice(0, 3)
  }, [allItems])

  // Sort items for display (used when showing cards)
  const sortedItems = useMemo(() => {
    return [...items].sort((a, b) => {
      const priorityOrder: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 }
      const aPriority = priorityOrder[a.priority?.toLowerCase()] ?? 4
      const bPriority = priorityOrder[b.priority?.toLowerCase()] ?? 4
      if (aPriority !== bPriority) return aPriority - bPriority
      return new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
    })
  }, [items])

  // Empty state - enhanced with top signals preview
  if (!category || !mode) {
    const totalHighPriority = allItems.filter(i =>
      i.priority?.toLowerCase() === 'critical' || i.priority?.toLowerCase() === 'high'
    ).length

    return (
      <div className="h-full flex flex-col p-6">
        {/* Header with pulse summary */}
        <div className="mb-6">
          <div className="flex items-center gap-2 mb-2">
            <div className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse" />
            <h3 className="text-sm font-bold uppercase tracking-wide text-slate-600">
              Intelligence Overview
            </h3>
          </div>
          <p className="text-2xl font-bold text-slate-800">
            <span className="text-teal-600">{totalHighPriority}</span> priority signals across{' '}
            <span className="text-teal-600">{categoryCount}</span> categories
          </p>
          <p className="text-sm text-slate-500 mt-1">
            Select a category to explore, or click AI Summary for instant analysis
          </p>
        </div>

        {/* Top Signals Preview */}
        {topSignals.length > 0 && (
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-3">
              <Zap size={14} className="text-amber-500" />
              <h4 className="text-xs font-bold uppercase tracking-wide text-slate-500">
                Today's Top Signals
              </h4>
            </div>
            <div className="space-y-3">
              {topSignals.map((item, idx) => {
                const itemConfig = CATEGORY_CONFIG[item.category] || {
                  label: item.category,
                  color: 'border-l-slate-400',
                  bgLight: 'bg-slate-50'
                }
                return (
                  <div
                    key={item.id}
                    className={cn(
                      "p-4 rounded-xl border-l-4 bg-gradient-to-r from-white to-slate-50/50 shadow-sm hover:shadow-md transition-all cursor-default",
                      itemConfig.color
                    )}
                  >
                    <div className="flex items-start gap-3">
                      <div className="shrink-0 w-6 h-6 rounded-full bg-slate-100 flex items-center justify-center text-xs font-bold text-slate-500">
                        {idx + 1}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className={cn(
                            "text-[10px] font-bold uppercase tracking-wide px-1.5 py-0.5 rounded",
                            item.priority?.toLowerCase() === 'critical'
                              ? "bg-red-100 text-red-700"
                              : "bg-amber-100 text-amber-700"
                          )}>
                            {item.priority}
                          </span>
                          <span className="text-[10px] text-slate-400 font-medium">
                            {itemConfig.label}
                          </span>
                        </div>
                        <p className="text-sm font-semibold text-slate-800 line-clamp-2 leading-snug">
                          {item.title}
                        </p>
                        {item.summary && (
                          <p className="text-xs text-slate-500 mt-1 line-clamp-1">
                            {item.summary}
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* Fallback if no items */}
        {topSignals.length === 0 && (
          <div className="flex-1 flex items-center justify-center text-slate-400">
            <div className="text-center">
              <Layers size={32} className="mx-auto mb-2 text-slate-300" />
              <p className="text-sm">No signals to display</p>
            </div>
          </div>
        )}
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
    // Sub-tab state
    const [activeSubTab, setActiveSubTab] = useState<SubTab>('themes')

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

    // Build context for the Ad Hoc assistant - makes it aware of visible items
    const adHocContext: AdHocBriefingContext = useMemo(() => {
      // Get top digest items (prioritizing high/critical, limit to 15 for prompt size)
      const topItems = items
        .sort((a, b) => {
          const priorityOrder: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 }
          return (priorityOrder[a.priority?.toLowerCase()] ?? 4) - (priorityOrder[b.priority?.toLowerCase()] ?? 4)
        })
        .slice(0, 15)
        .map(item => ({
          title: item.title,
          summary: item.summary,
          source_name: item.sources?.[0]?.name,
          category: item.category,
          priority: item.priority,
        }))

      return {
        visible_digest_items: topItems,
        active_category: selectedCategory || undefined,
        recent_digest_topics: Array.from(groupedByCategory.keys()),
      }
    }, [items, selectedCategory, groupedByCategory])

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

    // Ad-hoc assistant collapsed state - starts collapsed unless there's a query
    const [isAssistantExpanded, setIsAssistantExpanded] = useState(false)

    // Auto-expand when assistantQuery is set (e.g., from entity clicks)
    React.useEffect(() => {
      if (assistantQuery) {
        setIsAssistantExpanded(true)
      }
    }, [assistantQuery])

    return (
      <div className="h-full overflow-y-auto bg-slate-200 p-4">
        {/* Main Content Area */}
        <div className="min-h-full flex flex-col bg-white rounded-2xl shadow-sm border border-slate-100/60">
          {/* Header removed for cleaner layout */}
          <div className="h-2" />

          {/* Priority Spotlight - AI-generated guidance */}
          <div className="shrink-0 px-6 py-3 border-b border-slate-100">
            <BulletinBoard />
          </div>

          {/* Ask about the feed - Collapsible section */}
          <div className="shrink-0 px-6 py-3 border-b border-slate-100">
            <button
              onClick={() => setIsAssistantExpanded(!isAssistantExpanded)}
              className="w-full flex items-center justify-between p-3 rounded-xl bg-gradient-to-r from-emerald-50 to-teal-50 border border-emerald-200/50 hover:from-emerald-100 hover:to-teal-100 transition-colors"
            >
              <div className="flex items-center gap-2">
                <Sparkles size={16} className="text-emerald-600" />
                <span className="text-sm font-medium text-emerald-800">Ask about the feed...</span>
              </div>
              <ChevronRight
                size={16}
                className={cn(
                  "text-emerald-500 transition-transform duration-200",
                  isAssistantExpanded && "rotate-90"
                )}
              />
            </button>
            {isAssistantExpanded && (
              <div className="mt-3 max-h-[400px] overflow-y-auto scrollbar-thin scrollbar-thumb-slate-300">
                <AdHocBriefing compact initialQuery={assistantQuery} context={adHocContext} />
              </div>
            )}
          </div>

          {/* Sub-tab Navigation */}
          <div className="shrink-0 px-6 py-3 border-b border-slate-200 bg-slate-50/50">
            <div className="flex items-center gap-2">
              <button
                onClick={() => setActiveSubTab('themes')}
                className={cn(
                  "flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all",
                  activeSubTab === 'themes'
                    ? "bg-white shadow-sm border border-slate-200 text-slate-800"
                    : "text-slate-500 hover:text-slate-700 hover:bg-white/50"
                )}
              >
                <LayoutGrid size={16} />
                Themes
              </button>
              <button
                onClick={() => setActiveSubTab('fullFeed')}
                className={cn(
                  "flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all",
                  activeSubTab === 'fullFeed'
                    ? "bg-white shadow-sm border border-slate-200 text-slate-800"
                    : "text-slate-500 hover:text-slate-700 hover:bg-white/50"
                )}
              >
                <Rows3 size={16} />
                Full Feed
              </button>
            </div>
          </div>

          {/* Loading state */}
          {isLoading && (
            <div className="flex-1 flex items-center justify-center py-16">
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

          {/* Content Area: Themes or Full Feed */}
          {!isLoading && !error && (
            <>
              {activeSubTab === 'themes' ? (
                /* Themes View - Original 2-column grid */
                <div className="flex-1 p-6">
                  <div className="flex gap-6" style={{ minHeight: '500px' }}>
                    {/* Left Column: Category List */}
                    <div className="w-[480px] shrink-0">
                      <div className="flex items-center gap-2 mb-4">
                        <TrendingUp size={16} className="text-slate-500" />
                        <h2 className="text-sm font-semibold text-slate-600 uppercase tracking-wide">
                          Category Themes
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
                    <div className="flex-1 border-l border-slate-200 pl-6 min-h-[400px]">
                      <DetailPanel
                        category={selectedCategory}
                        items={selectedItems}
                        mode={detailMode}
                        summary={summary}
                        isLoadingSummary={isLoadingSummary}
                        onClose={handleCloseDetail}
                        onQuickFilter={handleQuickFilter}
                        allItems={items}
                        categoryCount={sortedCategories.length}
                      />
                    </div>
                  </div>
                </div>
              ) : (
                /* Full Feed View - Masonry layout with filters */
                <FullFeedView
                  items={items}
                  stats={stats}
                  isLoading={isLoading}
                  error={error}
                  onQuickFilter={handleQuickFilter}
                />
              )}
            </>
          )}
        </div>
      </div>
    )
  }
)

export default DiscoveryView
