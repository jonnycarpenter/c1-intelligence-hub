'use client'

import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { Newspaper, ExternalLink, ArrowRight } from 'lucide-react'
import { Badge } from '@/components/ui'

export default function LogisticsIntel() {
    const [items, setItems] = useState<any[]>([])
    const [loading, setLoading] = useState(true)

    useEffect(() => {
        async function loadData() {
            try {
                // Fetch last 7 days of logistics news
                const digest = await api.getDigest({
                    categories: ['logistics'],
                    hours: 168
                })
                setItems(Array.isArray(digest?.items) ? digest.items : [])
            } catch (e) {
                console.error("Failed to load logistics news", e)
                setItems([])
            } finally {
                setLoading(false)
            }
        }
        loadData()
    }, [])

    if (loading) return null
    if (items.length === 0) return null

    return (
        <div className="mt-8 mb-12">
            <div className="flex items-center justify-between mb-6">
                <h2 className="text-xl font-bold text-slate-900 flex items-center gap-2">
                    <Newspaper className="text-indigo-600" size={24} />
                    Logistics Intelligence
                </h2>
                <span className="text-xs text-slate-400 font-medium uppercase tracking-wider">
                    Recent Logistics Updates
                </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {items.slice(0, 3).map((item) => (
                    <div key={item.id} className="bg-white p-5 rounded-xl shadow-sm border border-slate-200 flex flex-col group hover:shadow-md transition-all duration-200">
                        <div className="mb-3">
                            <Badge variant="info" className="mb-3">Logistics</Badge>
                            <h3 className="font-bold text-slate-900 mb-2 line-clamp-2 group-hover:text-indigo-600 transition-colors">
                                {item.title}
                            </h3>
                            <p className="text-sm text-slate-600 line-clamp-3 leading-relaxed">
                                {item.summary}
                            </p>
                        </div>

                        <div className="mt-auto pt-4 border-t border-slate-50 flex items-center justify-between">
                            <span className="text-[10px] font-medium text-slate-400 uppercase">
                                {item.published_at ? new Date(item.published_at).toLocaleDateString() : 'Recent'}
                            </span>
                            <a
                                href={item.sources?.[0]?.url || item.url || '#'}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-indigo-600 hover:text-indigo-800 text-xs font-semibold flex items-center gap-1 transition-colors"
                            >
                                View Analysis <ExternalLink size={12} />
                            </a>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    )
}
