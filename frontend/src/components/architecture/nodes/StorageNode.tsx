'use client'

import { memo } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import type { ArchNodeData } from '../types'
import { Database, Cloud, HardDrive, Table } from 'lucide-react'

const iconMap: Record<string, typeof Database> = {
  database: Database,
  cloud: Cloud,
  drive: HardDrive,
  table: Table,
}

function StorageNode({ data, selected }: NodeProps & { data: ArchNodeData }) {
  const Icon = iconMap[data.icon || 'database'] || Database
  const isGcs = data.color === 'indigo'

  return (
    <div
      className={`
        group relative px-4 py-3 rounded-xl border-2 bg-white shadow-sm
        min-w-[140px] max-w-[180px] cursor-pointer transition-all duration-200
        ${isGcs
          ? (selected
            ? 'border-indigo-500 shadow-indigo-200 shadow-md ring-2 ring-indigo-200'
            : 'border-indigo-300 hover:border-indigo-400 hover:shadow-md')
          : (selected
            ? 'border-violet-500 shadow-violet-200 shadow-md ring-2 ring-violet-200'
            : 'border-violet-300 hover:border-violet-400 hover:shadow-md')
        }
      `}
    >
      <div className="flex items-center gap-2">
        <div className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 ${isGcs ? 'bg-indigo-50' : 'bg-violet-50'}`}>
          <Icon className={`w-4 h-4 ${isGcs ? 'text-indigo-500' : 'text-violet-500'}`} />
        </div>
        <div className="min-w-0">
          <div className="text-xs font-semibold text-slate-800 leading-tight truncate">
            {data.label}
          </div>
          {data.badge && (
            <span className={`text-[10px] font-medium ${isGcs ? 'text-indigo-500' : 'text-violet-500'}`}>{data.badge}</span>
          )}
        </div>
      </div>
      <Handle type="target" position={Position.Left} className={`!w-2 !h-2 ${isGcs ? '!bg-indigo-400 !border-indigo-500' : '!bg-violet-400 !border-violet-500'}`} />
      <Handle type="source" position={Position.Right} className={`!w-2 !h-2 ${isGcs ? '!bg-indigo-400 !border-indigo-500' : '!bg-violet-400 !border-violet-500'}`} />
    </div>
  )
}

export default memo(StorageNode)
