'use client'

import React, { createContext, useContext, useState, useCallback, useRef, ReactNode } from 'react'
import type {
    DeepResearchReport,
    ToolProgressEvent,
    NodeStatus,
    DeepResearchNode,
    CategoryOutput,
    ValidationOutput,
} from '@/types'

// Node descriptions that match the backend
const NODE_DESCRIPTIONS: Record<DeepResearchNode, string> = {
    groom: 'Analyzing your query...',
    financial_research: 'Researching financial data',
    industry_research: 'Researching industry intelligence',
    visual_research: 'Searching for relevant visuals',
    synthesize: 'Synthesizing findings into report',
    categorize: 'Generating sales intelligence',
    validate: 'Verifying citations and sources',
}

// All workflow nodes in order
const ALL_NODES: DeepResearchNode[] = [
    'groom',
    'financial_research',
    'industry_research',
    'visual_research',
    'synthesize',
    'categorize',
    'validate',
]

// ----------------------------------------------------------------------------
// Types
// ----------------------------------------------------------------------------

export interface DeepResearchState {
    isResearching: boolean
    status: string
    clarification: any | null
    report: DeepResearchReport | null
    categoryOutput: CategoryOutput | null
    validationOutput: ValidationOutput | null
    error: string | null
    // Progress tracking
    toolProgress: ToolProgressEvent[]
    nodeStatuses: NodeStatus[]
    activeNode: DeepResearchNode | null
    isCacheHit: boolean
    queryHash: string | null
    warnings: any[]
    // Timeout handling
    isTimeout: boolean
    timeoutInfo: {
        elapsed_seconds?: number
        timeout_seconds?: number
        completed_nodes?: string[]
        active_nodes?: string[]
    } | null
}

export interface DeepResearchContextType extends DeepResearchState {
    startDeepResearch: (query: string, history?: any[]) => Promise<void>
    cancelResearch: () => void
    resetResearch: () => void
}

// ----------------------------------------------------------------------------
// Initial State
// ----------------------------------------------------------------------------

const initialState: DeepResearchState = {
    isResearching: false,
    status: '',
    clarification: null,
    report: null,
    categoryOutput: null,
    validationOutput: null,
    error: null,
    toolProgress: [],
    nodeStatuses: ALL_NODES.map(node => ({
        node,
        status: 'pending',
        description: NODE_DESCRIPTIONS[node],
    })),
    activeNode: null,
    isCacheHit: false,
    queryHash: null,
    warnings: [],
    isTimeout: false,
    timeoutInfo: null,
}

// ----------------------------------------------------------------------------
// Context
// ----------------------------------------------------------------------------

const DeepResearchContext = createContext<DeepResearchContextType | undefined>(undefined)

export function useDeepResearchContext() {
    const context = useContext(DeepResearchContext)
    if (!context) {
        throw new Error('useDeepResearchContext must be used within a DeepResearchProvider')
    }
    return context
}

// ----------------------------------------------------------------------------
// Provider
// ----------------------------------------------------------------------------

