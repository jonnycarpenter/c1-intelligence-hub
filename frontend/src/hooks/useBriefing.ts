import { useState, useEffect, useCallback } from 'react'
import { api, TimeoutError } from '@/lib/api'
import type { BriefingData } from '@/components/dashboard/BriefingSection'
import type {
    WeeklyBriefing,
    AdHocBriefing,
    AdHocBriefingContext,
    AllBriefingHistory
} from '@/types/briefing'

/**
 * Hook for legacy category-based briefings
 */
export function useBriefing() {
    const [briefings, setBriefings] = useState<BriefingData[]>([])
    const [isLoading, setIsLoading] = useState(false)
    const [error, setError] = useState<Error | null>(null)

    const fetchBriefings = useCallback(async () => {
        setIsLoading(true)
        setError(null)
        try {
            const data = await api.getPulseSummaries()
            setBriefings(Array.isArray(data) ? data : [])
        } catch (err) {
            setError(err instanceof Error ? err : new Error('Failed to fetch briefings'))
            console.error('Error fetching briefings:', err)
        } finally {
            setIsLoading(false)
        }
    }, [])

    useEffect(() => {
        fetchBriefings()
    }, [fetchBriefings])

    return {
        briefings,
        isLoading,
        error,
        refresh: fetchBriefings
    }
}

/**
 * Hook for the new weekly executive briefing with dynamic sections
 */
export function useWeeklyBriefing() {
    const [briefing, setBriefing] = useState<WeeklyBriefing | null>(null)
    const [history, setHistory] = useState<WeeklyBriefing[]>([])
    const [isLoading, setIsLoading] = useState(false)
    const [isLoadingHistory, setIsLoadingHistory] = useState(false)
    const [error, setError] = useState<Error | null>(null)

    const fetchBriefing = useCallback(async () => {
        setIsLoading(true)
        setError(null)
        try {
            const data = await api.getWeeklyBriefing()
            setBriefing(data)
        } catch (err) {
            setError(err instanceof Error ? err : new Error('Failed to fetch weekly briefing'))
            console.error('Error fetching weekly briefing:', err)
        } finally {
            setIsLoading(false)
        }
    }, [])

    const fetchHistory = useCallback(async (limit: number = 10) => {
        setIsLoadingHistory(true)
        try {
            const data = await api.getWeeklyBriefingHistory(limit)
            setHistory(Array.isArray(data) ? data : [])
        } catch (err) {
            console.error('Error fetching briefing history:', err)
        } finally {
            setIsLoadingHistory(false)
        }
    }, [])

    useEffect(() => {
        fetchBriefing()
    }, [fetchBriefing])

    return {
        briefing,
        history,
        isLoading,
        isLoadingHistory,
        error,
        refresh: fetchBriefing,
        loadHistory: fetchHistory,
    }
}

/**
 * Progress step information from SSE events
 */
interface ProgressStep {
    step: string
    label: string
    message: string
    status: 'running' | 'complete'
    count?: number
}

/**
 * Hook for ad hoc quick briefings with session-based conversation tracking.
 * 
 * Session management:
 * - First request creates a new session (session_id returned in response)
 * - Subsequent requests use the same session_id for follow-up tracking
 * - Max 2 follow-ups before redirect to Deep Research
 * - Session expires after 30 minutes of inactivity
 * - Call reset() to start a new session
 * 
 * Progress events:
 * - progressSteps: Array of research phase progress updates
 * - Each step has: step, label, message, status, count
 */
import { usePulseContext } from '@/contexts/PulseContext'

/**
 * Hook for ad hoc quick briefings with session-based conversation tracking.
 * PERSISTED VIA PulseContext
 */
export function useAdHocBriefing() {
    return usePulseContext()
}

/**
 * Hook for combined briefing history timeline
 */
export function useBriefingHistory() {
    const [history, setHistory] = useState<AllBriefingHistory | null>(null)
    const [isLoading, setIsLoading] = useState(false)
    const [error, setError] = useState<Error | null>(null)

    const fetchHistory = useCallback(async (weeklyLimit = 10, adhocLimit = 20) => {
        setIsLoading(true)
        setError(null)
        try {
            const data = await api.getAllBriefingHistory(weeklyLimit, adhocLimit)
            setHistory(data)
        } catch (err) {
            setError(err instanceof Error ? err : new Error('Failed to fetch history'))
            console.error('Error fetching briefing history:', err)
        } finally {
            setIsLoading(false)
        }
    }, [])

    useEffect(() => {
        fetchHistory()
    }, [fetchHistory])

    return {
        history,
        isLoading,
        error,
        refresh: fetchHistory,
    }
}
