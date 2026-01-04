"""
Datasheet Scraper Health Check
==============================

Generates a health report for the datasheet scraping system.
Similar to the ingestion pipeline health check.

Usage:
    python -m app.scrapers.health_check
    python -m app.scrapers.health_check --days 7
    python -m app.scrapers.health_check --verbose
"""

import os
import sys
import argparse
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional

from google.cloud import bigquery
from google.api_core.exceptions import NotFound

from app.scrapers.config import ScraperConfig, SUPPLIERS, get_enabled_suppliers

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DatasheetHealthChecker:
    """Generates health reports for the datasheet scraper system."""
    
    def __init__(self, config: ScraperConfig):
        self.config = config
        self.client = bigquery.Client(project=config.gcp_project)
        self.dataset_id = f"{config.gcp_project}.{config.bq_dataset}"
    
    def check_tables_exist(self) -> Dict[str, bool]:
        """Check if required tables exist."""
        tables = {
            "datasheets": f"{self.dataset_id}.{self.config.bq_datasheets_table}",
            "scrape_runs": f"{self.dataset_id}.{self.config.bq_scrape_runs_table}",
            "suppliers": f"{self.dataset_id}.{self.config.bq_suppliers_table}",
        }
        
        results = {}
        for name, table_ref in tables.items():
            try:
                self.client.get_table(table_ref)
                results[name] = True
            except NotFound:
                results[name] = False
        
        return results
    
    def get_datasheet_counts(self) -> Dict[str, Dict[str, int]]:
        """Get datasheet counts by supplier and category."""
        query = f"""
        SELECT 
            supplier_name,
            material_category,
            COUNT(*) as count,
            COUNTIF(text_extraction_success) as with_text,
            SUM(file_size_bytes) / 1024 / 1024 as total_size_mb
        FROM `{self.dataset_id}.{self.config.bq_datasheets_table}`
        WHERE is_active = TRUE
        GROUP BY supplier_name, material_category
        ORDER BY supplier_name, count DESC
        """
        
        try:
            result = self.client.query(query).result()
            
            counts = {}
            for row in result:
                supplier = row.supplier_name
                if supplier not in counts:
                    counts[supplier] = {"total": 0, "with_text": 0, "size_mb": 0, "categories": {}}
                
                counts[supplier]["total"] += row.count
                counts[supplier]["with_text"] += row.with_text
                counts[supplier]["size_mb"] += row.total_size_mb or 0
                counts[supplier]["categories"][row.material_category] = row.count
            
            return counts
        except Exception as e:
            logger.error(f"Failed to get datasheet counts: {e}")
            return {}
    
    def get_recent_scrape_runs(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get recent scrape run statistics."""
        query = f"""
        SELECT 
            supplier_name,
            run_date,
            run_type,
            status,
            datasheets_discovered,
            datasheets_downloaded,
            datasheets_skipped,
            datasheets_failed,
            duration_seconds,
            error_message
        FROM `{self.dataset_id}.{self.config.bq_scrape_runs_table}`
        WHERE run_date > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @days DAY)
        ORDER BY run_date DESC
        LIMIT 100
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("days", "INT64", days)
            ]
        )
        
        try:
            result = self.client.query(query, job_config=job_config).result()
            return [dict(row) for row in result]
        except Exception as e:
            logger.error(f"Failed to get scrape runs: {e}")
            return []
    
    def get_supplier_health(self, days: int = 30) -> Dict[str, Dict[str, Any]]:
        """Get health metrics per supplier."""
        query = f"""
        SELECT 
            supplier_name,
            COUNT(*) as total_runs,
            COUNTIF(status = 'success') as successful_runs,
            COUNTIF(status = 'partial') as partial_runs,
            COUNTIF(status = 'failed') as failed_runs,
            MAX(run_date) as last_run,
            SUM(datasheets_downloaded) as total_downloaded,
            SUM(datasheets_failed) as total_failed,
            AVG(duration_seconds) as avg_duration
        FROM `{self.dataset_id}.{self.config.bq_scrape_runs_table}`
        WHERE run_date > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @days DAY)
        GROUP BY supplier_name
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("days", "INT64", days)
            ]
        )
        
        try:
            result = self.client.query(query, job_config=job_config).result()
            return {row.supplier_name: dict(row) for row in result}
        except Exception as e:
            logger.error(f"Failed to get supplier health: {e}")
            return {}
    
    def get_recent_errors(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get recent errors from scrape runs."""
        query = f"""
        SELECT 
            supplier_name,
            run_date,
            error_message,
            JSON_EXTRACT_ARRAY(errors) as error_details
        FROM `{self.dataset_id}.{self.config.bq_scrape_runs_table}`
        WHERE run_date > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @days DAY)
          AND (error_message IS NOT NULL OR JSON_ARRAY_LENGTH(errors) > 0)
        ORDER BY run_date DESC
        LIMIT 20
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("days", "INT64", days)
            ]
        )
        
        try:
            result = self.client.query(query, job_config=job_config).result()
            return [dict(row) for row in result]
        except Exception as e:
            logger.error(f"Failed to get recent errors: {e}")
            return []
    
    def generate_report(self, days: int = 30, verbose: bool = False) -> str:
        """Generate a comprehensive health report."""
        lines = []
        now = datetime.now(timezone.utc)
        
        lines.append("")
        lines.append("=" * 80)
        lines.append("DATASHEET SCRAPER - HEALTH CHECK REPORT")
        lines.append("=" * 80)
        lines.append(f"Generated: {now.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        lines.append(f"Reporting period: {days} days")
        lines.append("")
        
        # Check tables
        lines.append("-" * 80)
        lines.append("BIGQUERY TABLES")
        lines.append("-" * 80)
        tables = self.check_tables_exist()
        all_tables_exist = all(tables.values())
        
        for table_name, exists in tables.items():
            status = "✓ EXISTS" if exists else "✗ MISSING"
            lines.append(f"  {table_name:20} {status}")
        
        if not all_tables_exist:
            lines.append("")
            lines.append("  ⚠ WARNING: Some tables are missing!")
            lines.append("  Run create_tables.sql to create them.")
            lines.append("")
        
        # Datasheet inventory
        lines.append("")
        lines.append("-" * 80)
        lines.append("DATASHEET INVENTORY")
        lines.append("-" * 80)
        
        if all_tables_exist:
            counts = self.get_datasheet_counts()
            
            if counts:
                total_datasheets = sum(s["total"] for s in counts.values())
                total_size = sum(s["size_mb"] for s in counts.values())
                
                lines.append(f"  Total datasheets: {total_datasheets:,}")
                lines.append(f"  Total size: {total_size:.1f} MB")
                lines.append("")
                
                for supplier, data in sorted(counts.items()):
                    lines.append(f"  {supplier}")
                    lines.append(f"    Total: {data['total']:,}  |  With text: {data['with_text']:,}  |  Size: {data['size_mb']:.1f} MB")
                    
                    if verbose and data['categories']:
                        for cat, count in sorted(data['categories'].items(), key=lambda x: -x[1]):
                            lines.append(f"      - {cat}: {count}")
            else:
                lines.append("  No datasheets found in database.")
        else:
            lines.append("  Cannot query - tables missing")
        
        # Supplier health
        lines.append("")
        lines.append("-" * 80)
        lines.append("SUPPLIER HEALTH (Last {} days)".format(days))
        lines.append("-" * 80)
        
        if all_tables_exist:
            health = self.get_supplier_health(days)
            
            # Include all configured suppliers, even if no runs
            for supplier_id, supplier_config in SUPPLIERS.items():
                supplier_name = supplier_config.supplier_name
                
                if supplier_name in health:
                    h = health[supplier_name]
                    success_rate = (h['successful_runs'] / h['total_runs'] * 100) if h['total_runs'] > 0 else 0
                    
                    # Determine health status
                    if success_rate >= 90:
                        status = "✓ HEALTHY"
                    elif success_rate >= 50:
                        status = "⚠ DEGRADED"
                    else:
                        status = "✗ UNHEALTHY"
                    
                    last_run_str = h['last_run'].strftime('%Y-%m-%d %H:%M') if h['last_run'] else "Never"
                    
                    lines.append(f"  {supplier_name:20} {status}")
                    lines.append(f"    Last run: {last_run_str}")
                    lines.append(f"    Runs: {h['total_runs']} (✓{h['successful_runs']} ⚠{h['partial_runs']} ✗{h['failed_runs']})")
                    lines.append(f"    Downloaded: {h['total_downloaded']:,}  |  Failed: {h['total_failed']:,}")
                    lines.append(f"    Avg duration: {h['avg_duration']:.1f}s")
                else:
                    enabled = "enabled" if supplier_config.is_enabled else "disabled"
                    lines.append(f"  {supplier_name:20} ○ NO RUNS ({enabled})")
                
                lines.append("")
        else:
            lines.append("  Cannot query - tables missing")
        
        # Recent errors
        if verbose:
            lines.append("-" * 80)
            lines.append("RECENT ERRORS (Last 7 days)")
            lines.append("-" * 80)
            
            if all_tables_exist:
                errors = self.get_recent_errors(7)
                
                if errors:
                    for err in errors[:10]:
                        run_date = err['run_date'].strftime('%Y-%m-%d %H:%M') if err['run_date'] else "?"
                        lines.append(f"  [{run_date}] {err['supplier_name']}")
                        if err['error_message']:
                            lines.append(f"    {err['error_message'][:70]}")
                else:
                    lines.append("  No recent errors! 🎉")
            else:
                lines.append("  Cannot query - tables missing")
        
        # Configuration
        lines.append("")
        lines.append("-" * 80)
        lines.append("CONFIGURATION")
        lines.append("-" * 80)
        lines.append(f"  GCP Project: {self.config.gcp_project}")
        lines.append(f"  BQ Dataset: {self.config.bq_dataset}")
        lines.append(f"  Download dir: {self.config.download_dir}")
        lines.append(f"  Max concurrent: {self.config.max_concurrent_downloads}")
        lines.append(f"  Request delay: {self.config.request_delay}s")
        
        lines.append("")
        lines.append("=" * 80)
        lines.append("")
        
        return "\n".join(lines)


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Datasheet Scraper Health Check",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument("--days", type=int, default=30,
                        help="Number of days to look back (default: 30)")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Include detailed error information")
    
    args = parser.parse_args()
    
    config = ScraperConfig()
    checker = DatasheetHealthChecker(config)
    
    report = checker.generate_report(days=args.days, verbose=args.verbose)
    print(report)


if __name__ == "__main__":
    main()
