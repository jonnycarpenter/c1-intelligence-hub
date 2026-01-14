// ============================================
// Core Types
// ============================================
export type Mode = 'pulse' | 'research' | 'products' | 'field-sales' | 'pipeline' | 'companies' | 'industries' | 'data-preferences' // | 'importyeti' // ARCHIVED
export type ViewMode = 'grid' | 'list'
export type Priority = 'critical' | 'high' | 'medium' | 'low'
export type Category = 'market' | 'supply-chain' | 'regulatory' | 'competitor' | 'pricing' | 'product' | 'industry'

export interface Source {
  name: string
  url: string
  title?: string
  published_at?: string
}

export interface DigestEntities {
  companies?: string[]
  materials?: string[]
  topics?: string[]
  industries?: string[]
}

export interface DigestItem {
  id: string
  title: string
  summary: string
  category: Category
  priority: Priority
  sources?: Source[]
  entities?: DigestEntities
  timestamp: string
  publishedAt?: Date
  coverage_count?: number
}

export interface DigestStats {
  totalItems: number
  byCategory: Record<string, number>
  byPriority: Record<string, number>
  lastUpdated: string
}

export interface Message {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: string | Date
  agentName?: string
  isError?: boolean
  chart?: ChartData
  reportId?: string
  traceUrl?: string
  toolCalls?: ToolCall[]
  thinking?: AgentThinking[]
}

export interface ToolCall {
  id?: string
  name: string
  input?: unknown
  output?: unknown
  args?: Record<string, unknown>
  result?: string
  status: 'pending' | 'running' | 'completed' | 'error'
  duration?: number
  startTime?: Date
  endTime?: Date
}

export interface AgentThinking {
  step: string
  reasoning?: string
  toolCalls?: ToolCall[]
  status: 'pending' | 'in-progress' | 'completed' | 'error'
  timestamp: string
}

export interface ChartData {
  type: 'bar' | 'line' | 'pie' | 'scatter'
  data: Record<string, unknown>
  options?: Record<string, unknown>
}

export interface ChatRequest {
  message: string
  tab: string
  session_id: string
}

export interface ChatResponse {
  content: string
  agent: string
  chart?: ChartData
  report_id?: string
  trace_url?: string
}

export interface Report {
  id: string
  type: string
  status: 'pending' | 'generating' | 'ready' | 'error'
  title: string
  created_at: string
  download_url?: string
}

export interface ReportItem {
  id: string
  title: string
  summary?: string
  category: Category
  priority: Priority
  addedAt?: string
  content?: string
  source?: Mode
}

// ============================================
// Research Section Types
// ============================================
export interface ResearchSection {
  id: string
  title: string
  query: string  // Original user question
  content: string  // Markdown content from agent
  timestamp: string
  isCollapsed: boolean
  isDeepResearch?: boolean
  charts?: ChartData[]
  sources?: Source[]
}

export interface ResearchTemplate {
  id: string
  title: string
  description: string
  icon: string  // Icon name as string
  prompt: string
  color: string  // Tailwind color class
}

export interface RecentSearch {
  id: string
  query: string
  title: string  // Short title for display
  timestamp: string
  sectionId?: string  // Link to section if still on canvas
}

export type ClarificationAction = 'extend_current' | 'new_section' | null

export interface ClarificationRequest {
  question: string
  currentTopic: string
  suggestedNewTopic?: string
  relatednessScore: number
}

export interface Company {
  company: string
  stock_ticker?: string
  type: string
}

export interface Material {
  material_process_name: string
  category?: string
}

export interface Industry {
  industry: string
  application: string
}

export interface UserPreferences {
  global_exclusions: string[]
  tracked_companies: string[]
  created_at?: string
  updated_at?: string
}

export interface ApiError {
  detail: string
  status_code: number
}

// ============================================
// Pipeline Types
// ============================================
export interface PipelineProspect {
  id: string
  title: string
  url: string
  description: string
  score?: number
  published_date?: string
  highlights?: string[]
  // Enhanced fields (v2)
  domain?: string
  logo_url?: string
  company_name?: string
  apollo_enrichment?: ApolloEnrichmentResult
  // User-added fields
  notes?: string
  addedAt: string
  status: 'new' | 'contacted' | 'qualified' | 'converted'
}

