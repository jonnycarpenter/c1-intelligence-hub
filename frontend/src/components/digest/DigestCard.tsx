'use client'

import { useState, useMemo } from 'react'
import { 
  ExternalLink, 
  Newspaper, 
  ChevronDown, 
  ChevronUp,
  TrendingUp,    // Market
  Truck,         // Supply Chain, Logistics
  Scale,         // Regulatory
  Users,         // Competitor
  DollarSign,    // Earnings, pricing
  Package,       // Product
  Factory,       // industry, General
  Handshake,     // Partnership
  Building2,     // Expansion
  Star,          // C1 Mention
} from 'lucide-react'
import { Badge, PriorityBadge, CategoryBadge, Modal } from '@/components/ui'
import { cn } from '@/lib/utils'
import type { DigestItem, Priority, Category } from '@/types'

const priorityColors: Record<Priority, string> = {
  critical: 'bg-red-500',
  high: 'bg-emerald-500',
  medium: 'bg-blue-500',
  low: 'bg-slate-400',
}

// Category icons for visual distinction - supports both Title Case (backend) and legacy lowercase
const categoryIcons: Record<string, React.ReactNode> = {
  // Title Case (backend ContentCategory enum)
  'Market': <TrendingUp size={11} />,
  'Supply Chain': <Truck size={11} />,
  'Regulatory': <Scale size={11} />,
  'Competitor': <Users size={11} />,
  'Product': <Package size={11} />,
  'Earnings': <DollarSign size={11} />,
  'Partnership': <Handshake size={11} />,
  'Expansion': <Building2 size={11} />,
  'Logistics': <Truck size={11} />,
  'C1 Mention': <Star size={11} />,
  'General': <Factory size={11} />,
  // Legacy lowercase (backwards compatibility)
  'market': <TrendingUp size={11} />,
  'supply-chain': <Truck size={11} />,
  'regulatory': <Scale size={11} />,
  'competitor': <Users size={11} />,
  'pricing': <DollarSign size={11} />,
  'product': <Package size={11} />,
  'industry': <Factory size={11} />,
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
  onQuickFilter?: (query: string) => void  // Called when entity pill is clicked
}

