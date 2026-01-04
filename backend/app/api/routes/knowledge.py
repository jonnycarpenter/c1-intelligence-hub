"""
Knowledge Base API Routes
=========================

API endpoints for managing the Wikipedia-seeded knowledge base.
"""

import asyncio
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel, Field

from app.knowledge.seeder import KnowledgeSeeder, get_seeder
from app.knowledge.knowledge_store import get_knowledge_store
from app.models.knowledge import EntityType
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/knowledge", tags=["Knowledge Base"])


# ============================================================================
# Request/Response Models
# ============================================================================

class SeedRequest(BaseModel):
    """Request to seed knowledge base."""
    clear_first: bool = Field(
        default=False,
        description="Clear existing knowledge before seeding"
    )
    entity_types: Optional[list[str]] = Field(
        default=None,
        description="Specific entity types to seed (companies, materials, processes, industries). If None, seeds all."
    )


class SearchRequest(BaseModel):
    """Request to search knowledge base."""
    query: str = Field(..., description="Search query")
    limit: int = Field(default=10, ge=1, le=50)
    entity_type: Optional[str] = Field(
        default=None,
        description="Filter by entity type (company, material, process, industry)"
    )


class ExportRequest(BaseModel):
    """Request to export knowledge base."""
    output_path: str = Field(
        default="./data/knowledge_export.json",
        description="Output file path for JSON export"
    )


class ImportRequest(BaseModel):
    """Request to import knowledge base."""
    input_path: str = Field(..., description="Path to JSON file to import")
    clear_first: bool = Field(
        default=True,
        description="Clear existing data before import"
    )


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/status")
async def get_knowledge_status():
    """
    Get knowledge base status and statistics.
    
    Returns current state of the knowledge base including:
    - Document counts by entity type
    - Storage information
    - Seeding progress (if running)
    """
    try:
        seeder = get_seeder()
        await seeder.initialize()
        
        stats = await seeder.get_stats()
        progress = seeder.get_progress()
        
        return {
            "status": "ok",
            "knowledge_base": stats,
            "seeding_progress": progress,
        }
        
    except Exception as e:
        logger.error(f"Error getting knowledge status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/progress")
async def get_seeding_progress():
    """
    Get current seeding progress.
    
    Useful for polling during long-running seeding operations.
    """
    seeder = get_seeder()
    return seeder.get_progress()


@router.post("/seed")
async def seed_knowledge_base(request: SeedRequest, background_tasks: BackgroundTasks):
    """
    Start seeding the knowledge base from Wikipedia.
    
    This is a long-running operation that runs in the background.
    Use /api/knowledge/progress to monitor progress.
    
    **Note:** Full seeding takes ~5-10 minutes due to Wikipedia rate limiting.
    """
    seeder = get_seeder()
    
    # Check if already running
    if seeder.progress.status == "running":
        raise HTTPException(
            status_code=409,
            detail="Seeding already in progress. Check /api/knowledge/progress for status."
        )
    
    # Initialize
    if not await seeder.initialize():
        raise HTTPException(status_code=500, detail="Failed to initialize knowledge store")
    
    async def run_seeding():
        """Background seeding task."""
        try:
            if request.entity_types:
                # Seed specific types
                for entity_type in request.entity_types:
                    if entity_type == "companies":
                        await seeder.seed_companies_only()
                    elif entity_type == "materials":
                        await seeder.seed_materials_only()
                    elif entity_type == "processes":
                        await seeder.seed_processes_only()
                    elif entity_type == "industries":
                        await seeder.seed_industries_only()
            else:
                # Seed all
                await seeder.seed_all(clear_first=request.clear_first)
        except Exception as e:
            logger.error(f"Seeding error: {e}")
    
    background_tasks.add_task(run_seeding)
    
    return {
        "status": "started",
        "message": "Seeding started in background. Use /api/knowledge/progress to monitor.",
        "entity_types": request.entity_types or ["companies", "materials", "processes", "industries"],
        "clear_first": request.clear_first,
    }


@router.post("/seed/sync")
async def seed_knowledge_base_sync(request: SeedRequest):
    """
    Seed knowledge base synchronously (blocks until complete).
    
    **Warning:** This can take 5-10 minutes. Use /seed for background seeding.
    """
    seeder = get_seeder()
    
    if seeder.progress.status == "running":
        raise HTTPException(
            status_code=409,
            detail="Seeding already in progress"
        )
    
    if not await seeder.initialize():
        raise HTTPException(status_code=500, detail="Failed to initialize knowledge store")
    
    try:
        if request.entity_types:
            results = {}
            for entity_type in request.entity_types:
                if entity_type == "companies":
                    results["companies"] = await seeder.seed_companies_only()
                elif entity_type == "materials":
                    results["materials"] = await seeder.seed_materials_only()
                elif entity_type == "processes":
                    results["processes"] = await seeder.seed_processes_only()
                elif entity_type == "industries":
                    results["industries"] = await seeder.seed_industries_only()
        else:
            results = await seeder.seed_all(clear_first=request.clear_first)
        
        return {
            "status": "completed",
            "results": results,
            "progress": seeder.get_progress(),
        }
        
    except Exception as e:
        logger.error(f"Seeding error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cancel")
