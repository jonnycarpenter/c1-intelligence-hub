"""Briefing API endpoints - Pulse "Need to Know" functionality.

Endpoints:
- GET /summaries - Get latest weekly executive briefing (new format with dynamic sections)
- GET /summaries/{category} - Get briefing by category (legacy support)
- POST /adhoc - Generate an ad hoc quick briefing based on user question
- GET /adhoc/history - Get user's ad hoc briefing history
- GET /history - Get historical briefings (weekly + ad hoc)
- GET /trending/{entity_type} - Get trending entities from briefings
"""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from datetime import datetime
import json

from app.config.settings import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


# =============================================================================
# Response Models
# =============================================================================

class SourceArticle(BaseModel):
    """A source article used in briefing generation."""
    id: str
    title: str
    url: str
    source_name: str
    source_type: Optional[str] = None
    published_at: Optional[str] = None
    summary: Optional[str] = None
    priority: Optional[str] = None
    relevance_score: Optional[float] = None


class KeyFigure(BaseModel):
    """A key figure/statistic extracted from the briefing."""
    figure: str
    context: str
    source: Optional[str] = None


class BriefingResponse(BaseModel):
    """Full briefing response with source citations."""
    id: str
    category: str
    headline: str
    summary: str
    key_insights: List[str]
    trend_signal: str
    attention_flag: str
    attention_reason: Optional[str] = None
    period_start: datetime
    period_end: datetime
    generated_at: datetime
    model: str
    
    # Source tracking for citations
    article_ids: List[str] = []
    article_count: Optional[int] = None
    source_articles: Optional[List[SourceArticle]] = None
    sources_breakdown: Optional[Dict[str, int]] = None
    
    # Entity extraction for display
    companies_mentioned: Optional[List[str]] = None
    materials_mentioned: Optional[List[str]] = None
    topics_extracted: Optional[List[str]] = None
    key_figures: Optional[List[KeyFigure]] = None
    
    # Scheduler metadata
    scheduler_run: Optional[str] = None
    quarter: Optional[str] = None
    
    # Quality metrics
    avg_article_relevance: Optional[float] = None
    high_priority_count: Optional[int] = None


class TrendingEntity(BaseModel):
    """A trending entity from quarterly analysis."""
    name: str
    total_mentions: int
    categories_appeared: List[str]
    weeks_appeared: int
    sample_contexts: Optional[List[str]] = None


# =============================================================================
# New Weekly Briefing Models (Dynamic Sections)
# =============================================================================

class CompanyWithLogo(BaseModel):
    """Company with logo URL for display."""
    name: str
    domain: Optional[str] = None
    logo_url: Optional[str] = None


class BriefingInsight(BaseModel):
    """A single insight in a briefing section."""
    text: str
    status: str = Field(description="'net_new' or 'continuing'")
    companies_mentioned: List[str] = []


class BriefingSection(BaseModel):
    """A section in the weekly briefing."""
    header: str
    headline: BriefingInsight
    insights: List[BriefingInsight] = []
    source_articles: List[SourceArticle] = []
    companies_with_logos: List[CompanyWithLogo] = []


class WeeklyBriefingResponse(BaseModel):
    """Response model for the new weekly executive briefing."""
    id: str
    briefing_type: str = "weekly_executive"
    briefing_title: str
    sections: List[BriefingSection]
    all_companies_mentioned: List[CompanyWithLogo] = []
    key_topics_this_week: List[str] = []
    overall_trend: str
    period_start: datetime
    period_end: datetime
    generated_at: datetime
    model: str
    article_count: int
    article_ids: List[str] = []


# =============================================================================
# Ad Hoc Briefing Models
# =============================================================================

class AdHocBriefingRequest(BaseModel):
    """Request for generating an ad hoc quick briefing."""
    question: str = Field(..., min_length=10, max_length=1000, description="User's question")
    context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Structured context: current_brief_headlines, current_brief_date, recent_digest_topics"
    )
    is_follow_up: bool = Field(default=False, description="Whether this is a follow-up question")
    stream: bool = Field(default=False, description="Whether to stream the response")
    session_id: Optional[str] = Field(default=None, description="Session ID for stateful conversation. Omit for new session.")