export function DeepResearchProvider({ children }: { children: ReactNode }) {
    const [state, setState] = useState<DeepResearchState>(initialState)
    const abortControllerRef = useRef<AbortController | null>(null)

    // Helper to handle SSE events (moved inside/internal usage)
    const handleSSEEvent = useCallback((
        data: { type: string; content: any }
    ) => {
        setState(prev => {
            const next = { ...prev } // Clone

            switch (data.type) {
                case 'status':
                    const statusText = typeof data.content === 'string'
                        ? data.content
                        : data.content?.message || ''
                    if (prev.isResearching && statusText.toLowerCase().includes('complete')) {
                        return prev
                    }
                    return { ...prev, status: statusText }

                case 'cache_hit':
                    return {
                        ...prev,
                        isCacheHit: true,
                        queryHash: data.content.query_hash,
                        status: data.content.message,
                    }

                case 'node_start':
                    const node = data.content.node as DeepResearchNode
                    return {
                        ...prev,
                        activeNode: node,
                        status: data.content.description,
                        nodeStatuses: prev.nodeStatuses.map(ns =>
                            ns.node === node
                                ? {
                                    ...ns,
                                    status: 'running',
                                    startTime: new Date(),
                                    parallel_with: data.content.parallel_with,
                                }
                                : ns
                        ),
                    }

                case 'node_complete':
                    const completedNode = data.content.node as DeepResearchNode
                    return {
                        ...prev,
                        nodeStatuses: prev.nodeStatuses.map(ns =>
                            ns.node === completedNode
                                ? { ...ns, status: 'completed', endTime: new Date() }
                                : ns
                        ),
                    }

                case 'tool_progress':
                    return {
                        ...prev,
                        toolProgress: [
                            ...prev.toolProgress.slice(-19),
                            {
                                tool: data.content.tool,
                                message: data.content.message,
                                ticker: data.content.ticker,
                                status: data.content.status || 'running',
                            },
                        ],
                    }

                case 'clarification':
                    return {
                        ...prev,
                        isResearching: false,
                        clarification: data.content,
                    }

                case 'report':
                    return {
                        ...prev,
                        isResearching: false,
                        report: data.content,
                        status: 'Research complete',
                        nodeStatuses: prev.nodeStatuses.map(ns => ({
                            ...ns,
                            status: 'completed',
                        })),
                    }

                case 'category':
                    return { ...prev, categoryOutput: data.content }

                case 'validation':
                    return { ...prev, validationOutput: data.content }

                case 'warnings':
                    return { ...prev, warnings: data.content }

                case 'timeout':
                    return {
                        ...prev,
                        isResearching: false,
                        isTimeout: true,
                        error: data.content?.message || 'Research timed out',
                        timeoutInfo: {
                            elapsed_seconds: data.content?.elapsed_seconds,
                            timeout_seconds: data.content?.timeout_seconds,
                            completed_nodes: data.content?.completed_nodes,
                            active_nodes: data.content?.active_nodes,
                        },
                        nodeStatuses: prev.nodeStatuses.map(ns =>
                            ns.status === 'running'
                                ? { ...ns, status: 'timeout' as any }
                                : ns
                        ),
                    }

                case 'timeout_info':
                    return prev

                case 'error':
                    const errorMessage = typeof data.content === 'string'
                        ? data.content
                        : data.content?.message || 'An error occurred'
                    return {
                        ...prev,
                        isResearching: false,
                        error: errorMessage,
                        nodeStatuses: prev.nodeStatuses.map(ns =>
                            ns.status === 'running'
                                ? { ...ns, status: 'error' }
                                : ns
                        ),
                    }

                default:
                    console.log('Unknown SSE event type:', data.type, data.content)
                    return prev
            }
        })
    }, [])

    const startDeepResearch = useCallback(async (query: string, history: any[] = []) => {
        // Cancel any existing request
        if (abortControllerRef.current) {
            abortControllerRef.current.abort()
        }
        abortControllerRef.current = new AbortController()

        setState({
            ...initialState,
            isResearching: true,
            status: 'Starting deep research workflow...',
        })

        try {
            const response = await fetch('/api/research/deep/run', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query, history }),
                signal: abortControllerRef.current.signal,
            })

            if (!response.ok) throw new Error('Failed to start research')

            const reader = response.body?.getReader()
            if (!reader) throw new Error('No reader')

            const decoder = new TextDecoder()
            let buffer = ''

            // IMPORTANT: We do NOT use recursion or external handlers that obscure state updates here.
            // We read the stream directly in this function loop.
            while (true) {
                const { done, value } = await reader.read()
                if (done) break

                buffer += decoder.decode(value, { stream: true })
                const lines = buffer.split('\n\n')
                buffer = lines.pop() || ''

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const dataStr = line.replace('data: ', '').trim()
                        if (dataStr === '[DONE]') break

                        try {
                            const data = JSON.parse(dataStr)
                            handleSSEEvent(data)
                        } catch (e) {
                            console.error('Error parsing stream data:', e)
                        }
                    }
                }
            }
        } catch (error: any) {
            if (error.name === 'AbortError') {
                console.log('Research request aborted')
                setState(prev => ({
                    ...prev,
                    isResearching: false,
                    status: 'Research was cancelled',
                }))
                return
            }
            setState(prev => ({ ...prev, isResearching: false, error: error.message }))
        } finally {
            setState(prev => {
                if (prev.isResearching && !prev.report) {
                    return {
                        ...prev,
                        isResearching: false,
                        status: prev.error ? prev.status : 'Research ended unexpectedly',
                    }
                }
                return prev
            })
        }
    }, [handleSSEEvent])

    const cancelResearch = useCallback(() => {
        if (abortControllerRef.current) {
            abortControllerRef.current.abort()
            setState(prev => ({
                ...prev,
                isResearching: false,
                status: 'Research cancelled',
            }))
        }
    }, [])

    const resetResearch = useCallback(() => {
        if (abortControllerRef.current) {
            abortControllerRef.current.abort()
        }
        setState(initialState)
    }, [])

    const value = {
        ...state,
        startDeepResearch,
        cancelResearch,
        resetResearch
    }

    return (
        <DeepResearchContext.Provider value={value}>
            {children}
        </DeepResearchContext.Provider>
    )
}
