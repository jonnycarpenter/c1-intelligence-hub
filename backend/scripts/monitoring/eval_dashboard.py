#!/usr/bin/env python
"""Eval Dashboard — Unified quality, cost, and feedback summary.

Pulls together all evaluation data into a single formatted report.

Usage:
    cd backend
    python scripts/monitoring/eval_dashboard.py           # Last 30 days
    python scripts/monitoring/eval_dashboard.py --days 7   # Last 7 days
    python scripts/monitoring/eval_dashboard.py --json      # JSON output
"""

import argparse
import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def generate_dashboard(days: int = 30, output_json: bool = False):
    from app.evals.quality_metrics import compute_quality_report
    from app.db.gcp_storage import get_storage
    from google.cloud import bigquery

    storage = await get_storage()
    client = storage.client
    dataset = storage.config.full_dataset_id
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    # 1. Quality metrics
    quality = await compute_quality_report(days_back=days)

    # 2. LLM-as-judge scores
    judge_scores = await _get_judge_scores(client, dataset, cutoff)

    # 3. Token usage & cost
    cost_data = await _get_cost_summary(client, dataset, cutoff)

    # 4. User feedback
    feedback = await _get_feedback_summary(client, dataset, cutoff)

    dashboard = {
        "period_days": days,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "quality_metrics": quality,
        "llm_judge_scores": judge_scores,
        "token_usage_and_cost": cost_data,
        "user_feedback": feedback,
    }

    if output_json:
        print(json.dumps(dashboard, indent=2, default=str))
    else:
        _print_formatted(dashboard, days)


async def _get_judge_scores(client, dataset: str, cutoff: str) -> dict:
    from google.cloud import bigquery

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
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("cutoff", "TIMESTAMP", cutoff)]
    )
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
        logger.warning(f"Judge scores query failed: {e}")
        return {"total_evals": 0}


async def _get_cost_summary(client, dataset: str, cutoff: str) -> dict:
    from google.cloud import bigquery

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
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("cutoff", "TIMESTAMP", cutoff)]
    )

    try:
        results = list(client.query(query, job_config=job_config).result())
        row = results[0] if results else None
        if not row or row.total_calls == 0:
            return {"total_calls": 0, "note": "No token usage data yet. Data populates after LLM calls."}

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
        by_model = {
            r.model: {
                "calls": r.calls,
                "cost_usd": round(float(r.cost_usd or 0), 2),
                "tokens": int(r.tokens or 0),
            }
            for r in model_rows
        }

        # By caller breakdown
        caller_query = f"""
            SELECT caller, COUNT(*) as calls,
                   SUM(estimated_cost_usd) as cost_usd
            FROM `{dataset}.llm_token_usage`
            WHERE created_at >= @cutoff
            GROUP BY caller
            ORDER BY cost_usd DESC
            LIMIT 10
        """
        caller_rows = list(client.query(caller_query, job_config=job_config).result())
        by_caller = {
            r.caller: {
                "calls": r.calls,
                "cost_usd": round(float(r.cost_usd or 0), 2),
            }
            for r in caller_rows
        }

        return {
            "total_calls": row.total_calls,
            "total_input_tokens": int(row.total_input_tokens or 0),
            "total_output_tokens": int(row.total_output_tokens or 0),
            "total_tokens": int(row.total_tokens or 0),
            "total_cost_usd": round(float(row.total_cost_usd or 0), 2),
            "by_model": by_model,
            "by_caller": by_caller,
        }
    except Exception as e:
        logger.warning(f"Cost summary query failed: {e}")
        return {"total_calls": 0, "note": f"Query failed: {e}"}


