/**
 * Hooks for Data & Preferences management
 */

import { useState, useEffect, useCallback } from 'react'
import { API_BASE } from '@/lib/config'

// ============================================
// Types
// ============================================

export interface TrackedCompany {
  company_id: string
  company: string
  type: string
  stock_ticker: string
  industries_served: string
  description: string
  processes_services: string
}

export interface TrackedMaterial {
  material_proc_id: string
  material_process_name: string
  type: string
  est_manufacturer_margin_tier: string
  industries_served: string
  examples: string
}

export interface TrackedIndustry {
  industry_id: string
  industry_name: string
  description: string
  key_materials: string
  key_processes: string
}

export interface UserPreferences {
  global_exclusions: Array<{ id: string; value: string; status: string }>
  tracked_companies: string[]
  tracked_materials: string[]
  tracked_industries: string[]
  report_preferences: Record<string, unknown>
  created_at?: string
  updated_at?: string
}

export interface ChangeLogEntry {
  id: string
  timestamp: string
  change_type: string
  category: 'company' | 'material' | 'industry' | 'preference' | 'system'
  description: string
  user_name: string
  previous_value?: string
  new_value?: string
  status: 'success' | 'failed' | 'rolled_back'
  agent_used?: string
  details?: Record<string, unknown>
}

export interface DataSummary {
  companies: {
    total: number
    by_type: Record<string, number>
  }
  materials: {
    total: number
    by_type: Record<string, number>
  }
  industries: {
    total: number
  }
  preferences: {
    global_exclusions_count: number
    tracked_companies_count: number
    tracked_materials_count: number
    tracked_industries_count: number
  }
  change_log: {
    total_changes: number
    last_change: ChangeLogEntry | null
  }
}

// ============================================
// Hook: useDataSummary
// ============================================

export function useDataSummary() {
  const [summary, setSummary] = useState<DataSummary | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)

  const fetchSummary = useCallback(async () => {
    try {
      setIsLoading(true)
      const response = await fetch(`${API_BASE}/api/data-preferences/summary`)
      if (!response.ok) throw new Error('Failed to fetch summary')
      const data = await response.json()
      setSummary(data)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Unknown error'))
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchSummary()
  }, [fetchSummary])

  return { summary, isLoading, error, refresh: fetchSummary }
}

// ============================================
// Hook: useTrackedCompanies
// ============================================

export function useTrackedCompanies() {
  const [companies, setCompanies] = useState<TrackedCompany[]>([])
  const [types, setTypes] = useState<string[]>([])
  const [total, setTotal] = useState(0)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)

  const fetchCompanies = useCallback(async (params?: { type?: string; search?: string }) => {
    try {
      setIsLoading(true)
      const searchParams = new URLSearchParams()
      if (params?.type) searchParams.set('type_filter', params.type)
      if (params?.search) searchParams.set('search', params.search)
      searchParams.set('limit', '200')
      
      const response = await fetch(`${API_BASE}/api/data-preferences/companies?${searchParams}`)
      if (!response.ok) throw new Error('Failed to fetch companies')
      const data = await response.json()
      setCompanies(data.data)
      setTypes(data.types || [])
      setTotal(data.total)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Unknown error'))
    } finally {
      setIsLoading(false)
    }
  }, [])

  const addCompany = useCallback(async (name: string, userName: string, type?: string, ticker?: string) => {
    const response = await fetch(`${API_BASE}/api/data-preferences/companies`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, user_name: userName, item_type: type, ticker }),
    })
    if (!response.ok) {
      const data = await response.json()
      throw new Error(data.detail || 'Failed to add company')
    }
    await fetchCompanies()
    return response.json()
  }, [fetchCompanies])

  const removeCompany = useCallback(async (name: string, userName: string) => {
    const response = await fetch(
      `${API_BASE}/api/data-preferences/companies/${encodeURIComponent(name)}?user_name=${encodeURIComponent(userName)}`,
      { method: 'DELETE' }
    )
    if (!response.ok) {
      const data = await response.json()
      throw new Error(data.detail || 'Failed to remove company')
    }
    await fetchCompanies()
    return response.json()
  }, [fetchCompanies])

  useEffect(() => {
    fetchCompanies()
  }, [fetchCompanies])

  return { companies, types, total, isLoading, error, fetchCompanies, addCompany, removeCompany }
}

// ============================================
// Hook: useTrackedMaterials
// ============================================

