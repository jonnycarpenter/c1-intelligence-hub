'use client'

import { useState, useCallback } from 'react'
import {
  Search,
  Sparkles,
  BookOpen,
  FileText,
  Plus,
  ArrowRight,
  Scale,
  TrendingUp,
  Building2,
  Globe,
  BarChart3,
  Loader2,
  XCircle,
} from 'lucide-react'
import { Button } from '@/components/ui'
import ResearchSection from './ResearchSection'
import { cn } from '@/lib/utils'
import type { 
  ResearchSection as ResearchSectionType, 
  ResearchTemplate,
  NodeStatus,
  ToolProgressEvent,
  DeepResearchNode,
  CategoryOutput,
  ValidationOutput,
} from '@/types'
import ResearchReport from './ResearchReport'
import ClarificationPrompt from './ClarificationPrompt'
import ResearchProgress from './ResearchProgress'

// Research templates for empty state
const RESEARCH_TEMPLATES: ResearchTemplate[] = [
  {
    id: 'supplier-comparison',
    title: 'Supplier Comparison',
    description: 'Compare suppliers by capability, pricing, and reliability',
    icon: 'Scale',
    prompt: 'Compare [Supplier A] vs [Supplier B] for [material/product]. Include pricing trends, lead times, quality certifications, and capacity.',
    color: 'bg-blue-500',
  },
  {
    id: 'market-analysis',
    title: 'Market Analysis',
    description: 'Deep dive into market trends and forecasts',
    icon: 'TrendingUp',
    prompt: 'Analyze the market outlook for [material/industry] over the next 2-3 years. Include demand drivers, supply constraints, and price projections.',
    color: 'bg-emerald-500',
  },
  {
    id: 'company-profile',
    title: 'Company Deep Dive',
    description: 'Comprehensive analysis of a company',
    icon: 'Building2',
    prompt: 'Provide a comprehensive profile of [company name]. Include financials, product portfolio, recent news, strategic initiatives, and competitive positioning.',
    color: 'bg-violet-500',
  },
  {
    id: 'regulatory-impact',
    title: 'Regulatory Impact',
    description: 'Analyze regulatory changes and compliance',
    icon: 'FileText',
    prompt: 'Analyze the impact of [regulation/policy] on the composites industry. Include compliance requirements, timeline, and affected segments.',
    color: 'bg-amber-500',
  },
  {
    id: 'competitive-landscape',
    title: 'Competitive Landscape',
    description: 'Map competitors in a market segment',
    icon: 'Globe',
    prompt: 'Map the competitive landscape for [product category/market segment]. Include market share estimates, key differentiators, and emerging players.',
    color: 'bg-rose-500',
  },
  {
    id: 'supply-chain-risk',
    title: 'Supply Chain Risk',
    description: 'Assess supply chain vulnerabilities',
    icon: 'BarChart3',
    prompt: 'Assess supply chain risks for [material/component]. Include geographic concentration, alternative suppliers, and mitigation strategies.',
    color: 'bg-cyan-500',
  },
]

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const iconMap: Record<string, React.ElementType> = {
  Scale,
  TrendingUp,
  Building2,
  FileText,
  Globe,
  BarChart3,
}

interface ResearchCanvasProps {
  sections: ResearchSectionType[]
  activeSectionId: string | null
  onSectionsReorder: (sections: ResearchSectionType[]) => void
  onSectionCollapse: (id: string) => void
  onSectionDelete: (id: string) => void
  onSectionAddToReport: (section: ResearchSectionType) => void
  onAddAllToReport: () => void
  onTemplateSelect: (prompt: string) => void

  // Deep research props
  isResearching?: boolean
  researchStatus?: string
  clarification?: any | null
  deepResearchReport?: any | null
  onStartResearch?: (prompt: string) => void
  onCancelResearch?: () => void
  
  // Progress tracking props
  nodeStatuses?: NodeStatus[]
  toolProgress?: ToolProgressEvent[]
  activeNode?: DeepResearchNode | null
  isCacheHit?: boolean
  categoryOutput?: CategoryOutput | null
  validationOutput?: ValidationOutput | null
  researchError?: string | null
}

