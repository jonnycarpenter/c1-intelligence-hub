"""Custom callback handler for streaming agent thinking/tracing to the frontend."""

import asyncio
import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.messages import BaseMessage
from langchain_core.outputs import LLMResult
from langchain_core.agents import AgentAction, AgentFinish

from app.utils.logger import get_logger

logger = get_logger(__name__)


class ThinkingEvent:
    """Represents a single thinking/tracing event."""
    
    def __init__(
        self,
        event_type: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None,
    ):
        self.event_type = event_type
        self.content = content
        self.metadata = metadata or {}
        self.timestamp = timestamp or datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.event_type,
            "content": self.content,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
        }
    
    def to_sse(self) -> str:
        """Format as Server-Sent Event."""
        return f"data: {json.dumps(self.to_dict())}\n\n"


class StreamingThinkingHandler(AsyncCallbackHandler):
    """
    Async callback handler that captures agent thinking and streams to a queue.
    
    Events captured:
    - llm_start: When the LLM starts generating
    - llm_token: Each token streamed (for thinking animation)
    - tool_start: When a tool is about to be called
    - tool_end: When a tool returns results
    - agent_action: When the agent decides to take an action
    - agent_finish: When the agent completes
    - chain_start/end: Higher-level chain events
    """
    
    def __init__(self, queue: asyncio.Queue, agent_name: str = "Agent"):
        self.queue = queue
        self.agent_name = agent_name
        self.current_tool = None
        self.run_ids: Dict[str, str] = {}  # Track run_id to tool name mapping
    
    async def _emit(self, event: ThinkingEvent):
        """Emit an event to the queue."""
        await self.queue.put(event)
    
    # ==========================================
    # LLM Events
    # ==========================================
    
    async def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Called when LLM starts generating."""
        await self._emit(ThinkingEvent(
            event_type="thinking_start",
            content=f"{self.agent_name} is thinking...",
            metadata={"run_id": str(run_id)},
        ))
    
    async def on_chat_model_start(
        self,
        serialized: Dict[str, Any],
        messages: List[List[BaseMessage]],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Called when chat model starts generating (for chat-based LLMs)."""
        await self._emit(ThinkingEvent(
            event_type="thinking_start",
            content=f"{self.agent_name} is thinking...",
            metadata={"run_id": str(run_id)},
        ))
    
    async def on_llm_new_token(
        self,
        token: str,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> None:
        """Called for each new token (enables typing animation)."""
        # Only emit for substantial tokens to avoid flooding
        if token.strip():
            await self._emit(ThinkingEvent(
                event_type="thinking_token",
                content=token,
                metadata={"run_id": str(run_id)},
            ))
    
    async def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> None:
        """Called when LLM finishes generating."""
        await self._emit(ThinkingEvent(
            event_type="thinking_end",
            content=f"{self.agent_name} finished reasoning",
            metadata={"run_id": str(run_id)},
        ))
    
    async def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> None:
        """Called on LLM error."""
        await self._emit(ThinkingEvent(
            event_type="error",
            content=f"Error during reasoning: {str(error)}",
            metadata={"run_id": str(run_id), "error_type": type(error).__name__},
        ))
    
    # ==========================================
    # Tool Events
    # ==========================================
    
    async def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        inputs: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Called when a tool is about to be executed."""
        tool_name = serialized.get("name", "Unknown Tool")
        self.run_ids[str(run_id)] = tool_name
        self.current_tool = tool_name
        
        # Create a human-readable description
        tool_description = _get_tool_description(tool_name, inputs or {})
        
        await self._emit(ThinkingEvent(
            event_type="tool_start",
            content=tool_description,
            metadata={
                "run_id": str(run_id),
                "tool_name": tool_name,
                "inputs": _sanitize_inputs(inputs or {}),
            },
        ))
    
    async def on_tool_end(
        self,
        output: Any,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> None:
        """Called when a tool finishes execution."""
        tool_name = self.run_ids.get(str(run_id), "Unknown Tool")
        
        # Parse output for summary
        output_summary = _summarize_tool_output(output)
        
        # Get full output as JSON string for frontend parsing
        full_output = None
        try:
            if output is not None:
                if isinstance(output, str):
                    full_output = output
                elif hasattr(output, 'content'):
                    # Handle LangChain ToolMessage objects
                    full_output = output.content if isinstance(output.content, str) else json.dumps(output.content)
                else:
                    full_output = json.dumps(output) if not isinstance(output, str) else output
        except Exception as e:
            logger.debug(f"Could not serialize tool output: {e}")
        
        await self._emit(ThinkingEvent(
            event_type="tool_end",
            content=f"Completed: {tool_name}",
            metadata={
                "run_id": str(run_id),
                "tool_name": tool_name,
                "output_summary": output_summary,
                "output": full_output,  # Full output for frontend parsing
            },
        ))
        
        self.current_tool = None
    
    async def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> None:
        """Called on tool error."""
        tool_name = self.run_ids.get(str(run_id), "Unknown Tool")
        
        await self._emit(ThinkingEvent(
            event_type="tool_error",
            content=f"Error in {tool_name}: {str(error)}",
            metadata={
                "run_id": str(run_id),
                "tool_name": tool_name,
                "error_type": type(error).__name__,
            },
        ))
    
    # ==========================================
    # Chain Events (for workflow tracking)
    # ==========================================
    
    async def on_chain_start(
        self,
        serialized: Dict[str, Any],
        inputs: Dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Called when a chain starts."""
        # Handle case where serialized might be None or missing keys
        if not serialized:
            return
        
        chain_id = serialized.get("id")
        if isinstance(chain_id, list) and chain_id:
            chain_name = serialized.get("name", chain_id[-1])
        else:
            chain_name = serialized.get("name", "Unknown")
        
        # Only emit for significant chains (not internal ones)
        if chain_name in ["RunnableSequence", "RunnableParallel", "Unknown"]:
            return
            
        await self._emit(ThinkingEvent(
            event_type="step_start",
            content=f"Starting: {chain_name}",
            metadata={"run_id": str(run_id), "chain": chain_name},
        ))
    
    async def on_chain_end(
        self,
        outputs: Dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> None:
        """Called when a chain ends."""
        pass  # Usually not needed for UI
    
    # ==========================================
    # Agent Events
    # ==========================================
    
    async def on_agent_action(
        self,
        action: AgentAction,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> None:
        """Called when agent decides on an action."""
        await self._emit(ThinkingEvent(
            event_type="agent_action",
            content=f"Deciding to use: {action.tool}",
            metadata={
                "run_id": str(run_id),
                "tool": action.tool,
                "log": action.log[:200] if action.log else "",
            },
        ))
    
    async def on_agent_finish(
        self,
        finish: AgentFinish,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> None:
        """Called when agent finishes."""
        await self._emit(ThinkingEvent(
            event_type="agent_finish",
            content="Analysis complete",
            metadata={"run_id": str(run_id)},
        ))


# ==========================================
# Helper Functions
# ==========================================

def _get_tool_description(tool_name: str, inputs: Dict[str, Any]) -> str:
    """Generate a human-readable description of what the tool is doing."""
    timelimit_map = {"d": "last 24 hours", "w": "last week", "m": "last month"}
    descriptions = {
        "web_search_ddg": lambda i: f"Searching the web for: {i.get('query', 'information')}",
        "news_search": lambda i: f"Searching news ({timelimit_map.get(i.get('timelimit', 'w'), 'recent')}) for: {i.get('query', 'news')}",
        "get_general_news": lambda i: f"Fetching general news...",
        "get_stock_news": lambda i: f"Getting stock news for: {i.get('symbols', 'tracked companies')}",
        "get_press_releases": lambda i: f"Retrieving press releases...",
        "search_press_releases": lambda i: f"Searching press releases for: {i.get('symbols', 'companies')}",
        "get_earnings_transcript_latest": lambda i: f"Getting latest earnings transcript for: {i.get('symbol', 'company')}",
        "get_earnings_transcript": lambda i: f"Fetching earnings transcript for {i.get('symbol', 'company')} ({i.get('year', '')}/{i.get('quarter', '')})",
        "get_commodities_list": lambda i: f"Getting commodities prices...",
        "search_x_posts": lambda i: f"Searching X/Twitter for: {i.get('query', 'posts')}",
        "get_x_user_posts": lambda i: f"Getting posts from X user: @{i.get('username', 'user')}",
        "create_chart": lambda i: f"Creating {i.get('chart_type', 'visualization')} chart...",
        "get_companies_list": lambda i: f"Retrieving tracked companies list...",
        "get_materials_list": lambda i: f"Retrieving tracked materials list...",
        "get_preferences": lambda i: f"Loading user preferences...",
        "update_preferences": lambda i: f"Updating preferences: {i.get('list_name', 'settings')}",
        "add_company_to_tracker": lambda i: f"Adding company: {i.get('company_name', 'new company')}",
        "add_material_to_tracker": lambda i: f"Adding material: {i.get('material_name', 'new material')}",
        "add_multiple_items": lambda i: f"Adding multiple {i.get('item_type', 'items')}...",
        "remove_company_from_tracker": lambda i: f"Removing company: {i.get('company_name', 'company')}",
        "remove_material_from_tracker": lambda i: f"Removing material: {i.get('material_name', 'material')}",
        "crawl_for_documents": lambda i: f"Crawling for documents at: {i.get('url', 'website')}",
        "extract_document_content": lambda i: f"Extracting content from document...",
    }
    
    if tool_name in descriptions:
        try:
            return descriptions[tool_name](inputs)
        except Exception:
            pass
    
    return f"Using tool: {tool_name}"


def _sanitize_inputs(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize inputs for logging (remove sensitive data, truncate long values)."""
    sanitized = {}
    for key, value in inputs.items():
        if key in ["api_key", "token", "password", "secret"]:
            sanitized[key] = "***"
        elif isinstance(value, str) and len(value) > 200:
            sanitized[key] = value[:200] + "..."
        else:
            sanitized[key] = value
    return sanitized


def _summarize_tool_output(output: Any) -> str:
    """Create a brief summary of tool output."""
    if output is None:
        return "No results"
    
    try:
        if isinstance(output, str):
            # Try to parse as JSON
            try:
                data = json.loads(output)
                if isinstance(data, dict):
                    if "total_count" in data:
                        return f"Found {data['total_count']} results"
                    if "success" in data:
                        return "Success" if data["success"] else "Failed"
                    if "error" in data:
                        return f"Error: {data['error'][:100]}"
                return f"Received {len(data) if isinstance(data, (list, dict)) else 'data'}"
            except json.JSONDecodeError:
                return f"Received {len(output)} characters"
        
        if isinstance(output, list):
            return f"Found {len(output)} items"
        
        if isinstance(output, dict):
            return f"Received data with {len(output)} fields"
        
        return str(output)[:100]
        
    except Exception:
        return "Received results"
