import type { Edge } from '@xyflow/react'

// ============================================
// Section A: Weekly Executive Briefing — Edges
// ============================================

export const briefingEdges: Edge[] = [
  // ── Trigger → Data ──
  {
    id: 'e-brief-trigger-data',
    source: 'brief-trigger',
    target: 'brief-data',
    type: 'smoothstep',
    animated: true,
    label: 'POST /scheduler/briefing',
    style: { stroke: '#f97316', strokeWidth: 1.5 },
    labelStyle: { fontSize: 9, fill: '#94a3b8' },
  },

  // ── Data → Agent 1 ──
  {
    id: 'e-brief-data-agent1',
    source: 'brief-data',
    target: 'brief-agent1',
    type: 'smoothstep',
    animated: true,
    label: '~200 articles (batched)',
    style: { stroke: '#60a5fa', strokeWidth: 1.5 },
    labelStyle: { fontSize: 9, fill: '#64748b' },
  },

  // ── Agent 1 → Agent 2 ──
  {
    id: 'e-brief-agent1-agent2',
    source: 'brief-agent1',
    target: 'brief-agent2',
    type: 'smoothstep',
    animated: true,
    label: 'pre_briefing JSON',
    style: { stroke: '#10b981', strokeWidth: 2 },
    labelStyle: { fontSize: 9, fill: '#64748b' },
  },

  // ── Voice Enrichment → Agent 2 ──
  {
    id: 'e-brief-voice-agent2',
    source: 'brief-voice',
    target: 'brief-agent2',
    type: 'smoothstep',
    animated: true,
    label: 'exec quotes + nuggets',
    style: { stroke: '#8b5cf6', strokeWidth: 1.5, strokeDasharray: '5,5' },
    labelStyle: { fontSize: 9, fill: '#94a3b8' },
  },

  // ── Historical Context → Agent 2 ──
  {
    id: 'e-brief-history-agent2',
    source: 'brief-history',
    target: 'brief-agent2',
    type: 'smoothstep',
    animated: true,
    label: 'prior briefings',
    style: { stroke: '#8b5cf6', strokeWidth: 1.5, strokeDasharray: '5,5' },
    labelStyle: { fontSize: 9, fill: '#94a3b8' },
  },

  // ── Agent 2 → Podcast ──
  {
    id: 'e-brief-agent2-podcast',
    source: 'brief-agent2',
    target: 'brief-podcast',
    type: 'smoothstep',
    animated: true,
    label: 'briefing JSON',
    style: { stroke: '#10b981', strokeWidth: 2 },
    labelStyle: { fontSize: 9, fill: '#64748b' },
  },

  // ── Agent 2 → Storage ──
  {
    id: 'e-brief-agent2-store',
    source: 'brief-agent2',
    target: 'brief-store',
    type: 'smoothstep',
    label: 'weekly_briefings',
    style: { stroke: '#8b5cf6', strokeWidth: 2 },
    labelStyle: { fontSize: 9, fill: '#94a3b8' },
  },

  // ── Podcast → Storage ──
  {
    id: 'e-brief-podcast-store',
    source: 'brief-podcast',
    target: 'brief-store',
    type: 'smoothstep',
    label: 'MP3 → GCS',
    style: { stroke: '#8b5cf6', strokeWidth: 1.5 },
    labelStyle: { fontSize: 9, fill: '#94a3b8' },
  },
]


// ============================================
// Section B: Deep Research — Edges
// ============================================

