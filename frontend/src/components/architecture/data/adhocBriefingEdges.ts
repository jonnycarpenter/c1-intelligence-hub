import type { Edge } from '@xyflow/react'

// ============================================
// Section C: Ad-Hoc Briefing Agent — Edges
// ============================================

export const adhocBriefingEdges: Edge[] = [
  // ── Trigger → Session ──
  {
    id: 'e-adhoc-trigger-session',
    source: 'adhoc-trigger',
    target: 'adhoc-session',
    type: 'smoothstep',
    animated: true,
    label: 'user question',
    style: { stroke: '#3b82f6', strokeWidth: 1.5 },
    labelStyle: { fontSize: 9, fill: '#64748b' },
  },

  // ── Session → Router ──
  {
    id: 'e-adhoc-session-router',
    source: 'adhoc-session',
    target: 'adhoc-router',
    type: 'smoothstep',
    animated: true,
    label: 'session + context',
    style: { stroke: '#0ea5e9', strokeWidth: 1.5 },
    labelStyle: { fontSize: 9, fill: '#64748b' },
  },

  // ── Router → Article Feed searches ──
  {
    id: 'e-adhoc-router-corpus',
    source: 'adhoc-router',
    target: 'adhoc-corpus',
    type: 'smoothstep',
    label: 'article feed',
    style: { stroke: '#8b5cf6', strokeWidth: 1.5 },
    labelStyle: { fontSize: 9, fill: '#94a3b8' },
  },
  {
    id: 'e-adhoc-router-exa',
    source: 'adhoc-router',
    target: 'adhoc-exa',
    type: 'smoothstep',
    label: 'article feed',
    style: { stroke: '#8b5cf6', strokeWidth: 1.5 },
    labelStyle: { fontSize: 9, fill: '#94a3b8' },
  },
  {
    id: 'e-adhoc-router-stocknews',
    source: 'adhoc-router',
    target: 'adhoc-stocknews',
    type: 'smoothstep',
    label: 'article feed',
    style: { stroke: '#8b5cf6', strokeWidth: 1.5 },
    labelStyle: { fontSize: 9, fill: '#94a3b8' },
  },

  // ── Router → Financial Feed searches ──
  {
    id: 'e-adhoc-router-earnings',
    source: 'adhoc-router',
    target: 'adhoc-earnings',
    type: 'smoothstep',
    label: 'financial feed',
    style: { stroke: '#f59e0b', strokeWidth: 1.5, strokeDasharray: '5,5' },
    labelStyle: { fontSize: 9, fill: '#94a3b8' },
  },
  {
    id: 'e-adhoc-router-sec',
    source: 'adhoc-router',
    target: 'adhoc-sec',
    type: 'smoothstep',
    label: 'financial feed',
    style: { stroke: '#f59e0b', strokeWidth: 1.5, strokeDasharray: '5,5' },
    labelStyle: { fontSize: 9, fill: '#94a3b8' },
  },

  // ── Router → Expert Feed search ──
  {
    id: 'e-adhoc-router-podcast',
    source: 'adhoc-router',
    target: 'adhoc-podcast',
    type: 'smoothstep',
    label: 'expert feed',
    style: { stroke: '#10b981', strokeWidth: 1.5, strokeDasharray: '5,5' },
    labelStyle: { fontSize: 9, fill: '#94a3b8' },
  },

  // ── All searches → Synthesis ──
  {
    id: 'e-adhoc-corpus-synth',
    source: 'adhoc-corpus',
    target: 'adhoc-synth',
    type: 'smoothstep',
    animated: true,
    style: { stroke: '#10b981', strokeWidth: 2 },
  },
  {
    id: 'e-adhoc-exa-synth',
    source: 'adhoc-exa',
    target: 'adhoc-synth',
    type: 'smoothstep',
    animated: true,
    style: { stroke: '#10b981', strokeWidth: 2 },
  },
  {
    id: 'e-adhoc-stocknews-synth',
    source: 'adhoc-stocknews',
    target: 'adhoc-synth',
    type: 'smoothstep',
    animated: true,
    style: { stroke: '#10b981', strokeWidth: 2 },
  },
  {
    id: 'e-adhoc-earnings-synth',
    source: 'adhoc-earnings',
    target: 'adhoc-synth',
    type: 'smoothstep',
    animated: true,
    style: { stroke: '#10b981', strokeWidth: 2 },
  },
  {
    id: 'e-adhoc-sec-synth',
    source: 'adhoc-sec',
    target: 'adhoc-synth',
    type: 'smoothstep',
    animated: true,
    style: { stroke: '#10b981', strokeWidth: 2 },
  },
  {
    id: 'e-adhoc-podcast-synth',
    source: 'adhoc-podcast',
    target: 'adhoc-synth',
    type: 'smoothstep',
    animated: true,
    style: { stroke: '#10b981', strokeWidth: 2 },
  },

  // ── Synthesis → Output ──
  {
    id: 'e-adhoc-synth-output',
    source: 'adhoc-synth',
    target: 'adhoc-output',
    type: 'smoothstep',
    animated: true,
    label: 'SSE token stream',
    style: { stroke: '#6366f1', strokeWidth: 2 },
    labelStyle: { fontSize: 9, fill: '#64748b' },
  },

  // ── Output → BigQuery ──
  {
    id: 'e-adhoc-output-bq',
    source: 'adhoc-output',
    target: 'adhoc-bq',
    type: 'smoothstep',
    label: 'save briefing',
    style: { stroke: '#8b5cf6', strokeWidth: 1.5, strokeDasharray: '5,5' },
    labelStyle: { fontSize: 9, fill: '#94a3b8' },
  },
]
