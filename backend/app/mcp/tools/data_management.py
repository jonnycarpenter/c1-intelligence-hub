"""Data management tools - Available to ALL agents.

These tools allow users to manage tracked companies, materials, and preferences
from any conversation mode (Pulse, Research, or Products).

IMPORTANT: For any data modification (add/remove), the agent MUST ask the user
for their first name and last initial before proceeding. This is required for
accountability and audit trail purposes.
"""

import json
import pandas as pd
from datetime import datetime
from typing import Optional, List
from langchain_core.tools import tool

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
from app.config.settings import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


# ============================================
# Change Log Helper Functions
# ============================================

def load_change_log() -> dict:
    """Load the change log from file."""
    path = settings.data_dir / "change_log.json"
    if path.exists():
        with open(path, "r") as f:
            return json.load(f)
    return {"changes": [], "metadata": {"version": "1.0", "created_at": datetime.now().isoformat()}}


def save_change_log(data: dict) -> None:
    """Save the change log to file."""
    path = settings.data_dir / "change_log.json"
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
) -> dict:
    """Add a new entry to the change log."""
    log_data = load_change_log()
    
    existing_ids = [c["id"] for c in log_data.get("changes", [])]
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
        "status": "success",
        "agent_used": agent_used,
        "details": details,
    }
    
    log_data["changes"].insert(0, entry)
    save_change_log(log_data)
    
    return entry


@tool
def get_companies_list(
    type_filter: Optional[str] = None,
    limit: int = 50,
) -> str:
    """
    Get the list of companies from the master company list.
    
    Use this to see what companies are being tracked in the hub.
    
    Args:
        type_filter: Optional filter by company type (e.g., "raw_materials", "oem")
        limit: Maximum number of results to return
    
    Returns:
        JSON string with company list including name, ticker, and type
    """
    logger.info(f"Getting companies list: type_filter={type_filter}")
    
    df = load_companies()
    
    if type_filter:
        df = df[df["type"].str.lower() == type_filter.lower()]
    
    companies = df.head(limit).to_dict("records")
    
    return json.dumps({
        "total_count": len(load_companies()),
        "filtered_count": len(companies),
        "filter_applied": type_filter,
        "companies": companies,
    }, indent=2)


@tool
def get_materials_list(limit: int = 50) -> str:
    """
    Get the list of materials from the master materials list.
    
    Use this to see what materials and processes are being tracked.
    
    Args:
        limit: Maximum number of results to return
    
    Returns:
        JSON string with materials list
    """
    logger.info("Getting materials list")
    
    df = load_materials()
    materials = df.head(limit).to_dict("records")
    
    return json.dumps({
        "total_count": len(load_materials()),
        "returned_count": len(materials),
        "materials": materials,
    }, indent=2)


@tool
def get_industries_list(limit: int = 50) -> str:
    """
    Get the list of industries from the master industries list.
    
    Use this to see what industries are being tracked.
    
    Args:
        limit: Maximum number of results to return
    
    Returns:
        JSON string with industries list
    """
    logger.info("Getting industries list")
    
    df = load_industries()
    industries = df.head(limit).to_dict("records")
    
    return json.dumps({
        "total_count": len(load_industries()),
        "returned_count": len(industries),
        "industries": industries,
    }, indent=2)


@tool
def get_preferences() -> str:
    """
    Get the current user preferences.
    
    Use this to see current exclusions, tracked companies, and other settings.
    
    Returns:
        JSON string with user preferences
    """
    logger.info("Getting user preferences")
    
    prefs = load_preferences()
    return json.dumps(prefs, indent=2)


