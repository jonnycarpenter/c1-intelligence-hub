'use client'

import React, { useState } from 'react'
import {
  ChevronDown,
  ChevronUp,
  Mic,
  ExternalLink,
  User,
} from 'lucide-react'
import { Badge } from '@/components/ui'
import { cn } from '@/lib/utils'
import type { ExpertFeedItem } from '@/types'

function formatTheme(theme: string): string {
  return theme
    .split('_')
    .map(w => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')
}

function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60))
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

  if (diffHours < 1) return 'Just now'
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 7) return `${diffDays}d ago`
  return date.toLocaleDateString()
}

const roleConfig: Record<string, { label: string; color: string }> = {
  host: { label: 'Host', color: 'bg-violet-50 text-violet-700 border-violet-200' },
  guest: { label: 'Guest', color: 'bg-blue-50 text-blue-700 border-blue-200' },
  unknown: { label: 'Speaker', color: 'bg-slate-50 text-slate-600 border-slate-200' },
}

interface ExpertFeedCardProps {
  item: ExpertFeedItem
}

export default function ExpertFeedCard({ item }: ExpertFeedCardProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  const isLong = item.quote_text.length > 200
  const role = item.speaker_role ? roleConfig[item.speaker_role] || roleConfig.unknown : null

  return (
    <div className="bg-white rounded-xl border border-slate-200 border-l-4 border-l-violet-500 shadow-sm hover:shadow-md transition-shadow">
      <div className="p-4 space-y-3">
        {/* Header: podcast name + date */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-semibold rounded bg-violet-50 text-violet-700 border border-violet-200">
              <Mic size={11} />
              Podcast
            </span>
            <span className="text-sm font-medium text-slate-700">{item.podcast_name}</span>
          </div>
          <div className="flex items-center gap-2">
            {item.published_at && (
              <span className="text-xs text-slate-400">{formatRelativeTime(item.published_at)}</span>
            )}
            {item.relevance_score > 0 && (
              <span className={cn(
                'text-xs px-1.5 py-0.5 rounded',
                item.relevance_score >= 0.7 ? 'bg-emerald-50 text-emerald-600' :
                item.relevance_score >= 0.4 ? 'bg-blue-50 text-blue-600' : 'bg-slate-50 text-slate-500'
              )}>
                {Math.round(item.relevance_score * 100)}%
              </span>
            )}
          </div>
        </div>

        {/* Quote text */}
        <blockquote className={cn(
          'text-sm text-slate-700 italic border-l-2 border-violet-200 pl-3',
          !isExpanded && isLong && 'line-clamp-3'
        )}>
          &ldquo;{item.quote_text}&rdquo;
        </blockquote>
        {isLong && (
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="text-xs text-violet-600 hover:text-violet-700 flex items-center gap-0.5"
          >
            {isExpanded ? <><ChevronUp size={12} /> Show less</> : <><ChevronDown size={12} /> Read more</>}
          </button>
        )}

        {/* Context */}
        {item.context_summary && (
          <p className="text-xs text-slate-500">{item.context_summary}</p>
        )}

        {/* Speaker attribution */}
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 text-xs text-slate-600">
            <User size={12} className="text-slate-400" />
            <span className="font-medium">{item.speaker_name}</span>
            {role && (
              <span className={cn('px-1.5 py-0.5 rounded-full border text-xs', role.color)}>
                {role.label}
              </span>
            )}
          </div>
          {item.speaker_title && (
            <span className="text-xs text-slate-400">{item.speaker_title}</span>
          )}
          {item.speaker_company && (
            <span className="text-xs text-slate-400">at {item.speaker_company}</span>
          )}
        </div>

        {/* Episode link */}
        {item.episode_title && (
          <div className="flex items-center gap-1.5 text-xs">
            {item.episode_url ? (
              <a
                href={item.episode_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-violet-600 hover:text-violet-700 hover:underline flex items-center gap-1 truncate max-w-[300px]"
              >
                {item.episode_title}
                <ExternalLink size={10} />
              </a>
            ) : (
              <span className="text-slate-500 truncate max-w-[300px]">{item.episode_title}</span>
            )}
          </div>
        )}

        {/* Theme pills */}
        {item.themes.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {item.themes.slice(0, 5).map((theme, i) => (
              <span
                key={i}
                className="px-2 py-0.5 text-xs rounded-full bg-slate-100 text-slate-600 hover:bg-slate-200 cursor-default"
              >
                {formatTheme(theme)}
              </span>
            ))}
            {item.themes.length > 5 && (
              <span className="px-2 py-0.5 text-xs text-slate-400">+{item.themes.length - 5}</span>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
