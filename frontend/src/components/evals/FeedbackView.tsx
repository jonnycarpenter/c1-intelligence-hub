'use client'

import { useState, useMemo } from 'react'
import {
  MessageSquare, ThumbsUp, ThumbsDown, Star, ChevronDown,
  ChevronRight, Search, Filter, BarChart3,
} from 'lucide-react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip as RechartsTooltip,
  ResponsiveContainer, CartesianGrid, Cell, PieChart, Pie,
  Legend,
} from 'recharts'
import { cn } from '@/lib/utils'

// ── Types ──

interface FeedbackComment {
  id: string
  report_id: string
  query: string
  rating: number
  helpful: boolean | null
  comment: string
  created_at: string
  user_id?: string
}

interface FeedbackOverview {
  total_feedback: number
  avg_rating: number
  helpful_rate: number
  total_ratings: number
  total_comments: number
  rating_distribution: Record<string, number>
}

// ── Helpers ──

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

function StarRating({ rating }: { rating: number }) {
  return (
    <div className="flex items-center gap-0.5">
      {[1, 2, 3, 4, 5].map(i => (
        <Star
          key={i}
          size={12}
          className={cn(
            'transition-colors',
            i <= rating ? 'fill-amber-400 text-amber-400' : 'text-slate-200'
          )}
        />
      ))}
    </div>
  )
}

const SENTIMENT_COLORS = {
  positive: '#10b981',
  neutral: '#94a3b8',
  negative: '#ef4444',
}

const RATING_COLORS: Record<number, string> = {
  5: '#10b981',
  4: '#34d399',
  3: '#fbbf24',
  2: '#f97316',
  1: '#ef4444',
}

// ── Rating Distribution Chart ──

