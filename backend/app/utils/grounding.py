"""Grounding data loader utilities.

Supports both local CSV files and BigQuery for production.
In production (when GCP_PROJECT_ID is set), data is loaded from BigQuery
for better concurrency support and data persistence.
"""

import pandas as pd
from pathlib import Path
from typing import Dict, Any, Optional
import json
import os

from app.config.settings import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


def _is_production() -> bool:
    """Check if running in production (GCP) mode."""
    return bool(settings.gcp_project_id)


def _get_bigquery_client():
    """Get BigQuery client (lazy-loaded)."""
    try:
        from google.cloud import bigquery
        return bigquery.Client(project=settings.gcp_project_id)
    except ImportError:
        logger.warning("google-cloud-bigquery not installed, falling back to CSV")
        return None
    except Exception as e:
        logger.warning(f"Could not create BigQuery client: {e}, falling back to CSV")
        return None


def load_companies() -> pd.DataFrame:
    """Load master company list from BigQuery (production) or CSV (local)."""
    if _is_production():
        client = _get_bigquery_client()
        if client:
            try:
                query = f"""
                    SELECT company_id, company, type, stock_ticker, 
                           industries_served, description, processes_services
                    FROM `{settings.gcp_project_id}.{settings.gcp_dataset_id}.companies`
                    ORDER BY company
                """
                df = client.query(query).to_dataframe()
                logger.info(f"Loaded {len(df)} companies from BigQuery")
                return df
            except Exception as e:
                logger.error(f"Error loading companies from BigQuery: {e}")
                # Fall through to CSV fallback
    
    # Local/fallback: use CSV
    try:
        return pd.read_csv(settings.companies_file)
    except FileNotFoundError:
        logger.warning(f"Companies file not found: {settings.companies_file}")
        return pd.DataFrame(columns=["company", "stock_ticker", "type"])


def load_materials() -> pd.DataFrame:
    """Load master materials list from BigQuery (production) or CSV (local)."""
    if _is_production():
        client = _get_bigquery_client()
        if client:
            try:
                query = f"""
                    SELECT material_proc_id, material_process_name, type,
                           est_manufacturer_margin_tier, industries_served, examples
                    FROM `{settings.gcp_project_id}.{settings.gcp_dataset_id}.materials`
                    ORDER BY material_process_name
                """
                df = client.query(query).to_dataframe()
                logger.info(f"Loaded {len(df)} materials from BigQuery")
                return df
            except Exception as e:
                logger.error(f"Error loading materials from BigQuery: {e}")
                # Fall through to CSV fallback
    
    # Local/fallback: use CSV
    try:
        return pd.read_csv(settings.materials_file)
    except FileNotFoundError:
        logger.warning(f"Materials file not found: {settings.materials_file}")
        return pd.DataFrame(columns=["material_process_name", "category"])


def load_industries() -> pd.DataFrame:
    """Load master industries list from BigQuery (production) or CSV (local)."""
    if _is_production():
        client = _get_bigquery_client()
        if client:
            try:
                query = f"""
                    SELECT industry, application, end_users, naics_code,
                           naics_description, industry_priority_flag, example_products
                    FROM `{settings.gcp_project_id}.{settings.gcp_dataset_id}.industries`
                    ORDER BY industry
                """
                df = client.query(query).to_dataframe()
                logger.info(f"Loaded {len(df)} industries from BigQuery")
                return df
            except Exception as e:
                logger.error(f"Error loading industries from BigQuery: {e}")
                # Fall through to CSV fallback
    
    # Local/fallback: use CSV
    try:
        return pd.read_csv(settings.industries_file)
    except FileNotFoundError:
        logger.warning(f"Industries file not found: {settings.industries_file}")
        return pd.DataFrame(columns=["industry_id", "industry_name", "description", "key_materials", "key_processes"])
    except Exception as e:
        logger.error(f"Error loading industries: {e}")
        return pd.DataFrame(columns=["industry_id", "industry_name", "description", "key_materials", "key_processes"])


# =============================================================================
# BigQuery Save Functions (for concurrent-safe writes in production)
# =============================================================================

def save_company_to_bigquery(company_data: Dict[str, Any]) -> bool:
    """Insert a new company into BigQuery (concurrent-safe)."""
    if not _is_production():
        return False
    
    client = _get_bigquery_client()
    if not client:
        return False
    
    try:
        from datetime import datetime
        table_id = f"{settings.gcp_project_id}.{settings.gcp_dataset_id}.companies"
        
        row = {
            "company_id": company_data.get("company_id", ""),
            "company": company_data.get("company", ""),
            "type": company_data.get("type", ""),
            "stock_ticker": company_data.get("stock_ticker", ""),
            "industries_served": company_data.get("industries_served", ""),
            "description": company_data.get("description", ""),
            "processes_services": company_data.get("processes_services", ""),
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }
        
        errors = client.insert_rows_json(table_id, [row])
        if errors:
            logger.error(f"Error inserting company to BigQuery: {errors}")
            return False
        
        logger.info(f"Inserted company '{company_data.get('company')}' to BigQuery")
        return True
    except Exception as e:
        logger.error(f"Error saving company to BigQuery: {e}")
        return False


