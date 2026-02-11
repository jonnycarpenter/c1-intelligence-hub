"""Anomaly detection for eval metrics.

Surfaces unusual patterns by comparing current values against
rolling averages. Uses simple z-score approach (>2 std deviations).

Usage:
    from app.evals.anomaly_detection import detect_anomalies
    anomalies = await detect_anomalies(days_back=30)
"""

import json
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List

from app.utils.logger import get_logger

logger = get_logger(__name__)


async def detect_anomalies(days_back: int = 30) -> List[Dict[str, Any]]:
    """Detect anomalies in key metrics by comparing current vs historical values.

    Compares last `days_back` period against the prior period (same length)
    to find significant deviations.

    Returns:
        List of anomaly dicts with: metric, current_value, expected_range, severity, description
    """
    from google.cloud import bigquery
    from app.db.gcp_storage import get_storage

    storage = await get_storage()
    client = storage.client
    dataset = storage.config.full_dataset_id

    now = datetime.now(timezone.utc)
    current_start = (now - timedelta(days=days_back)).isoformat()
    prev_start = (now - timedelta(days=days_back * 2)).isoformat()
    prev_end = current_start

    anomalies = []

    try:
        # ── 1. Daily cost anomalies ──
        anomalies.extend(await _check_cost_anomalies(client, dataset, days_back))

        # ── 2. Quality score anomalies ──
        anomalies.extend(await _check_quality_anomalies(client, dataset, current_start, prev_start, prev_end))

        # ── 3. Ingestion health anomalies ──
        anomalies.extend(await _check_ingestion_anomalies(client, dataset, days_back))

        # ── 4. Token usage spike detection ──
        anomalies.extend(await _check_token_spikes(client, dataset, days_back))

    except Exception as e:
        logger.warning(f"[ANOMALY] Detection failed: {e}", exc_info=True)

    # Sort by severity
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    anomalies.sort(key=lambda a: severity_order.get(a.get("severity", "info"), 2))

    logger.info(f"[ANOMALY] Detected {len(anomalies)} anomalies")
    return anomalies


async def _check_cost_anomalies(
    client, dataset: str, days_back: int
) -> List[Dict[str, Any]]:
    """Check for daily cost spikes compared to rolling average."""
    from google.cloud import bigquery

    query = f"""
        WITH daily_costs AS (
            SELECT DATE(created_at) as day,
                   SUM(estimated_cost_usd) as daily_cost
            FROM `{dataset}.llm_token_usage`
            WHERE created_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {days_back * 2} DAY)
            GROUP BY day
        ),
        stats AS (
            SELECT
                AVG(daily_cost) as avg_cost,
                STDDEV(daily_cost) as stddev_cost
            FROM daily_costs
            WHERE day < DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY)
        ),
        recent AS (
            SELECT day, daily_cost
            FROM daily_costs
            WHERE day >= DATE_SUB(CURRENT_DATE(), INTERVAL 3 DAY)
            ORDER BY day DESC
            LIMIT 3
        )
        SELECT r.day, r.daily_cost, s.avg_cost, s.stddev_cost
        FROM recent r CROSS JOIN stats s
    """

    anomalies = []
    try:
        rows = list(client.query(query).result())
        for row in rows:
            if row.avg_cost and row.stddev_cost and row.stddev_cost > 0:
                z_score = (float(row.daily_cost) - float(row.avg_cost)) / float(row.stddev_cost)
                if z_score > 2:
                    severity = "critical" if z_score > 3 else "warning"
                    anomalies.append({
                        "metric": "daily_cost",
                        "current_value": round(float(row.daily_cost), 4),
                        "expected_range": f"${float(row.avg_cost) - float(row.stddev_cost):.2f}–${float(row.avg_cost) + float(row.stddev_cost):.2f}",
                        "severity": severity,
                        "description": f"Cost spike on {row.day}: ${float(row.daily_cost):.2f} (avg: ${float(row.avg_cost):.2f})",
                        "z_score": round(z_score, 1),
                    })
    except Exception as e:
        logger.warning(f"[ANOMALY] Cost anomaly check failed: {e}")

    return anomalies


