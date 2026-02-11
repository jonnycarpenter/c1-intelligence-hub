'use client'

import { useState, useEffect } from 'react'
import { X, FileCode, Cpu, Database, Globe, ArrowRight, ArrowLeft, ScrollText, DollarSign, BarChart3 } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import type { ArchNodeData, ArchNodeType } from './types'
import PromptModal from './PromptModal'

// Color mapping for node type indicators in detail panel header
const nodeTypeColors: Record<ArchNodeType, { dot: string; bg: string; text: string }> = {
  dataSource: { dot: 'bg-blue-400', bg: 'bg-blue-50/50', text: 'text-blue-500' },
  processing: { dot: 'bg-amber-400', bg: 'bg-amber-50/50', text: 'text-amber-500' },
  agent: { dot: 'bg-emerald-400', bg: 'bg-emerald-50/50', text: 'text-emerald-500' },
  storage: { dot: 'bg-violet-400', bg: 'bg-violet-50/50', text: 'text-violet-500' },
  scheduler: { dot: 'bg-orange-400', bg: 'bg-orange-50/50', text: 'text-orange-500' },
  fanOut: { dot: 'bg-slate-400', bg: 'bg-slate-50/50', text: 'text-slate-500' },
  externalApi: { dot: 'bg-rose-400', bg: 'bg-rose-50/50', text: 'text-rose-500' },
  gcpService: { dot: 'bg-sky-400', bg: 'bg-sky-50/50', text: 'text-sky-500' },
  tabNode: { dot: 'bg-cyan-400', bg: 'bg-cyan-50/50', text: 'text-cyan-500' },
}

interface DetailPanelProps {
  node: ArchNodeData | null
  onClose: () => void
}