def save_material_to_bigquery(material_data: Dict[str, Any]) -> bool:
    """Insert a new material into BigQuery (concurrent-safe)."""
    if not _is_production():
        return False
    
    client = _get_bigquery_client()
    if not client:
        return False
    
    try:
        from datetime import datetime
        table_id = f"{settings.gcp_project_id}.{settings.gcp_dataset_id}.materials"
        
        row = {
            "material_proc_id": material_data.get("material_proc_id", ""),
            "material_process_name": material_data.get("material_process_name", ""),
            "type": material_data.get("type", ""),
            "est_manufacturer_margin_tier": material_data.get("est_manufacturer_margin_tier", "MEDIUM"),
            "industries_served": material_data.get("industries_served", ""),
            "examples": material_data.get("examples", ""),
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }
        
        errors = client.insert_rows_json(table_id, [row])
        if errors:
            logger.error(f"Error inserting material to BigQuery: {errors}")
            return False
        
        logger.info(f"Inserted material '{material_data.get('material_process_name')}' to BigQuery")
        return True
    except Exception as e:
        logger.error(f"Error saving material to BigQuery: {e}")
        return False


def save_industry_to_bigquery(industry_data: Dict[str, Any]) -> bool:
    """Insert a new industry into BigQuery (concurrent-safe)."""
    if not _is_production():
        return False
    
    client = _get_bigquery_client()
    if not client:
        return False
    
    try:
        from datetime import datetime
        table_id = f"{settings.gcp_project_id}.{settings.gcp_dataset_id}.industries"
        
        row = {
            "industry": industry_data.get("industry", ""),
            "application": industry_data.get("application", ""),
            "end_users": industry_data.get("end_users", ""),
            "naics_code": industry_data.get("naics_code", ""),
            "naics_description": industry_data.get("naics_description", ""),
            "industry_priority_flag": industry_data.get("industry_priority_flag", "N"),
            "example_products": industry_data.get("example_products", ""),
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }
        
        errors = client.insert_rows_json(table_id, [row])
        if errors:
            logger.error(f"Error inserting industry to BigQuery: {errors}")
            return False
        
        logger.info(f"Inserted industry '{industry_data.get('industry')}' to BigQuery")
        return True
    except Exception as e:
        logger.error(f"Error saving industry to BigQuery: {e}")
        return False


def delete_company_from_bigquery(company_name: str) -> bool:
    """Delete a company from BigQuery."""
    if not _is_production():
        return False
    
    client = _get_bigquery_client()
    if not client:
        return False
    
    try:
        query = f"""
            DELETE FROM `{settings.gcp_project_id}.{settings.gcp_dataset_id}.companies`
            WHERE LOWER(company) = LOWER(@company_name)
        """
        job_config = _get_bigquery_job_config()
        job_config.query_parameters = [
            _get_bigquery_scalar_param("company_name", "STRING", company_name)
        ]
        
        client.query(query, job_config=job_config).result()
        logger.info(f"Deleted company '{company_name}' from BigQuery")
        return True
    except Exception as e:
        logger.error(f"Error deleting company from BigQuery: {e}")
        return False


def delete_material_from_bigquery(material_name: str) -> bool:
    """Delete a material from BigQuery."""
    if not _is_production():
        return False
    
    client = _get_bigquery_client()
    if not client:
        return False
    
    try:
        query = f"""
            DELETE FROM `{settings.gcp_project_id}.{settings.gcp_dataset_id}.materials`
            WHERE LOWER(material_process_name) = LOWER(@material_name)
        """
        job_config = _get_bigquery_job_config()
        job_config.query_parameters = [
            _get_bigquery_scalar_param("material_name", "STRING", material_name)
        ]
        
        client.query(query, job_config=job_config).result()
        logger.info(f"Deleted material '{material_name}' from BigQuery")
        return True
    except Exception as e:
        logger.error(f"Error deleting material from BigQuery: {e}")
        return False


def delete_industry_from_bigquery(industry_name: str) -> bool:
    """Delete an industry from BigQuery."""
    if not _is_production():
        return False
    
    client = _get_bigquery_client()
    if not client:
        return False
    
    try:
        query = f"""
            DELETE FROM `{settings.gcp_project_id}.{settings.gcp_dataset_id}.industries`
            WHERE LOWER(industry) = LOWER(@industry_name)
        """
        job_config = _get_bigquery_job_config()
        job_config.query_parameters = [
            _get_bigquery_scalar_param("industry_name", "STRING", industry_name)
        ]
        
        client.query(query, job_config=job_config).result()
        logger.info(f"Deleted industry '{industry_name}' from BigQuery")
        return True
    except Exception as e:
        logger.error(f"Error deleting industry from BigQuery: {e}")
        return False


def _get_bigquery_job_config():
    """Get a QueryJobConfig for parameterized queries."""
    from google.cloud import bigquery
    return bigquery.QueryJobConfig()


