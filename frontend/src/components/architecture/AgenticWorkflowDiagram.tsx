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
  type Edge,
  BackgroundVariant,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'

import { DataSourceNode, ProcessingNode, AgentNode, StorageNode, SchedulerNode, FanOutNode, OrchestratorNode } from './nodes'
import DetailPanel from './DetailPanel'
import SectionHeader from './SectionHeader'
import { briefingNodes } from './data/agenticNodes'
import { briefingEdges } from './data/agenticEdges'
import { deepResearchNodes } from './data/agenticNodes'
import { deepResearchEdges } from './data/agenticEdges'
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

// Minimap color resolver
function minimapColor(node: Node) {
  switch (node.type) {
    case 'dataSource': return '#93c5fd'
    case 'processing': return '#fcd34d'
    case 'agent': return '#6ee7b7'
    case 'storage': return '#c4b5fd'
    case 'scheduler': return '#fdba74'
    case 'fanOut': return '#e2e8f0'
    default: return '#e2e8f0'
  }
}

// Column labels for each section
const briefingColumns = [
  { label: 'TRIGGER', color: '#f97316' },
  { label: 'DATA INPUT', color: '#3b82f6' },
  { label: 'AI AGENTS', color: '#10b981' },
  { label: 'OUTPUT', color: '#8b5cf6' },
]

const researchColumns = [
  { label: 'INPUT', color: '#3b82f6' },
  { label: 'GROOMER', color: '#10b981' },
  { label: 'FAN-OUT', color: '#6b7280' },
  { label: 'PARALLEL AGENTS', color: '#10b981' },
  { label: 'FAN-IN', color: '#6b7280' },
  { label: 'SYNTHESIS', color: '#10b981' },
  { label: 'VALIDATION', color: '#f59e0b' },
  { label: 'OUTPUT', color: '#8b5cf6' },
]

// SSE event sequence for Deep Research overlay
const sseEventSequence = [
  { event: 'node_start', node: 'groomer', time: '0.0s' },
  { event: 'node_complete', node: 'groomer', time: '2.1s' },
  { event: 'node_start', node: 'financial_research', time: '2.2s', parallel: true },
  { event: 'node_start', node: 'industry_research', time: '2.2s', parallel: true },
  { event: 'node_start', node: 'visual_research', time: '2.2s', parallel: true },
  { event: 'tool_progress', node: 'financial', time: '5s', detail: 'Searching earnings quotes...' },
  { event: 'tool_progress', node: 'industry', time: '6s', detail: 'Exa search: composites market...' },
  { event: 'node_complete', node: 'visual_research', time: '12s' },
  { event: 'tool_progress', node: 'financial', time: '18s', detail: 'Querying SEC nuggets...' },
  { event: 'node_complete', node: 'financial_research', time: '30s' },
  { event: 'node_complete', node: 'industry_research', time: '32s' },
  { event: 'node_start', node: 'synthesizer', time: '33s' },
  { event: 'node_complete', node: 'synthesizer', time: '55s' },
  { event: 'node_start', node: 'validator', time: '56s' },
  { event: 'node_complete', node: 'validator', time: '62s' },
  { event: 'report_saved', node: 'output', time: '63s', detail: 'report_id: abc123' },
]

// ────────────────────────────────────────────────
// Reusable Section Canvas component
// ────────────────────────────────────────────────
interface SectionCanvasProps {
  nodes: Node<ArchNodeData>[]
  edges: Edge[]
  columnLabels: { label: string; color: string }[]
  height: string
  selectedNode: ArchNodeData | null
  onNodeClick: (_event: React.MouseEvent, node: Node) => void
  onPaneClick: () => void
  onClose: () => void
  showSSE?: boolean
  sseEvents?: typeof sseEventSequence
}

