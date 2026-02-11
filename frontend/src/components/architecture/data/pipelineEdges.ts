import type { Edge } from '@xyflow/react'

// ============================================
// Section D: Pipeline Sales Prospecting Agent — Edges
// ============================================

export const pipelineEdges: Edge[] = [
  // ── Input → Mode ──
  {
    id: 'e-pipe-input-mode',
    source: 'pipe-input',
    target: 'pipe-mode',
    type: 'smoothstep',
    animated: true,
    label: 'NL query',
    style: { stroke: '#3b82f6', strokeWidth: 1.5 },
    labelStyle: { fontSize: 9, fill: '#64748b' },
  },

  // ── Mode → Exa tools ──
  {
    id: 'e-pipe-mode-exa-similar',
    source: 'pipe-mode',
    target: 'pipe-exa-similar',
    type: 'smoothstep',
    label: 'Exa',
    style: { stroke: '#10b981', strokeWidth: 1.5 },
    labelStyle: { fontSize: 9, fill: '#94a3b8' },
  },
  {
    id: 'e-pipe-mode-exa-search',
    source: 'pipe-mode',
    target: 'pipe-exa-search',
    type: 'smoothstep',
    style: { stroke: '#10b981', strokeWidth: 1.5 },
  },
  {
    id: 'e-pipe-mode-exa-triggers',
    source: 'pipe-mode',
    target: 'pipe-exa-triggers',
    type: 'smoothstep',
    style: { stroke: '#10b981', strokeWidth: 1.5 },
  },

  // ── Mode → Apollo tools ──
  {
    id: 'e-pipe-mode-apollo-search',
    source: 'pipe-mode',
    target: 'pipe-apollo-search',
    type: 'smoothstep',
    label: 'Apollo',
    style: { stroke: '#f59e0b', strokeWidth: 1.5 },
    labelStyle: { fontSize: 9, fill: '#94a3b8' },
  },
  {
    id: 'e-pipe-mode-apollo-enrich',
    source: 'pipe-mode',
    target: 'pipe-apollo-enrich',
    type: 'smoothstep',
    style: { stroke: '#f59e0b', strokeWidth: 1.5 },
  },
  {
    id: 'e-pipe-mode-apollo-contacts',
    source: 'pipe-mode',
    target: 'pipe-apollo-contacts',
    type: 'smoothstep',
    style: { stroke: '#f59e0b', strokeWidth: 1.5 },
  },

  // ── Mode → BigQuery corpus ──
  {
    id: 'e-pipe-mode-bq',
    source: 'pipe-mode',
    target: 'pipe-bq-corpus',
    type: 'smoothstep',
    label: 'BigQuery',
    style: { stroke: '#8b5cf6', strokeWidth: 1.5, strokeDasharray: '5,5' },
    labelStyle: { fontSize: 9, fill: '#94a3b8' },
  },

  // ── Exa tools → Filter ──
  {
    id: 'e-pipe-exa-similar-filter',
    source: 'pipe-exa-similar',
    target: 'pipe-filter',
    type: 'smoothstep',
    animated: true,
    style: { stroke: '#10b981', strokeWidth: 2 },
  },
  {
    id: 'e-pipe-exa-search-filter',
    source: 'pipe-exa-search',
    target: 'pipe-filter',
    type: 'smoothstep',
    animated: true,
    style: { stroke: '#10b981', strokeWidth: 2 },
  },
  {
    id: 'e-pipe-exa-triggers-filter',
    source: 'pipe-exa-triggers',
    target: 'pipe-filter',
    type: 'smoothstep',
    animated: true,
    style: { stroke: '#10b981', strokeWidth: 2 },
  },

  // ── Apollo tools → Filter ──
  {
    id: 'e-pipe-apollo-search-filter',
    source: 'pipe-apollo-search',
    target: 'pipe-filter',
    type: 'smoothstep',
    animated: true,
    style: { stroke: '#f59e0b', strokeWidth: 2 },
  },
  {
    id: 'e-pipe-apollo-enrich-filter',
    source: 'pipe-apollo-enrich',
    target: 'pipe-filter',
    type: 'smoothstep',
    animated: true,
    style: { stroke: '#f59e0b', strokeWidth: 2 },
  },

  // ── Filter → Output ──
  {
    id: 'e-pipe-filter-output',
    source: 'pipe-filter',
    target: 'pipe-output',
    type: 'smoothstep',
    animated: true,
    label: 'filtered results',
    style: { stroke: '#6366f1', strokeWidth: 2 },
    labelStyle: { fontSize: 9, fill: '#64748b' },
  },

  // ── Contacts → Output (bypasses filter) ──
  {
    id: 'e-pipe-contacts-output',
    source: 'pipe-apollo-contacts',
    target: 'pipe-output',
    type: 'smoothstep',
    animated: true,
    label: 'contacts',
    style: { stroke: '#f59e0b', strokeWidth: 1.5 },
    labelStyle: { fontSize: 9, fill: '#94a3b8' },
  },

  // ── BigQuery → Output ──
  {
    id: 'e-pipe-bq-output',
    source: 'pipe-bq-corpus',
    target: 'pipe-output',
    type: 'smoothstep',
    label: 'chat insights',
    style: { stroke: '#8b5cf6', strokeWidth: 1.5, strokeDasharray: '5,5' },
    labelStyle: { fontSize: 9, fill: '#94a3b8' },
  },
]
