"""Corpus Query tools - Query pre-ingested intelligence corpus.

These tools query cached/indexed intelligence content for faster retrieval
without making external API calls. Available to ALL agents.

Uses BigQuery as the primary data store with vector search capabilities.
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Optional
from langchain_core.tools import tool

from app.db.gcp_storage import get_storage
from app.db.vector_store import get_production_vector_store
from app.models.corpus import ContentCategory, Priority
from app.utils.grounding import load_companies, load_preferences
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def _get_bq_storage():
    """Get BigQuery storage instance."""
    return await get_storage()


# Category aliases for natural language parsing
CATEGORY_ALIASES = {
    "competitor": "competitor",
    "competitors": "competitor",
    "market": "market",
    "market trend": "market",
    "trends": "market",
    "regulatory": "regulatory",
    "regulation": "regulatory",
    "product": "product",
    "product launch": "product",
    "earnings": "earnings",
    "partnership": "partnership",
    "expansion": "expansion",
    "supply chain": "supply_chain",
    "supply": "supply_chain",
    "c1": "c1_mention",
    "continental": "c1_mention",
    "general": "general",
}

PRIORITY_ALIASES = {
    "high": "high",
    "important": "high",
    "urgent": "high",
    "critical": "high",
    "medium": "medium",
    "normal": "medium",
    "low": "low",
}


def _run_async(coro):
    """Run an async coroutine from sync context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Create a new task if there's already a loop
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, coro)
                return future.result(timeout=30)
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


def _format_corpus_item(item) -> dict:
    """Format a corpus item for JSON output."""
    return {
        "id": item.id,
        "title": item.title,
        "summary": item.summary[:300] if item.summary else None,
        "url": item.url,
        "source": item.source.name if item.source else None,
        "category": item.primary_category.value if item.primary_category else "general",
        "priority": item.priority.value if item.priority else "medium",
        "relevance_score": item.relevance_score,
        "sentiment": item.sentiment,
        "companies_mentioned": item.companies_mentioned[:5] if item.companies_mentioned else [],
        "industries": [i.value for i in item.industries[:3]] if item.industries else [],
        "published_at": item.published_at.isoformat() if item.published_at else None,
    }


def _format_vector_result(result: dict) -> dict:
    """Format a vector search result for JSON output."""
    metadata = result.get("metadata", {})
    # Handle both source_name and source_type field names
    source = metadata.get("source_name") or metadata.get("source_type", "")
    return {
        "id": result.get("id"),
        "title": metadata.get("title", "") or result.get("title", ""),
        "summary": result.get("document", "")[:300] if result.get("document") else "",
        "url": metadata.get("url", ""),
        "source": source,
        "category": metadata.get("category", "general"),
        "priority": metadata.get("priority", "medium"),
        "relevance_score": result.get("relevance_score", 0.5),
        "semantic_distance": result.get("distance"),
        "companies": metadata.get("companies", "").split(",")[:5] if metadata.get("companies") else [],
    }


def _format_article_record(item) -> dict:
    """Format an ArticleRecord from BigQuery for JSON output."""
    return {
        "id": item.id,
        "title": item.title,
        "summary": item.summary[:300] if item.summary else None,
        "url": item.url,
        "source": item.source_name or "",
        "category": item.category or "general",
        "priority": "medium",  # ArticleRecord doesn't have priority
        "relevance_score": item.relevance_score or 0.5,
        "companies_mentioned": item.companies_mentioned[:5] if item.companies_mentioned else [],
        "published_at": item.published_at.isoformat() if item.published_at else None,
    }


