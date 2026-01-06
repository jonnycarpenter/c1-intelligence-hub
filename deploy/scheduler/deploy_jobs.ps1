# =============================================================================
# Cloud Scheduler Jobs Deployment Script
# =============================================================================
# IMPORTANT: Cloud Scheduler max timeout is 30 minutes (1800s)
# IMPORTANT: JSON body must use escaped quotes for PowerShell: '{\"key\": \"value\"}'
# =============================================================================

$ProjectId = "gen-lang-client-0436975498"
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
$Jobs = @(
    @{
        Name        = "ingest-flash-update"
        Schedule    = "0 */4 * * *"
        Uri         = "$ServiceUrl/api/v1/scheduler/ingest"
        # PowerShell requires escaped quotes for JSON to pass correctly to gcloud
        Body        = '{\"sources\": [\"rss\", \"stocknews\", \"freight\"]}'
        Timeout     = "900s"  # 15 min - flash jobs are lighter
        Description = "Flash Loop: Frequent updates for fast-moving data (RSS, StockNews, Freight)"
    },
    @{
        Name        = "ingest-deep-dive"
        Schedule    = "0 8 * * *" # 8 AM UTC = 2 AM CST (Standard Time)
        Uri         = "$ServiceUrl/api/v1/scheduler/ingest"
        # ALL sources: industry_queries (Exa+Tavily), rss, sec, earnings, stocknews, fmp_news, freight, press_releases (Exa)
        Body        = '{\"sources\": [\"industry_queries\", \"rss\", \"sec\", \"earnings\", \"stocknews\", \"fmp_news\", \"freight\", \"press_releases\"]}'
        Timeout     = "1800s"  # 30 min MAX - deep ingestion needs full time
        Description = "Deep Loop: Comprehensive daily ingestion (ALL sources)"
    },
    @{
        Name        = "weekly-executive-briefing"
        Schedule    = "30 14 * * 1" # 14:30 UTC = 8:30 AM CST on Mondays
        Uri         = "$ServiceUrl/api/v1/scheduler/briefing"
        Body        = '{}'
        Timeout     = "900s"  # 15 min - briefing generation
        Description = "Briefing Job: Generates weekly 'Need to Know' report"
    }
)

# Legacy Jobs to DELETE (will be removed if they exist)
$LegacyJobs = @(
    "daily-morning-ingest",
    "orchestrator-ingestion-morning", 
    "orchestrator-ingestion-evening",
    "daily-evening-ingest",        # Removed: redundant with ingest-deep-dive
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
