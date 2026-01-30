"""
Guide API Routes
=================

API endpoints for the Intelligence Hub Guide AI agent.
"""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

from app.agents.guide import get_guide_agent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/guide", tags=["guide"])


class GuideMessage(BaseModel):
    """A message in the Guide conversation."""
    role: str  # "user" or "assistant"
    content: str


class GuideChatRequest(BaseModel):
    """Request body for Guide chat endpoint."""
    message: str
    history: Optional[List[GuideMessage]] = None


class GuideChatResponse(BaseModel):
    """Response from Guide chat endpoint."""
    response: str


class GuideWelcomeResponse(BaseModel):
    """Response from Guide welcome endpoint."""
    message: str


@router.post("/chat", response_model=GuideChatResponse)
async def guide_chat(request: GuideChatRequest) -> GuideChatResponse:
    """
    Send a message to the Guide and get a response.
    
    The Guide is an AI assistant that helps prospective users understand
    the Intelligence Hub platform's capabilities.
    """
    try:
        logger.info(f"[GUIDE API] Chat request: {request.message[:100]}...")
        
        guide = get_guide_agent()
        
        # Convert history to dict format if provided
        history = None
        if request.history:
            history = [{"role": msg.role, "content": msg.content} for msg in request.history]
        
        response = await guide.chat(request.message, history)
        
        return GuideChatResponse(response=response)
        
    except Exception as e:
        logger.error(f"[GUIDE API] Error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to generate response. Please try again."
        )


@router.get("/welcome", response_model=GuideWelcomeResponse)
async def guide_welcome() -> GuideWelcomeResponse:
    """
    Get the initial welcome message for the Guide.
    """
    try:
        guide = get_guide_agent()
        return GuideWelcomeResponse(message=guide.get_welcome_message())
    except Exception as e:
        logger.error(f"[GUIDE API] Error getting welcome: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to get welcome message."
        )
