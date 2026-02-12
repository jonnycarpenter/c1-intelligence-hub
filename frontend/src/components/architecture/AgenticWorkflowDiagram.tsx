'use client'

import { useCallback, useState, useMemo, useEffect } from 'react'
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
import { adhocBriefingNodes } from './data/adhocBriefingNodes'
import { adhocBriefingEdges } from './data/adhocBriefingEdges'
import { pipelineNodes } from './data/pipelineNodes'
import { pipelineEdges } from './data/pipelineEdges'
import type { ArchNodeData } from './types'

// Path highlighting helpers
function getConnectedIds(selectedId: string | null, edges: Edge[]): Set<string> {
  if (!selectedId) return new Set()
  const connected = new Set<string>([selectedId])
  for (const e of edges) {
    if (e.source === selectedId) connected.add(e.target)
    if (e.target === selectedId) connected.add(e.source)
  }
  return connected
}

function applyHighlight<T extends Node>(
  nodes: T[],
  edges: Edge[],
  selectedId: string | null
): { highlightedNodes: T[]; highlightedEdges: Edge[] } {
  if (!selectedId) return { highlightedNodes: nodes, highlightedEdges: edges }
  const connected = getConnectedIds(selectedId, edges)
  const highlightedNodes = nodes.map((n) => ({
    ...n,
    style: { ...n.style, opacity: connected.has(n.id) ? 1 : 0.25, transition: 'opacity 0.3s ease' },
  }))
  const highlightedEdges = edges.map((e) => ({
    ...e,
    style: { ...e.style, opacity: e.source === selectedId || e.target === selectedId ? 1 : 0.12, transition: 'opacity 0.3s ease' },
    animated: e.source === selectedId || e.target === selectedId ? true : (e.animated ?? false),
  }))
  return { highlightedNodes, highlightedEdges }
}

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

const adhocColumns = [
  { label: 'TRIGGER', color: '#3b82f6' },
  { label: 'SESSION', color: '#0ea5e9' },
  { label: 'ROUTER', color: '#6b7280' },
  { label: 'DATA SOURCES', color: '#8b5cf6' },
  { label: 'SYNTHESIS', color: '#10b981' },
  { label: 'OUTPUT', color: '#6366f1' },
]

