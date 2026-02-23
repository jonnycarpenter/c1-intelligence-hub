"""
Image Enrichment Service for Data Pipeline
===========================================

Extracts, classifies, and stores images (charts, graphs, visualizations) from
ingested articles using:
1. Tavily's image search for finding related visualizations
2. Claude's vision capabilities for OCR and classification

Images are stored with metadata including:
- Source article reference
- AI-generated description
- Classification (chart type, data shown)
- Extracted text/data points via OCR

Use cases:
- 30-day executive briefings with embedded visuals
- Research tab chart/graph displays
- Visual trend tracking
"""

import asyncio
import base64
import hashlib
import json
import logging
import re
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Dict, Any, Optional, Literal
from urllib.parse import urlparse

import httpx
from anthropic import AsyncAnthropic  # Keep for vision API (complex multimodal)

from app.utils.resilient_llm import get_resilient_async_client
from app.config.settings import settings

logger = logging.getLogger(__name__)


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class ExtractedImage:
    """An image extracted and classified from content."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    # Source reference
    article_id: Optional[str] = None
    article_title: Optional[str] = None
    article_url: Optional[str] = None
    
    # Image data
    url: str = ""
    image_hash: str = ""  # For deduplication
    
    # AI Classification
    image_type: str = "unknown"  # chart, graph, infographic, photo, diagram, table
    chart_type: Optional[str] = None  # line, bar, pie, area, scatter, candlestick, etc.
    
    # AI-generated description
    description: str = ""
    alt_text: str = ""  # Short accessibility text
    
    # OCR extracted content
    extracted_text: Optional[str] = None
    extracted_data_points: List[Dict[str, Any]] = field(default_factory=list)
    
    # Classification
    topics: List[str] = field(default_factory=list)  # e.g., ["revenue", "market_share", "forecast"]
    companies: List[str] = field(default_factory=list)
    industries: List[str] = field(default_factory=list)
    time_period: Optional[str] = None  # e.g., "Q3 2024", "2020-2025"
    
    # Quality/relevance
    relevance_score: float = 0.0
    quality_score: float = 0.0  # Based on resolution, clarity
    
    # Metadata
    source_domain: str = ""
    width: Optional[int] = None
    height: Optional[int] = None
    format: Optional[str] = None  # png, jpg, svg, etc.
    
    # Timestamps
    extracted_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "id": self.id,
            "article_id": self.article_id,
            "article_title": self.article_title,
            "article_url": self.article_url,
            "url": self.url,
            "image_hash": self.image_hash,
            "image_type": self.image_type,
            "chart_type": self.chart_type,
            "description": self.description,
            "alt_text": self.alt_text,
            "extracted_text": self.extracted_text,
            "extracted_data_points": self.extracted_data_points,
            "topics": self.topics,
            "companies": self.companies,
            "industries": self.industries,
            "time_period": self.time_period,
            "relevance_score": self.relevance_score,
            "quality_score": self.quality_score,
            "source_domain": self.source_domain,
            "width": self.width,
            "height": self.height,
            "format": self.format,
            "extracted_at": self.extracted_at.isoformat(),
        }


# =============================================================================
# Constants
# =============================================================================

# Tavily API endpoint
TAVILY_SEARCH_URL = "https://api.tavily.com/search"

# Chart/visualization URL patterns (to prioritize)
CHART_URL_PATTERNS = [
    r'chart', r'graph', r'tradingview', r'stockcharts', r'highcharts',
    r'finance\.yahoo', r'seekingalpha', r'finviz', r'marketwatch',
    r'bloomberg', r'reuters', r'statista', r'tradingeconomics',
    r'simplywall', r'macrotrends', r'ycharts', r'earnings', r'revenue'
]

# Patterns to filter out (logos, icons, etc.)
SKIP_PATTERNS = [
    'logo', 'icon', 'avatar', 'profile', 'button', 'sprite',
    'ad-', 'banner', 'sponsor', 'tracking', 'pixel', 'spacer',
    'social', 'facebook', 'twitter', 'linkedin', 'share',
    'arrow', 'caret', 'chevron', 'close', 'menu', 'thumb',
    'emoji', 'badge', 'favicon', 'placeholder', 'loading',
    '1x1', 'transparent', 'blank'
]

# Minimum image dimensions (filter out tiny images)
MIN_IMAGE_WIDTH = 200
MIN_IMAGE_HEIGHT = 150


# =============================================================================
# Image Enrichment Service
# =============================================================================

class ImageEnrichmentService:
    """
    Service for extracting, classifying, and storing images from articles.
    
    Pipeline:
    1. Search for related images via Tavily (or extract from article content)
    2. Validate and filter images (remove logos, icons, check accessibility)
    3. Classify images using Claude's vision (chart type, content description)
    4. Extract text/data via OCR
    5. Store with full metadata
    """
    
    # Vision classification prompt
    CLASSIFICATION_PROMPT = """Analyze this image and provide a detailed classification.

