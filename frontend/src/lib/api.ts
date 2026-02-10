/**
 * API client for C1 Intelligence Hub backend
 */

import { API_BASE } from './config'

// Timeout configuration
const AD_HOC_BRIEFING_TIMEOUT_MS = 60000 // 60 seconds

// Custom error for timeout handling
export class TimeoutError extends Error {
  constructor(message: string = 'Request timed out') {
    super(message)
    this.name = 'TimeoutError'
  }
}

export interface ApiDigestItem {
  id: string
  title: string
  summary: string
  category: string
  priority: string
  sources: Array<{
    title: string
    url: string
    published_at?: string
  }>
  entities: {
    companies?: string[]
    materials?: string[]
    topics?: string[]
  }
  published_at: string
  ingested_at: string
  coverage_count?: number
  relevance_score?: number  // 0.0-1.0 from LLM classifier
}

export interface ApiDigest {
  id: string
  generated_at: string
  period_start: string
  period_end: string
  stats: {
    total_items: number
    by_category: Record<string, number>
    by_priority: Record<string, number>
  }
  items: ApiDigestItem[]
  summary?: string
}

export interface ApiQueryRequest {
  message: string
  mode: 'pulse' | 'discovery' | 'research' | 'products' | 'field-sales' | 'pipeline' | 'supply-network' | 'companies' | 'industries' | 'data-preferences' | 'importyeti' | 'app-architecture'
  conversation_id?: string
  context?: {
    companies?: string[]
    materials?: string[]
    timeframe?: string
  }
}

export interface ApiQueryResponse {
  message: {
    id: string
    role: 'assistant'
    content: string
    timestamp: string
    sources?: Array<{
      title: string
      url: string
    }>
  }
  conversation_id: string
  trace_url?: string
  thinking?: Array<{
    step: string
    reasoning?: string
    tool_calls?: Array<{
      name: string
      input?: unknown
      output?: unknown
      status: string
      duration?: number
    }>
    status: string
    timestamp: string
  }>
}

class ApiClient {
  private baseUrl: string

  constructor(baseUrl: string = API_BASE) {
    this.baseUrl = baseUrl
  }

  /**
   * Fetch the intelligence digest
   */
  async getDigest(options?: {
    hours?: number
    categories?: string[]
    priorities?: string[]
    limit?: number
  }): Promise<ApiDigest> {
    const params = new URLSearchParams()

    if (options?.hours) {
      params.set('hours', options.hours.toString())
    }
    if (options?.categories?.length) {
      params.set('categories', options.categories.join(','))
    }
    if (options?.priorities?.length) {
      params.set('priorities', options.priorities.join(','))
    }
    if (options?.limit) {
      params.set('limit', options.limit.toString())
    }

    const url = `${this.baseUrl}/api/digest${params.toString() ? `?${params}` : ''}`

    const response = await fetch(url)

    if (!response.ok) {
      throw new Error(`Failed to fetch digest: ${response.statusText}`)
    }

    return response.json()
  }

  /**
   * Refresh the digest
   */
  async refreshDigest(): Promise<ApiDigest> {
    const response = await fetch(`${this.baseUrl}/api/digest/refresh`, {
      method: 'POST',
    })

    if (!response.ok) {
      throw new Error(`Failed to refresh digest: ${response.statusText}`)
    }

    return response.json()
  }

  /**
   * Fetch the financial feed (earnings quotes + SEC nuggets)
   */
  async getFinancialFeed(options?: {
    search?: string
    source_type?: 'earnings' | 'sec' | 'all'
    ticker?: string
    type_filter?: string
    themes?: string[]
    sentiment?: string
    sort_by?: 'newest' | 'relevance'
    limit?: number
    offset?: number
  }): Promise<{ items: import('@/types').FinancialFeedItem[]; total_count: number; has_more: boolean }> {
    const params = new URLSearchParams()

    if (options?.search) params.set('search', options.search)
    if (options?.source_type && options.source_type !== 'all') params.set('source_type', options.source_type)
    if (options?.ticker) params.set('ticker', options.ticker)
    if (options?.type_filter) params.set('type_filter', options.type_filter)
    if (options?.themes?.length) params.set('themes', options.themes.join(','))
    if (options?.sentiment) params.set('sentiment', options.sentiment)
    if (options?.sort_by) params.set('sort_by', options.sort_by)
    if (options?.limit) params.set('limit', options.limit.toString())
    if (options?.offset) params.set('offset', options.offset.toString())

    const url = `${this.baseUrl}/api/discovery/financial-feed${params.toString() ? `?${params}` : ''}`
    const response = await fetch(url)

    if (!response.ok) {
      throw new Error(`Failed to fetch financial feed: ${response.statusText}`)
    }

    return response.json()
  }

