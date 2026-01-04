'use client'

import React, { useState, useMemo, useCallback } from 'react'
import DigestCard from '../digest/DigestCard'
import EntityAggregator from '../digest/EntityAggregator'
import BriefingSection from './BriefingSection'
import WeeklyBriefingSection from './WeeklyBriefingSection'
import AdHocBriefing from './AdHocBriefing'
import BriefingHistoryTimeline from './BriefingHistoryTimeline'
import { useBriefing, useWeeklyBriefing } from '@/hooks'
import { Calendar } from 'lucide-react'
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
  }, [])

  // Filter digest items based on selected entities
  const filteredItems = useMemo(() => {
    const items = digestItems || []
    if (selectedEntities.size === 0) return items

    return items.filter(item => {
      if (!item.entities) return false

      // Check if item contains ANY of the selected entities
      const allItemEntities = [
        ...(item.entities.companies || []),
        ...(item.entities.materials || []),
        ...(item.entities.topics || []),
        ...(item.entities.industries || []),
      ]

      return allItemEntities.some(entity => selectedEntities.has(entity))
    })
  }, [digestItems, selectedEntities])

  // Build context for ad hoc briefing from current weekly briefing and digest
  const adHocContext: AdHocBriefingContext = useMemo(() => {
    const context: AdHocBriefingContext = {}

    // Add weekly briefing headlines if available
    if (weeklyBriefing) {
      context.current_brief_headlines = weeklyBriefing.sections.map(s => s.headline.text)
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
  }, [weeklyBriefing, digestItems])

  return (
    <div className="h-full flex flex-col overflow-hidden p-6 pt-4">
      {/* Main 2-Column Layout */}
      <div className="flex-1 flex gap-8 overflow-hidden min-h-0">
        {/* Left Column: Drumbeat (Stacked Feed) */}
        <div className="w-1/3 flex flex-col gap-1 overflow-hidden border-r border-slate-100 pr-4">
          <div className="flex items-center justify-between shrink-0 mb-1">
            <h2 className="text-sm font-bold text-slate-500 uppercase tracking-widest">Drumbeat Feed</h2>
            {selectedEntities.size > 0 && (
              <span className="text-xs text-slate-400">
                {(filteredItems || []).length} of {(digestItems || []).length}
              </span>
            )}
          </div>

          {/* Entity Aggregator / Filter - shows all 4 entity types */}
          {!digestLoading && digestItems && digestItems.length > 0 && (
            <EntityAggregator
              items={digestItems}
              selectedEntities={selectedEntities}
              onEntityToggle={handleEntityToggle}
              onClearFilters={handleClearFilters}
            />
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
                  onAskAbout={onAskAbout}
                  onAddToReport={onAddToReport}
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
        <div className="flex-1 overflow-y-auto pb-10 space-y-6">
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
