"""Token usage and cost tracking for LLM calls.

Captures token counts from every LLM invocation and estimates cost.
Uses an in-memory buffer that flushes to BigQuery at natural checkpoints
(end of research workflow, briefing generation, etc.).

Usage:
    from app.evals import token_tracker

    # Record usage after an LLM call
    token_tracker.record(
        model="claude-sonnet-4-5",
        input_tokens=1200,
        output_tokens=800,
        caller="weekly_briefing",
    )

    # Flush to BigQuery
    await token_tracker.flush_to_bigquery()

    # Get current session summary
    summary = token_tracker.get_session_summary()
"""

import asyncio
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.utils.logger import get_logger

logger = get_logger(__name__)

# =============================================================================
# Model Pricing (USD per 1M tokens) — Updated Feb 2026
# =============================================================================

MODEL_PRICING: Dict[str, Dict[str, float]] = {
    # Anthropic
    "claude-opus-4-6": {"input": 5.0, "output": 25.0},
    "claude-opus-4-5": {"input": 15.0, "output": 75.0},  # Legacy
    "claude-sonnet-4-5": {"input": 3.0, "output": 15.0},
    "claude-sonnet-4-5-20250929": {"input": 3.0, "output": 15.0},
    "claude-3-5-sonnet-20241022": {"input": 3.0, "output": 15.0},
    "claude-haiku-4-5": {"input": 0.80, "output": 4.0},
    "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.0},
    "claude-3-5-haiku-20241022": {"input": 0.80, "output": 4.0},
    # OpenAI (fallback)
    "gpt-4o": {"input": 2.50, "output": 10.0},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
}

# Default pricing for unknown models
DEFAULT_PRICING = {"input": 3.0, "output": 15.0}


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate cost in USD for a single LLM call."""
    pricing = MODEL_PRICING.get(model, DEFAULT_PRICING)
    cost = (input_tokens / 1_000_000) * pricing["input"] + (output_tokens / 1_000_000) * pricing["output"]
    return round(cost, 6)


def _detect_provider(model: str) -> str:
    """Detect provider from model name."""
    if model.startswith("claude"):
        return "anthropic"
    elif model.startswith("gpt"):
        return "openai"
    return "unknown"


class TokenTracker:
    """In-memory token usage tracker with auto-flush to BigQuery."""

    AUTO_FLUSH_THRESHOLD = 5  # Flush after this many buffered records

    def __init__(self):
        self._buffer: List[Dict[str, Any]] = []
        self._session_start = time.time()
        self._flush_pending = False

    def record(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        caller: str = "unknown",
    ) -> None:
        """Record token usage from an LLM call. Auto-flushes to BigQuery."""
        cost = _estimate_cost(model, input_tokens, output_tokens)
        provider = _detect_provider(model)

        record = {
            "id": str(uuid.uuid4()),
            "model": model,
            "provider": provider,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "estimated_cost_usd": cost,
            "caller": caller,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._buffer.append(record)

        logger.info(
            f"[TOKEN_TRACKER] {model} | {input_tokens:,} in + {output_tokens:,} out "
            f"= {input_tokens + output_tokens:,} tokens | ${cost:.4f} | caller={caller}"
        )

        # Auto-flush when buffer reaches threshold
        if len(self._buffer) >= self.AUTO_FLUSH_THRESHOLD and not self._flush_pending:
            self._schedule_flush()

    def _schedule_flush(self) -> None:
        """Schedule a background flush to BigQuery."""
        self._flush_pending = True
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._auto_flush())
        except RuntimeError:
            # No running event loop — skip auto-flush (will flush later)
            self._flush_pending = False

    async def _auto_flush(self) -> None:
        """Background auto-flush task."""
        try:
            count = await self.flush_to_bigquery()
            if count > 0:
                logger.info(f"[TOKEN_TRACKER] Auto-flushed {count} records to BigQuery")
        except Exception as e:
            logger.warning(f"[TOKEN_TRACKER] Auto-flush failed: {e}")
        finally:
            self._flush_pending = False

    def get_session_summary(self) -> Dict[str, Any]:
        """Get summary of token usage for the current session."""
        if not self._buffer:
            return {
                "total_calls": 0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_tokens": 0,
                "total_cost_usd": 0.0,
                "by_model": {},
                "by_caller": {},
                "session_duration_seconds": time.time() - self._session_start,
            }

        by_model: Dict[str, Dict[str, Any]] = {}
        by_caller: Dict[str, Dict[str, Any]] = {}
        total_input = 0
        total_output = 0
        total_cost = 0.0

        for r in self._buffer:
            total_input += r["input_tokens"]
            total_output += r["output_tokens"]
            total_cost += r["estimated_cost_usd"]

            # By model
            model = r["model"]
            if model not in by_model:
                by_model[model] = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
            by_model[model]["calls"] += 1
            by_model[model]["input_tokens"] += r["input_tokens"]
            by_model[model]["output_tokens"] += r["output_tokens"]
            by_model[model]["cost_usd"] += r["estimated_cost_usd"]

            # By caller
            caller = r["caller"]
            if caller not in by_caller:
                by_caller[caller] = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
            by_caller[caller]["calls"] += 1
            by_caller[caller]["input_tokens"] += r["input_tokens"]
            by_caller[caller]["output_tokens"] += r["output_tokens"]
            by_caller[caller]["cost_usd"] += r["estimated_cost_usd"]

        return {
            "total_calls": len(self._buffer),
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_tokens": total_input + total_output,
            "total_cost_usd": round(total_cost, 4),
            "by_model": by_model,
            "by_caller": by_caller,
            "session_duration_seconds": round(time.time() - self._session_start, 1),
        }

    async def flush_to_bigquery(self) -> int:
        """Flush buffered records to the llm_token_usage BigQuery table.

        Returns the number of records flushed.
        """
        if not self._buffer:
            return 0

        records_to_flush = self._buffer.copy()
        self._buffer.clear()

        try:
            from app.db.gcp_storage import get_storage

            storage = await get_storage()
            table_ref = f"{storage.config.full_dataset_id}.llm_token_usage"

            rows = []
            for r in records_to_flush:
                rows.append({
                    "id": r["id"],
                    "model": r["model"],
                    "provider": r["provider"],
                    "input_tokens": r["input_tokens"],
                    "output_tokens": r["output_tokens"],
                    "total_tokens": r["total_tokens"],
                    "estimated_cost_usd": r["estimated_cost_usd"],
                    "caller": r["caller"],
                    "created_at": r["created_at"],
                })

            errors = storage.client.insert_rows_json(table_ref, rows)
            if errors:
                logger.error(f"[TOKEN_TRACKER] BigQuery insert errors: {errors}")
                # Put records back in buffer on failure
                self._buffer.extend(records_to_flush)
                return 0

            logger.info(f"[TOKEN_TRACKER] Flushed {len(rows)} records to BigQuery")
            return len(rows)

        except Exception as e:
            logger.error(f"[TOKEN_TRACKER] Failed to flush to BigQuery: {e}", exc_info=True)
            # Put records back in buffer on failure
            self._buffer.extend(records_to_flush)
            return 0

    @property
    def buffer_size(self) -> int:
        """Number of records waiting to be flushed."""
        return len(self._buffer)


# Module-level singleton
token_tracker = TokenTracker()