class AdHocBriefingSourceUsed(BaseModel):
    """A source used in an ad hoc briefing."""
    title: str
    url: Optional[str] = None
    relevance: Optional[str] = None


class SessionInfo(BaseModel):
    """Session state information returned with ad-hoc briefing responses."""
    session_id: str
    follow_up_count: int
    max_follow_ups: int
    turns_remaining: int
    created_at: str
    last_activity: str
    history_length: int


class AdHocBriefingResponse(BaseModel):
    """Response for an ad hoc briefing."""
    id: str
    question: str
    answer: str
    sources_used: List[AdHocBriefingSourceUsed] = []
    confidence: str = "medium"
    suggest_deep_research: bool = False
    deep_research_query: Optional[str] = None
    related_topics: List[str] = []
    follow_up_count: int = 0
    redirect_to_deep_research: bool = False
    generated_at: str
    model: Optional[str] = None
    error: Optional[str] = None
    # Session management fields
    session_id: Optional[str] = Field(default=None, description="Session ID for follow-up questions")
    session: Optional[SessionInfo] = Field(default=None, description="Full session state")


# =============================================================================
# Helper Functions
# =============================================================================

async def _get_bq_storage():
    """Get BigQuery storage if available."""
    try:
        from app.db.gcp_storage import BigQueryDataStorage, gcp_config
        if gcp_config.is_configured:
            storage = BigQueryDataStorage(gcp_config)
            await storage.initialize()
            return storage
    except Exception as e:
        logger.warning(f"BigQuery not available: {e}")
    return None


# =============================================================================
# API Endpoints
# =============================================================================

@router.get("/summaries", response_model=List[Dict[str, Any]])
async def get_pulse_summaries(include_sources: bool = Query(True, description="Include full source article details")):
    """
    Get the latest pre-computed briefings for each category.
    
    Returns the most recent briefing for each of the 5 categories:
    - MARKET
    - COMPETITOR  
    - PRODUCT
    - REGULATORY
    - SUPPLY_CHAIN
    
    Each briefing includes:
    - Executive headline and summary with source citations
    - Key insights (3-5 bullet points)
    - Trend signal and attention flags
    - Full source article list for citation verification (if include_sources=true)
    - Extracted entities (companies, materials, topics)
    """
    logger.info(f"Pulse summaries request (include_sources={include_sources})")
    
    try:
        # BigQuery is the only storage backend
        bq_storage = await _get_bq_storage()
        
        if not bq_storage:
            raise HTTPException(status_code=503, detail="BigQuery storage not available")
        
        briefings = await bq_storage.get_latest_briefings()
        logger.info(f"Retrieved {len(briefings)} briefings from BigQuery")
        
        # Optionally strip source_articles to reduce payload
        if not include_sources:
            for b in briefings:
                if 'source_articles' in b:
                    # Keep just the count
                    b['article_count'] = len(b.get('source_articles', []))
                    del b['source_articles']
        
        return briefings
        
    except Exception as e:
        logger.error(f"Error getting pulse summaries: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve pulse summaries")


@router.get("/summaries/{category}", response_model=Dict[str, Any])
async def get_briefing_by_category(
    category: str,
    include_sources: bool = Query(True, description="Include full source article details")
):
    """
    Get the latest briefing for a specific category.
    
    Categories: MARKET, COMPETITOR, PRODUCT, REGULATORY, SUPPLY_CHAIN
    """
    logger.info(f"Briefing request for category: {category}")
    
    try:
        bq_storage = await _get_bq_storage()
        
        if not bq_storage:
            raise HTTPException(status_code=503, detail="BigQuery storage not available")
        
        briefings = await bq_storage.get_latest_briefings()
        
        # Find the matching category
        category_upper = category.upper()
        for b in briefings:
            if b.get('category', '').upper() == category_upper:
                if not include_sources and 'source_articles' in b:
                    b['article_count'] = len(b.get('source_articles', []))
                    del b['source_articles']
                return b
        
        raise HTTPException(status_code=404, detail=f"No briefing found for category: {category}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting briefing for {category}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve briefing")


