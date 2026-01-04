'use client'

import { useState } from 'react'
import { 
  ChevronDown, 
  ChevronRight, 
  Wrench, 
  Brain,
  Zap,
  CheckCircle,
  Loader2,
  AlertCircle
} from 'lucide-react'
import { cn } from '@/lib/utils'
import type { AgentThinking, ToolCall } from '@/types'

interface StreamingThinkingPanelProps {
  thinking: AgentThinking[]
  agentName?: string | null
  isStreaming?: boolean
}

export default function StreamingThinkingPanel({ 
  thinking, 
  agentName,
  isStreaming = false 
}: StreamingThinkingPanelProps) {
  const [isExpanded, setIsExpanded] = useState(true)

  if (thinking.length === 0 && !isStreaming) return null

  // Get current active step
  const activeStep = thinking.find(s => s.status === 'in-progress')
  const completedSteps = thinking.filter(s => s.status === 'completed')

  return (
    <div className="bg-gradient-to-br from-violet-50 to-slate-50 border border-violet-200 rounded-xl overflow-hidden text-sm shadow-sm">
      {/* Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between p-3 hover:bg-violet-100/50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-lg bg-violet-500 flex items-center justify-center">
            <Brain size={14} className="text-white" />
          </div>
          <div className="flex flex-col items-start">
            <span className="font-semibold text-slate-700 text-sm">
              {agentName || 'Agent'} Thinking
            </span>
            {isStreaming && (
              <span className="text-xs text-violet-600 flex items-center gap-1">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-violet-400 opacity-75" />
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-violet-500" />
                </span>
                Live
              </span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-400">
            {completedSteps.length}/{thinking.length} steps
          </span>
          {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
        </div>
      </button>

      {/* Content */}
      {isExpanded && (
        <div className="border-t border-violet-200/50 p-3 space-y-2">
          {/* Progress track */}
          <div className="flex items-center gap-1 px-1 mb-2">
            {thinking.map((step, index) => (
              <div
                key={index}
                className={cn(
                  'flex-1 h-1 rounded-full transition-all duration-300',
                  step.status === 'completed' ? 'bg-emerald-400' :
                  step.status === 'in-progress' ? 'bg-amber-400 animate-pulse' :
                  step.status === 'error' ? 'bg-red-400' : 'bg-slate-200'
                )}
              />
            ))}
          </div>

          {/* Steps */}
          {thinking.map((step, index) => (
            <StreamingStep 
              key={index} 
              step={step} 
              isActive={step.status === 'in-progress'}
            />
          ))}
          
          {isStreaming && thinking.length === 0 && (
            <div className="flex items-center gap-2 text-slate-500 py-2 px-1">
              <Loader2 size={14} className="animate-spin text-violet-500" />
              <span>Initializing agent...</span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

interface StreamingStepProps {
  step: AgentThinking
  isActive: boolean
}

function StreamingStep({ step, isActive }: StreamingStepProps) {
  const [isOpen, setIsOpen] = useState(isActive)

  // Auto-expand active step
  if (isActive && !isOpen) {
    setIsOpen(true)
  }

  const hasToolCalls = step.toolCalls && step.toolCalls.length > 0

  return (
    <div className={cn(
      'rounded-lg overflow-hidden transition-all duration-200',
      isActive 
        ? 'bg-white border-2 border-violet-300 shadow-sm' 
        : 'bg-white/60 border border-slate-200'
    )}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center gap-2 p-2.5 hover:bg-slate-50/50 transition-colors text-left"
      >
        <StepStatusIcon status={step.status} />
        <span className={cn(
          'font-medium flex-1 truncate',
          isActive ? 'text-violet-700' : 'text-slate-700'
        )}>
          {step.step}
        </span>
        {hasToolCalls && (
          <span className="flex items-center gap-1 text-xs text-blue-600 bg-blue-50 px-1.5 py-0.5 rounded">
            <Wrench size={10} />
            {step.toolCalls?.length}
          </span>
        )}
        <span className="text-[10px] text-slate-400">{step.timestamp}</span>
        {(step.reasoning || hasToolCalls) && (
          isOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />
        )}
      </button>

      {isOpen && (step.reasoning || hasToolCalls) && (
        <div className="border-t border-slate-100 p-2.5 space-y-2 bg-slate-50/30">
          {/* Reasoning */}
          {step.reasoning && (
            <div className="text-xs">
              <span className="font-medium text-slate-500 uppercase tracking-wide">Reasoning</span>
              <p className="text-slate-600 mt-1 leading-relaxed">{step.reasoning}</p>
            </div>
          )}

          {/* Tool calls */}
          {hasToolCalls && (
            <div>
              <span className="text-xs font-medium text-slate-500 uppercase tracking-wide">Tools</span>
              <div className="mt-1.5 space-y-1">
                {step.toolCalls?.map((tool, idx) => (
                  <StreamingToolCall key={idx} tool={tool} />
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
      return <CheckCircle size={16} className="text-emerald-500 shrink-0" />
    case 'in-progress':
      return (
        <div className="relative shrink-0">
          <Zap size={16} className="text-amber-500" />
          <span className="absolute -top-0.5 -right-0.5 flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-amber-500" />
          </span>
        </div>
      )
    case 'error':
      return <AlertCircle size={16} className="text-red-500 shrink-0" />
    default:
      return <div className="w-4 h-4 rounded-full border-2 border-slate-300 shrink-0" />
  }
}

interface StreamingToolCallProps {
  tool: ToolCall
}

function StreamingToolCall({ tool }: StreamingToolCallProps) {
  return (
    <div className={cn(
      'rounded-md overflow-hidden border transition-all duration-200',
      tool.status === 'running' 
        ? 'border-blue-300 bg-blue-50' 
        : tool.status === 'completed'
        ? 'border-slate-200 bg-white'
        : tool.status === 'error'
        ? 'border-red-200 bg-red-50'
        : 'border-slate-200 bg-slate-50'
    )}>
      {/* Tool info display - no expandable details (protects IP) */}
      <div className="flex items-center gap-2 px-2 py-1.5">
        {tool.status === 'running' ? (
          <Loader2 size={12} className="text-blue-500 animate-spin shrink-0" />
        ) : (
          <Wrench size={12} className="text-blue-500 shrink-0" />
        )}
        <code className="text-xs font-mono text-blue-700 flex-1 truncate">{tool.name}</code>
        <ToolStatusBadge status={tool.status} />
        {tool.duration && (
          <span className="text-[10px] text-slate-400">{tool.duration}ms</span>
        )}
      </div>
    </div>
  )
}

function ToolStatusBadge({ status }: { status: ToolCall['status'] }) {
  const styles = {
    pending: 'bg-slate-100 text-slate-600 border-slate-200',
    running: 'bg-blue-100 text-blue-700 border-blue-200 animate-pulse',
    completed: 'bg-emerald-100 text-emerald-700 border-emerald-200',
    error: 'bg-red-100 text-red-700 border-red-200',
  }

  return (
    <span className={cn(
      'px-1.5 py-0.5 rounded border text-[10px] font-medium uppercase', 
      styles[status]
    )}>
      {status}
    </span>
  )
}
