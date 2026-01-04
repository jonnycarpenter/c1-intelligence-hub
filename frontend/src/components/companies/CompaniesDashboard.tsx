'use client'

import { useState, useMemo } from 'react'
import { 
  Building2, 
  Search, 
  Grid3X3,
  List,
  Globe,
  ChevronRight,
  Star,
  StarOff,
  Loader2,
  TrendingUp,
  Download,
  AlertCircle,
  RefreshCw,
  X,
  Bot,
  DollarSign,
  Users,
  MapPin
} from 'lucide-react'
import { Button } from '@/components/ui'
import { cn } from '@/lib/utils'
import { useCompanies, useCompanyTracking, type Company } from '@/hooks'

// Quick actions for company intelligence
const quickActions = [
  {
    id: 'tracked-companies',
    label: 'Tracked Companies',
    description: 'View monitored companies',
    prompt: 'Show me all the companies we are currently tracking.',
  },
  {
    id: 'competitor-analysis',
    label: 'Competitor Analysis',
    description: 'Analyze competitor activity',
    prompt: 'Give me a competitive analysis of the major carbon fiber manufacturers.',
  },
  {
    id: 'earnings-summary',
    label: 'Earnings Summary',
    description: 'Recent earnings highlights',
    prompt: 'What are the key takeaways from recent composites company earnings calls?',
  },
  {
    id: 'supplier-landscape',
    label: 'Supplier Landscape',
    description: 'Raw material suppliers',
    prompt: 'Give me an overview of the raw material supplier landscape for composites.',
  },
  {
    id: 'new-entrants',
    label: 'New Entrants',
    description: 'Emerging players',
    prompt: 'What new companies are entering the composites market?',
  },
  {
    id: 'ma-activity',
    label: 'M&A Activity',
    description: 'Mergers & acquisitions',
    prompt: 'What merger and acquisition activity is happening in the composites industry?',
  },
]

interface CompaniesDashboardProps {
  onAskAboutCompany: (prompt: string) => void
  displayCompanies?: Company[] // Companies to display from chat response
  onClearDisplayCompanies?: () => void // Callback to clear agent results
}

