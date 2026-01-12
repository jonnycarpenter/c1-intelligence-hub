'use client'

import React, { useState, useMemo, useCallback } from 'react'
import DigestCard from '../digest/DigestCard'
import EntityAggregator from '../digest/EntityAggregator'
import BriefingSection from './BriefingSection'
import WeeklyBriefingSection from './WeeklyBriefingSection'
import AdHocBriefing from './AdHocBriefing'
import BriefingHistoryTimeline from './BriefingHistoryTimeline'
import { useBriefing, useWeeklyBriefing } from '@/hooks'
import { Calendar, Activity, Search, X } from 'lucide-react'
import { cn } from '@/lib/utils'

import type { DigestItem } from '@/types'
import type { AdHocBriefingContext } from '@/types/briefing'

interface PulseDashboardProps {
  digestItems: DigestItem[]
  stats?: any  // Optional, not currently displayed
  isLoading: boolean
  error: Error | null
  onAskAbout: (item: DigestItem) => void
  onAddToReport: (item: DigestItem) => void
  onDeepResearch?: (query: string) => void  // Optional callback for deep research
}

export default function PulseDashboard({
  digestItems,
  isLoading: digestLoading,
  error,
  onAskAbout,
  onAddToReport,
  onDeepResearch,
}: PulseDashboardProps) {
  // Use the new weekly briefing hook
  const { briefing: weeklyBriefing, isLoading: weeklyLoading } = useWeeklyBriefing()
  // Keep legacy briefings as fallback
  const { briefings: legacyBriefings, isLoading: legacyLoading } = useBriefing()

  // State for history timeline modal
  const [isHistoryOpen, setIsHistoryOpen] = useState(false)

  // Entity filter state
  const [selectedEntities, setSelectedEntities] = useState<Set<string>>(new Set())

  // State for search and filters
  const [searchQuery, setSearchQuery] = useState('')
  const [sortBy, setSortBy] = useState<'newest' | 'priority'>('newest')
  const [timeFilter, setTimeFilter] = useState<'24h' | '3d' | '7d' | 'all'>('all')

  // Toggle entity selection
  const handleEntityToggle = useCallback((entity: string) => {
    setSelectedEntities(prev => {
      const next = new Set(prev)
      if (next.has(entity)) {
        next.delete(entity)
      } else {
        next.add(entity)
      }
      return next
    })
  }, [])

  // Clear all filters
  const handleClearFilters = useCallback(() => {
    setSelectedEntities(new Set())
    setSearchQuery('')
    setTimeFilter('all')
  }, [])

  // Filter digest items based on selected entities, search query, and time
  const filteredItems = useMemo(() => {
    let items = digestItems || []

    // 1. Filter by Entity
    if (selectedEntities.size > 0) {
      items = items.filter(item => {
        if (!item.entities) return false
        const allItemEntities = [
          ...(item.entities.companies || []),
          ...(item.entities.materials || []),
          ...(item.entities.topics || []),
          ...(item.entities.industries || []),
        ]
        return allItemEntities.some(entity => selectedEntities.has(entity))
      })
    }

    // 2. Filter by Search Query
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase()
      items = items.filter(item =>
        (item.title && item.title.toLowerCase().includes(query)) ||
        (item.summary && item.summary.toLowerCase().includes(query)) ||
        (item.entities?.companies?.some(c => c.toLowerCase().includes(query)))
      )
    }

    // 3. Filter by Time (Simple approximation based on timestamp string or publishedAt)
    // Note: This assumes 'timestamp' is somewhat parseable or we have 'publishedAt'. 
    // If strict time filtering is needed, we'd need reliable Date objects. 
    // For now, we'll skip complex time parsing if data isn't standardized, 
    // but here is a placeholder logic:
    /*
    if (timeFilter !== 'all') {
      const now = new Date()
      // Filter logic would go here
    }
    */

    // 4. Sort
    if (sortBy === 'priority') {
      const priorityOrder = { critical: 3, high: 2, medium: 1, low: 0 }
      items = [...items].sort((a, b) => (priorityOrder[b.priority] || 0) - (priorityOrder[a.priority] || 0))
    }
    // Default is 'newest' (assuming input array is already sorted by date, or we could sort by timestamp)

    return items
  }, [digestItems, selectedEntities, searchQuery, sortBy, timeFilter])

  // Build context for ad hoc briefing from current weekly briefing and digest
  const adHocContext: AdHocBriefingContext = useMemo(() => {
    const context: AdHocBriefingContext = {}

    // Add weekly briefing headlines if available
    if (weeklyBriefing) {
      context.current_brief_headlines = (weeklyBriefing.sections || []).map(s => s.headline?.text || '')
      context.current_brief_date = new Date(weeklyBriefing.generated_at).toLocaleDateString('en-US', {
        month: 'short', day: 'numeric', year: 'numeric'
      })
      context.current_brief_id = weeklyBriefing.id
    }

    // Add active UI filters (selected entities/companies/materials)
    if (selectedEntities.size > 0) {
      context.active_filters = Array.from(selectedEntities)
    }

    // Add recent digest topics
    if (digestItems && digestItems.length > 0) {
      const topics = new Set<string>()
      digestItems.slice(0, 20).forEach(item => {
        item.entities?.topics?.forEach(t => topics.add(t))
      })
      context.recent_digest_topics = Array.from(topics).slice(0, 15)
    }

    return context
  }, [weeklyBriefing, digestItems, selectedEntities])

  return (
    <div className="h-full flex flex-col overflow-hidden p-6 pt-4 bg-slate-100">
      {/* Main 2-Column Layout */}
      <div className="flex-1 flex gap-8 overflow-hidden min-h-0">
        {/* Left Column: Intelligence Feed (Expanded) */}
        <div className="flex-[1.2] flex flex-col gap-0 overflow-hidden border-r border-slate-200/60 pr-6">

          {/* Transparent / Glassy Header */}
          <div className="shrink-0 mb-4 space-y-3 z-10 bg-slate-100/80 backdrop-blur-sm sticky top-0 py-1">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="p-2 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-lg shadow-sm text-white">
                  <Activity size={18} />
                </div>
                <div>
                  <h2 className="text-lg font-bold text-slate-900 leading-none">Intelligence Feed</h2>
                  <p className="text-xs text-slate-500 mt-1">Real-time market signals</p>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <span className="px-2.5 py-1 bg-slate-200 text-slate-600 rounded-full text-xs font-semibold">
                  {filteredItems.length} items
                </span>
              </div>
            </div>

            {/* Search & Filter Bar */}
            <div className="flex items-center gap-2">
              <div className="relative flex-1">
                <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <input
                  type="text"
                  placeholder="Search companies, topics..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-9 pr-4 py-2 bg-white border border-slate-200 rounded-lg text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 transition-all shadow-sm"
                />
                {searchQuery && (
                  <button
                    onClick={() => setSearchQuery('')}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-300 hover:text-slate-500"
                  >
                    <X size={14} />
                  </button>
                )}
              </div>

              {/* Sort Toggle */}
              <div className="flex bg-white rounded-lg border border-slate-200 p-1 shadow-sm shrink-0">
                <button
                  onClick={() => setSortBy('newest')}
                  className={cn(
                    "px-3 py-1 text-xs font-medium rounded-md transition-colors",
                    sortBy === 'newest' ? "bg-slate-100 text-slate-900" : "text-slate-500 hover:text-slate-900"
                  )}
                >
                  Newest
                </button>
                <button
                  onClick={() => setSortBy('priority')}
                  className={cn(
                    "px-3 py-1 text-xs font-medium rounded-md transition-colors",
                    sortBy === 'priority' ? "bg-emerald-50 text-emerald-700" : "text-slate-500 hover:text-slate-900"
                  )}
                >
                  Priority
                </button>
              </div>
            </div>
          </div>

          {/* Entity Aggregator / Filter */}
          {!digestLoading && digestItems && digestItems.length > 0 && (
            <div className="mb-4">
              <EntityAggregator
                items={digestItems}
                selectedEntities={selectedEntities}
                onEntityToggle={handleEntityToggle}
                onClearFilters={handleClearFilters}
              />
            </div>
          )}

          <div className="flex-1 overflow-y-auto pr-2 space-y-4 pb-10">
            {digestLoading ? (
              [1, 2, 3].map(i => (
                <div key={i} className="h-48 bg-slate-50 rounded-xl animate-pulse border border-slate-100" />
              ))
            ) : error ? (
              <div className="bg-red-50 border border-red-100 rounded-xl p-6 text-center">
                <div className="w-12 h-12 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-3">
                  <span className="text-xl">⚠️</span>
                </div>
                <h3 className="text-sm font-semibold text-red-900 mb-1">Failed to Load Feed</h3>
                <p className="text-xs text-red-700 mb-4">{(error as any).message || 'There was a problem loading the intelligence feed.'}</p>
                <button
                  onClick={() => window.location.reload()}
                  className="px-4 py-2 bg-red-600 text-white text-xs font-medium rounded-lg hover:bg-red-700 transition-colors"
                >
                  Retry Connection
                </button>
              </div>
            ) : filteredItems.length > 0 ? (
              filteredItems.map((item) => (
                <DigestCard
                  key={item.id}
                  item={item}
                  onAsk={onAskAbout}
                />
              ))
            ) : selectedEntities.size > 0 ? (
              <div className="text-center py-10 text-slate-400 text-sm italic">
                No items match the selected filters.
              </div>
            ) : (
              <div className="text-center py-10 text-slate-400 text-sm italic">
                No recent activity in the last 7 days.
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Need to Know (Briefings) */}
        <div className="flex-1 overflow-y-auto p-6 pb-10 space-y-4 bg-slate-50 rounded-2xl border border-slate-100/60">
          {/* Ad Hoc Quick Briefing Input */}
          <AdHocBriefing
            context={adHocContext}
            onDeepResearch={onDeepResearch}
          />

          {/* Weekly Executive Briefing (new format) or Legacy Briefings (fallback) */}
          {weeklyBriefing || weeklyLoading ? (
            <WeeklyBriefingSection
              briefing={weeklyBriefing}
              isLoading={weeklyLoading}
              onHistoryClick={() => setIsHistoryOpen(true)}
            />
          ) : (
            // Fallback to legacy category-based briefings
            <BriefingSection briefings={legacyBriefings} isLoading={legacyLoading} />
          )}
        </div>
      </div>

      {/* Briefing History Timeline Modal */}
      <BriefingHistoryTimeline
        isOpen={isHistoryOpen}
        onClose={() => setIsHistoryOpen(false)}
      />
    </div>
  )
}
