'use client'

import { useState, useEffect } from 'react'
import { api } from '@/lib/api'
import { Ship, Users, Package, Search, Factory, AlertCircle, ArrowUpRight } from 'lucide-react'
import { cn } from '@/lib/utils'

interface DashboardStats {
    total_suppliers: number
    total_oems: number
    active_relationships: number
    tracked_shipments: number
}

interface Supplier {
    supplier_id: string
    supplier_name: string
    country: string
    supplier_tier?: string
    total_shipments?: number
    total_us_customers?: number
    is_c1_supplier?: boolean
}

import dynamic from 'next/dynamic'
import { LayoutGrid, Network, TrendingUp, Newspaper } from 'lucide-react'

const FreightRatesChart = dynamic(() => import('./FreightRatesChart'), { 
    ssr: false,
    loading: () => (
        <div className="h-[400px] flex items-center justify-center bg-white rounded-xl border border-slate-200 shadow-sm">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-500"></div>
        </div>
    )
})

const LogisticsIntel = dynamic(() => import('./LogisticsIntel'), { 
    ssr: false,
    loading: () => null 
})

const NetworkGraph = dynamic(() => import('./ImportYetiNetworkGraph'), {
    ssr: false,
    loading: () => (
        <div className="flex items-center justify-center h-[600px] bg-slate-50 rounded-xl border border-slate-200">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-500"></div>
        </div>
    )
})

