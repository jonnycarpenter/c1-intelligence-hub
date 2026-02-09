"""
Ingestion Pipeline
==================
Orchestrates the full ImportYeti data ingestion in 4 phases:

Phase 1 — RESOLVE: Search ImportYeti for each entity name,
           find the correct entity, store in BigQuery.

Phase 2 — COMPANIES: For each resolved entity, pull the full
           company profile. Extract suppliers_table and create edges.

Phase 3 — SUPPLIERS: For each unique supplier discovered in Phase 2,
           pull the full supplier profile. Extract companies_table
           (downstream buyers) and create edges.

Phase 4 — STATS: Report on what was ingested.

Each phase is idempotent — you can re-run the pipeline and it will
upsert entities that are already in the database.

Usage:
    from app.ingestion.importyeti.ingestion import IngestionPipeline
    pipeline = IngestionPipeline(api_key="your-key")
    pipeline.run()
"""

import json
import time
import uuid
import logging
from typing import Optional

from .config.settings import (
    COMPETITORS_PATH,
    MAX_SUPPLIERS_PER_COMPANY,
    MAX_BUYERS_PER_SUPPLIER,
    MAX_SEARCH_RESULTS_TO_CONSIDER,
)
from .client import ImportYetiClient
from .bigquery_store import BigQueryStore

logger = logging.getLogger("importyeti_ingestion")


