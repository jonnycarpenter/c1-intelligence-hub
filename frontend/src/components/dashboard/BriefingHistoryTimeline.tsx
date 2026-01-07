'use client'

import React, { useState } from 'react'
import { 
  Clock, 
  Calendar,
  MessageSquare,
  FileText,
  ChevronDown,
  ChevronRight,
  X,
  Zap
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { Badge, Modal } from '@/components/ui'
import { useBriefingHistory } from '@/hooks'
import type { WeeklyBriefing, AdHocBriefing } from '@/types/briefing'

// =============================================================================
// Timeline Item Types
// =============================================================================

type TimelineItem = {
  id: string
  type: 'weekly' | 'adhoc'
  title: string
  subtitle?: string
  date: Date
  data: WeeklyBriefing | AdHocBriefing
}

// =============================================================================
// Timeline Item Card
// =============================================================================

interface TimelineItemCardProps {
  item: TimelineItem
  onSelect: (item: TimelineItem) => void
  isSelected?: boolean
}

function TimelineItemCard({ item, onSelect, isSelected }: TimelineItemCardProps) {
  const formattedDate = item.date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })

  return (
    <button
      onClick={() => onSelect(item)}
      className={cn(
        "w-full text-left p-3 rounded-lg border transition-all duration-200",
        isSelected
          ? "border-emerald-300 bg-emerald-50"
          : "border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50"
      )}
    >
      <div className="flex items-start gap-3">
        {/* Icon */}
        <div className={cn(
          "p-1.5 rounded-lg shrink-0",
          item.type === 'weekly' 
            ? "bg-emerald-100 text-emerald-600"
            : "bg-blue-100 text-blue-600"
        )}>
          {item.type === 'weekly' ? (
            <Zap size={14} />
          ) : (
            <MessageSquare size={14} />
          )}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <Badge 
              className={cn(
                "text-[9px] uppercase tracking-wider bg-white",
                item.type === 'weekly' 
                  ? "border-emerald-200 text-emerald-700"
                  : "border-blue-200 text-blue-700"
              )}
            >
              {item.type === 'weekly' ? 'Weekly' : 'Quick'}
            </Badge>
            <span className="text-[10px] text-slate-400">{formattedDate}</span>
          </div>
          <p className="text-sm font-medium text-slate-900 truncate">
            {item.title}
          </p>
          {item.subtitle && (
            <p className="text-xs text-slate-500 mt-0.5 truncate">
              {item.subtitle}
            </p>
          )}
        </div>

        <ChevronRight size={16} className="text-slate-400 shrink-0" />
      </div>
    </button>
  )
}

// =============================================================================
// Weekly Briefing Detail View
// =============================================================================

interface WeeklyDetailProps {
  briefing: WeeklyBriefing
  onClose: () => void
}

function WeeklyDetail({ briefing, onClose }: WeeklyDetailProps) {
  const periodStart = new Date(briefing.period_start).toLocaleDateString('en-US', { 
    month: 'short', day: 'numeric' 
  })
  const periodEnd = new Date(briefing.period_end).toLocaleDateString('en-US', { 
    month: 'short', day: 'numeric' 
  })

  return (
    <div className="p-6">
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Badge className="bg-emerald-100 text-emerald-700">Weekly Briefing</Badge>
            <span className="text-xs text-slate-400">{periodStart} - {periodEnd}</span>
          </div>
          <h2 className="text-xl font-bold text-slate-900">{briefing.briefing_title}</h2>
          {briefing.overall_trend && (
            <p className="text-sm text-slate-600 mt-1">{briefing.overall_trend}</p>
          )}
        </div>
        <button 
          onClick={onClose}
          className="text-slate-400 hover:text-slate-600 transition-colors"
        >
          <X size={20} />
        </button>
      </div>

      {/* Sections */}
      <div className="space-y-4 max-h-[400px] overflow-y-auto">
        {briefing.sections.map((section, idx) => (
          <div 
            key={idx} 
            className="bg-slate-50 rounded-lg p-4 border border-slate-100"
          >
            <h3 className="font-semibold text-slate-900 mb-2">{section.header}</h3>
            <p className="text-sm text-slate-700">{section.headline.text}</p>
            {section.insights.length > 0 && (
              <ul className="mt-2 space-y-1">
                {section.insights.map((insight, iIdx) => (
                  <li key={iIdx} className="text-xs text-slate-600 flex items-start gap-2">
                    <span className="w-1 h-1 rounded-full bg-slate-400 mt-1.5 shrink-0" />
                    {insight.text}
                  </li>
                ))}
              </ul>
            )}
          </div>
        ))}
      </div>

      {/* Footer */}
      <div className="mt-4 pt-4 border-t border-slate-100 text-xs text-slate-400">
        <span>{briefing.article_count} articles analyzed</span>
        <span className="mx-2">•</span>
        <span>Generated {new Date(briefing.generated_at).toLocaleString()}</span>
      </div>
    </div>
  )
}

