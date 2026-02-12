"""Evals dashboard API — serves quality, cost, judge, feedback, ingestion health,
anomaly detection, alerts, pricing management, and trend data."""

import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.db.gcp_storage import get_storage
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


# ── Request models ──

class RunEvalRequest(BaseModel):
    count: int = 5
    model: str = "claude-haiku-4-5"


class UpdateThresholdsRequest(BaseModel):
    cost_usd: Optional[float] = None
    daily_cost_usd: Optional[float] = None
    quality_min: Optional[float] = None
    feedback_negative_rate: Optional[float] = None
    ingestion_stale_hours: Optional[float] = None


class UpdatePricingRequest(BaseModel):
    model: str
    input_price: float  # USD per 1M tokens
    output_price: float  # USD per 1M tokens


@router.get("/dashboard")
async def get_eval_dashboard(days: int = 30, compare: bool = False):
    """Return unified eval dashboard data (quality, cost, judge scores, feedback).

    If compare=True, also returns previous_period data for delta comparison (T3.8).
    """
    from google.cloud import bigquery
    from app.evals.quality_metrics import compute_quality_report

    # Flush any buffered token records before querying
    try:
        from app.evals.token_tracker import token_tracker
        await token_tracker.flush_to_bigquery()
    except Exception:
        pass

    storage = await get_storage()
    client = storage.client
    dataset = storage.config.full_dataset_id
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("cutoff", "TIMESTAMP", cutoff)]
    )

    # Run all queries
    quality = await compute_quality_report(days_back=days)
    judge = _get_judge_scores(client, dataset, cutoff, job_config)
    cost = _get_cost_summary(client, dataset, cutoff, job_config)
    feedback = _get_feedback_summary(client, dataset, cutoff, job_config)

    # T4.3: Anomaly detection
    anomalies = []
    try:
        from app.evals.anomaly_detection import detect_anomalies
        anomalies = await detect_anomalies(days_back=days)
    except Exception as e:
        logger.warning(f"[EVALS] Anomaly detection failed: {e}")

    result = {
        "period_days": days,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "quality_metrics": quality,
        "llm_judge_scores": judge,
        "token_usage_and_cost": cost,
        "user_feedback": feedback,
        "anomalies": anomalies,
    }

    # T3.8: Date range comparison — previous period
    if compare:
        prev_start = (datetime.now(timezone.utc) - timedelta(days=days * 2)).isoformat()
        prev_end = cutoff  # previous period ends where current begins

        prev_job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("cutoff", "TIMESTAMP", prev_start),
                bigquery.ScalarQueryParameter("period_end", "TIMESTAMP", prev_end),
            ]
        )

        prev_cost = _get_cost_summary(client, dataset, prev_start, prev_job_config, period_end=prev_end)
        prev_judge = _get_judge_scores(client, dataset, prev_start, prev_job_config, period_end=prev_end)
        prev_feedback = _get_feedback_summary(client, dataset, prev_start, prev_job_config, period_end=prev_end)
        prev_quality = await compute_quality_report(days_back=days * 2, period_end=cutoff)

        result["previous_period"] = {
            "token_usage_and_cost": prev_cost,
            "llm_judge_scores": prev_judge,
            "user_feedback": prev_feedback,
            "quality_metrics": prev_quality,
        }

    return result


# ── T3.1: Run Eval endpoints ──

@router.post("/run-judge")
async def run_eval_judge(request: RunEvalRequest):
    """Trigger an LLM-as-Judge evaluation batch in the background."""
    from app.evals.llm_judge import run_eval_batch, get_eval_job_status

    status = get_eval_job_status()
    if status["running"]:
        return {"status": "already_running", "message": "An evaluation is already in progress"}

    # Fire-and-forget background task
    asyncio.create_task(run_eval_batch(count=request.count, model=request.model))
    logger.info(f"[EVALS] Started eval batch: count={request.count}, model={request.model}")

    return {"status": "started", "count": request.count, "model": request.model}


