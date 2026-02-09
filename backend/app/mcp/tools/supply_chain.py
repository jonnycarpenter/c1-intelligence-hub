"""
Supply Chain MCP Tools — ImportYeti Trade Intelligence
======================================================

4 agent tools for dynamic ad-hoc supply chain lookups using ImportYeti data.
Tools are designed for a "search → confirm → fetch" workflow:

1. search_supply_chain_entity (0 credits) — Find companies/suppliers by name
2. get_company_supply_chain (1 credit)   — Fetch full supplier network for a US company
3. get_supplier_customers (1 credit)     — Fetch full buyer network for an overseas supplier
4. query_supply_chain_db (0 credits)     — Query cached data (8 query types)

The agent calls search first, presents candidates to the user, then fetches
the full network for the confirmed entity. Results are cached in BigQuery
so subsequent queries are free.

Usage:
    These tools are registered in app/mcp/server.py and available to all agents.
"""

import json
import logging
from typing import Optional

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


def _get_store():
    """Lazy-load BigQuery store to avoid import-time initialization."""
    from app.ingestion.importyeti.bigquery_store import BigQueryStore
    return BigQueryStore()


def _get_client():
    """Lazy-load ImportYeti API client."""
    from app.ingestion.importyeti.config.settings import get_importyeti_api_key
    from app.ingestion.importyeti.client import ImportYetiClient

    api_key = get_importyeti_api_key()
    if not api_key:
        return None
    return ImportYetiClient(api_key=api_key)


def _format_supplier_table(suppliers: list) -> str:
    """Format supplier list as markdown table."""
    if not suppliers:
        return "_No suppliers found._"

    lines = [
        "| Supplier | Country | Shipments (12m) | Total | % of Company |",
        "|----------|---------|-----------------|-------|--------------|",
    ]
    for s in suppliers[:30]:
        name = s.get("supplier_name") or s.get("name", "Unknown")
        country = s.get("supplier_country") or s.get("country", "—")
        ship_12m = s.get("shipments_12m") or "—"
        total = s.get("total_shipments") or "—"
        pct = s.get("shipment_pct_of_source") or s.get("pct_of_company") or "—"
        if isinstance(pct, (int, float)):
            pct = f"{pct:.1f}%"
        lines.append(f"| {name} | {country} | {ship_12m} | {total} | {pct} |")

    if len(suppliers) > 30:
        lines.append(f"| ... | _({len(suppliers) - 30} more)_ | | | |")

    return "\n".join(lines)


def _format_buyer_table(buyers: list) -> str:
    """Format buyer list as markdown table."""
    if not buyers:
        return "_No buyers found._"

    lines = [
        "| Buyer | Type | Shipments (12m) | Total | % of Supplier |",
        "|-------|------|-----------------|-------|---------------|",
    ]
    for b in buyers[:30]:
        name = b.get("buyer_name") or b.get("name", "Unknown")
        etype = b.get("buyer_entity_type", "discovered")
        # Highlight tracked entities
        if etype == "target":
            name = f"**[C1]** {name}"
        elif etype == "competitor":
            name = f"**[COMP]** {name}"

        ship_12m = b.get("shipments_12m") or "—"
        total = b.get("total_shipments") or "—"
        pct = b.get("shipment_pct_of_source") or b.get("pct_of_supplier") or "—"
        if isinstance(pct, (int, float)):
            pct = f"{pct:.1f}%"
        lines.append(f"| {name} | {etype} | {ship_12m} | {total} | {pct} |")

    if len(buyers) > 30:
        lines.append(f"| ... | | _({len(buyers) - 30} more)_ | | |")

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────
# TOOL 1: Search Entity (0 credits)
# ─────────────────────────────────────────────────────────

