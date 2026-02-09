'use client'

import { useEffect, useState, useRef, useCallback, useMemo } from 'react'
import ForceGraph2D from 'react-force-graph-2d'
import { ZoomIn, ZoomOut, Maximize2 } from 'lucide-react'

export interface GraphNode {
  id: string
  label: string
  type: 'company' | 'supplier'
  entity_type?: 'target' | 'competitor' | 'discovered'
  total_shipments?: number
  category?: string
  ticker?: string
  country?: string
  // Computed by ForceGraph
  x?: number
  y?: number
  color?: string
  val?: number
}

export interface GraphEdge {
  source: string
  target: string
  relationship: string
  total_shipments?: number
  shipments_12m?: number
}

export interface GraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
  stats: {
    total_companies: number
    total_suppliers: number
    total_edges: number
  }
}

interface NetworkGraphProps {
  data: GraphData
  onNodeClick?: (node: GraphNode) => void
  isLoading?: boolean
}

// Node color palette
const NODE_COLORS: Record<string, string> = {
  target: '#f59e0b',     // amber-500 (C1)
  competitor: '#3b82f6', // blue-500
  supplier: '#6366f1',   // indigo-500
  default: '#94a3b8',    // slate-400
}

export default function NetworkGraph({ data, onNodeClick, isLoading }: NetworkGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const graphRef = useRef<any>(null)
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 })

  // Resize handler
  useEffect(() => {
    const updateDimensions = () => {
      if (containerRef.current) {
        setDimensions({
          width: containerRef.current.clientWidth,
          height: containerRef.current.clientHeight,
        })
      }
    }

    const observer = new ResizeObserver(updateDimensions)
    if (containerRef.current) {
      observer.observe(containerRef.current)
    }
    updateDimensions()

    return () => observer.disconnect()
  }, [])

  // Transform data for ForceGraph2D
  const graphData = useMemo(() => {
    const nodes = data.nodes.map((n) => {
      let color = NODE_COLORS.default
      if (n.type === 'company') {
        color = NODE_COLORS[n.entity_type || 'default'] || NODE_COLORS.default
      } else if (n.type === 'supplier') {
        color = NODE_COLORS.supplier
      }

      // Size by shipment volume (log scale, clamped)
      const shipments = n.total_shipments || 0
      const val = shipments > 0
        ? Math.max(4, Math.min(20, 4 + Math.log10(shipments + 1) * 3))
        : 4

      return { ...n, color, val }
    })

    const links = data.edges.map((e) => ({
      source: e.source,
      target: e.target,
      value: e.shipments_12m || 1,
    }))

    return { nodes, links }
  }, [data])

  // Custom node rendering with labels
  const nodeCanvasObject = useCallback(
    (node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
      const radius = node.val || 4
      const fontSize = Math.max(10, 12 / globalScale)

      // Draw node circle
      ctx.beginPath()
      ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI, false)
      ctx.fillStyle = node.color || '#94a3b8'
      ctx.fill()

      // Draw border for company nodes
      if (node.type === 'company') {
        ctx.strokeStyle = node.entity_type === 'target' ? '#d97706' : '#2563eb'
        ctx.lineWidth = 1.5 / globalScale
        ctx.stroke()
      }

      // Draw label (only when zoomed in enough)
      if (globalScale > 0.6) {
        const label = node.label || ''
        ctx.font = `${node.type === 'company' ? 'bold ' : ''}${fontSize}px Inter, system-ui, sans-serif`
        ctx.textAlign = 'center'
        ctx.textBaseline = 'top'
        ctx.fillStyle = '#1e293b' // slate-800
        ctx.fillText(label, node.x, node.y + radius + 2)
      }
    },
    []
  )

  const handleNodeClick = useCallback(
    (node: any) => {
      if (onNodeClick) {
        onNodeClick(node as GraphNode)
      }
      // Center and zoom to node
      if (graphRef.current) {
        graphRef.current.centerAt(node.x, node.y, 800)
        graphRef.current.zoom(3, 800)
      }
    },
    [onNodeClick]
  )

  const handleZoomIn = () => graphRef.current?.zoom(graphRef.current.zoom() * 1.5, 400)
  const handleZoomOut = () => graphRef.current?.zoom(graphRef.current.zoom() / 1.5, 400)
  const handleResetView = () => graphRef.current?.zoomToFit(400, 60)

  if (isLoading) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-slate-50 rounded-xl border border-slate-200">
        <div className="text-center">
          <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-indigo-500 mx-auto mb-3" />
          <p className="text-sm text-slate-500">Loading network graph...</p>
        </div>
      </div>
    )
  }

  return (
    <div ref={containerRef} className="relative w-full h-full bg-white rounded-xl overflow-hidden">
      <ForceGraph2D
        ref={graphRef}
        width={dimensions.width}
        height={dimensions.height}
        graphData={graphData}
        nodeCanvasObject={nodeCanvasObject}
        nodePointerAreaPaint={(node: any, color: string, ctx: CanvasRenderingContext2D) => {
          const radius = (node.val || 4) + 2
          ctx.beginPath()
          ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI, false)
          ctx.fillStyle = color
          ctx.fill()
        }}
        linkColor={() => '#e2e8f0'}
        linkDirectionalArrowLength={3}
        linkDirectionalArrowRelPos={1}
        linkWidth={(link: any) => Math.max(0.5, Math.sqrt(link.value) / 8)}
        cooldownTicks={150}
        onNodeClick={handleNodeClick}
        enableNodeDrag={true}
        enableZoomInteraction={true}
        d3AlphaDecay={0.02}
        d3VelocityDecay={0.3}
      />

      {/* Legend */}
      <div className="absolute top-3 right-3 bg-white/95 backdrop-blur-sm p-3 rounded-lg shadow-sm border border-slate-200 text-xs space-y-1.5">
        <p className="font-semibold text-slate-700 mb-1.5">Legend</p>
        <div className="flex items-center gap-2">
          <span className="w-3 h-3 rounded-full bg-amber-500 border border-amber-600" />
          <span className="text-slate-600">Composites One</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-3 h-3 rounded-full bg-blue-500 border border-blue-600" />
          <span className="text-slate-600">Competitor</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-3 h-3 rounded-full bg-indigo-500" />
          <span className="text-slate-600">Supplier</span>
        </div>
      </div>

      {/* Zoom Controls */}
      <div className="absolute bottom-3 right-3 flex flex-col gap-1.5">
        <button
          onClick={handleZoomIn}
          className="p-2 bg-white/95 backdrop-blur-sm rounded-lg shadow-sm border border-slate-200 hover:bg-slate-50 transition-colors"
          title="Zoom In"
        >
          <ZoomIn size={16} className="text-slate-600" />
        </button>
        <button
          onClick={handleZoomOut}
          className="p-2 bg-white/95 backdrop-blur-sm rounded-lg shadow-sm border border-slate-200 hover:bg-slate-50 transition-colors"
          title="Zoom Out"
        >
          <ZoomOut size={16} className="text-slate-600" />
        </button>
        <button
          onClick={handleResetView}
          className="p-2 bg-white/95 backdrop-blur-sm rounded-lg shadow-sm border border-slate-200 hover:bg-slate-50 transition-colors"
          title="Fit to View"
        >
          <Maximize2 size={16} className="text-slate-600" />
        </button>
      </div>

      {/* Stats Badge */}
      <div className="absolute bottom-3 left-3 bg-white/95 backdrop-blur-sm px-3 py-1.5 rounded-lg shadow-sm border border-slate-200 text-xs text-slate-600">
        {data.stats.total_companies} companies &middot; {data.stats.total_suppliers} suppliers &middot; {data.stats.total_edges} relationships
      </div>
    </div>
  )
}
