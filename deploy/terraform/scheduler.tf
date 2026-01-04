# =============================================================================
# Cloud Scheduler Jobs
# =============================================================================
# Note: These require Cloud Run to be deployed first.
# The service_url variable needs to be set after deployment.
# 
# Either:
# 1. Set after initial apply: terraform apply -var="service_url=https://..."
# 2. Or use deploy-scheduler.sh script
# =============================================================================

variable "service_url" {
  description = "Cloud Run service URL (set after initial deployment)"
  type        = string
  default     = ""
}

variable "enable_scheduler" {
  description = "Enable Cloud Scheduler jobs (set to true after Cloud Run is deployed)"
  type        = bool
  default     = false
}

# Grant scheduler SA permission to invoke Cloud Run
# (This will be applied when Cloud Run is deployed and IAM is set)
resource "google_cloud_run_service_iam_member" "scheduler_invoker" {
  count = var.enable_scheduler ? 1 : 0
  
  # Note: service and location need to match your Cloud Run deployment
  service  = "c1-hub"
  location = var.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduler_invoker.email}"
}

# =============================================================================
# Hourly Jobs (every 4-6 hours)
# =============================================================================

resource "google_cloud_scheduler_job" "collect_stock_news" {
  count = var.enable_scheduler ? 1 : 0
  
  name        = "collect-stock-news"
  description = "Fetch stock news from FMP every 4 hours"
  schedule    = "0 */4 * * *"
  time_zone   = "America/New_York"
  region      = var.region
  
  http_target {
    uri         = "${var.service_url}/api/v1/scheduler/collect"
    http_method = "POST"
    
    headers = {
      "Content-Type" = "application/json"
    }
    
    body = base64encode(jsonencode({
      source  = "stock_news"
      cadence = "hourly"
    }))
    
    oidc_token {
      service_account_email = google_service_account.scheduler_invoker.email
      audience              = var.service_url
    }
  }
  
  retry_config {
    retry_count          = 2
    min_backoff_duration = "30s"
    max_backoff_duration = "300s"
  }
  
  depends_on = [google_project_service.apis]
}

resource "google_cloud_scheduler_job" "collect_tavily_news" {
  count = var.enable_scheduler ? 1 : 0
  
  name        = "collect-tavily-news"
  description = "Fetch industry news via Tavily every 6 hours"
  schedule    = "15 */6 * * *"
  time_zone   = "America/New_York"
  region      = var.region
  
  http_target {
    uri         = "${var.service_url}/api/v1/scheduler/collect"
    http_method = "POST"
    
    headers = {
      "Content-Type" = "application/json"
    }
    
    body = base64encode(jsonencode({
      source  = "tavily_news"
      cadence = "hourly"
    }))
    
    oidc_token {
      service_account_email = google_service_account.scheduler_invoker.email
      audience              = var.service_url
    }
  }
  
  retry_config {
    retry_count          = 2
    min_backoff_duration = "30s"
    max_backoff_duration = "300s"
  }
  
  depends_on = [google_project_service.apis]
}

resource "google_cloud_scheduler_job" "collect_rss_feeds" {
  count = var.enable_scheduler ? 1 : 0
  
  name        = "collect-rss-feeds"
  description = "Fetch RSS feeds every 6 hours"
  schedule    = "30 */6 * * *"
  time_zone   = "America/New_York"
  region      = var.region
  
  http_target {
    uri         = "${var.service_url}/api/v1/scheduler/collect"
    http_method = "POST"
    
    headers = {
      "Content-Type" = "application/json"
    }
    
    body = base64encode(jsonencode({
      source  = "rss_feeds"
      cadence = "hourly"
    }))
    
    oidc_token {
      service_account_email = google_service_account.scheduler_invoker.email
      audience              = var.service_url
    }
  }
  
  retry_config {
    retry_count          = 2
    min_backoff_duration = "30s"
    max_backoff_duration = "300s"
  }
  
  depends_on = [google_project_service.apis]
}

# =============================================================================
# Daily Jobs
# =============================================================================

resource "google_cloud_scheduler_job" "collect_commodity_prices" {
  count = var.enable_scheduler ? 1 : 0
  
  name        = "collect-commodity-prices"
  description = "Fetch daily commodity prices at 6 AM ET"
  schedule    = "0 6 * * *"
  time_zone   = "America/New_York"
  region      = var.region
  
  http_target {
    uri         = "${var.service_url}/api/v1/scheduler/collect"
    http_method = "POST"
    
    headers = {
      "Content-Type" = "application/json"
    }
    
    body = base64encode(jsonencode({
      source  = "commodity_prices"
      cadence = "daily"
    }))
    
    oidc_token {
      service_account_email = google_service_account.scheduler_invoker.email
      audience              = var.service_url
    }
  }
  
  retry_config {
    retry_count          = 3
    min_backoff_duration = "60s"
    max_backoff_duration = "600s"
  }
  
  depends_on = [google_project_service.apis]
}

