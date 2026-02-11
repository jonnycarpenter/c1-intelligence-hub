#!/usr/bin/env pwsh
# Verify Backfill Execution - Check what actually ran

$ProjectId = "<GCP_PROJECT_ID>"

Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "BACKFILL VERIFICATION REPORT" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host ""

# Get recent logs
Write-Host "Fetching Cloud Run logs..." -ForegroundColor Yellow
$allLogs = gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=c1-hub" --limit 300 --project=$ProjectId --format=json | ConvertFrom-Json

# Filter for pipeline steps
$stepLogs = $allLogs | Where-Object { $_.textPayload -match "Step \d" } | Select-Object -First 20

Write-Host "`n📋 PIPELINE STEPS EXECUTED:" -ForegroundColor Green
Write-Host "-" * 80
foreach ($log in $stepLogs | Sort-Object timestamp -Descending | Select-Object -First 15) {
    $text = $log.textPayload
    $time = $log.timestamp
    if ($text -match "(Step \d[ab]?:.*?)(?=\||$)") {
        Write-Host "  ✅ $($matches[1].Trim()) - $time" -ForegroundColor White
    }
}

# Check for specific indicators
Write-Host "`n📊 KEY METRICS:" -ForegroundColor Green
Write-Host "-" * 80

$storedArticles = $allLogs | Where-Object { $_.textPayload -match "Stored (\d+) articles in BigQuery" } | Select-Object -First 1
if ($storedArticles -and $storedArticles.textPayload -match "Stored (\d+)") {
    Write-Host "  Articles Stored: $($matches[1])" -ForegroundColor White
}

$storedDigest = $allLogs | Where-Object { $_.textPayload -match "Stored (\d+) digest items" } | Select-Object -First 1
if ($storedDigest -and $storedDigest.textPayload -match "Stored (\d+)") {
    Write-Host "  Digest Items: $($matches[1])" -ForegroundColor White
}

$vectorsAdded = $allLogs | Where-Object { $_.textPayload -match "Added (\d+) items to" } | Select-Object -First 1
if ($vectorsAdded -and $vectorsAdded.textPayload -match "Added (\d+)") {
    Write-Host "  Vector Embeddings: $($matches[1])" -ForegroundColor White
}

# Check for image extraction
Write-Host "`n🖼️  IMAGE EXTRACTION:" -ForegroundColor Green
Write-Host "-" * 80
$imageLogs = $allLogs | Where-Object { $_.textPayload -match "(image|Image|Step 5b)" }

if ($imageLogs) {
    $imageExtracted = $imageLogs | Where-Object { $_.textPayload -match "Extracted (\d+) images" } | Select-Object -First 1
    $imageStored = $imageLogs | Where-Object { $_.textPayload -match "Stored (\d+) images" } | Select-Object -First 1
    $imageStep = $imageLogs | Where-Object { $_.textPayload -match "Step 5b" } | Select-Object -First 1
    
    if ($imageStep) {
        Write-Host "  ✅ Step 5b executed" -ForegroundColor Green
    }
    else {
        Write-Host "  ⚠️  Step 5b not found in logs (may have been skipped)" -ForegroundColor Yellow
    }
    
    if ($imageExtracted -and ($imageExtracted.textPayload -match "Extracted (\d+)")) {
        Write-Host "  🖼️  Images Extracted: $($matches[1])" -ForegroundColor White
    }
    else {
        Write-Host "  ℹ️  No images extracted (expected if articles didn't meet relevance threshold)" -ForegroundColor Cyan
    }
    
    if ($imageStored -and ($imageStored.textPayload -match "Stored (\d+)")) {
        Write-Host "  💾 Images Stored: $($matches[1])" -ForegroundColor White
    }
}
else {
    Write-Host "  ⚠️  No image extraction logs found" -ForegroundColor Yellow
    Write-Host "  ℹ️  This is NORMAL if:" -ForegroundColor Cyan
    Write-Host "     - No articles met relevance threshold (>0.6)" -ForegroundColor Cyan
    Write-Host "     - Image enrichment was skipped during backfill" -ForegroundColor Cyan
}

# Check for completion
Write-Host "`n⏱️  EXECUTION STATUS:" -ForegroundColor Green
Write-Host "-" * 80
$completeLogs = $allLogs | Where-Object { $_.textPayload -match "Ingestion complete" } | Select-Object -First 1
if ($completeLogs) {
    if ($completeLogs.textPayload -match "(\d+\.\d+)s") {
        Write-Host "  ✅ COMPLETED in $($matches[1]) seconds" -ForegroundColor Green
        Write-Host "  Timestamp: $($completeLogs.timestamp)" -ForegroundColor Cyan
    }
    else {
        Write-Host "  ✅ COMPLETED" -ForegroundColor Green
    }
}
else {
    Write-Host "  ⚠️  No completion log found - checking for errors..." -ForegroundColor Yellow
    
    $errors = $allLogs | Where-Object { $_.textPayload -match "(error|Error|ERROR|failed|Failed)" } | Select-Object -First 5
    if ($errors) {
        Write-Host "`n  ❌ ERRORS FOUND:" -ForegroundColor Red
        foreach ($err in $errors) {
            Write-Host "     - $($err.textPayload.Substring(0, [Math]::Min(100, $err.textPayload.Length)))..." -ForegroundColor Red
        }
    }
}

Write-Host "`n" + "=" * 80
Write-Host "END REPORT" -ForegroundColor Cyan
Write-Host "=" * 80
Write-Host ""
