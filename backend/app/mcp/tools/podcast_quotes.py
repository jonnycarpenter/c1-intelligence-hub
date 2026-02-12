"""Podcast Quotes search tool - Query extracted quotes from composites industry podcasts.

Searches the podcast_quotes BigQuery table for speaker-attributed insights
from CW Talks, Composites Weekly, The Chemical Show, ICIS Chemical, and others.

Available to all agents via get_all_mcp_tools().
"""

import asyncio
import json
from typing import Optional, List
from langchain_core.tools import tool

from app.db.gcp_storage import get_storage
from app.db.semantic_search import get_semantic_searcher
from app.utils.logger import get_logger

logger = get_logger(__name__)


def _run_async(coro):
    """Run an async coroutine from sync context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, coro)
                return future.result(timeout=30)
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


@tool
def search_podcast_quotes(
    search_query: Optional[str] = None,
    themes: Optional[List[str]] = None,
    podcast_name: Optional[str] = None,
    speaker_name: Optional[str] = None,
    days: int = 90,
    limit: int = 15,
) -> str:
    """Search extracted podcast quotes from composites industry podcasts.

    This tool finds pre-extracted practitioner insights from industry podcasts
    including CW Talks (CompositesWorld), Composites Weekly, The Chemical Show,
    ICIS Chemical Podcasts, and Uptime Wind Energy.

    Quotes include speaker attribution, themes, and relevance scores.
    Use this for:
    - Finding expert opinions on specific topics (fiber materials, resin systems, etc.)
    - Sourcing quotes for briefings and reports
    - Understanding industry sentiment from practitioners
    - Identifying supply chain, pricing, or regulatory signals from podcast discussions

    Args:
        search_query: Free-text search across quote text, context, and speaker name
        themes: Filter by theme codes. Available themes:
            fiber_materials, resin_systems, manufacturing_processes,
            wind_energy, aerospace_composites, automotive_composites,
            infrastructure, marine_composites, sustainability, regulatory,
            supply_chain, market_dynamics, innovation, workforce, pricing, competitive
        podcast_name: Filter by podcast name (partial match)
        speaker_name: Filter by speaker name (partial match)
        days: Only return quotes from last N days (default 90)
        limit: Max quotes to return (default 15)

    Returns:
        JSON with list of matching quotes including speaker attribution,
        themes, relevance scores, and source episode info.
    """
    try:
        results = _run_async(_search_quotes(
            search_query=search_query,
            themes=themes,
            podcast_name=podcast_name,
            speaker_name=speaker_name,
            days=days,
            limit=limit,
        ))
        return json.dumps(results, indent=2, default=str)
    except Exception as e:
        logger.error(f"[PODCAST_QUOTES] Search failed: {e}", exc_info=True)
        return json.dumps({"error": str(e), "quotes": []})


async def _search_quotes(
    search_query: Optional[str] = None,
    themes: Optional[List[str]] = None,
    podcast_name: Optional[str] = None,
    speaker_name: Optional[str] = None,
    days: int = 90,
    limit: int = 15,
) -> dict:
    """Execute the quote search against BigQuery using semantic search when available."""
    # Try semantic (vector) search first for natural-language queries
    if search_query:
        try:
            searcher = await get_semantic_searcher()
            if searcher.is_available:
                logger.info("[PODCAST_QUOTES] Using semantic vector search")
                rows = await searcher.search_podcast_quotes(
                    query=search_query,
                    themes=themes,
                    podcast_name=podcast_name,
                    speaker_name=speaker_name,
                    days=days,
                    limit=limit,
                )
                if rows:
                    # Build response from semantic results
                    quotes = []
                    for row in rows:
                        themes_val = row.get("themes", "[]")
                        if isinstance(themes_val, str):
                            try:
                                themes_val = json.loads(themes_val)
                            except (json.JSONDecodeError, TypeError):
                                themes_val = []
                        quotes.append({
                            "quote_text": row.get("quote_text", ""),
                            "context": row.get("context_summary", ""),
                            "speaker": {
                                "name": row.get("speaker_name", "Unknown"),
                                "role": row.get("speaker_role", "unknown"),
                                "title": row.get("speaker_title"),
                                "company": row.get("speaker_company"),
                            },
                            "themes": themes_val,
                            "relevance_score": row.get("semantic_score", row.get("relevance_score", 0.0)),
                            "source": {
                                "podcast": row.get("podcast_name", ""),
                                "episode": row.get("episode_title", ""),
                                "url": row.get("episode_url", ""),
                                "date": str(row.get("published_at", ""))[:10],
                            },
                        })
                    return {
                        "total_results": len(quotes),
                        "search_params": {
                            "query": search_query,
                            "themes": themes,
                            "podcast": podcast_name,
                            "speaker": speaker_name,
                            "days": days,
                        },
                        "quotes": quotes,
                    }
        except Exception as e:
            logger.warning(f"[PODCAST_QUOTES] Semantic search failed, falling back to LIKE: {e}")

    # Fallback: original LIKE-based search
    logger.info("[PODCAST_QUOTES] Using LIKE-based search")
    storage = await get_storage()

    rows = await storage.get_podcast_quotes(
        search_query=search_query,
        themes=themes,
        podcast_name=podcast_name,
        speaker_name=speaker_name,
        days=days,
        limit=limit,
    )

    quotes = []
    for row in rows:
        # Parse themes JSON
        themes_val = row.get("themes", "[]")
        if isinstance(themes_val, str):
            try:
                themes_val = json.loads(themes_val)
            except (json.JSONDecodeError, TypeError):
                themes_val = []

        quotes.append({
            "quote_text": row.get("quote_text", ""),
            "context": row.get("context_summary", ""),
            "speaker": {
                "name": row.get("speaker_name", "Unknown"),
                "role": row.get("speaker_role", "unknown"),
                "title": row.get("speaker_title"),
                "company": row.get("speaker_company"),
            },
            "themes": themes_val,
            "relevance_score": row.get("relevance_score", 0.0),
            "source": {
                "podcast": row.get("podcast_name", ""),
                "episode": row.get("episode_title", ""),
                "url": row.get("episode_url", ""),
                "date": str(row.get("published_at", ""))[:10],
            },
        })

    return {
        "total_results": len(quotes),
        "search_params": {
            "query": search_query,
            "themes": themes,
            "podcast": podcast_name,
            "speaker": speaker_name,
            "days": days,
        },
        "quotes": quotes,
    }
