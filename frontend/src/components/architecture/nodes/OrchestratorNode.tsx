'use client'

import { memo } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import type { ArchNodeData } from '../types'
import { Workflow } from 'lucide-react'

function OrchestratorNode({ data, selected }: NodeProps & { data: ArchNodeData }) {
  return (
    <div
      title={data.description}
      className={`
        arch-node-hover animate-orchestrator-pulse group relative px-5 py-4 rounded-xl border-2 bg-gradient-to-br from-sky-50 to-white shadow-sm
        min-w-[170px] cursor-pointer transition-all duration-200
        ${selected
          ? 'border-sky-500 shadow-sky-200 shadow-md ring-2 ring-sky-200'
          : 'border-sky-300 hover:border-sky-400 hover:shadow-md'
        }
      `}
    >
      <div className="flex items-center gap-2.5">
        <div className="w-9 h-9 rounded-xl bg-sky-100 flex items-center justify-center shrink-0">
          <Workflow className="w-5 h-5 text-sky-600" />
        </div>
        <div>
          <div className="text-xs font-bold text-slate-800 leading-tight">
            {data.label}
          </div>
          {data.badge && (
            <span className="text-[10px] text-sky-600 font-medium">{data.badge}</span>
          )}
        </div>
      </div>
      <Handle type="target" position={Position.Left} className="!w-2.5 !h-2.5 !bg-sky-400 !border-sky-500" />
      <Handle type="source" position={Position.Right} className="!w-2.5 !h-2.5 !bg-sky-400 !border-sky-500" />
    </div>
  )
}

export default memo(OrchestratorNode)
