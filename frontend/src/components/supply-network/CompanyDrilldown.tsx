'use client'

import { useEffect, useState } from 'react'
import {
  ArrowLeft,
  MapPin,
  Package,
  Loader2,
  Factory,
  Truck,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { api } from '@/lib/api'
import type { TrackedCompany } from './CompanyCard'
import CompanyLogo from '@/components/pipeline/CompanyLogo'
import IntelligencePanel from './IntelligencePanel'

interface CompanyDrilldownProps {
  company: TrackedCompany
  onBack: () => void
}

type TableView = 'suppliers' | 'customers'

interface CompanyDetail {
  company: Record<string, any>
  suppliers: Array<Record<string, any>>
  supplier_count: number
  customers: Array<Record<string, any>>
  customer_count: number
}

export default function CompanyDrilldown({ company, onBack }: CompanyDrilldownProps) {
  const [detail, setDetail] = useState<CompanyDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [tableView, setTableView] = useState<TableView>('suppliers')

  useEffect(() => {
    let cancelled = false
    const fetchDetail = async () => {
      setLoading(true)
      setError(null)
      try {
        const data = await api.getCompanyDetail(company.importyeti_key)
        if (!cancelled) setDetail(data)
      } catch (err: any) {
        if (!cancelled) setError(err.message || 'Failed to load details')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    fetchDetail()
    return () => { cancelled = true }
  }, [company.importyeti_key])

  const isTarget = company.entity_type === 'target'

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="shrink-0 px-6 py-4 bg-white border-b border-slate-200">
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="p-1.5 rounded-lg hover:bg-slate-100 transition-colors"
          >
            <ArrowLeft size={18} className="text-slate-500" />
          </button>
          <CompanyLogo domain={company.website} size={36} />
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-semibold text-slate-800 truncate">{company.name}</h2>
              <span
                className={cn(
                  'px-1.5 py-0.5 rounded text-[10px] font-medium shrink-0',
                  isTarget ? 'bg-amber-100 text-amber-700' : 'bg-blue-100 text-blue-700'
                )}
              >
                {isTarget ? 'C1' : 'Competitor'}
              </span>
            </div>
            <div className="flex items-center gap-3 text-xs text-slate-500">
              {company.country && (
                <span className="flex items-center gap-1">
                  <MapPin size={11} />
                  {company.country}
                </span>
              )}
              {company.ticker && (
                <span className="px-1 py-0.5 bg-slate-100 text-slate-600 rounded text-[10px] font-medium">
                  {company.ticker}
                </span>
              )}
              {company.total_shipments != null && (
                <span className="flex items-center gap-1">
                  <Package size={11} />
                  {company.total_shipments.toLocaleString()} total shipments
                </span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Main content: table + intelligence */}
      <div className="flex-1 flex min-h-0 p-4 gap-4 overflow-hidden">
        {/* Table panel (left) */}
        <div className="flex-1 min-w-0 bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden flex flex-col">
          {/* Toggle header */}
          <div className="px-5 py-3 border-b border-slate-100 shrink-0">
            <div className="flex items-center gap-1 bg-slate-100 rounded-lg p-0.5 w-fit">
              <button
                onClick={() => setTableView('suppliers')}
                className={cn(
                  'flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded-md transition-colors',
                  tableView === 'suppliers'
                    ? 'bg-white text-slate-800 shadow-sm'
                    : 'text-slate-500 hover:text-slate-700'
                )}
              >
                <Factory size={12} />
                Suppliers
                {detail && (
                  <span className="text-slate-400 font-normal">({detail.supplier_count})</span>
                )}
              </button>
              <button
                onClick={() => setTableView('customers')}
                className={cn(
                  'flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded-md transition-colors',
                  tableView === 'customers'
                    ? 'bg-white text-slate-800 shadow-sm'
                    : 'text-slate-500 hover:text-slate-700'
                )}
              >
                <Truck size={12} />
                Customers
                {detail && (
                  <span className="text-slate-400 font-normal">({detail.customer_count})</span>
                )}
              </button>
            </div>
          </div>

          {/* Table content */}
          <div className="flex-1 overflow-auto">
            {loading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="w-6 h-6 animate-spin text-indigo-500" />
              </div>
            ) : error ? (
              <div className="text-center py-12">
                <p className="text-sm text-red-500">{error}</p>
                <button onClick={onBack} className="text-xs text-slate-500 hover:text-slate-700 underline mt-2">
                  Go back
                </button>
              </div>
            ) : tableView === 'suppliers' ? (
              <SupplierTable suppliers={detail?.suppliers || []} />
            ) : (
              <CustomerTable customers={detail?.customers || []} />
            )}
          </div>
        </div>

        {/* Intelligence panel (right) */}
        <div className="w-[340px] shrink-0 bg-white rounded-xl shadow-sm border border-slate-200 overflow-auto p-4">
          <IntelligencePanel
            importyetiKey={company.importyeti_key}
            companyName={company.name}
          />
        </div>
      </div>
    </div>
  )
}

function SupplierTable({ suppliers }: { suppliers: Array<Record<string, any>> }) {
  if (suppliers.length === 0) {
    return (
      <div className="text-center py-12">
        <Factory size={32} className="mx-auto text-slate-300 mb-2" />
        <p className="text-xs text-slate-400">No suppliers found in cache</p>
      </div>
    )
  }

  return (
    <table className="w-full text-xs">
      <thead className="bg-slate-50 text-slate-500 uppercase sticky top-0">
        <tr>
          <th className="px-4 py-2.5 text-left font-medium">Supplier</th>
          <th className="px-4 py-2.5 text-left font-medium">Country</th>
          <th className="px-4 py-2.5 text-right font-medium">12m Shipments</th>
          <th className="px-4 py-2.5 text-right font-medium">Total</th>
          <th className="px-4 py-2.5 text-right font-medium">% of Imports</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-slate-50">
        {suppliers.map((s, i) => (
          <tr key={i} className="hover:bg-slate-50/50 transition-colors">
            <td className="px-4 py-2.5 font-medium text-slate-800">
              {s.supplier_name || s.name || 'Unknown'}
            </td>
            <td className="px-4 py-2.5 text-slate-500">
              {s.supplier_country || s.country || '—'}
            </td>
            <td className="px-4 py-2.5 text-right text-slate-600">
              {s.shipments_12m ?? '—'}
            </td>
            <td className="px-4 py-2.5 text-right text-slate-600">
              {s.total_shipments?.toLocaleString() ?? '—'}
            </td>
            <td className="px-4 py-2.5 text-right text-slate-600">
              {formatPct(s.shipment_pct_of_source)}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function CustomerTable({ customers }: { customers: Array<Record<string, any>> }) {
  if (customers.length === 0) {
    return (
      <div className="text-center py-12">
        <Truck size={32} className="mx-auto text-slate-300 mb-2" />
        <p className="text-xs text-slate-400">No customer shipment data found</p>
      </div>
    )
  }

  return (
    <table className="w-full text-xs">
      <thead className="bg-slate-50 text-slate-500 uppercase sticky top-0">
        <tr>
          <th className="px-4 py-2.5 text-left font-medium">Customer</th>
          <th className="px-4 py-2.5 text-left font-medium">Country</th>
          <th className="px-4 py-2.5 text-left font-medium">Type</th>
          <th className="px-4 py-2.5 text-right font-medium">12m Shipments</th>
          <th className="px-4 py-2.5 text-right font-medium">Total</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-slate-50">
        {customers.map((c, i) => (
          <tr key={i} className="hover:bg-slate-50/50 transition-colors">
            <td className="px-4 py-2.5 font-medium text-slate-800">
              {c.customer_name || c.name || 'Unknown'}
            </td>
            <td className="px-4 py-2.5 text-slate-500">
              {c.customer_country || c.country || '—'}
            </td>
            <td className="px-4 py-2.5">
              {c.customer_entity_type && (
                <span className={cn(
                  'px-1.5 py-0.5 rounded text-[10px] font-medium',
                  c.customer_entity_type === 'target' ? 'bg-amber-100 text-amber-700' :
                  c.customer_entity_type === 'competitor' ? 'bg-blue-100 text-blue-700' :
                  'bg-slate-100 text-slate-500'
                )}>
                  {c.customer_entity_type === 'target' ? 'C1' :
                   c.customer_entity_type === 'competitor' ? 'Competitor' :
                   'Discovered'}
                </span>
              )}
            </td>
            <td className="px-4 py-2.5 text-right text-slate-600">
              {c.shipments_12m ?? '—'}
            </td>
            <td className="px-4 py-2.5 text-right text-slate-600">
              {c.total_shipments?.toLocaleString() ?? '—'}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function formatPct(value: any): string {
  if (value == null) return '—'
  const num = typeof value === 'string' ? parseFloat(value) : value
  if (isNaN(num)) return '—'
  return `${num.toFixed(1)}%`
}
