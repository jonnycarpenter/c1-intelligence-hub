'use client'

import { useState, useEffect } from 'react'
import {
  Brain, CheckCircle, FileText, ChevronDown, ChevronRight,
  Search, FlaskConical, Clock, TrendingUp, AlertCircle,
} from 'lucide-react'
import {
  LineChart, Line, XAxis, YAxis, Tooltip as RechartsTooltip,
  ResponsiveContainer, CartesianGrid, Legend,
} from 'recharts'
import { cn } from '@/lib/utils'
import { api } from '@/lib/api'

// ── Types ──

interface JudgeScores {
  total_evals: number
  avg_factual_grounding?: number
  avg_coherence?: number
  avg_actionability?: number
  avg_overall?: number
}

interface QualityMetrics {
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

interface EvalTrend {
  week: string
  avg_overall: number
  avg_factual: number
  avg_coherence: number
  avg_actionability: number
  eval_count: number
}

// ── Helper components ──

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

const scoreColor = (s: number) =>
  s >= 4 ? 'text-emerald-600 bg-emerald-50' : s >= 3 ? 'text-amber-600 bg-amber-50' : 'text-red-600 bg-red-50'

// ── Eval Reports Table ──

function EvalReportsTable({ reports }: { reports: EvalReport[] }) {
  const [expandedId, setExpandedId] = useState<string | null>(null)

  if (!reports || reports.length === 0) {
    return (
      <div className="text-center py-8 border-2 border-dashed border-slate-200 rounded-xl">
        <FlaskConical size={20} className="text-slate-400 mx-auto mb-2" />
        <p className="text-sm text-slate-500">No evaluations yet</p>
        <p className="text-xs text-slate-400 mt-1">Run an evaluation from the Overview tab</p>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
      <div className="px-5 py-4 border-b border-slate-100">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg flex items-center justify-center bg-violet-500">
            <FileText size={14} className="text-white" />
          </div>
          <h3 className="font-semibold text-slate-800">Evaluation Results</h3>
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

// ── Score Trend Chart (T4.6) ──

function ScoreTrendChart({ data }: { data: EvalTrend[] }) {
  if (!data || data.length === 0) {
    return (
      <div className="text-center py-8 border-2 border-dashed border-slate-200 rounded-xl">
        <TrendingUp size={20} className="text-slate-400 mx-auto mb-2" />
        <p className="text-sm text-slate-500">Not enough data for trends</p>
        <p className="text-xs text-slate-400 mt-1">Trends appear after evaluating reports across multiple weeks</p>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5">
      <h4 className="text-sm font-semibold text-slate-700 mb-4 flex items-center gap-2">
        <TrendingUp size={14} className="text-indigo-500" />
        Quality Score Trends
      </h4>
      <ResponsiveContainer width="100%" height={260}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
          <XAxis
            dataKey="week"
            tick={{ fontSize: 10 }}
            tickFormatter={(v: string) => v.slice(5, 10)}
          />
          <YAxis
            domain={[0, 5]}
            tick={{ fontSize: 10 }}
            ticks={[1, 2, 3, 4, 5]}
          />
          <RechartsTooltip
            contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e2e8f0' }}
            formatter={(v: any, name: any) => {
              const labels: Record<string, string> = {
                avg_overall: 'Overall',
                avg_factual: 'Factual',
                avg_coherence: 'Coherence',
                avg_actionability: 'Actionability',
              }
              return [Number(v).toFixed(2), labels[name] || name]
            }}
            labelFormatter={(l) => `Week of ${l}`}
          />
          <Legend
            verticalAlign="top"
            height={36}
            formatter={(value: string) => {
              const labels: Record<string, string> = {
                avg_overall: 'Overall',
                avg_factual: 'Factual',
                avg_coherence: 'Coherence',
                avg_actionability: 'Actionability',
              }
              return labels[value] || value
            }}
          />
          <Line type="monotone" dataKey="avg_overall" stroke="#6366f1" strokeWidth={2.5} dot={{ r: 3 }} name="avg_overall" />
          <Line type="monotone" dataKey="avg_factual" stroke="#10b981" strokeWidth={1.5} dot={{ r: 2 }} name="avg_factual" />
          <Line type="monotone" dataKey="avg_coherence" stroke="#f59e0b" strokeWidth={1.5} dot={{ r: 2 }} name="avg_coherence" />
          <Line type="monotone" dataKey="avg_actionability" stroke="#ec4899" strokeWidth={1.5} dot={{ r: 2 }} name="avg_actionability" />
        </LineChart>
      </ResponsiveContainer>
      <div className="flex items-center gap-2 mt-2 text-xs text-slate-400">
        <span>Showing {data.length} weeks</span>
        <span>·</span>
        <span>{data.reduce((s, d) => s + d.eval_count, 0)} total evaluations</span>
      </div>
    </div>
  )
}

// ── Main Quality View ──

export default function QualityView({
  quality,
  judge,
  evalReports,
  days,
}: {
  quality: QualityMetrics
  judge: JudgeScores
  evalReports: EvalReport[]
  days: number
}) {
  const [evalTrends, setEvalTrends] = useState<EvalTrend[]>([])
  const [trendsWeeks, setTrendsWeeks] = useState(12)

  useEffect(() => {
    const loadTrends = async () => {
      try {
        const res = await api.getEvalTrends(trendsWeeks)
        if (res?.eval_trends) setEvalTrends(res.eval_trends)
      } catch { /* ignore */ }
    }
    loadTrends()
  }, [trendsWeeks])

  return (
    <div className="space-y-6">
      {/* Top metrics grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Deep Research Quality */}
        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <div className="flex items-center gap-2 mb-4">
            <div className="w-7 h-7 rounded-lg flex items-center justify-center bg-emerald-500">
              <CheckCircle size={14} className="text-white" />
            </div>
            <h3 className="font-semibold text-slate-800">Deep Research Quality</h3>
          </div>
          {quality.deep_research.total_reports === 0 ? (
            <div className="text-center py-8 border-2 border-dashed border-slate-200 rounded-xl">
              <Search size={20} className="text-slate-400 mx-auto mb-2" />
              <p className="text-sm text-slate-500">No reports in this period</p>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-xs text-slate-500">Citation Health</p>
                  <p className="text-lg font-semibold text-slate-800">{quality.deep_research.citation_health_rate}%</p>
                </div>
                <div>
                  <p className="text-xs text-slate-500">Validation Pass Rate</p>
                  <p className="text-lg font-semibold text-slate-800">{quality.deep_research.validation_pass_rate}%</p>
                </div>
                <div>
                  <p className="text-xs text-slate-500">Avg Citations</p>
                  <p className="text-lg font-semibold text-slate-800">{quality.deep_research.avg_citation_count}</p>
                </div>
                <div>
                  <p className="text-xs text-slate-500">Avg Sources</p>
                  <p className="text-lg font-semibold text-slate-800">{quality.deep_research.avg_sources_count}</p>
                </div>
              </div>
              <div>
                <p className="text-xs text-slate-500 mb-2">Avg Research Time</p>
                <div className="flex items-center gap-2">
                  <Clock size={14} className="text-slate-400" />
                  <span className="text-sm font-medium text-slate-700">{quality.deep_research.avg_research_time_seconds}s</span>
                </div>
              </div>
              <div>
                <p className="text-xs text-slate-500 mb-2">Confidence Distribution</p>
                <ConfidenceDistribution data={quality.deep_research.confidence_distribution} />
              </div>
            </div>
          )}
        </div>

        {/* LLM Judge Scores */}
        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <div className="flex items-center gap-2 mb-4">
            <div className="w-7 h-7 rounded-lg flex items-center justify-center bg-indigo-500">
              <Brain size={14} className="text-white" />
            </div>
            <h3 className="font-semibold text-slate-800">LLM-as-Judge Scores</h3>
          </div>
          {judge.total_evals === 0 ? (
            <div className="text-center py-8 border-2 border-dashed border-slate-200 rounded-xl">
              <FlaskConical size={20} className="text-slate-400 mx-auto mb-2" />
              <p className="text-sm text-slate-500">No evaluations yet</p>
              <p className="text-xs text-slate-400 mt-1">Run an eval from the Overview tab</p>
            </div>
          ) : (
            <div className="space-y-4">
              <p className="text-xs text-slate-400">{judge.total_evals} reports evaluated</p>
              <ScoreBar label="Factual Grounding" score={judge.avg_factual_grounding || 0} />
              <ScoreBar label="Coherence" score={judge.avg_coherence || 0} />
              <ScoreBar label="Actionability" score={judge.avg_actionability || 0} />
              <div className="pt-2 border-t border-slate-100">
                <ScoreBar label="Overall" score={judge.avg_overall || 0} />
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Score Trend Chart (T4.6) */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <div />
          <select
            value={trendsWeeks}
            onChange={e => setTrendsWeeks(Number(e.target.value))}
            className="text-xs border border-slate-200 rounded-lg px-2 py-1 text-slate-600"
          >
            <option value={4}>Last 4 weeks</option>
            <option value={8}>Last 8 weeks</option>
            <option value={12}>Last 12 weeks</option>
          </select>
        </div>
        <ScoreTrendChart data={evalTrends} />
      </div>

      {/* Per-report evaluation table */}
      <EvalReportsTable reports={evalReports} />
    </div>
  )
}