@tool
async def search_supply_chain_entity(
    name: str,
    entity_type: str = "auto",
) -> str:
    """
    Search ImportYeti for a company (US importer) or supplier (overseas exporter)
    by name. Returns matching candidates with ImportYeti slugs, shipment counts,
    and whether they already exist in the local database cache.

    Costs 0 API credits. Always call this FIRST to identify the correct entity
    before calling get_company_supply_chain or get_supplier_customers.

    Args:
        name: Company or supplier name to search for (e.g., "Hexcel", "Jushi", "Toray")
        entity_type: "company" for US importers, "supplier" for overseas exporters,
                     "auto" to search both. Default: "auto"

    Returns:
        JSON with matching entities, their slugs, shipment counts, and cache status.
    """
    try:
        store = _get_store()
        client = _get_client()

        matches = []
        seen_keys = set()

        # Step 1: Check BigQuery cache first
        local_results = store.search_by_name(name)

        for company in local_results.get("companies", []):
            key = company["importyeti_key"]
            seen_keys.add(key)
            matches.append({
                "name": company["name"],
                "slug": key.replace("company/", ""),
                "importyeti_key": key,
                "entity_type": "company",
                "country": company.get("country", "US"),
                "total_shipments": company.get("total_shipments"),
                "in_local_db": True,
                "has_full_profile": company.get("raw_api_response") is not None,
                "local_entity_type": company.get("entity_type"),
            })

        for supplier in local_results.get("suppliers", []):
            key = supplier["importyeti_key"]
            seen_keys.add(key)
            matches.append({
                "name": supplier["name"],
                "slug": key.replace("supplier/", ""),
                "importyeti_key": key,
                "entity_type": "supplier",
                "country": supplier.get("country") or supplier.get("address_country", "Unknown"),
                "total_shipments": supplier.get("total_shipments"),
                "in_local_db": True,
                "has_full_profile": supplier.get("raw_api_response") is not None,
            })

        # Step 2: Search ImportYeti API (0 credits)
        credits_remaining = None

        if client:
            if entity_type in ("company", "auto"):
                try:
                    data, meta = client.search_company(name)
                    credits_remaining = meta.get("credits_remaining")
                    if data:
                        for item in data[:10]:
                            iy_key = item.get("key", "").strip("/")
                            if not iy_key.startswith("company/"):
                                iy_key = f"company/{iy_key}"
                            if iy_key in seen_keys:
                                continue
                            seen_keys.add(iy_key)

                            matches.append({
                                "name": item.get("title", "Unknown"),
                                "slug": iy_key.replace("company/", ""),
                                "importyeti_key": iy_key,
                                "entity_type": "company",
                                "country": item.get("countryCode", "US"),
                                "address": item.get("address"),
                                "total_shipments": item.get("totalShipments", 0),
                                "in_local_db": False,
                                "has_full_profile": False,
                            })
                except Exception as e:
                    logger.warning(f"[SUPPLY_CHAIN] Company search error: {e}")

            if entity_type in ("supplier", "auto"):
                try:
                    data, meta = client.search_supplier(name)
                    credits_remaining = meta.get("credits_remaining")
                    if data:
                        for item in data[:10]:
                            iy_key = item.get("key", "").strip("/")
                            if not iy_key.startswith("supplier/"):
                                iy_key = f"supplier/{iy_key}"
                            if iy_key in seen_keys:
                                continue
                            seen_keys.add(iy_key)

                            matches.append({
                                "name": item.get("title", "Unknown"),
                                "slug": iy_key.replace("supplier/", ""),
                                "importyeti_key": iy_key,
                                "entity_type": "supplier",
                                "country": item.get("countryCode", "Unknown"),
                                "address": item.get("address"),
                                "total_shipments": item.get("totalShipments", 0),
                                "in_local_db": False,
                                "has_full_profile": False,
                            })
                except Exception as e:
                    logger.warning(f"[SUPPLY_CHAIN] Supplier search error: {e}")

        # Sort: local DB matches first, then by shipments
        matches.sort(key=lambda m: (not m.get("in_local_db", False), -(m.get("total_shipments") or 0)))

        result = {
            "matches": matches[:20],
            "total_matches": len(matches),
            "credits_used": 0,
            "credits_remaining": credits_remaining,
        }

        return json.dumps(result, indent=2, default=str)

    except Exception as e:
        logger.error(f"[SUPPLY_CHAIN] search_entity error: {e}", exc_info=True)
        return json.dumps({"error": str(e)})


# ─────────────────────────────────────────────────────────
# TOOL 2: Get Company Network (1 credit)
# ─────────────────────────────────────────────────────────

