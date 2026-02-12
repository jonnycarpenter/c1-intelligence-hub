"""Deterministic quality metrics computed from existing BigQuery data.

No LLM calls — all metrics are derived from stored report metadata
(confidence levels, citation counts, validation status, etc.).

Usage:
    from app.evals.quality_metrics import compute_quality_report
    report = await compute_quality_report(days_back=30)
"""

import json
from datetime import datetime, timezone, timedelta
from typing import Any, Dict

from app.utils.logger import get_logger

logger = get_logger(__name__)


async def compute_quality_report(days_back: int = 30, period_end: str = None) -> Dict[str, Any]:
    """Compute quality metrics across deep research reports and weekly briefings.

    Args:
        days_back: Number of days to look back for metrics.
        period_end: Optional ISO timestamp — if provided, metrics are computed
                    for the window [cutoff, period_end) instead of [cutoff, now).
                    Used for T3.8 previous-period comparison.

    Returns:
        Dictionary with quality metrics organized by report type.
    """
    from google.cloud import bigquery
    from app.db.gcp_storage import get_storage

    storage = await get_storage()
    client = storage.client
    dataset = storage.config.full_dataset_id
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days_back)).isoformat()

    logger.info(f"[EVAL_METRICS] Computing quality report for last {days_back} days")

    deep_research = await _compute_deep_research_metrics(client, dataset, cutoff, period_end)
    weekly_briefing = await _compute_weekly_briefing_metrics(client, dataset, cutoff, period_end)

    report = {
        "period_days": days_back,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "deep_research": deep_research,
        "weekly_briefing": weekly_briefing,
    }

    logger.info(
        f"[EVAL_METRICS] Quality report complete: "
        f"{deep_research['total_reports']} research reports, "
        f"{weekly_briefing['total_briefings']} briefings"
    )
    return report


async def _compute_deep_research_metrics(
    client: Any, dataset: str, cutoff: str, period_end: str = None
) -> Dict[str, Any]:
    """Compute metrics for deep research reports."""
    from google.cloud import bigquery

    end_clause = "AND created_at < @period_end" if period_end else ""
    query = f"""
        SELECT
            COUNT(*) as total_reports,
            AVG(citation_count) as avg_citation_count,
            AVG(citation_issues_count) as avg_citation_issues,
            AVG(SAFE_DIVIDE(citation_count - citation_issues_count, citation_count)) as citation_health_rate,
            AVG(research_time_seconds) as avg_research_time_seconds,
            AVG(sources_count) as avg_sources_count,
            COUNTIF(validation_passed = TRUE) as validation_passed_count,
            COUNTIF(validation_passed = FALSE) as validation_failed_count,
            COUNTIF(overall_confidence = 'high') as confidence_high,
            COUNTIF(overall_confidence = 'medium') as confidence_medium,
            COUNTIF(overall_confidence = 'low') as confidence_low,
            COUNTIF(data_completeness = 'complete') as completeness_complete,
            COUNTIF(data_completeness = 'partial') as completeness_partial,
            COUNTIF(data_completeness = 'limited') as completeness_limited,
        FROM `{dataset}.deep_research_reports`
        WHERE created_at >= @cutoff {end_clause}
    """

    params = [bigquery.ScalarQueryParameter("cutoff", "TIMESTAMP", cutoff)]
    if period_end:
        params.append(bigquery.ScalarQueryParameter("period_end", "TIMESTAMP", period_end))
    job_config = bigquery.QueryJobConfig(query_parameters=params)

    results = list(client.query(query, job_config=job_config).result())

    if not results or results[0].total_reports == 0:
        return {"total_reports": 0}

    row = results[0]
    total = row.total_reports

    return {
        "total_reports": total,
        "avg_citation_count": round(float(row.avg_citation_count or 0), 1),
        "avg_citation_issues": round(float(row.avg_citation_issues or 0), 1),
        "citation_health_rate": round(float(row.citation_health_rate or 0) * 100, 1),
        "validation_pass_rate": round((row.validation_passed_count / total) * 100, 1) if total else 0,
        "avg_research_time_seconds": round(float(row.avg_research_time_seconds or 0), 1),
        "avg_sources_count": round(float(row.avg_sources_count or 0), 1),
        "confidence_distribution": {
            "high": row.confidence_high,
            "medium": row.confidence_medium,
            "low": row.confidence_low,
        },
        "data_completeness": {
            "complete": row.completeness_complete,
            "partial": row.completeness_partial,
            "limited": row.completeness_limited,
        },
    }


async def _compute_weekly_briefing_metrics(
    client: Any, dataset: str, cutoff: str, period_end: str = None
) -> Dict[str, Any]:
    """Compute metrics for weekly briefings."""
    from google.cloud import bigquery

    end_clause = "AND generated_at < @period_end" if period_end else ""
    query = f"""
        SELECT
            COUNT(*) as total_briefings,
            AVG(ARRAY_LENGTH(JSON_EXTRACT_ARRAY(sections))) as avg_section_count,
        FROM `{dataset}.weekly_briefings`
        WHERE generated_at >= @cutoff {end_clause}
            AND sections IS NOT NULL
            AND sections != '[]'
    """

    params = [bigquery.ScalarQueryParameter("cutoff", "TIMESTAMP", cutoff)]
    if period_end:
        params.append(bigquery.ScalarQueryParameter("period_end", "TIMESTAMP", period_end))
    job_config = bigquery.QueryJobConfig(query_parameters=params)

    try:
        results = list(client.query(query, job_config=job_config).result())
    except Exception as e:
        logger.warning(f"[EVAL_METRICS] Weekly briefing query failed: {e}")
        return {"total_briefings": 0}

    if not results or results[0].total_briefings == 0:
        return {"total_briefings": 0}

    row = results[0]

    return {
        "total_briefings": row.total_briefings,
        "avg_section_count": round(float(row.avg_section_count or 0), 1),
    }
