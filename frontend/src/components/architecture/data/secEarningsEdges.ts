import type { Edge } from '@xyflow/react'

// ============================================
// Section B: SEC Filings & Earnings — Edges
// ============================================

export const secEarningsEdges: Edge[] = [
  // ── Collection → Extraction ──
  {
    id: 'e-sec-collect-extract',
    source: 'sec-collect',
    target: 'sec-extract',
    type: 'smoothstep',
    animated: true,
    label: 'filings',
    style: { stroke: '#60a5fa', strokeWidth: 1.5 },
    labelStyle: { fontSize: 10, fill: '#64748b' },
  },
  {
    id: 'e-earn-collect-extract',
    source: 'earn-collect',
    target: 'earn-extract',
    type: 'smoothstep',
    animated: true,
    label: 'transcripts',
    style: { stroke: '#60a5fa', strokeWidth: 1.5 },
    labelStyle: { fontSize: 10, fill: '#64748b' },
  },

  // ── Extraction → Storage ──
  {
    id: 'e-sec-extract-filings',
    source: 'sec-extract',
    target: 'bq-sec-filings',
    type: 'smoothstep',
    style: { stroke: '#8b5cf6', strokeWidth: 2 },
  },
  {
    id: 'e-sec-extract-nuggets',
    source: 'sec-extract',
    target: 'bq-sec-nuggets',
    type: 'smoothstep',
    style: { stroke: '#8b5cf6', strokeWidth: 2 },
    label: 'nuggets',
    labelStyle: { fontSize: 9, fill: '#94a3b8' },
  },
  {
    id: 'e-earn-extract-quotes',
    source: 'earn-extract',
    target: 'bq-earn-quotes',
    type: 'smoothstep',
    style: { stroke: '#8b5cf6', strokeWidth: 2 },
    label: 'quotes',
    labelStyle: { fontSize: 9, fill: '#94a3b8' },
  },

  // ── Storage → Downstream ──
  {
    id: 'e-nuggets-briefing',
    source: 'bq-sec-nuggets',
    target: 'downstream-briefing',
    type: 'smoothstep',
    style: { stroke: '#a78bfa', strokeWidth: 1.5, strokeDasharray: '5,5' },
    label: 'voice enrichment',
    labelStyle: { fontSize: 9, fill: '#94a3b8' },
  },
  {
    id: 'e-quotes-briefing',
    source: 'bq-earn-quotes',
    target: 'downstream-briefing',
    type: 'smoothstep',
    style: { stroke: '#a78bfa', strokeWidth: 1.5, strokeDasharray: '5,5' },
  },
  {
    id: 'e-nuggets-research',
    source: 'bq-sec-nuggets',
    target: 'downstream-research',
    type: 'smoothstep',
    style: { stroke: '#a78bfa', strokeWidth: 1.5, strokeDasharray: '5,5' },
    label: 'MCP tools',
    labelStyle: { fontSize: 9, fill: '#94a3b8' },
  },
  {
    id: 'e-quotes-research',
    source: 'bq-earn-quotes',
    target: 'downstream-research',
    type: 'smoothstep',
    style: { stroke: '#a78bfa', strokeWidth: 1.5, strokeDasharray: '5,5' },
  },
]