export default function DigestCard({ item, onQuickFilter }: DigestCardProps) {
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

  // Memoize highlighted title (company names only for cleaner look)
  const highlightedTitle = useMemo(
    () => highlightEntities(item.title, item.entities?.companies || []),
    [item.title, item.entities?.companies]
  )

  // Normalize priority to lowercase for consistent lookup (backend sends Title Case)
  const normalizedPriority = (item.priority?.toLowerCase() || 'medium') as Priority

  // Priority color map for border
  const borderColors: Record<Priority, string> = {
    critical: 'border-red-500',
    high: 'border-emerald-500', // High priority is good/important usually
    medium: 'border-blue-400',
    low: 'border-slate-300',
  }

  // Subtle background gradients based on priority for visual interest
  const bgGradients: Record<Priority, string> = {
    critical: 'bg-gradient-to-br from-white via-white to-red-50/30',
    high: 'bg-gradient-to-br from-white via-white to-emerald-50/40',
    medium: 'bg-gradient-to-br from-white via-white to-blue-50/30',
    low: 'bg-gradient-to-br from-white to-slate-50/50',
  }

  return (
    <div className={cn(
      "group relative rounded-r-xl rounded-l-md shadow-sm border border-slate-200/60 transition-all duration-300",
      "hover:shadow-lg hover:-translate-y-0.5 hover:border-emerald-300/60",
      "border-l-4",
      borderColors[normalizedPriority] || 'border-slate-300',
      bgGradients[normalizedPriority] || 'bg-white'
    )}>
      <div className="p-4 space-y-3">
        {/* Header: Title & Meta */}
        <div className="space-y-1.5">
          {item.title && (
            <h3 className="text-base font-bold text-slate-900 leading-snug group-hover:text-emerald-700 transition-colors">
              {highlightedTitle}
            </h3>
          )}

          <div className="flex items-center flex-wrap gap-2 text-xs">
            {/* Priority Badge */}
            <PriorityBadge priority={item.priority} />

            <span className="text-slate-300">•</span>

            {/* Category with icon */}
            <span className="inline-flex items-center gap-1 font-semibold text-slate-500 uppercase tracking-wider text-[10px]">
              <span className="text-slate-400">{categoryIcons[item.category]}</span>
              {item.category.replace('-', ' ')}
            </span>

            <span className="text-slate-300">•</span>

            {/* Time */}
            <span className="text-slate-400">{item.timestamp}</span>
          </div>
        </div>

        {/* LLM Summary */}
        <div className="relative">
          <p className={cn(
            "text-sm text-slate-600 leading-relaxed transition-all duration-200",
            !isExpanded && "line-clamp-3"
          )}>
            {highlightedSummary}
          </p>
          {/* Expand/Collapse logic */}
          {item.summary && item.summary.length > 180 && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                setIsExpanded(!isExpanded);
              }}
              className="mt-1 inline-flex items-center gap-1 text-[11px] font-medium text-emerald-600 hover:text-emerald-700 transition-colors"
            >
              {isExpanded ? (
                <>Show less <ChevronUp size={12} /></>
              ) : (
                <>Read more <ChevronDown size={12} /></>
              )}
            </button>
          )}
        </div>

        {/* Dense Entity Pills (only showing top 3 distinct ones mixed) */}
        {item.entities && (
          <div className="flex flex-wrap gap-1.5 pt-1">
            {/* Mix specific entities for a cleaner look */}
            {[
              ...(item.entities.companies || []).map(e => ({ t: 'co', v: e })),
              ...(item.entities.topics || []).map(e => ({ t: 'tp', v: e })),
            ].slice(0, 4).map((ent, idx) => (
              <button
                key={idx}
                onClick={(e) => {
                  e.stopPropagation()
                  onQuickFilter?.(ent.v)
                }}
                className={cn(
                  "inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium border transition-all",
                  ent.t === 'co'
                    ? "bg-slate-50 text-slate-600 border-slate-200 hover:bg-teal-50 hover:text-teal-700 hover:border-teal-200"
                    : "bg-emerald-50/50 text-emerald-700 border-emerald-100 hover:bg-teal-50 hover:text-teal-700 hover:border-teal-200",
                  onQuickFilter && "cursor-pointer"
                )}
                disabled={!onQuickFilter}
              >
                {ent.v}
              </button>
            ))}
            {/* Count more... */}
          </div>
        )}

        {/* Footer: Source Link + Relevance Score */}
        {(sources.length > 0 || item.relevance_score !== undefined) && (
          <div className="pt-2 border-t border-slate-50 flex items-center justify-between">
            {/* Left: Source info */}
            {sources.length > 0 ? (
              hasMultipleSources ? (
                <button
                  onClick={() => setShowSourcesModal(true)}
                  className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-emerald-600 transition-colors group/src"
                >
                  <Newspaper size={12} />
                  <span className="group-hover/src:underline decoration-emerald-200 underline-offset-2">
                    {sources.length} sources analyzed
                  </span>
                </button>
              ) : (
                <a
                  href={sources[0].url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-emerald-600 transition-colors group/src"
                >
                  <ExternalLink size={12} />
                  <span className="truncate max-w-[200px] group-hover/src:underline decoration-emerald-200 underline-offset-2">
                    {sources[0].name || sources[0].title || 'Source'}
                  </span>
                </a>
              )
            ) : (
              <span />
            )}

            {/* Right: Relevance Score */}
            {item.relevance_score !== undefined && (
              <span 
                className={cn(
                  "inline-flex items-center gap-1 text-[10px] font-medium px-1.5 py-0.5 rounded",
                  item.relevance_score >= 0.7 
                    ? "bg-emerald-50 text-emerald-700" 
                    : item.relevance_score >= 0.4
                      ? "bg-blue-50 text-blue-600"
                      : "bg-slate-100 text-slate-500"
                )}
                title={`Relevance: ${Math.round(item.relevance_score * 100)}%`}
              >
                {Math.round(item.relevance_score * 100)}% match
              </span>
            )}
          </div>
        )}

        {/* Sources Modal */}
        <Modal
          isOpen={showSourcesModal}
          onClose={() => setShowSourcesModal(false)}
          title={`Coverage (${sources.length} sources)`}
        >
          <div className="space-y-3">
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
    </div>
  )
}

// Compact variant for lists
interface DigestListItemProps {
  item: DigestItem
  onClick?: (item: DigestItem) => void
}

export function DigestListItem({ item, onClick }: DigestListItemProps) {
  // Normalize priority to lowercase for consistent lookup (backend sends Title Case)
  const normalizedPriority = (item.priority?.toLowerCase() || 'medium') as Priority
  return (
    <div
      className="flex items-start gap-3 p-3 rounded-lg hover:bg-slate-50 cursor-pointer transition-colors"
      onClick={() => onClick?.(item)}
    >
      <div className={cn('w-1 h-full min-h-[40px] rounded-full', priorityColors[normalizedPriority])} />
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