def _get_bigquery_scalar_param(name: str, type_: str, value: Any):
    """Create a BigQuery scalar query parameter."""
    from google.cloud import bigquery
    return bigquery.ScalarQueryParameter(name, type_, value)


# =============================================================================
# Preferences (using BigQuery in production for concurrent safety)
# =============================================================================

def load_preferences() -> Dict[str, Any]:
    """Load user preferences from BigQuery (production) or JSON file (local)."""
    if _is_production():
        client = _get_bigquery_client()
        if client:
            try:
                # Check if preferences table exists and has data
                query = f"""
                    SELECT preferences_json 
                    FROM `{settings.gcp_project_id}.{settings.gcp_dataset_id}.user_preferences`
                    WHERE user_id = 'default'
                    LIMIT 1
                """
                result = list(client.query(query).result())
                if result:
                    return json.loads(result[0].preferences_json)
            except Exception as e:
                logger.warning(f"Could not load preferences from BigQuery: {e}")
                # Fall through to local file
    
    # Local/fallback: use JSON file
    try:
        with open(settings.preferences_file, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "global_exclusions": [],
            "tracked_companies": [],
            "created_at": None,
            "updated_at": None,
        }


def save_preferences(preferences: Dict[str, Any]) -> None:
    """Save user preferences to BigQuery (production) or JSON file (local)."""
    from datetime import datetime
    
    preferences["updated_at"] = datetime.now().isoformat()
    if not preferences.get("created_at"):
        preferences["created_at"] = preferences["updated_at"]
    
    # For now, preferences still use local file
    # TODO: Create user_preferences table in BigQuery for full concurrent safety
    settings.preferences_file.parent.mkdir(parents=True, exist_ok=True)
    with open(settings.preferences_file, "w") as f:
        json.dump(preferences, f, indent=2)


def build_grounding_context() -> str:
    """
    Build grounding context string from master data files.
    This is injected into agent system prompts.
    """
    companies_df = load_companies()
    materials_df = load_materials()
    industries_df = load_industries()
    
    # Format companies by type
    companies_context = "COMPANIES WE TRACK:\n"
    if not companies_df.empty:
        companies_by_type = companies_df.groupby("type").apply(
            lambda x: x[["company", "stock_ticker"]].to_dict("records")
        ).to_dict()
        
        for company_type, companies in companies_by_type.items():
            companies_context += f"\n  {company_type}:\n"
            for c in companies[:15]:  # Limit per type
                ticker = ""
                if pd.notna(c.get("stock_ticker")) and c.get("stock_ticker") not in ["private", "government", ""]:
                    ticker = f" ({c['stock_ticker']})"
                companies_context += f"    - {c['company']}{ticker}\n"
            if len(companies) > 15:
                companies_context += f"    ... and {len(companies) - 15} more\n"
    
    # Format materials
    materials_context = f"MATERIALS & PROCESSES ({len(materials_df)} total):\n"
    if not materials_df.empty:
        materials_list = materials_df["material_process_name"].tolist()
        materials_context += "  " + ", ".join(materials_list[:30])
        if len(materials_list) > 30:
            materials_context += f", ... and {len(materials_list) - 30} more"
    
    # Format industries
    industries_context = f"INDUSTRIES & APPLICATIONS ({len(industries_df)} total):\n"
    if not industries_df.empty:
        for _, row in industries_df.head(20).iterrows():
            industries_context += f"  - {row['industry']}: {row['application']}\n"
        if len(industries_df) > 20:
            industries_context += f"  ... and {len(industries_df) - 20} more\n"
    
    grounding = f"""
=== GROUNDING DATA (from master files) ===
Use this to understand WHAT companies, materials, and industries to consider when researching.

{companies_context}
{materials_context}

{industries_context}
=== END GROUNDING DATA ===
"""
    
    logger.info(
        f"Loaded grounding data: {len(companies_df)} companies, "
        f"{len(materials_df)} materials, {len(industries_df)} industries"
    )
    
    return grounding


def get_grounding_context() -> Dict[str, Any]:
    """
    Get grounding context as a structured dict for agent state.
    Returns lists of companies, materials, industries, and exclusions.
    """
    companies_df = load_companies()
    materials_df = load_materials()
    industries_df = load_industries()
    preferences = load_preferences()
    
    # Extract company names
    companies = []
    if not companies_df.empty and "company" in companies_df.columns:
        companies = companies_df["company"].tolist()
    
    # Extract material names
    materials = []
    if not materials_df.empty and "material_process_name" in materials_df.columns:
        materials = materials_df["material_process_name"].tolist()
    
    # Extract industries
    industries = []
    if not industries_df.empty and "industry" in industries_df.columns:
        industries = industries_df["industry"].tolist()
    
    # Get exclusions from preferences
    exclusions = preferences.get("global_exclusions", [])
    
    return {
        "companies": companies,
        "materials": materials,
        "industries": industries,
        "exclusions": exclusions,
    }
