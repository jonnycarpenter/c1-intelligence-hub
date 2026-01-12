'use client'

import { useState, useMemo } from 'react'
import { ExternalLink, Newspaper, ChevronDown, ChevronUp, Star, Copy, MessageSquare } from 'lucide-react'
import { Badge, PriorityBadge, CategoryBadge, Modal } from '@/components/ui'
import CompanyLogo from '../pipeline/CompanyLogo'
import { cn } from '@/lib/utils'
import type { DigestItem, Priority } from '@/types'

const priorityColors: Record<Priority, string> = {
  critical: 'bg-red-500',
  high: 'bg-emerald-500',
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

export default function DigestCard({ item, onAsk }: { item: DigestItem; onAsk?: (item: DigestItem) => void }) {
  const [showSourcesModal, setShowSourcesModal] = useState(false)
  const [isExpanded, setIsExpanded] = useState(false)
  const [isBookmarked, setIsBookmarked] = useState(false)
  const sources = item.sources || []
  const hasMultipleSources = sources.length > 1

  // Determine primary company domain for logo
  const primaryCompany = useMemo(() => {
    if (item.entities?.companies && item.entities.companies.length > 0) {
      return item.entities.companies[0]
    }
    return null
  }, [item.entities])

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

  // Handle copy to clipboard
  const handleCopy = (e: React.MouseEvent) => {
    e.stopPropagation()
    const text = `${item.title}\n\n${item.summary}\n\nSource: ${sources[0]?.url || 'Intelligence Hub'}`
    navigator.clipboard.writeText(text)
    // Could add toast here
  }

  // Handle bookmark toggle
  const handleBookmark = (e: React.MouseEvent) => {
    e.stopPropagation()
    setIsBookmarked(!isBookmarked)
    // Persist to local storage or API in future
  }

  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-hidden hover:shadow-[0_4px_20px_-4px_rgba(0,0,0,0.1)] transition-all duration-200 group relative hover:translate-y-[-2px]">
      {/* Priority indicator bar */}
      <div className={cn('absolute top-0 left-0 bottom-0 w-1', priorityColors[item.priority] || 'bg-slate-400')} />

      <div className="p-5 pl-6 space-y-4">
        {/* Header: Logo + Meta + Acts */}
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-start gap-3 flex-1">
            {/* Logo - visual anchor */}
            <div className="mt-1 shrink-0">
              <CompanyLogo
                domain={primaryCompany ? `${primaryCompany.replace(/\s+/g, '').toLowerCase()}.com` : undefined}
                size={36}
                className="shadow-sm"
              />
            </div>

            <div className="space-y-1">
              <div className="flex items-center gap-2 flex-wrap">
                <CategoryBadge category={item.category} />
                <span className="text-xs font-medium text-slate-400 flex items-center gap-1">
                  {item.timestamp}
                  {sources.length > 0 && (
                    <>
                      <span className="w-1 h-1 rounded-full bg-slate-300" />
                      <span className="truncate max-w-[120px]">
                        {sources[0].name || sources[0].title || 'Source'}
                      </span>
                    </>
                  )}
                </span>
              </div>
              {item.title && (
                <h3 className="text-[15px] font-bold text-slate-900 leading-snug group-hover:text-emerald-700 transition-colors">
                  {item.title}
                </h3>
              )}
            </div>
          </div>

          {/* Priority Badge (Mini) */}
          {item.priority === 'critical' || item.priority === 'high' ? (
            <PriorityBadge priority={item.priority} />
          ) : null}
        </div>

        {/* Content */}
        <div className="pl-[48px]">
          <p className={cn(
            "text-sm text-slate-600 leading-relaxed transition-all duration-200",
            !isExpanded && "line-clamp-3"
          )}>
            {highlightedSummary}
          </p>

          {item.summary && item.summary.length > 180 && (
            <button
              onClick={() => setIsExpanded(!isExpanded)}
              className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-emerald-600 hover:text-emerald-700 transition-colors"
            >
              {isExpanded ? (
                <>Show less <ChevronUp size={12} /></>
              ) : (
                <>Read more <ChevronDown size={12} /></>
              )}
            </button>
          )}

          {/* Entity Pills */}
          {item.entities && (
            <div className="flex flex-wrap gap-1.5 pt-3">
              {item.entities.companies?.slice(0, 3).map((company, idx) => (
                <span key={`c-${idx}`} className="inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-medium bg-slate-100 text-slate-600 border border-slate-200">
                  {company}
                </span>
              ))}
              {item.entities.topics?.slice(0, 2).map((topic, idx) => (
                <span key={`t-${idx}`} className="inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-100">
                  {topic}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Action Footer - Visible on Hover/Group Focus */}
      <div className="bg-slate-50/50 border-t border-slate-100 px-4 py-2 flex items-center justify-end gap-1 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
        <button
          onClick={handleBookmark}
          className={cn(
            "p-1.5 rounded-md transition-colors",
            isBookmarked ? "text-amber-500 bg-amber-50 hover:bg-amber-100" : "text-slate-400 hover:text-slate-600 hover:bg-slate-100"
          )}
          title="Save for later"
        >
          <Star size={16} fill={isBookmarked ? "currentColor" : "none"} />
        </button>

        <button
          onClick={handleCopy}
          className="p-1.5 rounded-md text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
          title="Copy details"
        >
          <Copy size={16} />
        </button>

        {sources.length > 0 && (
          <button
            onClick={() => hasMultipleSources ? setShowSourcesModal(true) : window.open(sources[0].url, '_blank')}
            className="p-1.5 rounded-md text-slate-400 hover:text-emerald-600 hover:bg-emerald-50 transition-colors"
            title="View Source"
          >
            <ExternalLink size={16} />
          </button>
        )}

        {onAsk && (
          <button
            onClick={() => onAsk(item)}
            className="ml-2 flex items-center gap-1.5 px-3 py-1 bg-white border border-slate-200 hover:border-emerald-300 hover:bg-emerald-50 text-slate-600 hover:text-emerald-700 text-xs font-medium rounded-md shadow-sm transition-all"
          >
            <MessageSquare size={14} />
            Ask AI
          </button>
        )}
      </div>

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
              className="flex items-center gap-3 p-3 rounded-lg border border-slate-200 hover:border-emerald-300 hover:bg-emerald-50 transition-colors group"
            >
              <div className="flex-shrink-0 w-8 h-8 rounded-full bg-slate-100 flex items-center justify-center group-hover:bg-emerald-100">
                <Newspaper size={16} className="text-slate-500 group-hover:text-emerald-600" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="font-medium text-slate-900 group-hover:text-emerald-600 truncate">
                  {source.name || source.title || 'Unknown Source'}
                </div>
                {source.published_at && (
                  <div className="text-xs text-slate-400">{source.published_at}</div>
                )}
              </div>
              <ExternalLink size={14} className="text-slate-400 group-hover:text-emerald-600" />
            </a>
          ))}
        </div>
      </Modal>
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
