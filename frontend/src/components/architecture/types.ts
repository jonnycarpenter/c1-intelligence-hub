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
}

export type ArchSubTab = 'ingestion' | 'tab-architecture' | 'agentic-workflows'