class IngestionPipeline:
    """
    Main pipeline orchestrator.

    Coordinates between the ImportYeti API client and BigQuery
    to build the full supply chain graph.
    """

    def __init__(self, api_key: str, db: Optional[BigQueryStore] = None):
        self.client = ImportYetiClient(api_key=api_key)
        self.db = db or BigQueryStore()
        self.run_id = str(uuid.uuid4())[:8]
        self.competitors_config = self._load_competitors_config()

        # Tracking
        self.resolved_companies = {}   # name -> importyeti_key
        self.discovered_suppliers = set()

    def _load_competitors_config(self) -> dict:
        """Load competitor definitions from JSON config."""
        with open(COMPETITORS_PATH) as f:
            return json.load(f)

    # =============================================
    # MAIN ENTRY POINT
    # =============================================

    def run(
        self,
        skip_supplier_details: bool = False,
        single_company: Optional[str] = None,
    ):
        """
        Run the full ingestion pipeline.

        Args:
            skip_supplier_details: If True, skip Phase 3 (saves credits).
            single_company: If set, only process this one entity (by name).
        """
        logger.info(f"{'='*60}")
        logger.info(f"[IMPORTYETI] INGESTION PIPELINE — Run ID: {self.run_id}")
        logger.info(f"{'='*60}")

        # Ensure BQ tables exist
        self.db.initialize()

        # --- Phase 1: Resolve entity names ---
        self._phase_1_resolve(single_company=single_company)

        # --- Phase 2: Pull company profiles + supplier edges ---
        self._phase_2_companies()

        # --- Phase 3: Pull supplier profiles + buyer edges ---
        if not skip_supplier_details:
            self._phase_3_suppliers()
        else:
            logger.info("[IMPORTYETI] Phase 3 SKIPPED (skip_supplier_details=True)")

        # --- Phase 4: Report ---
        self._phase_4_stats()

        logger.info(
            f"[IMPORTYETI] Pipeline complete. Credits used: "
            f"{self.client.total_credits_used}"
        )

    # =============================================
    # PHASE 1: RESOLVE ENTITY NAMES
    # =============================================

    def _phase_1_resolve(self, single_company: Optional[str] = None):
        """
        For each entity in the config, search ImportYeti to find
        the correct company and store it in BigQuery.
        """
        logger.info(f"\n{'_'*60}")
        logger.info("[IMPORTYETI] PHASE 1: Resolving entity names")
        logger.info(f"{'_'*60}")

        # Resolve target companies
        for target in self.competitors_config.get("target_companies", []):
            if single_company and target["name"].lower() != single_company.lower():
                continue
            self._resolve_single_company(
                name=target["name"],
                search_terms=target["search_terms"],
                entity_type="target",
                category=target.get("category"),
                notes=target.get("notes"),
            )

        # Resolve competitors
        for comp in self.competitors_config["competitors"]:
            if single_company and comp["name"].lower() != single_company.lower():
                continue
            self._resolve_single_company(
                name=comp["name"],
                search_terms=comp["search_terms"],
                entity_type="competitor",
                category=comp.get("category"),
                ticker=comp.get("ticker"),
                notes=comp.get("notes"),
            )

        logger.info(
            f"[IMPORTYETI] Phase 1 complete: "
            f"{len(self.resolved_companies)} companies resolved"
        )

    def _resolve_single_company(
        self,
        name: str,
        search_terms: list,
        entity_type: str,
        category: Optional[str] = None,
        ticker: Optional[str] = None,
        notes: Optional[str] = None,
    ):
        """
        Search ImportYeti for a company and store the best match.
        Tries each search term in order until a match is found.
        """
        start = time.time()
        logger.info(f"  Resolving: {name}")

        best_match = None

        for term in search_terms:
            data, meta = self.client.search_company(term)

            if meta["status"] != "success" or not data:
                logger.warning(f"    Search term '{term}' returned no results")
                continue

            candidates = data[:MAX_SEARCH_RESULTS_TO_CONSIDER]

            for candidate in candidates:
                if (
                    best_match is None
                    or candidate.get("totalShipments", 0)
                    > best_match.get("totalShipments", 0)
                ):
                    best_match = candidate

            if best_match:
                break

        if not best_match:
            logger.error(f"    FAILED to resolve: {name}")
            self.db.log_ingestion(
                run_id=self.run_id,
                phase="resolve",
                entity_name=name,
                entity_key=None,
                status="error",
                error_message="No matching company found in ImportYeti",
                duration_ms=int((time.time() - start) * 1000),
            )
            return

        # Extract importyeti_key
        iy_key = best_match.get("key", "").strip("/")
        if not iy_key.startswith("company/"):
            iy_key = f"company/{iy_key}"

        logger.info(
            f"    Resolved -> {best_match['title']} "
            f"(key: {iy_key}, shipments: {best_match.get('totalShipments', 'N/A')})"
        )

        # Store in BigQuery
        self.db.upsert_company(
            importyeti_key=iy_key,
            name=best_match["title"],
            entity_type=entity_type,
            address=best_match.get("address"),
            country=best_match.get("country", "United States"),
            country_code=best_match.get("countryCode", "US"),
            total_shipments=best_match.get("totalShipments"),
            category=category,
            ticker=ticker,
            notes=notes,
        )

        self.resolved_companies[name] = iy_key

        self.db.log_ingestion(
            run_id=self.run_id,
            phase="resolve",
            entity_name=name,
            entity_key=iy_key,
            status="success",
            api_credits_used=0,
            duration_ms=int((time.time() - start) * 1000),
        )

    # =============================================
    # PHASE 2: PULL COMPANY PROFILES
    # =============================================

    def _phase_2_companies(self):
        """
        For each resolved company, pull the full ImportYeti profile.
        Extract suppliers_table and create 'imports_from' edges.
        """
        logger.info(f"\n{'_'*60}")
        logger.info("[IMPORTYETI] PHASE 2: Pulling company profiles & supplier edges")
        logger.info(f"{'_'*60}")

        for name, iy_key in self.resolved_companies.items():
            self._process_company_profile(name, iy_key)

        logger.info(
            f"[IMPORTYETI] Phase 2 complete: "
            f"{len(self.discovered_suppliers)} unique suppliers discovered"
        )

    def _process_company_profile(self, name: str, iy_key: str):
        """Pull a company's full profile and extract supplier relationships."""
        start = time.time()
        logger.info(f"  Pulling profile: {name}")

        slug = iy_key.replace("company/", "")
        data, meta = self.client.get_company(slug)

        if meta["status"] != "success" or not data:
            logger.error(f"    FAILED to get profile for {name}: {meta.get('error')}")
            self.db.log_ingestion(
                run_id=self.run_id,
                phase="companies",
                entity_name=name,
                entity_key=iy_key,
                status="error",
                error_message=meta.get("error"),
                api_credits_used=meta.get("credits_used", 0),
                duration_ms=int((time.time() - start) * 1000),
            )
            return

        # Update company with full profile data
        shipments_by_country = None
        if "map_table" in data and "shipments_by_country" in data["map_table"]:
            shipments_by_country = data["map_table"]["shipments_by_country"]

        self.db.upsert_company(
            importyeti_key=iy_key,
            name=data.get("title", name),
            also_known_names=data.get("also_known_names"),
            address=data.get("address"),
            website=data.get("website"),
            phone_number=data.get("phone_number"),
            total_shipments=data.get("total_shipments"),
            shipments_by_country=shipments_by_country,
            raw_api_response=data,
        )

        # --- Extract suppliers_table -> batch insert suppliers + edges ---
        suppliers_table = data.get("suppliers_table", [])
        if not suppliers_table:
            logger.warning(f"    No suppliers_table found for {name}")
        else:
            cap = MAX_SUPPLIERS_PER_COMPANY or len(suppliers_table)
            suppliers_to_process = suppliers_table[:cap]
            logger.info(
                f"    Found {len(suppliers_table)} suppliers, "
                f"processing top {len(suppliers_to_process)}"
            )

            # Collect suppliers and edges for batch insert
            supplier_records = []
            edge_records = []

            for supplier_row in suppliers_to_process:
                supplier_key = supplier_row.get("key", "").strip("/")
                if not supplier_key:
                    continue
                if not supplier_key.startswith("supplier/"):
                    supplier_key = f"supplier/{supplier_key}"

                supplier_records.append({
                    "importyeti_key": supplier_key,
                    "name": supplier_row.get("supplier_name", "Unknown"),
                    "address": supplier_row.get("supplier_address"),
                    "address_country": supplier_row.get("supplier_address_country"),
                    "country": supplier_row.get("country"),
                    "country_code": supplier_row.get("country_code"),
                    "total_shipments": supplier_row.get("total_shipments_supplier"),
                })

                edge_records.append({
                    "source_type": "company",
                    "source_key": iy_key,
                    "target_type": "supplier",
                    "target_key": supplier_key,
                    "relationship_type": "imports_from",
                    "discovered_from": "company_profile",
                    "total_shipments": supplier_row.get("total_shipments_company"),
                    "shipments_12m": supplier_row.get("shipments_12m"),
                    "shipment_pct_of_source": supplier_row.get("shipments_percents_company"),
                    "shipment_pct_of_target": supplier_row.get("shipments_percents_supplier"),
                    "total_weight": supplier_row.get("total_weight"),
                    "total_teus": supplier_row.get("total_teus"),
                    "supplier_country": supplier_row.get("country"),
                    "supplier_country_code": supplier_row.get("country_code"),
                    "most_recent_shipment": supplier_row.get("most_recent_shipment"),
                    "first_shipment": supplier_row.get("first_shipment"),
                    "business_length": supplier_row.get("business_length"),
                    "is_new_relationship": supplier_row.get("is_new_supplier"),
                })

                self.discovered_suppliers.add(supplier_key)

            # Batch write — one streaming insert each instead of N MERGE queries
            self.db.batch_insert_suppliers(supplier_records)
            self.db.batch_insert_edges(edge_records)
            logger.info(
                f"    Batch wrote {len(supplier_records)} suppliers + "
                f"{len(edge_records)} edges for {name}"
            )

        self.db.log_ingestion(
            run_id=self.run_id,
            phase="companies",
            entity_name=name,
            entity_key=iy_key,
            status="success",
            api_credits_used=meta.get("credits_used", 0),
            duration_ms=int((time.time() - start) * 1000),
        )

    def _process_supplier_from_company_profile(
        self, company_key: str, supplier_row: dict
    ):
        """
        Process a single row from a company's suppliers_table.
        Creates a supplier record and an 'imports_from' edge.
        """
        supplier_key = supplier_row.get("key", "").strip("/")
        if not supplier_key:
            logger.warning(
                f"    Supplier row missing 'key': "
                f"{supplier_row.get('supplier_name')}"
            )
            return

        if not supplier_key.startswith("supplier/"):
            supplier_key = f"supplier/{supplier_key}"

        # Create minimal supplier record (enriched in Phase 3)
        self.db.upsert_supplier(
            importyeti_key=supplier_key,
            name=supplier_row.get("supplier_name", "Unknown"),
            address=supplier_row.get("supplier_address"),
            address_country=supplier_row.get("supplier_address_country"),
            country=supplier_row.get("country"),
            country_code=supplier_row.get("country_code"),
            total_shipments=supplier_row.get("total_shipments_supplier"),
        )

        # Create edge: company --[imports_from]--> supplier
        self.db.insert_edge(
            source_type="company",
            source_key=company_key,
            target_type="supplier",
            target_key=supplier_key,
            relationship_type="imports_from",
            discovered_from="company_profile",
            total_shipments=supplier_row.get("total_shipments_company"),
            shipments_12m=supplier_row.get("shipments_12m"),
            shipment_pct_of_source=supplier_row.get("shipments_percents_company"),
            shipment_pct_of_target=supplier_row.get("shipments_percents_supplier"),
            total_weight=supplier_row.get("total_weight"),
            total_teus=supplier_row.get("total_teus"),
            supplier_country=supplier_row.get("country"),
            supplier_country_code=supplier_row.get("country_code"),
            most_recent_shipment=supplier_row.get("most_recent_shipment"),
            first_shipment=supplier_row.get("first_shipment"),
            business_length=supplier_row.get("business_length"),
            is_new_relationship=supplier_row.get("is_new_supplier"),
        )

        self.discovered_suppliers.add(supplier_key)

    # =============================================
    # PHASE 3: PULL SUPPLIER PROFILES
    # =============================================

    def _phase_3_suppliers(self):
        """
        For each unique supplier discovered in Phase 2, pull the full
        profile and extract downstream buyers.
        """
        logger.info(f"\n{'_'*60}")
        logger.info("[IMPORTYETI] PHASE 3: Pulling supplier profiles & buyer edges")
        logger.info(f"{'_'*60}")

        # Get all supplier keys from BQ (supports resume)
        all_supplier_keys = set(self.db.get_all_supplier_keys())

        # Check which still need full profiles
        suppliers_to_process = []
        for key in all_supplier_keys:
            existing = self.db.get_supplier(key)
            if existing and existing.get("raw_api_response") is None:
                suppliers_to_process.append(key)

        # If this is a fresh run, use the discovered set
        if not suppliers_to_process:
            suppliers_to_process = list(self.discovered_suppliers)

        total = len(suppliers_to_process)
        logger.info(f"  {total} suppliers to process")

        for i, supplier_key in enumerate(suppliers_to_process, 1):
            logger.info(f"  [{i}/{total}] Processing {supplier_key}")
            self._process_supplier_profile(supplier_key)

            # Progress checkpoint every 50
            if i % 50 == 0:
                credits = self.client.get_credit_summary()
                logger.info(
                    f"  -- Checkpoint: {i}/{total} suppliers done | "
                    f"Credits used: {credits['total_credits_used']}"
                )

        logger.info("[IMPORTYETI] Phase 3 complete")

    def _process_supplier_profile(self, supplier_key: str):
        """Pull a supplier's full profile and extract buyer relationships."""
        start = time.time()
        slug = supplier_key.replace("supplier/", "")
        data, meta = self.client.get_supplier(slug)

        if meta["status"] != "success" or not data:
            logger.warning(
                f"    Failed to get supplier {supplier_key}: {meta.get('error')}"
            )
            self.db.log_ingestion(
                run_id=self.run_id,
                phase="suppliers",
                entity_name=slug,
                entity_key=supplier_key,
                status="error" if meta["status"] == "error" else "skipped",
                error_message=meta.get("error"),
                api_credits_used=meta.get("credits_used", 0),
                duration_ms=int((time.time() - start) * 1000),
            )
            return

        # Update supplier with full profile via streaming insert
        # (Cannot use MERGE — Phase 2 rows are still in BQ streaming buffer)
        self.db.batch_insert_suppliers([{
            "importyeti_key": supplier_key,
            "name": data.get("title", slug),
            "also_known_names": data.get("also_known_names"),
            "address": data.get("address"),
            "address_country": data.get("address_country"),
            "address_country_code": data.get("address_country_code"),
            "country": data.get("country"),
            "country_code": data.get("country_code"),
            "website": data.get("website"),
            "phone_number": data.get("phone_number"),
            "total_shipments": data.get("total_shipments"),
            "raw_api_response": data,
        }])

        # --- Extract companies_table -> batch insert buyers + edges ---
        companies_table = data.get("companies_table", [])
        if not companies_table:
            logger.debug(f"    No companies_table for {supplier_key}")
        else:
            cap = MAX_BUYERS_PER_SUPPLIER or len(companies_table)
            buyers_to_process = companies_table[:cap]

            # Collect buyers and edges for batch insert
            buyer_records = []
            edge_records = []

            for buyer_row in buyers_to_process:
                buyer_key = buyer_row.get("key", "").strip("/")
                if not buyer_key:
                    continue

                if buyer_key.startswith("company?name="):
                    buyer_key = "company/" + buyer_key.replace("company?name=", "")
                elif not buyer_key.startswith("company/"):
                    buyer_key = f"company/{buyer_key}"

                buyer_records.append({
                    "importyeti_key": buyer_key,
                    "name": buyer_row.get("company_name", "Unknown"),
                    "entity_type": "discovered",
                    "address": buyer_row.get("company_address"),
                    "country": buyer_row.get("company_address_country", "United States"),
                })

                edge_records.append({
                    "source_type": "supplier",
                    "source_key": supplier_key,
                    "target_type": "company",
                    "target_key": buyer_key,
                    "relationship_type": "supplies_to",
                    "discovered_from": "supplier_profile",
                    "total_shipments": buyer_row.get("total_shipments_supplier"),
                    "shipments_12m": buyer_row.get("shipments_12m"),
                    "shipment_pct_of_source": buyer_row.get("shipments_percents_supplier"),
                    "shipment_pct_of_target": buyer_row.get("shipments_percents_company"),
                    "total_weight": buyer_row.get("total_weight"),
                    "total_teus": buyer_row.get("total_teus"),
                    "most_recent_shipment": buyer_row.get("most_recent_shipment"),
                    "first_shipment": buyer_row.get("first_shipment"),
                    "business_length": buyer_row.get("business_length"),
                    "is_new_relationship": buyer_row.get("is_new_company"),
                })

            # Batch write
            self.db.batch_insert_companies(buyer_records)
            self.db.batch_insert_edges(edge_records)

        self.db.log_ingestion(
            run_id=self.run_id,
            phase="suppliers",
            entity_name=data.get("title", slug),
            entity_key=supplier_key,
            status="success",
            api_credits_used=meta.get("credits_used", 0),
            duration_ms=int((time.time() - start) * 1000),
        )

    def _process_buyer_from_supplier_profile(
        self, supplier_key: str, buyer_row: dict
    ):
        """
        Process a single row from a supplier's companies_table.
        Creates a buyer record and a 'supplies_to' edge.
        """
        buyer_key = buyer_row.get("key", "").strip("/")
        if not buyer_key:
            return

        # Normalize key formats
        if buyer_key.startswith("company?name="):
            buyer_key = "company/" + buyer_key.replace("company?name=", "")
        elif not buyer_key.startswith("company/"):
            buyer_key = f"company/{buyer_key}"

        # Create/update buyer as 'discovered'
        self.db.upsert_company(
            importyeti_key=buyer_key,
            name=buyer_row.get("company_name", "Unknown"),
            entity_type="discovered",
            address=buyer_row.get("company_address"),
            country=buyer_row.get("company_address_country", "United States"),
        )

        # Create edge: supplier --[supplies_to]--> buyer
        self.db.insert_edge(
            source_type="supplier",
            source_key=supplier_key,
            target_type="company",
            target_key=buyer_key,
            relationship_type="supplies_to",
            discovered_from="supplier_profile",
            total_shipments=buyer_row.get("total_shipments_supplier"),
            shipments_12m=buyer_row.get("shipments_12m"),
            shipment_pct_of_source=buyer_row.get("shipments_percents_supplier"),
            shipment_pct_of_target=buyer_row.get("shipments_percents_company"),
            total_weight=buyer_row.get("total_weight"),
            total_teus=buyer_row.get("total_teus"),
            most_recent_shipment=buyer_row.get("most_recent_shipment"),
            first_shipment=buyer_row.get("first_shipment"),
            business_length=buyer_row.get("business_length"),
            is_new_relationship=buyer_row.get("is_new_company"),
        )

    # =============================================
    # PHASE 4: STATS & REPORTING
    # =============================================

    def _phase_4_stats(self):
        """Print a summary of what was ingested."""
        logger.info(f"\n{'_'*60}")
        logger.info("[IMPORTYETI] PHASE 4: Ingestion Summary")
        logger.info(f"{'_'*60}")

        stats = self.db.get_stats()
        credits = self.client.get_credit_summary()

        logger.info(f"  BigQuery Dataset: {self.db.project_id}.{self.db.dataset_id}")
        logger.info(f"  Run ID:           {self.run_id}")
        logger.info(f"")
        logger.info(f"  Companies:  {stats.get('iy_companies', 0)}")
        for etype, count in stats.get("companies_by_type", {}).items():
            logger.info(f"    - {etype}: {count}")
        logger.info(f"  Suppliers:  {stats.get('iy_suppliers', 0)}")
        logger.info(f"  Edges:      {stats.get('iy_edges', 0)}")
        for rtype, count in stats.get("edges_by_type", {}).items():
            logger.info(f"    - {rtype}: {count}")
        logger.info(f"")
        logger.info(f"  API Credits Used:      {credits['total_credits_used']}")
        logger.info(f"  API Credits Remaining: {credits['credits_remaining']}")
        logger.info(f"{'_'*60}")
