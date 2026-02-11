#!/usr/bin/env pwsh
# Reset Cloud Scheduler to Normal Configuration
# Run this AFTER backfill completes

$ProjectId = "<GCP_PROJECT_ID>"
$Location = "us-central1"

Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "RESETTING SCHEDULER TO NORMAL CONFIGURATION" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host ""

# Reset morning job
Write-Host "Resetting daily-morning-ingest..." -ForegroundColor Yellow
gcloud scheduler jobs update http daily-morning-ingest `
    --location=$Location `
    --message-body='{}' `
    --project=$ProjectId

if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✅ Reset successfully" -ForegroundColor Green
}
else {
    Write-Host "  ❌ Failed to reset" -ForegroundColor Red
}

Write-Host ""
Write-Host "=" * 80 -ForegroundColor Green
Write-Host "SCHEDULER RESET COMPLETE" -ForegroundColor Green
Write-Host "=" * 80 -ForegroundColor Green
Write-Host ""
Write-Host "Scheduler jobs will now run normal 3-day ingestion windows (no backfill)."
Write-Host ""
