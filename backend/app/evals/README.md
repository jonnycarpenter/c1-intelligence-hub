# Evaluation Suite

Lightweight evaluation framework for monitoring AI agent output quality, cost, and user satisfaction.

## Components

### Token & Cost Tracking (`token_tracker.py`)
Every LLM call (via `resilient_llm.py`) automatically records token usage and estimated cost. Data buffers in memory and flushes to BigQuery's `llm_token_usage` table.

```python
from app.evals import token_tracker

# Automatic — instrumented in resilient_llm.py
# Manual usage:
token_tracker.record(model="claude-sonnet-4-5", input_tokens=1200, output_tokens=800, caller="my_module")
summary = token_tracker.get_session_summary()
await token_tracker.flush_to_bigquery()
```

### Quality Metrics (`quality_metrics.py`)
Deterministic quality signals computed from existing BigQuery data. No LLM calls needed.

- Citation density & health rate
- Validation pass rate
- Confidence distribution (high/medium/low)
- Data completeness rates
- Research time analysis

```python
from app.evals.quality_metrics import compute_quality_report
report = await compute_quality_report(days_back=30)
```

### LLM-as-Judge (`scripts/testing/eval_llm_judge.py`)
Batch evaluation of saved Deep Research reports using Claude Haiku as a judge. Scores on three dimensions:
- **Factual Grounding** — Are claims supported by cited sources?
- **Coherence** — Is the report well-structured and readable?
- **Actionability** — Would an executive know what action to take?

```bash
cd backend
python scripts/testing/eval_llm_judge.py --count 5
```

### User Feedback (`api/routes/feedback.py` + `FeedbackWidget.tsx`)
Thumbs up/down widget on Deep Research reports and Weekly Briefings. Stored in BigQuery `user_feedback` table.

### Eval Dashboard (`scripts/monitoring/eval_dashboard.py`)
Unified summary pulling quality metrics, LLM judge scores, cost data, and feedback.

```bash
cd backend
python scripts/monitoring/eval_dashboard.py --days 30
python scripts/monitoring/eval_dashboard.py --json  # Machine-readable
```

## BigQuery Tables

| Table | Purpose |
|-------|---------|
| `llm_token_usage` | Per-call token counts, cost estimates, caller attribution |
| `eval_results` | LLM-as-judge scores per report |
| `user_feedback` | Thumbs up/down ratings with optional comments |

## Architecture

```
LLM Call → resilient_llm.py → token_tracker.record()
                                    ↓
                            In-memory buffer
                                    ↓
                          flush_to_bigquery()
                                    ↓
                         BigQuery: llm_token_usage

Saved Report → eval_llm_judge.py → Claude Haiku → eval_results

User Click → FeedbackWidget → POST /api/feedback → user_feedback

All Data → eval_dashboard.py → Formatted Summary
```
