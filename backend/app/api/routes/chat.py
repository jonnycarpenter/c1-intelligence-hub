"""Chat API endpoints - New Architecture."""

import json
import uuid
from datetime import datetime
from typing import Optional, AsyncGenerator
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.api.schemas import (
    ChatRequest as NewChatRequest,
    ChatResponse as NewChatResponse,
    ChatMessage,
    WorkflowMode,
)
from app.graph.workflow import run_workflow
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


# Mode to agent mapping (new architecture)
MODE_TO_AGENT = {
    WorkflowMode.PULSE: "pulse_agent",      # Placeholder or new pulse implementation
    WorkflowMode.RESEARCH: "deep_research",  # New multi-agent deep research
    # Other modes are currently being transitioned
}


def generate_message_id() -> str:
    """Generate a unique message ID."""
    return f"msg_{uuid.uuid4().hex[:12]}"


def generate_conversation_id() -> str:
    """Generate a unique conversation ID."""
    return f"conv_{uuid.uuid4().hex[:12]}"


# ============================================
# Legacy Models (for backwards compatibility)
# ============================================

class LegacyChatRequest(BaseModel):
    """Legacy chat request model."""
    message: str
    tab: str  # market, financial, product, hub
    session_id: Optional[str] = None


class LegacyChatResponse(BaseModel):
    """Legacy chat response model."""
    content: str
    agent: str
    chart: Optional[dict] = None
    report_id: Optional[str] = None


# ============================================
# New Architecture Endpoints
# ============================================

@router.post("", response_model=NewChatResponse)
async def chat(request: NewChatRequest) -> NewChatResponse:
    """
    Process a chat message (non-streaming).
    
    Routes to the appropriate agent based on the mode:
    - pulse -> Pulse Agent (news, quick research)
    - research -> Deep Research Workflow
    """
    logger.info(f"Chat request: mode={request.mode}, message={request.message[:50]}...")
    
    target_agent = MODE_TO_AGENT.get(request.mode)
    if not target_agent:
        raise HTTPException(status_code=400, detail=f"Invalid mode: {request.mode}")
    
    conversation_id = request.conversation_id or generate_conversation_id()
    
    try:
        full_response = ""
        sources = []
        tools_used = []
        start_time = datetime.now()
        
        async for chunk in run_workflow(
            message=request.message,
            agent_type=target_agent,
            conversation_history=None,
            supply_chain="C1",
        ):
            if chunk.get("type") == "content":
                full_response += chunk.get("content", "")
            elif chunk.get("type") == "final":
                full_response = chunk.get("content", full_response)
            elif chunk.get("type") == "tool_call":
                tools_used.append(chunk.get("content", ""))
            elif chunk.get("type") == "sources":
                sources.extend(chunk.get("sources", []))
        
        duration = (datetime.now() - start_time).total_seconds()
        
        message = ChatMessage(
            id=generate_message_id(),
            role="assistant",
            content=full_response,
            timestamp=datetime.now(),
            sources=[{"title": s.get("title", ""), "url": s.get("url", "")} for s in sources] if sources else None,
            metadata={
                "tools_used": tools_used if tools_used else None,
                "duration": duration,
            },
        )
        
        return NewChatResponse(
            message=message,
            conversation_id=conversation_id,
        )
        
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stream")
async def chat_stream(request: NewChatRequest):
    """
    Process a chat message with streaming response.
    
    Returns Server-Sent Events (SSE) for real-time updates.
    """
    logger.info(f"Stream chat request: mode={request.mode}, message={request.message[:50]}...")
    
    target_agent = MODE_TO_AGENT.get(request.mode)
    if not target_agent:
        raise HTTPException(status_code=400, detail=f"Invalid mode: {request.mode}")
    
    conversation_id = request.conversation_id or generate_conversation_id()
    message_id = generate_message_id()
    
    async def generate() -> AsyncGenerator[str, None]:
        """Generate streaming response with thinking events."""
        try:
            # Send initial metadata
            yield f"data: {json.dumps({'type': 'start', 'message_id': message_id, 'conversation_id': conversation_id, 'agent': target_agent})}\n\n"
            
            async for chunk in run_workflow(
                message=request.message,
                agent_type=target_agent,
                conversation_history=None,
                supply_chain="C1",
            ):
                chunk_type = chunk.get("type", "")
                agent = chunk.get("agent", target_agent)
                metadata = chunk.get("metadata", {})
                
                # Content events (final response text)
                if chunk_type == "content":
                    yield f"data: {json.dumps({'type': 'content', 'content': chunk.get('content', ''), 'agent': agent})}\n\n"
                
                # Status updates
                elif chunk_type == "status":
                    yield f"data: {json.dumps({'type': 'status', 'content': chunk.get('content', ''), 'agent': agent})}\n\n"
                
                # Routing decisions
                elif chunk_type == "routing":
                    yield f"data: {json.dumps({'type': 'routing', 'content': chunk.get('content', ''), 'reasoning': chunk.get('reasoning', ''), 'agent': agent})}\n\n"
                
                # Thinking events (LLM processing)
                elif chunk_type in ["thinking_start", "thinking_end"]:
                    yield f"data: {json.dumps({'type': 'thinking', 'event': chunk_type, 'content': chunk.get('content', ''), 'agent': agent})}\n\n"
                
                # Tool events (detailed tracing)
                elif chunk_type == "tool_start":
                    yield f"data: {json.dumps({'type': 'tool_start', 'content': chunk.get('content', ''), 'tool_name': metadata.get('tool_name', ''), 'inputs': metadata.get('inputs', {}), 'agent': agent})}\n\n"
                
                elif chunk_type == "tool_end":
                    # Include full output for product extraction on frontend
                    output = metadata.get('output', '')
                    yield f"data: {json.dumps({'type': 'tool_end', 'content': chunk.get('content', ''), 'tool_name': metadata.get('tool_name', ''), 'output_summary': metadata.get('output_summary', ''), 'output': output, 'agent': agent})}\n\n"
                
                elif chunk_type == "tool_call":
                    yield f"data: {json.dumps({'type': 'tool_call', 'content': chunk.get('content', ''), 'tool_name': metadata.get('tool_name', ''), 'agent': agent})}\n\n"
                
                elif chunk_type == "tool_result":
                    result = metadata.get('result', '')
                    if isinstance(result, str) and len(result) > 500:
                        result = result[:500] + "..."
                    yield f"data: {json.dumps({'type': 'tool_result', 'tool': chunk.get('content', ''), 'result': result, 'agent': agent})}\n\n"
                
                elif chunk_type == "tool_error":
                    yield f"data: {json.dumps({'type': 'tool_error', 'content': chunk.get('content', ''), 'agent': agent})}\n\n"
                
                # Agent action/finish
                elif chunk_type == "agent_action":
                    yield f"data: {json.dumps({'type': 'agent_action', 'content': chunk.get('content', ''), 'tool': metadata.get('tool', ''), 'agent': agent})}\n\n"
                
                elif chunk_type == "agent_finish":
                    yield f"data: {json.dumps({'type': 'agent_finish', 'content': chunk.get('content', ''), 'agent': agent})}\n\n"
                
                # Final response
                elif chunk_type == "final":
                    yield f"data: {json.dumps({'type': 'final', 'content': chunk.get('content', ''), 'agent': agent})}\n\n"
                
                # Completion
                elif chunk_type == "complete":
                    yield f"data: {json.dumps({'type': 'complete', 'content': chunk.get('content', ''), 'agent': agent})}\n\n"
                
                # Errors
                elif chunk_type == "error":
                    yield f"data: {json.dumps({'type': 'error', 'content': chunk.get('content', ''), 'agent': agent})}\n\n"
            
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            
        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ============================================
