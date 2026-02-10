'use client'

import { memo } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import type { ArchNodeData } from '../types'
import {
  Zap,
  Compass,
  FlaskConical,
  GitBranch,
  Network,
  Factory,
  Settings,
} from 'lucide-react'

const iconMap: Record<string, typeof Zap> = {
  pulse: Zap,
  discovery: Compass,
  research: FlaskConical,
  pipeline: GitBranch,
  supply: Network,
  industries: Factory,
  prefs: Settings,
}

// Distinct sky/teal palette for frontend tab nodes
const TAB_COLOR = '#0891b2'        // cyan-600
const TAB_COLOR_LIGHT = '#ecfeff'  // cyan-50
const TAB_COLOR_MID = '#67e8f9'    // cyan-300
const TAB_BORDER = '#22d3ee'       // cyan-400

function TabNode({ data, selected }: NodeProps & { data: ArchNodeData }) {
  const Icon = iconMap[data.icon || 'pulse'] || Zap

  return (
    <div
      title={data.description}
      className={`
        arch-node-hover group relative px-4 py-3 rounded-lg border-2 bg-white shadow-sm
        min-w-[155px] max-w-[185px] cursor-pointer transition-all duration-200
        ${selected
          ? 'border-cyan-500 shadow-cyan-200 shadow-md ring-2 ring-cyan-200'
          : 'border-cyan-300 hover:border-cyan-400 hover:shadow-md'
        }
      `}
    >
      {/* Tab indicator bar */}
      <div className="absolute -left-0.5 top-2.5 bottom-2.5 w-1 rounded-r-full bg-cyan-400" />

      <div className="flex items-center gap-2.5 ml-1">
        <div
          className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0"
          style={{ backgroundColor: TAB_COLOR_LIGHT }}
        >
          <Icon className="w-4.5 h-4.5" style={{ color: TAB_COLOR }} />
        </div>
        <div className="min-w-0">
          <div className="text-xs font-semibold text-slate-800 leading-tight truncate">
            {data.label}
          </div>
          {data.badge && (
            <span className="text-[10px] font-medium text-cyan-600">{data.badge}</span>
          )}
        </div>
      </div>

      <Handle type="source" position={Position.Right} className="!w-2 !h-2 !bg-cyan-400 !border-cyan-500" />
    </div>
  )
}

export default memo(TabNode)
