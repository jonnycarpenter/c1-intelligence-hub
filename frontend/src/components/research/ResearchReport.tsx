'use client'

import { useState } from 'react'
import {
    FileText,
    BarChart3,
    Target,
    HelpCircle,
    ChevronRight,
    ShieldCheck,
    TrendingUp,
    LayoutDashboard,
    Bookmark,
    CheckCircle,
    Loader2,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import ReactMarkdown from 'react-markdown'
import { api } from '@/lib/api'

interface DeepResearchReportProps {
    report: any
}

export default function ResearchReport({ report }: DeepResearchReportProps) {
    const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')

    if (!report) return null

    const { executive_summary, sections, field_sales } = report

    const handleSaveToMemory = async () => {
        if (saveStatus === 'saving' || saveStatus === 'saved') return

        setSaveStatus('saving')
        try {
            await api.saveToMemory({
                type: 'research_export',
                question: report.query || executive_summary.headline,
                answer: [
                    `**${executive_summary.headline}**`,
                    '',
                    ...(executive_summary.key_points || []).map((p: string) => `• ${p}`),
                ].join('\n'),
                sources: (report.sources || []).slice(0, 5).map((s: any) => ({
                    title: s.title || s.name || 'Source',
                    url: s.url,
                })),
                confidence: report.overall_confidence || 'medium',
                tags: [
                    ...(report.companies || []).slice(0, 5),
                    ...(report.topics || []).slice(0, 3),
                ],
            })
            setSaveStatus('saved')
        } catch (err) {
            console.error('Failed to save to memory:', err)
            setSaveStatus('error')
            // Reset after 3 seconds so user can try again
            setTimeout(() => setSaveStatus('idle'), 3000)
        }
    }

    return (
        <div className="space-y-6 pb-12">
            {/* Executive Summary */}
            <section className="bg-white rounded-2xl border border-slate-200 overflow-hidden shadow-sm">
                <div className="bg-slate-900 px-6 py-4 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <LayoutDashboard size={20} className="text-emerald-400" />
                        <h2 className="text-white font-semibold">Executive Summary</h2>
                    </div>
                    <button
                        onClick={handleSaveToMemory}
                        disabled={saveStatus === 'saving' || saveStatus === 'saved'}
                        className={cn(
                            "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors",
                            saveStatus === 'saved'
                                ? "bg-emerald-600 text-white cursor-default"
                                : saveStatus === 'error'
                                    ? "bg-red-600 text-white"
                                    : "bg-slate-700 hover:bg-slate-600 text-slate-200"
                        )}
                        title="Save to Memory"
                    >
                        {saveStatus === 'saving' ? (
                            <><Loader2 size={14} className="animate-spin" /> Saving...</>
                        ) : saveStatus === 'saved' ? (
                            <><CheckCircle size={14} /> Saved</>
                        ) : saveStatus === 'error' ? (
                            <><Bookmark size={14} /> Error</>
                        ) : (
                            <><Bookmark size={14} /> Save to Memory</>
                        )}
                    </button>
                </div>
                <div className="p-6">
                    <h1 className="text-2xl font-bold text-slate-900 mb-4">{executive_summary.headline}</h1>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                        {executive_summary.key_metrics?.map((metric: any, idx: number) => (
                            <div key={idx} className="bg-slate-50 rounded-xl p-4 border border-slate-100 text-center">
                                <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">{metric.label}</p>
                                <p className="text-xl font-bold text-slate-900">{metric.value}</p>
                            </div>
                        ))}
                    </div>
                    <div className="space-y-2">
                        {executive_summary.key_points?.map((point: string, idx: number) => (
                            <div key={idx} className="flex gap-3">
                                <div className="mt-1.5 w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0" />
                                <p className="text-slate-700">{point}</p>
                            </div>
                        ))}
                    </div>
                </div>
            </section>

            {/* Main Sections */}
            {sections?.map((section: any, idx: number) => (
                <section key={idx} className="bg-white rounded-2xl border border-slate-200 overflow-hidden shadow-sm">
                    <div className="bg-slate-50 px-6 py-3 border-b border-slate-200 flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            <FileText size={18} className="text-slate-600" />
                            <h3 className="font-semibold text-slate-800">{section.section_title}</h3>
                        </div>
                        <span className="text-xs text-slate-400">Section {idx + 1}</span>
                    </div>
                    <div className="p-6">
                        <div className="prose prose-slate max-w-none mb-6">
                            <ReactMarkdown>{section.content}</ReactMarkdown>
                        </div>

                        {/* Tables */}
                        {section.tables && section.tables.length > 0 && (
                            <div className="space-y-8 mt-6 border-t border-slate-100 pt-6">
                                {section.tables.map((table: any, tIdx: number) => (
                                    <div key={tIdx} className="overflow-hidden rounded-xl border border-slate-200">
                                        <div className="bg-slate-50 px-4 py-2 border-b border-slate-200">
                                            <h4 className="text-sm font-bold text-slate-700">{table.title}</h4>
                                        </div>
                                        <div className="overflow-x-auto">
                                            <table className="w-full text-sm text-left">
                                                <thead className="bg-slate-50/50 text-slate-500 font-medium border-b border-slate-200">
                                                    <tr>
                                                        {table.columns.map((col: string, cIdx: number) => (
                                                            <th key={cIdx} className="px-4 py-2 whitespace-nowrap">{col}</th>
                                                        ))}
                                                    </tr>
                                                </thead>
                                                <tbody className="divide-y divide-slate-100">
                                                    {table.rows.map((row: any, rIdx: number) => (
                                                        <tr key={rIdx} className="hover:bg-slate-50/50 transition-colors">
                                                            {table.columns.map((col: string, cIdx: number) => (
                                                                <td key={cIdx} className={cn(
                                                                    "px-4 py-2 text-slate-700",
                                                                    // Right align if it looks like a number
                                                                    /^[0-9$%.,-]+%?$/.test(String(row[col])) && "text-right font-mono"
                                                                )}>
                                                                    {row[col]}
                                                                </td>
                                                            ))}
                                                        </tr>
                                                    ))}
                                                </tbody>
                                            </table>
                                        </div>
                                        <div className="bg-slate-50/30 px-4 py-1.5 border-t border-slate-100 flex justify-between items-center">
                                            <span className="text-[10px] text-slate-400 font-medium">Source: {table.source}</span>
                                            {table.notes && <span className="text-[10px] text-slate-400 italic">{table.notes}</span>}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </section>
            ))}

            {/* Field Sales Implications */}
            <section className="bg-emerald-50 rounded-2xl border border-emerald-100 overflow-hidden shadow-sm">
                <div className="bg-emerald-600 px-6 py-4 flex items-center gap-2">
                    <Target size={20} className="text-white" />
                    <h2 className="text-white font-semibold">Field Sales Implications</h2>
                </div>
                <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-8">
                    <div>
                        <h4 className="flex items-center gap-2 text-emerald-800 font-bold mb-4">
                            <TrendingUp size={18} />
                            Offensive Angles
                        </h4>
                        <div className="space-y-4">
                            {field_sales.offensive_angles?.map((angle: any, idx: number) => (
                                <div key={idx} className="bg-white rounded-xl p-4 border border-emerald-100">
                                    <p className="font-semibold text-slate-900 text-sm mb-1">{angle.angle}</p>
                                    <p className="text-xs text-slate-600 italic">Target: {angle.target_segment}</p>
                                </div>
                            ))}
                        </div>
                    </div>
                    <div>
                        <h4 className="flex items-center gap-2 text-emerald-800 font-bold mb-4">
                            <ShieldCheck size={18} />
                            Defensive Watch-outs
                        </h4>
                        <div className="space-y-4">
                            {field_sales.defensive_angles?.map((angle: any, idx: number) => (
                                <div key={idx} className="bg-white rounded-xl p-4 border border-emerald-100">
                                    <p className="font-semibold text-slate-900 text-sm mb-1">{angle.risk}</p>
                                    <p className="text-xs text-slate-600 italic">Mitigation: {angle.mitigation}</p>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
                <div className="bg-emerald-100/50 p-6 border-t border-emerald-100">
                    <h4 className="flex items-center gap-2 text-emerald-800 font-bold mb-4">
                        <HelpCircle size={18} />
                        Questions to Explore
                    </h4>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        {field_sales.questions_to_explore?.map((q: string, idx: number) => (
                            <div key={idx} className="flex gap-2">
                                <ChevronRight size={14} className="mt-1 text-emerald-500 shrink-0" />
                                <p className="text-slate-700 text-sm">{q}</p>
                            </div>
                        ))}
                    </div>
                </div>
            </section>
        </div>
    )
}