function RatingDistributionChart({ distribution }: { distribution: Record<string, number> }) {
  const data = [5, 4, 3, 2, 1].map(r => ({
    rating: `${r} ★`,
    count: distribution[String(r)] || 0,
    fill: RATING_COLORS[r],
  }))

  const total = data.reduce((s, d) => s + d.count, 0)
  if (total === 0) {
    return (
      <div className="text-center py-6 border-2 border-dashed border-slate-200 rounded-xl">
        <BarChart3 size={18} className="text-slate-400 mx-auto mb-2" />
        <p className="text-sm text-slate-500">No ratings yet</p>
      </div>
    )
  }

  return (
    <ResponsiveContainer width="100%" height={180}>
      <BarChart data={data} layout="vertical" margin={{ left: 10, right: 20 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" horizontal={false} />
        <XAxis type="number" tick={{ fontSize: 10 }} />
        <YAxis type="category" dataKey="rating" tick={{ fontSize: 11 }} width={36} />
        <RechartsTooltip
          contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e2e8f0' }}
          formatter={(value: any) => [`${value} ratings`, '']}
        />
        <Bar dataKey="count" radius={[0, 4, 4, 0]} barSize={16}>
          {data.map((entry, i) => (
            <Cell key={i} fill={entry.fill} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

// ── Sentiment Pie Chart ──

function SentimentChart({ comments }: { comments: FeedbackComment[] }) {
  const sentiment = useMemo(() => {
    let positive = 0, neutral = 0, negative = 0
    comments.forEach(c => {
      if (c.helpful === true) positive++
      else if (c.helpful === false) negative++
      else if (c.rating >= 4) positive++
      else if (c.rating <= 2) negative++
      else neutral++
    })
    return [
      { name: 'Positive', value: positive, fill: SENTIMENT_COLORS.positive },
      { name: 'Neutral', value: neutral, fill: SENTIMENT_COLORS.neutral },
      { name: 'Negative', value: negative, fill: SENTIMENT_COLORS.negative },
    ].filter(d => d.value > 0)
  }, [comments])

  if (sentiment.length === 0) {
    return (
      <div className="text-center py-6 border-2 border-dashed border-slate-200 rounded-xl">
        <MessageSquare size={18} className="text-slate-400 mx-auto mb-2" />
        <p className="text-sm text-slate-500">No feedback yet</p>
      </div>
    )
  }

  return (
    <ResponsiveContainer width="100%" height={180}>
      <PieChart>
        <Pie
          data={sentiment}
          dataKey="value"
          nameKey="name"
          cx="50%"
          cy="50%"
          innerRadius={40}
          outerRadius={65}
          paddingAngle={3}
          strokeWidth={0}
        >
          {sentiment.map((entry, i) => (
            <Cell key={i} fill={entry.fill} />
          ))}
        </Pie>
        <Legend
          verticalAlign="bottom"
          height={30}
          formatter={(value: string) => <span className="text-xs text-slate-600">{value}</span>}
        />
        <RechartsTooltip
          contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e2e8f0' }}
          formatter={(value: any, name: any) => [value, name]}
        />
      </PieChart>
    </ResponsiveContainer>
  )
}

// ── Feedback List Item ──

function FeedbackItem({ item }: { item: FeedbackComment }) {
  const [expanded, setExpanded] = useState(false)
  return (
    <div
      className="border border-slate-100 rounded-lg p-4 hover:border-slate-200 transition-colors cursor-pointer"
      onClick={() => setExpanded(!expanded)}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <StarRating rating={item.rating} />
            {item.helpful !== null && (
              <span className={cn(
                'text-xs px-1.5 py-0.5 rounded-full font-medium',
                item.helpful ? 'text-emerald-600 bg-emerald-50' : 'text-red-600 bg-red-50'
              )}>
                {item.helpful ? <ThumbsUp size={10} className="inline mr-0.5" /> : <ThumbsDown size={10} className="inline mr-0.5" />}
                {item.helpful ? 'Helpful' : 'Not helpful'}
              </span>
            )}
          </div>
          <p className="text-sm text-slate-700 truncate">{item.query || 'Untitled report'}</p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className="text-xs text-slate-400">{timeAgo(item.created_at)}</span>
          {item.comment && (
            expanded ? <ChevronDown size={14} className="text-slate-400" /> : <ChevronRight size={14} className="text-slate-400" />
          )}
        </div>
      </div>
      {expanded && item.comment && (
        <div className="mt-3 pt-3 border-t border-slate-100">
          <p className="text-sm text-slate-600 leading-relaxed">{item.comment}</p>
        </div>
      )}
    </div>
  )
}

// ── Main Feedback View ──

export default function FeedbackView({
  overview,
  comments,
}: {
  overview: FeedbackOverview
  comments: FeedbackComment[]
}) {
  const [searchTerm, setSearchTerm] = useState('')
  const [filterRating, setFilterRating] = useState<number | null>(null)

  const filtered = useMemo(() => {
    let list = comments || []
    if (searchTerm) {
      const q = searchTerm.toLowerCase()
      list = list.filter(c =>
        c.query?.toLowerCase().includes(q) || c.comment?.toLowerCase().includes(q)
      )
    }
    if (filterRating !== null) {
      list = list.filter(c => c.rating === filterRating)
    }
    return list
  }, [comments, searchTerm, filterRating])

  return (
    <div className="space-y-6">
      {/* Stat Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl border border-slate-200 p-4">
          <p className="text-xs text-slate-500 mb-1">Total Feedback</p>
          <p className="text-2xl font-bold text-slate-800">{overview.total_feedback || 0}</p>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 p-4">
          <p className="text-xs text-slate-500 mb-1">Avg Rating</p>
          <div className="flex items-center gap-2">
            <p className="text-2xl font-bold text-slate-800">{overview.avg_rating || '—'}</p>
            <StarRating rating={Math.round(overview.avg_rating || 0)} />
          </div>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 p-4">
          <p className="text-xs text-slate-500 mb-1">Helpful Rate</p>
          <p className="text-2xl font-bold text-emerald-600">{overview.helpful_rate || 0}%</p>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 p-4">
          <p className="text-xs text-slate-500 mb-1">With Comments</p>
          <p className="text-2xl font-bold text-slate-800">{overview.total_comments || 0}</p>
        </div>
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <h3 className="text-sm font-semibold text-slate-700 mb-3">Rating Distribution</h3>
          <RatingDistributionChart distribution={overview.rating_distribution || {}} />
        </div>
        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <h3 className="text-sm font-semibold text-slate-700 mb-3">Sentiment Overview</h3>
          <SentimentChart comments={comments || []} />
        </div>
      </div>

      {/* Feedback List */}
      <div className="bg-white rounded-xl border border-slate-200">
        <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg flex items-center justify-center bg-blue-500">
              <MessageSquare size={14} className="text-white" />
            </div>
            <h3 className="font-semibold text-slate-800">All Feedback</h3>
            <span className="text-xs text-slate-400">{filtered.length} entries</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="relative">
              <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                placeholder="Search..."
                value={searchTerm}
                onChange={e => setSearchTerm(e.target.value)}
                className="pl-8 pr-3 py-1.5 text-xs border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400 w-48"
              />
            </div>
            <div className="relative">
              <Filter size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
              <select
                value={filterRating ?? ''}
                onChange={e => setFilterRating(e.target.value ? Number(e.target.value) : null)}
                className="pl-8 pr-6 py-1.5 text-xs border border-slate-200 rounded-lg appearance-none bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400"
              >
                <option value="">All ratings</option>
                <option value="5">5 stars</option>
                <option value="4">4 stars</option>
                <option value="3">3 stars</option>
                <option value="2">2 stars</option>
                <option value="1">1 star</option>
              </select>
            </div>
          </div>
        </div>
        <div className="p-4 space-y-2 max-h-[600px] overflow-y-auto">
          {filtered.length === 0 ? (
            <div className="text-center py-8">
              <MessageSquare size={20} className="text-slate-400 mx-auto mb-2" />
              <p className="text-sm text-slate-500">No feedback found</p>
              {(searchTerm || filterRating !== null) && (
                <button
                  onClick={() => { setSearchTerm(''); setFilterRating(null) }}
                  className="text-xs text-blue-500 mt-2 hover:underline"
                >
                  Clear filters
                </button>
              )}
            </div>
          ) : (
            filtered.map(item => <FeedbackItem key={item.id} item={item} />)
          )}
        </div>
      </div>
    </div>
  )
}
