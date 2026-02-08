"""
Site Transcript Resolver
========================

Scrape transcripts directly from podcast websites.
FREE - no API costs.

Handles Transistor.fm, Simplecast, Buzzsprout, and custom sites.
"""

import re
import hashlib
import time
from typing import Optional
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from app.utils.logger import get_logger
from ..models import PodcastEpisode, TranscriptResult, TranscriptSource
from .base import TranscriptResolver, ResolutionResult

logger = get_logger(__name__)


class SiteTranscriptResolver(TranscriptResolver):
    """Scrape transcripts from podcast websites. FREE."""

    TRANSCRIPT_SELECTORS = [
        {'class': re.compile(r'transcript', re.I)},
        {'id': re.compile(r'transcript', re.I)},
        {'data-controller': 'transcript'},
        {'class': 'episode-transcript'},
        {'class': 'show-notes-transcript'},
        {'class': re.compile(r'episode-body|episode-content', re.I)},
        {'class': 'podcast-transcript'},
    ]

    MIN_TRANSCRIPT_LENGTH = 500

    def __init__(self, http_timeout: int = 30):
        self.http_timeout = http_timeout
        self._http_client: Optional[httpx.AsyncClient] = None

    @property
    def name(self) -> str:
        return "site_transcript"

    @property
    def is_paid(self) -> bool:
        return False

    async def _get_http_client(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                timeout=self.http_timeout,
                follow_redirects=True,
                headers={'User-Agent': 'Mozilla/5.0 (compatible; C1IntelBot/1.0)'},
            )
        return self._http_client

    async def resolve(self, episode: PodcastEpisode) -> ResolutionResult:
        start_time = time.time()

        if not episode.website_url:
            return ResolutionResult(success=False, error_message="No website URL available")

        http = await self._get_http_client()

        try:
            response = await http.get(episode.website_url)
            response.raise_for_status()
        except httpx.HTTPError as e:
            return ResolutionResult(success=False, error_message=f"HTTP error: {str(e)}")

        soup = BeautifulSoup(response.text, 'html.parser')

        # Try each selector
        transcript_text = None
        for selector in self.TRANSCRIPT_SELECTORS:
            elem = soup.find(['div', 'section', 'article', 'main'], selector)
            if elem:
                text = self._extract_text(elem)
                if text and len(text) >= self.MIN_TRANSCRIPT_LENGTH:
                    transcript_text = text
                    break

        # Look for dedicated transcript links
        if not transcript_text:
            transcript_link = soup.find('a', href=re.compile(r'transcript', re.I))
            if transcript_link:
                href = transcript_link.get('href')
                if href:
                    transcript_text = await self._fetch_transcript_page(href, episode.website_url, http)

        # Fall back to large text block
        if not transcript_text:
            transcript_text = self._find_large_text_block(soup)

        if not transcript_text or len(transcript_text) < self.MIN_TRANSCRIPT_LENGTH:
            return ResolutionResult(success=False, error_message="No transcript found on page")

        transcript_text = self._clean_transcript(transcript_text)

        # Check for speaker labels in the scraped text
        has_speakers = bool(re.search(r'^[A-Z][a-zA-Z\s]+:', transcript_text, re.MULTILINE))

        transcript = TranscriptResult(
            full_text=transcript_text,
            source=TranscriptSource.SITE_SCRAPE,
            has_speaker_labels=has_speakers,
            word_count=len(transcript_text.split()),
            cost_usd=0.0,
        )

        processing_time = time.time() - start_time
        logger.info(
            f"[SITE] Resolved transcript for {episode.title[:40]}... "
            f"({len(transcript_text)} chars, has_speakers={has_speakers}, {processing_time:.1f}s)"
        )

        return ResolutionResult(
            success=True,
            transcript=transcript,
            cost_usd=0.0,
            processing_time_seconds=processing_time,
        )

    async def _fetch_transcript_page(
        self, transcript_url: str, base_url: str, http: httpx.AsyncClient
    ) -> Optional[str]:
        full_url = urljoin(base_url, transcript_url)
        try:
            response = await http.get(full_url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            main = soup.find('main') or soup.find('article') or soup.body
            if main:
                return self._extract_text(main)
        except httpx.HTTPError as e:
            logger.debug(f"[SITE] Failed to fetch transcript page: {e}")
        return None

    def _find_large_text_block(self, soup: BeautifulSoup) -> Optional[str]:
        candidates = []
        for tag in ['div', 'article', 'section']:
            for elem in soup.find_all(tag):
                text = self._extract_text(elem)
                if len(text) >= self.MIN_TRANSCRIPT_LENGTH:
                    html_len = len(str(elem))
                    text_density = len(text) / max(html_len, 1)
                    candidates.append((text_density, text))
        if candidates:
            candidates.sort(reverse=True, key=lambda x: x[0])
            if candidates[0][0] > 0.1:
                return candidates[0][1]
        return None

    def _extract_text(self, element) -> str:
        for tag in element.find_all(['script', 'style', 'nav', 'footer', 'header', 'aside', 'form']):
            tag.decompose()
        text = element.get_text(separator='\n', strip=True)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    def _clean_transcript(self, text: str) -> str:
        boilerplate_patterns = [
            r'Subscribe to.*podcast',
            r'Follow us on.*',
            r'Rate and review.*',
            r'Share this episode.*',
            r'Listen on.*Apple.*Spotify',
        ]
        for pattern in boilerplate_patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    def estimate_cost(self, episode: PodcastEpisode) -> float:
        return 0.0

    def can_handle(self, episode: PodcastEpisode) -> bool:
        return episode.website_url is not None

    async def close(self):
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
