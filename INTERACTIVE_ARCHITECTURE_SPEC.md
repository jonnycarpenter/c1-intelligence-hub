# Interactive Architecture Showcase — Implementation Spec

> **Purpose**: This document is the single source of truth for building the "App Architecture" tab in the C1 Intelligence Hub frontend. It is designed to give fresh AI coding sessions full context to implement each section without needing to re-read the entire codebase.
>
> **Audience for the feature**: Technical recruiters, engineering managers, and "business-with-technical-curiosity" decision-makers evaluating Jonny's AI/data engineering capabilities. Lean toward *impressive technical depth* over simplification. A CTO should think "this person architects real systems" — not "this is a marketing deck."
>
> **Tech stack for implementation**: Next.js (React), Tailwind CSS, Framer Motion. Interactive node-graph library TBD (React Flow recommended — see § Implementation Notes).
>
> **Cloud infrastructure**: Fully deployed on **Google Cloud Platform** (10 GCP services): Cloud Run, BigQuery, Vertex AI, Cloud Storage, Cloud Scheduler, Cloud Build, Artifact Registry, Secret Manager, Cloud IAM, and Cloud Logging. The GCP layer is a first-class visual element in the architecture diagrams (§3.3) — designed to demonstrate production cloud engineering, not just app-level code.

---

## Table of Contents