@tool
def update_preferences(
    action: str,
    item: str,
    list_name: str = "global_exclusions",
) -> str:
    """
    Update user preferences by adding or removing items.
    
    Use this to manage exclusions and tracked companies.
    
    Args:
        action: "add" or "remove"
        item: The item to add or remove
        list_name: Which list to modify - "global_exclusions" or "tracked_companies"
    
    Returns:
        JSON string with updated preferences
    """
    logger.info(f"Updating preferences: {action} '{item}' to {list_name}")
    
    if action not in ["add", "remove"]:
        return json.dumps({"error": "Action must be 'add' or 'remove'"})
    
    if list_name not in ["global_exclusions", "tracked_companies"]:
        return json.dumps({"error": "list_name must be 'global_exclusions' or 'tracked_companies'"})
    
    prefs = load_preferences()
    
    if list_name not in prefs:
        prefs[list_name] = []
    
    if action == "add":
        if item not in prefs[list_name]:
            prefs[list_name].append(item)
            save_preferences(prefs)
            return json.dumps({
                "success": True,
                "action": "added",
                "item": item,
                "list": list_name,
                "current_list": prefs[list_name],
            }, indent=2)
        else:
            return json.dumps({
                "success": False,
                "message": f"'{item}' already in {list_name}",
                "current_list": prefs[list_name],
            }, indent=2)
    
    else:  # remove
        if item in prefs[list_name]:
            prefs[list_name].remove(item)
            save_preferences(prefs)
            return json.dumps({
                "success": True,
                "action": "removed",
                "item": item,
                "list": list_name,
                "current_list": prefs[list_name],
            }, indent=2)
        else:
            return json.dumps({
                "success": False,
                "message": f"'{item}' not found in {list_name}",
                "current_list": prefs[list_name],
            }, indent=2)


@tool
def add_company_to_tracker(
    company_name: str,
    user_name: str,
    ticker: Optional[str] = None,
    company_type: str = "Processor/Fabricator",
) -> str:
    """
    Add a new company to the master company tracking list.
    
    Use this when a user asks to track a new competitor, supplier, or customer.
    
    IMPORTANT: Before calling this tool, you MUST ask the user for their first name and last initial.
    Do not proceed without this information - it's required for accountability.
    
    Args:
        company_name: Name of the company to add
        user_name: First name and last initial of the person making the change (REQUIRED - ask user first!)
        ticker: Stock ticker symbol (optional)
        company_type: Type of company - "Intermediate Manufacturer", "Raw Material Manufacturer", 
                      "Processor/Fabricator", "Distributor", "OEM"
    
    Returns:
        JSON string confirming the addition
    """
    if not user_name or len(user_name.strip()) < 2:
        return json.dumps({
            "success": False,
            "error": "user_name is required. Please ask the user for their first name and last initial before making changes.",
        }, indent=2)
    
    logger.info(f"Adding company to tracker: {company_name} ({ticker}), type={company_type}, by {user_name}")
    
    try:
        # Load existing companies
        df = load_companies()
        
        # Check if already exists (using 'company' column)
        if company_name.lower() in df['company'].str.lower().values:
            return json.dumps({
                "success": False,
                "message": f"'{company_name}' is already in the tracking list",
            }, indent=2)
        
        # Generate a unique company_id
        import re
        company_id = re.sub(r'[^a-z0-9]', '_', company_name.lower())[:20] + "_001"
        
        # Prepare company data
        company_data = {
            "company_id": company_id,
            "company": company_name,
            "type": company_type,
            "stock_ticker": ticker or "",
            "industries_served": "",
            "description": "",
            "processes_services": "",
        }
        
        # Save to BigQuery in production, CSV in development
        if _is_production():
            success = save_company_to_bigquery(company_data)
            if not success:
                return json.dumps({
                    "success": False,
                    "error": "Failed to save company to database",
                }, indent=2)
        else:
            # Local development: use CSV
            new_row = pd.DataFrame([company_data])
            df = pd.concat([df, new_row], ignore_index=True)
            df.to_csv(settings.companies_file, index=False)
        
        # Log the change
        add_change_log_entry(
            change_type="company_added",
            category="company",
            description=f"Added company '{company_name}' to tracking list",
            user_name=user_name,
            new_value=company_name,
            agent_used="data_management",
            details={"type": company_type, "ticker": ticker},
        )
        
        return json.dumps({
            "success": True,
            "message": f"Added '{company_name}' to the company tracking list",
            "company": {
                "name": company_name,
                "ticker": ticker,
                "type": company_type,
            },
            "changed_by": user_name,
            "storage": "BigQuery" if _is_production() else "CSV",
        }, indent=2)
        
    except Exception as e:
        logger.error(f"Error adding company: {e}")
        return json.dumps({
            "success": False,
            "error": str(e),
        }, indent=2)


