'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import { api } from '@/lib/api'
import type { ExpertFeedItem } from '@/types'

export interface ExpertFeedFilters {
  search?: string
  podcast_name?: string
  speaker_name?: string
  themes?: string[]
  time_range?: string
  sort_by?: 'newest' | 'relevance'
}

interface UseExpertFeedResult {
  items: ExpertFeedItem[]
  isLoading: boolean
  error: Error | null
  hasMore: boolean
  totalCount: number
  filters: ExpertFeedFilters
  setFilters: (filters: ExpertFeedFilters) => void
  loadMore: () => void
}

const PAGE_SIZE = 40

export function useExpertFeed(): UseExpertFeedResult {
  const [items, setItems] = useState<ExpertFeedItem[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)
  const [hasMore, setHasMore] = useState(false)
  const [totalCount, setTotalCount] = useState(0)
  const [filters, setFilters] = useState<ExpertFeedFilters>({})
  const [offset, setOffset] = useState(0)
  const hasLoadedOnce = useRef(false)

  const fetchItems = useCallback(async (currentOffset: number, append: boolean) => {
    try {
      if (!append) {
        setIsLoading(true)
      }
      setError(null)

      const result = await api.getExpertFeed({
        ...filters,
        limit: PAGE_SIZE,
        offset: currentOffset,
      })

      if (append) {
        setItems(prev => [...prev, ...result.items])
      } else {
        setItems(result.items)
      }
      setTotalCount(result.total_count)
      setHasMore(result.has_more)
      hasLoadedOnce.current = true
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Failed to fetch expert feed'))
    } finally {
      setIsLoading(false)
    }
  }, [filters])

  // Reset and fetch when filters change
  useEffect(() => {
    setOffset(0)
    fetchItems(0, false)
  }, [fetchItems])

  const loadMore = useCallback(() => {
    if (!hasMore || isLoading) return
    const newOffset = offset + PAGE_SIZE
    setOffset(newOffset)
    fetchItems(newOffset, true)
  }, [hasMore, isLoading, offset, fetchItems])

  return {
    items,
    isLoading,
    error,
    hasMore,
    totalCount,
    filters,
    setFilters,
    loadMore,
  }
}

export default useExpertFeed