export default function CompaniesDashboard({ 
  onAskAboutCompany, 
  displayCompanies, 
  onClearDisplayCompanies 
}: CompaniesDashboardProps) {
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedType, setSelectedType] = useState('all')
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid')
  const [showTrackedOnly, setShowTrackedOnly] = useState(false)

  // Fetch companies from API
  const { 
    companies: apiCompanies, 
    types,
    isLoading, 
    error,
    refresh 
  } = useCompanies({
    type: selectedType === 'all' ? undefined : selectedType,
    query: searchQuery || undefined,
    trackedOnly: showTrackedOnly,
  })

  // Company tracking
  const { trackCompany, untrackCompany, isUpdating } = useCompanyTracking()

  // Use displayCompanies from chat if provided, otherwise use API companies
  const companies = displayCompanies || apiCompanies

  // Build types with counts
  const typesWithCounts = useMemo(() => {
    const baseTypes = [
      { id: 'all', label: 'All Companies' },
      { id: 'Raw Material Manufacturer', label: 'Raw Materials' },
      { id: 'Processor/Fabricator', label: 'Processors' },
      { id: 'OEM', label: 'OEMs' },
      { id: 'Distributor', label: 'Distributors' },
    ]
    
    return baseTypes.map(t => ({
      ...t,
      count: t.id === 'all' 
        ? apiCompanies.length 
        : apiCompanies.filter(c => c.type === t.id).length
    }))
  }, [apiCompanies])

  // Client-side filter for immediate feedback
  const filteredCompanies = useMemo(() => {
    if (!searchQuery && selectedType === 'all' && !showTrackedOnly) {
      return companies
    }
    
    return companies.filter(company => {
      const matchesSearch = !searchQuery || 
        company.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (company.ticker && company.ticker.toLowerCase().includes(searchQuery.toLowerCase()))
      
      const matchesType = selectedType === 'all' || company.type === selectedType
      const matchesTracked = !showTrackedOnly || company.is_tracked
      
      return matchesSearch && matchesType && matchesTracked
    })
  }, [companies, searchQuery, selectedType, showTrackedOnly])

  const handleCompanyClick = (company: Company) => {
    onAskAboutCompany(`Tell me about ${company.name}${company.ticker ? ` (${company.ticker})` : ''}. Include recent news, earnings, and industry positioning.`)
  }

  const handleQuickAction = (action: typeof quickActions[0]) => {
    onAskAboutCompany(action.prompt)
  }

  const handleToggleTracking = async (company: Company) => {
    try {
      if (company.is_tracked) {
        await untrackCompany(company.name)
      } else {
        await trackCompany(company.name, company.ticker, company.type)
      }
      refresh()
    } catch (err) {
      console.error('Failed to toggle tracking:', err)
    }
  }

  const handleExportCSV = () => {
    const headers = ['ID', 'Name', 'Ticker', 'Type', 'Industries', 'Tracked']
    const rows = filteredCompanies.map(c => [
      c.id,
      c.name,
      c.ticker || '',
      c.type,
      c.industries.join('; '),
      c.is_tracked ? 'Yes' : 'No'
    ])
    
    const csvContent = [
      headers.join(','),
      ...rows.map(row => row.map(cell => `"${cell}"`).join(','))
    ].join('\n')
    
    const blob = new Blob([csvContent], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `companies_export_${new Date().toISOString().split('T')[0]}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="h-full flex flex-col bg-gradient-to-br from-slate-50 to-emerald-50/30">
      {/* Header */}
      <div className="p-4 border-b border-slate-200 bg-white/80 backdrop-blur-sm">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-emerald-500 flex items-center justify-center">
              <Building2 size={18} className="text-white" />
            </div>
            <div>
              <h1 className="font-semibold text-slate-900">Company Intelligence</h1>
              <p className="text-xs text-slate-500">
                {isLoading ? 'Loading...' : `${filteredCompanies.length} companies`}
                {displayCompanies && ' (from chat)'}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button 
              variant="ghost" 
              size="sm"
              onClick={handleExportCSV}
              className="text-slate-600"
            >
              <Download size={14} />
              Export
            </Button>
            
            <Button 
              variant="ghost" 
              size="sm"
              onClick={() => refresh()}
              disabled={isLoading}
              className="text-slate-600"
            >
              <RefreshCw size={14} className={isLoading ? 'animate-spin' : ''} />
            </Button>
            
            <div className="flex border border-slate-200 rounded-lg overflow-hidden">
              <button
                onClick={() => setViewMode('grid')}
                className={cn(
                  "p-2 transition-colors",
                  viewMode === 'grid' ? 'bg-slate-100 text-slate-700' : 'text-slate-400 hover:text-slate-600'
                )}
              >
                <Grid3X3 size={16} />
              </button>
              <button
                onClick={() => setViewMode('list')}
                className={cn(
                  "p-2 transition-colors",
                  viewMode === 'list' ? 'bg-slate-100 text-slate-700' : 'text-slate-400 hover:text-slate-600'
                )}
              >
                <List size={16} />
              </button>
            </div>
          </div>
        </div>

        {/* Search */}
        <div className="relative">
          <Search size={16} className="absolute left-3 top-1/2 transform -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Search companies by name or ticker..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-4 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
          />
        </div>
      </div>

      {/* Agent Results Banner */}
      {displayCompanies && displayCompanies.length > 0 && (
        <div className="flex items-center gap-3 p-3 mx-4 mt-4 bg-gradient-to-r from-emerald-50 to-teal-50 border border-emerald-200 rounded-lg">
          <Bot size={18} className="text-emerald-600" />
          <span className="text-sm text-emerald-800 flex-1">
            Showing <strong>{displayCompanies.length}</strong> companies from your query
          </span>
          <Button
            variant="ghost"
            size="sm"
            onClick={onClearDisplayCompanies}
            className="text-emerald-600 hover:text-emerald-700 hover:bg-emerald-100"
          >
            <X size={14} className="mr-1" />
            Show All Companies
          </Button>
        </div>
      )}

      {/* Quick Actions */}
      <div className="p-4 border-b border-slate-200">
        <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-hide">
          {quickActions.map((action) => (
            <button
              key={action.id}
              onClick={() => handleQuickAction(action)}
              className="flex-shrink-0 px-3 py-1.5 text-xs font-medium bg-emerald-50 text-emerald-700 rounded-full hover:bg-emerald-100 transition-colors whitespace-nowrap"
            >
              {action.label}
            </button>
          ))}
        </div>
      </div>

      {/* Filters */}
      <div className="p-4 border-b border-slate-200 flex items-center gap-4">
        <div className="flex gap-2 overflow-x-auto">
          {typesWithCounts.map((type) => (
            <button
              key={type.id}
              onClick={() => setSelectedType(type.id)}
              className={cn(
                "px-3 py-1.5 text-xs font-medium rounded-lg transition-colors whitespace-nowrap",
                selectedType === type.id
                  ? 'bg-emerald-100 text-emerald-700'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              )}
            >
              {type.label}
              {type.count > 0 && (
                <span className="ml-1.5 text-slate-400">({type.count})</span>
              )}
            </button>
          ))}
        </div>
        
        <div className="flex-1" />
        
        <button
          onClick={() => setShowTrackedOnly(!showTrackedOnly)}
          className={cn(
            "flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg transition-colors",
            showTrackedOnly
              ? 'bg-emerald-100 text-emerald-700'
              : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
          )}
        >
          <Star size={12} />
          Tracked Only
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4">
        {error && (
          <div className="flex items-center gap-2 p-4 mb-4 bg-red-50 text-red-700 rounded-lg">
            <AlertCircle size={16} />
            <span className="text-sm">{error}</span>
          </div>
        )}

        {isLoading && !displayCompanies ? (
          <div className="flex items-center justify-center h-40">
            <Loader2 size={24} className="animate-spin text-emerald-500" />
          </div>
        ) : viewMode === 'grid' ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredCompanies.map((company) => (
              <CompanyCard
                key={company.id}
                company={company}
                onClick={() => handleCompanyClick(company)}
                onToggleTracking={() => handleToggleTracking(company)}
                isUpdating={isUpdating}
              />
            ))}
          </div>
        ) : (
          <div className="space-y-2">
            {filteredCompanies.map((company) => (
              <CompanyListItem
                key={company.id}
                company={company}
                onClick={() => handleCompanyClick(company)}
                onToggleTracking={() => handleToggleTracking(company)}
                isUpdating={isUpdating}
              />
            ))}
          </div>
        )}

        {filteredCompanies.length === 0 && !isLoading && (
          <div className="text-center py-12">
            <Building2 size={48} className="mx-auto text-slate-300 mb-4" />
            <h3 className="text-lg font-medium text-slate-600">No companies found</h3>
            <p className="text-sm text-slate-500 mt-1">Try adjusting your filters</p>
          </div>
        )}
      </div>
    </div>
  )
}

// Company Card Component
function CompanyCard({ 
  company, 
  onClick, 
  onToggleTracking,
  isUpdating 
}: { 
  company: Company
  onClick: () => void
  onToggleTracking: () => void
  isUpdating: boolean
}) {
  return (
    <div 
      className="group bg-white rounded-xl border border-slate-200 hover:border-emerald-300 hover:shadow-lg transition-all cursor-pointer"
    >
      <div className="p-4">
        <div className="flex items-start justify-between mb-3">
          <div className="flex-1" onClick={onClick}>
            <h3 className="font-semibold text-slate-900 group-hover:text-emerald-600 transition-colors">
              {company.name}
            </h3>
            {company.ticker && (
              <span className="text-xs font-mono text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded">
                {company.ticker}
              </span>
            )}
          </div>
          <button
            onClick={(e) => {
              e.stopPropagation()
              onToggleTracking()
            }}
            disabled={isUpdating}
            className={cn(
              "p-1.5 rounded-lg transition-colors",
              company.is_tracked
                ? "text-yellow-500 hover:bg-yellow-50"
                : "text-slate-300 hover:text-slate-400 hover:bg-slate-50"
            )}
          >
            {company.is_tracked ? <Star size={16} fill="currentColor" /> : <StarOff size={16} />}
          </button>
        </div>

        <div onClick={onClick}>
          <span className={cn(
            "inline-block px-2 py-0.5 text-xs font-medium rounded-full mb-3",
            company.type === 'OEM' ? 'bg-purple-100 text-purple-700' :
            company.type === 'Raw Material Manufacturer' ? 'bg-blue-100 text-blue-700' :
            company.type === 'Processor/Fabricator' ? 'bg-orange-100 text-orange-700' :
            'bg-slate-100 text-slate-700'
          )}>
            {company.type}
          </span>

          {company.description && (
            <p className="text-xs text-slate-600 mb-3 line-clamp-2">
              {company.description}
            </p>
          )}

          <div className="flex flex-wrap gap-1 mb-3">
            {company.industries.slice(0, 3).map((industry) => (
              <span
                key={industry}
                className="px-2 py-0.5 text-xs bg-slate-100 text-slate-600 rounded-full"
              >
                {industry.replace(/_/g, ' ')}
              </span>
            ))}
            {company.industries.length > 3 && (
              <span className="px-2 py-0.5 text-xs bg-slate-100 text-slate-500 rounded-full">
                +{company.industries.length - 3}
              </span>
            )}
          </div>

          <div className="flex items-center gap-4 text-xs text-slate-500">
            {company.revenue && (
              <span className="flex items-center gap-1">
                <DollarSign size={12} />
                {company.revenue}
              </span>
            )}
            {company.employees && (
              <span className="flex items-center gap-1">
                <Users size={12} />
                {company.employees}
              </span>
            )}
            {company.headquarters && (
              <span className="flex items-center gap-1">
                <MapPin size={12} />
                {company.headquarters}
              </span>
            )}
          </div>
        </div>
      </div>

      <div 
        onClick={onClick}
        className="px-4 py-2 bg-slate-50 border-t border-slate-100 flex items-center justify-between"
      >
        <span className="text-xs text-slate-500">Click for details</span>
        <ChevronRight size={14} className="text-slate-400 group-hover:text-emerald-500 group-hover:translate-x-1 transition-all" />
      </div>
    </div>
  )
}

// Company List Item Component
function CompanyListItem({ 
  company, 
  onClick, 
  onToggleTracking,
  isUpdating 
}: { 
  company: Company
  onClick: () => void
  onToggleTracking: () => void
  isUpdating: boolean
}) {
  return (
    <div 
      onClick={onClick}
      className="group flex items-center gap-4 p-3 bg-white rounded-lg border border-slate-200 hover:border-emerald-300 hover:shadow-md transition-all cursor-pointer"
    >
      <div className="w-10 h-10 rounded-lg bg-emerald-100 flex items-center justify-center">
        <Building2 size={20} className="text-emerald-600" />
      </div>

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-medium text-slate-900 truncate group-hover:text-emerald-600">
            {company.name}
          </span>
          {company.ticker && (
            <span className="text-xs font-mono text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded">
              {company.ticker}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2 mt-0.5">
          <span className="text-xs text-slate-500">{company.type}</span>
          {company.revenue && (
            <>
              <span className="text-slate-300">•</span>
              <span className="text-xs text-slate-500">{company.revenue}</span>
            </>
          )}
        </div>
      </div>

      <div className="flex items-center gap-2">
        {company.industries.slice(0, 2).map((industry) => (
          <span
            key={industry}
            className="px-2 py-0.5 text-xs bg-slate-100 text-slate-600 rounded-full hidden md:inline-block"
          >
            {industry.replace(/_/g, ' ')}
          </span>
        ))}
        
        <button
          onClick={(e) => {
            e.stopPropagation()
            onToggleTracking()
          }}
          disabled={isUpdating}
          className={cn(
            "p-1.5 rounded-lg transition-colors",
            company.is_tracked
              ? "text-yellow-500 hover:bg-yellow-50"
              : "text-slate-300 hover:text-slate-400 hover:bg-slate-50"
          )}
        >
          {company.is_tracked ? <Star size={16} fill="currentColor" /> : <StarOff size={16} />}
        </button>

        <ChevronRight size={16} className="text-slate-400 group-hover:text-emerald-500" />
      </div>
    </div>
  )
}
