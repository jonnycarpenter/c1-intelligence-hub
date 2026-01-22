'use client'

import React, { useState, useMemo, useImperativeHandle, forwardRef, useCallback } from 'react'
import {
  ChevronDown,
  ChevronRight,
  TrendingUp,
  Radio,
  Clock,
  Flame,
  Sparkles,
  Loader2,
  X,
  Zap,
  Target,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { Badge, PriorityBadge, CategoryBadge } from '@/components/ui'
import DigestCard from '@/components/digest/DigestCard'
import AdHocBriefing from '@/components/dashboard/AdHocBriefing'
import { api } from '@/lib/api'
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
  // Handle both lowercase (frontend type) and Title Case (backend API)
  const p = priority?.toLowerCase()
  return p === 'critical' || p === 'high'
}

function isWithin72Hours(timestamp: string | undefined): boolean {
  if (!timestamp) return false
  const date = new Date(timestamp)
  const now = new Date()
  const diffHours = (now.getTime() - date.getTime()) / (1000 * 60 * 60)
  return diffHours <= 72
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

// Category display configuration - aligned with backend ContentCategory enum
// Supports both Title Case (backend) and legacy lowercase (old frontend)
const CATEGORY_CONFIG: Record<string, { label: string; color: string; bgLight: string }> = {
  // Backend categories (Title Case)
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
  // Legacy lowercase categories (backwards compatibility)
  'market': { label: 'Market Dynamics', color: 'border-l-blue-500', bgLight: 'bg-blue-50' },
  'supply-chain': { label: 'Supply Chain', color: 'border-l-orange-500', bgLight: 'bg-orange-50' },
  'regulatory': { label: 'Health & Regulatory', color: 'border-l-amber-500', bgLight: 'bg-amber-50' },
  'competitor': { label: 'Competitor Moves', color: 'border-l-rose-500', bgLight: 'bg-rose-50' },
  'pricing': { label: 'Pricing & Financial', color: 'border-l-emerald-500', bgLight: 'bg-emerald-50' },
  'product': { label: 'Product News', color: 'border-l-cyan-500', bgLight: 'bg-cyan-50' },
  'industry': { label: 'Industry Trends', color: 'border-l-indigo-500', bgLight: 'bg-indigo-50' },
}

// Category priority for sorting (lower = shown first)
// Supports both Title Case and legacy lowercase
const CATEGORY_PRIORITY: Record<string, number> = {
  // Title Case (backend)
  'C1 Mention': 0,
  'Competitor': 1,
  'Market': 2,
  'Regulatory': 3,
  'Earnings': 4,
  'Partnership': 5,
  'Expansion': 6,
  'Supply Chain': 7,
  'Logistics': 8,
  'Product': 9,
  'General': 10,
  // Legacy lowercase
  'competitor': 1,
  'market': 2,
  'regulatory': 3,
  'pricing': 4,
  'supply-chain': 7,
  'product': 9,
  'industry': 10,
}

// =============================================================================
// Sub-Components
// =============================================================================

interface CategoryAccordionProps {
  category: Category
  items: DigestItem[]
  onSelectArticle?: (id: string) => void
  onQuickFilter?: (query: string) => void
  defaultOpen?: boolean
}

function CategoryAccordion({
  category,
  items,
  onSelectArticle,
  onQuickFilter,
  defaultOpen = false
}: CategoryAccordionProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen)
  const [showAll, setShowAll] = useState(false)

  // AI Summary state
  const [summary, setSummary] = useState<DiscoverySummaryResponse | null>(null)
  const [isLoadingSummary, setIsLoadingSummary] = useState(false)
  const [isSummaryVisible, setIsSummaryVisible] = useState(false)

  const config = CATEGORY_CONFIG[category] || {
    label: category,
    color: 'border-l-slate-400',
    bgLight: 'bg-slate-50'
  }

  // Sort items: critical first, then high, then by timestamp
  const sortedItems = useMemo(() => {
    return [...items].sort((a, b) => {
      const priorityOrder = { critical: 0, high: 1, medium: 2, low: 3 }
      const aPriority = priorityOrder[a.priority] ?? 4
      const bPriority = priorityOrder[b.priority] ?? 4
      if (aPriority !== bPriority) return aPriority - bPriority
      // Then by timestamp (newest first)
      return new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
    })
  }, [items])

  const highPriorityCount = items.filter(i => isHighPriority(i.priority)).length
  const displayItems = showAll ? sortedItems : sortedItems.slice(0, 8)
  const hasMore = sortedItems.length > 8

  // Fetch AI Summary
  const handleFetchSummary = useCallback(async (e: React.MouseEvent) => {
    e.stopPropagation() // Don't toggle accordion

    // Toggle visibility if already loaded
    if (isSummaryVisible) {
      setIsSummaryVisible(false)
      return
    }

    setIsSummaryVisible(true)

    // Only fetch if not cached
    if (!summary) {
      setIsLoadingSummary(true)
      try {
        const data = await api.getDiscoverySummary(category)
        setSummary(data)
      } catch (err) {
        console.error('Failed to fetch summary:', err)
      } finally {
        setIsLoadingSummary(false)
      }
    }
  }, [category, isSummaryVisible, summary])

  return (
    <div className={cn(
      "border-l-4 rounded-r-lg bg-white shadow-sm overflow-hidden",
      config.color
    )}>
      {/* Header */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between p-4 hover:bg-slate-50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <span className="font-semibold text-slate-800">{config.label}</span>
          {highPriorityCount > 0 && (
            <span className="flex items-center gap-1 text-xs font-medium text-amber-600">
              <Flame size={12} />
              {highPriorityCount} urgent
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          {/* AI Summary Button */}
          <button
            onClick={handleFetchSummary}
            className={cn(
              "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-bold uppercase tracking-wider transition-all border shadow-sm",
              isSummaryVisible
                ? "bg-gradient-to-r from-teal-500 to-emerald-500 text-white border-white/20 ring-2 ring-teal-500/20 shadow-lg scale-105"
                : "bg-white text-teal-600 border-teal-500/30 hover:bg-teal-50 hover:border-teal-500/50 active:scale-95"
            )}
          >
            {isLoadingSummary ? (
              <Loader2 size={12} className="animate-spin" />
            ) : (
              <Sparkles
                size={12}
                className={cn(
                  "animate-sparkle",
                  isSummaryVisible ? "text-white" : "text-teal-500"
                )}
              />
            )}
            AI Summary
          </button>

          <span className="text-sm text-slate-500">{items.length} items</span>
          {isOpen ? <ChevronDown size={18} className="text-slate-400" /> : <ChevronRight size={18} className="text-slate-400" />}
        </div>
      </button>

      {/* ⭐ GLASSMORPHISM AI SUMMARY DRAWER */}
      {isSummaryVisible && (
        <div className="mx-4 mb-4 relative z-10 animate-in fade-in slide-in-from-top-2 duration-300">
          <div className="bg-slate-900/95 text-white rounded-xl p-6 shadow-2xl border border-white/10 backdrop-blur-xl relative overflow-hidden animate-float">
            {/* Ambient background glows */}
            <div className="absolute -top-24 -right-24 w-48 h-48 bg-teal-500/20 rounded-full blur-3xl pointer-events-none" />
            <div className="absolute -bottom-24 -left-24 w-48 h-48 bg-blue-500/20 rounded-full blur-3xl pointer-events-none" />

            {/* Close button */}
            <button
              onClick={() => setIsSummaryVisible(false)}
              className="absolute top-4 right-4 p-1.5 hover:bg-white/10 rounded-full transition-colors z-10"
            >
              <X size={14} />
            </button>

            {isLoadingSummary ? (
              /* Loading State */
              <div className="flex flex-col items-center justify-center py-10 space-y-4">
                <div className="relative">
                  <Loader2 size={32} className="animate-spin text-teal-500 opacity-80" />
                  <Sparkles size={14} className="absolute -top-1 -right-1 text-yellow-400 animate-pulse" />
                </div>
                <div className="text-center space-y-1">
                  <p className="text-sm font-bold tracking-tight">Synthesizing {config.label} Insights</p>
                  <p className="text-[10px] uppercase tracking-widest opacity-50 font-bold">LLM Thematic Analysis</p>
                </div>
              </div>
            ) : summary ? (
              /* Summary Content */
              <div className="space-y-6 relative z-10">
                {/* Header */}
                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <div className="flex items-center gap-2">
                      <Sparkles size={14} className="text-yellow-400" />
                      <h4 className="text-sm font-bold tracking-tight uppercase">
                        {config.label} — Strategic Themes
                      </h4>
                    </div>
                    <p className="text-[10px] uppercase tracking-widest opacity-60 font-black">
                      {summary.period_label} • {summary.article_count} Signals Processed
                    </p>
                  </div>
                </div>

                {/* Theme Cards Grid */}
                {summary.themes.length > 0 && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {summary.themes.map((theme, idx) => (
                      <div
                        key={idx}
                        className="group p-4 rounded-xl bg-white/5 border border-white/10 hover:bg-white/10 hover:border-white/20 transition-all duration-300"
                      >
                        <div className="flex items-start gap-3">
                          {/* Icon anchor */}
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
                <div className="pt-4 border-t border-white/10 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <Target size={14} className="text-pink-400" />
                    <p className="text-[11px] font-bold opacity-80 italic leading-snug">
                      {summary.one_off_summary}
                    </p>
                  </div>
                  <button
                    onClick={() => setIsOpen(true)}
                    className="shrink-0 flex items-center gap-1.5 text-[10px] uppercase font-black tracking-widest text-teal-400 hover:text-white transition-colors"
                  >
                    Explore all signals
                    <ChevronRight size={12} />
                  </button>
                </div>
              </div>
            ) : (
              /* Error State */
              <div className="py-6 text-center">
                <p className="text-sm opacity-60 italic">Failed to generate summary. Please try again.</p>
              </div>
            )}
          </div>

          {/* Stem connector triangle */}
          <div className="absolute -top-2 left-8 w-0 h-0 border-l-[8px] border-l-transparent border-r-[8px] border-r-transparent border-b-[8px] border-b-slate-900/95" />
        </div>
      )}

      {/* Content */}
      {isOpen && (
        <div className="border-t border-slate-100 p-4 space-y-3">
          {displayItems.map((item) => (
            <DigestCard key={item.id} item={item} onQuickFilter={onQuickFilter} />
          ))}

          {hasMore && !showAll && (
            <button
              onClick={() => setShowAll(true)}
              className="w-full py-2 text-sm text-teal-600 hover:text-teal-700 font-medium transition-colors"
            >
              Show all {sortedItems.length - 8} more →
            </button>
          )}
        </div>
      )}
    </div>
  )
}

// =============================================================================
// Main Component
// =============================================================================

const DiscoveryView = forwardRef<DiscoveryViewRef, DiscoveryViewProps>(
  function DiscoveryView({ items, stats, isLoading, error, onSelectArticle }, ref) {
    const [assistantQuery, setAssistantQuery] = useState<string | undefined>(undefined)

    // Expose openAssistant method to parent (no-op now since always visible)
    useImperativeHandle(ref, () => ({
      openAssistant: () => { } // Always visible now
    }))

    // Handle quick filter from entity click
    const handleQuickFilter = useCallback((query: string) => {
      setAssistantQuery(`Tell me more about ${query}`)
    }, [])

    // Group items by category
    const groupedByCategory = useMemo(() => groupByCategory(items), [items])

    // Sort categories by: 1) high-priority count desc, 2) category priority
    const sortedCategories = useMemo(() => {
      return Array.from(groupedByCategory.entries())
        .sort(([catA, itemsA], [catB, itemsB]) => {
          const highCountA = itemsA.filter(i => isHighPriority(i.priority)).length
          const highCountB = itemsB.filter(i => isHighPriority(i.priority)).length
          if (highCountA !== highCountB) return highCountB - highCountA
          return (CATEGORY_PRIORITY[catA] ?? 10) - (CATEGORY_PRIORITY[catB] ?? 10)
        })
    }, [groupedByCategory])

    // Right column: filter for high/critical + last 72h
    const latestHighPriority = useMemo(() => {
      return items
        .filter(item => isHighPriority(item.priority) && isWithin72Hours(item.timestamp))
        .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
        .slice(0, 15)
    }, [items])

    // Calculate stats
    const totalItems = items.length
    const criticalCount = items.filter(i => i.priority === 'critical').length
    const highCount = items.filter(i => i.priority === 'high').length

    // Build context for ad hoc assistant
    const adHocContext: AdHocBriefingContext = useMemo(() => {
      // Get top visible items from "Latest Urgent" and the first category
      const visibleItems = [
        ...latestHighPriority.slice(0, 5),
        ...(sortedCategories[0]?.[1]?.slice(0, 5) || [])
      ].filter(Boolean)

      return {
        active_category: 'Discovery Data Feed',
        visible_digest_items: visibleItems.map(item => ({
          title: item.title,
          source: item.sources?.[0]?.name || 'Unknown'
        })),
        // Add active filters logic if needed
        active_filters: []
      }
    }, [latestHighPriority, sortedCategories])

    return (
      <div className="h-full flex flex-col overflow-hidden bg-slate-200 p-4 gap-4">
        <div className="flex-1 flex gap-4 min-h-0">

          {/* Main Content Area */}
          <div className="flex-1 flex flex-col min-w-0 overflow-hidden bg-white rounded-2xl shadow-sm border border-slate-100/60">
            {/* Header */}
            <div className="shrink-0 px-6 py-4 bg-white border-b border-slate-200">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  {/* Live badge */}
                  <div className="flex items-center gap-1.5 px-2.5 py-1 bg-emerald-100 text-emerald-700 rounded-full">
                    <Radio size={12} className="animate-pulse" />
                    <span className="text-xs font-semibold">Live Intelligence</span>
                  </div>

                  {/* Greeting and stats */}
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

            {/* Ad Hoc Assistant (Inline, Top of Feed) */}
            {!isLoading && !error && (
              <div className="px-6 py-4 bg-slate-50 border-b border-slate-100">
                <AdHocBriefing
                  context={adHocContext}
                  compact={true}
                />
              </div>
            )}

            {/* Main 2-column grid */}
            {!isLoading && !error && (
              <div className="flex-1 overflow-hidden p-6">
                <div className="h-full flex gap-6">
                  {/* Left Column: Category Accordions (30-day) */}
                  <div className="flex-1 overflow-y-auto pr-2 scrollbar-thin scrollbar-thumb-slate-300">
                    <div className="flex items-center gap-2 mb-4">
                      <TrendingUp size={16} className="text-slate-500" />
                      <h2 className="text-sm font-semibold text-slate-600 uppercase tracking-wide">
                        By Category (30 days)
                      </h2>
                    </div>

                    <div className="space-y-3">
                      {sortedCategories.map(([category, categoryItems], index) => (
                        <CategoryAccordion
                          key={category}
                          category={category}
                          items={categoryItems}
                          onSelectArticle={onSelectArticle}
                          onQuickFilter={handleQuickFilter}
                          defaultOpen={index === 0}
                        />
                      ))}

                      {sortedCategories.length === 0 && (
                        <div className="text-center py-12 text-slate-500">
                          <p>No articles found in the last 30 days.</p>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Right Column: Latest High-Priority (72h) */}
                  <div className="w-[360px] shrink-0 overflow-y-auto pl-4 border-l border-slate-200 scrollbar-thin scrollbar-thumb-slate-300">
                    <div className="flex items-center gap-2 mb-4">
                      <Clock size={16} className="text-amber-500" />
                      <h2 className="text-sm font-semibold text-slate-600 uppercase tracking-wide">
                        Latest Urgent (72h)
                      </h2>
                      {latestHighPriority.length > 0 && (
                        <span className="ml-auto text-xs text-slate-400">
                          {latestHighPriority.length} items
                        </span>
                      )}
                    </div>

                    {latestHighPriority.length > 0 ? (
                      <div className="space-y-3">
                        {latestHighPriority.map((item) => (
                          <DigestCard key={item.id} item={item} onQuickFilter={handleQuickFilter} />
                        ))}
                      </div>
                    ) : (
                      <div className="text-center py-12 text-slate-500">
                        <div className="p-3 bg-slate-100 rounded-full w-fit mx-auto mb-3">
                          <Clock size={24} className="text-slate-400" />
                        </div>
                        <p className="font-medium mb-1">All quiet</p>
                        <p className="text-sm">No high-priority items in the last 72 hours.</p>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    )
  }
)

export default DiscoveryView
