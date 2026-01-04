"""Companies API routes."""

from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.utils.grounding import load_companies, load_preferences
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/companies", tags=["companies"])


# Company types with metadata
COMPANY_CATALOG = {
    "hexcel": {
        "id": "hexcel",
        "name": "Hexcel Corporation",
        "ticker": "HXL",
        "type": "Raw Material Manufacturer",
        "industries": ["aerospace", "defense", "wind_energy", "automotive"],
        "description": "Leading advanced composites company for aerospace and industrial markets",
        "website": "https://www.hexcel.com",
        "headquarters": "Stamford, CT",
        "revenue": "$1.5B",
        "employees": "6,000+",
    },
    "toray": {
        "id": "toray",
        "name": "Toray Industries",
        "ticker": "TRYIF",
        "type": "Raw Material Manufacturer",
        "industries": ["aerospace", "automotive", "sporting_goods", "wind_energy"],
        "description": "World's largest carbon fiber manufacturer",
        "website": "https://www.toray.com",
        "headquarters": "Tokyo, Japan",
        "revenue": "$20B",
        "employees": "48,000+",
    },
    "sgl_carbon": {
        "id": "sgl_carbon",
        "name": "SGL Carbon",
        "ticker": "SGL.DE",
        "type": "Raw Material Manufacturer",
        "industries": ["automotive", "aerospace", "industrial"],
        "description": "Specialty graphite and carbon fiber solutions",
        "website": "https://www.sglcarbon.com",
        "headquarters": "Wiesbaden, Germany",
        "revenue": "€1.1B",
        "employees": "4,700+",
    },
    "owens_corning": {
        "id": "owens_corning",
        "name": "Owens Corning",
        "ticker": "OC",
        "type": "Raw Material Manufacturer",
        "industries": ["construction", "automotive", "wind_energy", "marine"],
        "description": "Global leader in glass fiber reinforcements",
        "website": "https://www.owenscorning.com",
        "headquarters": "Toledo, OH",
        "revenue": "$9.7B",
        "employees": "19,000+",
    },
    "jushi": {
        "id": "jushi",
        "name": "Jushi Group",
        "ticker": "600176.SS",
        "type": "Raw Material Manufacturer",
        "industries": ["construction", "automotive", "wind_energy", "electronics"],
        "description": "World's largest fiberglass manufacturer",
        "website": "https://www.jushi.com",
        "headquarters": "Tongxiang, China",
        "revenue": "$3B",
        "employees": "15,000+",
    },
    "teijin": {
        "id": "teijin",
        "name": "Teijin Limited",
        "ticker": "TEIN.F",
        "type": "Raw Material Manufacturer",
        "industries": ["aerospace", "automotive", "healthcare"],
        "description": "Advanced materials including carbon fiber and aramid",
        "website": "https://www.teijin.com",
        "headquarters": "Tokyo, Japan",
        "revenue": "$7.5B",
        "employees": "20,000+",
    },
    "huntsman": {
        "id": "huntsman",
        "name": "Huntsman Corporation",
        "ticker": "HUN",
        "type": "Raw Material Manufacturer",
        "industries": ["aerospace", "automotive", "construction", "wind_energy"],
        "description": "Specialty chemicals including epoxy resins",
        "website": "https://www.huntsman.com",
        "headquarters": "The Woodlands, TX",
        "revenue": "$8B",
        "employees": "9,000+",
    },
    "spirit_aerosystems": {
        "id": "spirit_aerosystems",
        "name": "Spirit AeroSystems",
        "ticker": "SPR",
        "type": "Processor/Fabricator",
        "industries": ["aerospace", "defense"],
        "description": "Largest independent aerostructures manufacturer",
        "website": "https://www.spiritaero.com",
        "headquarters": "Wichita, KS",
        "revenue": "$5B",
        "employees": "18,000+",
    },
    "gkn_aerospace": {
        "id": "gkn_aerospace",
        "name": "GKN Aerospace",
        "ticker": None,
        "type": "Processor/Fabricator",
        "industries": ["aerospace", "defense"],
        "description": "Tier 1 supplier of airframe and engine structures",
        "website": "https://www.gknaerospace.com",
        "headquarters": "Redditch, UK",
        "revenue": "$4B",
        "employees": "15,000+",
    },
    "boeing": {
        "id": "boeing",
        "name": "The Boeing Company",
        "ticker": "BA",
        "type": "OEM",
        "industries": ["aerospace", "defense"],
        "description": "World's largest aerospace company",
        "website": "https://www.boeing.com",
        "headquarters": "Arlington, VA",
        "revenue": "$66B",
        "employees": "140,000+",
    },
    "airbus": {
        "id": "airbus",
        "name": "Airbus SE",
        "ticker": "AIR.PA",
        "type": "OEM",
        "industries": ["aerospace", "defense"],
        "description": "Leading aircraft manufacturer",
        "website": "https://www.airbus.com",
        "headquarters": "Leiden, Netherlands",
        "revenue": "€65B",
        "employees": "130,000+",
    },
    "vestas": {
        "id": "vestas",
        "name": "Vestas Wind Systems",
        "ticker": "VWS.CO",
        "type": "OEM",
        "industries": ["wind_energy"],
        "description": "World's largest wind turbine manufacturer",
        "website": "https://www.vestas.com",
        "headquarters": "Aarhus, Denmark",
        "revenue": "€15B",
        "employees": "29,000+",
    },
}


