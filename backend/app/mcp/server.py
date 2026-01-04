"""
MCP tool server configuration.

DEPRECATION NOTICE (Phase 3 Consolidation - January 2026):
----------------------------------------------------------
The previous `get_mcp_tools(agent_type)` function has been removed.
The retired agent personas (industry_watcher, market_scout, product_maven) 
are no longer used. The unified agent now has access to ALL tools.

Use `get_all_mcp_tools()` which returns a flat list of all available tools.
"""

from typing import List
from langchain_core.tools import BaseTool

# Earnings transcript tools
from app.mcp.tools.api_ninja_earnings import (
    get_earnings_transcript_ninja,
    search_earnings_keywords,
)

# Exa.ai search tools - provides clean publishedDate for digest/pulse features
from app.mcp.tools.exa_search import (
    news_search,
    web_search,
    extract_content,
    crawl_website,
    find_similar,
)

# Visualization tools
from app.mcp.tools.visualization import create_chart

# Image search tools
from app.mcp.tools.image_extraction import search_images, search_financial_visuals

# Corpus query tools - for pre-ingested intelligence queries
from app.mcp.tools.corpus_query import (
    query_corpus,
    get_digest,
    get_entity_mentions,
    get_corpus_stats,
    get_priority_items,
    get_competitor_activity,
    get_market_signals,
)

# Product intelligence tools - product catalog and competitive analysis
from app.mcp.tools.product_intelligence import (
    search_competitor_products,
    get_product_specs,
    compare_product_specs,
    find_product_gaps,
    get_c1_catalog,
    suggest_alternatives,
)

# Time-series data tools - historical data from ingestion pipeline
from app.mcp.tools.timeseries_data import (
    search_press_release_archive,
    search_news_archive,
    get_corpus_summary,
)

# Google Trends tools - demand signal analysis
from app.mcp.tools.google_trends import (
    get_google_trends,
    get_related_searches,
    compare_composites_interest,
)

# StockNewsAPI tools - on-demand news retrieval for research workflow
from app.mcp.tools.stocknews_api import (
    get_company_news,
    search_news_keyword,
    get_press_releases,
    get_analyst_ratings,
    get_sentiment_summary,
    get_trending_headlines,
)

# Data management tools - company/material/industry tracker CRUD
from app.mcp.tools.data_management import (
    get_companies_list,
    get_materials_list,
    get_industries_list,
    get_preferences,
    update_preferences,
    add_company_to_tracker,
    add_material_to_tracker,
    add_industry_to_tracker,
    add_multiple_items,
    remove_company_from_tracker,
    remove_material_from_tracker,
)

# Document extraction tools
from app.mcp.tools.document_extraction import (
    crawl_for_documents,
    extract_pdf_content,
)

from app.utils.logger import get_logger

logger = get_logger(__name__)


def get_all_mcp_tools() -> List[BaseTool]:
    """
    Get ALL available MCP tools as a flat list.
    
    The unified agent has access to all tools - no persona-based filtering.
    Total: 43 tools across 8 categories.
    
    Categories:
        - Data Management (11): Company/material/industry tracker CRUD
        - Corpus Query (7): Query pre-ingested articles from BigQuery
        - External Search (6): Exa.ai web/news search
        - StockNews API (6): On-demand news retrieval
        - Time-series (3): Historical data from ingestion pipeline
        - Google Trends (3): Search interest analysis
        - Product Intelligence (6): Catalog and competitive analysis
        - Specialized (5): Earnings, visualization, images, documents
    
    Returns:
        List of all 43 available MCP tools
    """
    logger.info("Loading all MCP tools (unified agent)")
    
    # Data management tools (11)
    data_management_tools = [
        get_companies_list,
        get_materials_list,
        get_industries_list,
        get_preferences,
        update_preferences,
        add_company_to_tracker,
        add_material_to_tracker,
        add_industry_to_tracker,
        add_multiple_items,
        remove_company_from_tracker,
        remove_material_from_tracker,
    ]
    
    # Corpus query tools (7)
    corpus_tools = [
        query_corpus,
        get_digest,
        get_entity_mentions,
        get_corpus_stats,
        get_priority_items,
        get_competitor_activity,
        get_market_signals,
    ]
    
    # External search - Exa.ai (5)
    exa_tools = [
        web_search,
        news_search,
        extract_content,
        crawl_website,
        find_similar,
    ]
    
    # StockNews API tools (6)
    stocknews_tools = [
        get_company_news,
        search_news_keyword,
        get_press_releases,
        get_analyst_ratings,
        get_sentiment_summary,
        get_trending_headlines,
    ]
    
    # Time-series data tools (3)
    timeseries_tools = [
        search_press_release_archive,
        search_news_archive,
        get_corpus_summary,
    ]
    
    # Google Trends tools (3)
    google_trends_tools = [
        get_google_trends,
        get_related_searches,
        compare_composites_interest,
    ]
    
    # Product intelligence tools (6)
    product_tools = [
        search_competitor_products,
        get_product_specs,
        compare_product_specs,
        find_product_gaps,
        get_c1_catalog,
        suggest_alternatives,
    ]
    
    # Specialized tools (5)
    specialized_tools = [
        get_earnings_transcript_ninja,
        search_earnings_keywords,
        create_chart,
        search_images,
        search_financial_visuals,
    ]
    
    # Document extraction tools (2)
    document_tools = [
        crawl_for_documents,
        extract_pdf_content,
    ]
    
    all_tools = (
        data_management_tools +
        corpus_tools +
        exa_tools +
        stocknews_tools +
        timeseries_tools +
        google_trends_tools +
        product_tools +
        specialized_tools +
        document_tools
    )
    
    logger.info(f"Loaded {len(all_tools)} MCP tools")
    return all_tools


# Backwards compatibility alias (deprecated - will be removed in future)
def get_mcp_tools(agent_type: str = None) -> List[BaseTool]:
    """
    DEPRECATED: Use get_all_mcp_tools() instead.
    
    This function is kept for backwards compatibility only.
    Agent personas (industry_watcher, market_scout, product_maven) are retired.
    """
    logger.warning(
        f"get_mcp_tools() is deprecated. Use get_all_mcp_tools() instead. "
        f"Agent type '{agent_type}' is ignored - returning all tools."
    )
    return get_all_mcp_tools()
