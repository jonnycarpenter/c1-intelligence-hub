# C1 Intelligence Hub - GCP Deployment

This folder contains all the configuration needed to deploy C1 Intelligence Hub to Google Cloud Platform with full data architecture.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Cloud Run                                       │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                        c1-hub service                                  │  │
│  │  ┌─────────────┐  ┌────────────────────┐  ┌────────────────────────┐ │  │
│  │  │   FastAPI   │  │  Scheduler API     │  │  /app/data (GCS mount) │ │  │
│  │  │   Backend   │  │  /api/v1/scheduler │  │  ├── chroma/           │ │  │
│  │  │   :8080     │  │  /collect          │  │  └── knowledge_db/     │ │  │
│  │  └─────────────┘  │  /maintenance      │  └────────────────────────┘ │  │
│  │                   └────────────────────┘                              │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
           │                      ▲
           │                      │ OIDC Token Auth
           ▼                      │
┌──────────────────┐    ┌─────────────────────┐
│   BigQuery       │    │  Cloud Scheduler    │
│   c1_intelligence│    │  ┌───────────────┐  │
│  ├─freight_rates │    │  │ collect-*     │  │  ← Hourly/Daily/Weekly
│  ├─commodity_prc │    │  │ maintenance-* │  │
│  ├─articles      │    │  └───────────────┘  │
│  └─collection_log│    └─────────────────────┘
└──────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           GCS Bucket                                         │
│    gs://{project-id}-c1-hub-data                                            │
│    ├── chroma/          (ChromaDB vector store)                             │
│    ├── knowledge_db/    (Knowledge base vectors)                            │
│    └── downloads/       (Generated reports - auto-deleted after 30 days)    │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Data Collection Cadences

| Job | Schedule | Source |
|-----|----------|--------|
| `collect-stock-news` | Every 4 hours | FMP Stock News API |
| `collect-tavily-news` | Every 6 hours | Tavily Web Search |
| `collect-rss-feeds` | Every 6 hours | Industry RSS Feeds |
| `collect-commodity-prices` | Daily @ 6 AM ET | FMP Commodities |
| `collect-freight-rates` | Daily @ 7 AM ET | Freightos API (when available) |
| `collect-press-releases` | Daily @ 8 AM ET | FMP Press Releases |
| `weekly-data-cleanup` | Sundays @ 2 AM ET | Internal maintenance |
| `weekly-corpus-refresh` | Sundays @ 3 AM ET | Vector store reindex |
| `collect-earnings-transcripts` | Quarterly | API Ninjas |

## Prerequisites

1. **GCP Project** with billing enabled
2. **gcloud CLI** installed and authenticated
3. **Docker** installed (for local builds)
4. **(Optional) Terraform** >= 1.0 for IaC deployment

## Quick Start

### Option 1: Shell Script (Linux/Mac/WSL)

```bash
# 1. Run setup script
chmod +x deploy/setup-gcp.sh
./deploy/setup-gcp.sh YOUR_PROJECT_ID

# 2. Add API keys to Secret Manager
echo -n "sk-ant-xxxxx" | gcloud secrets versions add anthropic-api-key --data-file=-
echo -n "your-fmp-key" | gcloud secrets versions add fmp-api-key --data-file=-
echo -n "your-api-ninja-key" | gcloud secrets versions add api-ninja-key --data-file=-
echo -n "your-tavily-key" | gcloud secrets versions add tavily-api-key --data-file=-

# 3. Deploy to Cloud Run (builds run in us-central1)
gcloud builds submit --config=deploy/cloudbuild.yaml \
  --region=us-central1 \
  --substitutions=_DATA_BUCKET=YOUR_PROJECT_ID-c1-hub-data

# 4. Deploy scheduler jobs (after Cloud Run is up)
chmod +x deploy/scheduler/deploy-scheduler.sh
./deploy/scheduler/deploy-scheduler.sh YOUR_PROJECT_ID https://c1-hub-xxxxx-uc.a.run.app
```

### Option 2: Terraform (Infrastructure as Code)

```bash
cd deploy/terraform

# 1. Initialize Terraform
terraform init

# 2. Create infrastructure (without scheduler jobs)
terraform apply -var="project_id=YOUR_PROJECT_ID"

# 3. Add API keys (see output from terraform apply)

# 4. Deploy to Cloud Run (builds run in us-central1)
gcloud builds submit --config=../cloudbuild.yaml \
  --region=us-central1 \
  --substitutions=_DATA_BUCKET=$(terraform output -raw data_bucket_name)

# 5. Enable scheduler jobs
terraform apply \
  -var="project_id=YOUR_PROJECT_ID" \
  -var="enable_scheduler=true" \
  -var="service_url=https://c1-hub-xxxxx-uc.a.run.app"
```

### Option 3: PowerShell (Windows)

```powershell
# From c1-intelligence-hub_v2 directory
.\deploy\deploy.ps1 -ProjectId YOUR_PROJECT_ID
```

## GCP Resources Created