export interface PipelineContact {
  id: string
  name: string
  url: string
  snippet: string
  title?: string
  company?: string
  // Enhanced fields (v2)
  company_domain?: string
  logo_url?: string
  location?: string
  // User-added fields
  notes?: string
  addedAt: string
  prospectId?: string  // Link to saved prospect
}

// Legacy types (backward compatible)
export interface ProspectSearchResult {
  title: string
  url: string
  description: string
  score?: number
  published_date?: string
  highlights?: string[]
}

export interface ContactSearchResult {
  name: string
  url: string
  snippet: string
  title?: string
  company?: string
}

// Enhanced types (v2 - with logo support)
export interface EnhancedProspectSearchResult {
  title: string
  url: string
  description: string
  domain: string
  logo_url?: string
  score?: number
  published_date?: string
  highlights?: string[]
  company_name?: string
  apollo_enrichment?: ApolloEnrichmentResult
}

export interface EnhancedContactSearchResult {
  name: string
  url: string
  snippet: string
  title?: string
  company?: string
  company_domain?: string
  logo_url?: string
  location?: string
  score?: number
}

export interface EnhancedTriggerEventResult {
  title: string
  url: string
  summary: string
  source_domain: string
  published_date?: string
  event_type?: string
  highlights?: string[]
  mentioned_company?: string
  mentioned_company_domain?: string
  logo_url?: string
}

// ============================================
// Apollo.io Types
// ============================================

export interface ApolloEnrichmentResult {
  // Identity
  name: string
  domain: string
  description?: string
  logo_url?: string

  // Firmographics
  employee_count?: number
  founded_year?: number
  industry?: string
  annual_revenue?: number
  revenue_printed?: string  // e.g., "1.9B"

  // Location
  city?: string
  state?: string
  country?: string
  headquarters?: string // Keeping for backward compatibility

  // Contact & Web
  phone?: string
  linkedin_url?: string
  website_url?: string

  // Tech & Classification
  technologies?: string[]
  keywords?: string[]
  supply_chain_matches?: string[]

  // Stock info
  ticker?: string
}

export interface ApolloContactTeaserResult {
  id: string  // Apollo person ID - use for reveal
  first_name: string
  last_name_preview?: string  // Obfuscated in teaser
  name_display?: string
  title?: string
  seniority?: string
  department?: string
  company_name?: string
  company_domain?: string
  logo_url?: string
  has_email: boolean
  has_phone: boolean
  linkedin_url?: string
  location?: string  // "City, State"
}

export interface ApolloContactRevealedResult {
  id: string
  name: string
  first_name: string
  last_name: string
  title?: string
  seniority?: string
  photo_url?: string

  // The good stuff - verified contact info
  email?: string
  email_status?: string
  phone?: string
  linkedin_url?: string

  // Company info
  company_name?: string
  company_domain?: string
  logo_url?: string

  // Location
  location?: string
}

export interface ApolloCreditStatus {
  used: number
  remaining: number
  limit: number
  reset_date: string
  utilization: string
  can_reveal: boolean
}

// Response types
export interface ProspectSearchResponse {
  count: number
  results: ProspectSearchResult[]
  query_type: 'similar' | 'search'
}

export interface ContactSearchResponse {
  count: number
  results: ContactSearchResult[]
}

export interface EnhancedProspectSearchResponse {
  count: number
  results: EnhancedProspectSearchResult[]
  query_type: 'similar' | 'search'
}

export interface EnhancedContactSearchResponse {
  count: number
  results: EnhancedContactSearchResult[]
}

export interface EnhancedTriggerEventSearchResponse {
  count: number
  results: EnhancedTriggerEventResult[]
}

// ============================================
// Pipeline Agent Types
// ============================================
export type SearchBlockType =
  | 'similar_companies'
  | 'search_companies'
  | 'contacts'
  | 'trigger_events'
  | 'webset_building'
  | 'apollo_enrichment'
  | 'apollo_contacts'
  | 'apollo_contact_revealed'
  | 'apollo_credits'

export interface SearchBlock {
  id: string
  block_type: SearchBlockType
  title: string
  query_context: string

  // Exa.ai results
  prospects?: EnhancedProspectSearchResult[]
  contacts?: EnhancedContactSearchResult[]
  trigger_events?: EnhancedTriggerEventResult[]