export function ImportYetiDashboard() {
    const [stats, setStats] = useState<DashboardStats | null>(null)
    const [suppliers, setSuppliers] = useState<Supplier[]>([])
    const [loading, setLoading] = useState(true)
    const [search, setSearch] = useState('')
    const [view, setView] = useState<'dashboard' | 'network'>('dashboard')

    useEffect(() => {
        async function loadData() {
            try {
                const [statsData, suppliersData] = await Promise.all([
                    api.getImportYetiStats(),
                    api.getImportYetiSuppliers({ limit: 20 })
                ])
                setStats(statsData)
                setSuppliers(suppliersData)
            } catch (e) {
                console.error("Failed to load dashboard data", e)
            } finally {
                setLoading(false)
            }
        }
        loadData()
    }, [])

    return (
        <div className="flex-1 overflow-y-auto bg-slate-50 p-6">
            <div className="mb-8 flex justify-between items-start">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900 mb-2">Trade Intelligence</h1>
                    <p className="text-slate-500">Track shipments, suppliers, and supply chain relationships.</p>
                </div>

                <div className="flex p-1 bg-white rounded-lg border border-slate-200 shadow-sm">
                    <button
                        onClick={() => setView('dashboard')}
                        className={cn(
                            "flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-all",
                            view === 'dashboard'
                                ? "bg-indigo-50 text-indigo-700 shadow-sm"
                                : "text-slate-600 hover:bg-slate-50"
                        )}
                    >
                        <LayoutGrid size={16} />
                        Dashboard
                    </button>
                    <button
                        onClick={() => setView('network')}
                        className={cn(
                            "flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-all",
                            view === 'network'
                                ? "bg-indigo-50 text-indigo-700 shadow-sm"
                                : "text-slate-600 hover:bg-slate-50"
                        )}
                    >
                        <Network size={16} />
                        Network
                    </button>
                </div>
            </div>

            {loading ? (
                <div className="flex items-center justify-center h-64">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-500"></div>
                </div>
            ) : view === 'network' ? (
                <NetworkGraph />
            ) : (
                <>
                    {/* Stats Grid */}
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
                        <StatsCard
                            title="Tracked Suppliers"
                            value={stats?.total_suppliers || 0}
                            icon={Users}
                            color="text-indigo-600"
                            bg="bg-indigo-50"
                        />
                        <StatsCard
                            title="OEMs Monitored"
                            value={stats?.total_oems || 0}
                            icon={Factory}
                            color="text-emerald-600"
                            bg="bg-emerald-50"
                        />
                        <StatsCard
                            title="Active Relationships"
                            value={stats?.active_relationships || 0}
                            icon={ArrowUpRight}
                            color="text-blue-600"
                            bg="bg-blue-50"
                        />
                        <StatsCard
                            title="Tracked Shipments"
                            value={stats?.tracked_shipments || 0}
                            icon={Package}
                            color="text-emerald-600"
                            bg="bg-emerald-50"
                        />
                    </div>

                    {/* Freight Rate Trends */}
                    <FreightRatesChart />

                    {/* Suppliers Table */}
                    <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
                        <div className="p-4 border-b border-slate-200 flex justify-between items-center">
                            <h2 className="font-semibold text-slate-800">Top Suppliers</h2>
                            <div className="relative">
                                <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
                                <input
                                    type="text"
                                    placeholder="Search suppliers..."
                                    className="pl-9 pr-4 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition-all"
                                    value={search}
                                    onChange={(e) => setSearch(e.target.value)}
                                />
                            </div>
                        </div>

                        <div className="overflow-x-auto">
                            <table className="w-full text-sm text-left">
                                <thead className="text-xs text-slate-500 uppercase bg-slate-50/50">
                                    <tr>
                                        <th className="px-4 py-3 font-medium">Supplier</th>
                                        <th className="px-4 py-3 font-medium">Country</th>
                                        <th className="px-4 py-3 font-medium">Tier</th>
                                        <th className="px-4 py-3 font-medium text-right">Shipments (12m)</th>
                                        <th className="px-4 py-3 font-medium text-right">Customers (US)</th>
                                        <th className="px-4 py-3 font-medium text-center">Status</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-100">
                                    {(Array.isArray(suppliers) ? suppliers : []).map((s) => (
                                        <tr key={s.supplier_id} className="hover:bg-slate-50 transition-colors">
                                            <td className="px-4 py-3 font-medium text-slate-900">{s.supplier_name}</td>
                                            <td className="px-4 py-3 text-slate-600">{s.country || '-'}</td>
                                            <td className="px-4 py-3">
                                                <span className={cn(
                                                    "px-2 py-0.5 rounded-full text-[10px] font-medium uppercase",
                                                    s.supplier_tier === 'raw_material' ? "bg-purple-100 text-purple-700" :
                                                        s.supplier_tier === 'intermediate' ? "bg-emerald-100 text-emerald-700" :
                                                            "bg-slate-100 text-slate-600"
                                                )}>
                                                    {s.supplier_tier?.replace('_', ' ') || 'Unknown'}
                                                </span>
                                            </td>
                                            <td className="px-4 py-3 text-slate-600 text-right">{s.total_shipments?.toLocaleString() || 0}</td>
                                            <td className="px-4 py-3 text-slate-600 text-right">{s.total_us_customers?.toLocaleString() || 0}</td>
                                            <td className="px-4 py-3 text-center">
                                                {s.is_c1_supplier && (
                                                    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">
                                                        C1 Supplier
                                                    </span>
                                                )}
                                            </td>
                                        </tr>
                                    ))}
                                    {(!suppliers || suppliers.length === 0) && (
                                        <tr>
                                            <td colSpan={6} className="px-4 py-8 text-center text-slate-500">
                                                No suppliers found
                                            </td>
                                        </tr>
                                    )}
                                </tbody>
                            </table>
                        </div>
                    </div>

                    <LogisticsIntel />
                </>
            )}
        </div>
    )
}

function StatsCard({ title, value, icon: Icon, color, bg }: any) {
    return (
        <div className="bg-white p-4 rounded-xl shadow-sm border border-slate-200">
            <div className="flex items-center gap-4">
                <div className={cn("w-12 h-12 rounded-lg flex items-center justify-center", bg)}>
                    <Icon className={cn("w-6 h-6", color)} />
                </div>
                <div>
                    <p className="text-sm text-slate-500 font-medium">{title}</p>
                    <p className="text-2xl font-bold text-slate-900">{value.toLocaleString()}</p>
                </div>
            </div>
        </div>
    )
}
