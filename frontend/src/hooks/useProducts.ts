import { useState, useEffect, useCallback } from 'react'
import { API_BASE } from '@/lib/config'

// Types
export interface Product {
  id: string
  name: string
  supplier: string
  category: string
  subcategory?: string
  industries: string[]
  specs: Record<string, string>
  in_c1_catalog: boolean
}

export interface ProductsResponse {
  count: number
  products: Product[]
  categories: string[]
  suppliers: string[]
}

export interface ProductFilters {
  category?: string
  supplier?: string
  industry?: string
  query?: string
  c1Only?: boolean
}

export interface ProductGap {
  id: string
  name: string
  industries: string[]
}

export interface GapAnalysis {
  category: string
  industry_filter?: string
  summary: {
    total_products: number
    we_carry: number
    gaps: number
    coverage_percent: number
  }
  products_we_carry: Array<{ id: string; name: string; supplier: string }>
  gaps_by_supplier: Record<string, ProductGap[]>
}

export interface ProductComparison {
  products: Product[]
  spec_keys: string[]
  comparison_table: Record<string, Record<string, string>>
}

export function useProducts(initialFilters?: ProductFilters) {
  const [products, setProducts] = useState<Product[]>([])
  const [categories, setCategories] = useState<string[]>([])
  const [suppliers, setSuppliers] = useState<string[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filters, setFilters] = useState<ProductFilters>(initialFilters || {})

  const fetchProducts = useCallback(async (filterOverrides?: ProductFilters) => {
    setIsLoading(true)
    setError(null)

    const activeFilters = { ...filters, ...filterOverrides }
    
    try {
      const params = new URLSearchParams()
      if (activeFilters.category) params.append('category', activeFilters.category)
      if (activeFilters.supplier) params.append('supplier', activeFilters.supplier)
      if (activeFilters.industry) params.append('industry', activeFilters.industry)
      if (activeFilters.query) params.append('query', activeFilters.query)
      if (activeFilters.c1Only) params.append('c1_only', 'true')

      const response = await fetch(`${API_BASE}/api/products?${params}`)
      
      if (!response.ok) {
        throw new Error(`Failed to fetch products: ${response.statusText}`)
      }

      const data: ProductsResponse = await response.json()
      
      setProducts(data.products)
      setCategories(data.categories)
      setSuppliers(data.suppliers)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch products')
      console.error('Error fetching products:', err)
    } finally {
      setIsLoading(false)
    }
  }, [filters])

  // Fetch on mount and when filters change
  useEffect(() => {
    fetchProducts()
  }, [fetchProducts])

  const updateFilters = useCallback((newFilters: ProductFilters) => {
    setFilters(prev => ({ ...prev, ...newFilters }))
  }, [])

  const clearFilters = useCallback(() => {
    setFilters({})
  }, [])

  return {
    products,
    categories,
    suppliers,
    isLoading,
    error,
    filters,
    updateFilters,
    clearFilters,
    refresh: fetchProducts,
  }
}

// Hook for fetching a single product
export function useProduct(productId: string | null) {
  const [product, setProduct] = useState<Product | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!productId) {
      setProduct(null)
      return
    }

    const fetchProduct = async () => {
      setIsLoading(true)
      setError(null)

      try {
        const response = await fetch(`${API_BASE}/api/products/${productId}`)
        
        if (!response.ok) {
          throw new Error(`Product not found: ${productId}`)
        }

        const data = await response.json()
        setProduct(data)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch product')
      } finally {
        setIsLoading(false)
      }
    }

    fetchProduct()
  }, [productId])

  return { product, isLoading, error }
}

// Hook for comparing products
export function useProductComparison() {
  const [comparison, setComparison] = useState<ProductComparison | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const compareProducts = useCallback(async (productIds: string[]) => {
    if (productIds.length < 2) {
      setError('Need at least 2 products to compare')
      return
    }

    setIsLoading(true)
    setError(null)

    try {
      const response = await fetch(
        `${API_BASE}/api/products/compare/${productIds.join(',')}`
      )
      
      if (!response.ok) {
        throw new Error('Failed to compare products')
      }

      const data = await response.json()
      setComparison(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to compare products')
    } finally {
      setIsLoading(false)
    }
  }, [])

  const clearComparison = useCallback(() => {
    setComparison(null)
    setError(null)
  }, [])

  return { comparison, isLoading, error, compareProducts, clearComparison }
}

// Hook for gap analysis
export function useProductGaps() {
  const [gaps, setGaps] = useState<GapAnalysis | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const analyzeGaps = useCallback(async (category: string, industry?: string) => {
    setIsLoading(true)
    setError(null)

    try {
      const params = new URLSearchParams()
      if (industry) params.append('industry', industry)

      const response = await fetch(
        `${API_BASE}/api/products/gaps/${category}?${params}`
      )
      
      if (!response.ok) {
        throw new Error('Failed to analyze product gaps')
      }

      const data = await response.json()
      setGaps(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to analyze gaps')
    } finally {
      setIsLoading(false)
    }
  }, [])

  return { gaps, isLoading, error, analyzeGaps }
}
