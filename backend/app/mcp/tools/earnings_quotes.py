"""
Earnings Quotes Search Tool - C1 Intelligence Hub
==================================================

MCP agent tool for searching pre-extracted executive quotes from earnings calls.
Quotes are extracted during ingestion via Claude Haiku and stored in BigQuery.

Provides structured access to:
- Executive forward guidance and strategic insights
- Competitive intelligence from earnings calls
- Analyst pressure points (hedged Q&A responses)
- Raw materials and pricing commentary
- Market condition and demand signals
"""

import json
import logging
from typing import Optional

from langchain_core.tools import tool

from app.db.gcp_storage import get_storage

logger = logging.getLogger(__name__)


@tool
async def search_earnings_quotes(
    query: str,
    ticker: Optional[str] = None,
    quote_type: Optional[str] = None,
    speaker_role: Optional[str] = None,
    section: Optional[str] = None,
    year: Optional[int] = None,
    quarter: Optional[int] = None,
    quotable_only: bool = True,
    limit: int = 15,
) -> str:
    """
    Search pre-extracted executive quotes from earnings call transcripts.

    These quotes have been extracted and classified by AI from full earnings transcripts.
    Much more targeted than reading raw transcripts - each quote is attributed, typed, and scored.

    Args:
        query: Search text (searches quote text, context, companies mentioned, speaker names)
        ticker: Stock ticker to filter by (e.g., "HXL", "OC", "BA")
        quote_type: Type filter. Options: guidance, strategy, competitive, market_commentary,
                    segment_insight, channel_insight, pricing, innovation, risk_factor,
                    regional, analyst_pressure, raw_materials, acquisition, capacity, supply_chain
        speaker_role: Role filter. Options: ceo, cfo, coo, analyst, president, evp, vp
        section: Call section filter. Options: prepared_remarks, qa
        year: Fiscal year filter (e.g., 2025)
        quarter: Fiscal quarter filter (1-4)
        quotable_only: If true, only return high-value quotable quotes (default: true)
        limit: Maximum quotes to return (default: 15)

    Returns:
        JSON string with matching quotes, each including speaker attribution,
        classification, sentiment, confidence level, and relevance score.
    """
    logger.info(
        f"[EARNINGS_QUOTES_TOOL] Search: query='{query}', ticker={ticker}, "
        f"type={quote_type}, role={speaker_role}, section={section}"
    )

    try:
        storage = await get_storage()

        # Parse themes from query if present
        themes = None
        theme_keywords = {
            "carbon fiber": "carbon_fiber",
            "glass fiber": "glass_fiber",
            "resin": "resins_epoxy",
            "epoxy": "resins_epoxy",
            "prepreg": "prepreg",
            "aerospace": "aerospace_commercial",
            "defense": "aerospace_defense",
            "wind": "wind_energy",
            "automotive": "automotive",
            "boeing": "boeing",
            "airbus": "airbus",
            "supply chain": "supply_chain",
            "raw material": "raw_material_costs",
            "pricing": "pricing_strategy",
            "margin": "margin_improvement",
            "capacity": "capacity_expansion",
            "production rate": "production_rates",
        }
        detected_themes = []
        query_lower = query.lower()
        for keyword, theme in theme_keywords.items():
            if keyword in query_lower:
                detected_themes.append(theme)
        if detected_themes:
            themes = detected_themes

        results = await storage.get_earnings_quotes(
            ticker=ticker,
            search_query=query,
            quote_type=quote_type,
            themes=themes,
            speaker_role=speaker_role,
            section=section,
            year=year,
            quarter=quarter,
            quotable_only=quotable_only,
            min_relevance=0.3,
            limit=limit,
        )

        if not results:
            return json.dumps({
                "status": "no_results",
                "message": f"No earnings quotes found matching: {query}",
                "filters_applied": {
                    "ticker": ticker,
                    "quote_type": quote_type,
                    "speaker_role": speaker_role,
                    "year": year,
                    "quarter": quarter,
                },
            })

        # Format results for agent consumption
        formatted_quotes = []
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

            metrics = row.get("metrics_mentioned", "[]")
            if isinstance(metrics, str):
                try:
                    metrics = json.loads(metrics)
                except (json.JSONDecodeError, TypeError):
                    metrics = []

            formatted_quotes.append({
                "quote_text": row.get("quote_text", ""),
                "context": row.get("context_summary", ""),
                "speaker": {
                    "name": row.get("speaker_name", "Unknown"),
                    "role": row.get("speaker_role", "unknown"),
                    "title": row.get("speaker_title"),
                    "company": row.get("speaker_company"),
                    "firm": row.get("speaker_firm"),
                },
                "source": {
                    "ticker": row.get("ticker", ""),
                    "company": row.get("company_name", ""),
                    "quarter": f"Q{row.get('quarter', '?')} {row.get('year', '?')}",
                    "section": row.get("call_section", "unknown"),
                },
                "classification": {
                    "type": row.get("quote_type", ""),
                    "themes": themes_list,
                    "sentiment": row.get("sentiment", "neutral"),
                    "confidence": row.get("confidence_level", ""),
                },
                "relevance_score": row.get("relevance_score", 0),
                "is_quotable": row.get("is_quotable", False),
                "companies_mentioned": companies,
                "metrics_mentioned": metrics,
            })

        logger.info(f"[EARNINGS_QUOTES_TOOL] Returning {len(formatted_quotes)} quotes")

        return json.dumps({
            "status": "success",
            "total_results": len(formatted_quotes),
            "quotes": formatted_quotes,
        }, default=str)

    except Exception as e:
        logger.error(f"[EARNINGS_QUOTES_TOOL] Error: {e}", exc_info=True)
        return json.dumps({"status": "error", "message": str(e)})


@tool
async def get_earnings_quote_stats() -> str:
    """
    Get statistics about the earnings quote extraction database.

    Returns counts of total quotes, transcripts processed, unique tickers,
    quotable quotes, and average relevance scores. Useful for understanding
    the scope and quality of available earnings intelligence.
    """
    try:
        storage = await get_storage()
        stats = await storage.get_earnings_quote_stats()

        if not stats or not stats.get("total_quotes"):
            return json.dumps({
                "status": "empty",
                "message": "No earnings quotes have been extracted yet.",
            })

        return json.dumps({
            "status": "success",
            "stats": {
                "total_quotes": stats.get("total_quotes", 0),
                "transcripts_processed": stats.get("transcripts_processed", 0),
                "unique_tickers": stats.get("unique_tickers", 0),
                "quotable_quotes": stats.get("quotable_quotes", 0),
                "avg_relevance": round(stats.get("avg_relevance", 0), 3),
                "earliest_extraction": str(stats.get("earliest_extraction", "N/A")),
                "latest_extraction": str(stats.get("latest_extraction", "N/A")),
            },
        }, default=str)

    except Exception as e:
        logger.error(f"[EARNINGS_QUOTES_TOOL] Stats error: {e}", exc_info=True)
        return json.dumps({"status": "error", "message": str(e)})
