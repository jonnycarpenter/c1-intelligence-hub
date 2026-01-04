"""Main workflow graph using LangGraph."""

import asyncio
from typing import AsyncGenerator, Dict, Any, Optional
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, END

from app.graph.state import GraphState
from app.utils.grounding import get_grounding_context
from app.utils.streaming_callback import StreamingThinkingHandler, ThinkingEvent
from app.utils.logger import get_logger
from app.config.settings import settings
from app.graph.research_workflow import research_workflow as deep_research_workflow

logger = get_logger(__name__)


async def run_workflow(
    message: str,
    agent_type: str,
    conversation_history: Optional[list] = None,
    supply_chain: str = "C1",
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Run the agent workflow and yield streaming results.
    
    Args:
        message: User's message/query
        agent_type: Which agent to use (or "auto" for router to decide)
        conversation_history: Previous messages in conversation
        supply_chain: Supply chain context (C1, F1, E1, etc.)
    
    Yields:
        Dict with streaming chunks: {"type": "...", "content": "..."}
    """
    logger.info(f"Running workflow: agent_type={agent_type}, message={message[:50]}...")
    
    # Yield initial status
    yield {
        "type": "status",
        "content": "Starting analysis...",
        "agent": agent_type,
    }
    
    try:
        # Get grounding context
        grounding = get_grounding_context()
        
        # Build message history
        messages = []
        if conversation_history:
            for msg in conversation_history:
                if msg.get("role") == "user":
                    messages.append(HumanMessage(content=msg["content"]))
                elif msg.get("role") == "assistant":
                    messages.append(AIMessage(content=msg["content"]))
        
        # Add current message
        messages.append(HumanMessage(content=message))
        
        # Get the appropriate agent
        yield {
            "type": "status",
            "content": f"Connecting to {_agent_display_name(agent_type)}...",
            "agent": agent_type,
        }
        
        agent = _get_agent(agent_type)
        
        # Build agent state
        state = {
            "messages": messages,
            "query": message,
            "agent_type": agent_type,
            "companies": grounding["companies"],
            "materials": grounding["materials"],
            "industries": grounding["industries"],
            "exclusions": grounding["exclusions"],
            "supply_chain": supply_chain,
            "tool_results": [],
            "response": None,
        }
        
        # Create a queue for thinking events
        thinking_queue: asyncio.Queue = asyncio.Queue()
        
        # Create callback handler for tracing
        callback_handler = StreamingThinkingHandler(
            queue=thinking_queue,
            agent_name=_agent_display_name(agent_type),
        )
        
        # Run agent and stream results
        yield {
            "type": "status",
            "content": "Processing your request...",
            "agent": agent_type,
        }
        
        # Stream with callbacks for detailed tracing
        config = {"callbacks": [callback_handler]}
        
        async for chunk in agent.astream(state, config=config):
            # First, drain any thinking events from the queue
            while not thinking_queue.empty():
                try:
                    thinking_event = thinking_queue.get_nowait()
                    yield {
                        "type": thinking_event.event_type,
                        "content": thinking_event.content,
                        "metadata": thinking_event.metadata,
                        "agent": agent_type,
                    }
                except asyncio.QueueEmpty:
                    break
            
            # LangGraph astream returns chunks keyed by node name: {"node_name": {state_updates}}
            # We need to look inside each node's output
            for node_name, node_output in chunk.items():
                if not isinstance(node_output, dict):
                    continue
                    
                # Handle messages from agent nodes
                if "messages" in node_output and node_output["messages"]:
                    for msg in node_output["messages"]:
                        # Check for tool calls
                        if hasattr(msg, "tool_calls") and msg.tool_calls:
                            for tool_call in msg.tool_calls:
                                yield {
                                    "type": "tool_call",
                                    "content": f"Using {tool_call.get('name', 'tool')}...",
                                    "metadata": {
                                        "tool_name": tool_call.get("name"),
                                        "tool_args": tool_call.get("args", {}),
                                    },
                                    "agent": agent_type,
                                }
                        
                        # Check for content (but skip if this is just tool calling)
                        if hasattr(msg, "content") and msg.content:
                            # Don't yield content if there are tool calls - wait for final response
                            if not (hasattr(msg, "tool_calls") and msg.tool_calls):
                                yield {
                                    "type": "content",
                                    "content": msg.content,
                                    "agent": agent_type,
                                }
                
                if "tool_results" in node_output and node_output["tool_results"]:
                    for result in node_output["tool_results"]:
                        yield {
                            "type": "tool_result",
                            "content": result.get("tool", "Unknown tool"),
                            "metadata": {"result": result.get("result", "")},
                            "agent": agent_type,
                        }
                
                if "response" in node_output and node_output["response"]:
                    yield {
                        "type": "final",
                        "content": node_output["response"],
                        "agent": agent_type,
                    }
        
        # Drain any remaining thinking events
        while not thinking_queue.empty():
            try:
                thinking_event = thinking_queue.get_nowait()
                yield {
                    "type": thinking_event.event_type,
                    "content": thinking_event.content,
                    "metadata": thinking_event.metadata,
                    "agent": agent_type,
                }
            except asyncio.QueueEmpty:
                break
        
        yield {
            "type": "complete",
            "content": "Analysis complete",
            "agent": agent_type,
        }
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"Workflow error: {e}\n{error_details}")
        
        # Provide more specific error messages for common issues
        error_message = str(e)
        if "rate_limit" in error_message.lower() or "429" in error_message:
            error_message = "Rate limit exceeded. Please wait a moment and try again."
        elif "authentication" in error_message.lower() or "401" in error_message or "api_key" in error_message.lower():
            error_message = "API authentication error. Please check the API key configuration."
        elif "timeout" in error_message.lower():
            error_message = "Request timed out. Please try again with a simpler query."
        elif "connection" in error_message.lower():
            error_message = "Connection error. Please check network connectivity."
        
        yield {
            "type": "error",
            "content": error_message,
            "agent": agent_type,
        }


def _get_agent(agent_type: str):
    """Get the appropriate agent based on type."""
    agents = {
        "deep_research": lambda: deep_research_workflow.compile(),
        # "pulse_agent": ..., # To be implemented
    }
    
    if agent_type not in agents:
        # If we can't find the agent, raise a clear error
        raise ValueError(f"Retired or unknown agent type: {agent_type}")
    
    return agents[agent_type]()


def _agent_display_name(agent_type: str) -> str:
    """Get display name for agent type."""
    names = {
        "deep_research": "Deep Research",
    }
    return names.get(agent_type, agent_type)
