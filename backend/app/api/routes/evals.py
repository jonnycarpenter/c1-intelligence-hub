"""Evals dashboard API — serves quality, cost, judge, and feedback data."""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter

from app.db.gcp_storage import get_storage
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get("/dashboard")
async def get_eval_dashboard(days: int = 30):
    """Return unified eval dashboard data (quality, cost, judge scores, feedback)."""
    from google.cloud import bigquery
    from app.evals.quality_metrics import compute_quality_report

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

    return {
        "period_days": days,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "quality_metrics": quality,
        "llm_judge_scores": judge,
        "token_usage_and_cost": cost,
        "user_feedback": feedback,
    }


def _get_judge_scores(client, dataset: str, cutoff: str, job_config) -> dict:
    query = f"""
        SELECT
            COUNT(*) as total_evals,
            AVG(factual_grounding_score) as avg_factual_grounding,
            AVG(coherence_score) as avg_coherence,
            AVG(actionability_score) as avg_actionability,
            AVG(overall_score) as avg_overall,
        FROM `{dataset}.eval_results`
        WHERE created_at >= @cutoff
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


def _get_cost_summary(client, dataset: str, cutoff: str, job_config) -> dict:
    query = f"""
        SELECT
            COUNT(*) as total_calls,
            SUM(input_tokens) as total_input_tokens,
            SUM(output_tokens) as total_output_tokens,
            SUM(total_tokens) as total_tokens,
            SUM(estimated_cost_usd) as total_cost_usd,
        FROM `{dataset}.llm_token_usage`
        WHERE created_at >= @cutoff
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
            WHERE created_at >= @cutoff
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
            WHERE created_at >= @cutoff
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
            WHERE created_at >= @cutoff
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


def _get_feedback_summary(client, dataset: str, cutoff: str, job_config) -> dict:
    query = f"""
        SELECT
            COUNT(*) as total_feedback,
            COUNTIF(rating = 'positive') as positive_count,
            COUNTIF(rating = 'negative') as negative_count,
        FROM `{dataset}.user_feedback`
        WHERE created_at >= @cutoff
    """
    try:
        results = list(client.query(query, job_config=job_config).result())
        row = results[0] if results else None
        if not row or row.total_feedback == 0:
            return {"total_feedback": 0}
        total = row.total_feedback
        positive = row.positive_count
        return {
            "total_feedback": total,
            "positive_count": positive,
            "negative_count": row.negative_count,
            "positive_rate": round(positive / total, 2) if total > 0 else 0,
        }
    except Exception as e:
        logger.warning(f"[EVALS] Feedback summary query failed: {e}")
        return {"total_feedback": 0}
