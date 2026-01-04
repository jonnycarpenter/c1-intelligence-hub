"""MCP tool server configuration."""

from typing import List
from langchain_core.tools import BaseTool

from app.mcp.tools.api_ninja_earnings import (
    get_earnings_transcript_ninja,
    search_earnings_keywords,
)
# Exa.ai search tools - provides clean publishedDate for digest/pulse features
from app.mcp.tools.exa_search import news_search, web_search, extract_content, crawl_website, find_similar
from app.mcp.tools.visualization import create_chart
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

from app.utils.logger import get_logger

logger = get_logger(__name__)


def get_mcp_tools(agent_type: str) -> List[BaseTool]:
    """
    Get the appropriate MCP tools for each agent type.
    
    Args:
        agent_type: One of 'industry_watcher', 'market_scout', 'product_maven'
    
    Returns:
        List of tools available to that agent
    """
    logger.info(f"Loading MCP tools for agent: {agent_type}")
    
    # Import data management tools - available to ALL agents
    # so users can ask "what companies are we tracking?" in any mode
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
    
    # Data management tools are shared across all agents
    data_tools = [
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
    
    # Common tools available to all agents (Exa for web search - clean dates!)
    common_tools = [web_search] + data_tools
    
    # Corpus query tools - available to all conversational agents
    corpus_tools = [
        query_corpus,
        get_digest,
        get_entity_mentions,
        get_corpus_stats,
        get_priority_items,
        get_competitor_activity,
        get_market_signals,
    ]
    
    # Time-series data tools - historical data from ingestion pipeline
    # Available to Industry Watcher and Market Scout for trend analysis
    timeseries_tools = [
        search_press_release_archive,   # Search collected press releases
        search_news_archive,            # Search collected news articles
        get_corpus_summary,             # Quick overview of all collected data
    ]
    
    # Google Trends tools - available to both Industry Watcher and Market Scout
    google_trends_tools = [
        get_google_trends,              # Search interest trends over time
        get_related_searches,           # Related/rising search queries
        compare_composites_interest,    # Quick composites industry comparison
    ]
    
    # StockNewsAPI tools - on-demand news retrieval for deep research
    stocknews_tools = [
        get_company_news,               # News for specific tickers
        search_news_keyword,            # Keyword/phrase search (incl. private companies)
        get_press_releases,             # Official press releases
        get_analyst_ratings,            # Analyst upgrades/downgrades
        get_sentiment_summary,          # Aggregated sentiment for a ticker
        get_trending_headlines,         # Trending/high-coverage headlines
    ]
    
    if agent_type == "industry_watcher":
        # News, press release, and corpus query tools
        # news_search (Exa) provides date-filtered news with RELIABLE publishedDate
        # stocknews_tools provide on-demand ticker-based news and keyword search
        return common_tools + corpus_tools + timeseries_tools + google_trends_tools + stocknews_tools + [
            news_search,          # Exa news - clean publishedDate, date range support
            find_similar,         # Find related articles to a known URL
        ]
    
    elif agent_type == "market_scout":
        # Financial, earnings transcripts, corpus query, and visualization tools
        # stocknews_tools provide analyst ratings, sentiment, and press releases
        return common_tools + corpus_tools + timeseries_tools + google_trends_tools + stocknews_tools + [
            # API Ninjas earnings (primary - free tier, reliable)
            get_earnings_transcript_ninja,
            search_earnings_keywords,
            # Visualization
            create_chart,
            # Image search - find charts/graphs from web sources
            search_images,
            search_financial_visuals,
        ]
    
    elif agent_type == "product_maven":
        # Product intelligence and document extraction tools
        from app.mcp.tools.document_extraction import (
            crawl_for_documents,
            extract_pdf_content,
        )
        # Product intelligence tools for catalog queries
        product_tools = [
            search_competitor_products,
            get_product_specs,
            compare_product_specs,
            find_product_gaps,
            get_c1_catalog,
            suggest_alternatives,
        ]
        # Exa tools for web content extraction (datasheets, specs)
        exa_tools = [
            extract_content,    # Extract content from specific URLs (datasheets, product pages)
            crawl_website,      # Discover documents on supplier/competitor websites
            find_similar,       # Find similar products/specs to a known URL
        ]
        return common_tools + corpus_tools + product_tools + exa_tools + [
            crawl_for_documents,
            extract_pdf_content,
        ]
    
    else:
        logger.warning(f"Unknown agent type: {agent_type}, returning common tools only")
        return common_tools
