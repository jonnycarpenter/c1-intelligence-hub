import type { Node } from '@xyflow/react'
import type { ArchNodeData } from '../types'

// ============================================
// Tab 2 — Frontend Data Architecture + GCP Infrastructure
// ============================================
//
// Layout columns:
//   COL_TABS     = 0      — Frontend tab nodes (left)
//   COL_APP      = 320    — Shared application layer (middle)
//   COL_GCP_T1   = 680    — GCP Tier 1 Core Runtime
//   COL_GCP_T2   = 680    — GCP Tier 2 Automation/CI-CD (below T1)
//   COL_GCP_T3   = 680    — GCP Tier 3 Security/Ops (below T2)
//
// Row spacing: ~90px per node vertically

const COL_TABS = 0
const COL_APP = 320
const COL_GCP_LEFT = 660
const COL_GCP_RIGHT = 880

// ────────────────────────────────────────────────
// Section 1: Frontend Tab Nodes (7 tabs)
// ────────────────────────────────────────────────
const tabNodes: Node<ArchNodeData>[] = [
  {
    id: 'tab-pulse',
    type: 'tabNode',
    position: { x: COL_TABS, y: 0 },
    data: {
      label: 'The Brief (Pulse)',
      nodeType: 'tabNode',
      description: 'Real-time intelligence digest with entity heat map, weekly briefing with inline company logos, podcast audio player, and ad-hoc follow-up questions.',
      icon: 'pulse',
      badge: '5 tables',
      technicalDetails: {
        tables: ['digest_items', 'weekly_briefings', 'pre_briefings', 'article_tags', 'adhoc_briefings'],
        apis: ['GET /api/digest?hours=168&limit=100', 'GET /api/briefings/weekly/latest'],
        sourceFiles: ['PulseDashboard.tsx', 'WeeklyBriefingSection.tsx', 'PodcastModal.tsx', 'AdHocBriefing.tsx', 'EntityAggregator.tsx'],
        functions: ['useDigest()', 'useBriefing()'],
      },
      connections: {
        outgoing: ['api-layer'],
      },
    },
  },
  {
    id: 'tab-discovery',
    type: 'tabNode',
    position: { x: COL_TABS, y: 90 },
    data: {
      label: 'Market (Discovery)',
      nodeType: 'tabNode',
      description: '30-day lookback of intelligence items filterable by category and priority, with AI-generated discovery summaries per category.',
      icon: 'discovery',
      badge: '2 tables',
      technicalDetails: {
        tables: ['digest_items', 'article_tags'],
        apis: ['GET /api/digest?hours=720&limit=500&priorities=Critical,High,Medium'],
        sourceFiles: ['DiscoveryView.tsx'],
      },
      connections: {
        outgoing: ['api-layer'],
      },
    },
  },
  {
    id: 'tab-research',
    type: 'tabNode',
    position: { x: COL_TABS, y: 180 },
    data: {
      label: 'Research (Deep)',
      nodeType: 'tabNode',
      description: 'Real-time SSE streaming research with parallel agent execution, block-based report synthesis, and saved report history with 24h BigQuery cache.',
      icon: 'research',
      badge: '6 tables',
      technicalDetails: {
        tables: ['deep_research_reports', 'article_chunk_embeddings', 'earnings_quotes', 'sec_filing_nuggets', 'podcast_quotes', 'article_images'],
        apis: ['POST /api/deep-research/stream (SSE)'],
        sourceFiles: ['ResearchDashboard.tsx', 'ResearchProgress.tsx', 'ResearchCanvas.tsx', 'ResearchReport.tsx', 'SavedReportsPanel.tsx'],
        functions: ['useDeepResearch()'],
      },
      connections: {
        outgoing: ['api-layer', 'vector-store'],
      },
    },
  },
  {
    id: 'tab-pipeline',
    type: 'tabNode',
    position: { x: COL_TABS, y: 270 },
    data: {
      label: 'Company Lookup',
      nodeType: 'tabNode',
      description: 'Two modes — Instant (~350ms, 12 tools) and Full (1-5 min, 13 tools, requires CONFIRM). 12 MCP tools: Exa search, Apollo firmographic, BigQuery corpus. Post-enrichment filtering.',
      icon: 'pipeline',
      badge: '12 MCP tools',
      technicalDetails: {
        apis: ['POST /api/pipeline/query'],
        sourceFiles: ['PipelineDashboard.tsx', 'SearchBlockCard.tsx'],
        functions: ['usePipeline()'],
      },
      connections: {
        outgoing: ['api-layer'],
      },
    },
  },
  {
    id: 'tab-supply',
    type: 'tabNode',
    position: { x: COL_TABS, y: 360 },
    data: {
      label: 'Supply Network',
      nodeType: 'tabNode',
      description: 'Interactive force-directed graph visualization of supply chain relationships. Shared supplier detection, competitor overlap analysis.',
      icon: 'supply',
      badge: '3 tables + views',
      technicalDetails: {
        tables: ['iy_companies', 'iy_suppliers', 'iy_edges'],
        apis: ['GET /api/supply-network/graph'],
        sourceFiles: ['SupplyNetworkDashboard.tsx'],
      },
      connections: {
        outgoing: ['api-layer'],
      },
    },
  },
  {
    id: 'tab-industries',
    type: 'tabNode',
    position: { x: COL_TABS, y: 450 },
    data: {
      label: 'Industries',
      nodeType: 'tabNode',
      description: 'Narrative timeline per industry vertical. AI-generated summaries showing industry evolution over time.',
      icon: 'industries',
      badge: '2 tables',
      technicalDetails: {
        tables: ['digest_items', 'article_tags'],
        apis: ['GET /api/digest (industry filter)'],
        sourceFiles: ['IndustriesDashboard.tsx'],
      },
      connections: {
        outgoing: ['api-layer'],
      },
    },
  },
  {
    id: 'tab-prefs',
    type: 'tabNode',
    position: { x: COL_TABS, y: 540 },
    data: {
      label: 'Data & Prefs',
      nodeType: 'tabNode',
      description: 'Manage tracked companies, priority topics, blocked topics. Affects content filtering across all tabs.',
      icon: 'prefs',
      badge: '2 tables',
      technicalDetails: {
        tables: ['user_preferences', 'org_preferences'],
        apis: ['GET/POST /api/preferences'],
        sourceFiles: ['DataPreferencesDashboard.tsx', 'PreferencesPanel.tsx'],
      },
      connections: {
        outgoing: ['api-layer'],
      },
    },
  },
]

