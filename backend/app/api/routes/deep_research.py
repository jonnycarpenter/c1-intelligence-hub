from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from app.graph.research_workflow import research_workflow
from app.agents.research.state import DeepResearchState, QueryStatus
from app.agents.research.progress import set_progress_callback, ToolProgress
from app.agents.research.memory import get_research_memory, ResearchMemory
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from app.utils.retry import tool_metrics
import json
import asyncio
import logging
import hashlib
import uuid
from datetime import datetime, timedelta
from queue import Queue
from threading import Thread

logger = logging.getLogger(__name__)
router = APIRouter()


# =============================================================================
# Report Caching
# =============================================================================

class ReportCache:
    """
    In-memory cache for deep research reports.
    
    Caches reports by query hash to avoid re-running expensive workflows
    for identical or very similar queries.
    
    Cache TTL: 1 hour by default (reports can be expensive to generate)
    """
    
    def __init__(self, ttl_minutes: int = 60):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._ttl = timedelta(minutes=ttl_minutes)
    
    @staticmethod
    def compute_hash(query: str) -> str:
        """
        Compute a hash for the query.
        
        Normalizes the query (lowercase, strip whitespace) before hashing
        to improve cache hit rate for similar queries.
        """
        normalized = query.lower().strip()
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]
    
    def get(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Get a cached report if it exists and is not expired.
        
        Returns:
            Cached state dict or None if not found/expired
        """
        query_hash = self.compute_hash(query)
        if query_hash not in self._cache:
            return None
        
        entry = self._cache[query_hash]
        if datetime.now() - entry["cached_at"] > self._ttl:
            # Expired - remove and return None
            del self._cache[query_hash]
            logger.info(f"Cache expired for query hash: {query_hash}")
            return None
        
        logger.info(f"Cache HIT for query hash: {query_hash}")
        return entry["state"]
    
    def set(self, query: str, state: Dict[str, Any]) -> str:
        """
        Cache a completed report state.
        
        Returns:
            The query hash used as cache key
        """
        query_hash = self.compute_hash(query)
        self._cache[query_hash] = {
            "state": state,
            "cached_at": datetime.now(),
            "query": query,
        }
        logger.info(f"Cached report for query hash: {query_hash}")
        return query_hash
    
    def clear_expired(self) -> int:
        """Clear expired entries. Returns count of entries removed."""
        now = datetime.now()
        expired = [
            k for k, v in self._cache.items() 
            if now - v["cached_at"] > self._ttl
        ]
        for k in expired:
            del self._cache[k]
        return len(expired)


# Global cache instance
_report_cache = ReportCache(ttl_minutes=60)


# Human-readable descriptions for each node
NODE_DESCRIPTIONS = {
    "groom": "Analyzing your query...",
    "financial_research": "Researching financial data",
    "industry_research": "Researching industry intelligence", 
    "synthesize": "Synthesizing findings into report",
    "categorize": "Generating sales intelligence",
    "validate": "Verifying citations and sources",
}


class DeepResearchRequest(BaseModel):
    query: str
    history: List[Dict[str, Any]] = []


def _emit_event(event_type: str, content: Any) -> str:
    """Format an SSE event."""
    return f"data: {json.dumps({'type': event_type, 'content': content})}\n\n"


class ProgressCollector:
    """
    Collects progress events from agents via callback and makes them
    available to the streaming generator via an async queue.
    """
    def __init__(self):
        self.queue: asyncio.Queue = None
        self._loop: asyncio.AbstractEventLoop = None
    
    def setup(self, loop: asyncio.AbstractEventLoop):
        """Initialize with the event loop that will consume events."""
        self._loop = loop
        self.queue = asyncio.Queue()
    
    def on_progress(self, progress: ToolProgress):
        """
        Callback invoked by agents (may be from sync context).
        Safely puts event on async queue.
        """
        if self.queue and self._loop:
            # Thread-safe way to put on async queue from sync context
            self._loop.call_soon_threadsafe(
                self.queue.put_nowait,
                {
                    "type": "tool_progress",
                    "tool": progress.tool_name,
                    "message": progress.message,
                    "ticker": progress.ticker,
                    "status": progress.status,
                }
            )
    
    async def get_pending_events(self) -> List[Dict]:
        """Get all pending progress events without blocking."""
        events = []
        while not self.queue.empty():
            try:
                events.append(self.queue.get_nowait())
            except asyncio.QueueEmpty:
                break
        return events


@router.post("/run")
async def run_deep_research(request: DeepResearchRequest):
    """
    Trigger the deep research workflow with real-time streaming updates.
    
    Features:
    - Two-tier caching: in-memory (1 hour) + BigQuery (24 hours)
    - Parallel Financial + Industry agent execution
    - Real-time streaming with granular tool progress
    - BigQuery persistence for report history
    
    Streams SSE events:
    - type: "status" - High-level workflow progress
    - type: "cache_hit" - Report served from cache (includes query_hash, source)
    - type: "node_start" - Node beginning execution (includes parallel indicator)
    - type: "node_complete" - Node finished
    - type: "tool_progress" - Granular tool execution progress  
    - type: "clarification" - Query needs clarification
    - type: "report" - Final report payload
    - type: "category" - Sales intelligence output (Phase 2)
    - type: "validation" - Citation validation results (Phase 2)
    - type: "related_research" - Prior related reports found (memory integration)
    - type: "error" - Error details
    """
    # Tier 1: Check in-memory cache first (fastest)
    cached_state = _report_cache.get(request.query)
    if cached_state:
        # Return cached report via streaming (for UI consistency)
        async def cached_generator():
            yield _emit_event("status", "Loading cached report...")
            yield _emit_event("cache_hit", {
                "query_hash": ReportCache.compute_hash(request.query),
                "source": "memory",
                "message": "Report loaded from in-memory cache"
            })
            
            # Re-emit the cached results
            if cached_state.get("final_report"):
                yield _emit_event("report", cached_state["final_report"].model_dump())
            if cached_state.get("category_output"):
                yield _emit_event("category", cached_state["category_output"].model_dump())
            if cached_state.get("validator_output"):
                yield _emit_event("validation", cached_state["validator_output"].model_dump())
            if cached_state.get("errors"):
                yield _emit_event("warnings", cached_state["errors"])
            
            yield _emit_event("status", "Research complete (cached).")
            yield "data: [DONE]\n\n"
        
        return StreamingResponse(
            cached_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            }
        )
    
    # Tier 2: Check BigQuery persistent cache (24h TTL)
    memory = await get_research_memory()
    bq_cached = await memory.get_cached_report(request.query)
    if bq_cached:
        async def bq_cached_generator():
            yield _emit_event("status", "Loading saved report...")
            yield _emit_event("cache_hit", {
                "query_hash": bq_cached.get("query_hash"),
                "report_id": bq_cached.get("id"),
                "source": "bigquery",
                "message": "Report loaded from saved reports"
            })
            
            # Re-emit from stored JSON
            if bq_cached.get("final_report"):
                yield _emit_event("report", bq_cached["final_report"])
            if bq_cached.get("category_output"):
                yield _emit_event("category", bq_cached["category_output"])
            if bq_cached.get("validator_output"):
                yield _emit_event("validation", bq_cached["validator_output"])
            
            yield _emit_event("status", "Research complete (saved report).")
            yield "data: [DONE]\n\n"
        
        return StreamingResponse(
            bq_cached_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            }
        )
    
    # Not cached - run the full workflow
    initial_state: DeepResearchState = {
        "user_query": request.query,
        "conversation_history": [
            HumanMessage(content=m["content"]) if m["role"] == "user" else HumanMessage(content=m["content"])
            for m in request.history
        ],
        "research_brief": None,
        "clarification_count": 0,
        "financial_output": None,
        "industry_output": None,
        "final_report": None,
        "category_output": None,
        "validator_output": None,
        "current_status": "starting",
        "errors": [],
    }

    async def event_generator():
        """
        Stream workflow events in real-time.
        
        Uses two mechanisms:
        1. LangGraph astream_events for node lifecycle events
        2. ProgressCollector callback for granular tool progress
        """
        # Set up progress collector
        loop = asyncio.get_event_loop()
        progress_collector = ProgressCollector()
        progress_collector.setup(loop)
        
        # Register the progress callback so agents can emit tool progress
        set_progress_callback(progress_collector.on_progress)
        
        try:
            yield _emit_event("status", "Starting deep research workflow...")
            
            # Track which nodes are running (for parallel execution awareness)
            active_nodes = set()
            completed_nodes = set()
            final_state = None
            last_progress_check = 0
            
            # Generate unique run ID and query hash for tracing
            run_id = str(uuid.uuid4())
            query_hash = ReportCache.compute_hash(request.query)
            query_preview = request.query[:50] + "..." if len(request.query) > 50 else request.query
            
            # Configure LangSmith tracing with metadata for searchability
            # See: https://docs.smith.langchain.com/old/cookbook/tracing-examples/runnable-naming
            # Note: recursion_limit increased for parallel Send pattern (each parallel branch counts)
            langsmith_config = RunnableConfig(
                run_name=f"DeepResearch: {query_preview}",
                tags=["deep_research", "production"],
                recursion_limit=100,  # Increased from default 25 for parallel execution
                metadata={
                    "run_id": run_id,
                    "query_hash": query_hash,
                    "query": request.query,
                    "query_length": len(request.query),
                    "history_length": len(request.history),
                    "timestamp": datetime.now().isoformat(),
                },
            )
            
            logger.info(f"Starting DeepResearch run_id={run_id} query_hash={query_hash}")
            
            # Stream events from workflow execution
            async for event in research_workflow.astream_events(
                initial_state,
                config=langsmith_config,
                version="v2",  # Use v2 event schema
            ):
                # Check for any pending tool progress events
                progress_events = await progress_collector.get_pending_events()
                for progress in progress_events:
                    yield _emit_event("tool_progress", {
                        "tool": progress["tool"],
                        "message": progress["message"],
                        "ticker": progress.get("ticker"),
                    })
                
                event_type = event.get("event")
                event_name = event.get("name", "")
                event_data = event.get("data", {})
                
                # Node lifecycle events
                if event_type == "on_chain_start" and event_name in NODE_DESCRIPTIONS:
                    node_name = event_name
                    active_nodes.add(node_name)
                    
                    # Check if this is running in parallel with another node
                    parallel_with = None
                    if node_name == "financial_research" and "industry_research" in active_nodes:
                        parallel_with = "industry_research"
                    elif node_name == "industry_research" and "financial_research" in active_nodes:
                        parallel_with = "financial_research"
                    
                    yield _emit_event("node_start", {
                        "node": node_name,
                        "description": NODE_DESCRIPTIONS[node_name],
                        "parallel_with": parallel_with,
                    })
                
                elif event_type == "on_chain_end" and event_name in NODE_DESCRIPTIONS:
                    node_name = event_name
                    active_nodes.discard(node_name)
                    completed_nodes.add(node_name)
                    
                    # Extract output for specific nodes
                    output = event_data.get("output", {})
                    
                    # Check for clarification needed (from groom node)
                    if node_name == "groom" and output:
                        brief = output.get("research_brief")
                        if brief and hasattr(brief, "status"):
                            if brief.status == QueryStatus.NEEDS_CLARIFICATION:
                                yield _emit_event("clarification", {
                                    "question": brief.clarifying_question.model_dump() if brief.clarifying_question else None,
                                })
                                return  # Stop workflow - waiting for user input
                            else:
                                # Brief is ready - show sub-queries
                                yield _emit_event("status", {
                                    "message": "Query understood. Starting parallel research...",
                                    "financial_queries": brief.financial_agent_queries or [],
                                    "industry_queries": brief.industry_agent_queries or [],
                                    "entities": brief.entities_to_track or [],
                                })
                    
                    yield _emit_event("node_complete", {
                        "node": node_name,
                        "duration_hint": "complete",
                    })
                    
                    # Capture final state from last node
                    if output:
                        final_state = output
            
            # Drain any remaining progress events
            progress_events = await progress_collector.get_pending_events()
            for progress in progress_events:
                yield _emit_event("tool_progress", {
                    "tool": progress["tool"],
                    "message": progress["message"],
                    "ticker": progress.get("ticker"),
                })
            
            # Emit final outputs
            if final_state:
                # Final report
                if final_state.get("final_report"):
                    yield _emit_event("report", final_state["final_report"].model_dump())
                
                # Category/sales intelligence (Phase 2)
                if final_state.get("category_output"):
                    yield _emit_event("category", final_state["category_output"].model_dump())
                
                # Validation results (Phase 2)
                if final_state.get("validator_output"):
                    yield _emit_event("validation", final_state["validator_output"].model_dump())
                
                # Any errors accumulated
                if final_state.get("errors"):
                    yield _emit_event("warnings", final_state["errors"])
                
                # Cache the successful result for future queries
                if final_state.get("final_report"):
                    # Tier 1: In-memory cache (fast, 1 hour TTL)
                    query_hash = _report_cache.set(request.query, final_state)
                    logger.info(f"Cached research report (memory): hash={query_hash}, query='{request.query[:50]}...'")
                    
                    # Tier 2: BigQuery persistence (durable, 24 hour TTL)
                    try:
                        report_id = str(uuid.uuid4())
                        await memory.store_report(
                            report_id=report_id,
                            query=request.query,
                            state=final_state,
                        )
                        logger.info(f"Persisted research report (BigQuery): id={report_id}")
                        yield _emit_event("report_saved", {
                            "report_id": report_id,
                            "query_hash": query_hash,
                        })
                    except Exception as persist_error:
                        logger.warning(f"Failed to persist report to BigQuery: {persist_error}")
                        # Non-fatal - in-memory cache still works
            
            yield _emit_event("status", "Research complete.")
            yield "data: [DONE]\n\n"
            
        except Exception as e:
            logger.exception("Deep research workflow error")
            yield _emit_event("error", {"message": str(e), "type": type(e).__name__})
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(), 
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )


@router.get("/cache/stats")
async def get_cache_stats():
    """Get cache statistics for debugging and monitoring."""
    # Clear expired entries first
    expired_count = _report_cache.clear_expired()
    
    cache_entries = []
    for hash_key, entry in _report_cache._cache.items():
        cache_entries.append({
            "query_hash": hash_key,
            "query_preview": entry["query"][:100] + "..." if len(entry["query"]) > 100 else entry["query"],
            "cached_at": entry["cached_at"].isoformat(),
            "has_report": entry["state"].get("final_report") is not None,
            "has_category": entry["state"].get("category_output") is not None,
        })
    
    return {
        "total_cached": len(cache_entries),
        "expired_cleared": expired_count,
        "ttl_minutes": _report_cache._ttl.total_seconds() / 60,
        "entries": cache_entries,
    }


@router.delete("/cache/clear")
async def clear_cache():
    """Clear all cached reports."""
    count = len(_report_cache._cache)
    _report_cache._cache.clear()
    logger.info(f"Cleared {count} cached reports")
    return {"cleared": count, "message": f"Cleared {count} cached reports"}


@router.get("/observability/status")
async def get_observability_status():
    """
    Check LangSmith observability configuration status.
    
    Returns current tracing configuration for debugging.
    """
    import os
    from app.config.settings import settings
    
    langsmith_enabled = bool(settings.langchain_api_key and os.environ.get("LANGCHAIN_API_KEY"))
    
    return {
        "langsmith_enabled": langsmith_enabled,
        "project": settings.langchain_project if langsmith_enabled else None,
        "tracing_v2": settings.langchain_tracing_v2,
        "dashboard_url": f"https://smith.langchain.com/o/default/projects/p/{settings.langchain_project}" if langsmith_enabled else None,
        "notes": [
            "Traces are sent automatically when workflow runs",
            "Each run includes metadata: run_id, query_hash, timestamp",
            "Filter by tag: 'deep_research' in LangSmith dashboard",
        ] if langsmith_enabled else ["LangSmith not configured - add LANGCHAIN_API_KEY to .env"],
    }


@router.get("/tools/health")
async def get_tool_health():
    """
    Get tool performance metrics and health status.
    
    Returns success/failure rates, average latency, and recent errors
    for all instrumented tools (StockNewsAPI, Google Trends, etc.)
    """
    stats = tool_metrics.get_stats()
    
    # Calculate overall health score
    if not stats:
        return {
            "status": "no_data",
            "message": "No tool executions recorded yet",
            "tools": {},
        }
    
    # Aggregate health info
    healthy_tools = []
    degraded_tools = []
    failing_tools = []
    
    for tool_name, tool_stats in stats.items():
        success_rate = tool_stats.get("success_rate", 0)
        
        if success_rate >= 95:
            healthy_tools.append(tool_name)
        elif success_rate >= 70:
            degraded_tools.append(tool_name)
        else:
            failing_tools.append(tool_name)
    
    # Determine overall status
    if failing_tools:
        overall_status = "degraded"
    elif degraded_tools:
        overall_status = "partial"
    else:
        overall_status = "healthy"
    
    return {
        "status": overall_status,
        "summary": {
            "healthy": len(healthy_tools),
            "degraded": len(degraded_tools),
            "failing": len(failing_tools),
        },
        "healthy_tools": healthy_tools,
        "degraded_tools": degraded_tools,
        "failing_tools": failing_tools,
        "tools": stats,
        "notes": [
            "Healthy: ≥95% success rate",
            "Degraded: 70-94% success rate",
            "Failing: <70% success rate",
            "Metrics reset on server restart",
        ],
    }

# =============================================================================
# Saved Reports Endpoints (Phase 4)
# =============================================================================

@router.get("/reports")
async def list_saved_reports(
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    limit: int = Query(20, ge=1, le=100, description="Max reports to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
):
    """
    List saved deep research reports.
    
    Returns report summaries (not full content) for browsing.
    Use GET /reports/{report_id} to fetch full report.
    """
    memory = await get_research_memory()
    reports = await memory.get_recent_reports(
        user_id=user_id,
        limit=limit,
        offset=offset,
    )
    
    return {
        "total": len(reports),  # Note: This is the returned count, not total in DB
        "limit": limit,
        "offset": offset,
        "reports": reports,
    }


@router.get("/reports/{report_id}")
async def get_saved_report(report_id: str):
    """
    Get a specific saved research report by ID.
    
    Returns full report including all outputs (financial, industry,
    synthesis, category, validation).
    """
    memory = await get_research_memory()
    report = await memory.get_report_by_id(report_id)
    
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    return report


@router.get("/reports/search/related")
async def search_related_reports(
    query: str = Query(..., description="Query to find related reports for"),
    companies: Optional[str] = Query(None, description="Comma-separated company names"),
    industries: Optional[str] = Query(None, description="Comma-separated industries"),
    limit: int = Query(5, ge=1, le=20, description="Max related reports to return"),
):
    """
    Find related past research reports.
    
    Useful for:
    - Checking if similar research already exists
    - Finding context for new research
    - Avoiding redundant work
    
    Searches by:
    - Query text similarity
    - Company overlap
    - Industry overlap
    """
    memory = await get_research_memory()
    
    company_list = [c.strip() for c in companies.split(",")] if companies else None
    industry_list = [i.strip() for i in industries.split(",")] if industries else None
    
    related = await memory.find_related_research(
        query=query,
        companies=company_list,
        industries=industry_list,
    )
    
    # Limit results
    related = related[:limit]
    
    return {
        "query": query,
        "filters": {
            "companies": company_list,
            "industries": industry_list,
        },
        "count": len(related),
        "related_reports": related,
    }