  // Apollo.io results
  apollo_enrichment?: ApolloEnrichmentResult
  apollo_contacts?: ApolloContactTeaserResult[]
  apollo_contact_revealed?: ApolloContactRevealedResult
  apollo_credits?: ApolloCreditStatus

  // Company enrichment for contact searches (firmographics)
  company_enrichment?: ApolloEnrichmentResult

  // Webset fields for Full List mode
  webset_id?: string
  webset_name?: string
  webset_status?: 'idle' | 'running' | 'completed' | 'failed'

  result_count: number
  is_expanded: boolean
}

export interface AgentChatRequest {
  message: string
  conversation_history?: Array<{
    role: 'user' | 'assistant'
    content: string
  }>
}

export interface AgentChatResponse {
  message: string
  search_blocks: SearchBlock[]
  suggested_followups: string[]
  requires_confirmation: boolean
  confirmation_prompt?: string
}

export interface PipelineConversation {
  id: string
  messages: Array<{
    role: 'user' | 'assistant'
    content: string
    timestamp: string
    search_blocks?: SearchBlock[]
  }>
  search_blocks: SearchBlock[]  // All accumulated blocks
}

// ============================================
// Mode Configurations
// ============================================
export const modeConfig = {
  pulse: {
    icon: 'Activity',
    title: 'Intelligence Pulse',
    subtitle: 'Real-time industry monitoring',
    description: 'Real-time intelligence',
    color: 'text-emerald-500',
    bg: 'bg-emerald-100',
    bgDark: 'bg-emerald-500',
  },
  research: {
    icon: 'Search',
    title: 'Deep Research',
    subtitle: 'Comprehensive analysis & insights',
    description: 'Deep analysis',
    color: 'text-emerald-500',
    bg: 'bg-emerald-100',
    bgDark: 'bg-emerald-500',
  },
  products: {
    icon: 'Package',
    title: 'Product Intelligence',
    subtitle: 'SKU analysis & comparisons',
    description: 'Product intelligence',
    color: 'text-blue-500',
    bg: 'bg-blue-100',
    bgDark: 'bg-blue-500',
  },

  // ARCHIVED - Trade Intel
  // importyeti: {
  //   icon: 'Ship',
  //   title: 'Trade Intelligence',
  //   subtitle: 'Supply chain & shipment tracking',
  //   description: 'Trade intelligence',
  //   color: 'text-indigo-500',
  //   bg: 'bg-indigo-100',
  //   bgDark: 'bg-indigo-500',
  // },
} as const

export const chatSuggestions: Record<Mode, string[]> = {
  pulse: ['What happened with Hexcel this week?', 'Recent carbon fiber news', 'Competitor M&A activity'],
  research: ['Analyze aerospace themes from recent earnings', 'Carbon fiber price trends', 'Compare Hexcel vs Toray'],
  products: ['Hexcel prepreg SKUs for aerospace', 'Compare epoxy resin options', 'T700 carbon fiber specs'],
  'field-sales': ['Record field intel', 'Voice memo from customer visit', 'Log competitor sighting'],
  pipeline: ['Composite buyers at Boeing', 'Aerospace contacts in my territory', 'New prospect recommendations'],
  companies: ['Show tracked companies', 'Latest Hexcel news', 'Compare Toray vs SGL Carbon'],
  industries: ['Aerospace market overview', 'Which industries are growing fastest?', 'EV composites trends'],
  'data-preferences': ['Update my tracked companies', 'Change my material preferences', 'Set industry focus'],

  // importyeti: ['Show top suppliers', 'Analyze Jushi Group shipments', 'Find suppliers for fiberglass'], // ARCHIVED
}

