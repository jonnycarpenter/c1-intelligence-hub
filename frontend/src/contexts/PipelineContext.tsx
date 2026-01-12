'use client'

import React, { createContext, useContext, useState, useCallback, useEffect, ReactNode } from 'react'
import { API_BASE } from '@/lib/config'
import type {
    PipelineProspect,
    PipelineContact,
    ProspectSearchResult,
    ContactSearchResult,
    EnhancedProspectSearchResult,
    EnhancedContactSearchResult,
    EnhancedTriggerEventResult,
    EnhancedProspectSearchResponse,
    EnhancedContactSearchResponse,
    EnhancedTriggerEventSearchResponse,
    SearchBlock,
    AgentChatResponse,
    ApolloEnrichmentResult,
    ApolloContactTeaserResult,
    ApolloContactRevealedResult,
    ApolloCreditStatus,
} from '@/types'

// Conversation message type for agent chat
export interface ConversationMessage {
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
export type PipelineMode = 'instant' | 'full'

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

// ----------------------------------------------------------------------------
// Types
// ----------------------------------------------------------------------------

export interface PipelineState {
    isSearching: boolean
    searchError: string | null
    prospectResults: EnhancedProspectSearchResult[]
    contactResults: EnhancedContactSearchResult[]
    triggerResults: EnhancedTriggerEventResult[]
    lastQueryType: 'similar' | 'search' | 'triggers' | null

    // Agent chat state
    isAgentThinking: boolean
    agentError: string | null
    conversationHistory: ConversationMessage[]
    searchBlocks: SearchBlock[]
    suggestedFollowups: string[]

    // Pipeline mode state
    pipelineMode: PipelineMode

    // Saved data state
    savedProspects: PipelineProspect[]
    savedContacts: PipelineContact[]

    // Webset polling state
    pollingWebsets: Set<string>
}

export interface PipelineContextType extends PipelineState {
    // Setters
    setPipelineMode: (mode: PipelineMode) => void

    // Search Functions
    findSimilarCompanies: (referenceUrl: string, numResults?: number, excludeSource?: boolean) => Promise<EnhancedProspectSearchResult[]>
    searchCompanies: (query: string, numResults?: number, includeDomains?: string[], excludeDomains?: string[]) => Promise<EnhancedProspectSearchResult[]>
    findContacts: (role: string, industry?: string, company?: string, numResults?: number) => Promise<EnhancedContactSearchResult[]>
    findTriggerEvents: (topic: string, daysBack?: number, numResults?: number) => Promise<EnhancedTriggerEventResult[]>

    // Apollo Functions
    enrichCompany: (domain: string) => Promise<ApolloEnrichmentResult | null>
    enrichProspect: (blockId: string, domain: string) => Promise<ApolloEnrichmentResult | null>
    searchApolloContacts: (companyName?: string, companyDomain?: string, options?: any) => Promise<ApolloContactTeaserResult[]>
    revealApolloContact: (personId: string) => Promise<ApolloContactRevealedResult | null>
    getApolloCredits: () => Promise<ApolloCreditStatus | null>

    // Agent Functions
    sendAgentMessage: (message: string) => Promise<AgentChatResponse | null>
    clearConversation: () => void
    toggleBlockExpansion: (blockId: string) => void
    removeSearchBlock: (blockId: string) => void

    // Saved Data Management
    saveProspect: (result: EnhancedProspectSearchResult | ProspectSearchResult, notes?: string) => PipelineProspect
    updateProspect: (id: string, updates: Partial<PipelineProspect>) => void
    removeProspect: (id: string) => void
    saveContact: (result: EnhancedContactSearchResult | ContactSearchResult, notes?: string, prospectId?: string) => PipelineContact
    updateContact: (id: string, updates: Partial<PipelineContact>) => void
    removeContact: (id: string) => void

