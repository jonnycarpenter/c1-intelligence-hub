'use client'

import { useState } from 'react'
import { Database, Layout, Bot } from 'lucide-react'
import { cn } from '@/lib/utils'
import dynamic from 'next/dynamic'
import type { ArchSubTab } from './types'

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

export default function ArchitectureDashboard() {
  const [activeSubTab, setActiveSubTab] = useState<ArchSubTab>('ingestion')

  return (
    <div className="h-full flex flex-col bg-white">
      {/* Sub-tab navigation bar */}
      <div className="flex items-center gap-1 px-4 pt-3 pb-2 border-b border-slate-100 bg-slate-50/50">
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
      </div>

      {/* Sub-tab content */}
      <div className="flex-1 overflow-hidden">
        <div key={activeSubTab} className="h-full animate-tab-enter">
          {activeSubTab === 'ingestion' && <IngestionFlowDiagram />}
          {activeSubTab === 'tab-architecture' && <TabArchitectureDiagram />}
          {activeSubTab === 'agentic-workflows' && <AgenticWorkflowDiagram />}
        </div>
      </div>
    </div>
  )
}
