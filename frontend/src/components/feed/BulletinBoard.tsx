'use client'

import { useState, useEffect } from 'react'
import { Sparkles, Zap, Loader2, Clock, AlertCircle, ChevronDown } from 'lucide-react'
import { api } from '@/lib/api'
import TypewriterEffect from '@/components/ui/typewriter'

interface BulletinBoardData {
    market_pulse: string
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
            <div className={`bg-gradient-to-r from-teal-50 to-emerald-50 rounded-xl p-6 border border-teal-200/50 ${className || ''}`}>
                <div className="flex flex-col gap-2">
                    <div className="flex items-center gap-2 text-teal-600 mb-2">
                        <Loader2 size={16} className="animate-spin" />
                        <span className="text-xs font-bold uppercase tracking-widest">Generating Market Pulse...</span>
                    </div>
                    <div className="h-6 w-3/4 bg-teal-100/50 rounded animate-pulse" />
                </div>
            </div>
        )
    }

    // Error state - show fallback
    if (error || !data) {
        return null // Hide entirely if error
    }

    // No priority items
    if (data.total_priority_items === 0) {
        return (
            <div className={`bg-slate-50 rounded-xl p-4 border border-slate-200 ${className || ''}`}>
                <div className="flex items-center gap-3 text-slate-500">
                    <div className="p-2 bg-slate-100 rounded-full">
                        <Sparkles size={16} />
                    </div>
                    <div>
                        <span className="text-xs font-bold uppercase tracking-widest block text-slate-400 mb-0.5">Market Pulse</span>
                        <span className="text-sm font-medium">No critical signals detected. Monitoring active channels.</span>
                    </div>
                </div>
            </div>
        )
    }

    return (
        <div className={`relative overflow-hidden rounded-xl border border-teal-200/50 shadow-sm bg-gradient-to-r from-teal-50/50 via-white to-emerald-50/50 ${className || ''}`}>
            {/* Background Decorative Elements */}
            <div className="absolute top-0 right-0 -mt-4 -mr-4 w-24 h-24 bg-teal-100/30 rounded-full blur-2xl pointer-events-none" />

            <div className="flex flex-col md:flex-row items-stretch">
                {/* Left Side: Pulse Indicator & Context */}
                <div className="flex flex-col justify-center p-5 md:w-64 border-b md:border-b-0 md:border-r border-teal-100/50 bg-white/50">
                    <div className="flex items-center gap-2 mb-2">
                        <div className="relative flex h-2.5 w-2.5">
                            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-teal-400 opacity-75"></span>
                            <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-teal-500"></span>
                        </div>
                        <h3 className="text-xs font-bold text-teal-800 uppercase tracking-widest">
                            Market Pulse
                        </h3>
                    </div>
                    <div className="flex items-center gap-2 text-slate-400">
                        <Clock size={12} />
                        <span className="text-[10px] font-medium uppercase tracking-wide">
                            {data.extended_to_7_days ? 'Last 7 days' : 'Last 72 hours'}
                        </span>
                    </div>
                    <div className="mt-3 text-[10px] font-medium text-slate-500 bg-slate-100/50 self-start px-2 py-1 rounded-full border border-slate-100">
                        Analyzing {data.total_priority_items} critical signals
                    </div>
                </div>

                {/* Right Side: The Insight */}
                <div className="flex-1 p-5 flex items-center bg-white/30">
                    <p className="text-lg md:text-xl font-medium text-slate-700 leading-relaxed font-serif italic text-balance min-h-[3.5rem]">
                        "
                        <TypewriterEffect
                            text={data.market_pulse}
                            speed={25}
                            startDelay={300}
                            cursorClassName="bg-teal-500 w-[3px]"
                        />
                        "
                    </p>
                </div>
            </div>
        </div>
    )
}