export const deepResearchEdges: Edge[] = [
  // ── Input → Groomer ──
  {
    id: 'e-dr-input-groomer',
    source: 'dr-input',
    target: 'dr-groomer',
    type: 'smoothstep',
    animated: true,
    label: 'research query',
    style: { stroke: '#60a5fa', strokeWidth: 1.5 },
    labelStyle: { fontSize: 9, fill: '#64748b' },
  },

  // ── Groomer → Fan-Out ──
  {
    id: 'e-dr-groomer-fanout',
    source: 'dr-groomer',
    target: 'dr-fanout',
    type: 'smoothstep',
    animated: true,
    label: 'sub-queries',
    style: { stroke: '#10b981', strokeWidth: 2 },
    labelStyle: { fontSize: 9, fill: '#64748b' },
  },

  // ── Groomer ← → Input (clarification loop) ──
  {
    id: 'e-dr-groomer-clarify',
    source: 'dr-groomer',
    target: 'dr-input',
    type: 'smoothstep',
    label: 'clarification (max 2)',
    style: { stroke: '#f59e0b', strokeWidth: 1.5, strokeDasharray: '6,4' },
    labelStyle: { fontSize: 9, fill: '#d97706' },
    sourceHandle: undefined,
    targetHandle: undefined,
  },

  // ── Fan-Out → 3 Agents (parallel) ──
  {
    id: 'e-dr-fanout-financial',
    source: 'dr-fanout',
    target: 'dr-financial',
    type: 'smoothstep',
    animated: true,
    label: 'parallel',
    style: { stroke: '#10b981', strokeWidth: 2 },
    labelStyle: { fontSize: 9, fill: '#059669', fontWeight: 600 },
  },
  {
    id: 'e-dr-fanout-industry',
    source: 'dr-fanout',
    target: 'dr-industry',
    type: 'smoothstep',
    animated: true,
    style: { stroke: '#10b981', strokeWidth: 2 },
  },
  {
    id: 'e-dr-fanout-visual',
    source: 'dr-fanout',
    target: 'dr-visual',
    type: 'smoothstep',
    animated: true,
    style: { stroke: '#10b981', strokeWidth: 2 },
  },

  // ── 3 Agents → Fan-In ──
  {
    id: 'e-dr-financial-fanin',
    source: 'dr-financial',
    target: 'dr-fanin',
    type: 'smoothstep',
    animated: true,
    label: 'findings',
    style: { stroke: '#6366f1', strokeWidth: 1.5 },
    labelStyle: { fontSize: 9, fill: '#64748b' },
  },
  {
    id: 'e-dr-industry-fanin',
    source: 'dr-industry',
    target: 'dr-fanin',
    type: 'smoothstep',
    animated: true,
    style: { stroke: '#6366f1', strokeWidth: 1.5 },
  },
  {
    id: 'e-dr-visual-fanin',
    source: 'dr-visual',
    target: 'dr-fanin',
    type: 'smoothstep',
    animated: true,
    label: 'visuals',
    style: { stroke: '#6366f1', strokeWidth: 1.5 },
    labelStyle: { fontSize: 9, fill: '#64748b' },
  },

  // ── Fan-In → Synthesizer ──
  {
    id: 'e-dr-fanin-synth',
    source: 'dr-fanin',
    target: 'dr-synth',
    type: 'smoothstep',
    animated: true,
    label: 'merged state',
    style: { stroke: '#10b981', strokeWidth: 2 },
    labelStyle: { fontSize: 9, fill: '#64748b' },
  },

  // ── Synthesizer → Validator ──
  {
    id: 'e-dr-synth-validator',
    source: 'dr-synth',
    target: 'dr-validator',
    type: 'smoothstep',
    animated: true,
    label: 'draft report',
    style: { stroke: '#f59e0b', strokeWidth: 1.5 },
    labelStyle: { fontSize: 9, fill: '#64748b' },
  },

  // ── Validator → Output ──
  {
    id: 'e-dr-validator-output',
    source: 'dr-validator',
    target: 'dr-output',
    type: 'smoothstep',
    animated: true,
    label: 'validated report',
    style: { stroke: '#8b5cf6', strokeWidth: 2 },
    labelStyle: { fontSize: 9, fill: '#64748b' },
  },

  // ── Memory → Groomer (context injection) ──
  {
    id: 'e-dr-memory-groomer',
    source: 'dr-memory',
    target: 'dr-groomer',
    type: 'smoothstep',
    label: 'prior research context',
    style: { stroke: '#a78bfa', strokeWidth: 1.5, strokeDasharray: '5,5' },
    labelStyle: { fontSize: 9, fill: '#94a3b8' },
  },

  // ── Output → Memory (persistence) ──
  {
    id: 'e-dr-output-memory',
    source: 'dr-output',
    target: 'dr-memory',
    type: 'smoothstep',
    label: 'cache report',
    style: { stroke: '#a78bfa', strokeWidth: 1.5, strokeDasharray: '5,5' },
    labelStyle: { fontSize: 9, fill: '#94a3b8' },
  },
]
