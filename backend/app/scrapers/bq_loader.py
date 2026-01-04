"""
BigQuery Loader
===============

Loads scraped datasheets into BigQuery tables.
Handles upserts, deduplication, and scrape run tracking.
"""

import json
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict

from google.cloud import bigquery
from google.api_core.exceptions import NotFound

from app.scrapers.config import ScraperConfig

logger = logging.getLogger(__name__)


@dataclass
class DatasheetRecord:
    """A datasheet record for BigQuery insertion."""
    datasheet_id: str
    supplier_name: str
    product_name: Optional[str]
    product_family: Optional[str]
    title: str
    url: str
    filename: str
    
    material_category: str
    material_subcategory: Optional[str]
    industries: List[str]
    
    extracted_text: str
    text_preview: str
    page_count: int
    text_extraction_success: bool
    
    structured_properties: Optional[Dict[str, Any]] = None
    properties_extracted_at: Optional[datetime] = None
    
    file_size_bytes: int = 0
    file_hash: str = ""
    content_type: str = "application/pdf"
    
    scrape_run_id: str = ""
    discovered_at: Optional[datetime] = None
    downloaded_at: Optional[datetime] = None
    last_verified_at: Optional[datetime] = None
    is_active: bool = True
    
    def to_bq_row(self) -> Dict[str, Any]:
        """Convert to BigQuery row format."""
        now = datetime.now(timezone.utc)
        return {
            "datasheet_id": self.datasheet_id,
            "supplier_name": self.supplier_name,
            "product_name": self.product_name,
            "product_family": self.product_family,
            "title": self.title,
            "url": self.url,
            "filename": self.filename,
            "material_category": self.material_category,
            "material_subcategory": self.material_subcategory,
            "industries": self.industries,
            "extracted_text": self.extracted_text,
            "text_preview": self.text_preview,
            "page_count": self.page_count,
            "text_extraction_success": self.text_extraction_success,
            "structured_properties": json.dumps(self.structured_properties) if self.structured_properties else None,
            "properties_extracted_at": self.properties_extracted_at.isoformat() if self.properties_extracted_at else None,
            "file_size_bytes": self.file_size_bytes,
            "file_hash": self.file_hash,
            "content_type": self.content_type,
            "scrape_run_id": self.scrape_run_id,
            "discovered_at": self.discovered_at.isoformat() if self.discovered_at else now.isoformat(),
            "downloaded_at": self.downloaded_at.isoformat() if self.downloaded_at else now.isoformat(),
            "last_verified_at": self.last_verified_at.isoformat() if self.last_verified_at else now.isoformat(),
            "is_active": self.is_active,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }


@dataclass
class ScrapeRunRecord:
    """A scrape run record for tracking."""
    run_id: str
    run_date: datetime
    run_type: str  # 'scheduled', 'manual', 'backfill'
    supplier_name: str
    datasheets_discovered: int = 0
    datasheets_downloaded: int = 0
    datasheets_skipped: int = 0
    datasheets_failed: int = 0
    errors: List[Dict[str, str]] = field(default_factory=list)
    duration_seconds: float = 0.0
    status: str = "pending"  # 'success', 'partial', 'failed'
    error_message: Optional[str] = None
    
    def to_bq_row(self) -> Dict[str, Any]:
        """Convert to BigQuery row format."""
        return {
            "run_id": self.run_id,
            "run_date": self.run_date.isoformat(),
            "run_type": self.run_type,
            "supplier_name": self.supplier_name,
            "datasheets_discovered": self.datasheets_discovered,
            "datasheets_downloaded": self.datasheets_downloaded,
            "datasheets_skipped": self.datasheets_skipped,
            "datasheets_failed": self.datasheets_failed,
            "errors": json.dumps(self.errors),
            "duration_seconds": self.duration_seconds,
            "status": self.status,
            "error_message": self.error_message,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }


