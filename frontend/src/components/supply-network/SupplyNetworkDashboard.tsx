'use client'

import { useState, useEffect } from 'react'
import dynamic from 'next/dynamic'
import { Network, AlertCircle, RefreshCw, Search, Loader2, Building2 } from 'lucide-react'
import DetailPanel from './DetailPanel'
import CompanyCard from './CompanyCard'
import CompanyDrilldown from './CompanyDrilldown'
import SupplyChainSearch from './SupplyChainSearch'
import { api } from '@/lib/api'
import { cn } from '@/lib/utils'
import type { GraphNode, GraphData } from './NetworkGraph'
import type { TrackedCompany } from './CompanyCard'

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

type ActiveTab = 'directory' | 'network-map'

export default function SupplyNetworkDashboard() {
  const [activeTab, setActiveTab] = useState<ActiveTab>('directory')

  // Directory state
  const [companies, setCompanies] = useState<TrackedCompany[]>([])
  const [companiesLoading, setCompaniesLoading] = useState(true)
  const [companiesError, setCompaniesError] = useState<string | null>(null)
  const [lastUpdated, setLastUpdated] = useState<string | null>(null)
  const [selectedCompany, setSelectedCompany] = useState<TrackedCompany | null>(null)
  const [searchActive, setSearchActive] = useState(false)

  // Network map state (lazy-loaded)
  const [graphData, setGraphData] = useState<GraphData | null>(null)
  const [graphLoading, setGraphLoading] = useState(false)
  const [graphError, setGraphError] = useState<string | null>(null)
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null)

  // Load companies on mount
  useEffect(() => {
    loadCompanies()
  }, [])

  const loadCompanies = async () => {
    try {
      setCompaniesLoading(true)
      setCompaniesError(null)
      const data = await api.getTrackedCompanies()
      setCompanies(data.companies)
      setLastUpdated(data.last_updated)
    } catch (err: any) {
      setCompaniesError(err.message || 'Failed to load companies')
    } finally {
      setCompaniesLoading(false)
    }
  }

  // Lazy-load graph when switching to network-map tab
  const loadGraph = async () => {
    if (graphData && !graphLoading) return // Already loaded
    try {
      setGraphLoading(true)
      setGraphError(null)
      const data = await api.getSupplyNetworkGraph()
      setGraphData(data)
    } catch (err: any) {
      setGraphError(err.message || 'Failed to load network graph')
    } finally {
      setGraphLoading(false)
    }
  }

  const handleTabChange = (tab: ActiveTab) => {
    setActiveTab(tab)
    if (tab === 'network-map') {
      loadGraph()
    }
  }

  const handleCompanyClick = (company: TrackedCompany) => {
    setSelectedCompany(company)
    setSearchActive(false)
  }

  const handleBackToDirectory = () => {
    setSelectedCompany(null)
  }

  // If a company is selected, show drill-down (full-screen within tab)
  if (activeTab === 'directory' && selectedCompany) {
    return (
      <div className="h-full flex flex-col overflow-hidden bg-slate-100">
        <CompanyDrilldown
          company={selectedCompany}
          onBack={handleBackToDirectory}
        />
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col overflow-hidden bg-slate-100">
      {/* Header with tabs */}
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
                {lastUpdated && (
                  <span> &middot; Last updated {new Date(lastUpdated).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}</span>
                )}
              </p>
            </div>
          </div>

          {/* Tab toggle */}
          <div className="flex items-center gap-1 bg-slate-100 rounded-lg p-1">
            <button
              onClick={() => handleTabChange('directory')}
              className={cn(
                'px-3 py-1.5 text-xs font-medium rounded-md transition-colors',
                activeTab === 'directory'
                  ? 'bg-white text-slate-800 shadow-sm'
                  : 'text-slate-500 hover:text-slate-700'
              )}
            >
              <span className="flex items-center gap-1.5">
                <Building2 size={13} />
                Directory
              </span>
            </button>
            <button
              onClick={() => handleTabChange('network-map')}
              className={cn(
                'px-3 py-1.5 text-xs font-medium rounded-md transition-colors',
                activeTab === 'network-map'
                  ? 'bg-white text-slate-800 shadow-sm'
                  : 'text-slate-500 hover:text-slate-700'
              )}
            >
              <span className="flex items-center gap-1.5">
                <Network size={13} />
                Network Map
                <span className="px-1 py-0.5 bg-amber-100 text-amber-700 rounded text-[9px] font-semibold">
                  BETA
                </span>
              </span>
            </button>
          </div>
        </div>
      </div>

      {/* Tab content */}
      {activeTab === 'directory' ? (
        <DirectoryView
          companies={companies}
          loading={companiesLoading}
          error={companiesError}
          searchActive={searchActive}
          onSearchActivate={() => setSearchActive(true)}
          onSearchDeactivate={() => setSearchActive(false)}
          onCompanyClick={handleCompanyClick}
          onRetry={loadCompanies}
        />
      ) : (
        <NetworkMapView
          graphData={graphData}
          loading={graphLoading}
          error={graphError}
          selectedNode={selectedNode}
          onNodeClick={setSelectedNode}
          onCloseDetail={() => setSelectedNode(null)}
          onRetry={loadGraph}
        />
      )}
    </div>
  )
}

