'use client'

import { Building2, Package, Factory, MapPin } from 'lucide-react'
import { cn } from '@/lib/utils'

interface TrackedCompany {
  importyeti_key: string
  name: string
  entity_type: 'target' | 'competitor'
  ticker: string | null
  country: string
  category: string | null
  total_shipments: number
  supplier_count: number
  active_suppliers_12m: number
}

interface CompanyCardProps {
  company: TrackedCompany
  onClick: (company: TrackedCompany) => void
}

export type { TrackedCompany }

export default function CompanyCard({ company, onClick }: CompanyCardProps) {
  const isTarget = company.entity_type === 'target'

  return (
    <button
      onClick={() => onClick(company)}
      className={cn(
        'w-full text-left p-4 rounded-xl border transition-all duration-150',
        'hover:shadow-md hover:-translate-y-0.5 cursor-pointer',
        isTarget
          ? 'bg-amber-50/50 border-amber-200 hover:border-amber-300'
          : 'bg-white border-slate-200 hover:border-blue-300'
      )}
    >
      {/* Header: name + badge */}
      <div className="flex items-start justify-between gap-2 mb-3">
        <div className="flex items-center gap-2 min-w-0">
          <div
            className={cn(
              'w-8 h-8 rounded-lg flex items-center justify-center shrink-0',
              isTarget ? 'bg-amber-100' : 'bg-blue-100'
            )}
          >
            <Building2
              size={16}
              className={isTarget ? 'text-amber-600' : 'text-blue-600'}
            />
          </div>
          <h3 className="text-sm font-semibold text-slate-800 truncate">
            {company.name}
          </h3>
        </div>
        <span
          className={cn(
            'px-1.5 py-0.5 rounded text-[10px] font-medium shrink-0',
            isTarget
              ? 'bg-amber-100 text-amber-700'
              : 'bg-blue-100 text-blue-700'
          )}
        >
          {isTarget ? 'C1' : 'Competitor'}
        </span>
      </div>

      {/* Meta row */}
      <div className="flex items-center gap-3 text-[11px] text-slate-500 mb-3">
        {company.country && (
          <span className="flex items-center gap-1">
            <MapPin size={10} />
            {company.country}
          </span>
        )}
        {company.ticker && (
          <span className="px-1 py-0.5 bg-slate-100 text-slate-600 rounded text-[10px] font-medium">
            {company.ticker}
          </span>
        )}
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-2 gap-2">
        <div className="flex items-center gap-1.5 text-xs text-slate-600">
          <Factory size={12} className="text-indigo-500" />
          <span>
            <span className="font-semibold">{company.supplier_count}</span>{' '}
            <span className="text-slate-400">suppliers</span>
          </span>
        </div>
        <div className="flex items-center gap-1.5 text-xs text-slate-600">
          <Package size={12} className="text-emerald-500" />
          <span>
            <span className="font-semibold">
              {company.total_shipments?.toLocaleString() ?? '—'}
            </span>{' '}
            <span className="text-slate-400">total</span>
          </span>
        </div>
      </div>

      {/* Active 12m indicator */}
      {company.active_suppliers_12m > 0 && (
        <div className="mt-2 text-[10px] text-slate-400">
          {company.active_suppliers_12m} active in last 12 months
        </div>
      )}
    </button>
  )
}
