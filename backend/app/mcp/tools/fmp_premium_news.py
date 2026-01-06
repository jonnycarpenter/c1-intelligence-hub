"""FMP Premium News MCP Tool

Provides on-demand premium news retrieval from Financial Modeling Prep.

Uses the existing FMPNewsClient from ingestion tools but exposes it as an MCP tool
for agent use during briefings and research.

Sources include: Benzinga, Seeking Alpha, Bloomberg, WSJ, etc.
"""

import json
import time
from typing import List, Optional
from langchain_core.tools import tool

from app.config.settings import settings
from app.utils.logger import get_logger
from app.utils.retry import skip_on_failure, tool_metrics

logger = get_logger(__name__)


def _get_fmp_client():
    """Lazy-load FMP client to avoid circular imports."""
    from app.tools.fmp_news.client import FMPNewsClient
    return FMPNewsClient(api_key=settings.fmp_api_key)


def _format_article(article) -> dict:
    """Format FMPNewsArticle for JSON output."""
    return {
        "title": article.title,
        "url": article.url,
        "text": article.text[:500] + "..." if len(article.text) > 500 else article.text,
        "symbol": article.symbol,
        "publisher": article.publisher or article.site,
        "published_date": article.published_at.isoformat() if article.published_at else "",
    }


@tool
@skip_on_failure(default_return=json.dumps({"error": "FMP service temporarily unavailable", "skipped": True}), log_level="warning")
def get_fmp_premium_news(
    symbols: Optional[List[str]] = None,
    limit: int = 20,
) -> str:
    """
    Fetch premium financial news from FMP (Financial Modeling Prep).
    
    Premium sources include: Benzinga, Seeking Alpha, Bloomberg, WSJ, Reuters.
    
    Use this for:
    - High-quality financial and business news
    - Company-specific news for publicly traded companies
    - Market-moving announcements and analysis
    
    Key Ticker Reference (Composites Industry):
    - Composites: HXL (Hexcel), OC (Owens Corning), TRYIY (Toray), TPIC (TPI Composites)
    - Aerospace: BA (Boeing), EADSY (Airbus), RTX, LMT (Lockheed), GE
    - Wind Energy: VWDRY (Vestas), GEV (GE Vernova)
    - Marine: BC (Brunswick), MBUU (Malibu Boats)
    
    Args:
        symbols: Optional list of ticker symbols to filter (e.g., ["HXL", "BA"])
                 If not provided, returns general market news
        limit: Number of articles to return (default: 20, max: 50)
    
    Returns:
        JSON string with articles containing: title, url, text, symbol, publisher, published_date
    """
    logger.info(f"FMP premium news: symbols={symbols}, limit={limit}")
    start_time = time.time()
    
    if not settings.fmp_api_key:
        tool_metrics.record_failure("get_fmp_premium_news", "API key not configured")
        return json.dumps({"error": "FMP API key not configured"})
    
    try:
        client = _get_fmp_client()
        articles = client.get_stock_news(
            symbols=symbols,
            limit=min(limit, 50),
        )
        
        if not articles:
            duration = time.time() - start_time
            tool_metrics.record_success("get_fmp_premium_news", duration)
            return json.dumps({
                "message": f"No premium news found" + (f" for symbols: {symbols}" if symbols else ""),
                "symbols": symbols,
                "total_results": 0,
            })
        
        formatted = [_format_article(a) for a in articles]
        
        duration = time.time() - start_time
        tool_metrics.record_success("get_fmp_premium_news", duration)
        
        return json.dumps({
            "source": "FMP Premium News",
            "symbols": symbols,
            "total_results": len(formatted),
            "articles": formatted,
        }, indent=2)
        
    except Exception as e:
        duration = time.time() - start_time
        tool_metrics.record_failure("get_fmp_premium_news", str(e), duration)
        logger.error(f"FMP premium news error: {e}")
        raise  # Let skip_on_failure handle it