1. [Tab Structure Overview](#1-tab-structure-overview)
2. [Tab 1 — Data Ingestion Pipelines](#2-tab-1--data-ingestion-pipelines)
3. [Tab 2 — Frontend Data Architecture](#3-tab-2--frontend-data-architecture)
4. [Tab 3 — Agentic Workflows](#4-tab-3--agentic-workflows)
5. [Interaction Design](#5-interaction-design)
6. [Implementation Notes](#6-implementation-notes)
7. [Session Execution Plan](#7-session-execution-plan)
8. [Data Reference Tables](#8-data-reference-tables)

---

## 1. Tab Structure Overview

Add a new top-level mode `'app-architecture'` to the sidebar with label **"Architecture"** and a `Cpu` or `Workflow` lucide icon. This tab has 3 sub-tabs rendered as a horizontal tab bar within the main content area:

| Sub-Tab | Label | Content |
|---------|-------|---------|
| 1 | **Data Ingestion** | Interactive node graph of all ingestion pipelines |
| 2 | **Tab Architecture** | How each frontend tab is populated from the data layer |
| 3 | **Agentic Workflows** | Multi-agent briefing generation + deep research workflow |

Each sub-tab is a full-width canvas with:
- A node-and-edge interactive diagram (React Flow or similar)
- A right-side or bottom **detail panel** that populates when a node is clicked
- Section headers/labels to group related nodes

---

## 2. Tab 1 — Data Ingestion Pipelines

### 2.1 Layout: Four Section Headers (Horizontal Swim Lanes or Vertical Sections)

The diagram is organized into 4 logical sections, each with a labeled header bar:

```
┌─────────────────────────────────────────────────────────────────────────┐
│  SECTION A: Core Article Ingestion                                       │
├─────────────────────────────────────────────────────────────────────────┤
│  SECTION B: SEC Filings & Earnings Transcripts                           │
├─────────────────────────────────────────────────────────────────────────┤
│  SECTION C: Expert Podcast Intelligence                                  │
├─────────────────────────────────────────────────────────────────────────┤
│  SECTION D: ImportYeti Supply Chain Network                              │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Section A: Core Article Ingestion

**Narrative**: "10 data sources are consolidated through a single orchestrator into a unified intelligence corpus. Each article passes through deduplication, enrichment, AI classification, entity linking, and vector embedding before storage."

#### Nodes (left to right flow):

**Column 1 — Data Sources** (each is a node, color-coded by type):
| Node ID | Label | Node Detail (shown on click) |
|---------|-------|------------------------------|
| `src-rss` | RSS Feeds (14) | 14 industry RSS feeds: CompositesWorld, JEC, SAMPE, Plastics Today, etc. Parsed via `feedparser`. Runs every 4 hours via `ingest-flash-update` scheduler job. |
| `src-exa` | Exa.ai (~100 queries) | Neural search engine. ~100 industry-specific + per-company queries defined in `industry_queries.py`. Queries cover composites, aerospace programs (F-35, 787), EV platforms, wind energy, marine, construction. Uses `search_and_contents` API with auto-date filtering. Runs daily at 2:00 AM CST. |
| `src-tavily` | Tavily (75 queries) | Web crawl search. 75 broadening queries for coverage gaps. Includes company-specific news queries per tracked company. Runs daily at 2:20 AM CST. |
| `src-sec` | SEC EDGAR | Filing types: 10-K (annual), 10-Q (quarterly), 8-K (current events). Uses sec-api.io for query + section extraction. Targets ~35 public companies from master company list. Runs daily at 2:45 AM CST. |
| `src-earnings` | API Ninja Earnings | Earnings call transcripts with speaker attribution (CEO, CFO, analysts). Parsed into structured sections. Targets US-listed public companies. |
| `src-stocknews` | StockNews API | Market-focused news articles for tracked tickers. Includes analyst ratings, press releases, sector news. |
| `src-fmp` | FMP Premium News | Aggregated premium sources: Benzinga, Seeking Alpha, Bloomberg, Reuters. Article text included directly (no scraping needed). |
| `src-freight` | Drewry WCI | World Container Index freight rates. Web-scraped from Drewry's public dashboard. Stored in separate `freight_rates` table. |
| `src-pr` | Press Releases | Company press releases discovered via Exa search against tracked company names. |
| `src-drewry` | Drewry (WCI) | Freight rate indices for supply chain cost tracking. |

**Column 2 — Orchestrator** (single large node):
| Node ID | Label | Node Detail |
|---------|-------|-------------|
| `orch` | Ingestion Orchestrator | Central coordinator (`orchestrator.py`, ~1800 lines). Manages the full pipeline: source collection → dedup → enrichment → classification → storage. Handles 5 specialized run modes: `run_full_ingestion()`, `run_rss_only()`, `run_financials_only()`, `run_earnings_only()`, `run_digest_only()`. Each source type has a converter method (e.g., `_convert_sec_to_article()`) that normalizes into a common `Article` schema. Configurable via `IngestionConfig` dataclass holding all API keys. |

**Column 3 — Processing Pipeline** (sequential chain of nodes):
| Node ID | Label | Node Detail |
|---------|-------|-------------|
| `proc-dedup` | Deduplication | 3-tier dedup: (1) Exact URL match, (2) Normalized title match, (3) Fuzzy title similarity (SequenceMatcher, 0.85 threshold). BigQuery-backed with in-memory cache (168h lookback). Source priority ranking: Bloomberg/Reuters/WSJ > Seeking Alpha/Benzinga > other. Implementation: `processing/deduplication.py`. |
| `proc-scrape` | Web Scraper | Enriches articles with full text content from source URLs. 50 articles per run limit. Handles premium site 403s gracefully (FMP articles already include text). Uses `httpx` + BeautifulSoup. |
| `proc-classify` | AI Classifier | Claude Sonnet 4.5 with composites industry taxonomy. 10 concurrent classifications, 0.2s spacing. Outputs: category, industries[], priority (Critical/High/Medium/Low), relevance_score (0-1), summary, companies[], materials[], sentiment, `is_hero` flag for breaking news. Prompt includes full composites supply chain taxonomy (suppliers, OEMs, materials, processes). |
| `proc-entity` | Entity Linker | Links mentioned companies to master company list (~200 tracked companies with tickers, aliases, sectors). Resolves name variants (e.g., "Hexcel Corp" → HEXCEL → HXL). |
| `proc-image` | Image Enrichment | Tavily image search for high-priority articles. Claude Vision classifies images: chart_type, image_type, topics, companies, industries, relevance_score. Stored in `article_images` table. Used by Visual Research agent in Deep Research. |
| `proc-embed` | Vector Embedding | Vertex AI `text-embedding-004` (768 dimensions). Articles chunked and embedded into `article_chunk_embeddings` table. Enables semantic search across entire corpus via BigQuery native `VECTOR_SEARCH` with IVF index. |

**Column 4 — BigQuery Storage** (grouped storage nodes):
| Node ID | Label | Node Detail |
|---------|-------|-------------|
| `bq-articles` | `articles` table | Raw source of truth. All articles regardless of classification. ~5,000+ articles. Fields: title, content, url, source_type, companies_mentioned, published_at, fetched_at. |
| `bq-digest` | `digest_items` table | Classified articles with AI-generated summaries. Fields: category, priority, relevance_score, summary, companies, materials, industries, sentiment, is_hero, narrative enrichment fields. Primary table for Pulse and Discovery tabs. |
| `bq-tags` | `article_tags` table | Normalized tags extracted during classification. Powers trending analytics and entity aggregation on the Pulse tab. |
| `bq-embeddings` | `article_chunk_embeddings` | Vector store. Chunked text + 768-dim embeddings. Queried by Deep Research agents and ad-hoc briefing agent via `query_corpus` MCP tool. |
| `bq-images` | `article_images` table | Vision-classified images. Used by Visual Research agent to surface charts/graphs in Deep Research reports. |

**Column 5 — Post-Storage Processing** (optional downstream):
| Node ID | Label | Node Detail |
|---------|-------|-------------|
| `post-digest` | Digest Generator | Runs after article storage. Generates concise digest summaries for articles that passed classification threshold. |
| `post-nuggets` | SEC Nugget Extraction | For SEC filings: Claude extracts 15-30 strategic nuggets per filing (competitive disclosures, risk admissions, forward guidance). Stored in `sec_filing_nuggets`. |
| `post-quotes` | Earnings Quote Extraction | For earnings transcripts: Claude extracts 8-15 executive quotes per transcript (competitive intel, production rates, pricing signals). Stored in `earnings_quotes`. |

#### Edges:
- All `src-*` nodes → `orch` (many-to-one, labeled "raw data")
- `orch` → `proc-dedup` (labeled "normalized articles")
- `proc-dedup` → `proc-scrape` → `proc-classify` → `proc-entity` → `proc-image` → `proc-embed` (sequential chain)
- `proc-embed` → `bq-articles`, `bq-digest`, `bq-tags`, `bq-embeddings`, `bq-images` (fan-out to storage)
- `bq-articles` → `post-nuggets` (for SEC filings)
- `bq-articles` → `post-quotes` (for earnings transcripts)
- `bq-articles` → `post-digest`

#### Scheduler Overlay (Optional: toggle-able layer):
Show Cloud Scheduler timing annotations on source nodes:
- `ingest-flash-update` (every 4h): RSS + Freight
- `ingest-exa` (2:00 AM CST): Exa queries + Press Releases  
- `ingest-tavily` (2:20 AM CST): Tavily queries
- `ingest-financial` (2:45 AM CST): SEC + Earnings + FMP + StockNews

---

### 2.3 Section B: SEC Filings & Earnings Transcripts

**Narrative**: "Financial disclosures and earnings calls are ingested as articles, then undergo a second-pass AI extraction to pull strategic nuggets and executive quotes that enrich briefings and research reports."

#### Nodes:

**Left — Ingestion** (already covered in Section A, these are detail-expansion nodes):
| Node ID | Label | Node Detail |
|---------|-------|-------------|
| `sec-collect` | SEC Filing Collector | Queries sec-api.io for 10-K, 10-Q, 8-K filings. Section extraction: business (§1), risk_factors (§1A), MD&A (§7), market_risk (§7A). Targets ~35 public companies. `tools/sec_filings/collector.py` + `sec_client.py`. |
| `earn-collect` | Earnings Collector | API Ninjas-based. Iterates year/quarter combos per company. Parses participants list, transcript sections with speaker attribution (CEO, CFO, analyst). `tools/earnings/collector.py`. |

**Center — AI Extraction**:
| Node ID | Label | Node Detail |
|---------|-------|-------------|
| `sec-extract` | SEC Nugget Extractor | Claude Sonnet 4.5. Extracts 15-30 nuggets per filing. Nugget types: competitive_disclosure, risk_admission, forward_guidance, regulatory_exposure, material_change, market_condition. Themes tied to business segments (construction_products, performance_coatings, consumer_group). Cost: ~$0.20-0.60/filing. `ingestion/sec_filings/nugget_extractor.py` (487 lines). |
| `earn-extract` | Earnings Quote Extractor | Claude Haiku 3.5 (cost-optimized). Extracts 8-15 quotes per transcript. Categories: competitive_intelligence, production_rates, raw_materials, pricing, strategic_initiatives, analyst_pressure_points. Composites/aerospace/wind/marine/automotive focus. Cost: ~$0.02-0.05/transcript. `ingestion/earnings/quote_extractor.py` (484 lines). |

**Right — Storage + Downstream**:
| Node ID | Label | Node Detail |
|---------|-------|-------------|
| `bq-sec-filings` | `sec_filings` table | Filing metadata: company, filing_type, date, CIK, extracted sections. |
| `bq-sec-nuggets` | `sec_filing_nuggets` table | Extracted nuggets: nugget_type, signal_strength, theme, disclosure_text, company_context. Queried by `search_sec_nuggets` MCP tool. |
| `bq-earn-quotes` | `earnings_quotes` table | Executive quotes: speaker, speaker_role, quote_type, theme, strategic_relevance, verbatim_text. Queried by `search_earnings_quotes` MCP tool. |
| `downstream-briefing` | Voice Enrichment → Briefings | SEC nuggets + earnings quotes are pre-fetched as "voice enrichment" data injected into the weekly briefing Agent 2 prompt. This gives the executive synthesizer direct executive quotes and disclosure context to reference. |
| `downstream-research` | → Deep Research Agents | Financial Research agent calls `search_earnings_quotes` and `search_sec_nuggets` tools to find company-specific intelligence during Deep Research workflows. |

---

### 2.4 Section C: Expert Podcast Intelligence

**Narrative**: "Industry podcast episodes are discovered via RSS, transcribed through a multi-resolver chain, then processed by an LLM to extract speaker-attributed expert quotes relevant to the composites supply chain."

#### Nodes:

| Node ID | Label | Node Detail |
|---------|-------|-------------|
| `pod-rss` | Podcast RSS Discovery | RSS feed parsing with `httpx`. Discovers new episodes from configured podcast feeds (`C1_PODCAST_FEEDS`). Deduplicates against BigQuery `podcast_episodes` table by GUID. `ingestion/podcasts/discovery.py`. |
| `pod-resolve` | Transcript Resolution Chain | 3-resolver waterfall: (1) YouTube transcript API (free, fast), (2) Site-specific scraper (show notes), (3) AssemblyAI (paid, highest quality, speaker diarization). Quality-gated: falls through to next resolver if quality insufficient. `ingestion/podcasts/resolvers/chain.py`. |
| `pod-extract` | Quote Extraction | Claude Sonnet 4.5. Chunked processing (30K char chunks + 3K overlap for context continuity). Composites industry theme taxonomy. Speaker diarization healing (fixes ASR speaker label drift). Deduplication via SequenceMatcher. Extracts: speaker, role, verbatim quote, theme, strategic_relevance, companies_mentioned. `ingestion/podcasts/quote_extractor.py` (508 lines). |
| `bq-pod-episodes` | `podcast_episodes` table | Episode metadata + full transcript text. |
| `bq-pod-quotes` | `podcast_quotes` table | Speaker-attributed quotes. Queried by `search_podcast_quotes` MCP tool. |
| `pod-downstream` | → Industry Research Agent | Industry Research agent calls `search_podcast_quotes` during Deep Research to surface expert perspective on market topics. Also injected as voice enrichment into weekly briefings. |

#### Edges:
- `pod-rss` → `pod-resolve` → `pod-extract` → `bq-pod-episodes` + `bq-pod-quotes`
- `bq-pod-quotes` → `pod-downstream`

---

### 2.5 Section D: ImportYeti Supply Chain Network

**Narrative**: "Trade-level import/export data is ingested from ImportYeti to map the competitive supply chain network. A 4-phase pipeline resolves companies, discovers suppliers and downstream buyers, and builds a queryable network graph in BigQuery."

#### Nodes:

| Node ID | Label | Node Detail |
|---------|-------|-------------|
| `iy-config` | Competitor Config | `competitors.json` defines the tracked entity set (C1 Composites One + competitors). Each entry has name, aliases, and optional ImportYeti slug. |
| `iy-phase1` | Phase 1: RESOLVE | Search ImportYeti for each entity name, find best match by `totalShipments`, store resolved company in BigQuery `iy_companies` table. `ingestion/importyeti/ingestion.py`. |
| `iy-phase2` | Phase 2: COMPANIES | Pull full company profiles from ImportYeti. Extract `suppliers_table` (overseas manufacturers). Batch-insert suppliers into `iy_suppliers` + create `imports_from` edges in `iy_edges`. |
| `iy-phase3` | Phase 3: SUPPLIERS | Pull full supplier profiles. Extract `companies_table` (downstream US buyers). Batch-insert discovered buyers + create `supplies_to` edges. Discovers competitors' customer networks. |
| `iy-phase4` | Phase 4: STATS | Summary report: companies resolved, suppliers discovered, edges created, total shipments mapped. |
| `iy-client` | ImportYeti API Client | `search_company()`, `get_company()`, `search_supplier()`, `get_supplier()`. Retry logic, rate limiting, credit tracking. `ingestion/importyeti/client.py`. |
| `bq-iy-companies` | `iy_companies` table | US importers: name, slug, total_shipments, address, resolved_at. |
| `bq-iy-suppliers` | `iy_suppliers` table | Overseas exporters/manufacturers: name, country, shipment counts. |
| `bq-iy-edges` | `iy_edges` table | Directional relationships: source → target, edge_type (imports_from / supplies_to), shipment_count, period. |
| `bq-iy-log` | `iy_ingestion_log` | Audit trail per pipeline run. |
| `iy-views` | Analytical Views (5) | Pre-computed BigQuery views: `iy_v_shared_suppliers` (suppliers serving 2+ competitors), `iy_v_shared_suppliers_12m` (12-month active), `iy_v_exclusive_suppliers` (single-competitor suppliers), `iy_v_competitor_activity_12m` (per-company summary), `iy_v_buyer_overlap` (buyers in 2+ networks). |

#### Edges:
- `iy-config` → `iy-phase1` → `iy-phase2` → `iy-phase3` → `iy-phase4`
- `iy-phase1` ↔ `iy-client` (bidirectional, API calls)
- `iy-phase2` ↔ `iy-client`
- `iy-phase3` ↔ `iy-client`
- `iy-phase2` → `bq-iy-companies`, `bq-iy-suppliers`, `bq-iy-edges`
- `iy-phase3` → `bq-iy-suppliers`, `bq-iy-edges`
- `bq-iy-edges` → `iy-views`
- `iy-views` → (label: "Supply Network Tab") — feeds the frontend Supply Network visualization

---

## 3. Tab 2 — Frontend Data Architecture

**Narrative**: "Each frontend tab is backed by specific BigQuery tables, API endpoints, and data transformations. This view shows the mapping from stored data → API → frontend component."

### 3.1 Layout

One node per frontend tab (left column), connected to the BigQuery tables and services that feed it (right column). Each tab node click reveals:
- What API endpoint(s) it calls
- What BigQuery table(s) are queried
- What transformations/aggregations happen
- Key React hooks and components involved

### 3.2 Tab → Data Mapping Nodes

| Tab Node | Label | Data Sources (click detail) |
|----------|-------|-----------------------------|
| `tab-pulse` | **The Brief (Pulse)** | **Tables**: `digest_items`, `weekly_briefings`, `pre_briefings`, `article_tags`, `adhoc_briefings`. **API**: `GET /api/digest?hours=168&limit=100`, `GET /api/briefings/weekly/latest`. **Components**: `PulseDashboard`, `WeeklyBriefingSection`, `PodcastModal`, `AdHocBriefing`, `EntityAggregator`. **Hooks**: `useDigest()`, `useBriefing()`. **Key feature**: Entity heat map (tag frequency → opacity), weekly briefing with inline company logos (`[[Company]]` → Logo.dev), podcast audio player (GCS mp3), ad-hoc follow-up questions (max 2 then Deep Research redirect). **Cache**: 15-min TTL on digest queries. |
| `tab-discovery` | **Market (Discovery)** | **Tables**: `digest_items`, `article_tags`. **API**: `GET /api/digest?hours=720&limit=500&priorities=Critical,High,Medium`. **Components**: `DiscoveryView`, feed cards with category/priority badges. **Key feature**: 30-day lookback, filterable by category and priority, AI-generated discovery summaries per category. |
| `tab-research` | **Research (Deep)** | **Tables**: `deep_research_reports`, `article_chunk_embeddings`, `earnings_quotes`, `sec_filing_nuggets`, `podcast_quotes`, `article_images`. **API**: `POST /api/deep-research/stream` (SSE). **Components**: `ResearchDashboard` (400px emerald chat + results canvas), `ResearchProgress` (6-node pipeline visualization), `ResearchCanvas`, `ResearchReport` (block-based layout), `SavedReportsPanel`. **Hooks**: `useDeepResearch()`. **Key feature**: Real-time SSE streaming showing each agent's progress, parallel execution indicator (Financial + Industry + Visual), saved report history with 24h BigQuery cache, groomer clarifying questions. |
| `tab-pipeline` | **Pipeline** | **Tables**: BigQuery corpus + external APIs (Exa.ai, Apollo.io). **API**: `POST /api/pipeline/query`. **Components**: `PipelineDashboard`, `SearchBlockCard`. **Hooks**: `usePipeline()`. **Key feature**: Two modes — Instant (~350ms, 12 tools) and Full (1-5 min, 13 tools, requires CONFIRM). 12 MCP tools: Exa search (4), Apollo firmographic (5), BigQuery corpus (3). Post-enrichment filtering by revenue, employees, geography, industry. SearchBlocks for visual results + chat insights for corpus findings. |
| `tab-supply` | **Supply Network** | **Tables**: `iy_companies`, `iy_suppliers`, `iy_edges`, analytical views. **API**: `GET /api/supply-network/graph`. **Components**: `SupplyNetworkDashboard` (dynamic import — heavy component). **Key feature**: Interactive force-directed graph visualization of supply chain relationships. Shared supplier detection, competitor overlap analysis. |
| `tab-industries` | **Industries** | **Tables**: `digest_items` (filtered by industry), `article_tags`. **API**: `GET /api/digest` with industry filter. **Components**: `IndustriesDashboard`. **Key feature**: Narrative timeline per industry vertical. AI-generated summaries showing industry evolution over time. |
| `tab-prefs` | **Data & Prefs** | **Tables**: `user_preferences`, `org_preferences`. **API**: `GET/POST /api/preferences`. **Components**: `DataPreferencesDashboard`, `PreferencesPanel` (priority/blocked topic management). **Key feature**: Manage tracked companies, priority topics, blocked topics. Affects content filtering across all tabs. |

### 3.3 Google Cloud Platform Infrastructure Layer

> **Design intent**: This is the crown jewel of the Architecture tab for any Google (or cloud-forward) hiring manager. Render as a **dedicated "Google Cloud Platform" banner strip** across the bottom of the Tab 2 diagram. Use official GCP-branded styling — Google Blue (#4285F4) accent borders, hexagonal or rounded-rectangle nodes with the Google Cloud icon watermark. Each node should feel like a real infrastructure block, visually distinct from application-layer nodes above. A GCP-branded section header reading **"Google Cloud Platform — us-central1"** ties the layer together.
>
> **What this communicates**: "I design production systems on real cloud infrastructure with proper IAM, CI/CD, serverless compute, managed ML, and operational observability — not a local Flask prototype."

The platform runs **10 GCP services** across compute, data, ML, storage, CI/CD, security, and operations:

#### Tier 1 — Core Runtime (top row of GCP strip)

| Node | Label | Icon | Detail |
|------|-------|------|--------|
| `gcp-cloudrun` | **Cloud Run** | Container | Serverless container runtime (gen2 execution environment). Service: `c1-hub`, region: `us-central1`. **2 vCPU, 2 GiB memory**, auto-scales 0→10 instances, CPU boost enabled, no CPU throttling. 3600s max request timeout (long-running research workflows). Zero always-on instances — pure pay-per-request serverless. Serves the full-stack app: FastAPI backend + statically-exported Next.js frontend in a single container. |
| `gcp-bigquery` | **BigQuery** | Database/warehouse | Serverless analytics data warehouse — **the sole database** for the entire platform (no Postgres, no Redis, no SQLite). Dataset: `c1_intelligence` with 20+ tables covering articles, digest items, SEC filings, earnings, podcasts, supply chain, embeddings, briefings, and more. Native `VECTOR_SEARCH` with IVF index for semantic search. Auto-scales from bytes to petabytes. Project: `gen-lang-client-0436975498`. |
| `gcp-vertexai` | **Vertex AI** | Brain/ML | Google's managed ML platform. Provides `text-embedding-004` model (768-dimensional embeddings). Called during ingestion to vectorize article chunks → stored in BigQuery `article_chunk_embeddings` table. Powers semantic similarity search across the entire intelligence corpus via BigQuery `VECTOR_SEARCH`. Graceful fallback to local `sentence-transformers` (384-dim) if Vertex API unavailable. Initialized via `aiplatform.init(project=..., location='us-central1')`. |
| `gcp-gcs` | **Cloud Storage (GCS)** | Bucket | Bucket: `gen-lang-client-0436975498-c1-hub-data`. Dual-mode usage: **(1) GCS FUSE volume mount** on Cloud Run at `/app/data` for persistent file storage (knowledge DB, downloads) with 30-day lifecycle auto-delete. **(2) Direct GCS API** for uploading podcast MP3s (`/podcasts/{briefing_id}.mp3`) and serving via public URLs to the frontend audio player. |

#### Tier 2 — Automation & CI/CD (middle row of GCP strip)

| Node | Label | Icon | Detail |
|------|-------|------|--------|
| `gcp-scheduler` | **Cloud Scheduler** | Clock | Cron-as-a-service orchestrating the entire automated data pipeline. Fires authenticated HTTP POST requests (OIDC tokens) to Cloud Run endpoints. Jobs: `orchestrator-ingestion-morning` + `evening` (twice-daily article ingestion), `collect-stock-news` (4h), `collect-tavily-news` (6h), `collect-rss-feeds` (6h), `weekly-executive-briefing` (Mon 8:30 AM), `weekly-cleanup`, `importyeti-ingestion`. Uses dedicated `scheduler-invoker` service account with `roles/run.invoker`. |
| `gcp-cloudbuild` | **Cloud Build** | CI/CD | Fully automated CI/CD pipeline. Trigger: `git push origin master` → GitHub webhook → Cloud Build. Steps: (1) Docker build from `Dockerfile.prod`, (2) Push to **Artifact Registry**, (3) Deploy to **Cloud Run** with secret injection. Machine: `E2_HIGHCPU_8`, timeout 1800s, `CLOUD_LOGGING_ONLY`. ~3-5 minute full push-to-production cycle. |
| `gcp-artifact` | **Artifact Registry** | Package | Docker container image registry. Repository: `us-central1-docker.pkg.dev/.../c1-intelligence-hub/`. Stores versioned + `latest` tagged production images. Cloud Build pushes here; Cloud Run pulls from here. Replaces legacy Container Registry. |

#### Tier 3 — Security & Operations (bottom row of GCP strip)

| Node | Label | Icon | Detail |
|------|-------|------|--------|
| `gcp-secretmgr` | **Secret Manager** | Key/lock | Centralized secrets vault. Stores 13 API keys: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `FMP_API_KEY`, `API_NINJA_KEY`, `TAVILY_API_KEY`, `EXA_API_KEY`, `LOGO_DEV_TOKEN`, `STOCKNEWS_API_KEY`, `SEC_IO_KEY`, `APOLLO_API_KEY`, `ASSEMBLYAI_API_KEY`, `ELEVENLABS_API_KEY`, `IMPORTYETI_API_KEY`. Mounted as env vars in Cloud Run via `cloudbuild.yaml --set-secrets` at deploy time. Versioned secrets with automatic rotation support. |
| `gcp-iam` | **Cloud IAM** | Shield | Identity & Access Management governing cross-service permissions. 3 service accounts: **(1)** Default compute SA → `roles/bigquery.dataEditor`, `roles/bigquery.jobUser`, `roles/storage.objectAdmin`, `roles/secretmanager.secretAccessor`. **(2)** Cloud Build SA → `roles/run.admin`, `roles/iam.serviceAccountUser`. **(3)** `scheduler-invoker` SA → `roles/run.invoker` (least-privilege for Scheduler→Cloud Run auth). Principle of least privilege throughout. |
| `gcp-logging` | **Cloud Logging** | Monitor | Structured application logging and operational observability. All Cloud Run `structlog` output streams to Cloud Logging. Used for: monitoring ingestion pipeline status, debugging scheduler failures, verifying briefing generation, tracking API latency. Queried via `gcloud logging read` in monitoring scripts (`scripts/monitoring/scheduler_report.py`). Cloud Build logs also captured here. |

### 3.4 Shared Application Layer Nodes (Middle Row)

| Node | Label | Detail |
|------|-------|--------|
| `api-layer` | FastAPI Backend | Python FastAPI server deployed on **Cloud Run** (gen2). Single `main.py` entry point. Routes organized in `api/routes/`. RESTful + SSE streaming endpoints. Structured logging via `structlog` → **Cloud Logging**. |
| `bq-client` | BigQuery Client | `BigQueryDataStorage` singleton. 15-min query cache. Handles all CRUD operations against the **BigQuery** dataset. Authenticated via default compute SA (**Cloud IAM**). |
| `vector-store` | Vector Store | `BigQueryVectorStore` — uses **Vertex AI** embeddings (768-dim) with **BigQuery** native `VECTOR_SEARCH`. IVF index for fast approximate nearest-neighbor. Used by Deep Research, ad-hoc briefing, and pipeline agents. |
| `gcs-client` | GCS Client | Reads/writes podcast MP3s and assets to **Cloud Storage** bucket. Also manages GCS FUSE mount for persistent file access on Cloud Run. |

### 3.5 Edges

**Application → Infrastructure:**
- Each `tab-*` node → `api-layer` → `bq-client` → `gcp-bigquery`
- `tab-research` → `vector-store` → `gcp-vertexai` (embedding generation) + `gcp-bigquery` (vector search)
- `tab-pulse` → `gcs-client` → `gcp-gcs` (podcast audio)
- `api-layer` runs on `gcp-cloudrun`
- `api-layer` → `gcp-logging` (structured logs)

**GCP Service Mesh (infrastructure-to-infrastructure):**
- `gcp-scheduler` → `gcp-cloudrun` (OIDC-authenticated HTTP triggers)
- `gcp-cloudbuild` → `gcp-artifact` (push Docker images)
- `gcp-artifact` → `gcp-cloudrun` (pull images on deploy)
- `gcp-cloudbuild` → `gcp-cloudrun` (deploy new revisions)
- `gcp-secretmgr` → `gcp-cloudrun` (env var injection at deploy)
- `gcp-iam` → `gcp-cloudrun`, `gcp-bigquery`, `gcp-gcs`, `gcp-secretmgr` (permission grants — render as dotted lines)
- `gcp-logging` ← `gcp-cloudrun`, `gcp-cloudbuild` (log ingestion — render as dashed lines)

---

## 4. Tab 3 — Agentic Workflows

### 4.1 Layout: Two Sections

```
┌─────────────────────────────────────────────────────────────────────────┐
│  SECTION A: Weekly Executive Briefing (2-Agent Pipeline + Podcast)       │
├─────────────────────────────────────────────────────────────────────────┤
│  SECTION B: Deep Research Multi-Agent System (7-Node LangGraph)          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Section A: Weekly Executive Briefing Pipeline

**Narrative**: "Every Monday at 8:30 AM, a 2-agent pipeline generates an executive intelligence briefing. Agent 1 analyzes recent articles to identify strategic signals. Agent 2 synthesizes those signals with historical context, voice enrichment (exec quotes, SEC disclosures, podcast insights), and peripheral web intelligence into a polished report — then generates an audio podcast."

#### Nodes:

| Node ID | Label | Node Detail |
|---------|-------|-------------|
| `brief-trigger` | Cloud Scheduler | `weekly-executive-briefing` job fires Monday 8:30 AM CST → `POST /api/v1/scheduler/briefing`. |
| `brief-data` | Input: 14-Day Digest | Fetches all Medium/High/Critical priority `digest_items` from the last 14 days. Batched into groups of ~40 to prevent context window overflow. |
| `brief-agent1` | **Agent 1: Pre-Brief Generator** | Claude Sonnet 4.5. Analyzes batches of recent articles. Produces structured observations: category, signal_type (net_new / evolution / stalled), confidence_score, supporting_articles. Categories: Suppliers & Competitors, End Customers & OEMs, Materials & Products, Supply Chain. Merge prompt deduplicates across batches. Output: `pre_briefing` JSON. `ingestion/generators/pre_briefing.py` (480 lines). |
| `brief-voice` | Voice Enrichment | Pre-fetches 3 types of "voice" data from BigQuery to inject into Agent 2's prompt: (1) Recent `sec_filing_nuggets` — competitive disclosures, risk admissions, (2) Recent `earnings_quotes` — executive commentary on markets, (3) Recent `podcast_quotes` — industry expert perspectives. These give the synthesizer direct quotes to cite. |
| `brief-history` | Historical Context | Loads prior weekly briefings. Provides: BLUF, section headlines with net_new/continuing status, key companies, overall trend. Enables accurate differential analysis (Agent 2 knows what was covered before). |
| `brief-agent2` | **Agent 2: Executive Synthesizer** | Claude Opus 4.5 (most capable model). Receives: pre-brief JSON + historical context + voice enrichment. Has access to `search_peripheral_intelligence` tool (Exa, max 3 calls) for adjacent intelligence. Produces: 3-4 strategic sections, each with headline, net_new/continuing badge, narrative with inline citations `[N]`, company logos `[[Company]]`, entity highlights `{{Entity}}`. Plus: BLUF (single-sentence executive summary), overall_trend, source_articles array. Citation cleanup: renumbers `[37]`, `[Exa:6]` to sequential `[1]`, `[2]`. `ingestion/generators/weekly_briefing.py` (1,771 lines). |
| `brief-podcast` | Podcast Generation | 3-step audio pipeline: (1) **Scaffold**: Deterministic conversation structure from briefing JSON. (2) **Naturalize**: Claude Sonnet rewrites into natural dialogue — "$2.4B" → "2.4 billion dollars", abbreviations expanded, "net new" vs "continuing" phrasing. (3) **ElevenLabs TTS**: Text-to-Dialogue API with Host (Rachel) + Analyst (Josh) voices. Output: 4-6 minute MP3 uploaded to GCS `/podcasts/{briefing_id}.mp3`. |
| `brief-store` | Storage | `pre_briefings` table (Agent 1 output), `weekly_briefings` table (Agent 2 output + BLUF), GCS bucket (podcast MP3). |

#### Edges:
- `brief-trigger` → `brief-data`
- `brief-data` → `brief-agent1`
- `brief-agent1` → `brief-agent2`
- `brief-voice` → `brief-agent2` (injected context)
- `brief-history` → `brief-agent2` (injected context)
- `brief-agent2` → `brief-podcast` → `brief-store`
- `brief-agent2` → `brief-store`

---

### 4.3 Section B: Deep Research Multi-Agent System

**Narrative**: "A 7-node LangGraph workflow orchestrates parallel research agents to produce comprehensive intelligence reports in 45-90 seconds. The system includes query grooming with clarification, parallel financial/industry/visual research, block-based report synthesis, and automated citation validation."

#### Nodes:

| Node ID | Label | Node Detail |
|---------|-------|-------------|
| `dr-input` | User Query | User types a research question in the Research tab chat. SSE streaming begins immediately. |
| `dr-groomer` | **Groomer Agent** | Claude Haiku 3.5 (fast, cheap). Interprets query intent. Generates optimized sub-queries for Financial and Industry agents. Injects prior research context from `ResearchMemory` (two-tier cache: in-memory 1h + BigQuery 24h) to avoid redundant clarifying questions. Decides if clarification needed (threshold: ready >95%). If NEEDS_CLARIFICATION (max 2 rounds), emits SSE event and waits for user input. `agents/research/groomer.py` (658 lines). |
| `dr-fanout` | Parallel Fan-Out | LangGraph `Send` API dispatches 3 agents simultaneously. Zero sequential waiting — all 3 start at the same time. Frontend shows parallel execution indicator. |
| `dr-financial` | **Financial Research Agent** | Claude Opus 4.5. Tools: `search_earnings_quotes` (BigQuery), `search_sec_nuggets` (BigQuery), `query_corpus` (vector search), StockNews API (company news, press releases, analyst ratings, sentiment analysis). Conditional tool gating: external earnings API only called when user mentions specific companies (corpus always runs). Ticker resolution from master company list. ~30 seconds. `agents/research/financial.py` (738 lines). |
| `dr-industry` | **Industry Research Agent** | Claude Opus 4.5. Tools: Exa search (news, web, similar pages — uses composites trade publication domain list), `query_corpus`, `get_market_signals`, Google Trends, StockNews keyword search, `get_freight_rates`, `search_podcast_quotes`. Covers macro trends, market dynamics, industry signals. ~30 seconds. `agents/research/industry.py` (685 lines). |
| `dr-visual` | **Visual Research Agent** | Claude Sonnet 4.5. Searches `article_images` BigQuery table for relevant charts, graphs, and data visualizations. LLM-based ranking and caption generation. ~10-15 seconds (finishes before other agents). Graceful degradation if no relevant visuals found. `agents/research/visual.py` (442 lines). |
| `dr-fanin` | Fan-In (State Merge) | LangGraph reducer architecture merges parallel agent outputs. Reducer annotations: `_keep_first()` for immutable fields, `_keep_last()` for outputs, `_merge_errors()` for error lists. Handles state merge from 3 parallel branches. `agents/research/state.py` (395 lines). |
| `dr-synth` | **Synthesizer Agent** | Claude Opus 4.5 with Extended Thinking support. Produces block-based narrative: paragraph blocks, metric_grid blocks, visual_split blocks, quote blocks. 12-word max headlines. 2-3 sections max. Inline company logos (`[[Company]]`). Sequential numbered citations. Normalizes LLM enum values. `agents/research/synthesizer.py` (812 lines). |
| `dr-validator` | **Validator Agent** | Citation verification: checks that `[N]` references correspond to actual findings. Flags unsubstantiated claims. Adjusts confidence levels. Pass criteria: <3 errors, <5 unsubstantiated claims, >80% citations valid. `agents/research/validator.py` (359 lines). |
| `dr-output` | Report Output | Block-based report rendered in `ResearchCanvas`. SSE events: `node_start`, `node_complete`, `tool_progress`, `category`, `validation`, `warnings`, `report_saved`. Automatic persistence to `deep_research_reports` BigQuery table. |

#### Edges:
- `dr-input` → `dr-groomer`
- `dr-groomer` → `dr-fanout` (if ready) OR → `dr-input` (if clarification needed, max 2 rounds)
- `dr-fanout` → `dr-financial` + `dr-industry` + `dr-visual` (parallel, shown with parallel edge style)
- `dr-financial` → `dr-fanin`
- `dr-industry` → `dr-fanin`
- `dr-visual` → `dr-fanin`
- `dr-fanin` → `dr-synth`
- `dr-synth` → `dr-validator`
- `dr-validator` → `dr-output`

#### SSE Progress Overlay (toggle-able):
Show real-time SSE events that the frontend receives during execution:
- `node_start: groomer` → `node_complete: groomer`
- `node_start: financial_research` + `node_start: industry_research` + `node_start: visual_research` (parallel)
- Individual `tool_progress` events within each agent (e.g., "Searching earnings quotes for HEXCEL...")
- `node_complete: financial_research`, `node_complete: industry_research`, `node_complete: visual_research`
- `node_start: synthesizer` → `node_complete: synthesizer`
- `node_start: validator` → `node_complete: validator`
- `report_saved: {report_id}`

---

## 5. Interaction Design

### 5.1 Node Click → Detail Panel

When a user clicks any node in the graph:
1. The node highlights (border glow or background shift)
2. A **detail panel** slides in from the right (or bottom on mobile)
3. The panel shows:
   - **Title**: Node label
   - **Description**: 2-3 sentence narrative explanation (from "Node Detail" column above)
   - **Technical Details** (collapsible):
     - Source file path(s) with line counts
     - Key function/class names
     - Model used (if LLM node)
     - API(s) called (if external service node)
     - BigQuery table(s) read/written
   - **Connections**: List of incoming/outgoing edges with their labels
4. Clicking outside the panel or pressing Escape closes it

### 5.2 Node Visual Design

| Node Type | Color | Shape | Examples |
|-----------|-------|-------|----------|
| Data Source | Blue-500 | Rounded rectangle | RSS, Exa, Tavily, SEC |
| Processing Step | Amber-500 | Rectangle | Dedup, Classifier, Embedder |
| AI Agent | Emerald-500 | Rounded rectangle with brain icon | Agent 1, Agent 2, Groomer, Financial |
| Storage (BigQuery) | Violet-500 | Cylinder/database shape | articles, digest_items |
| Storage (GCS) | Indigo-400 | Cloud shape | Podcast MP3s |
| External API | Slate-400 | Dashed border rectangle | ElevenLabs, Logo.dev |
| Scheduler/Trigger | Orange-400 | Diamond | Cloud Scheduler jobs |
| Fan-out/Fan-in | Gray-300 | Small circle | Parallel dispatch/merge |

### 5.3 Edge Visual Design

| Edge Type | Style | Examples |
|-----------|-------|----------|
| Data flow | Solid line, animated dots | Source → Orchestrator |
| Parallel execution | Dashed line, same color group | Fan-out → 3 agents |
| LLM call | Gradient line (green) | Agent → Synthesizer |
| API call | Dotted line | Node → External API |
| Storage write | Solid thick line | Processing → BigQuery |

### 5.4 Section Headers

Each section has a colored header bar with:
- Section letter (A, B, C, D)
- Section title
- One-line description
- Collapse/expand toggle

---

## 6. Implementation Notes

### 6.1 Recommended Library: React Flow

**Why React Flow** (`reactflow` npm package):
- Purpose-built for node-and-edge diagrams in React
- Built-in pan/zoom, drag, minimap
- Custom node components (we can style with Tailwind)
- Edge labels and animations
- Handles large graphs efficiently
- Well-maintained, MIT licensed
- Works with Next.js and SSR (use dynamic import with `{ ssr: false }`)

**Alternative considered**: Mermaid.js — too static, no click interaction, limited styling.

**Installation**: `npm install reactflow`

### 6.2 Frontend File Structure

```
frontend/src/components/architecture/
├── ArchitectureDashboard.tsx        # Main container with 3 sub-tabs
├── IngestionFlowDiagram.tsx         # Tab 1: React Flow diagram
├── TabArchitectureDiagram.tsx       # Tab 2: React Flow diagram
├── AgenticWorkflowDiagram.tsx       # Tab 3: React Flow diagram
├── nodes/
│   ├── DataSourceNode.tsx           # Custom node: data sources
│   ├── ProcessingNode.tsx           # Custom node: processing steps
│   ├── AgentNode.tsx                # Custom node: AI agents
│   ├── StorageNode.tsx              # Custom node: BigQuery tables
│   ├── SchedulerNode.tsx            # Custom node: scheduler triggers
│   └── FanOutNode.tsx               # Custom node: parallel dispatch
├── DetailPanel.tsx                  # Right-side detail panel
├── SectionHeader.tsx                # Colored section header bars
├── data/
│   ├── ingestionNodes.ts            # Node definitions for Tab 1
│   ├── ingestionEdges.ts            # Edge definitions for Tab 1
│   ├── tabArchitectureNodes.ts      # Node definitions for Tab 2
│   ├── tabArchitectureEdges.ts      # Edge definitions for Tab 2
│   ├── agenticNodes.ts              # Node definitions for Tab 3
│   └── agenticEdges.ts              # Edge definitions for Tab 3
└── types.ts                         # Shared types for architecture diagrams
```

### 6.3 Registration Steps

1. **Add mode to types**: Add `'app-architecture'` to the `Mode` union type in `frontend/src/types/index.ts`
2. **Add sidebar item**: Add entry to `navItems` in `Sidebar.tsx` with `Cpu` icon and label "Architecture"
3. **Add page rendering**: Add `{activeMode === 'app-architecture' && <ArchitectureDashboard />}` to `page.tsx`
4. **Dynamic import**: Use `next/dynamic` with `{ ssr: false }` for React Flow components (canvas rendering requires browser DOM)

### 6.4 Responsive Considerations

- React Flow's built-in pan/zoom handles large diagrams on smaller screens
- Detail panel should be a slide-over on mobile (full-width) vs. side panel on desktop
- Consider a "fit to view" button for each section
- Mini-map in bottom-right corner for navigation

### 6.5 Dark Mode Compatibility

The app uses Tailwind dark mode. Node colors should use Tailwind's color scale and respect `dark:` variants. React Flow supports custom themes.

---

## 7. Session Execution Plan

This is a multi-phase build. Each phase is a single AI coding session that produces a working, committable, deployable result.

---

### Phase 1: Scaffolding + Tab 1 Section A (Core Ingestion) ✅
**Status**: ✅ Complete
**Estimated effort**: 1 session

This is the heaviest phase — it builds ALL reusable infrastructure (custom nodes, detail panel, types, dashboard shell). Phases 2-4 are primarily data entry using these components.

**Tasks**:
1. Install `@xyflow/react` dependency (formerly `reactflow`)
2. Add `'app-architecture'` mode to `Mode` type + sidebar nav item
3. Create `ArchitectureDashboard.tsx` with 3 sub-tab navigation
4. Create all 6 custom node components (DataSourceNode, ProcessingNode, AgentNode, StorageNode, SchedulerNode, FanOutNode)
5. Create `DetailPanel.tsx` (right-side slide-in on node click)
6. Create `SectionHeader.tsx`
7. Create shared types file (`types.ts`)
8. Build Tab 1 Section A (Core Ingestion) — all nodes, edges, and detail data:
   - 10 data source nodes → orchestrator → 6 processing nodes → 5 storage nodes → 3 post-storage nodes
9. Wire into `page.tsx`
10. Test: tab renders, nodes interactive, detail panel works

**Deliverable**: Architecture tab visible in app. Tab 1 shows Core Ingestion flow with click-to-detail. All reusable components built.

---

### Phase 2: Tab 1 Sections B, C, D ✅
**Status**: ✅ Complete
**Estimated effort**: 1 session (lighter — mostly node/edge data using Phase 1 components)

**Tasks**:
1. Add Section B nodes/edges (SEC Filings & Earnings Transcripts)
2. Add Section C nodes/edges (Expert Podcast Intelligence)
3. Add Section D nodes/edges (ImportYeti Supply Chain Network)
4. Add section collapse/expand toggles
5. Add scheduler overlay (toggle-able layer)
6. Polish layout and spacing

**Deliverable**: Tab 1 complete with all 4 sections.

---

### Phase 3: Tab 2 — Frontend Data Architecture + GCP Infrastructure Layer ✅
**Status**: ✅ Complete
**Estimated effort**: 1 session

**Tasks**:
1. Create `TabArchitectureDiagram.tsx`
2. Build tab → API → BigQuery mapping diagram (7 frontend tabs as nodes)
3. Add detail data for each tab's data sources, APIs, hooks, components
4. Add shared application layer nodes (FastAPI, BigQuery Client, Vector Store, GCS Client)
5. Build GCP Infrastructure strip — the "crown jewel" for hiring managers:
   - 10 GCP service nodes across 3 tiers (Core Runtime, Automation/CI/CD, Security/Ops)
   - GCP-branded styling (Google Blue accents, hexagonal nodes)
   - Service mesh edges (Scheduler→Cloud Run, Build→Artifact→Run, etc.)
6. Polish edge routing and labels

**Deliverable**: Tab 2 complete — frontend data architecture + full GCP infrastructure visualization.

---

### Phase 4: Tab 3 — Agentic Workflows + Final Polish
**Status**: ✅ Complete
**Estimated effort**: 1 session

**Tasks**:
1. Create `AgenticWorkflowDiagram.tsx`
2. Build Section A: Weekly Briefing 2-Agent Pipeline
   - Scheduler trigger → data fetch → Agent 1 → voice enrichment → Agent 2 → podcast → storage
3. Build Section B: Deep Research 7-Node LangGraph Workflow
   - Input → Groomer → parallel fan-out (Financial + Industry + Visual) → fan-in → Synthesizer → Validator → Output
4. Add parallel fan-out/fan-in visual treatment
5. Add SSE progress overlay (toggle-able)
6. Add groomer clarification loop visual
7. Final polish across all 3 tabs (animations, dark mode, responsive)
8. Commit and deploy

**Deliverable**: Full Architecture tab complete and deployed. All 3 sub-tabs fully interactive.

---

## 8. Data Reference Tables

### 8.1 All BigQuery Tables

| Table | Dataset | Primary Purpose | Fed By | Consumed By |
|-------|---------|-----------------|--------|-------------|
| `articles` | c1_intelligence | Raw article storage | Orchestrator | Digest generator, embeddings |
| `digest_items` | c1_intelligence | Classified articles | Classifier | Pulse, Discovery, Briefings |
| `article_tags` | c1_intelligence | Tag analytics | Entity linker | Pulse heat map, Discovery |
| `article_chunk_embeddings` | c1_intelligence | Vector search | Embedding pipeline | Deep Research, Ad-hoc, Pipeline |
| `article_images` | c1_intelligence | Classified images | Image enrichment | Visual Research agent |
| `weekly_briefings` | c1_intelligence | Weekly reports | Agent 2 synthesizer | Pulse tab |
| `pre_briefings` | c1_intelligence | Pre-brief data | Agent 1 pre-brief | Agent 2 input |
| `adhoc_briefings` | c1_intelligence | On-demand briefings | Ad-hoc agent | Pulse tab |
| `deep_research_reports` | c1_intelligence | Saved research | Deep Research pipeline | Research tab, memory |
| `freight_rates` | c1_intelligence | Shipping costs | Drewry scraper | Industry Research agent |
| `sec_filings` | c1_intelligence | SEC filing metadata | SEC collector | Nugget extractor |
| `sec_filing_nuggets` | c1_intelligence | Strategic nuggets | Nugget extractor | Financial Research, Briefings |
| `earnings_quotes` | c1_intelligence | Executive quotes | Quote extractor | Financial Research, Briefings |
| `podcast_episodes` | c1_intelligence | Episode metadata | Podcast pipeline | Quote extractor |
| `podcast_quotes` | c1_intelligence | Expert quotes | Quote extractor | Industry Research, Briefings |
| `ingestion_events` | c1_intelligence | Pipeline logs | Orchestrator | Monitoring |
| `user_logins` | c1_intelligence | Auth tracking | Login API | Analytics |
| `iy_companies` | c1_intelligence | US importers | ImportYeti Phase 1-2 | Supply Network tab |
| `iy_suppliers` | c1_intelligence | Overseas exporters | ImportYeti Phase 2-3 | Supply Network tab |
| `iy_edges` | c1_intelligence | Trade relationships | ImportYeti Phase 2-3 | Supply Network tab, views |
| `iy_ingestion_log` | c1_intelligence | IY audit trail | ImportYeti pipeline | Monitoring |

### 8.2 LLM Models Used

| Model | Use Cases | Cost Tier |
|-------|-----------|-----------|
| Claude Opus 4.5 | Deep Research (Financial, Industry, Synthesizer), Weekly Briefing Agent 2 | $$$ |
| Claude Sonnet 4.5 | Pre-briefing, Classification, Podcast quote extraction, SEC nugget extraction, Image vision, Visual Research | $$ |
| Claude Haiku 3.5 | Deep Research Groomer, Earnings quote extraction | $ |
| GPT-4o | Fallback for Opus/Sonnet (credit safety net) | $$ |
| GPT-4o-mini | Fallback for Haiku | $ |
| Vertex AI text-embedding-004 | Vector embeddings (768-dim) | ¢ |
| ElevenLabs TTS | Podcast audio generation (Rachel + Josh voices) | $$ |

### 8.3 External APIs

| API | Purpose | Used In |
|-----|---------|---------|
| Exa.ai | Neural web search | Orchestrator, Industry Research, Pipeline |
| Tavily | Web crawl search + image search | Orchestrator, Image Enrichment |
| sec-api.io | SEC EDGAR filing query + extraction | SEC Filing Collector |
| API Ninjas | Earnings call transcripts | Earnings Collector |
| StockNews API | Market news, analyst ratings | Orchestrator, Financial Research |
| FMP API | Premium news (Benzinga, etc.) | Orchestrator |
| Apollo.io | Firmographic enrichment, contacts | Pipeline agent |
| ImportYeti | Import/export trade data | ImportYeti pipeline |
| AssemblyAI | Audio transcription | Podcast transcript resolver |
| ElevenLabs | Text-to-speech | Podcast generation |
| Logo.dev | Company logo images | Briefing display |
| Google Trends | Search trend data | Industry Research |

### 8.4 Cloud Infrastructure

| Resource | Value |
|----------|-------|
| Cloud Run Service | `c1-hub` |
| Cloud Run URL | `https://c1-hub-4iz75bvpyq-uc.a.run.app` |
| GCP Project | `gen-lang-client-0436975498` |
| Region | `us-central1` |
| BigQuery Dataset | `c1_intelligence` |
| GCS Bucket | `gen-lang-client-0436975498-c1-hub-data` |
| CI/CD | GitHub → Cloud Build → Cloud Run |
| Scheduler Jobs | 5 jobs (see §2.2) |

---

## Appendix: Key Source Files Reference

For AI agents starting a fresh session, these are the most important files to understand:

| File | Lines | Why It Matters |
|------|-------|----------------|
| `backend/app/ingestion/orchestrator.py` | ~1800 | Core ingestion pipeline, all 10 sources |
| `backend/app/ingestion/processing/classifier.py` | ~367 | AI classification with composites taxonomy |
| `backend/app/ingestion/importyeti/ingestion.py` | ~647 | 4-phase supply chain data pipeline |
| `backend/app/ingestion/podcasts/pipeline.py` | ~288 | Podcast RSS → transcript → quotes |
| `backend/app/ingestion/sec_filings/nugget_extractor.py` | ~487 | SEC filing strategic nugget extraction |
| `backend/app/ingestion/earnings/quote_extractor.py` | ~484 | Earnings call quote extraction |
| `backend/app/ingestion/generators/pre_briefing.py` | ~480 | Agent 1: Pre-brief generation |
| `backend/app/ingestion/generators/weekly_briefing.py` | ~1771 | Agent 2: Executive synthesis + podcast |
| `backend/app/graph/research_workflow.py` | ~113 | LangGraph workflow definition |
| `backend/app/agents/research/state.py` | ~395 | Deep Research state with reducers |
| `backend/app/agents/research/groomer.py` | ~658 | Query grooming + prior context injection |
| `backend/app/agents/research/financial.py` | ~738 | Financial research agent |
| `backend/app/agents/research/industry.py` | ~685 | Industry research agent |
| `backend/app/agents/research/synthesizer.py` | ~812 | Report synthesis with block layout |
| `backend/app/agents/research/validator.py` | ~359 | Citation verification |
| `backend/app/db/gcp_storage.py` | ~4500+ | All BigQuery table schemas + CRUD |
| `frontend/src/app/page.tsx` | ~581 | Main page, tab rendering |
| `frontend/src/components/layout/Sidebar.tsx` | ~200 | Navigation tab definitions |
