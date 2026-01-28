'use client'

import React, { createContext, useContext, useState, useCallback, useEffect } from 'react'
import { v4 as uuidv4 } from 'uuid'
import {
    PipelineProspect,
    PipelineContact,
    SearchBlock,
    EnhancedProspectSearchResult,
    ProspectSearchResult,
    ContactSearchResult,
    EnhancedContactSearchResult,
    ApolloEnrichmentResult
} from '@/types'
import {
    apolloService
} from '@/lib/api'
import { getApiBaseUrl } from '@/lib/config'

// Local type definitions
export type PipelineMode = 'instant' | 'full'

export interface ConversationMessage {
    role: 'user' | 'assistant'
    content: string
    timestamp: Date
    isError?: boolean
}

interface PipelineContextType {
    // Search state
    isSearching: boolean
    searchError: string | null
    lastQueryType: 'semantic' | 'similar' | 'apollo_search' | null
    isAgentThinking: boolean
    agentError: string | null
    conversationHistory: ConversationMessage[]
    searchBlocks: SearchBlock[]
    suggestedFollowups: string[]

    // Pipeline mode state
    pipelineMode: PipelineMode

    // Saved items
    savedProspects: PipelineProspect[]
    savedContacts: PipelineContact[]

    // Actions
    setPipelineMode: (mode: PipelineMode) => void
    persistProspects: (prospects: PipelineProspect[]) => void
    persistContacts: (contacts: PipelineContact[]) => void

    // Core search methods
    findSimilarCompanies: (url: string) => Promise<void>
    searchCompanies: (query: string) => Promise<void>
    findContacts: (companyDomain: string) => Promise<void>
    findTriggerEvents: (companyDomain: string) => Promise<void>
    enrichCompany: (domain: string) => Promise<ApolloEnrichmentResult | null>
    enrichProspect: (prospectId: string) => Promise<void>

    // Apollo methods
    searchApolloContacts: (query: string) => Promise<void>
    revealApolloContact: (contactId: string) => Promise<string | null>
    getApolloCredits: () => Promise<any>

    // Agent methods
    sendAgentMessage: (message: string) => Promise<void>
    clearConversation: () => void

    // Block management
    toggleBlockExpansion: (blockId: string) => void
    removeSearchBlock: (blockId: string) => void

    // CRUD
    saveProspect: (result: EnhancedProspectSearchResult | ProspectSearchResult) => void
    updateProspect: (id: string, updates: Partial<PipelineProspect>) => void
    removeProspect: (id: string) => void
    saveContact: (contact: EnhancedContactSearchResult | ContactSearchResult) => void
    updateContact: (id: string, updates: Partial<PipelineContact>) => void
    removeContact: (id: string) => void

    // Export
    exportProspectsToCSV: () => void
    exportContactsToCSV: () => void
}

const PipelineContext = createContext<PipelineContextType | undefined>(undefined)

const STORAGE_KEYS = {
    PROSPECTS: 'c1_pipeline_prospects',
    CONTACTS: 'c1_pipeline_contacts'
}