async def _check_quality_anomalies(
    client, dataset: str, current_start: str, prev_start: str, prev_end: str
) -> List[Dict[str, Any]]:
    """Check for quality score drops."""
    from google.cloud import bigquery

    query = f"""
        WITH current_scores AS (
            SELECT AVG(overall_score) as avg_score, COUNT(*) as cnt
            FROM `{dataset}.eval_results`
            WHERE created_at >= @current_start
        ),
        prev_scores AS (
            SELECT AVG(overall_score) as avg_score, COUNT(*) as cnt
            FROM `{dataset}.eval_results`
            WHERE created_at >= @prev_start AND created_at < @prev_end
        )
        SELECT c.avg_score as current_avg, c.cnt as current_cnt,
               p.avg_score as prev_avg, p.cnt as prev_cnt
        FROM current_scores c CROSS JOIN prev_scores p
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("current_start", "TIMESTAMP", current_start),
            bigquery.ScalarQueryParameter("prev_start", "TIMESTAMP", prev_start),
            bigquery.ScalarQueryParameter("prev_end", "TIMESTAMP", prev_end),
        ]
    )

    anomalies = []
    try:
        rows = list(client.query(query, job_config=job_config).result())
        if rows and rows[0].current_avg and rows[0].prev_avg:
            row = rows[0]
            drop = float(row.prev_avg) - float(row.current_avg)
            if drop > 0.5 and float(row.current_cnt) >= 2:
                severity = "critical" if drop > 1.0 else "warning"
                anomalies.append({
                    "metric": "quality_score",
                    "current_value": round(float(row.current_avg), 1),
                    "expected_range": f"{float(row.prev_avg) - 0.5:.1f}–{float(row.prev_avg) + 0.5:.1f}",
                    "severity": severity,
                    "description": f"Quality drop: {float(row.current_avg):.1f}/5 (was {float(row.prev_avg):.1f}/5)",
                })
    except Exception as e:
        logger.warning(f"[ANOMALY] Quality anomaly check failed: {e}")

    return anomalies


async def _check_ingestion_anomalies(
    client, dataset: str, days_back: int
) -> List[Dict[str, Any]]:
    """Check for ingestion failures or stale sources."""
    anomalies = []

    try:
        # Check for recent failures
        query = f"""
            SELECT event_type, status, error_message, timestamp, metadata
            FROM `{dataset}.ingestion_events`
            WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {min(days_back, 7)} DAY)
              AND event_type = 'FAILED'
            ORDER BY timestamp DESC
            LIMIT 5
        """
        rows = list(client.query(query).result())

        if len(rows) >= 3:
            anomalies.append({
                "metric": "ingestion_failures",
                "current_value": len(rows),
                "expected_range": "0–1",
                "severity": "warning",
                "description": f"{len(rows)} ingestion failures in the last {min(days_back, 7)} days",
            })

        # Check time since last successful ingestion
        stale_query = f"""
            SELECT MAX(timestamp) as last_success
            FROM `{dataset}.ingestion_events`
            WHERE event_type = 'COMPLETED' AND status = 'success'
        """
        stale_rows = list(client.query(stale_query).result())
        if stale_rows and stale_rows[0].last_success:
            hours_since = (datetime.now(timezone.utc) - stale_rows[0].last_success.replace(tzinfo=timezone.utc)).total_seconds() / 3600
            if hours_since > 48:
                anomalies.append({
                    "metric": "ingestion_stale",
                    "current_value": round(hours_since, 1),
                    "expected_range": "0–24 hours",
                    "severity": "critical" if hours_since > 72 else "warning",
                    "description": f"No successful ingestion in {round(hours_since)}h (last: {stale_rows[0].last_success.strftime('%Y-%m-%d %H:%M')})",
                })

    except Exception as e:
        logger.warning(f"[ANOMALY] Ingestion anomaly check failed: {e}")

    return anomalies


async def _check_token_spikes(
    client, dataset: str, days_back: int
) -> List[Dict[str, Any]]:
    """Check for unusual token usage spikes by model."""
    anomalies = []

    try:
        query = f"""
            WITH daily AS (
                SELECT DATE(created_at) as day, model,
                       SUM(total_tokens) as tokens
                FROM `{dataset}.llm_token_usage`
                WHERE created_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {days_back} DAY)
                GROUP BY day, model
            ),
            model_stats AS (
                SELECT model,
                       AVG(tokens) as avg_tokens,
                       STDDEV(tokens) as std_tokens
                FROM daily
                GROUP BY model
                HAVING COUNT(*) >= 3
            ),
            today AS (
                SELECT model, tokens
                FROM daily
                WHERE day = CURRENT_DATE()
            )
            SELECT t.model, t.tokens, m.avg_tokens, m.std_tokens
            FROM today t
            JOIN model_stats m ON t.model = m.model
            WHERE m.std_tokens > 0 AND (t.tokens - m.avg_tokens) / m.std_tokens > 2.5
        """
        rows = list(client.query(query).result())
        for row in rows:
            anomalies.append({
                "metric": "token_spike",
                "current_value": int(row.tokens),
                "expected_range": f"{int(row.avg_tokens - row.std_tokens):,}–{int(row.avg_tokens + row.std_tokens):,}",
                "severity": "warning",
                "description": f"Token spike for {row.model}: {int(row.tokens):,} tokens today (avg: {int(row.avg_tokens):,})",
            })

    except Exception as e:
        logger.warning(f"[ANOMALY] Token spike check failed: {e}")

    return anomalies