  /**
   * Fetch the expert feed (podcast quotes)
   */
  async getExpertFeed(options?: {
    search?: string
    podcast_name?: string
    speaker_name?: string
    themes?: string[]
    time_range?: string
    sort_by?: 'newest' | 'relevance'
    limit?: number
    offset?: number
  }): Promise<{ items: import('@/types').ExpertFeedItem[]; total_count: number; has_more: boolean }> {
    const params = new URLSearchParams()

    if (options?.search) params.set('search', options.search)
    if (options?.podcast_name) params.set('podcast_name', options.podcast_name)
    if (options?.speaker_name) params.set('speaker_name', options.speaker_name)
    if (options?.themes?.length) params.set('themes', options.themes.join(','))
    if (options?.time_range) params.set('time_range', options.time_range)
    if (options?.sort_by) params.set('sort_by', options.sort_by)
    if (options?.limit) params.set('limit', options.limit.toString())
    if (options?.offset) params.set('offset', options.offset.toString())

    const url = `${this.baseUrl}/api/discovery/expert-feed${params.toString() ? `?${params}` : ''}`
    const response = await fetch(url)

    if (!response.ok) {
      throw new Error(`Failed to fetch expert feed: ${response.statusText}`)
    }

    return response.json()
  }

  /**
   * Get AI summary for a Discovery category (thematic analysis)
   */
  async getDiscoverySummary(category: string): Promise<{
    category: string
    period_label: string
    themes: Array<{ title: string; content: string }>
    one_off_summary: string
    article_count: number
    generated_at: string
  }> {
    const response = await fetch(
      `${this.baseUrl}/api/discovery/summary/${encodeURIComponent(category)}`
    )

    if (!response.ok) {
      throw new Error(`Failed to fetch discovery summary: ${response.statusText}`)
    }

    return response.json()
  }

  /**
   * Get the Bulletin Board - AI-generated priority spotlight
   * Returns actionable guidance bullets for high-priority items
   */
  async getBulletinBoard(): Promise<{
    market_pulse: string
    total_priority_items: number
    categories_covered: string[]
    time_window_hours: number
    extended_to_7_days: boolean
    generated_at: string
  }> {
    const response = await fetch(`${this.baseUrl}/api/discovery/bulletin`)

    if (!response.ok) {
      // Return empty fallback if endpoint not yet implemented
      if (response.status === 404) {
        return {
          market_pulse: "Explore the categories below for the latest intelligence.",
          total_priority_items: 0,
          categories_covered: [],
          time_window_hours: 72,
          extended_to_7_days: false,
          generated_at: new Date().toISOString(),
        }
      }
      throw new Error(`Failed to fetch bulletin board: ${response.statusText}`)
    }

    return response.json()
  }

  /**
   * Send a chat query
   */
  async query(request: ApiQueryRequest): Promise<ApiQueryResponse> {
    const response = await fetch(`${this.baseUrl}/api/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    })

    if (!response.ok) {
      throw new Error(`Query failed: ${response.statusText}`)
    }

    return response.json()
  }

  /**
   * Stream a chat query (for real-time thinking updates)
   */
  async *streamQuery(request: ApiQueryRequest): AsyncGenerator<{
    type: string
    content: string
    metadata?: Record<string, unknown>
  }> {
    const response = await fetch(`${this.baseUrl}/api/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    })

    if (!response.ok) {
      throw new Error(`Stream query failed: ${response.statusText}`)
    }

