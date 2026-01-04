# =============================================================================
# Terraform Configuration for C1 Intelligence Hub
# =============================================================================
# Infrastructure as Code for GCP resources
#
# Usage:
#   cd deploy/terraform
#   terraform init
#   terraform plan -var="project_id=YOUR_PROJECT_ID"
#   terraform apply -var="project_id=YOUR_PROJECT_ID"
# =============================================================================

terraform {
  required_version = ">= 1.0"
  
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
  
  # Uncomment to use GCS backend for state
  # backend "gcs" {
  #   bucket = "YOUR_PROJECT_ID-terraform-state"
  #   prefix = "c1-intelligence-hub"
  # }
}

# =============================================================================
# Variables
# =============================================================================

variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP Region"
  type        = string
  default     = "us-central1"
}

variable "environment" {
  description = "Environment (development, staging, production)"
  type        = string
  default     = "production"
}

# =============================================================================
# Provider Configuration
# =============================================================================

provider "google" {
  project = var.project_id
  region  = var.region
}

# =============================================================================
# Enable APIs
# =============================================================================

resource "google_project_service" "apis" {
  for_each = toset([
    "run.googleapis.com",
    "cloudbuild.googleapis.com",
    "artifactregistry.googleapis.com",
    "secretmanager.googleapis.com",
    "storage.googleapis.com",
    "bigquery.googleapis.com",
    "cloudscheduler.googleapis.com",
  ])
  
  project = var.project_id
  service = each.value
  
  disable_on_destroy = false
}

# =============================================================================
# Artifact Registry
# =============================================================================

resource "google_artifact_registry_repository" "c1_hub" {
  location      = var.region
  repository_id = "c1-intelligence-hub"
  description   = "C1 Intelligence Hub container images"
  format        = "DOCKER"
  
  depends_on = [google_project_service.apis]
}

# =============================================================================
# Cloud Storage Bucket
# =============================================================================

resource "google_storage_bucket" "data_bucket" {
  name          = "${var.project_id}-c1-hub-data"
  location      = var.region
  storage_class = "STANDARD"
  
  uniform_bucket_level_access = true
  
  lifecycle_rule {
    condition {
      age = 30
      matches_prefix = ["downloads/"]
    }
    action {
      type = "Delete"
    }
  }
  
  depends_on = [google_project_service.apis]
}

# Create folder structure via placeholder objects
resource "google_storage_bucket_object" "folders" {
  for_each = toset(["chroma/.keep", "knowledge_db/.keep", "downloads/.keep"])
  
  name    = each.value
  content = ""
  bucket  = google_storage_bucket.data_bucket.name
}

# =============================================================================
# BigQuery Dataset and Tables
# =============================================================================

resource "google_bigquery_dataset" "c1_intelligence" {
  dataset_id  = "c1_intelligence"
  description = "C1 Intelligence Hub time-series data"
  location    = var.region
  
  depends_on = [google_project_service.apis]
}

# Freight Rates Table
resource "google_bigquery_table" "freight_rates" {
  dataset_id = google_bigquery_dataset.c1_intelligence.dataset_id
  table_id   = "freight_rates"
  
  description = "Freight rate time-series data"
  
  time_partitioning {
    type  = "DAY"
    field = "date"
  }
  
  clustering = ["index_name", "lane_code"]
  
  schema = jsonencode([
    { name = "date", type = "DATE", mode = "REQUIRED" },
    { name = "index_name", type = "STRING", mode = "REQUIRED" },
    { name = "lane_code", type = "STRING", mode = "REQUIRED" },
    { name = "lane_description", type = "STRING" },
    { name = "rate_usd", type = "FLOAT64", mode = "REQUIRED" },
    { name = "rate_unit", type = "STRING" },
    { name = "change_wow", type = "FLOAT64" },
    { name = "change_mom", type = "FLOAT64" },
    { name = "change_yoy", type = "FLOAT64" },
    { name = "source", type = "STRING" },
    { name = "fetched_at", type = "TIMESTAMP", mode = "REQUIRED" },
  ])
}

# Commodity Prices Table
resource "google_bigquery_table" "commodity_prices" {
  dataset_id = google_bigquery_dataset.c1_intelligence.dataset_id
  table_id   = "commodity_prices"
  
  description = "Commodity price time-series data"
  
  time_partitioning {
    type  = "DAY"
    field = "date"
  }
  
  clustering = ["symbol"]
  
  schema = jsonencode([
    { name = "date", type = "DATE", mode = "REQUIRED" },
    { name = "symbol", type = "STRING", mode = "REQUIRED" },
    { name = "name", type = "STRING" },
    { name = "price", type = "FLOAT64", mode = "REQUIRED" },
    { name = "currency", type = "STRING" },
    { name = "unit", type = "STRING" },
    { name = "change_pct", type = "FLOAT64" },
    { name = "source", type = "STRING" },
    { name = "fetched_at", type = "TIMESTAMP", mode = "REQUIRED" },
  ])
}

