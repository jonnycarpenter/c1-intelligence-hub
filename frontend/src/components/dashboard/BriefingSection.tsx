'use client'

import React from 'react'
import { TrendingUp, AlertCircle, CheckCircle2, Zap } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Badge } from '@/components/ui'

export interface BriefingData {
    id: string
    category: string
    headline: string
    summary: string
    key_insights: string[]
    trend_signal: 'emerging' | 'accelerating' | 'stable' | 'declining' | 'mixed'
    attention_flag: 'high' | 'medium' | 'low'
    attention_reason: string | null
    article_ids: string[]
    period_start: string
    period_end: string
    generated_at: string
}

interface BriefingItemProps {
    briefing: BriefingData
}

const BriefingItem = ({ briefing }: BriefingItemProps) => {
    const getTrendIcon = (signal: string) => {
        switch (signal) {
            case 'accelerating': return <TrendingUp className="text-emerald-500" size={16} />
            case 'declining': return <TrendingUp className="text-rose-500 rotate-180" size={16} />
            case 'mixed': return <Zap className="text-emerald-500" size={16} />
            default: return <CheckCircle2 className="text-slate-400" size={16} />
        }
    }

    return (
        <div className={cn(
            "bg-white border rounded-xl overflow-hidden shadow-sm hover:shadow-md transition-all duration-200",
            briefing.attention_flag === 'high' ? "border-rose-200 ring-1 ring-rose-50" : "border-slate-200"
        )}>
            {briefing.attention_flag === 'high' && (
                <div className="bg-rose-500 h-1 w-full" />
            )}

            <div className="p-5">
                <div className="flex items-center justify-between mb-4">
                    <Badge variant="default" className="bg-slate-100 text-slate-700 capitalize">
                        {briefing.category.replace('_', ' ')}
                    </Badge>
                    <div className="flex items-center gap-2">
                        {getTrendIcon(briefing.trend_signal)}
                        <span className="text-[10px] uppercase tracking-wider font-bold text-slate-400">
                            {briefing.trend_signal}
                        </span>
                    </div>
                </div>

                <h3 className="text-lg font-bold text-slate-900 mb-2 leading-tight">
                    {briefing.headline}
                </h3>

                <p className="text-sm text-slate-600 mb-4 leading-relaxed">
                    {briefing.summary}
                </p>

                <div className="space-y-2 mb-4">
                    {briefing.key_insights.map((insight, idx) => (
                        <div key={idx} className="flex gap-2 items-start text-sm">
                            <div className="mt-1.5 w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0" />
                            <span className="text-slate-700 font-medium leading-normal">{insight}</span>
                        </div>
                    ))}
                </div>

                {briefing.attention_flag === 'high' && briefing.attention_reason && (
                    <div className="mt-4 p-3 bg-rose-50 rounded-lg border border-rose-100 flex gap-3">
                        <AlertCircle size={18} className="text-rose-500 shrink-0 mt-0.5" />
                        <div className="text-xs text-rose-800">
                            <span className="font-bold uppercase tracking-tighter mr-1">Attention Required:</span>
                            {briefing.attention_reason}
                        </div>
                    </div>
                )}
            </div>
        </div>
    )
}

interface BriefingSectionProps {
    briefings: BriefingData[]
    isLoading?: boolean
}

export default function BriefingSection({ briefings, isLoading }: BriefingSectionProps) {
    if (isLoading) {
        return (
            <div className="grid grid-cols-1 gap-6 animate-pulse">
                {[1, 2, 3].map(i => (
                    <div key={i} className="h-64 bg-slate-50 border border-slate-200 rounded-xl" />
                ))}
            </div>
        )
    }

    if (!briefings || briefings.length === 0) {
        return (
            <div className="text-center py-20 bg-slate-50 rounded-xl border border-dashed border-slate-300">
                <div className="text-4xl mb-4">📫</div>
                <h3 className="text-lg font-semibold text-slate-900">No active briefings</h3>
                <p className="text-sm text-slate-500 mt-1">Check back later for your 30-day intelligence summary</p>
            </div>
        )
    }

    return (
        <div className="space-y-8">
            <div className="flex items-center justify-between">
                <h2 className="text-2xl font-extrabold text-slate-900 flex items-center gap-3">
                    <span className="bg-emerald-100 text-emerald-600 p-2 rounded-lg">
                        <Zap size={24} fill="currentColor" />
                    </span>
                    Need to Know
                </h2>
                <span className="text-xs text-slate-400 font-medium">
                    30-DAY EXECUTIVE SUMMARY
                </span>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {briefings.map(briefing => (
                    <BriefingItem key={briefing.id} briefing={briefing} />
                ))}
            </div>
        </div>
    )
}
