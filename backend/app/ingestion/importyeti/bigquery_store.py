"""
ImportYeti BigQuery Storage
===========================

Handles storing ImportYeti trade data in BigQuery tables.
Tables are created in the c1_intelligence dataset.
"""

import os
import json
import logging
from datetime import datetime, date
from typing import List, Dict, Any, Optional
from dataclasses import asdict

from .models import (
    Snapshot,
    SupplierProfile,
    CompanyProfile,
    SupplierCustomerRelationship,
    CompanySupplierRelationship,
    ProductMarketResult,
    ShipmentTrend,
    ConcentrationMetrics,
    CompetitorOverlap,
    ChangeEvent,
)

logger = logging.getLogger(__name__)


class ImportYetiBigQueryStore:
    """
    BigQuery storage for ImportYeti data.
    
    Usage:
        store = ImportYetiBigQueryStore()
        await store.initialize()
        
        # Store collection results
        await store.store_snapshots(snapshots)
        await store.store_supplier_customers(relationships)
    """
    
    def __init__(
        self,
        project_id: Optional[str] = None,
        dataset_id: str = "c1_intelligence",
    ):
        self.project_id = project_id or os.getenv("GCP_PROJECT_ID")
        if not self.project_id:
             # Try to get from gcp_config if available (avoids circular import issues)
             try:
                 from app.db.gcp_storage import gcp_config
                 self.project_id = gcp_config.project_id
             except (ImportError, AttributeError):
                 pass
                 
        self.dataset_id = dataset_id
        self._client = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize BigQuery client and ensure tables exist."""
        if self._initialized:
            return
        
        try:
            from google.cloud import bigquery
            self._client = bigquery.Client(project=self.project_id)
            
            # Ensure tables exist
            await self._ensure_tables()
            
            self._initialized = True
            logger.info(f"ImportYeti BigQuery store initialized: {self.project_id}.{self.dataset_id}")
            
        except Exception as e:
            logger.error(f"Failed to initialize BigQuery store: {e}")
            raise
    
    def _get_table_id(self, table_name: str) -> str:
        """Get full table ID."""
        return f"{self.project_id}.{self.dataset_id}.{table_name}"
    
    async def _ensure_tables(self):
        """Ensure all ImportYeti tables exist."""
        from google.cloud import bigquery
        
        tables = {
            "iy_snapshots": self._get_snapshots_schema(),
            "iy_suppliers": self._get_suppliers_schema(),
            "iy_companies": self._get_companies_schema(),
            "iy_supplier_customers": self._get_supplier_customers_schema(),
            "iy_company_suppliers": self._get_company_suppliers_schema(),
            "iy_product_market": self._get_product_market_schema(),
            "iy_shipment_trends": self._get_shipment_trends_schema(),
            "iy_concentration_metrics": self._get_concentration_schema(),
            "iy_competitor_overlap": self._get_competitor_overlap_schema(),
            "iy_change_events": self._get_change_events_schema(),
        }
        
        for table_name, schema in tables.items():
            table_id = self._get_table_id(table_name)
            try:
                self._client.get_table(table_id)
                logger.debug(f"Table {table_name} exists")
            except Exception:
                # Create table
                table = bigquery.Table(table_id, schema=schema)
                
                # Add partitioning for date-based tables
                if table_name in ["iy_snapshots", "iy_supplier_customers", "iy_company_suppliers", 
                                  "iy_product_market", "iy_shipment_trends", "iy_concentration_metrics",
                                  "iy_competitor_overlap", "iy_change_events"]:
                    if "snapshot_date" in [f.name for f in schema]:
                        table.time_partitioning = bigquery.TimePartitioning(
                            type_=bigquery.TimePartitioningType.DAY,
                            field="snapshot_date"
                        )
                    elif "period_date" in [f.name for f in schema]:
                        table.time_partitioning = bigquery.TimePartitioning(
                            type_=bigquery.TimePartitioningType.DAY,
                            field="period_date"
                        )
                    elif "detected_date" in [f.name for f in schema]:
                        table.time_partitioning = bigquery.TimePartitioning(
                            type_=bigquery.TimePartitioningType.DAY,
                            field="detected_date"
                        )
                
                self._client.create_table(table)
                logger.info(f"Created table {table_name}")
    
    # =========================================================================
    # Table Schemas
    # =========================================================================
    
    def _get_snapshots_schema(self):
        from google.cloud import bigquery
        return [
            bigquery.SchemaField("snapshot_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("snapshot_date", "TIMESTAMP", mode="REQUIRED"),
            bigquery.SchemaField("endpoint_type", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("entity_key", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("entity_name", "STRING"),
            bigquery.SchemaField("request_cost", "INTEGER"),
            bigquery.SchemaField("credits_remaining", "INTEGER"),
            bigquery.SchemaField("execution_time_ms", "INTEGER"),
            bigquery.SchemaField("raw_response", "STRING"),  # JSON as string
            bigquery.SchemaField("created_at", "TIMESTAMP"),
        ]
    
    def _get_suppliers_schema(self):
        from google.cloud import bigquery
        return [
            bigquery.SchemaField("supplier_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("supplier_name", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("also_known_names", "STRING", mode="REPEATED"),
            bigquery.SchemaField("country", "STRING"),
            bigquery.SchemaField("country_code", "STRING"),
            bigquery.SchemaField("address", "STRING"),
            bigquery.SchemaField("website", "STRING"),
            bigquery.SchemaField("phone_number", "STRING"),
            bigquery.SchemaField("total_shipments", "INTEGER"),
            bigquery.SchemaField("total_us_customers", "INTEGER"),
            bigquery.SchemaField("primary_hs_codes", "STRING"),  # JSON array
            bigquery.SchemaField("is_c1_supplier", "BOOLEAN"),
            bigquery.SchemaField("is_tracked_competitor", "BOOLEAN"),
            bigquery.SchemaField("supplier_tier", "STRING"),
            bigquery.SchemaField("first_seen_date", "DATE"),
            bigquery.SchemaField("last_updated", "TIMESTAMP"),
        ]
    
    def _get_companies_schema(self):
        from google.cloud import bigquery
        return [
            bigquery.SchemaField("company_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("company_name", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("also_known_names", "STRING", mode="REPEATED"),
            bigquery.SchemaField("country", "STRING"),
            bigquery.SchemaField("country_code", "STRING"),
            bigquery.SchemaField("address", "STRING"),
            bigquery.SchemaField("website", "STRING"),
            bigquery.SchemaField("phone_number", "STRING"),
            bigquery.SchemaField("total_shipments", "INTEGER"),
            bigquery.SchemaField("total_suppliers", "INTEGER"),
            bigquery.SchemaField("primary_hs_codes", "STRING"),  # JSON array
            bigquery.SchemaField("company_type", "STRING"),
            bigquery.SchemaField("industries", "STRING", mode="REPEATED"),
            bigquery.SchemaField("is_c1_customer", "BOOLEAN"),
            bigquery.SchemaField("is_prospect", "BOOLEAN"),
            bigquery.SchemaField("first_seen_date", "DATE"),
            bigquery.SchemaField("last_updated", "TIMESTAMP"),
        ]
    
    def _get_supplier_customers_schema(self):
        from google.cloud import bigquery
        return [
            bigquery.SchemaField("relationship_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("snapshot_date", "DATE", mode="REQUIRED"),
            bigquery.SchemaField("supplier_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("supplier_name", "STRING"),
            bigquery.SchemaField("supplier_country", "STRING"),
            bigquery.SchemaField("customer_name", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("customer_name_normalized", "STRING"),
            bigquery.SchemaField("customer_address", "STRING"),
            bigquery.SchemaField("customer_country", "STRING"),
            bigquery.SchemaField("customer_key", "STRING"),
            bigquery.SchemaField("total_shipments_to_customer", "INTEGER"),
            bigquery.SchemaField("shipments_pct_of_supplier", "FLOAT64"),
            bigquery.SchemaField("shipments_pct_of_customer", "FLOAT64"),
            bigquery.SchemaField("shipments_12m", "INTEGER"),
            bigquery.SchemaField("total_weight_kg", "FLOAT64"),
            bigquery.SchemaField("total_teu", "FLOAT64"),
            bigquery.SchemaField("hs_code_chapters", "STRING"),  # JSON array
            bigquery.SchemaField("product_descriptions", "STRING", mode="REPEATED"),
            bigquery.SchemaField("customer_top_suppliers", "STRING"),  # JSON array
            bigquery.SchemaField("relationship_time_series", "STRING"),  # JSON array
            bigquery.SchemaField("first_shipment_date", "DATE"),
            bigquery.SchemaField("most_recent_shipment_date", "DATE"),
            bigquery.SchemaField("business_length", "STRING"),
            bigquery.SchemaField("is_new_customer", "BOOLEAN"),
            bigquery.SchemaField("first_seen_date", "DATE"),
            bigquery.SchemaField("last_seen_date", "DATE"),
            bigquery.SchemaField("is_active", "BOOLEAN"),
            bigquery.SchemaField("created_at", "TIMESTAMP"),
        ]
    
    def _get_company_suppliers_schema(self):
        from google.cloud import bigquery
        return [
            bigquery.SchemaField("relationship_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("snapshot_date", "DATE", mode="REQUIRED"),
            bigquery.SchemaField("company_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("company_name", "STRING"),
            bigquery.SchemaField("supplier_name", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("supplier_name_normalized", "STRING"),
            bigquery.SchemaField("supplier_address", "STRING"),
            bigquery.SchemaField("supplier_country", "STRING"),
            bigquery.SchemaField("supplier_key", "STRING"),
            bigquery.SchemaField("total_shipments_from_supplier", "INTEGER"),
            bigquery.SchemaField("shipments_pct_of_company", "FLOAT64"),
            bigquery.SchemaField("shipments_pct_of_supplier", "FLOAT64"),
            bigquery.SchemaField("shipments_12m", "INTEGER"),
            bigquery.SchemaField("total_weight_kg", "FLOAT64"),
            bigquery.SchemaField("total_teu", "FLOAT64"),
            bigquery.SchemaField("hs_code_chapters", "STRING"),  # JSON
            bigquery.SchemaField("product_descriptions", "STRING", mode="REPEATED"),
            bigquery.SchemaField("supplier_top_companies", "STRING"),  # JSON
            bigquery.SchemaField("relationship_time_series", "STRING"),  # JSON
            bigquery.SchemaField("first_shipment_date", "DATE"),
            bigquery.SchemaField("most_recent_shipment_date", "DATE"),
            bigquery.SchemaField("business_length", "STRING"),
            bigquery.SchemaField("first_seen_date", "DATE"),
            bigquery.SchemaField("last_seen_date", "DATE"),
            bigquery.SchemaField("is_active", "BOOLEAN"),
            bigquery.SchemaField("created_at", "TIMESTAMP"),
        ]
    
    def _get_product_market_schema(self):
        from google.cloud import bigquery
        return [
            bigquery.SchemaField("record_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("snapshot_date", "DATE", mode="REQUIRED"),
            bigquery.SchemaField("product_search_term", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("result_type", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("entity_name", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("entity_link", "STRING"),
            bigquery.SchemaField("entity_country", "STRING"),
            bigquery.SchemaField("entity_country_code", "STRING"),
            bigquery.SchemaField("entity_address", "STRING"),
            bigquery.SchemaField("matching_shipments", "INTEGER"),
            bigquery.SchemaField("specialization_pct", "FLOAT64"),
            bigquery.SchemaField("total_shipments", "INTEGER"),
            bigquery.SchemaField("experience_years", "FLOAT64"),
            bigquery.SchemaField("relevance_score", "FLOAT64"),
            bigquery.SchemaField("total_weight_kg", "FLOAT64"),
            bigquery.SchemaField("related_entities", "STRING", mode="REPEATED"),
            bigquery.SchemaField("total_related_count", "INTEGER"),
            bigquery.SchemaField("product_descriptions", "STRING", mode="REPEATED"),
            bigquery.SchemaField("created_at", "TIMESTAMP"),
        ]
    
    def _get_shipment_trends_schema(self):
        from google.cloud import bigquery
        return [
            bigquery.SchemaField("trend_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("period_date", "DATE", mode="REQUIRED"),
            bigquery.SchemaField("period_type", "STRING"),
            bigquery.SchemaField("dimension_type", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("dimension_key", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("dimension_name", "STRING"),
            bigquery.SchemaField("dimension_key_2", "STRING"),
            bigquery.SchemaField("dimension_name_2", "STRING"),
            bigquery.SchemaField("shipment_count", "INTEGER"),
            bigquery.SchemaField("weight_kg", "FLOAT64"),
            bigquery.SchemaField("teu", "FLOAT64"),
            bigquery.SchemaField("unique_counterparties", "INTEGER"),
            bigquery.SchemaField("shipment_count_prev", "INTEGER"),
            bigquery.SchemaField("shipment_count_change", "INTEGER"),
            bigquery.SchemaField("shipment_count_change_pct", "FLOAT64"),
            bigquery.SchemaField("created_at", "TIMESTAMP"),
        ]
    
    def _get_concentration_schema(self):
        from google.cloud import bigquery
        return [
            bigquery.SchemaField("metric_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("snapshot_date", "DATE", mode="REQUIRED"),
            bigquery.SchemaField("entity_type", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("entity_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("entity_name", "STRING"),
            bigquery.SchemaField("total_counterparties", "INTEGER"),
            bigquery.SchemaField("top_counterparty_name", "STRING"),
            bigquery.SchemaField("top_counterparty_pct", "FLOAT64"),
            bigquery.SchemaField("top_3_counterparty_pct", "FLOAT64"),
            bigquery.SchemaField("top_5_counterparty_pct", "FLOAT64"),
            bigquery.SchemaField("top_10_counterparty_pct", "FLOAT64"),
            bigquery.SchemaField("hhi_index", "FLOAT64"),
            bigquery.SchemaField("total_countries", "INTEGER"),
            bigquery.SchemaField("top_country", "STRING"),
            bigquery.SchemaField("top_country_pct", "FLOAT64"),
            bigquery.SchemaField("china_pct", "FLOAT64"),
            bigquery.SchemaField("total_hs_chapters", "INTEGER"),
            bigquery.SchemaField("top_hs_chapter", "STRING"),
            bigquery.SchemaField("top_hs_chapter_name", "STRING"),
            bigquery.SchemaField("top_hs_chapter_pct", "FLOAT64"),
            bigquery.SchemaField("created_at", "TIMESTAMP"),
        ]
    
    def _get_competitor_overlap_schema(self):
        from google.cloud import bigquery
        return [
            bigquery.SchemaField("overlap_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("snapshot_date", "DATE", mode="REQUIRED"),
            bigquery.SchemaField("supplier_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("supplier_name", "STRING"),
            bigquery.SchemaField("supplier_country", "STRING"),
            bigquery.SchemaField("shipments_to_c1", "INTEGER"),
            bigquery.SchemaField("other_customer_name", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("other_customer_normalized", "STRING"),
            bigquery.SchemaField("other_customer_type", "STRING"),
            bigquery.SchemaField("other_customer_industry", "STRING"),
            bigquery.SchemaField("shipments_to_other", "INTEGER"),
            bigquery.SchemaField("c1_vs_other_ratio", "FLOAT64"),
            bigquery.SchemaField("shared_hs_codes", "STRING", mode="REPEATED"),
            bigquery.SchemaField("shared_products", "STRING", mode="REPEATED"),
            bigquery.SchemaField("overlap_type", "STRING"),
            bigquery.SchemaField("threat_level", "STRING"),
            bigquery.SchemaField("opportunity_flag", "BOOLEAN"),
            bigquery.SchemaField("insight_summary", "STRING"),
            bigquery.SchemaField("created_at", "TIMESTAMP"),
        ]
    
    def _get_change_events_schema(self):
        from google.cloud import bigquery
        return [
            bigquery.SchemaField("event_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("detected_date", "TIMESTAMP", mode="REQUIRED"),
            bigquery.SchemaField("snapshot_id", "STRING"),
            bigquery.SchemaField("event_type", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("event_category", "STRING"),
            bigquery.SchemaField("primary_entity_type", "STRING"),
            bigquery.SchemaField("primary_entity_id", "STRING"),
            bigquery.SchemaField("primary_entity_name", "STRING"),
            bigquery.SchemaField("secondary_entity_name", "STRING"),
            bigquery.SchemaField("previous_value", "FLOAT64"),
            bigquery.SchemaField("new_value", "FLOAT64"),
            bigquery.SchemaField("change_absolute", "FLOAT64"),
            bigquery.SchemaField("change_pct", "FLOAT64"),
            bigquery.SchemaField("hs_codes", "STRING", mode="REPEATED"),
            bigquery.SchemaField("products", "STRING", mode="REPEATED"),
            bigquery.SchemaField("summary", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("significance", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("digest_item_id", "STRING"),
            bigquery.SchemaField("acknowledged", "BOOLEAN"),
            bigquery.SchemaField("acknowledged_by", "STRING"),
            bigquery.SchemaField("acknowledged_at", "TIMESTAMP"),
            bigquery.SchemaField("created_at", "TIMESTAMP"),
        ]
    
    # =========================================================================
    # Storage Methods
    # =========================================================================
    
    async def store_supplier_customers(
        self,
        relationships: List[SupplierCustomerRelationship]
    ) -> int:
        """Store supplier-customer relationships."""
        if not relationships:
            return 0
        
        table_id = self._get_table_id("iy_supplier_customers")
        
        rows = []
        for rel in relationships:
            row = {
                "relationship_id": rel.relationship_id,
                "snapshot_date": rel.snapshot_date.isoformat(),
                "supplier_id": rel.supplier_id,
                "supplier_name": rel.supplier_name,
                "supplier_country": rel.supplier_country,
                "customer_name": rel.customer_name,
                "customer_name_normalized": rel.customer_name_normalized,
                "customer_address": rel.customer_address,
                "customer_country": rel.customer_country,
                "customer_key": rel.customer_key,
                "total_shipments_to_customer": rel.total_shipments_to_customer,
                "shipments_pct_of_supplier": rel.shipments_pct_of_supplier,
                "shipments_pct_of_customer": rel.shipments_pct_of_customer,
                "shipments_12m": rel.shipments_12m,
                "total_weight_kg": rel.total_weight_kg,
                "total_teu": rel.total_teu,
                "hs_code_chapters": json.dumps([asdict(hs) for hs in rel.hs_code_chapters]),
                "product_descriptions": rel.product_descriptions,
                "customer_top_suppliers": json.dumps([asdict(s) for s in rel.customer_top_suppliers]),
                "relationship_time_series": json.dumps([asdict(t) for t in rel.relationship_time_series]),
                "first_shipment_date": rel.first_shipment_date.isoformat() if rel.first_shipment_date else None,
                "most_recent_shipment_date": rel.most_recent_shipment_date.isoformat() if rel.most_recent_shipment_date else None,
                "business_length": rel.business_length,
                "is_new_customer": rel.is_new_customer,
                "first_seen_date": rel.first_seen_date.isoformat() if rel.first_seen_date else None,
                "last_seen_date": rel.last_seen_date.isoformat() if rel.last_seen_date else None,
                "is_active": rel.is_active,
                "created_at": rel.created_at.isoformat(),
            }
            rows.append(row)
        
        errors = self._client.insert_rows_json(table_id, rows)
        if errors:
            logger.error(f"BigQuery insert errors: {errors[:3]}")
            raise Exception(f"Failed to insert {len(errors)} rows")
        
        logger.info(f"Stored {len(rows)} supplier-customer relationships")
        return len(rows)
    
    async def store_company_suppliers(
        self,
        relationships: List[CompanySupplierRelationship]
    ) -> int:
        """Store company-supplier relationships."""
        if not relationships:
            return 0
        
        table_id = self._get_table_id("iy_company_suppliers")
        
        rows = []
        for rel in relationships:
            row = {
                "relationship_id": rel.relationship_id,
                "snapshot_date": rel.snapshot_date.isoformat(),
                "company_id": rel.company_id,
                "company_name": rel.company_name,
                "supplier_name": rel.supplier_name,
                "supplier_name_normalized": rel.supplier_name_normalized,
                "supplier_address": rel.supplier_address,
                "supplier_country": rel.supplier_country,
                "supplier_key": rel.supplier_key,
                "total_shipments_from_supplier": rel.total_shipments_from_supplier,
                "shipments_pct_of_company": rel.shipments_pct_of_company,
                "shipments_pct_of_supplier": rel.shipments_pct_of_supplier,
                "shipments_12m": rel.shipments_12m,
                "total_weight_kg": rel.total_weight_kg,
                "total_teu": rel.total_teu,
                "hs_code_chapters": json.dumps([asdict(hs) for hs in rel.hs_code_chapters]),
                "product_descriptions": rel.product_descriptions,
                "supplier_top_companies": json.dumps([asdict(c) for c in rel.supplier_top_companies]),
                "relationship_time_series": json.dumps([asdict(t) for t in rel.relationship_time_series]),
                "first_shipment_date": rel.first_shipment_date.isoformat() if rel.first_shipment_date else None,
                "most_recent_shipment_date": rel.most_recent_shipment_date.isoformat() if rel.most_recent_shipment_date else None,
                "business_length": rel.business_length,
                "first_seen_date": rel.first_seen_date.isoformat() if rel.first_seen_date else None,
                "last_seen_date": rel.last_seen_date.isoformat() if rel.last_seen_date else None,
                "is_active": rel.is_active,
                "created_at": rel.created_at.isoformat(),
            }
            rows.append(row)
        
        errors = self._client.insert_rows_json(table_id, rows)
        if errors:
            logger.error(f"BigQuery insert errors: {errors[:3]}")
            raise Exception(f"Failed to insert {len(errors)} rows")
        
        logger.info(f"Stored {len(rows)} company-supplier relationships")
        return len(rows)
    
    async def store_suppliers(self, suppliers: List[SupplierProfile]) -> int:
        """Store/update supplier profiles."""
        if not suppliers:
            return 0
        
        table_id = self._get_table_id("iy_suppliers")
        
        rows = []
        for s in suppliers:
            row = {
                "supplier_id": s.supplier_id,
                "supplier_name": s.supplier_name,
                "also_known_names": s.also_known_names,
                "country": s.country,
                "country_code": s.country_code,
                "address": s.address,
                "website": s.website,
                "phone_number": s.phone_number,
                "total_shipments": s.total_shipments,
                "total_us_customers": s.total_us_customers,
                "primary_hs_codes": json.dumps([asdict(hs) for hs in s.primary_hs_codes]),
                "is_c1_supplier": s.is_c1_supplier,
                "is_tracked_competitor": s.is_tracked_competitor,
                "supplier_tier": s.supplier_tier.value if s.supplier_tier else None,
                "first_seen_date": s.first_seen_date.isoformat() if s.first_seen_date else None,
                "last_updated": s.last_updated.isoformat() if s.last_updated else None,
            }
            rows.append(row)
        
        # Use MERGE for upsert behavior
        # For simplicity, using insert (you'd want MERGE in production)
        errors = self._client.insert_rows_json(table_id, rows)
        if errors:
            logger.error(f"BigQuery insert errors: {errors[:3]}")
        
        logger.info(f"Stored {len(rows)} suppliers")
        return len(rows)
    
    async def store_companies(self, companies: List[CompanyProfile]) -> int:
        """Store/update company profiles."""
        if not companies:
            return 0
        
        table_id = self._get_table_id("iy_companies")
        
        rows = []
        for c in companies:
            row = {
                "company_id": c.company_id,
                "company_name": c.company_name,
                "also_known_names": c.also_known_names,
                "country": c.country,
                "country_code": c.country_code,
                "address": c.address,
                "website": c.website,
                "phone_number": c.phone_number,
                "total_shipments": c.total_shipments,
                "total_suppliers": c.total_suppliers,
                "primary_hs_codes": json.dumps([asdict(hs) for hs in c.primary_hs_codes]),
                "company_type": c.company_type.value if c.company_type else None,
                "industries": c.industries,
                "is_c1_customer": c.is_c1_customer,
                "is_prospect": c.is_prospect,
                "first_seen_date": c.first_seen_date.isoformat() if c.first_seen_date else None,
                "last_updated": c.last_updated.isoformat() if c.last_updated else None,
            }
            rows.append(row)
        
        errors = self._client.insert_rows_json(table_id, rows)
        if errors:
            logger.error(f"BigQuery insert errors: {errors[:3]}")
        
        logger.info(f"Stored {len(rows)} companies")
        return len(rows)
    
    async def store_change_events(self, events: List[ChangeEvent]) -> int:
        """Store change events."""
        if not events:
            return 0
        
        table_id = self._get_table_id("iy_change_events")
        
        rows = []
        for e in events:
            row = {
                "event_id": e.event_id,
                "detected_date": e.detected_date.isoformat(),
                "snapshot_id": e.snapshot_id,
                "event_type": e.event_type.value,
                "event_category": e.event_category,
                "primary_entity_type": e.primary_entity_type,
                "primary_entity_id": e.primary_entity_id,
                "primary_entity_name": e.primary_entity_name,
                "secondary_entity_name": e.secondary_entity_name,
                "previous_value": e.previous_value,
                "new_value": e.new_value,
                "change_absolute": e.change_absolute,
                "change_pct": e.change_pct,
                "hs_codes": e.hs_codes,
                "products": e.products,
                "summary": e.summary,
                "significance": e.significance.value,
                "digest_item_id": e.digest_item_id,
                "acknowledged": e.acknowledged,
                "acknowledged_by": e.acknowledged_by,
                "acknowledged_at": e.acknowledged_at.isoformat() if e.acknowledged_at else None,
                "created_at": e.created_at.isoformat(),
            }
            rows.append(row)
        
        errors = self._client.insert_rows_json(table_id, rows)
        if errors:
            logger.error(f"BigQuery insert errors: {errors[:3]}")
        
        logger.info(f"Stored {len(rows)} change events")
        return len(rows)
    
    # =========================================================================
    # Query Methods
    # =========================================================================
    
    async def get_previous_supplier_customers(
        self,
        supplier_id: str,
        before_date: date,
    ) -> List[Dict[str, Any]]:
        """Get previous snapshot's supplier customers for change detection."""
        query = f"""
        SELECT *
        FROM `{self._get_table_id('iy_supplier_customers')}`
        WHERE supplier_id = @supplier_id
          AND snapshot_date = (
              SELECT MAX(snapshot_date)
              FROM `{self._get_table_id('iy_supplier_customers')}`
              WHERE supplier_id = @supplier_id
                AND snapshot_date < @before_date
          )
        """
        
        from google.cloud import bigquery
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("supplier_id", "STRING", supplier_id),
                bigquery.ScalarQueryParameter("before_date", "DATE", before_date.isoformat()),
            ]
        )
        
        result = self._client.query(query, job_config=job_config)
        return [dict(row) for row in result]
    
    async def get_latest_snapshot_date(self) -> Optional[date]:
        """Get the most recent snapshot date."""
        query = f"""
        SELECT MAX(snapshot_date) as latest_date
        FROM `{self._get_table_id('iy_supplier_customers')}`
        """
        
        result = self._client.query(query)
        for row in result:
            if row.latest_date:
                return row.latest_date
        return None

    async def get_dashboard_stats(self) -> Dict[str, Any]:
        """Get high-level dashboard statistics."""
        # Get latest snapshot date
        latest_date = await self.get_latest_snapshot_date()
        if not latest_date:
            return {"suppliers": 0, "shipments": 0, "companies": 0, "relationships": 0}
            
        dataset = f"{self.project_id}.{self.dataset_id}"
        
        query = f"""
        WITH stats AS (
            SELECT 
                (SELECT COUNT(*) FROM `{dataset}.iy_suppliers`) as total_suppliers,
                (SELECT COUNT(*) FROM `{dataset}.iy_companies` WHERE company_type = 'oem') as total_oems,
                (SELECT COUNT(*) FROM `{dataset}.iy_supplier_customers` WHERE snapshot_date = @snapshot_date) as active_relationships,
                (SELECT SUM(total_shipments_to_customer) FROM `{dataset}.iy_supplier_customers` WHERE snapshot_date = @snapshot_date) as tracked_shipments
        )
        SELECT * FROM stats
        """
        
        from google.cloud import bigquery
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("snapshot_date", "DATE", latest_date),
            ]
        )
        
        result = self._client.query(query, job_config=job_config)
        rows = list(result)
        if rows:
            return dict(rows[0])
        return {"suppliers": 0, "shipments": 0, "companies": 0, "relationships": 0}

    async def get_suppliers_list(
        self, 
        limit: int = 50, 
        offset: int = 0,
        search: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get list of tracked suppliers."""
        dataset = f"{self.project_id}.{self.dataset_id}"
        
        where_clause = "WHERE 1=1"
        params = []
        
        from google.cloud import bigquery
        
        if search:
            where_clause += " AND LOWER(supplier_name) LIKE @search"
            params.append(bigquery.ScalarQueryParameter("search", "STRING", f"%{search.lower()}%"))
            
        query = f"""
        SELECT 
            supplier_id,
            supplier_name,
            country,
            supplier_tier,
            total_shipments,
            total_us_customers,
            is_c1_supplier,
            last_updated
        FROM `{dataset}.iy_suppliers`
        {where_clause}
        ORDER BY total_shipments DESC
        LIMIT @limit OFFSET @offset
        """
        
        params.extend([
            bigquery.ScalarQueryParameter("limit", "INTEGER", limit),
            bigquery.ScalarQueryParameter("offset", "INTEGER", offset),
        ])
        
        job_config = bigquery.QueryJobConfig(query_parameters=params)
        result = self._client.query(query, job_config=job_config)
        
        return [dict(row) for row in result]

    async def get_supplier_details(self, supplier_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed supplier info including recent customers."""
        dataset = f"{self.project_id}.{self.dataset_id}"
        
        # Get profile
        query_profile = f"""
        SELECT * FROM `{dataset}.iy_suppliers`
        WHERE supplier_id = @supplier_id
        LIMIT 1
        """
        
        from google.cloud import bigquery
        job_config = bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("supplier_id", "STRING", supplier_id)]
        )
        
        result = self._client.query(query_profile, job_config=job_config)
        profile_rows = list(result)
        if not profile_rows:
            return None
            
        profile = dict(profile_rows[0])
        
        # Get customers from latest snapshot
        latest_date = await self.get_latest_snapshot_date()
        if latest_date:
            query_customers = f"""
            SELECT 
                customer_name,
                customer_country,
                total_shipments_to_customer,
                shipments_pct_of_supplier,
                product_descriptions
            FROM `{dataset}.iy_supplier_customers`
            WHERE supplier_id = @supplier_id
              AND snapshot_date = @snapshot_date
            ORDER BY total_shipments_to_customer DESC
            LIMIT 20
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("supplier_id", "STRING", supplier_id),
                    bigquery.ScalarQueryParameter("snapshot_date", "DATE", latest_date),
                ]
            )
            
            customers_result = self._client.query(query_customers, job_config=job_config)
            profile["customers"] = [dict(row) for row in customers_result]
            
        return profile

    async def get_network_graph(self) -> Dict[str, List[Any]]:
        """Get nodes and links for network visualization."""
        latest_date = await self.get_latest_snapshot_date()
        if not latest_date:
            return {"nodes": [], "links": []}
            
        dataset = f"{self.project_id}.{self.dataset_id}"
        
        # Get top relationships
        query = f"""
        SELECT 
            t1.supplier_name,
            t1.customer_name,
            t1.total_shipments_to_customer,
            t2.supplier_tier
        FROM `{dataset}.iy_supplier_customers` t1
        LEFT JOIN `{dataset}.iy_suppliers` t2 ON t1.supplier_id = t2.supplier_id
        WHERE t1.snapshot_date = @snapshot_date
        ORDER BY t1.total_shipments_to_customer DESC
        LIMIT 200
        """
        
        from google.cloud import bigquery
        job_config = bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("snapshot_date", "DATE", latest_date)]
        )
        
        result = self._client.query(query, job_config=job_config)
        
        nodes = {}
        links = []
        
        for row in result:
            # Add supplier node
            s_name = row.supplier_name
            if s_name not in nodes:
                nodes[s_name] = {"id": s_name, "type": "supplier", "tier": row.supplier_tier or "unknown"}
            
            # Add customer node
            c_name = row.customer_name
            if c_name not in nodes:
                nodes[c_name] = {"id": c_name, "type": "customer"}
                
            # Add link
            links.append({
                "source": s_name,
                "target": c_name,
                "value": row.total_shipments_to_customer
            })
            
        return {
            "nodes": list(nodes.values()),
            "links": links
        }
