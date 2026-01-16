'use client'

import React, { useState, useMemo, useImperativeHandle, forwardRef, useCallback } from 'react'
import { 
  ChevronDown, 
  ChevronRight,
  TrendingUp, 
  Radio, 
  Clock,
  Flame,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { Badge, PriorityBadge, CategoryBadge } from '@/components/ui'
import DigestCard from '@/components/digest/DigestCard'
import DiscoveryAssistant from './DiscoveryAssistant'
import type { DigestItem, DigestStats, Category, Priority } from '@/types'

// =============================================================================
// Types
// =============================================================================

export interface DiscoveryViewProps {
  items: DigestItem[]           // All articles (30-day window)
  stats: DigestStats | null     // Aggregated statistics
  isLoading: boolean
  error: Error | null
  onSelectArticle?: (id: string) => void
}

export interface DiscoveryViewRef {
  openAssistant: () => void
}

// =============================================================================
// Helper Functions
// =============================================================================

function getGreeting(): string {
  const hour = new Date().getHours()
  if (hour < 12) return 'Good morning'
  if (hour < 18) return 'Good afternoon'
  return 'Good evening'
}

function isHighPriority(priority: Priority): boolean {
  // Handle both lowercase (frontend type) and Title Case (backend API)
  const p = priority?.toLowerCase()
  return p === 'critical' || p === 'high'
}

function isWithin72Hours(timestamp: string | undefined): boolean {
  if (!timestamp) return false
  const date = new Date(timestamp)
  const now = new Date()
  const diffHours = (now.getTime() - date.getTime()) / (1000 * 60 * 60)
  return diffHours <= 72
}

function groupByCategory(items: DigestItem[]): Map<Category, DigestItem[]> {
  const grouped = new Map<Category, DigestItem[]>()
  
  for (const item of items) {
    const category = item.category
    if (!grouped.has(category)) {
      grouped.set(category, [])
    }
    grouped.get(category)!.push(item)
  }
  
  return grouped
}

// Category display configuration - aligned with backend ContentCategory enum
// Supports both Title Case (backend) and legacy lowercase (old frontend)
const CATEGORY_CONFIG: Record<string, { label: string; color: string; bgLight: string }> = {
  // Backend categories (Title Case)
  'Competitor': { label: 'Competitor Moves', color: 'border-l-rose-500', bgLight: 'bg-rose-50' },
  'Market': { label: 'Market Dynamics', color: 'border-l-blue-500', bgLight: 'bg-blue-50' },
  'Regulatory': { label: 'Health & Regulatory', color: 'border-l-amber-500', bgLight: 'bg-amber-50' },
  'Product': { label: 'Product News', color: 'border-l-cyan-500', bgLight: 'bg-cyan-50' },
  'Earnings': { label: 'Earnings & Financial', color: 'border-l-emerald-500', bgLight: 'bg-emerald-50' },
  'Partnership': { label: 'Partnerships', color: 'border-l-violet-500', bgLight: 'bg-violet-50' },
  'Expansion': { label: 'Expansion & Investment', color: 'border-l-teal-500', bgLight: 'bg-teal-50' },
  'Supply Chain': { label: 'Supply Chain', color: 'border-l-orange-500', bgLight: 'bg-orange-50' },
  'Logistics': { label: 'Logistics', color: 'border-l-yellow-500', bgLight: 'bg-yellow-50' },
  'C1 Mention': { label: 'C1 Mentions', color: 'border-l-pink-500', bgLight: 'bg-pink-50' },
  'General': { label: 'General', color: 'border-l-slate-400', bgLight: 'bg-slate-50' },
  // Legacy lowercase categories (backwards compatibility)
  'market': { label: 'Market Dynamics', color: 'border-l-blue-500', bgLight: 'bg-blue-50' },
  'supply-chain': { label: 'Supply Chain', color: 'border-l-orange-500', bgLight: 'bg-orange-50' },
  'regulatory': { label: 'Health & Regulatory', color: 'border-l-amber-500', bgLight: 'bg-amber-50' },
  'competitor': { label: 'Competitor Moves', color: 'border-l-rose-500', bgLight: 'bg-rose-50' },
  'pricing': { label: 'Pricing & Financial', color: 'border-l-emerald-500', bgLight: 'bg-emerald-50' },
  'product': { label: 'Product News', color: 'border-l-cyan-500', bgLight: 'bg-cyan-50' },
  'industry': { label: 'Industry Trends', color: 'border-l-indigo-500', bgLight: 'bg-indigo-50' },
}

// Category priority for sorting (lower = shown first)
// Supports both Title Case and legacy lowercase
const CATEGORY_PRIORITY: Record<string, number> = {
  // Title Case (backend)
  'C1 Mention': 0,
  'Competitor': 1,
  'Market': 2,
  'Regulatory': 3,
  'Earnings': 4,
  'Partnership': 5,
  'Expansion': 6,
  'Supply Chain': 7,
  'Logistics': 8,
  'Product': 9,
  'General': 10,
  // Legacy lowercase
  'competitor': 1,
  'market': 2,
  'regulatory': 3,
  'pricing': 4,
  'supply-chain': 7,
  'product': 9,
  'industry': 10,
}

// =============================================================================
// Sub-Components
// =============================================================================

interface CategoryAccordionProps {
  category: Category
  items: DigestItem[]
  onSelectArticle?: (id: string) => void
  onQuickFilter?: (query: string) => void
  defaultOpen?: boolean
}

function CategoryAccordion({ 
  category, 
  items, 
  onSelectArticle,
  onQuickFilter,
  defaultOpen = false 
}: CategoryAccordionProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen)
  const [showAll, setShowAll] = useState(false)
  
  const config = CATEGORY_CONFIG[category] || { 
    label: category, 
    color: 'border-l-slate-400', 
    bgLight: 'bg-slate-50' 
  }
  
  // Sort items: critical first, then high, then by timestamp
  const sortedItems = useMemo(() => {
    return [...items].sort((a, b) => {
      const priorityOrder = { critical: 0, high: 1, medium: 2, low: 3 }
      const aPriority = priorityOrder[a.priority] ?? 4
      const bPriority = priorityOrder[b.priority] ?? 4
      if (aPriority !== bPriority) return aPriority - bPriority
      // Then by timestamp (newest first)
      return new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
    })
  }, [items])
  
  const highPriorityCount = items.filter(i => isHighPriority(i.priority)).length
  const displayItems = showAll ? sortedItems : sortedItems.slice(0, 8)
  const hasMore = sortedItems.length > 8
  
  return (
    <div className={cn(
      "border-l-4 rounded-r-lg bg-white shadow-sm overflow-hidden",
      config.color
    )}>
      {/* Header */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between p-4 hover:bg-slate-50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <span className="font-semibold text-slate-800">{config.label}</span>
          {highPriorityCount > 0 && (
            <span className="flex items-center gap-1 text-xs font-medium text-amber-600">
              <Flame size={12} />
              {highPriorityCount} urgent
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm text-slate-500">{items.length} items</span>
          {isOpen ? <ChevronDown size={18} className="text-slate-400" /> : <ChevronRight size={18} className="text-slate-400" />}
        </div>
      </button>
      
      {/* Content */}
      {isOpen && (
        <div className="border-t border-slate-100 p-4 space-y-3">
          {displayItems.map((item) => (
            <DigestCard key={item.id} item={item} onQuickFilter={onQuickFilter} />
          ))}
          
          {hasMore && !showAll && (
            <button
              onClick={() => setShowAll(true)}
              className="w-full py-2 text-sm text-teal-600 hover:text-teal-700 font-medium transition-colors"
            >
              Show all {sortedItems.length - 8} more →
            </button>
          )}
        </div>
      )}
    </div>
  )
}

// =============================================================================
// Main Component
// =============================================================================

const DiscoveryView = forwardRef<DiscoveryViewRef, DiscoveryViewProps>(
  function DiscoveryView({ items, stats, isLoading, error, onSelectArticle }, ref) {
    const [assistantQuery, setAssistantQuery] = useState<string | undefined>(undefined)
    
    // Expose openAssistant method to parent (no-op now since always visible)
    useImperativeHandle(ref, () => ({
      openAssistant: () => {} // Always visible now
    }))
    
    // Handle quick filter from entity click
    const handleQuickFilter = useCallback((query: string) => {
      setAssistantQuery(`Tell me more about ${query}`)
    }, [])
    
    // Group items by category
    const groupedByCategory = useMemo(() => groupByCategory(items), [items])
    
    // Sort categories by: 1) high-priority count desc, 2) category priority
    const sortedCategories = useMemo(() => {
      return Array.from(groupedByCategory.entries())
        .sort(([catA, itemsA], [catB, itemsB]) => {
          const highCountA = itemsA.filter(i => isHighPriority(i.priority)).length
          const highCountB = itemsB.filter(i => isHighPriority(i.priority)).length
          if (highCountA !== highCountB) return highCountB - highCountA
          return (CATEGORY_PRIORITY[catA] ?? 10) - (CATEGORY_PRIORITY[catB] ?? 10)
        })
    }, [groupedByCategory])
    
    // Right column: filter for high/critical + last 72h
    const latestHighPriority = useMemo(() => {
      return items
        .filter(item => isHighPriority(item.priority) && isWithin72Hours(item.timestamp))
        .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
        .slice(0, 15)
    }, [items])
    
    // Calculate stats
    const totalItems = items.length
    const criticalCount = items.filter(i => i.priority === 'critical').length
    const highCount = items.filter(i => i.priority === 'high').length
    
    return (
      <div className="h-full flex flex-col overflow-hidden bg-slate-200 p-4 gap-4">
        <div className="flex-1 flex gap-4 min-h-0">
          {/* AI Assistant Panel (always visible on left, like Pipeline) */}
          <DiscoveryAssistant 
            isOpen={true} 
            onClose={() => setAssistantQuery(undefined)}
            initialQuery={assistantQuery}
          />
          
          {/* Main Content Area */}
          <div className="flex-1 flex flex-col min-w-0 overflow-hidden bg-white rounded-2xl shadow-sm border border-slate-100/60">
          {/* Header */}
          <div className="shrink-0 px-6 py-4 bg-white border-b border-slate-200">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                {/* Live badge */}
                <div className="flex items-center gap-1.5 px-2.5 py-1 bg-emerald-100 text-emerald-700 rounded-full">
                  <Radio size={12} className="animate-pulse" />
                  <span className="text-xs font-semibold">Live Intelligence</span>
                </div>
                
                {/* Greeting and stats */}
                <div>
                  <h1 className="text-xl font-bold text-slate-800">{getGreeting()}, Team</h1>
                  <p className="text-sm text-slate-500">
                    We've analyzed <span className="font-medium text-slate-700">{totalItems}</span> signals
                    {criticalCount > 0 && (
                      <span className="ml-1">
                        • <span className="text-red-600 font-medium">{criticalCount} critical</span>
                      </span>
                    )}
                    {highCount > 0 && (
                      <span className="ml-1">
                        • <span className="text-emerald-600 font-medium">{highCount} high priority</span>
                      </span>
                    )}
                  </p>
                </div>
              </div>
              

            </div>
          </div>
          
          {/* Loading state */}
          {isLoading && (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center">
                <div className="animate-spin w-8 h-8 border-2 border-teal-500 border-t-transparent rounded-full mx-auto mb-3" />
                <p className="text-slate-500">Loading intelligence feed...</p>
              </div>
            </div>
          )}
          
          {/* Error state */}
          {error && (
            <div className="flex-1 flex items-center justify-center p-6">
              <div className="text-center bg-red-50 text-red-700 rounded-xl p-6 max-w-md">
                <p className="font-medium mb-1">Failed to load data</p>
                <p className="text-sm">{error.message}</p>
              </div>
            </div>
          )}
          
          {/* Main 2-column grid */}
          {!isLoading && !error && (
            <div className="flex-1 overflow-hidden p-6">
              <div className="h-full flex gap-6">
                {/* Left Column: Category Accordions (30-day) */}
                <div className="flex-1 overflow-y-auto pr-2 scrollbar-thin scrollbar-thumb-slate-300">
                  <div className="flex items-center gap-2 mb-4">
                    <TrendingUp size={16} className="text-slate-500" />
                    <h2 className="text-sm font-semibold text-slate-600 uppercase tracking-wide">
                      By Category (30 days)
                    </h2>
                  </div>
                  
                  <div className="space-y-3">
                    {sortedCategories.map(([category, categoryItems], index) => (
                      <CategoryAccordion
                        key={category}
                        category={category}
                        items={categoryItems}
                        onSelectArticle={onSelectArticle}
                        onQuickFilter={handleQuickFilter}
                        defaultOpen={index === 0}
                      />
                    ))}
                    
                    {sortedCategories.length === 0 && (
                      <div className="text-center py-12 text-slate-500">
                        <p>No articles found in the last 30 days.</p>
                      </div>
                    )}
                  </div>
                </div>
                
                {/* Right Column: Latest High-Priority (72h) */}
                <div className="w-[360px] shrink-0 overflow-y-auto pl-4 border-l border-slate-200 scrollbar-thin scrollbar-thumb-slate-300">
                  <div className="flex items-center gap-2 mb-4">
                    <Clock size={16} className="text-amber-500" />
                    <h2 className="text-sm font-semibold text-slate-600 uppercase tracking-wide">
                      Latest Urgent (72h)
                    </h2>
                    {latestHighPriority.length > 0 && (
                      <span className="ml-auto text-xs text-slate-400">
                        {latestHighPriority.length} items
                      </span>
                    )}
                  </div>
                  
                  {latestHighPriority.length > 0 ? (
                    <div className="space-y-3">
                      {latestHighPriority.map((item) => (
                        <DigestCard key={item.id} item={item} onQuickFilter={handleQuickFilter} />
                      ))}
                    </div>
                  ) : (
                    <div className="text-center py-12 text-slate-500">
                      <div className="p-3 bg-slate-100 rounded-full w-fit mx-auto mb-3">
                        <Clock size={24} className="text-slate-400" />
                      </div>
                      <p className="font-medium mb-1">All quiet</p>
                      <p className="text-sm">No high-priority items in the last 72 hours.</p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
          </div>
        </div>
      </div>
    )
  }
)

export default DiscoveryView