export function useTrackedMaterials() {
  const [materials, setMaterials] = useState<TrackedMaterial[]>([])
  const [types, setTypes] = useState<string[]>([])
  const [total, setTotal] = useState(0)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)

  const fetchMaterials = useCallback(async (params?: { type?: string; search?: string }) => {
    try {
      setIsLoading(true)
      const searchParams = new URLSearchParams()
      if (params?.type) searchParams.set('type_filter', params.type)
      if (params?.search) searchParams.set('search', params.search)
      searchParams.set('limit', '200')
      
      const response = await fetch(`${API_BASE}/api/data-preferences/materials?${searchParams}`)
      if (!response.ok) throw new Error('Failed to fetch materials')
      const data = await response.json()
      setMaterials(data.data)
      setTypes(data.types || [])
      setTotal(data.total)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Unknown error'))
    } finally {
      setIsLoading(false)
    }
  }, [])

  const addMaterial = useCallback(async (name: string, userName: string, type?: string) => {
    const response = await fetch(`${API_BASE}/api/data-preferences/materials`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, user_name: userName, item_type: type }),
    })
    if (!response.ok) {
      const data = await response.json()
      throw new Error(data.detail || 'Failed to add material')
    }
    await fetchMaterials()
    return response.json()
  }, [fetchMaterials])

  const removeMaterial = useCallback(async (name: string, userName: string) => {
    const response = await fetch(
      `${API_BASE}/api/data-preferences/materials/${encodeURIComponent(name)}?user_name=${encodeURIComponent(userName)}`,
      { method: 'DELETE' }
    )
    if (!response.ok) {
      const data = await response.json()
      throw new Error(data.detail || 'Failed to remove material')
    }
    await fetchMaterials()
    return response.json()
  }, [fetchMaterials])

  useEffect(() => {
    fetchMaterials()
  }, [fetchMaterials])

  return { materials, types, total, isLoading, error, fetchMaterials, addMaterial, removeMaterial }
}

// ============================================
// Hook: useTrackedIndustries
// ============================================

export function useTrackedIndustries() {
  const [industries, setIndustries] = useState<TrackedIndustry[]>([])
  const [total, setTotal] = useState(0)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)

  const fetchIndustries = useCallback(async (params?: { search?: string }) => {
    try {
      setIsLoading(true)
      const searchParams = new URLSearchParams()
      if (params?.search) searchParams.set('search', params.search)
      searchParams.set('limit', '100')
      
      const response = await fetch(`${API_BASE}/api/data-preferences/industries?${searchParams}`)
      if (!response.ok) throw new Error('Failed to fetch industries')
      const data = await response.json()
      setIndustries(data.data)
      setTotal(data.total)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Unknown error'))
    } finally {
      setIsLoading(false)
    }
  }, [])

  const addIndustry = useCallback(async (name: string, userName: string, description?: string) => {
    const response = await fetch(`${API_BASE}/api/data-preferences/industries`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, user_name: userName, description }),
    })
    if (!response.ok) {
      const data = await response.json()
      throw new Error(data.detail || 'Failed to add industry')
    }
    await fetchIndustries()
    return response.json()
  }, [fetchIndustries])

  const removeIndustry = useCallback(async (name: string, userName: string) => {
    const response = await fetch(
      `${API_BASE}/api/data-preferences/industries/${encodeURIComponent(name)}?user_name=${encodeURIComponent(userName)}`,
      { method: 'DELETE' }
    )
    if (!response.ok) {
      const data = await response.json()
      throw new Error(data.detail || 'Failed to remove industry')
    }
    await fetchIndustries()
    return response.json()
  }, [fetchIndustries])

  useEffect(() => {
    fetchIndustries()
  }, [fetchIndustries])

  return { industries, total, isLoading, error, fetchIndustries, addIndustry, removeIndustry }
}

// ============================================
// Hook: useUserPreferences
// ============================================

export function useUserPreferences() {
  const [preferences, setPreferences] = useState<UserPreferences | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)

  const fetchPreferences = useCallback(async () => {
    try {
      setIsLoading(true)
      const response = await fetch(`${API_BASE}/api/data-preferences/preferences`)
      if (!response.ok) throw new Error('Failed to fetch preferences')
      const data = await response.json()
      setPreferences(data)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Unknown error'))
    } finally {
      setIsLoading(false)
    }
  }, [])

  const updatePreference = useCallback(async (
    action: 'add' | 'remove' | 'update',
    preferenceType: string,
    value: string,
    userName: string
  ) => {
    const response = await fetch(`${API_BASE}/api/data-preferences/preferences`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action, preference_type: preferenceType, value, user_name: userName }),
    })
    if (!response.ok) {
      const data = await response.json()
      throw new Error(data.detail || 'Failed to update preference')
    }
    await fetchPreferences()
    return response.json()
  }, [fetchPreferences])

  useEffect(() => {
    fetchPreferences()
  }, [fetchPreferences])

  return { preferences, isLoading, error, fetchPreferences, updatePreference }
}

// ============================================
// Hook: useChangeLog
// ============================================

export function useChangeLog() {
  const [changes, setChanges] = useState<ChangeLogEntry[]>([])
  const [total, setTotal] = useState(0)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)

  const fetchChanges = useCallback(async (params?: { category?: string; user?: string; limit?: number }) => {
    try {
      setIsLoading(true)
      const searchParams = new URLSearchParams()
      if (params?.category) searchParams.set('category', params.category)
      if (params?.user) searchParams.set('user_name', params.user)
      searchParams.set('limit', String(params?.limit || 50))
      
      const response = await fetch(`${API_BASE}/api/data-preferences/change-log?${searchParams}`)
      if (!response.ok) throw new Error('Failed to fetch change log')
      const data = await response.json()
      setChanges(data.data)
      setTotal(data.total)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Unknown error'))
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchChanges()
  }, [fetchChanges])

  return { changes, total, isLoading, error, fetchChanges }
}
