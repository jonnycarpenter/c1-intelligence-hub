import type { Node } from '@xyflow/react'
import type { ArchNodeData } from '../types'
import {
  BATCH_ANALYSIS_PROMPT,
  MERGE_PROMPT,
  EXECUTIVE_SYNTHESIZER_PROMPT,
  GROOMER_SYSTEM_PROMPT,
  FINANCIAL_AGENT_SYSTEM_PROMPT,
  INDUSTRY_AGENT_SYSTEM_PROMPT,
  VISUAL_AGENT_SYSTEM_PROMPT,
  SYNTHESIZER_SYSTEM_PROMPT,
  VALIDATOR_SYSTEM_PROMPT,
} from './agentPrompts'

// ============================================
// Section A: Weekly Executive Briefing Pipeline
// ============================================

const A_COL_TRIGGER = 0
const A_COL_DATA = 240
const A_COL_AGENT1 = 500
const A_COL_ENRICH = 500
const A_COL_AGENT2 = 780
const A_COL_OUTPUT = 1060

const A_ROW_GAP = 90
const A_ROW_START = 30

function aRow(index: number) { return A_ROW_START + index * A_ROW_GAP }

export const briefingNodes: Node<ArchNodeData>[] = [
  // ── Trigger ──
  {
    id: 'brief-trigger',
    type: 'scheduler',
    position: { x: A_COL_TRIGGER, y: aRow(1.5) },
    data: {
      label: 'Cloud Scheduler',
      nodeType: 'scheduler',
      icon: 'calendar',
      badge: 'Mon 8:30 AM',
      description: 'weekly-executive-briefing job fires Monday 8:30 AM CST → POST /api/v1/scheduler/briefing. Uses dedicated scheduler-invoker service account with OIDC authentication to Cloud Run.',
      technicalDetails: {
        apis: ['Cloud Scheduler → Cloud Run OIDC'],
        functions: ['POST /api/v1/scheduler/briefing'],
      },
      connections: {
        outgoing: ['Input: 14-Day Digest'],
      },
      section: 'A',
    },
  },

  // ── Data Input ──
  {
    id: 'brief-data',
    type: 'processing',
    position: { x: A_COL_DATA, y: aRow(1.5) },
    data: {
      label: '14-Day Digest Input',
      nodeType: 'processing',
      icon: 'filter',
      badge: '~200 articles',
      description: 'Fetches all Medium/High/Critical priority digest_items from the last 14 days. Batched into groups of ~40 articles to prevent context window overflow. Sorted by priority and recency.',
      technicalDetails: {
        sourceFiles: ['ingestion/generators/pre_briefing.py'],
        functions: ['_get_articles()', '_batch_articles()'],
        tables: ['digest_items'],
      },
      connections: {
        incoming: ['Cloud Scheduler'],
        outgoing: ['Agent 1: Pre-Brief Generator'],
      },
      section: 'A',
    },
  },

  // ── Agent 1 ──
  {
    id: 'brief-agent1',
    type: 'agent',
    position: { x: A_COL_AGENT1, y: aRow(0) },
    data: {
      label: 'Agent 1: Pre-Brief',
      nodeType: 'agent',
      icon: 'brain',
      badge: 'Claude Sonnet',
      description: 'Claude Sonnet 4.5. Analyzes batches of recent articles. Produces structured observations: category, signal_type (net_new / evolution / stalled), confidence_score, supporting_articles. Categories: Suppliers & Competitors, End Customers & OEMs, Materials & Products, Supply Chain. Merge prompt deduplicates across batches.',
      prompt: BATCH_ANALYSIS_PROMPT + '\n\n--- MERGE PROMPT ---\n\n' + MERGE_PROMPT,
      technicalDetails: {
        sourceFiles: ['ingestion/generators/pre_briefing.py'],
        model: 'claude-sonnet-4-5',
        functions: ['generate_pre_briefing()', '_analyze_batch()', '_merge_observations()'],
        lineCount: 480,
        tables: ['pre_briefings'],
        cost: '~$0.50/briefing (Claude Sonnet)',
      },
      connections: {
        incoming: ['14-Day Digest Input'],
        outgoing: ['Agent 2: Executive Synthesizer'],
      },
      section: 'A',
    },
  },

  // ── Voice Enrichment ──
  {
    id: 'brief-voice',
    type: 'dataSource',
    position: { x: A_COL_ENRICH, y: aRow(2) },
    data: {
      label: 'Voice Enrichment',
      nodeType: 'dataSource',
      icon: 'quote',
      badge: '3 data types',
      description: 'Pre-fetches 3 types of "voice" data from BigQuery to inject into Agent 2\'s prompt: (1) Recent sec_filing_nuggets — competitive disclosures, risk admissions. (2) Recent earnings_quotes — executive commentary on markets. (3) Recent podcast_quotes — industry expert perspectives. These give the synthesizer direct quotes to cite.',
      technicalDetails: {
        tables: ['sec_filing_nuggets', 'earnings_quotes', 'podcast_quotes'],
        functions: ['_fetch_voice_enrichment()', '_format_sec_nuggets()', '_format_earnings_quotes()', '_format_podcast_quotes()'],
        sourceFiles: ['ingestion/generators/weekly_briefing.py'],
      },
      connections: {
        outgoing: ['Agent 2: Executive Synthesizer'],
      },
      section: 'A',
    },
  },

  // ── Historical Context ──
  {
    id: 'brief-history',
    type: 'dataSource',
    position: { x: A_COL_ENRICH, y: aRow(3) },
    data: {
      label: 'Historical Context',
      nodeType: 'dataSource',
      icon: 'history',
      badge: 'Prior briefings',
      description: 'Loads prior weekly briefings. Provides: BLUF, section headlines with net_new/continuing status, key companies, overall trend. Enables accurate differential analysis — Agent 2 knows what was covered before to correctly label topics as net_new or continuing.',
      technicalDetails: {
        tables: ['weekly_briefings'],
        functions: ['_get_historical_context()'],
        sourceFiles: ['ingestion/generators/weekly_briefing.py'],
      },
      connections: {
        outgoing: ['Agent 2: Executive Synthesizer'],
      },
      section: 'A',
    },
  },

  // ── Agent 2 ──
  {
    id: 'brief-agent2',
    type: 'agent',
    position: { x: A_COL_AGENT2, y: aRow(1.5) },
    data: {
      label: 'Agent 2: Synthesizer',
      nodeType: 'agent',
      icon: 'sparkles',
      badge: 'Claude Opus',
      description: 'Claude Opus 4.5 (most capable model). Receives: pre-brief JSON + historical context + voice enrichment. Has access to search_peripheral_intelligence tool (Exa, max 3 calls) for adjacent intelligence. Produces: 3-4 strategic sections, each with headline, net_new/continuing badge, narrative with inline citations [N], company logos [[Company]], entity highlights {{Entity}}. Plus: BLUF, overall_trend, source_articles array. Citation cleanup renumbers to sequential [1], [2].',
      prompt: EXECUTIVE_SYNTHESIZER_PROMPT,
      technicalDetails: {
        sourceFiles: ['ingestion/generators/weekly_briefing.py'],
        model: 'claude-opus-4-5',
        functions: ['generate_weekly_briefing()', '_build_synthesis_prompt()', '_extract_citation_numbers()'],
        apis: ['Exa.ai (peripheral intelligence, max 3 calls)'],
        lineCount: 1771,
        cost: '~$0.50/briefing (Claude Opus)',
      },
      connections: {
        incoming: ['Agent 1: Pre-Brief', 'Voice Enrichment', 'Historical Context'],
        outgoing: ['Podcast Generation', 'Briefing Storage'],
      },
      section: 'A',
    },
  },

  // ── Podcast Generation ──
  {
    id: 'brief-podcast',
    type: 'processing',
    position: { x: A_COL_OUTPUT, y: aRow(0.5) },
    data: {
      label: 'Podcast Generation',
      nodeType: 'processing',
      icon: 'audio',
      badge: '4-6 min MP3',
      description: '3-step audio pipeline: (1) Scaffold — deterministic conversation structure from briefing JSON. (2) Naturalize — Claude Sonnet rewrites into natural dialogue: "$2.4B" → "2.4 billion dollars", abbreviations expanded, "net new" vs "continuing" phrasing. (3) ElevenLabs TTS — Text-to-Dialogue API with Host (Rachel) + Analyst (Josh) voices. Output: 4-6 minute MP3 uploaded to GCS.',
      technicalDetails: {
        sourceFiles: ['ingestion/generators/weekly_briefing.py'],
        model: 'claude-sonnet-4-5 (naturalization)',
        functions: ['_generate_podcast()', '_build_podcast_script()', '_format_text_for_speech()'],
        apis: ['ElevenLabs Text-to-Dialogue API'],
      },
      connections: {
        incoming: ['Agent 2: Executive Synthesizer'],
        outgoing: ['Briefing Storage (GCS podcast MP3)'],
      },
      section: 'A',
    },
  },

  // ── Storage ──
  {
    id: 'brief-store',
    type: 'storage',
    position: { x: A_COL_OUTPUT, y: aRow(2.5) },
    data: {
      label: 'Briefing Storage',
      nodeType: 'storage',
      icon: 'database',
      badge: 'BQ + GCS',
      description: 'pre_briefings table (Agent 1 output), weekly_briefings table (Agent 2 output + BLUF), GCS bucket /podcasts/{briefing_id}.mp3 for audio. Frontend reads from weekly_briefings for the "Need to Know" section and streams podcast MP3 from GCS.',
      technicalDetails: {
        tables: ['pre_briefings', 'weekly_briefings'],
        functions: ['save_pre_briefing()', 'save_weekly_briefing()'],
        sourceFiles: ['db/gcp_storage.py'],
      },
      connections: {
        incoming: ['Agent 2: Executive Synthesizer', 'Podcast Generation'],
      },
      section: 'A',
    },
  },
]


