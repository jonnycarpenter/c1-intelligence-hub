'use client'

import { useState, useEffect, useRef, useMemo, useCallback } from 'react'
import { Search, X, Database, Cpu, Brain, HardDrive, Clock, GitFork, Globe, Cloud, Layout } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import type { ArchNodeData, ArchNodeType, ArchSubTab } from './types'
import type { Node } from '@xyflow/react'

// Icon + color mapping per node type
const nodeTypeMeta: Record<ArchNodeType, { icon: typeof Database; color: string; label: string }> = {
  dataSource:  { icon: Globe,    color: 'text-blue-500',    label: 'Data Source' },
  processing:  { icon: Cpu,      color: 'text-amber-500',   label: 'Processing' },
  agent:       { icon: Brain,    color: 'text-emerald-500', label: 'AI Agent' },
  storage:     { icon: Database,  color: 'text-violet-500',  label: 'Storage' },
  scheduler:   { icon: Clock,    color: 'text-orange-500',  label: 'Scheduler' },
  fanOut:      { icon: GitFork,  color: 'text-slate-400',   label: 'Fan-Out' },
  externalApi: { icon: Globe,    color: 'text-rose-500',    label: 'External API' },
  gcpService:  { icon: Cloud,    color: 'text-sky-500',     label: 'GCP Service' },
  tabNode:     { icon: Layout,   color: 'text-cyan-500',    label: 'Frontend Tab' },
}

const tabLabels: Record<ArchSubTab, string> = {
  'ingestion': 'Data Ingestion',
  'tab-architecture': 'Tab Architecture',
  'agentic-workflows': 'Agentic Workflows',
}

export interface SearchableNode {
  id: string
  label: string
  nodeType: ArchNodeType
  description: string
  tab: ArchSubTab
  section?: string
  badge?: string
}

interface SearchPaletteProps {
  isOpen: boolean
  onClose: () => void
  nodes: SearchableNode[]
  onSelect: (node: SearchableNode) => void
}

function fuzzyMatch(text: string, query: string): boolean {
  const lower = text.toLowerCase()
  const q = query.toLowerCase()
  // Simple substring match + word-start matching
  if (lower.includes(q)) return true
  // Match if all query words appear somewhere in text
  const words = q.split(/\s+/)
  return words.every(w => lower.includes(w))
}

function highlightMatch(text: string, query: string): React.ReactNode {
  if (!query) return text
  const idx = text.toLowerCase().indexOf(query.toLowerCase())
  if (idx === -1) return text
  return (
    <>
      {text.slice(0, idx)}
      <span className="text-sky-600 font-semibold bg-sky-50 rounded px-0.5">{text.slice(idx, idx + query.length)}</span>
      {text.slice(idx + query.length)}
    </>
  )
}