Context: This image was found in an article about the composites industry, advanced materials, 
or related companies. We're looking for charts, graphs, infographics, and data visualizations.

Provide your analysis in JSON format with these fields:

{
    "image_type": "chart|graph|infographic|diagram|table|photo|other",
    "chart_type": "line|bar|pie|area|scatter|candlestick|waterfall|treemap|heatmap|sankey|null",
    "description": "Detailed 2-3 sentence description of what this image shows",
    "alt_text": "Short 10-15 word accessibility description",
    "extracted_text": "Any text/labels visible in the image",
    "data_points": [{"label": "...", "value": "...", "unit": "..."}],
    "topics": ["revenue", "market_share", "forecast", "comparison", "trend", etc.],
    "companies": ["Company names visible or referenced"],
    "industries": ["aerospace", "automotive", "wind_energy", "marine", "construction", etc.],
    "time_period": "Time period shown (e.g., 'Q3 2024', '2020-2025', null if not visible)",
    "relevance_score": 0.0-1.0,
    "quality_score": 0.0-1.0,
    "is_useful": true|false
}

Focus on:
- Financial charts (revenue, earnings, stock prices)
- Market data (market size, market share, forecasts)
- Industry trends and comparisons
- Material/product demand projections

If the image is NOT a useful chart/visualization (e.g., a stock photo, logo, or irrelevant image), 
set is_useful to false and provide minimal classification.

