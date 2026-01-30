/**
 * Types for the new Need to Know briefing system
 * 
 * Weekly Executive Briefing: Dynamic sections with agent-chosen headers
 * Ad Hoc Briefing: Quick user-generated briefings
 */

// =============================================================================
// Weekly Executive Briefing Types
// =============================================================================

export interface CompanyWithLogo {
  name: string
  domain?: string
  logo_url?: string
}

export interface BriefingInsight {
  /** The insight text with inline citations [1], [2], etc. */
  text: string
  /** 'net_new' or 'continuing' - determines badge display */
  status: 'net_new' | 'continuing'
  /** Companies mentioned in this insight */
  companies_mentioned: string[]
}

export interface SourceArticle {
  /** Citation number - matches [N] in insight text */
  article_number: number | string
  id: string
  title: string
  url: string
  source_name: string
  source_type?: string
  published_at?: string
  summary?: string
  priority?: string
  relevance_score?: number
}

export interface BriefingSection {
  /** Agent-generated header (2-5 words, specific not generic) */
  header: string
  /** The main headline for this section - always visible, bolded */
  headline: BriefingInsight
  /** Supporting insights - shown in expandable tray */
  insights: BriefingInsight[]
  /** Source articles used for this section */
  source_articles: SourceArticle[]
  /** Companies mentioned with logos */
  companies_with_logos: CompanyWithLogo[]
}

export interface WeeklyBriefing {
  id: string
  briefing_type: 'weekly_executive'
  briefing_title: string
  /** Bottom Line Up Front - single sentence high-level summary */
  bluf?: string
  sections: BriefingSection[]
  all_companies_mentioned: CompanyWithLogo[]
  key_topics_this_week: string[]
  overall_trend: string
  period_start: string
  period_end: string
  generated_at: string
  model: string
  article_count: number
  article_ids: string[]
  /** Podcast audio fields */
  podcast_url?: string
  podcast_duration_seconds?: number
  podcast_generated_at?: string
}

// =============================================================================
// Ad Hoc Briefing Types
// =============================================================================

export interface AdHocBriefingContext {
  current_brief_headlines?: string[]
  current_brief_date?: string
  recent_digest_topics?: string[]
  current_brief_id?: string
  active_filters?: string[]
  // Discovery tab context
  visible_digest_items?: Array<{
    title: string
    summary?: string
    source_name?: string
    category?: string
    priority?: string
  }>
  active_category?: string
}

export interface AdHocBriefingRequest {
  question: string
  context?: AdHocBriefingContext
  is_follow_up?: boolean
  stream?: boolean
  session_id?: string  // Optional session ID for follow-up questions
}

export interface AdHocSourceUsed {
  title: string
  url?: string
  relevance?: string
}

/**
 * Session state for stateful ad-hoc briefing conversations
 */
export interface BriefingSessionInfo {
  session_id: string
  follow_up_count: number
  max_follow_ups: number
  turns_remaining: number
  created_at: string
  last_activity: string
  history_length: number
}

export interface AdHocBriefing {
  id: string
  question: string
  answer: string
  sources_used: AdHocSourceUsed[]
  confidence: 'high' | 'medium' | 'low'
  suggest_deep_research: boolean
  deep_research_query?: string
  related_topics: string[]
  follow_up_count: number
  redirect_to_deep_research?: boolean
  generated_at: string
  model?: string
  error?: string
  // Session management fields
  session_id?: string
  session?: BriefingSessionInfo
}

// =============================================================================
// Combined History Types
// =============================================================================

export interface BriefingHistoryItem {
  id: string
  type: 'weekly' | 'adhoc'
  title: string  // briefing_title for weekly, question for adhoc
  generated_at: string
  // Additional fields depending on type
  sections?: BriefingSection[]  // Weekly only
  answer?: string  // Ad hoc only
}

export interface AllBriefingHistory {
  weekly_briefings: WeeklyBriefing[]
  adhoc_briefings: AdHocBriefing[]
  total_weekly: number
  total_adhoc: number
}

// =============================================================================
// Legacy Support (existing category-based briefings)
// =============================================================================

export interface LegacyBriefingData {
  id: string
  category: string
  headline: string
  summary: string
  key_insights: string[]
  trend_signal: 'emerging' | 'accelerating' | 'stable' | 'declining' | 'mixed'
  attention_flag: 'high' | 'medium' | 'low'
  attention_reason: string | null
  article_ids: string[]
  period_start: string
  period_end: string
  generated_at: string
}
