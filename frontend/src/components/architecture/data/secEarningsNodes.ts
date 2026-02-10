import type { Node } from '@xyflow/react'
import type { ArchNodeData } from '../types'

// ============================================
// Section B: SEC Filings & Earnings Transcripts
// ============================================

const COL_COLLECT = 0
const COL_EXTRACT = 320
const COL_STORE = 640
const COL_DOWNSTREAM = 960

const ROW_GAP = 90
const ROW_START = 20

function row(index: number) { return ROW_START + index * ROW_GAP }

export const secEarningsNodes: Node<ArchNodeData>[] = [
  // ── Column 1: Ingestion / Collection ──
  {
    id: 'sec-collect',
    type: 'dataSource',
    position: { x: COL_COLLECT, y: row(0) },
    data: {
      label: 'SEC Filing Collector',
      nodeType: 'dataSource',
      icon: 'filing',
      badge: '10-K, 10-Q, 8-K',
      description: 'Queries sec-api.io for 10-K, 10-Q, 8-K filings. Section extraction: business (§1), risk_factors (§1A), MD&A (§7), market_risk (§7A). Targets ~35 public companies.',
      technicalDetails: {
        sourceFiles: ['tools/sec_filings/collector.py', 'tools/sec_filings/sec_client.py'],
        functions: ['collect_sec_filings()', 'search_filings()', 'get_filing_sections()'],
        apis: ['sec-api.io'],
      },
      connections: {
        outgoing: ['SEC Nugget Extractor'],
      },
      section: 'B',
    },
  },
  {
    id: 'earn-collect',
    type: 'dataSource',
    position: { x: COL_COLLECT, y: row(1.5) },
    data: {
      label: 'Earnings Collector',
      nodeType: 'dataSource',
      icon: 'earnings',
      badge: 'Speaker attribution',
      description: 'API Ninjas-based. Iterates year/quarter combos per company. Parses participants list, transcript sections with speaker attribution (CEO, CFO, analyst).',
      technicalDetails: {
        sourceFiles: ['tools/earnings/collector.py'],
        functions: ['collect_earnings_transcripts()', '_parse_transcript()'],
        apis: ['API Ninjas Earnings'],
      },
      connections: {
        outgoing: ['Earnings Quote Extractor'],
      },
      section: 'B',
    },
  },

  // ── Column 2: AI Extraction ──
  {
    id: 'sec-extract',
    type: 'agent',
    position: { x: COL_EXTRACT, y: row(0) },
    data: {
      label: 'SEC Nugget Extractor',
      nodeType: 'agent',
      icon: 'brain',
      badge: 'Claude Sonnet',
      description: 'Claude Sonnet 4.5. Extracts 15-30 nuggets per filing. Nugget types: competitive_disclosure, risk_admission, forward_guidance, regulatory_exposure, material_change, market_condition. Themes tied to business segments. Cost: ~$0.20-0.60/filing.',
      technicalDetails: {
        sourceFiles: ['ingestion/sec_filings/nugget_extractor.py'],
        model: 'claude-sonnet-4-5',
        functions: ['extract_nuggets()', '_build_extraction_prompt()'],
        lineCount: 487,
      },
      connections: {
        incoming: ['SEC Filing Collector'],
        outgoing: ['sec_filings table', 'sec_filing_nuggets table'],
      },
      section: 'B',
    },
  },
  {
    id: 'earn-extract',
    type: 'agent',
    position: { x: COL_EXTRACT, y: row(1.5) },
    data: {
      label: 'Earnings Quote Extractor',
      nodeType: 'agent',
      icon: 'brain',
      badge: 'Claude Haiku',
      description: 'Claude Haiku 3.5 (cost-optimized). Extracts 8-15 quotes per transcript. Categories: competitive_intelligence, production_rates, raw_materials, pricing, strategic_initiatives, analyst_pressure_points. Composites/aerospace/wind/marine/automotive focus. Cost: ~$0.02-0.05/transcript.',
      technicalDetails: {
        sourceFiles: ['ingestion/earnings/quote_extractor.py'],
        model: 'claude-haiku-3-5',
        functions: ['extract_quotes()', '_build_quote_prompt()'],
        lineCount: 484,
      },
      connections: {
        incoming: ['Earnings Collector'],
        outgoing: ['earnings_quotes table'],
      },
      section: 'B',
    },
  },

  // ── Column 3: Storage ──
  {
    id: 'bq-sec-filings',
    type: 'storage',
    position: { x: COL_STORE, y: row(0) - 30 },
    data: {
      label: 'sec_filings',
      nodeType: 'storage',
      icon: 'database',
      description: 'Filing metadata: company, filing_type, date, CIK, extracted sections. One row per filing with full section text for downstream extraction.',
      technicalDetails: {
        tables: ['sec_filings'],
      },
      connections: {
        incoming: ['SEC Nugget Extractor'],
      },
      section: 'B',
    },
  },
  {
    id: 'bq-sec-nuggets',
    type: 'storage',
    position: { x: COL_STORE, y: row(0.5) + 10 },
    data: {
      label: 'sec_filing_nuggets',
      nodeType: 'storage',
      icon: 'database',
      badge: 'MCP tool',
      description: 'Extracted nuggets: nugget_type, signal_strength, theme, disclosure_text, company_context. Queried by search_sec_nuggets MCP tool during Deep Research and weekly briefing voice enrichment.',
      technicalDetails: {
        tables: ['sec_filing_nuggets'],
        functions: ['search_sec_nuggets()'],
      },
      connections: {
        incoming: ['SEC Nugget Extractor'],
        outgoing: ['Financial Research agent', 'Weekly Briefing voice enrichment'],
      },
      section: 'B',
    },
  },
  {
    id: 'bq-earn-quotes',
    type: 'storage',
    position: { x: COL_STORE, y: row(1.5) },
    data: {
      label: 'earnings_quotes',
      nodeType: 'storage',
      icon: 'database',
      badge: 'MCP tool',
      description: 'Executive quotes: speaker, speaker_role, quote_type, theme, strategic_relevance, verbatim_text. Queried by search_earnings_quotes MCP tool.',
      technicalDetails: {
        tables: ['earnings_quotes'],
        functions: ['search_earnings_quotes()'],
      },
      connections: {
        incoming: ['Earnings Quote Extractor'],
        outgoing: ['Financial Research agent', 'Weekly Briefing voice enrichment'],
      },
      section: 'B',
    },
  },

  // ── Column 4: Downstream ──
  {
    id: 'downstream-briefing',
    type: 'processing',
    position: { x: COL_DOWNSTREAM, y: row(0.3) },
    data: {
      label: 'Voice Enrichment → Briefings',
      nodeType: 'processing',
      icon: 'workflow',
      description: 'SEC nuggets + earnings quotes are pre-fetched as "voice enrichment" data injected into the weekly briefing Agent 2 prompt. This gives the executive synthesizer direct executive quotes and disclosure context to reference.',
      technicalDetails: {
        sourceFiles: ['ingestion/generators/weekly_briefing.py'],
        functions: ['_get_voice_enrichment()'],
      },
      connections: {
        incoming: ['sec_filing_nuggets', 'earnings_quotes'],
        outgoing: ['Weekly Briefing Agent 2'],
      },
      section: 'B',
    },
  },
  {
    id: 'downstream-research',
    type: 'processing',
    position: { x: COL_DOWNSTREAM, y: row(1.5) },
    data: {
      label: '→ Deep Research Agents',
      nodeType: 'processing',
      icon: 'workflow',
      description: 'Financial Research agent calls search_earnings_quotes and search_sec_nuggets tools to find company-specific intelligence during Deep Research workflows.',
      technicalDetails: {
        sourceFiles: ['agents/research/financial.py'],
        functions: ['search_earnings_quotes()', 'search_sec_nuggets()'],
      },
      connections: {
        incoming: ['sec_filing_nuggets', 'earnings_quotes'],
        outgoing: ['Deep Research Financial Agent'],
      },
      section: 'B',
    },
  },
]
