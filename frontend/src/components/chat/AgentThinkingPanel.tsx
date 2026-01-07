'use client'

import { useState } from 'react'
import { 
  ChevronDown, 
  ChevronRight, 
  Wrench, 
  Brain, 
  ExternalLink,
  CheckCircle,
  Loader2,
  AlertCircle
} from 'lucide-react'
import { cn } from '@/lib/utils'
import type { AgentThinking, ToolCall } from '@/types'

interface AgentThinkingPanelProps {
  thinking: AgentThinking[]
  traceUrl?: string
  isStreaming?: boolean
}

export default function AgentThinkingPanel({ thinking, traceUrl, isStreaming = false }: AgentThinkingPanelProps) {
  const [isExpanded, setIsExpanded] = useState(true)

  if (thinking.length === 0 && !isStreaming) return null

  return (
    <div className="bg-slate-50 border border-slate-200 rounded-lg overflow-hidden text-sm">
      {/* Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between p-3 hover:bg-slate-100 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Brain size={16} className="text-violet-500" />
          <span className="font-medium text-slate-700">Agent Thinking</span>
          {isStreaming && (
            <span className="flex items-center gap-1 text-xs text-emerald-600">
              <Loader2 size={12} className="animate-spin" />
              Processing...
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {traceUrl && (
            <a
              href={traceUrl}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="flex items-center gap-1 text-xs text-violet-600 hover:text-violet-700 px-2 py-1 rounded bg-violet-50 hover:bg-violet-100 transition-colors"
            >
              <ExternalLink size={12} />
              View in LangSmith
            </a>
          )}
          {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
        </div>
      </button>

      {/* Content */}
      {isExpanded && (
        <div className="border-t border-slate-200 p-3 space-y-3">
          {thinking.map((step, index) => (
            <ThinkingStep key={index} step={step} index={index} />
          ))}
          
          {isStreaming && thinking.length === 0 && (
            <div className="flex items-center gap-2 text-slate-500 py-2">
              <Loader2 size={14} className="animate-spin" />
              <span>Analyzing your request...</span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

interface ThinkingStepProps {
  step: AgentThinking
  index: number
}

function ThinkingStep({ step, index }: ThinkingStepProps) {
  const [isOpen, setIsOpen] = useState(index === 0)

  return (
    <div className="border border-slate-200 rounded-lg overflow-hidden bg-white">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center gap-2 p-2.5 hover:bg-slate-50 transition-colors text-left"
      >
        <StepStatusIcon status={step.status} />
        <span className="font-medium text-slate-700 flex-1">{step.step}</span>
        <span className="text-xs text-slate-400">{step.timestamp}</span>
        {isOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
      </button>

      {isOpen && (
        <div className="border-t border-slate-100 p-3 space-y-2.5 bg-slate-50/50">
          {/* Reasoning */}
          {step.reasoning && (
            <div>
              <span className="text-xs font-medium text-slate-500 uppercase tracking-wide">Reasoning</span>
              <p className="text-slate-600 mt-1">{step.reasoning}</p>
            </div>
          )}

          {/* Tool calls */}
          {step.toolCalls && step.toolCalls.length > 0 && (
            <div>
              <span className="text-xs font-medium text-slate-500 uppercase tracking-wide">Tools Used</span>
              <div className="mt-1.5 space-y-1.5">
                {step.toolCalls.map((tool, idx) => (
                  <ToolCallItem key={idx} tool={tool} />
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function StepStatusIcon({ status }: { status: AgentThinking['status'] }) {
  switch (status) {
    case 'completed':
      return <CheckCircle size={16} className="text-emerald-500" />
    case 'in-progress':
      return <Loader2 size={16} className="text-emerald-500 animate-spin" />
    case 'error':
      return <AlertCircle size={16} className="text-red-500" />
    default:
      return <div className="w-4 h-4 rounded-full border-2 border-slate-300" />
  }
}

interface ToolCallItemProps {
  tool: ToolCall
}

function ToolCallItem({ tool }: ToolCallItemProps) {
  return (
    <div className="bg-white border border-slate-200 rounded-md overflow-hidden">
      {/* Tool info display - no expandable details (protects IP) */}
      <div className="flex items-center gap-2 px-2.5 py-1.5">
        <Wrench size={12} className="text-blue-500" />
        <code className="text-xs font-mono text-blue-700 flex-1">{tool.name}</code>
        <ToolStatusBadge status={tool.status} />
        {tool.duration !== undefined && (
          <span className="text-[10px] text-slate-400">{tool.duration}ms</span>
        )}
      </div>
    </div>
  )
}

function ToolStatusBadge({ status }: { status: ToolCall['status'] }) {
  const styles = {
    pending: 'bg-slate-100 text-slate-600',
    running: 'bg-emerald-100 text-emerald-700',
    completed: 'bg-emerald-100 text-emerald-700',
    error: 'bg-red-100 text-red-700',
  }

  return (
    <span className={cn('px-1.5 py-0.5 rounded text-[10px] font-medium uppercase', styles[status])}>
      {status}
    </span>
  )
}
