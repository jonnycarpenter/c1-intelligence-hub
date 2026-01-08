"""
Image Search and Interpretation Tools for C1 Intelligence Hub

Two-stage approach to chart/visualization handling:
1. SEARCH: Find relevant charts using Tavily's image search
2. INTERPRET: Use Claude vision to extract structured data from charts

This separation allows the agent to control latency and cost by choosing
which images are worth the extra interpretation step.
"""

from typing import Optional, List, Literal
import json
import re
import base64
import httpx
import anthropic
from langchain_core.tools import tool

from app.config.settings import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

# =============================================================================
# CONFIGURATION
# =============================================================================

TAVILY_SEARCH_URL = "https://api.tavily.com/search"

# Vision model for chart interpretation
VISION_MODEL = "claude-sonnet-4-5"

# Common chart/image hosting patterns to prioritize
CHART_URL_PATTERNS = [
    r'chart', r'graph', r'tradingview', r'stockcharts', r'highcharts',
    r'finance\.yahoo', r'seekingalpha', r'finviz', r'marketwatch',
    r'bloomberg', r'reuters', r'statista', r'tradingeconomics',
    r'simplywall', r'macrotrends', r'ycharts', r'earnings', r'revenue',
    r'compositesworld', r'jeccomposites', r'reinforcedplastics'
]

# Patterns to filter out (logos, icons, etc.)
SKIP_PATTERNS = [
    'logo', 'icon', 'avatar', 'profile', 'button', 'sprite',
    'ad-', 'banner', 'sponsor', 'tracking', 'pixel', 'spacer',
    'social', 'facebook', 'twitter', 'linkedin', 'share',
    'arrow', 'caret', 'chevron', 'close', 'menu', 'thumb',
    'emoji', 'badge', 'favicon', 'placeholder', 'default'
]

# Supported image media types
MEDIA_TYPE_MAP = {
    'png': 'image/png',
    'jpg': 'image/jpeg',
    'jpeg': 'image/jpeg',
    'gif': 'image/gif',
    'webp': 'image/webp'
}

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _get_tavily_api_key() -> Optional[str]:
    """Get Tavily API key from settings."""
    return getattr(settings, 'tavily_api_key', None) or getattr(settings, 'TAVILY_API_KEY', None)


def _get_anthropic_client() -> anthropic.Anthropic:
    """Get Anthropic client for vision API calls."""
    return anthropic.Anthropic()


def _detect_media_type(url: str, content_type: str = '') -> str:
    """Detect image media type from URL or content-type header."""
    url_lower = url.lower()
    content_type_lower = content_type.lower()
    
    for ext, media_type in MEDIA_TYPE_MAP.items():
        if f'.{ext}' in url_lower or ext in content_type_lower:
            return media_type
    
    return 'image/jpeg'  # Default fallback


def _score_and_filter_images(images: List[str], query_terms: List[str]) -> List[dict]:
    """Score images based on relevance and filter out junk."""
    scored_images = []
    
    for url in images:
        if not url or not isinstance(url, str):
            continue
            
        url_lower = url.lower()
        
        # Skip if matches any skip pattern
        if any(pattern in url_lower for pattern in SKIP_PATTERNS):
            continue
        
        # Calculate relevance score
        score = 0
        
        # Bonus for chart-related hosting patterns
        for pattern in CHART_URL_PATTERNS:
            if re.search(pattern, url_lower):
                score += 3
                break
        
        # Bonus for query terms in URL
        for term in query_terms:
            if len(term) > 2 and term.lower() in url_lower:
                score += 2
        
        # Bonus for image file extensions (actual images vs placeholders)
        if any(f'.{ext}' in url_lower for ext in MEDIA_TYPE_MAP.keys()):
            score += 1
        
        scored_images.append({
            'url': url,
            'score': score
        })
    
    # Sort by score descending
    scored_images.sort(key=lambda x: x['score'], reverse=True)
    
    return scored_images


