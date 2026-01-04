"""
ImportYeti Cloud Function Entry Point
=====================================

This module provides the entry point for Cloud Scheduler to trigger
the ImportYeti data collection pipeline.

Deployment:
    This is designed to be called via Cloud Run or Cloud Functions
    with the appropriate service account credentials.

Cloud Scheduler Configuration:
    - Schedule: 0 6 1,15 * * (6 AM on 1st and 15th of each month)
    - Target: This endpoint
    - HTTP Method: POST
    - Body: {"mode": "full"} or {"mode": "suppliers"} or {"mode": "companies"}
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from .pipeline import ImportYetiPipeline, PipelineResult
from .bigquery_store import ImportYetiBigQueryStore

logger = logging.getLogger(__name__)

# Router for FastAPI integration
router = APIRouter(prefix="/importyeti", tags=["importyeti"])


class ImportYetiTriggerRequest(BaseModel):
    """Request model for ImportYeti pipeline trigger."""
    mode: str = Field(
        default="full",
        description="Collection mode: 'full', 'suppliers', 'companies', or 'test'"
    )
    max_credits: int | None = Field(
        default=None,
        description="Maximum credits to use for this run"
    )
    dry_run: bool = Field(
        default=False,
        description="If true, log what would be done without making API calls"
    )
    supplier_names: list[str] | None = Field(
        default=None,
        description="Specific supplier names to collect (overrides tracked list)"
    )
    company_names: list[str] | None = Field(
        default=None,
        description="Specific company names to collect (overrides tracked list)"
    )


class ImportYetiTriggerResponse(BaseModel):
    """Response model for ImportYeti pipeline trigger."""
    status: str
    run_id: str | None = None
    message: str
    triggered_at: str


@router.post("/trigger", response_model=ImportYetiTriggerResponse)
async def trigger_importyeti_pipeline(
    request: ImportYetiTriggerRequest,
    background_tasks: BackgroundTasks,
):
    """
    Trigger the ImportYeti data collection pipeline.
    
    This endpoint is designed to be called by Cloud Scheduler on a bi-weekly
    schedule. The actual collection runs in the background.
    
    Modes:
    - full: Collect all data (suppliers, companies, products)
    - suppliers: Only collect supplier data
    - companies: Only collect company/OEM data  
    - test: Test API connection only
    """
    triggered_at = datetime.now(timezone.utc).isoformat()
    
    try:
        pipeline = ImportYetiPipeline()
        
        if request.mode == "test":
            # Run test synchronously
            test_result = await pipeline.test_connection()
            return ImportYetiTriggerResponse(
                status="success" if test_result.get("success") else "failed",
                run_id=None,
                message=json.dumps(test_result),
                triggered_at=triggered_at,
            )
        
        # Generate run ID for tracking
        run_id = f"iy_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        
        # Add the pipeline run to background tasks
        async def run_pipeline():
            try:
                if request.mode == "suppliers":
                    result = await pipeline.run_supplier_collection(
                        supplier_names=request.supplier_names,
                        max_credits=request.max_credits,
                    )
                elif request.mode == "companies":
                    result = await pipeline.run_company_collection(
                        company_names=request.company_names,
                        max_credits=request.max_credits,
                    )
                else:  # full
                    result = await pipeline.run(
                        max_credits=request.max_credits,
                        dry_run=request.dry_run,
                    )
                
                logger.info(f"Pipeline {run_id} completed: {result.to_dict()}")
                
            except Exception as e:
                logger.exception(f"Pipeline {run_id} failed: {e}")
        
        # Schedule the background task
        background_tasks.add_task(asyncio.create_task, run_pipeline())
        
        return ImportYetiTriggerResponse(
            status="accepted",
            run_id=run_id,
            message=f"ImportYeti pipeline started in mode '{request.mode}'",
            triggered_at=triggered_at,
        )
        
    except Exception as e:
        logger.exception(f"Failed to trigger ImportYeti pipeline: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_importyeti_status():
    """
    Get ImportYeti pipeline status and API connectivity.
    """
    try:
        pipeline = ImportYetiPipeline()
        status = await pipeline.test_connection()
        return {
            "api_connected": status.get("success", False),
            "database_updated": status.get("database_updated"),
            "credits_remaining": status.get("credits_remaining"),
            "credits_budget": status.get("credits_budget"),
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.exception(f"Failed to get ImportYeti status: {e}")
        return {
            "api_connected": False,
            "error": str(e),
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }


# =============================================================================
# Read Endpoints (Frontend)
# =============================================================================

@router.get("/dashboard")
async def get_dashboard_stats():
    """Get high-level dashboard metrics."""
    store = ImportYetiBigQueryStore()
    await store.initialize()
    return await store.get_dashboard_stats()


@router.get("/suppliers")
async def get_suppliers(
    limit: int = 50,
    offset: int = 0,
    search: str | None = None,
):
    """Get list of tracked suppliers."""
    store = ImportYetiBigQueryStore()
    await store.initialize()
    return await store.get_suppliers_list(limit=limit, offset=offset, search=search)


@router.get("/supplier/{supplier_id}")
async def get_supplier_details(supplier_id: str):
    """Get detailed supplier info."""
    store = ImportYetiBigQueryStore()
    await store.initialize()
    data = await store.get_supplier_details(supplier_id)
    if not data:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return data


@router.get("/network")
async def get_network_graph():
    """Get network graph data (nodes/links)."""
    store = ImportYetiBigQueryStore()
    await store.initialize()
    return await store.get_network_graph()


@router.get("/freight")
async def get_freight_data(
    lane: str | None = None,
    days: int = 90
):
    """Get freight rate time-series data."""
    try:
        from datetime import timedelta
        from app.db.gcp_storage import get_storage
        
        storage = await get_storage()
        start_date = datetime.utcnow() - timedelta(days=days)
        
        rates = await storage.get_freight_rates(
            lane=lane,
            start_date=start_date,
            limit=500
        )
        
        return [r.to_dict() for r in rates]
    except Exception as e:
        logger.error(f"Failed to fetch freight rates: {e}")
        return []


# =============================================================================
# Cloud Functions Entry Point (for direct Cloud Functions deployment)
# =============================================================================

def importyeti_cloud_function(request):
    """
    Google Cloud Functions entry point.
    
    Deploy with:
        gcloud functions deploy importyeti-pipeline \
            --runtime python311 \
            --trigger-http \
            --entry-point importyeti_cloud_function \
            --memory 1024MB \
            --timeout 540s
    
    Args:
        request: Flask request object
        
    Returns:
        JSON response with pipeline result
    """
    # Parse request
    request_json = request.get_json(silent=True) or {}
    mode = request_json.get("mode", "full")
    max_credits = request_json.get("max_credits")
    dry_run = request_json.get("dry_run", False)
    
    # Run pipeline
    async def run():
        pipeline = ImportYetiPipeline()
        
        if mode == "test":
            return await pipeline.test_connection()
        elif mode == "suppliers":
            result = await pipeline.run_supplier_collection(max_credits=max_credits)
        elif mode == "companies":
            result = await pipeline.run_company_collection(max_credits=max_credits)
        else:
            result = await pipeline.run(max_credits=max_credits, dry_run=dry_run)
        
        return result.to_dict()
    
    try:
        result = asyncio.run(run())
        return json.dumps(result), 200, {"Content-Type": "application/json"}
    except Exception as e:
        logger.exception(f"Cloud function failed: {e}")
        return json.dumps({"error": str(e)}), 500, {"Content-Type": "application/json"}


# =============================================================================
# Cloud Run Entry Point (for direct invocation)
# =============================================================================

async def main_cloud_run():
    """
    Direct entry point for Cloud Run jobs.
    
    Environment variables:
        IMPORTYETI_MODE: 'full', 'suppliers', 'companies', or 'test'
        IMPORTYETI_MAX_CREDITS: Maximum credits to use
        IMPORTYETI_DRY_RUN: Set to 'true' for dry run
    """
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    mode = os.getenv("IMPORTYETI_MODE", "full")
    max_credits = int(os.getenv("IMPORTYETI_MAX_CREDITS", "0")) or None
    dry_run = os.getenv("IMPORTYETI_DRY_RUN", "").lower() == "true"
    
    logger.info(f"Starting ImportYeti Cloud Run job: mode={mode}, max_credits={max_credits}")
    
    pipeline = ImportYetiPipeline()
    
    try:
        if mode == "test":
            result = await pipeline.test_connection()
            logger.info(f"Test result: {result}")
        elif mode == "suppliers":
            result = await pipeline.run_supplier_collection(max_credits=max_credits)
            logger.info(f"Supplier collection result: {result.to_dict()}")
        elif mode == "companies":
            result = await pipeline.run_company_collection(max_credits=max_credits)
            logger.info(f"Company collection result: {result.to_dict()}")
        else:
            result = await pipeline.run(max_credits=max_credits, dry_run=dry_run)
            logger.info(f"Full collection result: {result.to_dict()}")
        
        sys.exit(0)
        
    except Exception as e:
        logger.exception(f"Cloud Run job failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main_cloud_run())
