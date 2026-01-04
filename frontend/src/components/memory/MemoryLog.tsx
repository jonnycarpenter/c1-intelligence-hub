'use client'

import { useState, useEffect, useCallback } from 'react'
import {
  Bookmark,
  Clock,
  Trash2,
  Search,
  FileText,
  Filter,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  AlertCircle,
  Users,
  Pin,
  PinOff,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { api } from '@/lib/api'

interface MemoryItem {
  id: string
  source: string  // 'briefing' or 'research_export'
  question: string
  answer: string
  tags?: string[]
  team?: string
  pinned: boolean
  expires_at?: string
  user_name?: string
  created_at: string
}

interface MemoryLogProps {
  className?: string
}

// Calculate days until expiration
function getDaysUntilExpiry(expiresAt?: string): number | null {
  if (!expiresAt) return null
  const expiry = new Date(expiresAt)
  const now = new Date()
  const diffMs = expiry.getTime() - now.getTime()
  return Math.ceil(diffMs / (1000 * 60 * 60 * 24))
}

// Format relative time
function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))
  
  if (diffDays === 0) return 'Today'
  if (diffDays === 1) return 'Yesterday'
  if (diffDays < 7) return `${diffDays} days ago`
  if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`
  return `${Math.floor(diffDays / 30)} months ago`
}

// Team badge colors
const teamColors: Record<string, string> = {
  'Sales East': 'bg-blue-100 text-blue-700',
  'Sales West': 'bg-emerald-100 text-emerald-700',
  'Marketing': 'bg-purple-100 text-purple-700',
  'Product/Supplier': 'bg-amber-100 text-amber-700',
  'All Others': 'bg-slate-100 text-slate-700',
}

export function MemoryLog({ className }: MemoryLogProps) {
  const [memories, setMemories] = useState<MemoryItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [filter, setFilter] = useState<'all' | 'pinned' | 'briefing' | 'research'>('all')
  const [searchQuery, setSearchQuery] = useState('')

  const fetchMemories = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await api.getMemoryLog({
        limit: 50,
        pinnedOnly: filter === 'pinned',
      })
      setMemories(result.items)
      setTotal(result.total)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load memories')
    } finally {
      setLoading(false)
    }
  }, [filter])

  useEffect(() => {
    fetchMemories()
  }, [fetchMemories])

  const handlePin = async (memoryId: string, currentlyPinned: boolean) => {
    try {
      await api.toggleMemoryPin(memoryId, !currentlyPinned)
      // Update local state
      setMemories(prev => prev.map(m => 
        m.id === memoryId ? { ...m, pinned: !currentlyPinned } : m
      ))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update pin')
    }
  }

  const handleDelete = async (memoryId: string) => {
    if (!confirm('Are you sure you want to delete this memory?')) return
    
    try {
      await api.deleteMemory(memoryId)
      setMemories(prev => prev.filter(m => m.id !== memoryId))
      setTotal(prev => prev - 1)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete memory')
    }
  }

  // Filter memories based on selected filter and search
  const filteredMemories = memories.filter(m => {
    if (filter === 'briefing' && m.source !== 'briefing') return false
    if (filter === 'research' && m.source !== 'research_export') return false
    
    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      return m.question.toLowerCase().includes(query) || 
             m.answer.toLowerCase().includes(query) ||
             m.tags?.some(t => t.toLowerCase().includes(query))
    }
    return true
  })

  return (
    <div className={cn('bg-white rounded-xl border border-slate-200', className)}>
      {/* Header */}
      <div className="p-4 border-b border-slate-200">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Bookmark className="w-5 h-5 text-amber-500" />
            <h2 className="font-semibold text-slate-900">Memory Log</h2>
            <span className="text-xs text-slate-500 bg-slate-100 px-2 py-0.5 rounded-full">
              {total} saved
            </span>
          </div>
          <button
            onClick={fetchMemories}
            disabled={loading}
            className="p-2 text-slate-500 hover:bg-slate-100 rounded-lg transition-colors"
          >
            <RefreshCw className={cn('w-4 h-4', loading && 'animate-spin')} />
          </button>
        </div>

        {/* Search & Filters */}
        <div className="flex gap-2">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search memories..."
              className="w-full pl-9 pr-3 py-2 text-sm border border-slate-200 rounded-lg
                       focus:outline-none focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500"
            />
          </div>
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value as typeof filter)}
            className="px-3 py-2 text-sm border border-slate-200 rounded-lg bg-white
                     focus:outline-none focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500"
          >
            <option value="all">All</option>
            <option value="pinned">📌 Pinned</option>
            <option value="briefing">💬 Briefings</option>
            <option value="research">📄 Research</option>
          </select>
        </div>
      </div>

      {/* Error state */}
      {error && (
        <div className="p-4 m-4 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2 text-red-700 text-sm">
          <AlertCircle className="w-4 h-4" />
          {error}
        </div>
      )}

      {/* Memory List */}
      <div className="divide-y divide-slate-100 max-h-[600px] overflow-y-auto">
        {loading && memories.length === 0 ? (
          <div className="p-8 text-center text-slate-500">
            <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2" />
            Loading memories...
          </div>
        ) : filteredMemories.length === 0 ? (
          <div className="p-8 text-center text-slate-500">
            <Bookmark className="w-8 h-8 mx-auto mb-2 text-slate-300" />
            <p className="font-medium">No memories yet</p>
            <p className="text-sm mt-1">
              Save briefings or export research to build your memory log
            </p>
          </div>
        ) : (
          filteredMemories.map((memory) => {
            const isExpanded = expandedId === memory.id
            const daysLeft = getDaysUntilExpiry(memory.expires_at)
            
            return (
              <div key={memory.id} className="p-4 hover:bg-slate-50 transition-colors">
                {/* Memory Header */}
                <div className="flex items-start gap-3">
                  <div className={cn(
                    'w-8 h-8 rounded-lg flex items-center justify-center shrink-0',
                    memory.source === 'briefing' ? 'bg-amber-100' : 'bg-emerald-100'
                  )}>
                    {memory.source === 'briefing' ? (
                      <Bookmark className="w-4 h-4 text-amber-600" />
                    ) : (
                      <FileText className="w-4 h-4 text-emerald-600" />
                    )}
                  </div>
                  
                  <div className="flex-1 min-w-0">
                    {/* Question/Title */}
                    <button
                      onClick={() => setExpandedId(isExpanded ? null : memory.id)}
                      className="text-left w-full"
                    >
                      <p className="font-medium text-slate-900 line-clamp-2">
                        {memory.question}
                      </p>
                    </button>
                    
                    {/* Meta info */}
                    <div className="flex flex-wrap items-center gap-2 mt-1.5">
                      <span className="text-xs text-slate-500 flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {formatRelativeTime(memory.created_at)}
                      </span>
                      
                      {memory.team && (
                        <span className={cn(
                          'text-xs px-2 py-0.5 rounded-full',
                          teamColors[memory.team] || teamColors['All Others']
                        )}>
                          {memory.team}
                        </span>
                      )}
                      
                      {memory.pinned && (
                        <span className="text-xs px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 flex items-center gap-1">
                          <Pin className="w-3 h-3" />
                          Pinned
                        </span>
                      )}
                      
                      {!memory.pinned && daysLeft !== null && (
                        <span className={cn(
                          'text-xs px-2 py-0.5 rounded-full',
                          daysLeft <= 7 ? 'bg-red-100 text-red-700' : 'bg-slate-100 text-slate-600'
                        )}>
                          {daysLeft <= 0 ? 'Expiring' : `${daysLeft}d left`}
                        </span>
                      )}
                    </div>

                    {/* Tags */}
                    {memory.tags && memory.tags.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-2">
                        {memory.tags.slice(0, 5).map((tag, i) => (
                          <span key={i} className="text-xs px-2 py-0.5 bg-slate-100 text-slate-600 rounded">
                            {tag}
                          </span>
                        ))}
                        {memory.tags.length > 5 && (
                          <span className="text-xs text-slate-400">+{memory.tags.length - 5} more</span>
                        )}
                      </div>
                    )}
                  </div>
                  
                  {/* Actions */}
                  <div className="flex items-center gap-1 shrink-0">
                    <button
                      onClick={() => handlePin(memory.id, memory.pinned)}
                      className={cn(
                        'p-1.5 rounded-lg transition-colors',
                        memory.pinned 
                          ? 'text-amber-600 bg-amber-50 hover:bg-amber-100' 
                          : 'text-slate-400 hover:bg-slate-100 hover:text-slate-600'
                      )}
                      title={memory.pinned ? 'Unpin' : 'Pin'}
                    >
                      {memory.pinned ? <PinOff className="w-4 h-4" /> : <Pin className="w-4 h-4" />}
                    </button>
                    <button
                      onClick={() => handleDelete(memory.id)}
                      className="p-1.5 text-slate-400 hover:bg-red-50 hover:text-red-600 rounded-lg transition-colors"
                      title="Delete"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => setExpandedId(isExpanded ? null : memory.id)}
                      className="p-1.5 text-slate-400 hover:bg-slate-100 rounded-lg transition-colors"
                    >
                      {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                    </button>
                  </div>
                </div>
                
                {/* Expanded Content */}
                {isExpanded && (
                  <div className="mt-3 ml-11 p-3 bg-slate-50 rounded-lg">
                    <p className="text-sm text-slate-700 whitespace-pre-wrap">
                      {memory.answer}
                    </p>
                    {memory.user_name && (
                      <p className="text-xs text-slate-500 mt-2 flex items-center gap-1">
                        <Users className="w-3 h-3" />
                        Saved by {memory.user_name}
                      </p>
                    )}
                  </div>
                )}
              </div>
            )
          })
        )}
      </div>

      {/* Footer with count */}
      {filteredMemories.length > 0 && (
        <div className="p-3 border-t border-slate-100 text-xs text-slate-500 text-center">
          Showing {filteredMemories.length} of {total} memories
        </div>
      )}
    </div>
  )
}

export default MemoryLog