def _validate_image_urls(images: List[dict], timeout: float = 3.0) -> List[dict]:
    """
    Validate that image URLs are accessible. Returns only URLs that respond with 200.
    Uses HEAD requests for efficiency.
    """
    validated = []
    
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        for img in images:
            url = img.get('url', '')
            try:
                response = client.head(url)
                if response.status_code == 200:
                    validated.append(img)
                else:
                    logger.debug(f"Image URL returned {response.status_code}: {url[:60]}")
            except Exception as e:
                logger.debug(f"Image URL validation failed: {url[:60]} - {type(e).__name__}")
                continue
    
    return validated


def _fetch_image_as_base64(url: str, timeout: float = 10.0) -> tuple[str, str]:
    """
    Fetch an image and return as base64 with its media type.
    
    Returns:
        Tuple of (base64_data, media_type)
    
    Raises:
        Exception if fetch fails
    """
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        response = client.get(url)
        response.raise_for_status()
        
        content_type = response.headers.get('content-type', '')
        media_type = _detect_media_type(url, content_type)
        
        image_b64 = base64.standard_b64encode(response.content).decode('utf-8')
        
        return image_b64, media_type


# =============================================================================
# SEARCH TOOLS
# =============================================================================

@tool
def search_images(
    query: str,
    max_images: int = 5,
    search_depth: Literal["basic", "advanced"] = "advanced",
) -> str:
    """
    Search for charts, graphs, and visualizations using Tavily's image search.
    
    Use this to find visual content to illustrate your analysis.
    This tool FINDS images but does not interpret them. Use interpret_chart
    on the results if you need to extract data from the charts.
    
    Best for:
    - Finding charts showing company revenue/earnings trends
    - Market trend visualizations and forecasts
    - Industry comparison graphics
    - Financial data infographics
    
    Args:
        query: Search query describing the visual you need
               Examples: "Hexcel revenue chart 2024", "carbon fiber market forecast graph"
        max_images: Maximum number of images to return (1-10, default 5)
        search_depth: "basic" for quick search, "advanced" for deeper search
    
    Returns:
        JSON with image URLs. Use interpret_chart on URLs to extract data.
    """
    logger.info(f"Searching images: '{query}' (max={max_images}, depth={search_depth})")
    
    api_key = _get_tavily_api_key()
    if not api_key:
        return json.dumps({"error": "Tavily API key not configured"})
    
    try:
        # Add visualization keywords to improve image results
        enhanced_query = f"{query} chart graph visualization"
        
        # Build Tavily request with image search enabled
        payload = {
            "api_key": api_key,
            "query": enhanced_query,
            "search_depth": search_depth,
            "include_images": True,
            "include_answer": False,
            "max_results": 5,
        }
        
        with httpx.Client(timeout=30) as client:
            response = client.post(TAVILY_SEARCH_URL, json=payload)
            response.raise_for_status()
            data = response.json()
        
        # Get images from response
        raw_images = data.get("images", [])
        
        # Extract query terms for relevance scoring
        query_terms = [term for term in query.split() if len(term) > 2]
        
        # Score and filter images
        scored_images = _score_and_filter_images(raw_images, query_terms)
        
        # Limit to max requested (get a few extra in case some fail validation)
        max_images = min(max(1, max_images), 10)
        candidates = scored_images[:max_images + 3]
        
        # Validate URLs are accessible
        validated_images = _validate_image_urls(candidates)
        
        # Final limit
        filtered_images = validated_images[:max_images]
        
        # Also include related article sources for context
        sources = []
        for result in data.get("results", [])[:3]:
            sources.append({
                "title": result.get("title", ""),
                "url": result.get("url", ""),
                "snippet": result.get("content", "")[:200] if result.get("content") else ""
            })
        
        return json.dumps({
            "source": "Tavily Image Search",
            "query": query,
            "images_found": len(raw_images),
            "images_returned": len(filtered_images),
            "images": [
                {
                    "url": img['url'],
                    "relevance_score": img['score']
                } 
                for img in filtered_images
            ],
            "related_sources": sources,
            "next_step": "Use interpret_chart(url) on promising images to extract data"
        }, indent=2)
        
    except httpx.HTTPStatusError as e:
        logger.error(f"Tavily API error: {e}")
        return json.dumps({"error": f"Search API error: {e.response.status_code}"})
    except Exception as e:
        logger.error(f"Image search error: {e}")
        return json.dumps({"error": str(e)})