class BigQueryLoader:
    """
    Handles all BigQuery operations for the datasheet scraper.
    """
    
    def __init__(self, config: ScraperConfig):
        self.config = config
        self.client = bigquery.Client(project=config.gcp_project)
        self.dataset_id = f"{config.gcp_project}.{config.bq_dataset}"
        
        # Table references
        self.datasheets_table = f"{self.dataset_id}.{config.bq_datasheets_table}"
        self.scrape_runs_table = f"{self.dataset_id}.{config.bq_scrape_runs_table}"
        self.suppliers_table = f"{self.dataset_id}.{config.bq_suppliers_table}"
    
    def ensure_tables_exist(self) -> bool:
        """
        Check that required tables exist. 
        Returns False if tables are missing (run create_tables.sql first).
        """
        tables = [
            self.config.bq_datasheets_table,
            self.config.bq_scrape_runs_table,
            self.config.bq_suppliers_table,
        ]
        
        for table_name in tables:
            table_ref = f"{self.dataset_id}.{table_name}"
            try:
                self.client.get_table(table_ref)
                logger.info(f"Table exists: {table_ref}")
            except NotFound:
                logger.error(f"Table not found: {table_ref}")
                return False
        
        return True
    
    def insert_datasheets(self, records: List[DatasheetRecord]) -> int:
        """
        Insert datasheet records into BigQuery.
        Uses streaming insert for efficiency.
        
        Returns:
            Number of successfully inserted records
        """
        if not records:
            return 0
        
        rows = [r.to_bq_row() for r in records]
        
        errors = self.client.insert_rows_json(self.datasheets_table, rows)
        
        if errors:
            logger.error(f"BigQuery insert errors: {errors[:5]}")  # Log first 5
            # Count successes (rows without errors)
            return len(records) - len(errors)
        
        logger.info(f"Inserted {len(records)} datasheets into BigQuery")
        return len(records)
    
    def upsert_datasheets(self, records: List[DatasheetRecord]) -> int:
        """
        Upsert datasheet records (update if exists, insert if new).
        Uses MERGE statement for atomic upsert.
        
        Returns:
            Number of affected records
        """
        if not records:
            return 0
        
        # Create a temporary table with the new data
        temp_table = f"{self.dataset_id}._temp_datasheets_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        try:
            # Create temp table with explicit schema to avoid type inference issues
            rows = [r.to_bq_row() for r in records]
            
            schema = [
                bigquery.SchemaField("datasheet_id", "STRING"),
                bigquery.SchemaField("supplier_name", "STRING"),
                bigquery.SchemaField("product_name", "STRING"),
                bigquery.SchemaField("product_family", "STRING"),
                bigquery.SchemaField("title", "STRING"),
                bigquery.SchemaField("url", "STRING"),
                bigquery.SchemaField("filename", "STRING"),
                bigquery.SchemaField("material_category", "STRING"),
                bigquery.SchemaField("material_subcategory", "STRING"),
                bigquery.SchemaField("industries", "STRING", mode="REPEATED"),
                bigquery.SchemaField("extracted_text", "STRING"),
                bigquery.SchemaField("text_preview", "STRING"),
                bigquery.SchemaField("page_count", "INTEGER"),
                bigquery.SchemaField("text_extraction_success", "BOOLEAN"),
                bigquery.SchemaField("structured_properties", "JSON"),
                bigquery.SchemaField("properties_extracted_at", "TIMESTAMP"),
                bigquery.SchemaField("file_size_bytes", "INTEGER"),
                bigquery.SchemaField("file_hash", "STRING"),
                bigquery.SchemaField("content_type", "STRING"),
                bigquery.SchemaField("scrape_run_id", "STRING"),
                bigquery.SchemaField("discovered_at", "TIMESTAMP"),
                bigquery.SchemaField("downloaded_at", "TIMESTAMP"),
                bigquery.SchemaField("last_verified_at", "TIMESTAMP"),
                bigquery.SchemaField("is_active", "BOOLEAN"),
                bigquery.SchemaField("created_at", "TIMESTAMP"),
                bigquery.SchemaField("updated_at", "TIMESTAMP"),
            ]
            
            job_config = bigquery.LoadJobConfig(
                write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
                schema=schema,
            )
            
            # Load to temp table
            load_job = self.client.load_table_from_json(
                rows, temp_table, job_config=job_config
            )
            load_job.result()
            
            # Run MERGE
            merge_query = f"""
            MERGE `{self.datasheets_table}` T
            USING `{temp_table}` S
            ON T.datasheet_id = S.datasheet_id
            WHEN MATCHED THEN
                UPDATE SET
                    supplier_name = S.supplier_name,
                    product_name = S.product_name,
                    product_family = S.product_family,
                    title = S.title,
                    url = S.url,
                    filename = S.filename,
                    material_category = S.material_category,
                    material_subcategory = S.material_subcategory,
                    industries = S.industries,
                    extracted_text = S.extracted_text,
                    text_preview = S.text_preview,
                    page_count = S.page_count,
                    text_extraction_success = S.text_extraction_success,
                    file_size_bytes = S.file_size_bytes,
                    file_hash = S.file_hash,
                    scrape_run_id = S.scrape_run_id,
                    last_verified_at = S.last_verified_at,
                    updated_at = CURRENT_TIMESTAMP()
            WHEN NOT MATCHED THEN
                INSERT ROW
            """
            
            query_job = self.client.query(merge_query)
            result = query_job.result()
            
            affected = query_job.num_dml_affected_rows or len(records)
            logger.info(f"Upserted {affected} datasheets")
            
            return affected
            
        finally:
            # Clean up temp table
            try:
                self.client.delete_table(temp_table, not_found_ok=True)
            except Exception:
                pass
    
    def insert_scrape_run(self, record: ScrapeRunRecord) -> bool:
        """Insert a scrape run record."""
        row = record.to_bq_row()
        
        errors = self.client.insert_rows_json(self.scrape_runs_table, [row])
        
        if errors:
            logger.error(f"Failed to insert scrape run: {errors}")
            return False
        
        logger.info(f"Recorded scrape run: {record.run_id}")
        return True
    
    def get_existing_datasheet_ids(self, supplier_name: str) -> set:
        """Get set of existing datasheet IDs for a supplier."""
        query = f"""
        SELECT datasheet_id
        FROM `{self.datasheets_table}`
        WHERE supplier_name = @supplier_name
          AND is_active = TRUE
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("supplier_name", "STRING", supplier_name)
            ]
        )
        
        result = self.client.query(query, job_config=job_config).result()
        return {row.datasheet_id for row in result}
    
    def get_existing_file_hashes(self, supplier_name: str) -> Dict[str, str]:
        """Get mapping of datasheet_id -> file_hash for change detection."""
        query = f"""
        SELECT datasheet_id, file_hash
        FROM `{self.datasheets_table}`
        WHERE supplier_name = @supplier_name
          AND is_active = TRUE
          AND file_hash IS NOT NULL
          AND file_hash != ''
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("supplier_name", "STRING", supplier_name)
            ]
        )
        
        result = self.client.query(query, job_config=job_config).result()
        return {row.datasheet_id: row.file_hash for row in result}
    
    def mark_datasheets_inactive(self, datasheet_ids: List[str]) -> int:
        """Mark datasheets as inactive (URL no longer valid)."""
        if not datasheet_ids:
            return 0
        
        query = f"""
        UPDATE `{self.datasheets_table}`
        SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP()
        WHERE datasheet_id IN UNNEST(@ids)
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ArrayQueryParameter("ids", "STRING", datasheet_ids)
            ]
        )
        
        job = self.client.query(query, job_config=job_config)
        job.result()
        
        affected = job.num_dml_affected_rows or 0
        logger.info(f"Marked {affected} datasheets as inactive")
        return affected
    
    def get_scrape_stats(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get scrape statistics for the health dashboard."""
        query = f"""
        SELECT 
            supplier_name,
            COUNT(*) as total_runs,
            SUM(datasheets_downloaded) as total_downloaded,
            SUM(datasheets_failed) as total_failed,
            MAX(run_date) as last_run,
            COUNTIF(status = 'success') as successful_runs,
            COUNTIF(status = 'failed') as failed_runs,
            AVG(duration_seconds) as avg_duration_seconds
        FROM `{self.scrape_runs_table}`
        WHERE run_date > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @days DAY)
        GROUP BY supplier_name
        ORDER BY supplier_name
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("days", "INT64", days)
            ]
        )
        
        result = self.client.query(query, job_config=job_config).result()
        return [dict(row) for row in result]
    
    def get_datasheet_counts(self) -> Dict[str, int]:
        """Get datasheet counts by supplier."""
        query = f"""
        SELECT 
            supplier_name,
            COUNT(*) as count
        FROM `{self.datasheets_table}`
        WHERE is_active = TRUE
        GROUP BY supplier_name
        ORDER BY supplier_name
        """
        
        result = self.client.query(query).result()
        return {row.supplier_name: row.count for row in result}
    
    def search_datasheets(
        self,
        query_text: str,
        supplier_name: Optional[str] = None,
        material_category: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Search datasheets by text content.
        Basic CONTAINS_SUBSTR search - for production, consider using
        BigQuery's SEARCH function with search indexes.
        """
        where_clauses = ["is_active = TRUE"]
        params = []
        
        if query_text:
            where_clauses.append("CONTAINS_SUBSTR(extracted_text, @query_text)")
            params.append(bigquery.ScalarQueryParameter("query_text", "STRING", query_text))
        
        if supplier_name:
            where_clauses.append("supplier_name = @supplier_name")
            params.append(bigquery.ScalarQueryParameter("supplier_name", "STRING", supplier_name))
        
        if material_category:
            where_clauses.append("material_category = @material_category")
            params.append(bigquery.ScalarQueryParameter("material_category", "STRING", material_category))
        
        params.append(bigquery.ScalarQueryParameter("limit", "INT64", limit))
        
        query = f"""
        SELECT 
            datasheet_id,
            supplier_name,
            product_name,
            title,
            url,
            material_category,
            industries,
            text_preview,
            file_size_bytes,
            downloaded_at
        FROM `{self.datasheets_table}`
        WHERE {' AND '.join(where_clauses)}
        LIMIT @limit
        """
        
        job_config = bigquery.QueryJobConfig(query_parameters=params)
        result = self.client.query(query, job_config=job_config).result()
        
        return [dict(row) for row in result]
