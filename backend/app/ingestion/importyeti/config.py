"""
ImportYeti Tracked Entities Configuration
==========================================

Defines which suppliers, OEMs, and products to track.
Entities are derived from master_company_list.csv in resources folder.
"""

import os
import csv
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TrackedSupplier:
    """Configuration for a tracked supplier."""
    company_id: str
    name: str
    tier: str  # 'raw_material', 'intermediate'
    importyeti_key: Optional[str] = None  # Override key if different from name
    products: Optional[str] = None
    ticker: Optional[str] = None
    
    @property
    def search_key(self) -> str:
        """Key to use for ImportYeti API lookup."""
        if self.importyeti_key:
            return self.importyeti_key
        # Convert name to ImportYeti key format (lowercase, hyphenated)
        return self.name.lower().replace(' ', '-').replace(',', '').replace('.', '')


@dataclass  
class TrackedOEM:
    """Configuration for a tracked OEM (for competitive intelligence)."""
    company_id: str
    name: str
    industry: str
    importyeti_key: Optional[str] = None
    ticker: Optional[str] = None
    
    @property
    def search_key(self) -> str:
        """Key to use for ImportYeti API lookup."""
        if self.importyeti_key:
            return self.importyeti_key
        return self.name.lower().replace(' ', '-').replace(',', '').replace('.', '')


# =============================================================================
# Product Searches (Quarterly)
# =============================================================================

PRODUCT_SEARCHES: List[str] = [
    "carbon fiber",
    "fiberglass",
    "prepreg",
    "epoxy resin",
    "aramid fiber",
    "glass fiber",
    "composite material",
    "honeycomb core",
    "polyester resin",
    "vinyl ester",
]


# =============================================================================
# Functions to Load from master_company_list.csv
# =============================================================================
# Functions to Load from BigQuery Storage Layer
# =============================================================================

async def load_master_company_list() -> List[Dict[str, Any]]:
    """Load and parse master_company_list from BigQuery."""
    from app.db.gcp_storage import get_storage
    
    try:
        storage = await get_storage()
        companies = await storage.get_companies()
        logger.info(f"Loaded {len(companies)} companies from BigQuery")
        return companies
    except Exception as e:
        logger.error(f"Error loading companies from BigQuery: {e}")
        return []


async def get_tracked_suppliers_from_storage() -> Dict[str, TrackedSupplier]:
    """
    Extract tracked suppliers from BigQuery storage.
    
    Filters for:
    - type = 'Raw Material Manufacturer'
    - type = 'Intermediate Manufacturer'
    
    Returns:
        Dict mapping supplier key to TrackedSupplier
    """
    companies = await load_master_company_list()
    suppliers = {}
    
    supplier_types = ['Raw Material Manufacturer', 'Intermediate Manufacturer']
    
    for company in companies:
        company_type = company.get('type', '')
        if company_type not in supplier_types:
            continue
        
        # Determine tier
        tier = 'raw_material' if company_type == 'Raw Material Manufacturer' else 'intermediate'
        
        supplier = TrackedSupplier(
            company_id=company.get('id', company.get('company_id', '')),
            name=company.get('name', company.get('company', '')),
            tier=tier,
            products=company.get('description', ''),
            ticker=company.get('ticker') if company.get('ticker') != 'private' else None,
        )
        
        suppliers[supplier.search_key] = supplier
    
    logger.info(f"Found {len(suppliers)} tracked suppliers from storage")
    return suppliers


async def get_tracked_oems_from_storage() -> Dict[str, TrackedOEM]:
    """
    Extract tracked OEMs from BigQuery storage.
    
    Filters for:
    - type = 'OEM'
    
    Returns:
        Dict mapping OEM key to TrackedOEM
    """
    companies = await load_master_company_list()
    oems = {}
    
    for company in companies:
        company_type = company.get('type', '')
        if company_type != 'OEM':
            continue
        
        # Extract primary industry from industries_served
        industries_str = company.get('industries', company.get('industries_served', ''))
        industries = industries_str.split('|') if isinstance(industries_str, str) else []
        primary_industry = industries[0].lower() if industries else 'other'
        
        oem = TrackedOEM(
            company_id=company.get('id', company.get('company_id', '')),
            name=company.get('name', company.get('company', '')),
            industry=primary_industry,
            ticker=company.get('ticker') if company.get('ticker') != 'private' else None,
        )
        
        oems[oem.search_key] = oem
    
    logger.info(f"Found {len(oems)} tracked OEMs from storage")
    return oems


async def get_tracked_fabricators_from_storage() -> Dict[str, TrackedOEM]:
    """
    Extract tracked fabricators/processors from BigQuery storage.
    These are potential prospects or competitive intel targets.
    
    Filters for:
    - type = 'Processor/Fabricator'
    
    Returns:
        Dict mapping fabricator key to TrackedOEM (using same structure)
    """
    companies = await load_master_company_list()
    fabricators = {}
    
    for company in companies:
        company_type = company.get('type', '')
        if company_type != 'Processor/Fabricator':
            continue
        
        industries_str = company.get('industries', company.get('industries_served', ''))
        industries = industries_str.split('|') if isinstance(industries_str, str) else []
        primary_industry = industries[0].lower() if industries else 'other'
        
        fab = TrackedOEM(
            company_id=company.get('id', company.get('company_id', '')),
            name=company.get('name', company.get('company', '')),
            industry=primary_industry,
            ticker=company.get('ticker') if company.get('ticker') != 'private' else None,
        )
        
        fabricators[fab.search_key] = fab
    
    logger.info(f"Found {len(fabricators)} tracked fabricators from storage")
    return fabricators


