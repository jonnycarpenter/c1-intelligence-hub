'use client'

import { useState } from 'react'
import { Info, X } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'

const legendItems = [
  { type: 'Data Source',   color: 'bg-blue-400',    border: 'border-blue-300',    shape: 'Rounded rect' },
  { type: 'Processing',    color: 'bg-amber-400',   border: 'border-amber-300',   shape: 'Rectangle' },
  { type: 'AI Agent',      color: 'bg-emerald-400', border: 'border-emerald-300', shape: 'Rounded + glow' },
  { type: 'Storage (BQ)',  color: 'bg-violet-400',  border: 'border-violet-300',  shape: 'Rounded-xl' },
  { type: 'Scheduler',     color: 'bg-orange-400',  border: 'border-orange-300',  shape: 'Hexagon' },
  { type: 'Fan-Out/In',    color: 'bg-slate-400',   border: 'border-slate-300',   shape: 'Circle' },
  { type: 'GCP Service',   color: 'bg-[#4285F4]',   border: 'border-[#a8c7fa]',   shape: 'Google Blue' },
  { type: 'Frontend Tab',  color: 'bg-cyan-400',    border: 'border-cyan-300',    shape: 'Cyan bar' },
  { type: 'Orchestrator',  color: 'bg-sky-400',     border: 'border-sky-300',     shape: 'Pulsing ring' },
]

interface NodeLegendProps {
  className?: string
}

export default function NodeLegend({ className = '' }: NodeLegendProps) {
  const [isOpen, setIsOpen] = useState(false)

  return (
    <div className={`relative ${className}`}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`
          flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all
          ${isOpen
            ? 'bg-slate-200 text-slate-700 border border-slate-300'
            : 'bg-slate-100 text-slate-500 border border-slate-200 hover:bg-slate-200'
          }
        `}
      >
        <Info className="w-3.5 h-3.5" />
        Legend
      </button>

      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: -4, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -4, scale: 0.97 }}
            transition={{ duration: 0.15 }}
            className="absolute top-full right-0 mt-1.5 z-[60] bg-white border border-slate-200 rounded-lg shadow-lg p-3 w-[220px]"
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Node Types</span>
              <button onClick={() => setIsOpen(false)} className="p-0.5 hover:bg-slate-100 rounded">
                <X className="w-3 h-3 text-slate-400" />
              </button>
            </div>
            <div className="space-y-1.5">
              {legendItems.map((item) => (
                <div key={item.type} className="flex items-center gap-2">
                  <div className={`w-3 h-3 rounded-sm ${item.color} shrink-0`} />
                  <span className="text-[11px] text-slate-700 font-medium">{item.type}</span>
                </div>
              ))}
            </div>
            <div className="mt-2.5 pt-2 border-t border-slate-100">
              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Edge Styles</span>
              <div className="mt-1.5 space-y-1.5">
                <div className="flex items-center gap-2">
                  <div className="w-6 h-0 border-t-2 border-sky-400 shrink-0" />
                  <span className="text-[11px] text-slate-600">Data flow (animated)</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-6 h-0 border-t-2 border-dashed border-emerald-400 shrink-0" />
                  <span className="text-[11px] text-slate-600">Parallel execution</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-6 h-0 border-t-2 border-dotted border-gray-400 shrink-0" />
                  <span className="text-[11px] text-slate-600">IAM / Permissions</span>
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