@tool
async def get_company_supply_chain(
    slug: str,
    max_suppliers: int = 50,
) -> str:
    """
    Fetch the full supplier network for a US company from ImportYeti.
    Costs 1 API credit. Results are cached in BigQuery for future free lookups.

    Use search_supply_chain_entity first to find the correct slug.

    Args:
        slug: ImportYeti company slug (e.g., 'hexcel-corporation', 'owens-corning').
              Get this from search_supply_chain_entity results.
        max_suppliers: Maximum suppliers to return. Default: 50. Use -1 for all.

    Returns:
        JSON with company profile, supplier list with shipment volumes/countries,
        summary statistics, and formatted markdown table.
    """
    try:
        store = _get_store()
        client = _get_client()

        if not client:
            # Try returning cached data
            iy_key = f"company/{slug}"
            cached = store.get_company_suppliers(iy_key)
            if cached:
                company = store.get_company(iy_key)
                return json.dumps({
                    "company": {"name": company["name"] if company else slug, "slug": slug},
                    "suppliers": cached[:max_suppliers] if max_suppliers > 0 else cached,
                    "summary": {"total_suppliers": len(cached), "source": "cache"},
                    "credits_used": 0,
                    "formatted_table": _format_supplier_table(cached[:max_suppliers] if max_suppliers > 0 else cached),
                }, indent=2, default=str)
            return json.dumps({"error": "No API key configured and no cached data available."})

        # Call the API
        data, meta = client.get_company(slug)

        if meta["status"] != "success" or not data:
            return json.dumps({
                "error": f"Failed to fetch company '{slug}': {meta.get('error')}",
                "credits_used": meta.get("credits_used", 0),
            })

        # Persist company to BigQuery
        iy_key = f"company/{slug}"
        shipments_by_country = None
        if "map_table" in data and "shipments_by_country" in data["map_table"]:
            shipments_by_country = data["map_table"]["shipments_by_country"]

        store.upsert_company(
            importyeti_key=iy_key,
            name=data.get("title", slug),
            entity_type="discovered",
            also_known_names=data.get("also_known_names"),
            address=data.get("address"),
            website=data.get("website"),
            phone_number=data.get("phone_number"),
            total_shipments=data.get("total_shipments"),
            shipments_by_country=shipments_by_country,
            raw_api_response=data,
        )

        # Extract and persist suppliers
        suppliers_table = data.get("suppliers_table", [])
        cap = len(suppliers_table) if max_suppliers == -1 else min(max_suppliers, len(suppliers_table))
        suppliers_to_process = suppliers_table[:cap]

        suppliers_output = []
        country_counts = {}
        active_12m = 0

        for row in suppliers_to_process:
            supplier_key = row.get("key", "").strip("/")
            if not supplier_key:
                continue
            if not supplier_key.startswith("supplier/"):
                supplier_key = f"supplier/{supplier_key}"

            country = row.get("country") or row.get("supplier_address_country", "Unknown")

            store.upsert_supplier(
                importyeti_key=supplier_key,
                name=row.get("supplier_name", "Unknown"),
                address=row.get("supplier_address"),
                address_country=row.get("supplier_address_country"),
                country=country,
                country_code=row.get("country_code"),
                total_shipments=row.get("total_shipments_supplier"),
            )

            store.insert_edge(
                source_type="company",
                source_key=iy_key,
                target_type="supplier",
                target_key=supplier_key,
                relationship_type="imports_from",
                discovered_from="company_profile",
                total_shipments=row.get("total_shipments_company"),
                shipments_12m=row.get("shipments_12m"),
                shipment_pct_of_source=row.get("shipments_percents_company"),
                shipment_pct_of_target=row.get("shipments_percents_supplier"),
                total_weight=row.get("total_weight"),
                total_teus=row.get("total_teus"),
                supplier_country=country,
                supplier_country_code=row.get("country_code"),
                most_recent_shipment=row.get("most_recent_shipment"),
                first_shipment=row.get("first_shipment"),
                business_length=row.get("business_length"),
                is_new_relationship=row.get("is_new_supplier"),
            )

            ship_12m = row.get("shipments_12m", 0) or 0
            if ship_12m > 0:
                active_12m += 1
            country_counts[country] = country_counts.get(country, 0) + 1

            suppliers_output.append({
                "name": row.get("supplier_name", "Unknown"),
                "slug": supplier_key.replace("supplier/", ""),
                "country": country,
                "total_shipments": row.get("total_shipments_company"),
                "shipments_12m": row.get("shipments_12m"),
                "pct_of_company": row.get("shipments_percents_company"),
                "most_recent_shipment": row.get("most_recent_shipment"),
                "business_length": row.get("business_length"),
            })

        top_countries = dict(sorted(country_counts.items(), key=lambda x: -x[1])[:10])

        result = {
            "company": {
                "name": data.get("title", slug),
                "slug": slug,
                "importyeti_key": iy_key,
                "address": data.get("address"),
                "total_shipments": data.get("total_shipments"),
            },
            "suppliers": suppliers_output,
            "summary": {
                "total_suppliers_available": len(suppliers_table),
                "suppliers_returned": len(suppliers_output),
                "top_countries": top_countries,
                "active_12m": active_12m,
            },
            "credits_used": meta.get("credits_used", 1),
            "credits_remaining": meta.get("credits_remaining"),
            "saved_to_cache": True,
            "formatted_table": _format_supplier_table(suppliers_output),
        }

        return json.dumps(result, indent=2, default=str)

    except Exception as e:
        logger.error(f"[SUPPLY_CHAIN] get_company_network error: {e}", exc_info=True)
        return json.dumps({"error": str(e)})


