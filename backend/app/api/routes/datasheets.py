"""
Datasheets API Endpoints
========================

Query and search material datasheets scraped from supplier websites.
Data is stored in BigQuery: <GCP_PROJECT_ID>.c1_intelligence.datasheets
"""

from typing import Optional, List
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum

from google.cloud import bigquery
from google.api_core.exceptions import GoogleAPIError

from app.utils.logger import get_logger
from app.scrapers.config import ScraperConfig

logger = get_logger(__name__)

router = APIRouter()

# Initialize BigQuery client
config = ScraperConfig()


# ============================================================================
# Enums & Models
# ============================================================================

class MaterialCategory(str, Enum):
    """Material categories for filtering."""
    CARBON_FIBER = "carbon_fiber"
    GLASS_FIBER = "glass_fiber"
    ARAMID_FIBER = "aramid_fiber"
    PREPREG = "prepreg"
    RESIN_EPOXY = "resin_epoxy"
    RESIN_POLYESTER = "resin_polyester"
    RESIN_VINYLESTER = "resin_vinylester"
    CORE_HONEYCOMB = "core_honeycomb"
    CORE_FOAM = "core_foam"
    ADHESIVE = "adhesive"
    FABRIC = "fabric"
    TOOLING = "tooling"
    OTHER = "other"


class Datasheet(BaseModel):
    """Datasheet model for API responses."""
    datasheet_id: str
    supplier_name: str
    product_name: Optional[str] = None
    product_family: Optional[str] = None
    title: str
    url: str
    filename: str
    material_category: str
    material_subcategory: Optional[str] = None
    industries: List[str] = []
    text_preview: str = ""
    page_count: int = 0
    file_size_bytes: int = 0
    content_type: str = "application/pdf"
    downloaded_at: Optional[str] = None
    last_verified_at: Optional[str] = None


class DatasheetDetail(Datasheet):
    """Full datasheet details including extracted text."""
    extracted_text: str = ""
    structured_properties: Optional[dict] = None
    text_extraction_success: bool = True
    file_hash: str = ""
    scrape_run_id: str = ""


class DatasheetsResponse(BaseModel):
    """Response model for datasheets list."""
    count: int
    total: int
    offset: int
    limit: int
    datasheets: List[Datasheet]
    
    # Facets for filtering
    suppliers: List[str] = []
    categories: List[str] = []
    industries: List[str] = []


class DatasheetSearchResponse(BaseModel):
    """Response model for full-text search."""
    count: int
    query: str
    datasheets: List[Datasheet]


class SupplierStats(BaseModel):
    """Statistics for a supplier."""
    supplier_name: str
    datasheet_count: int
    categories: List[str]
    last_scraped: Optional[str] = None


class StatsResponse(BaseModel):
    """Response model for datasheet statistics."""
    total_datasheets: int
    total_suppliers: int
    suppliers: List[SupplierStats]
    categories: dict  # category -> count
    last_scrape_run: Optional[str] = None


# ============================================================================
# Helper Functions
# ============================================================================

def get_bq_client() -> bigquery.Client:
    """Get BigQuery client."""
    return bigquery.Client(project=config.gcp_project)


def row_to_datasheet(row: dict) -> Datasheet:
    """Convert BigQuery row to Datasheet model."""
    return Datasheet(
        datasheet_id=row.get("datasheet_id", ""),
        supplier_name=row.get("supplier_name", ""),
        product_name=row.get("product_name"),
        product_family=row.get("product_family"),
        title=row.get("title", ""),
        url=row.get("url", ""),
        filename=row.get("filename", ""),
        material_category=row.get("material_category", "other"),
        material_subcategory=row.get("material_subcategory"),
        industries=row.get("industries", []) or [],
        text_preview=row.get("text_preview", "")[:500] if row.get("text_preview") else "",
        page_count=row.get("page_count", 0) or 0,
        file_size_bytes=row.get("file_size_bytes", 0) or 0,
        content_type=row.get("content_type", "application/pdf"),
        downloaded_at=str(row.get("downloaded_at")) if row.get("downloaded_at") else None,
        last_verified_at=str(row.get("last_verified_at")) if row.get("last_verified_at") else None,
    )


