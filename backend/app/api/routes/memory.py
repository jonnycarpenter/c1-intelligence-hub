"""Memory API endpoints for long-term organizational memory.

Endpoints:
- GET/POST /api/memory/preferences - Org preferences CRUD
- POST /api/memory/log - Save briefing/research to memory
- GET /api/memory/relevant - Vector search for relevant memories
- PATCH /api/memory/:id/pin - Toggle pin status
- POST /api/memory/block - Block a topic
- POST /api/jobs/cleanup-memories - Cleanup job (Cloud Scheduler)
"""

from typing import Optional, List
from fastapi import APIRouter, HTTPException, Header, Query
from pydantic import BaseModel, Field
import os

from app.services.memory_service import (
    get_org_preferences,
    add_preference,
    remove_preference,
    save_to_memory,
    get_relevant_memories,
    pin_memory,
    unpin_memory,
    block_topic,
    cleanup_expired_memories,
    build_agent_context,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


# =============================================================================
# Request/Response Models
# =============================================================================

class PreferenceRequest(BaseModel):
    """Request to add a preference."""
    type: str = Field(..., description="'prioritize' or 'block'")
    target: str = Field(..., description="Topic/entity to prioritize or block")
    description: Optional[str] = Field(None, description="Optional description")


class SaveMemoryRequest(BaseModel):
    """Request to save to memory log."""
    type: str = Field(..., description="'briefing' or 'research_export'")
    question: str = Field(..., description="The query/question")
    answer: str = Field(..., description="The response/answer")
    sources: Optional[List[dict]] = Field(None, description="Source references")
    confidence: Optional[str] = Field(None, description="Confidence level")
    tags: Optional[List[str]] = Field(None, description="Tags/entities")


class PinRequest(BaseModel):
    """Request to toggle pin status."""
    pinned: bool = Field(..., description="Whether to pin or unpin")


class BlockTopicRequest(BaseModel):
    """Request to block a topic."""
    topic: str = Field(..., description="Topic to block")


class MemoryResponse(BaseModel):
    """Standard memory response."""
    success: bool
    memory_id: Optional[str] = None
    error: Optional[str] = None
    note: Optional[str] = None


# =============================================================================
# Preferences Endpoints
# =============================================================================

@router.get("/preferences")
async def get_preferences(
    x_user_team: Optional[str] = Header(None, alias="X-User-Team")
):
    """
    Get organization preferences (priorities and blocks).
    Returns team-specific + org-wide preferences.
    """
    logger.info(f"Getting preferences for team: {x_user_team}")
    preferences = await get_org_preferences(x_user_team)
    return preferences


@router.post("/preferences")
async def create_preference(
    request: PreferenceRequest,
    x_user_name: str = Header("anonymous", alias="X-User-Name"),
    x_user_team: Optional[str] = Header(None, alias="X-User-Team")
):
    """
    Add a new preference (priority or block).
    """
    logger.info(f"Adding preference: {request.type} - {request.target}")
    
    if request.type not in ["prioritize", "block"]:
        raise HTTPException(status_code=400, detail="Type must be 'prioritize' or 'block'")
    
    result = await add_preference(
        pref_type=request.type,
        target=request.target,
        description=request.description,
        user_name=x_user_name,
        user_team=x_user_team
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Failed to add preference"))
    
    return result


@router.delete("/preferences/{preference_id}")
async def delete_preference(preference_id: str):
    """
    Remove (deactivate) a preference.
    """
    logger.info(f"Removing preference: {preference_id}")
    result = await remove_preference(preference_id)
    
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Failed to remove preference"))
    
    return result


# =============================================================================
# Memory Log Endpoints
# =============================================================================

@router.get("/log")
async def list_memories(
    limit: int = Query(50, description="Max results to return"),
    offset: int = Query(0, description="Offset for pagination"),
    pinned_only: bool = Query(False, description="Only return pinned memories"),
    x_user_team: Optional[str] = Header(None, alias="X-User-Team")
):
    """
    List all memories for the memory log UI.
    Returns paginated results with total count.
    """
    logger.info(f"Listing memories: limit={limit}, offset={offset}, team={x_user_team}")
    
    from app.services.memory_service import list_memory_log
    result = await list_memory_log(
        user_team=x_user_team,
        limit=limit,
        offset=offset,
        pinned_only=pinned_only
    )
    
    return result


@router.post("/log")
async def save_memory(
    request: SaveMemoryRequest,
    x_user_name: str = Header("anonymous", alias="X-User-Name"),
    x_user_team: Optional[str] = Header(None, alias="X-User-Team")
) -> MemoryResponse:
    """
    Save a briefing or research export to memory log.
    Called when user clicks "Save to Memory" or exports a report.
    """
    logger.info(f"Saving to memory: {request.type} - {request.question[:50]}...")
    
    if request.type not in ["briefing", "research_export"]:
        raise HTTPException(status_code=400, detail="Type must be 'briefing' or 'research_export'")
    
    result = await save_to_memory(
        source=request.type,
        question=request.question,
        answer=request.answer,
        sources=request.sources,
        confidence=request.confidence,
        tags=request.tags,
        user_name=x_user_name,
        user_team=x_user_team
    )
    
    return MemoryResponse(**result)


@router.get("/relevant")
async def get_relevant(
    query: str = Query(..., description="Query to search for"),
    limit: int = Query(5, description="Max results to return"),
    x_user_team: Optional[str] = Header(None, alias="X-User-Team")
):
    """
    Get relevant memories via vector search with time-weighted scoring.
    Returns top memories matching the query, prioritizing:
    - Higher similarity scores
    - More recent memories
    - Same-team memories
    - Non-blocked topics
    """
    logger.info(f"Searching memories: {query[:50]}... (team: {x_user_team})")
    
    memories = await get_relevant_memories(
        query=query,
        user_team=x_user_team,
        limit=limit
    )
    
    return memories


@router.delete("/{memory_id}")
async def delete_memory_endpoint(
    memory_id: str,
    x_user_team: Optional[str] = Header(None, alias="X-User-Team")
):
    """
    Delete a memory from the log.
    """
    logger.info(f"Deleting memory: {memory_id}")
    
    from app.services.memory_service import delete_memory
    result = await delete_memory(memory_id)
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to delete memory"))
    
    return result


@router.patch("/{memory_id}/pin")
async def toggle_pin(
    memory_id: str,
    request: PinRequest,
    x_user_team: str = Header("All Others", alias="X-User-Team")
):
    """
    Pin or unpin a memory.
    Pinned memories never expire. Max 10 pins per team.
    """
    logger.info(f"{'Pinning' if request.pinned else 'Unpinning'} memory: {memory_id}")
    
    if request.pinned:
        result = await pin_memory(memory_id, x_user_team)
    else:
        result = await unpin_memory(memory_id)
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to update pin status"))
    
    return result


@router.post("/block")
async def block_topic_endpoint(
    request: BlockTopicRequest,
    x_user_name: str = Header("anonymous", alias="X-User-Name"),
    x_user_team: str = Header("All Others", alias="X-User-Team")
):
    """
    Block a topic from memory retrieval (soft deprioritization).
    Blocked topics still appear but with reduced relevance scores.
    """
    logger.info(f"Blocking topic: {request.topic}")
    
    result = await block_topic(
        topic=request.topic,
        user_team=x_user_team,
        user_name=x_user_name
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Failed to block topic"))
    
    return result


# =============================================================================
# Agent Context Endpoint
# =============================================================================

@router.get("/context")
async def get_context(
    query: str = Query(..., description="Query to build context for"),
    x_user_team: Optional[str] = Header(None, alias="X-User-Team")
):
    """
    Build full context bundle for agent prompts.
    Returns preferences, relevant memories, and formatted prompt additions.
    Used internally by agents to enrich their responses.
    """
    logger.info(f"Building context for query: {query[:50]}...")
    
    context = await build_agent_context(query, x_user_team)
    
    return {
        "preferences": context.preferences,
        "memories": context.memories,
        "prompt_addition": context.prompt_addition,
        "proactive_intro": context.proactive_intro
    }


# =============================================================================
# Cleanup Job Endpoint (Cloud Scheduler)
# =============================================================================

@router.post("/cleanup")
async def cleanup_memories(
    x_job_key: str = Header(None, alias="X-Job-Key")
):
    """
    Cleanup expired memories. Called by Cloud Scheduler daily.
    Requires X-Job-Key header for authentication.
    """
    # Verify job key for security
    expected_key = os.environ.get("JOB_SECRET_KEY")
    if expected_key and x_job_key != expected_key:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    logger.info("Running memory cleanup job")
    result = await cleanup_expired_memories()
    
    return result
