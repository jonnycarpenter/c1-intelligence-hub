'use client'

import { useState, useEffect } from 'react'
import {
  DollarSign, ChevronDown, ChevronRight, TrendingUp,
  AlertCircle, Settings2,
} from 'lucide-react'
import {
  AreaChart, Area, XAxis, YAxis, Tooltip as RechartsTooltip,
  ResponsiveContainer, CartesianGrid, LineChart, Line,
  BarChart, Bar, Legend,
} from 'recharts'
import { cn } from '@/lib/utils'
import { api } from '@/lib/api'

interface CostData {
  total_calls: number
  total_input_tokens?: number
  total_output_tokens?: number
  total_tokens?: number
  total_cost_usd?: number
  by_model?: Array<{ model: string; calls: number; cost_usd: number; tokens: number }>
  by_caller?: Array<{ caller: string; calls: number; cost_usd: number; tokens: number }>
  daily_trend?: Array<{ date: string; calls: number; cost_usd: number; tokens: number }>
}

interface CostTrend {
  week: string
  total_cost: number
  total_tokens: number
  total_calls: number
}

interface ModelPricing {
  [model: string]: { input: number; output: number }
}

function formatTokens(n: number) {
  const v = n ?? 0
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`
  if (v >= 1_000) return `${(v / 1_000).toFixed(0)}K`
  return String(v)
}

function formatCost(n: number) {
  const v = n ?? 0
  if (v >= 1) return `$${v.toFixed(2)}`
  if (v >= 0.01) return `$${v.toFixed(3)}`
  return `$${v.toFixed(4)}`
}

// ── Sortable table ──

type SortDir = 'asc' | 'desc'

function SortableTable({ title, data, columns, defaultSort }: {
  title: string
  data: Array<Record<string, any>>
  columns: Array<{ key: string; label: string; format?: (v: any) => string; align?: string }>
  defaultSort?: string
}) {
  const [sortKey, setSortKey] = useState(defaultSort || columns[0]?.key)
  const [sortDir, setSortDir] = useState<SortDir>('desc')

  if (!data || data.length === 0) return null

  const sorted = [...data].sort((a, b) => {
    const va = a[sortKey] ?? 0
    const vb = b[sortKey] ?? 0
    return sortDir === 'asc' ? (va > vb ? 1 : -1) : (va < vb ? 1 : -1)
  })

  const handleSort = (key: string) => {
    if (sortKey === key) {
      setSortDir(sortDir === 'asc' ? 'desc' : 'asc')
    } else {
      setSortKey(key)
      setSortDir('desc')
    }
  }

  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
      <div className="px-5 py-3 border-b border-slate-100">
        <h4 className="text-sm font-semibold text-slate-700">{title}</h4>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-slate-50">
              {columns.map(col => (
                <th
                  key={col.key}
                  onClick={() => handleSort(col.key)}
                  className={cn(
                    'px-4 py-2.5 font-medium text-xs text-slate-500 cursor-pointer hover:text-slate-700 select-none',
                    col.align === 'right' ? 'text-right' : 'text-left'
                  )}
                >
                  {col.label}
                  {sortKey === col.key && (
                    <span className="ml-1">{sortDir === 'asc' ? '↑' : '↓'}</span>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((row, i) => (
              <tr key={i} className="border-t border-slate-50 hover:bg-slate-50/50">
                {columns.map(col => (
                  <td
                    key={col.key}
                    className={cn(
                      'px-4 py-2.5 text-slate-700',
                      col.align === 'right' && 'text-right'
                    )}
                  >
                    {col.format ? col.format(row[col.key]) : row[col.key]}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── Pricing Table ──

function PricingTable({ pricing, onUpdate }: {
  pricing: ModelPricing
  onUpdate: (model: string, input: number, output: number) => void
}) {
  const [editingModel, setEditingModel] = useState<string | null>(null)
  const [editInput, setEditInput] = useState('')
  const [editOutput, setEditOutput] = useState('')

  const models = Object.entries(pricing).sort((a, b) => b[1].output - a[1].output)

  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
      <div className="px-5 py-3 border-b border-slate-100 flex items-center justify-between">
        <h4 className="text-sm font-semibold text-slate-700 flex items-center gap-2">
          <Settings2 size={14} className="text-slate-400" />
          Model Pricing (per 1M tokens)
        </h4>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-slate-50">
              <th className="text-left px-4 py-2.5 font-medium text-xs text-slate-500">Model</th>
              <th className="text-right px-4 py-2.5 font-medium text-xs text-slate-500">Input $/1M</th>
              <th className="text-right px-4 py-2.5 font-medium text-xs text-slate-500">Output $/1M</th>
              <th className="text-right px-4 py-2.5 font-medium text-xs text-slate-500">Action</th>
            </tr>
          </thead>
          <tbody>
            {models.map(([model, price]) => (
              <tr key={model} className="border-t border-slate-50 hover:bg-slate-50/50">
                <td className="px-4 py-2.5 text-slate-700 font-mono text-xs">{model}</td>
                {editingModel === model ? (
                  <>
                    <td className="text-right px-4 py-2">
                      <input
                        type="number"
                        step="0.01"
                        value={editInput}
                        onChange={e => setEditInput(e.target.value)}
                        className="w-20 text-right text-xs border border-slate-200 rounded px-2 py-1"
                      />
                    </td>
                    <td className="text-right px-4 py-2">
                      <input
                        type="number"
                        step="0.01"
                        value={editOutput}
                        onChange={e => setEditOutput(e.target.value)}
                        className="w-20 text-right text-xs border border-slate-200 rounded px-2 py-1"
                      />
                    </td>
                    <td className="text-right px-4 py-2 space-x-1">
                      <button
                        onClick={() => {
                          onUpdate(model, parseFloat(editInput), parseFloat(editOutput))
                          setEditingModel(null)
                        }}
                        className="text-xs px-2 py-1 bg-emerald-500 text-white rounded hover:bg-emerald-600"
                      >
                        Save
                      </button>
                      <button
                        onClick={() => setEditingModel(null)}
                        className="text-xs px-2 py-1 bg-slate-100 text-slate-600 rounded hover:bg-slate-200"
                      >
                        Cancel
                      </button>
                    </td>
                  </>
                ) : (
                  <>
                    <td className="text-right px-4 py-2.5 text-slate-600">${(price.input ?? 0).toFixed(2)}</td>
                    <td className="text-right px-4 py-2.5 text-slate-600">${(price.output ?? 0).toFixed(2)}</td>
                    <td className="text-right px-4 py-2.5">
                      <button
                        onClick={() => {
                          setEditingModel(model)
                          setEditInput(String(price.input))
                          setEditOutput(String(price.output))
                        }}
                        className="text-xs px-2 py-1 text-slate-500 hover:text-slate-700 hover:bg-slate-100 rounded"
                      >
                        Edit
                      </button>
                    </td>
                  </>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── Main CostExplorer Component ──

export default function CostExplorer({ data, days }: { data: CostData; days: number }) {
  const [pricing, setPricing] = useState<ModelPricing | null>(null)
  const [costTrends, setCostTrends] = useState<CostTrend[]>([])
  const [loadingPricing, setLoadingPricing] = useState(false)

  useEffect(() => {
    const loadExtra = async () => {
      try {
        const [pricingRes, trendsRes] = await Promise.all([
          api.getModelPricing().catch(() => null),
          api.getEvalTrends(12).catch(() => null),
        ])
        if (pricingRes?.models) setPricing(pricingRes.models)
        if (trendsRes?.cost_trends) setCostTrends(trendsRes.cost_trends)
      } catch { /* ignore */ }
    }
    loadExtra()
  }, [])

  const handlePricingUpdate = async (model: string, input: number, output: number) => {
    try {
      setLoadingPricing(true)
      await api.updateModelPricing(model, input, output)
      // Refresh pricing
      const res = await api.getModelPricing()
      if (res?.models) setPricing(res.models)
    } catch (err) {
      console.error('Failed to update pricing:', err)
    } finally {
      setLoadingPricing(false)
    }
  }

  // Compute cumulative cost for trend chart
  const cumulativeData = (data.daily_trend || []).reduce((acc, d, i) => {
    const prev = i > 0 ? acc[i - 1].cumulative : 0
    acc.push({ ...d, cumulative: +(prev + d.cost_usd).toFixed(4) })
    return acc
  }, [] as Array<{ date: string; cost_usd: number; calls: number; tokens: number; cumulative: number }>)

  if (data.total_calls === 0) {
    return (
      <div className="text-center py-16 border-2 border-dashed border-slate-200 rounded-xl">
        <DollarSign size={32} className="text-slate-300 mx-auto mb-3" />
        <p className="text-sm text-slate-500">No token usage data yet</p>
        <p className="text-xs text-slate-400 mt-1">Cost data populates automatically after LLM calls</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Summary row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl border border-slate-200 p-4">
          <p className="text-xs text-slate-500">Total Cost</p>
          <p className="text-2xl font-semibold text-amber-600">{formatCost(data.total_cost_usd || 0)}</p>
          <p className="text-xs text-slate-400">{days}-day period</p>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 p-4">
          <p className="text-xs text-slate-500">API Calls</p>
          <p className="text-2xl font-semibold text-slate-800">{data.total_calls.toLocaleString()}</p>
          <p className="text-xs text-slate-400">avg {formatCost((data.total_cost_usd || 0) / data.total_calls)}/call</p>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 p-4">
          <p className="text-xs text-slate-500">Input Tokens</p>
          <p className="text-2xl font-semibold text-slate-800">{formatTokens(data.total_input_tokens || 0)}</p>
          <p className="text-xs text-slate-400">{((data.total_input_tokens || 0) / (data.total_tokens || 1) * 100).toFixed(0)}% of total</p>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 p-4">
          <p className="text-xs text-slate-500">Output Tokens</p>
          <p className="text-2xl font-semibold text-slate-800">{formatTokens(data.total_output_tokens || 0)}</p>
          <p className="text-xs text-slate-400">{((data.total_output_tokens || 0) / (data.total_tokens || 1) * 100).toFixed(0)}% of total</p>
        </div>
      </div>

      {/* Large cost trend chart */}
      {cumulativeData.length > 0 && (
        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <h4 className="text-sm font-semibold text-slate-700 mb-4">Daily Cost & Cumulative Spend</h4>
          <ResponsiveContainer width="100%" height={280}>
            <AreaChart data={cumulativeData}>
              <defs>
                <linearGradient id="costGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#f59e0b" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="#f59e0b" stopOpacity={0.05} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} tickFormatter={(v: string) => v.slice(5)} />
              <YAxis yAxisId="left" tick={{ fontSize: 10 }} tickFormatter={(v: number) => `$${v}`} />
              <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 10 }} tickFormatter={(v: number) => `$${v}`} />
              <RechartsTooltip
                contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e2e8f0' }}
                formatter={(v: any, name: any) => [
                  `$${Number(v).toFixed(4)}`,
                  name === 'cost_usd' ? 'Daily Cost' : 'Cumulative'
                ]}
              />
              <Area yAxisId="left" type="monotone" dataKey="cost_usd" stroke="#f59e0b" fill="url(#costGrad)" strokeWidth={2} name="cost_usd" />
              <Line yAxisId="right" type="monotone" dataKey="cumulative" stroke="#6366f1" strokeWidth={2} dot={false} name="cumulative" strokeDasharray="5 5" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Weekly cost trends */}
      {costTrends.length > 0 && (
        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <h4 className="text-sm font-semibold text-slate-700 mb-4">Weekly Cost Trend</h4>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={costTrends}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="week" tick={{ fontSize: 10 }} tickFormatter={(v: string) => v.slice(5, 10)} />
              <YAxis tick={{ fontSize: 10 }} tickFormatter={(v: number) => `$${v}`} />
              <RechartsTooltip
                contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e2e8f0' }}
                formatter={(v: any) => [`$${Number(v).toFixed(4)}`, 'Weekly Cost']}
              />
              <Bar dataKey="total_cost" fill="#f59e0b" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* By Model + By Caller tables */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <SortableTable
          title="Cost by Model"
          data={data.by_model || []}
          defaultSort="cost_usd"
          columns={[
            { key: 'model', label: 'Model' },
            { key: 'calls', label: 'Calls', align: 'right', format: (v: number) => (v ?? 0).toLocaleString() },
            { key: 'cost_usd', label: 'Cost', align: 'right', format: (v: number) => formatCost(v ?? 0) },
            { key: 'tokens', label: 'Tokens', align: 'right', format: (v: number) => formatTokens(v ?? 0) },
          ]}
        />
        <SortableTable
          title="Cost by Module"
          data={data.by_caller || []}
          defaultSort="cost_usd"
          columns={[
            { key: 'caller', label: 'Module' },
            { key: 'calls', label: 'Calls', align: 'right', format: (v: number) => (v ?? 0).toLocaleString() },
            { key: 'cost_usd', label: 'Cost', align: 'right', format: (v: number) => formatCost(v ?? 0) },
            { key: 'tokens', label: 'Tokens', align: 'right', format: (v: number) => formatTokens(v ?? 0) },
          ]}
        />
      </div>

      {/* Daily data table */}
      <SortableTable
        title="Daily Breakdown"
        data={data.daily_trend || []}
        defaultSort="date"
        columns={[
          { key: 'date', label: 'Date' },
          { key: 'calls', label: 'Calls', align: 'right', format: (v: number) => (v ?? 0).toLocaleString() },
          { key: 'cost_usd', label: 'Cost', align: 'right', format: (v: number) => formatCost(v ?? 0) },
          { key: 'tokens', label: 'Tokens', align: 'right', format: (v: number) => formatTokens(v ?? 0) },
        ]}
      />

      {/* Model Pricing (T4.5) */}
      {pricing && (
        <PricingTable pricing={pricing} onUpdate={handlePricingUpdate} />
      )}
    </div>
  )
}