@router.get("/trending/{entity_type}", response_model=List[TrendingEntity])
async def get_trending_entities(
    entity_type: str,
    quarter: Optional[str] = Query(None, description="Quarter like '2025-Q1'. Defaults to current quarter.")
):
    """
    Get trending entities from briefings for quarterly analysis.
    
    Entity types:
    - companies: Company names mentioned across briefings
    - materials: Materials (carbon fiber, PEEK, etc.) mentioned
    - topics: Themes/topics extracted (capacity expansion, sustainability, etc.)
    
    This aggregates mentions across all briefings in the quarter to identify
    what's trending in the composites industry.
    """
    logger.info(f"Trending request: {entity_type} for quarter {quarter}")
    
    if entity_type not in ['companies', 'materials', 'topics']:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid entity_type: {entity_type}. Must be: companies, materials, or topics"
        )
    
    # Default to current quarter
    if not quarter:
        now = datetime.utcnow()
        quarter = f"{now.year}-Q{(now.month - 1) // 3 + 1}"
    
    try:
        bq_storage = await _get_bq_storage()
        
        if bq_storage:
            trending = await bq_storage.get_trending_from_briefings(quarter, entity_type)
            return trending
        else:
            # Local SQLite doesn't support quarterly trending well
            logger.warning("Trending endpoint requires BigQuery - returning empty")
            return []
        
    except Exception as e:
        logger.error(f"Error getting trending {entity_type}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve trending data")


@router.get("/history", response_model=List[Dict[str, Any]])
async def get_briefing_history(
    category: Optional[str] = Query(None, description="Filter by category"),
    quarter: Optional[str] = Query(None, description="Filter by quarter like '2025-Q1'"),
    limit: int = Query(20, description="Max briefings to return")
):
    """
    Get historical briefings for analysis and comparison.
    
    Useful for:
    - Comparing how briefings evolved over time
    - Auditing what sources were used
    - Quarterly review meetings
    """
    logger.info(f"Briefing history request: category={category}, quarter={quarter}")
    
    try:
        bq_storage = await _get_bq_storage()
        
        if not bq_storage:
            raise HTTPException(status_code=503, detail="BigQuery storage not available")
        
        if quarter:
            briefings = await bq_storage.get_briefings_for_quarter(quarter, category)
            return briefings[:limit]
        else:
            briefings = await bq_storage.get_latest_briefings(limit_per_category=limit)
            if category:
                briefings = [b for b in briefings if b.get('category', '').upper() == category.upper()]
            return briefings
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting briefing history: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve briefing history")

# =============================================================================
# New Weekly Briefing Endpoints
# =============================================================================

@router.get("/weekly", response_model=Dict[str, Any])
async def get_weekly_briefing():
    """
    Get the latest weekly executive briefing (new format with dynamic sections).
    
    Returns the most recent weekly briefing with:
    - Max 3 dynamic sections (agent-determined groupings)
    - Headline per section (bold, always visible)
    - Sub-bullet insights (in expandable tray)
    - Net New vs Continuing to Track status
    - Company logos via Logo.dev
    - Inline citations with sources at bottom of each section
    """
    logger.info("Weekly briefing request")
    
    try:
        bq_storage = await _get_bq_storage()
        
        if not bq_storage:
            raise HTTPException(status_code=503, detail="BigQuery storage not available")
        
        briefing = await bq_storage.get_latest_weekly_briefing()
        if briefing:
            logger.info(f"Retrieved weekly briefing from BigQuery: {briefing.get('id', 'unknown')}")
            return briefing
        
        # No briefing found
        raise HTTPException(status_code=404, detail="No weekly briefing found")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting weekly briefing: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve weekly briefing")


@router.get("/weekly/history", response_model=List[Dict[str, Any]])
async def get_weekly_briefing_history(
    limit: int = Query(10, ge=1, le=52, description="Number of past briefings to return")
):
    """
    Get historical weekly briefings for the Briefing History Timeline.
    
    Returns past weekly briefings for reference and trend analysis.
    """
    logger.info(f"Weekly briefing history request: limit={limit}")
    
    try:
        bq_storage = await _get_bq_storage()
        
        if not bq_storage:
            raise HTTPException(status_code=503, detail="BigQuery storage not available")
        
        briefings = await bq_storage.get_weekly_briefing_history(limit=limit)
        return briefings
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting weekly briefing history: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve briefing history")