async def cancel_seeding():
    """Cancel current seeding operation."""
    seeder = get_seeder()
    
    if seeder.progress.status != "running":
        raise HTTPException(status_code=400, detail="No seeding in progress")
    
    seeder.cancel()
    
    return {
        "status": "cancellation_requested",
        "message": "Seeding will stop after current entity completes",
    }


@router.post("/search")
async def search_knowledge(request: SearchRequest):
    """
    Search the knowledge base semantically.
    
    Returns relevant documents about companies, materials, processes,
    and industries based on the query.
    """
    seeder = get_seeder()
    
    if not await seeder.initialize():
        raise HTTPException(status_code=500, detail="Knowledge store unavailable")
    
    # Convert entity type string to enum
    entity_type = None
    if request.entity_type:
        try:
            entity_type = EntityType(request.entity_type)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid entity_type. Must be one of: company, material, process, industry"
            )
    
    results = await seeder.search(
        query=request.query,
        limit=request.limit,
        entity_type=entity_type,
    )
    
    return {
        "query": request.query,
        "count": len(results),
        "results": results,
    }


@router.get("/search")
async def search_knowledge_get(
    q: str = Query(..., description="Search query"),
    limit: int = Query(10, ge=1, le=50),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
):
    """Search knowledge base (GET method for convenience)."""
    request = SearchRequest(query=q, limit=limit, entity_type=entity_type)
    return await search_knowledge(request)


@router.get("/entity/{entity_name}")
async def get_entity(
    entity_name: str,
    entity_type: Optional[str] = Query(None),
):
    """
    Get all documents for a specific entity by name.
    
    Example: /api/knowledge/entity/Boeing
    """
    store = get_knowledge_store()
    await store.initialize()
    
    if not store.is_available:
        raise HTTPException(status_code=500, detail="Knowledge store unavailable")
    
    # Convert entity type
    et = None
    if entity_type:
        try:
            et = EntityType(entity_type)
        except ValueError:
            pass
    
    results = await store.get_by_entity_name(entity_name, et)
    
    if not results:
        raise HTTPException(status_code=404, detail=f"Entity '{entity_name}' not found")
    
    return {
        "entity_name": entity_name,
        "document_count": len(results),
        "documents": results,
    }


@router.post("/export")
async def export_knowledge(request: ExportRequest):
    """
    Export knowledge base to JSON file.
    
    This creates a backup that can be:
    - Uploaded to GCS for Cloud Run deployment
    - Version controlled
    - Imported into another environment
    """
    seeder = get_seeder()
    
    if not await seeder.initialize():
        raise HTTPException(status_code=500, detail="Knowledge store unavailable")
    
    success = await seeder.export_json(request.output_path)
    
    if not success:
        raise HTTPException(status_code=500, detail="Export failed")
    
    stats = await seeder.get_stats()
    
    return {
        "status": "exported",
        "output_path": request.output_path,
        "documents_exported": stats.get("total_documents", 0),
    }


@router.post("/import")
async def import_knowledge(request: ImportRequest):
    """
    Import knowledge base from JSON file.
    
    Use this to restore from a backup or deploy pre-seeded knowledge.
    """
    seeder = get_seeder()
    
    if not await seeder.initialize():
        raise HTTPException(status_code=500, detail="Knowledge store unavailable")
    
    count = await seeder.import_json(request.input_path, request.clear_first)
    
    if count == 0:
        raise HTTPException(status_code=500, detail="Import failed or file was empty")
    
    return {
        "status": "imported",
        "documents_imported": count,
        "input_path": request.input_path,
    }


@router.delete("/clear")
async def clear_knowledge():
    """
    Clear all documents from the knowledge base.
    
    **Warning:** This permanently deletes all knowledge. Use with caution.
    """
    store = get_knowledge_store()
    await store.initialize()
    
    if not store.is_available:
        raise HTTPException(status_code=500, detail="Knowledge store unavailable")
    
    await store.clear()
    
    return {
        "status": "cleared",
        "message": "Knowledge base has been cleared",
    }


