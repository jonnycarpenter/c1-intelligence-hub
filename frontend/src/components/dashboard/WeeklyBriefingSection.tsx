'use client'

import React, { useState } from 'react'
import {
  ChevronDown,
  ChevronUp,
  Zap,
  Sparkles,
  RefreshCw,
  ExternalLink,
  Clock
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { Badge } from '@/components/ui'
import { API_BASE } from '@/lib/config'
import PodcastPlayer from './PodcastPlayer'
import type {
  WeeklyBriefing,
  BriefingSection,
  BriefingInsight,
  CompanyWithLogo,
  SourceArticle
} from '@/types/briefing'

// =============================================================================
// Status Badge Component
// =============================================================================

interface StatusBadgeProps {
  status: 'net_new' | 'continuing'
}

function StatusBadge({ status }: StatusBadgeProps) {
  if (status === 'net_new') {
    return (
      <Badge className="bg-emerald-100 text-emerald-700 border-emerald-200 text-[10px] font-bold uppercase tracking-wider">
        <Sparkles size={10} className="mr-1" />
        Net New
      </Badge>
    )
  }
  return (
    <Badge className="bg-slate-100 text-slate-600 border-slate-200 text-[10px] font-medium uppercase tracking-wider">
      <RefreshCw size={10} className="mr-1" />
      Continuing
    </Badge>
  )
}

// =============================================================================
// Company Logo Component
// =============================================================================

interface CompanyLogoProps {
  company: CompanyWithLogo
  size?: 'sm' | 'md'
}

function CompanyLogo({ company, size = 'sm' }: CompanyLogoProps) {
  const [imageError, setImageError] = useState(false)
  const sizeClasses = size === 'sm' ? 'w-5 h-5' : 'w-6 h-6'

  // Use logo.dev API via our backend proxy
  // In development, API_BASE is http://localhost:8000
  // In production (same origin), it's empty so relative URL works
  const logoUrl = company.domain
    ? `${API_BASE}/api/pipeline/logo/${company.domain}`
    : null

  if (!logoUrl || imageError) {
    // Fallback to initials
    const initials = company.name
      .split(' ')
      .map(w => w[0])
      .slice(0, 2)
      .join('')
      .toUpperCase()

    return (
      <div
        className={cn(
          sizeClasses,
          "rounded bg-slate-200 flex items-center justify-center text-[8px] font-bold text-slate-500"
        )}
        title={company.name}
      >
        {initials}
      </div>
    )
  }

  return (
    <img
      src={logoUrl}
      alt={company.name}
      title={company.name}
      className={cn(sizeClasses, "rounded object-contain")}
      onError={() => setImageError(true)}
    />
  )
}

// =============================================================================
// Insight Item Component
// =============================================================================

interface InsightItemProps {
  insight: BriefingInsight
  companiesWithLogos: CompanyWithLogo[]
  isHeadline?: boolean
  isSneakPeak?: boolean
}

function InsightItem({ insight, companiesWithLogos, isHeadline = false, isSneakPeak = false }: InsightItemProps) {
  // Parse citations like [1], [2] and logos like [[Company Name]]
  const renderTextWithLogosAndCitations = (text: string, companiesWithLogos: CompanyWithLogo[]) => {
    // Split by citations [N] and company tags [[Company]]
    const parts = text.split(/(\[\d+\]|\[\[.*?\]\])/g)

    return parts.map((part, idx) => {
      // Handle citations [N]
      if (/^\[\d+\]$/.test(part)) {
        const num = part.replace(/[\[\]]/g, '')
        return (
          <sup
            key={idx}
            className="text-amber-600 font-semibold ml-0.5 cursor-help"
            title={`Source ${num}`}
          >
            {num}
          </sup>
        )
      }

      // Handle company logos [[Company]]
      if (/^\[\[.*?\]\]$/.test(part)) {
        const companyName = part.replace(/[\[\]]/g, '')
        const company = companiesWithLogos.find(c => c.name === companyName)

        return (
          <span key={idx} className="inline-flex items-center gap-1.5 align-baseline">
            <span className="font-bold text-slate-900 mx-0.5">{companyName}</span>
            {company && (
              <span className="inline-block transform translate-y-0.5">
                <CompanyLogo company={company} size="sm" />
              </span>
            )}
          </span>
        )
      }

      return part
    })
  }

  return (
    <div className={cn(
      "flex items-start gap-3",
      isHeadline ? "mb-3" : "",
      isSneakPeak ? "opacity-60 scale-[0.98] origin-top" : ""
    )}>
      {!isHeadline && (
        <div className="mt-2 w-1.5 h-1.5 rounded-full bg-amber-500 shrink-0" />
      )}
      <div className="flex-1">
        <div className={cn(
          "leading-relaxed",
          isHeadline
            ? "text-base font-semibold text-slate-900"
            : "text-sm text-slate-700",
          isSneakPeak ? "line-clamp-1 truncate" : ""
        )}>
          {renderTextWithLogosAndCitations(insight.text, companiesWithLogos)}
        </div>
        <div className="mt-1.5 flex items-center gap-2">
          {!isSneakPeak && <StatusBadge status={insight.status} />}
        </div>
      </div>
    </div>
  )
}

// =============================================================================
// Section Card Component
// =============================================================================

interface SectionCardProps {
  section: BriefingSection
  isFirst?: boolean
}

function SectionCard({ section, isFirst = false }: SectionCardProps) {
  const [isExpanded, setIsExpanded] = useState(isFirst) // Auto-expand first section

  // Safe accessors
  const companies = section.companies_with_logos || []
  const insights = section.insights || []
  const articles = section.source_articles || []

  return (
    <div className={cn(
      "bg-white border rounded-xl overflow-hidden shadow-sm hover:shadow-md transition-all duration-200",
      isFirst ? "border-amber-200 ring-1 ring-amber-50" : "border-slate-200"
    )}>
      {/* Section Header */}
      <div className="p-5">
        <div className="flex items-center justify-between mb-4 bg-amber-400/10 p-3 rounded-lg border border-amber-400/5">
          <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wide">
            {section.header}
          </h3>

          {/* Company Logos */}
          {companies.length > 0 && (
            <div className="flex items-center gap-1">
              {companies.slice(0, 5).map((company, idx) => (
                <CompanyLogo key={idx} company={company} size="sm" />
              ))}
              {companies.length > 5 && (
                <span className="text-[10px] text-slate-400 ml-1">
                  +{companies.length - 5}
                </span>
              )}
            </div>
          )}
        </div>

        {/* Headline (always visible) */}
        {section.headline && (
          <InsightItem
            insight={section.headline}
            companiesWithLogos={companies}
            isHeadline={true}
          />
        )}

        {/* Sneak Peak (visible when collapsed) */}
        {!isExpanded && insights.length > 0 && (
          <div className="mt-2 relative">
            <InsightItem
              insight={insights[0]}
              companiesWithLogos={companies}
              isSneakPeak={true}
            />
            <div className="absolute inset-x-0 bottom-0 h-8 bg-gradient-to-t from-white to-transparent pointer-events-none" />
          </div>
        )}

        {/* Expand/Collapse Button */}
        {insights.length > 0 && (
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="flex items-center gap-1 text-xs text-amber-600 font-medium hover:text-amber-700 transition-colors mt-1 relative z-10"
          >
            {isExpanded ? (
              <>
                <ChevronUp size={14} />
                Hide insights
              </>
            ) : (
              <>
                <ChevronDown size={14} />
                Show {insights.length} more insight{insights.length > 1 ? 's' : ''}
              </>
            )}
          </button>
        )}
      </div>

      {/* Expandable Insights Tray */}
      {isExpanded && insights.length > 0 && (
        <div className="border-t border-slate-100 bg-slate-50/50 p-5 space-y-3">
          {insights.map((insight, idx) => (
            <InsightItem
              key={idx}
              insight={insight}
              companiesWithLogos={companies}
            />
          ))}
        </div>
      )}

      {/* Sources Footer */}
      {articles.length > 0 && (
        <div className="border-t border-slate-100 px-5 py-3 bg-slate-50">
          <div className="flex items-center gap-2 text-[10px] text-slate-400 uppercase tracking-wider mb-2">
            <span className="font-semibold">Sources</span>
            <span>({articles.length})</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {articles.slice(0, 5).map((article, idx) => (
              <a
                key={idx}
                href={article.url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-xs text-slate-600 hover:text-amber-600 transition-colors"
                title={article.title}
              >
                <span className="font-medium">[{idx + 1}]</span>
                <span className="truncate max-w-[150px]">{article.source_name}</span>
                <ExternalLink size={10} className="shrink-0" />
              </a>
            ))}
            {articles.length > 5 && (
              <span className="text-xs text-slate-400">
                +{articles.length - 5} more
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

// =============================================================================
// Main Weekly Briefing Section Component
// =============================================================================

interface WeeklyBriefingSectionProps {
  briefing: WeeklyBriefing | null
  isLoading?: boolean
  onHistoryClick?: () => void
}

export default function WeeklyBriefingSection({
  briefing,
  isLoading,
  onHistoryClick
}: WeeklyBriefingSectionProps) {
  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div className="h-8 w-48 bg-slate-100 rounded animate-pulse" />
          <div className="h-4 w-32 bg-slate-100 rounded animate-pulse" />
        </div>
        {[1, 2, 3].map(i => (
          <div key={i} className="h-64 bg-slate-50 border border-slate-200 rounded-xl animate-pulse" />
        ))}
      </div>
    )
  }

  if (!briefing) {
    return (
      <div className="text-center py-20 bg-slate-50 rounded-xl border border-dashed border-slate-300">
        <div className="text-4xl mb-4">📫</div>
        <h3 className="text-lg font-semibold text-slate-900">No Weekly Briefing Yet</h3>
        <p className="text-sm text-slate-500 mt-1">
          The weekly executive briefing will be generated every Monday at 8:30 AM CST
        </p>
      </div>
    )
  }

  // Format date range
  const periodStart = new Date(briefing.period_start).toLocaleDateString('en-US', {
    month: 'short', day: 'numeric'
  })
  const periodEnd = new Date(briefing.period_end).toLocaleDateString('en-US', {
    month: 'short', day: 'numeric'
  })

  return (
    <div className="space-y-6">
      {/* Need to Know Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="p-3 bg-gradient-to-br from-amber-100 to-amber-50 rounded-xl shadow-sm border border-amber-200/60">
            <Zap size={24} className="text-amber-600" fill="currentColor" />
          </div>
          <div>
            <h2 className="text-2xl font-extrabold text-slate-900 tracking-tight leading-none">Need to Know</h2>
            <p className="text-xs text-amber-600/80 font-bold uppercase tracking-widest mt-1">Executive Briefing</p>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <Clock size={14} />
            <span>{periodStart} - {periodEnd}</span>
          </div>
          {onHistoryClick && (
            <button
              onClick={onHistoryClick}
              className="text-xs text-amber-600 hover:text-amber-700 font-medium transition-colors"
            >
              View History →
            </button>
          )}
        </div>
      </div>

      {/* Briefing Title + BLUF */}
      <div className="bg-gradient-to-r from-amber-50 to-orange-50 border border-amber-100 rounded-xl p-4">
        <h3 className="text-lg font-bold text-slate-900">{briefing.briefing_title}</h3>
        {briefing.bluf && (
          <div className="mt-3 p-3 bg-white/60 rounded-lg border border-amber-200/50">
            <div className="flex items-start gap-2">
              <span className="text-xs font-bold text-amber-700 uppercase tracking-wider shrink-0 mt-0.5">BLUF</span>
              <p className="text-sm font-medium text-slate-800 leading-relaxed">{briefing.bluf}</p>
            </div>
          </div>
        )}
        {briefing.overall_trend && (
          <p className="text-sm text-slate-600 mt-3">{briefing.overall_trend}</p>
        )}
        <div className="mt-3 flex items-center gap-4 text-xs text-slate-500">
          <span>{briefing.article_count} articles analyzed</span>
          <span>•</span>
          <span>{briefing.sections.length} key areas</span>
        </div>
      </div>

      {/* Podcast Player */}
      {briefing.podcast_url && (
        <PodcastPlayer
          audioUrl={briefing.podcast_url}
          duration={briefing.podcast_duration_seconds}
          title={briefing.briefing_title}
        />
      )}

      {/* Sections */}
      <div className="space-y-4">
        {(briefing.sections || []).map((section, idx) => (
          <SectionCard key={idx} section={section} isFirst={idx === 0} />
        ))}
      </div>

      {/* Key Topics Footer */}
      {briefing.key_topics_this_week.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 pt-4 border-t border-slate-100">
          <span className="text-xs text-slate-400 font-medium uppercase tracking-wider">
            Key Topics:
          </span>
          {briefing.key_topics_this_week.map((topic, idx) => (
            <Badge
              key={idx}
              className="text-xs text-slate-600 bg-white border-slate-200"
            >
              {topic}
            </Badge>
          ))}
        </div>
      )}
    </div>
  )
}
