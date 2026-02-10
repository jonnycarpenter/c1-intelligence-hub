import type { Node } from '@xyflow/react'
import type { ArchNodeData } from '../types'

// ============================================
// Section D: ImportYeti Supply Chain Network
// ============================================

const COL_CONFIG = 0
const COL_PHASES = 260
const COL_CLIENT = 260
const COL_STORE = 590
const COL_VIEWS = 900

const ROW_GAP = 80
const ROW_START = 20

function row(index: number) { return ROW_START + index * ROW_GAP }

export const importYetiNodes: Node<ArchNodeData>[] = [
  // ── Column 1: Config ──
  {
    id: 'iy-config',
    type: 'dataSource',
    position: { x: COL_CONFIG, y: row(1.5) },
    data: {
      label: 'Competitor Config',
      nodeType: 'dataSource',
      icon: 'settings',
      badge: 'competitors.json',
      description: 'competitors.json defines the tracked entity set (C1 Composites One + competitors). Each entry has name, aliases, and optional ImportYeti slug.',
      technicalDetails: {
        sourceFiles: ['ingestion/importyeti/competitors.json'],
      },
      connections: {
        outgoing: ['Phase 1: RESOLVE'],
      },
      section: 'D',
    },
  },

  // ── Column 2: Pipeline Phases (stacked vertically) ──
  {
    id: 'iy-phase1',
    type: 'processing',
    position: { x: COL_PHASES, y: row(0) },
    data: {
      label: 'Phase 1: RESOLVE',
      nodeType: 'processing',
      icon: 'search',
      description: 'Search ImportYeti for each entity name, find best match by totalShipments, store resolved company in BigQuery iy_companies table.',
      technicalDetails: {
        sourceFiles: ['ingestion/importyeti/ingestion.py'],
        functions: ['_run_resolve_phase()'],
      },
      connections: {
        incoming: ['Competitor Config', 'ImportYeti API Client'],
        outgoing: ['Phase 2: COMPANIES'],
      },
      section: 'D',
    },
  },
  {
    id: 'iy-phase2',
    type: 'processing',
    position: { x: COL_PHASES, y: row(1) },
    data: {
      label: 'Phase 2: COMPANIES',
      nodeType: 'processing',
      icon: 'workflow',
      description: 'Pull full company profiles from ImportYeti. Extract suppliers_table (overseas manufacturers). Batch-insert suppliers into iy_suppliers + create imports_from edges in iy_edges.',
      technicalDetails: {
        sourceFiles: ['ingestion/importyeti/ingestion.py'],
        functions: ['_run_companies_phase()'],
        tables: ['iy_companies', 'iy_suppliers', 'iy_edges'],
      },
      connections: {
        incoming: ['Phase 1: RESOLVE', 'ImportYeti API Client'],
        outgoing: ['Phase 3: SUPPLIERS', 'iy_companies', 'iy_suppliers', 'iy_edges'],
      },
      section: 'D',
    },
  },
  {
    id: 'iy-phase3',
    type: 'processing',
    position: { x: COL_PHASES, y: row(2) },
    data: {
      label: 'Phase 3: SUPPLIERS',
      nodeType: 'processing',
      icon: 'workflow',
      description: 'Pull full supplier profiles. Extract companies_table (downstream US buyers). Batch-insert discovered buyers + create supplies_to edges. Discovers competitors\' customer networks.',
      technicalDetails: {
        sourceFiles: ['ingestion/importyeti/ingestion.py'],
        functions: ['_run_suppliers_phase()'],
        tables: ['iy_suppliers', 'iy_edges'],
      },
      connections: {
        incoming: ['Phase 2: COMPANIES', 'ImportYeti API Client'],
        outgoing: ['Phase 4: STATS', 'iy_suppliers', 'iy_edges'],
      },
      section: 'D',
    },
  },
  {
    id: 'iy-phase4',
    type: 'processing',
    position: { x: COL_PHASES, y: row(3) },
    data: {
      label: 'Phase 4: STATS',
      nodeType: 'processing',
      icon: 'classify',
      description: 'Summary report: companies resolved, suppliers discovered, edges created, total shipments mapped. Final audit and logging.',
      technicalDetails: {
        sourceFiles: ['ingestion/importyeti/ingestion.py'],
        functions: ['_run_stats_phase()'],
        tables: ['iy_ingestion_log'],
      },
      connections: {
        incoming: ['Phase 3: SUPPLIERS'],
      },
      section: 'D',
    },
  },

  // ── API Client (positioned to the left of phases) ──
  {
    id: 'iy-client',
    type: 'dataSource',
    position: { x: COL_CONFIG, y: row(3) },
    data: {
      label: 'ImportYeti API Client',
      nodeType: 'externalApi',
      icon: 'api',
      badge: 'Rate limited',
      description: 'search_company(), get_company(), search_supplier(), get_supplier(). Retry logic, rate limiting, credit tracking.',
      technicalDetails: {
        sourceFiles: ['ingestion/importyeti/client.py'],
        functions: ['search_company()', 'get_company()', 'search_supplier()', 'get_supplier()'],
        apis: ['ImportYeti API'],
      },
      connections: {
        outgoing: ['Phase 1', 'Phase 2', 'Phase 3'],
      },
      section: 'D',
    },
  },

  // ── Column 3: BigQuery Storage ──
  {
    id: 'bq-iy-companies',
    type: 'storage',
    position: { x: COL_STORE, y: row(0) },
    data: {
      label: 'iy_companies',
      nodeType: 'storage',
      icon: 'database',
      description: 'US importers: name, slug, total_shipments, address, resolved_at. One row per resolved company from Phase 1-2.',
      technicalDetails: {
        tables: ['iy_companies'],
      },
      connections: {
        incoming: ['Phase 2: COMPANIES'],
      },
      section: 'D',
    },
  },
  {
    id: 'bq-iy-suppliers',
    type: 'storage',
    position: { x: COL_STORE, y: row(1) },
    data: {
      label: 'iy_suppliers',
      nodeType: 'storage',
      icon: 'database',
      description: 'Overseas exporters/manufacturers: name, country, shipment counts. Discovered during Phase 2 (company profiles) and Phase 3 (supplier profiles).',
      technicalDetails: {
        tables: ['iy_suppliers'],
      },
      connections: {
        incoming: ['Phase 2: COMPANIES', 'Phase 3: SUPPLIERS'],
      },
      section: 'D',
    },
  },
  {
    id: 'bq-iy-edges',
    type: 'storage',
    position: { x: COL_STORE, y: row(2) },
    data: {
      label: 'iy_edges',
      nodeType: 'storage',
      icon: 'database',
      description: 'Directional relationships: source → target, edge_type (imports_from / supplies_to), shipment_count, period. Core of the supply chain graph.',
      technicalDetails: {
        tables: ['iy_edges'],
      },
      connections: {
        incoming: ['Phase 2: COMPANIES', 'Phase 3: SUPPLIERS'],
        outgoing: ['Analytical Views'],
      },
      section: 'D',
    },
  },
  {
    id: 'bq-iy-log',
    type: 'storage',
    position: { x: COL_STORE, y: row(3) },
    data: {
      label: 'iy_ingestion_log',
      nodeType: 'storage',
      icon: 'database',
      description: 'Audit trail per pipeline run. Records: phase, entities processed, errors, timing, credits consumed.',
      technicalDetails: {
        tables: ['iy_ingestion_log'],
      },
      connections: {
        incoming: ['Phase 4: STATS'],
      },
      section: 'D',
    },
  },

  // ── Column 4: Analytical Views ──
  {
    id: 'iy-views',
    type: 'processing',
    position: { x: COL_VIEWS, y: row(0.5) },
    data: {
      label: 'Analytical Views (5)',
      nodeType: 'processing',
      icon: 'classify',
      badge: 'BigQuery Views',
      description: 'Pre-computed BigQuery views: iy_v_shared_suppliers (suppliers serving 2+ competitors), iy_v_shared_suppliers_12m (12-month active), iy_v_exclusive_suppliers (single-competitor suppliers), iy_v_competitor_activity_12m (per-company summary), iy_v_buyer_overlap (buyers in 2+ networks).',
      technicalDetails: {
        tables: ['iy_v_shared_suppliers', 'iy_v_shared_suppliers_12m', 'iy_v_exclusive_suppliers', 'iy_v_competitor_activity_12m', 'iy_v_buyer_overlap'],
        sourceFiles: ['db/gcp_storage.py'],
      },
      connections: {
        incoming: ['iy_edges'],
        outgoing: ['Supply Network Tab'],
      },
      section: 'D',
    },
  },
  {
    id: 'iy-frontend',
    type: 'processing',
    position: { x: COL_VIEWS, y: row(2) },
    data: {
      label: 'Supply Network Tab',
      nodeType: 'processing',
      icon: 'workflow',
      description: 'Interactive force-directed graph visualization of supply chain relationships. Shared supplier detection, competitor overlap analysis. Dynamic import for heavy component.',
      technicalDetails: {
        sourceFiles: ['components/supply/SupplyNetworkDashboard.tsx'],
        apis: ['GET /api/supply-network/graph'],
      },
      connections: {
        incoming: ['Analytical Views'],
      },
      section: 'D',
    },
  },
]