@router.get("/run-judge/status")
async def get_eval_judge_status():
    """Check if an eval job is running and get last run result."""
    from app.evals.llm_judge import get_eval_job_status
    return get_eval_job_status()


# ── T3.4: Per-report eval results ──

@router.get("/reports")
async def get_eval_reports(days: int = 30, limit: int = 20):
    """Return individual eval results with report metadata."""
    from google.cloud import bigquery

    storage = await get_storage()
    client = storage.client
    dataset = storage.config.full_dataset_id
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    query = f"""
        SELECT e.id, e.report_id, e.eval_model,
               e.factual_grounding_score, e.factual_grounding_reasoning,
               e.coherence_score, e.coherence_reasoning,
               e.actionability_score, e.actionability_reasoning,
               e.overall_score, e.overall_reasoning,
               e.eval_time_seconds, e.created_at,
               r.query, r.overall_confidence, r.sources_count
        FROM `{dataset}.eval_results` e
        LEFT JOIN `{dataset}.deep_research_reports` r ON e.report_id = r.id
        WHERE e.created_at >= @cutoff
        ORDER BY e.created_at DESC
        LIMIT @limit
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("cutoff", "TIMESTAMP", cutoff),
            bigquery.ScalarQueryParameter("limit", "INT64", limit),
        ]
    )

    try:
        rows = list(client.query(query, job_config=job_config).result())
        return {
            "reports": [
                {
                    "id": r.id,
                    "report_id": r.report_id,
                    "eval_model": r.eval_model,
                    "factual_grounding_score": r.factual_grounding_score,
                    "factual_grounding_reasoning": r.factual_grounding_reasoning,
                    "coherence_score": r.coherence_score,
                    "coherence_reasoning": r.coherence_reasoning,
                    "actionability_score": r.actionability_score,
                    "actionability_reasoning": r.actionability_reasoning,
                    "overall_score": r.overall_score,
                    "overall_reasoning": r.overall_reasoning,
                    "eval_time_seconds": r.eval_time_seconds,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "query": r.query,
                    "overall_confidence": r.overall_confidence,
                    "sources_count": r.sources_count,
                }
                for r in rows
            ],
            "total": len(rows),
        }
    except Exception as e:
        logger.warning(f"[EVALS] Eval reports query failed: {e}")
        return {"reports": [], "total": 0}


def _get_judge_scores(client, dataset: str, cutoff: str, job_config, period_end: str = None) -> dict:
    end_clause = "AND created_at < @period_end" if period_end else ""
    query = f"""
        SELECT
            COUNT(*) as total_evals,
            AVG(factual_grounding_score) as avg_factual_grounding,
            AVG(coherence_score) as avg_coherence,
            AVG(actionability_score) as avg_actionability,
            AVG(overall_score) as avg_overall,
        FROM `{dataset}.eval_results`
        WHERE created_at >= @cutoff {end_clause}
    """
    try:
        results = list(client.query(query, job_config=job_config).result())
        row = results[0] if results else None
        if not row or row.total_evals == 0:
            return {"total_evals": 0}
        return {
            "total_evals": row.total_evals,
            "avg_factual_grounding": round(float(row.avg_factual_grounding or 0), 1),
            "avg_coherence": round(float(row.avg_coherence or 0), 1),
            "avg_actionability": round(float(row.avg_actionability or 0), 1),
            "avg_overall": round(float(row.avg_overall or 0), 1),
        }
    except Exception as e:
        logger.warning(f"[EVALS] Judge scores query failed: {e}")
        return {"total_evals": 0}


def _get_cost_summary(client, dataset: str, cutoff: str, job_config, period_end: str = None) -> dict:
    end_clause = "AND created_at < @period_end" if period_end else ""
    query = f"""
        SELECT
            COUNT(*) as total_calls,
            SUM(input_tokens) as total_input_tokens,
            SUM(output_tokens) as total_output_tokens,
            SUM(total_tokens) as total_tokens,
            SUM(estimated_cost_usd) as total_cost_usd,
        FROM `{dataset}.llm_token_usage`
        WHERE created_at >= @cutoff {end_clause}
    """
    try:
        results = list(client.query(query, job_config=job_config).result())
        row = results[0] if results else None
        if not row or row.total_calls == 0:
            return {"total_calls": 0, "note": "No token usage data yet."}

        # By model breakdown
        model_query = f"""
            SELECT model, COUNT(*) as calls,
                   SUM(estimated_cost_usd) as cost_usd,
                   SUM(total_tokens) as tokens
            FROM `{dataset}.llm_token_usage`
            WHERE created_at >= @cutoff {end_clause}
            GROUP BY model
            ORDER BY cost_usd DESC
        """
        model_rows = list(client.query(model_query, job_config=job_config).result())
        by_model = [
            {
                "model": r.model,
                "calls": r.calls,
                "cost_usd": round(float(r.cost_usd or 0), 4),
                "tokens": int(r.tokens or 0),
            }
            for r in model_rows
        ]

        # By caller breakdown
        caller_query = f"""
            SELECT caller, COUNT(*) as calls,
                   SUM(estimated_cost_usd) as cost_usd,
                   SUM(total_tokens) as tokens
            FROM `{dataset}.llm_token_usage`
            WHERE created_at >= @cutoff {end_clause}
            GROUP BY caller
            ORDER BY cost_usd DESC
            LIMIT 10
        """
        caller_rows = list(client.query(caller_query, job_config=job_config).result())
        by_caller = [
            {
                "caller": r.caller,
                "calls": r.calls,
                "cost_usd": round(float(r.cost_usd or 0), 4),
                "tokens": int(r.tokens or 0),
            }
            for r in caller_rows
        ]

        # Daily cost trend (for chart)
        daily_query = f"""
            SELECT DATE(created_at) as day,
                   COUNT(*) as calls,
                   SUM(estimated_cost_usd) as cost_usd,
                   SUM(total_tokens) as tokens
            FROM `{dataset}.llm_token_usage`
            WHERE created_at >= @cutoff {end_clause}
            GROUP BY day
            ORDER BY day
        """
        daily_rows = list(client.query(daily_query, job_config=job_config).result())
        daily_trend = [
            {
                "date": r.day.isoformat(),
                "calls": r.calls,
                "cost_usd": round(float(r.cost_usd or 0), 4),
                "tokens": int(r.tokens or 0),
            }
            for r in daily_rows
        ]

        return {
            "total_calls": row.total_calls,
            "total_input_tokens": int(row.total_input_tokens or 0),
            "total_output_tokens": int(row.total_output_tokens or 0),
            "total_tokens": int(row.total_tokens or 0),
            "total_cost_usd": round(float(row.total_cost_usd or 0), 4),
            "by_model": by_model,
            "by_caller": by_caller,
            "daily_trend": daily_trend,
        }
    except Exception as e:
        logger.warning(f"[EVALS] Cost summary query failed: {e}")
        return {"total_calls": 0, "note": f"Query failed: {e}"}


def _get_feedback_summary(client, dataset: str, cutoff: str, job_config, period_end: str = None) -> dict:
    end_clause = "AND created_at < @period_end" if period_end else ""
    query = f"""
        SELECT
            COUNT(*) as total_feedback,
            COUNTIF(rating = 'positive') as positive_count,
            COUNTIF(rating = 'negative') as negative_count,
        FROM `{dataset}.user_feedback`
        WHERE created_at >= @cutoff {end_clause}
    """
    try:
        results = list(client.query(query, job_config=job_config).result())
        row = results[0] if results else None
        if not row or row.total_feedback == 0:
            return {"total_feedback": 0}
        total = row.total_feedback
        positive = row.positive_count

        # T3.2: Recent comments
        recent_comments = []
        try:
            comments_query = f"""
                SELECT report_type, rating, comment, created_at
                FROM `{dataset}.user_feedback`
                WHERE created_at >= @cutoff {end_clause}
                  AND comment IS NOT NULL AND comment != ''
                ORDER BY created_at DESC
                LIMIT 5
            """
            comments_rows = list(client.query(comments_query, job_config=job_config).result())
            recent_comments = [
                {
                    "report_type": r.report_type,
                    "rating": r.rating,
                    "comment": r.comment,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in comments_rows
            ]
        except Exception as ce:
            logger.warning(f"[EVALS] Recent comments query failed: {ce}")

        return {
            "total_feedback": total,
            "positive_count": positive,
            "negative_count": row.negative_count,
            "positive_rate": round(positive / total, 2) if total > 0 else 0,
            "recent_comments": recent_comments,
        }
    except Exception as e:
        logger.warning(f"[EVALS] Feedback summary query failed: {e}")
        return {"total_feedback": 0}


# ══════════════════════════════════════════════════════════════════════
# T4.2: Ingestion Health
# ══════════════════════════════════════════════════════════════════════

@router.get("/ingestion-health")
async def get_ingestion_health(days: int = 30):
    """Return ingestion pipeline health metrics: per-source status, error rates, trends."""
    from google.cloud import bigquery

    storage = await get_storage()
    client = storage.client
    dataset = storage.config.full_dataset_id
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("cutoff", "TIMESTAMP", cutoff),
        ]
    )

    # ── Source health from ingestion_events ──
    sources_health = []
    try:
        events_query = f"""
            SELECT event_type, status, timestamp, metadata, error_message, metrics
            FROM `{dataset}.ingestion_events`
            WHERE timestamp >= @cutoff
            ORDER BY timestamp DESC
        """
        rows = list(client.query(events_query, job_config=job_config).result())

        # Parse events to compute per-source health
        source_stats: Dict[str, Dict[str, Any]] = {}
        total_events = {"completed": 0, "failed": 0, "started": 0}

        for row in rows:
            ev_type = row.event_type
            total_events[ev_type.lower()] = total_events.get(ev_type.lower(), 0) + 1

            # Extract sources from metadata
            sources_list = []
            if row.metadata:
                try:
                    meta = json.loads(row.metadata)
                    sources_list = meta.get("sources", [])
                except (json.JSONDecodeError, TypeError):
                    pass

            for source in sources_list:
                if source not in source_stats:
                    source_stats[source] = {
                        "source": source,
                        "total_runs": 0,
                        "successes": 0,
                        "failures": 0,
                        "last_run": None,
                        "last_success": None,
                        "last_error": None,
                    }
                stats = source_stats[source]

                if ev_type == "STARTED":
                    stats["total_runs"] += 1
                    if not stats["last_run"] or row.timestamp > stats["last_run"]:
                        stats["last_run"] = row.timestamp

                if ev_type == "COMPLETED" and row.status == "success":
                    stats["successes"] += 1
                    if not stats["last_success"] or row.timestamp > stats["last_success"]:
                        stats["last_success"] = row.timestamp

                if ev_type == "FAILED":
                    stats["failures"] += 1
                    if not stats["last_error"]:
                        stats["last_error"] = row.error_message

        # Compute status and build response
        now = datetime.now(timezone.utc)
        for source, stats in source_stats.items():
            hours_since_run = None
            if stats["last_run"]:
                last_run_ts = stats["last_run"]
                if last_run_ts.tzinfo is None:
                    last_run_ts = last_run_ts.replace(tzinfo=timezone.utc)
                hours_since_run = round((now - last_run_ts).total_seconds() / 3600, 1)

            # Status: green if ran in <24h with success, yellow if <48h, red if >48h or all fails
            status = "green"
            if hours_since_run is None or hours_since_run > 48:
                status = "red"
            elif hours_since_run > 24 or stats["failures"] > stats["successes"]:
                status = "yellow"

            error_rate = round(stats["failures"] / stats["total_runs"] * 100, 1) if stats["total_runs"] > 0 else 0

            sources_health.append({
                "source": source,
                "status": status,
                "total_runs": stats["total_runs"],
                "successes": stats["successes"],
                "failures": stats["failures"],
                "error_rate": error_rate,
                "hours_since_last_run": hours_since_run,
                "last_run": stats["last_run"].isoformat() if stats["last_run"] else None,
                "last_success": stats["last_success"].isoformat() if stats["last_success"] else None,
                "last_error": stats["last_error"],
            })

    except Exception as e:
        logger.warning(f"[EVALS] Ingestion events query failed: {e}")

    # ── Articles per day trend ──
    articles_trend = []
    source_article_counts: Dict[str, Dict[str, Any]] = {}  # also used for fallback
    try:
        articles_query = f"""
            SELECT DATE(created_at) as day,
                   COUNT(*) as articles,
                   source_type
            FROM `{dataset}.articles`
            WHERE created_at >= @cutoff
            GROUP BY day, source_type
            ORDER BY day
        """
        article_rows = list(client.query(articles_query, job_config=job_config).result())

        day_totals: Dict[str, int] = {}
        now = datetime.now(timezone.utc)
        cutoff_24h = (now - timedelta(hours=24)).date()

        for r in article_rows:
            day = r.day.isoformat()
            day_totals[day] = day_totals.get(day, 0) + r.articles

            # Track per-source counts for fallback health
            src = r.source_type or "unknown"
            if src not in source_article_counts:
                source_article_counts[src] = {"total": 0, "last_24h": 0, "last_day": None}
            source_article_counts[src]["total"] += r.articles
            if r.day >= cutoff_24h:
                source_article_counts[src]["last_24h"] += r.articles
            if source_article_counts[src]["last_day"] is None or r.day > source_article_counts[src]["last_day"]:
                source_article_counts[src]["last_day"] = r.day

        articles_trend = [
            {"date": day, "articles": count}
            for day, count in sorted(day_totals.items())
        ]

    except Exception as e:
        logger.warning(f"[EVALS] Articles trend query failed: {e}")

    # ── Fallback: derive source health from articles table if ingestion_events is empty ──
    if not sources_health and source_article_counts:
        now = datetime.now(timezone.utc)
        for src, counts in source_article_counts.items():
            hours_since = None
            if counts["last_day"]:
                last_dt = datetime.combine(counts["last_day"], datetime.min.time()).replace(tzinfo=timezone.utc)
                hours_since = round((now - last_dt).total_seconds() / 3600, 1)

            status = "green"
            if hours_since is None or hours_since > 48:
                status = "red"
            elif hours_since > 24:
                status = "yellow"

            avg_daily = round(counts["total"] / max(days, 1), 1)
            sources_health.append({
                "source": src,
                "status": status,
                "total_runs": counts["total"],
                "successes": counts["total"],
                "failures": 0,
                "error_rate": 0,
                "hours_since_last_run": hours_since,
                "last_run": counts["last_day"].isoformat() if counts["last_day"] else None,
                "last_success": counts["last_day"].isoformat() if counts["last_day"] else None,
                "last_error": None,
                "articles_24h": counts["last_24h"],
                "avg_daily": avg_daily,
            })

    # Sort sources by status priority (red first, then yellow, then green)
    status_order = {"red": 0, "yellow": 1, "green": 2}
    sources_health.sort(key=lambda s: status_order.get(s["status"], 3))

    return {
        "sources": sources_health,
        "articles_trend": articles_trend,
        "summary": {
            "total_sources": len(sources_health),
            "healthy": sum(1 for s in sources_health if s["status"] == "green"),
            "warning": sum(1 for s in sources_health if s["status"] == "yellow"),
            "error": sum(1 for s in sources_health if s["status"] == "red"),
        },
    }


# ══════════════════════════════════════════════════════════════════════
# T4.4: Alerts
# ══════════════════════════════════════════════════════════════════════

@router.get("/alerts")
async def get_alerts(days: int = 7):
    """Get recent eval alerts."""
    from app.evals.alerts import get_recent_alerts
    alerts = await get_recent_alerts(days=days)
    return {"alerts": alerts, "total": len(alerts)}


@router.get("/alerts/thresholds")
async def get_alert_thresholds():
    """Get current alert threshold configuration."""
    from app.evals.alerts import get_thresholds
    return {"thresholds": get_thresholds()}


@router.post("/alerts/thresholds")
async def update_alert_thresholds(request: UpdateThresholdsRequest):
    """Update alert threshold configuration."""
    from app.evals.alerts import update_thresholds
    updates = {k: v for k, v in request.dict().items() if v is not None}
    new_thresholds = update_thresholds(updates)
    return {"thresholds": new_thresholds, "updated": list(updates.keys())}


# ══════════════════════════════════════════════════════════════════════
# T4.5: Model Pricing Management
# ══════════════════════════════════════════════════════════════════════

@router.get("/pricing")
async def get_model_pricing():
    """Get current model pricing table."""
    from app.evals.token_tracker import MODEL_PRICING, DEFAULT_PRICING
    return {
        "models": {
            model: {"input": price["input"], "output": price["output"]}
            for model, price in MODEL_PRICING.items()
        },
        "default": DEFAULT_PRICING,
    }


@router.post("/pricing")
async def update_model_pricing(request: UpdatePricingRequest):
    """Update pricing for a specific model."""
    from app.evals.token_tracker import MODEL_PRICING

    MODEL_PRICING[request.model] = {
        "input": request.input_price,
        "output": request.output_price,
    }
    logger.info(f"[EVALS] Updated pricing for {request.model}: in=${request.input_price}, out=${request.output_price}")

    return {
        "model": request.model,
        "input": request.input_price,
        "output": request.output_price,
        "status": "updated",
    }


# ══════════════════════════════════════════════════════════════════════
# T4.6: Eval Score Trends Over Time
# ══════════════════════════════════════════════════════════════════════

@router.get("/trends")
async def get_eval_trends(weeks: int = 12):
    """Return weekly aggregated eval score trends."""
    from google.cloud import bigquery

    storage = await get_storage()
    client = storage.client
    dataset = storage.config.full_dataset_id
    cutoff = (datetime.now(timezone.utc) - timedelta(weeks=weeks)).isoformat()

    # Weekly eval score trends
    query = f"""
        SELECT
            DATE_TRUNC(created_at, WEEK(MONDAY)) as week,
            AVG(overall_score) as avg_overall,
            AVG(factual_grounding_score) as avg_factual,
            AVG(coherence_score) as avg_coherence,
            AVG(actionability_score) as avg_actionability,
            COUNT(*) as eval_count
        FROM `{dataset}.eval_results`
        WHERE created_at >= @cutoff
        GROUP BY week
        ORDER BY week
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("cutoff", "TIMESTAMP", cutoff),
        ]
    )

    eval_trends = []
    try:
        rows = list(client.query(query, job_config=job_config).result())
        eval_trends = [
            {
                "week": r.week.isoformat() if r.week else None,
                "avg_overall": round(float(r.avg_overall or 0), 2),
                "avg_factual": round(float(r.avg_factual or 0), 2),
                "avg_coherence": round(float(r.avg_coherence or 0), 2),
                "avg_actionability": round(float(r.avg_actionability or 0), 2),
                "eval_count": r.eval_count,
            }
            for r in rows
        ]
    except Exception as e:
        logger.warning(f"[EVALS] Eval trends query failed: {e}")

    # Weekly cost trends
    cost_query = f"""
        SELECT
            DATE_TRUNC(created_at, WEEK(MONDAY)) as week,
            SUM(estimated_cost_usd) as total_cost,
            SUM(total_tokens) as total_tokens,
            COUNT(*) as total_calls
        FROM `{dataset}.llm_token_usage`
        WHERE created_at >= @cutoff
        GROUP BY week
        ORDER BY week
    """

    cost_trends = []
    try:
        cost_rows = list(client.query(cost_query, job_config=job_config).result())
        cost_trends = [
            {
                "week": r.week.isoformat() if r.week else None,
                "total_cost": round(float(r.total_cost or 0), 4),
                "total_tokens": int(r.total_tokens or 0),
                "total_calls": r.total_calls,
            }
            for r in cost_rows
        ]
    except Exception as e:
        logger.warning(f"[EVALS] Cost trends query failed: {e}")

    return {
        "eval_trends": eval_trends,
        "cost_trends": cost_trends,
        "weeks": weeks,
    }
