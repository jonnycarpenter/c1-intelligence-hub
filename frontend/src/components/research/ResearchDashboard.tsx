'use client'

import { useState, useCallback, useRef, useEffect } from 'react'
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
  Building2,
  TrendingUp,
  Scale,
  Archive,
  ArrowLeft,
} from 'lucide-react'
import { Button, MarkdownContent } from '@/components/ui'
import { cn } from '@/lib/utils'
import { api } from '@/lib/api'
import { useToast } from '@/components/ui'
import type {
  ResearchSection,
  RecentSearch,
  ReportItem,
  Category,
  NodeStatus,
  ToolProgressEvent,
  DeepResearchNode,
  ValidationOutput,
} from '@/types'
import ResearchReport from './ResearchReport'
import ClarificationPrompt from './ClarificationPrompt'
import ResearchProgress from './ResearchProgress'
import ValidationBadge from './ValidationBadge'
import SavedReportsPanel from './SavedReportsPanel'

// NOTE: TerritoryInsights, ProductRecommendations, and SalesPlays components removed
// Category agent (sales intelligence) has been removed from the workflow

interface ResearchDashboardProps {
  // From streaming/state
  sections: ResearchSection[]
  activeSectionId: string | null
  recentSearches: RecentSearch[]

  // Actions
  onSectionsUpdate: (sections: ResearchSection[]) => void
  onStartResearch: (prompt: string) => void
  onAddToReport: (item: ReportItem) => void
  onScrollToSection?: (sectionId: string) => void
  onCancelResearch?: () => void

  // Deep research props
  isResearching?: boolean
  researchStatus?: string
  clarification?: any | null
  deepResearchReport?: any | null

  // Progress tracking props
  nodeStatuses?: NodeStatus[]
  toolProgress?: ToolProgressEvent[]
  activeNode?: DeepResearchNode | null
  isCacheHit?: boolean
  validationOutput?: ValidationOutput | null
  researchError?: string | null

  // Timeout handling
  isTimeout?: boolean
  timeoutInfo?: {
    elapsed_seconds?: number
    timeout_seconds?: number
    completed_nodes?: string[]
    active_nodes?: string[]
  } | null
}

// Conversation message for chat display
interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
}

