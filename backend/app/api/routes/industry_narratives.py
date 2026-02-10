"""
Industry Narratives API Routes
===============================
REST endpoints for the Industry Narratives tab — 90-day timeline view
showing how news narratives evolve by composites end-market.

Endpoints:
    GET  /api/industry-narratives/industries          - Curated industry list with counts
    GET  /api/industry-narratives/{industry}/timeline  - Monthly breakdown with MoM deltas
    POST /api/industry-narratives/{industry}/narrative  - LLM narrative synthesis (on-demand)
    GET  /api/industry-narratives/{industry}/articles   - Paginated article drill-down
"""

import asyncio
import calendar
import json
import logging
import time
from collections import defaultdict
from datetime import datetime, timezone
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


def _days_in_month_period(month_key: str) -> int:
    """Return elapsed days for a month key (YYYY-MM).

    For the current (partial) month, returns only days elapsed so far.
    For past months, returns the full calendar length.
    For future months (shouldn't happen), returns the full calendar length.
    """
    try:
        y, m = int(month_key[:4]), int(month_key[5:7])
        now = datetime.now(timezone.utc)
        full_days = calendar.monthrange(y, m)[1]
        if y == now.year and m == now.month:
            return now.day  # partial month — only elapsed days
        return full_days
    except Exception:
        return 30  # safe fallback


def _is_partial_month(month_key: str) -> bool:
    """Return True if month_key is the current (incomplete) month."""
    try:
        y, m = int(month_key[:4]), int(month_key[5:7])
        now = datetime.now(timezone.utc)
        return y == now.year and m == now.month
    except Exception:
        return False


def _compute_window_start() -> datetime:
    """Compute the start date for the 3-month timeline window.

    Always starts on the 1st of the month, 2 full months before the current month.
    This ensures all included months start on day 1, making per-day divisors accurate.

    Examples:
        Feb 10, 2026 → Dec 1, 2025  (Dec, Jan, Feb)
        Mar 15, 2026 → Jan 1, 2026  (Jan, Feb, Mar)
        Jan  5, 2026 → Nov 1, 2025  (Nov, Dec, Jan)
    """
    now = datetime.now(timezone.utc)
    # 1st of current month
    current_first = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    # Subtract 2 months
    month = current_first.month - 2
    year = current_first.year
    if month <= 0:
        month += 12
        year -= 1
    return current_first.replace(year=year, month=month)


def _compute_deltas(
    current: Dict[str, int], prior: Optional[Dict[str, int]]
) -> List[Dict[str, Any]]:
    """Build list of {name, count, delta} sorted by count desc."""
    result = []
    for name, count in sorted(current.items(), key=lambda x: -x[1]):
        delta = None if prior is None else count - prior.get(name, 0)
        result.append({"name": name, "count": count, "delta": delta})
    return result


def _compute_deltas_per_day(
    current: Dict[str, int],
    current_days: int,
    prior: Optional[Dict[str, int]],
    prior_days: Optional[int],
) -> List[Dict[str, Any]]:
    """Build list of {name, count, per_day, delta_per_day} sorted by per_day desc."""
    result = []
    for name, count in sorted(current.items(), key=lambda x: -x[1]):
        per_day = round(count / max(current_days, 1), 2)
        delta_per_day = None
        if prior is not None and prior_days:
            prior_per_day = round(prior.get(name, 0) / max(prior_days, 1), 2)
            delta_per_day = round(per_day - prior_per_day, 2)
        result.append({
            "name": name,
            "count": count,
            "per_day": per_day,
            "delta": delta_per_day,
        })
    result.sort(key=lambda x: -x["per_day"])
    return result


# ---------------------------------------------------------------------------
# GET /industries  — list curated industries with 90-day article counts
# ---------------------------------------------------------------------------

