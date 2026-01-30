"""
Discovery Chat API - Streaming AI assistant with tool access.

Provides a real-time streaming chat interface for the Discovery tab.
The assistant has access to:
- corpus_search: Search internal article database (30-day window)
- exa_search: Live web search for real-time news
- podcast_insights: Find relevant podcast quotes (future)

SSE Event Types:
- chunk: Partial text response
- tool_call: Tool being invoked (for UI indicator)
- tool_result: Tool execution complete (optional, for debugging)
- complete: Final response with sources_used list
- error: Error message
"""

import json
import time
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, AsyncGenerator
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from anthropic import AsyncAnthropic

from app.config.settings import settings
from app.db.vector_store import get_production_vector_store
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


# =============================================================================
# Request/Response Models
# =============================================================================

class ChatMessage(BaseModel):
    role: str  # 'user' or 'assistant'
    content: str


class DiscoveryChatRequest(BaseModel):
    query: str
    history: List[ChatMessage] = []


class DiscoveryTheme(BaseModel):
    """A significant trend or topic identified within a category."""
    title: str  # e.g., "M&A Surge" or "Pricing Pressures"
    content: str  # 1-2 sentence AI summary


class DiscoverySummaryResponse(BaseModel):
    """Thematic summary for inline AI summary drawer."""
    category: str
    period_label: str = "Past 30 days"
    themes: List[DiscoveryTheme]
    one_off_summary: str  # e.g., "8 one-off stories about product launches and pricing"
    article_count: int
    generated_at: str


# =============================================================================
# System Prompt
# =============================================================================

DISCOVERY_SYSTEM_PROMPT = """You are the Discovery Assistant for C1 Intelligence Hub, a composites industry intelligence platform.

You help users explore recent market intelligence from the past 30 days. Your role is to surface insights from the article corpus and supplement with live web search when needed.

## Tool Usage Strategy
1. **ALWAYS start with corpus_search** - Our internal database has pre-classified, relevant articles
2. **Use exa_search sparingly** - Only when corpus has insufficient results or user explicitly asks for "latest" or "live" news
3. **Combine insights** - Synthesize findings from multiple sources when available

## Response Guidelines
- Be CONCISE - Discovery is for quick exploration, not deep analysis
- Use **bold** for key insights and company names
- Include [Source Title](url) citations inline
- If a topic requires deeper analysis, suggest the "Deep Research" feature
- For queries about events older than 30 days, redirect to Deep Research

## Data Window
- corpus_search: Last 30 days of pre-ingested articles
- exa_search: Live web results (any time range)

## Categories Available (for corpus filtering)
- competitor: Competitor activity, strategy, announcements
- market: Market trends, dynamics, forecasts
- regulatory: Regulatory changes, compliance
- product: Product launches, innovations
- earnings: Financial results, guidance
- partnership: Partnerships, joint ventures
- supply_chain: Supply chain updates, disruptions

## Format
Keep responses to 2-4 paragraphs maximum. Use bullet points for multiple findings.
Always cite sources with clickable links."""


# =============================================================================
# Tool Definitions (Anthropic format)
# =============================================================================

DISCOVERY_TOOLS = [
    {
        "name": "corpus_search",
        "description": "Search the internal article database for recent intelligence (last 30 days). Use this FIRST for any question about competitors, market trends, or industry news. Returns pre-classified, relevant articles.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query - be specific with company names, materials, or topics"
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of results (default 5, max 10)",
                    "default": 5
                },
                "category": {
                    "type": "string",
                    "description": "Optional category filter",
                    "enum": ["competitor", "market", "regulatory", "product", "earnings", "partnership", "supply_chain"]
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "exa_search",
        "description": "Search live web for real-time news. Use when corpus results are insufficient or user asks for 'latest' news. Returns results with reliable published dates.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query - include company names and specific topics"
                },
                "days_back": {
                    "type": "integer",
                    "description": "How many days back to search (default 7, max 30)",
                    "default": 7
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of results (default 5, max 10)",
                    "default": 5
                }
            },
            "required": ["query"]
        }
    }
]


