"""Alert system for eval metric thresholds.

Sends notifications to Slack webhook when thresholds are breached.
Stores alert history in BigQuery `eval_alerts` table.

Usage:
    from app.evals.alerts import check_and_alert, get_recent_alerts

    # Run after dashboard data is computed
    await check_and_alert(dashboard_data)

    # Get alert history
    alerts = await get_recent_alerts(days=7)
"""

import json
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

import httpx

from app.utils.logger import get_logger

logger = get_logger(__name__)


# ── Default alert thresholds (can be overridden via API) ──

DEFAULT_THRESHOLDS = {
    "cost_usd": 5.00,         # Total cost threshold per period
    "daily_cost_usd": 2.00,   # Single day cost threshold
    "quality_min": 3.0,       # Minimum acceptable quality score
    "feedback_negative_rate": 0.30,  # Max acceptable negative feedback rate
    "ingestion_stale_hours": 48,     # Hours before ingestion is "stale"
}

# In-memory threshold overrides
_threshold_overrides: Dict[str, float] = {}


def get_thresholds() -> Dict[str, float]:
    """Get current thresholds (defaults + overrides)."""
    thresholds = DEFAULT_THRESHOLDS.copy()
    thresholds.update(_threshold_overrides)
    return thresholds


def update_thresholds(updates: Dict[str, float]) -> Dict[str, float]:
    """Update threshold overrides. Returns new full thresholds."""
    for key, value in updates.items():
        if key in DEFAULT_THRESHOLDS:
            _threshold_overrides[key] = value
    return get_thresholds()


async def check_and_alert(dashboard_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Check dashboard data against thresholds and send alerts if breached.

    Returns list of triggered alerts.
    """
    thresholds = get_thresholds()
    alerts = []

    # ── Cost threshold ──
    total_cost = dashboard_data.get("token_usage_and_cost", {}).get("total_cost_usd", 0) or 0
    if total_cost > thresholds["cost_usd"]:
        alerts.append({
            "id": str(uuid.uuid4()),
            "type": "cost_threshold",
            "severity": "warning" if total_cost < thresholds["cost_usd"] * 2 else "critical",
            "title": "LLM cost threshold exceeded",
            "message": f"Total cost ${total_cost:.2f} exceeds ${thresholds['cost_usd']:.2f} threshold",
            "value": total_cost,
            "threshold": thresholds["cost_usd"],
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    # ── Quality threshold ──
    avg_quality = dashboard_data.get("llm_judge_scores", {}).get("avg_overall")
    if avg_quality and avg_quality < thresholds["quality_min"]:
        alerts.append({
            "id": str(uuid.uuid4()),
            "type": "quality_drop",
            "severity": "critical" if avg_quality < 2.0 else "warning",
            "title": "Quality score below threshold",
            "message": f"Average quality {avg_quality:.1f}/5 is below {thresholds['quality_min']:.1f} minimum",
            "value": avg_quality,
            "threshold": thresholds["quality_min"],
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    # ── Negative feedback rate ──
    feedback = dashboard_data.get("user_feedback", {})
    total_feedback = feedback.get("total_feedback", 0)
    negative_rate = 0
    if total_feedback > 0:
        negative_count = feedback.get("negative_count", 0) or 0
        negative_rate = negative_count / total_feedback
    if negative_rate > thresholds["feedback_negative_rate"] and total_feedback >= 5:
        alerts.append({
            "id": str(uuid.uuid4()),
            "type": "feedback_negative",
            "severity": "warning",
            "title": "High negative feedback rate",
            "message": f"{negative_rate * 100:.0f}% negative feedback ({feedback.get('negative_count', 0)} of {total_feedback})",
            "value": negative_rate,
            "threshold": thresholds["feedback_negative_rate"],
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    # ── Store alerts and send Slack notification ──
    if alerts:
        await _store_alerts(alerts)
        await _send_slack_notification(alerts)

    return alerts


async def _store_alerts(alerts: List[Dict[str, Any]]) -> None:
    """Store alerts to BigQuery eval_alerts table."""
    try:
        from app.db.gcp_storage import get_storage

        storage = await get_storage()
        table_id = f"{storage.config.full_dataset_id}.eval_alerts"

        rows = [
            {
                "id": a["id"],
                "type": a["type"],
                "severity": a["severity"],
                "title": a["title"],
                "message": a["message"],
                "value": a.get("value"),
                "threshold": a.get("threshold"),
                "created_at": a["created_at"],
                "acknowledged": False,
            }
            for a in alerts
        ]

        errors = storage.client.insert_rows_json(table_id, rows)
        if errors:
            logger.warning(f"[ALERTS] BigQuery insert errors: {errors}")
        else:
            logger.info(f"[ALERTS] Stored {len(rows)} alerts")
    except Exception as e:
        logger.warning(f"[ALERTS] Failed to store alerts: {e}")


async def _send_slack_notification(alerts: List[Dict[str, Any]]) -> None:
    """Send alert notification to Slack webhook if configured."""
    try:
        from app.config.settings import settings
        webhook_url = getattr(settings, "slack_webhook_url", None)
        if not webhook_url:
            logger.debug("[ALERTS] No Slack webhook URL configured, skipping notification")
            return

        severity_emoji = {"critical": "🔴", "warning": "🟡", "info": "🔵"}

        blocks = [{
            "type": "header",
            "text": {"type": "plain_text", "text": "⚠️ C1 Intelligence Hub — Eval Alerts"}
        }]

        for alert in alerts[:5]:
            emoji = severity_emoji.get(alert["severity"], "⚪")
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{emoji} *{alert['title']}*\n{alert['message']}"
                }
            })

        async with httpx.AsyncClient() as client:
            resp = await client.post(webhook_url, json={"blocks": blocks}, timeout=10.0)
            if resp.status_code == 200:
                logger.info(f"[ALERTS] Sent {len(alerts)} alerts to Slack")
            else:
                logger.warning(f"[ALERTS] Slack webhook returned {resp.status_code}")

    except Exception as e:
        logger.warning(f"[ALERTS] Failed to send Slack notification: {e}")


async def get_recent_alerts(days: int = 7) -> List[Dict[str, Any]]:
    """Get recent alerts from BigQuery."""
    try:
        from google.cloud import bigquery
        from app.db.gcp_storage import get_storage

        storage = await get_storage()
        client = storage.client
        dataset = storage.config.full_dataset_id
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        query = f"""
            SELECT id, type, severity, title, message, value, threshold,
                   acknowledged, created_at
            FROM `{dataset}.eval_alerts`
            WHERE created_at >= @cutoff
            ORDER BY created_at DESC
            LIMIT 50
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("cutoff", "TIMESTAMP", cutoff),
            ]
        )

        rows = list(client.query(query, job_config=job_config).result())
        return [
            {
                "id": r.id,
                "type": r.type,
                "severity": r.severity,
                "title": r.title,
                "message": r.message,
                "value": r.value,
                "threshold": r.threshold,
                "acknowledged": r.acknowledged,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    except Exception as e:
        logger.warning(f"[ALERTS] Failed to fetch recent alerts: {e}")
        return []
