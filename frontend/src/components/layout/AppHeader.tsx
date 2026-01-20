'use client'

import { useState, useEffect } from 'react'
import { Activity, Search, Package, Building2, Factory, Database, RefreshCw, Bell, User, Mic, GitBranch, Ship, LogOut } from 'lucide-react'
import { Button } from '@/components/ui'
import { cn } from '@/lib/utils'
import type { Mode } from '@/types'

// Team color mapping
const teamColors: Record<string, string> = {
  'Sales East': 'bg-blue-500',
  'Sales West': 'bg-emerald-500',
  'Marketing': 'bg-purple-500',
  'Product/Supplier': 'bg-emerald-500',
  'All Others': 'bg-slate-500',
}

const modeConfig: Record<Mode, { icon: typeof Activity; title: string; subtitle: string; color: string; bg: string }> = {
  pulse: {
    icon: Activity,
    title: 'Need to Know',
    subtitle: 'Curated headlines',
    color: 'text-emerald-500',
    bg: 'bg-emerald-100',
  },
  discovery: {
    icon: Activity, // Using Activity temporarily, could use Compass
    title: 'Discovery',
    subtitle: 'AI-guided market exploration',
    color: 'text-teal-500',
    bg: 'bg-teal-100',
  },
  research: {
    icon: Search,
    title: 'Deep Research',
    subtitle: 'Comprehensive analysis & insights',
    color: 'text-emerald-500',
    bg: 'bg-emerald-100',
  },
  products: {
    icon: Package,
    title: 'Product Intelligence',
    subtitle: 'SKU analysis & comparisons',
    color: 'text-blue-500',
    bg: 'bg-blue-100',
  },
  'field-sales': {
    icon: Mic,
    title: 'Field Intel',
    subtitle: 'Voice memos & field observations',
    color: 'text-rose-500',
    bg: 'bg-rose-100',
  },
  pipeline: {
    icon: GitBranch,
    title: 'Pipeline',
    subtitle: 'Companies, Prospects, and Decision Makers',
    color: 'text-slate-500',
    bg: 'bg-slate-100',
  },
  companies: {
    icon: Building2,
    title: 'Company Intelligence',
    subtitle: 'Competitor & supplier tracking',
    color: 'text-emerald-500',
    bg: 'bg-emerald-100',
  },
  industries: {
    icon: Factory,
    title: 'Industry Intelligence',
    subtitle: 'Market trends & insights',
    color: 'text-purple-500',
    bg: 'bg-purple-100',
  },
  'data-preferences': {
    icon: Database,
    title: 'Data & Preferences',
    subtitle: 'Manage tracked data & settings',
    color: 'text-cyan-500',
    bg: 'bg-cyan-100',
  },
  // ARCHIVED - Trade Intel
  // importyeti: {
  //   icon: Ship,
  //   title: 'Trade Intelligence',
  //   subtitle: 'Supply chain & shipment tracking',
  //   color: 'text-indigo-500',
  //   bg: 'bg-indigo-100',
  // },
}

interface AppHeaderProps {
  activeMode: Mode
  onRefresh?: () => void
  isRefreshing?: boolean
}

export default function AppHeader({ activeMode, onRefresh, isRefreshing = false }: AppHeaderProps) {
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
    <header className="h-16 bg-white border-b border-slate-200 flex items-center justify-between px-6 shrink-0">
      <div className="flex items-center gap-3">
        <div className={cn('w-10 h-10 rounded-xl flex items-center justify-center', config.bg)}>
          <Icon size={20} className={config.color} />
        </div>
        <div>
          <h1 className="text-lg font-semibold text-slate-900">{config.title}</h1>
          <p className="text-xs text-slate-500">{config.subtitle}</p>
        </div>
      </div>

      <div className="flex items-center gap-2">
        {activeMode === 'pulse' && onRefresh && (
          <Button variant="ghost" size="sm" onClick={onRefresh} disabled={isRefreshing}>
            <RefreshCw size={16} className={cn(isRefreshing && 'animate-spin')} />
            Refresh
          </Button>
        )}

        <button className="relative p-2 rounded-lg text-slate-500 hover:bg-slate-100 transition-colors">
          <Bell size={20} />
          <span className="absolute top-1 right-1 w-2 h-2 bg-emerald-500 rounded-full" />
        </button>

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
