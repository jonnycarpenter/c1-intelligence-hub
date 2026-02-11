"""Simple authentication endpoint for site access gate.

Simplified login: name-only, no password required.
Logs login events to BigQuery for basic usage analytics.
"""

import asyncio
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional

from app.config.settings import settings
from app.utils.logger import get_logger
from app.db.gcp_storage import get_storage

logger = get_logger(__name__)
router = APIRouter()


class VerifyAccessRequest(BaseModel):
    """Request to verify site access."""
    password: Optional[str] = None  # No longer required - simplified login
    user_name: str = ""   # For login tracking
    user_team: str = ""   # For login tracking


class VerifyAccessResponse(BaseModel):
    """Response from access verification."""
    success: bool


@router.post("/verify-access", response_model=VerifyAccessResponse)
async def verify_access(request: VerifyAccessRequest, http_request: Request):
    """
    Verify the site access password.
    
    This is a simple gate to prevent casual visitors from accessing
    the app during the pilot phase. Not real security.
    
    On successful login, logs the event to BigQuery for usage analytics.
    """
    # Simplified login: name-only, no password required
    # Password validation is optional - if SITE_ACCESS_PASSWORD is set and
    # a password is provided, we still validate it. Otherwise, allow access.
    valid_password = settings.site_access_password
    
    if valid_password and request.password and request.password != valid_password:
        logger.warning("Access denied - incorrect password")
        raise HTTPException(
            status_code=401,
            detail="Incorrect password"
        )
    
    logger.info(f"Access granted for {request.user_name or 'unknown'} ({request.user_team or 'unknown'})")
    
    # Log login event to BigQuery (fire-and-forget, don't block response)
    try:
        user_agent = http_request.headers.get("user-agent", "")
        storage = await get_storage()
        # Fire-and-forget - don't await
        asyncio.create_task(
            storage.log_user_login(
                user_name=request.user_name,
                user_team=request.user_team,
                user_agent=user_agent,
            )
        )
    except Exception as e:
        # Never fail login due to tracking issues
        logger.warning(f"[LOGIN_TRACKING] Could not log login: {e}")
    
    return VerifyAccessResponse(success=True)

