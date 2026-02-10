'use client'

import React, { useState } from 'react'
import {
  ChevronDown,
  ChevronUp,
  TrendingUp,
  TrendingDown,
  Minus,
  FileText,
  BarChart3,
  AlertTriangle,
  Sparkles,
  Shield,
  Target,
} from 'lucide-react'
import { Badge } from '@/components/ui'
import { cn } from '@/lib/utils'
import type { FinancialFeedItem } from '@/types'

// =============================================================================
// Sentiment config
// =============================================================================

const sentimentConfig: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
  bullish: { label: 'Bullish', color: 'bg-emerald-50 text-emerald-700 border-emerald-200', icon: <TrendingUp size={11} /> },
  bearish: { label: 'Bearish', color: 'bg-red-50 text-red-700 border-red-200', icon: <TrendingDown size={11} /> },
  cautious: { label: 'Cautious', color: 'bg-amber-50 text-amber-700 border-amber-200', icon: <AlertTriangle size={11} /> },
  neutral: { label: 'Neutral', color: 'bg-slate-50 text-slate-600 border-slate-200', icon: <Minus size={11} /> },
}

const signalStrengthConfig: Record<string, { label: string; style: string }> = {
  new: { label: 'NEW', style: 'bg-emerald-500 text-white' },
  explicit: { label: 'Explicit', style: 'bg-blue-100 text-blue-700 border border-blue-200' },
  standard: { label: 'Standard', style: 'bg-slate-100 text-slate-600 border border-slate-200' },
  hedged: { label: 'Hedged', style: 'bg-amber-100 text-amber-700 border border-amber-200' },
  buried: { label: 'Buried', style: 'bg-slate-200 text-slate-500 border border-slate-300' },
}

