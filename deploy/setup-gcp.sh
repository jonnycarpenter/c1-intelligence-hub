#!/bin/bash
# =============================================================================
# GCP Setup Script for C1 Intelligence Hub
# =============================================================================
# Run this script once to set up all GCP resources
# 
# Prerequisites:
#   - gcloud CLI installed and authenticated
#   - Billing enabled on your GCP project
#
# Usage:
#   chmod +x setup-gcp.sh
#   ./setup-gcp.sh <PROJECT_ID>
# =============================================================================

set -e  # Exit on error

# Configuration
PROJECT_ID="${1:-}"
REGION="us-central1"
SERVICE_NAME="c1-hub"
REPOSITORY_NAME="c1-intelligence-hub"
BUCKET_NAME="c1-hub-data"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Helper functions
log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check prerequisites
if [ -z "$PROJECT_ID" ]; then
    log_error "Usage: $0 <PROJECT_ID>"
    exit 1
fi

log_info "Setting up GCP resources for project: $PROJECT_ID"
log_info "Region: $REGION"

# Set the project
gcloud config set project "$PROJECT_ID"

# =============================================================================
# 1. Enable Required APIs
# =============================================================================
log_info "Enabling required APIs..."

APIS=(
    "run.googleapis.com"           # Cloud Run
    "cloudbuild.googleapis.com"    # Cloud Build
    "artifactregistry.googleapis.com"  # Artifact Registry
    "secretmanager.googleapis.com" # Secret Manager
    "storage.googleapis.com"       # Cloud Storage
    "bigquery.googleapis.com"      # BigQuery (time-series storage)
    "cloudscheduler.googleapis.com" # Cloud Scheduler (automated jobs)
)

for api in "${APIS[@]}"; do
    log_info "  Enabling $api..."
    gcloud services enable "$api" --quiet
done

# =============================================================================
# 2. Create Artifact Registry Repository
# =============================================================================
log_info "Creating Artifact Registry repository..."

gcloud artifacts repositories create "$REPOSITORY_NAME" \
    --repository-format=docker \
    --location="$REGION" \
    --description="C1 Intelligence Hub container images" \
    --quiet 2>/dev/null || log_warn "Repository may already exist"

# =============================================================================
# 3. Create GCS Bucket for Data Persistence
# =============================================================================
log_info "Creating GCS bucket for data persistence..."

FULL_BUCKET_NAME="${PROJECT_ID}-${BUCKET_NAME}"

gsutil mb -l "$REGION" "gs://${FULL_BUCKET_NAME}" 2>/dev/null || log_warn "Bucket may already exist"

# Create folder structure in bucket
log_info "Creating folder structure in bucket..."
echo "" | gsutil cp - "gs://${FULL_BUCKET_NAME}/chroma/.keep"
echo "" | gsutil cp - "gs://${FULL_BUCKET_NAME}/knowledge_db/.keep"
echo "" | gsutil cp - "gs://${FULL_BUCKET_NAME}/downloads/.keep"

# Set lifecycle policy (optional - auto-delete old downloads after 30 days)
cat > /tmp/lifecycle.json << EOF
{
  "rule": [
    {
      "action": {"type": "Delete"},
      "condition": {
        "age": 30,
        "matchesPrefix": ["downloads/"]
      }
    }
  ]
}
EOF
gsutil lifecycle set /tmp/lifecycle.json "gs://${FULL_BUCKET_NAME}"

# =============================================================================
# 4. Create BigQuery Dataset
# =============================================================================
log_info "Creating BigQuery dataset for time-series data..."

DATASET_ID="c1_intelligence"

# Create dataset
bq --location="$REGION" mk \
    --dataset \
    --description="C1 Intelligence Hub time-series data" \
    "${PROJECT_ID}:${DATASET_ID}" 2>/dev/null || log_warn "Dataset may already exist"

# Create freight_rates table
log_info "Creating BigQuery tables..."