export default function ResearchDashboard({
  sections,
  activeSectionId,
  recentSearches,
  onSectionsUpdate,
  onStartResearch,
  onAddToReport,
  onScrollToSection,
  onCancelResearch,
  isResearching,
  researchStatus,
  clarification,
  deepResearchReport,
  nodeStatuses,
  toolProgress,
  activeNode,
  isCacheHit,
  validationOutput,
  researchError,
  isTimeout,
  timeoutInfo,
}: ResearchDashboardProps) {
  const { addToast } = useToast()
  const [inputValue, setInputValue] = useState('')
  const [conversationHistory, setConversationHistory] = useState<ChatMessage[]>([])
  const [showSavedReports, setShowSavedReports] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // Handle opening a saved report
  const handleOpenSavedReport = useCallback(async (reportId: string) => {
    try {
      const report = await api.getSavedReportById(reportId)
      if (report) {
        // Create a new section from the saved report
        const sectionId = `saved-${reportId}-${Date.now()}`
        const newSection: ResearchSection = {
          id: sectionId,
          title: report.title || report.query,
          query: report.query,
          content: report.executive_summary || '',
          timestamp: report.created_at,
          isCollapsed: false,
          isDeepResearch: true,
        }
        onSectionsUpdate([...sections, newSection])
        setShowSavedReports(false)
      }
    } catch (err) {
      addToast({ type: 'error', title: 'Load failed', message: 'Could not load saved report' })
    }
  }, [sections, onSectionsUpdate, addToast])

  // Handle continuing research on a saved report
  const handleContinueResearch = useCallback((reportId: string, query: string) => {
    setShowSavedReports(false)
    onStartResearch(`Continue research on: ${query}`)
  }, [onStartResearch])

  // Scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [conversationHistory])

  // Handle sending a message
  const handleSend = async () => {
    if (!inputValue.trim() || isResearching) return

    const message = inputValue.trim()
    setInputValue('')

    // Add user message to conversation
    const userMessage: ChatMessage = {
      role: 'user',
      content: message,
      timestamp: new Date(),
    }
    setConversationHistory(prev => [...prev, userMessage])

    // Trigger research
    onStartResearch(message)
  }

  // Handle example prompt click
  const handleExampleClick = (prompt: string) => {
    setInputValue(prompt)
    // Auto-submit
    setTimeout(() => {
      if (prompt.trim()) {
        const userMessage: ChatMessage = {
          role: 'user',
          content: prompt,
          timestamp: new Date(),
        }
        setConversationHistory(prev => [...prev, userMessage])
        setInputValue('')
        onStartResearch(prompt)
      }
    }, 100)
  }

  // Clear conversation
  const clearConversation = () => {
    setConversationHistory([])
    onSectionsUpdate([])
  }

  const hasConversation = conversationHistory.length > 0
  const hasReport = deepResearchReport !== null && deepResearchReport !== undefined

  return (
    <div className="h-full flex bg-slate-50">
      {/* Left Panel - Chat Interface (Pipeline style) */}
      <div className="w-[400px] shrink-0 flex flex-col border-r border-slate-200 bg-white">
        {/* Header */}
        <div className="shrink-0 px-6 py-4 border-b border-slate-200 bg-gradient-to-r from-emerald-50 to-white">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-emerald-100 flex items-center justify-center">
                <Sparkles className="w-5 h-5 text-emerald-600" />
              </div>
              <div>
                <h1 className="text-lg font-semibold text-slate-800">Research Agent</h1>
                <p className="text-xs text-slate-500">Deep market intelligence</p>
              </div>
            </div>
            {hasConversation && (
              <Button
                variant="ghost"
                size="sm"
                onClick={clearConversation}
                className="text-slate-400 hover:text-slate-600"
              >
                <Trash2 size={14} />
                Clear
              </Button>
            )}
          </div>
        </div>

        {/* Chat Messages Area */}
        <div className="flex-1 overflow-auto p-6">
          {!hasConversation ? (
            // Empty state - show suggestions
            <div className="h-full flex flex-col items-center justify-center text-center px-4">
              <div className="w-16 h-16 rounded-2xl bg-emerald-100 flex items-center justify-center mb-4">
                <MessageSquare className="w-8 h-8 text-emerald-600" />
              </div>
              <h2 className="text-xl font-semibold text-slate-800 mb-2">
                Ask me anything about the market
              </h2>
              <p className="text-sm text-slate-500 mb-6 max-w-md">
                I can analyze suppliers, track market trends, dive deep into companies,
                and generate comprehensive research reports.
              </p>

              {/* Example prompts */}
              <div className="space-y-2 w-full max-w-lg">
                {[
                  { icon: Scale, text: "Compare Hexcel vs Toray carbon fiber capabilities" },
                  { icon: TrendingUp, text: "What's the outlook for aerospace composites in 2026?" },
                  { icon: Building2, text: "Give me everything I need to know about Spirit AeroSystems" },
                ].map((example, i) => (
                  <button
                    key={i}
                    onClick={() => handleExampleClick(example.text)}
                    className="w-full flex items-center gap-3 px-4 py-3 bg-slate-50 hover:bg-emerald-50 rounded-xl border border-slate-200 hover:border-emerald-200 transition-all text-left group"
                  >
                    <example.icon className="w-5 h-5 text-slate-400 group-hover:text-emerald-500 transition-colors" />
                    <span className="text-sm text-slate-600 group-hover:text-slate-800">{example.text}</span>
                    <ChevronRight className="w-4 h-4 text-slate-300 ml-auto group-hover:text-emerald-500 transition-colors" />
                  </button>
                ))}
              </div>
            </div>
          ) : (
            // Conversation messages
            <div className="space-y-4">
              {conversationHistory.map((msg, idx) => (
                <div
                  key={idx}
                  className={cn(
                    'flex',
                    msg.role === 'user' ? 'justify-end' : 'justify-start'
                  )}
                >
                  <div
                    className={cn(
                      'max-w-[85%] rounded-2xl px-4 py-3',
                      msg.role === 'user'
                        ? 'bg-emerald-500 text-white rounded-tr-sm'
                        : 'bg-white border border-slate-200 text-slate-700 rounded-tl-sm'
                    )}
                  >
                    <MarkdownContent
                      content={msg.content}
                      isUser={msg.role === 'user'}
                    />
                    <p className={cn(
                      'text-xs mt-1',
                      msg.role === 'user' ? 'text-emerald-200' : 'text-slate-400'
                    )}>
                      {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </p>
                  </div>
                </div>
              ))}

              {/* Agent thinking indicator */}
              {isResearching && (
                <div className="flex justify-start">
                  <div className="bg-emerald-50 rounded-2xl rounded-tl-sm px-4 py-3 border border-emerald-200 flex items-center gap-2">
                    <Loader2 className="w-4 h-4 animate-spin text-emerald-600" />
                    <span className="text-sm text-emerald-700">{researchStatus || 'Researching...'}</span>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Input Area */}
        <div className="shrink-0 p-4 border-t border-slate-200 bg-white">
          <div className="flex gap-2">
            <input
              ref={inputRef}
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
              placeholder="Ask about markets, companies, or trends..."
              className="flex-1 px-4 py-3 rounded-xl border border-slate-200 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100 outline-none transition-all"
              disabled={isResearching}
            />
            <Button
              onClick={handleSend}
              disabled={!inputValue.trim() || isResearching}
              className="px-4"
            >
              {isResearching ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <Send className="w-5 h-5" />
              )}
            </Button>
          </div>
        </div>
      </div>

      {/* Right Panel - Research Results */}
      <div className="flex-1 flex flex-col bg-white overflow-hidden">
        {/* Right Panel Header */}
        <div className="shrink-0 px-4 py-3 bg-white border-b border-slate-200 flex items-center justify-between">
          <div className="flex items-center gap-2">
            {showSavedReports ? (
              <>
                <button
                  onClick={() => setShowSavedReports(false)}
                  className="p-1 rounded hover:bg-slate-100 text-slate-500 hover:text-slate-700"
                >
                  <ArrowLeft size={16} />
                </button>
                <span className="font-medium text-slate-700">Saved Reports</span>
              </>
            ) : (
              <>
                <Search size={16} className="text-emerald-600" />
                <span className="font-medium text-slate-700">Research Results</span>
              </>
            )}
          </div>
          {!showSavedReports && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowSavedReports(true)}
              className="text-slate-500 hover:text-emerald-600 gap-1.5"
            >
              <Archive size={14} />
              Saved Reports
            </Button>
          )}
        </div>

        {showSavedReports ? (
          <SavedReportsPanel
            onOpenReport={handleOpenSavedReport}
            onContinueResearch={handleContinueResearch}
            onBack={() => setShowSavedReports(false)}
          />
        ) : (
          <div className="flex-1 overflow-auto p-6">
            <div className="max-w-4xl mx-auto">
              {/* Empty state */}
              {!hasReport && !isResearching && !clarification && !researchError && !isTimeout && (
                <div className="h-full flex flex-col items-center justify-center text-center py-12">
                  <div className="w-16 h-16 rounded-2xl bg-slate-100 flex items-center justify-center mb-4">
                    <Search className="w-8 h-8 text-slate-400" />
                  </div>
                  <h2 className="text-xl font-semibold text-slate-800 mb-2">
                    Your research results will appear here
                  </h2>
                  <p className="text-sm text-slate-500 max-w-md">
                    Ask a question in the chat to generate comprehensive market intelligence,
                    supplier comparisons, and actionable insights.
                  </p>
                </div>
              )}

              {/* Clarification Overlay */}
              {clarification && (
                <div className="my-8">
                  <ClarificationPrompt
                    question={clarification}
                    onResponse={(resp) => onStartResearch(resp)}
                  />
                </div>
              )}

              {/* Research Progress */}
              {isResearching && nodeStatuses && toolProgress && (
                <div className="space-y-4">
                  <ResearchProgress
                    nodeStatuses={nodeStatuses}
                    toolProgress={toolProgress}
                    activeNode={activeNode || null}
                    isCacheHit={isCacheHit || false}
                  />
                  {onCancelResearch && (
                    <div className="text-center">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={onCancelResearch}
                        className="text-slate-500 hover:text-red-500 gap-1.5"
                      >
                        <XCircle size={14} />
                        Cancel Research
                      </Button>
                    </div>
                  )}
                </div>
              )}

              {/* Fallback progress (if no node statuses available) */}
              {isResearching && !nodeStatuses && (
                <div className="bg-white rounded-xl border border-emerald-200 p-8 text-center shadow-sm">
                  <Loader2 size={32} className="text-emerald-500 animate-spin mx-auto mb-4" />
                  <h3 className="text-lg font-semibold text-slate-800 mb-1">{researchStatus}</h3>
                  <p className="text-sm text-slate-500">Our agents are analyzing financial reports and industry news.</p>
                </div>
              )}

              {/* Research Timeout */}
              {isTimeout && (
                <div className="bg-emerald-50 rounded-xl border border-emerald-200 p-6 shadow-sm">
                  <div className="flex items-start gap-3">
                    <RefreshCw className="text-emerald-500 shrink-0 mt-0.5" size={20} />
                    <div className="flex-1">
                      <h3 className="font-semibold text-emerald-800 mb-1">Research Timed Out</h3>
                      <p className="text-sm text-emerald-600 mb-3">
                        The research took longer than expected ({timeoutInfo?.elapsed_seconds || 300}s).
                        This can happen with complex queries or when external data sources are slow.
                      </p>
                      {timeoutInfo?.completed_nodes && timeoutInfo.completed_nodes.length > 0 && (
                        <div className="text-xs text-emerald-700 mb-3">
                          <span className="font-medium">Completed stages: </span>
                          {timeoutInfo.completed_nodes.join(', ')}
                        </div>
                      )}
                      <Button
                        variant="secondary"
                        size="sm"
                        className="gap-1.5"
                        onClick={() => onStartResearch('')}
                      >
                        <RefreshCw size={14} />
                        Try Again
                      </Button>
                    </div>
                  </div>
                </div>
              )}

              {/* Research Error (non-timeout) */}
              {researchError && !isTimeout && (
                <div className="bg-red-50 rounded-xl border border-red-200 p-6 shadow-sm">
                  <div className="flex items-start gap-3">
                    <XCircle className="text-red-500 shrink-0 mt-0.5" size={20} />
                    <div>
                      <h3 className="font-semibold text-red-800 mb-1">Research Error</h3>
                      <p className="text-sm text-red-600">{researchError}</p>
                      <Button
                        variant="secondary"
                        size="sm"
                        className="mt-3"
                        onClick={() => onStartResearch('')}
                      >
                        Try Again
                      </Button>
                    </div>
                  </div>
                </div>
              )}

              {/* Deep Research Report */}
              {deepResearchReport && (
                <div className="space-y-6">
                  <ResearchReport report={deepResearchReport} />

                  {/* Validation Badge */}
                  {validationOutput && (
                    <ValidationBadge validationOutput={validationOutput} />
                  )}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