# =============================================================================
# Tool Execution
# =============================================================================

async def execute_corpus_search(
    query: str, 
    limit: int = 5, 
    category: Optional[str] = None
) -> Dict[str, Any]:
    """Execute corpus search against BigQuery vector store."""
    start = time.time()
    logger.info(f"[DISCOVERY] Corpus search START: query='{query[:60]}...', limit={limit}, category={category}")
    
    try:
        vector_store = await get_production_vector_store()
        
        if not vector_store.is_available:
            logger.warning("[DISCOVERY] Vector store not available")
            return {
                "status": "error",
                "message": "Article database temporarily unavailable",
                "results": []
            }
        
        # Build search parameters
        search_kwargs = {
            "query": query,
            "limit": min(limit, 10),
        }
        
        if category:
            search_kwargs["where"] = {"category": category}
        
        results = await vector_store.search(**search_kwargs)
        
        # Format results
        formatted = []
        for r in results:
            metadata = r.get("metadata", {})
            formatted.append({
                "title": metadata.get("title", "Untitled"),
                "url": metadata.get("url", ""),
                "source": metadata.get("source_name", "Unknown"),
                "published_date": metadata.get("published_at", ""),
                "category": metadata.get("category", "general"),
                "summary": (r.get("document", "") or "")[:400],
                "relevance_score": r.get("relevance_score", 0),
            })
        
        elapsed = time.time() - start
        logger.info(f"[DISCOVERY] Corpus search COMPLETE: {elapsed:.2f}s, {len(formatted)} results")
        
        return {
            "status": "success",
            "count": len(formatted),
            "results": formatted
        }
        
    except Exception as e:
        elapsed = time.time() - start
        logger.error(f"[DISCOVERY] Corpus search FAILED: {elapsed:.2f}s, error={str(e)}")
        return {
            "status": "error",
            "message": str(e),
            "results": []
        }


async def execute_exa_search(
    query: str,
    days_back: int = 7,
    limit: int = 5
) -> Dict[str, Any]:
    """Execute Exa web search for live news."""
    start = time.time()
    logger.info(f"[DISCOVERY] Exa search START: query='{query[:60]}...', days_back={days_back}")
    
    try:
        from app.mcp.tools.exa_search import news_search
        
        # Use the existing news_search tool
        result_str = news_search.invoke({
            "query": query,
            "max_results": min(limit, 10),
            "time_range": "week" if days_back <= 7 else "month"
        })
        
        if not result_str:
            return {"status": "error", "message": "No results", "results": []}
        
        data = json.loads(result_str)
        results = data.get("results", [])
        
        # Format results consistently
        formatted = []
        for r in results[:limit]:
            formatted.append({
                "title": r.get("title", "Untitled"),
                "url": r.get("url", ""),
                "source": "Web",
                "published_date": r.get("published_date", ""),
                "summary": (r.get("snippet", "") or r.get("content", ""))[:400],
            })
        
        elapsed = time.time() - start
        logger.info(f"[DISCOVERY] Exa search COMPLETE: {elapsed:.2f}s, {len(formatted)} results")
        
        return {
            "status": "success",
            "count": len(formatted),
            "results": formatted
        }
        
    except Exception as e:
        elapsed = time.time() - start
        logger.error(f"[DISCOVERY] Exa search FAILED: {elapsed:.2f}s, error={str(e)}")
        return {
            "status": "error",
            "message": str(e),
            "results": []
        }


async def execute_tool(tool_name: str, tool_input: Dict[str, Any]) -> str:
    """Execute a tool and return JSON result."""
    if tool_name == "corpus_search":
        result = await execute_corpus_search(
            query=tool_input.get("query", ""),
            limit=tool_input.get("limit", 5),
            category=tool_input.get("category")
        )
    elif tool_name == "exa_search":
        result = await execute_exa_search(
            query=tool_input.get("query", ""),
            days_back=tool_input.get("days_back", 7),
            limit=tool_input.get("limit", 5)
        )
    else:
        result = {"status": "error", "message": f"Unknown tool: {tool_name}"}
    
    return json.dumps(result, default=str)


