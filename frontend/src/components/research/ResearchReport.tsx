'use client'

import { useState } from 'react'
import {
    FileText,
    BarChart3,
    Target,
    HelpCircle,
    ChevronRight,
    ChevronDown,
    ShieldCheck,
    TrendingUp,
    LayoutDashboard,
    Bookmark,
    CheckCircle,
    Loader2,
    ExternalLink,
    Brain,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import ReactMarkdown from 'react-markdown'
import { api } from '@/lib/api'
import { API_BASE } from '@/lib/config'
import { ReportBlockRenderer } from './ReportBlockRenderer'
import type { ReportBlock } from '@/types'

interface DeepResearchReportProps {
    report: any
}

// =============================================================================
// Helper: Extract domain from URL
// =============================================================================
const extractDomain = (url: string): string => {
    try {
        if (!url) return 'Unknown'
        const parsed = new URL(url)
        return parsed.hostname.replace('www.', '')
    } catch {
        return 'Unknown'
    }
}

// =============================================================================
// Company Logo Component
// =============================================================================
interface CompanyWithLogo {
    name: string
    domain?: string
    logo_url?: string
}

function CompanyLogo({ company }: { company: CompanyWithLogo }) {
    const [imageError, setImageError] = useState(false)

    // Use logo.dev API via our backend proxy
    const logoUrl = company.domain
        ? `${API_BASE}/api/pipeline/logo/${company.domain}`
        : null

    if (!logoUrl || imageError) {
        // Fallback to initials
        const initials = company.name
            .split(' ')
            .map(w => w[0])
            .slice(0, 2)
            .join('')
            .toUpperCase()

        return (
            <div
                className="w-6 h-6 rounded bg-slate-200 flex items-center justify-center text-[9px] font-bold text-slate-500"
                title={company.name}
            >
                {initials}
            </div>
        )
    }

    return (
        <img
            src={logoUrl}
            alt={company.name}
            title={company.name}
            className="w-6 h-6 rounded object-contain"
            onError={() => setImageError(true)}
        />
    )
}

// =============================================================================
// Citation Component - Shows domain, links to full URL
// =============================================================================
interface Citation {
    source_type?: string
    source_title: string
    source_url?: string | null
    source_date?: string | null
}

function CitationList({ citations }: { citations: Citation[] }) {
    if (!citations || citations.length === 0) return null

    // Filter to only citations with URLs
    const linkedCitations = citations.filter(c => c.source_url)
    if (linkedCitations.length === 0) return null

    return (
        <div className="mt-4 pt-4 border-t border-slate-100">
            <p className="text-xs font-medium text-slate-500 mb-2 flex items-center gap-1">
                <ExternalLink size={12} />
                Sources
            </p>
            <div className="flex flex-wrap gap-2">
                {linkedCitations.map((citation, idx) => {
                    const domain = citation.source_url ? extractDomain(citation.source_url) : 'Unknown'
                    return (
                        <a
                            key={idx}
                            href={citation.source_url || '#'}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded-lg text-xs text-slate-600 hover:text-slate-900 transition-colors group"
                            title={citation.source_title}
                        >
                            <span className="font-medium">{domain}</span>
                            <ExternalLink size={10} className="opacity-50 group-hover:opacity-100" />
                        </a>
                    )
                })}
            </div>
        </div>
    )
}

export default function ResearchReport({ report }: DeepResearchReportProps) {
    const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')

    if (!report) return null

    const { executive_summary, sections, field_sales, companies_with_logos, sources_used, data_gaps, thinking_content } = report
    const [thinkingExpanded, setThinkingExpanded] = useState(false)

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
                    <div className="space-y-3">
                        {executive_summary.key_points?.map((point: string, idx: number) => {
                            const citation = executive_summary.key_point_citations?.[idx]
                            const hasValidCitation = citation?.source_url && citation.source_title !== 'MISSING CITATION'
                            return (
                                <div key={idx} className="flex gap-3 group">
                                    <div className="mt-1.5 w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0" />
                                    <div className="flex-1">
                                        <p className="text-slate-700">{point}</p>
                                        {hasValidCitation && (
                                            <a
                                                href={citation.source_url!}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                className="inline-flex items-center gap-1 mt-1 px-2 py-0.5 bg-slate-100 hover:bg-slate-200 rounded text-xs text-slate-500 hover:text-slate-700 transition-colors"
                                                title={citation.source_title}
                                            >
                                                <ExternalLink size={10} />
                                                <span>{extractDomain(citation.source_url!)}</span>
                                            </a>
                                        )}
                                    </div>
                                </div>
                            )
                        })}
                    </div>

                    {/* Company Logos */}
                    {companies_with_logos && companies_with_logos.length > 0 && (
                        <div className="mt-6 pt-4 border-t border-slate-100">
                            <p className="text-xs font-medium text-slate-500 mb-3">Companies Mentioned</p>
                            <div className="flex flex-wrap gap-2">
                                {companies_with_logos.map((company: CompanyWithLogo, idx: number) => (
                                    <div
                                        key={idx}
                                        className="inline-flex items-center gap-2 px-3 py-1.5 bg-slate-50 border border-slate-200 rounded-lg"
                                    >
                                        <CompanyLogo company={company} />
                                        <span className="text-sm font-medium text-slate-700">{company.name}</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            </section>

            {/* Claude's Thinking Process - Extended Thinking Feature */}
            {thinking_content && (
                <section className="bg-gradient-to-br from-purple-50 to-indigo-50 rounded-2xl border border-purple-200 overflow-hidden shadow-sm">
                    <button
                        onClick={() => setThinkingExpanded(!thinkingExpanded)}
                        className="w-full px-6 py-4 flex items-center justify-between hover:bg-purple-100/50 transition-colors"
                    >
                        <div className="flex items-center gap-3">
                            <div className="p-2 bg-purple-100 rounded-lg">
                                <Brain size={20} className="text-purple-600" />
                            </div>
                            <div className="text-left">
                                <h2 className="font-semibold text-purple-900">Claude&apos;s Reasoning Process</h2>
                                <p className="text-xs text-purple-600">See how Claude analyzed and synthesized the research</p>
                            </div>
                        </div>
                        <ChevronDown
                            size={20}
                            className={cn(
                                "text-purple-500 transition-transform duration-200",
                                thinkingExpanded && "rotate-180"
                            )}
                        />
                    </button>
                    {thinkingExpanded && (
                        <div className="px-6 pb-6 border-t border-purple-200/50">
                            <div className="mt-4 p-4 bg-white/80 rounded-xl border border-purple-100">
                                <div className="prose prose-sm prose-slate max-w-none">
                                    <ReactMarkdown className="text-sm text-slate-700 leading-relaxed space-y-2">
                                        {thinking_content}
                                    </ReactMarkdown>
                                </div>
                            </div>
                            <p className="mt-3 text-xs text-purple-500 italic">
                                This is a summary of Claude&apos;s internal reasoning process using Extended Thinking.
                            </p>
                        </div>
                    )}
                </section>
            )}

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
                        {section.blocks && section.blocks.length > 0 ? (
                            <div className="mb-6">
                                {section.blocks.map((block: ReportBlock) => (
                                    <ReportBlockRenderer key={block.block_id} block={block} />
                                ))}
                            </div>
                        ) : (
                            <div className="prose prose-slate max-w-none mb-6">
                                <ReactMarkdown>{section.content}</ReactMarkdown>
                            </div>
                        )}

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

                        {/* Section Citations */}
                        <CitationList citations={section.citations} />
                    </div>
                </section>
            ))}

            {/* Field Sales Implications - only show if field_sales exists (Category agent output) */}
            {field_sales && (
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
            )}

            {/* All Sources Section */}
            {sources_used && sources_used.length > 0 && (
                <section className="bg-white rounded-2xl border border-slate-200 overflow-hidden shadow-sm">
                    <div className="bg-slate-100 px-6 py-4 flex items-center gap-2 border-b border-slate-200">
                        <ExternalLink size={20} className="text-slate-600" />
                        <h2 className="text-slate-800 font-semibold">Sources & References</h2>
                        <span className="ml-auto text-xs text-slate-500 bg-slate-200 px-2 py-0.5 rounded-full">
                            {sources_used.filter((s: Citation) => s.source_url && s.source_title !== 'MISSING CITATION').length} sources
                        </span>
                    </div>
                    <div className="p-6">
                        <div className="space-y-3">
                            {sources_used
                                .filter((source: Citation) => source.source_url && source.source_title !== 'MISSING CITATION')
                                .map((source: Citation, idx: number) => (
                                    <a
                                        key={idx}
                                        href={source.source_url!}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="flex items-start gap-3 p-3 rounded-lg border border-slate-100 hover:border-slate-300 hover:bg-slate-50 transition-all group"
                                    >
                                        <div className="w-8 h-8 rounded bg-slate-100 flex items-center justify-center shrink-0 group-hover:bg-slate-200 transition-colors">
                                            <FileText size={14} className="text-slate-500" />
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <p className="text-sm font-medium text-slate-800 truncate group-hover:text-slate-900">
                                                {source.source_title}
                                            </p>
                                            <div className="flex items-center gap-2 mt-0.5">
                                                <span className="text-xs text-slate-500">
                                                    {extractDomain(source.source_url!)}
                                                </span>
                                                {source.source_date && (
                                                    <>
                                                        <span className="text-slate-300">•</span>
                                                        <span className="text-xs text-slate-400">{source.source_date}</span>
                                                    </>
                                                )}
                                                {source.source_type && source.source_type !== 'unspecified' && (
                                                    <>
                                                        <span className="text-slate-300">•</span>
                                                        <span className="text-xs text-slate-400 capitalize">
                                                            {String(source.source_type).replace(/_/g, ' ')}
                                                        </span>
                                                    </>
                                                )}
                                            </div>
                                        </div>
                                        <ExternalLink size={14} className="text-slate-400 group-hover:text-slate-600 shrink-0 mt-1" />
                                    </a>
                                ))}
                        </div>

                        {/* Data Gaps Warning */}
                        {data_gaps && data_gaps.length > 0 && (
                            <div className="mt-6 pt-4 border-t border-slate-100">
                                <p className="text-xs font-medium text-amber-600 mb-2 flex items-center gap-1">
                                    <HelpCircle size={12} />
                                    Data Gaps
                                </p>
                                <div className="space-y-1">
                                    {data_gaps.map((gap: string, idx: number) => (
                                        <p key={idx} className="text-xs text-slate-500 italic">• {gap}</p>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                </section>
            )}
        </div>
    )
}
