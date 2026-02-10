"""
Supply Network API Routes
=========================
REST endpoints for the Supply Network tab — company directory cards,
drill-down details, intelligence context, and network graph visualization.

Endpoints:
    GET  /api/supply-network/companies       - Tracked companies with stats (card grid)
    GET  /api/supply-network/graph           - Network graph nodes/edges
    GET  /api/supply-network/stats           - Summary statistics
    GET  /api/supply-network/company/{key}/intelligence - Supply chain intelligence context
    GET  /api/supply-network/company/{key}   - Company drill-down (catch-all, must be AFTER /intelligence)
    GET  /api/supply-network/supplier/{key}  - Supplier drill-down
    GET  /api/supply-network/shared-suppliers - Shared supplier analysis
"""

import asyncio
import logging
import time
from typing import Optional

from fastapi import APIRouter, Query, HTTPException

from app.ingestion.importyeti.bigquery_store import BigQueryStore

logger = logging.getLogger(__name__)
router = APIRouter()


def _get_store() -> BigQueryStore:
    """Lazy-load BigQuery store."""
    return BigQueryStore()


@router.get("/companies")
async def get_tracked_companies():
    """Get all tracked companies (C1 + competitors) with supplier stats for directory cards."""
    try:
        start_time = time.time()
        store = _get_store()
        companies = store.get_tracked_companies_with_stats()
        # Compute most recent update across all companies
        last_updated = None
        for c in companies:
            ts = c.get("updated_at")
            if ts and (last_updated is None or ts > last_updated):
                last_updated = ts
        elapsed = time.time() - start_time
        logger.info(f"[SUPPLY_NETWORK] Companies loaded: {len(companies)} companies in {elapsed:.2f}s")
        return {"companies": companies, "last_updated": last_updated}
    except Exception as e:
        logger.error(f"[SUPPLY_NETWORK] Companies error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/graph")