@tool
def query_corpus(
    query: Optional[str] = None,
    hours: int = 72,
    category: Optional[str] = None,
    priority: Optional[str] = None,
    company: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 10,
) -> str:
    """
    Search the pre-ingested intelligence corpus for relevant content.
    
    USE THIS FIRST before web search for questions about recent industry activity.
    The corpus contains pre-classified, relevant composites industry content.
    
    Use when users ask:
    - "What happened with Hexcel this week?"
    - "Any news about carbon fiber supply?"
    - "Recent competitor announcements"
    - "What's in the news about aerospace composites?"
    - "Key competitor highlights from Q4 2025" (use date_from/date_to)
    - "Supply chain issues in November 2025" (use date_from/date_to)
    
    Args:
        query: Search terms (uses semantic search when provided)
        hours: How far back to look (default 72 hours) - ignored if date_from/date_to provided
        category: Filter by category: competitor, market, regulatory, product, earnings, partnership
        priority: Filter by priority: high, medium, low
        company: Filter by specific company mentioned
        date_from: Start date for search (ISO format: "2025-10-01" for Q4 2025)
        date_to: End date for search (ISO format: "2025-12-31" for Q4 2025)
        limit: Maximum results to return
    
    Returns:
        Relevant intelligence items from the corpus
    """
    logger.info(f"Corpus query: query={query}, hours={hours}, category={category}, company={company}")
    
    # Parse category and priority aliases
    parsed_category = CATEGORY_ALIASES.get(category.lower()) if category else None
    parsed_priority = PRIORITY_ALIASES.get(priority.lower()) if priority else None
    
    async def _query():
        # Use BigQuery vector store (primary method)
        vector_store = await get_production_vector_store()
        
        results = []
        search_method = "semantic"
        
        # Use semantic search via BigQuery vector store
        if vector_store.is_available:
            # Build metadata filters
            where = {}
            if parsed_category:
                where["category"] = parsed_category
            if parsed_priority:
                where["priority"] = parsed_priority
            
            # Build search kwargs - include date range if provided
            search_kwargs = {
                "query": query or "",  # Empty query returns recent items
                "limit": limit,
                "where": where if where else None,
            }
            
            # Add date filters if provided (these override the hours parameter)
            if date_from:
                search_kwargs["date_from"] = date_from
            if date_to:
                search_kwargs["date_to"] = date_to
            
            vector_results = await vector_store.search(**search_kwargs)
            results = [_format_vector_result(r) for r in vector_results]
        else:
            # Fall back to BigQuery articles table
            storage = await _get_bq_storage()
            
            # Calculate date range from hours if not provided
            start_date = None
            end_date = None
            if date_from:
                start_date = datetime.fromisoformat(date_from)
            elif hours:
                start_date = datetime.utcnow() - timedelta(hours=hours)
            if date_to:
                end_date = datetime.fromisoformat(date_to)
            
            items = await storage.get_articles(
                category=parsed_category,
                start_date=start_date,
                end_date=end_date,
                search_query=query,
                limit=limit,
            )
            
            results = [_format_article_record(item) for item in items]
            search_method = "bigquery"
        
        return {
            "status": "success",
            "search_method": search_method,
            "query": query,
            "filters": {
                "hours": hours,
                "category": parsed_category,
                "priority": parsed_priority,
                "company": company,
            },
            "count": len(results),
            "items": results,
        }
    
    try:
        result = _run_async(_query())
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"Corpus query error: {e}")
        return json.dumps({
            "status": "error",
            "message": str(e),
            "suggested_action": "Use web_search tool as fallback",
        }, indent=2)


