import type { Node } from '@xyflow/react'
import type { ArchNodeData } from '../types'

// ============================================
// Section C: Ad-Hoc Briefing Agent
// User question → route by subtab → multi-source search → Claude Opus streaming synthesis
// ============================================

const COL_TRIGGER = 0
const COL_SESSION = 240
const COL_ROUTE = 440
const COL_SEARCH = 680
const COL_SYNTH = 960
const COL_OUTPUT = 1200

const ROW_GAP = 80
const ROW_START = 30

function row(index: number) { return ROW_START + index * ROW_GAP }

export const adhocBriefingNodes: Node<ArchNodeData>[] = [
  // ── Trigger ──
  {
    id: 'adhoc-trigger',
    type: 'dataSource',
    position: { x: COL_TRIGGER, y: row(2) },
    data: {
      label: 'User Question',
      nodeType: 'dataSource',
      icon: 'messageSquare',
      badge: 'Pulse Tab',
      description: 'User types a natural-language question in the Pulse tab chat interface. Supports follow-up questions (max 2 per session) with full conversation memory.',
      technicalDetails: {
        sourceFiles: ['agents/adhoc_briefing/agent.py'],
        functions: ['POST /api/briefings/adhoc/stream'],
        apis: ['SSE streaming endpoint'],
      },
      connections: {
        outgoing: ['Session Manager'],
      },
      section: 'C',
    },
  },

  // ── Session Manager ──
  {
    id: 'adhoc-session',
    type: 'orchestrator',
    position: { x: COL_SESSION, y: row(2) },
    data: {
      label: 'Session Manager',
      nodeType: 'processing',
      icon: 'database',
      badge: 'LRU Cache',
      description: 'BriefingSessionManager singleton — in-memory LRU cache with 30-min TTL, max 1,000 concurrent sessions. Tracks conversation history, follow-up count, and user context.',
      technicalDetails: {
        sourceFiles: ['agents/adhoc_briefing/session_manager.py'],
        functions: ['BriefingSessionManager.get_or_create_session()'],
      },
      connections: {
        incoming: ['User Question'],
        outgoing: ['Subtab Router'],
      },
      section: 'C',
    },
  },

  // ── Subtab Router ──
  {
    id: 'adhoc-router',
    type: 'fanOut',
    position: { x: COL_ROUTE, y: row(2) },
    data: {
      label: 'Subtab Router',
      nodeType: 'fanOut',
      icon: 'gitBranch',
      badge: '3 routes',
      description: 'Routes query based on active Pulse subtab: Article Feed → corpus + Exa + StockNews, Financial Feed → earnings + SEC nuggets, Expert Feed → podcast quotes.',
      technicalDetails: {
        sourceFiles: ['agents/adhoc_briefing/agent.py'],
        functions: ['_route_by_subtab()'],
      },
      connections: {
        incoming: ['Session Manager'],
        outgoing: ['Corpus Search', 'Exa Search', 'StockNews Search', 'Earnings Search', 'SEC Search', 'Podcast Search'],
      },
      section: 'C',
    },
  },

  // ── Search Tools (Article Feed route) ──
  {
    id: 'adhoc-corpus',
    type: 'storage',
    position: { x: COL_SEARCH, y: row(0) },
    data: {
      label: 'Corpus Search',
      nodeType: 'storage',
      icon: 'database',
      badge: 'BigQuery',
      description: 'Semantic search across article_chunk_embeddings table — 768-dim vector similarity against 15K+ chunks. Returns top-k relevant article excerpts with source URLs.',
      technicalDetails: {
        sourceFiles: ['mcp/tools/corpus_query.py'],
        functions: ['search_articles()'],
        tables: ['article_chunk_embeddings'],
        dataVolume: '15K+ chunks, 768-dim',
      },
      connections: {
        incoming: ['Subtab Router'],
        outgoing: ['Claude Opus Synthesis'],
      },
      section: 'C',
    },
  },
  {
    id: 'adhoc-exa',
    type: 'processing',
    position: { x: COL_SEARCH, y: row(1) },
    data: {
      label: 'Exa News Search',
      nodeType: 'processing',
      icon: 'search',
      badge: 'External',
      description: 'Exa.ai neural search for real-time news. Finds relevant articles published in the last 7 days not yet in the corpus.',
      technicalDetails: {
        sourceFiles: ['mcp/tools/exa_search.py'],
        functions: ['search_external_news()'],
        apis: ['Exa.ai search_and_contents'],
        cost: '~$0.01/query',
      },
      connections: {
        incoming: ['Subtab Router'],
        outgoing: ['Claude Opus Synthesis'],
      },
      section: 'C',
    },
  },
  {
    id: 'adhoc-stocknews',
    type: 'processing',
    position: { x: COL_SEARCH, y: row(2) },
    data: {
      label: 'StockNews Search',
      nodeType: 'processing',
      icon: 'trendingUp',
      badge: 'External',
      description: 'StockNewsAPI keyword search for market-moving headlines and analyst coverage of tracked companies.',
      technicalDetails: {
        sourceFiles: ['mcp/tools/stocknews_api.py'],
        functions: ['search_external_news()'],
        apis: ['StockNews API'],
        cost: 'Free tier',
      },
      connections: {
        incoming: ['Subtab Router'],
        outgoing: ['Claude Opus Synthesis'],
      },
      section: 'C',
    },
  },

  // ── Search Tools (Financial Feed route) ──
  {
    id: 'adhoc-earnings',
    type: 'processing',
    position: { x: COL_SEARCH, y: row(3) },
    data: {
      label: 'Earnings Search',
      nodeType: 'processing',
      icon: 'dollarSign',
      badge: 'BigQuery',
      description: 'Searches earnings_quotes table for executive quotes from quarterly earnings calls. Filters by company, topic, and recency.',
      technicalDetails: {
        sourceFiles: ['mcp/tools/earnings_quotes.py'],
        functions: ['search_financial_data()'],
        tables: ['earnings_quotes'],
        dataVolume: '2,000+ exec quotes',
      },
      connections: {
        incoming: ['Subtab Router'],
        outgoing: ['Claude Opus Synthesis'],
      },
      section: 'C',
    },
  },
  {
    id: 'adhoc-sec',
    type: 'processing',
    position: { x: COL_SEARCH, y: row(4) },
    data: {
      label: 'SEC Nuggets Search',
      nodeType: 'processing',
      icon: 'fileText',
      badge: 'BigQuery',
      description: 'Searches sec_filing_nuggets table for strategic nuggets extracted from 10-K, 10-Q, and 8-K SEC filings.',
      technicalDetails: {
        sourceFiles: ['mcp/tools/sec_nuggets.py'],
        functions: ['search_financial_data()'],
        tables: ['sec_filing_nuggets'],
        dataVolume: '3,000+ nuggets',
      },
      connections: {
        incoming: ['Subtab Router'],
        outgoing: ['Claude Opus Synthesis'],
      },
      section: 'C',
    },
  },

  // ── Search Tools (Expert Feed route) ──
  {
    id: 'adhoc-podcast',
    type: 'processing',
    position: { x: COL_SEARCH, y: row(5) },
    data: {
      label: 'Podcast Search',
      nodeType: 'processing',
      icon: 'mic',
      badge: 'BigQuery',
      description: 'Searches podcast_quotes table for speaker-attributed quotes from industry expert podcast episodes.',
      technicalDetails: {
        sourceFiles: ['mcp/tools/podcast_quotes.py'],
        functions: ['search_expert_data()'],
        tables: ['podcast_quotes'],
        dataVolume: 'Speaker-attributed quotes',
      },
      connections: {
        incoming: ['Subtab Router'],
        outgoing: ['Claude Opus Synthesis'],
      },
      section: 'C',
    },
  },

  // ── Claude Opus Synthesis ──
  {
    id: 'adhoc-synth',
    type: 'agent',
    position: { x: COL_SYNTH, y: row(2) },
    data: {
      label: 'Claude Opus Synthesis',
      nodeType: 'agent',
      icon: 'brain',
      badge: 'Opus 4.5',
      description: 'Anthropic Claude Opus 4.5 streaming synthesis. Builds context from memory + data sources, then streams markdown response with ## sections, bold highlights, and [Source](url) citations. Max 3,000 tokens, temperature 0.',
      technicalDetails: {
        sourceFiles: ['agents/adhoc_briefing/agent.py'],
        functions: ['StreamingAdHocBriefingAgent._stream_synthesis()'],
        model: 'claude-opus-4-5',
        apis: ['Anthropic AsyncAnthropic streaming'],
        cost: '~$0.15–0.40/query (Opus 4.5)',
      },
      connections: {
        incoming: ['Corpus Search', 'Exa News Search', 'StockNews Search', 'Earnings Search', 'SEC Nuggets Search', 'Podcast Search'],
        outgoing: ['SSE Response Stream'],
      },
      section: 'C',
    },
  },

  // ── Output ──
  {
    id: 'adhoc-output',
    type: 'storage',
    position: { x: COL_OUTPUT, y: row(1.5) },
    data: {
      label: 'SSE Response Stream',
      nodeType: 'storage',
      icon: 'radio',
      badge: 'Streaming',
      description: 'Server-Sent Events stream: progress → content (token chunks) → session_info → complete. Frontend renders markdown in real-time with typing effect.',
      technicalDetails: {
        sourceFiles: ['api/routes/briefing.py'],
        functions: ['stream_adhoc_briefing()'],
        apis: ['EventSourceResponse'],
      },
      connections: {
        incoming: ['Claude Opus Synthesis'],
        outgoing: ['BigQuery Storage'],
      },
      section: 'C',
    },
  },
  {
    id: 'adhoc-bq',
    type: 'storage',
    position: { x: COL_OUTPUT, y: row(3) },
    data: {
      label: 'BigQuery Storage',
      nodeType: 'storage',
      icon: 'database',
      badge: 'adhoc_briefings',
      description: 'Completed briefings saved to adhoc_briefings table with question, answer, sources_used, confidence score, and session metadata.',
      technicalDetails: {
        tables: ['adhoc_briefings'],
        dataVolume: 'All ad-hoc briefings archived',
      },
      connections: {
        incoming: ['SSE Response Stream'],
      },
      section: 'C',
    },
  },
]