// ────────────────────────────────────────────────
// Section 2: Shared Application Layer (4 nodes)
// ────────────────────────────────────────────────
const appLayerNodes: Node<ArchNodeData>[] = [
  {
    id: 'api-layer',
    type: 'processing',
    position: { x: COL_APP, y: 100 },
    data: {
      label: 'FastAPI Backend',
      nodeType: 'processing',
      description: 'Python FastAPI server deployed on Cloud Run (gen2). Single main.py entry point. Routes organized in api/routes/. RESTful + SSE streaming endpoints. Structured logging via structlog → Cloud Logging.',
      icon: 'filter',
      badge: 'Cloud Run',
      technicalDetails: {
        sourceFiles: ['backend/app/main.py', 'backend/app/api/routes/'],
      },
      connections: {
        incoming: ['tab-pulse', 'tab-discovery', 'tab-research', 'tab-pipeline', 'tab-supply', 'tab-industries', 'tab-prefs'],
        outgoing: ['bq-client', 'gcs-client', 'gcp-cloudrun', 'gcp-logging'],
      },
    },
  },
  {
    id: 'bq-client',
    type: 'processing',
    position: { x: COL_APP, y: 250 },
    data: {
      label: 'BigQuery Client',
      nodeType: 'processing',
      description: 'BigQueryDataStorage singleton. 15-min query cache. Handles all CRUD operations against the BigQuery dataset. Authenticated via default compute SA (Cloud IAM).',
      icon: 'link',
      badge: '15-min cache',
      technicalDetails: {
        sourceFiles: ['backend/app/db/bigquery_store.py'],
        functions: ['BigQueryDataStorage', 'execute_query()', 'upsert_rows()'],
      },
      connections: {
        incoming: ['api-layer'],
        outgoing: ['gcp-bigquery'],
      },
    },
  },
  {
    id: 'vector-store',
    type: 'agent',
    position: { x: COL_APP, y: 380 },
    data: {
      label: 'Vector Store',
      nodeType: 'agent',
      description: 'BigQueryVectorStore — uses Vertex AI embeddings (768-dim) with BigQuery native VECTOR_SEARCH. IVF index for fast approximate nearest-neighbor. Used by Deep Research, ad-hoc briefing, and pipeline agents.',
      icon: 'brain',
      badge: '768-dim',
      technicalDetails: {
        sourceFiles: ['backend/app/db/vector_store.py'],
        functions: ['BigQueryVectorStore', 'similarity_search()'],
        model: 'text-embedding-004',
      },
      connections: {
        incoming: ['tab-research'],
        outgoing: ['gcp-vertexai', 'gcp-bigquery'],
      },
    },
  },
  {
    id: 'gcs-client',
    type: 'processing',
    position: { x: COL_APP, y: 500 },
    data: {
      label: 'GCS Client',
      nodeType: 'processing',
      description: 'Reads/writes podcast MP3s and assets to Cloud Storage bucket. Also manages GCS FUSE mount for persistent file access on Cloud Run.',
      icon: 'link',
      badge: 'FUSE + API',
      technicalDetails: {
        sourceFiles: ['backend/app/services/storage_service.py'],
        functions: ['upload_podcast()', 'get_public_url()'],
      },
      connections: {
        incoming: ['tab-pulse', 'api-layer'],
        outgoing: ['gcp-gcs'],
      },
    },
  },
]

