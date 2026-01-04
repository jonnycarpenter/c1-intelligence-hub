"""Data & Preferences API routes.

Provides endpoints for viewing and managing:
- Tracked companies, materials, industries
- User preferences
- Change log history
"""

import json
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Literal
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.config.settings import settings
from app.utils.logger import get_logger
from app.utils.grounding import (
    load_companies,
    load_materials,
    load_industries,
    load_preferences,
    save_preferences,
    save_company_to_bigquery,
    save_material_to_bigquery,
    save_industry_to_bigquery,
    delete_company_from_bigquery,
    delete_material_from_bigquery,
    delete_industry_from_bigquery,
    _is_production,
)

logger = get_logger(__name__)
router = APIRouter(prefix="/api/data-preferences", tags=["data-preferences"])


# ============================================
# Pydantic Models
# ============================================

class ChangeLogEntry(BaseModel):
    """A single change log entry."""
    id: str
    timestamp: str
    change_type: str
    category: Literal["company", "material", "industry", "preference", "system"]
    description: str
    user_name: str
    previous_value: Optional[str] = None
    new_value: Optional[str] = None
    status: Literal["success", "failed", "rolled_back"] = "success"
    agent_used: Optional[str] = None
    details: Optional[dict] = None


class AddItemRequest(BaseModel):
    """Request to add a company, material, or industry."""
    name: str = Field(..., description="Name of the item to add")
    user_name: str = Field(..., description="First name and last initial of person making change")
    item_type: Optional[str] = Field(None, description="Type/category of the item")
    ticker: Optional[str] = Field(None, description="Stock ticker (for companies)")
    industries_served: Optional[str] = Field(None, description="Industries served")
    description: Optional[str] = Field(None, description="Description of the item")


class RemoveItemRequest(BaseModel):
    """Request to remove a company, material, or industry."""
    name: str = Field(..., description="Name of the item to remove")
    user_name: str = Field(..., description="First name and last initial of person making change")


class UpdatePreferenceRequest(BaseModel):
    """Request to update a user preference."""
    action: Literal["add", "remove", "update"]
    preference_type: Literal["global_exclusions", "tracked_companies", "tracked_materials", "tracked_industries", "report_preferences"]
    value: str
    user_name: str = Field(..., description="First name and last initial of person making change")
    priority: Optional[Literal["high", "medium", "low"]] = None


class PreferenceStatus(BaseModel):
    """User preference with status."""
    id: str
    preference: str
    type: str
    status: Literal["active", "paused", "archived"] = "active"
    created_at: str
    updated_at: Optional[str] = None
    created_by: Optional[str] = None


# ============================================
# Helper Functions
# ============================================

def get_change_log_path() -> Path:
    """Get the path to the change log file."""
    return settings.data_dir / "change_log.json"


def load_change_log() -> dict:
    """Load the change log from file."""
    path = get_change_log_path()
    if path.exists():
        with open(path, "r") as f:
            return json.load(f)
    return {"changes": [], "metadata": {"version": "1.0", "created_at": datetime.now().isoformat()}}


def save_change_log(data: dict) -> None:
    """Save the change log to file."""
    path = get_change_log_path()
    data["metadata"]["last_updated"] = datetime.now().isoformat()
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def add_change_log_entry(
    change_type: str,
    category: str,
    description: str,
    user_name: str,
    previous_value: Optional[str] = None,
    new_value: Optional[str] = None,
    agent_used: Optional[str] = None,
    details: Optional[dict] = None,
    status: str = "success"
) -> ChangeLogEntry:
    """Add a new entry to the change log."""
    log_data = load_change_log()
    
    # Generate unique ID
    existing_ids = [c["id"] for c in log_data["changes"]]
    new_id = f"change_{len(existing_ids) + 1:04d}"
    
    entry = {
        "id": new_id,
        "timestamp": datetime.now().isoformat(),
        "change_type": change_type,
        "category": category,
        "description": description,
        "user_name": user_name,
        "previous_value": previous_value,
        "new_value": new_value,
        "status": status,
        "agent_used": agent_used,
        "details": details,
    }
    
    log_data["changes"].insert(0, entry)  # Most recent first
    save_change_log(log_data)
    
    return ChangeLogEntry(**entry)


