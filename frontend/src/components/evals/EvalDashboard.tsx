'use client'

import { useState, useEffect, useCallback } from 'react'
import {
  BarChart3, DollarSign, ThumbsUp, Brain, RefreshCw, AlertCircle,
  CheckCircle, FileText, Clock, Zap, TrendingUp, ChevronDown, ChevronRight,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { api } from '@/lib/api'

// ── Types ──

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
  }
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

function EmptyState({ message, hint }: { message: string; hint?: string }) {
  return (
    <div className="text-center py-6">
      <AlertCircle size={20} className="mx-auto text-slate-300 mb-2" />
      <p className="text-sm text-slate-500">{message}</p>
      {hint && <p className="text-xs text-slate-400 mt-1">{hint}</p>}
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

// ── Sparkline (CSS-only mini bar chart for daily trend) ──

function DailyTrendChart({ data }: { data: Array<{ date: string; cost_usd: number; calls: number }> }) {
  if (!data || data.length === 0) return null
  const maxCost = Math.max(...data.map(d => d.cost_usd), 0.001)

  return (
    <div className="mt-4">
      <p className="text-xs font-medium text-slate-500 mb-2">Daily Cost Trend</p>
      <div className="flex items-end gap-[2px] h-16">
        {data.map((d, i) => {
          const height = Math.max((d.cost_usd / maxCost) * 100, 4)
          return (
            <div
              key={i}
              className="flex-1 bg-amber-400 hover:bg-amber-500 rounded-t transition-colors group relative"
              style={{ height: `${height}%` }}
              title={`${d.date}: $${d.cost_usd.toFixed(4)} (${d.calls} calls)`}
            />
          )
        })}
      </div>
      <div className="flex justify-between mt-1">
        <span className="text-[10px] text-slate-400">{data[0]?.date?.slice(5)}</span>
        <span className="text-[10px] text-slate-400">{data[data.length - 1]?.date?.slice(5)}</span>
      </div>
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

// ── Main Dashboard ──

export default function EvalDashboard() {
  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [days, setDays] = useState(30)

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await api.getEvalDashboard(days)
      setData(result)
    } catch (err: any) {
      setError(err.message || 'Failed to load dashboard')
    } finally {
      setLoading(false)
    }
  }, [days])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  const formatTokens = (n: number) => {
    if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
    if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`
    return String(n)
  }

  const formatCost = (n: number) => {
    if (n >= 1) return `$${n.toFixed(2)}`
    if (n >= 0.01) return `$${n.toFixed(3)}`
    return `$${n.toFixed(4)}`
  }

  return (
    <div className="h-full overflow-y-auto bg-slate-50">
      {/* Header */}
      <div className="bg-white border-b border-slate-200 px-6 py-5">
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2">
              <BarChart3 size={22} className="text-amber-500" />
              <h1 className="text-xl font-semibold text-slate-800">AI Quality Dashboard</h1>
            </div>
            <p className="text-sm text-slate-500 mt-1">
              Evaluation metrics, LLM cost tracking, and user feedback
            </p>
          </div>
          <div className="flex items-center gap-3">
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
            <button
              onClick={fetchData}
              disabled={loading}
              className="flex items-center gap-1.5 text-sm px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-600 rounded-lg transition-colors disabled:opacity-50"
            >
              <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
              Refresh
            </button>
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

        {/* Loading state */}
        {loading && !data && (
          <div className="flex flex-col items-center justify-center py-20">
            <RefreshCw size={24} className="text-amber-500 animate-spin mb-3" />
            <p className="text-sm text-slate-500">Loading dashboard data...</p>
          </div>
        )}

        {data && (
          <>
            {/* Top-level stat cards */}
            <div className="grid grid-cols-4 gap-4 mb-6">
              <StatCard
                icon={FileText}
                label="Reports Generated"
                value={data.quality_metrics.deep_research.total_reports || 0}
                sub={`${data.quality_metrics.weekly_briefing.total_briefings || 0} weekly briefings`}
                color="bg-emerald-500"
              />
              <StatCard
                icon={DollarSign}
                label="Total LLM Cost"
                value={data.token_usage_and_cost.total_cost_usd ? formatCost(data.token_usage_and_cost.total_cost_usd) : '$0.00'}
                sub={data.token_usage_and_cost.total_calls ? `${data.token_usage_and_cost.total_calls.toLocaleString()} API calls` : 'No data yet'}
                color="bg-amber-500"
              />
              <StatCard
                icon={Brain}
                label="Avg Quality Score"
                value={data.llm_judge_scores.avg_overall ? `${data.llm_judge_scores.avg_overall}/5` : 'N/A'}
                sub={data.llm_judge_scores.total_evals ? `${data.llm_judge_scores.total_evals} reports evaluated` : 'Run eval script to populate'}
                color="bg-indigo-500"
              />
              <StatCard
                icon={ThumbsUp}
                label="User Satisfaction"
                value={data.user_feedback.positive_rate != null ? `${Math.round(data.user_feedback.positive_rate * 100)}%` : 'N/A'}
                sub={data.user_feedback.total_feedback ? `${data.user_feedback.total_feedback} ratings` : 'No feedback yet'}
                color="bg-sky-500"
              />
            </div>

            {/* Main grid */}
            <div className="grid grid-cols-2 gap-6">
              {/* Quality Metrics */}
              <div className="bg-white rounded-xl border border-slate-200 p-5">
                <SectionHeader icon={CheckCircle} title="Quality Metrics (Deep Research)" color="bg-emerald-500" />
                {data.quality_metrics.deep_research.total_reports === 0 ? (
                  <EmptyState message="No reports in this period" hint="Run a Deep Research query to generate data" />
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
                    message="No evaluations yet"
                    hint="Run: python scripts/testing/eval_llm_judge.py"
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

                    <DailyTrendChart data={data.token_usage_and_cost.daily_trend || []} />

                    <CostTable
                      title="Breakdown by Model"
                      data={data.token_usage_and_cost.by_model || []}
                      columns={[
                        { key: 'model', label: 'Model' },
                        { key: 'calls', label: 'Calls', format: (v: number) => v.toLocaleString() },
                        { key: 'cost_usd', label: 'Cost', format: (v: number) => formatCost(v) },
                        { key: 'tokens', label: 'Tokens', format: (v: number) => formatTokens(v) },
                      ]}
                    />
                    <CostTable
                      title="Breakdown by Caller"
                      data={data.token_usage_and_cost.by_caller || []}
                      columns={[
                        { key: 'caller', label: 'Module' },
                        { key: 'calls', label: 'Calls', format: (v: number) => v.toLocaleString() },
                        { key: 'cost_usd', label: 'Cost', format: (v: number) => formatCost(v) },
                        { key: 'tokens', label: 'Tokens', format: (v: number) => formatTokens(v) },
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
                    message="No feedback submitted yet"
                    hint="Users can rate reports with thumbs up/down"
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
                  </div>
                )}
              </div>
            </div>

            {/* Footer info */}
            <div className="mt-6 text-center text-xs text-slate-400">
              <p>
                Dashboard generated at {new Date(data.generated_at).toLocaleString()}
                {' | '}Showing last {data.period_days} days
              </p>
              <p className="mt-1">
                Run <code className="bg-slate-100 px-1.5 py-0.5 rounded text-[11px]">python scripts/testing/eval_llm_judge.py</code> to populate judge scores
                {' | '}
                <code className="bg-slate-100 px-1.5 py-0.5 rounded text-[11px]">python scripts/monitoring/eval_dashboard.py</code> for CLI view
              </p>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