function SectionCanvas({
  nodes,
  edges,
  columnLabels,
  height,
  selectedNode,
  onNodeClick,
  onPaneClick,
  onClose,
  showSSE,
  sseEvents,
}: SectionCanvasProps) {
  const [flowNodes, , onNodesChange] = useNodesState(nodes)
  const [flowEdges, , onEdgesChange] = useEdgesState(edges)

  return (
    <div className="relative" style={{ height }}>
      <ReactFlow
        nodes={flowNodes}
        edges={flowEdges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClick}
        onPaneClick={onPaneClick}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.18 }}
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

      {/* SSE Progress Overlay */}
      {showSSE && sseEvents && (
        <div className="absolute bottom-2 left-2 z-10 bg-slate-900/95 backdrop-blur-sm border border-slate-700 rounded-lg px-3 py-2 shadow-lg max-w-[340px] max-h-[220px] overflow-y-auto">
          <div className="text-[10px] font-bold text-emerald-400 uppercase tracking-wider mb-1.5 flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            SSE Event Stream
          </div>
          {sseEvents.map((evt, i) => (
            <div key={i} className="flex items-start gap-2 text-[10px] py-0.5 font-mono">
              <span className="text-slate-500 shrink-0 w-10 text-right">{evt.time}</span>
              <span className={`shrink-0 ${
                evt.event === 'node_start' ? 'text-sky-400' :
                evt.event === 'node_complete' ? 'text-emerald-400' :
                evt.event === 'tool_progress' ? 'text-amber-400' :
                'text-violet-400'
              }`}>
                {evt.event}
              </span>
              <span className="text-slate-300">
                {evt.node}
                {evt.parallel && <span className="text-orange-400 ml-1">⚡</span>}
              </span>
              {evt.detail && (
                <span className="text-slate-500 truncate">{evt.detail}</span>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Detail Panel */}
      <DetailPanel node={selectedNode} onClose={onClose} />
    </div>
  )
}

// ────────────────────────────────────────────────
// Main Agentic Workflow Diagram
// ────────────────────────────────────────────────
export default function AgenticWorkflowDiagram() {
  const [selectedNode, setSelectedNode] = useState<ArchNodeData | null>(null)
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({
    A: true,
    B: false,
  })
  const [showSSE, setShowSSE] = useState(false)

  const onNodeClick = useCallback((_event: React.MouseEvent, node: Node) => {
    setSelectedNode(node.data as ArchNodeData)
  }, [])

  const onPaneClick = useCallback(() => {
    setSelectedNode(null)
  }, [])

  const toggleSection = useCallback((section: string) => {
    setExpandedSections(prev => ({ ...prev, [section]: !prev[section] }))
  }, [])

  // Count expanded sections to determine sizing
  const expandedCount = Object.values(expandedSections).filter(Boolean).length
  const sectionHeight = expandedCount <= 1 ? 'calc(100vh - 280px)' : 'calc(50vh - 140px)'

  return (
    <div className="h-full flex flex-col overflow-y-auto">
      {/* SSE overlay toggle */}
      <div className="px-4 pt-3 pb-1 flex items-center justify-end">
        <button
          onClick={() => setShowSSE(!showSSE)}
          className={`
            flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all
            ${showSSE
              ? 'bg-emerald-100 text-emerald-700 border border-emerald-300'
              : 'bg-slate-100 text-slate-500 border border-slate-200 hover:bg-slate-200'
            }
          `}
        >
          <span className={`w-2 h-2 rounded-full ${showSSE ? 'bg-emerald-400 animate-pulse' : 'bg-slate-300'}`} />
          SSE Progress Overlay
        </button>
      </div>

      {/* Section A: Weekly Executive Briefing */}
      <div className="px-4 pt-1 pb-1">
        <SectionHeader
          letter="A"
          title="Weekly Executive Briefing"
          description="2-agent pipeline: scheduler → pre-brief → synthesis → podcast generation"
          color="orange"
          isExpanded={expandedSections.A}
          onToggle={() => toggleSection('A')}
          nodeCount={briefingNodes.length}
        />
      </div>
      {expandedSections.A && (
        <div className="px-2 section-content-enter">
          <SectionCanvas
            nodes={briefingNodes}
            edges={briefingEdges}
            columnLabels={briefingColumns}
            height={sectionHeight}
            selectedNode={selectedNode}
            onNodeClick={onNodeClick}
            onPaneClick={onPaneClick}
            onClose={() => setSelectedNode(null)}
          />
        </div>
      )}

      {/* Section B: Deep Research Multi-Agent System */}
      <div className="px-4 pt-2 pb-1">
        <SectionHeader
          letter="B"
          title="Deep Research Multi-Agent System"
          description="7-node LangGraph workflow with parallel fan-out → synthesis → validation (45-90s)"
          color="emerald"
          isExpanded={expandedSections.B}
          onToggle={() => toggleSection('B')}
          nodeCount={deepResearchNodes.length}
        />
      </div>
      {expandedSections.B && (
        <div className="px-2 pb-4 section-content-enter">
          <SectionCanvas
            nodes={deepResearchNodes}
            edges={deepResearchEdges}
            columnLabels={researchColumns}
            height={sectionHeight}
            selectedNode={selectedNode}
            onNodeClick={onNodeClick}
            onPaneClick={onPaneClick}
            onClose={() => setSelectedNode(null)}
            showSSE={showSSE}
            sseEvents={sseEventSequence}
          />
        </div>
      )}
    </div>
  )
}
