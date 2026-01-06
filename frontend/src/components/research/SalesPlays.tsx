'use client'

import { useState } from 'react'
import { Target, ChevronDown, ChevronUp, Copy, Check } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { CategoryOutput } from '@/types'

interface SalesPlaysProps {
    categoryOutput: CategoryOutput
}

export function SalesPlays({ categoryOutput }: SalesPlaysProps) {
    const { sales_plays, industry_talking_points } = categoryOutput
    const [expandedPlay, setExpandedPlay] = useState<number | null>(0) // First play expanded by default
    const [copiedIndex, setCopiedIndex] = useState<number | null>(null)

    if (!sales_plays || sales_plays.length === 0) return null

    const handleCopy = (text: string, index: number) => {
        navigator.clipboard.writeText(text)
        setCopiedIndex(index)
        setTimeout(() => setCopiedIndex(null), 2000)
    }

    return (
        <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden shadow-sm">
            <div className="bg-gradient-to-r from-purple-500 to-pink-500 px-6 py-4 flex items-center gap-2">
                <Target size={20} className="text-white" />
                <h3 className="text-white font-semibold">Sales Plays</h3>
                <span className="ml-auto text-purple-100 text-sm">
                    {sales_plays.length} {sales_plays.length === 1 ? 'play' : 'plays'}
                </span>
            </div>
            
            <div className="p-6 space-y-4">
                {/* Sales Plays Accordion */}
                {sales_plays.map((play, idx) => {
                    const isExpanded = expandedPlay === idx
                    
                    return (
                        <div
                            key={idx}
                            className="border border-slate-200 rounded-xl overflow-hidden hover:border-purple-300 transition-colors"
                        >
                            {/* Play Header */}
                            <button
                                onClick={() => setExpandedPlay(isExpanded ? null : idx)}
                                className="w-full flex items-center justify-between px-4 py-3 bg-slate-50 hover:bg-slate-100 transition-colors"
                            >
                                <div className="flex items-center gap-3">
                                    <div className="w-8 h-8 rounded-full bg-purple-500 text-white flex items-center justify-center text-sm font-bold">
                                        {idx + 1}
                                    </div>
                                    <span className="font-semibold text-slate-800 text-left">
                                        {play.title}
                                    </span>
                                </div>
                                {isExpanded ? (
                                    <ChevronUp size={20} className="text-slate-400" />
                                ) : (
                                    <ChevronDown size={20} className="text-slate-400" />
                                )}
                            </button>

                            {/* Play Content */}
                            {isExpanded && (
                                <div className="p-4 space-y-4 bg-white">
                                    {/* Hook */}
                                    <div>
                                        <div className="flex items-center justify-between mb-2">
                                            <h5 className="text-sm font-semibold text-purple-700 uppercase tracking-wide">
                                                Hook
                                            </h5>
                                            <button
                                                onClick={() => handleCopy(play.hook, idx * 100)}
                                                className="text-xs text-slate-500 hover:text-purple-600 transition-colors flex items-center gap-1"
                                            >
                                                {copiedIndex === idx * 100 ? (
                                                    <>
                                                        <Check size={12} />
                                                        Copied
                                                    </>
                                                ) : (
                                                    <>
                                                        <Copy size={12} />
                                                        Copy
                                                    </>
                                                )}
                                            </button>
                                        </div>
                                        <div className="bg-purple-50 border-l-4 border-purple-500 p-3 rounded-r-lg">
                                            <p className="text-sm text-slate-700 leading-relaxed">
                                                {play.hook}
                                            </p>
                                        </div>
                                    </div>

                                    {/* Objection Handlers */}
                                    {play.objection_handlers && play.objection_handlers.length > 0 && (
                                        <div>
                                            <h5 className="text-sm font-semibold text-slate-700 mb-2">
                                                Objection Handlers
                                            </h5>
                                            <div className="space-y-2">
                                                {play.objection_handlers.map((handler, hIdx) => (
                                                    <div
                                                        key={hIdx}
                                                        className="flex items-start gap-2 p-2 bg-slate-50 rounded-lg text-sm"
                                                    >
                                                        <div className="w-5 h-5 rounded-full bg-slate-300 text-white flex items-center justify-center text-xs font-bold shrink-0 mt-0.5">
                                                            {hIdx + 1}
                                                        </div>
                                                        <p className="text-slate-600 leading-relaxed">
                                                            {handler}
                                                        </p>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>
                    )
                })}

                {/* Industry Talking Points */}
                {industry_talking_points && industry_talking_points.length > 0 && (
                    <div className="mt-6 pt-6 border-t border-slate-200">
                        <h4 className="text-sm font-semibold text-slate-700 mb-3">
                            📌 Industry Talking Points
                        </h4>
                        <div className="space-y-2">
                            {industry_talking_points.map((point, idx) => (
                                <div key={idx} className="flex items-start gap-2">
                                    <div className="w-1.5 h-1.5 rounded-full bg-purple-500 shrink-0 mt-2" />
                                    <p className="text-sm text-slate-600 leading-relaxed">{point}</p>
                                </div>
                            ))}
                        </div>
                    </div>
                )}
            </div>
        </div>
    )
}

export default SalesPlays
