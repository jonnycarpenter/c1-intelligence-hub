import asyncio
import logging
from typing import List, Optional
import httpx
from bs4 import BeautifulSoup

from app.models.corpus import RawArticle

logger = logging.getLogger(__name__)

class WebScraper:
    """
    Extracts full article text from URLs.
    """
    
    # User agent to avoid blocks
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }
    
    # Selectors for article content
    CONTENT_SELECTORS = [
        "article",
        '[class*="article-body"]',
        '[class*="article-content"]',
        '[class*="post-content"]',
        '[class*="entry-content"]',
        '[class*="story-body"]',
        "main",
        '[role="main"]',
    ]
    
    # Elements to remove
    REMOVE_SELECTORS = [
        "nav", "header", "footer", "aside",
        '[class*="sidebar"]',
        '[class*="advertisement"]',
        '[class*="related"]',
        '[class*="comment"]',
        '[class*="share"]',
        '[class*="social"]',
        "script", "style", "noscript",
    ]
    
    def __init__(self, timeout: float = 15.0):
        self.timeout = timeout
    
    async def extract_article(self, url: str) -> Optional[str]:
        """Extract full article text from a URL"""
        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                response = await client.get(
                    url,
                    headers=self.HEADERS,
                    timeout=self.timeout
                )
                response.raise_for_status()
                
                html = response.text
                return self._parse_article(html)
        
        except Exception as e:
            logger.warning(f"Failed to extract article from {url}: {e}")
            return None
    
    def _parse_article(self, html: str) -> str:
        """Parse article content from HTML"""
        soup = BeautifulSoup(html, 'html.parser')
        
        # Remove unwanted elements
        for selector in self.REMOVE_SELECTORS:
            for element in soup.select(selector):
                element.decompose()
        
        # Try to find article content
        content = None
        for selector in self.CONTENT_SELECTORS:
            content = soup.select_one(selector)
            if content:
                break
        
        if not content:
            # Fallback to body
            content = soup.body
        
        if not content:
            return ""
        
        # Extract text
        text = content.get_text(separator='\n')
        
        # Clean up
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        text = '\n'.join(lines)
        
        # Limit length
        if len(text) > 10000:
            text = text[:10000] + "..."
        
        return text
    
    async def enrich_articles(
        self, 
        articles: List[RawArticle], 
        max_concurrent: int = 5
    ) -> List[RawArticle]:
        """Enrich multiple articles with full text"""
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def enrich_one(article: RawArticle) -> RawArticle:
            async with semaphore:
                # Skip if we already have substantial text
                if article.full_text and len(article.full_text) > 500:
                    return article
                
                full_text = await self.extract_article(article.url)
                if full_text:
                    article.full_text = full_text
                
                return article
        
        tasks = [enrich_one(article) for article in articles]
        enriched = await asyncio.gather(*tasks)
        
        logger.info(f"Enriched {len([a for a in enriched if a.full_text])} articles with full text")
        return enriched