# ─────────────────────────────────────────────────────────
# TOOL 3: Get Supplier Network (1 credit)
# ─────────────────────────────────────────────────────────

@tool
async def get_supplier_customers(
    slug: str,
    max_buyers: int = 50,
) -> str:
    """
    Fetch the full buyer (US importer) network for an overseas supplier from ImportYeti.
    Costs 1 API credit. Results are cached in BigQuery for future free lookups.

    Reveals which US companies buy from this supplier — highlights if any are
    Composites One (target) or tracked competitors.

    Args:
        slug: ImportYeti supplier slug (e.g., 'jushi-group-co-ltd', 'toray-industries').
              Get this from search_supply_chain_entity results.
        max_buyers: Maximum buyers to return. Default: 50. Use -1 for all.

    Returns:
        JSON with supplier profile, buyer list with entity type annotations
        (target/competitor/discovered), summary statistics, and formatted markdown table.
    """
    try:
        store = _get_store()
        client = _get_client()

        if not client:
            # Try returning cached data
            supplier_key = f"supplier/{slug}"
            cached = store.get_supplier_buyers(supplier_key)
            if cached:
                supplier = store.get_supplier(supplier_key)
                return json.dumps({
                    "supplier": {"name": supplier["name"] if supplier else slug, "slug": slug},
                    "buyers": cached[:max_buyers] if max_buyers > 0 else cached,
                    "summary": {"total_buyers": len(cached), "source": "cache"},
                    "credits_used": 0,
                    "formatted_table": _format_buyer_table(cached[:max_buyers] if max_buyers > 0 else cached),
                }, indent=2, default=str)
            return json.dumps({"error": "No API key configured and no cached data available."})

        data, meta = client.get_supplier(slug)

        if meta["status"] != "success" or not data:
            return json.dumps({
                "error": f"Failed to fetch supplier '{slug}': {meta.get('error')}",
                "credits_used": meta.get("credits_used", 0),
            })

        # Persist supplier
        supplier_key = f"supplier/{slug}"
        store.upsert_supplier(
            importyeti_key=supplier_key,
            name=data.get("title", slug),
            also_known_names=data.get("also_known_names"),
            address=data.get("address"),
            address_country=data.get("address_country"),
            address_country_code=data.get("address_country_code"),
            country=data.get("country"),
            country_code=data.get("country_code"),
            website=data.get("website"),
            phone_number=data.get("phone_number"),
            total_shipments=data.get("total_shipments"),
            raw_api_response=data,
        )

        # Extract and persist buyers
        companies_table = data.get("companies_table", [])
        cap = len(companies_table) if max_buyers == -1 else min(max_buyers, len(companies_table))
        buyers_to_process = companies_table[:cap]

        buyers_output = []
        active_12m = 0
        tracked_buyers = 0

        for row in buyers_to_process:
            buyer_key = row.get("key", "").strip("/")
            if not buyer_key:
                continue

            if buyer_key.startswith("company?name="):
                buyer_key = "company/" + buyer_key.replace("company?name=", "")
            elif not buyer_key.startswith("company/"):
                buyer_key = f"company/{buyer_key}"

            country = row.get("company_address_country", "United States")

            store.upsert_company(
                importyeti_key=buyer_key,
                name=row.get("company_name", "Unknown"),
                entity_type="discovered",
                address=row.get("company_address"),
                country=country,
            )

            store.insert_edge(
                source_type="supplier",
                source_key=supplier_key,
                target_type="company",
                target_key=buyer_key,
                relationship_type="supplies_to",
                discovered_from="supplier_profile",
                total_shipments=row.get("total_shipments_supplier"),
                shipments_12m=row.get("shipments_12m"),
                shipment_pct_of_source=row.get("shipments_percents_supplier"),
                shipment_pct_of_target=row.get("shipments_percents_company"),
                total_weight=row.get("total_weight"),
                total_teus=row.get("total_teus"),
                most_recent_shipment=row.get("most_recent_shipment"),
                first_shipment=row.get("first_shipment"),
                business_length=row.get("business_length"),
                is_new_relationship=row.get("is_new_company"),
            )

            # Check if tracked entity
            local_record = store.get_company(buyer_key)
            buyer_entity_type = "discovered"
            if local_record:
                buyer_entity_type = local_record.get("entity_type", "discovered")
                if buyer_entity_type in ("target", "competitor"):
                    tracked_buyers += 1

            ship_12m = row.get("shipments_12m", 0) or 0
            if ship_12m > 0:
                active_12m += 1

            buyers_output.append({
                "name": row.get("company_name", "Unknown"),
                "slug": buyer_key.replace("company/", ""),
                "buyer_entity_type": buyer_entity_type,
                "country": country,
                "total_shipments": row.get("total_shipments_supplier"),
                "shipments_12m": row.get("shipments_12m"),
                "pct_of_supplier": row.get("shipments_percents_supplier"),
                "most_recent_shipment": row.get("most_recent_shipment"),
                "business_length": row.get("business_length"),
            })

        result = {
            "supplier": {
                "name": data.get("title", slug),
                "slug": slug,
                "importyeti_key": supplier_key,
                "address": data.get("address"),
                "country": data.get("address_country") or data.get("country"),
                "total_shipments": data.get("total_shipments"),
            },
            "buyers": buyers_output,
            "summary": {
                "total_buyers_available": len(companies_table),
                "buyers_returned": len(buyers_output),
                "active_12m": active_12m,
                "tracked_buyers": tracked_buyers,
            },
            "credits_used": meta.get("credits_used", 1),
            "credits_remaining": meta.get("credits_remaining"),
            "saved_to_cache": True,
            "formatted_table": _format_buyer_table(buyers_output),
        }

        return json.dumps(result, indent=2, default=str)

    except Exception as e:
        logger.error(f"[SUPPLY_CHAIN] get_supplier_network error: {e}", exc_info=True)
        return json.dumps({"error": str(e)})


