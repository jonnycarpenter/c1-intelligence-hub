'use client'

import { useState, useCallback, useMemo, useRef, useEffect } from 'react'
import { cn } from '@/lib/utils'
import Sidebar from '@/components/layout/Sidebar'
import AppHeader from '@/components/layout/AppHeader'
import { PulseDashboard } from '@/components/dashboard'
import { ChatInterface } from '@/components/chat'
import { ReportDrawer } from '@/components/report'
import { ResearchDashboard } from '@/components/research'
import { ProductsDashboard } from '@/components/products'
import { CompaniesDashboard } from '@/components/companies'
import { IndustriesDashboard } from '@/components/industries'
import { FieldIntelDashboard } from '@/components/field-intel'
import { PipelineDashboard } from '@/components/pipeline'
// import { ImportYetiDashboard } from '@/components/importyeti' // ARCHIVED - Trade Intel feature
import DataPreferencesDashboard from '@/components/data-preferences/DataPreferencesDashboard'
import { WelcomeTourModal } from '@/components/welcome'
import { useDigest, useStreamingChat, useDeepResearch } from '@/hooks'
import { api } from '@/lib/api'
import type { Mode, DigestItem, ReportItem, ResearchSection, RecentSearch, Message } from '@/types'

export default function Home() {
  // Core state
  const [activeMode, setActiveMode] = useState<Mode>('pulse')
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [isReportOpen, setIsReportOpen] = useState(false)
  const [showWelcomeTour, setShowWelcomeTour] = useState(false)

  // Check if first visit and show welcome tour
  useEffect(() => {
    const hasSeenTour = localStorage.getItem('c1-hub-tour-seen')
    if (!hasSeenTour) {
      setShowWelcomeTour(true)
    }
  }, [])

  const handleCloseTour = () => {
    setShowWelcomeTour(false)
    localStorage.setItem('c1-hub-tour-seen', 'true')
  }

  // Research state
  const [researchSections, setResearchSections] = useState<ResearchSection[]>([])
  const [activeSectionId, setActiveSectionId] = useState<string | null>(null)
  const [recentSearches, setRecentSearches] = useState<RecentSearch[]>([])
  const researchIdCounter = useRef(0)

  // Fetch digest data from API
  const {
    items: digestItems,
    stats: digestStats,
    isLoading: digestLoading,
    error: digestError,
    refresh: refreshDigest
  } = useDigest({ hours: activeMode === 'pulse' ? 168 : 24 })

  // Streaming chat state
  const {
    messages,
    sendMessage,
    isStreaming,
    streamingState,
    clearProducts,
    clearCompanies,
    clearIndustries,
    setResearchContentCallback,
    setMessages,
  } = useStreamingChat()

  // Deep research state
  const {
    isResearching,
    status: researchStatus,
    clarification,
    report: deepResearchReport,
    startDeepResearch,
    resetResearch,
    cancelResearch,
    // Progress tracking
    nodeStatuses,
    toolProgress,
    activeNode,
    isCacheHit,
    categoryOutput,
    validationOutput,
    error: researchError,
  } = useDeepResearch()

  // Report state
  const [reportItems, setReportItems] = useState<ReportItem[]>([])

  // Stats for dashboard - computed from API data
  const stats = useMemo(() => ({
    criticalAlerts: (digestItems || []).filter(d => d.priority === 'critical').length,
    priceMovements: digestStats?.byCategory?.['pricing'] || 0,
    companiesMonitored: 70, // This would come from a different API
    newsItems: (digestItems || []).length,
  }), [digestItems, digestStats])

  // Handle sending a message with streaming
  const handleSendMessage = useCallback(async (content: string) => {
    await sendMessage(content, activeMode)
  }, [activeMode, sendMessage])

  // Handle asking about a digest item
  const handleAskAbout = useCallback((item: DigestItem) => {
    handleSendMessage(`Tell me more about: ${item.title}`)
  }, [handleSendMessage])

  // Handle adding to report
  const handleAddToReport = useCallback((item: DigestItem) => {
    const reportItem: ReportItem = {
      id: item.id,
      title: item.title,
      summary: item.summary,
      category: item.category,
      priority: item.priority,
      addedAt: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    }

    // Don't add duplicates
    setReportItems(prev => {
      if (prev.some(r => r.id === item.id)) return prev
      return [...prev, reportItem]
    })

    // Open report drawer when adding
    setIsReportOpen(true)
  }, [])

  // Handle removing from report
  const handleRemoveFromReport = useCallback((id: string) => {
    setReportItems(prev => prev.filter(r => r.id !== id))
  }, [])

  // Handle export
  const handleExport = useCallback(async (format: 'pdf' | 'docx' | 'pptx') => {
    if (reportItems.length === 0) return

    try {
      // Call export API
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/reports/export`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-Name': localStorage.getItem('userName') || 'Anonymous',
          'X-User-Team': localStorage.getItem('userTeam') || 'All Others',
        },
        body: JSON.stringify({
          format,
          items: reportItems,
          title: `Intelligence Report - ${new Date().toLocaleDateString()}`,
        }),
      })

      if (!response.ok) {
        throw new Error(`Export failed: ${response.statusText}`)
      }

      // Download the file
      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `intelligence-report-${Date.now()}.${format}`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)

      // Also save to memory for future reference
      await api.saveToMemory({
        type: 'research_export',
        question: `Research report exported (${reportItems.length} items)`,
        answer: reportItems.map(item => `**${item.title}**: ${item.summary}`).join('\n\n'),
        tags: reportItems.map(item => item.category).filter((v, i, a) => a.indexOf(v) === i),
      })

      console.log('Export complete and saved to memory')
    } catch (error) {
      console.error('Export failed:', error)
      // TODO: Show error toast to user
    }
  }, [reportItems])

  // Handle refresh
  const handleRefresh = useCallback(async () => {
    await refreshDigest()
  }, [refreshDigest])

  // Generate title from query
  const generateSectionTitle = (query: string): string => {
    // Extract key terms or use first ~50 chars
    const cleaned = query.replace(/^\[.*?\]\s*/, '').trim()
    if (cleaned.length <= 50) return cleaned
    return cleaned.substring(0, 47) + '...'
  }

  // Handle research-specific message sending
  const handleResearchMessage = useCallback(async (content: string) => {
    if (activeMode === 'research') {
      // Create a new section for this research
      const sectionId = `research-${Date.now()}-${researchIdCounter.current++}`
      const newSection: ResearchSection = {
        id: sectionId,
        title: generateSectionTitle(content),
        query: content,
        content: '', // Will be populated by streaming or deep research
        timestamp: new Date().toISOString(),
        isCollapsed: false,
        isDeepResearch: true, // Mark as deep research
      }

      setResearchSections(prev => [...prev, newSection])
      setActiveSectionId(sectionId)

      // Add to recent searches
      const recentSearch: RecentSearch = {
        id: `recent-${Date.now()}`,
        query: content,
        title: generateSectionTitle(content),
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        sectionId: sectionId,
      }
      setRecentSearches(prev => [recentSearch, ...prev.slice(0, 9)])

      // Add message to chat history for visual feedback
      const userMessage: Message = {
        id: `user_${Date.now()}`,
        role: 'user',
        content,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      }
      setMessages(prev => [...prev, userMessage])

      // Start deep research instead of regular streaming chat
      await startDeepResearch(content, [])
      return
    }

    // Send to streaming chat
    await sendMessage(content, activeMode)
  }, [activeMode, sendMessage])

  // Update active research section with streaming content
  const updateResearchSectionContent = useCallback((content: string) => {
    if (activeSectionId && activeMode === 'research') {
      setResearchSections(prev =>
        prev.map(s =>
          s.id === activeSectionId ? { ...s, content } : s
        )
      )
    }
  }, [activeSectionId, activeMode])

  // Register/unregister research content callback when active section changes
  useEffect(() => {
    if (activeSectionId && activeMode === 'research') {
      setResearchContentCallback(updateResearchSectionContent)
    } else {
      setResearchContentCallback(null)
    }
    // Cleanup on unmount or when section changes
    return () => setResearchContentCallback(null)
  }, [activeSectionId, activeMode, updateResearchSectionContent, setResearchContentCallback])

  // Clear active section when streaming completes and save to backend
  useEffect(() => {
    if (!isStreaming && activeSectionId) {
      // Find the completed section and save it
      const completedSection = researchSections.find(s => s.id === activeSectionId)
      if (completedSection && completedSection.content) {
        // Save research report to backend (fire and forget)
        api.saveResearchReport({
          query: completedSection.query,
          title: completedSection.title,
          content: completedSection.content,
          agent: 'market_scout',
          sources: completedSection.sources?.map(s => ({
            title: s.title,
            name: s.name,
            url: s.url,
          })) || [],
        }).catch(err => {
          console.error('Failed to save research report:', err)
        })
      }
      // Clear active section
      setActiveSectionId(null)
    }
  }, [isStreaming, activeSectionId, researchSections])

  // Scroll to a specific section in the canvas
  const handleScrollToSection = useCallback((sectionId: string) => {
    // Could add actual scroll logic here
    console.log('Scroll to section:', sectionId)
  }, [])

  // Handle adding ReportItem (used by research sections)
  const handleAddReportItem = useCallback((item: ReportItem) => {
    // Don't add duplicates
    setReportItems(prev => {
      if (prev.some(r => r.id === item.id)) return prev
      return [...prev, item]
    })
    setIsReportOpen(true)
  }, [])

  return (
    <div className="h-screen flex bg-slate-100">
      {/* Sidebar */}
      <Sidebar
        activeMode={activeMode}
        setActiveMode={setActiveMode}
        collapsed={sidebarCollapsed}
        setCollapsed={setSidebarCollapsed}
        reportCount={reportItems.length}
        onOpenReport={() => setIsReportOpen(true)}
      />

      {/* Main content area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <AppHeader
          activeMode={activeMode}
          onRefresh={handleRefresh}
        />

        {/* Main split view */}
        <div className="flex-1 flex overflow-hidden">
          {/* Left panel - Dashboard/Content */}
          <div className={cn(
            "flex-1 min-w-0 overflow-hidden border-r border-slate-200",
            activeMode === 'pulse' && "border-r-0"
          )}>
            {activeMode === 'pulse' && (
              <PulseDashboard
                digestItems={digestItems}
                stats={digestStats}
                onAskAbout={handleAskAbout}
                onAddToReport={handleAddToReport}
                isLoading={digestLoading}
                error={digestError as any}
              />
            )}
            {activeMode === 'research' && (
              <ResearchDashboard
                sections={researchSections}
                activeSectionId={activeSectionId}
                recentSearches={recentSearches}
                onSectionsUpdate={setResearchSections}
                onStartResearch={handleResearchMessage}
                onAddToReport={handleAddReportItem}
                onScrollToSection={handleScrollToSection}
                onCancelResearch={cancelResearch}
                // Deep research state
                isResearching={isResearching}
                researchStatus={researchStatus}
                clarification={clarification}
                deepResearchReport={deepResearchReport}
                // Progress tracking
                nodeStatuses={nodeStatuses}
                toolProgress={toolProgress}
                activeNode={activeNode}
                isCacheHit={isCacheHit}
                categoryOutput={categoryOutput}
                validationOutput={validationOutput}
                researchError={researchError}
              />
            )}
            {activeMode === 'products' && (
              <ProductsDashboard
                onAskAboutProduct={handleSendMessage}
                displayProducts={streamingState.products.length > 0 ? streamingState.products : undefined}
                onClearDisplayProducts={clearProducts}
              />
            )}
            {activeMode === 'companies' && (
              <div className="relative h-full">
                {/* Disabled overlay */}
                <div className="absolute inset-0 bg-slate-200/60 backdrop-blur-[1px] z-10 flex items-center justify-center">
                  <div className="bg-white rounded-xl shadow-lg px-8 py-6 text-center max-w-md mx-4">
                    <div className="w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center mx-auto mb-4">
                      <span className="text-2xl">🏢</span>
                    </div>
                    <h3 className="text-lg font-semibold text-slate-800 mb-2">Company Intelligence Coming Soon</h3>
                    <p className="text-sm text-slate-500">We're building comprehensive company tracking and analysis features. Stay tuned!</p>
                  </div>
                </div>
                {/* Greyed out content */}
                <div className="grayscale pointer-events-none opacity-40">
                  <CompaniesDashboard
                    onAskAboutCompany={handleSendMessage}
                    displayCompanies={streamingState.companies.length > 0 ? streamingState.companies : undefined}
                    onClearDisplayCompanies={clearCompanies}
                  />
                </div>
              </div>
            )}
            {activeMode === 'industries' && (
              <div className="relative h-full">
                {/* Disabled overlay */}
                <div className="absolute inset-0 bg-slate-200/60 backdrop-blur-[1px] z-10 flex items-center justify-center">
                  <div className="bg-white rounded-xl shadow-lg px-8 py-6 text-center max-w-md mx-4">
                    <div className="w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center mx-auto mb-4">
                      <span className="text-2xl">🏭</span>
                    </div>
                    <h3 className="text-lg font-semibold text-slate-800 mb-2">Industry Insights Coming Soon</h3>
                    <p className="text-sm text-slate-500">We're building detailed industry analysis and trend tracking. Stay tuned!</p>
                  </div>
                </div>
                {/* Greyed out content */}
                <div className="grayscale pointer-events-none opacity-40">
                  <IndustriesDashboard
                    onAskAboutIndustry={handleSendMessage}
                    displayIndustries={streamingState.industries.length > 0 ? streamingState.industries : undefined}
                    onClearDisplayIndustries={clearIndustries}
                  />
                </div>
              </div>
            )}
            {activeMode === 'field-sales' && (
              <FieldIntelDashboard />
            )}
            {activeMode === 'pipeline' && (
              <PipelineDashboard />
            )}
            {/* ARCHIVED - Trade Intel feature */}
            {/* {activeMode === 'importyeti' && (
              <ImportYetiDashboard />
            )} */}
            {activeMode === 'data-preferences' && (
              <DataPreferencesDashboard
                onAskAgent={handleSendMessage}
              />
            )}
          </div>

          {/* Right panel - Chat (hidden for pulse, pipeline, products, field-sales, and data-preferences) */}
          {activeMode !== 'pulse' && activeMode !== 'pipeline' && activeMode !== 'products' && activeMode !== 'field-sales' && activeMode !== 'data-preferences' && (
            <div className="w-[400px] shrink-0 border-l border-slate-200 bg-white">
              <ChatInterface
                mode={activeMode}
                messages={messages}
                onSendMessage={activeMode === 'research' ? handleResearchMessage : handleSendMessage}
                isLoading={false}
                isStreaming={isStreaming}
                streamingContent={streamingState.content}
                streamingThinking={streamingState.thinkingSteps}
                currentAgent={streamingState.currentAgent}
                hideStreamingContent={activeMode === 'research'}
              />
            </div>
          )}
        </div>
      </div>

      {/* Report Drawer */}
      <ReportDrawer
        isOpen={isReportOpen}
        onClose={() => setIsReportOpen(false)}
        items={reportItems}
        onRemoveItem={handleRemoveFromReport}
        onClearAll={() => setReportItems([])}
        onExport={handleExport}
        onGeneratePodcast={() => console.log('Generating podcast...')}
      />

      {/* Welcome Tour Modal */}
      <WelcomeTourModal
        isOpen={showWelcomeTour}
        onClose={handleCloseTour}
      />
    </div>
  )
}
