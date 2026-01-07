'use client'

import { useState, useEffect } from 'react'
import { 
  Scale, 
  TrendingUp, 
  Building2, 
  FileText, 
  Globe, 
  BarChart3,
  Clock,
  ChevronDown,
  ChevronRight,
  BookOpen,
  ArrowRight,
  Archive,
  ExternalLink,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { api } from '@/lib/api'
import type { ResearchTemplate, RecentSearch } from '@/types'

interface SavedReport {
  id: string
  query: string
  created_at: string
  title?: string
  overall_confidence?: string
  category?: string
}

// Research templates
const RESEARCH_TEMPLATES: ResearchTemplate[] = [
  {
    id: 'supplier-comparison',
    title: 'Supplier Comparison',
    description: 'Compare suppliers',
    icon: 'Scale',
    prompt: 'Compare [Supplier A] vs [Supplier B] for [material/product]. Include pricing trends, lead times, quality certifications, and capacity.',
    color: 'bg-blue-500',
  },
  {
    id: 'market-analysis',
    title: 'Market Analysis',
    description: 'Market trends',
    icon: 'TrendingUp',
    prompt: 'Analyze the market outlook for [material/industry] over the next 2-3 years. Include demand drivers, supply constraints, and price projections.',
    color: 'bg-emerald-500',
  },
  {
    id: 'company-profile',
    title: 'Company Deep Dive',
    description: 'Company analysis',
    icon: 'Building2',
    prompt: 'Provide a comprehensive profile of [company name]. Include financials, product portfolio, recent news, strategic initiatives, and competitive positioning.',
    color: 'bg-violet-500',
  },
  {
    id: 'regulatory-impact',
    title: 'Regulatory Impact',
    description: 'Compliance analysis',
    icon: 'FileText',
    prompt: 'Analyze the impact of [regulation/policy] on the composites industry. Include compliance requirements, timeline, and affected segments.',
    color: 'bg-emerald-500',
  },
  {
    id: 'competitive-landscape',
    title: 'Competitive Landscape',
    description: 'Market mapping',
    icon: 'Globe',
    prompt: 'Map the competitive landscape for [product category/market segment]. Include market share estimates, key differentiators, and emerging players.',
    color: 'bg-rose-500',
  },
  {
    id: 'supply-chain-risk',
    title: 'Supply Chain Risk',
    description: 'Risk assessment',
    icon: 'BarChart3',
    prompt: 'Assess supply chain risks for [material/component]. Include geographic concentration, alternative suppliers, and mitigation strategies.',
    color: 'bg-cyan-500',
  },
]

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const iconMap: Record<string, React.ElementType> = {
  Scale,
  TrendingUp,
  Building2,
  FileText,
  Globe,
  BarChart3,
}

interface ResearchSidebarProps {
  recentSearches: RecentSearch[]
  onTemplateSelect: (prompt: string) => void
  onRecentSearchClick: (search: RecentSearch) => void
  isCollapsed?: boolean
  onToggleCollapse?: () => void
  onOpenSavedReport?: (reportId: string) => void
  onViewAllSavedReports?: () => void
}

export default function ResearchSidebar({
  recentSearches,
  onTemplateSelect,
  onRecentSearchClick,
  isCollapsed = false,
  onToggleCollapse,
  onOpenSavedReport,
  onViewAllSavedReports,
}: ResearchSidebarProps) {
  const [templatesExpanded, setTemplatesExpanded] = useState(true)
  const [recentExpanded, setRecentExpanded] = useState(true)
  const [savedReportsExpanded, setSavedReportsExpanded] = useState(false)
  const [savedReports, setSavedReports] = useState<SavedReport[]>([])
  const [savedReportsLoading, setSavedReportsLoading] = useState(false)

  // Fetch saved reports when section is expanded
  useEffect(() => {
    if (savedReportsExpanded && savedReports.length === 0) {
      setSavedReportsLoading(true)
      api.getSavedReports({ limit: 5 })
        .then(data => {
          setSavedReports(data.reports || [])
        })
        .catch(err => {
          console.error('Failed to fetch saved reports:', err)
        })
        .finally(() => {
          setSavedReportsLoading(false)
        })
    }
  }, [savedReportsExpanded, savedReports.length])

  if (isCollapsed) {
    return (
      <div className="w-12 bg-white border-r border-slate-200 flex flex-col items-center py-4 gap-2">
        <button
          onClick={onToggleCollapse}
          className="p-2 rounded-lg hover:bg-slate-100 text-slate-500 hover:text-slate-700"
          title="Expand sidebar"
        >
          <ChevronRight size={16} />
        </button>
        <div className="w-8 h-px bg-slate-200 my-2" />
        <button
          className="p-2 rounded-lg hover:bg-slate-100 text-slate-500"
          title="Templates"
        >
          <BookOpen size={16} />
        </button>
        <button
          className="p-2 rounded-lg hover:bg-slate-100 text-slate-500"
          title="Recent"
        >
          <Clock size={16} />
        </button>
        <button
          className="p-2 rounded-lg hover:bg-slate-100 text-slate-500"
          title="Saved Reports"
          onClick={onViewAllSavedReports}
        >
          <Archive size={16} />
        </button>
      </div>
    )
  }

  return (
    <div className="w-56 bg-white border-r border-slate-200 flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="shrink-0 px-3 py-3 border-b border-slate-100 flex items-center justify-between">
        <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
          Research Tools
        </span>
        {onToggleCollapse && (
          <button
            onClick={onToggleCollapse}
            className="p-1 rounded hover:bg-slate-100 text-slate-400 hover:text-slate-600"
          >
            <ChevronDown size={14} className="rotate-90" />
          </button>
        )}
      </div>

      <div className="flex-1 overflow-y-auto">
        {/* Templates Section */}
        <div className="p-2">
          <button
            onClick={() => setTemplatesExpanded(!templatesExpanded)}
            className="w-full flex items-center gap-2 px-2 py-1.5 rounded hover:bg-slate-50 transition-colors"
          >
            {templatesExpanded ? (
              <ChevronDown size={14} className="text-slate-400" />
            ) : (
              <ChevronRight size={14} className="text-slate-400" />
            )}
            <BookOpen size={14} className="text-slate-500" />
            <span className="text-sm font-medium text-slate-700">Templates</span>
          </button>
          
          {templatesExpanded && (
            <div className="mt-1 space-y-0.5">
              {RESEARCH_TEMPLATES.map((template) => {
                const IconComponent = iconMap[template.icon]
                return (
                  <button
                    key={template.id}
                    onClick={() => onTemplateSelect(template.prompt)}
                    className="w-full flex items-center gap-2 px-2 py-2 rounded-lg hover:bg-emerald-50 transition-colors text-left group"
                  >
                    <div className={cn(
                      "w-6 h-6 rounded flex items-center justify-center shrink-0",
                      template.color
                    )}>
                      {IconComponent && <IconComponent size={12} className="text-white" />}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-slate-700 group-hover:text-emerald-700 truncate">
                        {template.title}
                      </p>
                    </div>
                  </button>
                )
              })}
            </div>
          )}
        </div>

        {/* Divider */}
        <div className="mx-3 h-px bg-slate-100" />

        {/* Recent Searches Section */}
        <div className="p-2">
          <button
            onClick={() => setRecentExpanded(!recentExpanded)}
            className="w-full flex items-center gap-2 px-2 py-1.5 rounded hover:bg-slate-50 transition-colors"
          >
            {recentExpanded ? (
              <ChevronDown size={14} className="text-slate-400" />
            ) : (
              <ChevronRight size={14} className="text-slate-400" />
            )}
            <Clock size={14} className="text-slate-500" />
            <span className="text-sm font-medium text-slate-700">Recent</span>
            {recentSearches.length > 0 && (
              <span className="ml-auto text-xs text-slate-400 bg-slate-100 px-1.5 py-0.5 rounded">
                {recentSearches.length}
              </span>
            )}
          </button>
          
          {recentExpanded && (
            <div className="mt-1 space-y-0.5">
              {recentSearches.length === 0 ? (
                <p className="px-2 py-3 text-xs text-slate-400 text-center">
                  No recent searches yet
                </p>
              ) : (
                recentSearches.slice(0, 10).map((search) => (
                  <button
                    key={search.id}
                    onClick={() => onRecentSearchClick(search)}
                    className="w-full flex items-start gap-2 px-2 py-2 rounded-lg hover:bg-slate-50 transition-colors text-left group"
                  >
                    <div className="w-5 h-5 rounded bg-slate-100 flex items-center justify-center shrink-0 mt-0.5">
                      <Clock size={10} className="text-slate-400" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-slate-700 group-hover:text-emerald-700 truncate">
                        {search.title}
                      </p>
                      <p className="text-xs text-slate-400 truncate">
                        {search.timestamp}
                      </p>
                    </div>
                  </button>
                ))
              )}
            </div>
          )}
        </div>

        {/* Divider */}
        <div className="mx-3 h-px bg-slate-100" />

        {/* Saved Reports Section */}
        <div className="p-2">
          <button
            onClick={() => setSavedReportsExpanded(!savedReportsExpanded)}
            className="w-full flex items-center gap-2 px-2 py-1.5 rounded hover:bg-slate-50 transition-colors"
          >
            {savedReportsExpanded ? (
              <ChevronDown size={14} className="text-slate-400" />
            ) : (
              <ChevronRight size={14} className="text-slate-400" />
            )}
            <Archive size={14} className="text-slate-500" />
            <span className="text-sm font-medium text-slate-700">Saved Reports</span>
          </button>
          
          {savedReportsExpanded && (
            <div className="mt-1 space-y-0.5">
              {savedReportsLoading ? (
                <p className="px-2 py-3 text-xs text-slate-400 text-center">
                  Loading...
                </p>
              ) : savedReports.length === 0 ? (
                <p className="px-2 py-3 text-xs text-slate-400 text-center">
                  No saved reports yet
                </p>
              ) : (
                <>
                  {savedReports.map((report) => (
                    <button
                      key={report.id}
                      onClick={() => onOpenSavedReport?.(report.id)}
                      className="w-full flex items-start gap-2 px-2 py-2 rounded-lg hover:bg-emerald-50 transition-colors text-left group"
                    >
                      <div className="w-5 h-5 rounded bg-emerald-100 flex items-center justify-center shrink-0 mt-0.5">
                        <FileText size={10} className="text-emerald-600" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm text-slate-700 group-hover:text-emerald-700 truncate">
                          {report.query}
                        </p>
                        <p className="text-xs text-slate-400 truncate">
                          {new Date(report.created_at).toLocaleDateString()}
                        </p>
                      </div>
                    </button>
                  ))}
                  {onViewAllSavedReports && (
                    <button
                      onClick={onViewAllSavedReports}
                      className="w-full flex items-center justify-center gap-1.5 px-2 py-2 rounded-lg hover:bg-slate-50 transition-colors text-xs text-emerald-600 hover:text-emerald-700"
                    >
                      <span>View All Reports</span>
                      <ExternalLink size={12} />
                    </button>
                  )}
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
