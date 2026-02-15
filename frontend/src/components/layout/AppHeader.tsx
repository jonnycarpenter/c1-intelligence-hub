'use client'

import { useState, useEffect } from 'react'
import { Activity, Search, Package, Building2, Factory, Database, User, Mic, GitBranch, Ship, LogOut, Compass, Cpu, PlayCircle, BarChart3 } from 'lucide-react'
import { cn } from '@/lib/utils'
import TypewriterEffect from '@/components/ui/typewriter'
import type { Mode } from '@/types'

// Team color mapping
const teamColors: Record<string, string> = {
  'Sales East': 'bg-blue-500',
  'Sales West': 'bg-emerald-500',
  'Marketing': 'bg-purple-500',
  'Product/Supplier': 'bg-emerald-500',
  'All Others': 'bg-slate-500',
}

const modeConfig: Record<Mode, { icon: typeof Activity; title: string; subtitle: string; description: string; color: string; bg: string }> = {
  pulse: {
    icon: Activity,
    title: 'The Brief',
    subtitle: 'Strategic Priorities',
    description: 'Your weekly executive briefing. AI-synthesized from hundreds of articles into the key themes that matter. Hit play on the podcast for an audio walkthrough.',
    color: 'text-emerald-500',
    bg: 'bg-emerald-100',
  },
  discovery: {
    icon: Compass,
    title: 'Discovery',
    subtitle: 'All Datasets',
    description: 'Ask the AI assistant anything about your market. It searches across all ingested articles, earnings transcripts, and SEC filings to surface what you need.',
    color: 'text-teal-500',
    bg: 'bg-teal-100',
  },
  research: {
    icon: Search,
    title: 'Deep Research',
    subtitle: 'Comprehensive analysis & insights',
    description: 'Launch a deep research workflow on any topic. Multiple AI agents run in parallel across financial data, industry trends, and web sources to build a comprehensive report.',
    color: 'text-emerald-500',
    bg: 'bg-emerald-100',
  },
  products: {
    icon: Package,
    title: 'Product Intelligence',
    subtitle: 'SKU analysis & comparisons',
    description: 'Explore product-level intelligence across your tracked SKUs and competitive landscape.',
    color: 'text-blue-500',
    bg: 'bg-blue-100',
  },
  'field-sales': {
    icon: Mic,
    title: 'Field Intel',
    subtitle: 'Voice memos & field observations',
    description: 'Capture and review field observations from your sales team.',
    color: 'text-rose-500',
    bg: 'bg-rose-100',
  },
  pipeline: {
    icon: GitBranch,
    title: 'Company Lookup',
    subtitle: 'Companies, Prospects, and Decision Makers',
    description: 'Search for any company to get an instant intelligence profile. Find similar companies, identify decision makers, and discover sales opportunities.',
    color: 'text-slate-500',
    bg: 'bg-slate-100',
  },
  'supply-network': {
    icon: Ship,
    title: 'Supply Network',
    subtitle: 'Supply chain graph & relationships',
    description: 'Visualize supplier and customer relationships across the composites industry. Drill into any company to see shipment data, intelligence, and network connections.',
    color: 'text-indigo-500',
    bg: 'bg-indigo-100',
  },
  companies: {
    icon: Building2,
    title: 'Company Intelligence',
    subtitle: 'Competitor & supplier tracking',
    description: 'Track competitors and suppliers with automated intelligence gathering.',
    color: 'text-emerald-500',
    bg: 'bg-emerald-100',
  },
  industries: {
    icon: Factory,
    title: 'Core Industries',
    subtitle: '90-day narrative timelines by end-market',
    description: 'Select an end-market to see its 90-day narrative arc. AI generates a storyline from article volume, sentiment shifts, and key events across each month.',
    color: 'text-emerald-500',
    bg: 'bg-emerald-100',
  },
  'data-preferences': {
    icon: Database,
    title: 'Tracked Entities',
    subtitle: 'Manage tracked companies & data',
    description: 'View and manage the companies, industries, and topics the platform is tracking. This is the data layer that feeds everything else.',
    color: 'text-cyan-500',
    bg: 'bg-cyan-100',
  },
  'app-architecture': {
    icon: Cpu,
    title: 'Platform Architecture',
    subtitle: 'System design & data flows',
    description: 'See how the entire platform is built. Explore the ingestion pipeline, agent workflows, and data flows. Click any node to view the actual prompts powering each agent.',
    color: 'text-emerald-500',
    bg: 'bg-emerald-100',
  },
  evals: {
    icon: BarChart3,
    title: 'AI Quality',
    subtitle: 'Eval & cost tracking',
    description: 'Track AI evaluation metrics, token costs, and user feedback across all generated content. Monitor quality scores and spending over time.',
    color: 'text-amber-500',
    bg: 'bg-amber-100',
  },
}

