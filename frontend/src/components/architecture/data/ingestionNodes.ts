import type { Node } from '@xyflow/react'
import type { ArchNodeData } from '../types'

// ============================================
// Column 1 — Data Sources (x: 0)
// ============================================

const COL_SRC = 0
const COL_ORCH = 280
const COL_PROC = 520
const COL_STORE = 820
const COL_POST = 1100

const ROW_GAP = 72
const ROW_START = 20

function srcY(index: number) { return ROW_START + index * ROW_GAP }
function procY(index: number) { return ROW_START + 60 + index * ROW_GAP }
function storeY(index: number) { return ROW_START + 30 + index * ROW_GAP }
function postY(index: number) { return ROW_START + 100 + index * ROW_GAP }

export const ingestionSectionANodes: Node<ArchNodeData>[] = [
  // ── Column 1: Data Sources ──
  {
    id: 'src-rss',
    type: 'dataSource',
    position: { x: COL_SRC, y: srcY(0) },
    data: {
      label: 'RSS Feeds',
      nodeType: 'dataSource',
      icon: 'rss',
      badge: '14 feeds',
      description: '14 industry RSS feeds: CompositesWorld, JEC, SAMPE, Plastics Today, and more. Parsed via feedparser. Runs every 4 hours via ingest-flash-update scheduler job.',
      technicalDetails: {
        sourceFiles: ['ingestion/orchestrator.py'],
        functions: ['_collect_rss_articles()'],
        apis: ['feedparser'],
        cost: 'Free',
        dataVolume: '14 feeds / ~200 articles/day',
      },
      connections: {
        outgoing: ['Ingestion Orchestrator'],
      },
    },
  },
  {
    id: 'src-exa',
    type: 'dataSource',
    position: { x: COL_SRC, y: srcY(1) },
    data: {
      label: 'Exa.ai',
      nodeType: 'dataSource',
      icon: 'search',
      badge: '~100 queries',
      description: 'Neural search engine. ~100 industry-specific + per-company queries defined in industry_queries.py. Queries cover composites, aerospace programs (F-35, 787), EV platforms, wind energy, marine, construction. Uses search_and_contents API with auto-date filtering. Runs daily at 2:00 AM CST.',
      technicalDetails: {
        sourceFiles: ['ingestion/orchestrator.py', 'tools/exa_search.py'],
        functions: ['_collect_exa_articles()'],
        apis: ['Exa.ai search_and_contents'],
        cost: '~$0.01/query',
        dataVolume: '~100 queries/day',
      },
      connections: {
        outgoing: ['Ingestion Orchestrator'],
      },
    },
  },
  {
    id: 'src-tavily',
    type: 'dataSource',
    position: { x: COL_SRC, y: srcY(2) },
    data: {
      label: 'Tavily',
      nodeType: 'dataSource',
      icon: 'search',
      badge: '75 queries',
      description: 'Web crawl search. 75 broadening queries for coverage gaps. Includes company-specific news queries per tracked company. Runs daily at 2:20 AM CST.',
      technicalDetails: {
        sourceFiles: ['ingestion/orchestrator.py'],
        functions: ['_collect_tavily_articles()'],
        apis: ['Tavily Search API'],
        cost: '~$0.01/query',
        dataVolume: '~100 queries/day',
      },
      connections: {
        outgoing: ['Ingestion Orchestrator'],
      },
    },
  },
  {
    id: 'src-sec',
    type: 'dataSource',
    position: { x: COL_SRC, y: srcY(3) },
    data: {
      label: 'SEC EDGAR',
      nodeType: 'dataSource',
      icon: 'filing',
      badge: '10-K, 10-Q, 8-K',
      description: 'Filing types: 10-K (annual), 10-Q (quarterly), 8-K (current events). Uses sec-api.io for query + section extraction. Targets ~35 public companies from master company list. Runs daily at 2:45 AM CST.',
      technicalDetails: {
        sourceFiles: ['tools/sec_filings/collector.py', 'tools/sec_filings/sec_client.py'],
        functions: ['collect_sec_filings()', '_convert_sec_to_article()'],
        apis: ['sec-api.io'],
      },
      connections: {
        outgoing: ['Ingestion Orchestrator'],
      },
    },
  },
  {
    id: 'src-earnings',
    type: 'dataSource',
    position: { x: COL_SRC, y: srcY(4) },
    data: {
      label: 'API Ninja Earnings',
      nodeType: 'dataSource',
      icon: 'earnings',
      description: 'Earnings call transcripts with speaker attribution (CEO, CFO, analysts). Parsed into structured sections. Targets US-listed public companies.',
      technicalDetails: {
        sourceFiles: ['tools/earnings/collector.py'],
        functions: ['collect_earnings_transcripts()'],
        apis: ['API Ninjas Earnings'],
      },
      connections: {
        outgoing: ['Ingestion Orchestrator'],
      },
    },
  },
  {
    id: 'src-stocknews',
    type: 'dataSource',
    position: { x: COL_SRC, y: srcY(5) },
    data: {
      label: 'StockNews API',
      nodeType: 'dataSource',
      icon: 'trending',
      description: 'Market-focused news articles for tracked tickers. Includes analyst ratings, press releases, sector news.',
      technicalDetails: {
        sourceFiles: ['ingestion/orchestrator.py'],
        apis: ['StockNews API'],
        cost: 'Free tier',
        dataVolume: '~50 articles/day',
      },
      connections: {
        outgoing: ['Ingestion Orchestrator'],
      },
    },
  },
  {
    id: 'src-fmp',
    type: 'dataSource',
    position: { x: COL_SRC, y: srcY(6) },
    data: {
      label: 'FMP Premium News',
      nodeType: 'dataSource',
      icon: 'news',
      description: 'Aggregated premium sources: Benzinga, Seeking Alpha, Bloomberg, Reuters. Article text included directly (no scraping needed).',
      technicalDetails: {
        sourceFiles: ['ingestion/orchestrator.py'],
        apis: ['Financial Modeling Prep API'],
      },
      connections: {
        outgoing: ['Ingestion Orchestrator'],
      },
    },
  },
  {
    id: 'src-freight',
    type: 'dataSource',
    position: { x: COL_SRC, y: srcY(7) },
    data: {
      label: 'Drewry WCI',
      nodeType: 'dataSource',
      icon: 'truck',
      description: 'World Container Index freight rates. Web-scraped from Drewry\'s public dashboard. Stored in separate freight_rates table.',
      technicalDetails: {
        sourceFiles: ['ingestion/orchestrator.py'],
        tables: ['freight_rates'],
      },
      connections: {
        outgoing: ['Ingestion Orchestrator'],
      },
    },
  },
  {
    id: 'src-pr',
    type: 'dataSource',
    position: { x: COL_SRC, y: srcY(8) },
    data: {
      label: 'Press Releases',
      nodeType: 'dataSource',
      icon: 'news',
      description: 'Company press releases discovered via Exa search against tracked company names.',
      technicalDetails: {
        sourceFiles: ['ingestion/orchestrator.py'],
        apis: ['Exa.ai'],
      },
      connections: {
        outgoing: ['Ingestion Orchestrator'],
      },
    },
  },
  {
    id: 'src-podcasts',
    type: 'dataSource',
    position: { x: COL_SRC, y: srcY(9) },
    data: {
      label: 'Podcast RSS',
      nodeType: 'dataSource',
      icon: 'radio',
      description: 'Industry podcast episodes discovered via RSS. Transcribed through a multi-resolver chain, then processed by LLM for speaker-attributed expert quotes.',
      technicalDetails: {
        sourceFiles: ['ingestion/podcasts/discovery.py'],
        apis: ['YouTube, AssemblyAI'],
      },
      connections: {
        outgoing: ['Ingestion Orchestrator'],
      },
    },
  },

  // ── Column 2: Orchestrator ──
  {
    id: 'orch',
    type: 'orchestrator',
    position: { x: COL_ORCH, y: srcY(4) },
    data: {
      label: 'Ingestion Orchestrator',
      nodeType: 'processing',
      icon: 'workflow',
      badge: '~1,800 lines',
      description: 'Central coordinator (orchestrator.py, ~1800 lines). Manages the full pipeline: source collection → dedup → enrichment → classification → storage. Handles 5 specialized run modes: run_full_ingestion(), run_rss_only(), run_financials_only(), run_earnings_only(), run_digest_only(). Each source type has a converter method (e.g., _convert_sec_to_article()) that normalizes into a common Article schema. Configurable via IngestionConfig dataclass.',
      technicalDetails: {
        sourceFiles: ['ingestion/orchestrator.py'],
        functions: ['run_full_ingestion()', 'run_rss_only()', 'run_financials_only()', 'run_earnings_only()', 'run_digest_only()'],
        lineCount: 1800,
        dataVolume: '~500 articles/day',
      },
      connections: {
        incoming: ['RSS Feeds', 'Exa.ai', 'Tavily', 'SEC EDGAR', 'Earnings', 'StockNews', 'FMP', 'Drewry', 'Press Releases', 'Podcasts'],
        outgoing: ['Deduplication'],
      },
    },
  },

  // ── Column 3: Processing Pipeline ──
  {
    id: 'proc-dedup',
    type: 'processing',
    position: { x: COL_PROC, y: procY(0) },
    data: {
      label: 'Deduplication',
      nodeType: 'processing',
      icon: 'filter',
      description: '3-tier dedup: (1) Exact URL match, (2) Normalized title match, (3) Fuzzy title similarity (SequenceMatcher, 0.85 threshold). BigQuery-backed with in-memory cache (168h lookback). Source priority ranking: Bloomberg/Reuters/WSJ > Seeking Alpha/Benzinga > other.',
      technicalDetails: {
        sourceFiles: ['ingestion/processing/deduplication.py'],
        functions: ['is_duplicate()', '_fuzzy_title_match()'],
        tables: ['articles'],
        dataVolume: '~500 articles/day',
      },
      connections: {
        incoming: ['Ingestion Orchestrator'],
        outgoing: ['Web Scraper'],
      },
    },
  },
  {
    id: 'proc-scrape',
    type: 'processing',
    position: { x: COL_PROC, y: procY(1) },
    data: {
      label: 'Web Scraper',
      nodeType: 'processing',
      icon: 'scrape',
      description: 'Enriches articles with full text content from source URLs. 50 articles per run limit. Handles premium site 403s gracefully (FMP articles already include text). Uses httpx + BeautifulSoup.',
      technicalDetails: {
        sourceFiles: ['ingestion/processing/scraper.py'],
        functions: ['scrape_article_content()'],
      },
      connections: {
        incoming: ['Deduplication'],
        outgoing: ['AI Classifier'],
      },
    },
  },
  {
    id: 'proc-classify',
    type: 'processing',
    position: { x: COL_PROC, y: procY(2) },
    data: {
      label: 'AI Classifier',
      nodeType: 'processing',
      icon: 'classify',
      badge: 'Claude Sonnet',
      description: 'Claude Sonnet 4.5 with composites industry taxonomy. 10 concurrent classifications, 0.2s spacing. Outputs: category, industries[], priority (Critical/High/Medium/Low), relevance_score (0-1), summary, companies[], materials[], sentiment, is_hero flag for breaking news.',
      technicalDetails: {
        sourceFiles: ['ingestion/processing/classifier.py'],
        model: 'claude-sonnet-4-5',
        functions: ['classify_article()', '_build_classification_prompt()'],
        cost: '~$0.002/article (GPT-4o-mini)',
        dataVolume: '~500 articles/day',
      },
      connections: {
        incoming: ['Web Scraper'],
        outgoing: ['Entity Linker'],
      },
    },
  },
  {
    id: 'proc-entity',
    type: 'processing',
    position: { x: COL_PROC, y: procY(3) },
    data: {
      label: 'Entity Linker',
      nodeType: 'processing',
      icon: 'link',
      description: 'Links mentioned companies to master company list (~200 tracked companies with tickers, aliases, sectors). Resolves name variants (e.g., "Hexcel Corp" → HEXCEL → HXL).',
      technicalDetails: {
        sourceFiles: ['ingestion/processing/entity_linker.py'],
        functions: ['link_entities()'],
        tables: ['companies'],
      },
      connections: {
        incoming: ['AI Classifier'],
        outgoing: ['Image Enrichment'],
      },
    },
  },
  {
    id: 'proc-image',
    type: 'processing',
    position: { x: COL_PROC, y: procY(4) },
    data: {
      label: 'Image Enrichment',
      nodeType: 'processing',
      icon: 'image',
      badge: 'Claude Vision',
      description: 'Tavily image search for high-priority articles. Claude Vision classifies images: chart_type, image_type, topics, companies, industries, relevance_score. Stored in article_images table. Used by Visual Research agent in Deep Research.',
      technicalDetails: {
        sourceFiles: ['ingestion/processing/image_enrichment.py'],
        model: 'claude-sonnet-4-5 (Vision)',
        tables: ['article_images'],
      },
      connections: {
        incoming: ['Entity Linker'],
        outgoing: ['Vector Embedding'],
      },
    },
  },
  {
    id: 'proc-embed',
    type: 'processing',
    position: { x: COL_PROC, y: procY(5) },
    data: {
      label: 'Vector Embedding',
      nodeType: 'processing',
      icon: 'embed',
      badge: 'Vertex AI',
      description: 'Vertex AI text-embedding-004 (768 dimensions). Articles chunked and embedded into article_chunk_embeddings table. Enables semantic search across entire corpus via BigQuery native VECTOR_SEARCH with IVF index.',
      technicalDetails: {
        sourceFiles: ['db/bq_vector_store.py'],
        model: 'Vertex AI text-embedding-004',
        functions: ['embed_and_store()'],
        tables: ['article_chunk_embeddings'],
        cost: '~$0.0001/article',
        dataVolume: '768-dim vectors',
      },
      connections: {
        incoming: ['Image Enrichment'],
        outgoing: ['articles table', 'digest_items table', 'article_tags table', 'embeddings table', 'article_images table'],
      },
    },
  },

  // ── Column 4: BigQuery Storage ──
  {
    id: 'bq-articles',
    type: 'storage',
    position: { x: COL_STORE, y: storeY(0) },
    data: {
      label: 'articles',
      nodeType: 'storage',
      icon: 'database',
      badge: '5,000+ rows',
      description: 'Raw source of truth. All articles regardless of classification. Fields: title, content, url, source_type, companies_mentioned, published_at, fetched_at.',
      technicalDetails: {
        tables: ['articles'],
        dataVolume: '5,200+ articles total',
      },
      connections: {
        incoming: ['Vector Embedding pipeline'],
        outgoing: ['Digest Generator', 'SEC Nugget Extraction', 'Earnings Quote Extraction'],
      },
    },
  },
  {
    id: 'bq-digest',
    type: 'storage',
    position: { x: COL_STORE, y: storeY(1) },
    data: {
      label: 'digest_items',
      nodeType: 'storage',
      icon: 'database',
      description: 'Classified articles with AI-generated summaries. Fields: category, priority, relevance_score, summary, companies, materials, industries, sentiment, is_hero, narrative enrichment fields. Primary table for Pulse and Discovery tabs.',
      technicalDetails: {
        tables: ['digest_items'],
        dataVolume: '5,200+ classified items',
      },
      connections: {
        incoming: ['AI Classifier pipeline'],
        outgoing: ['Pulse tab', 'Discovery tab', 'Briefing pipeline'],
      },
    },
  },
  {
    id: 'bq-tags',
    type: 'storage',
    position: { x: COL_STORE, y: storeY(2) },
    data: {
      label: 'article_tags',
      nodeType: 'storage',
      icon: 'database',
      description: 'Normalized tags extracted during classification. Powers trending analytics and entity aggregation on the Pulse tab.',
      technicalDetails: {
        tables: ['article_tags'],
      },
      connections: {
        incoming: ['Entity Linker pipeline'],
        outgoing: ['Pulse heat map', 'Discovery filters'],
      },
    },
  },
  {
    id: 'bq-embeddings',
    type: 'storage',
    position: { x: COL_STORE, y: storeY(3) },
    data: {
      label: 'article_chunk_embeddings',
      nodeType: 'storage',
      icon: 'database',
      badge: '768-dim vectors',
      description: 'Vector store. Chunked text + 768-dim embeddings. Queried by Deep Research agents and ad-hoc briefing agent via query_corpus MCP tool. BigQuery native VECTOR_SEARCH with IVF index.',
      technicalDetails: {
        tables: ['article_chunk_embeddings'],
        dataVolume: '768-dim vectors, 15K+ chunks',
      },
      connections: {
        incoming: ['Vector Embedding'],
        outgoing: ['Deep Research agents', 'Ad-hoc Briefing agent', 'Pipeline agent'],
      },
    },
  },
  {
    id: 'bq-images',
    type: 'storage',
    position: { x: COL_STORE, y: storeY(4) },
    data: {
      label: 'article_images',
      nodeType: 'storage',
      icon: 'database',
      description: 'Vision-classified images. Used by Visual Research agent to surface charts/graphs in Deep Research reports. Fields: image_url, image_type, chart_type, topics, companies, industries, relevance_score.',
      technicalDetails: {
        tables: ['article_images'],
      },
      connections: {
        incoming: ['Image Enrichment'],
        outgoing: ['Visual Research agent'],
      },
    },
  },

  // ── Column 5: Post-Storage Processing ──
  {
    id: 'post-digest',
    type: 'processing',
    position: { x: COL_POST, y: postY(0) },
    data: {
      label: 'Digest Generator',
      nodeType: 'processing',
      icon: 'classify',
      description: 'Runs after article storage. Generates concise digest summaries for articles that passed classification threshold.',
      technicalDetails: {
        sourceFiles: ['ingestion/generators/digest.py'],
        model: 'claude-sonnet-4-5',
      },
      connections: {
        incoming: ['articles table'],
      },
    },
  },
  {
    id: 'post-nuggets',
    type: 'processing',
    position: { x: COL_POST, y: postY(1) },
    data: {
      label: 'SEC Nugget Extraction',
      nodeType: 'processing',
      icon: 'classify',
      badge: 'Claude Sonnet',
      description: 'For SEC filings: Claude extracts 15-30 strategic nuggets per filing (competitive disclosures, risk admissions, forward guidance). Stored in sec_filing_nuggets. Cost: ~$0.20-0.60/filing.',
      technicalDetails: {
        sourceFiles: ['ingestion/sec_filings/nugget_extractor.py'],
        model: 'claude-sonnet-4-5',
        functions: ['extract_nuggets()'],
        tables: ['sec_filing_nuggets'],
        lineCount: 487,
        cost: '$0.20–0.60/filing (Claude Sonnet)',
        dataVolume: '~50 filings/week',
      },
      connections: {
        incoming: ['articles table (SEC filings)'],
        outgoing: ['Financial Research agent', 'Weekly Briefing voice enrichment'],
      },
    },
  },
  {
    id: 'post-quotes',
    type: 'processing',
    position: { x: COL_POST, y: postY(2) },
    data: {
      label: 'Earnings Quote Extraction',
      nodeType: 'processing',
      icon: 'classify',
      badge: 'Claude Haiku',
      description: 'For earnings transcripts: Claude extracts 8-15 executive quotes per transcript (competitive intel, production rates, pricing signals). Stored in earnings_quotes. Cost: ~$0.02-0.05/transcript.',
      technicalDetails: {
        sourceFiles: ['ingestion/earnings/quote_extractor.py'],
        model: 'claude-haiku-3-5',
        functions: ['extract_quotes()'],
        tables: ['earnings_quotes'],
        lineCount: 484,
        cost: '$0.02–0.05/transcript (GPT-4o-mini)',
        dataVolume: '~30 transcripts/quarter',
      },
      connections: {
        incoming: ['articles table (earnings transcripts)'],
        outgoing: ['Financial Research agent', 'Weekly Briefing voice enrichment'],
      },
    },
  },
]
