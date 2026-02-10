'use client'

import { memo } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import type { ArchNodeData } from '../types'
import {
  Container,
  Database,
  Brain,
  Cloud,
  Clock,
  Hammer,
  Package,
  KeyRound,
  Shield,
  Activity,
} from 'lucide-react'

const iconMap: Record<string, typeof Container> = {
  container: Container,
  database: Database,
  brain: Brain,
  bucket: Cloud,
  clock: Clock,
  cicd: Hammer,
  package: Package,
  key: KeyRound,
  shield: Shield,
  monitor: Activity,
}

// Google Blue accent for GCP-branded nodes
const GCP_BLUE = '#4285F4'
const GCP_BLUE_LIGHT = '#e8f0fe'
const GCP_BLUE_MID = '#a8c7fa'

function GcpServiceNode({ data, selected }: NodeProps & { data: ArchNodeData }) {
  const Icon = iconMap[data.icon || 'container'] || Container

  return (
    <div
      title={data.description}
      className={`
        arch-node-hover group relative px-4 py-3 rounded-xl border-2 bg-white shadow-sm
        min-w-[150px] max-w-[185px] cursor-pointer transition-all duration-200
        ${selected
          ? 'shadow-md ring-2'
          : 'hover:shadow-md'
        }
      `}
      style={{
        borderColor: selected ? GCP_BLUE : GCP_BLUE_MID,
        ...(selected ? { boxShadow: `0 4px 14px -3px ${GCP_BLUE}40`, ringColor: `${GCP_BLUE}30` } : {}),
      }}
    >
      {/* Subtle GCP watermark stripe at top */}
      <div
        className="absolute top-0 left-0 right-0 h-1 rounded-t-xl"
        style={{ background: `linear-gradient(90deg, ${GCP_BLUE}, ${GCP_BLUE_MID})` }}
      />

      <div className="flex items-center gap-2.5 mt-0.5">
        <div
          className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0"
          style={{ backgroundColor: GCP_BLUE_LIGHT }}
        >
          <Icon className="w-4.5 h-4.5" style={{ color: GCP_BLUE }} />
        </div>
        <div className="min-w-0">
          <div className="text-xs font-semibold text-slate-800 leading-tight truncate">
            {data.label}
          </div>
          {data.badge && (
            <span className="text-[10px] font-medium" style={{ color: GCP_BLUE }}>
              {data.badge}
            </span>
          )}
        </div>
      </div>

      <Handle
        type="target"
        position={Position.Left}
        className="!w-2 !h-2"
        style={{ background: GCP_BLUE_MID, borderColor: GCP_BLUE }}
      />
      <Handle
        type="source"
        position={Position.Right}
        className="!w-2 !h-2"
        style={{ background: GCP_BLUE_MID, borderColor: GCP_BLUE }}
      />
      <Handle
        type="target"
        position={Position.Top}
        id="top"
        className="!w-2 !h-2"
        style={{ background: GCP_BLUE_MID, borderColor: GCP_BLUE }}
      />
      <Handle
        type="source"
        position={Position.Bottom}
        id="bottom"
        className="!w-2 !h-2"
        style={{ background: GCP_BLUE_MID, borderColor: GCP_BLUE }}
      />
    </div>
  )
}

export default memo(GcpServiceNode)
