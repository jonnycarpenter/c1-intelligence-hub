'use client'

import React, { useState, useMemo, useEffect, useRef, useCallback } from 'react'
import {
  Search,
  ArrowUpDown,
  X,
  Loader2,
  BarChart3,
  FileText,
  Layers,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import FinancialFeedCard from './FinancialFeedCard'
import { useFinancialFeed } from '@/hooks/useFinancialFeed'
import type { FinancialFeedFilters } from '@/hooks/useFinancialFeed'

// =============================================================================
// Main Component
// =============================================================================

export default function FinancialFeedView() {
  const { items, isLoading, error, hasMore, totalCount, filters, setFilters, loadMore } = useFinancialFeed()

  // Local filter state (applied on change)
  const [searchInput, setSearchInput] = useState('')
  const [sourceType, setSourceType] = useState<'all' | 'earnings' | 'sec'>('all')
  const [selectedTicker, setSelectedTicker] = useState<string>('all')
  const [selectedType, setSelectedType] = useState<string>('all')
  const [selectedSentiment, setSelectedSentiment] = useState<string>('all')
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
    const newFilters: FinancialFeedFilters = {
      search: searchInput || undefined,
      source_type: sourceType,
      ticker: selectedTicker !== 'all' ? selectedTicker : undefined,
      type_filter: selectedType !== 'all' ? selectedType : undefined,
      sentiment: selectedSentiment !== 'all' ? selectedSentiment : undefined,
      sort_by: sortBy,
    }
    setFilters(newFilters)
  }, [sourceType, selectedTicker, selectedType, selectedSentiment, sortBy])

  // Extract unique tickers for dropdown
  const availableTickers = useMemo(() => {
    const tickers = new Set<string>()
    items.forEach(item => {
      if (item.ticker) tickers.add(item.ticker)
    })
    return Array.from(tickers).sort()
  }, [items])

  // Extract type values based on source filter
  const availableTypes = useMemo(() => {
    const types = new Set<string>()
    items.forEach(item => {
      if (item.source_type === 'earnings' && item.quote_type) types.add(item.quote_type)
      if (item.source_type === 'sec' && item.nugget_type) types.add(item.nugget_type)
    })
    return Array.from(types).sort()
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
    setSourceType('all')
    setSelectedTicker('all')
    setSelectedType('all')
    setSelectedSentiment('all')
    setSortBy('newest')
    setFilters({})
  }

  const hasActiveFilters = searchInput || sourceType !== 'all' || selectedTicker !== 'all' || selectedType !== 'all' || selectedSentiment !== 'all'

  function formatLabel(str: string): string {
    return str.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')
  }

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
              placeholder="Search quotes & nuggets..."
              className="w-full pl-8 pr-3 py-1.5 text-sm rounded-lg border border-slate-200 focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>

          {/* Source type segmented toggle */}
          <div className="flex items-center border border-slate-200 rounded-lg overflow-hidden">
            <button
              onClick={() => setSourceType('all')}
              className={cn(
                'flex items-center gap-1 px-3 py-1.5 text-xs font-medium transition-colors',
                sourceType === 'all' ? 'bg-slate-800 text-white' : 'bg-white text-slate-600 hover:bg-slate-50'
              )}
            >
              <Layers size={12} /> All
            </button>
            <button
              onClick={() => setSourceType('earnings')}
              className={cn(
                'flex items-center gap-1 px-3 py-1.5 text-xs font-medium border-x border-slate-200 transition-colors',
                sourceType === 'earnings' ? 'bg-blue-600 text-white' : 'bg-white text-slate-600 hover:bg-slate-50'
              )}
            >
              <BarChart3 size={12} /> Earnings
            </button>
            <button
              onClick={() => setSourceType('sec')}
              className={cn(
                'flex items-center gap-1 px-3 py-1.5 text-xs font-medium transition-colors',
                sourceType === 'sec' ? 'bg-amber-600 text-white' : 'bg-white text-slate-600 hover:bg-slate-50'
              )}
            >
              <FileText size={12} /> SEC
            </button>
          </div>

          {/* Ticker */}
          <select
            value={selectedTicker}
            onChange={(e) => setSelectedTicker(e.target.value)}
            className="px-3 py-1.5 text-xs rounded-lg border border-slate-200 bg-white focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="all">All Tickers</option>
            {availableTickers.map(t => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>

          {/* Type filter */}
          <select
            value={selectedType}
            onChange={(e) => setSelectedType(e.target.value)}
            className="px-3 py-1.5 text-xs rounded-lg border border-slate-200 bg-white focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="all">All Types</option>
            {availableTypes.map(t => (
              <option key={t} value={t}>{formatLabel(t)}</option>
            ))}
          </select>

          {/* Sentiment (earnings only) */}
          {sourceType !== 'sec' && (
            <select
              value={selectedSentiment}
              onChange={(e) => setSelectedSentiment(e.target.value)}
              className="px-3 py-1.5 text-xs rounded-lg border border-slate-200 bg-white focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option value="all">All Sentiment</option>
              <option value="bullish">Bullish</option>
              <option value="bearish">Bearish</option>
              <option value="cautious">Cautious</option>
              <option value="neutral">Neutral</option>
            </select>
          )}

          {/* Sort */}
          <div className="flex items-center gap-1 ml-auto">
            <ArrowUpDown size={12} className="text-slate-400" />
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as 'newest' | 'relevance')}
              className="px-2 py-1.5 text-xs rounded-lg border border-slate-200 bg-white focus:outline-none focus:ring-1 focus:ring-blue-500"
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
          {totalCount > 0 ? `${totalCount} items` : isLoading ? 'Loading...' : 'No items found'}
        </div>
      </div>

      {/* Card list */}
      <div className="px-6 py-4 space-y-3">
        {isLoading && items.length === 0 ? (
          <div className="flex items-center justify-center py-16">
            <div className="text-center">
              <Loader2 className="w-8 h-8 animate-spin text-blue-500 mx-auto mb-3" />
              <p className="text-slate-500 text-sm">Loading financial intelligence...</p>
            </div>
          </div>
        ) : error ? (
          <div className="flex items-center justify-center py-16">
            <p className="text-red-500 text-sm">{error.message}</p>
          </div>
        ) : items.length === 0 ? (
          <div className="flex items-center justify-center py-16">
            <div className="text-center">
              <BarChart3 className="w-10 h-10 text-slate-300 mx-auto mb-3" />
              <p className="text-slate-500 text-sm">No financial intelligence found</p>
              <p className="text-slate-400 text-xs mt-1">Try adjusting your filters</p>
            </div>
          </div>
        ) : (
          <>
            {items.map((item) => (
              <FinancialFeedCard key={item.id} item={item} />
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
                All {totalCount} items loaded
              </p>
            )}
          </>
        )}
      </div>
    </div>
  )
}
