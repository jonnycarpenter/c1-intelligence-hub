"""
Wikipedia API Client
====================

Async client for fetching Wikipedia and Wikidata content.
Uses REST API for Wikipedia and Wikidata for structured data.
"""

import asyncio
import re
from typing import Optional, List, Dict, Any

import httpx

from app.utils.logger import get_logger
from app.services.knowledge_base.config import SeederConfig
from app.services.knowledge_base.models import WikiArticle

logger = get_logger(__name__)


class WikipediaClient:
    """
    Client for Wikipedia and Wikidata APIs.
    
    Features:
    - Rate limiting to respect Wikipedia servers
    - Full article content retrieval
    - Category extraction
    - Wikidata structured data
    - Section parsing
    """
    
    def __init__(self, config: SeederConfig):
        self.config = config
        self._rate_semaphore = asyncio.Semaphore(int(config.requests_per_second))
        self._last_request_time = 0.0
    
    async def _rate_limit(self):
        """Enforce rate limiting to be nice to Wikipedia."""
        async with self._rate_semaphore:
            now = asyncio.get_event_loop().time()
            min_interval = 1.0 / self.config.requests_per_second
            wait_time = min_interval - (now - self._last_request_time)
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            self._last_request_time = asyncio.get_event_loop().time()
    
    async def get_article(self, title: str) -> Optional[WikiArticle]:
        """
        Fetch a Wikipedia article by title.
        
        Args:
            title: Wikipedia article title (e.g., "Hexcel", "Carbon fiber")
        
        Returns:
            WikiArticle if found, None otherwise
        """
        if not title:
            return None
        
        await self._rate_limit()
        
        try:
            # Get article summary via REST API
            summary_url = f"{self.config.wiki_api_url}/page/summary/{title.replace(' ', '_')}"
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    summary_url,
                    headers={"User-Agent": self.config.wiki_user_agent},
                    timeout=self.config.request_timeout,
                    follow_redirects=True,
                )
                
                if response.status_code == 404:
                    logger.warning(f"Wikipedia article not found: {title}")
                    return None
                
                response.raise_for_status()
                summary_data = response.json()
            
            # Get full article content
            full_content = await self._get_full_content(title)
            sections = self._parse_sections(full_content) if full_content else {}
            
            # Get Wikidata for structured info
            wikidata_id = summary_data.get("wikibase_item")
            infobox = {}
            if wikidata_id:
                infobox = await self._get_wikidata(wikidata_id)
            
            # Get categories
            categories = await self._get_categories(title)
            
            return WikiArticle(
                title=summary_data.get("title", title),
                page_id=summary_data.get("pageid", 0),
                url=summary_data.get("content_urls", {}).get("desktop", {}).get("page", ""),
                extract=summary_data.get("extract", ""),
                full_text=full_content or summary_data.get("extract", ""),
                sections=sections,
                categories=categories,
                infobox=infobox,
                wikidata_id=wikidata_id,
            )
        
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching Wikipedia article {title}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error fetching Wikipedia article {title}: {e}")
            return None
    
    async def _get_full_content(self, title: str) -> Optional[str]:
        """Get full article text via MediaWiki API."""
        await self._rate_limit()
        
        try:
            params = {
                "action": "query",
                "titles": title,
                "prop": "extracts",
                "explaintext": "1",
                "exsectionformat": "plain",
                "format": "json",
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self.config.wiki_mediawiki_url,
                    params=params,
                    headers={"User-Agent": self.config.wiki_user_agent},
                    timeout=self.config.request_timeout,
                )
                response.raise_for_status()
                data = response.json()
            
            pages = data.get("query", {}).get("pages", {})
            for page_id, page_data in pages.items():
                if page_id != "-1":
                    content = page_data.get("extract", "")
                    # Truncate if too long
                    if len(content) > self.config.max_content_length:
                        content = content[:self.config.max_content_length] + "..."
                    return content
            return None
            
        except Exception as e:
            logger.warning(f"Error getting full content for {title}: {e}")
            return None
    
    async def _get_categories(self, title: str) -> List[str]:
        """Get article categories."""
        await self._rate_limit()
        
        try:
            params = {
                "action": "query",
                "titles": title,
                "prop": "categories",
                "cllimit": "20",
                "format": "json",
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self.config.wiki_mediawiki_url,
                    params=params,
                    headers={"User-Agent": self.config.wiki_user_agent},
                    timeout=self.config.request_timeout,
                )
                response.raise_for_status()
                data = response.json()
            
            pages = data.get("query", {}).get("pages", {})
            categories = []
            
            # Skip internal Wikipedia categories
            skip_patterns = ["articles", "pages", "cs1", "webarchive", "wikipedia", "stub"]
            
            for page_data in pages.values():
                for cat in page_data.get("categories", []):
                    cat_title = cat.get("title", "").replace("Category:", "")
                    if not any(skip in cat_title.lower() for skip in skip_patterns):
                        categories.append(cat_title)
            
            return categories[:10]  # Limit to 10 useful categories
            
        except Exception as e:
            logger.warning(f"Error getting categories for {title}: {e}")
            return []
    
    async def _get_wikidata(self, wikidata_id: str) -> Dict[str, Any]:
        """Get structured data from Wikidata."""
        await self._rate_limit()
        
        try:
            params = {
                "action": "wbgetentities",
                "ids": wikidata_id,
                "props": "claims|labels|descriptions",
                "languages": "en",
                "format": "json",
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self.config.wikidata_api_url,
                    params=params,
                    headers={"User-Agent": self.config.wiki_user_agent},
                    timeout=self.config.request_timeout,
                )
                response.raise_for_status()
                data = response.json()
            
            entity = data.get("entities", {}).get(wikidata_id, {})
            claims = entity.get("claims", {})
            
            result = {}
            
            # Property mappings for useful corporate info
            property_map = {
                "P17": "country",
                "P159": "headquarters",
                "P571": "founded",
                "P452": "industry",
                "P1128": "employees",
                "P856": "website",
                "P154": "logo",
                "P169": "ceo",
                "P749": "parent_company",
                "P355": "subsidiaries",
            }
            
            for prop, name in property_map.items():
                if prop in claims:
                    value = self._get_claim_value(claims[prop])
                    if value:
                        result[name] = value
            
            return result
            
        except Exception as e:
            logger.warning(f"Error getting Wikidata for {wikidata_id}: {e}")
            return {}
    
    def _get_claim_value(self, claim_data: List) -> Optional[Any]:
        """Extract value from Wikidata claim."""
        try:
            mainsnak = claim_data[0].get("mainsnak", {})
            datavalue = mainsnak.get("datavalue", {})
            value = datavalue.get("value")
            
            if isinstance(value, dict):
                # Handle time values (e.g., founded date)
                if "time" in value:
                    time_str = value.get("time", "")
                    match = re.match(r'\+?(\d{4})', time_str)
                    if match:
                        return match.group(1)
                # Handle other complex types
                return value.get("amount") or value.get("text") or value.get("id")
            return value
            
        except (IndexError, KeyError, TypeError):
            return None
    
    def _parse_sections(self, text: str) -> Dict[str, str]:
        """Parse article text into named sections."""
        if not text:
            return {}
        
        sections = {}
        current_section = "Overview"
        current_content = []
        
        for line in text.split('\n'):
            # Match section headers (== Header ==, === Subheader ===, etc.)
            header_match = re.match(r'^={2,}\s*(.+?)\s*={2,}$', line)
            if header_match:
                # Save previous section
                if current_content:
                    content = '\n'.join(current_content).strip()
                    if len(content) > 50:  # Only keep substantial sections
                        sections[current_section] = content[:self.config.max_section_length]
                # Start new section
                current_section = header_match.group(1)
                current_content = []
            else:
                current_content.append(line)
        
        # Save final section
        if current_content:
            content = '\n'.join(current_content).strip()
            if len(content) > 50:
                sections[current_section] = content[:self.config.max_section_length]
        
        return sections
    
    async def test_connection(self) -> bool:
        """Test Wikipedia API connectivity."""
        try:
            article = await self.get_article("Carbon fiber")
            if article:
                logger.info(f"Wikipedia connection OK - got '{article.title}'")
                return True
            return False
        except Exception as e:
            logger.error(f"Wikipedia connection test failed: {e}")
            return False