export function PipelineProvider({ children }: { children: React.ReactNode }) {
    // Search state
    const [isSearching, setIsSearching] = useState(false)
    const [searchError, setSearchError] = useState<string | null>(null)
    const [lastQueryType, setLastQueryType] = useState<'semantic' | 'similar' | 'apollo_search' | null>(null)
    const [searchBlocks, setSearchBlocks] = useState<SearchBlock[]>([])

    // Agent state
    const [isAgentThinking, setIsAgentThinking] = useState(false)
    const [agentError, setAgentError] = useState<string | null>(null)
    const [conversationHistory, setConversationHistory] = useState<ConversationMessage[]>([
        {
            role: 'assistant',
            content: "Hi! I'm your Pipeline Agent. I can help you find companies and prospects to build your sales pipeline. What are you looking for today?",
            timestamp: new Date()
        }
    ])
    const [suggestedFollowups, setSuggestedFollowups] = useState<string[]>([
        "Find aerospace manufacturers in Florida",
        "Find companies similar to Hexcel",
        "Find wind energy companies in Texas"
    ])

    // Pipeline mode
    const [pipelineMode, setPipelineMode] = useState<PipelineMode>('instant')

    // Saved items
    const [savedProspects, setSavedProspects] = useState<PipelineProspect[]>([])
    const [savedContacts, setSavedContacts] = useState<PipelineContact[]>([])

    // Load from localStorage on mount
    useEffect(() => {
        try {
            const storedProspects = localStorage.getItem(STORAGE_KEYS.PROSPECTS)
            const storedContacts = localStorage.getItem(STORAGE_KEYS.CONTACTS)

            if (storedProspects) setSavedProspects(JSON.parse(storedProspects))
            if (storedContacts) setSavedContacts(JSON.parse(storedContacts))
        } catch (err) {
            console.error('Failed to load storage:', err)
        }
    }, [])

    // --- Actions ---

    const persistProspects = useCallback((prospects: PipelineProspect[]) => {
        setSavedProspects(prospects)
        localStorage.setItem(STORAGE_KEYS.PROSPECTS, JSON.stringify(prospects))
    }, [])

    const persistContacts = useCallback((contacts: PipelineContact[]) => {
        setSavedContacts(contacts)
        localStorage.setItem(STORAGE_KEYS.CONTACTS, JSON.stringify(contacts))
    }, [])

    const clearConversation = useCallback(() => {
        setConversationHistory([{
            role: 'assistant',
            content: "Hi! I'm your Pipeline Agent. I can help you find companies and prospects to build your sales pipeline. What are you looking for today?",
            timestamp: new Date()
        }])
        setSearchBlocks([])
        setSuggestedFollowups([
            "Find aerospace manufacturers in Florida",
            "Find companies similar to Hexcel",
            "Find wind energy companies in Texas"
        ])
    }, [])

    const toggleBlockExpansion = useCallback((blockId: string) => {
        setSearchBlocks(prev => prev.map(block =>
            block.id === blockId
                ? { ...block, is_expanded: !block.is_expanded }
                : block
        ))
    }, [])

    const removeSearchBlock = useCallback((blockId: string) => {
        setSearchBlocks(prev => prev.filter(block => block.id !== blockId))
    }, [])

    // --- CRUD ---

    const saveProspect = useCallback((result: EnhancedProspectSearchResult | ProspectSearchResult) => {
        const name = 'title' in result ? result.title : (result as any).title || 'Unknown Company' // ProspectSearchResult has title
        const domain = 'domain' in result ? result.domain : (result as any).url || ''
        const notes = 'description' in result ? result.description : ''

        const newProspect: PipelineProspect = {
            id: uuidv4(),
            company_name: ('company_name' in result ? result.company_name : name) || name,
            domain: domain,
            url: result.url,
            title: name,
            description: notes,
            status: 'new',
            score: result.score || 0,
            addedAt: new Date().toISOString(),
            notes: notes,
            apollo_enrichment: (result as any).apollo_enrichment
        }
        const updated = [...savedProspects, newProspect]
        persistProspects(updated)
    }, [savedProspects, persistProspects])

    const updateProspect = useCallback((id: string, updates: Partial<PipelineProspect>) => {
        const updated = savedProspects.map(p => p.id === id ? { ...p, ...updates } : p)
        persistProspects(updated)
    }, [savedProspects, persistProspects])

    const removeProspect = useCallback((id: string) => {
        const updated = savedProspects.filter(p => p.id !== id)
        persistProspects(updated)
    }, [savedProspects, persistProspects])

    const saveContact = useCallback((contact: EnhancedContactSearchResult | ContactSearchResult) => {
        const companyName = 'company' in contact ? contact.company : ''
        const companyDomain = 'company_domain' in contact ? contact.company_domain : ''

        const newContact: PipelineContact = {
            id: uuidv4(),
            name: contact.name,
            title: contact.title || '',
            company: companyName,
            company_domain: companyDomain,
            url: contact.url,
            snippet: contact.snippet,
            addedAt: new Date().toISOString()
        }

        const updated = [...savedContacts, newContact]
        persistContacts(updated)
    }, [savedContacts, persistContacts])

    const updateContact = useCallback((id: string, updates: Partial<PipelineContact>) => {
        const updated = savedContacts.map(c => c.id === id ? { ...c, ...updates } : c)
        persistContacts(updated)
    }, [savedContacts, persistContacts])

    const removeContact = useCallback((id: string) => {
        const updated = savedContacts.filter(c => c.id !== id)
        persistContacts(updated)
    }, [savedContacts, persistContacts])

    // --- Agent Interaction ---

    const sendAgentMessage = useCallback(async (message: string) => {
        setIsAgentThinking(true)
        setAgentError(null)

        const userMessage: ConversationMessage = {
            role: 'user',
            content: message,
            timestamp: new Date()
        }
        setConversationHistory(prev => [...prev, userMessage])

        try {
            // Prepare history for API
            const historyForApi = conversationHistory.map(msg => ({
                role: msg.role === 'user' ? 'user' : 'assistant',
                content: msg.content
            }))
            historyForApi.push({ role: 'user', content: message })

            const response = await fetch(`${getApiBaseUrl()}/api/pipeline/agent/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: message,
                    conversation_history: historyForApi,
                    mode: pipelineMode,
                    pipeline_context: {
                        prospect_count: savedProspects.length,
                        contact_count: savedContacts.length
                    }
                })
            })

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}))
                throw new Error(errorData.detail || `Error: ${response.statusText}`)
            }

            const data = await response.json()

            // Add assistant message
            const assistantMessage: ConversationMessage = {
                role: 'assistant',
                content: data.message,
                timestamp: new Date()
            }
            setConversationHistory(prev => [...prev, assistantMessage])

            if (data.search_blocks && data.search_blocks.length > 0) {
                const newBlocks = data.search_blocks.map((b: SearchBlock, idx: number) => ({
                    ...b,
                    is_expanded: idx === 0
                }))
                return setSearchBlocks(prev => [...newBlocks, ...prev])
            }

            if (data.suggested_followups) {
                setSuggestedFollowups(data.suggested_followups)
            }

        } catch (err: any) {
            console.error("Agent Error:", err)
            setAgentError(err.message || 'Failed to process your request.')
            setConversationHistory(prev => [...prev, {
                role: 'assistant',
                content: "I'm sorry, I encountered an error while processing your request. Please try again.",
                timestamp: new Date(),
                isError: true
            }])
        } finally {
            setIsAgentThinking(false)
        }
    }, [conversationHistory, pipelineMode, savedProspects.length, savedContacts.length])


    // --- Wrapped API Calls (for manual block usage if needed) ---

    const findSimilarCompanies = useCallback(async (url: string) => {
        await sendAgentMessage(`Find companies similar to ${url}`)
    }, [sendAgentMessage])

    const searchCompanies = useCallback(async (query: string) => {
        await sendAgentMessage(`Find companies matching: ${query}`)
    }, [sendAgentMessage])

    const findContacts = useCallback(async (companyDomain: string) => {
        await sendAgentMessage(`Find contacts at ${companyDomain}`)
    }, [sendAgentMessage])

    const findTriggerEvents = useCallback(async (companyDomain: string) => {
        await sendAgentMessage(`Find recent news and trigger events for ${companyDomain}`)
    }, [sendAgentMessage])

    // --- Single Enrichment & Apollo Actions ---

    const enrichCompany = useCallback(async (domain: string) => {
        try {
            return await apolloService.enrichOrganization(domain)
        } catch (err) {
            console.error('Enrichment error:', err)
            return null
        }
    }, [])

    const enrichProspect = useCallback(async (prospectId: string) => {
        const prospect = savedProspects.find(p => p.id === prospectId)
        const domain = prospect?.domain || (prospect?.url ? new URL(prospect.url).hostname : undefined)

        if (!prospect || !domain) return

        try {
            const enrichment = await apolloService.enrichOrganization(domain)
            if (enrichment) {
                updateProspect(prospectId, {
                    apollo_enrichment: enrichment,
                })
            }
        } catch (err) {
            console.error('Enrich Prospect Error:', err)
        }
    }, [savedProspects, updateProspect])

    const searchApolloContacts = useCallback(async (query: string) => {
        await sendAgentMessage(`Search Apollo contacts for: ${query}`)
    }, [sendAgentMessage])

    const revealApolloContact = useCallback(async (contactId: string) => {
        try {
            const result = await apolloService.revealContact(contactId)
            if (result.email) {
                return result.email
            }
            return null
        } catch (err) {
            console.error('Reveal error:', err)
            throw err
        }
    }, [])

    const getApolloCredits = useCallback(async () => {
        try {
            return await apolloService.health()
        } catch (err) {
            console.error('Credits error:', err)
            return null
        }
    }, [])


    // --- Exports ---

    const exportProspectsToCSV = useCallback(() => {
        if (savedProspects.length === 0) return

        const headers = ['Company', 'Domain', 'Status', 'Score', 'Industry', 'Headquarters', 'Notes', 'Added']
        const rows = savedProspects.map(p => [
            `"${p.company_name || p.title}"`,
            p.domain || '',
            p.status,
            p.score?.toString() || '0',
            `"${p.apollo_enrichment?.industry || ''}"`,
            `"${p.apollo_enrichment?.city || ''}"`,
            `"${(p.notes || '').replace(/"/g, '""').replace(/\n/g, ' ')}"`,
            new Date(p.addedAt).toLocaleDateString()
        ].join(','))

        const csvContent = [headers.join(','), ...rows].join('\n')
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
        const url = URL.createObjectURL(blob)
        const link = document.createElement('a')
        link.setAttribute('href', url)
        link.setAttribute('download', `pipeline_prospects_${new Date().toISOString().split('T')[0]}.csv`)
        link.style.visibility = 'hidden'
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
    }, [savedProspects])

    const exportContactsToCSV = useCallback(() => {
        if (savedContacts.length === 0) return

        const headers = ['Name', 'Title', 'Company', 'Status', 'Added']
        const rows = savedContacts.map(c => [
            `"${c.name}"`,
            `"${c.title || ''}"`,
            `"${c.company || ''}"`,
            '', // Status
            new Date(c.addedAt).toLocaleDateString()
        ].join(','))

        const csvContent = [headers.join(','), ...rows].join('\n')
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
        const url = URL.createObjectURL(blob)
        const link = document.createElement('a')
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
        lastQueryType,
        isAgentThinking,
        agentError,
        conversationHistory,
        searchBlocks,
        suggestedFollowups,
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
        exportContactsToCSV
    }

    return (
        <PipelineContext.Provider value={value}>
            {children}
        </PipelineContext.Provider>
    )
}

export function usePipelineContext() {
    const context = useContext(PipelineContext)
    if (context === undefined) {
        throw new Error('usePipelineContext must be used within a PipelineProvider')
    }
    return context
}