# Articles Table
resource "google_bigquery_table" "articles" {
  dataset_id = google_bigquery_dataset.c1_intelligence.dataset_id
  table_id   = "articles"
  
  description = "News and articles storage"
  
  time_partitioning {
    type  = "MONTH"
    field = "published_at"
  }
  
  clustering = ["source_type", "category"]
  
  schema = jsonencode([
    { name = "id", type = "STRING", mode = "REQUIRED" },
    { name = "title", type = "STRING", mode = "REQUIRED" },
    { name = "url", type = "STRING" },
    { name = "published_at", type = "TIMESTAMP" },
    { name = "source_name", type = "STRING" },
    { name = "source_type", type = "STRING" },
    { name = "summary", type = "STRING" },
    { name = "category", type = "STRING" },
    { name = "topics", type = "STRING" },
    { name = "companies_mentioned", type = "STRING" },
    { name = "relevance_score", type = "FLOAT64" },
    { name = "fetched_at", type = "TIMESTAMP", mode = "REQUIRED" },
  ])
}

# Collection Log Table
resource "google_bigquery_table" "collection_log" {
  dataset_id = google_bigquery_dataset.c1_intelligence.dataset_id
  table_id   = "collection_log"
  
  description = "Data collection run logs"
  
  time_partitioning {
    type  = "DAY"
    field = "started_at"
  }
  
  schema = jsonencode([
    { name = "id", type = "STRING", mode = "REQUIRED" },
    { name = "source", type = "STRING", mode = "REQUIRED" },
    { name = "cadence", type = "STRING" },
    { name = "started_at", type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "completed_at", type = "TIMESTAMP" },
    { name = "records_collected", type = "INT64" },
    { name = "status", type = "STRING" },
    { name = "error_message", type = "STRING" },
  ])
}

# =============================================================================
# Secret Manager
# =============================================================================

resource "google_secret_manager_secret" "api_keys" {
  for_each = toset([
    "anthropic-api-key",
    "fmp-api-key",
    "api-ninja-key",
    "tavily-api-key",
  ])
  
  secret_id = each.value
  
  replication {
    auto {}
  }
  
  depends_on = [google_project_service.apis]
}

# =============================================================================
# Service Accounts
# =============================================================================

# Scheduler invoker service account
resource "google_service_account" "scheduler_invoker" {
  account_id   = "scheduler-invoker"
  display_name = "Cloud Scheduler Invoker"
  description  = "Service account for Cloud Scheduler to invoke Cloud Run"
}

# =============================================================================
# IAM Bindings
# =============================================================================

# Get the default compute service account
data "google_compute_default_service_account" "default" {
  project = var.project_id
}

# Grant Cloud Run SA access to BigQuery
resource "google_project_iam_member" "cloud_run_bigquery_editor" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${data.google_compute_default_service_account.default.email}"
}

resource "google_project_iam_member" "cloud_run_bigquery_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${data.google_compute_default_service_account.default.email}"
}

# Grant Cloud Run SA access to GCS bucket
resource "google_storage_bucket_iam_member" "cloud_run_gcs" {
  bucket = google_storage_bucket.data_bucket.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${data.google_compute_default_service_account.default.email}"
}

# Grant Cloud Run SA access to secrets
resource "google_secret_manager_secret_iam_member" "cloud_run_secrets" {
  for_each = google_secret_manager_secret.api_keys
  
  secret_id = each.value.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${data.google_compute_default_service_account.default.email}"
}

# =============================================================================
# Outputs
# =============================================================================

output "artifact_registry_url" {
  description = "Artifact Registry URL"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.c1_hub.repository_id}"
}

output "data_bucket_name" {
  description = "GCS bucket name for data"
  value       = google_storage_bucket.data_bucket.name
}

output "bigquery_dataset" {
  description = "BigQuery dataset ID"
  value       = google_bigquery_dataset.c1_intelligence.dataset_id
}

output "scheduler_service_account" {
  description = "Scheduler service account email"
  value       = google_service_account.scheduler_invoker.email
}

output "next_steps" {
  description = "Next steps after terraform apply"
  value       = <<-EOT
    
    Next Steps:
    1. Add API key values to secrets:
       echo -n "YOUR_KEY" | gcloud secrets versions add anthropic-api-key --data-file=-
       echo -n "YOUR_KEY" | gcloud secrets versions add fmp-api-key --data-file=-
       echo -n "YOUR_KEY" | gcloud secrets versions add api-ninja-key --data-file=-
       echo -n "YOUR_KEY" | gcloud secrets versions add tavily-api-key --data-file=-
    
    2. Deploy to Cloud Run:
       gcloud builds submit --config=deploy/cloudbuild.yaml \
         --substitutions=_DATA_BUCKET=${google_storage_bucket.data_bucket.name}
    
    3. Deploy scheduler jobs (after Cloud Run):
       ./deploy/scheduler/deploy-scheduler.sh ${var.project_id} <CLOUD_RUN_URL>
  EOT
}
