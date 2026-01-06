'use client'

import { MapPin, TrendingUp, TrendingDown } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { CategoryOutput } from '@/types'

interface TerritoryInsightsProps {
    categoryOutput: CategoryOutput
}

export function TerritoryInsights({ categoryOutput }: TerritoryInsightsProps) {
    const { territory_insights } = categoryOutput

    if (!territory_insights) return null

    const eastScore = territory_insights.east_relevance || 0
    const westScore = territory_insights.west_relevance || 0
    const maxScore = Math.max(eastScore, westScore)

    return (
        <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden shadow-sm">
            <div className="bg-gradient-to-r from-blue-500 to-cyan-500 px-6 py-4 flex items-center gap-2">
                <MapPin size={20} className="text-white" />
                <h3 className="text-white font-semibold">Territory Insights</h3>
            </div>
            
            <div className="p-6 space-y-6">
                {/* Territory Scores */}
                <div className="grid grid-cols-2 gap-4">
                    {/* East Territory */}
                    <div className={cn(
                        "relative rounded-xl border-2 p-4 transition-all",
                        eastScore === maxScore 
                            ? "border-blue-500 bg-blue-50" 
                            : "border-slate-200 bg-slate-50"
                    )}>
                        {eastScore === maxScore && (
                            <div className="absolute -top-2 -right-2 bg-blue-500 text-white text-xs font-bold px-2 py-0.5 rounded-full">
                                Top Match
                            </div>
                        )}
                        <div className="flex items-center gap-2 mb-3">
                            <div className="w-3 h-3 rounded-full bg-blue-500" />
                            <span className="font-semibold text-slate-800">East Territory</span>
                        </div>
                        <div className="flex items-end gap-2 mb-2">
                            <span className="text-3xl font-bold text-blue-600">
                                {Math.round(eastScore * 100)}%
                            </span>
                            <span className="text-sm text-slate-500 mb-1">relevance</span>
                        </div>
                        {/* Progress bar */}
                        <div className="h-2 bg-slate-200 rounded-full overflow-hidden mb-3">
                            <div 
                                className="h-full bg-blue-500 transition-all duration-500"
                                style={{ width: `${eastScore * 100}%` }}
                            />
                        </div>
                        {territory_insights.east_summary && (
                            <p className="text-xs text-slate-600 leading-relaxed">
                                {territory_insights.east_summary}
                            </p>
                        )}
                    </div>

                    {/* West Territory */}
                    <div className={cn(
                        "relative rounded-xl border-2 p-4 transition-all",
                        westScore === maxScore 
                            ? "border-cyan-500 bg-cyan-50" 
                            : "border-slate-200 bg-slate-50"
                    )}>
                        {westScore === maxScore && (
                            <div className="absolute -top-2 -right-2 bg-cyan-500 text-white text-xs font-bold px-2 py-0.5 rounded-full">
                                Top Match
                            </div>
                        )}
                        <div className="flex items-center gap-2 mb-3">
                            <div className="w-3 h-3 rounded-full bg-cyan-500" />
                            <span className="font-semibold text-slate-800">West Territory</span>
                        </div>
                        <div className="flex items-end gap-2 mb-2">
                            <span className="text-3xl font-bold text-cyan-600">
                                {Math.round(westScore * 100)}%
                            </span>
                            <span className="text-sm text-slate-500 mb-1">relevance</span>
                        </div>
                        {/* Progress bar */}
                        <div className="h-2 bg-slate-200 rounded-full overflow-hidden mb-3">
                            <div 
                                className="h-full bg-cyan-500 transition-all duration-500"
                                style={{ width: `${westScore * 100}%` }}
                            />
                        </div>
                        {territory_insights.west_summary && (
                            <p className="text-xs text-slate-600 leading-relaxed">
                                {territory_insights.west_summary}
                            </p>
                        )}
                    </div>
                </div>

                {/* Key Industries */}
                <div className="bg-slate-50 rounded-xl p-4 border border-slate-200">
                    <h4 className="text-sm font-semibold text-slate-700 mb-2">Primary Focus Areas</h4>
                    <div className="flex flex-wrap gap-2">
                        {eastScore >= westScore ? (
                            <>
                                <span className="inline-flex items-center gap-1 px-3 py-1 bg-blue-100 text-blue-700 rounded-full text-xs font-medium">
                                    🚁 Aerospace
                                </span>
                                <span className="inline-flex items-center gap-1 px-3 py-1 bg-blue-100 text-blue-700 rounded-full text-xs font-medium">
                                    💨 Wind Energy
                                </span>
                                <span className="inline-flex items-center gap-1 px-3 py-1 bg-blue-100 text-blue-700 rounded-full text-xs font-medium">
                                    🚗 Automotive
                                </span>
                                <span className="inline-flex items-center gap-1 px-3 py-1 bg-blue-100 text-blue-700 rounded-full text-xs font-medium">
                                    🛡️ Defense
                                </span>
                            </>
                        ) : (
                            <>
                                <span className="inline-flex items-center gap-1 px-3 py-1 bg-cyan-100 text-cyan-700 rounded-full text-xs font-medium">
                                    ⚓ Marine
                                </span>
                                <span className="inline-flex items-center gap-1 px-3 py-1 bg-cyan-100 text-cyan-700 rounded-full text-xs font-medium">
                                    🚐 RVs
                                </span>
                                <span className="inline-flex items-center gap-1 px-3 py-1 bg-cyan-100 text-cyan-700 rounded-full text-xs font-medium">
                                    🛁 Spas
                                </span>
                            </>
                        )}
                    </div>
                </div>
            </div>
        </div>
    )
}

export default TerritoryInsights
