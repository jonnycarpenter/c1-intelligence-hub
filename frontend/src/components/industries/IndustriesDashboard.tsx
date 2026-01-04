'use client'

import { useState, useMemo } from 'react'
import { 
  Factory, 
  Search, 
  Grid3X3,
  List,
  ChevronRight,
  TrendingUp,
  TrendingDown,
  Loader2,
  Download,
  AlertCircle,
  RefreshCw,
  X,
  Bot,
  Plane,
  Car,
  Wind,
  Ship,
  Building2,
  HardHat,
  Zap,
  Trophy,
  Globe
} from 'lucide-react'
import { Button } from '@/components/ui'
import { cn } from '@/lib/utils'
import { useIndustries, type Industry } from '@/hooks'

// Industry icons mapping
const industryIcons: Record<string, any> = {
  aerospace: Plane,
  automotive: Car,
  wind_energy: Wind,
  marine: Ship,
  construction: HardHat,
  sporting_goods: Trophy,
  electronics: Zap,
  industrial: Factory,
  defense: Building2,
}

// Quick actions for industry intelligence
const quickActions = [
  {
    id: 'industry-overview',
    label: 'Industry Overview',
    description: 'Market landscape summary',
    prompt: 'Give me an overview of the composites industry landscape across all sectors.',
  },
  {
    id: 'growth-sectors',
    label: 'Growth Sectors',
    description: 'Fastest growing industries',
    prompt: 'Which industries are showing the strongest growth in composites adoption?',
  },
  {
    id: 'aerospace-trends',
    label: 'Aerospace Trends',
    description: 'Aviation composites update',
    prompt: 'What are the latest trends in aerospace composites usage?',
  },
  {
    id: 'automotive-ev',
    label: 'EV Composites',
    description: 'Electric vehicle applications',
    prompt: 'How are composites being used in electric vehicle manufacturing?',
  },
  {
    id: 'wind-energy',
    label: 'Wind Energy',
    description: 'Renewable energy sector',
    prompt: 'What is the outlook for composites in wind energy turbine blades?',
  },
  {
    id: 'emerging-applications',
    label: 'Emerging Applications',
    description: 'New use cases',
    prompt: 'What are the emerging applications for advanced composites?',
  },
]

interface IndustriesDashboardProps {
  onAskAboutIndustry: (prompt: string) => void
  displayIndustries?: Industry[] // Industries to display from chat response
  onClearDisplayIndustries?: () => void // Callback to clear agent results
}