# Legacy Endpoints (for backwards compatibility)
# ============================================

@router.post("/legacy")
async def chat_legacy(request: LegacyChatRequest):
    """
    Legacy chat endpoint (maintains backwards compatibility).
    """
    logger.warning("Legacy chat endpoint called - consider migrating to new API")
    
    tab_to_agent = {
        "market": "industry_watcher",
        "financial": "market_scout",
        "product": "product_maven",
        "hub": "industry_watcher",  # Data management tools available to industry_watcher
    }
    
    target_agent = tab_to_agent.get(request.tab)
    if not target_agent:
        raise HTTPException(status_code=400, detail=f"Invalid tab: {request.tab}")
    
    async def generate():
        try:
            async for chunk in run_workflow(
                message=request.message,
                agent_type=target_agent,
                conversation_history=None,
                supply_chain="C1",
            ):
                yield f"data: {json.dumps(chunk)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.error(f"Legacy workflow error: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.post("/sync")
async def chat_sync(request: LegacyChatRequest) -> LegacyChatResponse:
    """
    Legacy synchronous chat endpoint (non-streaming).
    """
    logger.info(f"Sync chat request: tab={request.tab}")
    
    tab_to_agent = {
        "market": "industry_watcher",
        "financial": "market_scout",
        "product": "product_maven",
        "hub": "industry_watcher",  # Data management tools available to industry_watcher
    }
    
    target_agent = tab_to_agent.get(request.tab)
    if not target_agent:
        raise HTTPException(status_code=400, detail=f"Invalid tab: {request.tab}")
    
    try:
        full_response = ""
        chart_data = None
        report_id = None
        
        async for chunk in run_workflow(
            message=request.message,
            agent_type=target_agent,
            conversation_history=None,
            supply_chain="C1",
        ):
            if "content" in chunk:
                full_response += chunk["content"]
            if "chart" in chunk:
                chart_data = chunk["chart"]
            if "report_id" in chunk:
                report_id = chunk["report_id"]
        
        return LegacyChatResponse(
            content=full_response,
            agent=target_agent,
            chart=chart_data,
            report_id=report_id,
        )
        
    except Exception as e:
        logger.error(f"Sync workflow error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