export default function DetailPanel({ node, onClose }: DetailPanelProps) {
  const [promptOpen, setPromptOpen] = useState(false)

  // Close modal on Esc
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && promptOpen) {
        setPromptOpen(false)
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [promptOpen])

  // Reset modal when node changes
  useEffect(() => {
    setPromptOpen(false)
  }, [node])

  return (
    <AnimatePresence>
      {node && (
        <motion.div
          initial={{ x: '100%', opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          exit={{ x: '100%', opacity: 0 }}
          transition={{ type: 'spring', damping: 25, stiffness: 300 }}
          className="absolute top-0 right-0 h-full w-[380px] bg-white border-l border-slate-200 shadow-xl z-50 flex flex-col overflow-hidden"
        >
          {/* Header */}
          <div className={`flex items-center justify-between px-5 py-4 border-b border-slate-100 ${nodeTypeColors[node.nodeType]?.bg || 'bg-slate-50/50'}`}>
            <div className="flex items-center gap-3">
              <div className={`w-2.5 h-2.5 rounded-full ${nodeTypeColors[node.nodeType]?.dot || 'bg-slate-400'} shrink-0`} />
              <div>
                <h3 className="text-sm font-bold text-slate-800">{node.label}</h3>
                <span className={`text-[10px] font-medium uppercase tracking-wider ${nodeTypeColors[node.nodeType]?.text || 'text-slate-400'}`}>
                  {node.nodeType.replace(/([A-Z])/g, ' $1').trim()}
                </span>
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg hover:bg-slate-200 text-slate-400 hover:text-slate-600 transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto px-5 py-4 space-y-5">
            {/* Description */}
            <div>
              <p className="text-sm text-slate-600 leading-relaxed">{node.description}</p>
            </div>

            {/* Technical Details */}
            {node.technicalDetails && (
              <div className="space-y-3">
                <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                  Technical Details
                </h4>

                {node.technicalDetails.model && (
                  <div className="flex items-start gap-2">
                    <Cpu className="w-3.5 h-3.5 text-emerald-500 mt-0.5 shrink-0" />
                    <div>
                      <span className="text-[10px] font-medium text-slate-400 uppercase">Model</span>
                      <p className="text-xs text-slate-700 font-mono">{node.technicalDetails.model}</p>
                    </div>
                  </div>
                )}

                {node.technicalDetails.sourceFiles && node.technicalDetails.sourceFiles.length > 0 && (
                  <div className="flex items-start gap-2">
                    <FileCode className="w-3.5 h-3.5 text-blue-500 mt-0.5 shrink-0" />
                    <div>
                      <span className="text-[10px] font-medium text-slate-400 uppercase">Source Files</span>
                      {node.technicalDetails.sourceFiles.map((file, i) => (
                        <p key={i} className="text-xs text-slate-700 font-mono">{file}</p>
                      ))}
                    </div>
                  </div>
                )}

                {node.technicalDetails.functions && node.technicalDetails.functions.length > 0 && (
                  <div className="flex items-start gap-2">
                    <FileCode className="w-3.5 h-3.5 text-purple-500 mt-0.5 shrink-0" />
                    <div>
                      <span className="text-[10px] font-medium text-slate-400 uppercase">Key Functions</span>
                      {node.technicalDetails.functions.map((fn, i) => (
                        <p key={i} className="text-xs text-slate-700 font-mono">{fn}</p>
                      ))}
                    </div>
                  </div>
                )}

                {node.technicalDetails.tables && node.technicalDetails.tables.length > 0 && (
                  <div className="flex items-start gap-2">
                    <Database className="w-3.5 h-3.5 text-violet-500 mt-0.5 shrink-0" />
                    <div>
                      <span className="text-[10px] font-medium text-slate-400 uppercase">BigQuery Tables</span>
                      {node.technicalDetails.tables.map((table, i) => (
                        <p key={i} className="text-xs text-slate-700 font-mono">{table}</p>
                      ))}
                    </div>
                  </div>
                )}

                {node.technicalDetails.apis && node.technicalDetails.apis.length > 0 && (
                  <div className="flex items-start gap-2">
                    <Globe className="w-3.5 h-3.5 text-slate-500 mt-0.5 shrink-0" />
                    <div>
                      <span className="text-[10px] font-medium text-slate-400 uppercase">APIs</span>
                      {node.technicalDetails.apis.map((api, i) => (
                        <p key={i} className="text-xs text-slate-700 font-mono">{api}</p>
                      ))}
                    </div>
                  </div>
                )}

                {node.technicalDetails.cost && (
                  <div className="flex items-start gap-2">
                    <DollarSign className="w-3.5 h-3.5 text-green-500 mt-0.5 shrink-0" />
                    <div>
                      <span className="text-[10px] font-medium text-slate-400 uppercase">Cost per Run</span>
                      <p className="text-xs text-slate-700 font-mono">{node.technicalDetails.cost}</p>
                    </div>
                  </div>
                )}

                {node.technicalDetails.dataVolume && (
                  <div className="flex items-start gap-2">
                    <BarChart3 className="w-3.5 h-3.5 text-indigo-500 mt-0.5 shrink-0" />
                    <div>
                      <span className="text-[10px] font-medium text-slate-400 uppercase">Data Volume</span>
                      <p className="text-xs text-slate-700 font-mono">{node.technicalDetails.dataVolume}</p>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* View System Prompt */}
            {node.prompt && (
              <button
                onClick={() => setPromptOpen(true)}
                className="flex items-center gap-2 w-full px-3 py-2.5 rounded-lg bg-indigo-50 hover:bg-indigo-100 border border-indigo-200/60 transition-colors group"
              >
                <ScrollText className="w-4 h-4 text-indigo-500 group-hover:text-indigo-600 shrink-0" />
                <span className="text-xs font-medium text-indigo-600 group-hover:text-indigo-700">
                  View System Prompt
                </span>
                <span className="ml-auto text-[10px] text-indigo-400">
                  {node.prompt.length.toLocaleString()} chars
                </span>
              </button>
            )}

            {/* Connections */}
            {node.connections && (
              <div className="space-y-3">
                <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                  Connections
                </h4>

                {node.connections.incoming && node.connections.incoming.length > 0 && (
                  <div className="space-y-1">
                    {node.connections.incoming.map((conn, i) => (
                      <div key={i} className="flex items-center gap-2 text-xs text-slate-600">
                        <ArrowRight className="w-3 h-3 text-green-500" />
                        <span>{conn}</span>
                      </div>
                    ))}
                  </div>
                )}

                {node.connections.outgoing && node.connections.outgoing.length > 0 && (
                  <div className="space-y-1">
                    {node.connections.outgoing.map((conn, i) => (
                      <div key={i} className="flex items-center gap-2 text-xs text-slate-600">
                        <ArrowLeft className="w-3 h-3 text-blue-500" />
                        <span>{conn}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </motion.div>
      )}

      {/* Prompt Modal (rendered outside the slide-in panel) */}
      {node?.prompt && (
        <PromptModal
          isOpen={promptOpen}
          onClose={() => setPromptOpen(false)}
          agentName={node.label}
          prompt={node.prompt}
        />
      )}
    </AnimatePresence>
  )
}
