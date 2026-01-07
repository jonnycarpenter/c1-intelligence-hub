'use client'

import { Activity, Search, Package, Building2, Factory, FileText, Settings, ChevronLeft, ChevronRight, Database, Users, ShoppingCart, Construction, Mic, GitBranch, Ship } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { Mode } from '@/types'

// Future pages that are not clickable - just displayed as coming soon
interface FuturePage {
  id: string
  label: string
  icon: typeof Activity
  description: string
  tooltip: string
}

const futurePages: FuturePage[] = [
  { id: 'customer-analytics', label: 'Customer Analytics', icon: Users, description: 'Customer insights', tooltip: 'Advanced customer file analytics with trend identification and opportunity discovery' },
  { id: 'ecommerce-analytics', label: 'Ecommerce Analytics', icon: ShoppingCart, description: 'Sales analytics', tooltip: 'Full site analytics, behavioral insights, and conversion optimization' },
]

interface NavItem {
  id: Mode
  label: string
  icon: typeof Activity
  description: string
  color: string
  bg: string
  isDisabled?: boolean
  isBeta?: boolean
  isDemo?: boolean
  isHidden?: boolean
  tooltip?: string
}

const navItems: NavItem[] = [
  { id: 'pulse', label: 'Pulse', icon: Activity, description: 'Real-time intelligence', color: 'text-emerald-500', bg: 'bg-emerald-500' },
  { id: 'research', label: 'Research', icon: Search, description: 'Deep analysis', color: 'text-emerald-500', bg: 'bg-emerald-500' },
  { id: 'pipeline', label: 'Pipeline', icon: GitBranch, description: 'Prospect discovery', color: 'text-purple-500', bg: 'bg-purple-500', tooltip: 'Find similar companies and decision makers' },
  // { id: 'importyeti', label: 'Trade Intel', icon: Ship, description: 'Supply chain tracking', color: 'text-indigo-500', bg: 'bg-indigo-500' }, // ARCHIVED
  { id: 'products', label: 'Products', icon: Package, description: 'Product intelligence', color: 'text-blue-500', bg: 'bg-blue-500', isBeta: true },
  { id: 'field-sales', label: 'Field Intel', icon: Mic, description: 'Field observations', color: 'text-emerald-500', bg: 'bg-emerald-500', isDemo: true, tooltip: 'Capture field intelligence' },
  { id: 'companies', label: 'Companies', icon: Building2, description: 'Coming soon', color: 'text-slate-500', bg: 'bg-slate-500', isDisabled: true, isHidden: true },
  { id: 'industries', label: 'Industries', icon: Factory, description: 'Coming soon', color: 'text-slate-500', bg: 'bg-slate-500', isDisabled: true, isHidden: true },
  { id: 'data-preferences', label: 'Data & Prefs', icon: Database, description: 'Manage tracked data', color: 'text-cyan-500', bg: 'bg-cyan-500' },
]

interface SidebarProps {
  activeMode: Mode
  setActiveMode: (mode: Mode) => void
  collapsed: boolean
  setCollapsed: (collapsed: boolean) => void
  reportCount: number
  onOpenReport: () => void
}

