import type { Node } from '@xyflow/react'
import type { ArchNodeData } from '../types'

// ============================================
// Section C: Expert Podcast Intelligence
// ============================================

const COL_DISCOVERY = 0
const COL_RESOLVE = 280
const COL_EXTRACT = 560
const COL_STORE = 840
const COL_DOWNSTREAM = 1100

const ROW_GAP = 90
const ROW_START = 20

function row(index: number) { return ROW_START + index * ROW_GAP }

export const podcastNodes: Node<ArchNodeData>[] = [
  // ── Column 1: Discovery ──
  {
    id: 'pod-rss',
    type: 'dataSource',
    position: { x: COL_DISCOVERY, y: row(0.5) },
    data: {
      label: 'Podcast RSS Discovery',
      nodeType: 'dataSource',
      icon: 'radio',
      badge: 'C1_PODCAST_FEEDS',
      description: 'RSS feed parsing with httpx. Discovers new episodes from configured podcast feeds (C1_PODCAST_FEEDS). Deduplicates against BigQuery podcast_episodes table by GUID.',
      technicalDetails: {
        sourceFiles: ['ingestion/podcasts/discovery.py'],
        functions: ['discover_new_episodes()', '_parse_rss_feed()'],
        tables: ['podcast_episodes'],
      },
      connections: {
        outgoing: ['Transcript Resolution Chain'],
      },
      section: 'C',
    },
  },

  // ── Column 2: Transcript Resolution ──
  {
    id: 'pod-resolve',
    type: 'processing',
    position: { x: COL_RESOLVE, y: row(0.5) },
    data: {
      label: 'Transcript Resolution Chain',
      nodeType: 'processing',
      icon: 'workflow',
      badge: '3-resolver waterfall',
      description: '3-resolver waterfall: (1) YouTube transcript API (free, fast), (2) Site-specific scraper (show notes), (3) AssemblyAI (paid, highest quality, speaker diarization). Quality-gated: falls through to next resolver if quality insufficient.',
      technicalDetails: {
        sourceFiles: ['ingestion/podcasts/resolvers/chain.py'],
        functions: ['resolve_transcript()'],
        apis: ['YouTube Transcript API', 'AssemblyAI'],
      },
      connections: {
        incoming: ['Podcast RSS Discovery'],
        outgoing: ['Quote Extraction'],
      },
      section: 'C',
    },
  },

  // ── Column 3: AI Extraction ──
  {
    id: 'pod-extract',
    type: 'agent',
    position: { x: COL_EXTRACT, y: row(0.5) },
    data: {
      label: 'Quote Extraction',
      nodeType: 'agent',
      icon: 'brain',
      badge: 'Claude Sonnet',
      description: 'Claude Sonnet 4.5. Chunked processing (30K char chunks + 3K overlap for context continuity). Composites industry theme taxonomy. Speaker diarization healing (fixes ASR speaker label drift). Deduplication via SequenceMatcher. Extracts: speaker, role, verbatim quote, theme, strategic_relevance, companies_mentioned.',
      technicalDetails: {
        sourceFiles: ['ingestion/podcasts/quote_extractor.py'],
        model: 'claude-sonnet-4-5',
        functions: ['extract_quotes()', '_chunk_transcript()', '_heal_speaker_labels()'],
        lineCount: 508,
      },
      connections: {
        incoming: ['Transcript Resolution Chain'],
        outgoing: ['podcast_episodes table', 'podcast_quotes table'],
      },
      section: 'C',
    },
  },

  // ── Column 4: Storage ──
  {
    id: 'bq-pod-episodes',
    type: 'storage',
    position: { x: COL_STORE, y: row(0) },
    data: {
      label: 'podcast_episodes',
      nodeType: 'storage',
      icon: 'database',
      description: 'Episode metadata + full transcript text. Fields: title, podcast_name, published_at, duration, transcript, speakers, resolver_used, quality_score.',
      technicalDetails: {
        tables: ['podcast_episodes'],
      },
      connections: {
        incoming: ['Quote Extraction'],
      },
      section: 'C',
    },
  },
  {
    id: 'bq-pod-quotes',
    type: 'storage',
    position: { x: COL_STORE, y: row(1) },
    data: {
      label: 'podcast_quotes',
      nodeType: 'storage',
      icon: 'database',
      badge: 'MCP tool',
      description: 'Speaker-attributed quotes with theme classification. Queried by search_podcast_quotes MCP tool. Fields: speaker, speaker_role, quote_text, theme, strategic_relevance, companies_mentioned.',
      technicalDetails: {
        tables: ['podcast_quotes'],
        functions: ['search_podcast_quotes()'],
      },
      connections: {
        incoming: ['Quote Extraction'],
        outgoing: ['Industry Research agent', 'Weekly Briefing voice enrichment'],
      },
      section: 'C',
    },
  },

  // ── Column 5: Downstream ──
  {
    id: 'pod-downstream',
    type: 'processing',
    position: { x: COL_DOWNSTREAM, y: row(0.5) },
    data: {
      label: '→ Research & Briefings',
      nodeType: 'processing',
      icon: 'workflow',
      description: 'Industry Research agent calls search_podcast_quotes during Deep Research to surface expert perspective on market topics. Also injected as voice enrichment into weekly briefings, giving Agent 2 direct expert quotes to cite.',
      technicalDetails: {
        sourceFiles: ['agents/research/industry.py', 'ingestion/generators/weekly_briefing.py'],
        functions: ['search_podcast_quotes()', '_get_voice_enrichment()'],
      },
      connections: {
        incoming: ['podcast_quotes table'],
        outgoing: ['Industry Research agent', 'Weekly Briefing Agent 2'],
      },
      section: 'C',
    },
  },
]