interface AppHeaderProps {
  activeMode: Mode
  onRefresh?: () => void
  isRefreshing?: boolean
  onOpenGuide?: () => void
  shouldAnimateGuide?: boolean
  onOpenWalkthrough?: () => void
}

export default function AppHeader({ activeMode, onOpenGuide, shouldAnimateGuide = false, onOpenWalkthrough }: AppHeaderProps) {
  const config = modeConfig[activeMode]
  const Icon = config.icon

  // User info from localStorage
  const [userName, setUserName] = useState<string>('')
  const [userTeam, setUserTeam] = useState<string>('')
  const [showUserMenu, setShowUserMenu] = useState(false)

  useEffect(() => {
    setUserName(localStorage.getItem('userName') || '')
    setUserTeam(localStorage.getItem('userTeam') || '')
  }, [])

  const handleLogout = () => {
    sessionStorage.removeItem('c1_hub_authenticated')
    window.location.reload()
  }

  // Get initials from name
  const getInitials = (name: string) => {
    if (!name || !name.trim()) return '??'
    return name
      .trim()
      .split(' ')
      .filter(n => n.length > 0)
      .map(n => n[0])
      .join('')
      .toUpperCase()
      .slice(0, 2) || '??'
  }

  return (
    <header className="min-h-16 bg-white border-b border-slate-200 flex items-center justify-between px-6 shrink-0 py-3">
      <div className="flex items-center gap-3 flex-1 min-w-0">
        <div className={cn('w-10 h-10 rounded-xl flex items-center justify-center shrink-0', config.bg)}>
          <Icon size={20} className={config.color} />
        </div>
        <div className="min-w-0 flex-1">
          <h1 className="text-lg font-semibold text-slate-900">{config.title}</h1>
          <TypewriterEffect
            key={activeMode}
            text={config.description}
            className="text-xs text-slate-500 leading-relaxed"
            speed={15}
            startDelay={200}
          />
        </div>
      </div>

      <div className="flex items-center gap-2 shrink-0 ml-4">
        {/* Walkthrough button */}
        {onOpenWalkthrough && (
          <button
            onClick={onOpenWalkthrough}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-emerald-600 hover:bg-emerald-50 transition-colors border border-emerald-200 hover:border-emerald-300"
          >
            <PlayCircle size={18} />
            <span className="text-sm font-medium">Walkthrough</span>
          </button>
        )}

        {/* Guide button */}
        {onOpenGuide && (
          <button
            onClick={onOpenGuide}
            className={cn(
              "flex items-center gap-1.5 px-3 py-2 rounded-lg text-teal-600 hover:bg-teal-50 transition-colors border border-teal-200 hover:border-teal-300",
              shouldAnimateGuide && "animate-pulse ring-2 ring-teal-400 ring-offset-2 shadow-lg shadow-teal-200"
            )}
          >
            <Compass size={18} className={cn(shouldAnimateGuide && "animate-spin")} style={shouldAnimateGuide ? { animationDuration: '3s' } : undefined} />
            <span className="text-sm font-medium">Guide</span>
            {shouldAnimateGuide && (
              <span className="ml-1 text-xs bg-teal-500 text-white px-1.5 py-0.5 rounded-full animate-bounce">New</span>
            )}
          </button>
        )}

        {/* User indicator with dropdown */}
        <div className="relative">
          <button
            onClick={() => setShowUserMenu(!showUserMenu)}
            className="flex items-center gap-2 p-1.5 rounded-lg hover:bg-slate-100 transition-colors"
          >
            <div className={cn(
              'w-8 h-8 rounded-full flex items-center justify-center text-white text-xs font-medium',
              teamColors[userTeam] || 'bg-slate-500'
            )}>
              {userName ? getInitials(userName) : <User size={16} />}
            </div>
            {userName && (
              <div className="hidden sm:block text-left">
                <div className="text-sm font-medium text-slate-700">{userName}</div>
                <div className="text-xs text-slate-500">{userTeam}</div>
              </div>
            )}
          </button>

          {/* Dropdown menu */}
          {showUserMenu && (
            <div className="absolute right-0 mt-2 w-48 bg-white rounded-lg shadow-lg border border-slate-200 py-1 z-50">
              <div className="px-4 py-2 border-b border-slate-100">
                <div className="text-sm font-medium text-slate-700">{userName || 'Anonymous'}</div>
                <div className="text-xs text-slate-500">{userTeam || 'No team'}</div>
              </div>
              <button
                onClick={handleLogout}
                className="w-full px-4 py-2 text-left text-sm text-slate-600 hover:bg-slate-50 flex items-center gap-2"
              >
                <LogOut size={14} />
                Sign Out
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}
