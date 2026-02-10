"""
BigQuery Storage for ImportYeti Supply Chain Graph
===================================================

Replaces the SQLite Database class from the reference implementation.
All CRUD operations target BigQuery tables in the c1_intelligence dataset.

Tables:
    iy_companies   — US importers (C1, competitors, discovered buyers)
    iy_suppliers   — Overseas exporters/manufacturers
    iy_edges       — Directional relationships (imports_from, supplies_to)
    iy_ingestion_log — Audit trail per pipeline run

Views:
    iy_v_shared_suppliers      — Suppliers serving 2+ competitors (all-time)
    iy_v_shared_suppliers_12m  — Same, filtered to 12-month active
    iy_v_exclusive_suppliers   — Suppliers serving exactly 1 competitor
    iy_v_competitor_activity_12m — Per-company summary
    iy_v_buyer_overlap         — Discovered buyers in 2+ supplier networks

Design:
    - Upserts use MERGE statements for idempotency
    - Entity type hierarchy preserved: target > competitor > discovered
    - All operations are synchronous (BigQuery client is sync)
"""

import json
import logging
import time
from datetime import datetime
from typing import Optional, List, Dict, Any

from google.cloud import bigquery
from google.api_core import exceptions as gcp_exceptions

from .config.settings import (
    GCP_PROJECT_ID,
    BQ_DATASET,
    TABLE_COMPANIES,
    TABLE_SUPPLIERS,
    TABLE_EDGES,
    TABLE_INGESTION_LOG,
)

logger = logging.getLogger("importyeti_bq")


