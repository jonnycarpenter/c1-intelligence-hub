import { useState, useEffect, useCallback } from 'react'
import { api } from '@/lib/api'
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
 * Hook for ad hoc quick briefings
 */
export function useAdHocBriefing() {
    const [response, setResponse] = useState<AdHocBriefing | null>(null)
    const [isLoading, setIsLoading] = useState(false)
    const [isStreaming, setIsStreaming] = useState(false)
    const [streamedText, setStreamedText] = useState('')
    const [error, setError] = useState<Error | null>(null)
    const [followUpCount, setFollowUpCount] = useState(0)

    const askQuestion = useCallback(async (
        question: string, 
        context?: AdHocBriefingContext,
        isFollowUp: boolean = false
    ) => {
        setIsLoading(true)
        setError(null)
        try {
            const data = await api.createAdHocBriefing({
                question,
                context,
                is_follow_up: isFollowUp,
            })
            setResponse(data)
            if (data.follow_up_count !== undefined) {
                setFollowUpCount(data.follow_up_count)
            }
            return data
        } catch (err) {
            const error = err instanceof Error ? err : new Error('Failed to create briefing')
            setError(error)
            console.error('Error creating ad hoc briefing:', err)
            throw error
        } finally {
            setIsLoading(false)
        }
    }, [])

    const streamQuestion = useCallback(async (
        question: string,
        context?: AdHocBriefingContext,
        isFollowUp: boolean = false
    ) => {
        setIsStreaming(true)
        setStreamedText('')
        setError(null)
        
        try {
            const stream = await api.streamAdHocBriefing({
                question,
                context,
                is_follow_up: isFollowUp,
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
                            setIsStreaming(false)
                            return fullText
                        }
                        try {
                            const parsed = JSON.parse(data)
                            if (parsed.type === 'content') {
                                fullText += parsed.text
                                setStreamedText(fullText)
                            } else if (parsed.type === 'redirect') {
                                setResponse({
                                    id: '',
                                    question,
                                    answer: parsed.message,
                                    sources_used: [],
                                    confidence: 'low',
                                    suggest_deep_research: true,
                                    deep_research_query: parsed.deep_research_query,
                                    related_topics: [],
                                    follow_up_count: followUpCount,
                                    redirect_to_deep_research: true,
                                    generated_at: new Date().toISOString(),
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

            return fullText
        } catch (err) {
            const error = err instanceof Error ? err : new Error('Failed to stream briefing')
            setError(error)
            console.error('Error streaming ad hoc briefing:', err)
            throw error
        } finally {
            setIsStreaming(false)
        }
    }, [followUpCount])

    const reset = useCallback(() => {
        setResponse(null)
        setStreamedText('')
        setFollowUpCount(0)
        setError(null)
    }, [])

    return {
        response,
        streamedText,
        isLoading,
        isStreaming,
        error,
        followUpCount,
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
