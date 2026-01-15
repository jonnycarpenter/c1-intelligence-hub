'use client'

import React, { useState, useMemo, useCallback } from 'react'
import EnhancedDigestFeed from '../digest/EnhancedDigestFeed'
import BriefingSection from './BriefingSection'
import WeeklyBriefingSection from './WeeklyBriefingSection'
import AdHocBriefing from './AdHocBriefing'
import BriefingHistoryTimeline from './BriefingHistoryTimeline'
import { useBriefing, useWeeklyBriefing } from '@/hooks'
import { Activity } from 'lucide-react'

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
  }, [weeklyBriefing, digestItems])

  return (
    <div className="h-full flex flex-col overflow-hidden p-6 pt-4 bg-slate-200">
      {/* Main 2-Column Layout */}
      <div className="flex-1 flex gap-8 overflow-hidden min-h-0">
        {/* Left Column: Need to Know (Briefings) - FIRST CLASS CITIZEN */}
        <div className="flex-1 overflow-y-auto p-6 pb-10 bg-slate-50 rounded-2xl border border-slate-100/60 scrollbar-hide">
          <div className="max-w-5xl mx-auto w-full space-y-4">
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

        {/* Right Column: Enhanced Drumbeat Feed with Hero + Collections + All Updates */}
        <div className="w-[400px] flex flex-col gap-1 overflow-hidden border-l border-slate-100 pl-4">
          <div className="flex items-center justify-between shrink-0 mb-3 px-1">
            <div className="flex items-center gap-2">
              <div className="p-1.5 bg-slate-100 rounded-md border border-slate-200">
                <Activity size={14} className="text-slate-500" />
              </div>
              <h2 className="text-xs font-bold text-slate-500 uppercase tracking-widest">Drumbeat Feed</h2>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto pr-2 pb-10 scrollbar-thin scrollbar-thumb-slate-200 scrollbar-track-transparent">
            <EnhancedDigestFeed
              items={digestItems || []}
              isLoading={digestLoading}
              error={error}
              selectedEntities={selectedEntities}
              onEntityToggle={handleEntityToggle}
              onClearFilters={handleClearFilters}
            />
          </div>
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