@tool
def add_material_to_tracker(
    material_name: str,
    user_name: str,
    material_type: str = "Raw Material",
) -> str:
    """
    Add a new material to the master materials tracking list.
    
    IMPORTANT: Before calling this tool, you MUST ask the user for their first name and last initial.
    Do not proceed without this information - it's required for accountability.
    
    Use this when a user asks to track new materials, resins, fibers, or processes.
    
    Args:
        material_name: Name of the material to add (e.g., "Carbon Fiber T800", "Epoxy Resin System 2000")
        user_name: First name and last initial of the person making the change (REQUIRED - ask user first!)
        material_type: Type of material - "Raw Material", "Intermediate", "Process"
    
    Returns:
        JSON string confirming the addition
    """
    if not user_name or len(user_name.strip()) < 2:
        return json.dumps({
            "success": False,
            "error": "user_name is required. Please ask the user for their first name and last initial before making changes.",
        }, indent=2)
    
    logger.info(f"Adding material to tracker: {material_name}, type={material_type}, by {user_name}")
    
    try:
        # Load existing materials
        df = load_materials()
        
        # Check if already exists (using 'material_process_name' column)
        if material_name.lower() in df['material_process_name'].str.lower().values:
            return json.dumps({
                "success": False,
                "message": f"'{material_name}' is already in the materials list",
            }, indent=2)
        
        # Generate a unique material_id
        import re
        material_id = "mat_" + re.sub(r'[^a-z0-9]', '_', material_name.lower())[:20] + "_001"
        
        # Prepare material data
        material_data = {
            "material_proc_id": material_id,
            "material_process_name": material_name,
            "type": material_type,
            "est_manufacturer_margin_tier": "MEDIUM",
            "industries_served": "",
            "examples": "",
        }
        
        # Save to BigQuery in production, CSV in development
        if _is_production():
            success = save_material_to_bigquery(material_data)
            if not success:
                return json.dumps({
                    "success": False,
                    "error": "Failed to save material to database",
                }, indent=2)
        else:
            # Local development: use CSV
            new_row = pd.DataFrame([material_data])
            df = pd.concat([df, new_row], ignore_index=True)
            df.to_csv(settings.materials_file, index=False)
        
        # Log the change
        add_change_log_entry(
            change_type="material_added",
            category="material",
            description=f"Added material '{material_name}' to tracking list",
            user_name=user_name,
            new_value=material_name,
            agent_used="data_management",
            details={"type": material_type},
        )
        
        return json.dumps({
            "success": True,
            "message": f"Added '{material_name}' to the materials tracking list",
            "material": {
                "name": material_name,
                "type": material_type,
            },
            "changed_by": user_name,
            "storage": "BigQuery" if _is_production() else "CSV",
        }, indent=2)
        
    except Exception as e:
        logger.error(f"Error adding material: {e}")
        return json.dumps({
            "success": False,
            "error": str(e),
        }, indent=2)


@tool
def add_industry_to_tracker(
    industry_name: str,
    user_name: str,
) -> str:
    """
    Add a new industry to the master industries tracking list.
    
    IMPORTANT: Before calling this tool, you MUST ask the user for their first name and last initial.
    Do not proceed without this information - it's required for accountability.
    
    Use this when a user asks to track a new industry or sector.
    
    Args:
        industry_name: Name of the industry to add (e.g., "Wind Energy", "Marine", "Automotive")
        user_name: First name and last initial of the person making the change (REQUIRED - ask user first!)
    
    Returns:
        JSON string confirming the addition
    """
    if not user_name or len(user_name.strip()) < 2:
        return json.dumps({
            "success": False,
            "error": "user_name is required. Please ask the user for their first name and last initial before making changes.",
        }, indent=2)
    
    logger.info(f"Adding industry to tracker: {industry_name}, by {user_name}")
    
    try:
        # Load existing industries
        df = load_industries()
        
        # Check if already exists (using 'industry' column)
        if industry_name.lower() in df['industry'].str.lower().values:
            return json.dumps({
                "success": False,
                "message": f"'{industry_name}' is already in the industries list",
            }, indent=2)
        
        # Prepare industry data
        industry_data = {
            "industry": industry_name,
            "application": "",
            "end_users": "",
            "naics_code": "",
            "naics_description": "",
            "industry_priority_flag": "N",
            "example_products": "",
        }
        
        # Save to BigQuery in production, CSV in development
        if _is_production():
            success = save_industry_to_bigquery(industry_data)
            if not success:
                return json.dumps({
                    "success": False,
                    "error": "Failed to save industry to database",
                }, indent=2)
        else:
            # Local development: use CSV (with local schema)
            import re
            industry_id = "ind_" + re.sub(r'[^a-z0-9]', '_', industry_name.lower())[:20] + "_001"
            new_row = pd.DataFrame([{
                "industry_id": industry_id,
                "industry": industry_name,
                "description": "",
                "key_materials": "",
                "major_oems": "",
            }])
            df = pd.concat([df, new_row], ignore_index=True)
            df.to_csv(settings.industries_file, index=False)
        
        # Log the change
        add_change_log_entry(
            change_type="industry_added",
            category="industry",
            description=f"Added industry '{industry_name}' to tracking list",
            user_name=user_name,
            new_value=industry_name,
            agent_used="data_management",
        )
        
        return json.dumps({
            "success": True,
            "message": f"Added '{industry_name}' to the industries tracking list",
            "industry": {
                "name": industry_name,
            },
            "changed_by": user_name,
            "storage": "BigQuery" if _is_production() else "CSV",
        }, indent=2)
        
    except Exception as e:
        logger.error(f"Error adding industry: {e}")
        return json.dumps({
            "success": False,
            "error": str(e),
        }, indent=2)