bq mk --table \
    --description="Freight rate time-series data" \
    --time_partitioning_field=date \
    --clustering_fields=index_name,lane_code \
    "${PROJECT_ID}:${DATASET_ID}.freight_rates" \
    "date:DATE,index_name:STRING,lane_code:STRING,lane_description:STRING,rate_usd:FLOAT64,rate_unit:STRING,change_wow:FLOAT64,change_mom:FLOAT64,change_yoy:FLOAT64,source:STRING,fetched_at:TIMESTAMP" \
    2>/dev/null || log_warn "Table freight_rates may already exist"

# Create commodity_prices table
bq mk --table \
    --description="Commodity price time-series data" \
    --time_partitioning_field=date \
    --clustering_fields=symbol \
    "${PROJECT_ID}:${DATASET_ID}.commodity_prices" \
    "date:DATE,symbol:STRING,name:STRING,price:FLOAT64,currency:STRING,unit:STRING,change_pct:FLOAT64,source:STRING,fetched_at:TIMESTAMP" \
    2>/dev/null || log_warn "Table commodity_prices may already exist"

# Create articles table
bq mk --table \
    --description="News and articles storage" \
    --time_partitioning_field=published_at \
    --time_partitioning_type=MONTH \
    --clustering_fields=source_type,category \
    "${PROJECT_ID}:${DATASET_ID}.articles" \
    "id:STRING,title:STRING,url:STRING,published_at:TIMESTAMP,source_name:STRING,source_type:STRING,summary:STRING,category:STRING,topics:STRING,companies_mentioned:STRING,relevance_score:FLOAT64,fetched_at:TIMESTAMP" \
    2>/dev/null || log_warn "Table articles may already exist"

# Create collection_log table (for tracking collection runs)
bq mk --table \
    --description="Data collection run logs" \
    --time_partitioning_field=started_at \
    "${PROJECT_ID}:${DATASET_ID}.collection_log" \
    "id:STRING,source:STRING,cadence:STRING,started_at:TIMESTAMP,completed_at:TIMESTAMP,records_collected:INT64,status:STRING,error_message:STRING" \
    2>/dev/null || log_warn "Table collection_log may already exist"

log_info "BigQuery dataset and tables created"

# =============================================================================
# 5. Create Secrets in Secret Manager
# =============================================================================
log_info "Setting up Secret Manager secrets..."

# Function to create or update secret
create_secret() {
    local SECRET_NAME=$1
    local SECRET_VALUE=$2
    
    if gcloud secrets describe "$SECRET_NAME" --quiet 2>/dev/null; then
        log_warn "Secret $SECRET_NAME exists, updating..."
        echo -n "$SECRET_VALUE" | gcloud secrets versions add "$SECRET_NAME" --data-file=-
    else
        log_info "Creating secret $SECRET_NAME..."
        echo -n "$SECRET_VALUE" | gcloud secrets create "$SECRET_NAME" --data-file=- --replication-policy="automatic"
    fi
}

log_warn "You'll need to manually add your API keys to Secret Manager."
log_info "Creating placeholder secrets (update with real values)..."

# Create placeholder secrets (you'll update these with real values)
SECRETS=(
    "anthropic-api-key"
    "fmp-api-key"
    "api-ninja-key"
    "tavily-api-key"
)

for secret in "${SECRETS[@]}"; do
    if ! gcloud secrets describe "$secret" --quiet 2>/dev/null; then
        echo -n "PLACEHOLDER_UPDATE_ME" | gcloud secrets create "$secret" --data-file=- --replication-policy="automatic"
        log_info "Created placeholder for $secret"
    else
        log_warn "Secret $secret already exists"
    fi
done

# =============================================================================
# 6. Set up IAM Permissions
# =============================================================================
log_info "Setting up IAM permissions..."

# Get the Cloud Run service account
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)")
CLOUD_RUN_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
CLOUD_BUILD_SA="${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"

# Grant Cloud Run SA access to secrets
for secret in "${SECRETS[@]}"; do
    gcloud secrets add-iam-policy-binding "$secret" \
        --member="serviceAccount:${CLOUD_RUN_SA}" \
        --role="roles/secretmanager.secretAccessor" \
        --quiet
done

# Grant Cloud Run SA access to GCS bucket
gsutil iam ch "serviceAccount:${CLOUD_RUN_SA}:objectAdmin" "gs://${FULL_BUCKET_NAME}"

