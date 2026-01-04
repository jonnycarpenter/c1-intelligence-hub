from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from app.graph.research_workflow import research_workflow
from app.agents.research.state import DeepResearchState
from langchain_core.messages import HumanMessage
import json
import asyncio

router = APIRouter()

class DeepResearchRequest(BaseModel):
    query: str
    history: List[Dict[str, Any]] = []

@router.post("/run")
async def run_deep_research(request: DeepResearchRequest):
    """
    Trigger the deep research workflow and stream status updates.
    """
    # Initialize state
    state: DeepResearchState = {
        "user_query": request.query,
        "conversation_history": [
            HumanMessage(content=m["content"]) if m["role"] == "user" else HumanMessage(content=m["content"]) # Placeholder for AIMessage
            for m in request.history
        ],
        "research_brief": None,
        "clarification_count": 0,
        "financial_output": None,
        "industry_output": None,
        "final_report": None,
        "current_status": "starting",
        "errors": [],
    }

    async def event_generator():
        # This is a simplified streaming implementation
        # In production, we'd stream individual node updates
        try:
            yield f"data: {json.dumps({'type': 'status', 'content': 'Grooming your query...'})}\n\n"
            
            # Execute workflow
            final_state = await research_workflow.ainvoke(state)
            
            # Stream milestones
            if final_state.get("research_brief"):
                brief = final_state["research_brief"]
                if brief.status == "needs_clarification":
                    yield f"data: {json.dumps({'type': 'clarification', 'content': brief.clarifying_question.model_dump()})}\n\n"
                    return
                else:
                    yield f"data: {json.dumps({'type': 'status', 'content': 'Starting multifaceted research...'})}\n\n"
            
            if final_state.get("financial_output"):
                yield f"data: {json.dumps({'type': 'status', 'content': 'Financial analysis complete.'})}\n\n"
                
            if final_state.get("industry_output"):
                yield f"data: {json.dumps({'type': 'status', 'content': 'Industry analysis complete.'})}\n\n"
                
            if final_state.get("final_report"):
                yield f"data: {json.dumps({'type': 'status', 'content': 'Synthesis complete. Generating report...'})}\n\n"
                report = final_state["final_report"].model_dump()
                yield f"data: {json.dumps({'type': 'report', 'content': report})}\n\n"
                
            yield "data: [DONE]\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
