'use client'

import { X, FileCode, Cpu, Database, Globe, ArrowRight, ArrowLeft } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import type { ArchNodeData } from './types'

interface DetailPanelProps {
  node: ArchNodeData | null
  onClose: () => void
}

export default function DetailPanel({ node, onClose }: DetailPanelProps) {
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
          <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100 bg-slate-50/50">
            <div>
              <h3 className="text-sm font-bold text-slate-800">{node.label}</h3>
              <span className="text-[10px] font-medium uppercase tracking-wider text-slate-400">
                {node.nodeType.replace(/([A-Z])/g, ' $1').trim()}
              </span>
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
              </div>
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
    </AnimatePresence>
  )
}