const riskLevelConfig: Record<string, { label: string; color: string }> = {
  high: { label: 'High Risk', color: 'bg-red-50 text-red-700 border-red-200' },
  medium: { label: 'Medium Risk', color: 'bg-amber-50 text-amber-700 border-amber-200' },
  low: { label: 'Low Risk', color: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
}

function formatQuoteType(type: string): string {
  return type
    .split('_')
    .map(w => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')
}

function formatTheme(theme: string): string {
  return theme
    .split('_')
    .map(w => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')
}

// =============================================================================
// Earnings Quote Card
// =============================================================================

function EarningsQuoteCard({ item }: { item: FinancialFeedItem }) {
  const [isExpanded, setIsExpanded] = useState(false)
  const isLong = item.text.length > 200
  const sentiment = item.sentiment ? sentimentConfig[item.sentiment] : null

  return (
    <div className="bg-white rounded-xl border border-slate-200 border-l-4 border-l-blue-500 shadow-sm hover:shadow-md transition-shadow">
      <div className="p-4 space-y-3">
        {/* Header: ticker + quarter + source badge */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-semibold rounded bg-blue-50 text-blue-700 border border-blue-200">
              <BarChart3 size={11} />
              Earnings
            </span>
            <span className="text-sm font-bold text-slate-800">{item.ticker}</span>
            {item.year && item.quarter && (
              <span className="text-xs text-slate-500">Q{item.quarter} {item.year}</span>
            )}
            {item.call_section && (
              <span className="text-xs text-slate-400">
                {item.call_section === 'prepared_remarks' ? 'Prepared Remarks' : 'Q&A'}
              </span>
            )}
          </div>
          {item.relevance_score > 0 && (
            <span className={cn(
              'text-xs px-1.5 py-0.5 rounded',
              item.relevance_score >= 0.7 ? 'bg-emerald-50 text-emerald-600' :
              item.relevance_score >= 0.4 ? 'bg-blue-50 text-blue-600' : 'bg-slate-50 text-slate-500'
            )}>
              {Math.round(item.relevance_score * 100)}%
            </span>
          )}
        </div>

        {/* Quote text */}
        <blockquote className={cn(
          'text-sm text-slate-700 italic border-l-2 border-blue-200 pl-3',
          !isExpanded && isLong && 'line-clamp-3'
        )}>
          &ldquo;{item.text}&rdquo;
        </blockquote>
        {isLong && (
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="text-xs text-blue-600 hover:text-blue-700 flex items-center gap-0.5"
          >
            {isExpanded ? <><ChevronUp size={12} /> Show less</> : <><ChevronDown size={12} /> Read more</>}
          </button>
        )}

        {/* Context summary */}
        {item.context && (
          <p className="text-xs text-slate-500">{item.context}</p>
        )}

        {/* Speaker attribution */}
        {item.speaker_name && (
          <div className="text-xs text-slate-600">
            <span className="font-medium">&mdash; {item.speaker_name}</span>
            {item.speaker_title && <span className="text-slate-400">, {item.speaker_title}</span>}
            {item.speaker_company && <span className="text-slate-400"> at {item.speaker_company}</span>}
          </div>
        )}

        {/* Badges row */}
        <div className="flex flex-wrap items-center gap-1.5">
          {sentiment && (
            <span className={cn('inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded-full border', sentiment.color)}>
              {sentiment.icon} {sentiment.label}
            </span>
          )}
          {item.confidence_level && (
            <Badge variant="default">{formatQuoteType(item.confidence_level)}</Badge>
          )}
          {item.quote_type && (
            <Badge variant="info">{formatQuoteType(item.quote_type)}</Badge>
          )}
        </div>

        {/* Theme pills */}
        {item.themes.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {item.themes.slice(0, 5).map((theme, i) => (
              <span
                key={i}
                className="px-2 py-0.5 text-xs rounded-full bg-slate-100 text-slate-600 hover:bg-slate-200 cursor-default"
              >
                {formatTheme(theme)}
              </span>
            ))}
            {item.themes.length > 5 && (
              <span className="px-2 py-0.5 text-xs text-slate-400">+{item.themes.length - 5}</span>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

// =============================================================================
// SEC Nugget Card
// =============================================================================

function SecNuggetCard({ item }: { item: FinancialFeedItem }) {
  const [isExpanded, setIsExpanded] = useState(false)
  const isLong = item.text.length > 200
  const signal = item.signal_strength ? signalStrengthConfig[item.signal_strength] : null
  const risk = item.risk_level ? riskLevelConfig[item.risk_level] : null

  return (
    <div className="bg-white rounded-xl border border-slate-200 border-l-4 border-l-amber-500 shadow-sm hover:shadow-md transition-shadow">
      <div className="p-4 space-y-3">
        {/* Header: ticker + filing type + source badge */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-semibold rounded bg-amber-50 text-amber-700 border border-amber-200">
              <FileText size={11} />
              SEC
            </span>
            <span className="text-sm font-bold text-slate-800">{item.ticker}</span>
            {item.filing_type && (
              <span className="text-xs font-medium text-slate-500">{item.filing_type.toUpperCase()}</span>
            )}
            {item.date && (
              <span className="text-xs text-slate-400">{item.date}</span>
            )}
          </div>
          <div className="flex items-center gap-1.5">
            {item.is_new_disclosure && (
              <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 text-xs font-semibold rounded bg-emerald-500 text-white animate-pulse">
                <Sparkles size={10} /> NEW
              </span>
            )}
            {item.relevance_score > 0 && (
              <span className={cn(
                'text-xs px-1.5 py-0.5 rounded',
                item.relevance_score >= 0.7 ? 'bg-emerald-50 text-emerald-600' :
                item.relevance_score >= 0.4 ? 'bg-blue-50 text-blue-600' : 'bg-slate-50 text-slate-500'
              )}>
                {Math.round(item.relevance_score * 100)}%
              </span>
            )}
          </div>
        </div>

        {/* Nugget text */}
        <p className={cn(
          'text-sm text-slate-700',
          !isExpanded && isLong && 'line-clamp-3'
        )}>
          {item.text}
        </p>
        {isLong && (
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="text-xs text-amber-600 hover:text-amber-700 flex items-center gap-0.5"
          >
            {isExpanded ? <><ChevronUp size={12} /> Show less</> : <><ChevronDown size={12} /> Read more</>}
          </button>
        )}

        {/* Context */}
        {item.context && (
          <p className="text-xs text-slate-500 italic">{item.context}</p>
        )}

        {/* Badges row */}
        <div className="flex flex-wrap items-center gap-1.5">
          {item.nugget_type && (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded-full bg-amber-50 text-amber-700 border border-amber-200">
              <Target size={10} />
              {formatQuoteType(item.nugget_type)}
            </span>
          )}
          {item.section && (
            <Badge variant="default">{formatQuoteType(item.section)}</Badge>
          )}
          {signal && (
            <span className={cn('px-2 py-0.5 text-xs rounded-full font-medium', signal.style)}>
              {signal.label}
            </span>
          )}
          {risk && (
            <span className={cn('inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded-full border', risk.color)}>
              <Shield size={10} />
              {risk.label}
            </span>
          )}
          {item.is_actionable && (
            <Badge variant="success">Actionable</Badge>
          )}
        </div>

        {/* Theme pills */}
        {item.themes.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {item.themes.slice(0, 5).map((theme, i) => (
              <span
                key={i}
                className="px-2 py-0.5 text-xs rounded-full bg-slate-100 text-slate-600 hover:bg-slate-200 cursor-default"
              >
                {formatTheme(theme)}
              </span>
            ))}
            {item.themes.length > 5 && (
              <span className="px-2 py-0.5 text-xs text-slate-400">+{item.themes.length - 5}</span>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

// =============================================================================
// Main Card Component (discriminated)
// =============================================================================

interface FinancialFeedCardProps {
  item: FinancialFeedItem
}

export default function FinancialFeedCard({ item }: FinancialFeedCardProps) {
  if (item.source_type === 'earnings') {
    return <EarningsQuoteCard item={item} />
  }
  return <SecNuggetCard item={item} />
}
