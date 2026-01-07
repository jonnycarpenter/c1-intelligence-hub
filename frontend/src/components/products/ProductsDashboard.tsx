'use client'

import { useState, useMemo } from 'react'
import { 
  Package, 
  Search, 
  Grid3X3,
  List,
  Building2,
  ChevronRight,
  CheckCircle,
  Loader2,
  ArrowUpDown,
  Sparkles,
  Download,
  AlertCircle,
  RefreshCw,
  X,
  Bot
} from 'lucide-react'
import { Button } from '@/components/ui'
import { cn } from '@/lib/utils'
import { useProducts, useProductComparison, type Product } from '@/hooks'

// Quick actions for product intelligence
const quickActions = [
  {
    id: 'show-our-products',
    label: 'Our Products',
    description: 'View C1 catalog',
    prompt: 'Show me all the products we currently carry in our catalog.',
  },
  {
    id: 'find-alternatives',
    label: 'Find Alternatives',
    description: 'Find substitute products',
    prompt: 'Find alternative products to replace [product name/SKU]. Consider performance specs, pricing, and availability.',
  },
  {
    id: 'compare-products',
    label: 'Compare Products',
    description: 'Side-by-side comparison',
    prompt: 'Compare [Product A] vs [Product B]. Include specifications, pricing, lead times, and applications.',
  },
  {
    id: 'product-gaps',
    label: 'Find Gaps',
    description: 'What we don\'t carry',
    prompt: 'Show me the product gaps - what competitors offer that we don\'t currently carry.',
  },
  {
    id: 'aerospace-products',
    label: 'Aerospace SKUs',
    description: 'Products for aerospace',
    prompt: 'Show me all products available for aerospace applications.',
  },
  {
    id: 'supplier-catalog',
    label: 'Supplier Catalog',
    description: 'Browse by supplier',
    prompt: 'Show me all the products from Hexcel.',
  },
]

interface ProductsDashboardProps {
  onAskAboutProduct: (prompt: string) => void
  displayProducts?: Product[] // Products to display from chat response
  onClearDisplayProducts?: () => void // Callback to clear agent results and show all products
}

