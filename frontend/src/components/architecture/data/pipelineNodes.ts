import type { Node } from '@xyflow/react'
import type { ArchNodeData } from '../types'

// ============================================
// Section D: Pipeline Sales Prospecting Agent
// User query → mode select → 12 MCP tools → post-enrichment filtering → SearchBlock results
// ============================================

const COL_INPUT = 0
const COL_MODE = 200
const COL_EXA = 440
const COL_APOLLO = 440
const COL_BQ = 440
const COL_FILTER = 720
const COL_OUTPUT = 960

const ROW_GAP = 72
const ROW_START = 20

function row(index: number) { return ROW_START + index * ROW_GAP }

export const pipelineNodes: Node<ArchNodeData>[] = [
  // ── Input ──
  {
    id: 'pipe-input',
    type: 'dataSource',
    position: { x: COL_INPUT, y: row(3) },
    data: {
      label: 'User Query',
      nodeType: 'dataSource',
      icon: 'messageSquare',
      badge: 'Pipeline Tab',
      description: 'Natural-language sales prospecting query in the Pipeline tab chat. E.g. "Find composite manufacturers in Texas with >$50M revenue." Supports multi-turn conversation.',
      technicalDetails: {
        sourceFiles: ['agents/pipeline/agent.py'],
        functions: ['POST /api/pipeline/agent/chat'],
      },
      connections: {
        outgoing: ['Mode Selection'],
      },
      section: 'D',
    },
  },

  // ── Mode Selection ──
  {
    id: 'pipe-mode',
    type: 'fanOut',
    position: { x: COL_MODE, y: row(3) },
    data: {
      label: 'Mode Selection',
      nodeType: 'fanOut',
      icon: 'gitBranch',
      badge: '2 modes',
      description: 'Instant mode (default, 12 tools, ~350ms) for quick discovery. Full mode (13 tools, 1-5 min) adds build_company_webset for comprehensive list building — requires explicit user CONFIRM.',
      technicalDetails: {
        sourceFiles: ['agents/pipeline/agent.py'],
        functions: ['PipelineAgent.chat()'],
      },
      connections: {
        incoming: ['User Query'],
        outgoing: ['Exa: find_similar_companies', 'Exa: search_companies', 'Exa: find_trigger_events', 'Apollo: search_filtered', 'Apollo: enrich_company', 'Apollo: find_contacts', 'BigQuery: query_corpus'],
      },
      section: 'D',
    },
  },

  // ── Exa.ai Tools ──
  {
    id: 'pipe-exa-similar',
    type: 'agent',
    position: { x: COL_EXA, y: row(0) },
    data: {
      label: 'find_similar_companies',
      nodeType: 'agent',
      icon: 'search',
      badge: 'Exa.ai',
      description: 'Lookalike targeting — finds companies similar to a reference domain. Uses Exa neural embeddings for semantic company matching.',
      technicalDetails: {
        sourceFiles: ['mcp/tools/pipeline_search.py'],
        apis: ['Exa.ai find_similar'],
        cost: '~$0.01/query',
      },
      connections: {
        incoming: ['Mode Selection'],
        outgoing: ['Post-Enrichment Filter'],
      },
      section: 'D',
    },
  },
  {
    id: 'pipe-exa-search',
    type: 'agent',
    position: { x: COL_EXA, y: row(1) },
    data: {
      label: 'search_companies',
      nodeType: 'agent',
      icon: 'search',
      badge: 'Exa.ai',
      description: 'Natural-language company search with post-enrichment filters (min_revenue, states, min_employees, industries). Combines semantic search with structured filtering.',
      technicalDetails: {
        sourceFiles: ['mcp/tools/pipeline_search.py'],
        apis: ['Exa.ai search_and_contents'],
        cost: '~$0.01/query',
      },
      connections: {
        incoming: ['Mode Selection'],
        outgoing: ['Post-Enrichment Filter'],
      },
      section: 'D',
    },
  },
  {
    id: 'pipe-exa-triggers',
    type: 'agent',
    position: { x: COL_EXA, y: row(2) },
    data: {
      label: 'find_trigger_events',
      nodeType: 'agent',
      icon: 'zap',
      badge: 'Exa.ai',
      description: 'Finds expansion signals, funding rounds, contract wins, and facility openings. Key for identifying buying intent.',
      technicalDetails: {
        sourceFiles: ['mcp/tools/pipeline_search.py'],
        apis: ['Exa.ai search_and_contents'],
        cost: '~$0.01/query',
      },
      connections: {
        incoming: ['Mode Selection'],
        outgoing: ['Post-Enrichment Filter'],
      },
      section: 'D',
    },
  },

  // ── Apollo.io Tools ──
  {
    id: 'pipe-apollo-search',
    type: 'agent',
    position: { x: COL_APOLLO, y: row(4) },
    data: {
      label: 'search_companies_filtered',
      nodeType: 'agent',
      icon: 'building',
      badge: 'Apollo.io',
      description: 'Structured company search with firmographic filters: location, employee count, revenue range, industry codes. Free tier — no credits consumed.',
      technicalDetails: {
        sourceFiles: ['mcp/tools/pipeline_search.py'],
        apis: ['Apollo.io organizations/search'],
        cost: 'Free',
      },
      connections: {
        incoming: ['Mode Selection'],
        outgoing: ['Post-Enrichment Filter'],
      },
      section: 'D',
    },
  },
  {
    id: 'pipe-apollo-enrich',
    type: 'agent',
    position: { x: COL_APOLLO, y: row(5) },
    data: {
      label: 'enrich_company',
      nodeType: 'agent',
      icon: 'sparkles',
      badge: 'Apollo.io',
      description: 'Deep company enrichment by domain — returns employee count, revenue, industry, technology stack, social links, and more. Free tier.',
      technicalDetails: {
        sourceFiles: ['mcp/tools/pipeline_search.py'],
        apis: ['Apollo.io organizations/enrich'],
        cost: 'Free',
      },
      connections: {
        incoming: ['Mode Selection'],
        outgoing: ['Post-Enrichment Filter'],
      },
      section: 'D',
    },
  },
  {
    id: 'pipe-apollo-contacts',
    type: 'agent',
    position: { x: COL_APOLLO, y: row(6) },
    data: {
      label: 'find_company_contacts',
      nodeType: 'agent',
      icon: 'users',
      badge: 'Apollo.io',
      description: 'Contact search with auto-reveal — finds decision-makers by title, seniority, department. Returns emails and phone numbers. Consumes Apollo credits.',
      technicalDetails: {
        sourceFiles: ['mcp/tools/pipeline_search.py'],
        apis: ['Apollo.io people/search + reveal'],
        cost: '1 credit/contact',
      },
      connections: {
        incoming: ['Mode Selection'],
        outgoing: ['SearchBlock Results'],
      },
      section: 'D',
    },
  },

  // ── BigQuery Corpus Tools ──
  {
    id: 'pipe-bq-corpus',
    type: 'storage',
    position: { x: COL_BQ, y: row(7.5) },
    data: {
      label: 'query_corpus',
      nodeType: 'storage',
      icon: 'database',
      badge: 'BigQuery',
      description: 'Semantic search across article_chunk_embeddings for company intelligence, market trends, and competitor activity. Chat-only insights — no SearchBlocks.',
      technicalDetails: {
        sourceFiles: ['mcp/tools/corpus_query.py'],
        functions: ['query_corpus()'],
        tables: ['article_chunk_embeddings'],
        dataVolume: '15K+ chunks',
      },
      connections: {
        incoming: ['Mode Selection'],
        outgoing: ['SearchBlock Results'],
      },
      section: 'D',
    },
  },

  // ── Post-Enrichment Filter ──
  {
    id: 'pipe-filter',
    type: 'processing',
    position: { x: COL_FILTER, y: row(2.5) },
    data: {
      label: 'Post-Enrichment Filter',
      nodeType: 'processing',
      icon: 'filter',
      badge: 'Smart Filter',
      description: 'CompanyFilters applied AFTER Exa semantic search + Apollo enrichment. Filters by min/max revenue, employee count, states, countries, industries. Returns FilterResult with rejection_reasons, near_misses, and expansion_suggestions.',
      technicalDetails: {
        sourceFiles: ['agents/pipeline/filters.py'],
        functions: ['apply_filters()', 'CompanyFilters'],
      },
      connections: {
        incoming: ['find_similar_companies', 'search_companies', 'find_trigger_events', 'search_companies_filtered', 'enrich_company'],
        outgoing: ['SearchBlock Results'],
      },
      section: 'D',
    },
  },

  // ── Output ──
  {
    id: 'pipe-output',
    type: 'processing',
    position: { x: COL_OUTPUT, y: row(3.5) },
    data: {
      label: 'SearchBlock Results',
      nodeType: 'processing',
      icon: 'layoutGrid',
      badge: '7 block types',
      description: 'PipelineAgentResponse with typed SearchBlocks: similar_companies, search_companies, contacts, trigger_events, webset_building, apollo_enrichment, apollo_contacts. Rendered in right-side results panel with company logos (Logo.dev).',
      technicalDetails: {
        sourceFiles: ['agents/pipeline/state.py'],
        functions: ['PipelineAgentResponse', 'SearchBlock'],
      },
      connections: {
        incoming: ['Post-Enrichment Filter', 'find_company_contacts', 'query_corpus'],
      },
      section: 'D',
    },
  },
]