// ============================================
// Section B: Deep Research Multi-Agent System
// ============================================

const B_COL_INPUT = 0
const B_COL_GROOMER = 220
const B_COL_FANOUT = 440
const B_COL_AGENTS = 580
const B_COL_FANIN = 800
const B_COL_SYNTH = 940
const B_COL_VALIDATE = 1140
const B_COL_OUTPUT = 1340

const B_ROW_GAP = 100
const B_ROW_START = 30

function bRow(index: number) { return B_ROW_START + index * B_ROW_GAP }

export const deepResearchNodes: Node<ArchNodeData>[] = [
  // ── Input ──
  {
    id: 'dr-input',
    type: 'dataSource',
    position: { x: B_COL_INPUT, y: bRow(1.5) },
    data: {
      label: 'User Query',
      nodeType: 'dataSource',
      icon: 'chat',
      description: 'User types a research question in the Research tab chat. SSE streaming begins immediately. The query is sent to POST /api/deep-research/stream and the frontend opens an EventSource connection for real-time progress updates.',
      technicalDetails: {
        sourceFiles: ['api/routes/deep_research.py'],
        functions: ['stream_research()'],
        apis: ['POST /api/deep-research/stream (SSE)'],
      },
      connections: {
        outgoing: ['Groomer Agent'],
      },
      section: 'B',
    },
  },

  // ── Groomer ──
  {
    id: 'dr-groomer',
    type: 'agent',
    position: { x: B_COL_GROOMER, y: bRow(1.5) },
    data: {
      label: 'Groomer Agent',
      nodeType: 'agent',
      icon: 'wand',
      badge: 'Claude Haiku',
      description: 'Claude Haiku 3.5 (fast, cheap). Interprets query intent. Generates optimized sub-queries for Financial and Industry agents. Injects prior research context from ResearchMemory (two-tier cache: in-memory 1h + BigQuery 24h) to avoid redundant clarifying questions. Decides if clarification needed (threshold: ready >95%). If NEEDS_CLARIFICATION (max 2 rounds), emits SSE event and waits for user input.',
      prompt: GROOMER_SYSTEM_PROMPT,
      technicalDetails: {
        sourceFiles: ['agents/research/groomer.py'],
        model: 'claude-haiku-4-5',
        functions: ['groom_query()', '_build_grooming_prompt()', '_inject_memory_context()'],
        lineCount: 658,
        cost: '$0.02/run (GPT-4o-mini)',
      },
      connections: {
        incoming: ['User Query', 'Research Memory (context)'],
        outgoing: ['Parallel Fan-Out (if ready)', 'User Query (if clarification needed)'],
      },
      section: 'B',
    },
  },

  // ── Fan-Out ──
  {
    id: 'dr-fanout',
    type: 'fanOut',
    position: { x: B_COL_FANOUT, y: bRow(1.5) },
    data: {
      label: 'Parallel Fan-Out',
      nodeType: 'fanOut',
      description: 'LangGraph Send API dispatches 3 agents simultaneously. Zero sequential waiting — all 3 start at the same time. Frontend shows parallel execution indicator. Uses LangGraph\'s conditional edges with Send() for dynamic parallel dispatch.',
      technicalDetails: {
        sourceFiles: ['graph/research_workflow.py'],
        functions: ['route_after_groomer()', 'Send("financial_research", ...)', 'Send("industry_research", ...)', 'Send("visual_research", ...)'],
      },
      connections: {
        incoming: ['Groomer Agent'],
        outgoing: ['Financial Research Agent', 'Industry Research Agent', 'Visual Research Agent'],
      },
      section: 'B',
    },
  },

  // ── Financial Agent ──
  {
    id: 'dr-financial',
    type: 'agent',
    position: { x: B_COL_AGENTS, y: bRow(0) },
    data: {
      label: 'Financial Research',
      nodeType: 'agent',
      icon: 'brain',
      badge: 'Claude Opus · ~30s',
      description: 'Claude Opus 4.5. Tools: search_earnings_quotes (BigQuery), search_sec_nuggets (BigQuery), query_corpus (vector search), StockNews API (company news, press releases, analyst ratings, sentiment analysis). Conditional tool gating: external earnings API only called when user mentions specific companies (corpus always runs). Ticker resolution from master company list.',
      prompt: FINANCIAL_AGENT_SYSTEM_PROMPT,
      technicalDetails: {
        sourceFiles: ['agents/research/financial.py'],
        model: 'claude-opus-4-5',
        functions: ['run_financial_research()', '_build_financial_prompt()', '_resolve_tickers()'],
        tables: ['earnings_quotes', 'sec_filing_nuggets', 'article_chunk_embeddings'],
        apis: ['StockNews API', 'BigQuery VECTOR_SEARCH'],
        lineCount: 738,
        cost: '$0.30–0.80/run (Claude Sonnet)',
      },
      connections: {
        incoming: ['Parallel Fan-Out'],
        outgoing: ['Fan-In (State Merge)'],
      },
      section: 'B',
    },
  },

  // ── Industry Agent ──
  {
    id: 'dr-industry',
    type: 'agent',
    position: { x: B_COL_AGENTS, y: bRow(1.5) },
    data: {
      label: 'Industry Research',
      nodeType: 'agent',
      icon: 'brain',
      badge: 'Claude Opus · ~30s',
      description: 'Claude Opus 4.5. Tools: Exa search (news, web, similar pages — uses composites trade publication domain list), query_corpus, get_market_signals, Google Trends, StockNews keyword search, get_freight_rates, search_podcast_quotes. Covers macro trends, market dynamics, industry signals.',
      prompt: INDUSTRY_AGENT_SYSTEM_PROMPT,
      technicalDetails: {
        sourceFiles: ['agents/research/industry.py'],
        model: 'claude-opus-4-5',
        functions: ['run_industry_research()', '_build_industry_prompt()'],
        tables: ['article_chunk_embeddings', 'podcast_quotes', 'freight_rates'],
        apis: ['Exa.ai', 'Google Trends', 'StockNews API'],
        lineCount: 685,
        cost: '$0.30–0.80/run (Claude Sonnet)',
      },
      connections: {
        incoming: ['Parallel Fan-Out'],
        outgoing: ['Fan-In (State Merge)'],
      },
      section: 'B',
    },
  },

  // ── Visual Agent ──
  {
    id: 'dr-visual',
    type: 'agent',
    position: { x: B_COL_AGENTS, y: bRow(3) },
    data: {
      label: 'Visual Research',
      nodeType: 'agent',
      icon: 'eye',
      badge: 'Claude Sonnet · ~15s',
      description: 'Claude Sonnet 4.5. Searches article_images BigQuery table for relevant charts, graphs, and data visualizations. LLM-based ranking and caption generation. ~10-15 seconds (finishes before other agents). Graceful degradation if no relevant visuals found.',
      prompt: VISUAL_AGENT_SYSTEM_PROMPT,
      technicalDetails: {
        sourceFiles: ['agents/research/visual.py'],
        model: 'claude-sonnet-4-5',
        functions: ['run_visual_research()', 'corpus_visuals_search()'],
        tables: ['article_images'],
        lineCount: 442,
        cost: '$0.10–0.20/run',
      },
      connections: {
        incoming: ['Parallel Fan-Out'],
        outgoing: ['Fan-In (State Merge)'],
      },
      section: 'B',
    },
  },

  // ── Fan-In ──
  {
    id: 'dr-fanin',
    type: 'fanOut',
    position: { x: B_COL_FANIN, y: bRow(1.5) },
    data: {
      label: 'Fan-In (Merge)',
      nodeType: 'fanOut',
      description: 'LangGraph reducer architecture merges parallel agent outputs. Reducer annotations: _keep_first() for immutable fields, _keep_last() for outputs, _merge_errors() for error lists. Handles state merge from 3 parallel branches without data loss.',
      technicalDetails: {
        sourceFiles: ['agents/research/state.py'],
        functions: ['_keep_first()', '_keep_last()', '_merge_errors()'],
        lineCount: 395,
      },
      connections: {
        incoming: ['Financial Research Agent', 'Industry Research Agent', 'Visual Research Agent'],
        outgoing: ['Synthesizer Agent'],
      },
      section: 'B',
    },
  },

  // ── Synthesizer ──
  {
    id: 'dr-synth',
    type: 'agent',
    position: { x: B_COL_SYNTH, y: bRow(1.5) },
    data: {
      label: 'Synthesizer',
      nodeType: 'agent',
      icon: 'sparkles',
      badge: 'Claude Opus + Thinking',
      description: 'Claude Opus 4.5 with Extended Thinking support. Produces block-based narrative: paragraph blocks, metric_grid blocks, visual_split blocks, quote blocks. 12-word max headlines. 2-3 sections max. Inline company logos ([[Company]]). Sequential numbered citations. Normalizes LLM enum values.',
      prompt: SYNTHESIZER_SYSTEM_PROMPT,
      technicalDetails: {
        sourceFiles: ['agents/research/synthesizer.py'],
        model: 'claude-opus-4-5 (extended thinking)',
        functions: ['run_synthesis()', '_build_synthesis_prompt()', '_normalize_blocks()'],
        lineCount: 812,
        cost: '$0.40–0.80/run (Claude Sonnet)',
      },
      connections: {
        incoming: ['Fan-In (State Merge)'],
        outgoing: ['Validator Agent'],
      },
      section: 'B',
    },
  },

  // ── Validator ──
  {
    id: 'dr-validator',
    type: 'processing',
    position: { x: B_COL_VALIDATE, y: bRow(1.5) },
    data: {
      label: 'Validator',
      nodeType: 'processing',
      icon: 'check',
      badge: 'Citation audit',
      description: 'Citation verification: checks that [N] references correspond to actual findings. Flags unsubstantiated claims. Adjusts confidence levels. Pass criteria: <3 errors, <5 unsubstantiated claims, >80% citations valid. Emits validation SSE event with pass/fail status.',
      prompt: VALIDATOR_SYSTEM_PROMPT,
      technicalDetails: {
        sourceFiles: ['agents/research/validator.py'],
        functions: ['run_validation()', '_check_citations()', '_flag_unsubstantiated()'],
        lineCount: 359,
        cost: '$0.05–0.10/run (GPT-4o-mini)',
      },
      connections: {
        incoming: ['Synthesizer Agent'],
        outgoing: ['Report Output'],
      },
      section: 'B',
    },
  },

  // ── Output ──
  {
    id: 'dr-output',
    type: 'storage',
    position: { x: B_COL_OUTPUT, y: bRow(1.5) },
    data: {
      label: 'Report Output',
      nodeType: 'storage',
      icon: 'database',
      badge: 'BQ + SSE',
      description: 'Block-based report rendered in ResearchCanvas. SSE events: node_start, node_complete, tool_progress, category, validation, warnings, report_saved. Automatic persistence to deep_research_reports BigQuery table. Two-tier cache: in-memory (1h TTL) + BigQuery (24h TTL).',
      technicalDetails: {
        tables: ['deep_research_reports'],
        sourceFiles: ['agents/research/memory.py', 'api/routes/deep_research.py'],
        functions: ['save_report()', 'ResearchMemory.cache_report()'],
      },
      connections: {
        incoming: ['Validator Agent'],
      },
      section: 'B',
    },
  },

  // ── Memory (side node connected to groomer) ──
  {
    id: 'dr-memory',
    type: 'storage',
    position: { x: B_COL_GROOMER, y: bRow(3.2) },
    data: {
      label: 'Research Memory',
      nodeType: 'storage',
      icon: 'database',
      badge: '2-tier cache',
      description: 'ResearchMemory service provides two-tier caching: in-memory (1h TTL) + BigQuery (24h TTL). Injects prior related research context into the Groomer prompt so it can skip redundant clarification questions. Also serves saved reports via API endpoints.',
      technicalDetails: {
        sourceFiles: ['agents/research/memory.py'],
        functions: ['get_related_context()', 'cache_report()', 'search_related_reports()'],
        tables: ['deep_research_reports'],
      },
      connections: {
        outgoing: ['Groomer Agent (context injection)'],
      },
      section: 'B',
    },
  },
]