class TrackCompanyRequest(BaseModel):
    company_name: str
    ticker: Optional[str] = None
    type: Optional[str] = "Processor/Fabricator"


class UntrackCompanyRequest(BaseModel):
    company_name: str


@router.get("")
async def get_companies(
    type: Optional[str] = Query(None, description="Filter by company type"),
    industry: Optional[str] = Query(None, description="Filter by industry served"),
    query: Optional[str] = Query(None, description="Search query"),
    tracked_only: bool = Query(False, description="Only show tracked companies"),
):
    """Get list of companies with optional filters."""
    logger.info(f"GET /api/companies - type={type}, industry={industry}, query={query}")
    
    # Get tracked companies from preferences
    prefs = load_preferences()
    tracked_companies = set(c.lower() for c in prefs.get("tracked_companies", []))
    
    # Also get from master list
    try:
        df = load_companies()
        master_companies = set(df['company'].str.lower().tolist())
    except Exception:
        master_companies = set()
    
    all_tracked = tracked_companies | master_companies
    
    # Convert catalog to list with tracking status
    companies = []
    for company_id, company in COMPANY_CATALOG.items():
        company_data = {
            **company,
            "is_tracked": company["name"].lower() in all_tracked or company_id in all_tracked,
        }
        
        # Apply filters
        if type and company_data["type"].lower() != type.lower():
            continue
        if industry and industry.lower() not in [i.lower() for i in company_data["industries"]]:
            continue
        if query and query.lower() not in company_data["name"].lower():
            continue
        if tracked_only and not company_data["is_tracked"]:
            continue
            
        companies.append(company_data)
    
    # Get unique types
    types = list(set(c["type"] for c in COMPANY_CATALOG.values()))
    
    return {
        "count": len(companies),
        "companies": companies,
        "types": sorted(types),
    }


@router.post("/track")
async def track_company(request: TrackCompanyRequest):
    """Add a company to the tracking list."""
    from app.mcp.tools.data_management import add_company_to_tracker
    
    result = add_company_to_tracker.invoke({
        "company_name": request.company_name,
        "ticker": request.ticker,
        "company_type": request.type or "Processor/Fabricator",
    })
    
    import json
    return json.loads(result)


@router.post("/untrack")
async def untrack_company(request: UntrackCompanyRequest):
    """Remove a company from the tracking list."""
    from app.mcp.tools.data_management import remove_company_from_tracker
    
    result = remove_company_from_tracker.invoke({
        "company_name": request.company_name,
    })
    
    import json
    return json.loads(result)


@router.get("/{company_id}")
async def get_company(company_id: str):
    """Get details for a specific company."""
    if company_id not in COMPANY_CATALOG:
        raise HTTPException(status_code=404, detail=f"Company {company_id} not found")
    
    company = COMPANY_CATALOG[company_id]
    prefs = load_preferences()
    tracked = prefs.get("tracked_companies", [])
    
    return {
        **company,
        "is_tracked": company["name"] in tracked or company_id in [c.lower() for c in tracked],
    }