async def _get_feedback_summary(client, dataset: str, cutoff: str) -> dict:
    from google.cloud import bigquery

    query = f"""
        SELECT
            COUNT(*) as total_feedback,
            COUNTIF(rating = 'positive') as positive_count,
            COUNTIF(rating = 'negative') as negative_count,
        FROM `{dataset}.user_feedback`
        WHERE created_at >= @cutoff
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("cutoff", "TIMESTAMP", cutoff)]
    )
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
        logger.warning(f"Feedback summary query failed: {e}")
        return {"total_feedback": 0}


def _print_formatted(dashboard: dict, days: int):
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days)

    print()
    print("=" * 70)
    print("  C1 Intelligence Hub — Eval Dashboard")
    print(f"  Period: {start.strftime('%Y-%m-%d')} to {now.strftime('%Y-%m-%d')}")
    print("=" * 70)

    # Quality Metrics
    dr = dashboard["quality_metrics"].get("deep_research", {})
    print(f"\n--- Quality Metrics (Deep Research) ---")
    if dr.get("total_reports", 0) == 0:
        print("  No reports in this period.")
    else:
        print(f"  Reports Generated:       {dr['total_reports']}")
        print(f"  Avg Citation Count:      {dr['avg_citation_count']}")
        print(f"  Citation Health Rate:    {dr['citation_health_rate']}%")
        print(f"  Validation Pass Rate:    {dr['validation_pass_rate']}%")
        conf = dr.get("confidence_distribution", {})
        total_conf = sum(conf.values()) or 1
        print(f"  Confidence Distribution: High={conf.get('high',0)} ({round(conf.get('high',0)/total_conf*100)}%), "
              f"Medium={conf.get('medium',0)} ({round(conf.get('medium',0)/total_conf*100)}%), "
              f"Low={conf.get('low',0)} ({round(conf.get('low',0)/total_conf*100)}%)")
        print(f"  Avg Research Time:       {dr['avg_research_time_seconds']}s")
        print(f"  Avg Sources per Report:  {dr['avg_sources_count']}")

    wb = dashboard["quality_metrics"].get("weekly_briefing", {})
    print(f"\n--- Quality Metrics (Weekly Briefings) ---")
    if wb.get("total_briefings", 0) == 0:
        print("  No briefings in this period.")
    else:
        print(f"  Briefings Generated:     {wb['total_briefings']}")
        print(f"  Avg Sections per Brief:  {wb.get('avg_section_count', 'N/A')}")

    # LLM-as-Judge
    judge = dashboard["llm_judge_scores"]
    print(f"\n--- LLM-as-Judge Scores ---")
    if judge.get("total_evals", 0) == 0:
        print("  No evaluations yet. Run: python scripts/testing/eval_llm_judge.py")
    else:
        print(f"  Reports Evaluated:       {judge['total_evals']}")
        print(f"  Factual Grounding:       {judge['avg_factual_grounding']}/5")
        print(f"  Coherence:               {judge['avg_coherence']}/5")
        print(f"  Actionability:           {judge['avg_actionability']}/5")
        print(f"  Overall:                 {judge['avg_overall']}/5")

    # Cost
    cost = dashboard["token_usage_and_cost"]
    print(f"\n--- Token Usage & Cost ---")
    if cost.get("total_calls", 0) == 0:
        print(f"  {cost.get('note', 'No data yet.')}")
    else:
        total_in = cost["total_input_tokens"]
        total_out = cost["total_output_tokens"]
        print(f"  Total LLM Calls:         {cost['total_calls']:,}")
        print(f"  Total Tokens:            {total_in:,} in / {total_out:,} out")
        print(f"  Total Estimated Cost:    ${cost['total_cost_usd']:.2f}")
        if cost.get("by_model"):
            print(f"  Model Breakdown:")
            for model, data in cost["by_model"].items():
                pct = (data["cost_usd"] / cost["total_cost_usd"] * 100) if cost["total_cost_usd"] > 0 else 0
                print(f"    {model:30s} ${data['cost_usd']:>8.2f} ({pct:.0f}%)")
        if cost.get("by_caller"):
            print(f"  Top Callers:")
            for caller, data in list(cost["by_caller"].items())[:5]:
                print(f"    {caller:30s} {data['calls']:>5} calls  ${data['cost_usd']:>8.2f}")

    # Feedback
    fb = dashboard["user_feedback"]
    print(f"\n--- User Feedback ---")
    if fb.get("total_feedback", 0) == 0:
        print("  No feedback submitted yet.")
    else:
        print(f"  Total Feedback:          {fb['total_feedback']}")
        print(f"  Positive Rate:           {fb['positive_rate']*100:.0f}%")
        print(f"  Positive: {fb['positive_count']}  |  Negative: {fb['negative_count']}")

    print()
    print("=" * 70)
    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="C1 Intelligence Hub Eval Dashboard")
    parser.add_argument("--days", type=int, default=30, help="Number of days to look back")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    asyncio.run(generate_dashboard(days=args.days, output_json=args.json))