// =============================================================================
// Ad Hoc Briefing Detail View
// =============================================================================

interface AdHocDetailProps {
  briefing: AdHocBriefing
  onClose: () => void
}

function AdHocDetail({ briefing, onClose }: AdHocDetailProps) {
  return (
    <div className="p-6">
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Badge className="bg-blue-100 text-blue-700">Quick Briefing</Badge>
            <Badge 
              className={cn(
                "text-[10px] bg-white",
                briefing.confidence === 'high' && "border-emerald-200 text-emerald-700",
                briefing.confidence === 'medium' && "border-emerald-200 text-emerald-700",
                briefing.confidence === 'low' && "border-rose-200 text-rose-700",
              )}
            >
              {briefing.confidence} confidence
            </Badge>
          </div>
          <h2 className="text-lg font-bold text-slate-900">{briefing.question}</h2>
        </div>
        <button 
          onClick={onClose}
          className="text-slate-400 hover:text-slate-600 transition-colors"
        >
          <X size={20} />
        </button>
      </div>

      {/* Answer */}
      <div className="bg-slate-50 rounded-lg p-4 border border-slate-100 max-h-[300px] overflow-y-auto">
        <p className="text-sm text-slate-700 whitespace-pre-wrap">{briefing.answer}</p>
      </div>

      {/* Sources */}
      {briefing.sources_used.length > 0 && (
        <div className="mt-4">
          <h4 className="text-xs text-slate-400 uppercase tracking-wider font-semibold mb-2">
            Sources Used
          </h4>
          <div className="flex flex-wrap gap-2">
            {briefing.sources_used.map((source, idx) => (
              <a
                key={idx}
                href={source.url || '#'}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-slate-600 hover:text-emerald-600 transition-colors"
              >
                {source.title}
              </a>
            ))}
          </div>
        </div>
      )}

      {/* Footer */}
      <div className="mt-4 pt-4 border-t border-slate-100 text-xs text-slate-400">
        <span>Generated {new Date(briefing.generated_at).toLocaleString()}</span>
      </div>
    </div>
  )
}

// =============================================================================
// Main Briefing History Timeline Component
// =============================================================================

interface BriefingHistoryTimelineProps {
  isOpen: boolean
  onClose: () => void
}