def row_to_datasheet_detail(row: dict) -> DatasheetDetail:
    """Convert BigQuery row to DatasheetDetail model."""
    return DatasheetDetail(
        datasheet_id=row.get("datasheet_id", ""),
        supplier_name=row.get("supplier_name", ""),
        product_name=row.get("product_name"),
        product_family=row.get("product_family"),
        title=row.get("title", ""),
        url=row.get("url", ""),
        filename=row.get("filename", ""),
        material_category=row.get("material_category", "other"),
        material_subcategory=row.get("material_subcategory"),
        industries=row.get("industries", []) or [],
        text_preview=row.get("text_preview", "")[:500] if row.get("text_preview") else "",
        page_count=row.get("page_count", 0) or 0,
        file_size_bytes=row.get("file_size_bytes", 0) or 0,
        content_type=row.get("content_type", "application/pdf"),
        downloaded_at=str(row.get("downloaded_at")) if row.get("downloaded_at") else None,
        last_verified_at=str(row.get("last_verified_at")) if row.get("last_verified_at") else None,
        extracted_text=row.get("extracted_text", "") or "",
        structured_properties=row.get("structured_properties"),
        text_extraction_success=row.get("text_extraction_success", True),
        file_hash=row.get("file_hash", ""),
        scrape_run_id=row.get("scrape_run_id", ""),
    )


# ============================================================================
# Endpoints
# ============================================================================