# =============================================================================
# Default Tracked Entities (Hardcoded fallback from architecture doc)
# =============================================================================

# These are used if CSV is not available or as priority overrides

TRACKED_SUPPLIERS: Dict[str, TrackedSupplier] = {
    # Raw material manufacturers
    'owens-corning': TrackedSupplier(
        company_id='owens_001',
        name='Owens Corning',
        tier='raw_material',
        products='Glass fiber',
        ticker='OC'
    ),
    'huntsman': TrackedSupplier(
        company_id='huntsman_001',
        name='Huntsman',
        tier='raw_material',
        products='Polyurethanes, resins',
        ticker='HUN'
    ),
    'basf': TrackedSupplier(
        company_id='basf_001',
        name='BASF',
        tier='raw_material',
        products='Resins, chemicals',
        ticker='BASFY'
    ),
    'dupont': TrackedSupplier(
        company_id='dupont_001',
        name='DuPont',
        tier='raw_material',
        products='Kevlar, Nomex',
        ticker='DD'
    ),
    
    # Intermediate manufacturers
    'hexcel': TrackedSupplier(
        company_id='hexcel_001',
        name='Hexcel',
        tier='intermediate',
        products='Prepregs, carbon fiber',
        ticker='HXL'
    ),
    'toray': TrackedSupplier(
        company_id='toray_001',
        name='Toray',
        tier='intermediate',
        products='Carbon fiber, prepregs',
        ticker='TRYIY'
    ),
    'teijin': TrackedSupplier(
        company_id='teijin_001',
        name='Teijin',
        tier='intermediate',
        products='Carbon fiber, aramid',
        ticker='TINLY'
    ),
    'solvay': TrackedSupplier(
        company_id='solvay_001',
        name='Solvay/Cytec',
        tier='intermediate',
        products='Prepregs, polymers',
        ticker='SOLVY'
    ),
    'gurit': TrackedSupplier(
        company_id='gurit_001',
        name='Gurit',
        tier='intermediate',
        products='Core materials, prepregs',
        ticker='GURN.SW'
    ),
    'jushi-group': TrackedSupplier(
        company_id='jushi_001',
        name='Jushi Group',
        tier='raw_material',
        products='Fiberglass',
        importyeti_key='jushi-group'  # Known key
    ),
}


TRACKED_OEMS: Dict[str, TrackedOEM] = {
    'spirit-aerosystems': TrackedOEM(
        company_id='spirit_001',
        name='Spirit Aerosystems',
        industry='aerospace',
        ticker='SPR'
    ),
    'tpi-composites': TrackedOEM(
        company_id='tpi_001',
        name='TPI Composites',
        industry='wind',
        ticker='TPIC'
    ),
    'brunswick': TrackedOEM(
        company_id='brunswick_001',
        name='Brunswick',
        industry='marine',
        ticker='BC'
    ),
    'grady-white': TrackedOEM(
        company_id='gradywhite_001',
        name='Grady-White',
        industry='marine',
    ),
    'boeing': TrackedOEM(
        company_id='boeing_001',
        name='Boeing',
        industry='aerospace',
        ticker='BA'
    ),
    'northrop-grumman': TrackedOEM(
        company_id='northrop_001',
        name='Northrop Grumman',
        industry='aerospace',
        ticker='NOC'
    ),
}


# =============================================================================
# Combined Entity Getters
# =============================================================================

def get_all_tracked_suppliers(use_csv: bool = True) -> Dict[str, TrackedSupplier]:
    """
    Get all tracked suppliers, combining CSV and hardcoded lists.
    
    Args:
        use_csv: If True, load from CSV and merge with defaults
        
    Returns:
        Dict of all tracked suppliers
    """
    suppliers = dict(TRACKED_SUPPLIERS)  # Start with defaults
    
    if use_csv:
        csv_suppliers = get_tracked_suppliers_from_csv()
        # CSV entries take precedence (update defaults)
        for key, supplier in csv_suppliers.items():
            if key not in suppliers:
                suppliers[key] = supplier
    
    return suppliers


def get_all_tracked_oems(use_csv: bool = True) -> Dict[str, TrackedOEM]:
    """
    Get all tracked OEMs, combining CSV and hardcoded lists.
    """
    oems = dict(TRACKED_OEMS)
    
    if use_csv:
        csv_oems = get_tracked_oems_from_csv()
        for key, oem in csv_oems.items():
            if key not in oems:
                oems[key] = oem
    
    return oems


# =============================================================================
# Credit Budget Configuration
# =============================================================================

@dataclass
class CreditBudget:
    """Credit budget management."""
    total_annual: int = 1500
    per_cycle_suppliers: int = 10  # ~10 supplier profiles
    per_cycle_company: int = 1    # C1 profile
    per_cycle_oems: int = 6       # OEM profiles
    cycles_per_year: int = 26     # Bi-weekly
    quarterly_product_searches: int = 16  # 8 products × 2 endpoints
    
    @property
    def scheduled_annual(self) -> int:
        """Calculate total scheduled credit usage."""
        per_cycle = self.per_cycle_suppliers + self.per_cycle_company + self.per_cycle_oems
        return (per_cycle * self.cycles_per_year) + (self.quarterly_product_searches * 4)
    
    @property
    def on_demand_budget(self) -> int:
        """Remaining credits for on-demand queries."""
        return self.total_annual - self.scheduled_annual


CREDIT_BUDGET = CreditBudget()