// ────────────────────────────────────────────────
// Section 3: GCP Infrastructure Layer (10 nodes)
// ────────────────────────────────────────────────

// Tier 1 — Core Runtime (top row, 4 nodes)
const gcpTier1Nodes: Node<ArchNodeData>[] = [
  {
    id: 'gcp-cloudrun',
    type: 'gcpService',
    position: { x: COL_GCP_LEFT, y: 0 },
    data: {
      label: 'Cloud Run',
      nodeType: 'gcpService',
      description: 'Serverless container runtime (gen2). Service: c1-hub, region: us-central1. 2 vCPU, 2 GiB memory, auto-scales 0→10 instances, CPU boost enabled. 3600s max timeout for long-running research workflows. Pure pay-per-request serverless.',
      icon: 'container',
      badge: 'us-central1',
      technicalDetails: {
        sourceFiles: ['Dockerfile.prod', 'cloudbuild.yaml', 'deploy/service.yaml'],
        cost: '~$50/month',
      },
      connections: {
        incoming: ['api-layer', 'gcp-scheduler', 'gcp-artifact', 'gcp-cloudbuild', 'gcp-secretmgr', 'gcp-iam'],
        outgoing: ['gcp-logging'],
      },
    },
  },
  {
    id: 'gcp-bigquery',
    type: 'gcpService',
    position: { x: COL_GCP_RIGHT, y: 0 },
    data: {
      label: 'BigQuery',
      nodeType: 'gcpService',
      description: 'Serverless analytics data warehouse — the sole database for the entire platform (no Postgres, no Redis, no SQLite). Dataset: c1_intelligence with 20+ tables. Native VECTOR_SEARCH with IVF index for semantic search.',
      icon: 'database',
      badge: '20+ tables',
      technicalDetails: {
        tables: ['articles', 'digest_items', 'sec_filing_nuggets', 'earnings_quotes', 'podcast_quotes', 'article_chunk_embeddings', 'iy_companies', 'iy_suppliers', 'iy_edges', 'weekly_briefings', 'deep_research_reports'],
        dataVolume: '20+ tables, 100GB+',
      },
      connections: {
        incoming: ['bq-client', 'vector-store', 'gcp-iam'],
      },
    },
  },
  {
    id: 'gcp-vertexai',
    type: 'gcpService',
    position: { x: COL_GCP_LEFT, y: 110 },
    data: {
      label: 'Vertex AI',
      nodeType: 'gcpService',
      description: 'Google managed ML platform. Provides text-embedding-004 model (768-dimensional embeddings). Powers semantic similarity search via BigQuery VECTOR_SEARCH. Graceful fallback to local sentence-transformers (384-dim).',
      icon: 'brain',
      badge: 'text-embedding-004',
      technicalDetails: {
        model: 'text-embedding-004',
        functions: ['aiplatform.init()', 'TextEmbeddingModel.get_embeddings()'],
      },
      connections: {
        incoming: ['vector-store'],
      },
    },
  },
  {
    id: 'gcp-gcs',
    type: 'gcpService',
    position: { x: COL_GCP_RIGHT, y: 110 },
    data: {
      label: 'Cloud Storage',
      nodeType: 'gcpService',
      description: 'Bucket: gen-lang-client-...-c1-hub-data. Dual-mode: (1) GCS FUSE volume mount at /app/data for persistent file storage with 30-day lifecycle auto-delete. (2) Direct GCS API for podcast MP3s served via public URLs.',
      icon: 'bucket',
      badge: 'FUSE + API',
      technicalDetails: {
        sourceFiles: ['deploy/service.yaml'],
        cost: '~$2/month',
        dataVolume: 'audio cache, exports',
      },
      connections: {
        incoming: ['gcs-client', 'gcp-iam'],
      },
    },
  },
]

