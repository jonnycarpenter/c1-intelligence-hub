"""
ImportYeti Pipeline Orchestrator
================================

Main orchestration for the ImportYeti data collection pipeline.
This is designed to be run independently via Cloud Scheduler (bi-weekly).

Usage:
    # Run via CLI entry point
    python -m app.ingestion.importyeti.pipeline --full
    
    # Or from code
    pipeline = ImportYetiPipeline()
    await pipeline.run()
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

from .client import ImportYetiClient
from .collector import ImportYetiCollector, CollectionResult
from .bigquery_store import ImportYetiBigQueryStore
from .config import CREDIT_BUDGET, get_tracked_suppliers_from_csv, get_tracked_oems_from_csv

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Result of a pipeline run."""
    run_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    success: bool = False
    
    # Collection stats
    suppliers_collected: int = 0
    companies_collected: int = 0
    product_searches: int = 0
    relationships_stored: int = 0
    change_events_detected: int = 0
    freight_rates_collected: int = 0
    
    # Credit tracking
    credits_used: int = 0
    credits_remaining: Optional[int] = None
    
    # Errors
    errors: List[str] = field(default_factory=list)
    
    @property
    def duration_seconds(self) -> Optional[float]:
        if self.completed_at and self.started_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "success": self.success,
            "duration_seconds": self.duration_seconds,
            "suppliers_collected": self.suppliers_collected,
            "companies_collected": self.companies_collected,
            "product_searches": self.product_searches,
            "relationships_stored": self.relationships_stored,
            "change_events_detected": self.change_events_detected,
            "credits_used": self.credits_used,
            "credits_remaining": self.credits_remaining,
            "errors": self.errors,
        }


