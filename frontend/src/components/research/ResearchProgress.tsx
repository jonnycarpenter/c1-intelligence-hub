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
                        // Split multi-word labels into lines
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

                        // Show parallel indicator between financial and industry
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
    // Format tool name for display
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
        'get_earnings_transcript_ninja': 'Earnings Transcript',
        'query_corpus': 'Corpus Search',
        'get_company_news': 'Company News',
        'get_press_releases': 'Press Releases',
        'get_analyst_ratings': 'Analyst Ratings',
        'get_sentiment_summary': 'Sentiment Analysis',
        'sec_filings': 'SEC Filings',
        'news_search': 'News Search',
        'web_search': 'Web Search',
        'get_market_signals': 'Market Signals',
        'get_google_trends': 'Google Trends',
        'get_freight_rates': 'Freight Rates',
        'query_datasheets': 'Datasheet Lookup',
        'get_products_by_industry': 'Product Search',
    }
    return toolLabels[name] || name.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
}

export default ResearchProgress