export default function BriefingHistoryTimeline({ isOpen, onClose }: BriefingHistoryTimelineProps) {
  const { history, isLoading } = useBriefingHistory()
  const [selectedItem, setSelectedItem] = useState<TimelineItem | null>(null)
  const [filter, setFilter] = useState<'all' | 'weekly' | 'adhoc'>('all')

  // Transform history into timeline items
  const timelineItems: TimelineItem[] = React.useMemo(() => {
    if (!history) return []

    const items: TimelineItem[] = []

    // Add weekly briefings
    history.weekly_briefings.forEach(wb => {
      items.push({
        id: wb.id,
        type: 'weekly',
        title: wb.briefing_title,
        subtitle: `${wb.sections.length} sections • ${wb.article_count} articles`,
        date: new Date(wb.generated_at),
        data: wb,
      })
    })

    // Add ad hoc briefings
    history.adhoc_briefings.forEach(ab => {
      items.push({
        id: ab.id,
        type: 'adhoc',
        title: ab.question,
        subtitle: `${ab.confidence} confidence`,
        date: new Date(ab.generated_at),
        data: ab,
      })
    })

    // Sort by date descending
    return items.sort((a, b) => b.date.getTime() - a.date.getTime())
  }, [history])

  // Filter items
  const filteredItems = timelineItems.filter(item => {
    if (filter === 'all') return true
    return item.type === filter
  })

  const handleSelectItem = (item: TimelineItem) => {
    setSelectedItem(item)
  }

  return (
    <Modal isOpen={isOpen} onClose={onClose} className="max-w-4xl w-full">
      <div className="flex h-[600px]">
        {/* Left Panel: Timeline List */}
        <div className={cn(
          "border-r border-slate-200 overflow-hidden flex flex-col",
          selectedItem ? "w-1/3" : "w-full"
        )}>
          {/* Header */}
          <div className="p-4 border-b border-slate-100">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Clock size={20} className="text-emerald-600" />
                <h2 className="text-lg font-bold text-slate-900">Briefing History</h2>
              </div>
              {!selectedItem && (
                <button 
                  onClick={onClose}
                  className="text-slate-400 hover:text-slate-600"
                >
                  <X size={20} />
                </button>
              )}
            </div>

            {/* Filter Tabs */}
            <div className="flex gap-1 bg-slate-100 rounded-lg p-1">
              {(['all', 'weekly', 'adhoc'] as const).map(f => (
                <button
                  key={f}
                  onClick={() => setFilter(f)}
                  className={cn(
                    "flex-1 px-3 py-1.5 text-xs font-medium rounded-md transition-colors",
                    filter === f
                      ? "bg-white text-slate-900 shadow-sm"
                      : "text-slate-500 hover:text-slate-700"
                  )}
                >
                  {f === 'all' ? 'All' : f === 'weekly' ? 'Weekly' : 'Quick'}
                </button>
              ))}
            </div>
          </div>

          {/* Timeline List */}
          <div className="flex-1 overflow-y-auto p-3 space-y-2">
            {isLoading ? (
              [1, 2, 3, 4, 5].map(i => (
                <div 
                  key={i} 
                  className="h-20 bg-slate-100 rounded-lg animate-pulse"
                />
              ))
            ) : filteredItems.length === 0 ? (
              <div className="text-center py-10 text-slate-400">
                <FileText size={32} className="mx-auto mb-2 opacity-50" />
                <p className="text-sm">No briefings found</p>
              </div>
            ) : (
              filteredItems.map(item => (
                <TimelineItemCard
                  key={item.id}
                  item={item}
                  onSelect={handleSelectItem}
                  isSelected={selectedItem?.id === item.id}
                />
              ))
            )}
          </div>

          {/* Stats Footer */}
          {history && (
            <div className="p-3 border-t border-slate-100 bg-slate-50 text-xs text-slate-500">
              <span className="font-medium">{history.total_weekly}</span> weekly •{' '}
              <span className="font-medium">{history.total_adhoc}</span> quick briefings
            </div>
          )}
        </div>

        {/* Right Panel: Detail View */}
        {selectedItem && (
          <div className="flex-1 overflow-hidden">
            {selectedItem.type === 'weekly' ? (
              <WeeklyDetail 
                briefing={selectedItem.data as WeeklyBriefing} 
                onClose={() => setSelectedItem(null)}
              />
            ) : (
              <AdHocDetail 
                briefing={selectedItem.data as AdHocBriefing} 
                onClose={() => setSelectedItem(null)}
              />
            )}
          </div>
        )}
      </div>
    </Modal>
  )
}
