"""
Progress tracking for Deep Research agents.

This module provides a callback mechanism for agents to emit granular progress
updates during tool execution. These updates are captured by the streaming API
and sent to the client in real-time.
"""
from typing import Optional, Callable, Any
from dataclasses import dataclass, field
from contextvars import ContextVar
import asyncio

# Context variable to hold the current progress callback
_progress_callback: ContextVar[Optional[Callable]] = ContextVar("progress_callback", default=None)


@dataclass
class ToolProgress:
    """Progress update for a tool execution."""
    tool_name: str
    message: str
    ticker: Optional[str] = None
    query: Optional[str] = None
    status: str = "running"  # "running", "complete", "error"
    result_count: Optional[int] = None
    

def set_progress_callback(callback: Optional[Callable[[ToolProgress], Any]]) -> None:
    """
    Set the progress callback for the current context.
    
    The callback will be invoked with ToolProgress objects as agents
    execute tools.
    """
    _progress_callback.set(callback)


def get_progress_callback() -> Optional[Callable[[ToolProgress], Any]]:
    """Get the current progress callback."""
    return _progress_callback.get()


async def emit_progress(progress: ToolProgress) -> None:
    """
    Emit a progress update to the registered callback.
    
    Safe to call even if no callback is registered.
    """
    callback = _progress_callback.get()
    if callback:
        if asyncio.iscoroutinefunction(callback):
            await callback(progress)
        else:
            callback(progress)


def emit_progress_sync(progress: ToolProgress) -> None:
    """
    Emit a progress update synchronously.
    
    For use in non-async contexts. If the callback is async,
    this will schedule it but not wait for completion.
    """
    callback = _progress_callback.get()
    if callback:
        if asyncio.iscoroutinefunction(callback):
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(callback(progress))
                else:
                    loop.run_until_complete(callback(progress))
            except RuntimeError:
                pass  # No event loop, skip
        else:
            callback(progress)


# Human-readable tool descriptions
TOOL_DESCRIPTIONS = {
    # Groomer agent tools
    "prior_research": "Checking for related prior research",
    "query_analysis": "Analyzing query and generating research plan",
    
    # Financial agent tools
    "sec_filings": "Fetching SEC filings",
    "sec_10k": "Fetching 10-K annual report",
    "sec_10q": "Fetching 10-Q quarterly report", 
    "sec_8k": "Fetching 8-K current report",
    "earnings_call": "Retrieving earnings transcript",
    "corpus_earnings": "Searching internal earnings data",
    "analyst_ratings": "Getting analyst ratings",
    "sentiment_summary": "Analyzing news sentiment",
    "press_releases": "Fetching press releases",
    "company_news": "Fetching company news",
    
    # Industry agent tools
    "corpus": "Searching internal intelligence",
    "exa_trade_pubs": "Searching trade publications",
    "exa_news": "Searching recent news",
    "exa_web": "Searching web sources",
    "market_signals": "Analyzing market signals",
    "stocknews_keyword": "Searching news by keyword",
    "stocknews_company": "Fetching company news",
    "stocknews_press_releases": "Fetching press releases",
    "stocknews_trending": "Getting trending headlines",
    "google_trends": "Checking Google Trends",
    "freight_rates": "Fetching freight rate data",
    
    # Category agent tools
    "datasheets": "Querying product datasheets",
    "datasheet_detail": "Fetching datasheet details",
    "products_by_industry": "Finding products by industry",
}


def get_tool_description(tool_name: str, ticker: Optional[str] = None, query: Optional[str] = None) -> str:
    """Get a human-readable description for a tool execution."""
    base = TOOL_DESCRIPTIONS.get(tool_name, f"Running {tool_name}")
    
    if ticker:
        return f"{base} for {ticker}"
    elif query and len(query) < 50:
        return f"{base}: {query}"
    
    return base
