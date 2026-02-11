# =============================================================================
# Cloud Scheduler Jobs Deployment Script
# =============================================================================
# IMPORTANT: Cloud Scheduler max timeout is 30 minutes (1800s)
# IMPORTANT: JSON body must use escaped quotes for PowerShell: '{\"key\": \"value\"}'
# =============================================================================

$ProjectId = "<GCP_PROJECT_ID>"
$Region = "us-central1"
$ServiceName = "c1-hub"
$ServiceAccount = "c1-hub-scheduler-sa@$ProjectId.iam.gserviceaccount.com"

# Set Project
Write-Host "Setting Project to $ProjectId..."
gcloud config set project $ProjectId

# Get Service URL
Write-Host "Getting Cloud Run Service URL..."
$ServiceUrl = gcloud run services describe $ServiceName --region $Region --format="value(status.url)"
Write-Host "Service URL: $ServiceUrl"

if (-not $ServiceUrl) {
    Write-Host "Error: Could not get Service URL" -ForegroundColor Red
    exit 1
}

# Jobs Configuration
# NOTE: Body must use escaped quotes for PowerShell → gcloud compatibility
# Cloud Scheduler max timeout is 1800s (30 min) - DO NOT EXCEED
#
# DAILY INGESTION STRATEGY (split by search engine to avoid timeout):
#   2:00 AM CST (8:00 UTC) - Exa queries (91 queries + press releases) ~15 min
#   2:20 AM CST (8:20 UTC) - Tavily queries (145 queries) ~18 min
#   2:45 AM CST (8:45 UTC) - Financial data (SEC, earnings, FMP, StockNews) ~25 min
#   Flash updates every 4 hours for fast-moving sources (RSS, freight)
#
$Jobs = @(
    @{
        Name        = "ingest-flash-update"
        Schedule    = "0 */4 * * *"
        Uri         = "$ServiceUrl/api/v1/scheduler/ingest"
        # Fast sources only - runs every 4 hours
        Body        = '{\"sources\": [\"rss\", \"freight\"]}'
        Timeout     = "600s"  # 10 min - these are very fast
        Description = "Flash Loop: RSS feeds + freight rates every 4 hours"
    },
    @{
        Name        = "ingest-exa"
        Schedule    = "0 8 * * *" # 8:00 AM UTC = 2:00 AM CST
        Uri         = "$ServiceUrl/api/v1/scheduler/ingest"
        # Exa search: 91 industry queries + press releases + per-company news
        Body        = '{\"sources\": [\"exa_queries\", \"press_releases\"]}'
        Timeout     = "1200s"  # 20 min - Exa is faster
        Description = "Exa Search: 91 industry queries + press releases at 2:00 AM CST"
    },
    @{
        Name        = "ingest-tavily"
        Schedule    = "20 8 * * *" # 8:20 AM UTC = 2:20 AM CST (20 min after Exa)
        Uri         = "$ServiceUrl/api/v1/scheduler/ingest"
        # Tavily search: 145 broadening queries
        Body        = '{\"sources\": [\"tavily_queries\"]}'
        Timeout     = "1500s"  # 25 min - Tavily has more queries
        Description = "Tavily Search: 145 monitoring queries at 2:20 AM CST"
    },
    @{
        Name        = "ingest-financial"
        Schedule    = "45 8 * * *" # 8:45 AM UTC = 2:45 AM CST (45 min after start)
        Uri         = "$ServiceUrl/api/v1/scheduler/ingest"
        # Financial/news sources: SEC filings, earnings, FMP premium, StockNews
        Body        = '{\"sources\": [\"sec\", \"earnings\", \"fmp_news\", \"stocknews\"]}'
        Timeout     = "1800s"  # 30 min MAX - StockNews can be slow (48 API calls)
        Description = "Financial Data: SEC, earnings, FMP news, StockNews at 2:45 AM CST"
    },
    @{
        Name        = "weekly-executive-briefing"
        Schedule    = "30 14 * * 1" # 14:30 UTC = 8:30 AM CST on Mondays
        Uri         = "$ServiceUrl/api/v1/scheduler/briefing"
        Body        = '{}'
        Timeout     = "900s"  # 15 min - briefing generation
        Description = "Briefing Job: Generates weekly 'Need to Know' report on Monday 8:30 AM CST"
    }
)

# Legacy Jobs to DELETE (will be removed if they exist)
$LegacyJobs = @(
    "daily-morning-ingest",
    "orchestrator-ingestion-morning", 
    "orchestrator-ingestion-evening",
    "daily-evening-ingest",        # Removed: redundant - sources now split across jobs
    "ingest-deep-dive",            # Removed: replaced by split jobs (Jan 2026)
    "ingest-web-search",           # Removed: replaced by ingest-exa + ingest-tavily (Jan 6, 2026)
    "weekly-corpus-refresh",       # Removed: stub implementation (did nothing)
    "weekly-data-cleanup"          # Removed: stub implementation (did nothing)
)

# Delete Legacy Jobs
foreach ($jobName in $LegacyJobs) {
    Write-Host "Checking for legacy job: $jobName..."
    $exists = gcloud scheduler jobs describe $jobName --location=$Region --quiet 2>$null
    if ($exists) {
        Write-Host "  Deleting legacy job: $jobName" -ForegroundColor Yellow
        gcloud scheduler jobs delete $jobName --location=$Region --quiet
    }
}

# Create/Update New Jobs
foreach ($job in $Jobs) {
    # Extract values to avoid PowerShell hashtable reference issues with gcloud
    $jobName = $job.Name
    $jobSchedule = $job.Schedule
    $jobUri = $job.Uri
    $jobBody = $job.Body
    $jobTimeout = $job.Timeout
    $jobDescription = $job.Description
    
    $exists = gcloud scheduler jobs describe $jobName --location=$Region --quiet 2>$null
    
    if ($exists) {
        Write-Host "Updating job: $jobName" -ForegroundColor Cyan
        gcloud scheduler jobs update http $jobName `
            --location=$Region `
            --schedule="$jobSchedule" `
            --uri="$jobUri" `
            --http-method=POST `
            --update-headers="Content-Type=application/json" `
            --message-body="$jobBody" `
            --time-zone="UTC" `
            --oidc-service-account-email=$ServiceAccount `
            --oidc-token-audience=$ServiceUrl `
            --attempt-deadline=$jobTimeout `
            --description="$jobDescription" `
            --quiet
    }
    else {
        Write-Host "Creating job: $jobName" -ForegroundColor Green
        gcloud scheduler jobs create http $jobName `
            --location=$Region `
            --schedule="$jobSchedule" `
            --uri="$jobUri" `
            --http-method=POST `
            --headers="Content-Type=application/json" `
            --message-body="$jobBody" `
            --time-zone="UTC" `
            --oidc-service-account-email=$ServiceAccount `
            --oidc-token-audience=$ServiceUrl `
            --attempt-deadline=$jobTimeout `
            --description="$jobDescription" `
            --quiet
    }
}

Write-Host "Scheduler Deployment Complete!" -ForegroundColor Green
