'use client'

import { useState, useCallback, useRef } from 'react'
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
    synthesize: 'Synthesizing findings into report',
    categorize: 'Generating sales intelligence',
    validate: 'Verifying citations and sources',
}

// All workflow nodes in order
const ALL_NODES: DeepResearchNode[] = [
    'groom',
    'financial_research',
    'industry_research',
    'synthesize',
    'categorize',
    'validate',
]

interface DeepResearchState {
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

export function useDeepResearch() {
    const [state, setState] = useState<DeepResearchState>(initialState)
    const abortControllerRef = useRef<AbortController | null>(null)

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
                            handleSSEEvent(data, setState)
                        } catch (e) {
                            console.error('Error parsing stream data:', e)
                        }
                    }
                }
            }
        } catch (error: any) {
            if (error.name === 'AbortError') {
                console.log('Research request aborted')
                return
            }
            setState(prev => ({ ...prev, isResearching: false, error: error.message }))
        }
    }, [])

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

    return {
        ...state,
        startDeepResearch,
        cancelResearch,
        resetResearch,
    }
}

// Re-export state type for consumers
export type { DeepResearchState }

/**
 * Handle incoming SSE events from the deep research workflow
 */
function handleSSEEvent(
    data: { type: string; content: any },
    setState: React.Dispatch<React.SetStateAction<DeepResearchState>>
) {
    switch (data.type) {
        case 'status':
            // Can be string or object with message
            const statusText = typeof data.content === 'string' 
                ? data.content 
                : data.content?.message || ''
            setState(prev => ({ ...prev, status: statusText }))
            break

        case 'cache_hit':
            setState(prev => ({
                ...prev,
                isCacheHit: true,
                queryHash: data.content.query_hash,
                status: data.content.message,
            }))
            break

        case 'node_start':
            setState(prev => {
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
            })
            break

        case 'node_complete':
            setState(prev => {
                const node = data.content.node as DeepResearchNode
                return {
                    ...prev,
                    nodeStatuses: prev.nodeStatuses.map(ns =>
                        ns.node === node
                            ? { ...ns, status: 'completed', endTime: new Date() }
                            : ns
                    ),
                }
            })
            break

        case 'tool_progress':
            setState(prev => ({
                ...prev,
                toolProgress: [
                    ...prev.toolProgress.slice(-19), // Keep last 20 events
                    {
                        tool: data.content.tool,
                        message: data.content.message,
                        ticker: data.content.ticker,
                        status: data.content.status || 'running',
                    },
                ],
            }))
            break

        case 'clarification':
            setState(prev => ({
                ...prev,
                isResearching: false,
                clarification: data.content,
            }))
            break

        case 'report':
            setState(prev => ({
                ...prev,
                isResearching: false,
                report: data.content,
                status: 'Research complete',
                nodeStatuses: prev.nodeStatuses.map(ns => ({
                    ...ns,
                    status: 'completed',
                })),
            }))
            break

        case 'category':
            setState(prev => ({
                ...prev,
                categoryOutput: data.content,
            }))
            break

        case 'validation':
            setState(prev => ({
                ...prev,
                validationOutput: data.content,
            }))
            break

        case 'warnings':
            setState(prev => ({
                ...prev,
                warnings: data.content,
            }))
            break

        case 'timeout':
            setState(prev => ({
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
            }))
            break

        case 'timeout_info':
            // Initial timeout configuration info (informational)
            setState(prev => ({
                ...prev,
                status: prev.status, // Keep current status
            }))
            break

        case 'error':
            const errorMessage = typeof data.content === 'string'
                ? data.content
                : data.content?.message || 'An error occurred'
            setState(prev => ({
                ...prev,
                isResearching: false,
                error: errorMessage,
                nodeStatuses: prev.nodeStatuses.map(ns =>
                    ns.status === 'running'
                        ? { ...ns, status: 'error' }
                        : ns
                ),
            }))
            break

        default:
            console.log('Unknown SSE event type:', data.type, data.content)
    }
}