    const reader = response.body?.getReader()
    if (!reader) return

    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6))
            yield data
          } catch {
            // Skip invalid JSON
          }
        }
      }
    }
  }

  /**
   * Health check
   */
  async health(): Promise<{ status: string; version: string }> {
    const response = await fetch(`${this.baseUrl}/api/health`)
    return response.json()
  }

  /**
   * Save a research report to backend storage
   */
  async saveResearchReport(report: {
    query: string
    title: string
    content: string
    agent?: string
    sources?: Array<{ title?: string; name?: string; url?: string }>
    companies_mentioned?: string[]
    materials_mentioned?: string[]
  }): Promise<{ id: string; success: boolean; message: string }> {
    const response = await fetch(`${this.baseUrl}/api/reports/research`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(report),
    })
    if (!response.ok) {
      throw new Error(`Failed to save research report: ${response.statusText}`)
    }
    return response.json()
  }

  /**
   * Get list of saved research reports
   */
  async getResearchReports(options?: {
    agent?: string
    limit?: number
  }): Promise<Array<{
    id: string
    query: string
    title: string
    content: string
    agent: string
    sources: Array<{ title?: string; url?: string }>
    companies_mentioned: string[]
    materials_mentioned: string[]
    created_at: string | null
  }>> {
    const params = new URLSearchParams()
    if (options?.agent) params.set('agent', options.agent)
    if (options?.limit) params.set('limit', options.limit.toString())

    const url = `${this.baseUrl}/api/reports/research${params.toString() ? '?' + params : ''}`
    const response = await fetch(url)
    if (!response.ok) {
      throw new Error(`Failed to fetch research reports: ${response.statusText}`)
    }
    return response.json()
  }

  /**
   * Get Pulse briefings (Need to Know) - Legacy category-based format
   */
  async getPulseSummaries(): Promise<any[]> {
    const response = await fetch(`${this.baseUrl}/api/pulse/summaries`)
    if (!response.ok) {
      throw new Error(`Failed to fetch pulse summaries: ${response.statusText}`)
    }
    return response.json()
  }

  // =====================================
  // Weekly Executive Briefing (New Dynamic Format)
  // =====================================

  /**
   * Get the latest weekly executive briefing
   */
  async getWeeklyBriefing(): Promise<any> {
    const response = await fetch(`${this.baseUrl}/api/pulse/weekly`)
    if (!response.ok) {
      if (response.status === 404) {
        return null  // No briefing found yet
      }
      throw new Error(`Failed to fetch weekly briefing: ${response.statusText}`)
    }
    return response.json()
  }

  /**
   * Get weekly briefing history
   */
  async getWeeklyBriefingHistory(limit: number = 10): Promise<any[]> {
    const response = await fetch(`${this.baseUrl}/api/pulse/weekly/history?limit=${limit}`)
    if (!response.ok) {
      throw new Error(`Failed to fetch briefing history: ${response.statusText}`)
    }
    return response.json()
  }

  // =====================================
  // Ad Hoc Quick Briefings
  // =====================================

  /**
   * Generate an ad hoc briefing from a user question
   * 
   * @param request.session_id - Optional session ID for follow-up questions.
   *   First request returns a session_id, pass it in subsequent requests for stateful conversation.
   */
  async createAdHocBriefing(request: {
    question: string
    context?: {
      current_brief_headlines?: string[]
      current_brief_date?: string
      recent_digest_topics?: string[]
      active_filters?: string[]
    }
    is_follow_up?: boolean
    session_id?: string
  }): Promise<any> {
    // Create AbortController for timeout
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), AD_HOC_BRIEFING_TIMEOUT_MS)

    try {
      const response = await fetch(`${this.baseUrl}/api/pulse/adhoc`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-Team': localStorage.getItem('userTeam') || 'All Others',
        },
        body: JSON.stringify(request),
        signal: controller.signal,
      })

      clearTimeout(timeoutId)

      if (!response.ok) {
        throw new Error(`Failed to create ad hoc briefing: ${response.statusText}`)
      }
      return response.json()
    } catch (error) {
      clearTimeout(timeoutId)

      // Check if error is due to abort (timeout)
      if (error instanceof Error && error.name === 'AbortError') {
        throw new TimeoutError('Request timed out after 60 seconds. Try simplifying your question or ask again.')
      }
      throw error
    }
  }

  /**
   * Stream an ad hoc briefing response
   * 
   * @param request.session_id - Optional session ID for follow-up questions.
   */
  async streamAdHocBriefing(request: {
    question: string
    context?: {
      current_brief_headlines?: string[]
      current_brief_date?: string
      recent_digest_topics?: string[]
      active_filters?: string[]
    }
    is_follow_up?: boolean
    session_id?: string
  }): Promise<ReadableStream<Uint8Array> | null> {
    // Create AbortController for timeout
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), AD_HOC_BRIEFING_TIMEOUT_MS)

    try {
      const response = await fetch(`${this.baseUrl}/api/pulse/adhoc/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-Team': localStorage.getItem('userTeam') || 'All Others',
        },
        body: JSON.stringify(request),
        signal: controller.signal,
      })

      clearTimeout(timeoutId)

      if (!response.ok) {
        throw new Error(`Failed to stream ad hoc briefing: ${response.statusText}`)
      }
      return response.body
    } catch (error) {
      clearTimeout(timeoutId)

      // Check if error is due to abort (timeout)
      if (error instanceof Error && error.name === 'AbortError') {
        throw new TimeoutError('Request timed out after 60 seconds. Try simplifying your question or ask again.')
      }
      throw error
    }
  }

  /**
   * Get ad hoc briefing history
   */
  async getAdHocBriefingHistory(limit: number = 20): Promise<any[]> {
    const response = await fetch(`${this.baseUrl}/api/pulse/adhoc/history?limit=${limit}`)
    if (!response.ok) {
      throw new Error(`Failed to fetch ad hoc history: ${response.statusText}`)
    }
    return response.json()
  }

  /**
   * Get combined briefing history for timeline
   */
  async getAllBriefingHistory(weeklyLimit: number = 10, adhocLimit: number = 20): Promise<{
    weekly_briefings: any[]
    adhoc_briefings: any[]
    total_weekly: number
    total_adhoc: number
  }> {
    const response = await fetch(
      `${this.baseUrl}/api/pulse/all-history?weekly_limit=${weeklyLimit}&adhoc_limit=${adhocLimit}`
    )
    if (!response.ok) {
      throw new Error(`Failed to fetch briefing history: ${response.statusText}`)
    }
    return response.json()
  }

  // =====================================
  // ImportYeti / Trade Intel - ARCHIVED
  // =====================================

  /**
   * Get Trade Intelligence Dashboard Stats - ARCHIVED
   */
  /*
  async getImportYetiStats(): Promise<{
    total_suppliers: number
    total_oems: number
    active_relationships: number
    tracked_shipments: number
  }> {
    const response = await fetch(`${this.baseUrl}/api/importyeti/dashboard`)
    if (!response.ok) {
      throw new Error(`Failed to fetch stats: ${response.statusText}`)
    }
    return response.json()
  }

  /**
   * Get list of suppliers - ARCHIVED
   */
  /*
  async getImportYetiSuppliers(options?: {
    limit?: number
    offset?: number
    search?: string
  }): Promise<Array<{
    supplier_id: string
    supplier_name: string
    country: string
    supplier_tier?: string
    total_shipments?: number
    total_us_customers?: number
    is_c1_supplier?: boolean
  }>> {
    const params = new URLSearchParams()
    if (options?.limit) params.set('limit', options.limit.toString())
    if (options?.offset) params.set('offset', options.offset.toString())
    if (options?.search) params.set('search', options.search)

    const response = await fetch(`${this.baseUrl}/api/importyeti/suppliers?${params}`)
    if (!response.ok) {
      throw new Error(`Failed to fetch suppliers: ${response.statusText}`)
    }
    return response.json()
  }

  /**
   * Get network graph data - ARCHIVED
   */
  /*
  async getImportYetiNetwork(): Promise<{
    nodes: Array<{ id: string; type: string; tier?: string }>
    links: Array<{ source: string; target: string; value: number }>
  }> {
    const response = await fetch(`${this.baseUrl}/api/importyeti/network`)
    if (!response.ok) {
      throw new Error(`Failed to fetch network graph: ${response.statusText}`)
    }
    return response.json()
  }

  /**
   * Get freight rate time-series data - ARCHIVED
   */
  /*
  async getFreightData(options?: {
    lane?: string
    days?: number
  }): Promise<Array<{
    lane: string
    rate: number
    change_pct: number | null
    as_of: string
    source: string
  }>> {
    const params = new URLSearchParams()
    if (options?.lane) params.set('lane', options.lane)
    if (options?.days) params.set('days', options.days.toString())

    const response = await fetch(`${this.baseUrl}/api/importyeti/freight?${params}`)
    if (!response.ok) {
      throw new Error(`Failed to fetch freight data: ${response.statusText}`)
    }
    return response.json()
  }
  */

  // =====================================
  // Supply Network
  // =====================================

  /**
   * Get network graph data (nodes/edges) for visualization
   */
  async getSupplyNetworkGraph(
    entityTypes: string = 'target,competitor',
    minShipments12m: number = 0
  ): Promise<{
    nodes: Array<{
      id: string
      label: string
      type: 'company' | 'supplier'
      entity_type?: 'target' | 'competitor' | 'discovered'
      total_shipments?: number
      category?: string
      ticker?: string
      country?: string
    }>
    edges: Array<{
      source: string
      target: string
      relationship: string
      total_shipments?: number
      shipments_12m?: number
    }>
    stats: {
      total_companies: number
      total_suppliers: number
      total_edges: number
    }
  }> {
    const params = new URLSearchParams({
      entity_types: entityTypes,
      min_shipments_12m: minShipments12m.toString(),
    })
    const response = await fetch(`${this.baseUrl}/api/supply-network/graph?${params}`)
    if (!response.ok) {
      throw new Error(`Failed to fetch network graph: ${response.statusText}`)
    }
    return response.json()
  }

  /**
   * Get supply network database stats
   */
  async getSupplyNetworkStats(): Promise<Record<string, any>> {
    const response = await fetch(`${this.baseUrl}/api/supply-network/stats`)
    if (!response.ok) {
      throw new Error(`Failed to fetch stats: ${response.statusText}`)
    }
    return response.json()
  }

  /**
   * Get company drill-down (profile + supplier list)
   */
  async getCompanyDetail(importyetiKey: string): Promise<{
    company: Record<string, any>
    suppliers: Array<Record<string, any>>
    supplier_count: number
  }> {
    const response = await fetch(
      `${this.baseUrl}/api/supply-network/company/${encodeURIComponent(importyetiKey)}`
    )
    if (!response.ok) {
      throw new Error(`Failed to fetch company: ${response.statusText}`)
    }
    return response.json()
  }

  /**
   * Get supplier drill-down (profile + buyer list)
   */
  async getSupplierDetail(importyetiKey: string): Promise<{
    supplier: Record<string, any>
    buyers: Array<Record<string, any>>
    buyer_count: number
  }> {
    const response = await fetch(
      `${this.baseUrl}/api/supply-network/supplier/${encodeURIComponent(importyetiKey)}`
    )
    if (!response.ok) {
      throw new Error(`Failed to fetch supplier: ${response.statusText}`)
    }
    return response.json()
  }

  /**
   * Get shared suppliers between competitors
   */
  async getSharedSuppliers(active12mOnly: boolean = false): Promise<{
    shared_suppliers: Array<Record<string, any>>
    total: number
  }> {
    const params = new URLSearchParams({
      active_12m_only: active12mOnly.toString(),
    })
    const response = await fetch(`${this.baseUrl}/api/supply-network/shared-suppliers?${params}`)
    if (!response.ok) {
      throw new Error(`Failed to fetch shared suppliers: ${response.statusText}`)
    }
    return response.json()
  }

  /**
   * Query the supply chain LLM agent via SSE streaming.
   * Returns a ReadableStream for SSE event parsing.
   */
  async querySupplyChainAgent(
    query: string,
    signal?: AbortSignal
  ): Promise<Response> {
    const response = await fetch(`${this.baseUrl}/api/supply-network/agent/query`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query }),
      signal,
    })
    if (!response.ok) {
      throw new Error(`Supply chain search failed: ${response.statusText}`)
    }
    return response
  }

  /**
   * Get tracked companies (C1 + competitors) with supplier stats for directory cards
   */
  async getTrackedCompanies(): Promise<{
    companies: Array<{
      importyeti_key: string
      name: string
      entity_type: 'target' | 'competitor'
      ticker: string | null
      country: string
      category: string | null
      total_shipments: number
      supplier_count: number
      active_suppliers_12m: number
    }>
  }> {
    const response = await fetch(`${this.baseUrl}/api/supply-network/companies`)
    if (!response.ok) {
      throw new Error(`Failed to fetch tracked companies: ${response.statusText}`)
    }
    return response.json()
  }

  /**
   * Get supply chain intelligence context for a company (earnings, SEC, articles)
   */
  async getCompanyIntelligence(importyetiKey: string): Promise<{
    company_name: string
    ticker: string | null
    earnings_quotes: Array<Record<string, any>>
    sec_nuggets: Array<Record<string, any>>
    recent_articles: Array<Record<string, any>>
  }> {
    const response = await fetch(
      `${this.baseUrl}/api/supply-network/company/${encodeURIComponent(importyetiKey)}/intelligence`
    )
    if (!response.ok) {
      throw new Error(`Failed to fetch intelligence: ${response.statusText}`)
    }
    return response.json()
  }

  // =====================================
  // Industry Narratives
  // =====================================

  /**
   * Get curated industry list with 90-day article counts
   */
  async getIndustryNarrativesList(): Promise<{
    industries: Array<{
      id: string
      name: string
      article_count_90d: number
      trend: 'up' | 'down' | 'flat'
    }>
  }> {
    const response = await fetch(`${this.baseUrl}/api/industry-narratives/industries`)
    if (!response.ok) {
      throw new Error(`Failed to fetch industries: ${response.statusText}`)
    }
    return response.json()
  }

  /**
   * Get monthly timeline breakdown for an industry (event types, companies, themes, etc.)
   */
  async getIndustryTimeline(industry: string, days: number = 90): Promise<{
    industry: string
    period_days: number
    monthly_data: Array<{
      month: string
      month_label: string
      article_count: number
      days_in_period: number
      articles_per_day: number
      delta_per_day: number | null
      event_types: Array<{ name: string; count: number; per_day: number; delta: number | null }>
      top_companies: Array<{ name: string; count: number; per_day: number; delta: number | null }>
      top_themes: Array<{ name: string; count: number; per_day: number; delta: number | null }>
      top_geographies: Array<{ name: string; count: number; per_day: number }>
      sentiment: { positive: number; neutral: number; negative: number }
      top_articles: Array<{
        id: string
        title: string
        url: string
        source_name: string
        published_at: string
        summary: string
        event_type: string | null
        sentiment: string
      }>
    }>
    totals: {
      total_articles: number
      avg_monthly: number
      trend_direction: 'up' | 'down' | 'flat'
    }
  }> {
    const params = new URLSearchParams({ days: days.toString() })
    const response = await fetch(
      `${this.baseUrl}/api/industry-narratives/${encodeURIComponent(industry)}/timeline?${params}`
    )
    if (!response.ok) {
      throw new Error(`Failed to fetch industry timeline: ${response.statusText}`)
    }
    return response.json()
  }

  /**
   * Get paginated articles for an industry with filters
   */
  async getIndustryArticles(
    industry: string,
    filters?: {
      month?: string
      event_type?: string
      theme?: string
      sentiment?: string
      limit?: number
      offset?: number
    }
  ): Promise<{
    industry: string
    filters_applied: Record<string, string>
    total_count: number
    articles: Array<{
      id: string
      title: string
      url: string
      source_name: string
      published_at: string
      summary: string
      event_type: string | null
      sentiment: string
      themes: string[]
      companies: string[]
      geography: string[]
    }>
    pagination: {
      limit: number
      offset: number
      has_more: boolean
    }
  }> {
    const params = new URLSearchParams()
    if (filters?.month) params.set('month', filters.month)
    if (filters?.event_type) params.set('event_type', filters.event_type)
    if (filters?.theme) params.set('theme', filters.theme)
    if (filters?.sentiment) params.set('sentiment', filters.sentiment)
    if (filters?.limit) params.set('limit', filters.limit.toString())
    if (filters?.offset) params.set('offset', filters.offset.toString())

    const response = await fetch(
      `${this.baseUrl}/api/industry-narratives/${encodeURIComponent(industry)}/articles?${params}`
    )
    if (!response.ok) {
      throw new Error(`Failed to fetch industry articles: ${response.statusText}`)
    }
    return response.json()
  }

  /**
   * Generate LLM narrative synthesis for an industry's 90-day timeline
   */
  async generateIndustryNarrative(industry: string): Promise<{
    industry: string
    industry_narrative: string
    monthly_narratives: Array<{
      month: string
      narrative: string
    }>
    key_insight: string
    enrichment_sources_used: number
    generated_at: string
  }> {
    const response = await fetch(
      `${this.baseUrl}/api/industry-narratives/${encodeURIComponent(industry)}/narrative`,
      { method: 'POST' }
    )
    if (!response.ok) {
      const detail = await response.text().catch(() => response.statusText)
      throw new Error(`Failed to generate narrative: ${detail}`)
    }
    return response.json()
  }

  // =====================================
  // Memory / Long-term Storage
  // =====================================

  /**
   * Save a briefing to memory log
   */
  async saveToMemory(data: {
    type: 'briefing' | 'research_export'
    question: string
    answer: string
    sources?: Array<{ title: string; url?: string }>
    confidence?: 'high' | 'medium' | 'low'
    tags?: string[]
  }): Promise<{ success: boolean; memory_id?: string }> {
    const response = await fetch(`${this.baseUrl}/api/memory/log`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-User-Name': localStorage.getItem('userName') || 'Anonymous',
        'X-User-Team': localStorage.getItem('userTeam') || 'All Others',
      },
      body: JSON.stringify(data),
    })
    if (!response.ok) {
      throw new Error(`Failed to save to memory: ${response.statusText}`)
    }
    return response.json()
  }

  /**
   * Get relevant memories for context
   */
  async getRelevantMemories(query: string, limit: number = 5): Promise<Array<{
    id: string
    question: string
    answer: string
    similarity: number
    created_at: string
    team?: string
    pinned?: boolean
  }>> {
    const params = new URLSearchParams({ query, limit: limit.toString() })
    const response = await fetch(`${this.baseUrl}/api/memory/relevant?${params}`, {
      headers: {
        'X-User-Team': localStorage.getItem('userTeam') || 'All Others',
      },
    })
    if (!response.ok) {
      throw new Error(`Failed to fetch memories: ${response.statusText}`)
    }
    return response.json()
  }

  /**
   * Get all memories for the memory log UI
   */
  async getMemoryLog(options?: {
    limit?: number
    offset?: number
    pinnedOnly?: boolean
  }): Promise<{
    items: Array<{
      id: string
      source: string
      question: string
      answer: string
      created_at: string
      expires_at?: string
      team?: string
      pinned: boolean
      user_name?: string
      tags?: string[]
    }>
    total: number
  }> {
    const params = new URLSearchParams()
    if (options?.limit) params.set('limit', options.limit.toString())
    if (options?.offset) params.set('offset', options.offset.toString())
    if (options?.pinnedOnly) params.set('pinned_only', 'true')

    const response = await fetch(`${this.baseUrl}/api/memory/log?${params}`, {
      headers: {
        'X-User-Team': localStorage.getItem('userTeam') || 'All Others',
      },
    })
    if (!response.ok) {
      throw new Error(`Failed to fetch memory log: ${response.statusText}`)
    }
    return response.json()
  }

  /**
   * Delete a memory from the log
   */
  async deleteMemory(memoryId: string): Promise<{ success: boolean }> {
    const response = await fetch(`${this.baseUrl}/api/memory/${memoryId}`, {
      method: 'DELETE',
      headers: {
        'X-User-Team': localStorage.getItem('userTeam') || 'All Others',
      },
    })
    if (!response.ok) {
      throw new Error(`Failed to delete memory: ${response.statusText}`)
    }
    return response.json()
  }

  /**
   * Pin/unpin a memory
   */
  async toggleMemoryPin(memoryId: string, pinned: boolean): Promise<{ success: boolean }> {
    const response = await fetch(`${this.baseUrl}/api/memory/${memoryId}/pin`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        'X-User-Team': localStorage.getItem('userTeam') || 'All Others',
      },
      body: JSON.stringify({ pinned }),
    })
    if (!response.ok) {
      throw new Error(`Failed to update pin status: ${response.statusText}`)
    }
    return response.json()
  }

  /**
   * Block a topic from memory
   */
  async blockTopic(topic: string): Promise<{ success: boolean }> {
    const response = await fetch(`${this.baseUrl}/api/memory/block`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-User-Team': localStorage.getItem('userTeam') || 'All Others',
      },
      body: JSON.stringify({ topic }),
    })
    if (!response.ok) {
      throw new Error(`Failed to block topic: ${response.statusText}`)
    }
    return response.json()
  }

  // =====================================
  // Preferences (Priority/Block Topics)
  // =====================================

  /**
   * Get organization preferences (priorities and blocks)
   */
  async getPreferences(): Promise<{
    priorities: Array<{ id: string; target: string; description?: string; team?: string | null }>
    blocks: Array<{ id: string; target: string; description?: string; team?: string | null }>
  }> {
    const response = await fetch(`${this.baseUrl}/api/memory/preferences`, {
      headers: {
        'X-User-Team': localStorage.getItem('userTeam') || 'All Others',
      },
    })
    if (!response.ok) {
      throw new Error(`Failed to fetch preferences: ${response.statusText}`)
    }
    return response.json()
  }

  /**
   * Add a new preference (priority or block)
   */
  async addPreference(data: {
    type: 'prioritize' | 'block'
    target: string
    description?: string
    team?: string
  }): Promise<{ success: boolean; preference_id?: string }> {
    const response = await fetch(`${this.baseUrl}/api/memory/preferences`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-User-Name': localStorage.getItem('userName') || 'Anonymous',
        'X-User-Team': localStorage.getItem('userTeam') || 'All Others',
      },
      body: JSON.stringify(data),
    })
    if (!response.ok) {
      throw new Error(`Failed to add preference: ${response.statusText}`)
    }
    return response.json()
  }

  /**
   * Remove a preference
   */
  async removePreference(preferenceId: string): Promise<{ success: boolean }> {
    const response = await fetch(`${this.baseUrl}/api/memory/preferences/${preferenceId}`, {
      method: 'DELETE',
    })
    if (!response.ok) {
      throw new Error(`Failed to remove preference: ${response.statusText}`)
    }
    return response.json()
  }

  // =====================================
  // Deep Research - Saved Reports
  // =====================================

  /**
   * Get saved deep research reports
   */
  async getSavedReports(options?: {
    userId?: string
    limit?: number
    offset?: number
  }): Promise<{
    total: number
    limit: number
    offset: number
    reports: Array<{
      id: string
      query_hash: string
      query: string
      title: string
      executive_summary: string
      data_completeness: string
      overall_confidence: string
      validation_passed: boolean
      citation_count: number
      research_time_seconds: number
      sources_count: number
      companies: string[]
      industries: string[]
      topics: string[]
      user_id?: string
      created_at: string
    }>
  }> {
    const params = new URLSearchParams()
    if (options?.userId) params.set('user_id', options.userId)
    if (options?.limit) params.set('limit', options.limit.toString())
    if (options?.offset) params.set('offset', options.offset.toString())

    const response = await fetch(`${this.baseUrl}/api/research/reports?${params}`)
    if (!response.ok) {
      throw new Error(`Failed to fetch saved reports: ${response.statusText}`)
    }
    return response.json()
  }

  /**
   * Get a specific saved report by ID
   */
  async getSavedReportById(reportId: string): Promise<{
    id: string
    query: string
    title: string
    executive_summary: string
    overall_confidence: string
    validation_passed: boolean
    citation_count: number
    companies: string[]
    industries: string[]
    topics: string[]
    created_at: string
  } | null> {
    const response = await fetch(`${this.baseUrl}/api/research/reports/${reportId}`)
    if (response.status === 404) {
      return null
    }
    if (!response.ok) {
      throw new Error(`Failed to fetch report: ${response.statusText}`)
    }
    return response.json()
  }

  /**
   * Search for related past research reports
   */
  async searchRelatedReports(options: {
    query: string
    companies?: string[]
    industries?: string[]
    limit?: number
  }): Promise<{
    query: string
    count: number
    related_reports: Array<{
      id: string
      query: string
      title: string
      companies: string[]
      industries: string[]
      created_at: string
    }>
  }> {
    const params = new URLSearchParams()
    params.set('query', options.query)
    if (options.companies?.length) params.set('companies', options.companies.join(','))
    if (options.industries?.length) params.set('industries', options.industries.join(','))
    if (options.limit) params.set('limit', options.limit.toString())

    const response = await fetch(`${this.baseUrl}/api/research/reports/search/related?${params}`)
    if (!response.ok) {
      throw new Error(`Failed to search reports: ${response.statusText}`)
    }
    return response.json()
  }

  // =====================================
  // Apollo Service
  // =====================================

  /**
   * Enrich an organization by domain
   */
  async enrichOrganization(domain: string): Promise<any | null> {
    const response = await fetch(`${this.baseUrl}/api/pipeline/enrich?domain=${domain}`, {
      headers: {
        'X-User-Team': localStorage.getItem('userTeam') || 'All Others',
      }
    })

    if (response.status === 404) return null

    if (!response.ok) {
      throw new Error(`Failed to enrich organization: ${response.statusText}`)
    }
    return response.json()
  }

  /**
   * Reveal a contact's email
   */
  async revealContact(contactId: string): Promise<{ email: string | null; status: string }> {
    const response = await fetch(`${this.baseUrl}/api/pipeline/apollo/reveal`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-User-Team': localStorage.getItem('userTeam') || 'All Others',
      },
      body: JSON.stringify({ contact_id: contactId })
    })

    if (!response.ok) {
      throw new Error(`Failed to reveal contact: ${response.statusText}`)
    }
    return response.json()
  }
}

// Export singleton instance
export const api = new ApiClient()

// Export individual services for context usage
export const apolloService = api

// Export class for custom instances
export { ApiClient }
