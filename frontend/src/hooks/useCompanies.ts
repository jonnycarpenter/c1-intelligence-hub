import { useState, useEffect, useCallback } from 'react'
import { API_BASE } from '@/lib/config'

// Types
export interface Company {
  id: string
  name: string
  ticker?: string
  type: string
  industries: string[]
  description?: string
  website?: string
  headquarters?: string
  revenue?: string
  employees?: string
  is_tracked: boolean
}

export interface CompaniesResponse {
  count: number
  companies: Company[]
  types: string[]
}

export interface CompanyFilters {
  type?: string
  industry?: string
  query?: string
  trackedOnly?: boolean
}

export function useCompanies(initialFilters?: CompanyFilters) {
  const [companies, setCompanies] = useState<Company[]>([])
  const [types, setTypes] = useState<string[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filters, setFilters] = useState<CompanyFilters>(initialFilters || {})

  const fetchCompanies = useCallback(async (filterOverrides?: CompanyFilters) => {
    setIsLoading(true)
    setError(null)

    const activeFilters = { ...filters, ...filterOverrides }
    
    try {
      const params = new URLSearchParams()
      if (activeFilters.type) params.append('type', activeFilters.type)
      if (activeFilters.industry) params.append('industry', activeFilters.industry)
      if (activeFilters.query) params.append('query', activeFilters.query)
      if (activeFilters.trackedOnly) params.append('tracked_only', 'true')

      const response = await fetch(`${API_BASE}/api/companies?${params}`)
      
      if (!response.ok) {
        throw new Error(`Failed to fetch companies: ${response.statusText}`)
      }

      const data: CompaniesResponse = await response.json()
      setCompanies(data.companies)
      setTypes(data.types)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch companies')
      console.error('Error fetching companies:', err)
    } finally {
      setIsLoading(false)
    }
  }, [filters])

  useEffect(() => {
    fetchCompanies()
  }, [fetchCompanies])

  const updateFilters = useCallback((newFilters: Partial<CompanyFilters>) => {
    setFilters(prev => ({ ...prev, ...newFilters }))
  }, [])

  const clearFilters = useCallback(() => {
    setFilters({})
  }, [])

  return {
    companies,
    types,
    isLoading,
    error,
    filters,
    updateFilters,
    clearFilters,
    refresh: fetchCompanies,
  }
}

// Hook for tracking/untracking companies
export function useCompanyTracking() {
  const [isUpdating, setIsUpdating] = useState(false)

  const trackCompany = useCallback(async (companyName: string, ticker?: string, type?: string) => {
    setIsUpdating(true)
    try {
      const response = await fetch(`${API_BASE}/api/companies/track`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ company_name: companyName, ticker, type }),
      })
      
      if (!response.ok) {
        throw new Error(`Failed to track company: ${response.statusText}`)
      }
      
      return await response.json()
    } catch (err) {
      console.error('Error tracking company:', err)
      throw err
    } finally {
      setIsUpdating(false)
    }
  }, [])

  const untrackCompany = useCallback(async (companyName: string) => {
    setIsUpdating(true)
    try {
      const response = await fetch(`${API_BASE}/api/companies/untrack`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ company_name: companyName }),
      })
      
      if (!response.ok) {
        throw new Error(`Failed to untrack company: ${response.statusText}`)
      }
      
      return await response.json()
    } catch (err) {
      console.error('Error untracking company:', err)
      throw err
    } finally {
      setIsUpdating(false)
    }
  }, [])

  return { trackCompany, untrackCompany, isUpdating }
}
