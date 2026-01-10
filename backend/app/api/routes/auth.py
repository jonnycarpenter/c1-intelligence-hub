"""Simple authentication endpoint for site access gate.

This is NOT real authentication - it's just a shared password
to keep casual visitors out during the pilot phase.

Also logs login events to BigQuery for basic usage analytics.
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
    """Request to verify site access password."""
    password: str
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
    valid_password = settings.site_access_password
    
    if not valid_password:
        logger.error("SITE_ACCESS_PASSWORD not configured")
        raise HTTPException(
            status_code=500,
            detail="Server configuration error"
        )
    
    if request.password == valid_password:
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
    else:
        logger.warning("Access denied - incorrect password")
        raise HTTPException(
            status_code=401,
            detail="Incorrect password"
        )