Respond with ONLY valid JSON, no markdown or explanation."""
    
    def __init__(
        self,
        tavily_api_key: str = None,
        anthropic_api_key: str = None,
        max_images_per_article: int = 3,
        enable_vision_classification: bool = True,
    ):
        self.tavily_api_key = tavily_api_key or settings.tavily_api_key
        self.anthropic_api_key = anthropic_api_key or settings.anthropic_api_key
        self.max_images_per_article = max_images_per_article
        self.enable_vision_classification = enable_vision_classification
        
        # HTTP client
        self._http_client = None
        
        # Anthropic client for vision
        self._anthropic_client = None
        
        # Image hash cache for deduplication
        self._image_hash_cache: set = set()
    
    @property
    def http_client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
        return self._http_client
    
    @property
    def anthropic_client(self) -> AsyncAnthropic:
        if self._anthropic_client is None:
            self._anthropic_client = AsyncAnthropic(api_key=self.anthropic_api_key)
        return self._anthropic_client
    
    async def close(self):
        """Close HTTP clients."""
        if self._http_client:
            await self._http_client.aclose()
        self._http_client = None
    
    # -------------------------------------------------------------------------
    # Main Entry Points
    # -------------------------------------------------------------------------
    
    async def enrich_article(
        self,
        article_id: str,
        article_title: str,
        article_url: str,
        article_summary: str,
        companies: List[str] = None,
        industries: List[str] = None,
    ) -> List[ExtractedImage]:
        """
        Enrich a single article with relevant images.
        
        Uses article context to search for relevant charts/visualizations,
        then classifies and stores them.
        """
        logger.info(f"Enriching article with images: {article_title[:60]}...")
        
        images = []
        
        try:
            # Build search query from article context
            search_query = self._build_image_query(
                title=article_title,
                summary=article_summary,
                companies=companies or [],
            )
            
            # Search for related images via Tavily
            raw_images = await self._search_images(search_query)
            
            if not raw_images:
                logger.debug(f"No images found for: {article_title[:40]}")
                return []
            
            # Score and filter images
            filtered_images = self._score_and_filter_images(raw_images, search_query)
            
            # Limit to max per article
            candidates = filtered_images[:self.max_images_per_article + 2]  # Get extras in case some fail
            
            # Validate and fetch image metadata
            validated = await self._validate_images(candidates)
            
            # Classify each image with vision AI
            for img_data in validated[:self.max_images_per_article]:
                try:
                    extracted = await self._classify_image(
                        image_url=img_data['url'],
                        article_id=article_id,
                        article_title=article_title,
                        article_url=article_url,
                        context_companies=companies,
                        context_industries=industries,
                    )
                    
                    if extracted and extracted.relevance_score >= 0.3:
                        images.append(extracted)
                        
                except Exception as e:
                    logger.warning(f"Failed to classify image {img_data['url'][:50]}: {e}")
                    continue
            
            logger.info(f"Extracted {len(images)} images for article: {article_title[:40]}")
            
        except Exception as e:
            logger.error(f"Image enrichment failed for {article_title[:40]}: {e}")
        
        return images
    
    async def enrich_articles_batch(
        self,
        articles: List[Dict[str, Any]],
        max_concurrent: int = 3,
    ) -> Dict[str, List[ExtractedImage]]:
        """
        Enrich multiple articles with images.
        
        Args:
            articles: List of article dicts with keys:
                - id, title, url, summary, companies, industries
            max_concurrent: Max concurrent enrichment tasks
            
        Returns:
            Dict mapping article_id -> list of ExtractedImage
        """
        logger.info(f"Enriching {len(articles)} articles with images...")
        
        results: Dict[str, List[ExtractedImage]] = {}
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def enrich_one(article: Dict) -> tuple:
            async with semaphore:
                images = await self.enrich_article(
                    article_id=article.get('id', ''),
                    article_title=article.get('title', ''),
                    article_url=article.get('url', ''),
                    article_summary=article.get('summary', ''),
                    companies=article.get('companies', []),
                    industries=article.get('industries', []),
                )
                return article.get('id', ''), images
        
        tasks = [enrich_one(a) for a in articles]
        completed = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in completed:
            if isinstance(result, Exception):
                logger.error(f"Article enrichment failed: {result}")
                continue
            article_id, images = result
            if images:
                results[article_id] = images
        
        total_images = sum(len(imgs) for imgs in results.values())
        logger.info(f"Enriched {len(results)} articles with {total_images} total images")
        
        return results
    
    async def search_images_for_topic(
        self,
        topic: str,
        max_images: int = 5,
        search_depth: str = "advanced",
    ) -> List[ExtractedImage]:
        """
        Search for images related to a specific topic (e.g., for briefings).
        
        Useful for finding charts/graphs to illustrate specific points in
        executive briefings or research reports.
        """
        logger.info(f"Searching images for topic: {topic}")
        
        # Enhance query for visualization focus
        enhanced_query = f"{topic} chart graph visualization"
        
        raw_images = await self._search_images(
            query=enhanced_query,
            search_depth=search_depth,
            max_results=max_images * 2,
        )
        
        if not raw_images:
            return []
        
        # Score and filter
        filtered = self._score_and_filter_images(raw_images, topic)
        validated = await self._validate_images(filtered[:max_images + 3])
        
        # Classify
        images = []
        for img_data in validated[:max_images]:
            try:
                extracted = await self._classify_image(
                    image_url=img_data['url'],
                    article_id=None,
                    article_title=topic,
                    article_url=None,
                )
                if extracted and extracted.relevance_score >= 0.3:
                    images.append(extracted)
            except Exception as e:
                logger.warning(f"Classification failed: {e}")
                continue
        
        return images
    
    # -------------------------------------------------------------------------
    # Image Search (Tavily)
    # -------------------------------------------------------------------------
    
    async def _search_images(
        self,
        query: str,
        search_depth: str = "advanced",
        max_results: int = 10,
    ) -> List[str]:
        """Search for images using Tavily API."""
        if not self.tavily_api_key:
            logger.warning("Tavily API key not configured, skipping image search")
            return []
        
        try:
            payload = {
                "api_key": self.tavily_api_key,
                "query": query,
                "search_depth": search_depth,
                "include_images": True,
                "include_answer": False,
                "max_results": 5,  # We mainly want the images
            }
            
            response = await self.http_client.post(TAVILY_SEARCH_URL, json=payload)
            response.raise_for_status()
            data = response.json()
            
            return data.get("images", [])
            
        except Exception as e:
            logger.error(f"Tavily image search error: {e}")
            return []
    
    # -------------------------------------------------------------------------
    # Image Filtering & Validation
    # -------------------------------------------------------------------------
    
    def _build_image_query(
        self,
        title: str,
        summary: str,
        companies: List[str],
    ) -> str:
        """Build an optimized search query for finding relevant images."""
        # Extract key terms from title
        query_parts = []
        
        # Add first company if available
        if companies:
            query_parts.append(companies[0])
        
        # Add key terms from title (skip common words)
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with'}
        title_words = [w for w in title.split()[:8] if w.lower() not in stop_words and len(w) > 2]
        query_parts.extend(title_words[:4])
        
        # Add visualization keywords
        query_parts.append("chart")
        
        return " ".join(query_parts)
    
    def _score_and_filter_images(
        self,
        images: List[str],
        query: str,
    ) -> List[Dict[str, Any]]:
        """Score images by relevance and filter out junk."""
        query_terms = [t.lower() for t in query.split() if len(t) > 2]
        scored = []
        
        for url in images:
            if not url or not isinstance(url, str):
                continue
            
            url_lower = url.lower()
            
            # Skip if matches any skip pattern
            if any(p in url_lower for p in SKIP_PATTERNS):
                continue
            
            score = 0
            
            # Bonus for chart-related URL patterns
            for pattern in CHART_URL_PATTERNS:
                if re.search(pattern, url_lower):
                    score += 3
                    break
            
            # Bonus for query terms in URL
            for term in query_terms:
                if term in url_lower:
                    score += 2
            
            # Bonus for image extensions
            if any(ext in url_lower for ext in ['.png', '.jpg', '.jpeg', '.webp']):
                score += 1
            
            # Penalty for generic image hosts (often low quality)
            if any(h in url_lower for h in ['unsplash', 'pexels', 'shutterstock', 'gettyimages']):
                score -= 2
            
            scored.append({'url': url, 'score': score})
        
        # Sort by score descending
        scored.sort(key=lambda x: x['score'], reverse=True)
        return scored
    
    async def _validate_images(
        self,
        images: List[Dict[str, Any]],
        timeout: float = 5.0,
    ) -> List[Dict[str, Any]]:
        """Validate image URLs are accessible and meet size requirements."""
        validated = []
        
        for img in images:
            url = img.get('url', '')
            try:
                # Use HEAD request for efficiency
                response = await self.http_client.head(url, timeout=timeout)
                
                if response.status_code != 200:
                    continue
                
                # Check content type
                content_type = response.headers.get('content-type', '')
                if not content_type.startswith('image/'):
                    continue
                
                # Get content length if available
                content_length = response.headers.get('content-length')
                if content_length and int(content_length) < 5000:  # Skip tiny images (<5KB)
                    continue
                
                # Compute hash for deduplication
                img_hash = hashlib.md5(url.encode()).hexdigest()
                if img_hash in self._image_hash_cache:
                    continue
                self._image_hash_cache.add(img_hash)
                
                img['hash'] = img_hash
                img['content_type'] = content_type
                validated.append(img)
                
            except Exception as e:
                logger.debug(f"Image validation failed for {url[:50]}: {e}")
                continue
        
        return validated
    
    # -------------------------------------------------------------------------
    # Vision Classification (Claude)
    # -------------------------------------------------------------------------
    
    async def _classify_image(
        self,
        image_url: str,
        article_id: Optional[str],
        article_title: str,
        article_url: Optional[str],
        context_companies: List[str] = None,
        context_industries: List[str] = None,
    ) -> Optional[ExtractedImage]:
        """Classify an image using Claude's vision capability."""
        
        if not self.enable_vision_classification:
            # Return basic image without classification
            return ExtractedImage(
                url=image_url,
                article_id=article_id,
                article_title=article_title,
                article_url=article_url,
                image_hash=hashlib.md5(image_url.encode()).hexdigest(),
                source_domain=urlparse(image_url).netloc,
                relevance_score=0.5,
            )
        
        try:
            # Fetch image data
            response = await self.http_client.get(image_url, timeout=15.0)
            response.raise_for_status()
            
            image_data = response.content
            content_type = response.headers.get('content-type', 'image/jpeg')
            
            # Determine media type
            if 'png' in content_type:
                media_type = "image/png"
            elif 'gif' in content_type:
                media_type = "image/gif"
            elif 'webp' in content_type:
                media_type = "image/webp"
            else:
                media_type = "image/jpeg"
            
            # Encode image as base64
            image_b64 = base64.standard_b64encode(image_data).decode("utf-8")
            
            # Call Claude vision
            message = await self.anthropic_client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1024,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": image_b64,
                                },
                            },
                            {
                                "type": "text",
                                "text": self.CLASSIFICATION_PROMPT,
                            }
                        ],
                    }
                ],
            )
            
            # Parse response
            response_text = message.content[0].text
            
            # Clean JSON from potential markdown
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]
            
            classification = json.loads(response_text.strip())
            
            # Check if image is useful
            if not classification.get('is_useful', True):
                logger.debug(f"Image classified as not useful: {image_url[:50]}")
                return None
            
            # Build ExtractedImage
            return ExtractedImage(
                article_id=article_id,
                article_title=article_title,
                article_url=article_url,
                url=image_url,
                image_hash=hashlib.md5(image_url.encode()).hexdigest(),
                image_type=classification.get('image_type', 'unknown'),
                chart_type=classification.get('chart_type'),
                description=classification.get('description', ''),
                alt_text=classification.get('alt_text', ''),
                extracted_text=classification.get('extracted_text'),
                extracted_data_points=classification.get('data_points', []),
                topics=classification.get('topics', []),
                companies=classification.get('companies', []) or context_companies or [],
                industries=classification.get('industries', []) or context_industries or [],
                time_period=classification.get('time_period'),
                relevance_score=classification.get('relevance_score', 0.5),
                quality_score=classification.get('quality_score', 0.5),
                source_domain=urlparse(image_url).netloc,
            )
            
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse vision response: {e}")
            return None
        except Exception as e:
            logger.error(f"Vision classification error for {image_url[:50]}: {e}")
            return None
    
    # -------------------------------------------------------------------------
    # Utility Methods
    # -------------------------------------------------------------------------
    
    def clear_hash_cache(self):
        """Clear the image hash cache."""
        self._image_hash_cache.clear()