# ─────────────────────────────────────────────────────────
# TOOL 4: Query Local DB (0 credits)
# ─────────────────────────────────────────────────────────

@tool
async def query_supply_chain_db(
    query_type: str,
    entity_key: Optional[str] = None,
    name: Optional[str] = None,
) -> str:
    """
    Query the ImportYeti supply chain database for cached data. Costs 0 API credits.

    Use this to check existing data before spending API credits, or to run
    analytical queries like shared supplier analysis.

    Args:
        query_type: One of:
            - "company_suppliers": Get supplier list for a company (requires entity_key)
            - "supplier_buyers": Get buyer list for a supplier (requires entity_key)
            - "shared_suppliers": Suppliers serving 2+ tracked competitors (all-time)
            - "shared_suppliers_12m": Same but only 12-month active relationships
            - "company_profile": Company metadata (requires entity_key)
            - "supplier_profile": Supplier metadata (requires entity_key)
            - "search_by_name": Search companies and suppliers by name (requires name)
            - "stats": Database counts and breakdowns
            - "competitor_activity": Per-company summary of supplier counts and shipments
            - "network_graph": Get nodes and edges for network visualization
        entity_key: ImportYeti key (e.g., 'company/hexcel-corporation' or
                    'supplier/jushi-group-co-ltd'). Required for profile/relationship queries.
        name: Entity name for search_by_name queries.

    Returns:
        JSON with query results and formatted tables where applicable.
    """
    try:
        store = _get_store()

        if query_type == "company_suppliers":
            if not entity_key:
                return json.dumps({"error": "entity_key required for company_suppliers"})
            company = store.get_company(entity_key)
            if not company:
                return json.dumps({"error": f"Company '{entity_key}' not found"})
            suppliers = store.get_company_suppliers(entity_key)
            return json.dumps({
                "company": {"name": company["name"], "entity_type": company.get("entity_type")},
                "suppliers": suppliers,
                "total": len(suppliers),
                "credits_used": 0,
                "formatted_table": _format_supplier_table(suppliers),
            }, indent=2, default=str)

        elif query_type == "supplier_buyers":
            if not entity_key:
                return json.dumps({"error": "entity_key required for supplier_buyers"})
            supplier = store.get_supplier(entity_key)
            if not supplier:
                return json.dumps({"error": f"Supplier '{entity_key}' not found"})
            buyers = store.get_supplier_buyers(entity_key)
            return json.dumps({
                "supplier": {"name": supplier["name"], "country": supplier.get("country")},
                "buyers": buyers,
                "total": len(buyers),
                "credits_used": 0,
                "formatted_table": _format_buyer_table(buyers),
            }, indent=2, default=str)

        elif query_type == "shared_suppliers":
            data = store.get_shared_suppliers(active_12m_only=False)
            return json.dumps({
                "shared_suppliers": data,
                "total": len(data),
                "credits_used": 0,
            }, indent=2, default=str)

        elif query_type == "shared_suppliers_12m":
            data = store.get_shared_suppliers(active_12m_only=True)
            return json.dumps({
                "shared_suppliers_12m": data,
                "total": len(data),
                "credits_used": 0,
            }, indent=2, default=str)

        elif query_type == "company_profile":
            if not entity_key:
                return json.dumps({"error": "entity_key required for company_profile"})
            company = store.get_company(entity_key)
            if not company:
                return json.dumps({"error": f"Company '{entity_key}' not found"})
            # Don't return raw_api_response (too large)
            profile = {k: v for k, v in company.items()
                       if k != "raw_api_response" and not hasattr(v, 'isoformat')}
            # Convert datetime fields
            for k, v in company.items():
                if hasattr(v, 'isoformat'):
                    profile[k] = v.isoformat()
            profile["has_full_profile"] = company.get("raw_api_response") is not None
            return json.dumps({"company": profile, "credits_used": 0}, indent=2, default=str)

        elif query_type == "supplier_profile":
            if not entity_key:
                return json.dumps({"error": "entity_key required for supplier_profile"})
            supplier = store.get_supplier(entity_key)
            if not supplier:
                return json.dumps({"error": f"Supplier '{entity_key}' not found"})
            profile = {k: v for k, v in supplier.items()
                       if k != "raw_api_response" and not hasattr(v, 'isoformat')}
            for k, v in supplier.items():
                if hasattr(v, 'isoformat'):
                    profile[k] = v.isoformat()
            profile["has_full_profile"] = supplier.get("raw_api_response") is not None
            return json.dumps({"supplier": profile, "credits_used": 0}, indent=2, default=str)

        elif query_type == "search_by_name":
            if not name:
                return json.dumps({"error": "name required for search_by_name"})
            results = store.search_by_name(name)
            return json.dumps({
                "companies": results.get("companies", []),
                "suppliers": results.get("suppliers", []),
                "credits_used": 0,
            }, indent=2, default=str)

        elif query_type == "stats":
            stats = store.get_stats()
            return json.dumps({"stats": stats, "credits_used": 0}, indent=2, default=str)

        elif query_type == "competitor_activity":
            data = store.get_competitor_activity()
            return json.dumps({
                "competitor_activity": data,
                "total": len(data),
                "credits_used": 0,
            }, indent=2, default=str)

        elif query_type == "network_graph":
            data = store.get_network_graph_data()
            return json.dumps({
                "graph": data,
                "credits_used": 0,
            }, indent=2, default=str)

        else:
            return json.dumps({
                "error": f"Unknown query_type: '{query_type}'",
                "valid_types": [
                    "company_suppliers", "supplier_buyers",
                    "shared_suppliers", "shared_suppliers_12m",
                    "company_profile", "supplier_profile",
                    "search_by_name", "stats",
                    "competitor_activity", "network_graph",
                ],
            })

    except Exception as e:
        logger.error(f"[SUPPLY_CHAIN] query_local_db error: {e}", exc_info=True)
        return json.dumps({"error": str(e)})