@tool
def get_digest(hours: int = 72) -> str:
    """
    Get the pre-computed intelligence digest - a curated summary of important items.
    
    The digest is organized by priority and category, highlighting what matters most.
    
    Use when users ask:
    - "What should I know about?"
    - "Give me the intelligence briefing"
    - "What happened in the last 3 days?"
    - "Show me the digest"
    
    Args:
        hours: Time period for digest (default 72 hours / 3 days)
    
    Returns:
        Formatted intelligence digest
    """
    logger.info(f"Getting digest for last {hours} hours")
    
    async def _get_digest():
        storage = await _get_bq_storage()
        
        # Get digest items from BigQuery (the primary source)
        items = await storage.get_digest_items(lookback_hours=hours, limit=20)
        
        if items:
            # Group by priority
            high_priority = [i for i in items if i.get("priority") == "high"]
            
            return {
                "status": "success",
                "digest": {
                    "period_hours": hours,
                    "items": [
                        {
                            "id": item.get("id"),
                            "title": item.get("title"),
                            "summary": (item.get("digest_summary") or item.get("original_summary", ""))[:200],
                            "category": item.get("category", "general"),
                            "priority": item.get("priority", "medium"),
                            "relevance_score": item.get("relevance_score", 0.5),
                        }
                        for item in items[:15]
                    ],
                    "stats": {
                        "total_items": len(items),
                        "high_priority": len(high_priority),
                    },
                },
            }
        else:
            return {
                "status": "no_items",
                "message": f"No digest items found for the last {hours} hours.",
                "suggested_action": "Run ingestion to generate fresh digest items",
            }
    
    try:
        result = _run_async(_get_digest())
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"Get digest error: {e}")
        return json.dumps({
            "status": "error",
            "message": str(e),
        }, indent=2)


@tool
def get_entity_mentions(
    entity_name: str,
    hours: int = 72,
    limit: int = 10,
) -> str:
    """
    Get recent mentions of a specific tracked entity in the corpus.
    
    Use when users ask:
    - "What's been said about Hexcel recently?"
    - "Recent mentions of Toray"
    - "News about Boeing in composites"
    
    Args:
        entity_name: Name of the entity (company, material, etc.)
        hours: How far back to look (default 72 hours)
        limit: Maximum mentions to return
    
    Returns:
        Recent corpus items mentioning the entity
    """
    logger.info(f"Getting mentions for {entity_name}, last {hours} hours")
    
    async def _get_mentions():
        vector_store = await get_production_vector_store()
        
        # Check if entity is tracked
        companies_df = load_companies()
        company_names = companies_df['company'].str.lower().tolist()
        is_tracked = entity_name.lower() in company_names
        
        results = []
        
        # Use semantic search to find mentions
        if vector_store.is_available:
            vector_results = await vector_store.search(
                query=f"{entity_name} news announcement activity",
                limit=limit * 2,  # Fetch more to filter
            )
            
            # Filter to items that likely mention the entity
            for r in vector_results:
                doc = r.get("document", "").lower()
                meta = r.get("metadata", {})
                companies = meta.get("companies", "").lower()
                
                if entity_name.lower() in doc or entity_name.lower() in companies:
                    results.append(_format_vector_result(r))
                    if len(results) >= limit:
                        break
        
        return {
            "status": "success",
            "entity": entity_name,
            "is_tracked": is_tracked,
            "time_range_hours": hours,
            "count": len(results),
            "mentions": results[:limit],
        }
    
    try:
        result = _run_async(_get_mentions())
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"Get entity mentions error: {e}")
        return json.dumps({
            "status": "error",
            "entity": entity_name,
            "message": str(e),
            "suggested_action": f"Use web_search with query '{entity_name} composites news'",
        }, indent=2)


@tool
def get_corpus_stats(hours: int = 72) -> str:
    """
    Get statistics about the intelligence corpus coverage.
    
    Use when users ask:
    - "How much content do we have?"
    - "What's the corpus coverage like?"
    - "How many articles this week?"
    
    Args:
        hours: Time period to analyze (default 72 hours)
    
    Returns:
        Corpus statistics including item counts, sources, categories
    """
    logger.info(f"Getting corpus stats for last {hours} hours")
    
    async def _get_stats():
        storage = await _get_bq_storage()
        vector_store = await get_production_vector_store()
        
        # Get digest stats from BigQuery
        digest_stats = await storage.get_digest_stats(hours=hours)
        
        # Get vector store count
        vector_count = await vector_store.get_count() if vector_store.is_available else 0
        
        # Get grounding data counts
        companies_df = load_companies()
        prefs = load_preferences()
        
        return {
            "status": "success",
            "time_range_hours": hours,
            "corpus_stats": digest_stats or {
                "total_items": 0,
                "items_in_period": 0,
            },
            "vector_store": {
                "available": vector_store.is_available,
                "total_indexed": vector_count,
            },
            "grounding_data": {
                "tracked_companies": len(companies_df),
                "priority_companies": len(prefs.get("tracked_companies", [])),
                "active_exclusions": len(prefs.get("global_exclusions", [])),
            },
        }
    
    try:
        result = _run_async(_get_stats())
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"Get corpus stats error: {e}")
        return json.dumps({
            "status": "error",
            "message": str(e),
        }, indent=2)