# =============================================================================
# SSE Helpers
# =============================================================================

def emit_event(event_type: str, data: Any) -> str:
    """Format an SSE event."""
    return f"data: {json.dumps({'type': event_type, **({'data': data} if not isinstance(data, dict) else data)})}\n\n"


def emit_chunk(text: str) -> str:
    """Emit a text chunk event."""
    return f"data: {json.dumps({'type': 'chunk', 'text': text})}\n\n"


def emit_tool_call(tool_name: str) -> str:
    """Emit a tool call event."""
    return f"data: {json.dumps({'type': 'tool_call', 'tool': tool_name})}\n\n"


def emit_complete(sources_used: List[str]) -> str:
    """Emit completion event."""
    return f"data: {json.dumps({'type': 'complete', 'sources_used': sources_used})}\n\n"


def emit_error(message: str) -> str:
    """Emit error event."""
    return f"data: {json.dumps({'type': 'error', 'message': message})}\n\n"


# =============================================================================
# Main Streaming Endpoint
# =============================================================================

@router.post("/chat/stream")
async def discovery_chat_stream(request: DiscoveryChatRequest):
    """
    Streaming chat endpoint for Discovery assistant.
    
    Uses Anthropic's native tool-use feature with a tool loop.
    Streams SSE events for real-time UI updates.
    """
    request_start = time.time()
    query_preview = request.query[:80] + ("..." if len(request.query) > 80 else "")
    logger.info(f"[DISCOVERY] Chat request START: query='{query_preview}', history_len={len(request.history)}")
    
    async def generate() -> AsyncGenerator[str, None]:
        """Generate SSE events."""
        try:
            # Initialize Anthropic client
            client = AsyncAnthropic(api_key=settings.anthropic_api_key)
            
            # Build message history (last 10 messages for context)
            messages = []
            for msg in request.history[-10:]:
                messages.append({
                    "role": msg.role,
                    "content": msg.content
                })
            
            # Add current query
            messages.append({
                "role": "user",
                "content": request.query
            })
            
            # Track which tools were used
            tools_used = set()
            
            # Tool loop (max 5 iterations to prevent runaway)
            MAX_ITERATIONS = 5
            for iteration in range(MAX_ITERATIONS):
                logger.info(f"[DISCOVERY] Tool loop iteration {iteration + 1}/{MAX_ITERATIONS}")
                
                try:
                    # Call Claude with tools
                    response = await asyncio.wait_for(
                        client.messages.create(
                            model="claude-3-5-haiku-20241022",  # Fast model for Discovery
                            max_tokens=1500,
                            system=DISCOVERY_SYSTEM_PROMPT,
                            tools=DISCOVERY_TOOLS,
                            messages=messages,
                        ),
                        timeout=60.0  # 60 second timeout per iteration
                    )
                except asyncio.TimeoutError:
                    logger.error(f"[DISCOVERY] LLM timeout at iteration {iteration + 1}")
                    yield emit_error("Request timed out. Please try again.")
                    return
                
                # Check for tool use
                tool_use_blocks = [
                    block for block in response.content 
                    if block.type == "tool_use"
                ]
                
                if tool_use_blocks:
                    # Process each tool call
                    tool_results = []
                    
                    for tool_block in tool_use_blocks:
                        tool_name = tool_block.name
                        tool_input = tool_block.input
                        tool_id = tool_block.id
                        
                        logger.info(f"[DISCOVERY] Tool call: {tool_name}, input={json.dumps(tool_input)[:100]}")
                        tools_used.add(tool_name)
                        
                        # Emit tool call event for UI
                        yield emit_tool_call(tool_name)
                        
                        # Execute tool
                        result = await execute_tool(tool_name, tool_input)
                        
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_id,
                            "content": result
                        })
                    
                    # Add assistant message and tool results to conversation
                    messages.append({
                        "role": "assistant",
                        "content": response.content
                    })
                    messages.append({
                        "role": "user",
                        "content": tool_results
                    })
                    
                    # Continue loop for next iteration
                    continue
                
                else:
                    # No tool calls - extract final text response
                    final_text = ""
                    for block in response.content:
                        if hasattr(block, "text"):
                            final_text += block.text
                    
                    # Stream text in chunks for typing effect
                    # Split into ~30 char chunks
                    chunk_size = 30
                    for i in range(0, len(final_text), chunk_size):
                        chunk = final_text[i:i + chunk_size]
                        yield emit_chunk(chunk)
                        await asyncio.sleep(0.02)  # Small delay for typing effect
                    
                    # Map tool names to user-friendly labels
                    source_labels = []
                    if "corpus_search" in tools_used:
                        source_labels.append("Corpus")
                    if "exa_search" in tools_used:
                        source_labels.append("Web")
                    
                    # Emit completion
                    yield emit_complete(source_labels)
                    
                    elapsed = time.time() - request_start
                    logger.info(
                        f"[DISCOVERY] Chat request COMPLETE: {elapsed:.2f}s, "
                        f"iterations={iteration + 1}, tools_used={list(tools_used)}"
                    )
                    return
            
            # If we exhaust iterations without final response
            logger.warning("[DISCOVERY] Exhausted tool loop iterations")
            yield emit_chunk("I've gathered the information. Based on my search, here's what I found...")
            yield emit_complete(list(tools_used))
            
        except Exception as e:
            elapsed = time.time() - request_start
            logger.error(
                f"[DISCOVERY] Chat request FAILED: {elapsed:.2f}s, "
                f"error_type={type(e).__name__}, error={str(e)}",
                exc_info=True
            )
            yield emit_error(f"An error occurred: {str(e)}")
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


