"""Corpus Visuals tool - Search for charts, graphs, and visual assets from ingested articles.

This tool queries the article_images BigQuery table to find relevant visuals
(charts, graphs, infographics, diagrams) that support research findings.

Available to the Visual Research Agent in the Deep Research workflow.
"""

import asyncio
import json
from typing import Optional, List, Dict, Any
from langchain_core.tools import tool

from app.db.gcp_storage import get_storage
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


async def _get_bq_storage():
    """Get BigQuery storage instance."""
    return await get_storage()


def _format_visual_result(item: Dict[str, Any]) -> dict:
    """Format a visual from BigQuery for JSON output."""
    # Parse JSON fields if they're strings
    companies = item.get("companies", [])
    if isinstance(companies, str):
        try:
            companies = json.loads(companies)
        except (json.JSONDecodeError, TypeError):
            companies = []

    industries = item.get("industries", [])
    if isinstance(industries, str):
        try:
            industries = json.loads(industries)
        except (json.JSONDecodeError, TypeError):
            industries = []

    topics = item.get("topics", [])
    if isinstance(topics, str):
        try:
            topics = json.loads(topics)
        except (json.JSONDecodeError, TypeError):
            topics = []

    return {
        "visual_id": item.get("id", ""),
        "image_url": item.get("url", ""),
        "description": item.get("description", ""),
        "article_title": item.get("article_title", ""),
        "article_id": item.get("article_id", ""),
        "image_type": item.get("image_type", "chart"),
        "chart_type": item.get("chart_type", ""),
        "companies": companies[:5] if companies else [],
        "industries": industries[:3] if industries else [],
        "topics": topics[:5] if topics else [],
        "relevance_score": float(item.get("relevance_score", 0.5)),
    }


@tool
def corpus_visuals_search(
    companies: Optional[List[str]] = None,
    industries: Optional[List[str]] = None,
    topics: Optional[List[str]] = None,
    image_types: Optional[List[str]] = None,
    chart_types: Optional[List[str]] = None,
    limit: int = 15,
    days: int = 90,
) -> str:
    """
    Search the article_images corpus for relevant charts, graphs, and visual assets.

    This tool finds visuals that support Deep Research findings. Use it to surface:
    - Market trend charts
    - Competitive positioning graphs
    - Revenue/profit comparisons
    - Supply chain diagrams
    - Product topology visualizations
    - Market share infographics

    Args:
        companies: List of company names to filter visuals by (e.g., ["Hexcel", "Solvay"])
        industries: List of industries to filter by (e.g., ["aerospace", "automotive"])
        topics: List of topics/metrics to filter by (e.g., ["revenue", "market_share", "forecast"])
        image_types: Types of images to include (default: all)
            - "chart" (default)
            - "graph"
            - "infographic"
            - "diagram"
            - "photo"
            - "table"
        chart_types: Specific chart types to include
            - "line", "bar", "pie", "area", "scatter", "candlestick"
        limit: Max visuals to return (default 15)
        days: Only return visuals from last N days (default 90)

    Returns:
        JSON string with list of relevant visuals. Each visual includes:
        - visual_id, image_url, description
        - article_title, article_id (source context)
        - image_type, chart_type
        - companies, industries, topics (metadata)
        - relevance_score (0-1)

    Example:
        >>> corpus_visuals_search(
        ...     companies=["Hexcel"],
        ...     industries=["aerospace"],
        ...     topics=["revenue"],
        ...     limit=10
        ... )
    """
    try:
        async def _search():
            storage = await _get_bq_storage()

            # Build WHERE conditions
            conditions = []

            if companies:
                # Companies stored as JSON array in BigQuery
                company_conditions = " OR ".join(
                    [f'JSON_EXTRACT_SCALAR(companies, "$[*]") LIKE "%{c}%"' for c in companies]
                )
                conditions.append(f"({company_conditions})")

            if industries:
                # Industries stored as JSON array
                industry_conditions = " OR ".join(
                    [f'JSON_EXTRACT_SCALAR(industries, "$[*]") LIKE "%{i}%"' for i in industries]
                )
                conditions.append(f"({industry_conditions})")

            if topics:
                # Topics stored as JSON array
                topic_conditions = " OR ".join(
                    [f'JSON_EXTRACT_SCALAR(topics, "$[*]") LIKE "%{t}%"' for t in topics]
                )
                conditions.append(f"({topic_conditions})")

            if image_types:
                image_type_conditions = " OR ".join(
                    [f'image_type = "{t}"' for t in image_types]
                )
                conditions.append(f"({image_type_conditions})")

            if chart_types:
                chart_type_conditions = " OR ".join(
                    [f'chart_type = "{t}"' for t in chart_types]
                )
                conditions.append(f"({chart_type_conditions})")

            # Add date filter
            conditions.append(f"DATE(ingested_at) >= DATE_SUB(CURRENT_DATE(), INTERVAL {days} DAY)")

            where_clause = " AND ".join(conditions) if conditions else "TRUE"

            # Build query
            query = f"""
            SELECT
                id,
                article_id,
                article_title,
                url,
                image_type,
                chart_type,
                description,
                companies,
                industries,
                topics,
                relevance_score,
                ingested_at
            FROM
                `gen-lang-client-0436975498.c1_intelligence_hub.article_images`
            WHERE
                {where_clause}
            ORDER BY
                relevance_score DESC
            LIMIT
                {limit}
            """

            logger.info(f"Executing corpus visuals search: {query[:200]}...")

            try:
                results = await storage.query_async(query)
                visuals = [_format_visual_result(row) for row in results]

                logger.info(f"Found {len(visuals)} visuals matching criteria")

                return json.dumps(
                    {
                        "status": "success",
                        "count": len(visuals),
                        "visuals": visuals,
                    },
                    indent=2,
                    default=str,
                )

            except Exception as e:
                logger.error(f"BigQuery query failed: {str(e)}")
                return json.dumps(
                    {
                        "status": "error",
                        "error": f"BigQuery query failed: {str(e)}",
                        "count": 0,
                        "visuals": [],
                    }
                )

        return _run_async(_search())

    except Exception as e:
        logger.error(f"corpus_visuals_search error: {str(e)}")
        return json.dumps(
            {
                "status": "error",
                "error": str(e),
                "count": 0,
                "visuals": [],
            }
        )