export default function ResearchCanvas({
  sections,
  activeSectionId,
  onSectionsReorder,
  onSectionCollapse,
  onSectionDelete,
  onSectionAddToReport,
  onAddAllToReport,
  onTemplateSelect,
  isResearching,
  researchStatus,
  clarification,
  deepResearchReport,
  onStartResearch,
  onCancelResearch,
  nodeStatuses,
  toolProgress,
  activeNode,
  isCacheHit,
  categoryOutput,
  validationOutput,
  researchError,
}: ResearchCanvasProps) {
  const [draggedId, setDraggedId] = useState<string | null>(null)
  const [dragOverId, setDragOverId] = useState<string | null>(null)

  // Drag and drop handlers
  const handleDragStart = useCallback((e: React.DragEvent, id: string) => {
    setDraggedId(id)
    e.dataTransfer.effectAllowed = 'move'
  }, [])

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'
  }, [])

  const handleDragEnter = useCallback((id: string) => {
    if (draggedId && draggedId !== id) {
      setDragOverId(id)
    }
  }, [draggedId])

  const handleDrop = useCallback((e: React.DragEvent, targetId: string) => {
    e.preventDefault()
    if (!draggedId || draggedId === targetId) {
      setDraggedId(null)
      setDragOverId(null)
      return
    }

    const draggedIndex = sections.findIndex(s => s.id === draggedId)
    const targetIndex = sections.findIndex(s => s.id === targetId)

    if (draggedIndex === -1 || targetIndex === -1) return

    const newSections = [...sections]
    const [removed] = newSections.splice(draggedIndex, 1)
    newSections.splice(targetIndex, 0, removed)

    onSectionsReorder(newSections)
    setDraggedId(null)
    setDragOverId(null)
  }, [draggedId, sections, onSectionsReorder])

  const handleDragEnd = useCallback(() => {
    setDraggedId(null)
    setDragOverId(null)
  }, [])

  // Empty state - show templates
  if (sections.length === 0) {
    return (
      <div className="h-full overflow-auto bg-gradient-to-br from-slate-50 to-emerald-50/30 p-6">
        <div className="max-w-3xl mx-auto">
          {/* Welcome Header */}
          <div className="text-center mb-8">
            <div className="inline-flex items-center gap-2 px-3 py-1 bg-emerald-100 text-emerald-700 rounded-full text-sm font-medium mb-4">
              <Search size={14} />
              Research Canvas
            </div>
            <h1 className="text-2xl font-bold text-slate-900 mb-2">
              Start Your Research
            </h1>
            <p className="text-slate-600 max-w-md mx-auto">
              Ask questions in the chat to generate comprehensive analysis.
              Your insights will appear here as sections you can organize and export.
            </p>
          </div>

          {/* Quick Start Templates */}
          <div className="mb-8">
            <div className="flex items-center gap-2 mb-4">
              <BookOpen size={18} className="text-slate-500" />
              <h2 className="font-semibold text-slate-800">Quick Start Templates</h2>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              {RESEARCH_TEMPLATES.map((template) => {
                const IconComponent = iconMap[template.icon]
                return (
                  <button
                    key={template.id}
                    onClick={() => onTemplateSelect(template.prompt)}
                    className="group p-4 bg-white border border-slate-200 rounded-xl hover:border-emerald-300 hover:shadow-md transition-all text-left"
                  >
                    <div className={cn(
                      "w-10 h-10 rounded-lg flex items-center justify-center mb-3",
                      template.color
                    )}>
                      {IconComponent && <IconComponent size={20} className="text-white" />}
                    </div>
                    <h3 className="font-medium text-slate-800 group-hover:text-emerald-700 transition-colors">
                      {template.title}
                    </h3>
                    <p className="text-xs text-slate-500 mt-1 line-clamp-2">
                      {template.description}
                    </p>
                    <div className="flex items-center gap-1 mt-3 text-xs text-emerald-600 opacity-0 group-hover:opacity-100 transition-opacity">
                      Use template
                      <ArrowRight size={12} />
                    </div>
                  </button>
                )
              })}
            </div>
          </div>

          {/* Tips */}
          <div className="bg-white/60 border border-slate-200 rounded-xl p-4">
            <h3 className="font-medium text-slate-700 text-sm mb-2">💡 Research Tips</h3>
            <ul className="text-xs text-slate-500 space-y-1">
              <li>• Be specific with company names and materials for better results</li>
              <li>• Ask follow-up questions to dive deeper into any topic</li>
              <li>• Each new topic creates a new section you can organize</li>
              <li>• Add sections to your report in any order you choose</li>
            </ul>
          </div>
        </div>
      </div>
    )
  }

  // Canvas with sections
  return (
    <div className="h-full flex flex-col bg-slate-50">
      {/* Canvas Header */}
      <div className="shrink-0 px-4 py-3 bg-white border-b border-slate-200 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Search size={16} className="text-emerald-600" />
          <span className="font-medium text-slate-700">
            {sections.length} Research {sections.length === 1 ? 'Section' : 'Sections'}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={onAddAllToReport}
            className="gap-1.5"
          >
            <Plus size={14} />
            Add All to Report
          </Button>
        </div>
      </div>

      {/* Sections List */}
      <div className="flex-1 overflow-auto p-4">
        <div className="max-w-4xl mx-auto space-y-6">
          {/* Clarification Overlay */}
          {clarification && onStartResearch && (
            <div className="my-8">
              <ClarificationPrompt
                question={clarification}
                onResponse={(resp) => onStartResearch(resp)}
              />
            </div>
          )}

          {/* Research Progress */}
          {isResearching && nodeStatuses && toolProgress && (
            <div className="space-y-4">
              <ResearchProgress
                nodeStatuses={nodeStatuses}
                toolProgress={toolProgress}
                activeNode={activeNode || null}
                isCacheHit={isCacheHit || false}
              />
              {onCancelResearch && (
                <div className="text-center">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={onCancelResearch}
                    className="text-slate-500 hover:text-red-500 gap-1.5"
                  >
                    <XCircle size={14} />
                    Cancel Research
                  </Button>
                </div>
              )}
            </div>
          )}

          {/* Fallback progress (if no node statuses available) */}
          {isResearching && !nodeStatuses && (
            <div className="bg-white rounded-xl border border-emerald-200 p-8 text-center shadow-sm">
              <Loader2 size={32} className="text-emerald-500 animate-spin mx-auto mb-4" />
              <h3 className="text-lg font-semibold text-slate-800 mb-1">{researchStatus}</h3>
              <p className="text-sm text-slate-500">Our agents are analyzing financial reports and industry news.</p>
            </div>
          )}

          {/* Research Error */}
          {researchError && (
            <div className="bg-red-50 rounded-xl border border-red-200 p-6 shadow-sm">
              <div className="flex items-start gap-3">
                <XCircle className="text-red-500 shrink-0 mt-0.5" size={20} />
                <div>
                  <h3 className="font-semibold text-red-800 mb-1">Research Error</h3>
                  <p className="text-sm text-red-600">{researchError}</p>
                  {onStartResearch && (
                    <Button
                      variant="secondary"
                      size="sm"
                      className="mt-3"
                      onClick={() => onStartResearch('')}
                    >
                      Try Again
                    </Button>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Deep Research Report */}
          {deepResearchReport && (
            <ResearchReport report={deepResearchReport} />
          )}

          {/* Legacy Sections (if any) */}
          <div
            className="space-y-4"
            onDragEnd={handleDragEnd}
          >
            {sections.filter(s => !s.isDeepResearch).map((section) => (
              <div
                key={section.id}
                onDragEnter={() => handleDragEnter(section.id)}
              >
                <ResearchSection
                  section={section}
                  isActive={section.id === activeSectionId}
                  onCollapse={onSectionCollapse}
                  onDelete={onSectionDelete}
                  onAddToReport={onSectionAddToReport}
                  onDragStart={handleDragStart}
                  onDragOver={handleDragOver}
                  onDrop={handleDrop}
                  isDragging={draggedId === section.id}
                  dragOverId={dragOverId}
                />
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
