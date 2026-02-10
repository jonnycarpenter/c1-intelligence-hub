import type { Edge } from '@xyflow/react'

// ============================================
// Tab 2 — Frontend Data Architecture Edges
// ============================================
// Per spec §3.5:
//   Application → Infrastructure edges
//   GCP Service Mesh edges (dotted for IAM, dashed for logging)

// Edge style helpers
const appFlow = { type: 'smoothstep' as const, animated: true }
const gcpMesh = { type: 'smoothstep' as const, animated: false }
const iamDotted = { type: 'smoothstep' as const, animated: false, style: { strokeDasharray: '3 3' } }
const logDashed = { type: 'smoothstep' as const, animated: false, style: { strokeDasharray: '8 4' } }

const APP_COLOR = '#f59e0b'       // amber for app data flow
const GCP_COLOR = '#4285F4'       // Google Blue for GCP mesh
const IAM_COLOR = '#9ca3af'       // gray for IAM permission grants
const LOG_COLOR = '#6b7280'       // gray for log ingestion
const RESEARCH_COLOR = '#10b981'  // emerald for research/ML path
const STORAGE_COLOR = '#8b5cf6'   // violet for storage writes

export const tabArchitectureEdges: Edge[] = [
  // ────────────────────────────────────────────
  // Tab → API Layer (all 7 tabs connect to FastAPI)
  // ────────────────────────────────────────────
  {
    id: 'tab-pulse-api',
    source: 'tab-pulse',
    target: 'api-layer',
    ...appFlow,
    style: { stroke: APP_COLOR },
  },
  {
    id: 'tab-discovery-api',
    source: 'tab-discovery',
    target: 'api-layer',
    ...appFlow,
    style: { stroke: APP_COLOR },
  },
  {
    id: 'tab-research-api',
    source: 'tab-research',
    target: 'api-layer',
    ...appFlow,
    style: { stroke: APP_COLOR },
  },
  {
    id: 'tab-pipeline-api',
    source: 'tab-pipeline',
    target: 'api-layer',
    ...appFlow,
    style: { stroke: APP_COLOR },
  },
  {
    id: 'tab-supply-api',
    source: 'tab-supply',
    target: 'api-layer',
    ...appFlow,
    style: { stroke: APP_COLOR },
  },
  {
    id: 'tab-industries-api',
    source: 'tab-industries',
    target: 'api-layer',
    ...appFlow,
    style: { stroke: APP_COLOR },
  },
  {
    id: 'tab-prefs-api',
    source: 'tab-prefs',
    target: 'api-layer',
    ...appFlow,
    style: { stroke: APP_COLOR },
  },

  // ────────────────────────────────────────────
  // Application Layer → BigQuery path
  // ────────────────────────────────────────────
  {
    id: 'api-bqclient',
    source: 'api-layer',
    target: 'bq-client',
    ...appFlow,
    style: { stroke: APP_COLOR },
  },
  {
    id: 'bqclient-bigquery',
    source: 'bq-client',
    target: 'gcp-bigquery',
    ...appFlow,
    style: { stroke: STORAGE_COLOR },
  },

  // ────────────────────────────────────────────
  // Research → Vector Store → Vertex AI + BigQuery
  // ────────────────────────────────────────────
  {
    id: 'research-vector',
    source: 'tab-research',
    target: 'vector-store',
    ...appFlow,
    style: { stroke: RESEARCH_COLOR },
    label: 'semantic search',
  },
  {
    id: 'vector-vertexai',
    source: 'vector-store',
    target: 'gcp-vertexai',
    ...appFlow,
    style: { stroke: RESEARCH_COLOR },
    label: 'embeddings',
  },
  {
    id: 'vector-bigquery',
    source: 'vector-store',
    target: 'gcp-bigquery',
    ...appFlow,
    style: { stroke: STORAGE_COLOR },
    label: 'VECTOR_SEARCH',
  },

  // ────────────────────────────────────────────
  // Podcast / GCS path
  // ────────────────────────────────────────────
  {
    id: 'api-gcsclient',
    source: 'api-layer',
    target: 'gcs-client',
    ...appFlow,
    style: { stroke: APP_COLOR },
  },
  {
    id: 'gcsclient-gcs',
    source: 'gcs-client',
    target: 'gcp-gcs',
    ...appFlow,
    style: { stroke: STORAGE_COLOR },
    label: 'MP3s & assets',
  },

  // ────────────────────────────────────────────
  // API Layer → Cloud Run (runs on)
  // ────────────────────────────────────────────
  {
    id: 'api-cloudrun',
    source: 'api-layer',
    target: 'gcp-cloudrun',
    ...appFlow,
    style: { stroke: GCP_COLOR },
    label: 'deployed on',
  },

  // ────────────────────────────────────────────
  // API Layer → Cloud Logging
  // ────────────────────────────────────────────
  {
    id: 'api-logging',
    source: 'api-layer',
    target: 'gcp-logging',
    ...logDashed,
    style: { ...logDashed.style, stroke: LOG_COLOR },
    label: 'structlog',
  },

  // ════════════════════════════════════════════
  // GCP Service Mesh (infrastructure-to-infrastructure)
  // ════════════════════════════════════════════

  // Scheduler → Cloud Run (OIDC triggers)
  {
    id: 'scheduler-cloudrun',
    source: 'gcp-scheduler',
    target: 'gcp-cloudrun',
    ...gcpMesh,
    style: { stroke: GCP_COLOR },
    label: 'OIDC triggers',
  },

  // Cloud Build → Artifact Registry (push images)
  {
    id: 'cloudbuild-artifact',
    source: 'gcp-cloudbuild',
    target: 'gcp-artifact',
    ...gcpMesh,
    style: { stroke: GCP_COLOR },
    label: 'push images',
  },

  // Artifact Registry → Cloud Run (pull on deploy)
  {
    id: 'artifact-cloudrun',
    source: 'gcp-artifact',
    target: 'gcp-cloudrun',
    ...gcpMesh,
    style: { stroke: GCP_COLOR },
    label: 'deploy',
  },

  // Cloud Build → Cloud Run (deploy revisions)
  {
    id: 'cloudbuild-cloudrun',
    source: 'gcp-cloudbuild',
    target: 'gcp-cloudrun',
    ...gcpMesh,
    style: { stroke: GCP_COLOR },
    label: 'new revision',
  },

  // Secret Manager → Cloud Run (env var injection)
  {
    id: 'secretmgr-cloudrun',
    source: 'gcp-secretmgr',
    target: 'gcp-cloudrun',
    ...gcpMesh,
    style: { stroke: GCP_COLOR },
    label: 'secrets',
  },

  // IAM → multiple services (dotted permission grants)
  {
    id: 'iam-cloudrun',
    source: 'gcp-iam',
    target: 'gcp-cloudrun',
    ...iamDotted,
    style: { ...iamDotted.style, stroke: IAM_COLOR },
    label: 'permissions',
  },
  {
    id: 'iam-bigquery',
    source: 'gcp-iam',
    target: 'gcp-bigquery',
    ...iamDotted,
    style: { ...iamDotted.style, stroke: IAM_COLOR },
  },
  {
    id: 'iam-gcs',
    source: 'gcp-iam',
    target: 'gcp-gcs',
    ...iamDotted,
    style: { ...iamDotted.style, stroke: IAM_COLOR },
  },
  {
    id: 'iam-secretmgr',
    source: 'gcp-iam',
    target: 'gcp-secretmgr',
    ...iamDotted,
    style: { ...iamDotted.style, stroke: IAM_COLOR },
  },

  // Logging ← Cloud Run, Cloud Build (dashed log ingestion)
  {
    id: 'cloudrun-logging',
    source: 'gcp-cloudrun',
    target: 'gcp-logging',
    sourceHandle: 'bottom',
    ...logDashed,
    style: { ...logDashed.style, stroke: LOG_COLOR },
    label: 'logs',
  },
  {
    id: 'cloudbuild-logging',
    source: 'gcp-cloudbuild',
    target: 'gcp-logging',
    ...logDashed,
    style: { ...logDashed.style, stroke: LOG_COLOR },
  },
]
