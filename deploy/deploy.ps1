# PowerShell deployment script for C1 Intelligence Hub
# Run from the c1-intelligence-hub_v2 directory

param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectId,
    
    [string]$Region = "us-central1",
    [string]$ServiceName = "c1-hub",
    [switch]$SkipBuild,
    [switch]$SetupOnly
)

$ErrorActionPreference = "Stop"

# Configuration
$RepositoryName = "c1-intelligence-hub"
$BucketName = "$ProjectId-c1-hub-data"
$ImageTag = "latest"
$FullImageName = "$Region-docker.pkg.dev/$ProjectId/$RepositoryName/${ServiceName}:$ImageTag"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "C1 Intelligence Hub - GCP Deployment" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Project: $ProjectId"
Write-Host "Region: $Region"
Write-Host "Service: $ServiceName"
Write-Host "Bucket: $BucketName"
Write-Host ""

# Set project
Write-Host "Setting GCP project..." -ForegroundColor Yellow
gcloud config set project $ProjectId

if ($SetupOnly) {
    Write-Host ""
    Write-Host "Running setup only (no deployment)..." -ForegroundColor Yellow
    
    # Enable APIs
    Write-Host "Enabling required APIs..." -ForegroundColor Yellow
    $apis = @(
        "run.googleapis.com",
        "cloudbuild.googleapis.com",
        "artifactregistry.googleapis.com",
        "secretmanager.googleapis.com",
        "storage.googleapis.com"
    )
    foreach ($api in $apis) {
        Write-Host "  Enabling $api..."
        gcloud services enable $api --quiet
    }
    
    # Create Artifact Registry
    Write-Host "Creating Artifact Registry repository..." -ForegroundColor Yellow
    gcloud artifacts repositories create $RepositoryName `
        --repository-format=docker `
        --location=$Region `
        --description="C1 Intelligence Hub container images" `
        --quiet 2>$null
    
    # Create GCS Bucket
    Write-Host "Creating GCS bucket..." -ForegroundColor Yellow
    gsutil mb -l $Region "gs://$BucketName" 2>$null
    
    # Create folder structure
    Write-Host "Creating bucket folder structure..." -ForegroundColor Yellow
    "" | gsutil cp - "gs://$BucketName/chroma/.keep"
    "" | gsutil cp - "gs://$BucketName/knowledge_db/.keep"
    "" | gsutil cp - "gs://$BucketName/downloads/.keep"
    
    # Create placeholder secrets
    Write-Host "Creating Secret Manager secrets (placeholders)..." -ForegroundColor Yellow
    $secrets = @("anthropic-api-key", "fmp-api-key", "api-ninja-key", "importyeti-api-key", "apollo-api-key")
    foreach ($secret in $secrets) {
        $exists = gcloud secrets describe $secret 2>$null
        if (-not $exists) {
            "PLACEHOLDER_UPDATE_ME" | gcloud secrets create $secret --data-file=- --replication-policy="automatic"
            Write-Host "  Created: $secret"
        }
        else {
            Write-Host "  Exists: $secret" -ForegroundColor DarkGray
        }
    }
    
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "Setup Complete!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Yellow
    Write-Host "1. Update secrets with real API keys:"
    Write-Host '   gcloud secrets versions add anthropic-api-key --data-file=<(echo -n "your-key")'
    Write-Host ""
    Write-Host "2. Run deployment:"
    Write-Host "   .\deploy\deploy.ps1 -ProjectId $ProjectId"
    Write-Host ""
    exit 0
}

# Build and deploy using Cloud Build (no local Docker required)
if (-not $SkipBuild) {
    Write-Host ""
    Write-Host "Building and deploying with Cloud Build..." -ForegroundColor Yellow
    Write-Host "This will build remotely and deploy automatically." -ForegroundColor Cyan
    Write-Host ""
    
    # Use Cloud Build to build and deploy
    # This avoids local Docker dependency and builds in GCP
    gcloud builds submit `
        --config="deploy/cloudbuild.yaml" `
        --project=$ProjectId `
        --substitutions="_TAG=prod-$(Get-Date -Format 'yyyyMMdd-HHmmss'),_DATA_BUCKET=$BucketName" `
        .
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Cloud Build failed!" -ForegroundColor Red
        exit 1
    }
    
    Write-Host ""
    Write-Host "✅ Build and deployment completed via Cloud Build" -ForegroundColor Green
}

# Cloud Build handles deployment automatically
# No need for separate gcloud run deploy

# Get service URL
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Deployment Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

$serviceUrl = gcloud run services describe $ServiceName --region $Region --format="value(status.url)"
Write-Host "Service URL: $serviceUrl" -ForegroundColor Cyan
Write-Host ""
Write-Host "Test the deployment:"
Write-Host "  curl $serviceUrl/health"
Write-Host "  curl $serviceUrl/api/products"
Write-Host ""
