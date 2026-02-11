"""Reusable LLM-as-Judge evaluation logic.

Extracted from scripts/testing/eval_llm_judge.py so it can be called
from both the CLI script and the REST API (POST /api/evals/run-judge).
"""

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from app.utils.logger import get_logger

logger = get_logger(__name__)

EVAL_PROMPT = """You are an expert evaluator of AI-generated intelligence reports.

Score the following Deep Research report on three dimensions, each on a 1-5 scale:

**Factual Grounding** (1-5): Are the claims in the executive summary and sections supported by cited sources? Does each key point have evidence?
- 5 = Every claim cited, strong evidence chain
- 3 = Most claims cited, some unsupported statements
- 1 = Mostly unsupported assertions

**Coherence** (1-5): Is the report well-structured, logically organized, and readable? Does the executive summary accurately reflect the sections?
- 5 = Excellent flow, clear narrative arc
- 3 = Adequate structure, some disconnects
- 1 = Disorganized, contradictory

**Actionability** (1-5): Would a business executive reading this know what decision to make or action to take? Are insights specific enough?
- 5 = Clear strategic implications, specific recommendations
- 3 = General insights, some actionable elements
- 1 = Purely informational, no clear next steps

Respond with ONLY valid JSON:
{
  "factual_grounding": {"score": <1-5>, "reasoning": "<1 sentence>"},
  "coherence": {"score": <1-5>, "reasoning": "<1 sentence>"},
  "actionability": {"score": <1-5>, "reasoning": "<1 sentence>"},
  "overall": {"score": <1-5>, "reasoning": "<1 sentence>"}
}

---
REPORT TO EVALUATE:

Query: {query}

Executive Summary:
{executive_summary}

Sections:
{sections_text}

Sources Used: {sources_count}
Validation Passed: {validation_passed}
"""


def _truncate(text: str, max_chars: int = 2000) -> str:
    if not text or len(text) <= max_chars:
        return text or ""
    return text[:max_chars] + "..."


# ── In-memory job state ──

_eval_job_state = {
    "running": False,
    "last_run": None,
    "last_result": None,
}


def get_eval_job_status() -> dict:
    """Return current eval job status."""
    return {
        "running": _eval_job_state["running"],
        "last_run": _eval_job_state["last_run"],
        "last_result": _eval_job_state["last_result"],
    }


