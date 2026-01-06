'use client'

import { useState, useMemo } from 'react'
import { ExternalLink, Newspaper, ChevronDown, ChevronUp } from 'lucide-react'
import { Badge, PriorityBadge, CategoryBadge, Modal } from '@/components/ui'
import { cn } from '@/lib/utils'
import type { DigestItem, Priority } from '@/types'

const priorityColors: Record<Priority, string> = {
  critical: 'bg-red-500',
  high: 'bg-amber-500',
  medium: 'bg-blue-500',
  low: 'bg-slate-400',
}

/**
 * Format a label: capitalize words, replace underscores/hyphens with spaces
 */
function formatLabel(label: string): string {
  if (!label || typeof label !== 'string') return label || ''
  return label
    .split(/[-_]/)
    .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ')
}

/**
 * Highlight entities in text by wrapping them in bold tags
 */
function highlightEntities(text: string, entities: string[]): React.ReactNode {
  if (!text || typeof text !== 'string') return text || ''
  if (!entities || entities.length === 0) return text

  // Sort entities by length (longest first) to avoid partial matches
  const sortedEntities = [...entities].sort((a, b) => b.length - a.length)

  // Create regex pattern for all entities (case insensitive)
  const pattern = new RegExp(
    `(${sortedEntities.map(e => e.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})`,
    'gi'
  )

  // Split text by entity matches
  const parts = text.split(pattern)

  return parts.map((part, idx) => {
    // Check if this part matches any entity (case insensitive)
    const isEntity = sortedEntities.some(
      entity => entity.toLowerCase() === part.toLowerCase()
    )
    return isEntity ? (
      <strong key={idx} className="font-semibold text-slate-900">{part}</strong>
    ) : (
      <span key={idx}>{part}</span>
    )
  })
}

interface DigestCardProps {
  item: DigestItem
}