// ─── Directory View ─────────────────────────────────────

function DirectoryView({
  companies,
  loading,
  error,
  searchActive,
  onSearchActivate,
  onSearchDeactivate,
  onCompanyClick,
  onRetry,
}: {
  companies: TrackedCompany[]
  loading: boolean
  error: string | null
  searchActive: boolean
  onSearchActivate: () => void
  onSearchDeactivate: () => void
  onCompanyClick: (company: TrackedCompany) => void
  onRetry: () => void
}) {
  return (
    <div className="flex-1 overflow-auto p-4 space-y-4">
      {/* Search bar */}
      <SupplyChainSearch
        onActivate={onSearchActivate}
        onDeactivate={onSearchDeactivate}
      />

      {/* Company cards grid */}
      {!searchActive && (
        <>
          {loading ? (
            <div className="flex items-center justify-center py-16">
              <div className="text-center">
                <Loader2 className="w-8 h-8 animate-spin text-indigo-500 mx-auto mb-3" />
                <p className="text-sm text-slate-500">Loading companies...</p>
              </div>
            </div>
          ) : error ? (
            <div className="flex items-center justify-center py-16">
              <div className="text-center">
                <AlertCircle className="w-10 h-10 text-red-400 mx-auto mb-3" />
                <p className="text-sm text-slate-700 font-medium mb-1">Failed to load companies</p>
                <p className="text-xs text-slate-500 mb-3">{error}</p>
                <button
                  onClick={onRetry}
                  className="px-4 py-2 text-xs font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 transition-colors"
                >
                  Try Again
                </button>
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
              {companies.map((company) => (
                <CompanyCard
                  key={company.importyeti_key}
                  company={company}
                  onClick={onCompanyClick}
                />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}

// ─── Network Map View ───────────────────────────────────

function NetworkMapView({
  graphData,
  loading,
  error,
  selectedNode,
  onNodeClick,
  onCloseDetail,
  onRetry,
}: {
  graphData: GraphData | null
  loading: boolean
  error: string | null
  selectedNode: GraphNode | null
  onNodeClick: (node: GraphNode) => void
  onCloseDetail: () => void
  onRetry: () => void
}) {
  return (
    <div className="flex-1 flex min-h-0 p-4 gap-4">
      {/* Graph panel */}
      <div className="flex-1 min-w-0 bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        {loading ? (
          <div className="w-full h-full flex items-center justify-center">
            <div className="text-center">
              <Loader2 className="w-8 h-8 animate-spin text-indigo-500 mx-auto mb-3" />
              <p className="text-sm text-slate-500">Loading network graph...</p>
            </div>
          </div>
        ) : error ? (
          <div className="w-full h-full flex items-center justify-center">
            <div className="text-center px-6">
              <AlertCircle className="w-10 h-10 text-red-400 mx-auto mb-3" />
              <p className="text-sm text-slate-700 font-medium mb-1">Failed to load graph</p>
              <p className="text-xs text-slate-500 mb-3">{error}</p>
              <button
                onClick={onRetry}
                className="px-4 py-2 text-xs font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 transition-colors"
              >
                Try Again
              </button>
            </div>
          </div>
        ) : graphData ? (
          <NetworkGraph
            data={graphData}
            onNodeClick={onNodeClick}
            isLoading={loading}
          />
        ) : null}
      </div>

      {/* Detail panel */}
      <div className="w-[380px] shrink-0 bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        <DetailPanel
          selectedNode={selectedNode}
          onClose={onCloseDetail}
          stats={graphData?.stats ?? null}
        />
      </div>
    </div>
  )
}