async def run_eval_batch(count: int = 5, model: str = "claude-haiku-4-5") -> dict:
    """Evaluate recent Deep Research reports with an LLM judge.

    Returns:
        dict with { evaluated, avg_scores, errors }
    """
    from app.db.gcp_storage import get_storage
    from app.utils.resilient_llm import get_resilient_async_client
    from app.config.settings import settings

    _eval_job_state["running"] = True
    start_time = time.time()

    try:
        storage = await get_storage()
        client = storage.client
        dataset = storage.config.full_dataset_id

        # Fetch recent reports that haven't been evaluated yet
        query = f"""
            SELECT r.id, r.query, r.executive_summary, r.final_report,
                   r.sources_count, r.validation_passed
            FROM `{dataset}.deep_research_reports` r
            LEFT JOIN `{dataset}.eval_results` e ON r.id = e.report_id
            WHERE r.final_report IS NOT NULL AND e.report_id IS NULL
            ORDER BY r.created_at DESC
            LIMIT {int(count)}
        """
        reports = list(client.query(query).result())

        if not reports:
            # Fall back to most recent reports (may re-evaluate)
            fallback_query = f"""
                SELECT id, query, executive_summary, final_report,
                       sources_count, validation_passed
                FROM `{dataset}.deep_research_reports`
                WHERE final_report IS NOT NULL
                ORDER BY created_at DESC
                LIMIT {int(count)}
            """
            reports = list(client.query(fallback_query).result())

        if not reports:
            result = {"evaluated": 0, "avg_scores": {}, "errors": 0, "message": "No reports found to evaluate"}
            _eval_job_state["last_result"] = result
            _eval_job_state["last_run"] = datetime.now(timezone.utc).isoformat()
            return result

        logger.info(f"[EVAL_JUDGE] Starting batch eval: {len(reports)} reports with {model}")

        llm_client = get_resilient_async_client(
            anthropic_api_key=settings.anthropic_api_key,
            openai_api_key=getattr(settings, "openai_api_key", None),
        )

        results = []
        error_count = 0

        for report in reports:
            # Parse sections
            sections_text = ""
            try:
                final_report = json.loads(report.final_report) if report.final_report else {}
                sections = final_report.get("sections", [])
                for s in sections[:5]:
                    title = s.get("section_title", "Untitled")
                    content = s.get("content", "")
                    sections_text += f"\n### {title}\n{_truncate(content, 1500)}\n"
            except (json.JSONDecodeError, TypeError):
                sections_text = _truncate(str(report.final_report), 3000)

            prompt = EVAL_PROMPT.format(
                query=report.query or "Unknown",
                executive_summary=_truncate(report.executive_summary or "", 1500),
                sections_text=_truncate(sections_text, 4000),
                sources_count=report.sources_count or 0,
                validation_passed=report.validation_passed,
            )

            eval_start = time.time()
            try:
                response = await asyncio.wait_for(
                    llm_client.messages_create(
                        model=model,
                        max_tokens=500,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.1,
                        _caller="eval_llm_judge",
                    ),
                    timeout=120.0,
                )
                elapsed = time.time() - eval_start
                response_text = response.content[0].text.strip()
                scores = json.loads(response_text)

                eval_result = {
                    "id": str(uuid.uuid4()),
                    "report_id": report.id,
                    "report_type": "deep_research",
                    "eval_model": model,
                    "factual_grounding_score": scores["factual_grounding"]["score"],
                    "factual_grounding_reasoning": scores["factual_grounding"]["reasoning"],
                    "coherence_score": scores["coherence"]["score"],
                    "coherence_reasoning": scores["coherence"]["reasoning"],
                    "actionability_score": scores["actionability"]["score"],
                    "actionability_reasoning": scores["actionability"]["reasoning"],
                    "overall_score": scores["overall"]["score"],
                    "overall_reasoning": scores["overall"]["reasoning"],
                    "eval_time_seconds": round(elapsed, 2),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
                results.append(eval_result)
                logger.info(f"[EVAL_JUDGE] Report {report.id[:8]} scored {scores['overall']['score']}/5 ({elapsed:.1f}s)")

            except asyncio.TimeoutError:
                error_count += 1
                logger.error(f"[EVAL_JUDGE] Timeout evaluating report {report.id}")
            except Exception as e:
                error_count += 1
                logger.error(f"[EVAL_JUDGE] Failed to evaluate report {report.id}: {e}")

        # Store results in BigQuery
        if results:
            table_id = f"{dataset}.eval_results"
            try:
                errors = client.insert_rows_json(table_id, results)
                if errors:
                    logger.error(f"[EVAL_JUDGE] BigQuery insert errors: {errors}")
                else:
                    logger.info(f"[EVAL_JUDGE] Stored {len(results)} eval results")
            except Exception as e:
                logger.error(f"[EVAL_JUDGE] Failed to store results: {e}")

        # Compute averages
        avg_scores = {}
        if results:
            avg_scores = {
                "factual_grounding": round(sum(r["factual_grounding_score"] for r in results) / len(results), 1),
                "coherence": round(sum(r["coherence_score"] for r in results) / len(results), 1),
                "actionability": round(sum(r["actionability_score"] for r in results) / len(results), 1),
                "overall": round(sum(r["overall_score"] for r in results) / len(results), 1),
            }

        total_elapsed = round(time.time() - start_time, 1)
        result = {
            "evaluated": len(results),
            "avg_scores": avg_scores,
            "errors": error_count,
            "elapsed_seconds": total_elapsed,
        }
        _eval_job_state["last_result"] = result
        _eval_job_state["last_run"] = datetime.now(timezone.utc).isoformat()
        logger.info(f"[EVAL_JUDGE] Batch complete: {len(results)} evaluated, {error_count} errors, {total_elapsed}s")
        return result

    except Exception as e:
        logger.error(f"[EVAL_JUDGE] Batch eval failed: {e}", exc_info=True)
        error_result = {"evaluated": 0, "avg_scores": {}, "errors": 1, "message": str(e)}
        _eval_job_state["last_result"] = error_result
        _eval_job_state["last_run"] = datetime.now(timezone.utc).isoformat()
        return error_result

    finally:
        _eval_job_state["running"] = False
