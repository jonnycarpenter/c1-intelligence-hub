'use client'

import { ExternalLink, Zap } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { DigestItem, Priority } from '@/types'

const priorityConfig: Record<Priority, { label: string; color: string; bg: string }> = {
    critical: { label: 'CRITICAL', color: 'text-red-600', bg: 'bg-red-50 border-red-200' },
    high: { label: 'HIGH PRIORITY', color: 'text-emerald-600', bg: 'bg-emerald-50 border-emerald-200' },
    medium: { label: 'MEDIUM', color: 'text-blue-600', bg: 'bg-blue-50 border-blue-200' },
    low: { label: 'LOW', color: 'text-slate-500', bg: 'bg-slate-50 border-slate-200' },
}

interface HeroCardProps {
    item: DigestItem
}

export default function HeroCard({ item }: HeroCardProps) {
    const sources = item.sources || []
    // Normalize priority to lowercase for consistent lookup (backend sends Title Case)
    const normalizedPriority = item.priority?.toLowerCase() as Priority
    const priorityCfg = priorityConfig[normalizedPriority] || priorityConfig.medium

    return (
        <div className={cn(
            "relative bg-white rounded-xl shadow-lg border-2 border-emerald-200/60",
            "ring-1 ring-emerald-100/50 transition-all duration-200 hover:shadow-xl",
            "overflow-hidden"
        )}>
            {/* Hero Accent Bar */}
            <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-emerald-500 via-emerald-400 to-emerald-500" />

            <div className="p-5 pt-4 space-y-3">
                {/* Header: Priority Badge + Lightning Icon */}
                <div className="flex items-center justify-between">
                    <span className={cn(
                        "inline-flex items-center px-2.5 py-1 rounded text-[10px] font-bold uppercase tracking-wider border",
                        priorityCfg.bg, priorityCfg.color
                    )}>
                        {priorityCfg.label}
                    </span>
                    <div className="flex items-center gap-1.5 text-amber-500">
                        <Zap size={14} fill="currentColor" />
                        <span className="text-[10px] font-bold uppercase tracking-wider">Breaking</span>
                    </div>
                </div>

                {/* Title */}
                <h3 className="text-lg font-bold text-slate-900 leading-snug">
                    {item.title}
                </h3>

                {/* Full Summary (no line-clamp) */}
                <p className="text-sm text-slate-600 leading-relaxed">
                    {item.summary}
                </p>

                {/* Entity Pills */}
                {item.entities && (
                    <div className="flex flex-wrap gap-1.5 pt-1">
                        {[
                            ...(item.entities.companies || []).slice(0, 3).map(e => ({ t: 'co', v: e })),
                            ...(item.entities.topics || []).slice(0, 2).map(e => ({ t: 'tp', v: e })),
                        ].map((ent, idx) => (
                            <span
                                key={idx}
                                className={cn(
                                    "inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium border",
                                    ent.t === 'co'
                                        ? "bg-slate-50 text-slate-600 border-slate-200"
                                        : "bg-emerald-50/50 text-emerald-700 border-emerald-100"
                                )}
                            >
                                {ent.v}
                            </span>
                        ))}
                    </div>
                )}

                {/* Footer: Meta & Source */}
                <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-xs text-slate-400">
                    <div className="flex items-center gap-2">
                        <span className="font-semibold text-slate-500 uppercase tracking-wider text-[10px]">
                            {item.category.replace('_', ' ')}
                        </span>
                        <span>•</span>
                        <span>{item.timestamp}</span>
                    </div>

                    {sources.length > 0 && (
                        <a
                            href={sources[0].url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 hover:text-emerald-600 transition-colors"
                        >
                            <ExternalLink size={12} />
                            <span className="truncate max-w-[120px]">
                                {sources[0].name || 'Source'}
                            </span>
                        </a>
                    )}
                </div>
            </div>
        </div>
    )
}
