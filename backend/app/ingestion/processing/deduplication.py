import logging
import re
import hashlib
from difflib import SequenceMatcher
from typing import Tuple, Dict, Any, Optional, List
from app.models.corpus import RawArticle

logger = logging.getLogger(__name__)

# Source tier ranking for premium source selection (lower = better)
PREMIUM_SOURCES = ["bloomberg", "reuters", "wsj", "wall street journal", "cnbc", "financial times", "barron's", "barrons"]
STANDARD_SOURCES = ["motley fool", "seeking alpha", "zacks", "benzinga", "fox business", "the street", "yahoo finance", "marketwatch"]


def get_source_priority(source_name: str) -> int:
    """Get numeric priority for source ranking (lower = better)."""
    source_lower = source_name.lower() if source_name else ""
    if any(p in source_lower for p in PREMIUM_SOURCES):
        return 1
    elif any(s in source_lower for s in STANDARD_SOURCES):
        return 2
    return 3


class DeduplicationService:
    """
    Prevents duplicate content from being stored.
    
    Supports:
    - URL-based exact matching
    - Title similarity matching (for cross-source duplicates)
    - Article aggregation (grouping same stories from multiple sources)
    """
    
    # Similarity threshold for title matching (0.85 = 85% similar)
    TITLE_SIMILARITY_THRESHOLD = 0.85
    
    def __init__(self, db):
        self.db = db
        self._url_cache: set = set()
        self._title_cache: Dict[str, str] = {}  # normalized_title -> article_id
        self._title_to_articles: Dict[str, List[Dict]] = {}  # For aggregation tracking
    
    async def load_recent_cache(self, hours: int = 168):
        """Load recent URLs and titles into memory cache"""
        try:
            items = await self.db.query_corpus(hours=hours, limit=1000)
            
            for item in items:
                self._url_cache.add(self._normalize_url(item.url))
                self._title_cache[self._normalize_title(item.title)] = item.id
            
            logger.info(f"Loaded {len(self._url_cache)} URLs into dedup cache")
        except Exception as e:
            logger.warning(f"Could not load dedup cache: {e}")
    
    async def check_duplicate(self, article: RawArticle) -> Tuple[bool, Optional[str]]:
        """
        Check if article is a duplicate.
        Returns: (is_duplicate, original_id or None)
        """
        # 1. URL exact match
        normalized_url = self._normalize_url(article.url)
        
        if normalized_url in self._url_cache:
            original_id = await self.db.check_duplicate(article.url)
            if original_id:
                return (True, original_id)
        
        original_id = await self.db.check_duplicate(article.url)
        if original_id:
            self._url_cache.add(normalized_url)
            return (True, original_id)
        
        # 2. Title exact match (normalized)
        normalized_title = self._normalize_title(article.title)
        if normalized_title in self._title_cache:
            return (True, self._title_cache[normalized_title])
        
        # 3. Title similarity match (fuzzy)
        similar_title = self._find_similar_title(normalized_title)
        if similar_title:
            return (True, self._title_cache.get(similar_title))
        
        # Not a duplicate
        self._url_cache.add(normalized_url)
        self._title_cache[normalized_title] = None
        
        return (False, None)
    
    def _find_similar_title(self, normalized_title: str) -> Optional[str]:
        """
        Find a similar title in the cache using fuzzy matching.
        
        Returns the matching cached title if similarity > threshold, else None.
        """
        if not normalized_title or len(normalized_title) < 10:
            return None
        
        for cached_title in self._title_cache.keys():
            if len(cached_title) < 10:
                continue
            
            # Quick length check - skip if lengths are too different
            len_ratio = len(normalized_title) / len(cached_title) if cached_title else 0
            if len_ratio < 0.5 or len_ratio > 2.0:
                continue
            
            # Compute similarity
            similarity = SequenceMatcher(None, normalized_title, cached_title).ratio()
            if similarity >= self.TITLE_SIMILARITY_THRESHOLD:
                logger.debug(f"Title similarity match ({similarity:.2f}): '{normalized_title[:50]}...'")
                return cached_title
        
        return None
    
    def _normalize_url(self, url: str) -> str:
        """Normalize URL for comparison"""
        url = url.lower()
        url = re.sub(r'^https?://', '', url)
        url = re.sub(r'^www\.', '', url)
        url = url.rstrip('/')
        url = url.split('?')[0]
        return url
    
    def _normalize_title(self, title: str) -> str:
        """Normalize title for comparison"""
        title = title.lower()
        title = re.sub(r'[^\w\s]', '', title)
        title = re.sub(r'\s+', ' ', title)
        return title.strip()


