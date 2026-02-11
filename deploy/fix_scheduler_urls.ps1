#!/usr/bin/env pwsh
# Fix Cloud Scheduler Jobs - Point to Correct Service URL

$ErrorActionPreference = "Stop"

$ProjectId = "<GCP_PROJECT_ID>"
$Location = "us-central1"
$CorrectServiceUrl = "https://c1-hub-<GCP_PROJECT_NUMBER>.us-central1.run.app"
$ServiceAccount = "<GCP_PROJECT_NUMBER>-compute@developer.gserviceaccount.com"

Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "FIXING CLOUD SCHEDULER JOBS" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "Correct Service URL: $CorrectServiceUrl"
Write-Host ""

# Update morning ingestion job
Write-Host "[1/2] Updating daily-morning-ingest..." -ForegroundColor Yellow
gcloud scheduler jobs update http daily-morning-ingest `
    --location=$Location `
    --uri="$CorrectServiceUrl/api/v1/scheduler/ingest" `
    --http-method=POST `
    --message-body='{"sources":["tavily","rss","sec"]}' `
    --headers="Content-Type=application/json" `
    --oidc-service-account-email=$ServiceAccount `
    --oidc-token-audience=$CorrectServiceUrl `
    --project=$ProjectId

if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✅ Updated successfully" -ForegroundColor Green
}
else {
    Write-Host "  ❌ Failed to update" -ForegroundColor Red
}
Write-Host ""

# Update evening ingestion job
Write-Host "[2/2] Updating daily-evening-ingest..." -ForegroundColor Yellow
gcloud scheduler jobs update http daily-evening-ingest `
    --location=$Location `
    --uri="$CorrectServiceUrl/api/v1/scheduler/ingest" `
    --http-method=POST `
    --message-body='{"sources":["tavily","rss","sec"]}' `
    --headers="Content-Type=application/json" `
    --oidc-service-account-email=$ServiceAccount `
    --oidc-token-audience=$CorrectServiceUrl `
    --project=$ProjectId

if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✅ Updated successfully" -ForegroundColor Green
}
else {
    Write-Host "  ❌ Failed to update" -ForegroundColor Red
}
Write-Host ""

Write-Host "=" * 80 -ForegroundColor Green
Write-Host "SCHEDULER JOBS UPDATED" -ForegroundColor Green
Write-Host "=" * 80 -ForegroundColor Green
Write-Host ""
Write-Host "Next: Test a job manually" -ForegroundColor Yellow
Write-Host "  gcloud scheduler jobs run daily-morning-ingest --location $Location --project $ProjectId"
Write-Host ""
