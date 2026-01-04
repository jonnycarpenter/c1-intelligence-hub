'use client'

import { cn } from '@/lib/utils'

type BadgeVariant = 'default' | 'danger' | 'warning' | 'success' | 'info' | 'accent' | 'purple'

interface BadgeProps {
  children: React.ReactNode
  variant?: BadgeVariant
  className?: string
}

const variantStyles: Record<BadgeVariant, string> = {
  default: 'bg-slate-100 text-slate-600 border-slate-200',
  danger: 'bg-red-50 text-red-700 border-red-200',
  warning: 'bg-amber-50 text-amber-700 border-amber-200',
  success: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  info: 'bg-blue-50 text-blue-700 border-blue-200',
  accent: 'bg-amber-50 text-amber-700 border-amber-200',
  purple: 'bg-purple-50 text-purple-700 border-purple-200',
}

export function Badge({ children, variant = 'default', className }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center px-2 py-0.5 text-xs font-medium rounded-full border',
        variantStyles[variant],
        className
      )}
    >
      {children}
    </span>
  )
}

// Priority Badge
interface PriorityBadgeProps {
  priority: 'critical' | 'high' | 'medium' | 'low' | string | undefined
}

const priorityConfig: Record<string, { variant: BadgeVariant; label: string; dot: string }> = {
  critical: { variant: 'danger' as BadgeVariant, label: 'Critical', dot: 'bg-red-600' },
  high: { variant: 'danger' as BadgeVariant, label: 'High', dot: 'bg-red-500' },
  medium: { variant: 'warning' as BadgeVariant, label: 'Medium', dot: 'bg-amber-500' },
  low: { variant: 'default' as BadgeVariant, label: 'Low', dot: 'bg-slate-400' },
}

export function PriorityBadge({ priority }: PriorityBadgeProps) {
  const config = (priority && priorityConfig[priority]) || priorityConfig.medium  // Fallback to medium
  const { variant, label, dot } = config
  return (
    <Badge variant={variant} className="gap-1.5">
      <span className={cn('w-1.5 h-1.5 rounded-full', dot)} />
      {label}
    </Badge>
  )
}

// Category Badge
interface CategoryBadgeProps {
  category: string
}

const categoryConfig: Record<string, { variant: BadgeVariant; label: string }> = {
  'market': { variant: 'success', label: 'Market' },
  'supply-chain': { variant: 'info', label: 'Supply Chain' },
  'supply_chain': { variant: 'info', label: 'Supply Chain' },
  'regulatory': { variant: 'warning', label: 'Regulatory' },
  'competitor': { variant: 'info', label: 'Competitor' },
  'pricing': { variant: 'accent', label: 'Pricing' },
  'product': { variant: 'accent', label: 'Product' },
  'priority': { variant: 'danger', label: 'Priority' },
  'industry': { variant: 'purple', label: 'Industry' },
  'logistics': { variant: 'info', label: 'Logistics' },
  'general': { variant: 'default', label: 'General' },
}

/**
 * Format a category string: uppercase first letter, replace underscores with spaces
 */
function formatCategoryLabel(category: string): string {
  if (!category || typeof category !== 'string') return category || ''
  return category
    .split(/[-_]/)
    .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ')
}

export function CategoryBadge({ category }: CategoryBadgeProps) {
  const config = categoryConfig[category] || {
    variant: 'default' as BadgeVariant,
    label: formatCategoryLabel(category)
  }
  return <Badge variant={config.variant}>{config.label}</Badge>
}