export default function ProductsDashboard({ onAskAboutProduct, displayProducts, onClearDisplayProducts }: ProductsDashboardProps) {
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedCategory, setSelectedCategory] = useState('all')
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid')
  const [selectedProducts, setSelectedProducts] = useState<string[]>([])
  const [showC1Only, setShowC1Only] = useState(false)

  // Fetch products from API
  const { 
    products: apiProducts, 
    categories: apiCategories,
    suppliers,
    isLoading, 
    error,
    refresh 
  } = useProducts({
    category: selectedCategory === 'all' ? undefined : selectedCategory,
    query: searchQuery || undefined,
    c1Only: showC1Only,
  })

  // Product comparison
  const { comparison, compareProducts, isLoading: isComparing } = useProductComparison()

  // Use displayProducts from chat if provided, otherwise use API products
  const products = displayProducts || apiProducts

  // Build categories with counts from API
  const categoriesWithCounts = useMemo(() => {
    const baseCats = [
      { id: 'all', label: 'All Products' },
      { id: 'carbon_fiber', label: 'Carbon Fiber' },
      { id: 'glass_fiber', label: 'Glass Fiber' },
      { id: 'prepreg', label: 'Prepregs' },
      { id: 'resin', label: 'Resins' },
    ]
    
    // Add counts from API categories
    return baseCats.map(cat => ({
      ...cat,
      count: cat.id === 'all' 
        ? apiProducts.length 
        : apiProducts.filter(p => p.category === cat.id).length
    }))
  }, [apiProducts])

  // Client-side filter for immediate feedback
  const filteredProducts = useMemo(() => {
    if (!searchQuery && selectedCategory === 'all' && !showC1Only) {
      return products
    }
    
    return products.filter(product => {
      const matchesSearch = !searchQuery || 
        product.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        product.supplier.toLowerCase().includes(searchQuery.toLowerCase()) ||
        product.id.toLowerCase().includes(searchQuery.toLowerCase())
      
      const matchesCategory = selectedCategory === 'all' || product.category === selectedCategory
      const matchesC1 = !showC1Only || product.in_c1_catalog
      
      return matchesSearch && matchesCategory && matchesC1
    })
  }, [products, searchQuery, selectedCategory, showC1Only])

  const handleProductClick = (product: Product) => {
    onAskAboutProduct(`Tell me about ${product.name} from ${product.supplier}. Include specifications, applications, and whether we carry it.`)
  }

  const handleQuickAction = (action: typeof quickActions[0]) => {
    onAskAboutProduct(action.prompt)
  }

  const handleCompareSelected = () => {
    if (selectedProducts.length >= 2) {
      const productNames = selectedProducts.map(id => {
        const product = products.find(p => p.id === id)
        return product ? `${product.name} (${product.supplier})` : id
      }).join(' vs ')
      onAskAboutProduct(`Compare these products: ${productNames}. Include specifications, pricing, and recommendations.`)
    }
  }

  const toggleProductSelection = (productId: string) => {
    setSelectedProducts(prev => 
      prev.includes(productId) 
        ? prev.filter(id => id !== productId)
        : [...prev, productId]
    )
  }

  const handleExportCSV = () => {
    // Create CSV content
    const headers = ['ID', 'Name', 'Supplier', 'Category', 'In C1 Catalog', 'Industries']
    const rows = filteredProducts.map(p => [
      p.id,
      p.name,
      p.supplier,
      p.category,
      p.in_c1_catalog ? 'Yes' : 'No',
      p.industries.join('; ')
    ])
    
    const csvContent = [
      headers.join(','),
      ...rows.map(row => row.map(cell => `"${cell}"`).join(','))
    ].join('\n')
    
    // Download
    const blob = new Blob([csvContent], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `products_export_${new Date().toISOString().split('T')[0]}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="h-full flex flex-col bg-gradient-to-br from-slate-50 to-blue-50/30">
      {/* Header */}
      <div className="p-4 border-b border-slate-200 bg-white/80 backdrop-blur-sm">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-blue-500 flex items-center justify-center">
              <Package size={18} className="text-white" />
            </div>
            <div>
              <h1 className="font-semibold text-slate-900">Product Intelligence</h1>
              <p className="text-xs text-slate-500">
                {isLoading ? 'Loading...' : `${filteredProducts.length} products`}
                {displayProducts && ' (from chat)'}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {/* Export Button */}
            <Button 
              variant="ghost" 
              size="sm"
              onClick={handleExportCSV}
              className="text-slate-600"
            >
              <Download size={14} />
              Export
            </Button>
            
            {/* Refresh Button */}
            <Button 
              variant="ghost" 
              size="sm"
              onClick={() => refresh()}
              disabled={isLoading}
              className="text-slate-600"
            >
              <RefreshCw size={14} className={isLoading ? 'animate-spin' : ''} />
            </Button>

            {/* Compare Button */}
            {selectedProducts.length >= 2 && (
              <Button 
                variant="primary" 
                size="sm"
                onClick={handleCompareSelected}
                className="bg-blue-600 hover:bg-blue-700"
              >
                <ArrowUpDown size={14} />
                Compare ({selectedProducts.length})
              </Button>
            )}
            
            {/* View Toggle */}
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

        {/* Search Bar */}
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={18} />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search products, suppliers, or SKUs..."
              className="w-full pl-10 pr-4 py-2.5 bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
            />
          </div>
          <label className="flex items-center gap-2 px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg cursor-pointer hover:bg-slate-100">
            <input
              type="checkbox"
              checked={showC1Only}
              onChange={(e) => setShowC1Only(e.target.checked)}
              className="rounded border-slate-300"
            />
            <span className="text-sm text-slate-600">C1 Only</span>
          </label>
        </div>
      </div>

      <div className="flex-1 flex overflow-hidden">
        {/* Sidebar - Categories & Quick Actions */}
        <div className="w-56 border-r border-slate-200 bg-white/50 p-4 overflow-y-auto">
          {/* Categories */}
          <div className="mb-6">
            <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
              Categories
            </h3>
            <div className="space-y-1">
              {categoriesWithCounts.map(category => (
                <button
                  key={category.id}
                  onClick={() => setSelectedCategory(category.id)}
                  className={cn(
                    "w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm transition-colors",
                    selectedCategory === category.id
                      ? "bg-blue-100 text-blue-700 font-medium"
                      : "text-slate-600 hover:bg-slate-100"
                  )}
                >
                  <span>{category.label}</span>
                  <span className={cn(
                    "text-xs px-1.5 py-0.5 rounded",
                    selectedCategory === category.id
                      ? "bg-blue-200 text-blue-700"
                      : "bg-slate-200 text-slate-500"
                  )}>
                    {category.count}
                  </span>
                </button>
              ))}
            </div>
          </div>

          {/* Quick Actions */}
          <div>
            <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
              Quick Actions
            </h3>
            <div className="space-y-2">
              {quickActions.map(action => (
                <button
                  key={action.id}
                  onClick={() => handleQuickAction(action)}
                  className="w-full p-3 bg-white border border-slate-200 rounded-lg hover:border-blue-300 hover:bg-blue-50/50 transition-all text-left group"
                >
                  <div className="flex items-center gap-2">
                    <Sparkles size={14} className="text-blue-500" />
                    <span className="font-medium text-slate-700 text-sm group-hover:text-blue-700">
                      {action.label}
                    </span>
                  </div>
                  <p className="text-xs text-slate-500 mt-1">{action.description}</p>
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Main Content - Product Grid/List */}
        <div className="flex-1 overflow-y-auto p-4">
          {/* Agent Results Banner */}
          {displayProducts && displayProducts.length > 0 && (
            <div className="flex items-center gap-3 p-3 mb-4 bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-lg">
              <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center">
                <Bot size={16} className="text-blue-600" />
              </div>
              <div className="flex-1">
                <p className="font-medium text-blue-900">
                  Showing {displayProducts.length} product{displayProducts.length !== 1 ? 's' : ''} from your query
                </p>
                <p className="text-xs text-blue-600">These results were found by the Product Maven agent</p>
              </div>
              {onClearDisplayProducts && (
                <Button 
                  variant="ghost" 
                  size="sm" 
                  onClick={onClearDisplayProducts}
                  className="text-blue-700 hover:text-blue-900 hover:bg-blue-100"
                >
                  <X size={14} />
                  Show All Products
                </Button>
              )}
            </div>
          )}

          {/* Error State */}
          {error && !displayProducts && (
            <div className="flex items-center gap-2 p-4 mb-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
              <AlertCircle size={18} />
              <span>{error}</span>
              <Button variant="ghost" size="sm" onClick={() => refresh()} className="ml-auto">
                Retry
              </Button>
            </div>
          )}

          {/* Loading State - only show when loading API data, not agent results */}
          {isLoading && !displayProducts ? (
            <div className="flex items-center justify-center h-full">
              <div className="text-center">
                <Loader2 className="animate-spin text-blue-500 mx-auto mb-2" size={32} />
                <p className="text-slate-500">Loading products...</p>
              </div>
            </div>
          ) : filteredProducts.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-slate-500">
              <Package size={48} className="mb-4 text-slate-300" />
              <p>No products found</p>
              <p className="text-sm">Try adjusting your search or filters</p>
            </div>
          ) : viewMode === 'grid' ? (
            <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
              {filteredProducts.map(product => (
                <ProductCard
                  key={product.id}
                  product={product}
                  isSelected={selectedProducts.includes(product.id)}
                  onSelect={() => toggleProductSelection(product.id)}
                  onClick={() => handleProductClick(product)}
                />
              ))}
            </div>
          ) : (
            <div className="space-y-2">
              {filteredProducts.map(product => (
                <ProductListItem
                  key={product.id}
                  product={product}
                  isSelected={selectedProducts.includes(product.id)}
                  onSelect={() => toggleProductSelection(product.id)}
                  onClick={() => handleProductClick(product)}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// Product Card Component
function ProductCard({ 
  product, 
  isSelected, 
  onSelect, 
  onClick 
}: { 
  product: Product
  isSelected: boolean
  onSelect: () => void
  onClick: () => void
}) {
  return (
    <div 
      className={cn(
        "bg-white border rounded-xl overflow-hidden hover:shadow-md transition-all cursor-pointer group",
        isSelected ? "border-blue-500 ring-2 ring-blue-100" : "border-slate-200"
      )}
    >
      {/* Header */}
      <div className="p-4 border-b border-slate-100">
        <div className="flex items-start justify-between">
          <div className="flex-1 min-w-0" onClick={onClick}>
            <h3 className="font-medium text-slate-900 truncate group-hover:text-blue-700">
              {product.name}
            </h3>
            <div className="flex items-center gap-1 mt-1 text-xs text-slate-500">
              <Building2 size={12} />
              {product.supplier}
            </div>
          </div>
          <button
            onClick={(e) => { e.stopPropagation(); onSelect(); }}
            className={cn(
              "w-5 h-5 rounded border flex items-center justify-center shrink-0",
              isSelected 
                ? "bg-blue-500 border-blue-500 text-white" 
                : "border-slate-300 hover:border-blue-400"
            )}
          >
            {isSelected && <CheckCircle size={12} />}
          </button>
        </div>
        <div className="flex items-center gap-2 mt-2">
          <span className="px-2 py-0.5 bg-slate-100 text-slate-600 text-xs rounded">
            {product.subcategory || product.category.replace('_', ' ')}
          </span>
          {product.in_c1_catalog ? (
            <span className="px-2 py-0.5 bg-emerald-100 text-emerald-700 text-xs rounded">
              In Catalog
            </span>
          ) : (
            <span className="px-2 py-0.5 bg-emerald-100 text-emerald-700 text-xs rounded">
              Competitor
            </span>
          )}
        </div>
      </div>

      {/* Specs Preview */}
      <div className="p-4 bg-slate-50/50" onClick={onClick}>
        <div className="text-xs text-slate-500 space-y-1">
          {Object.entries(product.specs).slice(0, 3).map(([key, value]) => (
            <div key={key} className="flex justify-between">
              <span>{key}:</span>
              <span className="font-medium text-slate-700">{value}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Footer */}
      <div className="px-4 py-2 border-t border-slate-100 flex items-center justify-between">
        <div className="flex gap-1">
          {product.industries.slice(0, 2).map(ind => (
            <span key={ind} className="text-[10px] text-slate-400">{ind}</span>
          ))}
        </div>
        <ChevronRight size={16} className="text-slate-300 group-hover:text-blue-500 transition-colors" />
      </div>
    </div>
  )
}

// Product List Item Component
function ProductListItem({ 
  product, 
  isSelected, 
  onSelect, 
  onClick 
}: { 
  product: Product
  isSelected: boolean
  onSelect: () => void
  onClick: () => void
}) {
  return (
    <div 
      className={cn(
        "bg-white border rounded-lg p-4 hover:shadow-md transition-all cursor-pointer group flex items-center gap-4",
        isSelected ? "border-blue-500 ring-2 ring-blue-100" : "border-slate-200"
      )}
    >
      <button
        onClick={(e) => { e.stopPropagation(); onSelect(); }}
        className={cn(
          "w-5 h-5 rounded border flex items-center justify-center shrink-0",
          isSelected 
            ? "bg-blue-500 border-blue-500 text-white" 
            : "border-slate-300 hover:border-blue-400"
        )}
      >
        {isSelected && <CheckCircle size={12} />}
      </button>

      <div className="flex-1 min-w-0" onClick={onClick}>
        <div className="flex items-center gap-3">
          <h3 className="font-medium text-slate-900 group-hover:text-blue-700">
            {product.name}
          </h3>
          <span className="text-xs text-slate-400">•</span>
          <span className="text-sm text-slate-500">{product.supplier}</span>
          <span className="px-2 py-0.5 bg-slate-100 text-slate-600 text-xs rounded">
            {product.subcategory || product.category.replace('_', ' ')}
          </span>
          {product.in_c1_catalog ? (
            <span className="px-2 py-0.5 bg-emerald-100 text-emerald-700 text-xs rounded">
              In Catalog
            </span>
          ) : (
            <span className="px-2 py-0.5 bg-emerald-100 text-emerald-700 text-xs rounded">
              Competitor
            </span>
          )}
        </div>
        <div className="flex gap-4 mt-2 text-xs text-slate-500">
          {Object.entries(product.specs).slice(0, 3).map(([key, value]) => (
            <span key={key}>
              <span className="text-slate-400">{key}:</span> <span className="text-slate-700">{value}</span>
            </span>
          ))}
        </div>
      </div>

      <ChevronRight size={20} className="text-slate-300 group-hover:text-blue-500 transition-colors shrink-0" />
    </div>
  )
}
