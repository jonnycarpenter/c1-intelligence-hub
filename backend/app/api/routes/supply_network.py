"""
Supply Network API Routes
=========================
REST endpoints for the Supply Network tab — network graph visualization
and drill-down details for companies/suppliers.

Endpoints:
    GET  /api/supply-network/graph           - Network graph nodes/edges
    GET  /api/supply-network/stats           - Summary statistics
    GET  /api/supply-network/company/{key}   - Company drill-down
    GET  /api/supply-network/supplier/{key}  - Supplier drill-down
    GET  /api/supply-network/shared-suppliers - Shared supplier analysis
"""

import logging
from typing import Optional

from fastapi import APIRouter, Query, HTTPException

from app.ingestion.importyeti.bigquery_store import BigQueryStore

logger = logging.getLogger(__name__)
router = APIRouter()


def _get_store() -> BigQueryStore:
    """Lazy-load BigQuery store."""
    return BigQueryStore()


@router.get("/graph")
async def get_network_graph(
    entity_types: str = Query("target,competitor", description="Comma-separated entity types"),
    min_shipments_12m: int = Query(0, ge=0, description="Minimum 12-month shipments filter"),
):
    """Get network graph nodes and edges for visualization."""
    try:
        store = _get_store()
        entity_type_list = [e.strip() for e in entity_types.split(",") if e.strip()]
        data = store.get_network_graph_data(
            entity_types=entity_type_list,
            min_shipments_12m=min_shipments_12m,
        )
        logger.info(
            f"[SUPPLY_NETWORK] Graph loaded: {data['stats']['total_companies']} companies, "
            f"{data['stats']['total_suppliers']} suppliers, {data['stats']['total_edges']} edges"
        )
        return data
    except Exception as e:
        logger.error(f"[SUPPLY_NETWORK] Graph error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_stats():
    """Get database summary statistics."""
    try:
        store = _get_store()
        stats = store.get_stats()
        return stats
    except Exception as e:
        logger.error(f"[SUPPLY_NETWORK] Stats error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/company/{importyeti_key:path}")
async def get_company_detail(importyeti_key: str):
    """Get company profile and supplier list for drill-down."""
    try:
        store = _get_store()
        company = store.get_company(importyeti_key)
        if not company:
            raise HTTPException(status_code=404, detail=f"Company '{importyeti_key}' not found")

        suppliers = store.get_company_suppliers(importyeti_key)

        # Strip raw_api_response to keep payload small
        profile = {k: v for k, v in company.items() if k != "raw_api_response"}
        # Convert datetimes
        for k, v in profile.items():
            if hasattr(v, "isoformat"):
                profile[k] = v.isoformat()

        return {
            "company": profile,
            "suppliers": suppliers[:50],
            "supplier_count": len(suppliers),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[SUPPLY_NETWORK] Company detail error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/supplier/{importyeti_key:path}")
async def get_supplier_detail(importyeti_key: str):
    """Get supplier profile and buyer list for drill-down."""
    try:
        store = _get_store()
        supplier = store.get_supplier(importyeti_key)
        if not supplier:
            raise HTTPException(status_code=404, detail=f"Supplier '{importyeti_key}' not found")

        buyers = store.get_supplier_buyers(importyeti_key)

        # Strip raw_api_response
        profile = {k: v for k, v in supplier.items() if k != "raw_api_response"}
        for k, v in profile.items():
            if hasattr(v, "isoformat"):
                profile[k] = v.isoformat()

        return {
            "supplier": profile,
            "buyers": buyers[:50],
            "buyer_count": len(buyers),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[SUPPLY_NETWORK] Supplier detail error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/shared-suppliers")
async def get_shared_suppliers(
    active_12m_only: bool = Query(False, description="Only show 12-month active relationships"),
):
    """Get suppliers shared between 2+ tracked competitors."""
    try:
        store = _get_store()
        data = store.get_shared_suppliers(active_12m_only=active_12m_only)
        return {
            "shared_suppliers": data,
            "total": len(data),
        }
    except Exception as e:
        logger.error(f"[SUPPLY_NETWORK] Shared suppliers error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
