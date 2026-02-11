"""Feedback API endpoints for rating AI-generated reports."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db.gcp_storage import get_storage
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


class FeedbackRequest(BaseModel):
    report_id: str
    report_type: str  # 'deep_research' | 'weekly_briefing'
    rating: str  # 'positive' | 'negative'
    comment: Optional[str] = None
    section_id: Optional[str] = None


class FeedbackResponse(BaseModel):
    id: str
    success: bool


@router.post("", response_model=FeedbackResponse)
async def submit_feedback(request: FeedbackRequest):
    """Submit thumbs-up/down feedback on a report."""
    if request.rating not in ("positive", "negative"):
        raise HTTPException(status_code=400, detail="rating must be 'positive' or 'negative'")
    if request.report_type not in ("deep_research", "weekly_briefing"):
        raise HTTPException(status_code=400, detail="report_type must be 'deep_research' or 'weekly_briefing'")

    feedback_id = str(uuid.uuid4())
    row = {
        "id": feedback_id,
        "report_id": request.report_id,
        "report_type": request.report_type,
        "rating": request.rating,
        "comment": request.comment,
        "section_id": request.section_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        storage = await get_storage()
        table_id = f"{storage.config.full_dataset_id}.user_feedback"
        errors = storage.client.insert_rows_json(table_id, [row])
        if errors:
            logger.error(f"[FEEDBACK] BigQuery insert errors: {errors}")
            raise HTTPException(status_code=500, detail="Failed to store feedback")

        logger.info(
            f"[FEEDBACK] Stored {request.rating} feedback for "
            f"{request.report_type}/{request.report_id}"
        )
        return FeedbackResponse(id=feedback_id, success=True)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[FEEDBACK] Error storing feedback: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to store feedback")


@router.get("/summary")
async def get_feedback_summary(
    report_type: Optional[str] = None,
    days: int = 30,
):
    """Get aggregated feedback stats."""
    from google.cloud import bigquery

    storage = await get_storage()
    client = storage.client
    dataset = storage.config.full_dataset_id

    where_clauses = ["created_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @days DAY)"]
    params = [bigquery.ScalarQueryParameter("days", "INT64", days)]

    if report_type:
        where_clauses.append("report_type = @report_type")
        params.append(bigquery.ScalarQueryParameter("report_type", "STRING", report_type))

    where = " AND ".join(where_clauses)

    query = f"""
        SELECT
            COUNT(*) as total_feedback,
            COUNTIF(rating = 'positive') as positive_count,
            COUNTIF(rating = 'negative') as negative_count,
        FROM `{dataset}.user_feedback`
        WHERE {where}
    """

    job_config = bigquery.QueryJobConfig(query_parameters=params)

    try:
        results = list(client.query(query, job_config=job_config).result())
        row = results[0] if results else None

        total = row.total_feedback if row else 0
        positive = row.positive_count if row else 0
        negative = row.negative_count if row else 0

        # Get recent comments
        comments_query = f"""
            SELECT report_type, rating, comment, created_at
            FROM `{dataset}.user_feedback`
            WHERE {where} AND comment IS NOT NULL AND comment != ''
            ORDER BY created_at DESC
            LIMIT 5
        """
        comments_results = list(client.query(comments_query, job_config=job_config).result())
        recent_comments = [
            {
                "report_type": r.report_type,
                "rating": r.rating,
                "comment": r.comment,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in comments_results
        ]

        return {
            "total_feedback": total,
            "positive_count": positive,
            "negative_count": negative,
            "positive_rate": round(positive / total, 2) if total > 0 else 0,
            "recent_comments": recent_comments,
            "period_days": days,
        }

    except Exception as e:
        logger.error(f"[FEEDBACK] Error fetching summary: {e}", exc_info=True)
        return {
            "total_feedback": 0,
            "positive_count": 0,
            "negative_count": 0,
            "positive_rate": 0,
            "recent_comments": [],
            "period_days": days,
        }