@tool
def search_financial_visuals(
    company_or_topic: str,
    visual_type: Literal["revenue", "earnings", "stock", "market_share", "forecast", "comparison", "industry_trend"] = "revenue",
    time_period: Optional[str] = None,
) -> str:
    """
    Search for specific types of financial and industry visualizations.
    
    A convenience tool for common chart searches. Automatically constructs
    optimized queries for different visualization types.
    
    Args:
        company_or_topic: Company name, ticker, or market topic
                         Examples: "Hexcel", "HXL", "carbon fiber industry"
        visual_type: Type of visualization:
            - "revenue": Revenue trends and breakdowns
            - "earnings": EPS, net income charts
            - "stock": Stock price charts
            - "market_share": Market share comparisons
            - "forecast": Future projections
            - "comparison": Company vs competitors
            - "industry_trend": Broader industry/market trends
        time_period: Optional time context (e.g., "2024", "Q3 2024", "5 year")
    
    Returns:
        JSON with images. Use interpret_chart on URLs to extract data.
    """
    logger.info(f"Financial visual search: {company_or_topic} - {visual_type}")
    
    # Build optimized query based on visual type
    query_templates = {
        "revenue": f"{company_or_topic} revenue growth chart",
        "earnings": f"{company_or_topic} earnings EPS chart",
        "stock": f"{company_or_topic} stock price chart",
        "market_share": f"{company_or_topic} market share pie chart comparison",
        "forecast": f"{company_or_topic} forecast projection chart",
        "comparison": f"{company_or_topic} vs competitors comparison chart",
        "industry_trend": f"{company_or_topic} market trend industry chart",
    }
    
    base_query = query_templates.get(visual_type, f"{company_or_topic} financial chart")
    
    # Add time period if specified
    if time_period:
        base_query = f"{base_query} {time_period}"
    
    # Use the main search_images tool
    return search_images.invoke({
        "query": base_query,
        "max_images": 5,
        "search_depth": "advanced"
    })


# =============================================================================
# INTERPRETATION TOOLS
# =============================================================================

