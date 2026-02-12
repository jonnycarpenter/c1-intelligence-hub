'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import {
  BarChart3, DollarSign, ThumbsUp, Brain, RefreshCw, AlertCircle,
  CheckCircle, FileText, Clock, Zap, TrendingUp, ChevronDown, ChevronRight,
  Search, FlaskConical, Play, Download, RotateCcw,
  ArrowUp, ArrowDown, AlertTriangle,
  ThumbsDown,
} from 'lucide-react'
import {
  AreaChart, Area, XAxis, YAxis, Tooltip as RechartsTooltip,
  ResponsiveContainer, CartesianGrid,
} from 'recharts'
import { cn } from '@/lib/utils'
import { api } from '@/lib/api'

// ── T3.7: Cost alert threshold ──
const COST_ALERT_THRESHOLD_USD = 5.00

// ── Types ──

interface FeedbackComment {
  report_type: string
  rating: string
  comment: string
  created_at: string
}

interface EvalReport {
  id: string
  report_id: string
  eval_model: string
  factual_grounding_score: number
  factual_grounding_reasoning: string
  coherence_score: number
  coherence_reasoning: string
  actionability_score: number
  actionability_reasoning: string
  overall_score: number
  overall_reasoning: string
  eval_time_seconds: number
  created_at: string
  query: string
  overall_confidence: string
  sources_count: number
}

interface Anomaly {
  metric: string
  current_value: number
  expected_range: [number, number]
  severity: 'warning' | 'critical'
  description: string
}

interface IngestionSourceHealth {
  source: string
  status: 'green' | 'yellow' | 'red'
  last_run: string | null
  total_articles: number
  articles_24h: number
  avg_daily: number
}

interface DashboardData {
  period_days: number
  generated_at: string
  quality_metrics: {
    deep_research: {
      total_reports: number
      avg_citation_count: number
      citation_health_rate: number
      validation_pass_rate: number
      confidence_distribution: { high: number; medium: number; low: number }
      avg_research_time_seconds: number
      avg_sources_count: number
    }
    weekly_briefing: {
      total_briefings: number
      avg_section_count: number
    }
  }
  llm_judge_scores: {
    total_evals: number
    avg_factual_grounding?: number
    avg_coherence?: number
    avg_actionability?: number
    avg_overall?: number
  }
  token_usage_and_cost: {
    total_calls: number
    total_input_tokens?: number
    total_output_tokens?: number
    total_tokens?: number
    total_cost_usd?: number
    by_model?: Array<{ model: string; calls: number; cost_usd: number; tokens: number }>
    by_caller?: Array<{ caller: string; calls: number; cost_usd: number; tokens: number }>
    daily_trend?: Array<{ date: string; calls: number; cost_usd: number; tokens: number }>
    note?: string
  }
  user_feedback: {
    total_feedback: number
    positive_count?: number
    negative_count?: number
    positive_rate?: number
    avg_rating?: number
    helpful_rate?: number
    total_ratings?: number
    total_comments?: number
    rating_distribution?: Record<string, number>
    recent_comments?: FeedbackComment[]
  }
  anomalies?: Anomaly[]
  previous_period?: {
    quality_metrics: any
    llm_judge_scores: any
    token_usage_and_cost: any
    user_feedback: any
  }
}

// ── Animated number hook (T2.2) ──

function useAnimatedNumber(target: number, duration = 800) {
  const [value, setValue] = useState(0)
  const ref = useRef<number>(0)

  useEffect(() => {
    const start = ref.current
    const startTime = performance.now()
    let frameId: number
    const animate = (now: number) => {
      const progress = Math.min((now - startTime) / duration, 1)
      const eased = 1 - Math.pow(1 - progress, 3) // ease-out cubic
      setValue(start + (target - start) * eased)
      if (progress < 1) {
        frameId = requestAnimationFrame(animate)
      } else {
        ref.current = target
      }
    }
    frameId = requestAnimationFrame(animate)
    return () => cancelAnimationFrame(frameId)
  }, [target, duration])

  return value
}

// ── Relative time util (T2.5) ──

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

// ── Skeleton components (T2.1) ──

function SkeletonCard() {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5 flex items-start gap-4 animate-pulse">
      <div className="w-10 h-10 rounded-lg bg-slate-200" />
      <div className="flex-1 space-y-2">
        <div className="h-3 w-20 bg-slate-200 rounded" />
        <div className="h-6 w-16 bg-slate-200 rounded" />
        <div className="h-2 w-24 bg-slate-100 rounded" />
      </div>
    </div>
  )
}

function SkeletonSection() {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5 animate-pulse">
      <div className="flex items-center gap-2 mb-4">
        <div className="w-7 h-7 rounded-lg bg-slate-200" />
        <div className="h-4 w-40 bg-slate-200 rounded" />
      </div>
      <div className="space-y-3">
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-1">
            <div className="h-2 w-16 bg-slate-100 rounded" />
            <div className="h-5 w-12 bg-slate-200 rounded" />
          </div>
          <div className="space-y-1">
            <div className="h-2 w-16 bg-slate-100 rounded" />
            <div className="h-5 w-12 bg-slate-200 rounded" />
          </div>
        </div>
        <div className="h-2 w-full bg-slate-100 rounded" />
        <div className="h-2 w-3/4 bg-slate-100 rounded" />
        <div className="h-2 w-5/6 bg-slate-100 rounded" />
      </div>
    </div>
  )
}

// ── Helper components ──

