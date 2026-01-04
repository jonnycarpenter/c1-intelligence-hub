"""Industries API routes."""

from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from app.utils.grounding import load_industries, load_preferences
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/industries", tags=["industries"])


# Industry catalog with metadata
INDUSTRY_CATALOG = {
    "aerospace": {
        "id": "aerospace",
        "name": "Aerospace",
        "category": "Transportation",
        "description": "Commercial and military aircraft, satellites, and space systems",
        "key_materials": ["Carbon Fiber", "Aramid", "Glass Fiber", "Epoxy Resins", "BMI", "Honeycomb Core"],
        "key_companies": ["Boeing", "Airbus", "Lockheed Martin", "Spirit AeroSystems", "GKN Aerospace"],
        "market_size": "$450B",
        "growth_rate": "4.5% CAGR",
        "trends": [
            "Sustainable aviation fuels driving lightweighting",
            "Increased single-aisle production rates",
            "Defense spending growth in Europe/Asia",
            "Urban air mobility emerging",
        ],
    },
    "automotive": {
        "id": "automotive",
        "name": "Automotive",
        "category": "Transportation",
        "description": "Passenger vehicles, commercial vehicles, and EV applications",
        "key_materials": ["Carbon Fiber", "Glass Fiber", "SMC/BMC", "Natural Fibers", "Thermoplastics"],
        "key_companies": ["BMW", "Tesla", "Mercedes", "Ford", "Toyota"],
        "market_size": "$85B (composites)",
        "growth_rate": "7.2% CAGR",
        "trends": [
            "EV lightweighting for range extension",
            "High-volume CFRP production methods",
            "Recycled carbon fiber adoption",
            "Structural battery enclosures",
        ],
    },
    "wind_energy": {
        "id": "wind_energy",
        "name": "Wind Energy",
        "category": "Energy",
        "description": "Onshore and offshore wind turbine blades and components",
        "key_materials": ["Glass Fiber", "Carbon Fiber", "Epoxy Resins", "Balsa Core", "PET Foam"],
        "key_companies": ["Vestas", "Siemens Gamesa", "GE Vernova", "Goldwind", "TPI Composites"],
        "market_size": "$35B (composites)",
        "growth_rate": "8.5% CAGR",
        "trends": [
            "Offshore wind expansion",
            "100m+ blade lengths",
            "Recyclable blade initiatives",
            "Carbon fiber spar caps for longer blades",
        ],
    },
    "marine": {
        "id": "marine",
        "name": "Marine",
        "category": "Transportation",
        "description": "Recreational boats, yachts, commercial vessels, and naval ships",
        "key_materials": ["Glass Fiber", "Carbon Fiber", "Vinyl Ester", "Polyester", "Foam Core"],
        "key_companies": ["Brunswick", "Groupe Beneteau", "Ferretti", "Sunseeker"],
        "market_size": "$12B (composites)",
        "growth_rate": "3.8% CAGR",
        "trends": [
            "Electric propulsion integration",
            "Sustainability certifications",
            "High-performance racing yachts",
            "Naval vessel stealth applications",
        ],
    },
    "construction": {
        "id": "construction",
        "name": "Construction",
        "category": "Infrastructure",
        "description": "Infrastructure, bridges, buildings, and architectural applications",
        "key_materials": ["Glass Fiber Rebar", "GFRP", "Pultruded Profiles", "FRP Panels"],
        "key_companies": ["Owens Corning", "Strongwell", "Creative Pultrusions", "Bedford Industries"],
        "market_size": "$8B (composites)",
        "growth_rate": "6.1% CAGR",
        "trends": [
            "Corrosion-resistant infrastructure",
            "Seismic retrofitting",
            "Sustainable building materials",
            "Modular construction",
        ],
    },
    "sporting_goods": {
        "id": "sporting_goods",
        "name": "Sporting Goods",
        "category": "Consumer",
        "description": "Golf, tennis, cycling, skiing, and other sports equipment",
        "key_materials": ["Carbon Fiber", "Glass Fiber", "Aramid", "Thermoplastics"],
        "key_companies": ["Callaway", "Trek", "Head", "Rossignol", "Specialized"],
        "market_size": "$6B (composites)",
        "growth_rate": "5.2% CAGR",
        "trends": [
            "Custom/personalized equipment",
            "Recycled materials adoption",
            "Smart/connected equipment",
            "Direct-to-consumer models",
        ],
    },
    "defense": {
        "id": "defense",
        "name": "Defense",
        "category": "Military",
        "description": "Military aircraft, vehicles, vessels, and protective equipment",
        "key_materials": ["Carbon Fiber", "Aramid", "UHMWPE", "Ceramic Composites", "Radar-Absorbing Materials"],
        "key_companies": ["Lockheed Martin", "Northrop Grumman", "BAE Systems", "Raytheon"],
        "market_size": "$25B (composites)",
        "growth_rate": "5.8% CAGR",
        "trends": [
            "Hypersonic vehicle development",
            "Unmanned systems growth",
            "Next-gen body armor",
            "Stealth technology advancement",
        ],
    },
    "industrial": {
        "id": "industrial",
        "name": "Industrial",
        "category": "Manufacturing",
        "description": "Pressure vessels, tanks, pipes, and industrial equipment",
        "key_materials": ["Glass Fiber", "Carbon Fiber", "Vinyl Ester", "Polyester", "Phenolics"],
        "key_companies": ["NOV", "Amiantit", "Future Pipe Industries", "National Oilwell Varco"],
        "market_size": "$15B (composites)",
        "growth_rate": "4.2% CAGR",
        "trends": [
            "Hydrogen storage tanks",
            "Corrosion replacement market",
            "Chemical processing equipment",
            "High-pressure applications",
        ],
    },
    "electronics": {
        "id": "electronics",
        "name": "Electronics",
        "category": "Technology",
        "description": "Consumer electronics, PCBs, EMI shielding, and thermal management",
        "key_materials": ["Glass Fiber PCB", "Carbon Fiber", "Thermally Conductive Composites"],
        "key_companies": ["Apple", "Samsung", "Isola", "Rogers Corporation"],
        "market_size": "$10B (composites)",
        "growth_rate": "6.5% CAGR",
        "trends": [
            "5G infrastructure",
            "EV battery thermal management",
            "Lightweight device housings",
            "High-frequency PCB materials",
        ],
    },
}