const pipelineColumns = [
  { label: 'INPUT', color: '#3b82f6' },
  { label: 'MODE', color: '#6b7280' },
  { label: 'MCP TOOLS', color: '#10b981' },
  { label: 'FILTER', color: '#f59e0b' },
  { label: 'OUTPUT', color: '#6366f1' },
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
// Animated SSE Replay Overlay
// ────────────────────────────────────────────────
function SSEReplayOverlay({ events }: { events: typeof sseEventSequence }) {
  const [visibleCount, setVisibleCount] = useState(0)
  const [isPlaying, setIsPlaying] = useState(false)
  const [isComplete, setIsComplete] = useState(false)
  const containerRef = useCallback((node: HTMLDivElement | null) => {
    if (node) node.scrollTop = node.scrollHeight
  }, [visibleCount]) // eslint-disable-line react-hooks/exhaustive-deps

  // Parse the time string (e.g. "2.1s", "30s") into seconds
  const parseSec = (t: string) => parseFloat(t.replace('s', ''))

  // Compute inter-event delays, compressed to ~15s total (63s real → ~4x speedup)
  const delays = useMemo(() => {
    const SPEEDUP = 4.2
    return events.map((evt, i) => {
      if (i === 0) return 300 // initial delay
      const prev = parseSec(events[i - 1].time)
      const curr = parseSec(evt.time)
      const delta = Math.max((curr - prev) * 1000 / SPEEDUP, 80)
      return delta
    })
  }, [events])

  useEffect(() => {
    if (!isPlaying || visibleCount >= events.length) {
      if (visibleCount >= events.length && isPlaying) {
        setIsPlaying(false)
        setIsComplete(true)
      }
      return
    }
    const timer = setTimeout(() => {
      setVisibleCount(c => c + 1)
    }, delays[visibleCount])
    return () => clearTimeout(timer)
  }, [isPlaying, visibleCount, events.length, delays])

  const handlePlay = () => {
    setVisibleCount(0)
    setIsComplete(false)
    setIsPlaying(true)
  }

  const handleReset = () => {
    setVisibleCount(0)
    setIsPlaying(false)
    setIsComplete(false)
  }

  const visibleEvents = events.slice(0, visibleCount)

  return (
    <div className="absolute bottom-2 left-2 z-10 bg-slate-900/95 backdrop-blur-sm border border-slate-700 rounded-lg shadow-lg max-w-[360px]">
      {/* Header with controls */}
      <div className="flex items-center justify-between px-3 pt-2 pb-1.5 border-b border-slate-700/50">
        <div className="text-[10px] font-bold text-emerald-400 uppercase tracking-wider flex items-center gap-1.5">
          {isPlaying && <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />}
          {isComplete && <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />}
          {!isPlaying && !isComplete && <span className="w-1.5 h-1.5 rounded-full bg-slate-500" />}
          SSE Event Stream
        </div>
        <div className="flex items-center gap-1.5">
          {!isPlaying ? (
            <button
              onClick={handlePlay}
              className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30 transition-colors"
            >
              {isComplete ? '↻ Replay' : '▶ Play'}
            </button>
          ) : (
            <button
              onClick={() => setIsPlaying(false)}
              className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-400 hover:bg-amber-500/30 transition-colors"
            >
              ⏸ Pause
            </button>
          )}
          {visibleCount > 0 && (
            <button
              onClick={handleReset}
              className="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-500/20 text-slate-400 hover:bg-slate-500/30 transition-colors"
            >
              Reset
            </button>
          )}
        </div>
      </div>

      {/* Progress bar */}
      <div className="h-0.5 bg-slate-800">
        <div
          className="h-full bg-emerald-400 transition-all duration-300 ease-out"
          style={{ width: `${(visibleCount / events.length) * 100}%` }}
        />
      </div>

      {/* Event stream */}
      <div ref={containerRef} className="px-3 py-2 max-h-[180px] overflow-y-auto">
        {visibleEvents.length === 0 && !isPlaying && (
          <div className="text-[10px] text-slate-500 text-center py-2">
            Press Play to replay a real 63-second deep research run
          </div>
        )}
        {visibleEvents.map((evt, i) => (
          <div
            key={i}
            className="flex items-start gap-2 text-[10px] py-0.5 font-mono animate-[fadeIn_0.2s_ease-out]"
          >
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
        {isComplete && (
          <div className="flex items-center gap-1.5 text-[10px] py-1 mt-1 border-t border-slate-700/50 text-emerald-400 font-bold">
            <span>✓</span>
            <span>Complete — 63s real-time → {Math.round(events.length * 0.9)}s replay</span>
          </div>
        )}
      </div>
    </div>
  )
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
  showSSE?: boolean
  sseEvents?: typeof sseEventSequence
  focusNodeId?: string | null
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
  focusNodeId,
}: SectionCanvasProps) {
  const [flowNodes, , onNodesChange] = useNodesState(nodes)
  const [flowEdges, , onEdgesChange] = useEdgesState(edges)

  // Path highlighting
  const selectedId = selectedNode ? nodes.find(n => n.data.label === selectedNode.label)?.id ?? null : null
  const { highlightedNodes, highlightedEdges } = useMemo(
    () => applyHighlight(flowNodes, flowEdges, selectedId),
    [flowNodes, flowEdges, selectedId]
  )

  // Auto-select focused node from search
  useEffect(() => {
    if (focusNodeId) {
      const match = nodes.find(n => n.id === focusNodeId)
      if (match) {
        onNodeClick({} as React.MouseEvent, match)
      }
    }
  }, [focusNodeId, nodes, onNodeClick])

  return (
    <div className="relative" style={{ height }}>
      <ReactFlow
        nodes={selectedId ? highlightedNodes : flowNodes}
        edges={selectedId ? highlightedEdges : flowEdges}
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

      {/* SSE Animated Replay Overlay */}
      {showSSE && sseEvents && (
        <SSEReplayOverlay events={sseEvents} />
      )}

      {/* Detail Panel */}
      <DetailPanel node={selectedNode} onClose={onClose} />
    </div>
  )
}

// ────────────────────────────────────────────────
// Main Agentic Workflow Diagram
// ────────────────────────────────────────────────
interface AgenticWorkflowDiagramProps {
  focusNodeId?: string | null
  focusSection?: string | null
}

export default function AgenticWorkflowDiagram({ focusNodeId, focusSection }: AgenticWorkflowDiagramProps) {
  const [selectedNode, setSelectedNode] = useState<ArchNodeData | null>(null)
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({
    A: false,
    B: false,
    C: false,
    D: false,
  })
  const [showSSE, setShowSSE] = useState(false)

  // Auto-expand section when triggered from search
  useEffect(() => {
    if (focusSection && !expandedSections[focusSection]) {
      setExpandedSections(prev => ({ ...prev, [focusSection]: true }))
    }
  }, [focusSection]) // eslint-disable-line react-hooks/exhaustive-deps

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
  const sectionHeight =
    expandedCount <= 1
      ? 'calc(100vh - 280px)'
      : expandedCount === 2
        ? 'calc(50vh - 140px)'
        : 'calc(33vh - 100px)'

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
            focusNodeId={focusSection === 'A' ? focusNodeId : null}
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
            focusNodeId={focusSection === 'B' ? focusNodeId : null}
          />
        </div>
      )}

      {/* Section C: Ad-Hoc Briefing Agent */}
      <div className="px-4 pt-2 pb-1">
        <SectionHeader
          letter="C"
          title="Ad-Hoc Briefing Agent"
          description="Multi-source synthesis: 6 parallel searches → Claude Opus streaming response"
          color="sky"
          isExpanded={expandedSections.C}
          onToggle={() => toggleSection('C')}
          nodeCount={adhocBriefingNodes.length}
        />
      </div>
      {expandedSections.C && (
        <div className="px-2 pb-4 section-content-enter">
          <SectionCanvas
            nodes={adhocBriefingNodes}
            edges={adhocBriefingEdges}
            columnLabels={adhocColumns}
            height={sectionHeight}
            selectedNode={selectedNode}
            onNodeClick={onNodeClick}
            onPaneClick={onPaneClick}
            onClose={() => setSelectedNode(null)}
            focusNodeId={focusSection === 'C' ? focusNodeId : null}
          />
        </div>
      )}

      {/* Section D: Pipeline Sales Prospecting Agent */}
      <div className="px-4 pt-2 pb-1">
        <SectionHeader
          letter="D"
          title="Pipeline Sales Prospecting Agent"
          description="Multi-tool prospecting: Exa + Apollo + BigQuery enrichment → filtered results"
          color="violet"
          isExpanded={expandedSections.D}
          onToggle={() => toggleSection('D')}
          nodeCount={pipelineNodes.length}
        />
      </div>
      {expandedSections.D && (
        <div className="px-2 pb-4 section-content-enter">
          <SectionCanvas
            nodes={pipelineNodes}
            edges={pipelineEdges}
            columnLabels={pipelineColumns}
            height={sectionHeight}
            selectedNode={selectedNode}
            onNodeClick={onNodeClick}
            onPaneClick={onPaneClick}
            onClose={() => setSelectedNode(null)}
            focusNodeId={focusSection === 'D' ? focusNodeId : null}
          />
        </div>
      )}
    </div>
  )
}