@tool
def add_multiple_items(
    items: str,
    user_name: str,
    item_type: str,
    category: Optional[str] = None,
) -> str:
    """
    Add multiple companies or materials at once.
    
    Use this when a user provides a list of items to track.
    
    IMPORTANT: Before calling this tool, you MUST ask the user for their first name and last initial.
    Do not proceed without this information - it's required for accountability.
    
    Args:
        items: Comma-separated list of items to add (e.g., "Hexcel, Toray, SGL Carbon")
        user_name: First name and last initial of the person making the change (REQUIRED - ask user first!)
        item_type: Either "company" or "material"
        category: For companies: "competitor", "supplier", etc. For materials: "fiber", "resin", etc.
    
    Returns:
        JSON string with results for each item
    """
    if not user_name or len(user_name.strip()) < 2:
        return json.dumps({
            "success": False,
            "error": "user_name is required. Please ask the user for their first name and last initial before making changes.",
        }, indent=2)
    
    logger.info(f"Adding multiple {item_type}s: {items}, by {user_name}")
    
    item_list = [item.strip() for item in items.split(",") if item.strip()]
    
    if not item_list:
        return json.dumps({
            "success": False,
            "error": "No valid items provided",
        }, indent=2)
    
    results = []
    added_count = 0
    
    import re
    
    for item in item_list:
        if item_type == "company":
            df = load_companies()
            if item.lower() not in df['company'].str.lower().values:
                company_id = re.sub(r'[^a-z0-9]', '_', item.lower())[:20] + "_001"
                new_row = pd.DataFrame([{
                    "company_id": company_id,
                    "company": item,
                    "type": category or "Processor/Fabricator",
                    "stock_ticker": "",
                    "industries_served": "",
                    "description": "",
                    "processes_services": "",
                }])
                df = pd.concat([df, new_row], ignore_index=True)
                df.to_csv(settings.companies_file, index=False)
                results.append({"item": item, "status": "added"})
                added_count += 1
            else:
                results.append({"item": item, "status": "already exists"})
        
        elif item_type == "material":
            df = load_materials()
            if item.lower() not in df['material_process_name'].str.lower().values:
                material_id = "mat_" + re.sub(r'[^a-z0-9]', '_', item.lower())[:20] + "_001"
                new_row = pd.DataFrame([{
                    "material_proc_id": material_id,
                    "material_process_name": item,
                    "type": category or "Raw Material",
                    "est_manufacturer_margin_tier": "MEDIUM",
                    "industries_served": "",
                    "examples": "",
                }])
                df = pd.concat([df, new_row], ignore_index=True)
                df.to_csv(settings.materials_file, index=False)
                results.append({"item": item, "status": "added"})
                added_count += 1
            else:
                results.append({"item": item, "status": "already exists"})
        
        else:
            results.append({"item": item, "status": "error", "message": "Invalid item_type"})
    
    # Log the bulk change
    if added_count > 0:
        added_items = [r["item"] for r in results if r["status"] == "added"]
        add_change_log_entry(
            change_type=f"bulk_{item_type}_added",
            category=item_type if item_type in ["company", "material"] else "system",
            description=f"Added {added_count} {item_type}(s) to tracking list: {', '.join(added_items)}",
            user_name=user_name,
            new_value=", ".join(added_items),
            agent_used="data_management",
            details={"count": added_count, "items": added_items},
        )
    
    return json.dumps({
        "success": True,
        "item_type": item_type,
        "total_requested": len(item_list),
        "added_count": added_count,
        "results": results,
        "changed_by": user_name,
    }, indent=2)