# Grant Cloud Run SA access to BigQuery
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${CLOUD_RUN_SA}" \
    --role="roles/bigquery.dataEditor" \
    --quiet

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${CLOUD_RUN_SA}" \
    --role="roles/bigquery.jobUser" \
    --quiet

# Grant Cloud Build SA permissions to deploy
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${CLOUD_BUILD_SA}" \
    --role="roles/run.admin" \
    --quiet

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${CLOUD_BUILD_SA}" \
    --role="roles/iam.serviceAccountUser" \
    --quiet

# =============================================================================
# 7. Create Scheduler Service Account
# =============================================================================
log_info "Creating scheduler service account..."

SCHEDULER_SA="scheduler-invoker"
SCHEDULER_SA_EMAIL="${SCHEDULER_SA}@${PROJECT_ID}.iam.gserviceaccount.com"

# Create service account if it doesn't exist
if ! gcloud iam service-accounts describe "$SCHEDULER_SA_EMAIL" --quiet 2>/dev/null; then
    gcloud iam service-accounts create "$SCHEDULER_SA" \
        --display-name="Cloud Scheduler Invoker" \
        --description="Service account for Cloud Scheduler to invoke Cloud Run"
    log_info "Created scheduler service account: $SCHEDULER_SA_EMAIL"
else
    log_warn "Scheduler service account already exists"
fi

# =============================================================================
# 8. Create Cloud Build Trigger (Optional - for CI/CD)
# =============================================================================
log_info "Cloud Build trigger setup..."
log_warn "To set up automatic deployments, connect your GitHub repo in Cloud Console"
log_info "Then create a trigger pointing to deploy/cloudbuild.yaml"

# =============================================================================
# Summary
# =============================================================================
echo ""
echo "============================================================================="
echo -e "${GREEN}GCP Setup Complete!${NC}"
echo "============================================================================="
echo ""
echo "Resources created:"
echo "  - Artifact Registry: ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY_NAME}"
echo "  - GCS Bucket: gs://${FULL_BUCKET_NAME}"
echo "  - BigQuery Dataset: ${PROJECT_ID}.${DATASET_ID}"
echo "    - freight_rates (partitioned by date)"
echo "    - commodity_prices (partitioned by date)"
echo "    - articles (partitioned by month)"
echo "    - collection_log (partitioned by started_at)"
echo "  - Secrets: anthropic-api-key, fmp-api-key, api-ninja-key, tavily-api-key"
echo "  - Scheduler SA: ${SCHEDULER_SA_EMAIL}"
echo ""
echo "Next steps:"
echo "  1. Update secrets with real API keys:"
echo "     gcloud secrets versions add anthropic-api-key --data-file=<(echo -n 'your-key')"
echo "     gcloud secrets versions add fmp-api-key --data-file=<(echo -n 'your-key')"
echo "     gcloud secrets versions add api-ninja-key --data-file=<(echo -n 'your-key')"
echo "     gcloud secrets versions add tavily-api-key --data-file=<(echo -n 'your-key')"
echo ""
echo "  2. Deploy to Cloud Run:"
echo "     cd c1-intelligence-hub_v2"
echo "     gcloud builds submit --config=deploy/cloudbuild.yaml \\"
echo "       --substitutions=_DATA_BUCKET=${FULL_BUCKET_NAME}"
echo ""
echo "  3. Deploy Cloud Scheduler jobs (after Cloud Run is deployed):"
echo "     cd deploy/scheduler"
echo "     ./deploy-scheduler.sh ${PROJECT_ID} https://<your-cloud-run-url>"
echo ""
echo "  4. (Optional) Set up CI/CD trigger in Cloud Console"
echo ""
echo "Environment variables needed in Cloud Run:"
echo "  - GCP_PROJECT_ID=${PROJECT_ID}"
echo "  - GCP_DATASET_ID=${DATASET_ID}"
echo "  - GCS_BUCKET_NAME=${FULL_BUCKET_NAME}"
echo "  - ENVIRONMENT=production"
echo ""
echo "============================================================================="
