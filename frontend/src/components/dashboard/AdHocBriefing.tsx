'use client'

import React, { useState, useRef, useEffect } from 'react'
import {
  Send,
  Loader2,
  AlertCircle,
  ExternalLink,
  MessageSquare,
  ArrowRight,
  Sparkles,
  X,
  Bookmark,
  Check
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { Badge, Button } from '@/components/ui'
import { MarkdownContent } from '@/components/ui'
import { useAdHocBriefing } from '@/hooks'
import { api } from '@/lib/api'
import type { AdHocBriefing as AdHocBriefingType, AdHocBriefingContext } from '@/types/briefing'

// =============================================================================
// Confidence Badge
// =============================================================================

interface ConfidenceBadgeProps {
  confidence: 'high' | 'medium' | 'low'
}

function ConfidenceBadge({ confidence }: ConfidenceBadgeProps) {
  const configs = {
    high: { bg: 'bg-emerald-100', text: 'text-emerald-700', label: 'High Confidence' },
    medium: { bg: 'bg-amber-100', text: 'text-amber-700', label: 'Medium Confidence' },
    low: { bg: 'bg-rose-100', text: 'text-rose-700', label: 'Limited Data' },
  }
  const config = configs[confidence]

  return (
    <Badge className={cn(config.bg, config.text, "text-[10px] font-medium")}>
      {config.label}
    </Badge>
  )
}

// =============================================================================
// Response Card Component
// =============================================================================

interface ResponseCardProps {
  response: AdHocBriefingType
  onDeepResearch?: (query: string) => void
  onClose?: () => void
  onSaveToMemory?: () => Promise<void>
}

function ResponseCard({ response, onDeepResearch, onClose, onSaveToMemory }: ResponseCardProps) {
  const [isSaving, setIsSaving] = useState(false)
  const [isSaved, setIsSaved] = useState(false)

  const handleSave = async () => {
    if (!onSaveToMemory || isSaving || isSaved) return
    setIsSaving(true)
    try {
      await onSaveToMemory()
      setIsSaved(true)
    } catch (error) {
      console.error('Failed to save to memory:', error)
    } finally {
      setIsSaving(false)
    }
  }
  return (
    <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
      {/* Header */}
      <div className="border-b border-slate-100 px-4 py-3 flex items-center justify-between bg-slate-50">
        <div className="flex items-center gap-2">
          <MessageSquare size={16} className="text-amber-600" />
          <span className="text-sm font-medium text-slate-700">Quick Briefing</span>
          <ConfidenceBadge confidence={response.confidence} />
        </div>
        <div className="flex items-center gap-1">
          {onSaveToMemory && (
            <button
              onClick={handleSave}
              disabled={isSaving || isSaved}
              className={cn(
                "p-1.5 rounded-lg transition-all duration-200",
                isSaved
                  ? "text-emerald-600 bg-emerald-50"
                  : "text-slate-400 hover:text-amber-600 hover:bg-amber-50"
              )}
              title={isSaved ? "Saved to memory" : "Save to memory"}
            >
              {isSaving ? (
                <Loader2 size={14} className="animate-spin" />
              ) : isSaved ? (
                <Check size={14} />
              ) : (
                <Bookmark size={14} />
              )}
            </button>
          )}
          {onClose && (
            <button
              onClick={onClose}
              className="text-slate-400 hover:text-slate-600 transition-colors p-1.5"
            >
              <X size={16} />
            </button>
          )}
        </div>
      </div>

      {/* Question */}
      <div className="px-4 py-3 bg-amber-50/50 border-b border-slate-100">
        <p className="text-sm text-slate-600">
          <span className="font-semibold text-slate-700">Q:</span> {response.question}
        </p>
      </div>

      {/* Answer */}
      <div className="p-4">
        <div className="prose prose-sm prose-slate max-w-none">
          <MarkdownContent content={response.answer} />
        </div>
      </div>

      {/* Sources */}
      {response.sources_used && response.sources_used.length > 0 && (
        <div className="border-t border-slate-100 px-4 py-3 bg-slate-50">
          <div className="text-[10px] text-slate-400 uppercase tracking-wider font-semibold mb-2">
            Sources
          </div>
          <div className="flex flex-wrap gap-2">
            {response.sources_used.map((source, idx) => (
              <a
                key={idx}
                href={source.url || '#'}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-xs text-slate-600 hover:text-amber-600 transition-colors"
              >
                <span className="truncate max-w-[200px]">{source.title}</span>
                {source.url && <ExternalLink size={10} />}
              </a>
            ))}
          </div>
        </div>
      )}

      {/* Deep Research Suggestion */}
      {(response.suggest_deep_research || response.redirect_to_deep_research) && (
        <div className="border-t border-amber-100 px-4 py-3 bg-amber-50">
          <div className="flex items-start gap-3">
            <AlertCircle size={18} className="text-amber-600 shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="text-sm text-amber-900">
                {response.redirect_to_deep_research
                  ? "You've asked several follow-up questions. For comprehensive analysis, try Deep Research."
                  : "This topic may benefit from deeper analysis with additional sources."
                }
              </p>
              {onDeepResearch && (
                <button
                  onClick={() => onDeepResearch(response.deep_research_query || response.question)}
                  className="mt-2 inline-flex items-center gap-1.5 px-3 py-1.5 bg-amber-600 text-white text-xs font-medium rounded-lg hover:bg-amber-700 transition-colors"
                >
                  <Sparkles size={12} />
                  Start Deep Research
                  <ArrowRight size={12} />
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Related Topics */}
      {response.related_topics && response.related_topics.length > 0 && (
        <div className="border-t border-slate-100 px-4 py-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[10px] text-slate-400 uppercase tracking-wider font-semibold">
              Related:
            </span>
            {response.related_topics.map((topic, idx) => (
              <Badge
                key={idx}
                className="text-xs text-slate-600 bg-white border-slate-200 cursor-pointer hover:bg-slate-100"
              >
                {topic}
              </Badge>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// =============================================================================
// Main Ad Hoc Briefing Component
// =============================================================================

interface AdHocBriefingProps {
  /** Context from current weekly briefing for better responses */
  context?: AdHocBriefingContext
  /** Callback when user wants to start deep research */
  onDeepResearch?: (query: string) => void
  /** Whether the component is in compact mode */
  compact?: boolean
}

export default function AdHocBriefing({
  context,
  onDeepResearch,
  compact = false
}: AdHocBriefingProps) {
  const [question, setQuestion] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  const {
    response,
    isLoading,
    error,
    isTimeout,
    followUpCount,
    askQuestion,
    reset
  } = useAdHocBriefing()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!question.trim() || isLoading) return

    const isFollowUp = response !== null
    await askQuestion(question.trim(), context, isFollowUp)
    setQuestion('')
  }

  const handleNewQuestion = () => {
    reset()
    inputRef.current?.focus()
  }

  return (
    <div className={cn(
      "flex flex-col",
      compact ? "gap-3" : "gap-4"
    )}>
      {/* Input Section */}
      <div className={cn(
        "bg-white border rounded-xl overflow-hidden transition-all duration-200",
        response ? "border-slate-200" : "border-amber-200 shadow-sm shadow-amber-100/50"
      )}>
        <form onSubmit={handleSubmit} className="flex items-center gap-2 p-3">
          <MessageSquare size={18} className="text-amber-500 shrink-0" />
          <input
            ref={inputRef}
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder={response ? "Ask a follow-up question..." : "Ask about this week's news..."}
            className="flex-1 text-sm bg-transparent border-none outline-none placeholder:text-slate-400"
            disabled={isLoading}
          />
          <button
            type="submit"
            disabled={!question.trim() || isLoading}
            className={cn(
              "p-2 rounded-lg transition-all duration-200",
              question.trim() && !isLoading
                ? "bg-amber-500 text-white hover:bg-amber-600"
                : "bg-slate-100 text-slate-400"
            )}
          >
            {isLoading ? (
              <Loader2 size={16} className="animate-spin" />
            ) : (
              <Send size={16} />
            )}
          </button>
        </form>

        {/* Follow-up indicator */}
        {followUpCount > 0 && followUpCount < 2 && (
          <div className="px-3 pb-2 flex items-center gap-2 text-xs text-slate-400">
            <span>Follow-up {followUpCount}/2</span>
            <button
              onClick={handleNewQuestion}
              className="text-amber-600 hover:text-amber-700 font-medium"
            >
              Start new question
            </button>
          </div>
        )}
      </div>

      {/* Loading State */}
      {isLoading && (
        <div className="bg-slate-50 border border-slate-200 rounded-xl p-6 flex items-center justify-center gap-3">
          <Loader2 size={20} className="animate-spin text-amber-500" />
          <span className="text-sm text-slate-600">Analyzing relevant articles...</span>
        </div>
      )}

      {/* Error State */}
      {error && !isLoading && (
        <div className={cn(
          "border rounded-xl p-4 flex items-start gap-3",
          isTimeout ? "bg-amber-50 border-amber-200" : "bg-rose-50 border-rose-200"
        )}>
          <AlertCircle size={18} className={cn(
            "shrink-0 mt-0.5",
            isTimeout ? "text-amber-500" : "text-rose-500"
          )} />
          <div>
            <p className={cn(
              "text-sm font-medium",
              isTimeout ? "text-amber-800" : "text-rose-800"
            )}>
              {isTimeout ? 'Request timed out' : 'Failed to generate briefing'}
            </p>
            <p className={cn(
              "text-xs mt-1",
              isTimeout ? "text-amber-600" : "text-rose-600"
            )}>
              {isTimeout
                ? 'The request took longer than 60 seconds. Try simplifying your question or ask again.'
                : error.message
              }
            </p>
            <button
              onClick={() => inputRef.current?.focus()}
              className={cn(
                "mt-2 text-xs font-medium",
                isTimeout
                  ? "text-amber-700 hover:text-amber-800"
                  : "text-rose-700 hover:text-rose-800"
              )}
            >
              Try again
            </button>
          </div>
        </div>
      )}

      {/* Response */}
      {response && !isLoading && (
        <ResponseCard
          response={response}
          onDeepResearch={onDeepResearch}
          onClose={handleNewQuestion}
          onSaveToMemory={async () => {
            await api.saveToMemory({
              type: 'briefing',
              question: response.question,
              answer: response.answer,
              sources: response.sources_used,
              confidence: response.confidence,
              tags: response.related_topics,
            })
          }}
        />
      )}

      {/* Empty State Hint */}
      {!response && !isLoading && !error && !compact && (
        <div className="text-center py-4 text-xs text-slate-400">
          <p>Try asking about topics in this week's briefing, or any industry news</p>
          <p className="mt-1">
            <span className="font-medium">Examples:</span>{' '}
            "What's the latest on Hexcel's expansion?" • "Any supply chain disruptions?"
          </p>
        </div>
      )}
    </div>
  )
}