export default function Sidebar({
  activeMode,
  setActiveMode,
  collapsed,
  setCollapsed,
  reportCount,
  onOpenReport,
}: SidebarProps) {
  return (
    <aside
      className={cn(
        'h-full bg-slate-900 flex flex-col shrink-0 transition-all duration-200',
        collapsed ? 'w-[72px]' : 'w-60'
      )}
    >
      {/* Logo */}
      <div className="h-16 flex items-center px-4 border-b border-slate-800/50">
        {!collapsed ? (
          <div className="flex flex-col">
            <h1 className="text-slate-100 font-semibold text-base leading-tight">Composites One</h1>
            <p className="text-slate-400 text-xs">Intelligence Hub</p>
          </div>
        ) : (
          <div className="flex items-center justify-center w-full">
            <span className="text-slate-100 font-bold text-lg">C1</span>
          </div>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-4 px-2 space-y-1 overflow-y-auto scrollbar-hide">
        {navItems.filter(item => !item.isHidden).map((item) => {
          const isActive = activeMode === item.id
          const Icon = item.icon
          const isDisabled = item.isDisabled
          return (
            <button
              key={item.id}
              onClick={() => setActiveMode(item.id)}
              title={isDisabled && item.tooltip ? item.tooltip : undefined}
              className={cn(
                'w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all relative group',
                isDisabled
                  ? 'opacity-50 cursor-default'
                  : isActive
                    ? 'bg-slate-800/80 text-white'
                    : 'text-slate-300 hover:bg-slate-800/40 hover:text-white'
              )}
            >
              {isActive && !isDisabled && (
                <span className={cn('absolute left-0 top-1/2 -translate-y-1/2 w-1 h-6 rounded-r-full', item.bg)} />
              )}
              <span
                className={cn(
                  'w-8 h-8 rounded-lg flex items-center justify-center transition-colors',
                  isDisabled ? 'bg-slate-800/30' : isActive ? `${item.bg}/20` : 'bg-slate-800/50'
                )}
              >
                <Icon size={18} className={isDisabled ? 'text-slate-600' : isActive ? item.color : 'text-slate-400'} />
              </span>
              {!collapsed && (
                <span className="flex-1 text-left">
                  <span className="flex items-center gap-2">
                    <span className={cn('text-sm font-medium', isDisabled && 'text-slate-500')}>{item.label}</span>
                    {isDisabled && (
                      <span className="text-[10px] px-1.5 py-0.5 bg-slate-700 text-slate-400 rounded-full">Soon</span>
                    )}
                    {item.isBeta && (
                      <span className="text-[10px] px-1.5 py-0.5 bg-blue-600 text-blue-100 rounded-full font-medium">Beta</span>
                    )}
                    {item.isDemo && (
                      <span className="text-[10px] px-1.5 py-0.5 bg-blue-600 text-blue-100 rounded-full font-medium">Demo</span>
                    )}
                  </span>
                  <span className="text-xs text-slate-500 block">{item.description}</span>
                </span>
              )}
            </button>
          )
        })}

        <div className="my-4 mx-3 border-t border-slate-800/50" />

        {/* Report Builder Button */}
        <button
          onClick={onOpenReport}
          className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-slate-300 hover:bg-slate-800/40 hover:text-white transition-all"
        >
          <span className="w-8 h-8 rounded-lg bg-slate-800/50 flex items-center justify-center relative">
            <FileText size={18} className="text-slate-400" />
            {reportCount > 0 && (
              <span className="absolute -top-1 -right-1 w-4 h-4 bg-emerald-500 text-white text-xs font-bold rounded-full flex items-center justify-center">
                {reportCount}
              </span>
            )}
          </span>
          {!collapsed && (
            <span className="flex-1 text-left">
              <span className="text-sm font-medium block">Report Builder</span>
              <span className="text-xs text-slate-500 block">{reportCount} items</span>
            </span>
          )}
        </button>

        {/* Divider before future pages */}
        <div className="my-4 mx-3 border-t border-slate-800/50" />

        {/* Future Pages - Under Construction */}
        {futurePages.map((page) => {
          const Icon = page.icon
          return (
            <div
              key={page.id}
              className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg opacity-40 cursor-not-allowed relative group"
              title={page.tooltip}
            >
              <div className="w-8 h-8 rounded-lg bg-slate-800/30 flex items-center justify-center">
                <Icon size={18} className="text-slate-600" />
              </div>
              {!collapsed && (
                <div className="flex-1 text-left">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-medium text-slate-500">{page.label}</p>
                  </div>
                  <p className="text-xs text-slate-600">{page.description}</p>
                </div>
              )}
              {/* Under Construction overlay */}
              <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                <div className={cn(
                  "flex items-center gap-1 bg-emerald-500/90 text-white text-[10px] font-bold px-2 py-1 rounded-full shadow-lg",
                  collapsed && "px-1.5"
                )}>
                  <Construction size={12} />
                  {!collapsed && <span>UNDER CONSTRUCTION</span>}
                </div>
              </div>
              {/* Custom tooltip for better styling */}
              <div className="absolute left-full ml-2 top-1/2 -translate-y-1/2 z-50 hidden group-hover:block">
                <div className="bg-slate-800 text-white text-xs px-3 py-2 rounded-lg shadow-xl max-w-[200px] whitespace-normal border border-slate-700">
                  <p className="font-semibold text-emerald-400 mb-1">{page.label}</p>
                  <p className="text-slate-300">{page.tooltip}</p>
                </div>
              </div>
            </div>
          )
        })}
      </nav>

      {/* Footer */}
      <div className="p-2 border-t border-slate-800/50">
        <button className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-slate-400 hover:bg-slate-800/40 hover:text-slate-200 transition-colors">
          <Settings size={18} />
          {!collapsed && <span className="text-sm">Settings</span>}
        </button>
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 mt-2 rounded-lg text-slate-500 hover:bg-slate-800/40 hover:text-slate-300 transition-colors"
        >
          {collapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
          {!collapsed && <span className="text-xs">Collapse</span>}
        </button>
      </div>
    </aside>
  )
}
