import type { Edge } from '@xyflow/react'

// ============================================
// Section C: Expert Podcast Intelligence — Edges
// ============================================

export const podcastEdges: Edge[] = [
  // ── Pipeline: Discovery → Resolve → Extract ──
  {
    id: 'e-pod-rss-resolve',
    source: 'pod-rss',
    target: 'pod-resolve',
    type: 'smoothstep',
    animated: true,
    label: 'new episodes',
    style: { stroke: '#60a5fa', strokeWidth: 1.5 },
    labelStyle: { fontSize: 10, fill: '#64748b' },
  },
  {
    id: 'e-pod-resolve-extract',
    source: 'pod-resolve',
    target: 'pod-extract',
    type: 'smoothstep',
    animated: true,
    label: 'transcripts',
    style: { stroke: '#f59e0b', strokeWidth: 1.5 },
    labelStyle: { fontSize: 10, fill: '#64748b' },
  },

  // ── Extract → Storage ──
  {
    id: 'e-pod-extract-episodes',
    source: 'pod-extract',
    target: 'bq-pod-episodes',
    type: 'smoothstep',
    style: { stroke: '#8b5cf6', strokeWidth: 2 },
  },
  {
    id: 'e-pod-extract-quotes',
    source: 'pod-extract',
    target: 'bq-pod-quotes',
    type: 'smoothstep',
    style: { stroke: '#8b5cf6', strokeWidth: 2 },
    label: 'quotes',
    labelStyle: { fontSize: 9, fill: '#94a3b8' },
  },

  // ── Storage → Downstream ──
  {
    id: 'e-pod-quotes-downstream',
    source: 'bq-pod-quotes',
    target: 'pod-downstream',
    type: 'smoothstep',
    style: { stroke: '#a78bfa', strokeWidth: 1.5, strokeDasharray: '5,5' },
    label: 'MCP tool',
    labelStyle: { fontSize: 9, fill: '#94a3b8' },
  },
]
