import { useState, useEffect, useCallback } from 'react'
import { api } from '@/lib/api'

// Types matching the API response
export interface NarrativeIndustry {
  id: string
  name: string
  article_count_90d: number
  trend: 'up' | 'down' | 'flat'
}

export interface MonthlyData {
  month: string
  month_label: string
  article_count: number
  delta_vs_prior: number | null
  event_types: Array<{ name: string; count: number; delta: number | null }>
  top_companies: Array<{ name: string; count: number; delta: number | null }>
  top_themes: Array<{ name: string; count: number; delta: number | null }>
  top_geographies: Array<{ name: string; count: number }>
  sentiment: { positive: number; neutral: number; negative: number }
  top_articles: Array<{
    id: string
    title: string
    url: string
    source_name: string
    published_at: string
    summary: string
    event_type: string | null
    sentiment: string
  }>
}

export interface TimelineResponse {
  industry: string
  period_days: number
  monthly_data: MonthlyData[]
  totals: {
    total_articles: number
    avg_monthly: number
    trend_direction: 'up' | 'down' | 'flat'
  }
}

export function useIndustryNarratives() {
  const [industries, setIndustries] = useState<NarrativeIndustry[]>([])
  const [selectedIndustry, setSelectedIndustry] = useState<string | null>(null)
  const [timeline, setTimeline] = useState<TimelineResponse | null>(null)
  const [isLoadingList, setIsLoadingList] = useState(true)
  const [isLoadingTimeline, setIsLoadingTimeline] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Fetch industry list on mount
  const fetchIndustries = useCallback(async () => {
    setIsLoadingList(true)
    setError(null)
    try {
      const data = await api.getIndustryNarrativesList()
      setIndustries(data.industries)
      // Auto-select first industry if none selected
      if (!selectedIndustry && data.industries.length > 0) {
        setSelectedIndustry(data.industries[0].id)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch industries')
      console.error('Error fetching industry narratives list:', err)
    } finally {
      setIsLoadingList(false)
    }
  }, [selectedIndustry])

  // Fetch timeline when industry changes
  const fetchTimeline = useCallback(async (industryId: string) => {
    setIsLoadingTimeline(true)
    setError(null)
    try {
      const data = await api.getIndustryTimeline(industryId)
      setTimeline(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch timeline')
      console.error('Error fetching industry timeline:', err)
    } finally {
      setIsLoadingTimeline(false)
    }
  }, [])

  useEffect(() => {
    fetchIndustries()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (selectedIndustry) {
      fetchTimeline(selectedIndustry)
    }
  }, [selectedIndustry, fetchTimeline])

  const selectIndustry = useCallback((id: string) => {
    setSelectedIndustry(id)
  }, [])

  const refresh = useCallback(() => {
    fetchIndustries()
    if (selectedIndustry) {
      fetchTimeline(selectedIndustry)
    }
  }, [fetchIndustries, fetchTimeline, selectedIndustry])

  return {
    industries,
    selectedIndustry,
    selectIndustry,
    timeline,
    isLoadingList,
    isLoadingTimeline,
    error,
    refresh,
  }
}
