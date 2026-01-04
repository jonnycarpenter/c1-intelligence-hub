import asyncio
import re
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any

# Third-party imports
import feedparser
from bs4 import BeautifulSoup

# App imports
from app.models.corpus import RawArticle
from app.ingestion.config import RSS_FEEDS

logger = logging.getLogger(__name__)

# RSS Feed Sources are now imported from config.py

class RSSFetcher:
    """
    Fetches articles from RSS feeds.
    """
    
    def __init__(self, config=None):
        self.config = config
        self.feeds = RSS_FEEDS
        self.max_age_days = getattr(config, 'max_article_age_days', 7) if config else 7
        self.max_per_feed = getattr(config, 'max_articles_per_feed', 20) if config else 20
    
    async def fetch_feed(self, feed_config: Dict[str, Any], days_back: int = None) -> List[RawArticle]:
        """Fetch articles from a single RSS feed"""
        articles = []
        
        # Override max age if days_back is provided (for backfill)
        age_days = days_back if days_back is not None else self.max_age_days
        cutoff_date = datetime.utcnow() - timedelta(days=age_days)
        
        if days_back and days_back > 30:
            logger.warning(f"RSS backfill requested for {days_back} days, but standard RSS feeds usually only retain recent items.")
        
        try:
            logger.info(f"Fetching RSS feed: {feed_config['name']}")
            
            loop = asyncio.get_event_loop()
            parsed = await loop.run_in_executor(
                None, 
                feedparser.parse, 
                feed_config["url"]
            )
            
            if parsed.bozo:
                logger.warning(f"Feed parse warning for {feed_config['name']}: {parsed.bozo_exception}")
            
            filter_keywords = feed_config.get("filter_keywords", [])
            
            # For backfill, we might want to fetch more if the feed supports it (most don't)
            # But we'll at least process everything we get
            entries_to_process = parsed.entries if days_back else parsed.entries[:self.max_per_feed]
            
            for entry in entries_to_process:
                # Parse published date
                published = None
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    published = datetime(*entry.published_parsed[:6])
                elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                    published = datetime(*entry.updated_parsed[:6])
                else:
                    published = datetime.utcnow()
                
                # Skip old articles
                if published < cutoff_date:
                    continue
                
                # Get summary
                summary = ""
                if hasattr(entry, 'summary'):
                    summary = self._clean_html(entry.summary)
                elif hasattr(entry, 'description'):
                    summary = self._clean_html(entry.description)
                elif hasattr(entry, 'content'):
                    # Some feeds put content in content list
                    summary = self._clean_html(entry.content[0].value)
                
                # Apply keyword filter for non-composites feeds
                if filter_keywords:
                    text_to_check = f"{entry.title} {summary}".lower()
                    if not any(kw.lower() in text_to_check for kw in filter_keywords):
                        continue
                
                article = RawArticle(
                    title=entry.title,
                    url=entry.link,
                    summary=summary[:1000],  # Limit summary length
                    published_at=published,
                    source_name=feed_config["name"],
                    source_type="rss",
                    raw_data={
                        "feed_category": feed_config.get("category"),
                        "priority_boost": feed_config.get("priority_boost", 0),
                    }
                )
                articles.append(article)
            
            logger.info(f"Fetched {len(articles)} articles from {feed_config['name']}")
            
        except Exception as e:
            logger.error(f"Error fetching feed {feed_config['name']}: {e}")
        
        return articles
    
    async def fetch_all_feeds(self, days_back: int = None) -> List[RawArticle]:
        """Fetch articles from all configured RSS feeds"""
        all_articles = []
        
        # Fetch feeds concurrently
        tasks = [self.fetch_feed(feed, days_back) for feed in self.feeds]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Feed fetch error: {result}")
            else:
                all_articles.extend(result)
        
        logger.info(f"Total RSS articles fetched: {len(all_articles)}")
        return all_articles
    
    def _clean_html(self, html_text: str) -> str:
        """Remove HTML tags and clean text"""
        if not html_text:
            return ""
        try:
            soup = BeautifulSoup(html_text, 'html.parser')
            text = soup.get_text(separator=' ')
            # Clean up whitespace
            text = re.sub(r'\s+', ' ', text).strip()
            return text
        except Exception:
            return html_text