| Resource | Name | Purpose |
|----------|------|---------|
| **Artifact Registry** | `c1-intelligence-hub` | Container images |
| **GCS Bucket** | `{project}-c1-hub-data` | Persistent storage |
| **BigQuery Dataset** | `c1_intelligence` | Time-series data |
| **BigQuery Tables** | `freight_rates`, `commodity_prices`, `articles`, `collection_log` | Data storage |
| **Secret Manager** | `anthropic-api-key`, `fmp-api-key`, etc. | API credentials |
| **Service Account** | `scheduler-invoker` | Scheduler → Cloud Run auth |
| **Cloud Scheduler** | 9 jobs | Automated data collection |

## Environment Variables

### Required in Cloud Run

| Variable | Value | Description |
|----------|-------|-------------|
| `ENVIRONMENT` | `production` | Environment identifier |
| `GCP_PROJECT_ID` | `your-project-id` | GCP project |
| `GCP_DATASET_ID` | `c1_intelligence` | BigQuery dataset |
| `GCS_BUCKET_NAME` | `{project}-c1-hub-data` | Storage bucket |
| `CHROMA_PERSIST_DIR` | `/app/data/chroma` | ChromaDB storage |
| `KNOWLEDGE_PERSIST_DIR` | `/app/data/knowledge_db` | Knowledge base |

### Secrets (via Secret Manager)

| Secret | Description |
|--------|-------------|
| `anthropic-api-key` | Claude API key |
| `fmp-api-key` | Financial Modeling Prep API key |
| `api-ninja-key` | API Ninjas key (earnings transcripts) |
| `tavily-api-key` | Tavily web search API key |

## Directory Structure

```
deploy/
├── README.md                 # This file
├── setup-gcp.sh              # One-time GCP setup script
├── deploy.ps1                # Windows deployment script
├── cloudbuild.yaml           # Cloud Build CI/CD pipeline
├── service.yaml              # Cloud Run service definition
├── scheduler/
│   ├── scheduler-jobs.yaml   # Job definitions (reference)
│   └── deploy-scheduler.sh   # Scheduler deployment script
└── terraform/
    ├── main.tf               # Core infrastructure
    └── scheduler.tf          # Cloud Scheduler jobs
```

## Manual Operations

### Trigger a Collection Job Manually

```bash
# Via gcloud
gcloud scheduler jobs run collect-stock-news --location=us-central1

# Via curl (with auth token)
curl -X POST "https://c1-hub-xxxxx-uc.a.run.app/api/v1/scheduler/collect" \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  -H "Content-Type: application/json" \
  -d '{"source": "stock_news", "cadence": "hourly"}'
```

### Check Scheduler Status

```bash
# List all jobs
gcloud scheduler jobs list --location=us-central1

# Check job execution history
gcloud scheduler jobs describe collect-stock-news --location=us-central1
```

### Query BigQuery Data

```sql
-- Recent commodity prices
SELECT date, symbol, name, price, change_pct
FROM `your-project.c1_intelligence.commodity_prices`
WHERE date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
ORDER BY date DESC, symbol;

-- Article counts by source
SELECT source_type, COUNT(*) as count
FROM `your-project.c1_intelligence.articles`
GROUP BY source_type
ORDER BY count DESC;

-- Collection history
SELECT source, started_at, records_collected, status
FROM `your-project.c1_intelligence.collection_log`
ORDER BY started_at DESC
LIMIT 50;
```

## Monitoring

### Check Cloud Build Status

```bash
# List recent builds (note: builds are in us-central1 region)
gcloud builds list --region=us-central1 --limit=5

# Check a specific build
gcloud builds describe BUILD_ID --region=us-central1
```

### Cloud Run Metrics
- **Request latency**: Should be < 2s for API calls, < 30s for collection jobs
- **Memory usage**: Configured for 2Gi, monitor for spikes
- **Error rate**: Alert on > 1% error rate

### BigQuery
- **Storage costs**: Articles table grows ~1GB/month
- **Query costs**: Use partitioning and clustering for efficiency

### Recommended Alerts

```bash
# Create alert for scheduler job failures
gcloud monitoring policies create \
  --display-name="Scheduler Job Failures" \
  --condition-filter='resource.type="cloud_scheduler_job" AND metric.type="cloud_scheduler.googleapis.com/job/execution_count" AND metric.labels.execution_status="failed"' \
  --condition-threshold-value=1 \
  --notification-channels=YOUR_CHANNEL_ID
```

## Troubleshooting

### Scheduler Jobs Not Running

1. Check service account has `run.invoker` role
2. Verify Cloud Run URL is correct
3. Check job logs: `gcloud scheduler jobs describe <job-name> --location=us-central1`

### BigQuery Insert Errors

1. Verify service account has `bigquery.dataEditor` role
2. Check schema matches (especially timestamp formats)
3. Review Cloud Run logs for specific errors

### GCS Mount Issues

1. Cloud Run Gen2 is required for GCS mounts
2. Verify bucket exists and SA has `storage.objectAdmin` role
3. Check mount path matches environment variables

## Cost Estimation

| Resource | Estimated Monthly Cost |
|----------|------------------------|
| Cloud Run (1 instance, light usage) | $10-30 |
| BigQuery (1GB storage, light queries) | $5-10 |
| Cloud Storage (5GB) | $1-2 |
| Cloud Scheduler (9 jobs) | ~$0.30 |
| Secret Manager (4 secrets) | ~$0.10 |
| **Total** | **~$20-50/month** |

*Costs vary based on usage. Free tier covers most development usage.*
