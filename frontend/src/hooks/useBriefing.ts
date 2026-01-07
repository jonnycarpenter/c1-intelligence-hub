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
export function useAdHocBriefing() {
    // Stack of briefings - newest first
    const [briefings, setBriefings] = useState<AdHocBriefing[]>([])
    const [isLoading, setIsLoading] = useState(false)
    const [isStreaming, setIsStreaming] = useState(false)
    const [streamedText, setStreamedText] = useState('')
    const [error, setError] = useState<Error | null>(null)
    const [isTimeout, setIsTimeout] = useState(false)
    const [followUpCount, setFollowUpCount] = useState(0)
    const [sessionId, setSessionId] = useState<string | null>(null)
    const [turnsRemaining, setTurnsRemaining] = useState(2)
    // Progress tracking for streaming
    const [progressSteps, setProgressSteps] = useState<ProgressStep[]>([])

    // Helper to add a new briefing to the stack (prepend)
    const addBriefing = useCallback((briefing: AdHocBriefing) => {
        setBriefings(prev => [briefing, ...prev])
    }, [])

    const askQuestion = useCallback(async (
        question: string,
        context?: AdHocBriefingContext,
        isFollowUp: boolean = false
    ) => {
        setIsLoading(true)
        setError(null)
        setIsTimeout(false)
        try {
            const data = await api.createAdHocBriefing({
                question,
                context,
                is_follow_up: isFollowUp,
                session_id: sessionId ?? undefined,  // Pass existing session_id if we have one
            })
            addBriefing(data)

            // Update session state from response
            if (data.session_id) {
                setSessionId(data.session_id)
            }
            if (data.follow_up_count !== undefined) {
                setFollowUpCount(data.follow_up_count)
            }
            if (data.session?.turns_remaining !== undefined) {
                setTurnsRemaining(data.session.turns_remaining)
            }

            return data
        } catch (err) {
            const error = err instanceof Error ? err : new Error('Failed to create briefing')
            setError(error)
            setIsTimeout(err instanceof TimeoutError)
            console.error('Error creating ad hoc briefing:', err)
            throw error
        } finally {
            setIsLoading(false)
        }
    }, [sessionId])

    const streamQuestion = useCallback(async (
        question: string,
        context?: AdHocBriefingContext,
        isFollowUp: boolean = false
    ) => {
        setIsStreaming(true)
        setStreamedText('')
        setError(null)
        setIsTimeout(false)
        setProgressSteps([])  // Reset progress for new stream

        try {
            const stream = await api.streamAdHocBriefing({
                question,
                context,
                is_follow_up: isFollowUp,
                session_id: sessionId ?? undefined,  // Pass existing session_id if we have one
            })

            if (!stream) {
                throw new Error('No stream returned')
            }

            const reader = stream.getReader()
            const decoder = new TextDecoder()
            let fullText = ''

            while (true) {
                const { done, value } = await reader.read()
                if (done) break

                const chunk = decoder.decode(value, { stream: true })
                const lines = chunk.split('\n')

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const data = line.slice(6)
                        if (data === '[DONE]') {
                            // Construct response before returning
                            if (fullText) {
                                const streamedResponse: AdHocBriefing = {
                                    id: sessionId || `stream-${Date.now()}`,
                                    question,
                                    answer: fullText,
                                    sources_used: [],
                                    confidence: 'medium',
                                    suggest_deep_research: followUpCount >= 2,
                                    related_topics: [],
                                    follow_up_count: followUpCount,
                                    generated_at: new Date().toISOString(),
                                    session_id: sessionId ?? undefined,
                                }
                                addBriefing(streamedResponse)
                            }
                            setIsStreaming(false)
                            return fullText
                        }
                        try {
                            const parsed = JSON.parse(data)
                            if (parsed.type === 'content') {
                                fullText += parsed.text
                                setStreamedText(fullText)
                            } else if (parsed.type === 'progress') {
                                // Update progress steps
                                setProgressSteps(prev => {
                                    const steps = prev || []
                                    const existing = steps.findIndex(p => p.step === parsed.step)
                                    const newStep: ProgressStep = {
                                        step: parsed.step,
                                        label: parsed.label || parsed.step,
                                        message: parsed.message,
                                        status: parsed.status,
                                        count: parsed.count,
                                    }
                                    if (existing >= 0) {
                                        // Update existing step
                                        const updated = [...steps]
                                        updated[existing] = newStep
                                        return updated
                                    } else {
                                        // Add new step
                                        return [...steps, newStep]
                                    }
                                })
                            } else if (parsed.type === 'session_info') {
                                // Update session state from streaming response
                                if (parsed.session_id) {
                                    setSessionId(parsed.session_id)
                                }
                                if (parsed.follow_up_count !== undefined) {
                                    setFollowUpCount(parsed.follow_up_count)
                                }
                                if (parsed.turns_remaining !== undefined) {
                                    setTurnsRemaining(parsed.turns_remaining)
                                }
                            } else if (parsed.type === 'redirect') {
                                addBriefing({
                                    id: '',
                                    question,
                                    answer: parsed.message,
                                    sources_used: [],
                                    confidence: 'low',
                                    suggest_deep_research: true,
                                    deep_research_query: parsed.deep_research_query,
                                    related_topics: [],
                                    follow_up_count: parsed.follow_up_count ?? followUpCount,
                                    redirect_to_deep_research: true,
                                    generated_at: new Date().toISOString(),
                                    session_id: parsed.session_id,
                                })
                            }
                        } catch {
                            // Plain text chunk
                            fullText += data
                            setStreamedText(fullText)
                        }
                    }
                }
            }

            // Construct the response object from streamed text so ResponseCard renders
            if (fullText) {
                const streamedResponse: AdHocBriefing = {
                    id: sessionId || `stream-${Date.now()}`,
                    question,
                    answer: fullText,
                    sources_used: [], // Sources embedded in markdown text
                    confidence: 'medium',
                    suggest_deep_research: followUpCount >= 2,
                    related_topics: [],
                    follow_up_count: followUpCount,
                    generated_at: new Date().toISOString(),
                    session_id: sessionId ?? undefined,
                }
                addBriefing(streamedResponse)
            }

            return fullText
        } catch (err) {
            const error = err instanceof Error ? err : new Error('Failed to stream briefing')
            setError(error)
            setIsTimeout(err instanceof TimeoutError)
            console.error('Error streaming ad hoc briefing:', err)
            throw error
        } finally {
            setIsStreaming(false)
        }
    }, [sessionId, followUpCount])

    const reset = useCallback(() => {
        setBriefings([])  // Clear all briefings
        setStreamedText('')
        setFollowUpCount(0)
        setSessionId(null)  // Clear session to start fresh
        setTurnsRemaining(2)
        setError(null)
        setIsTimeout(false)
        setProgressSteps([])  // Clear progress
    }, [])

    // Current briefing is the first in the stack (most recent)
    const currentBriefing = briefings.length > 0 ? briefings[0] : null

    return {
        briefings,        // All briefings in the session (newest first)
        currentBriefing,  // Most recent briefing (for backward compat)
        response: currentBriefing, // Backward compat alias
        streamedText,
        isLoading,
        isStreaming,
        error,
        isTimeout,
        followUpCount,
        sessionId,        // Expose session ID for debugging/display
        turnsRemaining,   // How many follow-ups left before redirect
        progressSteps,    // Research phase progress
        askQuestion,
        streamQuestion,
        reset,
    }
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
