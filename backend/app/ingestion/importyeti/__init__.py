"""
ImportYeti Trade Intelligence Module
=====================================

Provides access to US Customs Bill of Lading data via ImportYeti API.
This module supports tracking supplier-customer relationships, detecting
changes in trade patterns, and analyzing competitive intelligence.

Tables created in BigQuery (c1_intelligence dataset):
- iy_snapshots: Raw API responses
- iy_suppliers: Supplier profiles
- iy_companies: US company profiles  
- iy_supplier_customers: Supplier → customer relationships
- iy_company_suppliers: Company → supplier relationships
- iy_product_market: Product search results
- iy_shipment_trends: Time series aggregations
- iy_concentration_metrics: Dependency analysis
- iy_competitor_overlap: Competitive intelligence
- iy_change_events: Detected changes

Usage:
    # Run the pipeline
    from app.ingestion.importyeti import ImportYetiPipeline
    
    pipeline = ImportYetiPipeline()
    result = await pipeline.run()
    
    # Or use the collector directly
    from app.ingestion.importyeti import ImportYetiClient, ImportYetiCollector
    
    client = ImportYetiClient()
    collector = ImportYetiCollector(client=client)
    async with client:
        result = await collector.run_full_collection()
"""

from .client import ImportYetiClient
from .collector import ImportYetiCollector, CollectionResult, CollectionStats
from .bigquery_store import ImportYetiBigQueryStore
from .pipeline import ImportYetiPipeline, PipelineResult
from .cloud_function import router as importyeti_router
from .models import (
    SupplierProfile,
    CompanyProfile,
    SupplierCustomerRelationship,
    CompanySupplierRelationship,
    ProductMarketResult,
    ShipmentTrend,
    ConcentrationMetrics,
    CompetitorOverlap,
    ChangeEvent,
    Snapshot,
    ChangeEventType,
    Significance,
    SupplierTier,
    CompanyType,
    HSCodeChapter,
    TopHSCode,
    TopSupplier,
    TopCompany,
    TimePeriod,
)
from .config import (
    TRACKED_SUPPLIERS,
    TRACKED_OEMS,
    PRODUCT_SEARCHES,
    CREDIT_BUDGET,
    get_tracked_suppliers_from_csv,
    get_tracked_oems_from_csv,
)

__all__ = [
    # Client
    "ImportYetiClient",
    
    # Collector
    "ImportYetiCollector",
    "CollectionResult",
    "CollectionStats",
    
    # Storage
    "ImportYetiBigQueryStore",
    
    # Pipeline
    "ImportYetiPipeline",
    "PipelineResult",
    
    # Router (for FastAPI)
    "importyeti_router",
    
    # Models
    "SupplierProfile",
    "CompanyProfile",
    "SupplierCustomerRelationship",
    "CompanySupplierRelationship",
    "ProductMarketResult",
    "ShipmentTrend",
    "ConcentrationMetrics",
    "CompetitorOverlap",
    "ChangeEvent",
    "Snapshot",
    "ChangeEventType",
    "Significance",
    "SupplierTier",
    "CompanyType",
    "HSCodeChapter",
    "TopHSCode",
    "TopSupplier",
    "TopCompany",
    "TimePeriod",
    
    # Config
    "TRACKED_SUPPLIERS",
    "TRACKED_OEMS",
    "PRODUCT_SEARCHES",
    "CREDIT_BUDGET",
    "get_tracked_suppliers_from_csv",
    "get_tracked_oems_from_csv",
]
