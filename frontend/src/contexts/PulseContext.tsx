'use client'

import React, { createContext, useContext, useState, useCallback, ReactNode } from 'react'
import { api, TimeoutError } from '@/lib/api' // Assuming api is available here, might need import adjustment
import type {
    AdHocBriefing,
    AdHocBriefingContext,
} from '@/types/briefing'

// ----------------------------------------------------------------------------
// Types
// ----------------------------------------------------------------------------

interface ProgressStep {
    step: string
    label: string
    message: string
    status: 'running' | 'complete'
    count?: number
}

export interface PulseState {
    briefings: AdHocBriefing[]
    currentBriefing: AdHocBriefing | null
    response: AdHocBriefing | null // Backward compat
    streamedText: string
    isLoading: boolean
    isStreaming: boolean
    error: Error | null
    isTimeout: boolean
    followUpCount: number
    sessionId: string | null
    turnsRemaining: number
    progressSteps: ProgressStep[]
}

export interface PulseContextType extends PulseState {
    askQuestion: (question: string, context?: AdHocBriefingContext, isFollowUp?: boolean) => Promise<AdHocBriefing>
    streamQuestion: (question: string, context?: AdHocBriefingContext, isFollowUp?: boolean) => Promise<string>
    reset: () => void
}

// ----------------------------------------------------------------------------
// Context
// ----------------------------------------------------------------------------

const PulseContext = createContext<PulseContextType | undefined>(undefined)

export function usePulseContext() {
    const context = useContext(PulseContext)
    if (!context) {
        throw new Error('usePulseContext must be used within a PulseProvider')
    }
    return context
}

// ----------------------------------------------------------------------------
// Provider
// ----------------------------------------------------------------------------

export function PulseProvider({ children }: { children: ReactNode }) {
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

            // IMPORTANT: Direct reading loop
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
                                        const updated = [...steps]
                                        updated[existing] = newStep
                                        return updated
                                    } else {
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

    const value = {
        briefings,
        currentBriefing,
        response: currentBriefing, // Backward compat
        streamedText,
        isLoading,
        isStreaming,
        error,
        isTimeout,
        followUpCount,
        sessionId,
        turnsRemaining,
        progressSteps,
        askQuestion,
        streamQuestion,
        reset,
    }

    return (
        <PulseContext.Provider value={value}>
            {children}
        </PulseContext.Provider>
    )
}
