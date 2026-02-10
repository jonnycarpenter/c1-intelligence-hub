import type { Edge } from '@xyflow/react'

// ============================================
// Section A: Core Article Ingestion — Edges
// ============================================

export const ingestionSectionAEdges: Edge[] = [
  // ── Sources → Orchestrator (many-to-one) ──
  { id: 'e-rss-orch', source: 'src-rss', target: 'orch', type: 'smoothstep', animated: true, style: { stroke: '#60a5fa', strokeWidth: 1.5 }, label: '' },
  { id: 'e-exa-orch', source: 'src-exa', target: 'orch', type: 'smoothstep', animated: true, style: { stroke: '#60a5fa', strokeWidth: 1.5 } },
  { id: 'e-tavily-orch', source: 'src-tavily', target: 'orch', type: 'smoothstep', animated: true, style: { stroke: '#60a5fa', strokeWidth: 1.5 } },
  { id: 'e-sec-orch', source: 'src-sec', target: 'orch', type: 'smoothstep', animated: true, style: { stroke: '#60a5fa', strokeWidth: 1.5 } },
  { id: 'e-earnings-orch', source: 'src-earnings', target: 'orch', type: 'smoothstep', animated: true, style: { stroke: '#60a5fa', strokeWidth: 1.5 } },
  { id: 'e-stocknews-orch', source: 'src-stocknews', target: 'orch', type: 'smoothstep', animated: true, style: { stroke: '#60a5fa', strokeWidth: 1.5 } },
  { id: 'e-fmp-orch', source: 'src-fmp', target: 'orch', type: 'smoothstep', animated: true, style: { stroke: '#60a5fa', strokeWidth: 1.5 } },
  { id: 'e-freight-orch', source: 'src-freight', target: 'orch', type: 'smoothstep', animated: true, style: { stroke: '#60a5fa', strokeWidth: 1.5 } },
  { id: 'e-pr-orch', source: 'src-pr', target: 'orch', type: 'smoothstep', animated: true, style: { stroke: '#60a5fa', strokeWidth: 1.5 } },
  { id: 'e-pod-orch', source: 'src-podcasts', target: 'orch', type: 'smoothstep', animated: true, style: { stroke: '#60a5fa', strokeWidth: 1.5 } },

  // ── Orchestrator → Processing Pipeline (sequential chain) ──
  { id: 'e-orch-dedup', source: 'orch', target: 'proc-dedup', type: 'smoothstep', animated: true, label: 'normalized', style: { stroke: '#38bdf8', strokeWidth: 2 }, labelStyle: { fontSize: 10, fill: '#64748b' } },
  { id: 'e-dedup-scrape', source: 'proc-dedup', target: 'proc-scrape', type: 'smoothstep', animated: true, style: { stroke: '#f59e0b', strokeWidth: 1.5 } },
  { id: 'e-scrape-classify', source: 'proc-scrape', target: 'proc-classify', type: 'smoothstep', animated: true, style: { stroke: '#f59e0b', strokeWidth: 1.5 } },
  { id: 'e-classify-entity', source: 'proc-classify', target: 'proc-entity', type: 'smoothstep', animated: true, style: { stroke: '#f59e0b', strokeWidth: 1.5 } },
  { id: 'e-entity-image', source: 'proc-entity', target: 'proc-image', type: 'smoothstep', animated: true, style: { stroke: '#f59e0b', strokeWidth: 1.5 } },
  { id: 'e-image-embed', source: 'proc-image', target: 'proc-embed', type: 'smoothstep', animated: true, style: { stroke: '#f59e0b', strokeWidth: 1.5 } },

  // ── Processing → Storage (fan-out) ──
  { id: 'e-embed-articles', source: 'proc-embed', target: 'bq-articles', type: 'smoothstep', style: { stroke: '#8b5cf6', strokeWidth: 2 } },
  { id: 'e-embed-digest', source: 'proc-embed', target: 'bq-digest', type: 'smoothstep', style: { stroke: '#8b5cf6', strokeWidth: 2 } },
  { id: 'e-embed-tags', source: 'proc-embed', target: 'bq-tags', type: 'smoothstep', style: { stroke: '#8b5cf6', strokeWidth: 2 } },
  { id: 'e-embed-embeddings', source: 'proc-embed', target: 'bq-embeddings', type: 'smoothstep', style: { stroke: '#8b5cf6', strokeWidth: 2 } },
  { id: 'e-embed-images', source: 'proc-embed', target: 'bq-images', type: 'smoothstep', style: { stroke: '#8b5cf6', strokeWidth: 2 } },

  // ── Storage → Post-Processing ──
  { id: 'e-articles-digest', source: 'bq-articles', target: 'post-digest', type: 'smoothstep', style: { stroke: '#a78bfa', strokeWidth: 1.5, strokeDasharray: '5,5' } },
  { id: 'e-articles-nuggets', source: 'bq-articles', target: 'post-nuggets', type: 'smoothstep', label: 'SEC filings', style: { stroke: '#a78bfa', strokeWidth: 1.5, strokeDasharray: '5,5' }, labelStyle: { fontSize: 9, fill: '#94a3b8' } },
  { id: 'e-articles-quotes', source: 'bq-articles', target: 'post-quotes', type: 'smoothstep', label: 'earnings', style: { stroke: '#a78bfa', strokeWidth: 1.5, strokeDasharray: '5,5' }, labelStyle: { fontSize: 9, fill: '#94a3b8' } },
]
