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
  type Edge,
  BackgroundVariant,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'

import { DataSourceNode, ProcessingNode, AgentNode, StorageNode, SchedulerNode, FanOutNode, OrchestratorNode } from './nodes'
import DetailPanel from './DetailPanel'
import SectionHeader from './SectionHeader'
import { ingestionSectionANodes } from './data/ingestionNodes'
import { ingestionSectionAEdges } from './data/ingestionEdges'
import { secEarningsNodes } from './data/secEarningsNodes'
import { secEarningsEdges } from './data/secEarningsEdges'
import { podcastNodes } from './data/podcastNodes'
import { podcastEdges } from './data/podcastEdges'
import { importYetiNodes } from './data/importYetiNodes'
import { importYetiEdges } from './data/importYetiEdges'
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

// Minimap color resolver shared across all sections
function minimapColor(node: Node) {
  switch (node.type) {
    case 'dataSource': return '#93c5fd'
    case 'processing': return '#fcd34d'
    case 'agent': return '#6ee7b7'
    case 'storage': return '#c4b5fd'
    case 'orchestrator': return '#7dd3fc'
    default: return '#e2e8f0'
  }
}

// Column labels per section
const sectionAColumns = [
  { label: 'DATA SOURCES', color: '#3b82f6' },
  { label: 'ORCHESTRATOR', color: '#0ea5e9' },
  { label: 'PROCESSING PIPELINE', color: '#f59e0b' },
  { label: 'BIGQUERY STORAGE', color: '#8b5cf6' },
  { label: 'POST-PROCESSING', color: '#a78bfa' },
]

const sectionBColumns = [
  { label: 'COLLECTION', color: '#3b82f6' },
  { label: 'AI EXTRACTION', color: '#10b981' },
  { label: 'BIGQUERY STORAGE', color: '#8b5cf6' },
  { label: 'DOWNSTREAM', color: '#a78bfa' },
]

const sectionCColumns = [
  { label: 'DISCOVERY', color: '#3b82f6' },
  { label: 'RESOLUTION', color: '#f59e0b' },
  { label: 'AI EXTRACTION', color: '#10b981' },
  { label: 'BIGQUERY STORAGE', color: '#8b5cf6' },
  { label: 'DOWNSTREAM', color: '#a78bfa' },
]

const sectionDColumns = [
  { label: 'CONFIG', color: '#3b82f6' },
  { label: 'PIPELINE PHASES', color: '#f59e0b' },
  { label: 'BIGQUERY STORAGE', color: '#8b5cf6' },
  { label: 'VIEWS & FRONTEND', color: '#a78bfa' },
]