class BigQueryStore:
    """
    BigQuery storage manager for the ImportYeti supply chain graph.

    Handles table creation, upserts, edge insertion, and analytical queries.
    Drop-in replacement for the SQLite Database class.
    """

    def __init__(
        self,
        project_id: Optional[str] = None,
        dataset_id: Optional[str] = None,
    ):
        self.project_id = project_id or GCP_PROJECT_ID
        self.dataset_id = dataset_id or BQ_DATASET
        self._client = None

    @property
    def client(self) -> bigquery.Client:
        if self._client is None:
            self._client = bigquery.Client(project=self.project_id)
        return self._client

    def _table_id(self, table_name: str) -> str:
        return f"{self.project_id}.{self.dataset_id}.{table_name}"

    def _streaming_insert_with_retry(
        self, table_id: str, rows: list, max_retries: int = 3
    ) -> list:
        """
        Streaming insert with retry for transient BQ errors
        (e.g., table not yet propagated after creation).
        Returns list of errors (empty = success).
        """
        for attempt in range(max_retries):
            try:
                errors = self.client.insert_rows_json(table_id, rows)
                return errors
            except gcp_exceptions.NotFound:
                if attempt < max_retries - 1:
                    wait = 5 * (attempt + 1)
                    logger.warning(
                        f"[IMPORTYETI_BQ] Table not found for streaming, "
                        f"retrying in {wait}s (attempt {attempt + 1}/{max_retries})"
                    )
                    time.sleep(wait)
                else:
                    raise
            except Exception:
                if attempt < max_retries - 1:
                    time.sleep(2)
                else:
                    raise
        return []

    # =============================================
    # INITIALIZATION
    # =============================================

    def initialize(self, created_tables: bool = False):
        """Create all tables and views if they don't exist."""
        logger.info("[IMPORTYETI_BQ] Initializing BigQuery schema...")
        t1 = self._ensure_companies_table()
        t2 = self._ensure_suppliers_table()
        t3 = self._ensure_edges_table()
        t4 = self._ensure_ingestion_log_table()
        self._ensure_views()

        # BigQuery needs propagation time after table creation
        # before streaming inserts work (typically 5-30 seconds)
        if any([t1, t2, t3, t4]) or created_tables:
            logger.info("[IMPORTYETI_BQ] New tables created — waiting 10s for BQ propagation")
            time.sleep(10)

        logger.info("[IMPORTYETI_BQ] Schema initialized successfully")

    def _ensure_companies_table(self) -> bool:
        table_id = self._table_id(TABLE_COMPANIES)
        schema = [
            bigquery.SchemaField("importyeti_key", "STRING", mode="REQUIRED",
                                 description="e.g., company/sherwin-williams"),
            bigquery.SchemaField("name", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("also_known_names", "STRING",
                                 description="JSON array of alternate names"),
            bigquery.SchemaField("address", "STRING"),
            bigquery.SchemaField("country", "STRING", default_value_expression="'United States'"),
            bigquery.SchemaField("country_code", "STRING", default_value_expression="'US'"),
            bigquery.SchemaField("website", "STRING"),
            bigquery.SchemaField("phone_number", "STRING"),
            bigquery.SchemaField("total_shipments", "INTEGER"),
            bigquery.SchemaField("entity_type", "STRING", mode="REQUIRED",
                                 description="target, competitor, or discovered"),
            bigquery.SchemaField("category", "STRING",
                                 description="From competitors.json"),
            bigquery.SchemaField("ticker", "STRING"),
            bigquery.SchemaField("notes", "STRING"),
            bigquery.SchemaField("shipments_by_country", "STRING",
                                 description="JSON: {China: 1234, India: 567}"),
            bigquery.SchemaField("raw_api_response", "STRING",
                                 description="Full JSON from ImportYeti"),
            bigquery.SchemaField("ingested_at", "TIMESTAMP",
                                 default_value_expression="CURRENT_TIMESTAMP()"),
            bigquery.SchemaField("updated_at", "TIMESTAMP",
                                 default_value_expression="CURRENT_TIMESTAMP()"),
        ]
        return self._create_table_if_not_exists(table_id, schema)

    def _ensure_suppliers_table(self) -> bool:
        table_id = self._table_id(TABLE_SUPPLIERS)
        schema = [
            bigquery.SchemaField("importyeti_key", "STRING", mode="REQUIRED",
                                 description="e.g., supplier/basf"),
            bigquery.SchemaField("name", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("also_known_names", "STRING",
                                 description="JSON array"),
            bigquery.SchemaField("address", "STRING"),
            bigquery.SchemaField("address_country", "STRING"),
            bigquery.SchemaField("address_country_code", "STRING"),
            bigquery.SchemaField("country", "STRING"),
            bigquery.SchemaField("country_code", "STRING"),
            bigquery.SchemaField("website", "STRING"),
            bigquery.SchemaField("phone_number", "STRING"),
            bigquery.SchemaField("total_shipments", "INTEGER"),
            bigquery.SchemaField("raw_api_response", "STRING"),
            bigquery.SchemaField("ingested_at", "TIMESTAMP",
                                 default_value_expression="CURRENT_TIMESTAMP()"),
            bigquery.SchemaField("updated_at", "TIMESTAMP",
                                 default_value_expression="CURRENT_TIMESTAMP()"),
        ]
        return self._create_table_if_not_exists(table_id, schema)

    def _ensure_edges_table(self) -> bool:
        table_id = self._table_id(TABLE_EDGES)
        schema = [
            bigquery.SchemaField("source_type", "STRING", mode="REQUIRED",
                                 description="company or supplier"),
            bigquery.SchemaField("source_key", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("target_type", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("target_key", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("relationship_type", "STRING", mode="REQUIRED",
                                 description="imports_from or supplies_to"),
            bigquery.SchemaField("discovered_from", "STRING", mode="REQUIRED",
                                 description="company_profile or supplier_profile"),
            bigquery.SchemaField("total_shipments", "INTEGER"),
            bigquery.SchemaField("shipments_12m", "INTEGER"),
            bigquery.SchemaField("shipment_pct_of_source", "FLOAT"),
            bigquery.SchemaField("shipment_pct_of_target", "FLOAT"),
            bigquery.SchemaField("total_weight", "INTEGER"),
            bigquery.SchemaField("total_teus", "INTEGER"),
            bigquery.SchemaField("supplier_country", "STRING"),
            bigquery.SchemaField("supplier_country_code", "STRING"),
            bigquery.SchemaField("most_recent_shipment", "STRING"),
            bigquery.SchemaField("first_shipment", "STRING"),
            bigquery.SchemaField("business_length", "STRING"),
            bigquery.SchemaField("is_new_relationship", "BOOLEAN"),
            bigquery.SchemaField("ingested_at", "TIMESTAMP",
                                 default_value_expression="CURRENT_TIMESTAMP()"),
        ]
        return self._create_table_if_not_exists(table_id, schema)

    def _ensure_ingestion_log_table(self) -> bool:
        table_id = self._table_id(TABLE_INGESTION_LOG)
        schema = [
            bigquery.SchemaField("run_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("phase", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("entity_name", "STRING"),
            bigquery.SchemaField("entity_key", "STRING"),
            bigquery.SchemaField("status", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("error_message", "STRING"),
            bigquery.SchemaField("api_credits_used", "INTEGER", default_value_expression="0"),
            bigquery.SchemaField("duration_ms", "INTEGER"),
            bigquery.SchemaField("timestamp", "TIMESTAMP",
                                 default_value_expression="CURRENT_TIMESTAMP()"),
        ]
        return self._create_table_if_not_exists(table_id, schema)

    def _create_table_if_not_exists(self, table_id: str, schema: list) -> bool:
        """Create a BigQuery table if it doesn't already exist. Returns True if created."""
        try:
            self.client.get_table(table_id)
            logger.debug(f"[IMPORTYETI_BQ] Table exists: {table_id}")
            return False
        except Exception:
            table = bigquery.Table(table_id, schema=schema)
            self.client.create_table(table)
            logger.info(f"[IMPORTYETI_BQ] Created table: {table_id}")
            return True

    def _ensure_views(self):
        """Create analytical views (with dedup for append-only supplier rows)."""
        # Dedup CTE fragment used by all views that join iy_suppliers.
        # Streaming inserts are append-only, so Phase 2 (basic) + Phase 3
        # (full profile) produce 2 rows per supplier. We pick the latest.
        suppliers_dedup = f"""
            SELECT * EXCEPT(_rn) FROM (
                SELECT *, ROW_NUMBER() OVER (
                    PARTITION BY importyeti_key ORDER BY updated_at DESC
                ) AS _rn
                FROM `{self._table_id(TABLE_SUPPLIERS)}`
            ) WHERE _rn = 1
        """

        views = {
            # Shared suppliers: suppliers serving 2+ tracked entities
            self._table_id("iy_v_shared_suppliers"): f"""
                WITH s_dedup AS ({suppliers_dedup})
                SELECT
                    s.name AS supplier_name,
                    s.importyeti_key AS supplier_key,
                    s.country AS supplier_country,
                    COUNT(DISTINCT c.importyeti_key) AS num_competitors_served,
                    STRING_AGG(DISTINCT c.name, ', ' ORDER BY c.name) AS competitors_served,
                    SUM(e.total_shipments) AS total_shipments_across_competitors
                FROM `{self._table_id(TABLE_EDGES)}` e
                JOIN s_dedup s ON e.target_key = s.importyeti_key
                JOIN `{self._table_id(TABLE_COMPANIES)}` c ON e.source_key = c.importyeti_key
                WHERE e.relationship_type = 'imports_from'
                  AND c.entity_type IN ('target', 'competitor')
                GROUP BY s.name, s.importyeti_key, s.country
                HAVING COUNT(DISTINCT c.importyeti_key) >= 2
                ORDER BY num_competitors_served DESC, total_shipments_across_competitors DESC
            """,

            # Shared suppliers (12-month active)
            self._table_id("iy_v_shared_suppliers_12m"): f"""
                WITH s_dedup AS ({suppliers_dedup})
                SELECT
                    s.name AS supplier_name,
                    s.importyeti_key AS supplier_key,
                    s.country AS supplier_country,
                    COUNT(DISTINCT c.importyeti_key) AS num_competitors_served,
                    STRING_AGG(DISTINCT c.name, ', ' ORDER BY c.name) AS competitors_served,
                    SUM(e.shipments_12m) AS shipments_12m_across_competitors
                FROM `{self._table_id(TABLE_EDGES)}` e
                JOIN s_dedup s ON e.target_key = s.importyeti_key
                JOIN `{self._table_id(TABLE_COMPANIES)}` c ON e.source_key = c.importyeti_key
                WHERE e.relationship_type = 'imports_from'
                  AND c.entity_type IN ('target', 'competitor')
                  AND COALESCE(e.shipments_12m, 0) > 0
                GROUP BY s.name, s.importyeti_key, s.country
                HAVING COUNT(DISTINCT c.importyeti_key) >= 2
                ORDER BY num_competitors_served DESC, shipments_12m_across_competitors DESC
            """,

            # Exclusive suppliers (serve exactly 1 tracked entity)
            self._table_id("iy_v_exclusive_suppliers"): f"""
                WITH s_dedup AS ({suppliers_dedup})
                SELECT
                    s.name AS supplier_name,
                    s.importyeti_key AS supplier_key,
                    s.country AS supplier_country,
                    c.name AS exclusive_to,
                    c.entity_type,
                    e.total_shipments,
                    e.shipments_12m
                FROM `{self._table_id(TABLE_EDGES)}` e
                JOIN s_dedup s ON e.target_key = s.importyeti_key
                JOIN `{self._table_id(TABLE_COMPANIES)}` c ON e.source_key = c.importyeti_key
                WHERE e.relationship_type = 'imports_from'
                  AND c.entity_type IN ('target', 'competitor')
                  AND s.importyeti_key NOT IN (
                      SELECT e2.target_key
                      FROM `{self._table_id(TABLE_EDGES)}` e2
                      JOIN `{self._table_id(TABLE_COMPANIES)}` c2 ON e2.source_key = c2.importyeti_key
                      WHERE e2.relationship_type = 'imports_from'
                        AND c2.entity_type IN ('target', 'competitor')
                      GROUP BY e2.target_key
                      HAVING COUNT(DISTINCT e2.source_key) >= 2
                  )
                ORDER BY e.total_shipments DESC
            """,

            # Competitor activity (12-month) — no iy_suppliers join needed
            self._table_id("iy_v_competitor_activity_12m"): f"""
                SELECT
                    c.name AS company_name,
                    c.importyeti_key AS company_key,
                    c.entity_type,
                    c.total_shipments AS company_total_shipments,
                    COUNT(DISTINCT e.target_key) AS total_suppliers,
                    COUNTIF(COALESCE(e.shipments_12m, 0) > 0) AS active_suppliers_12m,
                    COUNTIF(COALESCE(e.shipments_12m, 0) = 0) AS dormant_suppliers,
                    SUM(e.shipments_12m) AS total_shipments_12m
                FROM `{self._table_id(TABLE_COMPANIES)}` c
                LEFT JOIN `{self._table_id(TABLE_EDGES)}` e
                    ON c.importyeti_key = e.source_key
                    AND e.relationship_type = 'imports_from'
                WHERE c.entity_type IN ('target', 'competitor')
                GROUP BY c.name, c.importyeti_key, c.entity_type, c.total_shipments
                ORDER BY total_shipments_12m DESC
            """,

            # Buyer overlap (discovered buyers appearing in 2+ supplier networks)
            self._table_id("iy_v_buyer_overlap"): f"""
                WITH s_dedup AS ({suppliers_dedup})
                SELECT
                    c.name AS buyer_name,
                    c.importyeti_key AS buyer_key,
                    COUNT(DISTINCT e.source_key) AS num_suppliers,
                    STRING_AGG(DISTINCT s.name, ', ' ORDER BY s.name) AS suppliers,
                    SUM(e.total_shipments) AS total_shipments
                FROM `{self._table_id(TABLE_EDGES)}` e
                JOIN `{self._table_id(TABLE_COMPANIES)}` c ON e.target_key = c.importyeti_key
                JOIN s_dedup s ON e.source_key = s.importyeti_key
                WHERE e.relationship_type = 'supplies_to'
                GROUP BY c.name, c.importyeti_key
                HAVING COUNT(DISTINCT e.source_key) >= 2
                ORDER BY num_suppliers DESC, total_shipments DESC
            """,
        }

        for view_id, query in views.items():
            try:
                view = bigquery.Table(view_id)
                view.view_query = query
                self.client.create_table(view, exists_ok=True)
                logger.debug(f"[IMPORTYETI_BQ] View ensured: {view_id}")
            except Exception as e:
                # Update view if it exists with different SQL
                try:
                    view = bigquery.Table(view_id)
                    view.view_query = query
                    self.client.update_table(view, ["view_query"])
                    logger.debug(f"[IMPORTYETI_BQ] View updated: {view_id}")
                except Exception as e2:
                    logger.warning(f"[IMPORTYETI_BQ] Could not create/update view {view_id}: {e2}")

    # =============================================
    # COMPANIES — UPSERT / READ
    # =============================================

    def upsert_company(
        self,
        importyeti_key: str,
        name: str,
        entity_type: str = "discovered",
        also_known_names: Optional[list] = None,
        address: Optional[str] = None,
        country: str = "United States",
        country_code: str = "US",
        website: Optional[str] = None,
        phone_number: Optional[str] = None,
        total_shipments: Optional[int] = None,
        category: Optional[str] = None,
        ticker: Optional[str] = None,
        notes: Optional[str] = None,
        shipments_by_country: Optional[dict] = None,
        raw_api_response: Optional[dict] = None,
    ):
        """
        Insert or update a company record.
        Entity type hierarchy preserved: target > competitor > discovered.
        """
        akn_json = json.dumps(also_known_names) if also_known_names else None
        sbc_json = json.dumps(shipments_by_country) if shipments_by_country else None
        raw_json = json.dumps(raw_api_response) if raw_api_response else None

        table_id = self._table_id(TABLE_COMPANIES)

        query = f"""
            MERGE `{table_id}` T
            USING (SELECT @importyeti_key AS importyeti_key) S
            ON T.importyeti_key = S.importyeti_key
            WHEN MATCHED THEN UPDATE SET
                name = COALESCE(@name, T.name),
                also_known_names = COALESCE(@also_known_names, T.also_known_names),
                address = COALESCE(@address, T.address),
                country = COALESCE(@country, T.country),
                country_code = COALESCE(@country_code, T.country_code),
                website = COALESCE(@website, T.website),
                phone_number = COALESCE(@phone_number, T.phone_number),
                total_shipments = COALESCE(@total_shipments, T.total_shipments),
                shipments_by_country = COALESCE(@shipments_by_country, T.shipments_by_country),
                raw_api_response = COALESCE(@raw_api_response, T.raw_api_response),
                entity_type = CASE
                    WHEN T.entity_type = 'target' THEN 'target'
                    WHEN T.entity_type = 'competitor' THEN
                        CASE WHEN @entity_type = 'target' THEN 'target' ELSE 'competitor' END
                    ELSE @entity_type
                END,
                updated_at = CURRENT_TIMESTAMP()
            WHEN NOT MATCHED THEN INSERT (
                importyeti_key, name, entity_type, also_known_names,
                address, country, country_code, website, phone_number,
                total_shipments, category, ticker, notes,
                shipments_by_country, raw_api_response, ingested_at, updated_at
            ) VALUES (
                @importyeti_key, @name, @entity_type, @also_known_names,
                @address, @country, @country_code, @website, @phone_number,
                @total_shipments, @category, @ticker, @notes,
                @shipments_by_country, @raw_api_response, CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP()
            )
        """

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("importyeti_key", "STRING", importyeti_key),
                bigquery.ScalarQueryParameter("name", "STRING", name),
                bigquery.ScalarQueryParameter("entity_type", "STRING", entity_type),
                bigquery.ScalarQueryParameter("also_known_names", "STRING", akn_json),
                bigquery.ScalarQueryParameter("address", "STRING", address),
                bigquery.ScalarQueryParameter("country", "STRING", country),
                bigquery.ScalarQueryParameter("country_code", "STRING", country_code),
                bigquery.ScalarQueryParameter("website", "STRING", website),
                bigquery.ScalarQueryParameter("phone_number", "STRING", phone_number),
                bigquery.ScalarQueryParameter("total_shipments", "INT64", total_shipments),
                bigquery.ScalarQueryParameter("category", "STRING", category),
                bigquery.ScalarQueryParameter("ticker", "STRING", ticker),
                bigquery.ScalarQueryParameter("notes", "STRING", notes),
                bigquery.ScalarQueryParameter("shipments_by_country", "STRING", sbc_json),
                bigquery.ScalarQueryParameter("raw_api_response", "STRING", raw_json),
            ]
        )

        self.client.query(query, job_config=job_config).result()
        logger.debug(f"[IMPORTYETI_BQ] Upserted company: {name} ({importyeti_key})")

    def get_company(self, importyeti_key: str) -> Optional[Dict[str, Any]]:
        """Fetch a company by its ImportYeti key."""
        query = f"""
            SELECT * FROM `{self._table_id(TABLE_COMPANIES)}`
            WHERE importyeti_key = @key
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("key", "STRING", importyeti_key),
            ]
        )
        rows = list(self.client.query(query, job_config=job_config).result())
        if rows:
            return dict(rows[0])
        return None

    def company_exists(self, importyeti_key: str) -> bool:
        """Check if a company is already in the database."""
        return self.get_company(importyeti_key) is not None

    def search_companies_by_name(self, name: str) -> List[Dict[str, Any]]:
        """LIKE search for companies by name."""
        query = f"""
            SELECT * FROM `{self._table_id(TABLE_COMPANIES)}`
            WHERE LOWER(name) LIKE LOWER(@pattern)
               OR LOWER(also_known_names) LIKE LOWER(@pattern)
            ORDER BY total_shipments DESC
            LIMIT 20
        """
        pattern = f"%{name}%"
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("pattern", "STRING", pattern),
            ]
        )
        rows = list(self.client.query(query, job_config=job_config).result())
        return [dict(r) for r in rows]

    def get_all_companies(self, entity_types: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Get all companies, optionally filtered by entity type."""
        if entity_types:
            placeholders = ", ".join(f"'{et}'" for et in entity_types)
            query = f"""
                SELECT * FROM `{self._table_id(TABLE_COMPANIES)}`
                WHERE entity_type IN ({placeholders})
                ORDER BY total_shipments DESC
            """
        else:
            query = f"""
                SELECT * FROM `{self._table_id(TABLE_COMPANIES)}`
                ORDER BY total_shipments DESC
            """
        rows = list(self.client.query(query).result())
        return [dict(r) for r in rows]

    # =============================================
    # SUPPLIERS — UPSERT / READ
    # =============================================

    def upsert_supplier(
        self,
        importyeti_key: str,
        name: str,
        also_known_names: Optional[list] = None,
        address: Optional[str] = None,
        address_country: Optional[str] = None,
        address_country_code: Optional[str] = None,
        country: Optional[str] = None,
        country_code: Optional[str] = None,
        website: Optional[str] = None,
        phone_number: Optional[str] = None,
        total_shipments: Optional[int] = None,
        raw_api_response: Optional[dict] = None,
    ):
        """Insert or update a supplier record."""
        akn_json = json.dumps(also_known_names) if also_known_names else None
        raw_json = json.dumps(raw_api_response) if raw_api_response else None

        table_id = self._table_id(TABLE_SUPPLIERS)

        query = f"""
            MERGE `{table_id}` T
            USING (SELECT @importyeti_key AS importyeti_key) S
            ON T.importyeti_key = S.importyeti_key
            WHEN MATCHED THEN UPDATE SET
                name = COALESCE(@name, T.name),
                also_known_names = COALESCE(@also_known_names, T.also_known_names),
                address = COALESCE(@address, T.address),
                address_country = COALESCE(@address_country, T.address_country),
                address_country_code = COALESCE(@address_country_code, T.address_country_code),
                country = COALESCE(@country, T.country),
                country_code = COALESCE(@country_code, T.country_code),
                website = COALESCE(@website, T.website),
                phone_number = COALESCE(@phone_number, T.phone_number),
                total_shipments = COALESCE(@total_shipments, T.total_shipments),
                raw_api_response = COALESCE(@raw_api_response, T.raw_api_response),
                updated_at = CURRENT_TIMESTAMP()
            WHEN NOT MATCHED THEN INSERT (
                importyeti_key, name, also_known_names, address,
                address_country, address_country_code, country, country_code,
                website, phone_number, total_shipments, raw_api_response,
                ingested_at, updated_at
            ) VALUES (
                @importyeti_key, @name, @also_known_names, @address,
                @address_country, @address_country_code, @country, @country_code,
                @website, @phone_number, @total_shipments, @raw_api_response,
                CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP()
            )
        """

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("importyeti_key", "STRING", importyeti_key),
                bigquery.ScalarQueryParameter("name", "STRING", name),
                bigquery.ScalarQueryParameter("also_known_names", "STRING", akn_json),
                bigquery.ScalarQueryParameter("address", "STRING", address),
                bigquery.ScalarQueryParameter("address_country", "STRING", address_country),
                bigquery.ScalarQueryParameter("address_country_code", "STRING", address_country_code),
                bigquery.ScalarQueryParameter("country", "STRING", country),
                bigquery.ScalarQueryParameter("country_code", "STRING", country_code),
                bigquery.ScalarQueryParameter("website", "STRING", website),
                bigquery.ScalarQueryParameter("phone_number", "STRING", phone_number),
                bigquery.ScalarQueryParameter("total_shipments", "INT64", total_shipments),
                bigquery.ScalarQueryParameter("raw_api_response", "STRING", raw_json),
            ]
        )

        self.client.query(query, job_config=job_config).result()
        logger.debug(f"[IMPORTYETI_BQ] Upserted supplier: {name} ({importyeti_key})")

    def batch_insert_suppliers(self, suppliers: List[Dict[str, Any]]) -> int:
        """
        Bulk-insert new supplier records via streaming inserts.
        Use for initial ingestion when records are known to be new.
        Skips duplicates silently (BQ streaming is append-only, caller
        should ensure dedup or use upsert_supplier for known-existing).

        Args:
            suppliers: List of dicts with keys matching iy_suppliers schema.
                Required: importyeti_key, name.

        Returns:
            Number of rows successfully inserted.
        """
        if not suppliers:
            return 0

        table_id = self._table_id(TABLE_SUPPLIERS)
        now = datetime.utcnow().isoformat()

        rows = []
        for s in suppliers:
            rows.append({
                "importyeti_key": s["importyeti_key"],
                "name": s["name"],
                "also_known_names": json.dumps(s["also_known_names"]) if s.get("also_known_names") else None,
                "address": s.get("address"),
                "address_country": s.get("address_country"),
                "address_country_code": s.get("address_country_code"),
                "country": s.get("country"),
                "country_code": s.get("country_code"),
                "website": s.get("website"),
                "phone_number": s.get("phone_number"),
                "total_shipments": s.get("total_shipments"),
                "raw_api_response": json.dumps(s["raw_api_response"]) if s.get("raw_api_response") else None,
                "ingested_at": now,
                "updated_at": now,
            })

        errors = self._streaming_insert_with_retry(table_id, rows)
        if errors:
            logger.warning(f"[IMPORTYETI_BQ] Batch supplier insert had {len(errors)} errors: {errors[:3]}")
        inserted = len(rows) - len(errors)
        logger.info(f"[IMPORTYETI_BQ] Batch inserted {inserted}/{len(rows)} suppliers")
        return inserted

    def batch_insert_edges(self, edges: List[Dict[str, Any]]) -> int:
        """
        Bulk-insert edge records via streaming inserts.
        No dedup check — caller must ensure no duplicates.

        Args:
            edges: List of dicts with keys matching iy_edges schema.
                Required: source_type, source_key, target_type, target_key,
                         relationship_type, discovered_from.

        Returns:
            Number of rows successfully inserted.
        """
        if not edges:
            return 0

        table_id = self._table_id(TABLE_EDGES)
        now = datetime.utcnow().isoformat()

        rows = []
        for e in edges:
            rows.append({
                "source_type": e["source_type"],
                "source_key": e["source_key"],
                "target_type": e["target_type"],
                "target_key": e["target_key"],
                "relationship_type": e["relationship_type"],
                "discovered_from": e["discovered_from"],
                "total_shipments": e.get("total_shipments"),
                "shipments_12m": e.get("shipments_12m"),
                "shipment_pct_of_source": e.get("shipment_pct_of_source"),
                "shipment_pct_of_target": e.get("shipment_pct_of_target"),
                "total_weight": e.get("total_weight"),
                "total_teus": e.get("total_teus"),
                "supplier_country": e.get("supplier_country"),
                "supplier_country_code": e.get("supplier_country_code"),
                "most_recent_shipment": e.get("most_recent_shipment"),
                "first_shipment": e.get("first_shipment"),
                "business_length": e.get("business_length"),
                "is_new_relationship": e.get("is_new_relationship"),
                "ingested_at": now,
            })

        errors = self._streaming_insert_with_retry(table_id, rows)
        if errors:
            logger.warning(f"[IMPORTYETI_BQ] Batch edge insert had {len(errors)} errors: {errors[:3]}")
        inserted = len(rows) - len(errors)
        logger.info(f"[IMPORTYETI_BQ] Batch inserted {inserted}/{len(rows)} edges")
        return inserted

    def batch_insert_companies(self, companies: List[Dict[str, Any]]) -> int:
        """
        Bulk-insert new company records via streaming inserts.
        For initial discovered-buyer inserts during Phase 3.
        """
        if not companies:
            return 0

        table_id = self._table_id(TABLE_COMPANIES)
        now = datetime.utcnow().isoformat()

        rows = []
        for c in companies:
            rows.append({
                "importyeti_key": c["importyeti_key"],
                "name": c["name"],
                "entity_type": c.get("entity_type", "discovered"),
                "also_known_names": json.dumps(c["also_known_names"]) if c.get("also_known_names") else None,
                "address": c.get("address"),
                "country": c.get("country", "United States"),
                "country_code": c.get("country_code", "US"),
                "website": c.get("website"),
                "phone_number": c.get("phone_number"),
                "total_shipments": c.get("total_shipments"),
                "category": c.get("category"),
                "ticker": c.get("ticker"),
                "notes": c.get("notes"),
                "shipments_by_country": json.dumps(c["shipments_by_country"]) if c.get("shipments_by_country") else None,
                "raw_api_response": json.dumps(c["raw_api_response"]) if c.get("raw_api_response") else None,
                "ingested_at": now,
                "updated_at": now,
            })

        errors = self._streaming_insert_with_retry(table_id, rows)
        if errors:
            logger.warning(f"[IMPORTYETI_BQ] Batch company insert had {len(errors)} errors: {errors[:3]}")
        inserted = len(rows) - len(errors)
        logger.info(f"[IMPORTYETI_BQ] Batch inserted {inserted}/{len(rows)} companies")
        return inserted

    def get_supplier(self, importyeti_key: str) -> Optional[Dict[str, Any]]:
        """Fetch a supplier by its ImportYeti key (latest version if dupes exist)."""
        query = f"""
            SELECT * FROM `{self._table_id(TABLE_SUPPLIERS)}`
            WHERE importyeti_key = @key
            ORDER BY updated_at DESC
            LIMIT 1
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("key", "STRING", importyeti_key),
            ]
        )
        rows = list(self.client.query(query, job_config=job_config).result())
        if rows:
            return dict(rows[0])
        return None

    def supplier_exists(self, importyeti_key: str) -> bool:
        return self.get_supplier(importyeti_key) is not None

    def search_suppliers_by_name(self, name: str) -> List[Dict[str, Any]]:
        """LIKE search for suppliers by name (deduped to latest version)."""
        query = f"""
            WITH ranked AS (
                SELECT *, ROW_NUMBER() OVER (
                    PARTITION BY importyeti_key ORDER BY updated_at DESC
                ) AS _rn
                FROM `{self._table_id(TABLE_SUPPLIERS)}`
            )
            SELECT * EXCEPT(_rn) FROM ranked
            WHERE _rn = 1
              AND (LOWER(name) LIKE LOWER(@pattern)
                   OR LOWER(also_known_names) LIKE LOWER(@pattern))
            ORDER BY total_shipments DESC
            LIMIT 20
        """
        pattern = f"%{name}%"
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("pattern", "STRING", pattern),
            ]
        )
        rows = list(self.client.query(query, job_config=job_config).result())
        return [dict(r) for r in rows]

    def get_all_supplier_keys(self) -> List[str]:
        """Get all supplier importyeti_keys currently stored."""
        query = f"SELECT DISTINCT importyeti_key FROM `{self._table_id(TABLE_SUPPLIERS)}`"
        rows = list(self.client.query(query).result())
        return [r["importyeti_key"] for r in rows]

    # =============================================
    # EDGES — INSERT / READ
    # =============================================

    def insert_edge(
        self,
        source_type: str,
        source_key: str,
        target_type: str,
        target_key: str,
        relationship_type: str,
        discovered_from: str,
        total_shipments: Optional[int] = None,
        shipments_12m: Optional[int] = None,
        shipment_pct_of_source: Optional[float] = None,
        shipment_pct_of_target: Optional[float] = None,
        total_weight: Optional[int] = None,
        total_teus: Optional[int] = None,
        supplier_country: Optional[str] = None,
        supplier_country_code: Optional[str] = None,
        most_recent_shipment: Optional[str] = None,
        first_shipment: Optional[str] = None,
        business_length: Optional[str] = None,
        is_new_relationship: Optional[bool] = None,
    ) -> bool:
        """
        Insert an edge if it doesn't already exist.
        Deduplicates on (source_key, target_key, relationship_type, discovered_from).
        Returns True if inserted, False if already existed.
        """
        table_id = self._table_id(TABLE_EDGES)

        # Check for existing edge first
        check_query = f"""
            SELECT 1 FROM `{table_id}`
            WHERE source_key = @source_key
              AND target_key = @target_key
              AND relationship_type = @relationship_type
              AND discovered_from = @discovered_from
            LIMIT 1
        """
        check_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("source_key", "STRING", source_key),
                bigquery.ScalarQueryParameter("target_key", "STRING", target_key),
                bigquery.ScalarQueryParameter("relationship_type", "STRING", relationship_type),
                bigquery.ScalarQueryParameter("discovered_from", "STRING", discovered_from),
            ]
        )
        existing = list(self.client.query(check_query, job_config=check_config).result())
        if existing:
            return False

        # Insert new edge
        rows = [{
            "source_type": source_type,
            "source_key": source_key,
            "target_type": target_type,
            "target_key": target_key,
            "relationship_type": relationship_type,
            "discovered_from": discovered_from,
            "total_shipments": total_shipments,
            "shipments_12m": shipments_12m,
            "shipment_pct_of_source": shipment_pct_of_source,
            "shipment_pct_of_target": shipment_pct_of_target,
            "total_weight": total_weight,
            "total_teus": total_teus,
            "supplier_country": supplier_country,
            "supplier_country_code": supplier_country_code,
            "most_recent_shipment": most_recent_shipment,
            "first_shipment": first_shipment,
            "business_length": business_length,
            "is_new_relationship": is_new_relationship,
            "ingested_at": datetime.utcnow().isoformat(),
        }]

        errors = self._streaming_insert_with_retry(table_id, rows)
        if errors:
            logger.error(f"[IMPORTYETI_BQ] Edge insert errors: {errors}")
            return False
        return True

    def get_company_suppliers(self, company_key: str) -> List[Dict[str, Any]]:
        """Get all suppliers for a company from edges (deduped)."""
        query = f"""
            WITH s_dedup AS (
                SELECT * EXCEPT(_rn) FROM (
                    SELECT *, ROW_NUMBER() OVER (
                        PARTITION BY importyeti_key ORDER BY updated_at DESC
                    ) AS _rn
                    FROM `{self._table_id(TABLE_SUPPLIERS)}`
                ) WHERE _rn = 1
            )
            SELECT
                s.name AS supplier_name,
                s.importyeti_key AS supplier_key,
                s.country AS supplier_country,
                s.total_shipments AS supplier_total_shipments,
                e.total_shipments,
                e.shipments_12m,
                e.shipment_pct_of_source,
                e.shipment_pct_of_target,
                e.most_recent_shipment,
                e.first_shipment,
                e.business_length,
                e.is_new_relationship
            FROM `{self._table_id(TABLE_EDGES)}` e
            JOIN s_dedup s ON e.target_key = s.importyeti_key
            WHERE e.source_key = @company_key
              AND e.relationship_type = 'imports_from'
            ORDER BY e.shipments_12m DESC NULLS LAST, e.total_shipments DESC NULLS LAST
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("company_key", "STRING", company_key),
            ]
        )
        rows = list(self.client.query(query, job_config=job_config).result())
        return [dict(r) for r in rows]

    def get_supplier_buyers(self, supplier_key: str) -> List[Dict[str, Any]]:
        """Get all buyers for a supplier from edges."""
        query = f"""
            SELECT
                c.name AS buyer_name,
                c.importyeti_key AS buyer_key,
                c.entity_type AS buyer_entity_type,
                c.total_shipments AS buyer_total_shipments,
                e.total_shipments,
                e.shipments_12m,
                e.shipment_pct_of_source,
                e.shipment_pct_of_target,
                e.most_recent_shipment,
                e.first_shipment,
                e.business_length,
                e.is_new_relationship
            FROM `{self._table_id(TABLE_EDGES)}` e
            JOIN `{self._table_id(TABLE_COMPANIES)}` c ON e.target_key = c.importyeti_key
            WHERE e.source_key = @supplier_key
              AND e.relationship_type = 'supplies_to'
            ORDER BY e.shipments_12m DESC NULLS LAST, e.total_shipments DESC NULLS LAST
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("supplier_key", "STRING", supplier_key),
            ]
        )
        rows = list(self.client.query(query, job_config=job_config).result())
        return [dict(r) for r in rows]

    # =============================================
    # INGESTION LOG
    # =============================================

    def log_ingestion(
        self,
        run_id: str,
        phase: str,
        entity_name: Optional[str] = None,
        entity_key: Optional[str] = None,
        status: str = "success",
        error_message: Optional[str] = None,
        api_credits_used: int = 0,
        duration_ms: Optional[int] = None,
    ):
        """Write an audit trail entry."""
        table_id = self._table_id(TABLE_INGESTION_LOG)
        rows = [{
            "run_id": run_id,
            "phase": phase,
            "entity_name": entity_name,
            "entity_key": entity_key,
            "status": status,
            "error_message": error_message,
            "api_credits_used": api_credits_used,
            "duration_ms": duration_ms,
            "timestamp": datetime.utcnow().isoformat(),
        }]
        errors = self._streaming_insert_with_retry(table_id, rows)
        if errors:
            logger.error(f"[IMPORTYETI_BQ] Ingestion log insert errors: {errors}")

    # =============================================
    # ANALYTICS QUERIES
    # =============================================

    def get_shared_suppliers(self, active_12m_only: bool = False) -> List[Dict[str, Any]]:
        """Query shared suppliers view."""
        view = "iy_v_shared_suppliers_12m" if active_12m_only else "iy_v_shared_suppliers"
        query = f"SELECT * FROM `{self._table_id(view)}` LIMIT 50"
        rows = list(self.client.query(query).result())
        return [dict(r) for r in rows]

    def get_competitor_activity(self) -> List[Dict[str, Any]]:
        """Query competitor activity view."""
        query = f"SELECT * FROM `{self._table_id('iy_v_competitor_activity_12m')}`"
        rows = list(self.client.query(query).result())
        return [dict(r) for r in rows]

    def get_buyer_overlap(self) -> List[Dict[str, Any]]:
        """Query buyer overlap view."""
        query = f"SELECT * FROM `{self._table_id('iy_v_buyer_overlap')}` LIMIT 50"
        rows = list(self.client.query(query).result())
        return [dict(r) for r in rows]

    def get_stats(self) -> Dict[str, Any]:
        """Get summary counts for all tables (deduped for suppliers)."""
        stats = {}
        for table_name in [TABLE_COMPANIES, TABLE_SUPPLIERS, TABLE_EDGES, TABLE_INGESTION_LOG]:
            table_id = self._table_id(table_name)
            try:
                if table_name == TABLE_SUPPLIERS:
                    query = f"SELECT COUNT(DISTINCT importyeti_key) as cnt FROM `{table_id}`"
                else:
                    query = f"SELECT COUNT(*) as cnt FROM `{table_id}`"
                rows = list(self.client.query(query).result())
                stats[table_name] = rows[0]["cnt"] if rows else 0
            except Exception:
                stats[table_name] = 0

        # Entity type breakdown
        try:
            query = f"""
                SELECT entity_type, COUNT(*) as cnt
                FROM `{self._table_id(TABLE_COMPANIES)}`
                GROUP BY entity_type
            """
            rows = list(self.client.query(query).result())
            stats["companies_by_type"] = {r["entity_type"]: r["cnt"] for r in rows}
        except Exception:
            stats["companies_by_type"] = {}

        # Edge type breakdown
        try:
            query = f"""
                SELECT relationship_type, COUNT(*) as cnt
                FROM `{self._table_id(TABLE_EDGES)}`
                GROUP BY relationship_type
            """
            rows = list(self.client.query(query).result())
            stats["edges_by_type"] = {r["relationship_type"]: r["cnt"] for r in rows}
        except Exception:
            stats["edges_by_type"] = {}

        return stats

    def get_tracked_companies_with_stats(self) -> List[Dict[str, Any]]:
        """Get all target + competitor companies with supplier count stats.

        Used by the Supply Network directory cards view.
        """
        query = f"""
            SELECT
                c.importyeti_key,
                c.name,
                c.entity_type,
                c.ticker,
                c.country,
                c.category,
                c.total_shipments,
                COALESCE(edge_stats.supplier_count, 0) AS supplier_count,
                COALESCE(edge_stats.active_suppliers_12m, 0) AS active_suppliers_12m
            FROM `{self._table_id(TABLE_COMPANIES)}` c
            LEFT JOIN (
                SELECT
                    source_key,
                    COUNT(DISTINCT target_key) AS supplier_count,
                    COUNT(DISTINCT CASE WHEN shipments_12m > 0 THEN target_key END) AS active_suppliers_12m
                FROM `{self._table_id(TABLE_EDGES)}`
                WHERE relationship_type = 'imports_from'
                GROUP BY source_key
            ) edge_stats ON c.importyeti_key = edge_stats.source_key
            WHERE c.entity_type IN ('target', 'competitor')
            ORDER BY
                CASE c.entity_type WHEN 'target' THEN 0 ELSE 1 END,
                c.name
        """
        try:
            rows = list(self.client.query(query).result())
            results = []
            for r in rows:
                row_dict = dict(r)
                # Convert datetimes
                for k, v in row_dict.items():
                    if hasattr(v, "isoformat"):
                        row_dict[k] = v.isoformat()
                results.append(row_dict)
            return results
        except Exception as e:
            logger.error(f"[IY_STORE] get_tracked_companies_with_stats error: {e}", exc_info=True)
            return []

    def search_by_name(self, name: str) -> Dict[str, List[Dict[str, Any]]]:
        """Search both companies and suppliers by name. Used by MCP tools."""
        return {
            "companies": self.search_companies_by_name(name),
            "suppliers": self.search_suppliers_by_name(name),
        }

    # =============================================
    # GRAPH DATA FOR VISUALIZATION
    # =============================================

    def get_network_graph_data(
        self,
        entity_types: Optional[List[str]] = None,
        min_shipments_12m: int = 0,
    ) -> Dict[str, Any]:
        """
        Get nodes and edges for the frontend network graph visualization.

        Returns:
            {"nodes": [...], "edges": [...], "stats": {...}}
        """
        # Get tracked companies as nodes
        if entity_types is None:
            entity_types = ["target", "competitor"]

        placeholders = ", ".join(f"'{et}'" for et in entity_types)

        # Company nodes
        company_query = f"""
            SELECT importyeti_key, name, entity_type, total_shipments, category, ticker
            FROM `{self._table_id(TABLE_COMPANIES)}`
            WHERE entity_type IN ({placeholders})
        """
        companies = list(self.client.query(company_query).result())

        nodes = []
        company_keys = set()
        for c in companies:
            company_keys.add(c["importyeti_key"])
            nodes.append({
                "id": c["importyeti_key"],
                "label": c["name"],
                "type": "company",
                "entity_type": c["entity_type"],
                "total_shipments": c["total_shipments"],
                "category": c["category"],
                "ticker": c["ticker"],
            })

        # Get edges for these companies -> their suppliers
        if company_keys:
            keys_list = ", ".join(f"'{k}'" for k in company_keys)
            edge_query = f"""
                WITH s_dedup AS (
                    SELECT * EXCEPT(_rn) FROM (
                        SELECT *, ROW_NUMBER() OVER (
                            PARTITION BY importyeti_key ORDER BY updated_at DESC
                        ) AS _rn
                        FROM `{self._table_id(TABLE_SUPPLIERS)}`
                    ) WHERE _rn = 1
                )
                SELECT
                    e.source_key, e.target_key, e.relationship_type,
                    e.total_shipments, e.shipments_12m,
                    s.name AS supplier_name, s.country AS supplier_country
                FROM `{self._table_id(TABLE_EDGES)}` e
                JOIN s_dedup s ON e.target_key = s.importyeti_key
                WHERE e.source_key IN ({keys_list})
                  AND e.relationship_type = 'imports_from'
                  AND COALESCE(e.shipments_12m, 0) >= @min_shipments
            """
            edge_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("min_shipments", "INT64", min_shipments_12m),
                ]
            )
            edges_data = list(self.client.query(edge_query, job_config=edge_config).result())

            # Add supplier nodes and edges
            supplier_keys_seen = set()
            edges = []
            for e in edges_data:
                if e["target_key"] not in supplier_keys_seen:
                    supplier_keys_seen.add(e["target_key"])
                    nodes.append({
                        "id": e["target_key"],
                        "label": e["supplier_name"],
                        "type": "supplier",
                        "country": e["supplier_country"],
                    })

                edges.append({
                    "source": e["source_key"],
                    "target": e["target_key"],
                    "relationship": e["relationship_type"],
                    "total_shipments": e["total_shipments"],
                    "shipments_12m": e["shipments_12m"],
                })
        else:
            edges = []

        return {
            "nodes": nodes,
            "edges": edges,
            "stats": {
                "total_companies": len([n for n in nodes if n["type"] == "company"]),
                "total_suppliers": len([n for n in nodes if n["type"] == "supplier"]),
                "total_edges": len(edges),
            },
        }
