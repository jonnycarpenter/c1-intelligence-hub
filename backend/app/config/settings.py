"""Application settings and configuration."""

import os
from pathlib import Path
from typing import Optional
from pydantic import ConfigDict, Field, AliasChoices
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent  # app/
BACKEND_DIR = BASE_DIR.parent  # backend/
PROJECT_DIR = BACKEND_DIR.parent  # c1-intelligence-hub_v2/
DATA_DIR = BACKEND_DIR / "data"  # backend/data/

# Load environment variables from project root .env
# Check both backend/.env and project root .env
load_dotenv(BACKEND_DIR / ".env")  # backend/.env (if exists)
load_dotenv(PROJECT_DIR / ".env")  # c1-intelligence-hub_v2/.env (main)


class Settings(BaseSettings):
    """Application settings."""
    
    # Allow model_ prefix for our model configuration fields
    model_config = ConfigDict(
        protected_namespaces=(),
        env_file=(PROJECT_DIR / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )
    
    # Environment
    environment: str = "development"
    log_level: str = "INFO"
    
    # API Keys
    anthropic_api_key: str = ""
    tavily_api_key: str = ""
    exa_api_key: str = Field(validation_alias=AliasChoices("EXA_API_KEY", "EXA_AI_API_KEY"), default="")
    groq_api_key: str = ""
    api_ninja_key: str = ""
    stocknews_api_key: str = Field(validation_alias=AliasChoices("STOCKNEWS_API_KEY", "STOCK_NEWS_API_KEY", "STOCK_NEWS_API"), default="")
    fmp_api_key: str = Field(validation_alias=AliasChoices("FMP_API_KEY", "FMP_API_KEY"), default="")  # Financial Modeling Prep
    
    # X/Twitter API (for social intelligence)
    x_bearer_token: str = ""
    
    # ElevenLabs API (for podcast generation)
    elevenlabs_api_key: str = ""
    
    # Logo.dev API (for company logos)
    logo_dev_token: str = ""
    
    # Apollo.io API (for company enrichment and contact discovery)
    apollo_api_key: str = Field(
        validation_alias=AliasChoices("APOLLO_API_KEY", "APOLLO_IO_API_KEY"),
        default=""
    )
    
    # Freightos API (for freight/container rates)
    freightos_api_key: str = ""
    
    # ImportYeti API (for US Customs trade data)
    importyeti_api_key: str = Field(
        validation_alias=AliasChoices("IMPORTYETI_API_KEY", "IMPORT_YETI_API_KEY"),
        default=""
    )
    
    # Site Access (simple password gate for pilot)
    site_access_password: str = Field(
        validation_alias=AliasChoices("SITE_ACCESS_PASSWORD", "ACCESS_PASSWORD"),
        default=""
    )
    
    # GCP Configuration (for production storage)
    # Hardcoded production defaults - BigQuery is ALWAYS the destination
    gcp_project_id: str = "gen-lang-client-0436975498"
    gcp_dataset_id: str = "c1_intelligence"
    gcs_bucket_name: str = "gen-lang-client-0436975498-c1-hub-data"
    gcp_location: str = "us-central1"
    
    # LangSmith (optional)
    langchain_api_key: Optional[str] = None
    langchain_tracing_v2: bool = True
    langchain_project: str = "c1-intelligence-hub-v2"
    
    # Tool Configuration
    sec_api_key: str = Field(validation_alias=AliasChoices("SEC_IO_KEY", "SEC_IO_API_KEY"), default="")
    
    # Press Release Tool
    pr_sources: list = ["prnewswire.com", "businesswire.com", "globenewswire.com"]
    pr_search_depth: str = "advanced"
    pr_max_results: int = 10
    
    # SEC Tool
    sec_filing_types: list = ["10-K", "10-Q", "8-K"]
    sec_extract_sections: list = ["1", "1A", "7", "7A"]
    
    # Deep Research Workflow models will be added here
    
    # Groq model for X/Twitter analysis (fast inference)
    model_groq_x_analyzer: str = "llama-3.3-70b-versatile"
    
    # API Ninjas
    api_ninja_base_url: str = "https://api.api-ninjas.com/v1"
    
    # Tavily
    tavily_max_results: int = 5
    
    # Paths
    base_dir: Path = BASE_DIR
    data_dir: Path = DATA_DIR
    
    # Data files
    @property
    def companies_file(self) -> Path:
        # Use resources directory for static master lists to avoid GCS mount issues
        static_file = self.base_dir / "resources" / "master_company_list.csv"
        if static_file.exists():
            return static_file
        return self.data_dir / "master_company_list.csv"
    
    @property
    def materials_file(self) -> Path:
        static_file = self.base_dir / "resources" / "master_materials_list.csv"
        if static_file.exists():
            return static_file
        return self.data_dir / "master_materials_list.csv"
    
    @property
    def industries_file(self) -> Path:
        static_file = self.base_dir / "resources" / "master_industries_list.csv"
        if static_file.exists():
            return static_file
        return self.data_dir / "master_industries_list.csv"
    
    @property
    def preferences_file(self) -> Path:
        return self.data_dir / "user_preferences.json"
    
    # Auth (future - scaffolding)
    jwt_secret: Optional[str] = None
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24
    
    @property
    def is_gcp_configured(self) -> bool:
        """Check if GCP storage is configured."""
        return bool(self.gcp_project_id and self.gcs_bucket_name)


# Create settings instance
settings = Settings()

# Set environment variables for LangChain
if settings.langchain_api_key:
    os.environ["LANGCHAIN_API_KEY"] = settings.langchain_api_key
    os.environ["LANGCHAIN_TRACING_V2"] = str(settings.langchain_tracing_v2).lower()
    os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project
