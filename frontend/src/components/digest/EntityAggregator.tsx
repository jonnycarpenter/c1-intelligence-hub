'use client'

import { useMemo, useState } from 'react'
import { Building2, FlaskConical, Tag, Factory, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { DigestItem } from '@/types'

interface EntityCount {
  name: string
  count: number
}

interface EntityAggregatorProps {
  items: DigestItem[]
  selectedEntities: Set<string>
  onEntityToggle: (entity: string, type: EntityType) => void
  onClearFilters: () => void
}

type EntityType = 'companies' | 'materials' | 'topics' | 'industries'

const entityConfig: Record<EntityType, { icon: typeof Building2; label: string; color: string; bgColor: string; borderColor: string; activeColor: string }> = {
  companies: {
    icon: Building2,
    label: 'Companies',
    color: 'text-blue-600',
    bgColor: 'bg-blue-50',
    borderColor: 'border-blue-200',
    activeColor: 'bg-amber-100 border-amber-400 text-amber-800',
  },
  materials: {
    icon: FlaskConical,
    label: 'Materials',
    color: 'text-emerald-600',
    bgColor: 'bg-emerald-50',
    borderColor: 'border-emerald-200',
    activeColor: 'bg-amber-100 border-amber-400 text-amber-800',
  },
  topics: {
    icon: Tag,
    label: 'Topics',
    color: 'text-amber-600',
    bgColor: 'bg-amber-50',
    borderColor: 'border-amber-200',
    activeColor: 'bg-amber-100 border-amber-400 text-amber-800',
  },
  industries: {
    icon: Factory,
    label: 'Industries',
    color: 'text-purple-600',
    bgColor: 'bg-purple-50',
    borderColor: 'border-purple-200',
    activeColor: 'bg-amber-100 border-amber-400 text-amber-800',
  },
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
 * Truncate a string to maxLen characters with ellipsis
 */
function truncate(str: string, maxLen: number): string {
  if (str.length <= maxLen) return str
  return str.slice(0, maxLen - 1) + '…'
}

const MAX_VISIBLE = 5
const MAX_NAME_LENGTH = 14

export default function EntityAggregator({
  items,
  selectedEntities,
  onEntityToggle,
  onClearFilters,
}: EntityAggregatorProps) {
  const [expandedTypes, setExpandedTypes] = useState<Set<EntityType>>(new Set())

  // Aggregate entities across all items
  const aggregatedEntities = useMemo(() => {
    const counts: Record<EntityType, Map<string, number>> = {
      companies: new Map(),
      materials: new Map(),
      topics: new Map(),
      industries: new Map(),
    }

    items.forEach(item => {
      if (!item.entities) return

      const types: EntityType[] = ['companies', 'materials', 'topics', 'industries']
      types.forEach(type => {
        const entities = item.entities?.[type] || []
        entities.forEach(entity => {
          if (!entity) return
          const current = counts[type].get(entity) || 0
          counts[type].set(entity, current + 1)
        })
      })
    })

    // Convert to sorted arrays
    const result: Record<EntityType, EntityCount[]> = {
      companies: [],
      materials: [],
      topics: [],
      industries: [],
    }

    Object.entries(counts).forEach(([type, map]) => {
      result[type as EntityType] = Array.from(map.entries())
        .map(([name, count]) => ({ name, count }))
        .sort((a, b) => b.count - a.count)
    })

    return result
  }, [items])

  const hasFilters = selectedEntities.size > 0

  const toggleExpand = (type: EntityType) => {
    setExpandedTypes(prev => {
      const next = new Set(prev)
      if (next.has(type)) {
        next.delete(type)
      } else {
        next.add(type)
      }
      return next
    })
  }

  // Calculate max count for "heat map" scaling per category
  const getMaxCount = (type: EntityType) => {
    const entities = aggregatedEntities[type]
    return entities.length > 0 ? entities[0].count : 1
  }

  // Don't render if no entities
  const hasAnyEntities = Object.values(aggregatedEntities).some(arr => arr.length > 0)
  if (!hasAnyEntities) return null

  return (
    <div className="space-y-2 pb-2 border-b border-slate-100 mb-2">
      {/* Clear filters button */}
      {hasFilters && (
        <div className="flex justify-end">
          <button
            onClick={onClearFilters}
            className="inline-flex items-center gap-1 px-2 py-0.5 text-[10px] font-medium text-amber-700 bg-amber-50 hover:bg-amber-100 rounded-md transition-colors"
          >
            <X size={10} />
            Clear filters ({selectedEntities.size})
          </button>
        </div>
      )}

      {/* Entity rows */}
      {(Object.keys(entityConfig) as EntityType[]).map(type => {
        const config = entityConfig[type]
        const entities = aggregatedEntities[type]
        const Icon = config.icon
        const isExpanded = expandedTypes.has(type)
        const visibleEntities = isExpanded ? entities : entities.slice(0, MAX_VISIBLE)
        const hasMore = entities.length > MAX_VISIBLE
        const maxCount = getMaxCount(type)

        if (entities.length === 0) return null

        return (
          <div key={type} className="flex items-start gap-3 group">
            {/* Icon label (Compact) */}
            <div
              className={cn('flex items-center justify-center w-6 h-6 rounded-md shrink-0 mt-0.5 transition-colors', config.bgColor)}
              title={config.label}
            >
              <Icon size={14} className={config.color} />
            </div>

            {/* Scrollable chips */}
            <div className="flex-1 overflow-x-auto scrollbar-thin scrollbar-thumb-slate-200 scrollbar-track-transparent">
              <div className="flex items-center gap-1.5 pb-1">
                {visibleEntities.map(({ name, count }) => {
                  const isSelected = selectedEntities.has(name)
                  const displayName = type === 'industries' ? formatLabel(name) : name

                  // Heat map calculation: higher percentage of maxCount = more opaque/saturated
                  // Base opacity 10%, scales up to 100% (or distinct shades)
                  // We'll simplisticly use opacity on the border/bg
                  const intensity = Math.max(0.2, count / maxCount)

                  return (
                    <button
                      key={name}
                      onClick={() => onEntityToggle(name, type)}
                      className={cn(
                        'relative inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-[11px] font-medium border transition-all whitespace-nowrap',
                        isSelected
                          ? "bg-slate-900 border-slate-900 text-white shadow-sm"
                          : "bg-white text-slate-700 hover:border-slate-300"
                      )}
                      style={!isSelected ? {
                        opacity: 0.7 + (intensity * 0.3), // Slight opacity scaling
                        borderColor: `rgba(0,0,0, ${intensity * 0.2})`, // Dynamic border darkness
                        backgroundColor: `rgba(0,0,0, ${intensity * 0.02})` // Very subtle background tint
                      } : {}}
                      title={`${displayName} (${count} mentions)`}
                    >
                      <span className="max-w-[120px] truncate">{displayName}</span>
                      {count > 1 && (
                        <span className={cn(
                          "text-[9px] font-bold px-1 rounded-sm",
                          isSelected ? "bg-slate-700 text-slate-200" : "bg-slate-100 text-slate-500"
                        )}>
                          {count}
                        </span>
                      )}
                    </button>
                  )
                })}

                {/* Show more/less button */}
                {hasMore && (
                  <button
                    onClick={() => toggleExpand(type)}
                    className="inline-flex items-center justify-center w-5 h-5 rounded-full text-[10px] font-medium text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
                    title={isExpanded ? "Show less" : `Show ${entities.length - MAX_VISIBLE} more`}
                  >
                    {isExpanded ? <X size={12} /> : '+'}
                  </button>
                )}
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}
