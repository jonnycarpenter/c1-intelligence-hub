"""
Supply Chain Agent API Route — SSE Streaming
=============================================

POST /api/supply-network/agent/query
Streams progress events and final result from the LLM supply chain agent.

SSE events:
    data: {"type": "progress", "step": "Searching...", "tool": "search_supply_chain_entity"}
    data: {"type": "result", "data": {...structured response...}}
    data: {"type": "error", "message": "..."}
    data: [DONE]
"""

import json
import logging
import time

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()


class AgentQueryRequest(BaseModel):
    query: str
    session_id: str | None = None


@router.post("/agent/query")
async def query_supply_chain_agent(request: AgentQueryRequest):
    """Stream LLM supply chain agent results via SSE."""

    async def event_stream():
        start_time = time.time()
        logger.info(f"[SUPPLY_CHAIN_AGENT_API] Request START: query={request.query[:100]}")

        try:
            from app.agents.supply_chain.agent import SupplyChainAgent
            agent = SupplyChainAgent()

            async for event in agent.query_stream(request.query):
                yield f"data: {json.dumps(event, default=str)}\n\n"

        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"[SUPPLY_CHAIN_AGENT_API] Error in {elapsed:.2f}s: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

        finally:
            elapsed = time.time() - start_time
            logger.info(f"[SUPPLY_CHAIN_AGENT_API] Request COMPLETE: {elapsed:.2f}s")
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
