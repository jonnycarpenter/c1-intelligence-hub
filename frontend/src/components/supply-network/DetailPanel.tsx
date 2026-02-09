'use client'

import { useEffect, useState } from 'react'
import {
  Building2,
  Factory,
  Ship,
  MapPin,
  Package,
  X,
  Loader2,
  ExternalLink,
  Users,
  ArrowUpRight,
  Globe,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { api } from '@/lib/api'
import type { GraphNode } from './NetworkGraph'

interface DetailPanelProps {
  selectedNode: GraphNode | null
  onClose: () => void
  stats: {
    total_companies: number
    total_suppliers: number
    total_edges: number
  } | null
}

interface CompanyDetail {
  company: Record<string, any>
  suppliers: Array<Record<string, any>>
  supplier_count: number
}

interface SupplierDetail {
  supplier: Record<string, any>
  buyers: Array<Record<string, any>>
  buyer_count: number
}

export default function DetailPanel({ selectedNode, onClose, stats }: DetailPanelProps) {
  const [companyDetail, setCompanyDetail] = useState<CompanyDetail | null>(null)
  const [supplierDetail, setSupplierDetail] = useState<SupplierDetail | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Fetch detail when a node is selected
  useEffect(() => {
    if (!selectedNode) {
      setCompanyDetail(null)
      setSupplierDetail(null)
      return
    }

    const fetchDetail = async () => {
      setLoading(true)
      setError(null)
      setCompanyDetail(null)
      setSupplierDetail(null)

      try {
        if (selectedNode.type === 'company') {
          const data = await api.getCompanyDetail(selectedNode.id)
          setCompanyDetail(data)
        } else {
          const data = await api.getSupplierDetail(selectedNode.id)
          setSupplierDetail(data)
        }
      } catch (err: any) {
        setError(err.message || 'Failed to load details')
      } finally {
        setLoading(false)
      }
    }

    fetchDetail()
  }, [selectedNode])

  // Default view: summary stats
  if (!selectedNode) {
    return (
      <div className="h-full flex flex-col">
        <div className="shrink-0 px-5 py-4 border-b border-slate-200">
          <h2 className="text-base font-semibold text-slate-800">Network Overview</h2>
          <p className="text-xs text-slate-500 mt-0.5">Click a node on the graph to drill down</p>
        </div>

        <div className="flex-1 overflow-auto p-5 space-y-4">
          {stats && (
            <div className="grid grid-cols-3 gap-3">
              <StatCard
                label="Companies"
                value={stats.total_companies}
                icon={Building2}
                color="text-blue-600"
                bg="bg-blue-50"
              />
              <StatCard
                label="Suppliers"
                value={stats.total_suppliers}
                icon={Factory}
                color="text-indigo-600"
                bg="bg-indigo-50"
              />
              <StatCard
                label="Relationships"
                value={stats.total_edges}
                icon={ArrowUpRight}
                color="text-emerald-600"
                bg="bg-emerald-50"
              />
            </div>
          )}

          <div className="bg-slate-50 rounded-xl p-4 border border-slate-200">
            <h3 className="text-sm font-medium text-slate-700 mb-2">How to use</h3>
            <ul className="text-xs text-slate-500 space-y-1.5">
              <li className="flex items-start gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-amber-500 mt-1 shrink-0" />
                Gold nodes are Composites One (C1)
              </li>
              <li className="flex items-start gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-blue-500 mt-1 shrink-0" />
                Blue nodes are tracked competitors
              </li>
              <li className="flex items-start gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-indigo-500 mt-1 shrink-0" />
                Indigo nodes are upstream suppliers
              </li>
              <li className="flex items-start gap-2">
                <span className="text-slate-400 mt-0.5 shrink-0">Click</span>
                any node to see its supplier or buyer breakdown
              </li>
            </ul>
          </div>
        </div>
      </div>
    )
  }

  // Loading state
  if (loading) {
    return (
      <div className="h-full flex flex-col">
        <DetailHeader node={selectedNode} onClose={onClose} />
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <Loader2 className="w-8 h-8 animate-spin text-indigo-500 mx-auto mb-2" />
            <p className="text-sm text-slate-500">Loading details...</p>
          </div>
        </div>
      </div>
    )
  }

  // Error state
  if (error) {
    return (
      <div className="h-full flex flex-col">
        <DetailHeader node={selectedNode} onClose={onClose} />
        <div className="flex-1 flex items-center justify-center p-6">
          <div className="text-center">
            <p className="text-sm text-red-600 mb-2">{error}</p>
            <button
              onClick={onClose}
              className="text-xs text-slate-500 hover:text-slate-700 underline"
            >
              Go back
            </button>
          </div>
        </div>
      </div>
    )
  }

  // Company detail view
  if (companyDetail) {
    return (
      <div className="h-full flex flex-col">
        <DetailHeader node={selectedNode} onClose={onClose} />
        <div className="flex-1 overflow-auto">
          {/* Profile */}
          <div className="px-5 py-4 border-b border-slate-100">
            <div className="flex items-center gap-2 text-xs text-slate-500">
              {companyDetail.company.country && (
                <span className="flex items-center gap-1">
                  <MapPin size={12} />
                  {companyDetail.company.country}
                </span>
              )}
              {companyDetail.company.ticker && (
                <span className="px-1.5 py-0.5 bg-blue-50 text-blue-700 rounded text-[10px] font-medium">
                  {companyDetail.company.ticker}
                </span>
              )}
              {companyDetail.company.total_shipments != null && (
                <span className="flex items-center gap-1">
                  <Package size={12} />
                  {companyDetail.company.total_shipments.toLocaleString()} shipments
                </span>
              )}
            </div>
          </div>

          {/* Supplier table */}
          <div className="px-5 py-3">
            <h3 className="text-sm font-medium text-slate-700 mb-2">
              Suppliers ({companyDetail.supplier_count})
            </h3>
            {companyDetail.suppliers.length > 0 ? (
              <div className="border border-slate-200 rounded-lg overflow-hidden">
                <table className="w-full text-xs">
                  <thead className="bg-slate-50 text-slate-500 uppercase">
                    <tr>
                      <th className="px-3 py-2 text-left font-medium">Supplier</th>
                      <th className="px-3 py-2 text-left font-medium">Country</th>
                      <th className="px-3 py-2 text-right font-medium">12m</th>
                      <th className="px-3 py-2 text-right font-medium">%</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {companyDetail.suppliers.map((s, i) => (
                      <tr key={i} className="hover:bg-slate-50 transition-colors">
                        <td className="px-3 py-2 font-medium text-slate-800">
                          {s.supplier_name || s.name || 'Unknown'}
                        </td>
                        <td className="px-3 py-2 text-slate-500">
                          {s.supplier_country || s.country || '-'}
                        </td>
                        <td className="px-3 py-2 text-right text-slate-600">
                          {s.shipments_12m ?? '-'}
                        </td>
                        <td className="px-3 py-2 text-right text-slate-600">
                          {formatPct(s.shipment_pct_of_source)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-xs text-slate-400 py-4 text-center">No suppliers found in cache</p>
            )}
          </div>
        </div>
      </div>
    )
  }

  // Supplier detail view
  if (supplierDetail) {
    return (
      <div className="h-full flex flex-col">
        <DetailHeader node={selectedNode} onClose={onClose} />
        <div className="flex-1 overflow-auto">
          {/* Profile */}
          <div className="px-5 py-4 border-b border-slate-100">
            <div className="flex items-center gap-2 text-xs text-slate-500">
              {supplierDetail.supplier.country && (
                <span className="flex items-center gap-1">
                  <Globe size={12} />
                  {supplierDetail.supplier.country}
                </span>
              )}
              {supplierDetail.supplier.total_shipments != null && (
                <span className="flex items-center gap-1">
                  <Package size={12} />
                  {supplierDetail.supplier.total_shipments.toLocaleString()} shipments
                </span>
              )}
            </div>
          </div>

          {/* Buyer table */}
          <div className="px-5 py-3">
            <h3 className="text-sm font-medium text-slate-700 mb-2">
              Buyers ({supplierDetail.buyer_count})
            </h3>
            {supplierDetail.buyers.length > 0 ? (
              <div className="border border-slate-200 rounded-lg overflow-hidden">
                <table className="w-full text-xs">
                  <thead className="bg-slate-50 text-slate-500 uppercase">
                    <tr>
                      <th className="px-3 py-2 text-left font-medium">Buyer</th>
                      <th className="px-3 py-2 text-left font-medium">Type</th>
                      <th className="px-3 py-2 text-right font-medium">12m</th>
                      <th className="px-3 py-2 text-right font-medium">%</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {supplierDetail.buyers.map((b, i) => (
                      <tr key={i} className="hover:bg-slate-50 transition-colors">
                        <td className="px-3 py-2 font-medium text-slate-800">
                          {b.buyer_name || b.name || 'Unknown'}
                        </td>
                        <td className="px-3 py-2">
                          <EntityTypeBadge type={b.buyer_entity_type} />
                        </td>
                        <td className="px-3 py-2 text-right text-slate-600">
                          {b.shipments_12m ?? '-'}
                        </td>
                        <td className="px-3 py-2 text-right text-slate-600">
                          {formatPct(b.shipment_pct_of_source || b.shipment_pct_of_target)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-xs text-slate-400 py-4 text-center">No buyers found in cache</p>
            )}
          </div>
        </div>
      </div>
    )
  }

  return null
}

// ── Sub-components ──────────────────────────────────────

function DetailHeader({ node, onClose }: { node: GraphNode; onClose: () => void }) {
  const isCompany = node.type === 'company'
  const Icon = isCompany ? Building2 : Factory

  return (
    <div className="shrink-0 px-5 py-4 border-b border-slate-200 flex items-center justify-between">
      <div className="flex items-center gap-3 min-w-0">
        <div
          className={cn(
            'w-9 h-9 rounded-lg flex items-center justify-center shrink-0',
            node.entity_type === 'target'
              ? 'bg-amber-50'
              : node.entity_type === 'competitor'
                ? 'bg-blue-50'
                : 'bg-indigo-50'
          )}
        >
          <Icon
            size={18}
            className={
              node.entity_type === 'target'
                ? 'text-amber-600'
                : node.entity_type === 'competitor'
                  ? 'text-blue-600'
                  : 'text-indigo-600'
            }
          />
        </div>
        <div className="min-w-0">
          <h2 className="text-sm font-semibold text-slate-800 truncate">{node.label}</h2>
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] text-slate-400 uppercase">
              {isCompany ? 'Company' : 'Supplier'}
            </span>
            {node.entity_type && node.entity_type !== 'discovered' && (
              <EntityTypeBadge type={node.entity_type} />
            )}
          </div>
        </div>
      </div>
      <button
        onClick={onClose}
        className="p-1.5 rounded-lg hover:bg-slate-100 transition-colors shrink-0"
      >
        <X size={16} className="text-slate-400" />
      </button>
    </div>
  )
}

function StatCard({
  label,
  value,
  icon: Icon,
  color,
  bg,
}: {
  label: string
  value: number
  icon: typeof Building2
  color: string
  bg: string
}) {
  return (
    <div className="bg-white p-3 rounded-lg border border-slate-200">
      <div className={cn('w-8 h-8 rounded-lg flex items-center justify-center mb-2', bg)}>
        <Icon size={16} className={color} />
      </div>
      <p className="text-lg font-bold text-slate-800">{value.toLocaleString()}</p>
      <p className="text-[10px] text-slate-500 uppercase tracking-wider">{label}</p>
    </div>
  )
}

function EntityTypeBadge({ type }: { type?: string }) {
  if (!type || type === 'discovered') {
    return <span className="px-1.5 py-0.5 bg-slate-100 text-slate-500 rounded text-[10px]">Discovered</span>
  }
  if (type === 'target') {
    return <span className="px-1.5 py-0.5 bg-amber-100 text-amber-700 rounded text-[10px] font-medium">C1</span>
  }
  if (type === 'competitor') {
    return <span className="px-1.5 py-0.5 bg-blue-100 text-blue-700 rounded text-[10px] font-medium">Competitor</span>
  }
  return null
}

function formatPct(value: any): string {
  if (value == null) return '-'
  const num = typeof value === 'string' ? parseFloat(value) : value
  if (isNaN(num)) return '-'
  return `${num.toFixed(1)}%`
}