export default function SearchPalette({ isOpen, onClose, nodes, onSelect }: SearchPaletteProps) {
  const [query, setQuery] = useState('')
  const [selectedIndex, setSelectedIndex] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLDivElement>(null)

  // Reset on open
  useEffect(() => {
    if (isOpen) {
      setQuery('')
      setSelectedIndex(0)
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }, [isOpen])

  // Filter results
  const results = useMemo(() => {
    if (!query.trim()) return nodes.slice(0, 20) // Show first 20 when empty
    return nodes.filter(n =>
      fuzzyMatch(n.label, query) ||
      fuzzyMatch(n.description, query) ||
      fuzzyMatch(n.nodeType, query) ||
      (n.badge && fuzzyMatch(n.badge, query))
    )
  }, [nodes, query])

  // Clamp selected index
  useEffect(() => {
    setSelectedIndex(0)
  }, [query])

  // Scroll selected item into view
  useEffect(() => {
    const el = listRef.current?.children[selectedIndex] as HTMLElement | undefined
    el?.scrollIntoView({ block: 'nearest' })
  }, [selectedIndex])

  // Keyboard navigation
  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault()
        setSelectedIndex(i => Math.min(i + 1, results.length - 1))
        break
      case 'ArrowUp':
        e.preventDefault()
        setSelectedIndex(i => Math.max(i - 1, 0))
        break
      case 'Enter':
        e.preventDefault()
        if (results[selectedIndex]) {
          onSelect(results[selectedIndex])
          onClose()
        }
        break
      case 'Escape':
        e.preventDefault()
        onClose()
        break
    }
  }, [results, selectedIndex, onSelect, onClose])

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.1 }}
            className="fixed inset-0 bg-black/40 backdrop-blur-sm z-[200]"
            onClick={onClose}
          />

          {/* Palette */}
          <motion.div
            initial={{ opacity: 0, scale: 0.96, y: -10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: -10 }}
            transition={{ type: 'spring', damping: 30, stiffness: 400 }}
            className="fixed top-[15%] left-1/2 -translate-x-1/2 w-[560px] max-h-[60vh] bg-white rounded-xl shadow-2xl border border-slate-200 z-[201] flex flex-col overflow-hidden"
          >
            {/* Search input */}
            <div className="flex items-center gap-3 px-4 py-3 border-b border-slate-100">
              <Search className="w-4.5 h-4.5 text-slate-400 shrink-0" />
              <input
                ref={inputRef}
                type="text"
                value={query}
                onChange={e => setQuery(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Search 92 nodes across all diagrams..."
                className="flex-1 text-sm text-slate-800 placeholder:text-slate-400 outline-none bg-transparent"
              />
              <kbd className="hidden sm:flex items-center gap-0.5 px-1.5 py-0.5 rounded border border-slate-200 bg-slate-50 text-[10px] text-slate-400 font-mono">
                ESC
              </kbd>
            </div>

            {/* Results list */}
            <div ref={listRef} className="flex-1 overflow-y-auto py-1">
              {results.length === 0 ? (
                <div className="px-4 py-8 text-center text-sm text-slate-400">
                  No nodes matching &ldquo;{query}&rdquo;
                </div>
              ) : (
                results.map((node, i) => {
                  const meta = nodeTypeMeta[node.nodeType]
                  const Icon = meta.icon
                  const isSelected = i === selectedIndex
                  return (
                    <button
                      key={node.id}
                      onClick={() => { onSelect(node); onClose() }}
                      onMouseEnter={() => setSelectedIndex(i)}
                      className={`
                        w-full flex items-start gap-3 px-4 py-2.5 text-left transition-colors
                        ${isSelected ? 'bg-sky-50' : 'hover:bg-slate-50'}
                      `}
                    >
                      <div className={`mt-0.5 shrink-0 ${meta.color}`}>
                        <Icon className="w-4 h-4" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium text-slate-800 truncate">
                            {highlightMatch(node.label, query)}
                          </span>
                          {node.badge && (
                            <span className="text-[10px] text-slate-400 font-medium shrink-0">{node.badge}</span>
                          )}
                        </div>
                        <div className="flex items-center gap-1.5 mt-0.5">
                          <span className={`text-[10px] font-medium ${meta.color}`}>{meta.label}</span>
                          <span className="text-[10px] text-slate-300">·</span>
                          <span className="text-[10px] text-slate-400">{tabLabels[node.tab]}</span>
                          {node.section && (
                            <>
                              <span className="text-[10px] text-slate-300">·</span>
                              <span className="text-[10px] text-slate-400">Section {node.section}</span>
                            </>
                          )}
                        </div>
                        <p className="text-[11px] text-slate-500 mt-0.5 line-clamp-1">
                          {highlightMatch(node.description, query)}
                        </p>
                      </div>
                    </button>
                  )
                })
              )}
            </div>

            {/* Footer hint */}
            <div className="px-4 py-2 border-t border-slate-100 flex items-center gap-4 text-[10px] text-slate-400">
              <span className="flex items-center gap-1">
                <kbd className="px-1 py-0.5 rounded border border-slate-200 bg-slate-50 font-mono">↑↓</kbd>
                navigate
              </span>
              <span className="flex items-center gap-1">
                <kbd className="px-1 py-0.5 rounded border border-slate-200 bg-slate-50 font-mono">↵</kbd>
                select
              </span>
              <span className="ml-auto">{results.length} result{results.length !== 1 ? 's' : ''}</span>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