@router.get("")
async def get_industries(
    category: Optional[str] = Query(None, description="Filter by category"),
    query: Optional[str] = Query(None, description="Search query"),
    tracked_only: bool = Query(False, description="Only show tracked industries"),
):
    """Get list of industries with optional filters."""
    logger.info(f"GET /api/industries - category={category}, query={query}")
    
    # Get tracked industries from preferences
    prefs = load_preferences()
    tracked_industries = set(i.lower() for i in prefs.get("tracked_industries", []))
    
    # Also get from master list
    try:
        df = load_industries()
        master_industries = set(df['industry'].str.lower().tolist()) if 'industry' in df.columns else set()
    except Exception:
        master_industries = set()
    
    all_tracked = tracked_industries | master_industries
    
    # Convert catalog to list with tracking status
    industries = []
    for industry_id, industry in INDUSTRY_CATALOG.items():
        industry_data = {
            **industry,
            "is_tracked": industry["name"].lower() in all_tracked or industry_id in all_tracked,
        }
        
        # Apply filters
        if category and industry_data.get("category", "").lower() != category.lower():
            continue
        if query and query.lower() not in industry_data["name"].lower():
            continue
        if tracked_only and not industry_data["is_tracked"]:
            continue
            
        industries.append(industry_data)
    
    # Get unique categories
    categories = list(set(i.get("category", "Other") for i in INDUSTRY_CATALOG.values()))
    
    return {
        "count": len(industries),
        "industries": industries,
        "categories": sorted(categories),
    }


@router.get("/{industry_id}")
async def get_industry(industry_id: str):
    """Get details for a specific industry."""
    if industry_id not in INDUSTRY_CATALOG:
        raise HTTPException(status_code=404, detail=f"Industry {industry_id} not found")
    
    industry = INDUSTRY_CATALOG[industry_id]
    prefs = load_preferences()
    tracked = prefs.get("tracked_industries", [])
    
    return {
        **industry,
        "is_tracked": industry["name"] in tracked or industry_id in [i.lower() for i in tracked],
    }


@router.get("/{industry_id}/insights")
async def get_industry_insights(industry_id: str):
    """Get latest insights for an industry."""
    if industry_id not in INDUSTRY_CATALOG:
        raise HTTPException(status_code=404, detail=f"Industry {industry_id} not found")
    
    industry = INDUSTRY_CATALOG[industry_id]
    
    # Mock insights - in production would query corpus
    return {
        "industry": industry_id,
        "news": [
            {"title": f"Major development in {industry['name']} sector", "date": "2024-12-15", "source": "Industry News"},
            {"title": f"New material innovation for {industry['name']}", "date": "2024-12-14", "source": "Tech Review"},
        ],
        "trends": industry.get("trends", []),
        "companies": [
            {"name": company, "activity": "Recent earnings call mentioned growth"}
            for company in industry.get("key_companies", [])[:3]
        ],
    }
