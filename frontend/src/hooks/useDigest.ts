'use client'

import { useState, useEffect, useCallback } from 'react'
import { api, ApiDigest, ApiDigestItem } from '@/lib/api'
import { DigestItem, DigestStats } from '@/types'

/**
 * Transform API digest item to frontend format
 */
function transformDigestItem(item: ApiDigestItem): DigestItem {
  return {
    id: item.id,
    title: item.title,
    summary: item.summary,
    category: item.category as DigestItem['category'],
    priority: item.priority as DigestItem['priority'],
    sources: item.sources.map(s => ({
      name: s.title,
      url: s.url,
    })),
    entities: {
      companies: item.entities.companies || [],
      materials: item.entities.materials || [],
      topics: item.entities.topics || [],
    },
    timestamp: formatRelativeTime(item.published_at),
    coverage_count: item.coverage_count,
    relevance_score: item.relevance_score,
  }
}

/**
 * Format ISO date string to relative time
 */
function formatRelativeTime(isoString: string): string {
  const date = new Date(isoString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / (1000 * 60))
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60))
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

  if (diffMins < 1) return 'Just now'
  if (diffMins < 60) return `${diffMins} minute${diffMins !== 1 ? 's' : ''} ago`
  if (diffHours < 24) return `${diffHours} hour${diffHours !== 1 ? 's' : ''} ago`
  if (diffDays < 7) return `${diffDays} day${diffDays !== 1 ? 's' : ''} ago`

  return date.toLocaleDateString()
}

/**
 * Transform API digest stats to frontend format
 */
function transformStats(apiDigest: ApiDigest | null): DigestStats | null {
  if (!apiDigest?.stats) return null
  return {
    totalItems: apiDigest.stats.total_items || 0,
    byCategory: apiDigest.stats.by_category || {},
    byPriority: apiDigest.stats.by_priority || {},
    lastUpdated: apiDigest.generated_at || new Date().toISOString(),
  }
}

interface UseDigestResult {
  items: DigestItem[]
  stats: DigestStats | null
  summary: string | null
  isLoading: boolean
  error: Error | null
  refresh: () => Promise<void>
  filterByCategory: (category: string | null) => void
  filterByPriority: (priority: string | null) => void
}

interface UseDigestOptions {
  hours?: number
  limit?: number  // Max items to return (default 100, max 1000)
  priorities?: string[]  // Filter to specific priorities (e.g., ['Critical', 'High', 'Medium'])
  autoRefresh?: boolean
  refreshInterval?: number
}

/**
 * React hook for fetching and managing digest data
 */
export function useDigest(options: UseDigestOptions = {}): UseDigestResult {
  const {
    hours = 24,
    limit = 100,
    priorities: initialPriorities,
    autoRefresh = false,
    refreshInterval = 5 * 60 * 1000 // 5 minutes
  } = options

  const [rawDigest, setRawDigest] = useState<ApiDigest | null>(null)
  const [items, setItems] = useState<DigestItem[]>([])
  const [stats, setStats] = useState<DigestStats | null>(null)
  const [summary, setSummary] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)
  const [categoryFilter, setCategoryFilter] = useState<string | null>(null)
  const [priorityFilter, setPriorityFilter] = useState<string | null>(null)

  const fetchDigest = useCallback(async () => {
    try {
      setIsLoading(true)
      setError(null)

      const filters: { hours?: number; categories?: string[]; priorities?: string[]; limit?: number } = { hours, limit }
      if (categoryFilter) filters.categories = [categoryFilter]

      // Use initial priorities from options, or dynamic filter if set
      if (priorityFilter) {
        filters.priorities = [priorityFilter]
      } else if (initialPriorities?.length) {
        filters.priorities = initialPriorities
      }

      const digest = await api.getDigest(filters)
      setRawDigest(digest)
      setItems(Array.isArray(digest?.items) ? digest.items.map(transformDigestItem) : [])
      setStats(transformStats(digest))
      setSummary(digest?.summary || null)
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Failed to fetch digest'))
    } finally {
      setIsLoading(false)
    }
  }, [hours, limit, initialPriorities, categoryFilter, priorityFilter])

  const refresh = useCallback(async () => {
    try {
      setIsLoading(true)
      setError(null)

      const digest = await api.refreshDigest()
      setRawDigest(digest)
      setItems(digest.items.map(transformDigestItem))
      setStats(transformStats(digest))
      setSummary(digest.summary || null)
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Failed to refresh digest'))
    } finally {
      setIsLoading(false)
    }
  }, [])

  const filterByCategory = useCallback((category: string | null) => {
    setCategoryFilter(category)
  }, [])

  const filterByPriority = useCallback((priority: string | null) => {
    setPriorityFilter(priority)
  }, [])

  // Initial fetch
  useEffect(() => {
    fetchDigest()
  }, [fetchDigest])

  // Auto-refresh
  useEffect(() => {
    if (!autoRefresh) return

    const interval = setInterval(fetchDigest, refreshInterval)
    return () => clearInterval(interval)
  }, [autoRefresh, refreshInterval, fetchDigest])

  return {
    items,
    stats,
    summary,
    isLoading,
    error,
    refresh,
    filterByCategory,
    filterByPriority,
  }
}

export default useDigest
