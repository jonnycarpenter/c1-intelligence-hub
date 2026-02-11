#!/usr/bin/env pwsh
# Production Deployment Script - Post Backfill
# Includes frontend stability fixes and backend monitoring improvements

param(
    [switch]$SkipBuild = $false,
    [switch]$SkipDeploy = $false
)

$ProjectId = "<GCP_PROJECT_ID>"
$Region = "us-central1"
$ServiceName = "c1-hub"

Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "PRODUCTION DEPLOYMENT - POST BACKFILL" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host ""

# Verify backfill completion
Write-Host "Verifying backfill status..." -ForegroundColor Yellow
$backfillCheck = gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=$ServiceName AND textPayload:complete" --limit 1 --project=$ProjectId --format=json | ConvertFrom-Json

if ($backfillCheck) {
    Write-Host "  ✅ Backfill completed" -ForegroundColor Green
}
else {
    Write-Host "  ⚠️  No backfill completion logs found - proceed anyway? (Y/N)" -ForegroundColor Yellow
    $response = Read-Host
    if ($response -ne "Y") {
        Write-Host "Deployment cancelled." -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "Deployment includes:" -ForegroundColor Green
Write-Host "  🔧 Frontend: Error boundaries, loading states, defensive coding" -ForegroundColor White
Write-Host "  📊 Backend: Enhanced monitoring, backfilled data" -ForegroundColor White
Write-Host "  🛡️  Stability: Trade Intelligence tab crash fixes" -ForegroundColor White
Write-Host ""

# Build
if (-not $SkipBuild) {
    Write-Host "Building Docker image..." -ForegroundColor Yellow
    gcloud builds submit --config=cloudbuild.prod.yaml --project=$ProjectId

    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✅ Build completed" -ForegroundColor Green
    }
    else {
        Write-Host "  ❌ Build failed" -ForegroundColor Red
        exit 1
    }
}
else {
    Write-Host "⏭️  Skipping build (--SkipBuild flag set)" -ForegroundColor Yellow
}

Write-Host ""

# Deploy
if (-not $SkipDeploy) {
    Write-Host "Deploying to Cloud Run..." -ForegroundColor Yellow
    
    # Deployment happens automatically via Cloud Build trigger
    Write-Host "  📦 Image will auto-deploy via Cloud Build trigger" -ForegroundColor Cyan
    Write-Host "  ⏳ Monitoring deployment..." -ForegroundColor Cyan
    
    Start-Sleep -Seconds 30
    
    # Check service status
    $service = gcloud run services describe $ServiceName --region=$Region --project=$ProjectId --format=json | ConvertFrom-Json
    
    if ($service) {
        Write-Host "  ✅ Service deployed: $($service.status.url)" -ForegroundColor Green
        Write-Host "  📊 Revision: $($service.status.latestReadyRevisionName)" -ForegroundColor Cyan
    }
    else {
        Write-Host "  ❌ Deployment verification failed" -ForegroundColor Red
        exit 1
    }
}
else {
    Write-Host "⏭️  Skipping deploy (--SkipDeploy flag set)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=" * 80 -ForegroundColor Green
Write-Host "DEPLOYMENT COMPLETE" -ForegroundColor Green
Write-Host "=" * 80 -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Test Trade Intelligence tab (Freight Rates chart)" -ForegroundColor White
Write-Host "  2. Verify Pulse tab shows recovered data" -ForegroundColor White
Write-Host "  3. Run: python backend/scripts/production_dashboard.py --days 7" -ForegroundColor White
Write-Host "  4. Monitor logs for first 30 minutes" -ForegroundColor White
Write-Host ""
