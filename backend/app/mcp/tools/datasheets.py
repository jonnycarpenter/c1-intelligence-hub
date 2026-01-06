"""Datasheets MCP tools - Query product spec sheets from BigQuery.

These tools query the datasheets table for material specifications, product info,
and supplier data. Used by the Category Agent for product recommendations.

Data source: BigQuery `c1_intelligence.datasheets` (scraped from supplier websites)
"""

import asyncio
import json
from typing import Optional, List
from langchain_core.tools import tool

from google.cloud import bigquery
from google.api_core.exceptions import GoogleAPIError

from app.utils.logger import get_logger
from app.scrapers.config import ScraperConfig

logger = get_logger(__name__)

# Initialize config for BQ settings
config = ScraperConfig()


def _get_bq_client() -> bigquery.Client:
    """Get BigQuery client."""
    return bigquery.Client(project=config.gcp_project)


def _format_datasheet(row: dict) -> dict:
    """Format a datasheet row for tool output."""
    return {
        "datasheet_id": row.get("datasheet_id", ""),
        "supplier": row.get("supplier_name", ""),
        "product_name": row.get("product_name"),
        "product_family": row.get("product_family"),
        "title": row.get("title", ""),
        "url": row.get("url", ""),
        "material_category": row.get("material_category", "other"),
        "material_subcategory": row.get("material_subcategory"),
        "industries": row.get("industries", []) or [],
        "text_preview": (row.get("text_preview", "") or "")[:300],
        "page_count": row.get("page_count", 0) or 0,
    }


@tool
def query_datasheets(
    query: Optional[str] = None,
    supplier: Optional[str] = None,
    category: Optional[str] = None,
    industry: Optional[str] = None,
    product_family: Optional[str] = None,
    limit: int = 20,
) -> str:
    """
    Query product datasheets from BigQuery.
    
    Search for material specifications, product data sheets, and technical specs
    from composites industry suppliers. Returns product details with links to
    full datasheet PDFs.
    
    Args:
        query: Free-text search across title, product name, and content.
               Example: "carbon fiber prepreg", "epoxy resin", "honeycomb core"
        supplier: Filter by supplier name. 
                  Example: "Hexcel", "Toray", "Solvay", "Gurit"
        category: Filter by material category.
                  Options: carbon_fiber, glass_fiber, aramid_fiber, prepreg,
                          resin_epoxy, resin_polyester, resin_vinylester,
                          core_honeycomb, core_foam, adhesive, fabric, tooling, other
        industry: Filter by target industry.
                  Example: "aerospace", "automotive", "marine", "wind"
        product_family: Filter by product family/line.
                        Example: "HexPly", "AS4", "IM7"
        limit: Maximum results to return (default 20, max 50)
    
    Returns:
        JSON with matching datasheets including product specs and PDF links.
    """
    logger.info(f"query_datasheets: query={query}, supplier={supplier}, category={category}, industry={industry}")
    
    try:
        client = _get_bq_client()
        table_id = f"{config.gcp_project}.{config.bq_dataset}.{config.bq_datasheets_table}"
        
        # Build query with filters
        where_clauses = ["is_active = TRUE"]
        params = []
        
        # Full-text search if query provided
        if query:
            where_clauses.append("""(
                LOWER(title) LIKE LOWER(@search_term)
                OR LOWER(product_name) LIKE LOWER(@search_term)
                OR LOWER(product_family) LIKE LOWER(@search_term)
                OR LOWER(extracted_text) LIKE LOWER(@search_term)
            )""")
            params.append(bigquery.ScalarQueryParameter("search_term", "STRING", f"%{query}%"))
        
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
        
        # Enforce limit bounds
        limit = min(max(limit, 1), 50)
        
        # Build the query
        sql = f"""
            SELECT 
                datasheet_id, supplier_name, product_name, product_family,
                title, url, filename, material_category, material_subcategory,
                industries, text_preview, page_count
            FROM `{table_id}`
            WHERE {where_sql}
            ORDER BY 
                CASE 
                    WHEN @search_term IS NOT NULL AND LOWER(title) LIKE LOWER(@search_term) THEN 1
                    WHEN @search_term IS NOT NULL AND LOWER(product_name) LIKE LOWER(@search_term) THEN 2
                    ELSE 3
                END,
                supplier_name, title
            LIMIT @limit
        """
        
        # Add search_term param even if null for ORDER BY
        if not query:
            params.append(bigquery.ScalarQueryParameter("search_term", "STRING", None))
        
        params.append(bigquery.ScalarQueryParameter("limit", "INT64", limit))
        
        job_config = bigquery.QueryJobConfig(query_parameters=params)
        results = client.query(sql, job_config=job_config).result()
        
        datasheets = [_format_datasheet(dict(row)) for row in results]
        
        return json.dumps({
            "status": "success",
            "count": len(datasheets),
            "datasheets": datasheets,
        }, indent=2)
        
    except GoogleAPIError as e:
        logger.error(f"BigQuery error in query_datasheets: {e}")
        return json.dumps({
            "status": "error",
            "error": f"Database error: {str(e)}",
            "datasheets": [],
        })
    except Exception as e:
        logger.error(f"Error in query_datasheets: {e}")
        return json.dumps({
            "status": "error",
            "error": str(e),
            "datasheets": [],
        })


