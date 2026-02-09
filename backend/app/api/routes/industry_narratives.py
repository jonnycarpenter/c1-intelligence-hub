"""
Industry Narratives API Routes
===============================
REST endpoints for the Industry Narratives tab — 90-day timeline view
showing how news narratives evolve by composites end-market.

Endpoints:
    GET  /api/industry-narratives/industries          - Curated industry list with counts
    GET  /api/industry-narratives/{industry}/timeline  - Monthly breakdown with MoM deltas
    GET  /api/industry-narratives/{industry}/articles   - Paginated article drill-down
"""

import json
import logging
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from google.cloud import bigquery

from app.db.gcp_storage import GCPConfig, _safe_parse_list

logger = logging.getLogger(__name__)
router = APIRouter()

# Curated top-10 composites end-markets
CURATED_INDUSTRIES = [
    "Aerospace",
    "Transportation",
    "Automotive",
    "Defense Space",
    "Infrastructure",
    "Construction",
    "Industrial",
    "Marine",
    "Wind",
    "Sporting Goods",
]

_bq_client: Optional[bigquery.Client] = None
_config = GCPConfig()


def _get_client() -> bigquery.Client:
    """Lazy-load BigQuery client."""
    global _bq_client
    if _bq_client is None:
        _bq_client = bigquery.Client(project=_config.project_id)
    return _bq_client


def _dataset() -> str:
    return _config.full_dataset_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MONTH_NAMES = {
    1: "January", 2: "February", 3: "March", 4: "April",
    5: "May", 6: "June", 7: "July", 8: "August",
    9: "September", 10: "October", 11: "November", 12: "December",
}


def _month_label(month_key: str) -> str:
    """Convert '2026-02' to 'February 2026'."""
    try:
        y, m = month_key.split("-")
        return f"{MONTH_NAMES[int(m)]} {y}"
    except Exception:
        return month_key


def _compute_deltas(
    current: Dict[str, int], prior: Optional[Dict[str, int]]
) -> List[Dict[str, Any]]:
    """Build list of {name, count, delta} sorted by count desc."""
    result = []
    for name, count in sorted(current.items(), key=lambda x: -x[1]):
        delta = None if prior is None else count - prior.get(name, 0)
        result.append({"name": name, "count": count, "delta": delta})
    return result


# ---------------------------------------------------------------------------
# GET /industries  — list curated industries with 90-day article counts
# ---------------------------------------------------------------------------