@tool  
def remove_company_from_tracker(company_name: str, user_name: str) -> str:
    """
    Remove a company from the master tracking list.
    
    IMPORTANT: Before calling this tool, you MUST ask the user for their first name and last initial.
    Do not proceed without this information - it's required for accountability.
    
    Args:
        company_name: Name of the company to remove
        user_name: First name and last initial of the person making the change (REQUIRED - ask user first!)
    
    Returns:
        JSON string confirming the removal
    """
    if not user_name or len(user_name.strip()) < 2:
        return json.dumps({
            "success": False,
            "error": "user_name is required. Please ask the user for their first name and last initial before making changes.",
        }, indent=2)
    
    logger.info(f"Removing company from tracker: {company_name}, by {user_name}")
    
    try:
        df = load_companies()
        
        # Find and remove (case-insensitive) using 'company' column
        mask = df['company'].str.lower() == company_name.lower()
        if not mask.any():
            return json.dumps({
                "success": False,
                "message": f"'{company_name}' not found in the tracking list",
            }, indent=2)
        
        removed_name = df[mask]['company'].iloc[0]
        removed_type = df[mask]['type'].iloc[0] if 'type' in df.columns else None
        
        # Delete from BigQuery in production, CSV in development
        if _is_production():
            success = delete_company_from_bigquery(company_name)
            if not success:
                return json.dumps({
                    "success": False,
                    "error": "Failed to remove company from database",
                }, indent=2)
        else:
            # Local development: use CSV
            df = df[~mask]
            df.to_csv(settings.companies_file, index=False)
        
        # Log the change
        add_change_log_entry(
            change_type="company_removed",
            category="company",
            description=f"Removed company '{removed_name}' from tracking list",
            user_name=user_name,
            previous_value=removed_name,
            agent_used="data_management",
            details={"type": removed_type},
        )
        
        return json.dumps({
            "success": True,
            "message": f"Removed '{removed_name}' from the company tracking list",
            "changed_by": user_name,
            "storage": "BigQuery" if _is_production() else "CSV",
        }, indent=2)
        
    except Exception as e:
        logger.error(f"Error removing company: {e}")
        return json.dumps({
            "success": False,
            "error": str(e),
        }, indent=2)


@tool
def remove_material_from_tracker(material_name: str, user_name: str) -> str:
    """
    Remove a material from the master tracking list.
    
    IMPORTANT: Before calling this tool, you MUST ask the user for their first name and last initial.
    Do not proceed without this information - it's required for accountability.
    
    Args:
        material_name: Name of the material to remove
        user_name: First name and last initial of the person making the change (REQUIRED - ask user first!)
    
    Returns:
        JSON string confirming the removal
    """
    if not user_name or len(user_name.strip()) < 2:
        return json.dumps({
            "success": False,
            "error": "user_name is required. Please ask the user for their first name and last initial before making changes.",
        }, indent=2)
    
    logger.info(f"Removing material from tracker: {material_name}, by {user_name}")
    
    try:
        df = load_materials()
        
        # Find and remove (case-insensitive) using 'material_process_name' column
        mask = df['material_process_name'].str.lower() == material_name.lower()
        if not mask.any():
            return json.dumps({
                "success": False,
                "message": f"'{material_name}' not found in the materials list",
            }, indent=2)
        
        removed_name = df[mask]['material_process_name'].iloc[0]
        removed_type = df[mask]['type'].iloc[0] if 'type' in df.columns else None
        
        # Delete from BigQuery in production, CSV in development
        if _is_production():
            success = delete_material_from_bigquery(material_name)
            if not success:
                return json.dumps({
                    "success": False,
                    "error": "Failed to remove material from database",
                }, indent=2)
        else:
            # Local development: use CSV
            df = df[~mask]
            df.to_csv(settings.materials_file, index=False)
        
        # Log the change
        add_change_log_entry(
            change_type="material_removed",
            category="material",
            description=f"Removed material '{removed_name}' from tracking list",
            user_name=user_name,
            previous_value=removed_name,
            agent_used="data_management",
            details={"type": removed_type},
        )
        
        return json.dumps({
            "success": True,
            "message": f"Removed '{removed_name}' from the materials tracking list",
            "changed_by": user_name,
            "storage": "BigQuery" if _is_production() else "CSV",
        }, indent=2)
        
    except Exception as e:
        logger.error(f"Error removing material: {e}")
        return json.dumps({
            "success": False,
            "error": str(e),
        }, indent=2)
