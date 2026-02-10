'use client'

import { memo } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import type { ArchNodeData } from '../types'
import { Rss, Search, FileText, DollarSign, Newspaper, TrendingUp, Radio, Globe, Truck } from 'lucide-react'

const iconMap: Record<string, typeof Rss> = {
  rss: Rss,
  search: Search,
  filing: FileText,
  earnings: DollarSign,
  news: Newspaper,
  trending: TrendingUp,
  radio: Radio,
  globe: Globe,
  truck: Truck,
}

function DataSourceNode({ data, selected }: NodeProps & { data: ArchNodeData }) {
  const Icon = iconMap[data.icon || 'globe'] || Globe

  return (
    <div
      className={`
        group relative px-4 py-3 rounded-lg border-2 bg-white shadow-sm
        min-w-[140px] max-w-[170px] cursor-pointer transition-all duration-200
        ${selected
          ? 'border-blue-500 shadow-blue-200 shadow-md ring-2 ring-blue-200'
          : 'border-blue-300 hover:border-blue-400 hover:shadow-md'
        }
      `}
    >
      <div className="flex items-center gap-2">
        <div className="w-7 h-7 rounded-md bg-blue-50 flex items-center justify-center shrink-0">
          <Icon className="w-4 h-4 text-blue-500" />
        </div>
        <div className="min-w-0">
          <div className="text-xs font-semibold text-slate-800 leading-tight truncate">
            {data.label}
          </div>
          {data.badge && (
            <span className="text-[10px] text-blue-500 font-medium">{data.badge}</span>
          )}
        </div>
      </div>
      <Handle type="source" position={Position.Right} className="!w-2 !h-2 !bg-blue-400 !border-blue-500" />
    </div>
  )
}

export default memo(DataSourceNode)