    // Export
    exportProspectsToCSV: () => void
    exportContactsToCSV: () => void
}

// ----------------------------------------------------------------------------
// Context
// ----------------------------------------------------------------------------

const PipelineContext = createContext<PipelineContextType | undefined>(undefined)

export function usePipelineContext() {
    const context = useContext(PipelineContext)
    if (!context) {
        throw new Error('usePipelineContext must be used within a PipelineProvider')
    }
    return context
}

// ----------------------------------------------------------------------------
// Provider
// ----------------------------------------------------------------------------

export function PipelineProvider({ children }: { children: ReactNode }) {
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
                setPipelineModeState(storedMode as PipelineMode)
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

    // Search Functions
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

    // Apollo Functions
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

    // Agent Chat Functions
    const startWebsetPolling = useCallback((websetId: string) => {
        if (pollingWebsets.has(websetId)) return
        setPollingWebsets(prev => new Set(prev).add(websetId))

        const pollInterval = setInterval(async () => {
            try {
                const response = await fetch(`${API_BASE}/api/pipeline/webset/${websetId}/status`)
                if (!response.ok) return

                const status: WebsetStatusResponse = await response.json()
                if (status.status === 'completed' || status.status === 'failed') {
                    clearInterval(pollInterval)
                    setPollingWebsets(prev => {
                        const next = new Set(prev)
                        next.delete(websetId)
                        return next
                    })
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
        }, 5000)

        return () => clearInterval(pollInterval)
    }, [pollingWebsets])

    const sendAgentMessage = useCallback(async (message: string) => {
        setIsAgentThinking(true)
        setAgentError(null)
        const userMessage: ConversationMessage = {
            role: 'user',
            content: message,
            timestamp: new Date().toISOString(),
        }
        setConversationHistory(prev => [...prev, userMessage])

        try {
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
            const assistantMessage: ConversationMessage = {
                role: 'assistant',
                content: data.message,
                timestamp: new Date().toISOString(),
                search_blocks: data.search_blocks,
            }
            setConversationHistory(prev => [...prev, assistantMessage])

            if (data.search_blocks.length > 0) {
                setSearchBlocks(prev => [...data.search_blocks, ...prev])
                data.search_blocks.forEach(block => {
                    if (block.block_type === 'webset_building' && block.webset_id) {
                        startWebsetPolling(block.webset_id)
                    }
                })
            }
            setSuggestedFollowups(data.suggested_followups)
            return data
        } catch (err) {
            const message = err instanceof Error ? err.message : 'Failed to process your request'
            setAgentError(message)
            console.error('Error in agent chat:', err)
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
    }, [conversationHistory, pipelineMode, startWebsetPolling])

    const clearConversation = useCallback(() => {
        setConversationHistory([])
        setSearchBlocks([])
        setSuggestedFollowups([])
        setAgentError(null)
        setPollingWebsets(new Set())
    }, [])

    const toggleBlockExpansion = useCallback((blockId: string) => {
        setSearchBlocks(prev =>
            prev.map(block =>
                block.id === blockId
                    ? { ...block, is_expanded: !block.is_expanded }
                    : block
            )
        )
    }, [])

    const removeSearchBlock = useCallback((blockId: string) => {
        setSearchBlocks(prev => prev.filter(block => block.id !== blockId))
    }, [])

    // Saved Data Management
    const saveProspect = useCallback((result: EnhancedProspectSearchResult | ProspectSearchResult, notes?: string) => {
        const enhancedResult = result as EnhancedProspectSearchResult
        const newProspect: PipelineProspect = {
            id: generateId(),
            title: result.title,
            url: result.url,
            description: result.description,
            score: result.score,
            published_date: result.published_date,
            highlights: result.highlights,
            domain: enhancedResult.domain,
            logo_url: enhancedResult.logo_url,
            company_name: enhancedResult.company_name,
            apollo_enrichment: enhancedResult.apollo_enrichment,
            notes,
            addedAt: new Date().toISOString(),
            status: 'new',
        }

        setSavedProspects(prev => {
            if (prev.some(p => p.url === result.url)) return prev
            const updated = [newProspect, ...prev]
            persistProspects(updated)
            return updated
        })
        return newProspect
    }, [persistProspects])

    const updateProspect = useCallback((id: string, updates: Partial<PipelineProspect>) => {
        setSavedProspects(prev => {
            const updated = prev.map(p => p.id === id ? { ...p, ...updates } : p)
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

    const saveContact = useCallback((result: EnhancedContactSearchResult | ContactSearchResult, notes?: string, prospectId?: string) => {
        const enhancedResult = result as EnhancedContactSearchResult
        const newContact: PipelineContact = {
            id: generateId(),
            name: result.name,
            url: result.url,
            snippet: result.snippet,
            title: result.title,
            company: result.company,
            company_domain: enhancedResult.company_domain,
            logo_url: enhancedResult.logo_url,
            location: enhancedResult.location,
            notes,
            addedAt: new Date().toISOString(),
            prospectId,
        }

        setSavedContacts(prev => {
            if (prev.some(c => c.url === result.url)) return prev
            const updated = [newContact, ...prev]
            persistContacts(updated)
            return updated
        })
        return newContact
    }, [persistContacts])

    const updateContact = useCallback((id: string, updates: Partial<PipelineContact>) => {
        setSavedContacts(prev => {
            const updated = prev.map(c => c.id === id ? { ...c, ...updates } : c)
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

    // Export
    const exportProspectsToCSV = useCallback(() => {
        if (savedProspects.length === 0) return
        const headers = [
            'Company Name', 'Domain', 'Website', 'Description', 'Status', 'Score', 'Notes', 'Added Date',
            'Industry', 'Headquarters', 'City', 'State', 'Country', 'Employee Count', 'Revenue (Est)', 'Founded Year',
            'Phone', 'LinkedIn', 'Supply Chain Matches', 'Keywords', 'Technologies'
        ]

        const rows = savedProspects.map(p => {
            const enrich = (p.apollo_enrichment || {}) as Partial<ApolloEnrichmentResult>
            const clean = (str: string | undefined | null) => {
                if (!str) return ''
                return `"${str.replace(/"/g, '""').replace(/\n/g, ' ')}"`
            }

            return [
                clean(p.company_name || p.title),
                clean(p.domain),
                clean(p.url),
                clean(p.description),
                clean(p.status),
                clean(p.score?.toString()),
                clean(p.notes),
                clean(new Date(p.addedAt).toLocaleDateString()),
                clean(enrich.industry),
                clean(enrich.headquarters),
                clean(enrich.city),
                clean(enrich.state),
                clean(enrich.country),
                clean(enrich.employee_count?.toString()),
                clean(enrich.revenue_printed),
                clean(enrich.founded_year?.toString()),
                clean(enrich.phone),
                clean(enrich.linkedin_url),
                clean(enrich.supply_chain_matches?.join(', ')),
                clean(enrich.keywords?.join(', ')),
                clean(enrich.technologies?.join(', '))
            ].join(',')
        })
        const csvContent = [headers.join(','), ...rows].join('\n')
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
        const link = document.createElement('a')
        const url = URL.createObjectURL(blob)
        link.setAttribute('href', url)
        link.setAttribute('download', `pipeline_prospects_${new Date().toISOString().split('T')[0]}.csv`)
        link.style.visibility = 'hidden'
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
    }, [savedProspects])

    const exportContactsToCSV = useCallback(() => {
        if (savedContacts.length === 0) return

        const headers = [
            'Name',
            'Title',
            'Company',
            'Location',
            'Snippet',
            'LinkedIn Profile',
            'Company Domain',
            'Added Date',
            'Notes'
        ]

        const rows = savedContacts.map(c => {
            // Helper to clean text for CSV
            const clean = (str: string | undefined | null) => {
                if (!str) return ''
                return `"${str.replace(/"/g, '""').replace(/\n/g, ' ')}"`
            }

            return [
                clean(c.name),
                clean(c.title),
                clean(c.company),
                clean(c.location),
                clean(c.snippet),
                clean(c.url),
                clean(c.company_domain),
                clean(new Date(c.addedAt).toLocaleDateString()),
                clean(c.notes)
            ].join(',')
        })

        const csvContent = [headers.join(','), ...rows].join('\n')
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
        const link = document.createElement('a')
        const url = URL.createObjectURL(blob)
        link.setAttribute('href', url)
        link.setAttribute('download', `pipeline_contacts_${new Date().toISOString().split('T')[0]}.csv`)
        link.style.visibility = 'hidden'
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
    }, [savedContacts])

    const value = {
        isSearching,
        searchError,
        prospectResults,
        contactResults,
        triggerResults,
        lastQueryType,
        isAgentThinking,
        agentError,
        conversationHistory,
        searchBlocks,
        suggestedFollowups,
        pollingWebsets,
        pipelineMode,
        savedProspects,
        savedContacts,
        setPipelineMode,
        persistProspects,
        persistContacts,
        findSimilarCompanies,
        searchCompanies,
        findContacts,
        findTriggerEvents,
        enrichCompany,
        enrichProspect,
        searchApolloContacts,
        revealApolloContact,
        getApolloCredits,
        sendAgentMessage,
        clearConversation,
        toggleBlockExpansion,
        removeSearchBlock,
        saveProspect,
        updateProspect,
        removeProspect,
        saveContact,
        updateContact,
        removeContact,
        exportProspectsToCSV,
        exportContactsToCSV,
    }

    return (
        <PipelineContext.Provider value={value}>
            {children}
        </PipelineContext.Provider>
    )
}
