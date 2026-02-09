'use client'

import { useState, useEffect } from 'react'
import dynamic from 'next/dynamic'
import { Network, AlertCircle, RefreshCw } from 'lucide-react'
import DetailPanel from './DetailPanel'
import { api } from '@/lib/api'
import type { GraphNode, GraphData } from './NetworkGraph'

// Dynamic import for ForceGraph2D (canvas-based, no SSR)
const NetworkGraph = dynamic(() => import('./NetworkGraph'), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full flex items-center justify-center bg-slate-50 rounded-xl border border-slate-200">
      <div className="text-center">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-indigo-500 mx-auto mb-3" />
        <p className="text-sm text-slate-500">Loading network graph...</p>
      </div>
    </div>
  ),
})

export default function SupplyNetworkDashboard() {
  const [graphData, setGraphData] = useState<GraphData | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null)

  useEffect(() => {
    loadGraph()
  }, [])

  const loadGraph = async () => {
    try {
      setIsLoading(true)
      setError(null)
      const data = await api.getSupplyNetworkGraph()
      setGraphData(data)
    } catch (err: any) {
      setError(err.message || 'Failed to load network graph')
    } finally {
      setIsLoading(false)
    }
  }

  const handleNodeClick = (node: GraphNode) => {
    setSelectedNode(node)
  }

  const handleCloseDetail = () => {
    setSelectedNode(null)
  }

  return (
    <div className="h-full flex flex-col overflow-hidden bg-slate-100">
      {/* Header */}
      <div className="shrink-0 px-6 py-4 bg-white border-b border-slate-200">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-indigo-100 flex items-center justify-center">
              <Network className="w-5 h-5 text-indigo-600" />
            </div>
            <div>
              <h1 className="text-lg font-semibold text-slate-800">Supply Network</h1>
              <p className="text-xs text-slate-500">
                C1 + 10 competitors &middot; Upstream supplier relationships
              </p>
            </div>
          </div>
          <button
            onClick={loadGraph}
            disabled={isLoading}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-600 bg-slate-100 rounded-lg hover:bg-slate-200 transition-colors disabled:opacity-50"
          >
            <RefreshCw size={14} className={isLoading ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>
      </div>

      {/* Main content: graph + detail panel */}
      <div className="flex-1 flex min-h-0 p-4 gap-4">
        {/* Graph panel (flexible width) */}
        <div className="flex-1 min-w-0 bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
          {error ? (
            <div className="w-full h-full flex items-center justify-center">
              <div className="text-center px-6">
                <AlertCircle className="w-10 h-10 text-red-400 mx-auto mb-3" />
                <p className="text-sm text-slate-700 font-medium mb-1">Failed to load graph</p>
                <p className="text-xs text-slate-500 mb-3">{error}</p>
                <button
                  onClick={loadGraph}
                  className="px-4 py-2 text-xs font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 transition-colors"
                >
                  Try Again
                </button>
              </div>
            </div>
          ) : graphData ? (
            <NetworkGraph
              data={graphData}
              onNodeClick={handleNodeClick}
              isLoading={isLoading}
            />
          ) : null}
        </div>

        {/* Detail panel (fixed width) */}
        <div className="w-[380px] shrink-0 bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
          <DetailPanel
            selectedNode={selectedNode}
            onClose={handleCloseDetail}
            stats={graphData?.stats ?? null}
          />
        </div>
      </div>
    </div>
  )
}
