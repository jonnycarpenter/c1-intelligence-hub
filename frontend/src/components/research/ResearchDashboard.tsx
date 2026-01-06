'use client'

import { useState, useCallback } from 'react'
import ResearchCanvas from './ResearchCanvas'
import ResearchSidebar from './ResearchSidebar'
import SavedReportsPanel from './SavedReportsPanel'
import { api } from '@/lib/api'
import { useToast } from '@/components/ui'
import type { 
  ResearchSection, 
  RecentSearch, 
  ReportItem, 
  Category,
  NodeStatus,
  ToolProgressEvent,
  DeepResearchNode,
  CategoryOutput,
  ValidationOutput,
} from '@/types'

interface ResearchDashboardProps {
  // From streaming/state
  sections: ResearchSection[]
  activeSectionId: string | null
  recentSearches: RecentSearch[]

  // Actions
  onSectionsUpdate: (sections: ResearchSection[]) => void
  onStartResearch: (prompt: string) => void
  onAddToReport: (item: ReportItem) => void
  onScrollToSection?: (sectionId: string) => void
  onCancelResearch?: () => void

  // Deep research props
  isResearching?: boolean
  researchStatus?: string
  clarification?: any | null
  deepResearchReport?: any | null
  
  // Progress tracking props
  nodeStatuses?: NodeStatus[]
  toolProgress?: ToolProgressEvent[]
  activeNode?: DeepResearchNode | null
  isCacheHit?: boolean
  categoryOutput?: CategoryOutput | null
  validationOutput?: ValidationOutput | null
  researchError?: string | null
  
  // Timeout handling
  isTimeout?: boolean
  timeoutInfo?: {
    elapsed_seconds?: number
    timeout_seconds?: number
    completed_nodes?: string[]
    active_nodes?: string[]
  } | null
}

export default function ResearchDashboard({
  sections,
  activeSectionId,
  recentSearches,
  onSectionsUpdate,
  onStartResearch,
  onAddToReport,
  onScrollToSection,
  onCancelResearch,
  isResearching,
  researchStatus,
  clarification,
  deepResearchReport,
  nodeStatuses,
  toolProgress,
  activeNode,
  isCacheHit,
  categoryOutput,
  validationOutput,
  researchError,
  isTimeout,
  timeoutInfo,
}: ResearchDashboardProps) {
  const { addToast } = useToast()
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [showSavedReports, setShowSavedReports] = useState(false)
  const [selectedReportId, setSelectedReportId] = useState<string | null>(null)

  // Handle template selection - sends to chat
  const handleTemplateSelect = useCallback((prompt: string) => {
    onStartResearch(prompt)
  }, [onStartResearch])

  // Handle opening a saved report
  const handleOpenSavedReport = useCallback(async (reportId: string) => {
    try {
      const report = await api.getSavedReportById(reportId)
      if (report) {
        // Create a new section from the saved report
        const sectionId = `saved-${reportId}-${Date.now()}`
        const newSection: ResearchSection = {
          id: sectionId,
          title: report.title || report.query,
          query: report.query,
          content: report.executive_summary || '',
          timestamp: report.created_at,
          isCollapsed: false,
          isDeepResearch: true,
        }
        onSectionsUpdate([...sections, newSection])
        setShowSavedReports(false)
      }
    } catch (err) {
      addToast({ type: 'error', title: 'Load failed', message: 'Could not load saved report' })
    }
  }, [sections, onSectionsUpdate, addToast])

  // Handle continuing research on a saved report
  const handleContinueResearch = useCallback((reportId: string, query: string) => {
    setShowSavedReports(false)
    onStartResearch(`Continue research on: ${query}`)
  }, [onStartResearch])

  // Handle viewing all saved reports
  const handleViewAllSavedReports = useCallback(() => {
    setShowSavedReports(true)
  }, [])

  // Handle recent search click - scroll to section or restart research
  const handleRecentSearchClick = useCallback((search: RecentSearch) => {
    if (search.sectionId && onScrollToSection) {
      // Section still exists on canvas, scroll to it
      onScrollToSection(search.sectionId)
    } else {
      // Re-run the search
      onStartResearch(search.query)
    }
  }, [onStartResearch, onScrollToSection])

  // Handle section collapse toggle
  const handleSectionCollapse = useCallback((id: string) => {
    onSectionsUpdate(
      sections.map(s =>
        s.id === id ? { ...s, isCollapsed: !s.isCollapsed } : s
      )
    )
  }, [sections, onSectionsUpdate])

  // Handle section delete
  const handleSectionDelete = useCallback((id: string) => {
    onSectionsUpdate(sections.filter(s => s.id !== id))
  }, [sections, onSectionsUpdate])

  // Handle section add to report
  const handleSectionAddToReport = useCallback((section: ResearchSection) => {
    const reportItem: ReportItem = {
      id: section.id,
      title: section.title,
      summary: section.content.substring(0, 200) + '...',
      content: section.content,
      category: 'market' as Category, // Default category
      priority: 'medium',
      addedAt: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      source: 'research',
    }
    onAddToReport(reportItem)
  }, [onAddToReport])

  // Handle add all sections to report
  const handleAddAllToReport = useCallback(() => {
    sections.forEach(section => {
      handleSectionAddToReport(section)
    })
  }, [sections, handleSectionAddToReport])

  // Handle sections reorder (from drag & drop)
  const handleSectionsReorder = useCallback((newSections: ResearchSection[]) => {
    onSectionsUpdate(newSections)
  }, [onSectionsUpdate])

  return (
    <div className="h-full flex overflow-hidden">
      {/* Left Sidebar - Templates & Recent */}
      <ResearchSidebar
        recentSearches={recentSearches}
        onTemplateSelect={handleTemplateSelect}
        onRecentSearchClick={handleRecentSearchClick}
        isCollapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
        onOpenSavedReport={handleOpenSavedReport}
        onViewAllSavedReports={handleViewAllSavedReports}
      />

      {/* Main Canvas or Saved Reports Panel */}
      <div className="flex-1 min-w-0">
        {showSavedReports ? (
          <SavedReportsPanel
            onOpenReport={handleOpenSavedReport}
            onContinueResearch={handleContinueResearch}
            onBack={() => setShowSavedReports(false)}
          />
        ) : (
          <ResearchCanvas
            sections={sections}
            activeSectionId={activeSectionId}
            onSectionsReorder={handleSectionsReorder}
            onSectionCollapse={handleSectionCollapse}
            onSectionDelete={handleSectionDelete}
            onSectionAddToReport={handleSectionAddToReport}
            onAddAllToReport={handleAddAllToReport}
            onTemplateSelect={handleTemplateSelect}
            isResearching={isResearching}
            researchStatus={researchStatus}
            clarification={clarification}
            deepResearchReport={deepResearchReport}
            onStartResearch={onStartResearch}
            onCancelResearch={onCancelResearch}
            nodeStatuses={nodeStatuses}
            toolProgress={toolProgress}
            activeNode={activeNode}
            isCacheHit={isCacheHit}
            categoryOutput={categoryOutput}
            validationOutput={validationOutput}
            researchError={researchError}
            isTimeout={isTimeout}
            timeoutInfo={timeoutInfo}
          />
        )}
      </div>
    </div>
  )
}