resource "google_cloud_scheduler_job" "collect_freight_rates" {
  count = var.enable_scheduler ? 1 : 0
  
  name        = "collect-freight-rates"
  description = "Fetch freight rates at 7 AM ET"
  schedule    = "0 7 * * *"
  time_zone   = "America/New_York"
  region      = var.region
  
  http_target {
    uri         = "${var.service_url}/api/v1/scheduler/collect"
    http_method = "POST"
    
    headers = {
      "Content-Type" = "application/json"
    }
    
    body = base64encode(jsonencode({
      source  = "freight_rates"
      cadence = "daily"
    }))
    
    oidc_token {
      service_account_email = google_service_account.scheduler_invoker.email
      audience              = var.service_url
    }
  }
  
  retry_config {
    retry_count          = 3
    min_backoff_duration = "60s"
    max_backoff_duration = "600s"
  }
  
  depends_on = [google_project_service.apis]
}

resource "google_cloud_scheduler_job" "collect_press_releases" {
  count = var.enable_scheduler ? 1 : 0
  
  name        = "collect-press-releases"
  description = "Fetch press releases at 8 AM ET"
  schedule    = "0 8 * * *"
  time_zone   = "America/New_York"
  region      = var.region
  
  http_target {
    uri         = "${var.service_url}/api/v1/scheduler/collect"
    http_method = "POST"
    
    headers = {
      "Content-Type" = "application/json"
    }
    
    body = base64encode(jsonencode({
      source  = "press_releases"
      cadence = "daily"
    }))
    
    oidc_token {
      service_account_email = google_service_account.scheduler_invoker.email
      audience              = var.service_url
    }
  }
  
  retry_config {
    retry_count          = 3
    min_backoff_duration = "60s"
    max_backoff_duration = "600s"
  }
  
  depends_on = [google_project_service.apis]
}

# =============================================================================
# Weekly Jobs
# =============================================================================

resource "google_cloud_scheduler_job" "weekly_cleanup" {
  count = var.enable_scheduler ? 1 : 0
  
  name        = "weekly-data-cleanup"
  description = "Weekly data cleanup on Sundays at 2 AM ET"
  schedule    = "0 2 * * 0"
  time_zone   = "America/New_York"
  region      = var.region
  
  http_target {
    uri         = "${var.service_url}/api/v1/scheduler/maintenance"
    http_method = "POST"
    
    headers = {
      "Content-Type" = "application/json"
    }
    
    body = base64encode(jsonencode({
      task           = "cleanup"
      retention_days = 90
    }))
    
    oidc_token {
      service_account_email = google_service_account.scheduler_invoker.email
      audience              = var.service_url
    }
  }
  
  retry_config {
    retry_count          = 1
    min_backoff_duration = "300s"
    max_backoff_duration = "600s"
  }
  
  depends_on = [google_project_service.apis]
}

resource "google_cloud_scheduler_job" "weekly_reindex" {
  count = var.enable_scheduler ? 1 : 0
  
  name        = "weekly-corpus-refresh"
  description = "Weekly vector store reindex on Sundays at 3 AM ET"
  schedule    = "0 3 * * 0"
  time_zone   = "America/New_York"
  region      = var.region
  
  http_target {
    uri         = "${var.service_url}/api/v1/scheduler/maintenance"
    http_method = "POST"
    
    headers = {
      "Content-Type" = "application/json"
    }
    
    body = base64encode(jsonencode({
      task = "reindex"
    }))
    
    oidc_token {
      service_account_email = google_service_account.scheduler_invoker.email
      audience              = var.service_url
    }
  }
  
  retry_config {
    retry_count          = 1
    min_backoff_duration = "300s"
    max_backoff_duration = "600s"
  }
  
  depends_on = [google_project_service.apis]
}

# =============================================================================
# Quarterly Jobs
# =============================================================================

resource "google_cloud_scheduler_job" "collect_earnings" {
  count = var.enable_scheduler ? 1 : 0
  
  name        = "collect-earnings-transcripts"
  description = "Fetch earnings transcripts quarterly (15th of Jan, Apr, Jul, Oct)"
  schedule    = "0 9 15 1,4,7,10 *"
  time_zone   = "America/New_York"
  region      = var.region
  
  http_target {
    uri         = "${var.service_url}/api/v1/scheduler/collect"
    http_method = "POST"
    
    headers = {
      "Content-Type" = "application/json"
    }
    
    body = base64encode(jsonencode({
      source  = "earnings_transcripts"
      cadence = "quarterly"
    }))
    
    oidc_token {
      service_account_email = google_service_account.scheduler_invoker.email
      audience              = var.service_url
    }
  }
  
  retry_config {
    retry_count          = 3
    min_backoff_duration = "300s"
    max_backoff_duration = "900s"
  }
  
  depends_on = [google_project_service.apis]
}
