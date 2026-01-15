# Deep Research Recreation Guide

**Purpose**: Complete implementation guide for recreating the Deep Research feature with real-time SSE streaming and visual progress display.

**This Guide Contains Everything Needed To**:
1. Build the backend LangGraph workflow with parallel execution
2. Implement SSE streaming with granular progress events
3. Create the visual progress pipeline display (the impressive part!)
4. Build the research report display components
5. Handle errors, timeouts, and edge cases

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [TypeScript Types (Frontend)](#typescript-types-frontend)
3. [React Hook: useDeepResearch](#react-hook-usedeepresearch)
4. [Visual Components](#visual-components)
   - [ResearchProgress](#researchprogress-component)
   - [ResearchReport](#researchreport-component)
   - [ResearchDashboard](#researchdashboard-component)
   - [Supporting Components](#supporting-components)
5. [Backend State Management](#backend-state-management)
6. [Backend SSE API Route](#backend-sse-api-route)
7. [Styling Utilities](#styling-utilities)
8. [Key Implementation Details](#key-implementation-details)
9. [Production Checklist](#production-checklist)

---

## Architecture Overview

### High-Level Flow

```
User Query → [Groomer] → [Financial + Industry + Visual (parallel)] → [Synthesizer] → Final Report
                                         ↓
                                  SSE Events stream
                                         ↓
                               Frontend Progress Display
```

### SSE Event Types

The frontend receives these event types via Server-Sent Events:

| Event Type | Purpose | Example Content |
|------------|---------|-----------------|
| `status` | High-level workflow progress | `"Starting deep research workflow..."` |
| `cache_hit` | Report served from cache | `{query_hash, source, message}` |
| `node_start` | Node beginning execution | `{node: "financial_research", description: "..."}` |
| `node_complete` | Node finished | `{node: "financial_research"}` |
| `tool_progress` | Granular tool execution | `{tool: "query_corpus", message: "Searching..."}` |
| `clarification` | Query needs clarification | `{question, options}` |
| `report` | Final report payload | Full report object |
| `category` | Sales intelligence output | Territory insights, product recommendations |
| `validation` | Citation validation results | `{validation_passed, issues}` |
| `timeout` | Research timed out | `{message, elapsed_seconds, completed_nodes}` |
| `error` | Error details | `{message}` |

---

## TypeScript Types (Frontend)

Create these types in your frontend (e.g., `types/index.ts`):

```typescript
// =============================================================================
// Deep Research Types (SSE Events)
// =============================================================================

/** Tool progress event from agent execution */
export interface ToolProgressEvent {
  tool: string
  message: string
  ticker?: string | null
  status?: 'running' | 'completed' | 'error'
}

/** Node lifecycle events */
export interface NodeProgressEvent {
  node: string
  description: string
  parallel_with?: string | null
  duration_hint?: string
}

/** Cache hit event */
export interface CacheHitEvent {
  query_hash: string
  message: string
  source?: 'memory' | 'bigquery'
}

/** Workflow node types - add/remove based on your agents */
export type DeepResearchNode =
  | 'groom'
  | 'financial_research'
  | 'industry_research'
  | 'visual_research'
  | 'synthesize'
  | 'categorize'
  | 'validate'

/** Node status for UI display */
export interface NodeStatus {
  node: DeepResearchNode
  status: 'pending' | 'running' | 'completed' | 'error'
  description: string
  startTime?: Date
  endTime?: Date
  parallel_with?: string | null
}

/** Category/sales intelligence output */
export interface CategoryOutput {
  territory_insights?: {
    east_relevance: number
    west_relevance: number
    east_summary?: string
    west_summary?: string
  }
  product_recommendations?: Array<{
    product_name: string
    relevance_score: number
    rationale: string
  }>
  sales_plays?: Array<{
    title: string
    hook: string
    objection_handlers?: string[]
  }>
  industry_talking_points?: string[]
}

/** Validation output */
export interface ValidationOutput {
  validation_passed: boolean
  citation_issues?: Array<{
    claim: string
    issue: string
  }>
  unsubstantiated_claims?: string[]
  confidence_adjustments?: Array<{
    section: string
    adjustment: string
  }>
  warnings?: string[]
}

/** Deep Research report structure */
export interface DeepResearchReport {
  report_id: string
  generated_at: string
  query: string
  data_completeness?: number
  overall_confidence?: string
  executive_summary: {
    headline: string
    key_points: string[]
    key_metrics: Array<{ label: string; value: string; context?: string }>
  }
  sections: Array<{
    section_title: string
    content: string
    citations: Array<{
      source_type?: string
      source_title: string
      source_url?: string | null
      source_date?: string | null
    }>
    tables?: Array<{
      title: string
      columns: string[]
      rows: Record<string, any>[]
      source?: string
      notes?: string
    }>
  }>
  field_sales?: {
    offensive_angles: Array<{
      angle: string
      target_segment?: string
    }>
    defensive_angles: Array<{
      risk: string
      mitigation?: string
    }>
    questions_to_explore: string[]
  }
  companies_with_logos?: Array<{
    name: string
    domain?: string
    logo_url?: string
  }>
}
```

---

## React Hook: useDeepResearch

This hook manages all state for the deep research workflow and handles SSE streaming:

```typescript
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

/**
 * Handle incoming SSE events from the deep research workflow
 */
function handleSSEEvent(
    data: { type: string; content: any },
    setState: React.Dispatch<React.SetStateAction<DeepResearchState>>
) {
    switch (data.type) {
        case 'status':
            const statusText = typeof data.content === 'string' 
                ? data.content 
                : data.content?.message || ''
            setState(prev => {
                if (prev.isResearching && statusText.toLowerCase().includes('complete')) {
                    return prev
                }
                return { ...prev, status: statusText }
            })
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
                        ? { ...ns, status: 'error' as const }
                        : ns
                ),
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

export type { DeepResearchState }
```

---

## Visual Components

### Styling Utility

First, add the `cn` utility for Tailwind class merging:

```typescript
// lib/utils.ts
import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
```

Install dependencies:
```bash
npm install clsx tailwind-merge lucide-react react-markdown
```

---

### ResearchProgress Component

This is the **impressive visual pipeline display** showing node progress:

```tsx
'use client'

import { useMemo } from 'react'
import {
    Search,
    DollarSign,
    Factory,
    FileText,
    ShoppingCart,
    Shield,
    CheckCircle,
    Loader2,
    Circle,
    AlertCircle,
    Zap,
    Image,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import type { NodeStatus, ToolProgressEvent, DeepResearchNode } from '@/types'

// Icons for each node
const NODE_ICONS: Record<DeepResearchNode, React.ElementType> = {
    groom: Search,
    financial_research: DollarSign,
    industry_research: Factory,
    visual_research: Image,
    synthesize: FileText,
    categorize: ShoppingCart,
    validate: Shield,
}

// Friendly labels
const NODE_LABELS: Record<DeepResearchNode, string> = {
    groom: 'Query Analysis',
    financial_research: 'Financial Research',
    industry_research: 'Industry Research',
    visual_research: 'Visual Research',
    synthesize: 'Report Synthesis',
    categorize: 'Sales Intelligence',
    validate: 'Quality Check',
}

interface ResearchProgressProps {
    nodeStatuses: NodeStatus[]
    toolProgress: ToolProgressEvent[]
    activeNode: DeepResearchNode | null
    isCacheHit: boolean
}

export function ResearchProgress({
    nodeStatuses,
    toolProgress,
    activeNode,
    isCacheHit,
}: ResearchProgressProps) {
    // Get the most recent tool progress for display
    const recentTools = useMemo(() => {
        return toolProgress.slice(-5).reverse()
    }, [toolProgress])

    // Check if financial and industry are running in parallel
    const parallelNodes = useMemo(() => {
        const financial = nodeStatuses.find(n => n.node === 'financial_research')
        const industry = nodeStatuses.find(n => n.node === 'industry_research')
        return financial?.status === 'running' && industry?.status === 'running'
    }, [nodeStatuses])

    return (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
            {/* Header */}
            <div className="px-4 py-3 bg-gradient-to-r from-emerald-50 to-blue-50 border-b border-slate-200">
                <div className="flex items-center gap-2">
                    <Zap size={16} className="text-emerald-600" />
                    <span className="font-medium text-slate-800">
                        {isCacheHit ? 'Loading Cached Report' : 'Deep Research in Progress'}
                    </span>
                    {parallelNodes && (
                        <span className="ml-auto text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full">
                            ⚡ Parallel execution
                        </span>
                    )}
                </div>
            </div>

            {/* Pipeline Visualization */}
            <div className="px-4 py-4">
                {/* Node labels above icons */}
                <div className="hidden sm:flex items-end justify-between mb-2 px-1">
                    {nodeStatuses.map(node => {
                        const label = NODE_LABELS[node.node]
                        const words = label.split(' ')

                        return (
                            <div key={`label-${node.node}`} className="flex-1 text-center">
                                <div className={cn(
                                    'text-xs leading-tight',
                                    node.status === 'running' && 'text-emerald-600 font-medium',
                                    node.status === 'completed' && 'text-slate-500',
                                    node.status === 'pending' && 'text-slate-400',
                                    node.status === 'error' && 'text-red-500',
                                )}>
                                    {words.map((word, idx) => (
                                        <div key={idx}>{word}</div>
                                    ))}
                                </div>
                            </div>
                        )
                    })}
                </div>

                {/* Icon row */}
                <div className="flex items-center justify-between gap-1">
                    {nodeStatuses.map((node, idx) => {
                        const Icon = NODE_ICONS[node.node]
                        const isActive = node.status === 'running'
                        const isComplete = node.status === 'completed'
                        const isError = node.status === 'error'
                        const isPending = node.status === 'pending'

                        const showParallelBracket =
                            (node.node === 'financial_research' || node.node === 'industry_research') &&
                            parallelNodes

                        return (
                            <div key={node.node} className="flex items-center">
                                {/* Connector line */}
                                {idx > 0 && node.node !== 'industry_research' && (
                                    <div
                                        className={cn(
                                            'w-4 h-0.5 mx-0.5',
                                            isComplete || isActive
                                                ? 'bg-emerald-400'
                                                : 'bg-slate-200'
                                        )}
                                    />
                                )}

                                {/* Node */}
                                <div
                                    className={cn(
                                        'relative group',
                                        showParallelBracket && 'flex flex-col items-center'
                                    )}
                                >
                                    {/* Parallel bracket indicator */}
                                    {showParallelBracket && node.node === 'financial_research' && (
                                        <div className="absolute -top-3 left-1/2 transform -translate-x-1/2 w-24 h-2 border-t border-l border-r border-blue-300 rounded-t-lg" />
                                    )}

                                    {/* Node circle */}
                                    <div
                                        className={cn(
                                            'w-10 h-10 rounded-full flex items-center justify-center transition-all duration-300',
                                            isComplete && 'bg-emerald-500 text-white',
                                            isActive && 'bg-emerald-100 text-emerald-600 ring-2 ring-emerald-400 ring-offset-2',
                                            isError && 'bg-red-500 text-white',
                                            isPending && 'bg-slate-100 text-slate-400'
                                        )}
                                    >
                                        {isActive ? (
                                            <Loader2 size={18} className="animate-spin" />
                                        ) : isComplete ? (
                                            <CheckCircle size={18} />
                                        ) : isError ? (
                                            <AlertCircle size={18} />
                                        ) : (
                                            <Icon size={18} />
                                        )}
                                    </div>

                                    {/* Tooltip for mobile */}
                                    <div className="sm:hidden absolute -bottom-8 left-1/2 transform -translate-x-1/2 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                                        <div className="bg-slate-900 text-white text-xs px-2 py-1 rounded whitespace-nowrap">
                                            {NODE_LABELS[node.node]}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        )
                    })}
                </div>
            </div>

            {/* Tool Activity Feed */}
            {recentTools.length > 0 && (
                <div className="border-t border-slate-100 px-4 py-3 bg-slate-50">
                    <div className="flex items-center gap-2 mb-2">
                        <Circle size={8} className="text-emerald-500 fill-emerald-500 animate-pulse" />
                        <span className="text-xs font-medium text-slate-600">Live Activity</span>
                    </div>
                    <div className="space-y-1.5 max-h-32 overflow-y-auto">
                        {recentTools.map((tool, idx) => (
                            <ToolProgressItem key={idx} tool={tool} isLatest={idx === 0} />
                        ))}
                    </div>
                </div>
            )}
        </div>
    )
}

interface ToolProgressItemProps {
    tool: ToolProgressEvent
    isLatest: boolean
}

function ToolProgressItem({ tool, isLatest }: ToolProgressItemProps) {
    const toolLabel = formatToolName(tool.tool)

    return (
        <div
            className={cn(
                'flex items-center gap-2 text-xs transition-opacity duration-300',
                isLatest ? 'opacity-100' : 'opacity-60'
            )}
        >
            <span
                className={cn(
                    'shrink-0 w-2 h-2 rounded-full',
                    tool.status === 'error' ? 'bg-red-400' :
                        tool.status === 'completed' ? 'bg-emerald-400' :
                            'bg-blue-400 animate-pulse'
                )}
            />
            <span className="font-medium text-slate-700">{toolLabel}</span>
            {tool.ticker && (
                <span className="text-slate-400 shrink-0">({tool.ticker})</span>
            )}
            <span className="text-slate-500 truncate">{tool.message}</span>
        </div>
    )
}

/**
 * Convert snake_case tool names to human-friendly labels
 */
function formatToolName(name: string): string {
    const toolLabels: Record<string, string> = {
        'get_earnings_transcript': 'Earnings Transcript',
        'query_corpus': 'Corpus Search',
        'get_company_news': 'Company News',
        'get_press_releases': 'Press Releases',
        'sec_filings': 'SEC Filings',
        'news_search': 'News Search',
        'web_search': 'Web Search',
    }
    return toolLabels[name] || name.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
}

export default ResearchProgress
```

---

### ResearchReport Component

Displays the final research report with sections, citations, and field sales implications:

```tsx
'use client'

import { useState } from 'react'
import {
    FileText,
    Target,
    HelpCircle,
    ChevronRight,
    ShieldCheck,
    TrendingUp,
    LayoutDashboard,
    Bookmark,
    CheckCircle,
    Loader2,
    ExternalLink,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import ReactMarkdown from 'react-markdown'

interface DeepResearchReportProps {
    report: any
}

const extractDomain = (url: string): string => {
    try {
        if (!url) return 'Unknown'
        const parsed = new URL(url)
        return parsed.hostname.replace('www.', '')
    } catch {
        return 'Unknown'
    }
}

interface Citation {
    source_type?: string
    source_title: string
    source_url?: string | null
    source_date?: string | null
}

function CitationList({ citations }: { citations: Citation[] }) {
    if (!citations || citations.length === 0) return null

    const linkedCitations = citations.filter(c => c.source_url)
    if (linkedCitations.length === 0) return null

    return (
        <div className="mt-4 pt-4 border-t border-slate-100">
            <p className="text-xs font-medium text-slate-500 mb-2 flex items-center gap-1">
                <ExternalLink size={12} />
                Sources
            </p>
            <div className="flex flex-wrap gap-2">
                {linkedCitations.map((citation, idx) => {
                    const domain = citation.source_url ? extractDomain(citation.source_url) : 'Unknown'
                    return (
                        <a
                            key={idx}
                            href={citation.source_url || '#'}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded-lg text-xs text-slate-600 hover:text-slate-900 transition-colors group"
                            title={citation.source_title}
                        >
                            <span className="font-medium">{domain}</span>
                            <ExternalLink size={10} className="opacity-50 group-hover:opacity-100" />
                        </a>
                    )
                })}
            </div>
        </div>
    )
}

export default function ResearchReport({ report }: DeepResearchReportProps) {
    const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')

    if (!report) return null

    const { executive_summary, sections, field_sales, companies_with_logos } = report

    return (
        <div className="space-y-6 pb-12">
            {/* Executive Summary */}
            <section className="bg-white rounded-2xl border border-slate-200 overflow-hidden shadow-sm">
                <div className="bg-slate-900 px-6 py-4 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <LayoutDashboard size={20} className="text-emerald-400" />
                        <h2 className="text-white font-semibold">Executive Summary</h2>
                    </div>
                    <button
                        onClick={() => setSaveStatus('saved')} // Replace with actual save logic
                        disabled={saveStatus === 'saving' || saveStatus === 'saved'}
                        className={cn(
                            "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors",
                            saveStatus === 'saved'
                                ? "bg-emerald-600 text-white cursor-default"
                                : "bg-slate-700 hover:bg-slate-600 text-slate-200"
                        )}
                    >
                        {saveStatus === 'saving' ? (
                            <><Loader2 size={14} className="animate-spin" /> Saving...</>
                        ) : saveStatus === 'saved' ? (
                            <><CheckCircle size={14} /> Saved</>
                        ) : (
                            <><Bookmark size={14} /> Save to Memory</>
                        )}
                    </button>
                </div>
                <div className="p-6">
                    <h1 className="text-2xl font-bold text-slate-900 mb-4">{executive_summary.headline}</h1>
                    
                    {/* Key Metrics */}
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                        {executive_summary.key_metrics?.map((metric: any, idx: number) => (
                            <div key={idx} className="bg-slate-50 rounded-xl p-4 border border-slate-100 text-center">
                                <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">{metric.label}</p>
                                <p className="text-xl font-bold text-slate-900">{metric.value}</p>
                            </div>
                        ))}
                    </div>
                    
                    {/* Key Points */}
                    <div className="space-y-2">
                        {executive_summary.key_points?.map((point: string, idx: number) => (
                            <div key={idx} className="flex gap-3">
                                <div className="mt-1.5 w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0" />
                                <p className="text-slate-700">{point}</p>
                            </div>
                        ))}
                    </div>
                    
                    {/* Company Logos */}
                    {companies_with_logos && companies_with_logos.length > 0 && (
                        <div className="mt-6 pt-4 border-t border-slate-100">
                            <p className="text-xs font-medium text-slate-500 mb-3">Companies Mentioned</p>
                            <div className="flex flex-wrap gap-2">
                                {companies_with_logos.map((company: any, idx: number) => (
                                    <div
                                        key={idx}
                                        className="inline-flex items-center gap-2 px-3 py-1.5 bg-slate-50 border border-slate-200 rounded-lg"
                                    >
                                        <div className="w-6 h-6 rounded bg-slate-200 flex items-center justify-center text-[9px] font-bold text-slate-500">
                                            {company.name.slice(0, 2).toUpperCase()}
                                        </div>
                                        <span className="text-sm font-medium text-slate-700">{company.name}</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            </section>

            {/* Main Sections */}
            {sections?.map((section: any, idx: number) => (
                <section key={idx} className="bg-white rounded-2xl border border-slate-200 overflow-hidden shadow-sm">
                    <div className="bg-slate-50 px-6 py-3 border-b border-slate-200 flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            <FileText size={18} className="text-slate-600" />
                            <h3 className="font-semibold text-slate-800">{section.section_title}</h3>
                        </div>
                        <span className="text-xs text-slate-400">Section {idx + 1}</span>
                    </div>
                    <div className="p-6">
                        <div className="prose prose-slate max-w-none mb-6">
                            <ReactMarkdown>{section.content}</ReactMarkdown>
                        </div>

                        {/* Tables */}
                        {section.tables && section.tables.length > 0 && (
                            <div className="space-y-8 mt-6 border-t border-slate-100 pt-6">
                                {section.tables.map((table: any, tIdx: number) => (
                                    <div key={tIdx} className="overflow-hidden rounded-xl border border-slate-200">
                                        <div className="bg-slate-50 px-4 py-2 border-b border-slate-200">
                                            <h4 className="text-sm font-bold text-slate-700">{table.title}</h4>
                                        </div>
                                        <div className="overflow-x-auto">
                                            <table className="w-full text-sm text-left">
                                                <thead className="bg-slate-50/50 text-slate-500 font-medium border-b border-slate-200">
                                                    <tr>
                                                        {table.columns.map((col: string, cIdx: number) => (
                                                            <th key={cIdx} className="px-4 py-2 whitespace-nowrap">{col}</th>
                                                        ))}
                                                    </tr>
                                                </thead>
                                                <tbody className="divide-y divide-slate-100">
                                                    {table.rows.map((row: any, rIdx: number) => (
                                                        <tr key={rIdx} className="hover:bg-slate-50/50 transition-colors">
                                                            {table.columns.map((col: string, cIdx: number) => (
                                                                <td key={cIdx} className={cn(
                                                                    "px-4 py-2 text-slate-700",
                                                                    /^[0-9$%.,-]+%?$/.test(String(row[col])) && "text-right font-mono"
                                                                )}>
                                                                    {row[col]}
                                                                </td>
                                                            ))}
                                                        </tr>
                                                    ))}
                                                </tbody>
                                            </table>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                        
                        <CitationList citations={section.citations} />
                    </div>
                </section>
            ))}

            {/* Field Sales Implications */}
            {field_sales && (
                <section className="bg-emerald-50 rounded-2xl border border-emerald-100 overflow-hidden shadow-sm">
                    <div className="bg-emerald-600 px-6 py-4 flex items-center gap-2">
                        <Target size={20} className="text-white" />
                        <h2 className="text-white font-semibold">Field Sales Implications</h2>
                    </div>
                    <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-8">
                        <div>
                            <h4 className="flex items-center gap-2 text-emerald-800 font-bold mb-4">
                                <TrendingUp size={18} />
                                Offensive Angles
                            </h4>
                            <div className="space-y-4">
                                {field_sales.offensive_angles?.map((angle: any, idx: number) => (
                                    <div key={idx} className="bg-white rounded-xl p-4 border border-emerald-100">
                                        <p className="font-semibold text-slate-900 text-sm mb-1">{angle.angle}</p>
                                        <p className="text-xs text-slate-600 italic">Target: {angle.target_segment}</p>
                                    </div>
                                ))}
                            </div>
                        </div>
                        <div>
                            <h4 className="flex items-center gap-2 text-emerald-800 font-bold mb-4">
                                <ShieldCheck size={18} />
                                Defensive Watch-outs
                            </h4>
                            <div className="space-y-4">
                                {field_sales.defensive_angles?.map((angle: any, idx: number) => (
                                    <div key={idx} className="bg-white rounded-xl p-4 border border-emerald-100">
                                        <p className="font-semibold text-slate-900 text-sm mb-1">{angle.risk}</p>
                                        <p className="text-xs text-slate-600 italic">Mitigation: {angle.mitigation}</p>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                    <div className="bg-emerald-100/50 p-6 border-t border-emerald-100">
                        <h4 className="flex items-center gap-2 text-emerald-800 font-bold mb-4">
                            <HelpCircle size={18} />
                            Questions to Explore
                        </h4>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                            {field_sales.questions_to_explore?.map((q: string, idx: number) => (
                                <div key={idx} className="flex gap-2">
                                    <ChevronRight size={14} className="mt-1 text-emerald-500 shrink-0" />
                                    <p className="text-slate-700 text-sm">{q}</p>
                                </div>
                            ))}
                        </div>
                    </div>
                </section>
            )}
        </div>
    )
}
```

---

### ResearchDashboard Component

Main container that ties everything together (simplified version - see actual component for full implementation):

```tsx
'use client'

import { useState, useRef, useEffect } from 'react'
import {
  Send,
  Sparkles,
  MessageSquare,
  Loader2,
  Trash2,
  XCircle,
  RefreshCw,
  Search,
  ChevronRight,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import ResearchReport from './ResearchReport'
import ResearchProgress from './ResearchProgress'
import type { NodeStatus, ToolProgressEvent, DeepResearchNode, CategoryOutput, ValidationOutput } from '@/types'

interface ResearchDashboardProps {
  // Actions
  onStartResearch: (prompt: string) => void
  onCancelResearch?: () => void

  // Deep research state
  isResearching?: boolean
  researchStatus?: string
  deepResearchReport?: any | null
  researchError?: string | null

  // Progress tracking
  nodeStatuses?: NodeStatus[]
  toolProgress?: ToolProgressEvent[]
  activeNode?: DeepResearchNode | null
  isCacheHit?: boolean

  // Timeout handling
  isTimeout?: boolean
  timeoutInfo?: {
    elapsed_seconds?: number
    completed_nodes?: string[]
  } | null
}

export default function ResearchDashboard({
  onStartResearch,
  onCancelResearch,
  isResearching,
  researchStatus,
  deepResearchReport,
  nodeStatuses,
  toolProgress,
  activeNode,
  isCacheHit,
  researchError,
  isTimeout,
  timeoutInfo,
}: ResearchDashboardProps) {
  const [inputValue, setInputValue] = useState('')
  const [conversationHistory, setConversationHistory] = useState<{role: 'user' | 'assistant', content: string, timestamp: Date}[]>([])
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [conversationHistory])

  const handleSend = async () => {
    if (!inputValue.trim() || isResearching) return
    const message = inputValue.trim()
    setInputValue('')
    setConversationHistory(prev => [...prev, { role: 'user', content: message, timestamp: new Date() }])
    onStartResearch(message)
  }

  const hasConversation = conversationHistory.length > 0
  const hasReport = deepResearchReport !== null

  return (
    <div className="h-full flex bg-slate-50">
      {/* Left Panel - Chat Interface */}
      <div className="w-[400px] shrink-0 flex flex-col border-r border-slate-200 bg-white">
        {/* Header */}
        <div className="shrink-0 px-6 py-4 border-b border-slate-200 bg-gradient-to-r from-emerald-50 to-white">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-emerald-100 flex items-center justify-center">
              <Sparkles className="w-5 h-5 text-emerald-600" />
            </div>
            <div>
              <h1 className="text-lg font-semibold text-slate-800">Research Agent</h1>
              <p className="text-xs text-slate-500">Deep market intelligence</p>
            </div>
          </div>
        </div>

        {/* Chat Area & Input - abbreviated for guide */}
        <div className="flex-1 overflow-auto p-6">
          {/* Conversation messages or empty state */}
        </div>

        {/* Input */}
        <div className="shrink-0 p-4 border-t border-slate-200">
          <div className="flex gap-2">
            <input
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSend()}
              placeholder="Ask about markets, companies, or trends..."
              className="flex-1 px-4 py-3 rounded-xl border border-slate-200 focus:border-emerald-500 outline-none"
              disabled={isResearching}
            />
            <button onClick={handleSend} disabled={!inputValue.trim() || isResearching}
              className="px-4 py-3 bg-emerald-600 text-white rounded-xl">
              <Send className="w-5 h-5" />
            </button>
          </div>
        </div>
      </div>

      {/* Right Panel - Results */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <div className="flex-1 overflow-auto p-6">
          <div className="max-w-4xl mx-auto">
            {/* Research Progress */}
            {isResearching && nodeStatuses && toolProgress && (
              <ResearchProgress
                nodeStatuses={nodeStatuses}
                toolProgress={toolProgress}
                activeNode={activeNode || null}
                isCacheHit={isCacheHit || false}
              />
            )}

            {/* Research Report */}
            {deepResearchReport && <ResearchReport report={deepResearchReport} />}
          </div>
        </div>
      </div>
    </div>
  )
}
```

---

### Supporting Components

#### TerritoryInsights

```tsx
'use client'

import { MapPin } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { CategoryOutput } from '@/types'

export function TerritoryInsights({ categoryOutput }: { categoryOutput: CategoryOutput }) {
    const { territory_insights } = categoryOutput
    if (!territory_insights) return null

    const eastScore = territory_insights.east_relevance || 0
    const westScore = territory_insights.west_relevance || 0
    const maxScore = Math.max(eastScore, westScore)

    return (
        <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden shadow-sm">
            <div className="bg-gradient-to-r from-blue-500 to-cyan-500 px-6 py-4 flex items-center gap-2">
                <MapPin size={20} className="text-white" />
                <h3 className="text-white font-semibold">Territory Insights</h3>
            </div>
            
            <div className="p-6 grid grid-cols-2 gap-4">
                {/* East Territory */}
                <div className={cn(
                    "relative rounded-xl border-2 p-4",
                    eastScore === maxScore ? "border-blue-500 bg-blue-50" : "border-slate-200 bg-slate-50"
                )}>
                    {eastScore === maxScore && (
                        <div className="absolute -top-2 -right-2 bg-blue-500 text-white text-xs font-bold px-2 py-0.5 rounded-full">
                            Top Match
                        </div>
                    )}
                    <span className="font-semibold">East Territory</span>
                    <span className="text-3xl font-bold text-blue-600">{Math.round(eastScore * 100)}%</span>
                    <div className="h-2 bg-slate-200 rounded-full overflow-hidden">
                        <div className="h-full bg-blue-500" style={{ width: `${eastScore * 100}%` }} />
                    </div>
                </div>

                {/* West Territory - similar structure */}
            </div>
        </div>
    )
}
```

#### ValidationBadge

```tsx
'use client'

import { useState } from 'react'
import { ShieldCheck, ShieldAlert, ChevronDown, ChevronUp, AlertCircle } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { ValidationOutput } from '@/types'

export function ValidationBadge({ validationOutput }: { validationOutput: ValidationOutput }) {
    const [isExpanded, setIsExpanded] = useState(false)
    const { validation_passed, citation_issues = [], unsubstantiated_claims = [] } = validationOutput
    const totalIssues = citation_issues.length + unsubstantiated_claims.length

    return (
        <div className="rounded-2xl border-2 overflow-hidden border-emerald-300 bg-emerald-50/50">
            <button
                onClick={() => setIsExpanded(!isExpanded)}
                className="w-full px-6 py-4 flex items-center justify-between bg-emerald-500 hover:bg-emerald-600"
            >
                <div className="flex items-center gap-3">
                    {validation_passed ? <ShieldCheck size={24} className="text-white" /> : <ShieldAlert size={24} className="text-white" />}
                    <h3 className="text-white font-semibold">
                        {validation_passed ? 'Validation Passed' : 'Validation Issues'}
                    </h3>
                </div>
                {isExpanded ? <ChevronUp className="text-white" /> : <ChevronDown className="text-white" />}
            </button>

            {isExpanded && totalIssues > 0 && (
                <div className="p-6 space-y-4">
                    {/* Issue lists */}
                </div>
            )}
        </div>
    )
}
```

---

## Backend State Management

### State Schema with Reducers

```python
"""
State management for Deep Research workflow.

File: app/agents/research/state.py

CRITICAL: Every field MUST have a reducer annotation for parallel execution!
"""

from typing import Annotated, TypedDict, List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum

# =============================================================================
# REDUCER FUNCTIONS
# =============================================================================

def _keep_first(a, b):
    """Keep original value (immutable fields)."""
    if a is not None and a != "":
        return a
    return b

def _keep_last(a, b):
    """Keep latest value (mutable outputs)."""
    return b if b is not None else a

def _merge_errors(a, b):
    """Combine error lists from parallel branches."""
    return (a or []) + (b or [])

# =============================================================================
# STATE SCHEMA
# =============================================================================

class DeepResearchState(TypedDict):
    # Immutable inputs
    user_query: Annotated[str, _keep_first]
    conversation_history: Annotated[List[Any], _keep_first]
    
    # Groomer output
    research_brief: Annotated[Optional[Any], _keep_first]
    clarification_count: Annotated[int, _keep_first]
    
    # Agent outputs (each agent updates its own)
    financial_output: Annotated[Optional[Any], _keep_last]
    industry_output: Annotated[Optional[Any], _keep_last]
    visual_output: Annotated[Optional[Any], _keep_last]
    
    # Final output
    final_report: Annotated[Optional[Any], _keep_last]
    current_status: Annotated[str, _keep_last]
    
    # Error accumulation
    errors: Annotated[List[Dict[str, Any]], _merge_errors]
```

---

## Backend SSE API Route

```python
"""
SSE streaming endpoint for Deep Research.

File: app/api/routes/deep_research.py
"""

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any
import json
import asyncio

router = APIRouter()

NODE_DESCRIPTIONS = {
    "groom": "Analyzing your query...",
    "financial_research": "Researching financial data",
    "industry_research": "Researching industry intelligence",
    "visual_research": "Searching for relevant visuals",
    "synthesize": "Synthesizing findings into report",
}

class DeepResearchRequest(BaseModel):
    query: str
    history: List[Dict[str, Any]] = []


def _emit_event(event_type: str, content: Any) -> str:
    """Format an SSE event."""
    return f"data: {json.dumps({'type': event_type, 'content': content})}\n\n"


@router.post("/run")
async def run_deep_research(request: DeepResearchRequest):
    """
    Streams SSE events:
    - status, node_start, node_complete, tool_progress
    - clarification, report, category, validation
    - timeout, error
    """
    
    async def event_generator():
        try:
            yield _emit_event("status", "Starting deep research workflow...")
            
            # Your LangGraph workflow execution here
            # For each node event, emit node_start/node_complete
            # For each tool progress, emit tool_progress
            # At the end, emit report
            
            yield _emit_event("status", "Research complete.")
            yield "data: [DONE]\n\n"
            
        except Exception as e:
            yield _emit_event("error", {"message": str(e)})
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
```

---

## Key Implementation Details

### 1. SSE Event Stream Format

Events are sent as `data: {json}\n\n` with a special `[DONE]` marker:

```
data: {"type": "status", "content": "Starting deep research workflow..."}

data: {"type": "node_start", "content": {"node": "groom", "description": "Analyzing your query..."}}

data: {"type": "tool_progress", "content": {"tool": "query_corpus", "message": "Searching..."}}

data: {"type": "node_complete", "content": {"node": "groom"}}

data: {"type": "report", "content": {...full report...}}

data: [DONE]
```

### 2. Parallel Execution with LangGraph

```python
from langgraph.types import Send

def route_after_groom(state):
    """Fan out to parallel research branches."""
    brief = state.get("research_brief")
    
    if not brief or brief.status == "needs_clarification":
        return END
    
    # Fan out to 3 agents in parallel
    return [
        Send("financial_research", state),
        Send("industry_research", state),
        Send("visual_research", state),
    ]
```

### 3. Critical: asyncio.shield() for SSE Polling

```python
# WRONG - This cancels pending tasks!
event = await asyncio.wait_for(task, timeout=0.1)

# CORRECT - Shield protects from cancellation
event = await asyncio.wait_for(asyncio.shield(task), timeout=0.1)
```

### 4. Progress Emission from Agents

```python
from app.agents.research.progress import emit_progress_sync, ToolProgress

# In your agent code:
emit_progress_sync(ToolProgress(
    tool_name="query_corpus",
    message="Searching for market trends...",
    status="running"
))
```

---

## Production Checklist

### Frontend
- [ ] Types defined for all SSE events
- [ ] `useDeepResearch` hook handles all event types
- [ ] Progress display shows parallel execution
- [ ] Error and timeout states handled
- [ ] Cancel button works correctly

### Backend
- [ ] All LLM calls wrapped with `asyncio.wait_for(timeout=90)`
- [ ] State schema has reducers for ALL fields
- [ ] SSE endpoint uses `asyncio.shield()` for iterator
- [ ] Progress emission works from all agents
- [ ] Workflow timeout enforced (5 minutes)

### Styling
- [ ] Tailwind CSS configured with custom colors (emerald, slate)
- [ ] `cn()` utility installed (clsx + tailwind-merge)
- [ ] lucide-react icons imported
- [ ] Responsive design for mobile

---

## Quick Start

1. **Install dependencies**:
   ```bash
   # Frontend
   npm install clsx tailwind-merge lucide-react react-markdown
   
   # Backend
   pip install langgraph langchain-anthropic fastapi sse-starlette
   ```

2. **Copy the types and components to your project**

3. **Set up the API route to stream SSE events**

4. **Use the hook in your page**:
   ```tsx
   const { 
     isResearching, 
     status, 
     report, 
     nodeStatuses, 
     toolProgress,
     startDeepResearch 
   } = useDeepResearch()
   ```

5. **Render the dashboard**:
   ```tsx
   <ResearchDashboard
     onStartResearch={startDeepResearch}
     isResearching={isResearching}
     researchStatus={status}
     deepResearchReport={report}
     nodeStatuses={nodeStatuses}
     toolProgress={toolProgress}
   />
   ```

---

## Additional Reference

For more detailed backend implementation including:
- Agent implementation patterns
- LangGraph workflow setup with Send API
- Testing and debugging strategies
- Key learnings and gotchas

See the existing [deep_research_guide.md](deep_research_guide.md) in this repository.

---

**Original Implementation**: C1 Intelligence Hub  
**Performance**: ~90-120 seconds for comprehensive reports  
**Key Visual Feature**: Real-time pipeline with parallel execution indicator

Good luck building! 🚀
