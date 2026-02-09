"""
ImportYeti Ingestion — Pipeline Configuration

All configurable settings in one place. API key loaded from environment
or from the app settings module.
"""
import os
from pathlib import Path

# ─────────────────────────────────────────
# Paths (relative to this module)
# ─────────────────────────────────────────
MODULE_ROOT = Path(__file__).parent.parent          # importyeti/
CONFIG_DIR = Path(__file__).parent                  # importyeti/config/
COMPETITORS_PATH = CONFIG_DIR / "competitors.json"

# ─────────────────────────────────────────
# ImportYeti API
# ─────────────────────────────────────────
def get_importyeti_api_key() -> str:
    """Get API key from environment or app settings."""
    key = os.getenv("IMPORTYETI_API_KEY", "")
    if not key:
        try:
            from app.config.settings import settings
            key = settings.importyeti_api_key
        except Exception:
            pass
    return key


IMPORTYETI_BASE_URL = "https://data.importyeti.com/v1.0"

# API behavior
API_TIMEOUT_SECONDS = 30
API_RETRY_ATTEMPTS = 3
API_RETRY_DELAY_SECONDS = 2       # Base delay, exponential backoff applied
API_DELAY_BETWEEN_CALLS = 0.5     # Courtesy delay between calls (seconds)

# ─────────────────────────────────────────
# BigQuery Settings
# ─────────────────────────────────────────
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "gen-lang-client-0436975498")
BQ_DATASET = "c1_intelligence"

# Table names
TABLE_COMPANIES = "iy_companies"
TABLE_SUPPLIERS = "iy_suppliers"
TABLE_EDGES = "iy_edges"
TABLE_INGESTION_LOG = "iy_ingestion_log"

# View names
VIEW_SHARED_SUPPLIERS = "iy_v_shared_suppliers"
VIEW_SHARED_SUPPLIERS_12M = "iy_v_shared_suppliers_12m"
VIEW_EXCLUSIVE_SUPPLIERS = "iy_v_exclusive_suppliers"
VIEW_COMPETITOR_ACTIVITY_12M = "iy_v_competitor_activity_12m"
VIEW_BUYER_OVERLAP = "iy_v_buyer_overlap"

# ─────────────────────────────────────────
# Pipeline Settings
# ─────────────────────────────────────────

# Maximum number of suppliers to pull per company.
# ImportYeti can return hundreds — this caps how deep we go.
MAX_SUPPLIERS_PER_COMPANY = 100

# Maximum number of downstream buyers to store per supplier.
MAX_BUYERS_PER_SUPPLIER = 50

# When resolving company names via /company/search, how many
# search results to consider before picking the best match.
MAX_SEARCH_RESULTS_TO_CONSIDER = 5

# ─────────────────────────────────────────
# Logging
# ─────────────────────────────────────────
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
