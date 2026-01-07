'use client'

import { useMemo, useState } from 'react'
import { Building2, FlaskConical, Tag, Factory, AlertTriangle, ChevronDown, X } from 'lucide-react'
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

type EntityType = 'companies' | 'materials' | 'topics' | 'industries' | 'highPriority'

const entityConfig: Record<EntityType, { icon: typeof Building2; label: string; color: string; tooltipPrefix: string }> = {
  companies: {
    icon: Building2,
    label: 'Companies',
    color: 'text-blue-600',
    tooltipPrefix: 'companies',
  },
  materials: {
    icon: FlaskConical,
    label: 'Materials',
    color: 'text-emerald-600',
    tooltipPrefix: 'materials',
  },
  industries: {
    icon: Factory,
    label: 'Industries',
    color: 'text-purple-600',
    tooltipPrefix: 'industries',
  },
  topics: {
    icon: Tag,
    label: 'Topics',
    color: 'text-emerald-600',
    tooltipPrefix: 'topics',
  },
  highPriority: {
    icon: AlertTriangle,
    label: 'High Priority',
    color: 'text-red-600',
    tooltipPrefix: 'high priority items',
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

export default function EntityAggregator({
  items,
  selectedEntities,
  onEntityToggle,
  onClearFilters,
}: EntityAggregatorProps) {
  const [expandedType, setExpandedType] = useState<EntityType | null>(null)

  // Aggregate entities and high priority count
  const { aggregatedEntities, highPriorityCount } = useMemo(() => {
    const counts: Record<Exclude<EntityType, 'highPriority'>, Map<string, number>> = {
      companies: new Map(),
      materials: new Map(),
      topics: new Map(),
      industries: new Map(),
    }

    let highPriority = 0

    items.forEach(item => {
      // Count high priority items
      if (item.priority === 'high') {
        highPriority++
      }

      if (!item.entities) return

      const types: Array<Exclude<EntityType, 'highPriority'>> = ['companies', 'materials', 'topics', 'industries']
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
    const result: Record<Exclude<EntityType, 'highPriority'>, EntityCount[]> = {
      companies: [],
      materials: [],
      topics: [],
      industries: [],
    }

    Object.entries(counts).forEach(([type, map]) => {
      result[type as Exclude<EntityType, 'highPriority'>] = Array.from(map.entries())
        .map(([name, count]) => ({ name, count }))
        .sort((a, b) => b.count - a.count) // Sort by count descending
    })

    return { aggregatedEntities: result, highPriorityCount: highPriority }
  }, [items])

  const hasFilters = selectedEntities.size > 0

  const toggleExpand = (type: EntityType) => {
    if (type === 'highPriority') return // High priority is not expandable (just a count)
    setExpandedType(prev => prev === type ? null : type)
  }

  // Get distinct count for each type
  const getCounts = () => ({
    companies: aggregatedEntities.companies.length,
    materials: aggregatedEntities.materials.length,
    industries: aggregatedEntities.industries.length,
    topics: aggregatedEntities.topics.length,
    highPriority: highPriorityCount,
  })

  const counts = getCounts()

  // Don't render if no data
  const hasAnyData = Object.values(counts).some(c => c > 0)
  if (!hasAnyData) return null

  return (
    <div className="space-y-2 pb-3 border-b border-slate-200 mb-4">
      {/* Summary Stats Row */}
      <div className="flex items-center gap-3 flex-wrap">
        {(Object.keys(entityConfig) as EntityType[]).map(type => {
          const config = entityConfig[type]
          const Icon = config.icon
          const count = counts[type]
          const isExpanded = expandedType === type
          const isExpandable = type !== 'highPriority'

          if (count === 0) return null

          return (
            <button
              key={type}
              onClick={() => toggleExpand(type)}
              disabled={!isExpandable}
              className={cn(
                'inline-flex items-center gap-2 px-3 py-1.5 rounded-lg border transition-all',
                isExpandable && 'hover:bg-slate-50 hover:border-slate-300 cursor-pointer',
                !isExpandable && 'cursor-default',
                isExpanded && 'bg-slate-50 border-slate-300 shadow-sm'
              )}
              title={`${count} ${config.tooltipPrefix} mentioned in the current drumbeat feed`}
            >
              <Icon size={16} className={config.color} />
              <span className="text-sm font-semibold text-slate-700">{count}</span>
              {isExpandable && (
                <ChevronDown
                  size={14}
                  className={cn(
                    'text-slate-400 transition-transform',
                    isExpanded && 'rotate-180'
                  )}
                />
              )}
            </button>
          )
        })}

        {/* Clear filters button */}
        {hasFilters && (
          <button
            onClick={onClearFilters}
            className="ml-auto inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium text-emerald-700 bg-emerald-50 hover:bg-emerald-100 rounded-md transition-colors"
          >
            <X size={12} />
            Clear filters ({selectedEntities.size})
          </button>
        )}
      </div>

      {/* Expandable Drawer for Pills */}
      {expandedType && expandedType !== 'highPriority' && (
        <div className="max-h-[200px] overflow-y-auto scrollbar-thin scrollbar-thumb-slate-300 scrollbar-track-slate-100 rounded-lg border border-slate-200 bg-slate-50 p-3">
          <div className="flex flex-wrap gap-1.5">
            {aggregatedEntities[expandedType].map(({ name, count }) => {
              const isSelected = selectedEntities.has(name)
              const displayName = expandedType === 'industries' ? formatLabel(name) : name

              return (
                <button
                  key={name}
                  onClick={() => onEntityToggle(name, expandedType)}
                  className={cn(
                    'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium border transition-all',
                    isSelected
                      ? 'bg-slate-900 border-slate-900 text-white shadow-sm'
                      : 'bg-white border-slate-200 text-slate-700 hover:border-slate-400 hover:shadow-sm'
                  )}
                  title={`${displayName} (${count} mentions)`}
                >
                  <span className="max-w-[150px] truncate">{displayName}</span>
                  <span
                    className={cn(
                      'text-[10px] font-bold px-1.5 py-0.5 rounded',
                      isSelected ? 'bg-slate-700 text-slate-200' : 'bg-slate-100 text-slate-600'
                    )}
                  >
                    {count}
                  </span>
                </button>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
