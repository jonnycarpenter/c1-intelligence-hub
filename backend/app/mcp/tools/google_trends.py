"""
Google Trends Tool
==================

Provides search interest data from Google Trends for demand signal analysis.
Useful for tracking interest in materials, companies, and industry terms.

Uses pytrends library to access Google Trends data.
"""

from typing import Optional, List, Dict, Any
import json
import time

from langchain_core.tools import tool
from app.utils.retry import retry_on_rate_limit, skip_on_failure, tool_metrics

from app.utils.logger import get_logger

logger = get_logger(__name__)


@tool
def get_google_trends(
    keywords: List[str],
    timeframe: str = "today 3-m",
    geo: str = "US",
) -> Dict[str, Any]:
    """
    Get Google Trends data for keywords to analyze search interest over time.
    
    Use this for:
    - Demand signal analysis (is interest in a material/product growing?)
    - Comparing competing materials or companies
    @skip_on_failure(default_return={"error": "Google Trends temporarily unavailable", "skipped": True}, log_level="warning")
    @retry_on_rate_limit(max_retries=3, initial_delay=2.0)
    def get_google_trends(
    - Tracking brand/company awareness trends
    
    Examples:
    - "Compare interest in carbon fiber vs fiberglass"
    - "What's the trend for epoxy resin searches?"
        start_time = time.time()
    - "Is Hexcel getting more search interest than Toray?"
    
    Returns interest scores (0-100) over time with trend analysis.
    """
    logger.info(f"Fetching Google Trends for: {keywords}")
    
    # Limit to 5 keywords (Google Trends maximum)
    keywords = keywords[:5]
    
    try:
        from pytrends.request import TrendReq
        
        # Initialize pytrends
        pytrends = TrendReq(hl='en-US', tz=360)
        
        # Build payload
        pytrends.build_payload(
            keywords,
            cat=0,
            timeframe=timeframe,
            geo=geo,
            gprop=''
        )
        
        # Get interest over time
        interest_df = pytrends.interest_over_time()
        
        if interest_df.empty:
            return {
                "keywords": keywords,
                "timeframe": timeframe,
                "geo": geo,
                "error": "No trend data available for these keywords",
                "interest_over_time": {},
            }
        
        # Remove isPartial column if present
        if 'isPartial' in interest_df.columns:
            interest_df = interest_df.drop('isPartial', axis=1)
        
        # Calculate trend direction and change
        trend_analysis = {}
        for kw in keywords:
            if kw in interest_df.columns:
                values = interest_df[kw].values
                
                # Get first and last values for comparison
                first_half_avg = values[:len(values)//2].mean()
                second_half_avg = values[len(values)//2:].mean()
                
                if first_half_avg > 0:
                    percent_change = ((second_half_avg - first_half_avg) / first_half_avg) * 100
                else:
                    percent_change = 0
                
                if percent_change > 10:
                    direction = "rising"
                elif percent_change < -10:
                    direction = "declining"
                else:
                    direction = "stable"
                
                trend_analysis[kw] = {
                    "direction": direction,
                    "percent_change": round(percent_change, 1),
                    "current_interest": int(values[-1]) if len(values) > 0 else 0,
                    "peak_interest": int(values.max()),
                    "average_interest": round(float(values.mean()), 1),
                }
        
        # Convert interest over time to serializable format (last 10 data points for brevity)
        interest_dict = {}
        for kw in keywords:
            if kw in interest_df.columns:
                # Get last 10 data points
                recent = interest_df[kw].tail(10)
                interest_dict[kw] = {
                    str(date.date()): int(val) 
                    for date, val in recent.items()
                }
        
        # Generate summary
        summary_parts = []
        for kw, analysis in trend_analysis.items():
            summary_parts.append(
                f"{kw}: {analysis['direction']} ({analysis['percent_change']:+.1f}%), "
                f"current: {analysis['current_interest']}/100"
            )
        
        return {
            "keywords": keywords,
            "timeframe": timeframe,
            "geo": geo,
            "data_points": len(interest_df),
            "trend_analysis": trend_analysis,
            "recent_interest": interest_dict,
            "summary": " | ".join(summary_parts),
        }
        
    except ImportError:
        logger.warning("pytrends not installed")
        return {
            "keywords": keywords,
            "timeframe": timeframe,
            "geo": geo,
            "error": "pytrends library not installed. Install with: pip install pytrends",
        }
    except Exception as e:
        logger.error(f"Google Trends error: {e}")
        return {
            "keywords": keywords,
            "timeframe": timeframe,
            "geo": geo,
            "error": str(e),
        }


@tool
def get_related_searches(
    keyword: str,
    geo: str = "US",
) -> Dict[str, Any]:
    """
    Get related search queries for a keyword from Google Trends.
    
    Use this to discover:
    - What people also search for alongside a term
    - Rising/breakout search terms in a category
    - Related product/material searches
    
    Examples:
    - "What are people searching related to carbon fiber?"
    - "Find rising searches around composites materials"
    """
    logger.info(f"Fetching related queries for: {keyword}")
    
    try:
        from pytrends.request import TrendReq
        
        pytrends = TrendReq(hl='en-US', tz=360)
        pytrends.build_payload([keyword], geo=geo)
        
        related = pytrends.related_queries()
        
        result = {
            "keyword": keyword,
            "geo": geo,
            "top_queries": [],
            "rising_queries": [],
        }
        
        if keyword in related:
            top_df = related[keyword].get('top')
            rising_df = related[keyword].get('rising')
            
            if top_df is not None and not top_df.empty:
                result["top_queries"] = top_df.to_dict('records')[:10]
            
            if rising_df is not None and not rising_df.empty:
                result["rising_queries"] = rising_df.to_dict('records')[:10]
        
        return result
        
    except ImportError:
        return {
            "keyword": keyword,
            "geo": geo,
            "error": "pytrends library not installed",
        }
    except Exception as e:
        logger.error(f"Related queries error: {e}")
        return {
            "keyword": keyword,
            "geo": geo,
            "error": str(e),
        }


@tool
def compare_composites_interest() -> Dict[str, Any]:
    """
    Compare Google Trends interest in key composites industry terms.
    
    Pre-configured comparison of:
    - carbon fiber
    - fiberglass  
    - prepreg
    - epoxy resin
    - composites
    
    Useful for quick industry demand signal overview.
    """
    composites_keywords = [
        "carbon fiber",
        "fiberglass",
        "prepreg",
        "epoxy resin",
        "composites",
    ]
    
    return get_google_trends.invoke({
        "keywords": composites_keywords,
        "timeframe": "today 12-m",
        "geo": "US",
    })
