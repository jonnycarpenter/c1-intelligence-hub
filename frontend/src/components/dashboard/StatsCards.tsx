'use client'

import { AlertTriangle, TrendingUp, Building2, Newspaper } from 'lucide-react'
import { cn } from '@/lib/utils'

interface StatCard {
  label: string
  value: string | number
  icon: React.ElementType
  color: string
  bgColor: string
}

interface StatsCardsProps {
  stats?: {
    criticalAlerts: number
    priceMovements: number
    companiesMonitored: number
    newsItems: number
  }
}

export default function StatsCards({ stats }: StatsCardsProps) {
  const defaultStats = {
    criticalAlerts: 0,
    priceMovements: 0,
    companiesMonitored: 0,
    newsItems: 0,
  }

  const s = stats || defaultStats

  const cards: StatCard[] = [
    {
      label: 'Critical Alerts',
      value: s.criticalAlerts,
      icon: AlertTriangle,
      color: 'text-red-600',
      bgColor: 'bg-red-50',
    },
    {
      label: 'Price Movements',
      value: s.priceMovements,
      icon: TrendingUp,
      color: 'text-emerald-600',
      bgColor: 'bg-emerald-50',
    },
    {
      label: 'Companies Tracked',
      value: s.companiesMonitored,
      icon: Building2,
      color: 'text-blue-600',
      bgColor: 'bg-blue-50',
    },
    {
      label: 'News Items',
      value: s.newsItems,
      icon: Newspaper,
      color: 'text-emerald-600',
      bgColor: 'bg-emerald-50',
    },
  ]

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {cards.map((card, idx) => {
        const Icon = card.icon
        return (
          <div
            key={idx}
            className="bg-white rounded-xl border border-slate-200 p-4 hover:shadow-sm transition-shadow"
          >
            <div className="flex items-center justify-between mb-3">
              <div className={cn('w-10 h-10 rounded-lg flex items-center justify-center', card.bgColor)}>
                <Icon size={20} className={card.color} />
              </div>
            </div>
            <div className="text-2xl font-bold text-slate-900">{card.value}</div>
            <div className="text-sm text-slate-500">{card.label}</div>
          </div>
        )
      })}
    </div>
  )
}
