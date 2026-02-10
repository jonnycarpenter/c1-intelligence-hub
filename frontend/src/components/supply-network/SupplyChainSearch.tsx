'use client'

import { useState, useRef, useCallback } from 'react'
import {
  Search,
  X,
  Loader2,
  Building2,
  Factory,
  AlertCircle,
  Package,
  MapPin,
  ChevronRight,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { api } from '@/lib/api'

interface SupplyChainSearchProps {
  onActivate: () => void
  onDeactivate: () => void
}

interface ProgressStep {
  step: string
  tool: string
  status: 'active' | 'complete'
}

interface AgentResult {
  answer: string
  entity_type?: string
  entity_name?: string
  entity_key?: string
  relationships?: Array<Record<string, any>>
  summary_stats?: Record<string, any>
  not_found?: boolean
  not_found_message?: string
}

export default function SupplyChainSearch({ onActivate, onDeactivate }: SupplyChainSearchProps) {
  const [query, setQuery] = useState('')
  const [isSearching, setIsSearching] = useState(false)
  const [progressSteps, setProgressSteps] = useState<ProgressStep[]>([])
  const [result, setResult] = useState<AgentResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [showResults, setShowResults] = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleSearch = useCallback(async () => {
    const trimmed = query.trim()
    if (!trimmed || isSearching) return

    setIsSearching(true)
    setProgressSteps([])
    setResult(null)
    setError(null)
    setShowResults(true)
    onActivate()

    // Abort any previous request
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    try {
      const response = await api.querySupplyChainAgent(trimmed, controller.signal)

      const reader = response.body?.getReader()
      if (!reader) throw new Error('No response stream')

      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6).trim()
            if (data === '[DONE]') continue

            try {
              const event = JSON.parse(data)

              if (event.type === 'progress') {
                setProgressSteps((prev) => {
                  const updated = prev.map((s) => ({ ...s, status: 'complete' as const }))
                  return [...updated, { step: event.step, tool: event.tool || '', status: 'active' }]
                })
              } else if (event.type === 'result') {
                setResult(event.data)
              } else if (event.type === 'error') {
                setError(event.message || 'Search failed')
              }
            } catch {
              // Skip malformed events
            }
          }
        }
      }
    } catch (err: any) {
      if (err.name !== 'AbortError') {
        setError(err.message || 'Search failed')
      }
    } finally {
      setIsSearching(false)
    }
  }, [query, isSearching, onActivate])

  const handleClear = () => {
    setQuery('')
    setResult(null)
    setError(null)
    setProgressSteps([])
    setShowResults(false)
    abortRef.current?.abort()
    onDeactivate()
    inputRef.current?.focus()
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleSearch()
    if (e.key === 'Escape') handleClear()
  }

  return (
    <div className="space-y-3">
      {/* Search input */}
      <div className="relative">
        <Search
          size={16}
          className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
        />
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={"Ask about suppliers, buyers, or trade relationships..."}
          className="w-full pl-10 pr-20 py-2.5 text-sm bg-white border border-slate-200 rounded-xl
                     focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-300
                     placeholder:text-slate-400 transition-all"
        />
        <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1">
          {showResults && (
            <button
              onClick={handleClear}
              className="p-1 rounded-md hover:bg-slate-100 transition-colors"
              title="Clear"
            >
              <X size={14} className="text-slate-400" />
            </button>
          )}
          <button
            onClick={handleSearch}
            disabled={isSearching || !query.trim()}
            className={cn(
              'px-3 py-1 text-xs font-medium rounded-lg transition-colors',
              isSearching || !query.trim()
                ? 'bg-slate-100 text-slate-400 cursor-not-allowed'
                : 'bg-indigo-600 text-white hover:bg-indigo-700'
            )}
          >
            {isSearching ? (
              <Loader2 size={12} className="animate-spin" />
            ) : (
              'Search'
            )}
          </button>
        </div>
      </div>

      {/* Progress steps */}
      {isSearching && progressSteps.length > 0 && (
        <div className="bg-white rounded-xl border border-slate-200 p-4">
          <div className="space-y-2">
            {progressSteps.map((step, i) => (
              <div key={i} className="flex items-center gap-2 text-xs">
                {step.status === 'active' ? (
                  <Loader2 size={12} className="animate-spin text-indigo-500" />
                ) : (
                  <div className="w-3 h-3 rounded-full bg-emerald-500 flex items-center justify-center">
                    <svg className="w-2 h-2 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                    </svg>
                  </div>
                )}
                <span className={step.status === 'active' ? 'text-slate-700' : 'text-slate-400'}>
                  {step.step}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="bg-red-50 rounded-xl border border-red-200 p-4 flex items-start gap-3">
          <AlertCircle size={16} className="text-red-500 shrink-0 mt-0.5" />
          <div>
            <p className="text-sm text-red-700 font-medium">Search failed</p>
            <p className="text-xs text-red-600 mt-0.5">{error}</p>
          </div>
        </div>
      )}

      {/* Results */}
      {result && (
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          {result.not_found ? (
            <div className="p-6 text-center">
              <AlertCircle size={24} className="text-slate-300 mx-auto mb-2" />
              <p className="text-sm text-slate-600 font-medium">Company Not Found</p>
              <p className="text-xs text-slate-400 mt-1">
                {result.not_found_message || "We couldn't find that company or supplier in our database or ImportYeti."}
              </p>
            </div>
          ) : (
            <>
              {/* Answer text */}
              {result.answer && (
                <div className="px-5 py-4 border-b border-slate-100">
                  <p className="text-sm text-slate-700 leading-relaxed">{result.answer}</p>
                </div>
              )}

              {/* Summary stats */}
              {result.summary_stats && (
                <div className="px-5 py-3 border-b border-slate-100 flex items-center gap-4 text-xs text-slate-500">
                  {result.entity_name && (
                    <span className="font-medium text-slate-700">{result.entity_name}</span>
                  )}
                  {result.summary_stats.total_suppliers_available != null && (
                    <span className="flex items-center gap-1">
                      <Factory size={12} className="text-indigo-500" />
                      {result.summary_stats.total_suppliers_available} suppliers
                    </span>
                  )}
                  {result.summary_stats.active_12m != null && (
                    <span>{result.summary_stats.active_12m} active (12m)</span>
                  )}
                </div>
              )}

              {/* Relationships table */}
              {result.relationships && result.relationships.length > 0 && (
                <div className="overflow-auto max-h-[400px]">
                  <table className="w-full text-xs">
                    <thead className="bg-slate-50 text-slate-500 uppercase sticky top-0">
                      <tr>
                        <th className="px-4 py-2.5 text-left font-medium">Name</th>
                        <th className="px-4 py-2.5 text-left font-medium">Country</th>
                        <th className="px-4 py-2.5 text-right font-medium">12m</th>
                        <th className="px-4 py-2.5 text-right font-medium">Total</th>
                        <th className="px-4 py-2.5 text-right font-medium">%</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-50">
                      {result.relationships.map((r, i) => (
                        <tr key={i} className="hover:bg-slate-50/50">
                          <td className="px-4 py-2.5 font-medium text-slate-800">
                            {r.name || r.supplier_name || r.buyer_name || 'Unknown'}
                          </td>
                          <td className="px-4 py-2.5 text-slate-500">
                            {r.country || r.supplier_country || '—'}
                          </td>
                          <td className="px-4 py-2.5 text-right text-slate-600">
                            {r.shipments_12m ?? '—'}
                          </td>
                          <td className="px-4 py-2.5 text-right text-slate-600">
                            {r.total_shipments?.toLocaleString() ?? '—'}
                          </td>
                          <td className="px-4 py-2.5 text-right text-slate-600">
                            {formatPct(r.pct_of_company || r.pct_of_supplier || r.shipment_pct_of_source)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}

function formatPct(value: any): string {
  if (value == null) return '—'
  const num = typeof value === 'string' ? parseFloat(value) : value
  if (isNaN(num)) return '—'
  return `${num.toFixed(1)}%`
}