async def get_network_graph(
    entity_types: str = Query("target,competitor", description="Comma-separated entity types"),
    min_shipments_12m: int = Query(0, ge=0, description="Minimum 12-month shipments filter"),
):
    """Get network graph nodes and edges for visualization."""
    try:
        store = _get_store()
        entity_type_list = [e.strip() for e in entity_types.split(",") if e.strip()]
        data = store.get_network_graph_data(
            entity_types=entity_type_list,
            min_shipments_12m=min_shipments_12m,
        )
        logger.info(
            f"[SUPPLY_NETWORK] Graph loaded: {data['stats']['total_companies']} companies, "
            f"{data['stats']['total_suppliers']} suppliers, {data['stats']['total_edges']} edges"
        )
        return data
    except Exception as e:
        logger.error(f"[SUPPLY_NETWORK] Graph error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_stats():
    """Get database summary statistics."""
    try:
        store = _get_store()
        stats = store.get_stats()
        return stats
    except Exception as e:
        logger.error(f"[SUPPLY_NETWORK] Stats error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/company/{importyeti_key:path}/intelligence")
async def get_company_intelligence(importyeti_key: str):
    """Get supply chain intelligence context for a company (earnings, SEC, articles)."""
    try:
        start_time = time.time()
        store = _get_store()
        company = store.get_company(importyeti_key)
        if not company:
            raise HTTPException(status_code=404, detail=f"Company '{importyeti_key}' not found")

        name = company["name"]
        ticker = company.get("ticker")

        logger.info(f"[SUPPLY_NETWORK] Intelligence START: {name} (ticker={ticker})")

        # Run all searches in parallel
        earnings_task = _search_earnings_for_company(ticker, name)
        sec_task = _search_sec_for_company(ticker, name)
        corpus_task = _search_corpus_for_company(name)

        earnings, sec_nuggets, articles = await asyncio.gather(
            earnings_task, sec_task, corpus_task,
            return_exceptions=True,
        )

        # Handle exceptions from gather
        if isinstance(earnings, Exception):
            logger.warning(f"[SUPPLY_NETWORK] Earnings gather error: {earnings}")
            earnings = []
        if isinstance(sec_nuggets, Exception):
            logger.warning(f"[SUPPLY_NETWORK] SEC gather error: {sec_nuggets}")
            sec_nuggets = []
        if isinstance(articles, Exception):
            logger.warning(f"[SUPPLY_NETWORK] Corpus gather error: {articles}")
            articles = []

        elapsed = time.time() - start_time
        logger.info(
            f"[SUPPLY_NETWORK] Intelligence COMPLETE: {name} in {elapsed:.2f}s — "
            f"{len(earnings)} quotes, {len(sec_nuggets)} nuggets, {len(articles)} articles"
        )

        return {
            "company_name": name,
            "ticker": ticker,
            "earnings_quotes": earnings,
            "sec_nuggets": sec_nuggets,
            "recent_articles": articles,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[SUPPLY_NETWORK] Intelligence error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/company/{importyeti_key:path}")
async def get_company_detail(importyeti_key: str):
    """Get company profile and supplier list for drill-down."""
    try:
        store = _get_store()
        company = store.get_company(importyeti_key)
        if not company:
            raise HTTPException(status_code=404, detail=f"Company '{importyeti_key}' not found")

        suppliers = store.get_company_suppliers(importyeti_key)
        customers = store.get_company_customers(importyeti_key)

        # Strip raw_api_response to keep payload small
        profile = {k: v for k, v in company.items() if k != "raw_api_response"}
        # Convert datetimes
        for k, v in profile.items():
            if hasattr(v, "isoformat"):
                profile[k] = v.isoformat()

        return {
            "company": profile,
            "suppliers": suppliers[:50],
            "supplier_count": len(suppliers),
            "customers": customers[:50],
            "customer_count": len(customers),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[SUPPLY_NETWORK] Company detail error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/supplier/{importyeti_key:path}")
async def get_supplier_detail(importyeti_key: str):
    """Get supplier profile and buyer list for drill-down."""
    try:
        store = _get_store()
        supplier = store.get_supplier(importyeti_key)
        if not supplier:
            raise HTTPException(status_code=404, detail=f"Supplier '{importyeti_key}' not found")

        buyers = store.get_supplier_buyers(importyeti_key)

        # Strip raw_api_response
        profile = {k: v for k, v in supplier.items() if k != "raw_api_response"}
        for k, v in profile.items():
            if hasattr(v, "isoformat"):
                profile[k] = v.isoformat()

        return {
            "supplier": profile,
            "buyers": buyers[:50],
            "buyer_count": len(buyers),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[SUPPLY_NETWORK] Supplier detail error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/shared-suppliers")
async def get_shared_suppliers(
    active_12m_only: bool = Query(False, description="Only show 12-month active relationships"),
):
    """Get suppliers shared between 2+ tracked competitors."""
    try:
        store = _get_store()
        data = store.get_shared_suppliers(active_12m_only=active_12m_only)
        return {
            "shared_suppliers": data,
            "total": len(data),
        }
    except Exception as e:
        logger.error(f"[SUPPLY_NETWORK] Shared suppliers error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────
# Intelligence Context (supply-chain insights for a company)
# ─────────────────────────────────────────────────────────

async def _search_earnings_for_company(ticker: Optional[str], company_name: str):
    """Search earnings quotes related to supply chain for a company."""
    from app.db.gcp_storage import BigQueryDataStorage
    try:
        storage = BigQueryDataStorage()
        # Try ticker-based search first (more precise)
        if ticker:
            results = await storage.get_earnings_quotes(
                ticker=ticker,
                quote_type="supply_chain",
                limit=5,
            )
            if results:
                return results
        # Fallback to name-based search
        results = await storage.get_earnings_quotes(
            search_query=f"{company_name} supply chain",
            limit=5,
        )
        return results
    except Exception as e:
        logger.warning(f"[SUPPLY_NETWORK] Earnings search error for {company_name}: {e}")
        return []


async def _search_sec_for_company(ticker: Optional[str], company_name: str):
    """Search SEC filing nuggets related to supply chain for a company."""
    from app.db.gcp_storage import BigQueryDataStorage
    try:
        storage = BigQueryDataStorage()
        if ticker:
            results = await storage.get_sec_filing_nuggets(
                ticker=ticker,
                limit=5,
            )
            if results:
                return results
        results = await storage.get_sec_filing_nuggets(
            search_query=f"{company_name} supply chain",
            limit=5,
        )
        return results
    except Exception as e:
        logger.warning(f"[SUPPLY_NETWORK] SEC search error for {company_name}: {e}")
        return []


async def _search_corpus_for_company(company_name: str):
    """Search recent articles mentioning this company with supply chain context."""
    from app.db.gcp_storage import BigQueryDataStorage
    try:
        storage = BigQueryDataStorage()
        results = await storage.get_articles(
            search_query=company_name,
            category="supply-chain",
            limit=5,
        )
        if not results:
            # Broader search without category filter
            results = await storage.get_articles(
                search_query=company_name,
                limit=5,
            )
        # Convert ArticleRecord objects to dicts
        articles = []
        for r in (results or []):
            article = r if isinstance(r, dict) else r.__dict__ if hasattr(r, '__dict__') else {}
            # Only keep serializable fields
            articles.append({
                "title": article.get("title", "Unknown"),
                "url": article.get("url", ""),
                "source": article.get("source", ""),
                "published_at": str(article.get("published_at", "")),
                "category": article.get("category", ""),
                "summary": article.get("summary", ""),
            })
        return articles
    except Exception as e:
        logger.warning(f"[SUPPLY_NETWORK] Corpus search error for {company_name}: {e}")
        return []
