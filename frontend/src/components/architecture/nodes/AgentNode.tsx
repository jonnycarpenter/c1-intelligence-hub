'use client'

import { memo } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import type { ArchNodeData } from '../types'
import { Brain, Sparkles, Wand2, MessageSquare, Eye } from 'lucide-react'

const iconMap: Record<string, typeof Brain> = {
  brain: Brain,
  sparkles: Sparkles,
  wand: Wand2,
  chat: MessageSquare,
  eye: Eye,
}

function AgentNode({ data, selected }: NodeProps & { data: ArchNodeData }) {
  const Icon = iconMap[data.icon || 'brain'] || Brain

  return (
    <div
      className={`
        group relative px-4 py-3.5 rounded-lg border-2 bg-gradient-to-br from-emerald-50 to-white shadow-sm
        min-w-[160px] max-w-[190px] cursor-pointer transition-all duration-200
        ${selected
          ? 'border-emerald-500 shadow-emerald-200 shadow-md ring-2 ring-emerald-200'
          : 'border-emerald-300 hover:border-emerald-400 hover:shadow-md'
        }
      `}
    >
      <div className="flex items-center gap-2">
        <div className="w-8 h-8 rounded-lg bg-emerald-100 flex items-center justify-center shrink-0">
          <Icon className="w-4.5 h-4.5 text-emerald-600" />
        </div>
        <div className="min-w-0">
          <div className="text-xs font-bold text-slate-800 leading-tight">
            {data.label}
          </div>
          {data.badge && (
            <span className="text-[10px] text-emerald-600 font-medium">{data.badge}</span>
          )}
        </div>
      </div>
      <Handle type="target" position={Position.Left} className="!w-2 !h-2 !bg-emerald-400 !border-emerald-500" />
      <Handle type="source" position={Position.Right} className="!w-2 !h-2 !bg-emerald-400 !border-emerald-500" />
    </div>
  )
}

export default memo(AgentNode)