def load_companies_df() -> pd.DataFrame:
    """Load companies from BigQuery (production) or CSV (local)."""
    return load_companies()


def load_materials_df() -> pd.DataFrame:
    """Load materials from BigQuery (production) or CSV (local)."""
    return load_materials()


def load_industries_df() -> pd.DataFrame:
    """Load industries from BigQuery (production) or CSV (local)."""
    return load_industries()


def load_preferences_dict() -> dict:
    """Load user preferences."""
    return load_preferences()


def save_preferences_dict(data: dict) -> None:
    """Save user preferences."""
    save_preferences(data)


# ============================================
# GET Endpoints - Read Data
# ============================================

@router.get("/companies")
async def get_companies(
    type_filter: Optional[str] = Query(None, description="Filter by company type"),
    search: Optional[str] = Query(None, description="Search by name"),
    limit: int = Query(100, description="Maximum results"),
    offset: int = Query(0, description="Offset for pagination"),
):
    """Get all tracked companies."""
    try:
        df = load_companies_df()
        
        if type_filter:
            df = df[df["type"].str.lower() == type_filter.lower()]
        
        if search:
            df = df[df["company"].str.lower().str.contains(search.lower(), na=False)]
        
        total = len(df)
        df = df.iloc[offset:offset + limit]
        
        companies = df.to_dict("records")
        
        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "data": companies,
            "types": load_companies_df()["type"].unique().tolist(),
        }
    except Exception as e:
        logger.error(f"Error loading companies: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/materials")
async def get_materials(
    type_filter: Optional[str] = Query(None, description="Filter by material type"),
    search: Optional[str] = Query(None, description="Search by name"),
    limit: int = Query(100, description="Maximum results"),
    offset: int = Query(0, description="Offset for pagination"),
):
    """Get all tracked materials."""
    try:
        df = load_materials_df()
        
        if type_filter:
            df = df[df["type"].str.lower() == type_filter.lower()]
        
        if search:
            df = df[df["material_process_name"].str.lower().str.contains(search.lower(), na=False)]
        
        total = len(df)
        df = df.iloc[offset:offset + limit]
        
        materials = df.to_dict("records")
        
        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "data": materials,
            "types": load_materials_df()["type"].unique().tolist(),
        }
    except Exception as e:
        logger.error(f"Error loading materials: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/industries")
async def get_industries(
    search: Optional[str] = Query(None, description="Search by name"),
    limit: int = Query(100, description="Maximum results"),
    offset: int = Query(0, description="Offset for pagination"),
):
    """Get all tracked industries."""
    try:
        df = load_industries_df()
        
        if search:
            # Support both 'industry' (BigQuery) and 'industry_name' (CSV) column names
            search_col = "industry" if "industry" in df.columns else "industry_name"
            df = df[df[search_col].str.lower().str.contains(search.lower(), na=False)]
        
        total = len(df)
        df = df.iloc[offset:offset + limit]
        
        industries = df.to_dict("records")
        
        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "data": industries,
        }
    except Exception as e:
        logger.error(f"Error loading industries: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/preferences")
async def get_preferences():
    """Get all user preferences."""
    try:
        prefs = load_preferences_dict()
        
        # Transform to structured format with status
        formatted_prefs = {
            "global_exclusions": [
                {"id": f"excl_{i}", "value": excl, "status": "active"}
                for i, excl in enumerate(prefs.get("global_exclusions", []))
            ],
            "tracked_companies": prefs.get("tracked_companies", []),
            "tracked_materials": prefs.get("tracked_materials", []),
            "tracked_industries": prefs.get("tracked_industries", []),
            "report_preferences": prefs.get("report_preferences", {}),
            "created_at": prefs.get("created_at"),
            "updated_at": prefs.get("updated_at"),
        }
        
        return formatted_prefs
    except Exception as e:
        logger.error(f"Error loading preferences: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/change-log")
