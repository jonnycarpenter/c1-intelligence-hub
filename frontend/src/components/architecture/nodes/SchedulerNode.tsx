'use client'

import { memo } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import type { ArchNodeData } from '../types'
import { Clock, Timer, CalendarClock } from 'lucide-react'

const iconMap: Record<string, typeof Clock> = {
  clock: Clock,
  timer: Timer,
  calendar: CalendarClock,
}

function SchedulerNode({ data, selected }: NodeProps & { data: ArchNodeData }) {
  const Icon = iconMap[data.icon || 'clock'] || Clock

  return (
    <div
      className={`
        arch-node-hover group relative px-3 py-2.5 bg-white shadow-sm cursor-pointer transition-all duration-200
        min-w-[120px] max-w-[160px]
        border-2 rounded-lg
        ${selected
          ? 'border-orange-500 shadow-orange-200 shadow-md ring-2 ring-orange-200'
          : 'border-orange-300 hover:border-orange-400 hover:shadow-md'
        }
      `}
      style={{ clipPath: 'polygon(12% 0%, 88% 0%, 100% 50%, 88% 100%, 12% 100%, 0% 50%)' }}
    >
      <div className="flex items-center justify-center gap-1.5">
        <Icon className="w-3.5 h-3.5 text-orange-500" />
        <span className="text-[10px] font-semibold text-slate-700 leading-tight">
          {data.label}
        </span>
      </div>
      <Handle type="source" position={Position.Right} className="!w-2 !h-2 !bg-orange-400 !border-orange-500" />
    </div>
  )
}

export default memo(SchedulerNode)
