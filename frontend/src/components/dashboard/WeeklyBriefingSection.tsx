'use client'

import React, { useState } from 'react'
import {
  ChevronDown,
  ChevronUp,
  Zap,
  Sparkles,
  RefreshCw,
  ExternalLink,
  Clock,
  Headphones,
  TrendingUp,
  Globe,
  Radio
} from 'lucide-react'
import { motion } from 'framer-motion'
import { cn } from '@/lib/utils'
import { Badge } from '@/components/ui'
import { API_BASE } from '@/lib/config'
import PodcastModal from './PodcastModal'
import MotionWrapper from '@/components/ui/motion-wrapper'
import TypewriterEffect from '@/components/ui/typewriter'
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
      <Badge className="bg-emerald-100 text-emerald-700 border-emerald-200 text-[10px] font-bold uppercase tracking-wider shadow-sm">
        <Sparkles size={10} className="mr-1 fill-emerald-500/20" />
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
      className={cn(sizeClasses, "rounded object-contain bg-white")}
      onError={() => setImageError(true)}
    />
  )
}

// =============================================================================
// Text Rendering Helper - Handles logos and citations
// =============================================================================

// Helper to extract domain from URL
const extractDomain = (url: string): string => {
  try {
    if (!url) return 'Unknown'
    const parsed = new URL(url)
    return parsed.hostname.replace('www.', '')
  } catch {
    return 'Unknown'
  }
}

// Parse citations like [1], [2], logos like [[Company Name]], and entity highlights like {{Entity}} or {Entity}
// Now accepts optional sourceArticles to make citations clickable with domain hover
const renderTextWithLogosAndCitations = (
  text: string,
  companiesWithLogos: CompanyWithLogo[],
  sourceArticles?: SourceArticle[]
) => {
  // Split by citations [N], [Exa:N], company tags [[Company]], entity tags {{Entity}}, and single brace {Entity}
  // Note: Single brace {Entity} is for materials/products from the LLM
  const parts = text.split(/(\[(?:Exa:)?\d+\]|\[\[.*?\]\]|\{\{.*?\}\}|\{[^{}]+\})/g)

  return parts.map((part, idx) => {
    // Handle citations [N] or [Exa:N]
    if (/^\[(?:Exa:)?\d+\]$/.test(part)) {
      const numStr = part.replace(/[\[\]Exa:]/g, '')
      const num = parseInt(numStr, 10)
      const article = sourceArticles?.find(a => a.article_number === num || a.article_number === `Exa:${num}`)
      const domain = article?.url ? extractDomain(article.url) : null

      // If we have a URL, make it clickable
      if (article?.url) {
        return (
          <a
            key={idx}
            href={article.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-emerald-600 font-semibold ml-0.5 cursor-pointer hover:underline decoration-emerald-300 underline-offset-2"
            title={domain || `Source ${num}`}
          >
            <sup>{numStr}</sup>
          </a>
        )
      }

      // Fallback to non-clickable
      return (
        <sup
          key={idx}
          className="text-emerald-600 font-semibold ml-0.5 cursor-help"
          title={`Source ${numStr}`}
        >
          {numStr}
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
            <span className="inline-block transform translate-y-0.5 shadow-sm rounded-sm">
              <CompanyLogo company={company} size="sm" />
            </span>
          )}
        </span>
      )
    }

    // Handle entity highlights {{Entity}} - bold text without logo (double braces)
    if (/^\{\{.*?\}\}$/.test(part)) {
      const entityName = part.replace(/[\{\}]/g, '')
      return (
        <span key={idx} className="font-bold text-slate-800 bg-slate-100/50 px-1 rounded">
          {entityName}
        </span>
      )
    }

    // Handle single braces {Entity} - bold text for materials/products from LLM
    if (/^\{[^{}]+\}$/.test(part)) {
      const entityName = part.slice(1, -1) // Remove single braces
      return (
        <span key={idx} className="font-semibold text-emerald-700">
          {entityName}
        </span>
      )
    }

    return part
  })
}