// Tier 2 — Automation & CI/CD (middle row, 3 nodes)
const gcpTier2Nodes: Node<ArchNodeData>[] = [
  {
    id: 'gcp-scheduler',
    type: 'gcpService',
    position: { x: COL_GCP_LEFT, y: 250 },
    data: {
      label: 'Cloud Scheduler',
      nodeType: 'gcpService',
      description: 'Cron-as-a-service orchestrating the entire automated data pipeline. Fires authenticated HTTP POST requests (OIDC tokens) to Cloud Run endpoints. 8+ scheduled jobs covering ingestion, briefings, and cleanup.',
      icon: 'clock',
      badge: '8+ jobs',
      technicalDetails: {
        sourceFiles: ['deploy/scheduler/scheduler-jobs.yaml'],
        functions: ['orchestrator-ingestion-morning', 'orchestrator-ingestion-evening', 'weekly-executive-briefing', 'importyeti-ingestion'],
        cost: '~$3/month',
      },
      connections: {
        outgoing: ['gcp-cloudrun'],
      },
    },
  },
  {
    id: 'gcp-cloudbuild',
    type: 'gcpService',
    position: { x: COL_GCP_RIGHT, y: 250 },
    data: {
      label: 'Cloud Build',
      nodeType: 'gcpService',
      description: 'Fully automated CI/CD pipeline. Trigger: git push origin master → GitHub webhook → Cloud Build. Steps: Docker build, push to Artifact Registry, deploy to Cloud Run with secret injection. ~3-5 minute push-to-production cycle.',
      icon: 'cicd',
      badge: 'CI/CD',
      technicalDetails: {
        sourceFiles: ['cloudbuild.yaml'],
      },
      connections: {
        outgoing: ['gcp-artifact', 'gcp-cloudrun'],
      },
    },
  },
  {
    id: 'gcp-artifact',
    type: 'gcpService',
    position: { x: COL_GCP_LEFT + 110, y: 340 },
    data: {
      label: 'Artifact Registry',
      nodeType: 'gcpService',
      description: 'Docker container image registry. Repository: us-central1-docker.pkg.dev/.../c1-intelligence-hub/. Stores versioned + latest tagged production images. Cloud Build pushes here; Cloud Run pulls from here.',
      icon: 'package',
      badge: 'Docker',
      technicalDetails: {
        sourceFiles: ['cloudbuild.yaml'],
      },
      connections: {
        incoming: ['gcp-cloudbuild'],
        outgoing: ['gcp-cloudrun'],
      },
    },
  },
]