@tool
def get_priority_items(hours: int = 72, limit: int = 10) -> str:
    """
    Get high-priority intelligence items that need attention.
    
    Use when users ask:
    - "What's most important right now?"
    - "Any urgent news?"
    - "Show me priority items"
    - "What requires my attention?"
    
    Args:
        hours: Time period (default 72 hours)
        limit: Maximum items to return
    
    Returns:
        High-priority intelligence items
    """
    logger.info(f"Getting priority items for last {hours} hours, limit={limit}")
    
    async def _get_priority():
        storage = await _get_bq_storage()
        
        # Get high-priority digest items from BigQuery
        items = await storage.get_digest_items(
            lookback_hours=hours,
            limit=limit,
        )
        
        # Filter to high priority items
        high_priority = [i for i in items if i.get("priority") == "high"]
        
        return {
            "status": "success",
            "priority_level": "high",
            "time_range_hours": hours,
            "count": len(high_priority),
            "items": [
                {
                    "id": item.get("id"),
                    "title": item.get("title"),
                    "summary": (item.get("digest_summary") or item.get("original_summary", ""))[:300],
                    "url": item.get("url"),
                    "source": item.get("source_name"),
                    "category": item.get("category", "general"),
                    "priority": item.get("priority", "high"),
                    "relevance_score": item.get("relevance_score", 0.5),
                    "published_at": item.get("published_at"),
                }
                for item in high_priority[:limit]
            ],
        }
    
    try:
        result = _run_async(_get_priority())
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"Get priority items error: {e}")
        return json.dumps({
            "status": "error",
            "message": str(e),
        }, indent=2)


@tool
def get_competitor_activity(
    competitor_name: Optional[str] = None,
    hours: int = 72,
    limit: int = 10,
) -> str:
    """
    Get recent competitor activity and news from the corpus.
    
    Use when users ask:
    - "What are competitors doing?"
    - "Any news from Hexcel?"
    - "Competitor announcements this week"
    
    Args:
        competitor_name: Specific competitor (optional, shows all if not specified)
        hours: Time period (default 72 hours)
        limit: Maximum items to return
    
    Returns:
        Competitor-related intelligence
    """
    logger.info(f"Getting competitor activity: competitor={competitor_name}, hours={hours}")
    
    async def _get_competitor():
        vector_store = await get_production_vector_store()
        
        # Get tracked competitors
        companies_df = load_companies()
        competitors = companies_df[
            companies_df['type'].str.lower().str.contains('manufacturer', na=False)
        ]['company'].tolist()[:15]
        
        results = []
        
        if competitor_name:
            # Search for specific competitor using vector store
            if vector_store.is_available:
                vector_results = await vector_store.search(
                    query=f"{competitor_name} news announcement partnership acquisition",
                    limit=limit,
                    where={"category": "competitor"},
                )
                results = [_format_vector_result(r) for r in vector_results]
        else:
            # Get all competitor activity
            if vector_store.is_available:
                vector_results = await vector_store.search(
                    query="competitor announcement news partnership acquisition manufacturer",
                    limit=limit,
                    where={"category": "competitor"},
                )
                results = [_format_vector_result(r) for r in vector_results]
        
        return {
            "status": "success",
            "query_type": "competitor_activity",
            "competitor": competitor_name,
            "time_range_hours": hours,
            "tracked_competitors": competitors,
            "count": len(results),
            "items": results[:limit],
        }
    
    try:
        result = _run_async(_get_competitor())
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"Get competitor activity error: {e}")
        return json.dumps({
            "status": "error",
            "message": str(e),
            "suggested_action": f"Use web_search with query '{competitor_name or 'composites manufacturer'} news'",
        }, indent=2)


