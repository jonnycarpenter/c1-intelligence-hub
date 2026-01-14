import { useState, useCallback, useEffect } from 'react'
import { API_BASE } from '@/lib/config'
import type {
  PipelineProspect,
  PipelineContact,
  ProspectSearchResult,
  ContactSearchResult,
  ProspectSearchResponse,
  ContactSearchResponse,
  EnhancedProspectSearchResult,
  EnhancedContactSearchResult,
  EnhancedTriggerEventResult,
  EnhancedProspectSearchResponse,
  EnhancedContactSearchResponse,
  EnhancedTriggerEventSearchResponse,
  SearchBlock,
  AgentChatResponse,
  // Apollo.io types
  ApolloEnrichmentResult,
  ApolloContactTeaserResult,
  ApolloContactRevealedResult,
  ApolloCreditStatus,
} from '@/types'

// Conversation message type for agent chat
interface ConversationMessage {
  role: 'user' | 'assistant'
  content: string
  timestamp: string
  search_blocks?: SearchBlock[]
}

// Local storage keys
const STORAGE_KEYS = {
  PROSPECTS: 'c1-pipeline-prospects',
  CONTACTS: 'c1-pipeline-contacts',
  PIPELINE_MODE: 'c1-pipeline-mode',
}

// Pipeline search modes
type PipelineMode = 'instant' | 'full'

// Webset status response type
interface WebsetStatusResponse {
  webset_id: string
  status: 'running' | 'completed' | 'failed' | 'idle'
  progress?: number
  total_items?: number
  completed_items?: number
  error_message?: string
}

// Generate unique ID
function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
}

