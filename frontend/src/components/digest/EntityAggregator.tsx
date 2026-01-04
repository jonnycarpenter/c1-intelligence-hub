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

  // Don't render if no entities
  const hasAnyEntities = Object.values(aggregatedEntities).some(arr => arr.length > 0)
  if (!hasAnyEntities) return null

  return (
    <div className="space-y-1.5 pb-2 border-b border-slate-100 mb-2">
      {/* Clear filters button */}
      {hasFilters && (
        <button
          onClick={onClearFilters}
          className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium text-amber-700 bg-amber-50 hover:bg-amber-100 rounded-md transition-colors"
        >
          <X size={12} />
          Clear filters ({selectedEntities.size})
        </button>
      )}

      {/* Entity rows */}
      {(Object.keys(entityConfig) as EntityType[]).map(type => {
        const config = entityConfig[type]
        const entities = aggregatedEntities[type]
        const Icon = config.icon
        const isExpanded = expandedTypes.has(type)
        const visibleEntities = isExpanded ? entities : entities.slice(0, MAX_VISIBLE)
        const hasMore = entities.length > MAX_VISIBLE

        if (entities.length === 0) return null

        return (
          <div key={type} className="flex items-start gap-2">
            {/* Icon label */}
            <div className={cn('flex items-center gap-1 shrink-0 pt-0.5', config.color)}>
              <Icon size={12} />
              <span className="text-[10px] font-medium uppercase tracking-wide w-[52px]">
                {config.label.slice(0, 6)}
              </span>
            </div>

            {/* Scrollable chips */}
            <div className="flex-1 overflow-x-auto scrollbar-thin scrollbar-thumb-slate-200 scrollbar-track-transparent">
              <div className="flex items-center gap-1.5 pb-1">
                {visibleEntities.map(({ name, count }) => {
                  const isSelected = selectedEntities.has(name)
                  const displayName = type === 'industries' ? formatLabel(name) : name

                  return (
                    <button
                      key={name}
                      onClick={() => onEntityToggle(name, type)}
                      className={cn(
                        'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium border transition-all whitespace-nowrap',
                        isSelected
                          ? config.activeColor
                          : `${config.bgColor} ${config.borderColor} hover:border-slate-300`
                      )}
                      title={displayName}
                    >
                      <span>{truncate(displayName, MAX_NAME_LENGTH)}</span>
                      <span className={cn(
                        'text-[10px] opacity-70',
                        isSelected ? 'text-amber-600' : ''
                      )}>
                        ({count})
                      </span>
                    </button>
                  )
                })}

                {/* Show more/less button */}
                {hasMore && (
                  <button
                    onClick={() => toggleExpand(type)}
                    className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium text-slate-500 bg-slate-100 hover:bg-slate-200 border border-slate-200 transition-colors whitespace-nowrap"
                  >
                    {isExpanded ? 'Less' : `+${entities.length - MAX_VISIBLE}`}
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
