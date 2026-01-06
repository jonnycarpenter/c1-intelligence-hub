'use client'

import { useState } from 'react'
import { ShieldCheck, ShieldAlert, AlertCircle, ChevronDown, ChevronUp, AlertTriangle } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { ValidationOutput } from '@/types'

interface ValidationBadgeProps {
    validationOutput: ValidationOutput
}

export function ValidationBadge({ validationOutput }: ValidationBadgeProps) {
    const [isExpanded, setIsExpanded] = useState(false)

    const {
        validation_passed,
        citation_issues = [],
        unsubstantiated_claims = [],
        confidence_adjustments = [],
        warnings = []
    } = validationOutput

    const totalIssues = citation_issues.length + unsubstantiated_claims.length + warnings.length
    const hasCriticalIssues = !validation_passed || unsubstantiated_claims.length > 0

    return (
        <div className={cn(
            "rounded-2xl border-2 overflow-hidden shadow-sm transition-all",
            validation_passed 
                ? "border-emerald-300 bg-emerald-50/50" 
                : "border-amber-300 bg-amber-50/50"
        )}>
            {/* Header Badge */}
            <button
                onClick={() => setIsExpanded(!isExpanded)}
                className={cn(
                    "w-full px-6 py-4 flex items-center justify-between transition-colors",
                    validation_passed
                        ? "bg-emerald-500 hover:bg-emerald-600"
                        : "bg-amber-500 hover:bg-amber-600"
                )}
            >
                <div className="flex items-center gap-3">
                    {validation_passed ? (
                        <ShieldCheck size={24} className="text-white" />
                    ) : (
                        <ShieldAlert size={24} className="text-white" />
                    )}
                    <div className="text-left">
                        <h3 className="text-white font-semibold">
                            {validation_passed ? 'Validation Passed' : 'Validation Issues Detected'}
                        </h3>
                        <p className="text-white/80 text-sm">
                            {totalIssues === 0 
                                ? 'All citations verified' 
                                : `${totalIssues} ${totalIssues === 1 ? 'issue' : 'issues'} found`
                            }
                        </p>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    {totalIssues > 0 && (
                        <div className="bg-white/20 text-white text-xs font-bold px-2 py-1 rounded-full">
                            {totalIssues}
                        </div>
                    )}
                    {isExpanded ? (
                        <ChevronUp size={20} className="text-white" />
                    ) : (
                        <ChevronDown size={20} className="text-white" />
                    )}
                </div>
            </button>

            {/* Expanded Details */}
            {isExpanded && totalIssues > 0 && (
                <div className="p-6 space-y-4">
                    {/* Unsubstantiated Claims (Critical) */}
                    {unsubstantiated_claims.length > 0 && (
                        <div className="bg-red-50 border border-red-200 rounded-xl p-4">
                            <div className="flex items-center gap-2 mb-3">
                                <AlertCircle size={18} className="text-red-600" />
                                <h4 className="font-semibold text-red-800">
                                    Unsubstantiated Claims ({unsubstantiated_claims.length})
                                </h4>
                            </div>
                            <div className="space-y-2">
                                {unsubstantiated_claims.map((claim, idx) => (
                                    <div key={idx} className="flex items-start gap-2 text-sm">
                                        <div className="w-5 h-5 rounded-full bg-red-200 text-red-700 flex items-center justify-center text-xs font-bold shrink-0 mt-0.5">
                                            {idx + 1}
                                        </div>
                                        <p className="text-red-700 leading-relaxed">{claim}</p>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Citation Issues */}
                    {citation_issues.length > 0 && (
                        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
                            <div className="flex items-center gap-2 mb-3">
                                <AlertTriangle size={18} className="text-amber-600" />
                                <h4 className="font-semibold text-amber-800">
                                    Citation Issues ({citation_issues.length})
                                </h4>
                            </div>
                            <div className="space-y-3">
                                {citation_issues.map((issue, idx) => (
                                    <div key={idx} className="bg-white rounded-lg p-3 border border-amber-200">
                                        <p className="text-sm text-slate-700 mb-1 font-medium">
                                            {issue.claim}
                                        </p>
                                        <p className="text-xs text-amber-700">
                                            Issue: {issue.issue}
                                        </p>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Confidence Adjustments */}
                    {confidence_adjustments.length > 0 && (
                        <div className="bg-blue-50 border border-blue-200 rounded-xl p-4">
                            <div className="flex items-center gap-2 mb-3">
                                <AlertCircle size={18} className="text-blue-600" />
                                <h4 className="font-semibold text-blue-800">
                                    Confidence Adjustments ({confidence_adjustments.length})
                                </h4>
                            </div>
                            <div className="space-y-2">
                                {confidence_adjustments.map((adj, idx) => (
                                    <div key={idx} className="flex items-start gap-2 text-sm">
                                        <span className="text-blue-600 font-semibold shrink-0">
                                            {adj.section}:
                                        </span>
                                        <p className="text-slate-700">{adj.adjustment}</p>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* General Warnings */}
                    {warnings.length > 0 && (
                        <div className="bg-slate-50 border border-slate-200 rounded-xl p-4">
                            <div className="flex items-center gap-2 mb-3">
                                <AlertTriangle size={18} className="text-slate-600" />
                                <h4 className="font-semibold text-slate-800">
                                    Warnings ({warnings.length})
                                </h4>
                            </div>
                            <div className="space-y-1">
                                {warnings.map((warning, idx) => (
                                    <div key={idx} className="flex items-start gap-2 text-sm">
                                        <div className="w-1.5 h-1.5 rounded-full bg-slate-400 shrink-0 mt-2" />
                                        <p className="text-slate-600">{warning}</p>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            )}

            {/* All Clear Message */}
            {isExpanded && totalIssues === 0 && (
                <div className="p-6">
                    <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 text-center">
                        <ShieldCheck size={48} className="mx-auto text-emerald-500 mb-2" />
                        <p className="text-emerald-700 font-medium">
                            All citations verified and complete
                        </p>
                        <p className="text-emerald-600 text-sm mt-1">
                            No issues detected in this research report
                        </p>
                    </div>
                </div>
            )}
        </div>
    )
}

export default ValidationBadge