@router.get("", response_model=DatasheetsResponse)
async def list_datasheets(
    supplier: Optional[str] = Query(None, description="Filter by supplier name"),
    category: Optional[str] = Query(None, description="Filter by material category"),
    industry: Optional[str] = Query(None, description="Filter by industry"),
    product_family: Optional[str] = Query(None, description="Filter by product family"),
    limit: int = Query(50, le=200, ge=1, description="Maximum results to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
):
    """
    List datasheets with optional filtering.
    
    Returns datasheets from all scraped suppliers with faceted filtering support.
    """
    logger.info(f"GET /datasheets: supplier={supplier}, category={category}, industry={industry}")
    
    try:
        client = get_bq_client()
        table_id = f"{config.gcp_project}.{config.bq_dataset}.{config.bq_datasheets_table}"
        
        # Build query with filters
        where_clauses = ["is_active = TRUE"]
        params = []
        
        if supplier:
            where_clauses.append("LOWER(supplier_name) LIKE LOWER(@supplier)")
            params.append(bigquery.ScalarQueryParameter("supplier", "STRING", f"%{supplier}%"))
        
        if category:
            where_clauses.append("LOWER(material_category) = LOWER(@category)")
            params.append(bigquery.ScalarQueryParameter("category", "STRING", category))
        
        if industry:
            where_clauses.append("@industry IN UNNEST(industries)")
            params.append(bigquery.ScalarQueryParameter("industry", "STRING", industry))
        
        if product_family:
            where_clauses.append("LOWER(product_family) LIKE LOWER(@product_family)")
            params.append(bigquery.ScalarQueryParameter("product_family", "STRING", f"%{product_family}%"))
        
        where_sql = " AND ".join(where_clauses)
        
        # Get total count
        count_query = f"""
            SELECT COUNT(*) as total
            FROM `{table_id}`
            WHERE {where_sql}
        """
        
        job_config = bigquery.QueryJobConfig(query_parameters=params)
        count_result = client.query(count_query, job_config=job_config).result()
        total = list(count_result)[0].total
        
        # Get datasheets
        query = f"""
            SELECT 
                datasheet_id, supplier_name, product_name, product_family,
                title, url, filename, material_category, material_subcategory,
                industries, text_preview, page_count, file_size_bytes,
                content_type, downloaded_at, last_verified_at
            FROM `{table_id}`
            WHERE {where_sql}
            ORDER BY supplier_name, title
            LIMIT @limit OFFSET @offset
        """
        
        params.extend([
            bigquery.ScalarQueryParameter("limit", "INT64", limit),
            bigquery.ScalarQueryParameter("offset", "INT64", offset),
        ])
        
        job_config = bigquery.QueryJobConfig(query_parameters=params)
        results = client.query(query, job_config=job_config).result()
        
        datasheets = [row_to_datasheet(dict(row)) for row in results]
        
        # Get facets (unique values for filtering)
        facets_query = f"""
            SELECT 
                ARRAY_AGG(DISTINCT supplier_name ORDER BY supplier_name) as suppliers,
                ARRAY_AGG(DISTINCT material_category ORDER BY material_category) as categories
            FROM `{table_id}`
            WHERE is_active = TRUE
        """
        facets_result = list(client.query(facets_query).result())[0]
        
        # Get unique industries
        industries_query = f"""
            SELECT DISTINCT industry
            FROM `{table_id}`, UNNEST(industries) as industry
            WHERE is_active = TRUE
            ORDER BY industry
        """
        industries_result = client.query(industries_query).result()
        unique_industries = [row.industry for row in industries_result]
        
        return DatasheetsResponse(
            count=len(datasheets),
            total=total,
            offset=offset,
            limit=limit,
            datasheets=datasheets,
            suppliers=list(facets_result.suppliers or []),
            categories=list(facets_result.categories or []),
            industries=unique_industries,
        )
        
    except GoogleAPIError as e:
        logger.error(f"BigQuery error: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/search", response_model=DatasheetSearchResponse)
async def search_datasheets(
    q: str = Query(..., min_length=2, description="Search query"),
    supplier: Optional[str] = Query(None, description="Filter by supplier"),
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(50, le=100, ge=1, description="Maximum results"),
):
    """
    Full-text search across datasheet content.
    
    Searches in:
    - Title
    - Product name
    - Extracted text content
    """
    logger.info(f"GET /datasheets/search: q={q}, supplier={supplier}, category={category}")
    
    try:
        client = get_bq_client()
        table_id = f"{config.gcp_project}.{config.bq_dataset}.{config.bq_datasheets_table}"
        
        # Build search query
        where_clauses = [
            "is_active = TRUE",
            """(
                LOWER(title) LIKE LOWER(@search_term)
                OR LOWER(product_name) LIKE LOWER(@search_term)
                OR LOWER(product_family) LIKE LOWER(@search_term)
                OR LOWER(extracted_text) LIKE LOWER(@search_term)
            )"""
        ]
        
        params = [
            bigquery.ScalarQueryParameter("search_term", "STRING", f"%{q}%"),
        ]
        
        if supplier:
            where_clauses.append("LOWER(supplier_name) LIKE LOWER(@supplier)")
            params.append(bigquery.ScalarQueryParameter("supplier", "STRING", f"%{supplier}%"))
        
        if category:
            where_clauses.append("LOWER(material_category) = LOWER(@category)")
            params.append(bigquery.ScalarQueryParameter("category", "STRING", category))
        
        where_sql = " AND ".join(where_clauses)
        
        query = f"""
            SELECT 
                datasheet_id, supplier_name, product_name, product_family,
                title, url, filename, material_category, material_subcategory,
                industries, text_preview, page_count, file_size_bytes,
                content_type, downloaded_at, last_verified_at
            FROM `{table_id}`
            WHERE {where_sql}
            ORDER BY 
                CASE 
                    WHEN LOWER(title) LIKE LOWER(@search_term) THEN 1
                    WHEN LOWER(product_name) LIKE LOWER(@search_term) THEN 2
                    ELSE 3
                END,
                supplier_name, title
            LIMIT @limit
        """
        
        params.append(bigquery.ScalarQueryParameter("limit", "INT64", limit))
        
        job_config = bigquery.QueryJobConfig(query_parameters=params)
        results = client.query(query, job_config=job_config).result()
        
        datasheets = [row_to_datasheet(dict(row)) for row in results]
        
        return DatasheetSearchResponse(
            count=len(datasheets),
            query=q,
            datasheets=datasheets,
        )
        
    except GoogleAPIError as e:
        logger.error(f"BigQuery error: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/stats", response_model=StatsResponse)
async def get_datasheet_stats():
    """
    Get statistics about the datasheet collection.
    
    Returns counts by supplier, category, and scrape run info.
    """
    logger.info("GET /datasheets/stats")
    
    try:
        client = get_bq_client()
        table_id = f"{config.gcp_project}.{config.bq_dataset}.{config.bq_datasheets_table}"
        runs_table = f"{config.gcp_project}.{config.bq_dataset}.{config.bq_scrape_runs_table}"
        
        # Get supplier stats
        supplier_query = f"""
            SELECT 
                supplier_name,
                COUNT(*) as datasheet_count,
                ARRAY_AGG(DISTINCT material_category) as categories,
                MAX(downloaded_at) as last_scraped
            FROM `{table_id}`
            WHERE is_active = TRUE
            GROUP BY supplier_name
            ORDER BY datasheet_count DESC
        """
        
        supplier_results = client.query(supplier_query).result()
        supplier_stats = []
        total_datasheets = 0
        
        for row in supplier_results:
            total_datasheets += row.datasheet_count
            supplier_stats.append(SupplierStats(
                supplier_name=row.supplier_name,
                datasheet_count=row.datasheet_count,
                categories=list(row.categories or []),
                last_scraped=str(row.last_scraped) if row.last_scraped else None,
            ))
        
        # Get category counts
        category_query = f"""
            SELECT material_category, COUNT(*) as count
            FROM `{table_id}`
            WHERE is_active = TRUE
            GROUP BY material_category
            ORDER BY count DESC
        """
        
        category_results = client.query(category_query).result()
        categories = {row.material_category: row.count for row in category_results}
        
        # Get last scrape run
        run_query = f"""
            SELECT run_id, run_date
            FROM `{runs_table}`
            ORDER BY run_date DESC
            LIMIT 1
        """
        
        try:
            run_result = list(client.query(run_query).result())
            last_run = str(run_result[0].run_date) if run_result else None
        except:
            last_run = None
        
        return StatsResponse(
            total_datasheets=total_datasheets,
            total_suppliers=len(supplier_stats),
            suppliers=supplier_stats,
            categories=categories,
            last_scrape_run=last_run,
        )
        
    except GoogleAPIError as e:
        logger.error(f"BigQuery error: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/{datasheet_id}", response_model=DatasheetDetail)
async def get_datasheet(datasheet_id: str):
    """
    Get full details for a specific datasheet.
    
    Includes the complete extracted text content.
    """
    logger.info(f"GET /datasheets/{datasheet_id}")
    
    try:
        client = get_bq_client()
        table_id = f"{config.gcp_project}.{config.bq_dataset}.{config.bq_datasheets_table}"
        
        query = f"""
            SELECT *
            FROM `{table_id}`
            WHERE datasheet_id = @datasheet_id
            LIMIT 1
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("datasheet_id", "STRING", datasheet_id),
            ]
        )
        
        results = list(client.query(query, job_config=job_config).result())
        
        if not results:
            raise HTTPException(status_code=404, detail=f"Datasheet not found: {datasheet_id}")
        
        return row_to_datasheet_detail(dict(results[0]))
        
    except GoogleAPIError as e:
        logger.error(f"BigQuery error: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/supplier/{supplier_name}", response_model=DatasheetsResponse)
async def get_supplier_datasheets(
    supplier_name: str,
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(100, le=500, ge=1),
    offset: int = Query(0, ge=0),
):
    """
    Get all datasheets for a specific supplier.
    """
    logger.info(f"GET /datasheets/supplier/{supplier_name}")
    
    # Reuse list endpoint with supplier filter
    return await list_datasheets(
        supplier=supplier_name,
        category=category,
        industry=None,
        product_family=None,
        limit=limit,
        offset=offset,
    )