class ArticleAggregator:
    """
    Aggregates similar articles from multiple sources into a single entry.
    
    When the same story is published by multiple outlets (e.g., AP wire story
    picked up by Yahoo, CNBC, and local news), this groups them together and
    selects the best source to display.
    
    Output format:
    - Primary article from best source (Bloomberg > Reuters > Yahoo > etc.)
    - coverage_count: total number of sources
    - duplicate_sources: list of other source names (for "+N" display)
    - all_urls: list of all URLs for the story
    """
    
    TITLE_SIMILARITY_THRESHOLD = 0.85
    
    def __init__(self):
        self._groups: Dict[str, List[Dict]] = {}  # normalized_title -> articles
    
    def add_article(self, article: Dict[str, Any]):
        """Add an article to be grouped."""
        title = article.get("title", "")
        normalized = self._normalize_title(title)
        
        if not normalized or len(normalized) < 10:
            # Too short to match meaningfully - treat as unique
            unique_key = f"_unique_{len(self._groups)}"
            self._groups[unique_key] = [article]
            return
        
        # Find existing group with similar title
        matched_key = self._find_matching_group(normalized)
        
        if matched_key:
            self._groups[matched_key].append(article)
        else:
            self._groups[normalized] = [article]
    
    def _find_matching_group(self, normalized_title: str) -> Optional[str]:
        """Find an existing group with similar title."""
        for group_key in self._groups.keys():
            if group_key.startswith("_unique_"):
                continue
            
            # Quick length check
            len_ratio = len(normalized_title) / len(group_key) if group_key else 0
            if len_ratio < 0.5 or len_ratio > 2.0:
                continue
            
            similarity = SequenceMatcher(None, normalized_title, group_key).ratio()
            if similarity >= self.TITLE_SIMILARITY_THRESHOLD:
                return group_key
        
        return None
    
    def _normalize_title(self, title: str) -> str:
        """Normalize title for comparison."""
        title = title.lower()
        title = re.sub(r'[^\w\s]', '', title)
        title = re.sub(r'\s+', ' ', title)
        return title.strip()
    
    def get_aggregated_articles(self) -> List[Dict[str, Any]]:
        """
        Return aggregated articles with best source selection.
        
        Each returned article will have:
        - coverage_count: number of sources
        - duplicate_sources: list of other source names
        - all_urls: list of all URLs
        """
        results = []
        
        for group_key, articles in self._groups.items():
            if len(articles) == 1:
                # Single source - no aggregation needed
                article = articles[0].copy()
                article["coverage_count"] = 1
                article["duplicate_sources"] = []
                article["all_urls"] = [article.get("url", "")]
                results.append(article)
            else:
                # Multiple sources - select best and aggregate
                aggregated = self._select_best_and_aggregate(articles)
                results.append(aggregated)
        
        return results
    
    def _select_best_and_aggregate(self, articles: List[Dict]) -> Dict[str, Any]:
        """Select best source from duplicates and aggregate metadata."""
        # Sort by source priority (lower = better)
        sorted_articles = sorted(
            articles,
            key=lambda a: get_source_priority(a.get("source_name", ""))
        )
        
        best = sorted_articles[0].copy()
        
        # Aggregate all sources and URLs
        all_sources = [a.get("source_name", "") for a in articles]
        all_urls = [a.get("url", "") for a in articles if a.get("url")]
        
        # Duplicate sources excludes the primary
        duplicate_sources = [s for s in all_sources if s != best.get("source_name")]
        
        best["coverage_count"] = len(articles)
        best["duplicate_sources"] = duplicate_sources
        best["all_urls"] = all_urls
        
        logger.debug(f"Aggregated {len(articles)} sources for: {best.get('title', '')[:50]}...")
        
        return best
    
    def clear(self):
        """Clear all groups for a fresh aggregation run."""
        self._groups.clear()