@router.get("/test/wikipedia")
async def test_wikipedia_connection():
    """
    Test Wikipedia API connection.
    
    Fetches a test article to verify connectivity.
    """
    from app.knowledge.wikipedia_client import WikipediaClient
    
    client = WikipediaClient()
    success = await client.test_connection()
    
    if success:
        return {
            "status": "connected",
            "message": "Successfully connected to Wikipedia API",
        }
    else:
        raise HTTPException(
            status_code=503,
            detail="Failed to connect to Wikipedia API"
        )


@router.get("/entities/summary")
async def get_entities_summary():
    """
    Get summary of all entities available for seeding.
    
    Returns counts of companies, materials, processes, and industries
    that will be seeded from the master lists.
    """
    from app.knowledge.entities import (
        COMPANIES_TO_SEED,
        MATERIALS_TO_SEED,
        PROCESSES_TO_SEED,
        INDUSTRIES_TO_SEED,
        get_total_entity_count,
    )
    
    company_count = sum(len(companies) for companies in COMPANIES_TO_SEED.values())
    
    return {
        "total_entities": get_total_entity_count(),
        "companies": {
            "total": company_count,
            "by_type": {k: len(v) for k, v in COMPANIES_TO_SEED.items()},
        },
        "materials": len(MATERIALS_TO_SEED),
        "processes": len(PROCESSES_TO_SEED),
        "industries": len(INDUSTRIES_TO_SEED),
    }


# ============================================================================
# GCS Export/Import Endpoints (for Cloud Run deployment)
# ============================================================================

class GCSUploadRequest(BaseModel):
    """Request to upload to GCS."""
    local_path: str = Field(
        default="./data/knowledge_export.json",
        description="Local JSON file to upload"
    )


class GCSDownloadRequest(BaseModel):
    """Request to download from GCS."""
    local_path: str = Field(
        default="./data/knowledge_import.json",
        description="Where to save downloaded file"
    )


@router.get("/gcs/status")
async def get_gcs_status():
    """
    Check GCS connectivity status.
    
    Returns whether GCS is available and configured.
    """
    from app.knowledge.gcs_export import get_gcs_exporter, GCS_AVAILABLE
    
    if not GCS_AVAILABLE:
        return {
            "status": "unavailable",
            "message": "google-cloud-storage not installed. Run: pip install google-cloud-storage",
            "gcs_available": False,
        }
    
    exporter = get_gcs_exporter()
    
    return {
        "status": "available",
        "bucket_name": exporter.bucket_name,
        "project_id": exporter.project_id,
        "gcs_available": True,
    }


@router.post("/gcs/upload")
async def upload_to_gcs(request: GCSUploadRequest):
    """
    Upload knowledge export to GCS.
    
    First export the knowledge base locally, then use this to upload to GCS.
    Creates both a timestamped version and a 'latest' version.
    """
    from app.knowledge.gcs_export import get_gcs_exporter, GCS_AVAILABLE
    
    if not GCS_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="GCS not available. Install google-cloud-storage package."
        )
    
    # Verify local file exists
    from pathlib import Path
    local_path = Path(request.local_path)
    if not local_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Local file not found: {request.local_path}. Export knowledge first with /api/knowledge/export"
        )
    
    exporter = get_gcs_exporter()
    success = await exporter.upload_latest(str(local_path))
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to upload to GCS")
    
    return {
        "status": "uploaded",
        "bucket": exporter.bucket_name,
        "message": "Uploaded to both timestamped and 'latest' locations",
    }


@router.post("/gcs/download")
async def download_from_gcs(request: GCSDownloadRequest):
    """
    Download latest knowledge export from GCS.
    
    Downloads the 'latest.json' file from GCS. Use this on Cloud Run
    startup to initialize the knowledge base from a pre-seeded export.
    """
    from app.knowledge.gcs_export import get_gcs_exporter, GCS_AVAILABLE
    
    if not GCS_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="GCS not available. Install google-cloud-storage package."
        )
    
    exporter = get_gcs_exporter()
    success = await exporter.download_latest(request.local_path)
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to download from GCS")
    
    return {
        "status": "downloaded",
        "local_path": request.local_path,
        "message": "Downloaded latest.json from GCS. Use /api/knowledge/import to load it.",
    }


@router.get("/gcs/list")
async def list_gcs_exports():
    """
    List all knowledge exports in GCS bucket.
    
    Shows timestamped backups and the current 'latest' version.
    """
    from app.knowledge.gcs_export import get_gcs_exporter, GCS_AVAILABLE
    
    if not GCS_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="GCS not available"
        )
    
    exporter = get_gcs_exporter()
    exports = await exporter.list_exports()
    
    return {
        "bucket": exporter.bucket_name,
        "exports": exports,
        "count": len(exports),
    }
