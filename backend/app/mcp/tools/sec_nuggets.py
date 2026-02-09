"""
SEC Filing Nuggets Search Tool - C1 Intelligence Hub
=====================================================

MCP agent tool for searching pre-extracted strategic insights from SEC filings.
Nuggets are extracted during ingestion via Claude Haiku and stored in BigQuery.

Provides structured access to:
- Competitive disclosures (named competitors in required filings)
- Risk admissions and new disclosures
- Forward guidance and strategic initiatives
- Regulatory exposure and litigation
- Raw material and supply chain intelligence
- M&A activity and material changes
"""

import json
import logging
from typing import Optional

from langchain_core.tools import tool

from app.db.gcp_storage import get_storage

logger = logging.getLogger(__name__)


@tool
async def search_sec_nuggets(
    query: str,
    ticker: Optional[str] = None,
    nugget_type: Optional[str] = None,
    section: Optional[str] = None,
    signal_strength: Optional[str] = None,
    fiscal_year: Optional[int] = None,
    actionable_only: bool = False,
    new_disclosures_only: bool = False,
    limit: int = 15,
) -> str:
    """
    Search pre-extracted strategic insights from SEC filings (10-K, 10-Q, 8-K).

    These nuggets are extracted from legally mandated SEC disclosures - companies MUST
    disclose material risks, competitors, and forward-looking statements. Much more
    targeted than reading raw filings.

    Args:
        query: Search text (searches nugget text, companies mentioned, competitors named)
        ticker: Stock ticker to filter by (e.g., "RPM", "SHW", "PPG")
        nugget_type: Type filter. Options: competitive_disclosure, risk_admission,
                    market_position, forward_guidance, regulatory_exposure,
                    litigation_disclosure, material_change, strategic_initiative,
                    supply_chain, raw_materials, financial_metric, esg_disclosure, acquisition
        section: Filing section filter. Options: risk_factors, business, mda,
                legal_proceedings, market_risk
        signal_strength: Disclosure signal filter. Options: explicit, standard, hedged,
                        buried, new (new disclosures are highest value)
        fiscal_year: Fiscal year filter (e.g., 2025)
        actionable_only: If true, only return actionable nuggets (default: false)
        new_disclosures_only: If true, only return new disclosures not in prior filings (default: false)
        limit: Maximum nuggets to return (default: 15)

    Returns:
        JSON string with matching nuggets, each including classification,
        signal strength, competitors named, and relevance score.
    """
    logger.info(
        f"[SEC_NUGGETS_TOOL] Search: query='{query}', ticker={ticker}, "
        f"type={nugget_type}, section={section}, signal={signal_strength}"
    )

    try:
        storage = await get_storage()

        # Parse themes from query if present
        themes = None
        theme_keywords = {
            "coating": "protective_coatings",
            "waterproof": "waterproofing",
            "concrete": "concrete_repair",
            "flooring": "flooring_systems",
            "sealant": "sealants_adhesives",
            "fireproof": "fireproofing",
            "sherwin": "sherwin_williams",
            "ppg": "ppg_industries",
            "sika": "sika_group",
            "raw material": "raw_material_costs",
            "tio2": "raw_material_costs",
            "resin": "raw_material_costs",
            "supply chain": "supply_chain",
            "pricing": "pricing_strategy",
            "acquisition": "ma_activity",
            "margin": "margin_improvement",
            "construction": "commercial_construction",
            "residential": "residential_construction",
            "infrastructure": "infrastructure",
            "sustainability": "sustainability",
            "esg": "sustainability",
            "retail": "retail_channel",
            "contractor": "contractor_channel",
        }
        detected_themes = []
        query_lower = query.lower()
        for keyword, theme in theme_keywords.items():
            if keyword in query_lower:
                detected_themes.append(theme)
        if detected_themes:
            themes = detected_themes

        results = await storage.get_sec_filing_nuggets(
            ticker=ticker,
            search_query=query,
            nugget_type=nugget_type,
            themes=themes,
            section=section,
            signal_strength=signal_strength,
            fiscal_year=fiscal_year,
            actionable_only=actionable_only,
            new_disclosures_only=new_disclosures_only,
            min_relevance=0.3,
            limit=limit,
        )

        if not results:
            return json.dumps({
                "status": "no_results",
                "message": f"No SEC filing nuggets found matching: {query}",
                "filters_applied": {
                    "ticker": ticker,
                    "nugget_type": nugget_type,
                    "section": section,
                    "fiscal_year": fiscal_year,
                },
            })

        # Format results for agent consumption
        formatted_nuggets = []
        for row in results:
            # Parse JSON array fields
            themes_list = row.get("themes", "[]")
            if isinstance(themes_list, str):
                try:
                    themes_list = json.loads(themes_list)
                except (json.JSONDecodeError, TypeError):
                    themes_list = []

            companies = row.get("companies_mentioned", "[]")
            if isinstance(companies, str):
                try:
                    companies = json.loads(companies)
                except (json.JSONDecodeError, TypeError):
                    companies = []

            competitors = row.get("competitors_named", "[]")
            if isinstance(competitors, str):
                try:
                    competitors = json.loads(competitors)
                except (json.JSONDecodeError, TypeError):
                    competitors = []

            brands = row.get("brands_mentioned", "[]")
            if isinstance(brands, str):
                try:
                    brands = json.loads(brands)
                except (json.JSONDecodeError, TypeError):
                    brands = []

            regulators = row.get("regulators_mentioned", "[]")
            if isinstance(regulators, str):
                try:
                    regulators = json.loads(regulators)
                except (json.JSONDecodeError, TypeError):
                    regulators = []

            formatted_nuggets.append({
                "nugget_text": row.get("nugget_text", ""),
                "context": row.get("context_text"),
                "source": {
                    "ticker": row.get("ticker", ""),
                    "company": row.get("company_name", ""),
                    "filing_type": row.get("filing_type", ""),
                    "section": row.get("section", ""),
                    "fiscal_year": row.get("fiscal_year"),
                    "fiscal_quarter": row.get("fiscal_quarter"),
                    "filing_date": row.get("filing_date"),
                },
                "classification": {
                    "type": row.get("nugget_type", ""),
                    "themes": themes_list,
                    "signal_strength": row.get("signal_strength", ""),
                    "risk_level": row.get("risk_level", ""),
                },
                "relevance_score": row.get("relevance_score", 0),
                "is_actionable": row.get("is_actionable", False),
                "is_new_disclosure": row.get("is_new_disclosure", False),
                "business_segment": row.get("business_segment"),
                "competitors_named": competitors,
                "companies_mentioned": companies,
                "brands_mentioned": brands,
                "regulators_mentioned": regulators,
            })

        logger.info(f"[SEC_NUGGETS_TOOL] Returning {len(formatted_nuggets)} nuggets")

        return json.dumps({
            "status": "success",
            "total_results": len(formatted_nuggets),
            "nuggets": formatted_nuggets,
        }, default=str)

    except Exception as e:
        logger.error(f"[SEC_NUGGETS_TOOL] Error: {e}", exc_info=True)
        return json.dumps({"status": "error", "message": str(e)})