@tool
def get_datasheet_detail(datasheet_id: str) -> str:
    """
    Get full details for a specific datasheet including extracted text.
    
    Use this to get complete product specifications after finding a datasheet
    via query_datasheets.
    
    Args:
        datasheet_id: The unique ID of the datasheet (from query_datasheets results)
    
    Returns:
        JSON with full datasheet details including extracted text content.
    """
    logger.info(f"get_datasheet_detail: {datasheet_id}")
    
    try:
        client = _get_bq_client()
        table_id = f"{config.gcp_project}.{config.bq_dataset}.{config.bq_datasheets_table}"
        
        query = f"""
            SELECT 
                datasheet_id, supplier_name, product_name, product_family,
                title, url, filename, material_category, material_subcategory,
                industries, text_preview, extracted_text, page_count,
                file_size_bytes, structured_properties
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
            return json.dumps({
                "status": "error",
                "error": f"Datasheet not found: {datasheet_id}",
            })
        
        row = dict(results[0])
        
        return json.dumps({
            "status": "success",
            "datasheet": {
                "datasheet_id": row.get("datasheet_id", ""),
                "supplier": row.get("supplier_name", ""),
                "product_name": row.get("product_name"),
                "product_family": row.get("product_family"),
                "title": row.get("title", ""),
                "url": row.get("url", ""),
                "material_category": row.get("material_category", "other"),
                "material_subcategory": row.get("material_subcategory"),
                "industries": row.get("industries", []) or [],
                "page_count": row.get("page_count", 0) or 0,
                "file_size_bytes": row.get("file_size_bytes", 0) or 0,
                "extracted_text": row.get("extracted_text", "") or "",
                "structured_properties": row.get("structured_properties"),
            },
        }, indent=2)
        
    except GoogleAPIError as e:
        logger.error(f"BigQuery error in get_datasheet_detail: {e}")
        return json.dumps({
            "status": "error",
            "error": f"Database error: {str(e)}",
        })
    except Exception as e:
        logger.error(f"Error in get_datasheet_detail: {e}")
        return json.dumps({
            "status": "error",
            "error": str(e),
        })


@tool
def get_datasheet_stats() -> str:
    """
    Get statistics about the datasheet collection.
    
    Returns counts by supplier, material category, and last update info.
    Useful for understanding what product data is available.
    
    Returns:
        JSON with datasheet collection statistics.
    """
    logger.info("get_datasheet_stats")
    
    try:
        client = _get_bq_client()
        table_id = f"{config.gcp_project}.{config.bq_dataset}.{config.bq_datasheets_table}"
        
        # Get supplier stats
        supplier_query = f"""
            SELECT 
                supplier_name,
                COUNT(*) as datasheet_count,
                ARRAY_AGG(DISTINCT material_category) as categories
            FROM `{table_id}`
            WHERE is_active = TRUE
            GROUP BY supplier_name
            ORDER BY datasheet_count DESC
        """
        
        supplier_results = client.query(supplier_query).result()
        suppliers = []
        total_datasheets = 0
        
        for row in supplier_results:
            total_datasheets += row.datasheet_count
            suppliers.append({
                "supplier": row.supplier_name,
                "count": row.datasheet_count,
                "categories": list(row.categories or []),
            })
        
        # Get category breakdown
        category_query = f"""
            SELECT material_category, COUNT(*) as count
            FROM `{table_id}`
            WHERE is_active = TRUE
            GROUP BY material_category
            ORDER BY count DESC
        """
        
        category_results = client.query(category_query).result()
        categories = {row.material_category: row.count for row in category_results}
        
        return json.dumps({
            "status": "success",
            "total_datasheets": total_datasheets,
            "total_suppliers": len(suppliers),
            "suppliers": suppliers,
            "categories_breakdown": categories,
        }, indent=2)
        
    except GoogleAPIError as e:
        logger.error(f"BigQuery error in get_datasheet_stats: {e}")
        return json.dumps({
            "status": "error",
            "error": f"Database error: {str(e)}",
        })
    except Exception as e:
        logger.error(f"Error in get_datasheet_stats: {e}")
        return json.dumps({
            "status": "error",
            "error": str(e),
        })


@tool
def get_products_by_industry(
    industry: str,
    limit: int = 30,
) -> str:
    """
    Get product datasheets relevant to a specific industry.
    
    Use this to find materials and products commonly used in a target market.
    
    Args:
        industry: Target industry (aerospace, automotive, marine, wind, defense,
                  sporting_goods, construction, industrial)
        limit: Maximum results (default 30)
    
    Returns:
        JSON with datasheets organized by material category for the industry.
    """
    logger.info(f"get_products_by_industry: {industry}")
    
    try:
        client = _get_bq_client()
        table_id = f"{config.gcp_project}.{config.bq_dataset}.{config.bq_datasheets_table}"
        
        limit = min(max(limit, 1), 100)
        
        query = f"""
            SELECT 
                datasheet_id, supplier_name, product_name, product_family,
                title, url, material_category, material_subcategory,
                industries, text_preview
            FROM `{table_id}`
            WHERE is_active = TRUE
              AND @industry IN UNNEST(industries)
            ORDER BY material_category, supplier_name, title
            LIMIT @limit
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("industry", "STRING", industry.lower()),
                bigquery.ScalarQueryParameter("limit", "INT64", limit),
            ]
        )
        
        results = client.query(query, job_config=job_config).result()
        
        # Group by category
        by_category = {}
        for row in results:
            row_dict = dict(row)
            cat = row_dict.get("material_category", "other")
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(_format_datasheet(row_dict))
        
        return json.dumps({
            "status": "success",
            "industry": industry,
            "total_count": sum(len(v) for v in by_category.values()),
            "by_category": by_category,
        }, indent=2)
        
    except GoogleAPIError as e:
        logger.error(f"BigQuery error in get_products_by_industry: {e}")
        return json.dumps({
            "status": "error",
            "error": f"Database error: {str(e)}",
        })
    except Exception as e:
        logger.error(f"Error in get_products_by_industry: {e}")
        return json.dumps({
            "status": "error",
            "error": str(e),
        })