export default function DigestCard({ item }: DigestCardProps) {
  const [showSourcesModal, setShowSourcesModal] = useState(false)
  const [isExpanded, setIsExpanded] = useState(false)
  const sources = item.sources || []
  const hasMultipleSources = sources.length > 1

  // Combine all entities for text highlighting
  const allEntities = useMemo(() => {
    if (!item.entities) return []
    return [
      ...(item.entities.companies || []),
      ...(item.entities.materials || []),
      ...(item.entities.topics || []),
      ...(item.entities.industries || []),
    ]
  }, [item.entities])

  // Memoize highlighted summary
  const highlightedSummary = useMemo(
    () => highlightEntities(item.summary, allEntities),
    [item.summary, allEntities]
  )

  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-hidden hover:shadow-md transition-shadow group">
      {/* Priority indicator bar */}
      <div className={cn('h-1', priorityColors[item.priority] || 'bg-slate-400')} />

      <div className="p-4 space-y-3">
        {/* Header with badges */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CategoryBadge category={item.category} />
            <PriorityBadge priority={item.priority} />
          </div>
          <span className="text-xs text-slate-400">{item.timestamp}</span>
        </div>

        {/* LLM Summary with highlighted entities - expandable */}
        <div className="relative">
          {item.title && (
            <h3 className="text-base font-bold text-slate-900 mb-2 leading-snug group-hover:text-amber-600 transition-colors">
              {item.title}
            </h3>
          )}
          <p className={cn(
            "text-sm text-slate-700 transition-all duration-200",
            !isExpanded && "line-clamp-4"
          )}>
            {highlightedSummary}
          </p>
          {/* Expand/Collapse button - only show if text is long enough */}
          {item.summary && item.summary.length > 200 && (
            <button
              onClick={() => setIsExpanded(!isExpanded)}
              className="mt-1 inline-flex items-center gap-0.5 text-xs text-slate-500 hover:text-amber-600 transition-colors"
            >
              {isExpanded ? (
                <>
                  <ChevronUp size={14} />
                  <span>Show less</span>
                </>
              ) : (
                <>
                  <ChevronDown size={14} />
                  <span>Read more</span>
                </>
              )}
            </button>
          )}
        </div>

        {/* Entity Pills - Companies, Materials, Topics, Industries */}
        {item.entities && (
          <div className="flex flex-wrap gap-1.5 pt-1">
            {/* Companies - Blue pills */}
            {item.entities.companies?.slice(0, 3).map((company, idx) => (
              <span
                key={`company-${idx}`}
                className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-blue-50 text-blue-700 border border-blue-200"
              >
                {company}
              </span>
            ))}
            {/* Materials - Green pills */}
            {item.entities.materials?.slice(0, 3).map((material, idx) => (
              <span
                key={`material-${idx}`}
                className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200"
              >
                {material}
              </span>
            ))}
            {/* Industries - Purple pills */}
            {item.entities.industries?.slice(0, 3).map((industry, idx) => (
              <span
                key={`industry-${idx}`}
                className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-purple-50 text-purple-700 border border-purple-200"
              >
                {formatLabel(industry)}
              </span>
            ))}
            {/* Topics - Amber pills */}
            {item.entities.topics?.slice(0, 3).map((topic, idx) => (
              <span
                key={`topic-${idx}`}
                className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200"
              >
                {topic}
              </span>
            ))}
          </div>
        )}

        {/* Source links */}
        {sources.length > 0 && (
          <div className="flex flex-wrap gap-2 pt-1">
            {hasMultipleSources ? (
              // Multiple sources - show clickable "Sources" button
              <button
                onClick={() => setShowSourcesModal(true)}
                className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-amber-600 transition-colors"
              >
                <Newspaper size={12} />
                <span>{sources.length} Sources</span>
              </button>
            ) : (
              // Single source - show direct link with publication name
              <a
                href={sources[0].url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-amber-600 transition-colors"
              >
                <ExternalLink size={12} />
                {sources[0].name || sources[0].title || 'Source'}
              </a>
            )}
          </div>
        )}

        {/* Sources Modal */}
        <Modal
          isOpen={showSourcesModal}
          onClose={() => setShowSourcesModal(false)}
          title={`Sources (${sources.length})`}
        >
          <div className="space-y-3">
            <p className="text-sm text-slate-600 mb-4">
              This story was covered by {sources.length} publications:
            </p>
            {sources.map((source, idx) => (
              <a
                key={idx}
                href={source.url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-3 p-3 rounded-lg border border-slate-200 hover:border-amber-300 hover:bg-amber-50 transition-colors group"
              >
                <div className="flex-shrink-0 w-8 h-8 rounded-full bg-slate-100 flex items-center justify-center group-hover:bg-amber-100">
                  <Newspaper size={16} className="text-slate-500 group-hover:text-amber-600" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="font-medium text-slate-900 group-hover:text-amber-600 truncate">
                    {source.name || source.title || 'Unknown Source'}
                  </div>
                  {source.published_at && (
                    <div className="text-xs text-slate-400">{source.published_at}</div>
                  )}
                </div>
                <ExternalLink size={14} className="text-slate-400 group-hover:text-amber-600" />
              </a>
            ))}
          </div>
        </Modal>


      </div>
    </div>
  )
}

// Compact variant for lists
interface DigestListItemProps {
  item: DigestItem
  onClick?: (item: DigestItem) => void
}

export function DigestListItem({ item, onClick }: DigestListItemProps) {
  return (
    <div
      className="flex items-start gap-3 p-3 rounded-lg hover:bg-slate-50 cursor-pointer transition-colors"
      onClick={() => onClick?.(item)}
    >
      <div className={cn('w-1 h-full min-h-[40px] rounded-full', priorityColors[item.priority])} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <CategoryBadge category={item.category} />
          <span className="text-xs text-slate-400">{item.timestamp}</span>
        </div>
        <h4 className="text-sm font-medium text-slate-900 truncate">{item.title}</h4>
        <p className="text-xs text-slate-500 line-clamp-1">{item.summary}</p>
      </div>
    </div>
  )
}