# =============================================================================
# Ad Hoc Briefing Endpoints
# =============================================================================

@router.post("/adhoc", response_model=AdHocBriefingResponse)
async def create_adhoc_briefing(
    request: AdHocBriefingRequest,
    x_user_team: Optional[str] = Header(None, alias="X-User-Team"),
):
    """
    Generate an ad hoc quick briefing based on user's question.
    
    Features:
    - Fast response using Claude Haiku
    - Searches embedded articles (semantic search)
    - Context-aware of current brief and digest
    - **Session-based follow-up tracking** - Max 2 follow-ups, then suggests Deep Research
    - **Memory context** - Injects user preferences and relevant past memories
    - Stores in adhoc_briefings BigQuery table
    
    Request headers:
    - X-User-Team: User's team for team-scoped memory context
    
    Request body:
    - question: User's question (required)
    - context: {current_brief_headlines, current_brief_date, recent_digest_topics}
    - is_follow_up: Whether this is a follow-up question
    - session_id: Optional session ID for follow-up questions (omit for new session)
    - stream: Whether to stream the response (use /adhoc/stream endpoint instead)
    
    Response includes:
    - session_id: Use this for follow-up questions
    - session: Full session state with follow_up_count and turns_remaining
    """
    logger.info(f"Ad hoc briefing request: '{request.question[:50]}...' follow_up={request.is_follow_up} session={request.session_id} team={x_user_team}")
    
    try:
        from app.agents.adhoc_briefing import AdHocBriefingAgent, BriefingContext, get_session_manager
        
        # Get or create session
        session_manager = get_session_manager()
        session = session_manager.get_or_create_session(request.session_id)
        
        logger.info(f"Using session {session.session_id} (follow_up_count={session.follow_up_count})")
        
        # Build context
        context = BriefingContext.from_dict(request.context)
        
        # Create agent and generate briefing with session and memory context
        agent = AdHocBriefingAgent()
        result = await agent.generate_briefing(
            question=request.question,
            context=context,
            is_follow_up=request.is_follow_up,
            session=session,
            user_team=x_user_team,
        )
        
        logger.info(f"Ad hoc briefing generated: id={result.get('id')}, confidence={result.get('confidence')}, session={session.session_id}")
        
        return AdHocBriefingResponse(**result)
        
    except Exception as e:
        logger.error(f"Error generating ad hoc briefing: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate briefing: {str(e)}")


@router.post("/adhoc/stream")
async def create_adhoc_briefing_stream(
    request: AdHocBriefingRequest,
    x_user_team: Optional[str] = Header(None, alias="X-User-Team"),
):
    """
    Stream an ad hoc quick briefing response.
    
    Returns a streaming response with chunks of the briefing as they're generated.
    Better UX for longer responses. Includes memory context (preferences + past memories).
    
    Request headers:
    - X-User-Team: User's team for team-scoped memory context
    
    Request body:
    - question: User's question (required)
    - context: {current_brief_headlines, current_brief_date, recent_digest_topics}
    - is_follow_up: Whether this is a follow-up question
    - session_id: Optional session ID for follow-up questions
    
    SSE events include:
    - {"type": "content", "text": "..."} - Response text chunks
    - {"type": "session_info", "session_id": "...", "follow_up_count": N, "turns_remaining": N} - Session state at end
    - {"type": "redirect", ...} - Redirect to Deep Research
    """
    logger.info(f"Ad hoc briefing stream request: '{request.question[:50]}...' session={request.session_id} team={x_user_team}")
    
    try:
        from app.agents.adhoc_briefing import StreamingAdHocBriefingAgent, BriefingContext, get_session_manager
        
        # Get or create session
        session_manager = get_session_manager()
        session = session_manager.get_or_create_session(request.session_id)
        
        logger.info(f"Streaming with session {session.session_id} (follow_up_count={session.follow_up_count})")
        
        context = BriefingContext.from_dict(request.context)
        agent = StreamingAdHocBriefingAgent()
        
        async def generate():
            async for chunk in agent.generate_briefing_stream(
                question=request.question,
                context=context,
                is_follow_up=request.is_follow_up,
                session=session,
                user_team=x_user_team,
            ):
                yield f"data: {chunk}\n\n"
            yield "data: [DONE]\n\n"
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )
        
    except Exception as e:
        logger.error(f"Error streaming ad hoc briefing: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to stream briefing: {str(e)}")


