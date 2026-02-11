
# Workflow to sync local data to GCS bucket for production
$ProjectId = "<GCP_PROJECT_ID>"
$BucketName = "${ProjectId}-c1-hub-data"

Write-Host "Syncing local data to GCS bucket: $BucketName" -ForegroundColor Cyan

# 1. Sync SQLite DB (if exists)
if (Test-Path "backend/data/c1_corpus.db") {
    Write-Host "Uploading c1_corpus.db..."
    gsutil cp "backend/data/c1_corpus.db" "gs://$BucketName/c1_corpus.db"
}
else {
    Write-Host "Warning: backend/data/c1_corpus.db not found" -ForegroundColor Yellow
}

# 2. Sync ChromaDB (if exists)
if (Test-Path "backend/data/chroma") {
    Write-Host "Uploading chroma..."
    gsutil -m rsync -r "backend/data/chroma" "gs://$BucketName/chroma"
}
else {
    Write-Host "Warning: backend/data/chroma not found" -ForegroundColor Yellow
}

Write-Host "Sync Complete!" -ForegroundColor Green
