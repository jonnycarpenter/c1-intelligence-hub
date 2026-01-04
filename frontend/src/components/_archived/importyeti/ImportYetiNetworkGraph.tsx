'use client'

import { useEffect, useState, useRef, useCallback } from 'react'
import ForceGraph2D from 'react-force-graph-2d'
import { api } from '@/lib/api'

interface Node {
    id: string
    name: string
    type: 'supplier' | 'customer'
    tier?: string
    val: number // for node size
    color?: string
}

interface Link {
    source: string
    target: string
    value: number
}

interface GraphData {
    nodes: Node[]
    links: Link[]
}

export default function ImportYetiNetworkGraph() {
    const [data, setData] = useState<GraphData>({ nodes: [], links: [] })
    const [loading, setLoading] = useState(true)
    const containerRef = useRef<HTMLDivElement>(null)
    const [dimensions, setDimensions] = useState({ width: 800, height: 600 })

    useEffect(() => {
        // Handle resize
        const updateDimensions = () => {
            if (containerRef.current) {
                setDimensions({
                    width: containerRef.current.clientWidth,
                    height: containerRef.current.clientHeight
                })
            }
        }

        window.addEventListener('resize', updateDimensions)
        updateDimensions()

        return () => window.removeEventListener('resize', updateDimensions)
    }, [])

    useEffect(() => {
        async function loadData() {
            try {
                const networkData = await api.getImportYetiNetwork()

                // Transform for visualization
                const nodes = networkData.nodes.map(n => ({
                    id: n.id,
                    name: n.id,
                    type: n.type as 'supplier' | 'customer',
                    tier: n.tier,
                    val: n.type === 'supplier' ? 10 : 5, // Default sizes
                    color: n.type === 'supplier' ? '#4f46e5' : '#10b981' // Indigo vs Emerald
                }))

                // Process links
                const links = networkData.links.map(l => ({
                    source: l.source,
                    target: l.target,
                    value: l.value
                }))

                setData({ nodes, links })
            } catch (e) {
                console.error("Failed to load network graph", e)
            } finally {
                setLoading(false)
            }
        }
        loadData()
    }, [])

    const nodeCanvasObject = useCallback((node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
        const label = node.name
        const fontSize = 12 / globalScale
        ctx.font = `${fontSize}px Sans-Serif`

        // Draw node
        ctx.beginPath()
        ctx.arc(node.x, node.y, 5, 0, 2 * Math.PI, false)
        ctx.fillStyle = node.color || '#ccc'
        ctx.fill()

        // Draw label
        ctx.textAlign = 'center'
        ctx.textBaseline = 'middle'
        ctx.fillStyle = '#1e293b' // Slate-800
        ctx.fillText(label, node.x, node.y + 8)
    }, [])

    if (loading) {
        return (
            <div className="flex items-center justify-center h-full min-h-[500px] bg-slate-50 rounded-xl border border-slate-200">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-500"></div>
            </div>
        )
    }

    return (
        <div ref={containerRef} className="w-full h-[600px] bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden relative">
            <ForceGraph2D
                width={dimensions.width}
                height={dimensions.height}
                graphData={data}
                nodeLabel="name"
                nodeColor="color"
                nodeRelSize={6}
                linkColor={() => '#e2e8f0'} // Slate-200
                linkDirectionalArrowLength={3.5}
                linkDirectionalArrowRelPos={1}
                cooldownTicks={100}
                onNodeClick={(node) => {
                    // Center view on node
                    // graphRef.current?.centerAt(node.x, node.y, 1000);
                    // graphRef.current?.zoom(8, 2000);
                }}
            />

            <div className="absolute top-4 right-4 bg-white/90 backdrop-blur-sm p-3 rounded-lg shadow-sm border border-slate-200 text-xs">
                <div className="flex items-center gap-2 mb-1">
                    <span className="w-3 h-3 rounded-full bg-indigo-600"></span>
                    <span>Supplier</span>
                </div>
                <div className="flex items-center gap-2">
                    <span className="w-3 h-3 rounded-full bg-emerald-500"></span>
                    <span>Customer</span>
                </div>
            </div>
        </div>
    )
}