@router.get("/industries")
async def list_industries(days: int = Query(90, ge=1, le=365)):
    """Return curated industry list with article counts in the time window."""
    try:
        client = _get_client()

        # Use aligned window start (1st of month, 2 months back)
        window_start = _compute_window_start()
        window_start_str = window_start.strftime("%Y-%m-%d")

        # Build UNNEST query to count articles per curated industry
        industry_list_sql = ", ".join(f"'{i}'" for i in CURATED_INDUSTRIES)

        query = f"""
            SELECT
                TRIM(ind, '"') AS industry,
                COUNT(DISTINCT id) AS article_count
            FROM `{_dataset()}.digest_items`,
                UNNEST(JSON_EXTRACT_ARRAY(industries)) AS ind
            WHERE published_at >= TIMESTAMP('{window_start_str}')
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
        # Group by industry -> [(month_key, count), ...] ordered most recent first
        trend_map: Dict[str, List[tuple]] = defaultdict(list)
        for r in trend_rows:
            trend_map[r.industry].append((r.month_key, r.cnt))

        industries_out = []
        for name in CURATED_INDUSTRIES:
            cnt = count_map.get(name, 0)
            # Check case-insensitive match
            if cnt == 0:
                for k, v in count_map.items():
                    if k.lower() == name.lower():
                        cnt = v
                        break

            trend_entries = trend_map.get(name.lower(), [])
            if len(trend_entries) >= 2:
                # Compare per-day rates (most recent vs prior)
                recent_mk, recent_cnt = trend_entries[0]
                prior_mk, prior_cnt = trend_entries[1]
                recent_rate = recent_cnt / max(_days_in_month_period(recent_mk), 1)
                prior_rate = prior_cnt / max(_days_in_month_period(prior_mk), 1)
                trend = "up" if recent_rate > prior_rate else (
                    "down" if recent_rate < prior_rate else "flat"
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
        # Use aligned window start (1st of month, 2 months back) for clean month boundaries
        window_start = _compute_window_start()
        window_start_str = window_start.strftime("%Y-%m-%d")

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
            WHERE published_at >= TIMESTAMP('{window_start_str}')
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

        # Sort months ascending (oldest first → chronological left-to-right)
        sorted_months = sorted(months.keys())

        # ----- Build response with per-day normalization and deltas -----
        monthly_data = []
        for i, mk in enumerate(sorted_months):
            m = months[mk]
            article_count = len(m["articles"])
            current_days = _days_in_month_period(mk)
            articles_per_day = round(article_count / max(current_days, 1), 2)

            # Prior month for deltas (previous index in chronological order)
            prior_mk = sorted_months[i - 1] if i > 0 else None
            prior = months.get(prior_mk) if prior_mk else None
            prior_count = len(prior["articles"]) if prior else None
            prior_days = _days_in_month_period(prior_mk) if prior_mk else None

            # Per-day delta for article count
            if prior_count is not None and prior_days:
                prior_per_day = round(prior_count / max(prior_days, 1), 2)
                delta_per_day = round(articles_per_day - prior_per_day, 2)
            else:
                delta_per_day = None

            # Event types with per-day deltas
            event_types_list = _compute_deltas_per_day(
                m["event_types"], current_days,
                prior["event_types"] if prior else None,
                prior_days,
            )

            # Top companies (top 10) with per-day deltas
            companies_list = _compute_deltas_per_day(
                m["companies"], current_days,
                prior["companies"] if prior else None,
                prior_days,
            )[:10]

            # Top themes (top 10) with per-day deltas
            themes_list = _compute_deltas_per_day(
                m["themes"], current_days,
                prior["themes"] if prior else None,
                prior_days,
            )[:10]

            # Top geographies (top 5) — per-day as well
            geo_list = sorted(
                [
                    {"name": k, "count": v, "per_day": round(v / max(current_days, 1), 2)}
                    for k, v in m["geographies"].items()
                ],
                key=lambda x: -x["per_day"],
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
                "days_in_period": current_days,
                "articles_per_day": articles_per_day,
                "delta_per_day": delta_per_day,
                "is_partial": _is_partial_month(mk),
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
        # Trend based on per-day rate of most recent vs second-most-recent
        if len(monthly_data) >= 2:
            latest_rate = monthly_data[-1]["articles_per_day"]
            prior_rate = monthly_data[-2]["articles_per_day"]
            trend = "up" if latest_rate > prior_rate else (
                "down" if latest_rate < prior_rate else "flat"
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
# POST /{industry}/narrative  — LLM narrative synthesis (on-demand)
# ---------------------------------------------------------------------------

_bq_storage = None


async def _get_bq_storage():
    """Lazy-init BigQuery storage for enrichment queries."""
    global _bq_storage
    if _bq_storage is not None:
        return _bq_storage
    try:
        from app.db.gcp_storage import BigQueryDataStorage, gcp_config
        if gcp_config.is_configured:
            storage = BigQueryDataStorage(gcp_config)
            await storage.initialize()
            _bq_storage = storage
            return storage
    except Exception as e:
        logger.warning(f"[INDUSTRY_NARRATIVES] BigQuery storage not available: {e}")
    return None


def _extract_top_companies(monthly_data: List[Dict]) -> List[str]:
    """Extract deduplicated top companies across all months, ranked by total count."""
    company_totals: Dict[str, int] = defaultdict(int)
    for month in monthly_data:
        for c in month.get("top_companies", []):
            company_totals[c["name"]] += c["count"]
    ranked = sorted(company_totals.items(), key=lambda x: -x[1])
    return [name for name, _ in ranked[:8]]


def _compress_monthly_for_prompt(monthly_data: List[Dict]) -> str:
    """Compress monthly timeline data into a concise prompt-friendly format."""
    parts = []
    for m in monthly_data:
        month_label = m["month_label"]
        count = m["article_count"]
        delta = m.get("delta_vs_prior")
        delta_str = f" (Δ {delta:+d} vs prior month)" if delta is not None else ""

        # Top 5 event types
        events = ", ".join(
            f"{e['name']}({e['count']})" for e in m.get("event_types", [])[:5]
        )
        # Top 5 companies
        companies = ", ".join(
            f"{c['name']}({c['count']})" for c in m.get("top_companies", [])[:5]
        )
        # Top 5 themes
        themes = ", ".join(
            f"{t['name']}({t['count']})" for t in m.get("top_themes", [])[:5]
        )
        # Sentiment
        sen = m.get("sentiment", {})
        sen_str = f"pos={sen.get('positive', 0)}, neu={sen.get('neutral', 0)}, neg={sen.get('negative', 0)}"
        # Top geos
        geos = ", ".join(g["name"] for g in m.get("top_geographies", [])[:3])
        # Top article titles (just titles for context)
        titles = "; ".join(
            a["title"][:80] for a in m.get("top_articles", [])[:3]
        )

        parts.append(
            f"### {month_label} — {count} articles{delta_str}\n"
            f"Events: {events}\n"
            f"Companies: {companies}\n"
            f"Themes: {themes}\n"
            f"Sentiment: {sen_str}\n"
            f"Geographies: {geos}\n"
            f"Key headlines: {titles}"
        )
    return "\n\n".join(parts)


def _format_enrichment_for_prompt(
    earnings_quotes: List[Dict], sec_nuggets: List[Dict]
) -> str:
    """Format enrichment data as text blocks for the LLM prompt."""
    parts = []

    if earnings_quotes:
        eq_lines = ["=== EARNINGS CALL QUOTES ==="]
        for q in earnings_quotes:
            speaker = q.get("speaker_name", "Unknown")
            role = q.get("speaker_role", "")
            ticker = q.get("ticker", "")
            company = q.get("company_name", "")
            text = q.get("quote_text", "")
            quarter = q.get("quarter", "")
            year = q.get("year", "")
            eq_lines.append(
                f"[{company} ({ticker}) — {speaker}, {role} — Q{quarter} {year}]\n\"{text[:300]}\""
            )
        parts.append("\n\n".join(eq_lines))

    if sec_nuggets:
        sec_lines = ["=== SEC FILING DISCLOSURES ==="]
        for n in sec_nuggets:
            ticker = n.get("ticker", "N/A")
            filing_type = n.get("filing_type", "")
            nugget_type = n.get("nugget_type", "")
            text = n.get("nugget_text", "")
            signal = n.get("signal_strength", "")
            sec_lines.append(
                f"[{ticker} / {filing_type}] ({nugget_type}, signal: {signal})\n{text[:300]}"
            )
        parts.append("\n\n".join(sec_lines))

    if not parts:
        return "No enrichment data available."
    return "\n\n".join(parts)


NARRATIVE_SYSTEM_PROMPT = """You are a composites industry analyst synthesizing intelligence for Composites One (C1), a leading composites materials distributor. Your audience is C1's executive leadership team who need to understand how end-market narratives are evolving.

