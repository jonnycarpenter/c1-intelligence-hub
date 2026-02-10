import type { Edge } from '@xyflow/react'

// ============================================
// Section D: ImportYeti Supply Chain Network — Edges
// ============================================

export const importYetiEdges: Edge[] = [
  // ── Config → Phase 1 ──
  {
    id: 'e-iy-config-p1',
    source: 'iy-config',
    target: 'iy-phase1',
    type: 'smoothstep',
    animated: true,
    label: 'entity list',
    style: { stroke: '#60a5fa', strokeWidth: 1.5 },
    labelStyle: { fontSize: 10, fill: '#64748b' },
  },

  // ── Phase chain: 1 → 2 → 3 → 4 ──
  {
    id: 'e-iy-p1-p2',
    source: 'iy-phase1',
    target: 'iy-phase2',
    type: 'smoothstep',
    animated: true,
    style: { stroke: '#f59e0b', strokeWidth: 2 },
    label: 'resolved',
    labelStyle: { fontSize: 10, fill: '#64748b' },
  },
  {
    id: 'e-iy-p2-p3',
    source: 'iy-phase2',
    target: 'iy-phase3',
    type: 'smoothstep',
    animated: true,
    style: { stroke: '#f59e0b', strokeWidth: 2 },
    label: 'suppliers',
    labelStyle: { fontSize: 10, fill: '#64748b' },
  },
  {
    id: 'e-iy-p3-p4',
    source: 'iy-phase3',
    target: 'iy-phase4',
    type: 'smoothstep',
    animated: true,
    style: { stroke: '#f59e0b', strokeWidth: 2 },
  },

  // ── Client ↔ Phases (bidirectional, API calls) ──
  {
    id: 'e-iy-client-p1',
    source: 'iy-client',
    target: 'iy-phase1',
    type: 'smoothstep',
    style: { stroke: '#94a3b8', strokeWidth: 1, strokeDasharray: '4,4' },
    label: 'API',
    labelStyle: { fontSize: 9, fill: '#94a3b8' },
  },
  {
    id: 'e-iy-client-p2',
    source: 'iy-client',
    target: 'iy-phase2',
    type: 'smoothstep',
    style: { stroke: '#94a3b8', strokeWidth: 1, strokeDasharray: '4,4' },
  },
  {
    id: 'e-iy-client-p3',
    source: 'iy-client',
    target: 'iy-phase3',
    type: 'smoothstep',
    style: { stroke: '#94a3b8', strokeWidth: 1, strokeDasharray: '4,4' },
  },

  // ── Phases → Storage ──
  {
    id: 'e-iy-p2-companies',
    source: 'iy-phase2',
    target: 'bq-iy-companies',
    type: 'smoothstep',
    style: { stroke: '#8b5cf6', strokeWidth: 2 },
  },
  {
    id: 'e-iy-p2-suppliers',
    source: 'iy-phase2',
    target: 'bq-iy-suppliers',
    type: 'smoothstep',
    style: { stroke: '#8b5cf6', strokeWidth: 2 },
  },
  {
    id: 'e-iy-p2-edges',
    source: 'iy-phase2',
    target: 'bq-iy-edges',
    type: 'smoothstep',
    style: { stroke: '#8b5cf6', strokeWidth: 2 },
    label: 'imports_from',
    labelStyle: { fontSize: 9, fill: '#94a3b8' },
  },
  {
    id: 'e-iy-p3-suppliers',
    source: 'iy-phase3',
    target: 'bq-iy-suppliers',
    type: 'smoothstep',
    style: { stroke: '#8b5cf6', strokeWidth: 1.5 },
  },
  {
    id: 'e-iy-p3-edges',
    source: 'iy-phase3',
    target: 'bq-iy-edges',
    type: 'smoothstep',
    style: { stroke: '#8b5cf6', strokeWidth: 1.5 },
    label: 'supplies_to',
    labelStyle: { fontSize: 9, fill: '#94a3b8' },
  },
  {
    id: 'e-iy-p4-log',
    source: 'iy-phase4',
    target: 'bq-iy-log',
    type: 'smoothstep',
    style: { stroke: '#8b5cf6', strokeWidth: 1.5 },
  },

  // ── Storage → Views → Frontend ──
  {
    id: 'e-iy-edges-views',
    source: 'bq-iy-edges',
    target: 'iy-views',
    type: 'smoothstep',
    style: { stroke: '#a78bfa', strokeWidth: 1.5, strokeDasharray: '5,5' },
    label: 'materialized',
    labelStyle: { fontSize: 9, fill: '#94a3b8' },
  },
  {
    id: 'e-iy-views-frontend',
    source: 'iy-views',
    target: 'iy-frontend',
    type: 'smoothstep',
    style: { stroke: '#10b981', strokeWidth: 1.5, strokeDasharray: '5,5' },
    label: 'Supply Network Tab',
    labelStyle: { fontSize: 9, fill: '#64748b' },
  },
]