class ImportYetiPipeline:
    """
    Main orchestrator for ImportYeti data collection.
    
    Pipeline phases:
    1. Check API availability and credits
    2. Collect supplier data (tracked suppliers)
    3. Collect company data (OEMs)
    4. Product market analysis
    5. Change detection
    6. Store to BigQuery
    7. Generate summary
    
    Example:
        pipeline = ImportYetiPipeline()
        result = await pipeline.run()
        
        # Or with options
        result = await pipeline.run(
            suppliers_only=True,
            max_credits=500
        )
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        project_id: Optional[str] = None,
        dataset_id: str = "c1_intelligence",
    ):
        self.api_key = api_key
        self.project_id = project_id
        self.dataset_id = dataset_id
        
        self._client: Optional[ImportYetiClient] = None
        self._store: Optional[ImportYetiBigQueryStore] = None
        self._collector: Optional[ImportYetiCollector] = None
    
    async def _initialize(self):
        """Initialize components."""
        # Initialize client
        self._client = ImportYetiClient(api_key=self.api_key)
        
        # Initialize BigQuery store
        self._store = ImportYetiBigQueryStore(
            project_id=self.project_id,
            dataset_id=self.dataset_id,
        )
        await self._store.initialize()
        
        # Initialize collector
        self._collector = ImportYetiCollector(client=self._client)
        
        logger.info("ImportYeti pipeline initialized")
    
    async def run(
        self,
        suppliers_only: bool = False,
        companies_only: bool = False,
        products_only: bool = False,
        max_credits: Optional[int] = None,
        dry_run: bool = False,
    ) -> PipelineResult:
        """
        Run the ImportYeti collection pipeline.
        
        Args:
            suppliers_only: Only collect supplier data
            companies_only: Only collect company (OEM) data
            products_only: Only run product market searches
            max_credits: Maximum credits to use (default: CREDIT_BUDGET)
            dry_run: Log what would be done without making API calls
            
        Returns:
            PipelineResult with collection statistics
        """
        run_id = f"iy_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        result = PipelineResult(
            run_id=run_id,
            started_at=datetime.now(timezone.utc),
        )
        
        try:
            # Initialize
            await self._initialize()
            
            # Check API availability
            logger.info("Checking ImportYeti API status...")
            async with self._client:
                db_status = await self._client.get_database_updated()
                if db_status:
                    logger.info(f"ImportYeti database last updated: {db_status}")
                
                # Determine what to collect
                collect_suppliers = not companies_only and not products_only
                collect_companies = not suppliers_only and not products_only
                collect_products = not suppliers_only and not companies_only
                
                if dry_run:
                    result.success = True
                    result.completed_at = datetime.now(timezone.utc)
                    logger.info(f"DRY RUN: Would collect suppliers={collect_suppliers}, "
                               f"companies={collect_companies}, products={collect_products}")
                    return result
                
                # Run full collection
                max_creds = max_credits or CREDIT_BUDGET
                collection_result = await self._collector.run_full_collection(
                    max_credits=max_creds
                )
                
                # Update result stats from collection
                result.suppliers_collected = len(collection_result.suppliers)
                result.companies_collected = len(collection_result.companies)
                result.credits_used = collection_result.stats.credits_used
                result.change_events_detected = len(collection_result.change_events)
                
                # Store to BigQuery
                logger.info("Storing results to BigQuery...")
                
                # Store suppliers
                if collection_result.suppliers:
                    await self._store.store_suppliers(collection_result.suppliers)
                
                # Store companies
                if collection_result.companies:
                    await self._store.store_companies(collection_result.companies)
                
                # Store supplier-customer relationships
                if collection_result.supplier_customers:
                    rows_stored = await self._store.store_supplier_customers(
                        collection_result.supplier_customers
                    )
                    result.relationships_stored += rows_stored
                
                # Store company-supplier relationships
                if collection_result.company_suppliers:
                    rows_stored = await self._store.store_company_suppliers(
                        collection_result.company_suppliers
                    )
                    result.relationships_stored += rows_stored
                
                # Store change events
                if collection_result.change_events:
                    await self._store.store_change_events(collection_result.change_events)
                
                # Get final credit count
                result.credits_remaining = await self._client.get_credits_remaining()
                
                result.success = True
                logger.info(f"Pipeline completed successfully. Run ID: {run_id}")
                
        except Exception as e:
            logger.exception(f"Pipeline failed: {e}")
            result.errors.append(str(e))
            result.success = False
        
        finally:
            result.completed_at = datetime.now(timezone.utc)
            
            # Log summary
            self._log_summary(result)
        
        return result
    
    async def run_supplier_collection(
        self,
        supplier_names: Optional[List[str]] = None,
        max_credits: Optional[int] = None,
    ) -> PipelineResult:
        """
        Run collection for specific suppliers only.
        
        Args:
            supplier_names: List of supplier names (or use tracked from CSV)
            max_credits: Credit limit
        """
        run_id = f"iy_sup_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        result = PipelineResult(
            run_id=run_id,
            started_at=datetime.now(timezone.utc),
        )
        
        try:
            await self._initialize()
            
            suppliers = supplier_names or get_tracked_suppliers_from_csv()
            logger.info(f"Collecting data for {len(suppliers)} suppliers")
            
            async with self._client:
                all_supplier_profiles = []
                all_relationships = []
                
                for supplier_name in suppliers:
                    profile, relationships = await self._collector._fetch_supplier(supplier_name)
                    if profile:
                        all_supplier_profiles.append(profile)
                        all_relationships.extend(relationships)
                        result.suppliers_collected += 1
                    
                    # Check credit limit
                    if max_credits and self._client.credits_used >= max_credits:
                        logger.warning(f"Credit limit reached: {self._client.credits_used}")
                        break
                
                # Store results
                if all_supplier_profiles:
                    await self._store.store_suppliers(all_supplier_profiles)
                
                if all_relationships:
                    rows_stored = await self._store.store_supplier_customers(all_relationships)
                    result.relationships_stored = rows_stored
                
                result.credits_used = self._client.credits_used
                result.credits_remaining = await self._client.get_credits_remaining()
                result.success = True
                
        except Exception as e:
            logger.exception(f"Supplier collection failed: {e}")
            result.errors.append(str(e))
        
        finally:
            result.completed_at = datetime.now(timezone.utc)
            self._log_summary(result)
        
        return result
    
    async def run_company_collection(
        self,
        company_names: Optional[List[str]] = None,
        max_credits: Optional[int] = None,
    ) -> PipelineResult:
        """
        Run collection for specific companies (OEMs) only.
        """
        run_id = f"iy_oem_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        result = PipelineResult(
            run_id=run_id,
            started_at=datetime.now(timezone.utc),
        )
        
        try:
            await self._initialize()
            
            companies = company_names or get_tracked_oems_from_csv()
            logger.info(f"Collecting data for {len(companies)} companies/OEMs")
            
            async with self._client:
                all_company_profiles = []
                all_relationships = []
                
                for company_name in companies:
                    profile, relationships = await self._collector._fetch_company(company_name)
                    if profile:
                        all_company_profiles.append(profile)
                        all_relationships.extend(relationships)
                        result.companies_collected += 1
                    
                    if max_credits and self._client.credits_used >= max_credits:
                        logger.warning(f"Credit limit reached: {self._client.credits_used}")
                        break
                
                # Store results
                if all_company_profiles:
                    await self._store.store_companies(all_company_profiles)
                
                if all_relationships:
                    rows_stored = await self._store.store_company_suppliers(all_relationships)
                    result.relationships_stored = rows_stored
                
                result.credits_used = self._client.credits_used
                result.credits_remaining = await self._client.get_credits_remaining()
                result.success = True
                
        except Exception as e:
            logger.exception(f"Company collection failed: {e}")
            result.errors.append(str(e))
        
        finally:
            result.completed_at = datetime.now(timezone.utc)
            self._log_summary(result)
        
        return result
    
    async def test_connection(self) -> Dict[str, Any]:
        """
        Test API connection and return status.
        
        Returns:
            Dict with connection status and API info
        """
        try:
            client = ImportYetiClient(api_key=self.api_key)
            async with client:
                db_updated = await client.get_database_updated()
                credits_remaining = await client.get_credits_remaining()
                
                return {
                    "success": True,
                    "database_updated": db_updated,
                    "credits_remaining": credits_remaining,
                    "credits_budget": CREDIT_BUDGET,
                    "tested_at": datetime.now(timezone.utc).isoformat(),
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "tested_at": datetime.now(timezone.utc).isoformat(),
            }
    
    def _log_summary(self, result: PipelineResult):
        """Log pipeline run summary."""
        logger.info("=" * 60)
        logger.info(f"ImportYeti Pipeline Summary - {result.run_id}")
        logger.info("=" * 60)
        logger.info(f"Status: {'SUCCESS' if result.success else 'FAILED'}")
        logger.info(f"Duration: {result.duration_seconds:.1f}s" if result.duration_seconds else "Duration: N/A")
        logger.info(f"Suppliers Collected: {result.suppliers_collected}")
        logger.info(f"Companies Collected: {result.companies_collected}")
        logger.info(f"Relationships Stored: {result.relationships_stored}")
        logger.info(f"Change Events: {result.change_events_detected}")
        logger.info(f"Credits Used: {result.credits_used}")
        logger.info(f"Credits Remaining: {result.credits_remaining}")
        if result.errors:
            logger.error(f"Errors: {result.errors}")
        logger.info("=" * 60)


# =============================================================================
# CLI Entry Point
# =============================================================================

async def main():
    """CLI entry point for ImportYeti pipeline."""
    import argparse
    from dotenv import load_dotenv
    
    # Load environment variables
    load_dotenv()
    
    parser = argparse.ArgumentParser(
        description="ImportYeti Trade Intelligence Pipeline"
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Run full collection (suppliers, companies, products)"
    )
    parser.add_argument(
        "--suppliers",
        action="store_true",
        help="Collect supplier data only"
    )
    parser.add_argument(
        "--companies",
        action="store_true",
        help="Collect company/OEM data only"
    )
    parser.add_argument(
        "--products",
        action="store_true",
        help="Run product market searches only"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Test API connection only"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log what would be done without making API calls"
    )
    parser.add_argument(
        "--max-credits",
        type=int,
        default=None,
        help=f"Maximum credits to use (default: {CREDIT_BUDGET})"
    )
    parser.add_argument(
        "--supplier-name",
        type=str,
        nargs="+",
        help="Specific supplier names to collect"
    )
    parser.add_argument(
        "--company-name",
        type=str,
        nargs="+",
        help="Specific company names to collect"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose logging"
    )
    
    args = parser.parse_args()
    
    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    pipeline = ImportYetiPipeline()
    
    if args.test:
        print("Testing ImportYeti API connection...")
        status = await pipeline.test_connection()
        print(f"\nConnection Status:")
        for key, value in status.items():
            print(f"  {key}: {value}")
        return
    
    if args.suppliers or args.supplier_name:
        result = await pipeline.run_supplier_collection(
            supplier_names=args.supplier_name,
            max_credits=args.max_credits,
        )
    elif args.companies or args.company_name:
        result = await pipeline.run_company_collection(
            company_names=args.company_name,
            max_credits=args.max_credits,
        )
    elif args.full or args.dry_run:
        result = await pipeline.run(
            max_credits=args.max_credits,
            dry_run=args.dry_run,
        )
    else:
        # Default to full run
        result = await pipeline.run(max_credits=args.max_credits)
    
    # Print result summary
    print("\n" + "=" * 60)
    print("PIPELINE RESULT")
    print("=" * 60)
    for key, value in result.to_dict().items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    asyncio.run(main())
