'use client'

import { useState, useEffect, useMemo, useCallback } from 'react'
import { Database, Layout, Bot, Search } from 'lucide-react'
import { cn } from '@/lib/utils'
import dynamic from 'next/dynamic'
import type { ArchSubTab } from './types'
import SearchPalette, { type SearchableNode } from './SearchPalette'
import NodeLegend from './NodeLegend'

// Import all node data for the search index
import { ingestionSectionANodes } from './data/ingestionNodes'
import { secEarningsNodes } from './data/secEarningsNodes'
import { podcastNodes } from './data/podcastNodes'
import { importYetiNodes } from './data/importYetiNodes'
import { tabArchitectureNodes } from './data/tabArchitectureNodes'
import { briefingNodes, deepResearchNodes } from './data/agenticNodes'
import { adhocBriefingNodes } from './data/adhocBriefingNodes'
import { pipelineNodes } from './data/pipelineNodes'

// Dynamic imports for React Flow (requires browser DOM)
const IngestionFlowDiagram = dynamic(() => import('./IngestionFlowDiagram'), {
  ssr: false,
  loading: () => (
    <div className="h-full flex items-center justify-center">
      <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-sky-500" />
    </div>
  ),
})

const TabArchitectureDiagram = dynamic(() => import('./TabArchitectureDiagram'), {
  ssr: false,
  loading: () => (
    <div className="h-full flex items-center justify-center">
      <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-sky-500" />
    </div>
  ),
})

const AgenticWorkflowDiagram = dynamic(() => import('./AgenticWorkflowDiagram'), {
  ssr: false,
  loading: () => (
    <div className="h-full flex items-center justify-center">
      <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-emerald-500" />
    </div>
  ),
})

const subTabs: { id: ArchSubTab; label: string; icon: typeof Database; description: string }[] = [
  { id: 'ingestion', label: 'Data Ingestion', icon: Database, description: 'Interactive pipeline diagrams' },
  { id: 'tab-architecture', label: 'Tab Architecture', icon: Layout, description: 'Frontend data flows + GCP' },
  { id: 'agentic-workflows', label: 'Agentic Workflows', icon: Bot, description: 'Multi-agent systems' },
]

// ── Stats banner data (static production metrics) ──
const stats = [
  { label: 'Nodes', value: '115' },
  { label: 'Articles Ingested', value: '5,200+' },
  { label: 'BigQuery Tables', value: '20+' },
  { label: 'MCP Tools', value: '48' },
  { label: 'GCP Services', value: '10' },
  { label: 'AI Agents', value: '9' },
  { label: 'Data Sources', value: '10' },
]

// ── Build the global search index ──
function buildSearchIndex(): SearchableNode[] {
  const nodes: SearchableNode[] = []

  const addNodes = (list: typeof ingestionSectionANodes, tab: ArchSubTab, section?: string) => {
    for (const n of list) {
      nodes.push({
        id: n.id,
        label: n.data.label,
        nodeType: n.data.nodeType,
        description: n.data.description,
        tab,
        section: section || n.data.section,
        badge: n.data.badge,
      })
    }
  }

  addNodes(ingestionSectionANodes, 'ingestion', 'A')
  addNodes(secEarningsNodes, 'ingestion', 'B')
  addNodes(podcastNodes, 'ingestion', 'C')
  addNodes(importYetiNodes, 'ingestion', 'D')
  addNodes(tabArchitectureNodes, 'tab-architecture')
  addNodes(briefingNodes, 'agentic-workflows', 'A')
  addNodes(deepResearchNodes, 'agentic-workflows', 'B')
  addNodes(adhocBriefingNodes, 'agentic-workflows', 'C')
  addNodes(pipelineNodes, 'agentic-workflows', 'D')

  return nodes
}