Your task is to weave together article trends, executive commentary from earnings calls, and SEC filing disclosures into a connected narrative — NOT just a summary of themes, but a STORY that identifies:
- Inflection points and catalysts driving change
- Continuing themes vs genuinely new signals
- Sentiment shifts and what's driving them
- How different data points (articles, earnings quotes, SEC filings) corroborate or contradict each other

Write in a direct, analytical tone. Avoid generic filler. Every sentence should convey specific, actionable intelligence.

FORMAT WITH MARKDOWN for readability:
- Use **bold** for company names, key metrics, dollar figures, and critical takeaways
- Keep paragraphs short (2-3 sentences max) for scannability
- You may use bullet points sparingly for lists of related developments
- Do NOT use headers (h1/h2/h3) — the UI provides its own headers"""


def _build_narrative_prompt(
    industry: str,
    compressed_monthly: str,
    enrichment_text: str,
    total_articles: int,
    num_months: int,
) -> str:
    return f"""Analyze the following {num_months}-month timeline data for the **{industry}** composites end-market ({total_articles} total articles) and synthesize a cohesive narrative.

## MONTHLY TIMELINE DATA
{compressed_monthly}

## ENRICHMENT: EXECUTIVE COMMENTARY & SEC DISCLOSURES
{enrichment_text}

