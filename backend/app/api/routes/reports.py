"""Reports API endpoints."""

from typing import Optional, List
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from pathlib import Path
import uuid
from datetime import datetime

from app.api.schemas import ReportExportRequest, ReportExportItem, ExportFormat
from app.services.report_service import ReportService
from app.utils.logger import get_logger
from app.config.settings import settings

logger = get_logger(__name__)
router = APIRouter()

# Initialize report service
report_service = ReportService()

# In-memory report storage (would be database in production)
REPORTS_STORE: dict = {}
REPORTS_DIR = Path(__file__).parent.parent.parent / "reports"
REPORTS_DIR.mkdir(exist_ok=True)


class ReportRequest(BaseModel):
    """Report generation request."""
    type: str  # intelligence, financial, product, data
    title: Optional[str] = None
    parameters: Optional[dict] = None


class ReportResponse(BaseModel):
    """Report response."""
    report_id: str
    status: str
    title: str
    created_at: str
    download_url: Optional[str] = None


@router.post("/generate")
async def generate_report(request: ReportRequest) -> ReportResponse:
    """
    Generate a report based on type and parameters.
    
    Report types:
    - intelligence: Market intelligence report
    - financial: Financial insights report
    - product: Product analysis report
    - data: Data export
    """
    logger.info(f"Report generation request: type={request.type}")
    
    report_id = str(uuid.uuid4())[:8]
    title = request.title or f"{request.type.title()} Report"
    created_at = datetime.now().isoformat()
    
    # Store report metadata
    REPORTS_STORE[report_id] = {
        "id": report_id,
        "type": request.type,
        "title": title,
        "status": "generating",
        "created_at": created_at,
        "parameters": request.parameters,
    }
    
    # TODO: Implement actual report generation
    # For now, just mark as ready
    REPORTS_STORE[report_id]["status"] = "ready"
    REPORTS_STORE[report_id]["download_url"] = f"/api/reports/{report_id}/download"
    
    return ReportResponse(
        report_id=report_id,
        status="ready",
        title=title,
        created_at=created_at,
        download_url=f"/api/reports/{report_id}/download",
    )


@router.get("/{report_id}")
async def get_report(report_id: str) -> ReportResponse:
    """Get report status and metadata."""
    if report_id not in REPORTS_STORE:
        raise HTTPException(status_code=404, detail="Report not found")
    
    report = REPORTS_STORE[report_id]
    return ReportResponse(
        report_id=report["id"],
        status=report["status"],
        title=report["title"],
        created_at=report["created_at"],
        download_url=report.get("download_url"),
    )


@router.get("/{report_id}/download")
async def download_report(report_id: str):
    """Download a generated report."""
    if report_id not in REPORTS_STORE:
        raise HTTPException(status_code=404, detail="Report not found")
    
    report = REPORTS_STORE[report_id]
    if report["status"] != "ready":
        raise HTTPException(status_code=400, detail="Report not ready for download")
    
    # Check for file
    report_file = REPORTS_DIR / f"{report_id}.md"
    if not report_file.exists():
        # Create a placeholder report
        report_file.write_text(f"# {report['title']}\n\nGenerated: {report['created_at']}\n\nReport content would go here.")
    
    return FileResponse(
        path=str(report_file),
        filename=f"{report['title'].replace(' ', '_')}.md",
        media_type="text/markdown",
    )


@router.get("")
async def list_reports() -> list[ReportResponse]:
    """List all reports."""
    return [
        ReportResponse(
            report_id=r["id"],
            status=r["status"],
            title=r["title"],
            created_at=r["created_at"],
            download_url=r.get("download_url"),
        )
        for r in REPORTS_STORE.values()
    ]


# ============================================
# New Export Endpoint (for Report Builder)
# ============================================

@router.post("/export")
async def export_report(request: ReportExportRequest):
    """
    Export report items to PDF, DOCX, or PPTX format.
    
    This endpoint is used by the Report Builder feature to export
    collected intelligence items into a downloadable document.
    
    Formats:
    - pdf: Professional PDF document
    - docx: Microsoft Word document (editable)
    - pptx: PowerPoint presentation
    """
    logger.info(f"Report export request: format={request.format}, items={len(request.items)}")
    
    if not request.items:
        raise HTTPException(status_code=400, detail="No items to export")
    
    try:
        content = await report_service.export_report(
            format=request.format,
            items=request.items,
            title=request.title or "Intelligence Report",
        )
        
        # Set appropriate content type and filename
        content_types = {
            ExportFormat.PDF: "application/pdf",
            ExportFormat.DOCX: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ExportFormat.PPTX: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        }
        
        extensions = {
            ExportFormat.PDF: "pdf",
            ExportFormat.DOCX: "docx",
            ExportFormat.PPTX: "pptx",
        }
        
        filename = f"intelligence_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{extensions[request.format]}"
        
        return Response(
            content=content,
            media_type=content_types[request.format],
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
            },
        )
        
    except Exception as e:
        logger.error(f"Export error: {e}")
        raise HTTPException(status_code=500, detail="Failed to export report")


