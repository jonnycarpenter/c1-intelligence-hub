'use client'

import React, { useState, useMemo, useEffect, useRef, useCallback } from 'react'
import {
  Search,
  ArrowUpDown,
  X,
  Loader2,
  Mic,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import ExpertFeedCard from './ExpertFeedCard'
import { useExpertFeed } from '@/hooks/useExpertFeed'
import type { ExpertFeedFilters } from '@/hooks/useExpertFeed'

// =============================================================================
// Main Component
// =============================================================================

export default function ExpertFeedView() {
  const { items, isLoading, error, hasMore, totalCount, filters, setFilters, loadMore } = useExpertFeed()

  // Local filter state
  const [searchInput, setSearchInput] = useState('')
  const [selectedPodcast, setSelectedPodcast] = useState<string>('all')
  const [selectedSpeaker, setSelectedSpeaker] = useState<string>('all')
  const [selectedTimeRange, setSelectedTimeRange] = useState<string>('90d')
  const [sortBy, setSortBy] = useState<'newest' | 'relevance'>('newest')
  const observerTarget = useRef<HTMLDivElement>(null)
  const searchTimeout = useRef<ReturnType<typeof setTimeout>>()

  // Debounced search
  const handleSearchChange = useCallback((value: string) => {
    setSearchInput(value)
    if (searchTimeout.current) clearTimeout(searchTimeout.current)
    searchTimeout.current = setTimeout(() => {
      setFilters({ ...filters, search: value || undefined })
    }, 300)
  }, [filters, setFilters])

  // Apply filters when dropdowns change
  useEffect(() => {
    const newFilters: ExpertFeedFilters = {
      search: searchInput || undefined,
      podcast_name: selectedPodcast !== 'all' ? selectedPodcast : undefined,
      speaker_name: selectedSpeaker !== 'all' ? selectedSpeaker : undefined,
      time_range: selectedTimeRange,
      sort_by: sortBy,
    }
    setFilters(newFilters)
  }, [selectedPodcast, selectedSpeaker, selectedTimeRange, sortBy])

  // Extract unique podcasts for dropdown
  const availablePodcasts = useMemo(() => {
    const podcasts = new Set<string>()
    items.forEach(item => {
      if (item.podcast_name) podcasts.add(item.podcast_name)
    })
    return Array.from(podcasts).sort()
  }, [items])

  // Extract unique speakers for dropdown
  const availableSpeakers = useMemo(() => {
    const speakers = new Set<string>()
    items.forEach(item => {
      if (item.speaker_name) speakers.add(item.speaker_name)
    })
    return Array.from(speakers).sort()
  }, [items])

  // Infinite scroll
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasMore && !isLoading) {
          loadMore()
        }
      },
      { threshold: 0.1, rootMargin: '400px' }
    )
    if (observerTarget.current) {
      observer.observe(observerTarget.current)
    }
    return () => observer.disconnect()
  }, [hasMore, isLoading, loadMore])

  // Clear all filters
  const clearFilters = () => {
    setSearchInput('')
    setSelectedPodcast('all')
    setSelectedSpeaker('all')
    setSelectedTimeRange('90d')
    setSortBy('newest')
    setFilters({})
  }

  const hasActiveFilters = searchInput || selectedPodcast !== 'all' || selectedSpeaker !== 'all' || selectedTimeRange !== '90d'

  return (
    <div className="flex-1 overflow-y-auto">
      {/* Filter Toolbar */}
      <div className="sticky top-0 z-10 bg-white/95 backdrop-blur-sm border-b border-slate-200 px-6 py-3">
        <div className="flex flex-wrap items-center gap-2">
          {/* Search */}
          <div className="relative flex-1 min-w-[200px] max-w-[300px]">
            <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              value={searchInput}
              onChange={(e) => handleSearchChange(e.target.value)}
              placeholder="Search expert quotes..."
              className="w-full pl-8 pr-3 py-1.5 text-sm rounded-lg border border-slate-200 focus:outline-none focus:ring-1 focus:ring-violet-500 focus:border-violet-500"
            />
          </div>

          {/* Podcast */}
          <select
            value={selectedPodcast}
            onChange={(e) => setSelectedPodcast(e.target.value)}
            className="px-3 py-1.5 text-xs rounded-lg border border-slate-200 bg-white focus:outline-none focus:ring-1 focus:ring-violet-500"
          >
            <option value="all">All Podcasts</option>
            {availablePodcasts.map(p => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>

          {/* Speaker */}
          <select
            value={selectedSpeaker}
            onChange={(e) => setSelectedSpeaker(e.target.value)}
            className="px-3 py-1.5 text-xs rounded-lg border border-slate-200 bg-white focus:outline-none focus:ring-1 focus:ring-violet-500"
          >
            <option value="all">All Speakers</option>
            {availableSpeakers.map(s => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>

          {/* Time range */}
          <select
            value={selectedTimeRange}
            onChange={(e) => setSelectedTimeRange(e.target.value)}
            className="px-3 py-1.5 text-xs rounded-lg border border-slate-200 bg-white focus:outline-none focus:ring-1 focus:ring-violet-500"
          >
            <option value="7d">Last 7 days</option>
            <option value="14d">Last 14 days</option>
            <option value="30d">Last 30 days</option>
            <option value="90d">Last 90 days</option>
            <option value="180d">Last 6 months</option>
          </select>

          {/* Sort */}
          <div className="flex items-center gap-1 ml-auto">
            <ArrowUpDown size={12} className="text-slate-400" />
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as 'newest' | 'relevance')}
              className="px-2 py-1.5 text-xs rounded-lg border border-slate-200 bg-white focus:outline-none focus:ring-1 focus:ring-violet-500"
            >
              <option value="newest">Newest</option>
              <option value="relevance">Relevance</option>
            </select>
          </div>

          {/* Clear filters */}
          {hasActiveFilters && (
            <button
              onClick={clearFilters}
              className="flex items-center gap-1 px-2 py-1.5 text-xs text-slate-500 hover:text-slate-700 rounded-lg hover:bg-slate-100"
            >
              <X size={12} /> Clear
            </button>
          )}
        </div>

        {/* Results count */}
        <div className="mt-2 text-xs text-slate-400">
          {totalCount > 0 ? `${totalCount} quotes` : isLoading ? 'Loading...' : 'No quotes found'}
        </div>
      </div>

      {/* Card list */}
      <div className="px-6 py-4 space-y-3">
        {isLoading && items.length === 0 ? (
          <div className="flex items-center justify-center py-16">
            <div className="text-center">
              <Loader2 className="w-8 h-8 animate-spin text-violet-500 mx-auto mb-3" />
              <p className="text-slate-500 text-sm">Loading expert insights...</p>
            </div>
          </div>
        ) : error ? (
          <div className="flex items-center justify-center py-16">
            <p className="text-red-500 text-sm">{error.message}</p>
          </div>
        ) : items.length === 0 ? (
          <div className="flex items-center justify-center py-16">
            <div className="text-center">
              <Mic className="w-10 h-10 text-slate-300 mx-auto mb-3" />
              <p className="text-slate-500 text-sm">No expert quotes found</p>
              <p className="text-slate-400 text-xs mt-1">Try adjusting your filters or time range</p>
            </div>
          </div>
        ) : (
          <>
            {items.map((item) => (
              <ExpertFeedCard key={item.id} item={item} />
            ))}

            {/* Infinite scroll sentinel */}
            <div ref={observerTarget} className="h-4" />

            {isLoading && items.length > 0 && (
              <div className="flex items-center justify-center py-4">
                <Loader2 className="w-5 h-5 animate-spin text-slate-400" />
              </div>
            )}

            {!hasMore && items.length > 0 && (
              <p className="text-center text-xs text-slate-400 py-4">
                All {totalCount} quotes loaded
              </p>
            )}
          </>
        )}
      </div>
    </div>
  )
}