async def get_change_log(
    category: Optional[str] = Query(None, description="Filter by category"),
    user_name: Optional[str] = Query(None, description="Filter by user"),
    limit: int = Query(50, description="Maximum results"),
    offset: int = Query(0, description="Offset for pagination"),
):
    """Get the change log history."""
    try:
        log_data = load_change_log()
        changes = log_data.get("changes", [])
        
        if category:
            changes = [c for c in changes if c.get("category") == category]
        
        if user_name:
            changes = [c for c in changes if user_name.lower() in c.get("user_name", "").lower()]
        
        total = len(changes)
        changes = changes[offset:offset + limit]
        
        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "data": changes,
            "metadata": log_data.get("metadata", {}),
        }
    except Exception as e:
        logger.error(f"Error loading change log: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary")
async def get_data_summary():
    """Get a summary of all tracked data."""
    try:
        companies_df = load_companies_df()
        materials_df = load_materials_df()
        industries_df = load_industries_df()
        prefs = load_preferences_dict()
        log_data = load_change_log()
        
        return {
            "companies": {
                "total": len(companies_df),
                "by_type": companies_df["type"].value_counts().to_dict(),
            },
            "materials": {
                "total": len(materials_df),
                "by_type": materials_df["type"].value_counts().to_dict(),
            },
            "industries": {
                "total": len(industries_df),
            },
            "preferences": {
                "global_exclusions_count": len(prefs.get("global_exclusions", [])),
                "tracked_companies_count": len(prefs.get("tracked_companies", [])),
                "tracked_materials_count": len(prefs.get("tracked_materials", [])),
                "tracked_industries_count": len(prefs.get("tracked_industries", [])),
            },
            "change_log": {
                "total_changes": len(log_data.get("changes", [])),
                "last_change": log_data["changes"][0] if log_data.get("changes") else None,
            },
        }
    except Exception as e:
        logger.error(f"Error getting summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# POST Endpoints - Add Data
# ============================================

@router.post("/companies")
async def add_company(request: AddItemRequest):
    """Add a new company to the tracking list."""
    try:
        import re
        df = load_companies_df()
        
        # Check if already exists
        if request.name.lower() in df["company"].str.lower().values:
            raise HTTPException(status_code=400, detail=f"'{request.name}' already exists")
        
        # Generate ID
        company_id = re.sub(r'[^a-z0-9]', '_', request.name.lower())[:20] + "_001"
        
        # Prepare company data
        company_data = {
            "company_id": company_id,
            "company": request.name,
            "type": request.item_type or "Processor/Fabricator",
            "stock_ticker": request.ticker or "",
            "industries_served": request.industries_served or "",
            "description": request.description or "",
            "processes_services": "",
        }
        
        # Save to BigQuery in production, CSV locally
        if _is_production():
            save_company_to_bigquery(company_data)
        else:
            new_row = pd.DataFrame([company_data])
            df = pd.concat([df, new_row], ignore_index=True)
            df.to_csv(settings.companies_file, index=False)
        
        # Log the change
        add_change_log_entry(
            change_type="company_added",
            category="company",
            description=f"Added company '{request.name}' to tracking list",
            user_name=request.user_name,
            new_value=request.name,
            details={"type": request.item_type, "ticker": request.ticker},
        )
        
        # Get updated count
        updated_df = load_companies_df()
        
        return {
            "success": True,
            "message": f"Added '{request.name}' to company tracking list",
            "company": company_data,
            "total_companies": len(updated_df),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding company: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/materials")
async def add_material(request: AddItemRequest):
    """Add a new material to the tracking list."""
    try:
        import re
        df = load_materials_df()
        
        # Check if already exists
        if request.name.lower() in df["material_process_name"].str.lower().values:
            raise HTTPException(status_code=400, detail=f"'{request.name}' already exists")
        
        # Generate ID
        material_id = "mat_" + re.sub(r'[^a-z0-9]', '_', request.name.lower())[:20] + "_001"
        
        # Prepare material data
        material_data = {
            "material_proc_id": material_id,
            "material_process_name": request.name,
            "type": request.item_type or "Raw Material",
            "est_manufacturer_margin_tier": "MEDIUM",
            "industries_served": request.industries_served or "",
            "examples": "",
        }
        
        # Save to BigQuery in production, CSV locally
        if _is_production():
            save_material_to_bigquery(material_data)
        else:
            new_row = pd.DataFrame([material_data])
            df = pd.concat([df, new_row], ignore_index=True)
            df.to_csv(settings.materials_file, index=False)
        
        # Log the change
        add_change_log_entry(
            change_type="material_added",
            category="material",
            description=f"Added material '{request.name}' to tracking list",
            user_name=request.user_name,
            new_value=request.name,
            details={"type": request.item_type},
        )
        
        # Get updated count
        updated_df = load_materials_df()
        
        return {
            "success": True,
            "message": f"Added '{request.name}' to materials tracking list",
            "material": material_data,
            "total_materials": len(updated_df),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding material: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/industries")
async def add_industry(request: AddItemRequest):
    """Add a new industry to the tracking list."""
    try:
        import re
        df = load_industries_df()
        
        # Check if already exists
        if request.name.lower() in df["industry_name"].str.lower().values:
            raise HTTPException(status_code=400, detail=f"'{request.name}' already exists")
        
        # Generate ID
        industry_id = "ind_" + re.sub(r'[^a-z0-9]', '_', request.name.lower())[:20] + "_001"
        
        # Prepare industry data
        industry_data = {
            "industry_id": industry_id,
            "industry_name": request.name,
            "description": request.description or "",
            "key_materials": "",
            "key_processes": "",
        }
        
        # Save to BigQuery in production, CSV locally
        if _is_production():
            save_industry_to_bigquery(industry_data)
        else:
            new_row = pd.DataFrame([industry_data])
            df = pd.concat([df, new_row], ignore_index=True)
            df.to_csv(settings.industries_file, index=False)
        
        # Log the change
        add_change_log_entry(
            change_type="industry_added",
            category="industry",
            description=f"Added industry '{request.name}' to tracking list",
            user_name=request.user_name,
            new_value=request.name,
        )
        
        # Get updated count
        updated_df = load_industries_df()
        
        return {
            "success": True,
            "message": f"Added '{request.name}' to industries tracking list",
            "industry": industry_data,
            "total_industries": len(updated_df),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding industry: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/preferences")
async def update_preference(request: UpdatePreferenceRequest):
    """Update a user preference."""
    try:
        prefs = load_preferences_dict()
        
        if request.preference_type not in prefs:
            prefs[request.preference_type] = [] if request.preference_type != "report_preferences" else {}
        
        previous_value = None
        
        if request.action == "add":
            if isinstance(prefs[request.preference_type], list):
                if request.value not in prefs[request.preference_type]:
                    prefs[request.preference_type].append(request.value)
                else:
                    raise HTTPException(status_code=400, detail="Preference already exists")
            else:
                prefs[request.preference_type][request.value] = True
        
        elif request.action == "remove":
            if isinstance(prefs[request.preference_type], list):
                if request.value in prefs[request.preference_type]:
                    previous_value = request.value
                    prefs[request.preference_type].remove(request.value)
                else:
                    raise HTTPException(status_code=404, detail="Preference not found")
            else:
                if request.value in prefs[request.preference_type]:
                    previous_value = str(prefs[request.preference_type][request.value])
                    del prefs[request.preference_type][request.value]
        
        save_preferences_dict(prefs)
        
        # Log the change
        add_change_log_entry(
            change_type=f"preference_{request.action}",
            category="preference",
            description=f"{request.action.capitalize()}d preference: '{request.value}' in {request.preference_type}",
            user_name=request.user_name,
            previous_value=previous_value,
            new_value=request.value if request.action == "add" else None,
        )
        
        return {
            "success": True,
            "message": f"Preference {request.action}d successfully",
            "preference_type": request.preference_type,
            "value": request.value,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating preference: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# DELETE Endpoints - Remove Data
# ============================================

@router.delete("/companies/{company_name}")
async def remove_company(company_name: str, user_name: str = Query(..., description="First name and last initial")):
    """Remove a company from the tracking list."""
    try:
        df = load_companies_df()
        
        # Find the company
        mask = df["company"].str.lower() == company_name.lower()
        if not mask.any():
            raise HTTPException(status_code=404, detail=f"'{company_name}' not found")
        
        removed = df[mask].to_dict("records")[0]
        
        # Delete from BigQuery in production, CSV locally
        if _is_production():
            delete_company_from_bigquery(removed["company"])
        else:
            df = df[~mask]
            df.to_csv(settings.companies_file, index=False)
        
        # Log the change
        add_change_log_entry(
            change_type="company_removed",
            category="company",
            description=f"Removed company '{removed['company']}' from tracking list",
            user_name=user_name,
            previous_value=removed["company"],
            details={"type": removed.get("type"), "ticker": removed.get("stock_ticker")},
        )
        
        # Get updated count
        updated_df = load_companies_df()
        
        return {
            "success": True,
            "message": f"Removed '{removed['company']}' from tracking list",
            "removed": removed,
            "total_companies": len(updated_df),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing company: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/materials/{material_name}")
async def remove_material(material_name: str, user_name: str = Query(..., description="First name and last initial")):
    """Remove a material from the tracking list."""
    try:
        df = load_materials_df()
        
        # Find the material
        mask = df["material_process_name"].str.lower() == material_name.lower()
        if not mask.any():
            raise HTTPException(status_code=404, detail=f"'{material_name}' not found")
        
        removed = df[mask].to_dict("records")[0]
        
        # Delete from BigQuery in production, CSV locally
        if _is_production():
            delete_material_from_bigquery(removed["material_process_name"])
        else:
            df = df[~mask]
            df.to_csv(settings.materials_file, index=False)
        
        # Log the change
        add_change_log_entry(
            change_type="material_removed",
            category="material",
            description=f"Removed material '{removed['material_process_name']}' from tracking list",
            user_name=user_name,
            previous_value=removed["material_process_name"],
            details={"type": removed.get("type")},
        )
        
        # Get updated count
        updated_df = load_materials_df()
        
        return {
            "success": True,
            "message": f"Removed '{removed['material_process_name']}' from tracking list",
            "removed": removed,
            "total_materials": len(updated_df),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing material: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/industries/{industry_name}")
async def remove_industry(industry_name: str, user_name: str = Query(..., description="First name and last initial")):
    """Remove an industry from the tracking list."""
    try:
        df = load_industries_df()
        
        # Find the industry
        mask = df["industry_name"].str.lower() == industry_name.lower()
        if not mask.any():
            raise HTTPException(status_code=404, detail=f"'{industry_name}' not found")
        
        removed = df[mask].to_dict("records")[0]
        
        # Delete from BigQuery in production, CSV locally
        if _is_production():
            delete_industry_from_bigquery(removed["industry_name"])
        else:
            df = df[~mask]
            df.to_csv(settings.industries_file, index=False)
        
        # Log the change
        add_change_log_entry(
            change_type="industry_removed",
            category="industry",
            description=f"Removed industry '{removed['industry_name']}' from tracking list",
            user_name=user_name,
            previous_value=removed["industry_name"],
        )
        
        # Get updated count
        updated_df = load_industries_df()
        
        return {
            "success": True,
            "message": f"Removed '{removed['industry_name']}' from tracking list",
            "removed": removed,
            "total_industries": len(updated_df),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing industry: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# Export Endpoint
# ============================================

@router.get("/export")
async def export_data(data_type: Literal["companies", "materials", "industries", "preferences", "change_log"]):
    """Export data as JSON for download or backup."""
    try:
        if data_type == "companies":
            df = load_companies_df()
            return {"data": df.to_dict("records")}
        elif data_type == "materials":
            df = load_materials_df()
            return {"data": df.to_dict("records")}
        elif data_type == "industries":
            df = load_industries_df()
            return {"data": df.to_dict("records")}
        elif data_type == "preferences":
            return {"data": load_preferences_dict()}
        elif data_type == "change_log":
            return {"data": load_change_log()}
    except Exception as e:
        logger.error(f"Error exporting data: {e}")
        raise HTTPException(status_code=500, detail=str(e))