@router.get("/industries")
async def list_industries(days: int = Query(90, ge=1, le=365)):
    """Return curated industry list with article counts in the time window."""
    try:
        client = _get_client()

        # Build UNNEST query to count articles per curated industry
        industry_list_sql = ", ".join(f"'{i}'" for i in CURATED_INDUSTRIES)

        query = f"""
            SELECT
                TRIM(ind, '"') AS industry,
                COUNT(DISTINCT id) AS article_count
            FROM `{_dataset()}.digest_items`,
                UNNEST(JSON_EXTRACT_ARRAY(industries)) AS ind
            WHERE published_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {days} DAY)
              AND LOWER(TRIM(ind, '"')) IN ({', '.join(f"'{i.lower()}'" for i in CURATED_INDUSTRIES)})
            GROUP BY industry
            ORDER BY article_count DESC
        """

        rows = list(client.query(query).result())
        count_map = {row.industry.strip(): row.article_count for row in rows}

        # Also get last-month vs prior-month counts for trend direction
        trend_query = f"""
            WITH monthly AS (
                SELECT
                    LOWER(TRIM(ind, '"')) AS industry,
                    FORMAT_TIMESTAMP('%Y-%m', published_at) AS month_key,
                    COUNT(DISTINCT id) AS cnt
                FROM `{_dataset()}.digest_items`,
                    UNNEST(JSON_EXTRACT_ARRAY(industries)) AS ind
                WHERE published_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
                  AND LOWER(TRIM(ind, '"')) IN ({', '.join(f"'{i.lower()}'" for i in CURATED_INDUSTRIES)})
                GROUP BY industry, month_key
            )
            SELECT industry, month_key, cnt
            FROM monthly
            ORDER BY industry, month_key DESC
        """
        trend_rows = list(client.query(trend_query).result())
        # Group by industry -> [most_recent_month_count, prior_month_count]
        trend_map: Dict[str, List[int]] = defaultdict(list)
        for r in trend_rows:
            trend_map[r.industry].append(r.cnt)

        industries_out = []
        for name in CURATED_INDUSTRIES:
            cnt = count_map.get(name, 0)
            # Check case-insensitive match
            if cnt == 0:
                for k, v in count_map.items():
                    if k.lower() == name.lower():
                        cnt = v
                        break

            trend_counts = trend_map.get(name.lower(), [])
            if len(trend_counts) >= 2:
                trend = "up" if trend_counts[0] > trend_counts[1] else (
                    "down" if trend_counts[0] < trend_counts[1] else "flat"
                )
            else:
                trend = "flat"

            industries_out.append({
                "id": name.lower().replace(" ", "_"),
                "name": name,
                "article_count_90d": cnt,
                "trend": trend,
            })

        logger.info(f"[INDUSTRY_NARRATIVES] Listed {len(industries_out)} industries ({days}d)")
        return {"industries": industries_out}

    except Exception as e:
        logger.error(f"[INDUSTRY_NARRATIVES] list_industries error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# GET /{industry}/timeline  — monthly breakdown with MoM deltas
# ---------------------------------------------------------------------------

@router.get("/{industry}/timeline")
async def get_industry_timeline(
    industry: str,
    days: int = Query(90, ge=1, le=365),
):
    """Get monthly aggregated timeline data for an industry."""
    try:
        client = _get_client()

        # Resolve display name from slug
        display_name = _resolve_industry_name(industry)
        industry_lower = display_name.lower()

        # ----- Fetch all matching articles in the time window -----
        query = f"""
            SELECT
                id,
                title,
                url,
                source_name,
                published_at,
                digest_summary,
                event_type,
                sentiment,
                companies,
                themes,
                geography,
                relevance_score,
                FORMAT_TIMESTAMP('%Y-%m', published_at) AS month_key
            FROM `{_dataset()}.digest_items`
            WHERE published_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {days} DAY)
              AND EXISTS(
                SELECT 1
                FROM UNNEST(JSON_EXTRACT_ARRAY(industries)) AS ind
                WHERE LOWER(TRIM(ind, '"')) = '{industry_lower}'
              )
            ORDER BY published_at DESC
        """

        rows = list(client.query(query).result())
        logger.info(f"[INDUSTRY_NARRATIVES] Timeline query returned {len(rows)} articles for '{display_name}' ({days}d)")

        if not rows:
            return {
                "industry": display_name,
                "period_days": days,
                "monthly_data": [],
                "totals": {"total_articles": 0, "avg_monthly": 0, "trend_direction": "flat"},
            }

        # ----- Group by month and aggregate -----
        months: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "articles": [],
            "event_types": defaultdict(int),
            "companies": defaultdict(int),
            "themes": defaultdict(int),
            "geographies": defaultdict(int),
            "sentiment": {"positive": 0, "neutral": 0, "negative": 0},
        })

        for row in rows:
            mk = row.month_key
            m = months[mk]
            m["articles"].append(row)

            # Event type
            evt = row.event_type or "other"
            m["event_types"][evt] += 1

            # Sentiment
            sen = (row.sentiment or "neutral").lower()
            if sen in m["sentiment"]:
                m["sentiment"][sen] += 1
            else:
                m["sentiment"]["neutral"] += 1

            # Companies (JSON array)
            for c in _safe_parse_list(row.companies):
                if c and len(c) > 1:
                    m["companies"][c] += 1

            # Themes (JSON array)
            for t in _safe_parse_list(row.themes):
                if t:
                    m["themes"][t] += 1

            # Geography (JSON array)
            for g in _safe_parse_list(row.geography):
                if g:
                    m["geographies"][g] += 1

        # Sort months descending (most recent first)
        sorted_months = sorted(months.keys(), reverse=True)

        # ----- Build response with deltas -----
        monthly_data = []
        for i, mk in enumerate(sorted_months):
            m = months[mk]
            article_count = len(m["articles"])

            # Prior month for deltas
            prior_mk = sorted_months[i + 1] if i + 1 < len(sorted_months) else None
            prior = months.get(prior_mk) if prior_mk else None
            prior_count = len(prior["articles"]) if prior else None

            # Event types with deltas
            event_types_list = _compute_deltas(
                m["event_types"],
                prior["event_types"] if prior else None,
            )

            # Top companies (top 10) with deltas
            companies_list = _compute_deltas(
                m["companies"],
                prior["companies"] if prior else None,
            )[:10]

            # Top themes (top 10) with deltas
            themes_list = _compute_deltas(
                m["themes"],
                prior["themes"] if prior else None,
            )[:10]

            # Top geographies (top 5)
            geo_list = sorted(
                [{"name": k, "count": v} for k, v in m["geographies"].items()],
                key=lambda x: -x["count"],
            )[:5]

            # Top articles (top 5 by relevance_score)
            top_articles = sorted(
                m["articles"],
                key=lambda a: (a.relevance_score or 0),
                reverse=True,
            )[:5]

            monthly_data.append({
                "month": mk,
                "month_label": _month_label(mk),
                "article_count": article_count,
                "delta_vs_prior": (article_count - prior_count) if prior_count is not None else None,
                "event_types": event_types_list,
                "top_companies": companies_list,
                "top_themes": themes_list,
                "top_geographies": geo_list,
                "sentiment": m["sentiment"],
                "top_articles": [
                    {
                        "id": str(a.id),
                        "title": a.title,
                        "url": a.url,
                        "source_name": a.source_name or "",
                        "published_at": a.published_at.isoformat() if a.published_at else "",
                        "summary": (a.digest_summary or "")[:300],
                        "event_type": a.event_type,
                        "sentiment": a.sentiment or "neutral",
                    }
                    for a in top_articles
                ],
            })

        total_articles = len(rows)
        avg_monthly = total_articles / max(len(sorted_months), 1)
        if len(monthly_data) >= 2:
            trend = "up" if monthly_data[0]["article_count"] > monthly_data[1]["article_count"] else (
                "down" if monthly_data[0]["article_count"] < monthly_data[1]["article_count"] else "flat"
            )
        else:
            trend = "flat"

        logger.info(
            f"[INDUSTRY_NARRATIVES] Timeline built: {display_name}, "
            f"{len(monthly_data)} months, {total_articles} total articles"
        )

        return {
            "industry": display_name,
            "period_days": days,
            "monthly_data": monthly_data,
            "totals": {
                "total_articles": total_articles,
                "avg_monthly": round(avg_monthly, 1),
                "trend_direction": trend,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[INDUSTRY_NARRATIVES] timeline error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# GET /{industry}/articles  — paginated article drill-down
# ---------------------------------------------------------------------------

@router.get("/{industry}/articles")
async def get_industry_articles(
    industry: str,
    month: Optional[str] = Query(None, description="Filter by month (YYYY-MM)"),
    event_type: Optional[str] = Query(None),
    theme: Optional[str] = Query(None),
    sentiment: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Get paginated articles for an industry with optional filters."""
    try:
        client = _get_client()
        display_name = _resolve_industry_name(industry)
        industry_lower = display_name.lower()

        where_clauses = [
            f"""EXISTS(
                SELECT 1 FROM UNNEST(JSON_EXTRACT_ARRAY(industries)) AS ind
                WHERE LOWER(TRIM(ind, '"')) = '{industry_lower}'
            )""",
            "published_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 90 DAY)",
        ]

        if month:
            where_clauses.append(f"FORMAT_TIMESTAMP('%Y-%m', published_at) = '{month}'")
        if event_type:
            where_clauses.append(f"LOWER(event_type) = '{event_type.lower()}'")
        if sentiment:
            where_clauses.append(f"LOWER(sentiment) = '{sentiment.lower()}'")

        where_sql = " AND ".join(where_clauses)

        # Theme filter requires checking JSON array
        theme_filter = ""
        if theme:
            theme_filter = f"""
                AND EXISTS(
                    SELECT 1 FROM UNNEST(JSON_EXTRACT_ARRAY(themes)) AS t
                    WHERE LOWER(TRIM(t, '"')) = '{theme.lower()}'
                )
            """

        # Count query
        count_query = f"""
            SELECT COUNT(*) as total
            FROM `{_dataset()}.digest_items`
            WHERE {where_sql} {theme_filter}
        """
        total_count = list(client.query(count_query).result())[0].total

        # Data query
        query = f"""
            SELECT
                id, title, url, source_name, published_at,
                digest_summary, event_type, sentiment,
                companies, themes, geography, relevance_score
            FROM `{_dataset()}.digest_items`
            WHERE {where_sql} {theme_filter}
            ORDER BY published_at DESC
            LIMIT {limit} OFFSET {offset}
        """

        rows = list(client.query(query).result())

        articles = []
        for row in rows:
            articles.append({
                "id": str(row.id),
                "title": row.title,
                "url": row.url,
                "source_name": row.source_name or "",
                "published_at": row.published_at.isoformat() if row.published_at else "",
                "summary": row.digest_summary or "",
                "event_type": row.event_type,
                "sentiment": row.sentiment or "neutral",
                "themes": _safe_parse_list(row.themes),
                "companies": _safe_parse_list(row.companies),
                "geography": _safe_parse_list(row.geography),
            })

        filters_applied = {}
        if month:
            filters_applied["month"] = month
        if event_type:
            filters_applied["event_type"] = event_type
        if theme:
            filters_applied["theme"] = theme
        if sentiment:
            filters_applied["sentiment"] = sentiment

        logger.info(
            f"[INDUSTRY_NARRATIVES] Articles: {display_name}, "
            f"filters={filters_applied}, returned {len(articles)}/{total_count}"
        )

        return {
            "industry": display_name,
            "filters_applied": filters_applied,
            "total_count": total_count,
            "articles": articles,
            "pagination": {
                "limit": limit,
                "offset": offset,
                "has_more": (offset + limit) < total_count,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[INDUSTRY_NARRATIVES] articles error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_industry_name(slug: str) -> str:
    """Convert URL slug like 'aerospace' or 'defense_space' back to display name."""
    slug_lower = slug.lower().replace("_", " ").replace("-", " ")
    for name in CURATED_INDUSTRIES:
        if name.lower() == slug_lower:
            return name
    # Fallback: title-case the slug
    return slug.replace("_", " ").replace("-", " ").title()