// =============================================================================
// Insight Item Component
// =============================================================================

interface InsightItemProps {
  insight: BriefingInsight
  companiesWithLogos: CompanyWithLogo[]
  sourceArticles?: SourceArticle[]
  isHeadline?: boolean
  isSneakPeek?: boolean
}

function InsightItem({ insight, companiesWithLogos, sourceArticles, isHeadline = false, isSneakPeek = false }: InsightItemProps) {

  return (
    <div className={cn(
      "flex items-start gap-3",
      isHeadline ? "mb-3" : "",
      isSneakPeek ? "opacity-60 scale-[0.98] origin-top" : ""
    )}>
      {!isHeadline && (
        <div className="mt-2 w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0 shadow-sm shadow-emerald-200" />
      )}
      <div className="flex-1">
        <div className={cn(
          "leading-relaxed",
          isHeadline
            ? "text-base font-semibold text-slate-900"
            : "text-sm text-slate-700",
          isSneakPeek ? "line-clamp-1 truncate" : ""
        )}>
          {renderTextWithLogosAndCitations(insight.text, companiesWithLogos, sourceArticles)}
        </div>
        <div className="mt-1.5 flex items-center gap-2">
          {!isSneakPeek && <StatusBadge status={insight.status} />}
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
  index: number
}

function SectionCard({ section, isFirst = false, index }: SectionCardProps) {
  const [isExpanded, setIsExpanded] = useState(isFirst) // Auto-expand first section

  // Safe accessors
  const companies = section.companies_with_logos || []
  const insights = section.insights || []
  const articles = section.source_articles || []

  // Animation variants for card slide-in
  const cardVariants = {
    hidden: { opacity: 0, y: 20 },
    show: {
      opacity: 1,
      y: 0,
      transition: {
        type: "spring" as const,
        stiffness: 100,
        damping: 15,
        delay: index * 0.05 // Stagger based on index
      }
    }
  }

  return (
    <motion.div
      variants={cardVariants}
      className={cn(
        "bg-white border rounded-xl overflow-hidden shadow-sm hover:shadow-lg hover:shadow-emerald-900/5 transition-all duration-300",
        isFirst ? "border-emerald-200 ring-1 ring-emerald-50 shadow-md" : "border-slate-200"
      )}
    >
      {/* Section Header */}
      <div className="p-5">
        <div className="flex items-center justify-between mb-4 bg-gradient-to-r from-emerald-50/80 to-teal-50/30 p-3 rounded-lg border border-emerald-100/50">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wide">
              {section.header}
            </h3>
          </div>

          {/* Company Logos */}
          {companies.length > 0 && (
            <div className="flex items-center gap-1">
              {companies.slice(0, 5).map((company, idx) => (
                <CompanyLogo key={idx} company={company} size="sm" />
              ))}
              {companies.length > 5 && (
                <span className="text-[10px] text-slate-400 ml-1 font-medium bg-slate-100 px-1.5 py-0.5 rounded-full">
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
            sourceArticles={articles}
            isHeadline={true}
          />
        )}

        {/* Sneak Peek (visible when collapsed) */}
        {!isExpanded && insights.length > 0 && (
          <div className="mt-2 relative">
            <InsightItem
              insight={insights[0]}
              companiesWithLogos={companies}
              sourceArticles={articles}
              isSneakPeek={true}
            />
            <div className="absolute inset-x-0 bottom-0 h-10 bg-gradient-to-t from-white via-white/80 to-transparent pointer-events-none" />
          </div>
        )}

        {/* Expand/Collapse Button */}
        {insights.length > 0 && (
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="group flex items-center gap-1.5 text-xs text-emerald-600 font-medium hover:text-emerald-700 transition-colors mt-2 relative z-10 px-2 py-1 -ml-2 rounded-md hover:bg-emerald-50"
          >
            {isExpanded ? (
              <>
                <ChevronUp size={14} className="group-hover:-translate-y-0.5 transition-transform" />
                Hide insights
              </>
            ) : (
              <>
                <ChevronDown size={14} className="group-hover:translate-y-0.5 transition-transform" />
                Show {insights.length} more insight{insights.length > 1 ? 's' : ''}
              </>
            )}
          </button>
        )}
      </div>

      {/* Expandable Insights Tray */}
      {isExpanded && insights.length > 0 && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          exit={{ opacity: 0, height: 0 }}
          className="border-t border-slate-100 bg-slate-50/50 p-5 space-y-4"
        >
          {insights.map((insight, idx) => (
            <InsightItem
              key={idx}
              insight={insight}
              companiesWithLogos={companies}
              sourceArticles={articles}
            />
          ))}
        </motion.div>
      )}

      {/* Sources Footer - Grouped by Domain */}
      {articles.length > 0 && (() => {
        // Group articles by domain
        const articlesByDomain = articles.reduce((acc, article) => {
          const domain = article.url ? extractDomain(article.url) : 'unknown'
          if (!acc[domain]) acc[domain] = []
          acc[domain].push(article)
          return acc
        }, {} as Record<string, SourceArticle[]>)

        return (
          <div className="border-t border-slate-100 px-5 py-3 bg-slate-50/80">
            <div className="flex items-center gap-2 text-[10px] text-slate-400 uppercase tracking-wider mb-2">
              <Globe size={10} />
              <span className="font-semibold">Intelligence Sources</span>
              <span>({articles.length})</span>
            </div>
            <div className="flex flex-wrap gap-x-4 gap-y-2">
              {Object.entries(articlesByDomain).slice(0, 6).map(([domain, domainArticles]) => (
                <a
                  key={domain}
                  href={domainArticles[0].url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 text-xs text-slate-500 hover:text-emerald-600 transition-colors bg-white px-2 py-1 rounded border border-slate-200 hover:border-emerald-200 hover:shadow-sm"
                  title={domainArticles.map(a => a.title).join(' | ')}
                >
                  <span className="font-medium">{domain}</span>
                  <span className="text-slate-400 text-[10px]">
                    [{domainArticles.map(a => a.article_number).join(', ')}]
                  </span>
                  <ExternalLink size={10} className="shrink-0 text-slate-400 opacity-50" />
                </a>
              ))}
              {Object.keys(articlesByDomain).length > 6 && (
                <span className="text-xs text-slate-400 self-center px-1">
                  +{Object.keys(articlesByDomain).length - 6} more
                </span>
              )}
            </div>
          </div>
        )
      })()}
    </motion.div>
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
  const [isPodcastModalOpen, setIsPodcastModalOpen] = useState(false)
  const [isOverallTrendExpanded, setIsOverallTrendExpanded] = useState(false)

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

  // Collect all companies with logos from all sections
  const allCompaniesWithLogos = briefing.sections.flatMap(
    section => section.companies_with_logos || []
  )

  // Format date range
  const periodStart = new Date(briefing.period_start).toLocaleDateString('en-US', {
    month: 'short', day: 'numeric'
  })
  const periodEnd = new Date(briefing.period_end).toLocaleDateString('en-US', {
    month: 'short', day: 'numeric'
  })

  return (
    <MotionWrapper className="space-y-6">
      {/* The Brief Header */}
      <div className="flex items-center justify-between">
        <motion.div
          className="flex items-center gap-4"
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.5 }}
        >
          <div className="p-3 bg-gradient-to-br from-emerald-100 to-teal-50 rounded-xl shadow-lg shadow-emerald-900/5 border border-emerald-200/60 relative overflow-hidden group">
            <div className="absolute inset-0 bg-white/40 opacity-0 group-hover:opacity-100 transition-opacity" />
            <Zap size={24} className="text-emerald-600 relative z-10" fill="currentColor" />
          </div>
          <div>
            <h2 className="text-2xl font-extrabold text-slate-900 tracking-tight leading-none bg-clip-text text-transparent bg-gradient-to-r from-slate-900 to-slate-700">
              The Brief
            </h2>
            <div className="flex items-center gap-2 mt-1">
              <div className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
              <p className="text-xs text-emerald-600 font-bold uppercase tracking-widest">
                Strategic Priorities
              </p>
            </div>
          </div>

          {/* Listen to Podcast Button */}
          {briefing.podcast_url && (
            <motion.button
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ delay: 0.3 }}
              onClick={() => setIsPodcastModalOpen(true)}
              className="ml-2 flex items-center gap-2 px-3 py-1.5 bg-gradient-to-r from-emerald-100 to-teal-50 hover:from-emerald-200 hover:to-teal-100 text-emerald-800 rounded-full transition-all border border-emerald-200/60 shadow-sm hover:shadow-md group"
              title="Listen to podcast"
            >
              <div className="p-1 bg-white rounded-full">
                <Headphones size={12} className="text-emerald-600 group-hover:scale-110 transition-transform" />
              </div>
              <span className="text-xs font-bold mr-1">Listen to Briefing</span>
            </motion.button>
          )}
        </motion.div>

        <motion.div
          className="flex items-center gap-4"
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.5, delay: 0.1 }}
        >
          <div className="flex items-center gap-2 text-xs text-slate-400 bg-slate-50 px-3 py-1.5 rounded-full border border-slate-100">
            <Clock size={14} />
            <span className="font-medium font-mono">{periodStart} - {periodEnd}</span>
          </div>
          {onHistoryClick && (
            <button
              onClick={onHistoryClick}
              className="text-xs text-emerald-600 hover:text-emerald-700 font-bold transition-colors uppercase tracking-wider flex items-center gap-1 hover:gap-1.5"
            >
              View History <ChevronDown className="-rotate-90" size={12} />
            </button>
          )}
        </motion.div>
      </div>

      {/* Briefing Title + Summary */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="relative overflow-hidden bg-gradient-to-br from-emerald-50 via-white to-teal-50/30 border border-emerald-100 rounded-2xl p-6 shadow-sm group"
      >
        {/* Background decorative elements */}
        <div className="absolute top-0 right-0 w-64 h-64 bg-emerald-100/20 rounded-full blur-3xl -mr-32 -mt-32 pointer-events-none" />

        <div className="relative z-10">
          <h3 className="text-lg font-bold text-slate-900 mb-4">{briefing.briefing_title}</h3>

          {briefing.bluf && (
            <div className="mb-4 p-4 bg-white/80 rounded-xl border border-emerald-100/60 shadow-sm relative">
              <div className="absolute top-3 right-3 text-emerald-200">
                <Sparkles size={16} />
              </div>
              <motion.p
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.8, delay: 0.4 }}
                className="text-sm font-medium text-slate-800 leading-relaxed font-serif"
              >
                {renderTextWithLogosAndCitations(briefing.bluf, allCompaniesWithLogos)}
              </motion.p>
            </div>
          )}

          {/* Overall Trend Section */}
          {briefing.overall_trend && (
            <div className="mt-2 pl-1 border-l-2 border-emerald-100">
              <div className="pl-3">
                <div className="flex items-center gap-2 mb-1.5">
                  <TrendingUp size={12} className="text-emerald-500" />
                  <span className="text-xs font-bold uppercase tracking-widest text-emerald-600/70">Market Trajectory</span>
                </div>

                {/* Collapsible Overall Trend */}
                {!isOverallTrendExpanded && (
                  <div className="relative">
                    <p className="text-sm text-slate-600 line-clamp-2 leading-relaxed">
                      {renderTextWithLogosAndCitations(briefing.overall_trend, allCompaniesWithLogos)}
                    </p>
                    <div className="absolute inset-x-0 bottom-0 h-8 bg-gradient-to-t from-white/90 to-transparent pointer-events-none" />
                  </div>
                )}

                {isOverallTrendExpanded && (
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ duration: 0.5 }}
                  >
                    <p className="text-sm text-slate-600 leading-relaxed">
                      {renderTextWithLogosAndCitations(briefing.overall_trend, allCompaniesWithLogos)}
                    </p>
                  </motion.div>
                )}

                <button
                  onClick={() => setIsOverallTrendExpanded(!isOverallTrendExpanded)}
                  className="flex items-center gap-1 text-xs text-emerald-600 font-medium hover:text-emerald-700 transition-colors mt-2"
                >
                  {isOverallTrendExpanded ? (
                    <><ChevronUp size={14} /> Show less</>
                  ) : (
                    <><ChevronDown size={14} /> Read full trajectory</>
                  )}
                </button>
              </div>
            </div>
          )}

          <div className="mt-6 flex items-center gap-4 text-xs font-medium text-slate-400 border-t border-emerald-100/50 pt-4">
            <div className="flex items-center gap-1.5">
              <div className="w-1.5 h-1.5 bg-emerald-300 rounded-full" />
              <span>{briefing.article_count} articles analyzed</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="w-1.5 h-1.5 bg-teal-300 rounded-full" />
              <span>{briefing.sections.length} key priority areas</span>
            </div>
          </div>
        </div>
      </motion.div>

      {/* Podcast Modal */}
      {briefing.podcast_url && (
        <PodcastModal
          isOpen={isPodcastModalOpen}
          onClose={() => setIsPodcastModalOpen(false)}
          audioUrl={`${API_BASE}/api/podcast/briefing/${briefing.id}`}
          duration={briefing.podcast_duration_seconds}
          title={briefing.briefing_title}
        />
      )}

      {/* Industry Headlines Section */}
      <div className="mt-10">
        <motion.div
          className="flex items-center gap-3 mb-6"
          initial={{ opacity: 0, x: -10 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.3 }}
        >
          <div className="h-8 w-1 bg-emerald-500 rounded-full" />
          <h2 className="text-xl font-bold text-slate-800 tracking-tight">
            Industry Headlines
          </h2>
        </motion.div>

        <motion.div
          className="space-y-5"
          initial="hidden"
          animate="show"
          variants={{
            hidden: { opacity: 0 },
            show: {
              opacity: 1,
              transition: {
                staggerChildren: 0.1,
                delayChildren: 0.3
              }
            }
          }}
        >
          {(briefing.sections || []).map((section, idx) => (
            <SectionCard key={idx} section={section} isFirst={idx === 0} index={idx} />
          ))}
        </motion.div>
      </div>

      {/* Key Topics Footer */}
      {briefing.key_topics_this_week.length > 0 && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 1 }}
          className="flex flex-col gap-4 pt-6 border-t border-slate-100"
        >
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs text-slate-400 font-bold uppercase tracking-wider flex items-center gap-1">
              <Radio size={12} />
              Detected Signals:
            </span>
            {briefing.key_topics_this_week.map((topic, idx) => (
              <Badge
                key={idx}
                className="text-[10px] uppercase font-bold text-slate-500 bg-slate-50 border-slate-100 hover:bg-emerald-50 hover:text-emerald-600 transition-colors cursor-default"
              >
                #{topic}
              </Badge>
            ))}
          </div>

          {/* AI Attribution Footer */}
          <div className="flex items-center justify-between text-[10px] text-slate-300 font-medium border-t border-slate-50 pt-2">
            <span>Analysis generated by Claude 3.5 Sonnet</span>
            <span>Synthesized from {briefing.article_count} sources</span>
          </div>
        </motion.div>
      )}
    </MotionWrapper>
  )
}