@tool
async def get_sec_nugget_stats() -> str:
    """
    Get statistics about the SEC filing nugget extraction database.

    Returns counts of total nuggets, filings processed, unique tickers,
    actionable nuggets, new disclosures, and average relevance scores.
    Useful for understanding the scope of available SEC intelligence.
    """
    try:
        storage = await get_storage()
        stats = await storage.get_sec_filing_nugget_stats()

        if not stats or not stats.get("total_nuggets"):
            return json.dumps({
                "status": "empty",
                "message": "No SEC filing nuggets have been extracted yet.",
            })

        return json.dumps({
            "status": "success",
            "stats": {
                "total_nuggets": stats.get("total_nuggets", 0),
                "filings_processed": stats.get("filings_processed", 0),
                "unique_tickers": stats.get("unique_tickers", 0),
                "actionable_nuggets": stats.get("actionable_nuggets", 0),
                "new_disclosures": stats.get("new_disclosures", 0),
                "avg_relevance": round(stats.get("avg_relevance", 0), 3),
                "earliest_extraction": str(stats.get("earliest_extraction", "N/A")),
                "latest_extraction": str(stats.get("latest_extraction", "N/A")),
            },
        }, default=str)

    except Exception as e:
        logger.error(f"[SEC_NUGGETS_TOOL] Stats error: {e}", exc_info=True)
        return json.dumps({"status": "error", "message": str(e)})
