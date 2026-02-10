'use client'

import { ChevronDown, ChevronRight } from 'lucide-react'

interface SectionHeaderProps {
  letter: string
  title: string
  description: string
  color: string // tailwind color name e.g. 'blue', 'amber', 'emerald'
  isExpanded?: boolean
  onToggle?: () => void
}

const colorMap: Record<string, { bg: string; border: string; text: string; badge: string }> = {
  blue: { bg: 'bg-blue-50', border: 'border-blue-200', text: 'text-blue-700', badge: 'bg-blue-100 text-blue-600' },
  amber: { bg: 'bg-amber-50', border: 'border-amber-200', text: 'text-amber-700', badge: 'bg-amber-100 text-amber-600' },
  emerald: { bg: 'bg-emerald-50', border: 'border-emerald-200', text: 'text-emerald-700', badge: 'bg-emerald-100 text-emerald-600' },
  violet: { bg: 'bg-violet-50', border: 'border-violet-200', text: 'text-violet-700', badge: 'bg-violet-100 text-violet-600' },
  sky: { bg: 'bg-sky-50', border: 'border-sky-200', text: 'text-sky-700', badge: 'bg-sky-100 text-sky-600' },
  orange: { bg: 'bg-orange-50', border: 'border-orange-200', text: 'text-orange-700', badge: 'bg-orange-100 text-orange-600' },
  indigo: { bg: 'bg-indigo-50', border: 'border-indigo-200', text: 'text-indigo-700', badge: 'bg-indigo-100 text-indigo-600' },
}

export default function SectionHeader({
  letter,
  title,
  description,
  color,
  isExpanded = true,
  onToggle,
}: SectionHeaderProps) {
  const colors = colorMap[color] || colorMap.blue

  return (
    <button
      onClick={onToggle}
      className={`w-full flex items-center gap-3 px-4 py-2.5 ${colors.bg} border ${colors.border} rounded-lg transition-colors hover:opacity-90`}
    >
      <span className={`text-xs font-bold px-2 py-0.5 rounded ${colors.badge}`}>
        {letter}
      </span>
      <span className={`text-sm font-semibold ${colors.text}`}>{title}</span>
      <span className="text-xs text-slate-500 hidden sm:inline">— {description}</span>
      <div className="ml-auto">
        {isExpanded ? (
          <ChevronDown className={`w-4 h-4 ${colors.text}`} />
        ) : (
          <ChevronRight className={`w-4 h-4 ${colors.text}`} />
        )}
      </div>
    </button>
  )
}
