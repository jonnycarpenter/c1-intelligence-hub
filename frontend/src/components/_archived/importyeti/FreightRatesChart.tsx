'use client'

import { useEffect, useState } from 'react'
import {
    LineChart,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    Legend,
    ResponsiveContainer
} from 'recharts'
import { api } from '@/lib/api'

interface FreightRate {
    lane: string
    rate: number
    as_of: string
}

export default function FreightRatesChart() {
    const [data, setData] = useState<any[]>([])
    const [loading, setLoading] = useState(true)

    useEffect(() => {
        async function loadData() {
            try {
                const rawData = await api.getFreightData({ days: 120 })

                if (!Array.isArray(rawData)) {
                    console.error("Freight data is not an array", rawData)
                    setData([])
                    return
                }

                // Transform data for Recharts
                // We need it by date: { date: '2025-01-01', lane1: 1200, lane2: 1300 }
                const formatted = rawData.reduce((acc: any, curr) => {
                    const asOf = curr?.as_of
                    if (!asOf || typeof asOf !== 'string') return acc

                    const date = asOf.split('T')[0]
                    if (!acc[date]) acc[date] = { date }
                    if (curr.lane) {
                        acc[date][curr.lane] = curr.rate
                    }
                    return acc
                }, {})

                // Sort data chronologically for the line chart
                const chartData = Object.values(formatted).sort((a: any, b: any) => {
                    const dateA = a && (a as any).date ? new Date((a as any).date).getTime() : 0
                    const dateB = b && (b as any).date ? new Date((b as any).date).getTime() : 0
                    return dateA - dateB
                })

                setData(chartData)
            } catch (e) {
                console.error("Failed to load freight data", e)
            } finally {
                setLoading(false)
            }
        }
        loadData()
    }, [])

    if (loading) {
        return (
            <div className="h-[400px] flex items-center justify-center bg-white rounded-xl border border-slate-200 shadow-sm">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-500"></div>
            </div>
        )
    }

    // Handle empty data state
    if (!data || data.length === 0) {
        return (
            <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm mb-8">
                <div className="mb-6">
                    <h3 className="text-lg font-bold text-slate-900">Freight Rate Trends</h3>
                    <p className="text-sm text-slate-500">Weekly Drewry World Container Index (WCI) Spot Rates per 40ft Container</p>
                </div>
                <div className="h-[300px] flex items-center justify-center text-slate-400">
                    No freight rate data available
                </div>
            </div>
        )
    }

    // Get unique lanes for lines (excluding the 'date' key)
    const lanes = Array.from(new Set(data.flatMap(d => d ? Object.keys(d).filter(k => k !== 'date') : [])))

    // High-fidelity colors
    const colors = [
        '#4f46e5', // Indigo
        '#10b981', // Emerald
        '#f59e0b', // Amber
        '#ef4444', // Red
        '#8b5cf6', // Violet
        '#06b6d4', // Cyan
    ]

    return (
        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm mb-8">
            <div className="mb-6">
                <h3 className="text-lg font-bold text-slate-900">Freight Rate Trends</h3>
                <p className="text-sm text-slate-500">Weekly Drewry World Container Index (WCI) Spot Rates per 40ft Container</p>
            </div>

            <div className="h-[400px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={data}>
                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                        <XAxis
                            dataKey="date"
                            stroke="#64748b"
                            fontSize={11}
                            tickMargin={12}
                            axisLine={false}
                            tickLine={false}
                            minTickGap={30}
                        />
                        <YAxis
                            stroke="#64748b"
                            fontSize={11}
                            tickFormatter={(value) => value != null ? `$${value.toLocaleString()}` : ''}
                            axisLine={false}
                            tickLine={false}
                            domain={['auto', 'auto']}
                            orientation="right"
                        />
                        <Tooltip
                            contentStyle={{
                                backgroundColor: 'rgba(255, 255, 255, 0.95)',
                                borderRadius: '12px',
                                border: '1px solid #e2e8f0',
                                boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)',
                                backdropFilter: 'blur(4px)',
                                padding: '12px'
                            }}
                            formatter={(value: any) => [value != null ? `$${value.toLocaleString()}` : '$0', 'Rate']}
                            labelStyle={{ fontWeight: 'bold', color: '#1e293b', marginBottom: '8px' }}
                        />
                        <Legend
                            verticalAlign="top"
                            align="right"
                            iconType="circle"
                            iconSize={8}
                            wrapperStyle={{ paddingBottom: '20px', fontSize: '12px' }}
                        />
                        {lanes.map((lane, index) => (
                            <Line
                                key={lane}
                                type="monotone"
                                dataKey={lane}
                                stroke={colors[index % colors.length]}
                                strokeWidth={2.5}
                                dot={false}
                                activeDot={{ r: 6, strokeWidth: 0 }}
                                name={lane}
                                animationDuration={1500}
                            />
                        ))}
                    </LineChart>
                </ResponsiveContainer>
            </div>
        </div>
    )
}