@tool
def interpret_chart(
    image_url: str,
    context: Optional[str] = None,
) -> str:
    """
    Analyze a chart or graph image and extract structured data using AI vision.
    
    Use this AFTER search_images or search_financial_visuals to understand
    what a chart actually shows. Only call this on charts that are highly
    relevant to your analysis - each call takes 2-3 seconds.
    
    Args:
        image_url: URL of the chart/graph image to analyze
        context: Optional context about what you're looking for
                 (e.g., "Looking for carbon fiber pricing trends")
    
    Returns:
        JSON with structured interpretation including:
        - chart_type: Type of visualization (bar, line, pie, etc.)
        - description: What the chart shows
        - data_points: Key values extracted from the chart
        - caption: One-sentence summary suitable for reports
        - confidence: How readable/clear the chart was
    """
    logger.info(f"Interpreting chart: {image_url[:80]}...")
    
    try:
        # Fetch and encode the image
        image_b64, media_type = _fetch_image_as_base64(image_url)
        
        # Build the interpretation prompt
        context_section = f"\n\nContext from the analyst: {context}" if context else ""
        
        interpretation_prompt = f"""Analyze this chart, graph, or data visualization and extract structured information.

Provide your analysis in this exact JSON format:
{{
    "chart_type": "bar|line|pie|table|scatter|area|combo|other",
    "title": "Chart title if visible, or null if not visible",
    "x_axis": "What the x-axis represents, or null if not applicable",
    "y_axis": "What the y-axis represents, or null if not applicable",
    "description": "2-3 sentence description of what this chart shows and its key message",
    "data_points": [
        {{"label": "Category or time period", "value": "The value with units", "note": "Optional context"}}
    ],
    "trends_observed": ["List of trends or patterns visible in the data"],
    "key_takeaway": "The single most important insight someone should get from this chart",
    "caption": "A one-sentence caption suitable for including in an executive report",
    "data_freshness": "The time period or date the data represents, if visible",
    "source_attribution": "Data source if credited in the chart, or null",
    "confidence": "high|medium|low",
    "confidence_reason": "Brief explanation of confidence rating"
}}

Guidelines:
- Extract specific numbers and values when visible
- For trends, note direction (increasing/decreasing) and rough magnitude
- If the chart is low-resolution or values are hard to read, still extract what you can
- Rate confidence as "low" if significant data is unreadable, "medium" if some values are estimated, "high" if clearly readable
- Keep data_points to the most important 5-10 values, not every single bar/point
{context_section}

Respond ONLY with valid JSON, no additional text or markdown formatting."""

        # Call Claude vision
        client = _get_anthropic_client()
        
        message = client.messages.create(
            model=VISION_MODEL,
            max_tokens=1500,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_b64
                            }
                        },
                        {
                            "type": "text",
                            "text": interpretation_prompt
                        }
                    ]
                }
            ]
        )
        
        # Parse the response
        response_text = message.content[0].text.strip()
        
        # Clean up potential markdown code blocks
        if response_text.startswith("```"):
            response_text = re.sub(r'^```(?:json)?\n?', '', response_text)
            response_text = re.sub(r'\n?```$', '', response_text)
        
        interpretation = json.loads(response_text)
        
        # Add metadata to response
        interpretation["image_url"] = image_url
        interpretation["interpretation_model"] = VISION_MODEL
        
        logger.info(f"Chart interpreted successfully: {interpretation.get('chart_type', 'unknown')} - {interpretation.get('confidence', 'unknown')} confidence")
        
        return json.dumps(interpretation, indent=2)
        
    except httpx.HTTPStatusError as e:
        logger.error(f"Failed to fetch image: {e}")
        return json.dumps({
            "error": f"Could not fetch image: HTTP {e.response.status_code}",
            "image_url": image_url,
            "suggestion": "The image URL may be blocked or expired. Try a different image."
        })
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse interpretation response: {e}")
        return json.dumps({
            "error": "Chart interpretation response was not valid JSON",
            "raw_response": response_text[:500] if 'response_text' in locals() else None,
            "image_url": image_url,
            "suggestion": "The chart may be too complex or unclear. Try a different image."
        })
    except anthropic.APIError as e:
        logger.error(f"Anthropic API error during interpretation: {e}")
        return json.dumps({
            "error": f"Vision API error: {str(e)}",
            "image_url": image_url
        })
    except Exception as e:
        logger.error(f"Chart interpretation error: {e}")
        return json.dumps({
            "error": str(e),
            "image_url": image_url
        })