// Scheduler overlay data
const schedulerAnnotations: Record<string, string> = {
  'src-rss': 'Every 4h (ingest-flash-update)',
  'src-exa': '2:00 AM CST (ingest-exa)',
  'src-tavily': '2:20 AM CST (ingest-tavily)',
  'src-sec': '2:45 AM CST (ingest-financial)',
  'src-earnings': '2:45 AM CST (ingest-financial)',
  'src-stocknews': '4h (collect-stock-news)',
  'src-fmp': '2:45 AM CST (ingest-financial)',
  'src-freight': 'Every 4h (ingest-flash-update)',
}

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
  showScheduler?: boolean
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
  showScheduler,
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

      {/* Scheduler annotations overlay */}
      {showScheduler && (
        <div className="absolute bottom-2 left-2 z-10 bg-orange-50/95 backdrop-blur-sm border border-orange-200 rounded-lg px-3 py-2 shadow-sm max-w-[280px]">
          <div className="text-[10px] font-bold text-orange-600 uppercase tracking-wider mb-1.5">
            Cloud Scheduler Jobs
          </div>
          {Object.entries(schedulerAnnotations).map(([nodeId, schedule]) => (
            <div key={nodeId} className="flex items-center gap-1.5 text-[10px] text-slate-600 py-0.5">
              <span className="w-1.5 h-1.5 rounded-full bg-orange-400 shrink-0" />
              <span className="font-medium text-slate-700">{nodeId.replace('src-', '').toUpperCase()}</span>
              <span className="text-slate-400">·</span>
              <span>{schedule}</span>
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
// Main Ingestion Flow Diagram
// ────────────────────────────────────────────────
export default function IngestionFlowDiagram() {
  const [selectedNode, setSelectedNode] = useState<ArchNodeData | null>(null)
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({
    A: true,
    B: false,
    C: false,
    D: false,
  })
  const [showScheduler, setShowScheduler] = useState(false)

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

  // Dynamic height: distribute available space
  const sectionHeight = expandedCount <= 1 ? 'calc(100vh - 280px)' : expandedCount === 2 ? 'calc(50vh - 140px)' : '380px'

  return (
    <div className="h-full flex flex-col overflow-y-auto">
      {/* Scheduler toggle */}
      <div className="px-4 pt-3 pb-1 flex items-center justify-end">
        <button
          onClick={() => setShowScheduler(!showScheduler)}
          className={`
            flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all
            ${showScheduler
              ? 'bg-orange-100 text-orange-700 border border-orange-300'
              : 'bg-slate-100 text-slate-500 border border-slate-200 hover:bg-slate-200'
            }
          `}
        >
          <span className={`w-2 h-2 rounded-full ${showScheduler ? 'bg-orange-400' : 'bg-slate-300'}`} />
          Scheduler Overlay
        </button>
      </div>

      {/* Section A: Core Article Ingestion */}
      <div className="px-4 pt-1 pb-1">
        <SectionHeader
          letter="A"
          title="Core Article Ingestion"
          description="10 sources → orchestrator → processing pipeline → BigQuery storage"
          color="sky"
          isExpanded={expandedSections.A}
          onToggle={() => toggleSection('A')}
          nodeCount={ingestionSectionANodes.length}
        />
      </div>
      {expandedSections.A && (
        <div className="px-2 section-content-enter">
          <SectionCanvas
            nodes={ingestionSectionANodes}
            edges={ingestionSectionAEdges}
            columnLabels={sectionAColumns}
            height={sectionHeight}
            selectedNode={selectedNode}
            onNodeClick={onNodeClick}
            onPaneClick={onPaneClick}
            onClose={() => setSelectedNode(null)}
            showScheduler={showScheduler}
          />
        </div>
      )}

      {/* Section B: SEC Filings & Earnings Transcripts */}
      <div className="px-4 pt-2 pb-1">
        <SectionHeader
          letter="B"
          title="SEC Filings & Earnings Transcripts"
          description="Financial disclosures → AI extraction → strategic nuggets & executive quotes"
          color="amber"
          isExpanded={expandedSections.B}
          onToggle={() => toggleSection('B')}
          nodeCount={secEarningsNodes.length}
        />
      </div>
      {expandedSections.B && (
        <div className="px-2 section-content-enter">
          <SectionCanvas
            nodes={secEarningsNodes}
            edges={secEarningsEdges}
            columnLabels={sectionBColumns}
            height={sectionHeight}
            selectedNode={selectedNode}
            onNodeClick={onNodeClick}
            onPaneClick={onPaneClick}
            onClose={() => setSelectedNode(null)}
          />
        </div>
      )}

      {/* Section C: Expert Podcast Intelligence */}
      <div className="px-4 pt-2 pb-1">
        <SectionHeader
          letter="C"
          title="Expert Podcast Intelligence"
          description="Podcast RSS → transcript resolution → speaker-attributed quote extraction"
          color="emerald"
          isExpanded={expandedSections.C}
          onToggle={() => toggleSection('C')}
          nodeCount={podcastNodes.length}
        />
      </div>
      {expandedSections.C && (
        <div className="px-2 section-content-enter">
          <SectionCanvas
            nodes={podcastNodes}
            edges={podcastEdges}
            columnLabels={sectionCColumns}
            height={sectionHeight}
            selectedNode={selectedNode}
            onNodeClick={onNodeClick}
            onPaneClick={onPaneClick}
            onClose={() => setSelectedNode(null)}
          />
        </div>
      )}

      {/* Section D: ImportYeti Supply Chain Network */}
      <div className="px-4 pt-2 pb-1">
        <SectionHeader
          letter="D"
          title="ImportYeti Supply Chain Network"
          description="4-phase pipeline → company resolution → supplier discovery → network graph"
          color="violet"
          isExpanded={expandedSections.D}
          onToggle={() => toggleSection('D')}
          nodeCount={importYetiNodes.length}
        />
      </div>
      {expandedSections.D && (
        <div className="px-2 pb-4 section-content-enter">
          <SectionCanvas
            nodes={importYetiNodes}
            edges={importYetiEdges}
            columnLabels={sectionDColumns}
            height={sectionHeight}
            selectedNode={selectedNode}
            onNodeClick={onNodeClick}
            onPaneClick={onPaneClick}
            onClose={() => setSelectedNode(null)}
          />
        </div>
      )}
    </div>
  )
}