# ============================================
# Research Reports Storage (BigQuery)
# ============================================

class ResearchReportSource(BaseModel):
    """A source referenced in a research report."""
    title: Optional[str] = None
    name: Optional[str] = None
    url: Optional[str] = None


class SaveResearchReportRequest(BaseModel):
    """Request to save a research report."""
    query: str = Field(..., description="The original query that generated this report")
    title: str = Field(..., description="Title of the report section")
    content: str = Field(..., description="The full markdown content of the report")
    agent: str = Field(default="market_scout", description="Agent that generated the report")
    sources: List[ResearchReportSource] = Field(default_factory=list)
    companies_mentioned: List[str] = Field(default_factory=list)
    materials_mentioned: List[str] = Field(default_factory=list)


class SaveResearchReportResponse(BaseModel):
    """Response after saving a research report."""
    id: str
    success: bool
    message: str


class ResearchReportResponse(BaseModel):
    """A stored research report."""
    id: str
    query: str
    title: str
    content: str
    agent: str
    sources: List[dict]
    companies_mentioned: List[str]
    materials_mentioned: List[str]
    created_at: Optional[str]


@router.post("/research", response_model=SaveResearchReportResponse)
async def save_research_report(request: SaveResearchReportRequest):
    """
    Save a research report to BigQuery for tracking and history.
    
    Called when the Market Scout agent completes a research query
    and generates a report section on the canvas.
    """
    report_id = str(uuid.uuid4())[:12]
    
    try:
        # Check if we're using BigQuery storage
        if settings.storage_backend == "gcp":
            from app.db.gcp_storage import get_bigquery_storage
            
            storage = get_bigquery_storage()
            await storage.initialize()
            
            # Convert sources to dicts
            sources_dicts = [s.model_dump() for s in request.sources]
            
            success = await storage.store_research_report(
                report_id=report_id,
                query=request.query,
                title=request.title,
                content=request.content,
                agent=request.agent,
                sources=sources_dicts,
                companies=request.companies_mentioned,
                materials=request.materials_mentioned,
            )
            
            if success:
                return SaveResearchReportResponse(
                    id=report_id,
                    success=True,
                    message="Report saved to BigQuery",
                )
            else:
                raise HTTPException(status_code=500, detail="Failed to save to BigQuery")
        else:
            # Fallback to in-memory storage for local dev
            REPORTS_STORE[report_id] = {
                "id": report_id,
                "type": "research",
                "query": request.query,
                "title": request.title,
                "content": request.content,
                "agent": request.agent,
                "sources": [s.model_dump() for s in request.sources],
                "companies_mentioned": request.companies_mentioned,
                "materials_mentioned": request.materials_mentioned,
                "created_at": datetime.now().isoformat(),
            }
            return SaveResearchReportResponse(
                id=report_id,
                success=True,
                message="Report saved locally",
            )
            
    except Exception as e:
        logger.error(f"Failed to save research report: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save report: {str(e)}")


@router.get("/research", response_model=List[ResearchReportResponse])
async def list_research_reports(
    agent: Optional[str] = None,
    limit: int = 50,
):
    """
    List saved research reports.
    
    Optionally filter by agent type.
    """
    try:
        if settings.storage_backend == "gcp":
            from app.db.gcp_storage import get_bigquery_storage
            
            storage = get_bigquery_storage()
            await storage.initialize()
            
            reports = await storage.get_research_reports(agent=agent, limit=limit)
            return [ResearchReportResponse(**r) for r in reports]
        else:
            # Return from in-memory store
            research_reports = [
                r for r in REPORTS_STORE.values() 
                if r.get("type") == "research" and (not agent or r.get("agent") == agent)
            ]
            return [
                ResearchReportResponse(
                    id=r["id"],
                    query=r.get("query", ""),
                    title=r["title"],
                    content=r.get("content", ""),
                    agent=r.get("agent", "market_scout"),
                    sources=r.get("sources", []),
                    companies_mentioned=r.get("companies_mentioned", []),
                    materials_mentioned=r.get("materials_mentioned", []),
                    created_at=r.get("created_at"),
                )
                for r in research_reports[:limit]
            ]
            
    except Exception as e:
        logger.error(f"Failed to list research reports: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list reports: {str(e)}")
