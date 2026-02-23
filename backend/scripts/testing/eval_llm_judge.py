#!/usr/bin/env python
"""LLM-as-Judge evaluation script for Deep Research reports.

Reads saved reports from BigQuery, sends them to Claude Haiku for
structured quality scoring, and stores results in the eval_results table.

Usage:
    cd backend
    python scripts/testing/eval_llm_judge.py              # Evaluate 5 most recent
    python scripts/testing/eval_llm_judge.py --count 10    # Evaluate 10 reports
    python scripts/testing/eval_llm_judge.py --model claude-sonnet-4-6  # Use different judge
"""

import argparse
import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timezone

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

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


def truncate(text: str, max_chars: int = 2000) -> str:
    if not text or len(text) <= max_chars:
        return text or ""
    return text[:max_chars] + "..."


async def evaluate_reports(count: int = 5, model: str = "claude-haiku-4-5"):
    from app.db.gcp_storage import get_storage
    from app.utils.resilient_llm import get_resilient_async_client
    from app.config.settings import settings
    from google.cloud import bigquery

    storage = await get_storage()
    client = storage.client
    dataset = storage.config.full_dataset_id

    # Fetch recent reports
    query = f"""
        SELECT id, query, executive_summary, final_report, sources_count,
               validation_passed, citation_count, overall_confidence
        FROM `{dataset}.deep_research_reports`
        WHERE final_report IS NOT NULL
        ORDER BY created_at DESC
        LIMIT {count}
    """
    reports = list(client.query(query).result())

    if not reports:
        print("No reports found to evaluate.")
        return

    print(f"\nEvaluating {len(reports)} reports with {model}...\n")
    print("-" * 80)

    llm_client = get_resilient_async_client(
        anthropic_api_key=settings.anthropic_api_key,
        openai_api_key=getattr(settings, "openai_api_key", None),
    )

    results = []
    for idx, report in enumerate(reports):
        report_id = report.id
        query_text = report.query or "Unknown"

        # Parse sections from final_report JSON
        sections_text = ""
        try:
            final_report = json.loads(report.final_report) if report.final_report else {}
            sections = final_report.get("sections", [])
            for s in sections[:5]:  # Limit to first 5 sections
                title = s.get("section_title", "Untitled")
                content = s.get("content", "")
                sections_text += f"\n### {title}\n{truncate(content, 1500)}\n"
        except (json.JSONDecodeError, TypeError):
            sections_text = truncate(str(report.final_report), 3000)

        prompt = EVAL_PROMPT.format(
            query=query_text,
            executive_summary=truncate(report.executive_summary or "", 1500),
            sections_text=truncate(sections_text, 4000),
            sources_count=report.sources_count or 0,
            validation_passed=report.validation_passed,
        )

        start = time.time()
        try:
            response = await llm_client.messages_create(
                model=model,
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                _caller="eval_llm_judge",
            )
            elapsed = time.time() - start
            response_text = response.content[0].text.strip()

            # Parse JSON response
            scores = json.loads(response_text)

            result = {
                "id": str(uuid.uuid4()),
                "report_id": report_id,
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
            results.append(result)

            print(f"[{idx + 1}/{len(reports)}] {query_text[:60]}")
            print(f"  Factual Grounding: {scores['factual_grounding']['score']}/5 - {scores['factual_grounding']['reasoning']}")
            print(f"  Coherence:         {scores['coherence']['score']}/5 - {scores['coherence']['reasoning']}")
            print(f"  Actionability:     {scores['actionability']['score']}/5 - {scores['actionability']['reasoning']}")
            print(f"  Overall:           {scores['overall']['score']}/5 ({elapsed:.1f}s)")
            print()

        except Exception as e:
            logger.error(f"Failed to evaluate report {report_id}: {e}")
            print(f"[{idx + 1}/{len(reports)}] FAILED: {e}\n")

    # Store results in BigQuery
    if results:
        table_id = f"{dataset}.eval_results"
        try:
            errors = client.insert_rows_json(table_id, results)
            if errors:
                logger.error(f"BigQuery insert errors: {errors}")
            else:
                print(f"Stored {len(results)} eval results in BigQuery")
        except Exception as e:
            logger.error(f"Failed to store results: {e}")

    # Print summary
    if results:
        avg_fg = sum(r["factual_grounding_score"] for r in results) / len(results)
        avg_co = sum(r["coherence_score"] for r in results) / len(results)
        avg_ac = sum(r["actionability_score"] for r in results) / len(results)
        avg_ov = sum(r["overall_score"] for r in results) / len(results)

        print("=" * 80)
        print(f"SUMMARY ({len(results)} reports evaluated)")
        print(f"  Avg Factual Grounding: {avg_fg:.1f}/5")
        print(f"  Avg Coherence:         {avg_co:.1f}/5")
        print(f"  Avg Actionability:     {avg_ac:.1f}/5")
        print(f"  Avg Overall:           {avg_ov:.1f}/5")
        print("=" * 80)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate Deep Research reports with LLM-as-judge")
    parser.add_argument("--count", type=int, default=5, help="Number of reports to evaluate")
    parser.add_argument("--model", type=str, default="claude-haiku-4-5", help="Model to use as judge")
    args = parser.parse_args()

    asyncio.run(evaluate_reports(count=args.count, model=args.model))
