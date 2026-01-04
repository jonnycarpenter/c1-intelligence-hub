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
$Jobs = @(
    @{
        Name        = "ingest-flash-update"
        Schedule    = "0 */4 * * *"
        Uri         = "$ServiceUrl/api/v1/scheduler/ingest"
        Body        = '{"sources": ["rss", "stocknews", "freight"]}'
        Timeout     = "900s"
        Description = "Flash Loop: Frequent updates for fast-moving data (RSS, StockNews, Freight)"
    },
    @{
        Name        = "ingest-deep-dive"
        Schedule    = "0 8 * * *" # 8 AM UTC = 2 AM CST (Standard Time)
        Uri         = "$ServiceUrl/api/v1/scheduler/ingest"
        Body        = '{"sources": ["tavily", "sec", "earnings", "press_releases", "rss", "stocknews"]}'
        Timeout     = "3600s"
        Description = "Deep Loop: Comprehensive daily ingestion (Web Search, SEC, Earnings)"
    },
    @{
        Name        = "weekly-executive-briefing"
        Schedule    = "30 14 * * 1" # 14:30 UTC = 8:30 AM CST
        Uri         = "$ServiceUrl/api/v1/scheduler/briefing"
        Body        = '{}'
        Timeout     = "900s"
        Description = "Briefing Job: Generates weekly 'Need to Know' report"
    }
)

# Legacy Jobs to DELETE
$LegacyJobs = @("daily-morning-ingest", "orchestrator-ingestion-morning", "orchestrator-ingestion-evening")

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
    $exists = gcloud scheduler jobs describe $job.Name --location=$Region --quiet 2>$null
    
    if ($exists) {
        Write-Host "Updating job: $($job.Name)" -ForegroundColor Cyan
        gcloud scheduler jobs update http $job.Name `
            --location=$Region `
            --schedule=$job.Schedule `
            --uri=$job.Uri `
            --http-method=POST `
            --headers="Content-Type=application/json" `
            --message-body=$job.Body `
            --time-zone="UTC" `
            --oidc-service-account-email=$ServiceAccount `
            --oidc-token-audience=$ServiceUrl `
            --attempt-deadline=$job.Timeout `
            --description=$job.Description `
            --quiet
    }
    else {
        Write-Host "Creating job: $($job.Name)" -ForegroundColor Green
        gcloud scheduler jobs create http $job.Name `
            --location=$Region `
            --schedule=$job.Schedule `
            --uri=$job.Uri `
            --http-method=POST `
            --headers="Content-Type=application/json" `
            --message-body=$job.Body `
            --time-zone="UTC" `
            --oidc-service-account-email=$ServiceAccount `
            --oidc-token-audience=$ServiceUrl `
            --attempt-deadline=$job.Timeout `
            --description=$job.Description `
            --quiet
    }
}

Write-Host "Scheduler Deployment Complete!" -ForegroundColor Green
