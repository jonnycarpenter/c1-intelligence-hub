'use client'

import { useState, useMemo } from 'react'
import { ChevronDown, ChevronUp, Target, Link, Scale, TrendingUp } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { DigestItem, Category } from '@/types'

// Collection theme configuration
interface CollectionTheme {
    id: string
    label: string
    icon: React.ReactNode
    categories: Category[]
    color: string
    bgColor: string
    borderColor: string
}

const collectionThemes: CollectionTheme[] = [
    {
        id: 'competitor',
        label: 'Competitor Watch',
        icon: <Target size={14} />,
        categories: ['competitor'],
        color: 'text-red-600',
        bgColor: 'bg-red-50',
        borderColor: 'border-red-200',
    },
    {
        id: 'supply_chain',
        label: 'Supply Chain',
        icon: <Link size={14} />,
        categories: ['supply-chain'],
        color: 'text-amber-600',
        bgColor: 'bg-amber-50',
        borderColor: 'border-amber-200',
    },
    {
        id: 'regulatory',
        label: 'Regulatory',
        icon: <Scale size={14} />,
        categories: ['regulatory'],
        color: 'text-purple-600',
        bgColor: 'bg-purple-50',
        borderColor: 'border-purple-200',
    },
    {
        id: 'market',
        label: 'Market & Pricing',
        icon: <TrendingUp size={14} />,
        categories: ['market', 'pricing'],
        color: 'text-blue-600',
        bgColor: 'bg-blue-50',
        borderColor: 'border-blue-200',
    },
]

interface CollectionAccordionProps {
    items: DigestItem[]
    heroItemIds?: Set<string>  // Items to exclude (already shown in hero)
}

export default function CollectionAccordion({ items, heroItemIds = new Set() }: CollectionAccordionProps) {
    const [expandedId, setExpandedId] = useState<string | null>(null)

    // Group items by collection theme
    const groupedItems = useMemo(() => {
        const groups: Record<string, DigestItem[]> = {}

        for (const theme of collectionThemes) {
            groups[theme.id] = items.filter(item =>
                !heroItemIds.has(item.id) &&
                theme.categories.some(cat =>
                    item.category.toLowerCase().replace('_', '-') === cat.toLowerCase() ||
                    item.category.toLowerCase() === cat.toLowerCase().replace('-', '_')
                )
            )
        }

        return groups
    }, [items, heroItemIds])

    const toggleExpand = (id: string) => {
        setExpandedId(prev => prev === id ? null : id)
    }

    // Only show collections with items
    const activeThemes = collectionThemes.filter(theme => groupedItems[theme.id]?.length > 0)

    if (activeThemes.length === 0) return null

    return (
        <div className="space-y-1">
            {activeThemes.map(theme => {
                const themeItems = groupedItems[theme.id] || []
                const isExpanded = expandedId === theme.id

                return (
                    <div key={theme.id} className="rounded-lg border border-slate-200/80 bg-white overflow-hidden">
                        {/* Header Row */}
                        <button
                            onClick={() => toggleExpand(theme.id)}
                            className={cn(
                                "w-full flex items-center justify-between px-3 py-2.5",
                                "hover:bg-slate-50 transition-colors"
                            )}
                        >
                            <div className="flex items-center gap-2">
                                <span className={cn("p-1 rounded", theme.bgColor, theme.color)}>
                                    {theme.icon}
                                </span>
                                <span className="text-sm font-medium text-slate-700">
                                    {theme.label}
                                </span>
                                <span className={cn(
                                    "px-1.5 py-0.5 text-[10px] font-bold rounded",
                                    theme.bgColor, theme.color
                                )}>
                                    {themeItems.length}
                                </span>
                            </div>
                            <span className="text-slate-400">
                                {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                            </span>
                        </button>

                        {/* Expanded Content */}
                        {isExpanded && (
                            <div className="px-3 pb-3 space-y-2 border-t border-slate-100">
                                {themeItems.slice(0, 5).map(item => (
                                    <div key={item.id} className="pt-2">
                                        <div className="flex items-start gap-2">
                                            <div className={cn("w-1 h-full min-h-[32px] rounded-full shrink-0",
                                                item.priority === 'critical' ? 'bg-red-500' :
                                                    item.priority === 'high' ? 'bg-emerald-500' :
                                                        item.priority === 'medium' ? 'bg-blue-400' : 'bg-slate-300'
                                            )} />
                                            <div className="flex-1 min-w-0">
                                                <h4 className="text-sm font-medium text-slate-800 line-clamp-2">
                                                    {item.title}
                                                </h4>
                                                <div className="flex items-center gap-2 mt-0.5 text-[10px] text-slate-400">
                                                    <span>{item.timestamp}</span>
                                                    {item.sources && item.sources[0] && (
                                                        <>
                                                            <span>•</span>
                                                            <a
                                                                href={item.sources[0].url}
                                                                target="_blank"
                                                                rel="noopener noreferrer"
                                                                className="hover:text-emerald-600 truncate max-w-[120px]"
                                                            >
                                                                {item.sources[0].name || 'Source'}
                                                            </a>
                                                        </>
                                                    )}
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                ))}
                                {themeItems.length > 5 && (
                                    <div className="text-xs text-slate-400 text-center pt-1">
                                        +{themeItems.length - 5} more
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                )
            })}
        </div>
    )
}

export { collectionThemes }
export type { CollectionTheme }
