'use client'

import { useCallback, useState } from 'react'
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  type NodeTypes,
  type Node,
  BackgroundVariant,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'

import {
  DataSourceNode,
  ProcessingNode,
  AgentNode,
  StorageNode,
  SchedulerNode,
  FanOutNode,
  OrchestratorNode,
  GcpServiceNode,
  TabNode,
} from './nodes'
import DetailPanel from './DetailPanel'
import { tabArchitectureNodes } from './data/tabArchitectureNodes'
import { tabArchitectureEdges } from './data/tabArchitectureEdges'
import type { ArchNodeData } from './types'

const nodeTypes: NodeTypes = {
  dataSource: DataSourceNode as any,
  processing: ProcessingNode as any,
  agent: AgentNode as any,
  storage: StorageNode as any,
  scheduler: SchedulerNode as any,
  fanOut: FanOutNode as any,
  orchestrator: OrchestratorNode as any,
  gcpService: GcpServiceNode as any,
  tabNode: TabNode as any,
}

// Minimap color resolver
function minimapColor(node: Node) {
  switch (node.type) {
    case 'tabNode': return '#67e8f9'     // cyan-300
    case 'processing': return '#fcd34d'  // amber-300
    case 'agent': return '#6ee7b7'       // emerald-300
    case 'gcpService': return '#93b4f4'  // google blue light
    case 'storage': return '#c4b5fd'     // violet-300
    default: return '#e2e8f0'
  }
}

// Column legend items
const columnLabels = [
  { label: 'FRONTEND TABS', color: '#0891b2' },
  { label: 'APPLICATION LAYER', color: '#f59e0b' },
  { label: 'GOOGLE CLOUD PLATFORM', color: '#4285F4' },
]

export default function TabArchitectureDiagram() {
  const [selectedNode, setSelectedNode] = useState<ArchNodeData | null>(null)
  const [showIam, setShowIam] = useState(true)

  const [flowNodes, , onNodesChange] = useNodesState(tabArchitectureNodes)
  const [flowEdges, , onEdgesChange] = useEdgesState(tabArchitectureEdges)

  const onNodeClick = useCallback((_event: React.MouseEvent, node: Node) => {
    setSelectedNode(node.data as ArchNodeData)
  }, [])

  const onPaneClick = useCallback(() => {
    setSelectedNode(null)
  }, [])

  // Filter IAM/logging edges for clarity toggle
  const visibleEdges = showIam
    ? flowEdges
    : flowEdges.filter(e => !e.id.startsWith('iam-'))

  return (
    <div className="h-full flex flex-col">
      {/* Header bar with GCP banner + IAM toggle */}
      <div className="px-4 pt-3 pb-2 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#e8f0fe] border border-[#a8c7fa]">
            <div className="w-3 h-3 rounded-sm" style={{ background: '#4285F4' }} />
            <span className="text-xs font-bold text-[#4285F4] tracking-wide">
              Google Cloud Platform — us-central1
            </span>
          </div>
          <span className="text-xs text-slate-400">
            10 GCP services · 7 frontend tabs · 4 app layer nodes
          </span>
        </div>
        <button
          onClick={() => setShowIam(!showIam)}
          className={`
            flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all
            ${showIam
              ? 'bg-gray-100 text-gray-600 border border-gray-300'
              : 'bg-slate-100 text-slate-400 border border-slate-200 hover:bg-slate-200'
            }
          `}
        >
          <span className={`w-2 h-2 rounded-full ${showIam ? 'bg-gray-500' : 'bg-slate-300'}`} />
          IAM Edges
        </button>
      </div>

      {/* Main canvas */}
      <div className="flex-1 relative">
        <ReactFlow
          nodes={flowNodes}
          edges={visibleEdges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={onNodeClick}
          onPaneClick={onPaneClick}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          minZoom={0.3}
          maxZoom={1.5}
          proOptions={{ hideAttribution: true }}
          className="bg-slate-50/50"
        >
          <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="#e2e8f0" />
          <Controls
            className="!bg-white !border-slate-200 !shadow-sm"
            showInteractive={false}
          />
          <MiniMap
            nodeColor={minimapColor}
            maskColor="rgba(248, 250, 252, 0.75)"
            className="!bg-white !border-slate-200"
          />
        </ReactFlow>

        {/* Column header overlay */}
        <div className="absolute top-2 left-0 right-0 flex pointer-events-none z-10 px-2 gap-1">
          {columnLabels.map(({ label, color }) => (
            <div key={label} className="flex-1 text-center">
              <span
                className="inline-block text-[10px] font-bold tracking-wider px-2 py-0.5 rounded bg-white/90 backdrop-blur-sm border shadow-sm"
                style={{ color, borderColor: color + '40' }}
              >
                {label}
              </span>
            </div>
          ))}
        </div>

        {/* GCP infrastructure zone indicator */}
        <div className="absolute bottom-2 right-2 z-10 flex items-center gap-4 bg-white/95 backdrop-blur-sm border border-slate-200 rounded-lg px-3 py-2 shadow-sm">
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-0.5 bg-amber-400 rounded" />
            <span className="text-[10px] text-slate-500">App data flow</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-0.5 rounded" style={{ background: '#4285F4' }} />
            <span className="text-[10px] text-slate-500">GCP service mesh</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-0.5 border-t border-dashed border-gray-400" />
            <span className="text-[10px] text-slate-500">IAM / Logging</span>
          </div>
        </div>

        {/* Detail Panel */}
        <DetailPanel node={selectedNode} onClose={() => setSelectedNode(null)} />
      </div>
    </div>
  )
}
