import { useState, useEffect, useCallback } from 'react'
import { API_BASE } from '@/lib/config'

// Types
export interface Industry {
  id: string
  name: string
  category?: string
  description?: string
  key_materials?: string[]
  key_companies?: string[]
  key_applications?: string[]
  market_size?: string
  growth_rate?: number
  trend?: 'growing' | 'emerging' | 'stable' | 'declining'
  trends?: string[]
  is_tracked?: boolean
}

export interface IndustriesResponse {
  count: number
  industries: Industry[]
  categories: string[]
}

export interface IndustryFilters {
  category?: string
  query?: string
  trackedOnly?: boolean
}

export function useIndustries(initialFilters?: IndustryFilters) {
  const [industries, setIndustries] = useState<Industry[]>([])
  const [categories, setCategories] = useState<string[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filters, setFilters] = useState<IndustryFilters>(initialFilters || {})

  const fetchIndustries = useCallback(async (filterOverrides?: IndustryFilters) => {
    setIsLoading(true)
    setError(null)

    const activeFilters = { ...filters, ...filterOverrides }
    
    try {
      const params = new URLSearchParams()
      if (activeFilters.category) params.append('category', activeFilters.category)
      if (activeFilters.query) params.append('query', activeFilters.query)
      if (activeFilters.trackedOnly) params.append('tracked_only', 'true')

      const response = await fetch(`${API_BASE}/api/industries?${params}`)
      
      if (!response.ok) {
        throw new Error(`Failed to fetch industries: ${response.statusText}`)
      }

      const data: IndustriesResponse = await response.json()
      setIndustries(data.industries)
      setCategories(data.categories)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch industries')
      console.error('Error fetching industries:', err)
    } finally {
      setIsLoading(false)
    }
  }, [filters])

  useEffect(() => {
    fetchIndustries()
  }, [fetchIndustries])

  const updateFilters = useCallback((newFilters: Partial<IndustryFilters>) => {
    setFilters(prev => ({ ...prev, ...newFilters }))
  }, [])

  const clearFilters = useCallback(() => {
    setFilters({})
  }, [])

  return {
    industries,
    categories,
    isLoading,
    error,
    filters,
    updateFilters,
    clearFilters,
    refresh: fetchIndustries,
  }
}

// Hook for getting industry insights
export function useIndustryInsights(industryId?: string) {
  const [insights, setInsights] = useState<{
    news: Array<{ title: string; date: string; source: string }>
    trends: string[]
    companies: Array<{ name: string; activity: string }>
  } | null>(null)
  const [isLoading, setIsLoading] = useState(false)

  const fetchInsights = useCallback(async (id: string) => {
    setIsLoading(true)
    try {
      const response = await fetch(`${API_BASE}/api/industries/${id}/insights`)
      
      if (!response.ok) {
        throw new Error(`Failed to fetch insights: ${response.statusText}`)
      }
      
      const data = await response.json()
      setInsights(data)
    } catch (err) {
      console.error('Error fetching industry insights:', err)
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    if (industryId) {
      fetchInsights(industryId)
    }
  }, [industryId, fetchInsights])

  return { insights, isLoading, refresh: fetchInsights }
}