@router.get("/adhoc/history", response_model=List[Dict[str, Any]])
async def get_adhoc_briefing_history(
    limit: int = Query(20, ge=1, le=100, description="Number of past briefings to return")
):
    """
    Get user's ad hoc briefing history.
    
    Returns past ad hoc briefings for reference. Part of the Briefing History Timeline.
    """
    logger.info(f"Ad hoc briefing history request: limit={limit}")
    
    try:
        bq_storage = await _get_bq_storage()
        
        if not bq_storage:
            raise HTTPException(status_code=503, detail="BigQuery storage unavailable")
        
        briefings = await bq_storage.get_adhoc_briefing_history(limit=limit)
        return briefings
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting ad hoc briefing history: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve briefing history")


@router.get("/adhoc/session/{session_id}", response_model=Dict[str, Any])
async def get_session_info(session_id: str):
    """
    Get information about a briefing session.
    
    Useful for:
    - Checking how many follow-ups remain
    - Viewing conversation history length
    - Debugging session state
    """
    try:
        from app.agents.adhoc_briefing import get_session_manager
        
        session_manager = get_session_manager()
        session = session_manager.get_session(session_id)
        
        if not session:
            raise HTTPException(status_code=404, detail="Session not found or expired")
        
        return session.to_dict()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session info: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve session")


@router.delete("/adhoc/session/{session_id}")
async def end_session(session_id: str):
    """
    End a briefing session explicitly.
    
    The session will also expire automatically after 30 minutes of inactivity.
    """
    try:
        from app.agents.adhoc_briefing import get_session_manager
        
        session_manager = get_session_manager()
        deleted = session_manager.delete_session(session_id)
        
        if not deleted:
            raise HTTPException(status_code=404, detail="Session not found")
        
        return {"message": "Session ended", "session_id": session_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error ending session: {e}")
        raise HTTPException(status_code=500, detail="Failed to end session")


@router.get("/adhoc/sessions/stats", response_model=Dict[str, Any])
async def get_session_stats():
    """
    Get session manager statistics (admin/debug endpoint).
    
    Returns:
    - total_sessions: Number of sessions in memory
    - active_sessions: Non-expired sessions
    - max_sessions: Maximum allowed sessions (LRU eviction after)
    - ttl_minutes: Session timeout in minutes
    """
    try:
        from app.agents.adhoc_briefing import get_session_manager
        
        session_manager = get_session_manager()
        return session_manager.get_stats()
        
    except Exception as e:
        logger.error(f"Error getting session stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve stats")


# =============================================================================
# Combined Briefing History (for Timeline feature)
# =============================================================================

@router.get("/all-history", response_model=Dict[str, Any])
async def get_all_briefing_history(
    weekly_limit: int = Query(10, ge=1, le=52),
    adhoc_limit: int = Query(20, ge=1, le=100),
):
    """
    Get combined briefing history for the Briefing History Timeline.
    
    Returns both weekly and ad hoc briefings, sorted by date.
    This powers the "Briefing History" / "Past Briefings" dropdown on Pulse.
    """
    logger.info(f"All briefing history request: weekly={weekly_limit}, adhoc={adhoc_limit}")
    
    try:
        bq_storage = await _get_bq_storage()
        
        if not bq_storage:
            raise HTTPException(status_code=503, detail="BigQuery storage unavailable")
        
        weekly_briefings = await bq_storage.get_weekly_briefing_history(limit=weekly_limit)
        adhoc_briefings = await bq_storage.get_adhoc_briefing_history(limit=adhoc_limit)
        
        return {
            "weekly_briefings": weekly_briefings,
            "adhoc_briefings": adhoc_briefings,
            "total_weekly": len(weekly_briefings),
            "total_adhoc": len(adhoc_briefings),
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting all briefing history: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve briefing history")