export default function IndustriesDashboard({ 
  onAskAboutIndustry, 
  displayIndustries, 
  onClearDisplayIndustries 
}: IndustriesDashboardProps) {
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedGrowth, setSelectedGrowth] = useState('all')
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid')

  // Fetch industries from API
  const { 
    industries: apiIndustries, 
    isLoading, 
    error,
    refresh 
  } = useIndustries({
    query: searchQuery || undefined,
  })

  // Use displayIndustries from chat if provided, otherwise use API industries
  const industries = displayIndustries || apiIndustries

  // Build growth filters
  const growthFilters = useMemo(() => {
    const filters = [
      { id: 'all', label: 'All Industries' },
      { id: 'high', label: 'High Growth', minGrowth: 7 },
      { id: 'moderate', label: 'Moderate Growth', minGrowth: 3, maxGrowth: 7 },
      { id: 'stable', label: 'Stable', maxGrowth: 3 },
    ]
    
    return filters.map(f => ({
      ...f,
      count: f.id === 'all' 
        ? apiIndustries.length 
        : apiIndustries.filter(i => {
            const growth = Number(i.growth_rate) || 0
            if (f.minGrowth && f.maxGrowth) return growth >= f.minGrowth && growth < f.maxGrowth
            if (f.minGrowth) return growth >= f.minGrowth
            if (f.maxGrowth) return growth < f.maxGrowth
            return true
          }).length
    }))
  }, [apiIndustries])

  // Client-side filter for immediate feedback
  const filteredIndustries = useMemo(() => {
    return industries.filter(industry => {
      const matchesSearch = !searchQuery || 
        industry.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        industry.description?.toLowerCase().includes(searchQuery.toLowerCase())
      
      const growth = Number(industry.growth_rate) || 0
      let matchesGrowth = true
      if (selectedGrowth === 'high') matchesGrowth = growth >= 7
      else if (selectedGrowth === 'moderate') matchesGrowth = growth >= 3 && growth < 7
      else if (selectedGrowth === 'stable') matchesGrowth = growth < 3
      
      return matchesSearch && matchesGrowth
    })
  }, [industries, searchQuery, selectedGrowth])

  const handleIndustryClick = (industry: Industry) => {
    onAskAboutIndustry(`Tell me about the ${industry.name} industry for composites. Include market size, growth trends, key players, and opportunities.`)
  }

  const handleQuickAction = (action: typeof quickActions[0]) => {
    onAskAboutIndustry(action.prompt)
  }

  const handleExportCSV = () => {
    const headers = ['ID', 'Name', 'Market Size', 'Growth Rate', 'Trend', 'Description']
    const rows = filteredIndustries.map(i => [
      i.id,
      i.name,
      i.market_size || '',
      i.growth_rate !== undefined ? String(i.growth_rate) : '',
      i.trend || (i.trends?.[0] || ''),
      i.description || ''
    ])
    
    const csvContent = [
      headers.join(','),
      ...rows.map(row => row.map(cell => `"${cell}"`).join(','))
    ].join('\n')
    
    const blob = new Blob([csvContent], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `industries_export_${new Date().toISOString().split('T')[0]}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="h-full flex flex-col bg-gradient-to-br from-slate-50 to-purple-50/30">
      {/* Header */}
      <div className="p-4 border-b border-slate-200 bg-white/80 backdrop-blur-sm">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-purple-500 flex items-center justify-center">
              <Factory size={18} className="text-white" />
            </div>
            <div>
              <h1 className="font-semibold text-slate-900">Industry Intelligence</h1>
              <p className="text-xs text-slate-500">
                {isLoading ? 'Loading...' : `${filteredIndustries.length} industries`}
                {displayIndustries && ' (from chat)'}
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
            placeholder="Search industries..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-4 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500"
          />
        </div>
      </div>

      {/* Agent Results Banner */}
      {displayIndustries && displayIndustries.length > 0 && (
        <div className="flex items-center gap-3 p-3 mx-4 mt-4 bg-gradient-to-r from-purple-50 to-indigo-50 border border-purple-200 rounded-lg">
          <Bot size={18} className="text-purple-600" />
          <span className="text-sm text-purple-800 flex-1">
            Showing <strong>{displayIndustries.length}</strong> industries from your query
          </span>
          <Button
            variant="ghost"
            size="sm"
            onClick={onClearDisplayIndustries}
            className="text-purple-600 hover:text-purple-700 hover:bg-purple-100"
          >
            <X size={14} className="mr-1" />
            Show All Industries
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
              className="flex-shrink-0 px-3 py-1.5 text-xs font-medium bg-purple-50 text-purple-700 rounded-full hover:bg-purple-100 transition-colors whitespace-nowrap"
            >
              {action.label}
            </button>
          ))}
        </div>
      </div>

      {/* Filters */}
      <div className="p-4 border-b border-slate-200 flex items-center gap-4">
        <div className="flex gap-2 overflow-x-auto">
          {growthFilters.map((filter) => (
            <button
              key={filter.id}
              onClick={() => setSelectedGrowth(filter.id)}
              className={cn(
                "px-3 py-1.5 text-xs font-medium rounded-lg transition-colors whitespace-nowrap",
                selectedGrowth === filter.id
                  ? 'bg-purple-100 text-purple-700'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              )}
            >
              {filter.label}
              {filter.count > 0 && (
                <span className="ml-1.5 text-slate-400">({filter.count})</span>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4">
        {error && (
          <div className="flex items-center gap-2 p-4 mb-4 bg-red-50 text-red-700 rounded-lg">
            <AlertCircle size={16} />
            <span className="text-sm">{error}</span>
          </div>
        )}

        {isLoading && !displayIndustries ? (
          <div className="flex items-center justify-center h-40">
            <Loader2 size={24} className="animate-spin text-purple-500" />
          </div>
        ) : viewMode === 'grid' ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredIndustries.map((industry) => (
              <IndustryCard
                key={industry.id}
                industry={industry}
                onClick={() => handleIndustryClick(industry)}
              />
            ))}
          </div>
        ) : (
          <div className="space-y-2">
            {filteredIndustries.map((industry) => (
              <IndustryListItem
                key={industry.id}
                industry={industry}
                onClick={() => handleIndustryClick(industry)}
              />
            ))}
          </div>
        )}

        {filteredIndustries.length === 0 && !isLoading && (
          <div className="text-center py-12">
            <Factory size={48} className="mx-auto text-slate-300 mb-4" />
            <h3 className="text-lg font-medium text-slate-600">No industries found</h3>
            <p className="text-sm text-slate-500 mt-1">Try adjusting your filters</p>
          </div>
        )}
      </div>
    </div>
  )
}

// Industry Card Component
function IndustryCard({ 
  industry, 
  onClick 
}: { 
  industry: Industry
  onClick: () => void
}) {
  const IconComponent = industryIcons[industry.id] || Globe
  const growthNum = Number(industry.growth_rate) || 0
  const isGrowing = growthNum > 0
  const growthColor = growthNum >= 7 ? 'text-green-600' : 
                      growthNum >= 3 ? 'text-emerald-600' : 'text-slate-500'
  const displayTrend = industry.trend || (industry.trends?.[0] ? 'growing' : undefined)

  return (
    <div 
      onClick={onClick}
      className="group bg-white rounded-xl border border-slate-200 hover:border-purple-300 hover:shadow-lg transition-all cursor-pointer overflow-hidden"
    >
      <div className="p-4">
        <div className="flex items-start justify-between mb-3">
          <div className="w-10 h-10 rounded-lg bg-purple-100 flex items-center justify-center">
            <IconComponent size={20} className="text-purple-600" />
          </div>
          
          {industry.growth_rate !== undefined && (
            <div className={cn("flex items-center gap-1", growthColor)}>
              {isGrowing ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
              <span className="text-sm font-medium">{growthNum}%</span>
            </div>
          )}
        </div>

        <h3 className="font-semibold text-slate-900 group-hover:text-purple-600 transition-colors mb-2">
          {industry.name}
        </h3>

        {industry.description && (
          <p className="text-xs text-slate-600 mb-3 line-clamp-2">
            {industry.description}
          </p>
        )}

        <div className="flex items-center gap-4 text-xs text-slate-500">
          {industry.market_size && (
            <span className="bg-slate-100 px-2 py-0.5 rounded">
              {industry.market_size}
            </span>
          )}
          {displayTrend && (
            <span className={cn(
              "px-2 py-0.5 rounded",
              displayTrend === 'growing' ? 'bg-green-100 text-green-700' :
              displayTrend === 'emerging' ? 'bg-purple-100 text-purple-700' :
              'bg-slate-100 text-slate-600'
            )}>
              {displayTrend}
            </span>
          )}
        </div>

        {industry.key_applications && industry.key_applications.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-3">
            {industry.key_applications.slice(0, 3).map((app: string) => (
              <span
                key={app}
                className="px-2 py-0.5 text-xs bg-slate-100 text-slate-600 rounded-full"
              >
                {app}
              </span>
            ))}
            {industry.key_applications.length > 3 && (
              <span className="px-2 py-0.5 text-xs bg-slate-100 text-slate-500 rounded-full">
                +{industry.key_applications.length - 3}
              </span>
            )}
          </div>
        )}
      </div>

      <div className="px-4 py-2 bg-slate-50 border-t border-slate-100 flex items-center justify-between">
        <span className="text-xs text-slate-500">Click for insights</span>
        <ChevronRight size={14} className="text-slate-400 group-hover:text-purple-500 group-hover:translate-x-1 transition-all" />
      </div>
    </div>
  )
}

// Industry List Item Component
function IndustryListItem({ 
  industry, 
  onClick 
}: { 
  industry: Industry
  onClick: () => void
}) {
  const IconComponent = industryIcons[industry.id] || Globe
  const growthNum = Number(industry.growth_rate) || 0
  const isGrowing = growthNum > 0
  const growthColor = growthNum >= 7 ? 'text-green-600' : 
                      growthNum >= 3 ? 'text-emerald-600' : 'text-slate-500'
  const displayTrend = industry.trend || (industry.trends?.[0] ? 'growing' : undefined)

  return (
    <div 
      onClick={onClick}
      className="group flex items-center gap-4 p-3 bg-white rounded-lg border border-slate-200 hover:border-purple-300 hover:shadow-md transition-all cursor-pointer"
    >
      <div className="w-10 h-10 rounded-lg bg-purple-100 flex items-center justify-center">
        <IconComponent size={20} className="text-purple-600" />
      </div>

      <div className="flex-1 min-w-0">
        <span className="font-medium text-slate-900 truncate group-hover:text-purple-600 block">
          {industry.name}
        </span>
        <div className="flex items-center gap-2 mt-0.5">
          {industry.market_size && (
            <span className="text-xs text-slate-500">{industry.market_size}</span>
          )}
          {displayTrend && (
            <>
              <span className="text-slate-300">•</span>
              <span className={cn(
                "text-xs",
                displayTrend === 'growing' ? 'text-green-600' :
                displayTrend === 'emerging' ? 'text-purple-600' :
                'text-slate-500'
              )}>
                {displayTrend}
              </span>
            </>
          )}
        </div>
      </div>

      <div className="flex items-center gap-3">
        {industry.key_applications && industry.key_applications.slice(0, 2).map((app: string) => (
          <span
            key={app}
            className="px-2 py-0.5 text-xs bg-slate-100 text-slate-600 rounded-full hidden md:inline-block"
          >
            {app}
          </span>
        ))}
        
        {industry.growth_rate !== undefined && (
          <div className={cn("flex items-center gap-1", growthColor)}>
            {isGrowing ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
            <span className="text-sm font-medium">{growthNum}%</span>
          </div>
        )}

        <ChevronRight size={16} className="text-slate-400 group-hover:text-purple-500" />
      </div>
    </div>
  )
}