function StatCard({ icon: Icon, label, value, sub, color }: {
  icon: typeof BarChart3; label: string; value: string | number; sub?: string; color: string
}) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5 flex items-start gap-4">
      <div className={cn('w-10 h-10 rounded-lg flex items-center justify-center', color)}>
        <Icon size={20} className="text-white" />
      </div>
      <div className="min-w-0">
        <p className="text-sm text-slate-500">{label}</p>
        <p className="text-2xl font-semibold text-slate-800 mt-0.5">{value}</p>
        {sub && <p className="text-xs text-slate-400 mt-1">{sub}</p>}
      </div>
    </div>
  )
}

/** Stat card with animated count-up number (T2.2) */
function AnimatedStatCard({ icon: Icon, label, numericValue, formatValue, sub, color }: {
  icon: typeof BarChart3; label: string; numericValue: number; formatValue: (n: number) => string; sub?: string; color: string
}) {
  const animated = useAnimatedNumber(numericValue)
  return (
    <StatCard icon={Icon} label={label} value={formatValue(animated)} sub={sub} color={color} />
  )
}

function ScoreBar({ label, score, maxScore = 5 }: { label: string; score: number; maxScore?: number }) {
  const pct = (score / maxScore) * 100
  const color = score >= 4 ? 'bg-emerald-500' : score >= 3 ? 'bg-amber-500' : 'bg-red-500'
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-sm">
        <span className="text-slate-600">{label}</span>
        <span className="font-medium text-slate-800">{score}/{maxScore}</span>
      </div>
      <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
        <div className={cn('h-full rounded-full transition-all', color)} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

function SectionHeader({ icon: Icon, title, color }: { icon: typeof BarChart3; title: string; color: string }) {
  return (
    <div className="flex items-center gap-2 mb-4">
      <div className={cn('w-7 h-7 rounded-lg flex items-center justify-center', color)}>
        <Icon size={14} className="text-white" />
      </div>
      <h3 className="font-semibold text-slate-800">{title}</h3>
    </div>
  )
}

function EmptyState({ message, hint, icon: Icon = AlertCircle, actionLabel, actionHref }: {
  message: string; hint?: string; icon?: typeof AlertCircle; actionLabel?: string; actionHref?: string
}) {
  return (
    <div className="text-center py-8 border-2 border-dashed border-slate-200 rounded-xl">
      <div className="w-10 h-10 rounded-full bg-slate-100 flex items-center justify-center mx-auto mb-3">
        <Icon size={20} className="text-slate-400" />
      </div>
      <p className="text-sm text-slate-500">{message}</p>
      {hint && <p className="text-xs text-slate-400 mt-1">{hint}</p>}
      {actionLabel && (
        <p className="text-xs text-amber-600 font-medium mt-2 cursor-pointer hover:text-amber-700">
          {actionLabel} →
        </p>
      )}
    </div>
  )
}

// ── Collapsible cost table ──

function CostTable({ title, data, columns }: {
  title: string
  data: Array<Record<string, any>>
  columns: Array<{ key: string; label: string; format?: (v: any) => string }>
}) {
  const [expanded, setExpanded] = useState(false)
  if (!data || data.length === 0) return null

  return (
    <div className="mt-3">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1.5 text-xs font-medium text-slate-500 hover:text-slate-700 transition-colors"
      >
        {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        {title} ({data.length})
      </button>
      {expanded && (
        <div className="mt-2 border border-slate-100 rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-50 text-slate-500">
                {columns.map(col => (
                  <th key={col.key} className="text-left px-3 py-2 font-medium text-xs">{col.label}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.map((row, i) => (
                <tr key={i} className="border-t border-slate-50">
                  {columns.map(col => (
                    <td key={col.key} className="px-3 py-2 text-slate-700">
                      {col.format ? col.format(row[col.key]) : row[col.key]}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ── T3.3: Recharts cost trend chart ──

function CostTrendChart({ data }: { data: Array<{ date: string; cost_usd: number; calls: number }> }) {
  if (!data || data.length === 0) return null
  return (
    <div className="mt-4">
      <p className="text-xs font-medium text-slate-500 mb-2">Daily Cost Trend</p>
      <ResponsiveContainer width="100%" height={180}>
        <AreaChart data={data}>
          <defs>
            <linearGradient id="costGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#f59e0b" stopOpacity={0.3} />
              <stop offset="100%" stopColor="#f59e0b" stopOpacity={0.05} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
          <XAxis dataKey="date" tick={{ fontSize: 10 }} tickFormatter={(v: string) => v.slice(5)} />
          <YAxis tick={{ fontSize: 10 }} tickFormatter={(v: number) => `$${v}`} />
          <RechartsTooltip
            contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e2e8f0' }}
            formatter={(v) => [`$${Number(v).toFixed(4)}`, 'Cost']}
            labelFormatter={(l) => String(l)}
          />
          <Area type="monotone" dataKey="cost_usd" stroke="#f59e0b" fill="url(#costGradient)" strokeWidth={2} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}

// ── Confidence distribution bar ──

function ConfidenceDistribution({ data }: { data: { high: number; medium: number; low: number } }) {
  const total = (data.high || 0) + (data.medium || 0) + (data.low || 0)
  if (total === 0) return <p className="text-sm text-slate-400">No data</p>

  const pctHigh = Math.round((data.high / total) * 100)
  const pctMed = Math.round((data.medium / total) * 100)
  const pctLow = Math.round((data.low / total) * 100)

  return (
    <div className="space-y-2">
      <div className="flex h-3 rounded-full overflow-hidden bg-slate-100">
        {pctHigh > 0 && <div className="bg-emerald-500 transition-all" style={{ width: `${pctHigh}%` }} />}
        {pctMed > 0 && <div className="bg-amber-400 transition-all" style={{ width: `${pctMed}%` }} />}
        {pctLow > 0 && <div className="bg-red-400 transition-all" style={{ width: `${pctLow}%` }} />}
      </div>
      <div className="flex gap-4 text-xs text-slate-500">
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-emerald-500" /> High {pctHigh}%</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-amber-400" /> Medium {pctMed}%</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-red-400" /> Low {pctLow}%</span>
      </div>
    </div>
  )
}

// ── T3.6: CSV export ──

function exportToCsv(data: DashboardData) {
  const lines: string[] = []
  lines.push('Section,Metric,Value')
  lines.push(`Summary,Total Reports,${data.quality_metrics.deep_research.total_reports}`)
  lines.push(`Summary,Weekly Briefings,${data.quality_metrics.weekly_briefing.total_briefings}`)
  lines.push(`Summary,Total LLM Cost,$${data.token_usage_and_cost.total_cost_usd || 0}`)
  lines.push(`Summary,Total API Calls,${data.token_usage_and_cost.total_calls}`)
  lines.push(`Summary,Avg Quality Score,${data.llm_judge_scores.avg_overall || 'N/A'}`)
  lines.push(`Summary,User Satisfaction,${data.user_feedback.positive_rate != null ? Math.round(data.user_feedback.positive_rate * 100) + '%' : 'N/A'}`)
  lines.push(`Summary,Citation Health,${data.quality_metrics.deep_research.citation_health_rate}%`)
  lines.push(`Summary,Validation Pass Rate,${data.quality_metrics.deep_research.validation_pass_rate}%`)

  lines.push('')
  lines.push('Model,Calls,Cost USD,Tokens')
  data.token_usage_and_cost.by_model?.forEach(m => {
    lines.push(`${m.model},${m.calls},${m.cost_usd},${m.tokens}`)
  })

  lines.push('')
  lines.push('Caller,Calls,Cost USD,Tokens')
  data.token_usage_and_cost.by_caller?.forEach(c => {
    lines.push(`${c.caller},${c.calls},${c.cost_usd},${c.tokens}`)
  })

  lines.push('')
  lines.push('Date,Calls,Cost USD,Tokens')
  data.token_usage_and_cost.daily_trend?.forEach(d => {
    lines.push(`${d.date},${d.calls},${d.cost_usd},${d.tokens}`)
  })

  const blob = new Blob([lines.join('\n')], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `eval-dashboard-${data.period_days}d-${new Date().toISOString().slice(0, 10)}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

// ── T3.8: Delta display helper ──

function DeltaArrow({ current, previous, invert = false }: {
  current: number; previous: number; invert?: boolean
}) {
  if (!previous || previous === 0) return null
  const pctChange = ((current - previous) / previous) * 100
  if (Math.abs(pctChange) < 0.5) return null

  // invert = true means lower is better (e.g., cost)
  const isPositive = invert ? pctChange < 0 : pctChange > 0
  const color = isPositive ? 'text-emerald-600' : 'text-red-500'
  const Icon = pctChange > 0 ? ArrowUp : ArrowDown

  return (
    <span className={cn('inline-flex items-center gap-0.5 text-xs font-medium', color)}>
      <Icon size={12} />
      {Math.abs(pctChange).toFixed(1)}%
    </span>
  )
}

// ── T3.4: Eval reports table ──

function EvalReportsTable({ reports }: { reports: EvalReport[] }) {
  const [expandedId, setExpandedId] = useState<string | null>(null)

  if (!reports || reports.length === 0) return null

  const scoreColor = (s: number) =>
    s >= 4 ? 'text-emerald-600 bg-emerald-50' : s >= 3 ? 'text-amber-600 bg-amber-50' : 'text-red-600 bg-red-50'

  return (
    <div className="mt-6 bg-white rounded-xl border border-slate-200 overflow-hidden">
      <div className="px-5 py-4 border-b border-slate-100">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg flex items-center justify-center bg-violet-500">
            <FileText size={14} className="text-white" />
          </div>
          <h3 className="font-semibold text-slate-800">Recent Evaluations</h3>
          <span className="text-xs text-slate-400 ml-auto">{reports.length} reports</span>
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-slate-50 text-slate-500">
              <th className="text-left px-4 py-2.5 font-medium text-xs w-8"></th>
              <th className="text-left px-4 py-2.5 font-medium text-xs">Query</th>
              <th className="text-center px-3 py-2.5 font-medium text-xs">Overall</th>
              <th className="text-center px-3 py-2.5 font-medium text-xs">Factual</th>
              <th className="text-center px-3 py-2.5 font-medium text-xs">Coherence</th>
              <th className="text-center px-3 py-2.5 font-medium text-xs">Action.</th>
              <th className="text-center px-3 py-2.5 font-medium text-xs">Confidence</th>
              <th className="text-right px-4 py-2.5 font-medium text-xs">Date</th>
            </tr>
          </thead>
          <tbody>
            {reports.map((r) => (
              <>
                <tr
                  key={r.id}
                  className="border-t border-slate-50 hover:bg-slate-50/50 cursor-pointer transition-colors"
                  onClick={() => setExpandedId(expandedId === r.id ? null : r.id)}
                >
                  <td className="px-4 py-2.5 text-slate-400">
                    {expandedId === r.id ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                  </td>
                  <td className="px-4 py-2.5 text-slate-700 max-w-[200px] truncate" title={r.query}>
                    {r.query || 'Untitled'}
                  </td>
                  <td className="text-center px-3 py-2.5">
                    <span className={cn('px-2 py-0.5 rounded-full text-xs font-medium', scoreColor(r.overall_score))}>
                      {r.overall_score}/5
                    </span>
                  </td>
                  <td className="text-center px-3 py-2.5">
                    <span className={cn('px-2 py-0.5 rounded-full text-xs font-medium', scoreColor(r.factual_grounding_score))}>
                      {r.factual_grounding_score}
                    </span>
                  </td>
                  <td className="text-center px-3 py-2.5">
                    <span className={cn('px-2 py-0.5 rounded-full text-xs font-medium', scoreColor(r.coherence_score))}>
                      {r.coherence_score}
                    </span>
                  </td>
                  <td className="text-center px-3 py-2.5">
                    <span className={cn('px-2 py-0.5 rounded-full text-xs font-medium', scoreColor(r.actionability_score))}>
                      {r.actionability_score}
                    </span>
                  </td>
                  <td className="text-center px-3 py-2.5 text-xs text-slate-500 capitalize">
                    {r.overall_confidence || '—'}
                  </td>
                  <td className="text-right px-4 py-2.5 text-xs text-slate-400">
                    {r.created_at ? timeAgo(r.created_at) : '—'}
                  </td>
                </tr>
                {expandedId === r.id && (
                  <tr key={`${r.id}-detail`} className="border-t border-slate-50 bg-slate-50/50">
                    <td colSpan={8} className="px-6 py-4">
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs text-slate-600">
                        {[
                          { label: 'Factual Grounding', score: r.factual_grounding_score, reasoning: r.factual_grounding_reasoning },
                          { label: 'Coherence', score: r.coherence_score, reasoning: r.coherence_reasoning },
                          { label: 'Actionability', score: r.actionability_score, reasoning: r.actionability_reasoning },
                          { label: 'Overall', score: r.overall_score, reasoning: r.overall_reasoning },
                        ].map((dim) => (
                          <div key={dim.label} className="bg-white rounded-lg border border-slate-100 p-3">
                            <div className="flex items-center justify-between mb-1">
                              <span className="font-medium text-slate-700">{dim.label}</span>
                              <span className={cn('px-2 py-0.5 rounded-full font-medium', scoreColor(dim.score))}>
                                {dim.score}/5
                              </span>
                            </div>
                            <p className="text-slate-500 leading-relaxed">{dim.reasoning || 'No reasoning provided'}</p>
                          </div>
                        ))}
                        <div className="col-span-full flex items-center gap-4 text-xs text-slate-400 pt-1">
                          <span>Model: {r.eval_model}</span>
                          <span>Sources: {r.sources_count ?? '—'}</span>
                          <span>Eval time: {r.eval_time_seconds?.toFixed(1)}s</span>
                        </div>
                      </div>
                    </td>
                  </tr>
                )}
              </>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── T3.1: Run Eval Modal ──

function RunEvalModal({ onRun, onClose }: { onRun: (count: number, model: string) => void; onClose: () => void }) {
  const [count, setCount] = useState(5)
  const [model, setModel] = useState('claude-haiku-4-5')

  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-white rounded-xl border border-slate-200 shadow-xl p-6 w-80" onClick={(e) => e.stopPropagation()}>
        <h3 className="font-semibold text-slate-800 mb-4 flex items-center gap-2">
          <FlaskConical size={18} className="text-indigo-500" />
          Run LLM-as-Judge Eval
        </h3>
        <div className="space-y-3">
          <div>
            <label className="text-xs font-medium text-slate-500 block mb-1">Reports to evaluate</label>
            <div className="flex gap-2">
              {[5, 10, 20].map((n) => (
                <button
                  key={n}
                  onClick={() => setCount(n)}
                  className={cn(
                    'flex-1 py-1.5 rounded-lg text-sm font-medium transition-colors',
                    count === n
                      ? 'bg-indigo-500 text-white'
                      : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                  )}
                >
                  {n}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="text-xs font-medium text-slate-500 block mb-1">Eval model</label>
            <select
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="w-full text-sm border border-slate-200 rounded-lg px-3 py-1.5 bg-white text-slate-700 focus:outline-none focus:ring-1 focus:ring-indigo-300"
            >
              <option value="claude-haiku-4-5">Claude Haiku 4.5</option>
              <option value="claude-sonnet-4-20250514">Claude Sonnet 4</option>
            </select>
          </div>
        </div>
        <div className="flex gap-2 mt-5">
          <button
            onClick={onClose}
            className="flex-1 py-2 rounded-lg text-sm text-slate-600 bg-slate-100 hover:bg-slate-200 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={() => onRun(count, model)}
            className="flex-1 py-2 rounded-lg text-sm text-white bg-indigo-500 hover:bg-indigo-600 transition-colors font-medium"
          >
            Run Eval
          </button>
        </div>
      </div>
    </div>
  )
}

// ── T3.2: Recent comments ──

function RecentComments({ comments }: { comments: FeedbackComment[] }) {
  if (!comments || comments.length === 0) {
    return <p className="text-xs text-slate-400 mt-3 italic">No comments yet</p>
  }

  return (
    <div className="mt-4 pt-3 border-t border-slate-100">
      <p className="text-xs font-medium text-slate-500 mb-2">Recent Comments</p>
      <div className="space-y-2">
        {comments.map((c, i) => (
          <div key={i} className="flex items-start gap-2 text-xs">
            {c.rating === 'positive' ? (
              <ThumbsUp size={12} className="text-emerald-500 mt-0.5 shrink-0" />
            ) : (
              <ThumbsDown size={12} className="text-red-400 mt-0.5 shrink-0" />
            )}
            <div className="min-w-0">
              <p className="text-slate-600 leading-relaxed">{c.comment}</p>
              <div className="flex items-center gap-2 mt-0.5">
                <span className="px-1.5 py-0.5 rounded bg-slate-100 text-[10px] text-slate-500 capitalize">
                  {c.report_type?.replace('_', ' ')}
                </span>
                <span className="text-[10px] text-slate-400">{c.created_at ? timeAgo(c.created_at) : ''}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Main Dashboard ──

export default function EvalDashboard() {
  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [days, setDays] = useState(30)

  // T3.8: Compare toggle
  const [compare, setCompare] = useState(false)

  // T3.1: Run eval state
  const [showRunModal, setShowRunModal] = useState(false)
  const [evalRunning, setEvalRunning] = useState(false)

  // T3.4: Eval reports
  const [evalReports, setEvalReports] = useState<EvalReport[]>([])

  // T3.5: Auto-refresh
  const [autoRefresh, setAutoRefresh] = useState(false)
  const autoRefreshRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // T4.2: Ingestion health
  const [ingestionHealth, setIngestionHealth] = useState<IngestionSourceHealth[]>([])

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [result, reportsResult, healthResult] = await Promise.all([
        api.getEvalDashboard(days, compare),
        api.getEvalReports(days).catch(() => ({ reports: [] })),
        api.getIngestionHealth(days).catch(() => ({ sources: [] })),
      ])
      setData(result)
      setEvalReports(reportsResult.reports || [])
      setIngestionHealth((healthResult.sources || []).map((s: any) => ({
        source: s.source || 'unknown',
        status: s.status || 'red',
        last_run: s.last_run || null,
        total_articles: s.total_runs ?? s.successes ?? 0,
        articles_24h: s.articles_24h ?? 0,
        avg_daily: s.avg_daily ?? (s.total_runs ? +(s.total_runs / 30).toFixed(1) : 0),
      })))
    } catch (err: any) {
      setError(err.message || 'Failed to load dashboard')
    } finally {
      setLoading(false)
    }
  }, [days, compare])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  // T3.5: Auto-refresh interval
  useEffect(() => {
    if (autoRefresh) {
      autoRefreshRef.current = setInterval(() => {
        fetchData()
      }, 60_000)
    }
    return () => {
      if (autoRefreshRef.current) {
        clearInterval(autoRefreshRef.current)
        autoRefreshRef.current = null
      }
    }
  }, [autoRefresh, fetchData])

  // T3.1: Poll eval job status
  useEffect(() => {
    if (!evalRunning) return
    const interval = setInterval(async () => {
      try {
        const status = await api.getEvalJobStatus()
        if (!status.running) {
          setEvalRunning(false)
          fetchData() // auto-refresh on completion
        }
      } catch {
        // ignore polling errors
      }
    }, 5_000)
    return () => clearInterval(interval)
  }, [evalRunning, fetchData])

  const handleRunEval = async (count: number, model: string) => {
    setShowRunModal(false)
    try {
      const result = await api.runEvalJudge(count, model)
      if (result.status === 'started') {
        setEvalRunning(true)
      }
    } catch (err: any) {
      setError(err.message || 'Failed to start eval')
    }
  }

  const formatTokens = (n: number) => {
    const v = n ?? 0
    if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`
    if (v >= 1_000) return `${(v / 1_000).toFixed(0)}K`
    return String(v)
  }

  const formatCost = (n: number) => {
    const v = n ?? 0
    if (v >= 1) return `$${v.toFixed(2)}`
    if (v >= 0.01) return `$${v.toFixed(3)}`
    return `$${v.toFixed(4)}`
  }

  return (
    <div className="h-full overflow-y-auto bg-slate-50">
      {/* T3.1: Run Eval Modal */}
      {showRunModal && (
        <RunEvalModal onRun={handleRunEval} onClose={() => setShowRunModal(false)} />
      )}

      {/* Header */}
      <div className="bg-white border-b border-slate-200 px-6 py-5">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <div className="flex items-center gap-2">
              <BarChart3 size={22} className="text-amber-500" />
              <h1 className="text-xl font-semibold text-slate-800">AI Quality Dashboard</h1>
              {/* T3.1: Eval running indicator */}
              {evalRunning && (
                <span className="ml-2 inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-indigo-50 text-indigo-600 animate-pulse">
                  <FlaskConical size={12} /> Evaluation running...
                </span>
              )}
              {/* T3.5: Auto-refresh badge */}
              {autoRefresh && (
                <span className="ml-1 inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-emerald-50 text-emerald-600">
                  <RotateCcw size={10} /> Auto-refreshing
                </span>
              )}
            </div>
            <p className="text-sm text-slate-500 mt-1">
              Evaluation metrics, LLM cost tracking, and user feedback
            </p>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            {/* T3.8: Compare toggle */}
            <label className="flex items-center gap-1.5 text-xs text-slate-500 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={compare}
                onChange={(e) => setCompare(e.target.checked)}
                className="rounded border-slate-300 text-indigo-500 focus:ring-indigo-300"
              />
              Compare
            </label>

            <select
              value={days}
              onChange={(e) => setDays(Number(e.target.value))}
              className="text-sm border border-slate-200 rounded-lg px-3 py-1.5 bg-white text-slate-700 focus:outline-none focus:ring-1 focus:ring-amber-300"
            >
              <option value={7}>Last 7 days</option>
              <option value={14}>Last 14 days</option>
              <option value={30}>Last 30 days</option>
              <option value={90}>Last 90 days</option>
            </select>

            {/* T3.5: Auto-refresh toggle */}
            <button
              onClick={() => setAutoRefresh(!autoRefresh)}
              title={autoRefresh ? 'Disable auto-refresh' : 'Enable auto-refresh (60s)'}
              className={cn(
                'flex items-center gap-1 text-sm px-2.5 py-1.5 rounded-lg transition-colors',
                autoRefresh
                  ? 'bg-emerald-100 text-emerald-700 hover:bg-emerald-200'
                  : 'bg-slate-100 text-slate-500 hover:bg-slate-200'
              )}
            >
              <RotateCcw size={14} />
            </button>

            <button
              onClick={fetchData}
              disabled={loading}
              className="flex items-center gap-1.5 text-sm px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-600 rounded-lg transition-colors disabled:opacity-50"
            >
              <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
              Refresh
            </button>

            {/* T3.1: Run Eval button */}
            <button
              onClick={() => setShowRunModal(true)}
              disabled={evalRunning}
              className="flex items-center gap-1.5 text-sm px-3 py-1.5 bg-indigo-500 hover:bg-indigo-600 text-white rounded-lg transition-colors disabled:opacity-50 font-medium"
            >
              <Play size={14} />
              Run Eval
            </button>

            {/* T3.6: CSV export */}
            {data && (
              <button
                onClick={() => exportToCsv(data)}
                className="flex items-center gap-1.5 text-sm px-2.5 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-600 rounded-lg transition-colors"
                title="Export to CSV"
              >
                <Download size={14} />
              </button>
            )}
          </div>
        </div>
      </div>


      {/* Content */}
      <div className="p-6 max-w-7xl mx-auto">
        {/* Error state */}
        {error && (
          <div className="mb-6 bg-red-50 border border-red-200 rounded-xl px-4 py-3 flex items-center gap-2 text-sm text-red-700">
            <AlertCircle size={16} />
            {error}
          </div>
        )}

        {/* Skeleton loading state (T2.1) */}
        {loading && !data && (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
              <SkeletonCard />
              <SkeletonCard />
              <SkeletonCard />
              <SkeletonCard />
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <SkeletonSection />
              <SkeletonSection />
              <SkeletonSection />
              <SkeletonSection />
            </div>
          </>
        )}

        {data && (
          <>
            {/* T4.3: Anomaly alerts banner */}
            {data.anomalies && data.anomalies.length > 0 && (
              <div className="mb-4 space-y-2">
                {data.anomalies.map((a, i) => (
                  <div
                    key={i}
                    className={cn(
                      'rounded-xl px-4 py-3 flex items-center gap-2 text-sm',
                      a.severity === 'critical'
                        ? 'bg-red-50 border border-red-200 text-red-800'
                        : 'bg-amber-50 border border-amber-200 text-amber-800'
                    )}
                  >
                    <AlertTriangle size={16} className="shrink-0" />
                    <span className="font-medium">{a.metric}:</span>
                    <span>{a.description}</span>
                  </div>
                ))}
              </div>
            )}

            {/* T3.7: Cost alert banner */}
            {(data.token_usage_and_cost.total_cost_usd || 0) > COST_ALERT_THRESHOLD_USD && (
              <div className="mb-4 bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 flex items-center gap-2 text-sm text-amber-800">
                <AlertTriangle size={16} className="shrink-0" />
                <span>
                  LLM costs (${(data.token_usage_and_cost.total_cost_usd || 0).toFixed(2)}) exceed the $
                  {COST_ALERT_THRESHOLD_USD.toFixed(2)} threshold for the last {data.period_days} days
                </span>
              </div>
            )}

            {/* ── Overview ── */}
            <>
            {/* Top-level stat cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
              <div className="relative">
                <AnimatedStatCard
                  icon={FileText}
                  label="Reports Generated"
                  numericValue={data.quality_metrics.deep_research.total_reports || 0}
                  formatValue={(n) => String(Math.round(n))}
                  sub={`${data.quality_metrics.weekly_briefing.total_briefings || 0} weekly briefings`}
                  color="bg-emerald-500"
                />
                {data.previous_period && (
                  <div className="absolute top-3 right-4">
                    <DeltaArrow
                      current={data.quality_metrics.deep_research.total_reports || 0}
                      previous={data.previous_period.quality_metrics?.deep_research?.total_reports || 0}
                    />
                  </div>
                )}
              </div>
              <div className="relative">
                <AnimatedStatCard
                  icon={DollarSign}
                  label="Total LLM Cost"
                  numericValue={data.token_usage_and_cost.total_cost_usd || 0}
                  formatValue={formatCost}
                  sub={data.token_usage_and_cost.total_calls ? `${data.token_usage_and_cost.total_calls.toLocaleString()} API calls` : 'No data yet'}
                  color={(data.token_usage_and_cost.total_cost_usd || 0) > COST_ALERT_THRESHOLD_USD ? 'bg-red-500' : 'bg-amber-500'}
                />
                {data.previous_period && (
                  <div className="absolute top-3 right-4">
                    <DeltaArrow
                      current={data.token_usage_and_cost.total_cost_usd || 0}
                      previous={data.previous_period.token_usage_and_cost?.total_cost_usd || 0}
                      invert
                    />
                  </div>
                )}
              </div>
              <div className="relative">
                <StatCard
                  icon={Brain}
                  label="Avg Quality Score"
                  value={data.llm_judge_scores.avg_overall ? `${data.llm_judge_scores.avg_overall}/5` : 'N/A'}
                  sub={data.llm_judge_scores.total_evals ? `${data.llm_judge_scores.total_evals} reports evaluated` : 'Run eval to populate'}
                  color="bg-indigo-500"
                />
                {data.previous_period && data.llm_judge_scores.avg_overall && (
                  <div className="absolute top-3 right-4">
                    <DeltaArrow
                      current={data.llm_judge_scores.avg_overall}
                      previous={data.previous_period.llm_judge_scores?.avg_overall || 0}
                    />
                  </div>
                )}
              </div>
              <div className="relative">
                {data.user_feedback.positive_rate != null ? (
                  <AnimatedStatCard
                    icon={ThumbsUp}
                    label="User Satisfaction"
                    numericValue={Math.round(data.user_feedback.positive_rate * 100)}
                    formatValue={(n) => `${Math.round(n)}%`}
                    sub={data.user_feedback.total_feedback ? `${data.user_feedback.total_feedback} ratings` : 'No feedback yet'}
                    color="bg-sky-500"
                  />
                ) : (
                  <StatCard
                    icon={ThumbsUp}
                    label="User Satisfaction"
                    value="N/A"
                    sub={data.user_feedback.total_feedback ? `${data.user_feedback.total_feedback} ratings` : 'No feedback yet'}
                    color="bg-sky-500"
                  />
                )}
                {data.previous_period && data.user_feedback.positive_rate != null && (
                  <div className="absolute top-3 right-4">
                    <DeltaArrow
                      current={data.user_feedback.positive_rate || 0}
                      previous={data.previous_period.user_feedback?.positive_rate || 0}
                    />
                  </div>
                )}
              </div>
            </div>

            {/* Main grid */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Quality Metrics */}
              <div className="bg-white rounded-xl border border-slate-200 p-5">
                <SectionHeader icon={CheckCircle} title="Quality Metrics (Deep Research)" color="bg-emerald-500" />
                {data.quality_metrics.deep_research.total_reports === 0 ? (
                  <EmptyState
                    icon={Search}
                    message="No reports in this period"
                    hint="Run a Deep Research query to generate data"
                    actionLabel="Run a Deep Research query"
                  />
                ) : (
                  <div className="space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <p className="text-xs text-slate-500">Citation Health</p>
                        <p className="text-lg font-semibold text-slate-800">{data.quality_metrics.deep_research.citation_health_rate}%</p>
                      </div>
                      <div>
                        <p className="text-xs text-slate-500">Validation Pass Rate</p>
                        <p className="text-lg font-semibold text-slate-800">{data.quality_metrics.deep_research.validation_pass_rate}%</p>
                      </div>
                      <div>
                        <p className="text-xs text-slate-500">Avg Citations</p>
                        <p className="text-lg font-semibold text-slate-800">{data.quality_metrics.deep_research.avg_citation_count}</p>
                      </div>
                      <div>
                        <p className="text-xs text-slate-500">Avg Sources</p>
                        <p className="text-lg font-semibold text-slate-800">{data.quality_metrics.deep_research.avg_sources_count}</p>
                      </div>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500 mb-2">Avg Research Time</p>
                      <div className="flex items-center gap-2">
                        <Clock size={14} className="text-slate-400" />
                        <span className="text-sm font-medium text-slate-700">{data.quality_metrics.deep_research.avg_research_time_seconds}s</span>
                      </div>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500 mb-2">Confidence Distribution</p>
                      <ConfidenceDistribution data={data.quality_metrics.deep_research.confidence_distribution} />
                    </div>
                  </div>
                )}
              </div>

              {/* LLM-as-Judge Scores */}
              <div className="bg-white rounded-xl border border-slate-200 p-5">
                <SectionHeader icon={Brain} title="LLM-as-Judge Scores" color="bg-indigo-500" />
                {data.llm_judge_scores.total_evals === 0 ? (
                  <EmptyState
                    icon={FlaskConical}
                    message="No evaluations yet"
                    hint="Run: python scripts/testing/eval_llm_judge.py"
                    actionLabel="Run the eval script to populate"
                  />
                ) : (
                  <div className="space-y-4">
                    <p className="text-xs text-slate-400">{data.llm_judge_scores.total_evals} reports evaluated by Claude Haiku</p>
                    <ScoreBar label="Factual Grounding" score={data.llm_judge_scores.avg_factual_grounding || 0} />
                    <ScoreBar label="Coherence" score={data.llm_judge_scores.avg_coherence || 0} />
                    <ScoreBar label="Actionability" score={data.llm_judge_scores.avg_actionability || 0} />
                    <div className="pt-2 border-t border-slate-100">
                      <ScoreBar label="Overall" score={data.llm_judge_scores.avg_overall || 0} />
                    </div>
                  </div>
                )}
              </div>

              {/* Token Usage & Cost */}
              <div className="bg-white rounded-xl border border-slate-200 p-5">
                <SectionHeader icon={DollarSign} title="Token Usage & Cost" color="bg-amber-500" />
                {data.token_usage_and_cost.total_calls === 0 ? (
                  <EmptyState
                    icon={DollarSign}
                    message={data.token_usage_and_cost.note || 'No token usage data yet'}
                    hint="Cost data populates automatically after LLM calls"
                  />
                ) : (
                  <div className="space-y-3">
                    <div className="grid grid-cols-3 gap-4">
                      <div>
                        <p className="text-xs text-slate-500">Input Tokens</p>
                        <p className="text-lg font-semibold text-slate-800">{formatTokens(data.token_usage_and_cost.total_input_tokens || 0)}</p>
                      </div>
                      <div>
                        <p className="text-xs text-slate-500">Output Tokens</p>
                        <p className="text-lg font-semibold text-slate-800">{formatTokens(data.token_usage_and_cost.total_output_tokens || 0)}</p>
                      </div>
                      <div>
                        <p className="text-xs text-slate-500">Total Cost</p>
                        <p className="text-lg font-semibold text-amber-600">{formatCost(data.token_usage_and_cost.total_cost_usd || 0)}</p>
                      </div>
                    </div>

                    <CostTrendChart data={data.token_usage_and_cost.daily_trend || []} />

                    <CostTable
                      title="Breakdown by Model"
                      data={data.token_usage_and_cost.by_model || []}
                      columns={[
                        { key: 'model', label: 'Model' },
                        { key: 'calls', label: 'Calls', format: (v: number) => (v ?? 0).toLocaleString() },
                        { key: 'cost_usd', label: 'Cost', format: (v: number) => formatCost(v ?? 0) },
                        { key: 'tokens', label: 'Tokens', format: (v: number) => formatTokens(v ?? 0) },
                      ]}
                    />
                    <CostTable
                      title="Breakdown by Caller"
                      data={data.token_usage_and_cost.by_caller || []}
                      columns={[
                        { key: 'caller', label: 'Module' },
                        { key: 'calls', label: 'Calls', format: (v: number) => (v ?? 0).toLocaleString() },
                        { key: 'cost_usd', label: 'Cost', format: (v: number) => formatCost(v ?? 0) },
                        { key: 'tokens', label: 'Tokens', format: (v: number) => formatTokens(v ?? 0) },
                      ]}
                    />
                  </div>
                )}
              </div>

              {/* User Feedback */}
              <div className="bg-white rounded-xl border border-slate-200 p-5">
                <SectionHeader icon={ThumbsUp} title="User Feedback" color="bg-sky-500" />
                {data.user_feedback.total_feedback === 0 ? (
                  <EmptyState
                    icon={ThumbsUp}
                    message="No feedback submitted yet"
                    hint="Users can rate reports with thumbs up/down"
                    actionLabel="Rate a research report to get started"
                  />
                ) : (
                  <div className="space-y-4">
                    <div className="grid grid-cols-3 gap-4">
                      <div>
                        <p className="text-xs text-slate-500">Total Ratings</p>
                        <p className="text-lg font-semibold text-slate-800">{data.user_feedback.total_feedback}</p>
                      </div>
                      <div>
                        <p className="text-xs text-slate-500">Positive</p>
                        <p className="text-lg font-semibold text-emerald-600">{data.user_feedback.positive_count || 0}</p>
                      </div>
                      <div>
                        <p className="text-xs text-slate-500">Negative</p>
                        <p className="text-lg font-semibold text-red-500">{data.user_feedback.negative_count || 0}</p>
                      </div>
                    </div>
                    {/* Satisfaction gauge */}
                    <div className="pt-3">
                      <div className="flex justify-between text-xs text-slate-500 mb-1">
                        <span>Satisfaction Rate</span>
                        <span className="font-medium">{Math.round((data.user_feedback.positive_rate || 0) * 100)}%</span>
                      </div>
                      <div className="h-3 bg-slate-100 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-gradient-to-r from-emerald-400 to-emerald-500 rounded-full transition-all"
                          style={{ width: `${(data.user_feedback.positive_rate || 0) * 100}%` }}
                        />
                      </div>
                    </div>
                    {/* T3.2: Recent comments */}
                    <RecentComments comments={data.user_feedback.recent_comments || []} />
                  </div>
                )}
              </div>
            </div>

            {/* T3.4: Recent Evaluations table */}
            <EvalReportsTable reports={evalReports} />

            {/* T4.2: Ingestion Health Summary */}
            {ingestionHealth.length > 0 && (
              <div className="mt-6 bg-white rounded-xl border border-slate-200 p-5">
                <SectionHeader icon={Zap} title="Ingestion Health" color="bg-violet-500" />
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
                  {ingestionHealth.map(src => (
                    <div key={src.source} className="border border-slate-100 rounded-lg p-3">
                      <div className="flex items-center gap-2 mb-1">
                        <span className={cn(
                          'w-2 h-2 rounded-full shrink-0',
                          src.status === 'green' ? 'bg-emerald-500'
                            : src.status === 'yellow' ? 'bg-amber-400'
                            : 'bg-red-500'
                        )} />
                        <span className="text-xs font-medium text-slate-700 truncate">
                          {src.source.replace(/_/g, ' ')}
                        </span>
                      </div>
                      <p className="text-lg font-semibold text-slate-800">{src.total_articles ?? 0}</p>
                      <p className="text-[10px] text-slate-400">{days}d total · avg {(src.avg_daily ?? 0).toFixed(0)}/day</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            </>

            {/* Footer info */}
            <div className="mt-6 text-center text-xs text-slate-400">
              <p>
                Dashboard generated{' '}
                <span title={new Date(data.generated_at).toLocaleString()}>
                  {timeAgo(data.generated_at)}
                </span>
                {' | '}Showing last {data.period_days} days
                {compare && ' | Comparing with previous period'}
              </p>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
