'use client'

import { useState, useEffect } from 'react'
import {
  TrendingUp,
  FileText,
  Newspaper,
  ChevronDown,
  ChevronRight,
  Loader2,
  ExternalLink,
  Quote,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { api } from '@/lib/api'

interface IntelligencePanelProps {
  importyetiKey: string
  companyName: string
}

interface IntelligenceData {
  company_name: string
  ticker: string | null
  earnings_quotes: Array<Record<string, any>>
  sec_nuggets: Array<Record<string, any>>
  recent_articles: Array<Record<string, any>>
}

export default function IntelligencePanel({ importyetiKey, companyName }: IntelligencePanelProps) {
  const [data, setData] = useState<IntelligenceData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    const fetchIntelligence = async () => {
      setLoading(true)
      setError(null)
      try {
        const result = await api.getCompanyIntelligence(importyetiKey)
        if (!cancelled) setData(result)
      } catch (err: any) {
        if (!cancelled) setError(err.message || 'Failed to load intelligence')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    fetchIntelligence()
    return () => { cancelled = true }
  }, [importyetiKey])

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-center">
          <Loader2 className="w-6 h-6 animate-spin text-indigo-500 mx-auto mb-2" />
          <p className="text-xs text-slate-500">Loading intelligence...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-4 text-center">
        <p className="text-xs text-red-500">{error}</p>
      </div>
    )
  }

  if (!data) return null

  const totalItems =
    (data.earnings_quotes?.length || 0) +
    (data.sec_nuggets?.length || 0) +
    (data.recent_articles?.length || 0)

  if (totalItems === 0) {
    return (
      <div className="p-4 text-center">
        <p className="text-xs text-slate-400">No supply chain intelligence found for {companyName}</p>
      </div>
    )
  }

  return (
    <div className="space-y-1">
      <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider px-1 mb-2">
        Supply Chain Intelligence
      </h3>

      {/* Earnings Quotes */}
      {data.earnings_quotes?.length > 0 && (
        <CollapsibleSection
          title="Executive Quotes"
          icon={TrendingUp}
          iconColor="text-amber-500"
          count={data.earnings_quotes.length}
          defaultOpen={true}
        >
          <div className="space-y-2">
            {data.earnings_quotes.map((quote, i) => (
              <div key={i} className="pl-3 border-l-2 border-amber-200">
                <p className="text-xs text-slate-700 italic leading-relaxed">
                  &ldquo;{quote.quote_text || quote.text || 'No text'}&rdquo;
                </p>
                <div className="flex items-center gap-2 mt-1 text-[10px] text-slate-400">
                  {quote.speaker_name && <span className="font-medium text-slate-500">{quote.speaker_name}</span>}
                  {quote.speaker_title && <span>&middot; {quote.speaker_title}</span>}
                  {(quote.quarter || quote.year) && (
                    <span>&middot; Q{quote.quarter} {quote.year}</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </CollapsibleSection>
      )}

      {/* SEC Nuggets */}
      {data.sec_nuggets?.length > 0 && (
        <CollapsibleSection
          title="SEC Insights"
          icon={FileText}
          iconColor="text-blue-500"
          count={data.sec_nuggets.length}
          defaultOpen={true}
        >
          <div className="space-y-2">
            {data.sec_nuggets.map((nugget, i) => (
              <div key={i} className="pl-3 border-l-2 border-blue-200">
                <p className="text-xs text-slate-700 leading-relaxed">
                  {nugget.nugget_text || nugget.text || 'No text'}
                </p>
                <div className="flex items-center gap-2 mt-1 text-[10px] text-slate-400">
                  {nugget.filing_type && (
                    <span className="px-1 py-0.5 bg-blue-50 text-blue-600 rounded font-medium">
                      {nugget.filing_type}
                    </span>
                  )}
                  {nugget.signal_strength && (
                    <span className={cn(
                      'px-1 py-0.5 rounded font-medium',
                      nugget.signal_strength === 'explicit' ? 'bg-red-50 text-red-600' :
                      nugget.signal_strength === 'new' ? 'bg-emerald-50 text-emerald-600' :
                      'bg-slate-100 text-slate-500'
                    )}>
                      {nugget.signal_strength}
                    </span>
                  )}
                  {nugget.is_new_disclosure && (
                    <span className="px-1 py-0.5 bg-emerald-50 text-emerald-600 rounded font-medium">NEW</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </CollapsibleSection>
      )}

      {/* Recent Articles */}
      {data.recent_articles?.length > 0 && (
        <CollapsibleSection
          title="Recent News"
          icon={Newspaper}
          iconColor="text-emerald-500"
          count={data.recent_articles.length}
          defaultOpen={false}
        >
          <div className="space-y-2">
            {data.recent_articles.map((article, i) => (
              <div key={i} className="group">
                {article.url ? (
                  <a
                    href={article.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="block"
                  >
                    <p className="text-xs text-slate-700 font-medium group-hover:text-indigo-600 transition-colors leading-snug">
                      {article.title}
                      <ExternalLink size={10} className="inline ml-1 opacity-0 group-hover:opacity-100 transition-opacity" />
                    </p>
                  </a>
                ) : (
                  <p className="text-xs text-slate-700 font-medium leading-snug">{article.title}</p>
                )}
                <div className="flex items-center gap-2 mt-0.5 text-[10px] text-slate-400">
                  {article.source && <span>{article.source}</span>}
                  {article.published_at && (
                    <span>&middot; {new Date(article.published_at).toLocaleDateString()}</span>
                  )}
                  {article.category && (
                    <span className="px-1 py-0.5 bg-slate-100 text-slate-500 rounded">{article.category}</span>
                  )}
                </div>
                {article.summary && (
                  <p className="text-[11px] text-slate-500 mt-1 line-clamp-2">{article.summary}</p>
                )}
              </div>
            ))}
          </div>
        </CollapsibleSection>
      )}
    </div>
  )
}


function CollapsibleSection({
  title,
  icon: Icon,
  iconColor,
  count,
  defaultOpen,
  children,
}: {
  title: string
  icon: typeof TrendingUp
  iconColor: string
  count: number
  defaultOpen: boolean
  children: React.ReactNode
}) {
  const [open, setOpen] = useState(defaultOpen)

  return (
    <div className="rounded-lg border border-slate-100 overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-2 px-3 py-2 hover:bg-slate-50 transition-colors"
      >
        {open ? (
          <ChevronDown size={12} className="text-slate-400" />
        ) : (
          <ChevronRight size={12} className="text-slate-400" />
        )}
        <Icon size={14} className={iconColor} />
        <span className="text-xs font-medium text-slate-700 flex-1 text-left">{title}</span>
        <span className="text-[10px] text-slate-400 bg-slate-100 px-1.5 py-0.5 rounded-full">
          {count}
        </span>
      </button>
      {open && <div className="px-3 pb-3">{children}</div>}
    </div>
  )
}
