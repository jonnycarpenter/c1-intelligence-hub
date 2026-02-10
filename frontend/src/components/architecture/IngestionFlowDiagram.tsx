'use client'

import { useCallback, useState, useMemo } from 'react'
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

import { DataSourceNode, ProcessingNode, AgentNode, StorageNode, SchedulerNode, FanOutNode, OrchestratorNode } from './nodes'
import DetailPanel from './DetailPanel'
import SectionHeader from './SectionHeader'
import { ingestionSectionANodes } from './data/ingestionNodes'
import { ingestionSectionAEdges } from './data/ingestionEdges'
import type { ArchNodeData } from './types'

const nodeTypes: NodeTypes = {
  dataSource: DataSourceNode as any,
  processing: ProcessingNode as any,
  agent: AgentNode as any,
  storage: StorageNode as any,
  scheduler: SchedulerNode as any,
  fanOut: FanOutNode as any,
  orchestrator: OrchestratorNode as any,
}

// Column labels for the diagram
const columnLabels = [
  { x: 30, label: 'DATA SOURCES', color: '#3b82f6' },
  { x: 305, label: 'ORCHESTRATOR', color: '#0ea5e9' },
  { x: 555, label: 'PROCESSING PIPELINE', color: '#f59e0b' },
  { x: 860, label: 'BIGQUERY STORAGE', color: '#8b5cf6' },
  { x: 1125, label: 'POST-PROCESSING', color: '#a78bfa' },
]

export default function IngestionFlowDiagram() {
  const [nodes, setNodes, onNodesChange] = useNodesState(ingestionSectionANodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(ingestionSectionAEdges)
  const [selectedNode, setSelectedNode] = useState<ArchNodeData | null>(null)
  const [sectionAExpanded, setSectionAExpanded] = useState(true)

  const onNodeClick = useCallback((_event: React.MouseEvent, node: Node) => {
    setSelectedNode(node.data as ArchNodeData)
  }, [])

  const onPaneClick = useCallback(() => {
    setSelectedNode(null)
  }, [])

  // Memoize default viewport for performance
  const defaultViewport = useMemo(() => ({ x: 30, y: 20, zoom: 0.85 }), [])

  return (
    <div className="h-full flex flex-col">
      {/* Section Header */}
      <div className="px-4 pt-3 pb-2">
        <SectionHeader
          letter="A"
          title="Core Article Ingestion"
          description="10 sources → orchestrator → processing pipeline → BigQuery storage"
          color="sky"
          isExpanded={sectionAExpanded}
          onToggle={() => setSectionAExpanded(!sectionAExpanded)}
        />
      </div>

      {/* React Flow Canvas */}
      {sectionAExpanded && (
        <div className="flex-1 relative">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onNodeClick={onNodeClick}
            onPaneClick={onPaneClick}
            nodeTypes={nodeTypes}
            defaultViewport={defaultViewport}
            fitView
            fitViewOptions={{ padding: 0.15 }}
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
              nodeColor={(node) => {
                switch (node.type) {
                  case 'dataSource': return '#93c5fd'
                  case 'processing': return '#fcd34d'
                  case 'agent': return '#6ee7b7'
                  case 'storage': return '#c4b5fd'
                  case 'orchestrator': return '#7dd3fc'
                  default: return '#e2e8f0'
                }
              }}
              maskColor="rgba(248, 250, 252, 0.75)"
              className="!bg-white !border-slate-200"
            />

            {/* Column Labels (rendered as SVG annotations) */}
            {columnLabels.map(({ x, label, color }) => (
              <div
                key={label}
                className="absolute pointer-events-none"
                style={{
                  left: x,
                  top: -8,
                  transform: 'translateX(-50%)',
                }}
              >
                {/* These are purely decorative — React Flow handles pan/zoom positioning */}
              </div>
            ))}
          </ReactFlow>

          {/* Column header overlay */}
          <div className="absolute top-2 left-0 right-0 flex pointer-events-none z-10 px-2 gap-1">
            {columnLabels.map(({ label, color }) => (
              <div
                key={label}
                className="flex-1 text-center"
              >
                <span
                  className="inline-block text-[10px] font-bold tracking-wider px-2 py-0.5 rounded bg-white/90 backdrop-blur-sm border shadow-sm"
                  style={{ color, borderColor: color + '40' }}
                >
                  {label}
                </span>
              </div>
            ))}
          </div>

          {/* Detail Panel */}
          <DetailPanel
            node={selectedNode}
            onClose={() => setSelectedNode(null)}
          />
        </div>
      )}
    </div>
  )
}