export default function ArchitectureDashboard() {
  const [activeSubTab, setActiveSubTab] = useState<ArchSubTab>('ingestion')
  const [searchOpen, setSearchOpen] = useState(false)
  // Navigation target: when user selects from search, we set this to tell the child diagram to focus a node
  const [focusNodeId, setFocusNodeId] = useState<string | null>(null)
  // Section to auto-expand (for ingestion/agentic tabs)
  const [focusSection, setFocusSection] = useState<string | null>(null)

  const searchIndex = useMemo(() => buildSearchIndex(), [])

  // ── Keyboard shortcut: Ctrl+K / Cmd+K ──
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        setSearchOpen(true)
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  // ── Handle search selection ──
  const handleSearchSelect = useCallback((node: SearchableNode) => {
    // Switch to the correct tab
    setActiveSubTab(node.tab)
    // If the node is in a collapsible section, expand it
    if (node.section) {
      setFocusSection(node.section)
    }
    // Tell the diagram to focus this node
    setFocusNodeId(node.id)
    // Clear focus after a short delay so repeated clicks on same node still work
    setTimeout(() => {
      setFocusNodeId(null)
      setFocusSection(null)
    }, 500)
  }, [])

  return (
    <div className="h-full flex flex-col bg-white">
      {/* Stats banner */}
      <div className="flex items-center gap-4 px-4 pt-2.5 pb-1.5 bg-gradient-to-r from-slate-50 to-white border-b border-slate-100/60">
        <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest shrink-0">System Scale</span>
        <div className="flex items-center gap-3 overflow-x-auto">
          {stats.map((s) => (
            <div key={s.label} className="flex items-center gap-1.5 shrink-0">
              <span className="text-sm font-bold text-slate-800">{s.value}</span>
              <span className="text-[10px] text-slate-400 font-medium">{s.label}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Sub-tab navigation bar */}
      <div className="flex items-center gap-1 px-4 pt-2 pb-2 border-b border-slate-100 bg-slate-50/50">
        {subTabs.map((tab) => {
          const Icon = tab.icon
          const isActive = activeSubTab === tab.id
          return (
            <button
              key={tab.id}
              onClick={() => setActiveSubTab(tab.id)}
              className={cn(
                'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-150',
                isActive
                  ? 'bg-white text-slate-800 shadow-sm border border-slate-200'
                  : 'text-slate-500 hover:text-slate-700 hover:bg-slate-100'
              )}
            >
              <Icon className={cn('w-4 h-4', isActive ? 'text-sky-500' : 'text-slate-400')} />
              <span>{tab.label}</span>
              {!isActive && (
                <span className="hidden md:inline text-xs text-slate-400 ml-1">· {tab.description}</span>
              )}
            </button>
          )
        })}

        {/* Right side: search + legend */}
        <div className="ml-auto flex items-center gap-2">
          <button
            onClick={() => setSearchOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-100 text-slate-500 border border-slate-200 hover:bg-slate-200 transition-all"
          >
            <Search className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Search</span>
            <kbd className="hidden sm:inline ml-1 px-1 py-0.5 rounded border border-slate-200 bg-slate-50 text-[10px] text-slate-400 font-mono">
              ⌘K
            </kbd>
          </button>
          <NodeLegend />
        </div>
      </div>

      {/* Sub-tab content */}
      <div className="flex-1 overflow-hidden">
        <div key={activeSubTab} className="h-full animate-tab-enter">
          {activeSubTab === 'ingestion' && (
            <IngestionFlowDiagram focusNodeId={focusNodeId} focusSection={focusSection} />
          )}
          {activeSubTab === 'tab-architecture' && (
            <TabArchitectureDiagram focusNodeId={focusNodeId} />
          )}
          {activeSubTab === 'agentic-workflows' && (
            <AgenticWorkflowDiagram focusNodeId={focusNodeId} focusSection={focusSection} />
          )}
        </div>
      </div>

      {/* Global search palette */}
      <SearchPalette
        isOpen={searchOpen}
        onClose={() => setSearchOpen(false)}
        nodes={searchIndex}
        onSelect={handleSearchSelect}
      />
    </div>
  )
}