// Tier 3 — Security & Operations (bottom row, 3 nodes)
const gcpTier3Nodes: Node<ArchNodeData>[] = [
  {
    id: 'gcp-secretmgr',
    type: 'gcpService',
    position: { x: COL_GCP_LEFT, y: 450 },
    data: {
      label: 'Secret Manager',
      nodeType: 'gcpService',
      description: 'Centralized secrets vault. Stores 13 API keys including Anthropic, OpenAI, FMP, Tavily, Exa, Apollo, ElevenLabs, and more. Mounted as env vars in Cloud Run via cloudbuild.yaml --set-secrets at deploy time.',
      icon: 'key',
      badge: '13 secrets',
      technicalDetails: {
        sourceFiles: ['cloudbuild.yaml'],
        apis: ['ANTHROPIC_API_KEY', 'OPENAI_API_KEY', 'TAVILY_API_KEY', 'EXA_API_KEY', 'APOLLO_API_KEY', 'ELEVENLABS_API_KEY'],
      },
      connections: {
        outgoing: ['gcp-cloudrun'],
      },
    },
  },
  {
    id: 'gcp-iam',
    type: 'gcpService',
    position: { x: COL_GCP_RIGHT, y: 450 },
    data: {
      label: 'Cloud IAM',
      nodeType: 'gcpService',
      description: '3 service accounts with least-privilege access: (1) Default compute SA for BigQuery/GCS/Secrets, (2) Cloud Build SA for run.admin, (3) scheduler-invoker SA for run.invoker.',
      icon: 'shield',
      badge: '3 SAs',
      technicalDetails: {
        sourceFiles: ['deploy/setup-gcp.sh', 'deploy/terraform/main.tf'],
        functions: ['roles/bigquery.dataEditor', 'roles/bigquery.jobUser', 'roles/storage.objectAdmin', 'roles/run.invoker'],
      },
      connections: {
        outgoing: ['gcp-cloudrun', 'gcp-bigquery', 'gcp-gcs', 'gcp-secretmgr'],
      },
    },
  },
  {
    id: 'gcp-logging',
    type: 'gcpService',
    position: { x: COL_GCP_LEFT + 110, y: 545 },
    data: {
      label: 'Cloud Logging',
      nodeType: 'gcpService',
      description: 'Structured application logging and operational observability. All Cloud Run structlog output streams here. Used for monitoring ingestion pipeline status, debugging scheduler failures, tracking API latency.',
      icon: 'monitor',
      badge: 'Observability',
      technicalDetails: {
        sourceFiles: ['scripts/monitoring/scheduler_report.py'],
        functions: ['structlog.get_logger()', 'gcloud logging read'],
      },
      connections: {
        incoming: ['gcp-cloudrun', 'gcp-cloudbuild', 'api-layer'],
      },
    },
  },
]

// ────────────────────────────────────────────────
// Exported combined arrays
// ────────────────────────────────────────────────
export const tabArchitectureNodes: Node<ArchNodeData>[] = [
  ...tabNodes,
  ...appLayerNodes,
  ...gcpTier1Nodes,
  ...gcpTier2Nodes,
  ...gcpTier3Nodes,
]
