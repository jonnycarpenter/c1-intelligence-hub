'use client'

import { useState } from 'react'
import {
  Factory,
  RefreshCw,
  TrendingUp,
  TrendingDown,
  Minus,
  Loader2,
  AlertCircle,
  ExternalLink,
  ChevronDown,
  ChevronUp,
  Newspaper,
  X,
  Sparkles,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useIndustryNarratives, type MonthlyData } from '@/hooks'
import { api } from '@/lib/api'
import { MarkdownContent } from '@/components/ui'

// ============================================
// Delta Indicator
// ============================================

function formatDelta(delta: number): string {
  // Show as integer if whole number, otherwise 1 decimal place
  if (Number.isInteger(delta)) return delta > 0 ? `+${delta}` : `${delta}`
  return delta > 0 ? `+${delta.toFixed(1)}` : `${delta.toFixed(1)}`
}

function DeltaIndicator({ delta, showZero = false }: { delta: number | null; showZero?: boolean }) {
  if (delta === null) return <span className="text-xs text-slate-400">—</span>
  if (delta === 0 && !showZero) return <span className="text-xs text-slate-400">—</span>
  if (delta > 0) {
    return (
      <span className="inline-flex items-center gap-0.5 text-xs font-medium text-emerald-600">
        <TrendingUp size={12} />
        {formatDelta(delta)}
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-0.5 text-xs font-medium text-red-500">
      <TrendingDown size={12} />
      {formatDelta(delta)}
    </span>
  )
}

// ============================================
// Sentiment Bar
// ============================================

function SentimentBar({ sentiment }: { sentiment: { positive: number; neutral: number; negative: number } }) {
  const total = sentiment.positive + sentiment.neutral + sentiment.negative
  if (total === 0) return null

  const pPct = Math.round((sentiment.positive / total) * 100)
  const nPct = Math.round((sentiment.negative / total) * 100)
  const neuPct = 100 - pPct - nPct

  return (
    <div className="space-y-1">
      <div className="flex h-2 rounded-full overflow-hidden bg-slate-100">
        {pPct > 0 && (
          <div className="bg-emerald-400 transition-all" style={{ width: `${pPct}%` }} />
        )}
        {neuPct > 0 && (
          <div className="bg-slate-300 transition-all" style={{ width: `${neuPct}%` }} />
        )}
        {nPct > 0 && (
          <div className="bg-red-400 transition-all" style={{ width: `${nPct}%` }} />
        )}
      </div>
      <div className="flex justify-between text-[10px] text-slate-500">
        <span className="text-emerald-600">{pPct}% pos</span>
        <span>{neuPct}% neu</span>
        <span className="text-red-500">{nPct}% neg</span>
      </div>
    </div>
  )
}

// ============================================
// Collapsible Section
// ============================================

function CollapsibleSection({
  title,
  defaultOpen = true,
  children,
}: {
  title: string
  defaultOpen?: boolean
  children: React.ReactNode
}) {
  const [isOpen, setIsOpen] = useState(defaultOpen)

  return (
    <div className="border-t border-slate-100 pt-2">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center justify-between w-full text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5 hover:text-slate-700"
      >
        {title}
        {isOpen ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
      </button>
      {isOpen && children}
    </div>
  )
}

// ============================================
// Article Drawer
// ============================================

function ArticleDrawer({
  industry,
  month,
  filterLabel,
  onClose,
}: {
  industry: string
  month?: string
  filterLabel: string
  onClose: () => void
}) {
  const [articles, setArticles] = useState<any[]>([])
  const [totalCount, setTotalCount] = useState(0)
  const [isLoading, setIsLoading] = useState(true)
  const [offset, setOffset] = useState(0)
  const limit = 20

  const fetchArticles = async (newOffset: number) => {
    setIsLoading(true)
    try {
      const data = await api.getIndustryArticles(industry, { month, limit, offset: newOffset })
      setArticles(data.articles)
      setTotalCount(data.total_count)
      setOffset(newOffset)
    } catch (err) {
      console.error('Error fetching articles:', err)
    } finally {
      setIsLoading(false)
    }
  }

  useState(() => {
    fetchArticles(0)
  })

  return (
    <div className="fixed inset-y-0 right-0 w-[480px] bg-white shadow-2xl z-50 flex flex-col border-l border-slate-200">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200 bg-slate-50">
        <div>
          <h3 className="font-semibold text-slate-900 text-sm">{filterLabel}</h3>
          <p className="text-xs text-slate-500">{totalCount} articles</p>
        </div>
        <button onClick={onClose} className="p-1 hover:bg-slate-200 rounded">
          <X size={18} className="text-slate-500" />
        </button>
      </div>

      {/* Articles */}
      <div className="flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="flex items-center justify-center h-40">
            <Loader2 size={20} className="animate-spin text-emerald-500" />
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {articles.map((article) => (
              <div key={article.id} className="p-4 hover:bg-slate-50">
                <div className="flex items-start gap-2 mb-1">
                  <a
                    href={article.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm font-medium text-slate-900 hover:text-emerald-600 flex-1 line-clamp-2"
                  >
                    {article.title}
                  </a>
                  <ExternalLink size={14} className="text-slate-400 shrink-0 mt-0.5" />
                </div>
                <p className="text-xs text-slate-500 mb-2 line-clamp-2">{article.summary}</p>
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-[10px] text-slate-400">{article.source_name}</span>
                  {article.event_type && (
                    <span className="text-[10px] px-1.5 py-0.5 bg-emerald-50 text-emerald-600 rounded">
                      {article.event_type.replace(/_/g, ' ')}
                    </span>
                  )}
                  <span
                    className={cn(
                      'text-[10px] px-1.5 py-0.5 rounded',
                      article.sentiment === 'positive'
                        ? 'bg-emerald-50 text-emerald-600'
                        : article.sentiment === 'negative'
                          ? 'bg-red-50 text-red-600'
                          : 'bg-slate-50 text-slate-500'
                    )}
                  >
                    {article.sentiment}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Pagination */}
      {totalCount > limit && (
        <div className="flex items-center justify-between px-4 py-2 border-t border-slate-200 bg-slate-50">
          <button
            onClick={() => fetchArticles(Math.max(0, offset - limit))}
            disabled={offset === 0}
            className="text-xs text-emerald-600 disabled:text-slate-400"
          >
            Previous
          </button>
          <span className="text-xs text-slate-500">
            {offset + 1}–{Math.min(offset + limit, totalCount)} of {totalCount}
          </span>
          <button
            onClick={() => fetchArticles(offset + limit)}
            disabled={offset + limit >= totalCount}
            className="text-xs text-emerald-600 disabled:text-slate-400"
          >
            Next
          </button>
        </div>
      )}
    </div>
  )
}

// ============================================
// Narrative Banner (90-day arc + key insight)
// ============================================

function NarrativeBanner({
  narrative,
  keyInsight,
  enrichmentSources,
}: {
  narrative: string
  keyInsight: string
  enrichmentSources: number
}) {
  return (
    <div className="mx-6 mt-4 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 p-5 text-white shadow-lg">
      <div className="flex items-start gap-3 mb-3">
        <Sparkles size={20} className="text-emerald-200 shrink-0 mt-0.5" />
        <div>
          <h3 className="font-semibold text-sm mb-2">90-Day Narrative Arc</h3>
          <MarkdownContent content={narrative} className="text-sm leading-relaxed text-emerald-100" isUser />
        </div>
      </div>
      <div className="mt-4 pt-3 border-t border-emerald-400/30">
        <div className="flex items-start gap-2">
          <span className="text-[10px] font-semibold uppercase tracking-wider text-emerald-300 shrink-0 mt-0.5">
            Key Insight
          </span>
          <MarkdownContent content={keyInsight} className="text-sm font-medium" isUser />
        </div>
      </div>
      <div className="mt-2 text-[10px] text-emerald-300">
        Synthesized from {enrichmentSources} earnings quotes &amp; SEC filings
      </div>
    </div>
  )
}

// ============================================
// Month Column
// ============================================

function MonthColumn({
  data,
  monthNarrative,
  onViewArticles,
}: {
  data: MonthlyData
  monthNarrative?: string
  onViewArticles: (month: string, label: string) => void
}) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 flex flex-col min-w-0">
      {/* Month Header */}
      <div className="px-4 py-3 border-b border-slate-100 bg-slate-50/50 rounded-t-xl">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-slate-900 text-sm">{data.month_label}</h3>
            {data.is_partial && (
              <span className="text-[10px] font-semibold text-amber-600 bg-amber-50 px-1.5 py-0.5 rounded-full border border-amber-200">
                Month in Progress
              </span>
            )}
          </div>
          <DeltaIndicator delta={data.delta_per_day} showZero />
        </div>
        <div className="flex items-center gap-2 mt-1">
          <span className="text-2xl font-bold text-slate-900">{data.articles_per_day}</span>
          <span className="text-xs text-slate-500">articles / day</span>
        </div>
        <div className="text-[10px] text-slate-400 mt-0.5">
          {data.article_count} total across {data.days_in_period} days
        </div>
      </div>

      <div className="p-4 space-y-4 flex-1">
        {/* Month Narrative (if generated) */}
        {monthNarrative && (
          <div className="bg-emerald-50 border border-emerald-100 rounded-lg p-3">
            <div className="flex items-center gap-1.5 mb-1.5">
              <Sparkles size={12} className="text-emerald-500" />
              <span className="text-[10px] font-semibold text-emerald-600 uppercase tracking-wider">
                Narrative
              </span>
            </div>
            <MarkdownContent content={monthNarrative} className="text-xs text-emerald-900 leading-relaxed" />
          </div>
        )}

        {/* Event Types */}
        <CollapsibleSection title="Event Types">
          <div className="space-y-1">
            {data.event_types.slice(0, 8).map((evt) => (
              <div key={evt.name} className="flex items-center justify-between text-xs">
                <span className="text-slate-700 truncate mr-2">{evt.name.replace(/_/g, ' ')}</span>
                <div className="flex items-center gap-2 shrink-0">
                  <span className="font-medium text-slate-900 tabular-nums">{evt.per_day}/d</span>
                  <DeltaIndicator delta={evt.delta} />
                </div>
              </div>
            ))}
          </div>
        </CollapsibleSection>

        {/* Top Companies */}
        <CollapsibleSection title="Top Companies">
          <div className="space-y-1">
            {data.top_companies.slice(0, 8).map((co) => (
              <div key={co.name} className="flex items-center justify-between text-xs">
                <span className="text-slate-700 truncate mr-2">{co.name}</span>
                <div className="flex items-center gap-2 shrink-0">
                  <span className="font-medium text-slate-900 tabular-nums">{co.per_day}/d</span>
                  <DeltaIndicator delta={co.delta} />
                </div>
              </div>
            ))}
          </div>
        </CollapsibleSection>

        {/* Top Themes */}
        <CollapsibleSection title="Themes">
          <div className="flex flex-wrap gap-1">
            {data.top_themes.slice(0, 6).map((t) => (
              <span
                key={t.name}
                className="inline-flex items-center gap-1 px-2 py-0.5 text-[11px] bg-emerald-50 text-emerald-700 rounded-full"
              >
                {t.name.replace(/_/g, ' ')}
                <span className="font-semibold">{t.per_day}/d</span>
                {t.delta !== null && t.delta !== 0 && (
                  <span className={t.delta > 0 ? 'text-emerald-600' : 'text-red-500'}>
                    {formatDelta(t.delta)}
                  </span>
                )}
              </span>
            ))}
          </div>
        </CollapsibleSection>

        {/* Geographies */}
        {data.top_geographies.length > 0 && (
          <CollapsibleSection title="Geographies" defaultOpen={false}>
            <div className="flex flex-wrap gap-1">
              {data.top_geographies.map((g) => (
                <span
                  key={g.name}
                  className="inline-flex items-center gap-1 px-2 py-0.5 text-[11px] bg-slate-100 text-slate-600 rounded-full"
                >
                  {g.name}
                  <span className="font-semibold">{g.per_day}/d</span>
                </span>
              ))}
            </div>
          </CollapsibleSection>
        )}

        {/* Sentiment */}
        <CollapsibleSection title="Sentiment" defaultOpen={false}>
          <SentimentBar sentiment={data.sentiment} />
        </CollapsibleSection>

        {/* Top Articles */}
        <CollapsibleSection title="Key Articles">
          <div className="space-y-2">
            {data.top_articles.slice(0, 4).map((article) => (
              <a
                key={article.id}
                href={article.url}
                target="_blank"
                rel="noopener noreferrer"
                className="block group"
              >
                <p className="text-xs text-slate-800 group-hover:text-emerald-600 line-clamp-2 leading-relaxed">
                  {article.title}
                </p>
                <div className="flex items-center gap-1.5 mt-0.5">
                  <span className="text-[10px] text-slate-400">{article.source_name}</span>
                  {article.event_type && (
                    <span className="text-[10px] text-emerald-500">
                      {article.event_type.replace(/_/g, ' ')}
                    </span>
                  )}
                </div>
              </a>
            ))}
          </div>
        </CollapsibleSection>
      </div>

      {/* Footer */}
      <div className="px-4 py-2 border-t border-slate-100 bg-slate-50/50 rounded-b-xl">
        <button
          onClick={() => onViewArticles(data.month, data.month_label)}
          className="text-xs text-emerald-600 hover:text-emerald-700 font-medium flex items-center gap-1"
        >
          <Newspaper size={12} />
          View all {data.article_count} articles
        </button>
      </div>
    </div>
  )
}

// ============================================
// Main Dashboard
// ============================================

export default function IndustriesDashboard() {
  const {
    industries,
    selectedIndustry,
    selectIndustry,
    timeline,
    isLoadingList,
    isLoadingTimeline,
    error,
    refresh,
    narrative,
    isGeneratingNarrative,
    narrativeError,
    generateNarrative,
  } = useIndustryNarratives()

  const [drawer, setDrawer] = useState<{ industry: string; month: string; label: string } | null>(null)

  const handleViewArticles = (month: string, label: string) => {
    if (selectedIndustry) {
      setDrawer({ industry: selectedIndustry, month, label: `${timeline?.industry} — ${label}` })
    }
  }

  // Build a lookup for month narratives
  const monthNarrativeMap = new Map<string, string>()
  if (narrative?.monthly_narratives) {
    for (const mn of narrative.monthly_narratives) {
      monthNarrativeMap.set(mn.month, mn.narrative)
    }
  }

  return (
    <div className="h-full flex flex-col bg-gradient-to-br from-slate-50 to-emerald-50/30">
      {/* Header */}
      <div className="px-6 py-4 border-b border-slate-200 bg-white/80 backdrop-blur-sm shrink-0">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-emerald-500 flex items-center justify-center">
              <Factory size={18} className="text-white" />
            </div>
            <div>
              <h1 className="font-semibold text-slate-900">Industry Narratives</h1>
              <p className="text-xs text-slate-500">
                90-day narrative timelines by composites end-market
              </p>
            </div>
          </div>
          <button
            onClick={refresh}
            disabled={isLoadingList || isLoadingTimeline}
            className="p-2 text-slate-500 hover:text-slate-700 hover:bg-slate-100 rounded-lg transition-colors"
          >
            <RefreshCw size={16} className={isLoadingTimeline ? 'animate-spin' : ''} />
          </button>
        </div>

        {/* Industry Selector Pills */}
        {!isLoadingList && industries.length > 0 && (
          <div className="flex gap-2 overflow-x-auto pb-2">
            {industries.map((ind) => {
              const isActive = selectedIndustry === ind.id
              return (
                <button
                  key={ind.id}
                  onClick={() => selectIndustry(ind.id)}
                  className={cn(
                    'flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium whitespace-nowrap transition-all shrink-0',
                    isActive
                      ? 'bg-emerald-600 text-white shadow-sm'
                      : 'bg-white text-slate-600 border border-slate-200 hover:border-emerald-300 hover:text-emerald-600'
                  )}
                >
                  {ind.name}
                  <span
                    className={cn(
                      'text-xs tabular-nums',
                      isActive ? 'text-emerald-200' : 'text-slate-400'
                    )}
                  >
                    {ind.article_count_90d}
                  </span>
                  {ind.trend === 'up' && (
                    <TrendingUp size={12} className={isActive ? 'text-emerald-300' : 'text-emerald-500'} />
                  )}
                  {ind.trend === 'down' && (
                    <TrendingDown size={12} className={isActive ? 'text-red-300' : 'text-red-500'} />
                  )}
                  {ind.trend === 'flat' && (
                    <Minus size={12} className={isActive ? 'text-emerald-300' : 'text-slate-400'} />
                  )}
                </button>
              )
            })}
          </div>
        )}
      </div>

      {/* Error */}
      {error && (
        <div className="mx-6 mt-4 flex items-center gap-2 p-3 bg-red-50 text-red-700 rounded-lg">
          <AlertCircle size={16} />
          <span className="text-sm">{error}</span>
        </div>
      )}

      {/* Loading State */}
      {(isLoadingList || isLoadingTimeline) && !timeline && (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <Loader2 size={28} className="animate-spin text-emerald-500 mx-auto mb-3" />
            <p className="text-sm text-slate-500">Loading narrative data...</p>
          </div>
        </div>
      )}

      {/* Timeline Summary */}
      {timeline && !isLoadingTimeline && (
        <>
          <div className="px-6 py-3 border-b border-slate-200 bg-white/50 flex items-center gap-6 shrink-0">
            <div>
              <span className="text-xs text-slate-500">Total Articles</span>
              <p className="text-lg font-bold text-slate-900">{timeline.totals.total_articles}</p>
            </div>
            <div>
              <span className="text-xs text-slate-500">Avg / Month</span>
              <p className="text-lg font-bold text-slate-900">{timeline.totals.avg_monthly}</p>
            </div>
            <div>
              <span className="text-xs text-slate-500">Trend</span>
              <p className="text-lg font-bold">
                {timeline.totals.trend_direction === 'up' && (
                  <span className="text-emerald-600 flex items-center gap-1">
                    <TrendingUp size={18} /> Rising
                  </span>
                )}
                {timeline.totals.trend_direction === 'down' && (
                  <span className="text-red-500 flex items-center gap-1">
                    <TrendingDown size={18} /> Declining
                  </span>
                )}
                {timeline.totals.trend_direction === 'flat' && (
                  <span className="text-slate-500 flex items-center gap-1">
                    <Minus size={18} /> Stable
                  </span>
                )}
              </p>
            </div>
            <div className="ml-auto">
              <button
                onClick={generateNarrative}
                disabled={isGeneratingNarrative}
                className={cn(
                  'inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all',
                  isGeneratingNarrative
                    ? 'bg-emerald-100 text-emerald-400 cursor-not-allowed'
                    : 'bg-emerald-600 text-white hover:bg-emerald-700 shadow-sm hover:shadow'
                )}
              >
                {isGeneratingNarrative ? (
                  <Loader2 size={16} className="animate-spin" />
                ) : (
                  <Sparkles size={16} />
                )}
                {isGeneratingNarrative ? 'Generating...' : 'Generate Narrative'}
              </button>
            </div>
          </div>

          {/* Narrative Error */}
          {narrativeError && (
            <div className="mx-6 mt-3 flex items-center gap-2 p-3 bg-red-50 text-red-700 rounded-lg">
              <AlertCircle size={16} />
              <span className="text-sm">{narrativeError}</span>
            </div>
          )}

          {/* Scrollable area: narrative banner + monthly grid */}
          <div className="flex-1 overflow-auto min-h-0">
            {/* Overall Narrative Banner */}
            {narrative && (
              <NarrativeBanner
                narrative={narrative.industry_narrative}
                keyInsight={narrative.key_insight}
                enrichmentSources={narrative.enrichment_sources_used}
              />
            )}

            {/* Monthly Timeline Grid */}
            <div className="p-6">
              {timeline.monthly_data.length === 0 ? (
                <div className="flex items-center justify-center h-40 text-center">
                  <div>
                    <Factory size={40} className="text-slate-300 mx-auto mb-3" />
                    <p className="text-sm text-slate-500">No articles found for this industry in the last 90 days</p>
                  </div>
                </div>
              ) : (
                <div
                  className="grid gap-4"
                  style={{
                    gridTemplateColumns: `repeat(${Math.min(timeline.monthly_data.length, 3)}, minmax(320px, 1fr))`,
                  }}
                >
                  {timeline.monthly_data.slice(0, 3).map((month) => (
                    <MonthColumn
                      key={month.month}
                      data={month}
                      monthNarrative={monthNarrativeMap.get(month.month)}
                      onViewArticles={handleViewArticles}
                    />
                  ))}
                </div>
              )}
            </div>
          </div>
        </>
      )}

      {/* Loading overlay for timeline refresh */}
      {isLoadingTimeline && timeline && (
        <div className="absolute inset-0 bg-white/50 flex items-center justify-center z-10">
          <Loader2 size={28} className="animate-spin text-emerald-500" />
        </div>
      )}

      {/* Article Drawer */}
      {drawer && (
        <>
          <div
            className="fixed inset-0 bg-black/20 z-40"
            onClick={() => setDrawer(null)}
          />
          <ArticleDrawer
            industry={drawer.industry}
            month={drawer.month}
            filterLabel={drawer.label}
            onClose={() => setDrawer(null)}
          />
        </>
      )}
    </div>
  )
}