export const welcomeMessages: Record<Mode, string> = {
  pulse: "Welcome to the Intelligence Pulse. I'm monitoring the composites industry in real-time.\n\nI can help you with:\n• **Recent news** on companies, materials, or markets\n• **Competitor movements** and announcements\n• **Supply chain** updates",
  research: "Welcome to Deep Research. I'm ready for comprehensive analysis.\n\nI can help you with:\n• **Earnings call analysis** — themes, sentiment\n• **Financial trends** — commodities, pricing\n• **Comparative analysis** — across companies",
  products: "Welcome to Product Intelligence.\n\nI can help you with:\n• **SKU lookups** — competitor catalogs\n• **Spec comparisons** — technical specs\n• **Gap analysis** — opportunities",
  'field-sales': "Welcome to Field Intel. Coming soon!\n\nYou'll be able to:\n• **Record voice memos** — capture field intelligence\n• **Log competitor sightings** — track field observations\n• **Share insights** — distribute intel to the team",
  pipeline: "Welcome to Pipeline.\n\nDiscover new prospects and contacts using AI-powered semantic search:\n• **Find Similar Companies** — Enter a customer URL to find lookalikes\n• **Search Companies** — Natural language company discovery\n• **Find Contacts** — Decision makers by role and industry",
  companies: "Welcome to Company Intelligence.\n\nI can help you with:\n• **Company tracking** — competitors, suppliers, customers\n• **Earnings analysis** — financial performance\n• **Market position** — competitive landscape",
  industries: "Welcome to Industry Intelligence.\n\nI can help you with:\n• **Market analysis** — size, growth, trends\n• **Industry trends** — emerging applications\n• **Sector comparisons** — cross-industry insights",
  'data-preferences': "Welcome to Data Preferences.\n\nI can help you with:\n• **Company tracking** — add or remove companies\n• **Material preferences** — focus materials\n• **Industry settings** — customize your focus areas",

  // importyeti: "Welcome to Trade Intelligence.\n\nI can help you with:\n• **Shipment tracking** — Monitor import volumes\n• **Supplier analysis** — Deep dive into supplier relationships\n• **Competitive intel** — See who else is buying from your suppliers", // ARCHIVED
}

// ============================================
// Deep Research Types (SSE Events)
// ============================================

/** Tool progress event from agent execution */
export interface ToolProgressEvent {
  tool: string
  message: string
  ticker?: string | null
  status?: 'running' | 'completed' | 'error'
}

/** Node lifecycle events */
export interface NodeProgressEvent {
  node: string
  description: string
  parallel_with?: string | null
  duration_hint?: string
}

/** Cache hit event */
export interface CacheHitEvent {
  query_hash: string
  message: string
}

/** Category/sales intelligence output */
export interface CategoryOutput {
  territory_insights?: {
    east_relevance: number
    west_relevance: number
    east_summary?: string
    west_summary?: string
  }
  product_recommendations?: Array<{
    product_name: string
    relevance_score: number
    rationale: string
  }>
  sales_plays?: Array<{
    title: string
    hook: string
    objection_handlers?: string[]
  }>
  industry_talking_points?: string[]
}

/** Validation output */
export interface ValidationOutput {
  validation_passed: boolean
  citation_issues?: Array<{
    claim: string
    issue: string
  }>
  unsubstantiated_claims?: string[]
  confidence_adjustments?: Array<{
    section: string
    adjustment: string
  }>
  warnings?: string[]
}

/** Deep Research report structure */
export interface DeepResearchReport {
  report_id: string
  generated_at: string
  query: string
  data_completeness?: number
  overall_confidence?: string
  executive_summary: {
    headline: string
    key_points: string[]
    key_metrics: Array<{ label: string; value: string; context?: string }>
  }
  sections: Array<{
    section_title: string
    content: string
    citations: Array<{
      source_name: string
      url?: string
      published_date?: string
      quote?: string
    }>
  }>
  field_sales?: {
    offensive_angles: Array<{
      title: string
      description: string
      target_persona?: string
    }>
    defensive_angles: Array<{
      title: string
      description: string
      competitive_threat?: string
    }>
    questions_to_explore: string[]
  }
}

/** Workflow node types */
export type DeepResearchNode =
  | 'groom'
  | 'financial_research'
  | 'industry_research'
  | 'visual_research'
  | 'synthesize'
  | 'categorize'
  | 'validate'

/** Node status for UI display */
export interface NodeStatus {
  node: DeepResearchNode
  status: 'pending' | 'running' | 'completed' | 'error'
  description: string
  startTime?: Date
  endTime?: Date
  parallel_with?: string | null
}

// ============================================
// Utility Functions
// ============================================
export function formatRelativeTime(date: Date): string {
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  const hours = Math.floor(diff / (1000 * 60 * 60))
  if (hours < 1) return 'Just now'
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}