@tool
def interpret_multiple_charts(
    image_urls: List[str],
    context: Optional[str] = None,
    max_charts: int = 3,
) -> str:
    """
    Interpret multiple charts in sequence, useful for comparative analysis.
    
    Use when you have several charts on the same topic and want to understand
    them together. Limits to max_charts to control latency.
    
    Args:
        image_urls: List of chart image URLs to interpret
        context: Shared context for all interpretations
        max_charts: Maximum number to interpret (default 3, max 5)
    
    Returns:
        JSON with interpretations for each chart plus a comparative summary.
    """
    logger.info(f"Interpreting {len(image_urls)} charts (max {max_charts})")
    
    # Limit the number of charts
    max_charts = min(max(1, max_charts), 5)
    urls_to_process = image_urls[:max_charts]
    
    interpretations = []
    errors = []
    
    for url in urls_to_process:
        result = interpret_chart.invoke({
            "image_url": url,
            "context": context
        })
        
        try:
            parsed = json.loads(result)
            if "error" in parsed:
                errors.append({"url": url, "error": parsed["error"]})
            else:
                interpretations.append(parsed)
        except json.JSONDecodeError:
            errors.append({"url": url, "error": "Failed to parse interpretation"})
    
    # Generate comparative summary if multiple charts interpreted
    summary = None
    if len(interpretations) >= 2:
        takeaways = [i.get("key_takeaway", "") for i in interpretations if i.get("key_takeaway")]
        if takeaways:
            summary = {
                "charts_analyzed": len(interpretations),
                "combined_insights": takeaways,
                "note": "Consider how these charts relate to each other in your analysis"
            }
    
    return json.dumps({
        "requested": len(image_urls),
        "processed": len(urls_to_process),
        "successful": len(interpretations),
        "failed": len(errors),
        "interpretations": interpretations,
        "errors": errors if errors else None,
        "comparative_summary": summary
    }, indent=2)


# =============================================================================
# COMBINED CONVENIENCE TOOLS
# =============================================================================

@tool
def search_and_interpret_charts(
    query: str,
    context: Optional[str] = None,
    max_results: int = 2,
) -> str:
    """
    Search for charts AND interpret the top results in one call.
    
    Convenience tool that combines search_images + interpret_chart.
    Use when you definitely want interpreted chart data and are willing
    to wait for the extra processing time.
    
    Note: This is slower than search_images alone. Use search_images first
    if you just need to find images to display without interpretation.
    
    Args:
        query: Search query for charts (e.g., "Hexcel revenue trend 2024")
        context: Context to help interpret charts (e.g., "Analyzing carbon fiber market")
        max_results: How many top charts to interpret (1-3, default 2)
    
    Returns:
        JSON with search results and interpretations of top charts.
    """
    logger.info(f"Search and interpret: '{query}' (max_results={max_results})")
    
    # Limit results to control latency
    max_results = min(max(1, max_results), 3)
    
    # First, search for images
    search_result = search_images.invoke({
        "query": query,
        "max_images": max_results + 2,  # Get extras in case some fail
        "search_depth": "advanced"
    })
    
    try:
        search_data = json.loads(search_result)
    except json.JSONDecodeError:
        return json.dumps({"error": "Search failed", "raw": search_result})
    
    if "error" in search_data:
        return json.dumps({"error": search_data["error"], "stage": "search"})
    
    # Get top image URLs
    images = search_data.get("images", [])
    if not images:
        return json.dumps({
            "query": query,
            "images_found": 0,
            "interpretations": [],
            "message": "No relevant chart images found for this query"
        })
    
    # Interpret top results
    urls_to_interpret = [img["url"] for img in images[:max_results]]
    
    interpretations = []
    for url in urls_to_interpret:
        result = interpret_chart.invoke({
            "image_url": url,
            "context": context or query
        })
        
        try:
            parsed = json.loads(result)
            interpretations.append(parsed)
        except json.JSONDecodeError:
            interpretations.append({"url": url, "error": "Interpretation failed"})
    
    # Filter successful interpretations
    successful = [i for i in interpretations if "error" not in i]
    
    return json.dumps({
        "query": query,
        "images_found": search_data.get("images_found", 0),
        "images_interpreted": len(interpretations),
        "successful_interpretations": len(successful),
        "interpretations": interpretations,
        "related_sources": search_data.get("related_sources", [])
    }, indent=2)


# =============================================================================
# TOOL EXPORTS
# =============================================================================

# List of all tools for easy importing
IMAGE_TOOLS = [
    search_images,
    search_financial_visuals,
    interpret_chart,
    interpret_multiple_charts,
    search_and_interpret_charts,
]