@tool
def get_market_signals(
    industry: Optional[str] = None,
    hours: int = 168,
    limit: int = 10,
) -> str:
    """
    Get market trend signals and demand indicators from the corpus.
    
    Use when users ask:
    - "What are the market trends?"
    - "Aerospace market signals"
    - "Any demand indicators?"
    - "Industry outlook"
    
    Args:
        industry: Filter by industry (aerospace, automotive, marine, wind_energy, etc.)
        hours: Time period (default 168 hours / 1 week for trends)
        limit: Maximum items to return
    
    Returns:
        Market trend intelligence
    """
    logger.info(f"Getting market signals: industry={industry}, hours={hours}")
    
    # Map industry aliases
    industry_map = {
        "aerospace": "aerospace",
        "aviation": "aerospace",
        "auto": "automotive",
        "automotive": "automotive",
        "marine": "marine",
        "boat": "marine",
        "wind": "wind_energy",
        "wind energy": "wind_energy",
        "defense": "defense",
        "military": "defense",
        "construction": "construction",
        "sporting": "sporting_goods",
        "sports": "sporting_goods",
    }
    
    parsed_industry = industry_map.get(industry.lower()) if industry else None
    
    async def _get_market():
        vector_store = await get_production_vector_store()
        
        results = []
        
        # Search for market signals using vector store
        search_query = f"{parsed_industry or 'composites'} market trend demand forecast outlook"
        
        if vector_store.is_available:
            where = {"category": "market"}
            
            vector_results = await vector_store.search(
                query=search_query,
                limit=limit * 2,
                where=where,
            )
            
            # Filter by industry if specified
            for r in vector_results:
                meta = r.get("metadata", {})
                industries = meta.get("industries", "")
                
                if not parsed_industry or parsed_industry in industries.lower():
                    results.append(_format_vector_result(r))
                    if len(results) >= limit:
                        break
        
        days = hours // 24
        
        return {
            "status": "success",
            "query_type": "market_signals",
            "industry": parsed_industry or industry,
            "time_range_hours": hours,
            "time_range_days": days,
            "count": len(results),
            "items": results[:limit],
        }
    
    try:
        result = _run_async(_get_market())
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"Get market signals error: {e}")
        return json.dumps({
            "status": "error",
            "message": str(e),
            "suggested_queries": [
                f"{industry or 'composites'} market outlook",
                f"{industry or 'composites'} demand forecast",
            ],
        }, indent=2)


@tool
def semantic_search(
    query: str,
    limit: int = 10,
) -> str:
    """
    Perform semantic search across the intelligence corpus.
    
    Uses vector embeddings to find conceptually similar content,
    even if exact keywords don't match.
    
    Use when users ask natural language questions like:
    - "What's happening with supply chain disruptions?"
    - "Find articles about sustainability initiatives"
    - "Anything about new manufacturing technologies?"
    
    Args:
        query: Natural language search query
        limit: Maximum results to return
    
    Returns:
        Semantically similar corpus items
    """
    logger.info(f"Semantic search: {query}")
    
    async def _search():
        vector_store = await get_production_vector_store()
        
        if not vector_store.is_available:
            return {
                "status": "unavailable",
                "message": "Vector store not available. Use query_corpus for keyword search.",
            }
        
        results = await vector_store.search(query=query, limit=limit)
        
        return {
            "status": "success",
            "query": query,
            "search_method": "semantic_embedding",
            "count": len(results),
            "items": [_format_vector_result(r) for r in results],
        }
    
    try:
        result = _run_async(_search())
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"Semantic search error: {e}")
        return json.dumps({
            "status": "error",
            "message": str(e),
        }, indent=2)