## OUTPUT FORMAT (respond with valid JSON only)
{{
  "industry_narrative": "<3-5 sentences with **bold** key points: the overarching story arc for this end-market. What is the dominant narrative? What shifted? What should C1 leadership pay attention to? Use markdown formatting.>",
  "monthly_narratives": [
    {{
      "month": "<YYYY-MM>",
      "narrative": "<2-3 sentences with **bold** highlights: what happened THIS month specifically, how it connects to the prior month, and any notable inflection points. Reference specific **company names**, quotes, or filings. Use markdown formatting.>"
    }}
  ],
  "key_insight": "<1 sentence with the most critical term **bolded**: the single most important takeaway for C1's commercial strategy>"
}}

IMPORTANT:
- monthly_narratives must be in chronological order (oldest first)
- Include one entry per month from the timeline data
- Reference specific companies, earnings quotes, or SEC filings when they strengthen the narrative
- Do NOT just list themes — tell a STORY with causality and connections
- The key_insight should be specific and actionable for a composites distributor"""


@router.post("/{industry}/narrative")
async def generate_industry_narrative(industry: str):
    """Generate LLM-synthesized narrative for an industry's 90-day timeline."""
    start_time = time.time()
    logger.info(f"[INDUSTRY_NARRATIVES] Narrative generation START: {industry}")

    try:
        # 1. Get timeline data (reuse existing logic — uses _compute_window_start() internally)
        timeline_response = await get_industry_timeline(industry)
        monthly_data = timeline_response.get("monthly_data", [])
        display_name = timeline_response.get("industry", industry)
        totals = timeline_response.get("totals", {})

        if not monthly_data:
            raise HTTPException(
                status_code=404,
                detail=f"No timeline data found for '{display_name}' in the last 90 days",
            )

        # 2. Extract top companies for enrichment queries
        top_companies = _extract_top_companies(monthly_data)
        logger.info(
            f"[INDUSTRY_NARRATIVES] Top companies for enrichment: {top_companies}"
        )

        # 3. Fetch enrichment data (earnings quotes + SEC nuggets) in parallel
        all_earnings_quotes = []
        all_sec_nuggets = []
        seen_quote_ids = set()
        seen_nugget_ids = set()
        enrichment_sources = 0

        bq_storage = await _get_bq_storage()
        if bq_storage:
            enrich_start = time.time()

            # Build coroutines for parallel fetching
            async def fetch_earnings(company: str):
                try:
                    return await bq_storage.get_earnings_quotes(
                        search_query=company,
                        quotable_only=True,
                        min_relevance=0.3,
                        limit=3,
                    )
                except Exception as e:
                    logger.warning(f"[INDUSTRY_NARRATIVES] Earnings fetch failed for '{company}': {e}")
                    return []

            async def fetch_sec(company: str):
                try:
                    return await bq_storage.get_sec_filing_nuggets(
                        search_query=company,
                        min_relevance=0.3,
                        limit=3,
                    )
                except Exception as e:
                    logger.warning(f"[INDUSTRY_NARRATIVES] SEC fetch failed for '{company}': {e}")
                    return []

            # Run all enrichment queries in parallel
            tasks = []
            for company in top_companies:
                tasks.append(("earnings", company, fetch_earnings(company)))
                tasks.append(("sec", company, fetch_sec(company)))

            results = await asyncio.gather(
                *[t[2] for t in tasks], return_exceptions=True
            )

            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    continue
                query_type = tasks[i][0]
                if query_type == "earnings":
                    for q in result:
                        qid = q.get("quote_id", q.get("id", ""))
                        if qid and qid not in seen_quote_ids:
                            seen_quote_ids.add(qid)
                            all_earnings_quotes.append(q)
                elif query_type == "sec":
                    for n in result:
                        nid = n.get("nugget_id", n.get("id", ""))
                        if nid and nid not in seen_nugget_ids:
                            seen_nugget_ids.add(nid)
                            all_sec_nuggets.append(n)

            # Sort by relevance and cap
            all_earnings_quotes.sort(
                key=lambda x: x.get("relevance_score", 0), reverse=True
            )
            all_earnings_quotes = all_earnings_quotes[:10]
            all_sec_nuggets.sort(
                key=lambda x: x.get("relevance_score", 0), reverse=True
            )
            all_sec_nuggets = all_sec_nuggets[:10]
            enrichment_sources = len(all_earnings_quotes) + len(all_sec_nuggets)

            enrich_elapsed = time.time() - enrich_start
            logger.info(
                f"[INDUSTRY_NARRATIVES] Enrichment COMPLETE: {enrich_elapsed:.2f}s, "
                f"{len(all_earnings_quotes)} quotes, {len(all_sec_nuggets)} SEC nuggets"
            )
        else:
            logger.warning("[INDUSTRY_NARRATIVES] BigQuery storage unavailable, skipping enrichment")

        # 4. Build prompt
        compressed_monthly = _compress_monthly_for_prompt(monthly_data)
        enrichment_text = _format_enrichment_for_prompt(
            all_earnings_quotes, all_sec_nuggets
        )
        prompt = _build_narrative_prompt(
            industry=display_name,
            compressed_monthly=compressed_monthly,
            enrichment_text=enrichment_text,
            total_articles=totals.get("total_articles", 0),
            num_months=len(monthly_data),
        )

        # 5. Call Claude Sonnet via resilient client
        from app.config.settings import settings
        from app.utils.resilient_llm import get_resilient_async_client

        client = get_resilient_async_client(
            anthropic_api_key=settings.anthropic_api_key,
            openai_api_key=settings.openai_api_key,
        )

        llm_start = time.time()
        try:
            response = await asyncio.wait_for(
                client.messages_create(
                    model="claude-opus-4-5-20250514",
                    max_tokens=8192,
                    system=NARRATIVE_SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": prompt}],
                ),
                timeout=180.0,  # Opus may take longer
            )
            llm_elapsed = time.time() - llm_start
            logger.info(f"[INDUSTRY_NARRATIVES] LLM call COMPLETE: {llm_elapsed:.2f}s")
        except asyncio.TimeoutError:
            llm_elapsed = time.time() - llm_start
            logger.error(f"[INDUSTRY_NARRATIVES] LLM call TIMEOUT: {llm_elapsed:.2f}s")
            raise HTTPException(
                status_code=504,
                detail="Narrative generation timed out. Please try again.",
            )

        # 6. Parse JSON response
        raw_text = response.content[0].text.strip()
        # Strip markdown code fences if present
        if raw_text.startswith("```"):
            raw_text = raw_text.split("\n", 1)[1] if "\n" in raw_text else raw_text[3:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3].strip()

        try:
            narrative_data = json.loads(raw_text)
        except json.JSONDecodeError:
            logger.error(f"[INDUSTRY_NARRATIVES] Failed to parse LLM JSON: {raw_text[:200]}")
            raise HTTPException(
                status_code=502,
                detail="Failed to parse narrative response. Please try again.",
            )

        total_elapsed = time.time() - start_time
        logger.info(
            f"[INDUSTRY_NARRATIVES] Narrative generation COMPLETE: {display_name}, "
            f"{total_elapsed:.2f}s total, {enrichment_sources} enrichment sources"
        )

        return {
            "industry": display_name,
            "industry_narrative": narrative_data.get("industry_narrative", ""),
            "monthly_narratives": narrative_data.get("monthly_narratives", []),
            "key_insight": narrative_data.get("key_insight", ""),
            "enrichment_sources_used": enrichment_sources,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(
            f"[INDUSTRY_NARRATIVES] Narrative generation FAILED: {elapsed:.2f}s, {e}",
            exc_info=True,
        )
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
