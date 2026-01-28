'use client'

import { useState, useEffect } from 'react'
import { Sparkles, Zap, Loader2, Clock, AlertCircle } from 'lucide-react'
import { api } from '@/lib/api'

interface BulletinBoardData {
    bullets: string[]
    total_priority_items: number
    categories_covered: string[]
    time_window_hours: number
    extended_to_7_days: boolean
    generated_at: string
}

interface BulletinBoardProps {
    className?: string
}

export default function BulletinBoard({ className }: BulletinBoardProps) {
    const [data, setData] = useState<BulletinBoardData | null>(null)
    const [isLoading, setIsLoading] = useState(true)
    const [error, setError] = useState<Error | null>(null)

    useEffect(() => {
        let isMounted = true

        async function fetchBulletin() {
            try {
                setIsLoading(true)
                const result = await api.getBulletinBoard()
                if (isMounted) {
                    setData(result)
                    setError(null)
                }
            } catch (err) {
                if (isMounted) {
                    setError(err instanceof Error ? err : new Error('Failed to load bulletin'))
                }
            } finally {
                if (isMounted) {
                    setIsLoading(false)
                }
            }
        }

        fetchBulletin()

        return () => {
            isMounted = false
        }
    }, [])

    // Loading state
    if (isLoading) {
        return (
            <div className={`bg-gradient-to-r from-teal-50 to-emerald-50 rounded-xl p-4 border border-teal-200/50 ${className || ''}`}>
                <div className="flex items-center gap-2 text-teal-600">
                    <Loader2 size={14} className="animate-spin" />
                    <span className="text-xs font-medium">Loading priority insights...</span>
                </div>
            </div>
        )
    }

    // Error state - show fallback
    if (error || !data) {
        return (
            <div className={`bg-gradient-to-r from-slate-50 to-slate-100 rounded-xl p-4 border border-slate-200 ${className || ''}`}>
                <div className="flex items-center gap-2 text-slate-500">
                    <AlertCircle size={14} />
                    <span className="text-sm">Explore the industry themes below for the latest intelligence.</span>
                </div>
            </div>
        )
    }

    // No priority items
    if (data.total_priority_items === 0) {
        return (
            <div className={`bg-gradient-to-r from-emerald-50 to-teal-50 rounded-xl p-4 border border-emerald-200/50 ${className || ''}`}>
                <div className="flex items-center gap-2 text-emerald-600">
                    <Sparkles size={14} />
                    <span className="text-sm font-medium">All clear – no urgent items in the last few days.</span>
                </div>
            </div>
        )
    }

    return (
        <div className={`bg-gradient-to-r from-teal-50 via-white to-emerald-50 rounded-xl overflow-hidden border border-teal-200/50 shadow-sm ${className || ''}`}>
            {/* Header */}
            <div className="px-4 py-3 border-b border-teal-100 bg-gradient-to-r from-teal-50/80 to-emerald-50/80">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <div className="p-1.5 bg-gradient-to-br from-teal-500/20 to-emerald-500/20 rounded-lg">
                            <Zap size={14} className="text-teal-600" />
                        </div>
                        <h3 className="text-xs font-bold text-teal-800 uppercase tracking-widest">
                            Priority Spotlight
                        </h3>
                    </div>
                    <div className="flex items-center gap-1.5 text-slate-400">
                        <Clock size={10} />
                        <span className="text-[10px] font-medium">
                            {data.extended_to_7_days ? 'Last 7 days' : 'Last 72 hours'}
                        </span>
                    </div>
                </div>
            </div>

            {/* Bullets */}
            <div className="p-4 space-y-3">
                {data.bullets.map((bullet, idx) => (
                    <div
                        key={idx}
                        className="flex items-start gap-3 group"
                    >
                        <span className={`flex items-center justify-center w-5 h-5 rounded-full text-[10px] font-bold shrink-0 mt-0.5 ${idx === 0
                            ? "bg-gradient-to-br from-teal-500 to-emerald-600 text-white shadow-md shadow-teal-500/20"
                            : "bg-teal-100 text-teal-600"
                            }`}>
                            {idx + 1}
                        </span>
                        <p className={`text-sm leading-relaxed ${idx === 0 ? "text-slate-800 font-medium" : "text-slate-600"
                            }`}>
                            {bullet}
                        </p>
                    </div>
                ))}
            </div>

            {/* Footer - Total count */}
            {data.total_priority_items > 0 && (
                <div className="px-4 py-2.5 border-t border-teal-100 bg-gradient-to-r from-teal-50/50 to-emerald-50/50">
                    <p className="text-[10px] text-slate-400 font-medium">
                        {data.total_priority_items} priority item{data.total_priority_items !== 1 ? 's' : ''} across{' '}
                        {data.categories_covered.length} theme{data.categories_covered.length !== 1 ? 's' : ''}
                    </p>
                </div>
            )}
        </div>
    )
}