export function usePipeline() {
  // Search state (legacy direct API calls)
  const [isSearching, setIsSearching] = useState(false)
  const [searchError, setSearchError] = useState<string | null>(null)
  const [prospectResults, setProspectResults] = useState<EnhancedProspectSearchResult[]>([])
  const [contactResults, setContactResults] = useState<EnhancedContactSearchResult[]>([])
  const [triggerResults, setTriggerResults] = useState<EnhancedTriggerEventResult[]>([])
  const [lastQueryType, setLastQueryType] = useState<'similar' | 'search' | 'triggers' | null>(null)

  // Agent chat state
  const [isAgentThinking, setIsAgentThinking] = useState(false)
  const [agentError, setAgentError] = useState<string | null>(null)
  const [conversationHistory, setConversationHistory] = useState<ConversationMessage[]>([])
  const [searchBlocks, setSearchBlocks] = useState<SearchBlock[]>([])
  const [suggestedFollowups, setSuggestedFollowups] = useState<string[]>([])

  // Pipeline mode state
  const [pipelineMode, setPipelineModeState] = useState<PipelineMode>('instant')

  // Webset polling state
  const [pollingWebsets, setPollingWebsets] = useState<Set<string>>(new Set())

  // Saved data state (localStorage)
  const [savedProspects, setSavedProspects] = useState<PipelineProspect[]>([])
  const [savedContacts, setSavedContacts] = useState<PipelineContact[]>([])

  // Load saved data from localStorage on mount
  useEffect(() => {
    try {
      const storedProspects = localStorage.getItem(STORAGE_KEYS.PROSPECTS)
      const storedContacts = localStorage.getItem(STORAGE_KEYS.CONTACTS)
      const storedMode = localStorage.getItem(STORAGE_KEYS.PIPELINE_MODE)

      if (storedProspects) {
        setSavedProspects(JSON.parse(storedProspects))
      }
      if (storedContacts) {
        setSavedContacts(JSON.parse(storedContacts))
      }
      if (storedMode === 'instant' || storedMode === 'full') {
        setPipelineModeState(storedMode)
      }
    } catch (err) {
      console.error('Error loading pipeline data from localStorage:', err)
    }
  }, [])

  // Set pipeline mode and persist
  const setPipelineMode = useCallback((mode: PipelineMode) => {
    setPipelineModeState(mode)
    try {
      localStorage.setItem(STORAGE_KEYS.PIPELINE_MODE, mode)
    } catch (err) {
      console.error('Error saving pipeline mode:', err)
    }
  }, [])

  // Persist prospects to localStorage
  const persistProspects = useCallback((prospects: PipelineProspect[]) => {
    try {
      localStorage.setItem(STORAGE_KEYS.PROSPECTS, JSON.stringify(prospects))
    } catch (err) {
      console.error('Error saving prospects to localStorage:', err)
    }
  }, [])

  // Persist contacts to localStorage
  const persistContacts = useCallback((contacts: PipelineContact[]) => {
    try {
      localStorage.setItem(STORAGE_KEYS.CONTACTS, JSON.stringify(contacts))
    } catch (err) {
      console.error('Error saving contacts to localStorage:', err)
    }
  }, [])

  // ============================================
  // Search Functions
  // ============================================

  const findSimilarCompanies = useCallback(async (
    referenceUrl: string,
    numResults: number = 25,
    excludeSource: boolean = true
  ) => {
    setIsSearching(true)
    setSearchError(null)
    setProspectResults([])
    setLastQueryType('similar')

    try {
      // Use v2 endpoint for enhanced results with logos
      const response = await fetch(`${API_BASE}/api/pipeline/v2/similar`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          reference_url: referenceUrl,
          num_results: numResults,
          exclude_source: excludeSource,
        }),
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || `Error: ${response.statusText}`)
      }

      const data: EnhancedProspectSearchResponse = await response.json()
      setProspectResults(data.results)
      return data.results
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to find similar companies'
      setSearchError(message)
      console.error('Error finding similar companies:', err)
      return []
    } finally {
      setIsSearching(false)
    }
  }, [])

  const searchCompanies = useCallback(async (
    query: string,
    numResults: number = 25,
    includeDomains?: string[],
    excludeDomains?: string[]
  ) => {
    setIsSearching(true)
    setSearchError(null)
    setProspectResults([])
    setLastQueryType('search')

    try {
      // Use v2 endpoint for enhanced results with logos
      const response = await fetch(`${API_BASE}/api/pipeline/v2/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query,
          num_results: numResults,
          include_domains: includeDomains,
          exclude_domains: excludeDomains,
        }),
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || `Error: ${response.statusText}`)
      }

      const data: EnhancedProspectSearchResponse = await response.json()
      setProspectResults(data.results)
      return data.results
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to search companies'
      setSearchError(message)
      console.error('Error searching companies:', err)
      return []
    } finally {
      setIsSearching(false)
    }
  }, [])

  const findContacts = useCallback(async (
    role: string,
    industry?: string,
    company?: string,
    numResults: number = 10
  ) => {
    setIsSearching(true)
    setSearchError(null)
    setContactResults([])

    try {
      // Use v2 endpoint for enhanced results with logos
      const response = await fetch(`${API_BASE}/api/pipeline/v2/contacts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          role,
          industry,
          company,
          num_results: numResults,
        }),
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || `Error: ${response.statusText}`)
      }

      const data: EnhancedContactSearchResponse = await response.json()
      setContactResults(data.results)
      return data.results
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to find contacts'
      setSearchError(message)
      console.error('Error finding contacts:', err)
      return []
    } finally {
      setIsSearching(false)
    }
  }, [])

  const findTriggerEvents = useCallback(async (
    topic: string,
    daysBack: number = 30,
    numResults: number = 25
  ) => {
    setIsSearching(true)
    setSearchError(null)
    setTriggerResults([])
    setLastQueryType('triggers')

    try {
      const response = await fetch(`${API_BASE}/api/pipeline/v2/triggers`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          topic,
          days_back: daysBack,
          num_results: numResults,
        }),
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || `Error: ${response.statusText}`)
      }

      const data: EnhancedTriggerEventSearchResponse = await response.json()
      setTriggerResults(data.results)
      return data.results
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to find trigger events'
      setSearchError(message)
      console.error('Error finding trigger events:', err)
      return []
    } finally {
      setIsSearching(false)
    }
  }, [])

  // ============================================
  // Apollo.io Functions (Company Enrichment & Contact Discovery)
  // ============================================

  /**
   * Enrich company data using Apollo.io.
   * This is FREE and doesn't consume credits.
   * @param domain Company domain (e.g., "hexcel.com")
   */
  const enrichCompany = useCallback(async (domain: string): Promise<ApolloEnrichmentResult | null> => {
    setIsSearching(true)
    setSearchError(null)

    try {
      const response = await fetch(`${API_BASE}/api/pipeline/apollo/enrich/${encodeURIComponent(domain)}`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || `Error: ${response.statusText}`)
      }

      const data: ApolloEnrichmentResult = await response.json()
      return data
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to enrich company'
      setSearchError(message)
      console.error('Error enriching company:', err)
      return null
    } finally {
      setIsSearching(false)
    }
  }, [])

  /**
   * Enrich a specific prospect within a search block.
   * Updates the searchBlocks state to persist enrichment data.
   */
  const enrichProspect = useCallback(async (blockId: string, domain: string) => {
    const enrichment = await enrichCompany(domain)
    if (!enrichment) return null

    setSearchBlocks(prev => prev.map(block => {
      if (block.id === blockId && block.prospects) {
        return {
          ...block,
          prospects: block.prospects.map(p => {
            if (p.domain === domain) {
              return { ...p, apollo_enrichment: enrichment }
            }
            return p
          })
        }
      }
      return block
    }))

    return enrichment
  }, [enrichCompany])

  /**
   * Search for contacts at a company using Apollo.io.
   * This is FREE and doesn't consume credits - returns teasers (preview data).
   */
  const searchApolloContacts = useCallback(async (
    companyName?: string,
    companyDomain?: string,
    options?: {
      titles?: string[]
      department?: 'purchasing' | 'engineering' | 'executive'
      seniorities?: string[]
      numResults?: number
    }
  ): Promise<ApolloContactTeaserResult[]> => {
    setIsSearching(true)
    setSearchError(null)

    try {
      const response = await fetch(`${API_BASE}/api/pipeline/apollo/contacts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          company_name: companyName,
          company_domain: companyDomain,
          titles: options?.titles,
          department: options?.department,
          seniorities: options?.seniorities,
          num_results: options?.numResults ?? 10,
        }),
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || `Error: ${response.statusText}`)
      }

      const data = await response.json()
      return data.results as ApolloContactTeaserResult[]
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to search Apollo contacts'
      setSearchError(message)
      console.error('Error searching Apollo contacts:', err)
      return []
    } finally {
      setIsSearching(false)
    }
  }, [])

  /**
   * Reveal full contact details from Apollo.io.
   * ⚠️ COSTS 1 CREDIT - use wisely!
   * @param personId Apollo person ID from contact search results
   */
  const revealApolloContact = useCallback(async (personId: string): Promise<ApolloContactRevealedResult | null> => {
    setIsSearching(true)
    setSearchError(null)

    try {
      const response = await fetch(`${API_BASE}/api/pipeline/apollo/reveal`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          person_id: personId,
        }),
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        if (response.status === 429) {
          throw new Error(errorData.detail || 'Monthly credit limit reached')
        }
        throw new Error(errorData.detail || `Error: ${response.statusText}`)
      }

      const data: ApolloContactRevealedResult = await response.json()
      return data
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to reveal contact'
      setSearchError(message)
      console.error('Error revealing Apollo contact:', err)
      return null
    } finally {
      setIsSearching(false)
    }
  }, [])

  /**
   * Get Apollo.io credit usage status.
   * Check this before revealing contacts to see remaining balance.
   */
  const getApolloCredits = useCallback(async (): Promise<ApolloCreditStatus | null> => {
    try {
      const response = await fetch(`${API_BASE}/api/pipeline/apollo/credits`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || `Error: ${response.statusText}`)
      }

      const data: ApolloCreditStatus = await response.json()
      return data
    } catch (err) {
      console.error('Error getting Apollo credits:', err)
      return null
    }
  }, [])

  // ============================================
  // Agent Chat Functions
  // ============================================

  /**
   * Send a message to the Pipeline Agent.
   * The agent will understand natural language queries and execute appropriate searches.
   */
  const sendAgentMessage = useCallback(async (message: string) => {
    setIsAgentThinking(true)
    setAgentError(null)

    // Add user message to conversation history
    const userMessage: ConversationMessage = {
      role: 'user',
      content: message,
      timestamp: new Date().toISOString(),
    }

    setConversationHistory(prev => [...prev, userMessage])

    try {
      // Build conversation history for context
      const historyForApi = conversationHistory.map(msg => ({
        role: msg.role,
        content: msg.content,
      }))

      const response = await fetch(`${API_BASE}/api/pipeline/agent/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message,
          conversation_history: historyForApi,
          mode: pipelineMode,
        }),
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || `Error: ${response.statusText}`)
      }

      const data: AgentChatResponse = await response.json()

      // Add assistant message to conversation history
      const assistantMessage: ConversationMessage = {
        role: 'assistant',
        content: data.message,
        timestamp: new Date().toISOString(),
        search_blocks: data.search_blocks,
      }

      setConversationHistory(prev => [...prev, assistantMessage])

      // Accumulate search blocks (new ones on top)
      console.log('[usePipeline] Received search_blocks:', data.search_blocks.length, data.search_blocks)
      if (data.search_blocks.length > 0) {
        setSearchBlocks(prev => {
          const newBlocks = [...data.search_blocks, ...prev]
          console.log('[usePipeline] Setting searchBlocks state:', newBlocks.length, newBlocks)
          return newBlocks
        })

        // Start polling for any webset blocks
        data.search_blocks.forEach(block => {
          if (block.block_type === 'webset_building' && block.webset_id) {
            startWebsetPolling(block.webset_id)
          }
        })
      }

      // Update suggested followups
      setSuggestedFollowups(data.suggested_followups)

      return data
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to process your request'
      setAgentError(message)
      console.error('Error in agent chat:', err)

      // Add error message to conversation
      const errorMessage: ConversationMessage = {
        role: 'assistant',
        content: `I encountered an error: ${message}. Please try rephrasing your query.`,
        timestamp: new Date().toISOString(),
      }
      setConversationHistory(prev => [...prev, errorMessage])

      return null
    } finally {
      setIsAgentThinking(false)
    }
  }, [conversationHistory, pipelineMode])

  /**
   * Poll webset status and update search blocks when complete
   */
  const startWebsetPolling = useCallback((websetId: string) => {
    // Don't start duplicate polling
    if (pollingWebsets.has(websetId)) return

    setPollingWebsets(prev => new Set(prev).add(websetId))

    const pollInterval = setInterval(async () => {
      try {
        const response = await fetch(`${API_BASE}/api/pipeline/webset/${websetId}/status`)

        if (!response.ok) {
          console.error(`Error polling webset ${websetId}:`, response.statusText)
          return
        }

        const status: WebsetStatusResponse = await response.json()

        if (status.status === 'completed' || status.status === 'failed') {
          // Stop polling
          clearInterval(pollInterval)
          setPollingWebsets(prev => {
            const next = new Set(prev)
            next.delete(websetId)
            return next
          })

          // Update the search block
          setSearchBlocks(prev => prev.map(block => {
            if (block.webset_id === websetId) {
              return {
                ...block,
                webset_status: status.status,
                result_count: status.total_items || 0,
              }
            }
            return block
          }))
        }
      } catch (err) {
        console.error(`Error polling webset ${websetId}:`, err)
      }
    }, 5000) // Poll every 5 seconds

    // Clean up on unmount
    return () => clearInterval(pollInterval)
  }, [pollingWebsets])

  /**
   * Clear conversation and all search blocks
   */
  const clearConversation = useCallback(() => {
    setConversationHistory([])
    setSearchBlocks([])
    setSuggestedFollowups([])
    setAgentError(null)
    // Clear any webset polling
    setPollingWebsets(new Set())
  }, [])

  /**
   * Toggle expansion of a search block
   */
  const toggleBlockExpansion = useCallback((blockId: string) => {
    setSearchBlocks(prev =>
      prev.map(block =>
        block.id === blockId
          ? { ...block, is_expanded: !block.is_expanded }
          : block
      )
    )
  }, [])

  /**
   * Remove a search block from the display
   */
  const removeSearchBlock = useCallback((blockId: string) => {
    setSearchBlocks(prev => prev.filter(block => block.id !== blockId))
  }, [])

  // ============================================
  // Saved Prospects Management
  // ============================================

  const saveProspect = useCallback((result: EnhancedProspectSearchResult | ProspectSearchResult, notes?: string) => {
    // Handle both enhanced and legacy result types
    const enhancedResult = result as EnhancedProspectSearchResult

    const newProspect: PipelineProspect = {
      id: generateId(),
      title: result.title,
      url: result.url,
      description: result.description,
      score: result.score,
      published_date: result.published_date,
      highlights: result.highlights,
      // Enhanced fields
      domain: enhancedResult.domain,
      logo_url: enhancedResult.logo_url,
      company_name: enhancedResult.company_name,
      apollo_enrichment: enhancedResult.apollo_enrichment,
      notes,
      addedAt: new Date().toISOString(),
      status: 'new',
    }

    setSavedProspects(prev => {
      // Check for duplicates by URL
      if (prev.some(p => p.url === result.url)) {
        return prev
      }
      const updated = [newProspect, ...prev]
      persistProspects(updated)
      return updated
    })

    return newProspect
  }, [persistProspects])

  const updateProspect = useCallback((id: string, updates: Partial<PipelineProspect>) => {
    setSavedProspects(prev => {
      const updated = prev.map(p =>
        p.id === id ? { ...p, ...updates } : p
      )
      persistProspects(updated)
      return updated
    })
  }, [persistProspects])

  const removeProspect = useCallback((id: string) => {
    setSavedProspects(prev => {
      const updated = prev.filter(p => p.id !== id)
      persistProspects(updated)
      return updated
    })
  }, [persistProspects])

  // ============================================
  // Saved Contacts Management
  // ============================================

  const saveContact = useCallback((result: EnhancedContactSearchResult | ContactSearchResult, notes?: string, prospectId?: string) => {
    // Handle both enhanced and legacy result types
    const enhancedResult = result as EnhancedContactSearchResult

    const newContact: PipelineContact = {
      id: generateId(),
      name: result.name,
      url: result.url,
      snippet: result.snippet,
      title: result.title,
      company: result.company,
      // Enhanced fields
      company_domain: enhancedResult.company_domain,
      logo_url: enhancedResult.logo_url,
      location: enhancedResult.location,
      notes,
      addedAt: new Date().toISOString(),
      prospectId,
    }

    setSavedContacts(prev => {
      // Check for duplicates by URL
      if (prev.some(c => c.url === result.url)) {
        return prev
      }
      const updated = [newContact, ...prev]
      persistContacts(updated)
      return updated
    })

    return newContact
  }, [persistContacts])

  const updateContact = useCallback((id: string, updates: Partial<PipelineContact>) => {
    setSavedContacts(prev => {
      const updated = prev.map(c =>
        c.id === id ? { ...c, ...updates } : c
      )
      persistContacts(updated)
      return updated
    })
  }, [persistContacts])

  const removeContact = useCallback((id: string) => {
    setSavedContacts(prev => {
      const updated = prev.filter(c => c.id !== id)
      persistContacts(updated)
      return updated
    })
  }, [persistContacts])

  // ============================================
  // Export Functions
  // ============================================

  const exportProspectsToCSV = useCallback(() => {
    if (savedProspects.length === 0) return

    // Define rich headers for maximum utility
    const headers = [
      'Company Name',
      'Domain',
      'Website',
      'Description',
      'Status',
      'Score',
      'Notes',
      'Added Date',
      // Firmographics
      'Industry',
      'Headquarters',
      'City',
      'State',
      'Country',
      'Employee Count',
      'Revenue (Est)',
      'Founded Year',
      // Contact Info
      'Phone',
      'LinkedIn',
      // Tags & Tech
      'Supply Chain Matches',
      'Keywords',
      'Technologies'
    ]

    const rows = savedProspects.map(p => {
      const enrich = (p.apollo_enrichment || {}) as Partial<ApolloEnrichmentResult>

      // Helper to clean text for CSV (escape quotes and remove newlines)
      const clean = (str: string | undefined | null) => {
        if (!str) return ''
        return str.toString().replace(/"/g, '""').replace(/\n/g, ' ')
      }

      return [
        clean(p.company_name || p.title),
        clean(p.domain),
        clean(p.url),
        clean(p.description),
        clean(p.status),
        p.score?.toFixed(3) || '',
        clean(p.notes),
        new Date(p.addedAt).toLocaleDateString(),
        // Firmographics
        clean(enrich.industry),
        clean(enrich.headquarters),
        clean(enrich.city),
        clean(enrich.state),
        clean(enrich.country),
        enrich.employee_count || '',
        clean(enrich.revenue_printed || enrich.annual_revenue?.toString()),
        enrich.founded_year || '',
        // Contact Info
        clean(enrich.phone),
        clean(enrich.linkedin_url),
        // Tags (joined by semicolon)
        clean((enrich.supply_chain_matches || []).join('; ')),
        clean((enrich.keywords || []).join('; ')),
        clean((enrich.technologies || []).join('; '))
      ]
    })

    const csvContent = [
      headers.join(','),
      ...rows.map(row => row.map(cell => `"${cell}"`).join(','))
    ].join('\n')

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = `pipeline-prospects-${new Date().toISOString().split('T')[0]}.csv`
    link.click()
    URL.revokeObjectURL(link.href)
  }, [savedProspects])

  const exportContactsToCSV = useCallback(() => {
    if (savedContacts.length === 0) return

    const headers = [
      'Name',
      'Title',
      'Company',
      'Company Domain',
      'Location',
      'LinkedIn URL',
      'Snippet/Bio',
      'Notes',
      'Added Date'
    ]

    const rows = savedContacts.map(c => {
      const clean = (str: string | undefined | null) => {
        if (!str) return ''
        return str.toString().replace(/"/g, '""').replace(/\n/g, ' ')
      }

      return [
        clean(c.name),
        clean(c.title),
        clean(c.company),
        clean(c.company_domain),
        clean(c.location),
        clean(c.url), // Usually LinkedIn URL for contacts
        clean(c.snippet),
        clean(c.notes),
        new Date(c.addedAt).toLocaleDateString()
      ]
    })

    const csvContent = [
      headers.join(','),
      ...rows.map(row => row.map(cell => `"${cell}"`).join(','))
    ].join('\n')

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = `pipeline-contacts-${new Date().toISOString().split('T')[0]}.csv`
    link.click()
    URL.revokeObjectURL(link.href)
  }, [savedContacts])

  // Clear search results
  const clearResults = useCallback(() => {
    setProspectResults([])
    setContactResults([])
    setTriggerResults([])
    setSearchError(null)
    setLastQueryType(null)
  }, [])

  return {
    // Search state (legacy direct API)
    isSearching,
    searchError,
    prospectResults,
    contactResults,
    triggerResults,
    lastQueryType,

    // Search functions (legacy direct API)
    findSimilarCompanies,
    searchCompanies,
    findContacts,
    findTriggerEvents,
    clearResults,

    // Apollo.io functions
    enrichCompany,
    enrichProspect,
    searchApolloContacts,
    revealApolloContact,
    getApolloCredits,

    // Pipeline mode
    pipelineMode,
    setPipelineMode,

    // Agent chat state
    isAgentThinking,
    agentError,
    conversationHistory,
    searchBlocks,
    suggestedFollowups,

    // Webset polling state
    pollingWebsets,

    // Agent chat functions
    sendAgentMessage,
    clearConversation,
    toggleBlockExpansion,
    removeSearchBlock,

    // Saved data
    savedProspects,
    savedContacts,

    // Prospect management
    saveProspect,
    updateProspect,
    removeProspect,

    // Contact management
    saveContact,
    updateContact,
    removeContact,

    // Export
    exportProspectsToCSV,
    exportContactsToCSV,
  }
}
