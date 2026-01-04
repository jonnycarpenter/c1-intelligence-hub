"""Data management API endpoints."""

from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.utils.grounding import (
    load_companies,
    load_materials,
    load_industries,
    load_preferences,
    save_preferences,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


class Company(BaseModel):
    """Company model."""
    company: str
    stock_ticker: Optional[str] = None
    type: str


class Material(BaseModel):
    """Material model."""
    material_process_name: str
    category: Optional[str] = None


class Industry(BaseModel):
    """Industry model."""
    industry_id: str
    industry_name: str
    description: Optional[str] = None
    key_materials: Optional[str] = None
    key_processes: Optional[str] = None


class UserPreferences(BaseModel):
    """User preferences model."""
    global_exclusions: List[str] = []
    tracked_companies: List[str] = []
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# Companies endpoints
@router.get("/companies")
async def get_companies() -> List[Company]:
    """Get all companies from master list."""
    df = load_companies()
    return [
        Company(
            company=row["company"],
            stock_ticker=row.get("stock_ticker"),
            type=row["type"],
        )
        for _, row in df.iterrows()
    ]


@router.get("/companies/count")
async def get_companies_count() -> dict:
    """Get company count by type."""
    df = load_companies()
    if df.empty:
        return {"total": 0, "by_type": {}}
    
    by_type = df.groupby("type").size().to_dict()
    return {"total": len(df), "by_type": by_type}


# Materials endpoints
@router.get("/materials")
async def get_materials() -> List[Material]:
    """Get all materials from master list."""
    df = load_materials()
    return [
        Material(
            material_process_name=row["material_process_name"],
            category=row.get("category"),
        )
        for _, row in df.iterrows()
    ]


@router.get("/materials/count")
async def get_materials_count() -> dict:
    """Get material count."""
    df = load_materials()
    return {"total": len(df)}


# Industries endpoints
@router.get("/industries")
async def get_industries() -> List[Industry]:
    """Get all industries from master list."""
    df = load_industries()
    return [
        Industry(
            industry_id=row["industry_id"],
            industry_name=row["industry_name"],
            description=row.get("description"),
            key_materials=row.get("key_materials"),
            key_processes=row.get("key_processes"),
        )
        for _, row in df.iterrows()
    ]


@router.get("/industries/count")
async def get_industries_count() -> dict:
    """Get industry count."""
    df = load_industries()
    if df.empty:
        return {"total": 0}
    
    return {"total": len(df)}


# Preferences endpoints
@router.get("/preferences")
async def get_preferences() -> UserPreferences:
    """Get user preferences."""
    prefs = load_preferences()
    return UserPreferences(**prefs)


@router.put("/preferences")
async def update_preferences(preferences: UserPreferences) -> UserPreferences:
    """Update user preferences."""
    logger.info("Updating user preferences")
    
    prefs_dict = preferences.model_dump()
    save_preferences(prefs_dict)
    
    # Return updated preferences
    return UserPreferences(**load_preferences())


@router.post("/preferences/exclusions")
async def add_exclusion(exclusion: str) -> UserPreferences:
    """Add a global exclusion."""
    prefs = load_preferences()
    if exclusion not in prefs["global_exclusions"]:
        prefs["global_exclusions"].append(exclusion)
        save_preferences(prefs)
    return UserPreferences(**prefs)


@router.delete("/preferences/exclusions/{exclusion}")
async def remove_exclusion(exclusion: str) -> UserPreferences:
    """Remove a global exclusion."""
    prefs = load_preferences()
    if exclusion in prefs["global_exclusions"]:
        prefs["global_exclusions"].remove(exclusion)
        save_preferences(prefs)
    return UserPreferences(**prefs)


# Summary endpoint
@router.get("/summary")
async def get_data_summary() -> dict:
    """Get summary of all data."""
    companies_df = load_companies()
    materials_df = load_materials()
    industries_df = load_industries()
    preferences = load_preferences()
    
    return {
        "companies": {
            "total": len(companies_df),
            "by_type": companies_df.groupby("type").size().to_dict() if not companies_df.empty else {},
        },
        "materials": {
            "total": len(materials_df),
        },
        "industries": {
            "total": len(industries_df),
        },
        "preferences": {
            "exclusions_count": len(preferences.get("global_exclusions", [])),
            "tracked_companies_count": len(preferences.get("tracked_companies", [])),
        },
    }
