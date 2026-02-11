'use client'

import { Activity, Search, Package, Building2, Factory, FileText, ChevronLeft, ChevronRight, Database, Users, ShoppingCart, Construction, Mic, GitBranch, Ship, Compass, Cpu, BarChart3 } from 'lucide-react'
import { motion } from 'framer-motion'
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

// Hidden for demo - will re-enable when features are ready
const futurePages: FuturePage[] = [
  // { id: 'customer-analytics', label: 'Customer Analytics', icon: Users, description: 'Customer insights', tooltip: 'Advanced customer file analytics with trend identification and opportunity discovery' },
  // { id: 'ecommerce-analytics', label: 'Ecommerce Analytics', icon: ShoppingCart, description: 'Sales analytics', tooltip: 'Full site analytics, behavioral insights, and conversion optimization' },
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
  highlight?: boolean
}

// Core workflow tabs
const coreNavItems: NavItem[] = [
  { id: 'pulse', label: 'The Brief', icon: Activity, description: 'Strategic Priorities', color: 'text-emerald-500', bg: 'bg-emerald-500' },
  { id: 'discovery', label: 'Discovery', icon: Compass, description: 'All Datasets', color: 'text-teal-500', bg: 'bg-teal-500', tooltip: 'Explore market intelligence with AI assistant' },
  { id: 'research', label: 'Deep Research', icon: Search, description: 'Deep analysis', color: 'text-emerald-500', bg: 'bg-emerald-500' },
  { id: 'industries', label: 'Core Industries', icon: Factory, description: 'Narrative timelines', color: 'text-emerald-500', bg: 'bg-emerald-500' },
  { id: 'supply-network', label: 'Supply Network', icon: Ship, description: 'Supply chain graph', color: 'text-indigo-500', bg: 'bg-indigo-500' },
  { id: 'pipeline', label: 'Company Lookup', icon: GitBranch, description: 'Prospect discovery', color: 'text-purple-500', bg: 'bg-purple-500', isBeta: true, tooltip: 'Find similar companies and decision makers' },
]

// Documentation & settings tabs (below divider)
const secondaryNavItems: NavItem[] = [
  { id: 'app-architecture', label: 'Architecture', icon: Cpu, description: 'System design', color: 'text-emerald-400', bg: 'bg-emerald-500', highlight: true },
  { id: 'ai-quality', label: 'AI Quality', icon: BarChart3, description: 'Eval & cost metrics', color: 'text-amber-500', bg: 'bg-amber-500' },
  { id: 'data-preferences', label: 'Tracked Entities', icon: Database, description: 'Manage tracked data', color: 'text-cyan-500', bg: 'bg-cyan-500' },
]

// Hidden tabs (kept for type completeness)
const hiddenNavItems: NavItem[] = [
  { id: 'products', label: 'Products', icon: Package, description: 'Product intelligence', color: 'text-blue-500', bg: 'bg-blue-500', isBeta: true, isHidden: true },
  { id: 'field-sales', label: 'Field Intel', icon: Mic, description: 'Field observations', color: 'text-emerald-500', bg: 'bg-emerald-500', isDemo: true, isHidden: true, tooltip: 'Capture field intelligence' },
  { id: 'companies', label: 'Companies', icon: Building2, description: 'Coming soon', color: 'text-slate-500', bg: 'bg-slate-500', isDisabled: true, isHidden: true },
]

const navItems: NavItem[] = [...coreNavItems, ...secondaryNavItems, ...hiddenNavItems]

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
  const renderNavItem = (item: NavItem) => {
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
          <motion.span
            layoutId="sidebar-active-pill"
            transition={{ type: "spring", stiffness: 300, damping: 30 }}
            className={cn('absolute left-0 top-1/2 -translate-y-1/2 w-1 h-6 rounded-r-full', item.bg)}
          />
        )}
        <span
          className={cn(
            'w-8 h-8 rounded-lg flex items-center justify-center transition-colors relative z-10',
            isDisabled ? 'bg-slate-800/30' : isActive ? `${item.bg}/20` : 'bg-slate-800/50'
          )}
        >
          <Icon size={18} className={isDisabled ? 'text-slate-600' : isActive ? item.color : 'text-slate-400'} />
        </span>
        {!collapsed && (
          <span className="flex-1 text-left">
            <span className="flex items-center gap-2">
              <span className={cn(
                'text-sm font-medium',
                isDisabled && 'text-slate-500',
                !isDisabled && !isActive && item.highlight && 'text-emerald-400'
              )}>{item.label}</span>
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
  }

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
            <h1 className="text-slate-100 font-semibold text-base leading-tight">Composites Industry</h1>
            <p className="text-slate-400 text-xs">Intelligence Hub</p>
          </div>
        ) : (
          <div className="flex items-center justify-center w-full">
            <span className="text-slate-100 font-bold text-lg">CI</span>
          </div>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-4 px-2 space-y-1 overflow-y-auto scrollbar-hide">
        {/* Core workflow tabs */}
        {coreNavItems.filter(item => !item.isHidden).map((item) => renderNavItem(item))}

        {/* Divider between core and secondary */}
        <div className="my-4 mx-3 border-t border-slate-800/50" />

        {/* Documentation & settings tabs */}
        {secondaryNavItems.filter(item => !item.isHidden).map((item) => renderNavItem(item))}

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
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-slate-500 hover:bg-slate-800/40 hover:text-slate-300 transition-colors"
        >
          {collapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
          {!collapsed && <span className="text-xs">Collapse</span>}
        </button>
        {/* Branding */}
        {!collapsed && (
          <div className="text-center mt-3 pt-3 border-t border-slate-800/30">
            <p className="text-[10px] text-slate-600 uppercase tracking-wider">Powered by</p>
            <p className="text-xs text-slate-500 font-medium">KZ Intel</p>
          </div>
        )}
      </div>
    </aside>
  )
}
