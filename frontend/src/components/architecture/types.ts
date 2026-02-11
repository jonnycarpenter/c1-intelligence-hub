// ============================================
// Architecture Diagram Types
// ============================================

export type ArchNodeType =
  | 'dataSource'
  | 'processing'
  | 'agent'
  | 'storage'
  | 'scheduler'
  | 'fanOut'
  | 'externalApi'
  | 'gcpService'
  | 'tabNode'

export interface TechnicalDetail {
  sourceFiles?: string[]
  functions?: string[]
  model?: string
  apis?: string[]
  tables?: string[]
  lineCount?: number
  cost?: string          // e.g. "$0.20–0.60 / filing"
  dataVolume?: string    // e.g. "5,000+ articles"
}

export interface ConnectionInfo {
  incoming?: string[]
  outgoing?: string[]
}

export interface ArchNodeData {
  [key: string]: unknown
  label: string
  nodeType: ArchNodeType
  description: string
  technicalDetails?: TechnicalDetail
  connections?: ConnectionInfo
  // Visual customizations
  icon?: string
  color?: string
  badge?: string
  // Section grouping
  section?: string
  // Which sub-tab this node belongs to (for search navigation)
  tab?: ArchSubTab
  // Verbatim system prompt (for agent nodes)
  prompt?: string
}

export type ArchSubTab = 'ingestion' | 'tab-architecture' | 'agentic-workflows'
