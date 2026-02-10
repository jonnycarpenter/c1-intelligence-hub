'use client'

import { memo } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import type { ArchNodeData } from '../types'

function FanOutNode({ data, selected }: NodeProps & { data: ArchNodeData }) {
  return (
    <div
      className={`
        group relative w-8 h-8 rounded-full border-2 bg-white shadow-sm
        cursor-pointer transition-all duration-200 flex items-center justify-center
        ${selected
          ? 'border-slate-500 shadow-slate-200 shadow-md ring-2 ring-slate-200'
          : 'border-slate-300 hover:border-slate-400 hover:shadow-md'
        }
      `}
    >
      <div className="w-2 h-2 rounded-full bg-slate-400" />
      <Handle type="target" position={Position.Left} className="!w-2 !h-2 !bg-slate-400 !border-slate-500" />
      <Handle type="source" position={Position.Right} className="!w-2 !h-2 !bg-slate-400 !border-slate-500" />
    </div>
  )
}

export default memo(FanOutNode)
