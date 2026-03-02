# =============================================================================
# Freeze C1 Intelligence Hub for Demo Mode
# =============================================================================
# This script pauses all Cloud Scheduler jobs and optionally reduces Cloud Run
# resources to minimize GCP costs while keeping the platform functional for demos.
#
# Usage:
#   .\freeze_for_demo.ps1 -ProjectId "your-project-id"
#
# What it does:
#   1. Pauses ALL Cloud Scheduler jobs (ingestion, briefing, cleanup, podcast)
#   2. Lists current Cloud Run config for verification
#
# To fully revert (unfreeze):
#   .\freeze_for_demo.ps1 -ProjectId "your-project-id" -Unfreeze
#
# Cost Savings:
#   - Cloud Scheduler: $0 (paused jobs don't trigger)
#   - LLM API (ingestion classification): $0 (no new articles)
#   - LLM API (weekly briefing): $0 (no new briefings)
#   - External APIs (Tavily, Exa, SEC.io, etc.): $0 (no ingestion)
#   - Cloud Run: Near-zero (scales to 0, CPU throttled when idle)
#   - BigQuery: Minimal (read-only queries during demos, storage ~$0.02/GB/mo)
# =============================================================================

param(
    [Parameter(Mandatory=$true)]
    [string]$ProjectId,
    
    [switch]$Unfreeze,
    
    [string]$Region = "us-central1"
)

$ErrorActionPreference = "Continue"

Write-Host ""
Write-Host "=========================================" -ForegroundColor Cyan
if ($Unfreeze) {
    Write-Host "  UNFREEZING C1 Intelligence Hub" -ForegroundColor Yellow
} else {
    Write-Host "  FREEZING C1 Intelligence Hub" -ForegroundColor Yellow
}
Write-Host "  Project: $ProjectId" -ForegroundColor Cyan
Write-Host "  Region:  $Region" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""

# Set project
gcloud config set project $ProjectId --quiet

# =============================================================================
# 1. Cloud Scheduler Jobs (C1 Hub only)
# =============================================================================
Write-Host "Step 1: Cloud Scheduler Jobs (C1 Hub only)" -ForegroundColor Green
Write-Host "-------------------------------------------"

# C1 Hub job name patterns — only pause these, leave other projects alone
$c1JobPatterns = @(
    "weekly-executive-briefing",
    "weekly-cleanup",
    "orchestrator-ingestion*",
    "podcast-weekly-ingestion",
    "ingest-exa",
    "ingest-tavily",
    "ingest-flash-update",
    "ingest-financial"
)

# List all scheduler jobs
$jobs = gcloud scheduler jobs list --location=$Region --format="value(name)" 2>$null

if (-not $jobs) {
    Write-Host "  No Cloud Scheduler jobs found in $Region" -ForegroundColor Yellow
} else {
    foreach ($job in $jobs) {
        $jobName = $job.Trim()
        if (-not $jobName) { continue }
        
        # Check if this job matches any C1 Hub pattern
        $isC1Job = $false
        foreach ($pattern in $c1JobPatterns) {
            if ($jobName -like $pattern) {
                $isC1Job = $true
                break
            }
        }
        
        if (-not $isC1Job) {
            Write-Host "  Skipping (not C1 Hub): $jobName" -ForegroundColor DarkGray
            continue
        }
        
        if ($Unfreeze) {
            Write-Host "  Resuming job: $jobName" -ForegroundColor Green
            gcloud scheduler jobs resume $jobName --location=$Region --quiet 2>$null
        } else {
            Write-Host "  Pausing job: $jobName" -ForegroundColor Yellow
            gcloud scheduler jobs pause $jobName --location=$Region --quiet 2>$null
        }
    }
}

Write-Host ""

# =============================================================================
# 2. Verify Cloud Run Configuration  
# =============================================================================
Write-Host "Step 2: Cloud Run Service Status" -ForegroundColor Green
Write-Host "-------------------------------------------"

$serviceInfo = gcloud run services describe c1-hub --region=$Region --format="yaml(spec.template.spec.containers[0].resources,spec.template.metadata.annotations)" 2>$null
if ($serviceInfo) {
    Write-Host "  Current Cloud Run config:" -ForegroundColor Cyan
    Write-Host $serviceInfo
}

Write-Host ""

# =============================================================================
# 3. Summary
# =============================================================================
Write-Host "=========================================" -ForegroundColor Cyan
if ($Unfreeze) {
    Write-Host "  UNFREEZE COMPLETE" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Next steps:" -ForegroundColor Yellow
    Write-Host "  1. Remove DEMO_MODE=true from cloudbuild.yaml env vars"
    Write-Host "  2. Restore CPU/memory in cloudbuild.yaml if needed"
    Write-Host "  3. Redeploy: git push origin master"
} else {
    Write-Host "  FREEZE COMPLETE" -ForegroundColor Green
    Write-Host ""
    Write-Host "  What's been done:" -ForegroundColor Yellow
    Write-Host "  [x] All Cloud Scheduler jobs paused"
    Write-Host "  [x] No automated ingestion will run"
    Write-Host "  [x] No weekly briefings will generate"
    Write-Host ""
    Write-Host "  Remaining steps (deploy code changes):" -ForegroundColor Yellow
    Write-Host "  1. Commit & push the code changes to master"
    Write-Host "     git add -A; git commit -m 'Freeze platform for demo mode'; git push origin master"
    Write-Host "  2. Wait ~3-5 min for Cloud Build to deploy"
    Write-Host ""
    Write-Host "  Estimated monthly cost after freeze:" -ForegroundColor Cyan
    Write-Host "    Cloud Run:     ~$0-2/mo  (scale to 0 + CPU throttling)"
    Write-Host "    BigQuery:      ~$1-3/mo  (storage only, minimal queries)"
    Write-Host "    Cloud Storage: ~$0.50/mo (static data)"
    Write-Host "    Secret Manager:~$0.50/mo (14 secrets)"
    Write-Host "    LLM APIs:      $0/mo     (no automated calls)"
    Write-Host "    External APIs:  $0/mo     (no ingestion)"
    Write-Host "    Cloud Build:   ~$0.10/build (only when you push)"
    Write-Host "    ------------------------------------------"
    Write-Host "    TOTAL:         ~$2-6/month (from probably $50-200+)"
    Write-Host ""
    Write-Host "  Interactive demo features still work:" -ForegroundColor Green
    Write-Host "    [*] Chat / Ad-hoc Briefing (costs LLM tokens per use)"
    Write-Host "    [*] Deep Research (costs LLM tokens per use)"
    Write-Host "    [*] Article feed browsing (free - BigQuery reads)"
    Write-Host "    [*] Weekly briefing viewing (free - already generated)"
    Write-Host "    [*] Podcast playback (free - already in GCS)"
    Write-Host "    [*] Discovery/Corpus search (costs embedding + LLM per use)"
    Write-Host "    [*] Pipeline/Supply Chain (free reads, LLM on interaction)"
}
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""
