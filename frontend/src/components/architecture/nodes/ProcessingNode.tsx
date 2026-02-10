'use client'

import { memo } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import type { ArchNodeData } from '../types'
import { Filter, Globe, Brain, Link, Image, Layers } from 'lucide-react'

const iconMap: Record<string, typeof Filter> = {
  filter: Filter,
  scrape: Globe,
  classify: Brain,
  link: Link,
  image: Image,
  embed: Layers,
}

function ProcessingNode({ data, selected }: NodeProps & { data: ArchNodeData }) {
  const Icon = iconMap[data.icon || 'filter'] || Filter

  return (
    <div
      title={data.description}
      className={`
        arch-node-hover group relative px-4 py-3 rounded border-2 bg-white shadow-sm
        min-w-[140px] max-w-[170px] cursor-pointer transition-all duration-200
        ${selected
          ? 'border-amber-500 shadow-amber-200 shadow-md ring-2 ring-amber-200'
          : 'border-amber-300 hover:border-amber-400 hover:shadow-md'
        }
      `}
    >
      <div className="flex items-center gap-2">
        <div className="w-7 h-7 rounded-md bg-amber-50 flex items-center justify-center shrink-0">
          <Icon className="w-4 h-4 text-amber-600" />
        </div>
        <div className="min-w-0">
          <div className="text-xs font-semibold text-slate-800 leading-tight truncate">
            {data.label}
          </div>
          {data.badge && (
            <span className="text-[10px] text-amber-600 font-medium">{data.badge}</span>
          )}
        </div>
      </div>
      <Handle type="target" position={Position.Left} className="!w-2 !h-2 !bg-amber-400 !border-amber-500" />
      <Handle type="source" position={Position.Right} className="!w-2 !h-2 !bg-amber-400 !border-amber-500" />
    </div>
  )
}

export default memo(ProcessingNode)
