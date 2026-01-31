'use client'

import React, { useState, useMemo, useCallback, useEffect } from 'react'
import {
    Search,
    Layers,
    ShieldAlert,
    Globe,
    Factory,
    Calendar,
    Shuffle,
    ArrowUpDown,
    X,
    Loader2,
    Clock,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import DigestCard from '@/components/digest/DigestCard'
import type { DigestItem, DigestStats } from '@/types'

// =============================================================================
// Types
// =============================================================================

export interface FullFeedViewProps {
    items: DigestItem[]
    stats: DigestStats | null
    isLoading: boolean
    error: Error | null
    onQuickFilter?: (query: string) => void
}

// =============================================================================
// Main Component
// =============================================================================

export default function FullFeedView({
    items,
    stats,
    isLoading,
    error,
    onQuickFilter,
}: FullFeedViewProps) {
    // Filter state
    const [searchQuery, setSearchQuery] = useState('')
    const [selectedCategory, setSelectedCategory] = useState<string>('all')
    const [selectedPriority, setSelectedPriority] = useState<string>('all')
    const [selectedSource, setSelectedSource] = useState<string>('all')
    const [selectedIndustry, setSelectedIndustry] = useState<string>('all')
    const [timeRange, setTimeRange] = useState<string>('month') // Default: 30 days
    const [sortBy, setSortBy] = useState<'priority' | 'newest' | 'oldest' | 'relevance'>('priority')

    // Shuffle state
    const [isShuffled, setIsShuffled] = useState(false)
    const [shuffledOrder, setShuffledOrder] = useState<string[]>([])

    // Last visit time for NEW badges
    const [lastVisitTime, setLastVisitTime] = useState<Date | null>(null)

    // Load and update last visit time from localStorage
    useEffect(() => {
        const STORAGE_KEY = 'c1-fullfeed-last-visit'
        const stored = localStorage.getItem(STORAGE_KEY)
        if (stored) {
            setLastVisitTime(new Date(stored))
        }
        // Update last visit time on mount (after a short delay to show NEW badges first)
        const timeout = setTimeout(() => {
            localStorage.setItem(STORAGE_KEY, new Date().toISOString())
        }, 5000) // Update after 5 seconds of viewing
        return () => clearTimeout(timeout)
    }, [])

    // =============================================================================
    // Derived Filter Options
    // =============================================================================

    // Categories: from stats or items
    const availableCategories = useMemo(() => {
        if (stats?.byCategory) {
            return Object.keys(stats.byCategory).sort()
        }
        const cats = new Set(items.map(item => item.category))
        return Array.from(cats).sort()
    }, [items, stats])

    // Sources: from items
    const availableSources = useMemo(() => {
        const sources = new Set(items.map(item => item.sources?.[0]?.name).filter(Boolean))
        return Array.from(sources).sort()
    }, [items])

    // Industries: top 50 by frequency from entity arrays
    const availableIndustries = useMemo(() => {
        const industryCounts = new Map<string, number>()
        items.forEach(item => {
            item.entities?.industries?.forEach((ind: string) => {
                industryCounts.set(ind, (industryCounts.get(ind) || 0) + 1)
            })
        })
        return Array.from(industryCounts.entries())
            .sort((a, b) => b[1] - a[1])
            .slice(0, 50)
            .map(([name]) => name)
            .sort()
    }, [items])

    // =============================================================================
    // Filtering & Sorting Logic
    // =============================================================================

    const filteredItems = useMemo(() => {
        let result = items.filter(item => {
            // 1. Text search (title, summary)
            const matchesSearch = searchQuery === '' ||
                item.title?.toLowerCase().includes(searchQuery.toLowerCase()) ||
                item.summary?.toLowerCase().includes(searchQuery.toLowerCase())

            // 2. Category filter
            const matchesCategory = selectedCategory === 'all' ||
                item.category === selectedCategory

            // 3. Priority filter
            const matchesPriority = selectedPriority === 'all' ||
                item.priority?.toLowerCase() === selectedPriority.toLowerCase()

            // 4. Source filter
            const matchesSource = selectedSource === 'all' ||
                item.sources?.[0]?.name === selectedSource

            // 5. Industry filter (checks if industry is in entities array)
            const matchesIndustry = selectedIndustry === 'all' ||
                (item.entities?.industries && item.entities.industries.includes(selectedIndustry))

            // 6. Time range filter
            let matchesTime = true
            const itemDate = item.publishedAt || item.timestamp
            if (timeRange !== 'all' && itemDate) {
                const date = new Date(itemDate)
                const now = new Date()
                const diffTime = Math.abs(now.getTime() - date.getTime())
                const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24))

                if (timeRange === 'today') matchesTime = diffDays <= 1
                if (timeRange === 'week') matchesTime = diffDays <= 7
                if (timeRange === 'twoWeeks') matchesTime = diffDays <= 14
                if (timeRange === 'month') matchesTime = diffDays <= 30
            }

            return matchesSearch && matchesCategory && matchesPriority &&
                matchesSource && matchesIndustry && matchesTime
        })

        // Apply sorting
        if (isShuffled && shuffledOrder.length > 0) {
            // Shuffle mode: sort by pre-computed shuffled order
            result = result.sort((a, b) => {
                const indexA = shuffledOrder.indexOf(a.id)
                const indexB = shuffledOrder.indexOf(b.id)
                if (indexA === -1) return 1
                if (indexB === -1) return -1
                return indexA - indexB
            })
        } else {
            // Standard sorting
            result = result.sort((a, b) => {
                if (sortBy === 'priority') {
                    const priorityOrder: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 }
                    const aPriority = priorityOrder[a.priority?.toLowerCase()] ?? 4
                    const bPriority = priorityOrder[b.priority?.toLowerCase()] ?? 4
                    if (aPriority !== bPriority) return aPriority - bPriority
                    // Secondary sort by date
                    const dateA = a.publishedAt ? new Date(a.publishedAt).getTime() : (a.timestamp ? new Date(a.timestamp).getTime() : 0)
                    const dateB = b.publishedAt ? new Date(b.publishedAt).getTime() : (b.timestamp ? new Date(b.timestamp).getTime() : 0)
                    return dateB - dateA
                }
                if (sortBy === 'newest') {
                    const dateA = a.publishedAt ? new Date(a.publishedAt).getTime() : (a.timestamp ? new Date(a.timestamp).getTime() : 0)
                    const dateB = b.publishedAt ? new Date(b.publishedAt).getTime() : (b.timestamp ? new Date(b.timestamp).getTime() : 0)
                    return dateB - dateA
                }
                if (sortBy === 'oldest') {
                    const dateA = a.publishedAt ? new Date(a.publishedAt).getTime() : (a.timestamp ? new Date(a.timestamp).getTime() : 0)
                    const dateB = b.publishedAt ? new Date(b.publishedAt).getTime() : (b.timestamp ? new Date(b.timestamp).getTime() : 0)
                    return dateA - dateB
                }
                // relevance
                return (b.relevance_score ?? 0) - (a.relevance_score ?? 0)
            })
        }

        return result
    }, [items, searchQuery, selectedCategory, selectedPriority,
        selectedSource, selectedIndustry, timeRange, sortBy,
        isShuffled, shuffledOrder])

    // =============================================================================
    // Handlers
    // =============================================================================

    const handleShuffle = useCallback(() => {
        // Fisher-Yates shuffle
        const allIds = items.map(i => i.id)
        for (let i = allIds.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [allIds[i], allIds[j]] = [allIds[j], allIds[i]]
        }
        setShuffledOrder(allIds)
        setIsShuffled(true)
    }, [items])

    const clearFilters = useCallback(() => {
        setSearchQuery('')
        setSelectedCategory('all')
        setSelectedPriority('all')
        setSelectedSource('all')
        setSelectedIndustry('all')
        setTimeRange('month')
        setIsShuffled(false)
        setShuffledOrder([])
        setSortBy('priority')
    }, [])

    const hasFilters = searchQuery !== '' ||
        selectedCategory !== 'all' ||
        selectedPriority !== 'all' ||
        selectedSource !== 'all' ||
        selectedIndustry !== 'all' ||
        timeRange !== 'month' ||
        isShuffled

    // =============================================================================
    // Render
    // =============================================================================

    if (isLoading) {
        // Skeleton placeholders - feels faster than a spinner
        return (
            <div className="flex flex-col h-full">
                {/* Skeleton Filter Toolbar */}
                <div className="shrink-0 p-4 border-b bg-white space-y-3">
                    <div className="flex flex-wrap items-center gap-3">
                        <div className="h-9 w-48 bg-slate-200 rounded-lg animate-pulse" />
                        <div className="h-9 w-28 bg-slate-200 rounded-lg animate-pulse" />
                        <div className="h-9 w-28 bg-slate-200 rounded-lg animate-pulse" />
                        <div className="h-9 w-28 bg-slate-200 rounded-lg animate-pulse" />
                    </div>
                    <div className="flex items-center gap-3">
                        <div className="h-6 w-24 bg-slate-200 rounded-full animate-pulse" />
                        <div className="h-4 w-32 bg-slate-100 rounded animate-pulse" />
                    </div>
                </div>
                {/* Skeleton Cards */}
                <div className="flex-1 overflow-y-auto p-4 md:p-6 bg-slate-100">
                    <div className="max-w-7xl mx-auto">
                        <div className="columns-1 md:columns-2 xl:columns-3 gap-4">
                            {[180, 240, 160, 200, 280, 150, 220, 190, 260].map((height, i) => (
                                <div
                                    key={i}
                                    className="mb-4 break-inside-avoid bg-white rounded-xl p-4 animate-pulse"
                                    style={{ height: `${height}px` }}
                                >
                                    <div className="flex items-center gap-2 mb-3">
                                        <div className="h-5 w-16 bg-slate-200 rounded" />
                                        <div className="h-5 w-12 bg-slate-100 rounded" />
                                    </div>
                                    <div className="h-5 w-3/4 bg-slate-200 rounded mb-2" />
                                    <div className="h-4 w-full bg-slate-100 rounded mb-1" />
                                    <div className="h-4 w-5/6 bg-slate-100 rounded mb-1" />
                                    <div className="h-4 w-2/3 bg-slate-100 rounded" />
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            </div>
        )
    }

    if (error) {
        return (
            <div className="flex-1 flex items-center justify-center p-6">
                <div className="text-center bg-red-50 text-red-700 rounded-xl p-6 max-w-md">
                    <p className="font-medium mb-1">Failed to load data</p>
                    <p className="text-sm">{error.message}</p>
                </div>
            </div>
        )
    }

    return (
        <div className="flex flex-col h-full">
            {/* Filter Toolbar */}
            <div className="shrink-0 p-4 border-b bg-white space-y-3">
                {/* Row 1: Search + Filters */}
                <div className="flex flex-wrap items-center gap-3">
                    {/* Search Input */}
                    <div className="relative flex-1 min-w-[200px]">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
                        <input
                            type="text"
                            placeholder="Search signals..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            className="w-full pl-10 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-400"
                        />
                    </div>

                    {/* Category Filter */}
                    <div className="flex items-center gap-2 bg-slate-50 border border-slate-200 rounded-xl px-3 py-1.5">
                        <Layers size={14} className="text-slate-400" />
                        <select
                            value={selectedCategory}
                            onChange={(e) => setSelectedCategory(e.target.value)}
                            className="bg-transparent text-sm font-medium focus:outline-none cursor-pointer"
                        >
                            <option value="all">All Categories</option>
                            {availableCategories.map(cat => (
                                <option key={cat} value={cat}>{cat}</option>
                            ))}
                        </select>
                    </div>

                    {/* Priority Filter */}
                    <div className="flex items-center gap-2 bg-slate-50 border border-slate-200 rounded-xl px-3 py-1.5">
                        <ShieldAlert size={14} className="text-slate-400" />
                        <select
                            value={selectedPriority}
                            onChange={(e) => setSelectedPriority(e.target.value)}
                            className="bg-transparent text-sm font-medium focus:outline-none cursor-pointer"
                        >
                            <option value="all">All Priorities</option>
                            <option value="critical">Critical</option>
                            <option value="high">High</option>
                            <option value="medium">Medium</option>
                            <option value="low">Low</option>
                        </select>
                    </div>

                    {/* Source Filter */}
                    <div className="flex items-center gap-2 bg-slate-50 border border-slate-200 rounded-xl px-3 py-1.5">
                        <Globe size={14} className="text-slate-400" />
                        <select
                            value={selectedSource}
                            onChange={(e) => setSelectedSource(e.target.value)}
                            className="bg-transparent text-sm font-medium focus:outline-none cursor-pointer max-w-[140px]"
                        >
                            <option value="all">All Sources</option>
                            {availableSources.map(src => (
                                <option key={src} value={src}>{src}</option>
                            ))}
                        </select>
                    </div>

                    {/* Industry Filter (NEW) */}
                    <div className="flex items-center gap-2 bg-slate-50 border border-slate-200 rounded-xl px-3 py-1.5">
                        <Factory size={14} className="text-slate-400" />
                        <select
                            value={selectedIndustry}
                            onChange={(e) => setSelectedIndustry(e.target.value)}
                            className="bg-transparent text-sm font-medium focus:outline-none cursor-pointer max-w-[140px]"
                        >
                            <option value="all">All Industries</option>
                            {availableIndustries.map(ind => (
                                <option key={ind} value={ind}>{ind}</option>
                            ))}
                        </select>
                    </div>

                    {/* Time Range Filter */}
                    <div className="flex items-center gap-2 bg-slate-50 border border-slate-200 rounded-xl px-3 py-1.5">
                        <Calendar size={14} className="text-slate-400" />
                        <select
                            value={timeRange}
                            onChange={(e) => setTimeRange(e.target.value)}
                            className="bg-transparent text-sm font-medium focus:outline-none cursor-pointer"
                        >
                            <option value="today">Today</option>
                            <option value="week">Last 7 Days</option>
                            <option value="twoWeeks">Last 14 Days</option>
                            <option value="month">Last 30 Days</option>
                        </select>
                    </div>

                    {/* Surprise Me Button */}
                    <button
                        onClick={handleShuffle}
                        className={cn(
                            "flex items-center gap-2 px-3 py-1.5 rounded-xl border transition-all",
                            isShuffled
                                ? "bg-violet-50 border-violet-200 text-violet-600"
                                : "bg-slate-50 border-slate-200 text-slate-600 hover:bg-slate-100"
                        )}
                    >
                        <Shuffle size={14} />
                        <span className="text-sm font-medium">Surprise Me</span>
                    </button>

                    {/* Sort Dropdown (pushed to right) */}
                    <div className="flex items-center gap-2 bg-slate-50 border border-slate-200 rounded-xl px-3 py-1.5 ml-auto">
                        <ArrowUpDown size={14} className="text-slate-400" />
                        <select
                            value={sortBy}
                            onChange={(e) => {
                                setSortBy(e.target.value as typeof sortBy)
                                setIsShuffled(false)
                            }}
                            className="bg-transparent text-sm font-medium focus:outline-none cursor-pointer"
                        >
                            <option value="priority">By Priority</option>
                            <option value="newest">Newest First</option>
                            <option value="oldest">Oldest First</option>
                            <option value="relevance">Most Relevant</option>
                        </select>
                    </div>
                </div>

                {/* Row 2: Time window banner + Results count */}
                <div className="flex items-center justify-between">
                    {/* Left: Time window indicator + Count */}
                    <div className="flex items-center gap-3">
                        {/* Time Window Badge */}
                        <div className="flex items-center gap-1.5 px-3 py-1 bg-gradient-to-r from-teal-50 to-emerald-50 border border-teal-200/50 rounded-full">
                            <Clock size={12} className="text-teal-600" />
                            <span className="text-xs font-semibold text-teal-700">
                                {timeRange === 'today' ? 'Today' : timeRange === 'week' ? 'Last 7 days' : timeRange === 'twoWeeks' ? 'Last 14 days' : 'Last 30 days'}
                            </span>
                        </div>
                        {/* Signal Count */}
                        <div className="text-xs text-slate-500">
                            <b className="text-slate-700">{filteredItems.length}</b> of {items.length} signals
                            {isShuffled && <span className="ml-1 text-violet-500 font-medium">(Shuffled)</span>}
                        </div>
                        {hasFilters && (
                            <button
                                onClick={clearFilters}
                                className="flex items-center gap-1 text-teal-600 hover:underline font-medium text-xs"
                            >
                                <X size={12} />
                                Clear filters
                            </button>
                        )}
                    </div>

                    {/* Right: Active filter pills */}
                    <div className="flex gap-2 flex-wrap">
                        {selectedCategory !== 'all' && (
                            <span className="px-2 py-0.5 bg-blue-500/10 text-blue-600 rounded-md text-[10px] font-bold uppercase">
                                {selectedCategory}
                            </span>
                        )}
                        {selectedPriority !== 'all' && (
                            <span className="px-2 py-0.5 bg-orange-500/10 text-orange-600 rounded-md text-[10px] font-bold uppercase">
                                {selectedPriority}
                            </span>
                        )}
                        {selectedSource !== 'all' && (
                            <span className="px-2 py-0.5 bg-green-500/10 text-green-600 rounded-md text-[10px] font-bold uppercase">
                                {selectedSource}
                            </span>
                        )}
                        {selectedIndustry !== 'all' && (
                            <span className="px-2 py-0.5 bg-indigo-500/10 text-indigo-600 rounded-md text-[10px] font-bold uppercase">
                                {selectedIndustry}
                            </span>
                        )}
                        {timeRange !== 'month' && (
                            <span className="px-2 py-0.5 bg-amber-500/10 text-amber-600 rounded-md text-[10px] font-bold uppercase">
                                {timeRange === 'today' ? 'Today' : timeRange === 'week' ? '7 Days' : timeRange === 'twoWeeks' ? '14 Days' : '30 Days'}
                            </span>
                        )}
                    </div>
                </div>
            </div>

            {/* Masonry Grid */}
            <div className="flex-1 overflow-y-auto p-4 md:p-6 bg-slate-100">
                <div className="max-w-7xl mx-auto">
                    {filteredItems.length > 0 ? (
                        <div className="columns-1 md:columns-2 xl:columns-3 gap-4">
                            {filteredItems.map((item) => (
                                <div key={item.id} className="mb-4 break-inside-avoid">
                                    <DigestCard
                                        item={item}
                                        onQuickFilter={onQuickFilter}
                                        lastVisitTime={lastVisitTime}
                                    />
                                </div>
                            ))}
                        </div>
                    ) : items.length === 0 ? (
                        // No data at all - possible ingestion issue
                        <div className="text-center py-20 bg-gradient-to-br from-amber-50 to-orange-50 rounded-3xl border border-dashed border-amber-200">
                            <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-amber-100 flex items-center justify-center">
                                <Layers size={28} className="text-amber-500" />
                            </div>
                            <h3 className="text-lg font-semibold text-amber-800 mb-2">No signals available</h3>
                            <p className="text-amber-600 mb-2 text-sm max-w-md mx-auto">
                                The intelligence feed is currently empty. This may be due to:
                            </p>
                            <ul className="text-amber-600 text-sm mb-6 space-y-1">
                                <li>• Data ingestion pipeline not running</li>
                                <li>• Recent system maintenance</li>
                                <li>• Network connectivity issues</li>
                            </ul>
                            <p className="text-xs text-amber-500">
                                Try refreshing the page, or contact support if this persists.
                            </p>
                        </div>
                    ) : (
                        // Filters too restrictive
                        <div className="text-center py-20 bg-white rounded-3xl border border-dashed border-slate-300">
                            <Layers size={40} className="mx-auto mb-3 text-slate-300" />
                            <h3 className="text-lg font-semibold text-slate-700 mb-2">No signals match your filters</h3>
                            <p className="text-slate-500 mb-2 text-sm">
                                {items.length} signals exist, but none match your current criteria.
                            </p>
                            <p className="text-slate-400 mb-6 text-xs">
                                Try broadening your search or adjusting filter settings.
                            </p>
                            <button
                                onClick={clearFilters}
                                className="px-6 py-2 bg-slate-900 text-white rounded-xl hover:bg-slate-800 transition-colors"
                            >
                                Clear All Filters
                            </button>
                        </div>
                    )}
                </div>
            </div>
        </div>
    )
}
