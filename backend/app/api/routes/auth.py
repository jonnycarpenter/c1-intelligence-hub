"""Simple authentication endpoint for site access gate.

This is NOT real authentication - it's just a shared password
to keep casual visitors out during the pilot phase.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config.settings import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


class VerifyAccessRequest(BaseModel):
    """Request to verify site access password."""
    password: str


class VerifyAccessResponse(BaseModel):
    """Response from access verification."""
    success: bool


@router.post("/verify-access", response_model=VerifyAccessResponse)
async def verify_access(request: VerifyAccessRequest):
    """
    Verify the site access password.
    
    This is a simple gate to prevent casual visitors from accessing
    the app during the pilot phase. Not real security.
    """
    valid_password = settings.site_access_password
    
    if not valid_password:
        logger.error("SITE_ACCESS_PASSWORD not configured")
        raise HTTPException(
            status_code=500,
            detail="Server configuration error"
        )
    
    if request.password == valid_password:
        logger.info("Access granted")
        return VerifyAccessResponse(success=True)
    else:
        logger.warning("Access denied - incorrect password")
        raise HTTPException(
            status_code=401,
            detail="Incorrect password"
        )
