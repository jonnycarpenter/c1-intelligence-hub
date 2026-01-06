'use client'

import { Package, TrendingUp, MessageSquare, ExternalLink } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { CategoryOutput } from '@/types'

interface ProductRecommendationsProps {
    categoryOutput: CategoryOutput
    onAskAbout?: (product: string) => void
}

export function ProductRecommendations({ categoryOutput, onAskAbout }: ProductRecommendationsProps) {
    const { product_recommendations } = categoryOutput

    if (!product_recommendations || product_recommendations.length === 0) return null

    // Sort by relevance score
    const sortedProducts = [...product_recommendations].sort((a, b) => b.relevance_score - a.relevance_score)

    return (
        <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden shadow-sm">
            <div className="bg-gradient-to-r from-emerald-500 to-teal-500 px-6 py-4 flex items-center gap-2">
                <Package size={20} className="text-white" />
                <h3 className="text-white font-semibold">Product Recommendations</h3>
                <span className="ml-auto text-emerald-100 text-sm">
                    {sortedProducts.length} {sortedProducts.length === 1 ? 'product' : 'products'}
                </span>
            </div>
            
            <div className="p-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {sortedProducts.map((product, idx) => {
                        const relevancePercent = Math.round(product.relevance_score * 100)
                        const isHighRelevance = product.relevance_score >= 0.7
                        
                        return (
                            <div
                                key={idx}
                                className={cn(
                                    "relative rounded-xl border-2 p-4 hover:shadow-md transition-all group",
                                    isHighRelevance 
                                        ? "border-emerald-300 bg-emerald-50/50" 
                                        : "border-slate-200 bg-white"
                                )}
                            >
                                {/* Relevance Badge */}
                                <div className="absolute -top-2 -right-2 flex items-center gap-1 bg-emerald-500 text-white text-xs font-bold px-2 py-1 rounded-full shadow-sm">
                                    <TrendingUp size={12} />
                                    {relevancePercent}%
                                </div>

                                {/* Product Name */}
                                <h4 className="font-semibold text-slate-900 mb-2 pr-12">
                                    {product.product_name}
                                </h4>

                                {/* Rationale */}
                                <p className="text-sm text-slate-600 mb-3 leading-relaxed">
                                    {product.rationale}
                                </p>

                                {/* Progress Bar */}
                                <div className="mb-3">
                                    <div className="h-1.5 bg-slate-200 rounded-full overflow-hidden">
                                        <div 
                                            className={cn(
                                                "h-full transition-all duration-500",
                                                isHighRelevance ? "bg-emerald-500" : "bg-slate-400"
                                            )}
                                            style={{ width: `${relevancePercent}%` }}
                                        />
                                    </div>
                                </div>

                                {/* Action Buttons */}
                                <div className="flex items-center gap-2">
                                    {onAskAbout && (
                                        <button
                                            onClick={() => onAskAbout(product.product_name)}
                                            className="flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-medium rounded-lg transition-colors"
                                        >
                                            <MessageSquare size={12} />
                                            Ask About Product
                                        </button>
                                    )}
                                    <button
                                        className="flex items-center justify-center gap-1 px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-medium rounded-lg transition-colors"
                                        title="View datasheet"
                                    >
                                        <ExternalLink size={12} />
                                    </button>
                                </div>
                            </div>
                        )
                    })}
                </div>

                {/* No recommendations message */}
                {sortedProducts.length === 0 && (
                    <div className="text-center py-8">
                        <Package size={48} className="mx-auto text-slate-300 mb-3" />
                        <p className="text-slate-500">No product recommendations available</p>
                    </div>
                )}
            </div>
        </div>
    )
}

export default ProductRecommendations