# =============================================================================
# Non-streaming endpoint (for testing)
# =============================================================================

@router.post("/chat")
async def discovery_chat(request: DiscoveryChatRequest) -> Dict[str, Any]:
    """
    Non-streaming chat endpoint for testing.
    
    Returns the full response at once instead of streaming.
    """
    request_start = time.time()
    
    try:
        client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        
        messages = []
        for msg in request.history[-10:]:
            messages.append({"role": msg.role, "content": msg.content})
        messages.append({"role": "user", "content": request.query})
        
        tools_used = set()
        
        for iteration in range(5):
            response = await asyncio.wait_for(
                client.messages.create(
                    model="claude-3-5-haiku-20241022",
                    max_tokens=1500,
                    system=DISCOVERY_SYSTEM_PROMPT,
                    tools=DISCOVERY_TOOLS,
                    messages=messages,
                ),
                timeout=60.0
            )
            
            tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
            
            if tool_use_blocks:
                tool_results = []
                for tool_block in tool_use_blocks:
                    tools_used.add(tool_block.name)
                    result = await execute_tool(tool_block.name, tool_block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_block.id,
                        "content": result
                    })
                
                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})
                continue
            else:
                final_text = "".join(
                    block.text for block in response.content 
                    if hasattr(block, "text")
                )
                
                elapsed = time.time() - request_start
                return {
                    "message": final_text,
                    "sources_used": list(tools_used),
                    "elapsed_seconds": round(elapsed, 2)
                }
        
        return {
            "message": "Unable to complete request within iteration limit.",
            "sources_used": list(tools_used),
            "elapsed_seconds": round(time.time() - request_start, 2)
        }
        
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Request timed out")
    except Exception as e:
        logger.error(f"[DISCOVERY] Non-streaming chat error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Category Summary Endpoint (AI Summary Drawer)
# =============================================================================

@router.get("/summary/{category}", response_model=DiscoverySummaryResponse)
async def get_discovery_category_summary(category: str):
    """
    Get a thematic AI summary for a specific category (last 30 days).
    
    Returns 2 key themes and a summary of one-off stories.
    Used by the Discovery tab's category accordion "AI Summary" button.
    """
    request_start = time.time()
    logger.info(f"[DISCOVERY_SUMMARY] Endpoint START: category={category}")
    
    try:
        # Import the generator
        from app.ingestion.generators.discovery_summary import DiscoverySummaryGenerator
        
        # Get the vector store for article retrieval
        vector_store = await get_production_vector_store()
        
        if not vector_store.is_available:
            logger.warning("[DISCOVERY_SUMMARY] Vector store not available")
            raise HTTPException(status_code=503, detail="Article database temporarily unavailable")
        
        # Map frontend category names to search-friendly terms
        # Handle both Title Case (frontend) and lowercase
        category_mapping = {
            'Competitor': 'competitor',
            'Market': 'market',
            'Regulatory': 'regulatory',
            'Product': 'product',
            'Earnings': 'earnings',
            'Partnership': 'partnership',
            'Expansion': 'expansion',
            'Supply Chain': 'supply_chain',
            'Logistics': 'logistics',
            'C1 Mention': 'c1_mention',
            'General': 'general',
        }
        
        # Normalize the category for search (lowercase, underscores)
        search_category = category_mapping.get(category, category.lower().replace(' ', '_'))
        
        # Fetch articles using semantic search (skip strict where filter due to mixed casing in data)
        # The vector store has categories in mixed formats: 'Competitor', 'competitor', 'Market', 'market', etc.
        logger.info(f"[DISCOVERY_SUMMARY] Fetching articles: category={category}, normalized={search_category}")
        
        results = await vector_store.search(
            query=f"{category} industry news developments trends",
            limit=150  # Fetch more to filter from
        )
        
        # Case-insensitive category filtering (handles mixed casing in vector store)
        filtered_results = []
        for r in results:
            result_category = r.get("metadata", {}).get("category", "")
            result_cat_lower = result_category.lower().replace(' ', '_').replace('-', '_')
            
            # Check for match (lowercase comparison)
            if (result_cat_lower == search_category 
                or search_category in result_cat_lower 
                or result_cat_lower in search_category):
                filtered_results.append(r)
        
        results = filtered_results[:50]
        logger.info(f"[DISCOVERY_SUMMARY] Filtered results: {len(filtered_results)} matched out of 150 searched")
        
        # Convert to article dicts for the generator
        articles = []
        for r in results:
            metadata = r.get("metadata", {})
            articles.append({
                "title": metadata.get("title", "Untitled"),
                "summary": r.get("document", "") or metadata.get("summary", ""),
                "url": metadata.get("url", ""),
                "published_at": metadata.get("published_at", ""),
                "category": metadata.get("category", ""),
            })
        
        logger.info(f"[DISCOVERY_SUMMARY] Found {len(articles)} articles for category={category}")
        
        # Generate the thematic summary
        generator = DiscoverySummaryGenerator()
        result = await generator.generate(category, articles)
        
        elapsed = time.time() - request_start
        logger.info(f"[DISCOVERY_SUMMARY] Endpoint COMPLETE: {elapsed:.2f}s, themes={len(result.get('themes', []))}")
        
        return DiscoverySummaryResponse(
            category=result["category"],
            period_label=result["period_label"],
            themes=[DiscoveryTheme(**t) for t in result.get("themes", [])],
            one_off_summary=result.get("one_off_summary", ""),
            article_count=result.get("article_count", 0),
            generated_at=result.get("generated_at", datetime.utcnow().isoformat())
        )
        
    except HTTPException:
        raise
    except Exception as e:
        elapsed = time.time() - request_start
        logger.error(f"[DISCOVERY_SUMMARY] Endpoint FAILED: {elapsed:.2f}s, error={str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate summary: {str(e)}")


# =============================================================================
# Bulletin Board Endpoint (Priority Spotlight)
# =============================================================================

class BulletinBoardResponse(BaseModel):
    """Contextual guidance for the Market Intelligence bulletin board."""
    bullets: List[str]
    total_priority_items: int
    categories_covered: List[str] = []
    time_window_hours: int
    extended_to_7_days: bool = False
    generated_at: str


@router.get("/bulletin", response_model=BulletinBoardResponse)
async def get_bulletin_board():
    """
    Get contextual guidance bullets for the Market Intelligence bulletin board.
    
    Analyzes HIGH/CRITICAL priority items from the last 72 hours (or 7 days if none).
    Uses Haiku LLM to generate 1-3 brief, actionable guidance bullets pointing
    users to the most important content.
    """
    request_start = time.time()
    logger.info("[BULLETIN_BOARD] Endpoint START")
    
    try:
        from app.ingestion.generators.bulletin_board import BulletinBoardGenerator
        from app.db.gcp_storage import get_storage
        
        storage = await get_storage()
        
        # 1. Try 72 hours first
        hours = 72
        priority_items = []
        
        # Get HIGH/CRITICAL priority articles
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        
        # Query digest_items for high priority articles
        try:
            items = await storage.get_digest_items(hours=hours)
            for item in items:
                priority = getattr(item, 'priority', '') or ''
                if priority.lower() in ['high', 'critical']:
                    priority_items.append({
                        "id": getattr(item, 'id', ''),
                        "title": getattr(item, 'title', ''),
                        "primary_category": getattr(item, 'category', ''),
                        "priority": priority,
                        "published_at": getattr(item, 'published_at', None),
                        "source_name": getattr(item, 'source_name', ''),
                    })
        except Exception as e:
            logger.warning(f"[BULLETIN_BOARD] Failed to get digest items: {e}")
        
        # 2. If no items in 72h, extend to 7 days
        extended = False
        if len(priority_items) == 0:
            hours = 168  # 7 days
            extended = True
            try:
                items = await storage.get_digest_items(hours=hours)
                for item in items:
                    priority = getattr(item, 'priority', '') or ''
                    if priority.lower() in ['high', 'critical']:
                        priority_items.append({
                            "id": getattr(item, 'id', ''),
                            "title": getattr(item, 'title', ''),
                            "primary_category": getattr(item, 'category', ''),
                            "priority": priority,
                            "published_at": getattr(item, 'published_at', None),
                            "source_name": getattr(item, 'source_name', ''),
                        })
            except Exception as e:
                logger.warning(f"[BULLETIN_BOARD] Failed to get extended digest items: {e}")
        
        # 3. Sort by published_at (most recent first)
        priority_items.sort(
            key=lambda x: x.get("published_at") or "",
            reverse=True
        )
        
        logger.info(f"[BULLETIN_BOARD] Found {len(priority_items)} priority items in {hours}h window")
        
        # 4. Generate bulletin board content
        try:
            generator = BulletinBoardGenerator(anthropic_api_key=settings.anthropic_api_key)
            result = await generator.generate(priority_items, hours_window=hours, extended=extended)
            
            elapsed = time.time() - request_start
            logger.info(f"[BULLETIN_BOARD] Endpoint COMPLETE: {elapsed:.2f}s, bullets={len(result.get('bullets', []))}")
            
            return BulletinBoardResponse(**result)
            
        except Exception as gen_error:
            logger.error(f"[BULLETIN_BOARD] Generator failed: {gen_error}")
            # Fallback response
            return BulletinBoardResponse(
                bullets=["Check out the category themes below for the latest intelligence."],
                total_priority_items=len(priority_items),
                categories_covered=[],
                time_window_hours=hours,
                extended_to_7_days=extended,
                generated_at=datetime.utcnow().isoformat()
            )
        
    except Exception as e:
        elapsed = time.time() - request_start
        logger.error(f"[BULLETIN_BOARD] Endpoint FAILED: {elapsed:.2f}s, error={str(e)}", exc_info=True)
        # Return graceful fallback
        return BulletinBoardResponse(
            bullets=["Explore the categories below for the latest intelligence."],
            total_priority_items=0,
            categories_covered=[],
            time_window_hours=72,
            extended_to_7_days=False,
            generated_at=datetime.utcnow().isoformat()
        )
