"""
RSS Feed Discovery
==================

Parse podcast RSS feeds to discover episodes.
Adapted from REFERENCE_podcast_ingestion/discovery/rss.py for C1 Intelligence Hub.
"""

import re
import hashlib
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import List, Optional, Dict

import httpx

from app.utils.logger import get_logger
from .models import PodcastEpisode, PodcastFeed

logger = get_logger(__name__)


NAMESPACES = {
    'itunes': 'http://www.itunes.com/dtds/podcast-1.0.dtd',
    'content': 'http://purl.org/rss/1.0/modules/content/',
    'podcast': 'https://podcastindex.org/namespace/1.0',
    'atom': 'http://www.w3.org/2005/Atom',
}


class RSSDiscovery:
    """Parse podcast RSS feeds to discover episodes."""

    def __init__(self, http_timeout: int = 30):
        self.http_timeout = http_timeout
        self._http_client: Optional[httpx.AsyncClient] = None

    async def _get_http_client(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                timeout=self.http_timeout,
                follow_redirects=True,
                headers={'User-Agent': 'Mozilla/5.0 (compatible; C1IntelBot/1.0)'},
            )
        return self._http_client

    async def discover_episodes(
        self,
        feed: PodcastFeed,
        days: int = 14,
        limit: Optional[int] = None,
    ) -> List[PodcastEpisode]:
        """
        Fetch episodes from an RSS feed.

        Args:
            feed: Podcast feed configuration
            days: Only fetch episodes from last N days
            limit: Maximum episodes to return

        Returns:
            List of PodcastEpisode objects
        """
        if not feed.rss_url:
            logger.warning(f"[PODCAST_DISCOVERY] No RSS URL for {feed.name}, skipping")
            return []

        since_date = datetime.utcnow() - timedelta(days=days)
        http = await self._get_http_client()

        try:
            response = await http.get(feed.rss_url)
            response.raise_for_status()
        except httpx.HTTPError as e:
            logger.error(f"[PODCAST_DISCOVERY] Failed to fetch {feed.rss_url}: {e}")
            return []

        try:
            root = ET.fromstring(response.text)
        except ET.ParseError as e:
            logger.error(f"[PODCAST_DISCOVERY] Failed to parse {feed.rss_url}: {e}")
            return []

        channel = root.find('channel')
        if channel is None:
            logger.error(f"[PODCAST_DISCOVERY] No channel element in {feed.rss_url}")
            return []

        episodes = []
        for item in channel.findall('item'):
            if limit and len(episodes) >= limit:
                break
            episode = self._parse_episode(item, feed, since_date)
            if episode:
                episodes.append(episode)

        logger.info(
            f"[PODCAST_DISCOVERY] Found {len(episodes)} episodes for {feed.name} "
            f"(since {since_date.strftime('%Y-%m-%d')})"
        )
        return episodes

    def _parse_episode(
        self,
        item: ET.Element,
        feed: PodcastFeed,
        since_date: datetime,
    ) -> Optional[PodcastEpisode]:
        """Parse a single RSS item into a PodcastEpisode."""
        pub_date_str = _get_text(item, 'pubDate')
        pub_date = _parse_date(pub_date_str)

        if not pub_date:
            return None

        # Make timezone-naive for comparison
        if pub_date.tzinfo:
            pub_date = pub_date.replace(tzinfo=None)

        if pub_date < since_date:
            return None

        # Audio from enclosure
        enclosure = item.find('enclosure')
        audio_url = enclosure.get('url') if enclosure is not None else None
        if not audio_url:
            return None

        # GUID
        guid_elem = item.find('guid')
        guid = guid_elem.text if guid_elem is not None and guid_elem.text else audio_url

        # Duration
        duration_str = _get_text(item, 'itunes:duration', NAMESPACES)
        duration_seconds = _parse_duration(duration_str)

        # Website URL
        website_url = _get_text(item, 'link')

        title = _get_text(item, 'title') or "Untitled Episode"

        return PodcastEpisode(
            id=f"ep_{_hash(guid)}",
            podcast_id=feed.id,
            guid=guid,
            title=title,
            description=_get_text(item, 'description'),
            audio_url=audio_url,
            audio_duration_seconds=duration_seconds,
            website_url=website_url,
            published_at=pub_date,
        )

    async def close(self):
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_text(element: ET.Element, tag: str, namespaces: Optional[Dict] = None) -> Optional[str]:
    if namespaces and ':' in tag:
        child = element.find(tag, namespaces)
    else:
        child = element.find(tag)
    return child.text.strip() if child is not None and child.text else None


def _parse_date(date_str: Optional[str]) -> Optional[datetime]:
    if not date_str:
        return None
    try:
        return parsedate_to_datetime(date_str)
    except (ValueError, TypeError):
        return None


def _parse_duration(duration_str: Optional[str]) -> Optional[int]:
    if not duration_str:
        return None
    try:
        return int(duration_str)
    except ValueError:
        pass
    parts = duration_str.split(':')
    try:
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        elif len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
    except ValueError:
        pass
    return None


def _hash(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()[:12]
