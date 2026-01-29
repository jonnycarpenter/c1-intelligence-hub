'use client'

import { useMemo } from 'react'
import { Activity, Zap, FolderOpen } from 'lucide-react'
import HeroCard from './HeroCard'
import CollectionAccordion from './CollectionAccordion'
import DigestCard from './DigestCard'
import EntityAggregator from './EntityAggregator'
import { cn } from '@/lib/utils'
import type { DigestItem } from '@/types'

interface EnhancedDigestFeedProps {
    items: DigestItem[]
    isLoading: boolean
    error: Error | null
    selectedEntities: Set<string>
    onEntityToggle: (entity: string) => void
    onClearFilters: () => void
}

export default function EnhancedDigestFeed({
    items,
    isLoading,
    error,
    selectedEntities,
    onEntityToggle,
    onClearFilters,
}: EnhancedDigestFeedProps) {
    // Filter items based on selected entities (same logic as before)
    const filteredItems = useMemo(() => {
        if (selectedEntities.size === 0) return items

        return items.filter(item => {
            if (!item.entities) return false
            const allItemEntities = [
                ...(item.entities.companies || []),
                ...(item.entities.materials || []),
                ...(item.entities.topics || []),
                ...(item.entities.industries || []),
            ]
            return allItemEntities.some(entity => selectedEntities.has(entity))
        })
    }, [items, selectedEntities])

    // Identify hero articles:
    // 1. First check for is_hero flag from classifier
    // 2. Fallback: priority=critical OR (priority=high AND category=competitor)
    const { heroItems, nonHeroItems, heroItemIds } = useMemo(() => {
        const heroes: DigestItem[] = []
        const nonHeroes: DigestItem[] = []
        const heroIds = new Set<string>()

        for (const item of filteredItems) {
            const isHeroFlagged = item.is_hero === true
            // Normalize priority to lowercase for consistent comparison (backend sends Title Case)
            const normalizedPriority = item.priority?.toLowerCase()
            const isFallbackHero =
                normalizedPriority === 'critical' ||
                (normalizedPriority === 'high' && item.category === 'competitor')

            if (isHeroFlagged || isFallbackHero) {
                if (heroes.length < 2) {  // Max 2 hero articles
                    heroes.push(item)
                    heroIds.add(item.id)
                } else {
                    nonHeroes.push(item)
                }
            } else {
                nonHeroes.push(item)
            }
        }

        return { heroItems: heroes, nonHeroItems: nonHeroes, heroItemIds: heroIds }
    }, [filteredItems])

    // Items for "All Updates" section - exclude hero items and collection theme items
    // Actually, let's keep all non-hero items in "All Updates" for simplicity
    const allUpdatesItems = nonHeroItems

    if (isLoading) {
        return (
            <div className="space-y-4">
                {[1, 2, 3].map(i => (
                    <div key={i} className="h-48 bg-slate-50 rounded-xl animate-pulse border border-slate-100" />
                ))}
            </div>
        )
    }

    if (error) {
        return (
            <div className="bg-red-50 border border-red-100 rounded-xl p-6 text-center">
                <div className="w-12 h-12 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-3">
                    <span className="text-xl">⚠️</span>
                </div>
                <h3 className="text-sm font-semibold text-red-900 mb-1">Failed to Load Feed</h3>
                <p className="text-xs text-red-700 mb-4">{error.message || 'There was a problem loading the intelligence feed.'}</p>
                <button
                    onClick={() => window.location.reload()}
                    className="px-4 py-2 bg-red-600 text-white text-xs font-medium rounded-lg hover:bg-red-700 transition-colors"
                >
                    Retry Connection
                </button>
            </div>
        )
    }

    return (
        <div className="space-y-4">
            {/* Entity Aggregator / Filter */}
            {items.length > 0 && (
                <EntityAggregator
                    items={items}
                    selectedEntities={selectedEntities}
                    onEntityToggle={onEntityToggle}
                    onClearFilters={onClearFilters}
                />
            )}

            {/* BREAKING / HERO SECTION */}
            {heroItems.length > 0 && (
                <div className="space-y-3">
                    <div className="flex items-center gap-2 px-1">
                        <div className="p-1.5 bg-amber-100 rounded-md border border-amber-200">
                            <Zap size={12} className="text-amber-600" fill="currentColor" />
                        </div>
                        <h2 className="text-xs font-bold text-amber-700 uppercase tracking-widest">
                            Breaking
                        </h2>
                    </div>
                    {heroItems.map(item => (
                        <HeroCard key={item.id} item={item} />
                    ))}
                </div>
            )}

            {/* COLLECTIONS SECTION */}
            {filteredItems.length > 0 && (
                <div className="space-y-2">
                    <div className="flex items-center gap-2 px-1">
                        <div className="p-1.5 bg-slate-100 rounded-md border border-slate-200">
                            <FolderOpen size={12} className="text-slate-500" />
                        </div>
                        <h2 className="text-xs font-bold text-slate-500 uppercase tracking-widest">
                            Collections
                        </h2>
                    </div>
                    <CollectionAccordion items={filteredItems} heroItemIds={heroItemIds} />
                </div>
            )}

            {/* ALL UPDATES SECTION */}
            <div className="space-y-3">
                <div className="flex items-center justify-between px-1">
                    <div className="flex items-center gap-2">
                        <div className="p-1.5 bg-slate-100 rounded-md border border-slate-200">
                            <Activity size={12} className="text-slate-500" />
                        </div>
                        <h2 className="text-xs font-bold text-slate-500 uppercase tracking-widest">
                            All Updates
                        </h2>
                    </div>
                    {selectedEntities.size > 0 && (
                        <span className="text-xs text-slate-400">
                            {filteredItems.length} of {items.length}
                        </span>
                    )}
                </div>

                <div className="space-y-3">
                    {allUpdatesItems.length > 0 ? (
                        allUpdatesItems.map(item => (
                            <DigestCard key={item.id} item={item} />
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
        </div>
    )
}
