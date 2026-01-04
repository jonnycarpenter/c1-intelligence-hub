#!/bin/bash
# =============================================================================
# Deploy Cloud Scheduler Jobs
# =============================================================================
# Creates Cloud Scheduler jobs that trigger data collection endpoints
#
# Prerequisites:
#   - Cloud Run service deployed
#   - Cloud Scheduler API enabled
#   - Service account with invoker permissions
#
# Usage:
#   chmod +x deploy-scheduler.sh
#   ./deploy-scheduler.sh <PROJECT_ID> <CLOUD_RUN_URL>
#
# Example:
#   ./deploy-scheduler.sh my-project https://c1-hub-xxxxx.run.app
# =============================================================================

set -e

# Configuration
PROJECT_ID="${1:-}"
SERVICE_URL="${2:-}"
REGION="us-central1"
SERVICE_ACCOUNT_NAME="scheduler-invoker"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Validate inputs
if [ -z "$PROJECT_ID" ] || [ -z "$SERVICE_URL" ]; then
    log_error "Usage: $0 <PROJECT_ID> <CLOUD_RUN_URL>"
    echo "Example: $0 my-project https://c1-hub-xxxxx.run.app"
    exit 1
fi

gcloud config set project "$PROJECT_ID"

# =============================================================================
# 1. Enable Cloud Scheduler API
# =============================================================================
log_info "Enabling Cloud Scheduler API..."
gcloud services enable cloudscheduler.googleapis.com --quiet

# =============================================================================
# 2. Create Service Account for Scheduler
# =============================================================================
log_info "Setting up scheduler service account..."

SA_EMAIL="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

# Create service account if it doesn't exist
if ! gcloud iam service-accounts describe "$SA_EMAIL" --quiet 2>/dev/null; then
    gcloud iam service-accounts create "$SERVICE_ACCOUNT_NAME" \
        --display-name="Cloud Scheduler Invoker" \
        --description="Service account for Cloud Scheduler to invoke Cloud Run"
    log_info "Created service account: $SA_EMAIL"
else
    log_warn "Service account already exists: $SA_EMAIL"
fi

# Grant the service account permission to invoke Cloud Run
log_info "Granting Cloud Run invoker role..."
gcloud run services add-iam-policy-binding c1-hub \
    --region="$REGION" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/run.invoker" \
    --quiet 2>/dev/null || log_warn "IAM binding may already exist"

# =============================================================================
# 3. Create/Update Scheduler Jobs
# =============================================================================
log_info "Creating Cloud Scheduler jobs..."

create_job() {
    local JOB_NAME=$1
    local SCHEDULE=$2
    local ENDPOINT=$3
    local BODY=$4
    local DESCRIPTION=$5
    local TIMEZONE=${6:-"America/New_York"}
    
    FULL_URL="${SERVICE_URL}${ENDPOINT}"
    
    # Check if job exists
    if gcloud scheduler jobs describe "$JOB_NAME" --location="$REGION" --quiet 2>/dev/null; then
        log_warn "Updating existing job: $JOB_NAME"
        gcloud scheduler jobs update http "$JOB_NAME" \
            --location="$REGION" \
            --schedule="$SCHEDULE" \
            --uri="$FULL_URL" \
            --http-method=POST \
            --headers="Content-Type=application/json" \
            --message-body="$BODY" \
            --time-zone="$TIMEZONE" \
            --oidc-service-account-email="$SA_EMAIL" \
            --oidc-token-audience="$SERVICE_URL" \
            --attempt-deadline="300s" \
            --description="$DESCRIPTION" \
            --quiet
    else
        log_info "Creating job: $JOB_NAME"
        gcloud scheduler jobs create http "$JOB_NAME" \
            --location="$REGION" \
            --schedule="$SCHEDULE" \
            --uri="$FULL_URL" \
            --http-method=POST \
            --headers="Content-Type=application/json" \
            --message-body="$BODY" \
            --time-zone="$TIMEZONE" \
            --oidc-service-account-email="$SA_EMAIL" \
            --oidc-token-audience="$SERVICE_URL" \
            --attempt-deadline="300s" \
            --description="$DESCRIPTION"
    fi
}

# ---------------------------------------------------------------------------
# Hourly Jobs (every 4-6 hours)
# ---------------------------------------------------------------------------

create_job "collect-stock-news" \
    "0 */4 * * *" \
    "/api/v1/scheduler/collect" \
    '{"source": "stock_news", "cadence": "hourly"}' \
    "Fetch stock news from FMP every 4 hours"

create_job "collect-tavily-news" \
    "15 */6 * * *" \
    "/api/v1/scheduler/collect" \
    '{"source": "tavily_news", "cadence": "hourly"}' \
    "Fetch industry news via Tavily every 6 hours"

create_job "collect-rss-feeds" \
    "30 */6 * * *" \
    "/api/v1/scheduler/collect" \
    '{"source": "rss_feeds", "cadence": "hourly"}' \
    "Fetch RSS feeds every 6 hours"

# ---------------------------------------------------------------------------
# Daily Jobs
# ---------------------------------------------------------------------------

create_job "collect-commodity-prices" \
    "0 6 * * *" \
    "/api/v1/scheduler/collect" \
    '{"source": "commodity_prices", "cadence": "daily"}' \
    "Fetch daily commodity prices at 6 AM ET"

create_job "collect-freight-rates" \
    "0 7 * * *" \
    "/api/v1/scheduler/collect" \
    '{"source": "freight_rates", "cadence": "daily"}' \
    "Fetch freight rates at 7 AM ET"

create_job "collect-press-releases" \
    "0 8 * * *" \
    "/api/v1/scheduler/collect" \
    '{"source": "press_releases", "cadence": "daily"}' \
    "Fetch press releases at 8 AM ET"

# ---------------------------------------------------------------------------
# Weekly Jobs
# ---------------------------------------------------------------------------

create_job "weekly-data-cleanup" \
    "0 2 * * 0" \
    "/api/v1/scheduler/maintenance" \
    '{"task": "cleanup", "retention_days": 90}' \
    "Weekly data cleanup on Sundays at 2 AM ET"

create_job "weekly-corpus-refresh" \
    "0 3 * * 0" \
    "/api/v1/scheduler/maintenance" \
    '{"task": "reindex"}' \
    "Weekly vector store reindex on Sundays at 3 AM ET"

# ---------------------------------------------------------------------------
# Quarterly Jobs
# ---------------------------------------------------------------------------

create_job "collect-earnings-transcripts" \
    "0 9 15 1,4,7,10 *" \
    "/api/v1/scheduler/collect" \
    '{"source": "earnings_transcripts", "cadence": "quarterly"}' \
    "Fetch earnings transcripts quarterly"

# =============================================================================
# Summary
# =============================================================================
echo ""
echo "============================================================================="
echo -e "${GREEN}Cloud Scheduler Setup Complete!${NC}"
echo "============================================================================="
echo ""
echo "Jobs created:"
gcloud scheduler jobs list --location="$REGION" --format="table(name,schedule,state)"
echo ""
echo "To manually trigger a job:"
echo "  gcloud scheduler jobs run <job-name> --location=$REGION"
echo ""
echo "To pause a job:"
echo "  gcloud scheduler jobs pause <job-name> --location=$REGION"
echo ""
echo "============================================================================="
