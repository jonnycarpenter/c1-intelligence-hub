"""
Podcast Ingestion Pipeline
===========================

Standalone async orchestrator for podcast quote ingestion.

Steps:
1. Discover episodes from RSS feeds
2. Dedup against BigQuery podcast_episodes table (by guid)
3. Resolve transcripts (YouTube -> Site -> AssemblyAI)
4. Extract quotes with C1 composites theme taxonomy
5. Store episodes + quotes in BigQuery
"""

import time
from typing import List, Optional, Dict, Any

from app.utils.logger import get_logger
from app.config.settings import settings
from app.db.gcp_storage import get_storage

from .config import C1_PODCAST_FEEDS, get_feed_by_id, get_active_feeds
from .models import (
    PodcastFeed, PodcastEpisode, PodcastEpisodeRecord,
    ProcessingStatus, TranscriptSource,
)
from .discovery import RSSDiscovery
from .resolvers import (
    YouTubeTranscriptResolver,
    SiteTranscriptResolver,
    AssemblyAIResolver,
    ResolutionChain,
    ResolutionConfig,
)
from .quote_extractor import QuoteExtractor

logger = get_logger(__name__)


class PodcastPipeline:
    """
    End-to-end podcast ingestion pipeline.

    Discovers episodes, resolves transcripts with quality-gated
    fallback chain, extracts speaker-attributed quotes, and stores
    everything in BigQuery.
    """

    def __init__(self, require_speaker_labels: bool = True):
        self.require_speaker_labels = require_speaker_labels
        self.rss_discovery = RSSDiscovery()
        self.quote_extractor = QuoteExtractor()
        self.resolution_chain: Optional[ResolutionChain] = None

    def _setup_resolution_chain(self, allow_paid: bool = True):
        """Initialize the resolution chain."""
        resolvers = {
            "youtube_transcript": YouTubeTranscriptResolver(),
            "site_transcript": SiteTranscriptResolver(),
            "assemblyai": AssemblyAIResolver(),
        }

        config = ResolutionConfig(
            require_speaker_labels=self.require_speaker_labels,
            allow_paid_resolvers=allow_paid,
        )

        self.resolution_chain = ResolutionChain(resolvers=resolvers, config=config)
        logger.info(
            f"[PODCAST_PIPELINE] Resolution chain configured: "
            f"resolvers={list(resolvers.keys())}, require_speakers={config.require_speaker_labels}"
        )

    async def run(
        self,
        podcast_ids: Optional[List[str]] = None,
        days: int = 14,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Run the podcast ingestion pipeline.

        Args:
            podcast_ids: Specific podcast IDs to process (None = all active feeds)
            days: Number of days back to fetch episodes
            dry_run: If True, discover episodes but skip transcription/extraction

        Returns:
            Stats dict with episodes_discovered, episodes_transcribed,
            quotes_extracted, total_cost_usd, errors
        """
        pipeline_start = time.time()
        self._setup_resolution_chain(allow_paid=not dry_run)

        # Get storage
        storage = await get_storage()

        # Select feeds
        if podcast_ids:
            feeds_data = [get_feed_by_id(pid) for pid in podcast_ids]
        else:
            feeds_data = get_active_feeds()

        feeds = [PodcastFeed(**f) for f in feeds_data]

        logger.info(
            f"[PODCAST_PIPELINE] START: processing {len(feeds)} podcasts, "
            f"days={days}, dry_run={dry_run}"
        )

        stats = {
            "podcasts_processed": 0,
            "episodes_discovered": 0,
            "episodes_new": 0,
            "episodes_transcribed": 0,
            "quotes_extracted": 0,
            "total_cost_usd": 0.0,
            "errors": [],
        }

        for feed in feeds:
            try:
                feed_stats = await self._process_feed(
                    feed=feed,
                    days=days,
                    dry_run=dry_run,
                    storage=storage,
                )
                stats["podcasts_processed"] += 1
                stats["episodes_discovered"] += feed_stats["episodes_discovered"]
                stats["episodes_new"] += feed_stats["episodes_new"]
                stats["episodes_transcribed"] += feed_stats["episodes_transcribed"]
                stats["quotes_extracted"] += feed_stats["quotes_extracted"]
                stats["total_cost_usd"] += feed_stats["cost_usd"]
            except Exception as e:
                error_msg = f"{feed.name}: {type(e).__name__} - {e}"
                stats["errors"].append(error_msg)
                logger.error(f"[PODCAST_PIPELINE] Feed failed: {error_msg}", exc_info=True)

        elapsed = time.time() - pipeline_start
        logger.info(
            f"[PODCAST_PIPELINE] COMPLETE: {elapsed:.1f}s, "
            f"discovered={stats['episodes_discovered']}, "
            f"new={stats['episodes_new']}, "
            f"transcribed={stats['episodes_transcribed']}, "
            f"quotes={stats['quotes_extracted']}, "
            f"cost=${stats['total_cost_usd']:.4f}, "
            f"errors={len(stats['errors'])}"
        )

        # Cleanup
        await self.rss_discovery.close()

        return stats

    async def _process_feed(
        self,
        feed: PodcastFeed,
        days: int,
        dry_run: bool,
        storage,
    ) -> Dict[str, Any]:
        """Process a single podcast feed."""
        feed_stats = {
            "episodes_discovered": 0,
            "episodes_new": 0,
            "episodes_transcribed": 0,
            "quotes_extracted": 0,
            "cost_usd": 0.0,
        }

        # 1. Discover episodes
        episodes = await self.rss_discovery.discover_episodes(feed=feed, days=days)
        feed_stats["episodes_discovered"] = len(episodes)

        if not episodes:
            logger.info(f"[PODCAST_PIPELINE] No episodes found for {feed.name}")
            return feed_stats

        if dry_run:
            logger.info(
                f"[PODCAST_PIPELINE] Dry run - discovered {len(episodes)} episodes for {feed.name}"
            )
            return feed_stats

        # 2. Process each episode
        for episode in episodes:
            # Dedup check
            exists = await storage.check_episode_exists(episode.guid)
            if exists:
                logger.debug(f"[PODCAST_PIPELINE] Skipping (already processed): {episode.title[:40]}")
                continue

            feed_stats["episodes_new"] += 1

            # Create episode record
            ep_record = PodcastEpisodeRecord(
                id=episode.id,
                podcast_id=feed.id,
                podcast_name=feed.name,
                guid=episode.guid,
                title=episode.title,
                description=episode.description,
                audio_url=episode.audio_url,
                audio_duration_seconds=episode.audio_duration_seconds,
                website_url=episode.website_url,
                youtube_video_id=episode.youtube_video_id,
                published_at=episode.published_at,
                guest_name=episode.guest_name,
                guest_title=episode.guest_title,
                guest_company=episode.guest_company,
                processing_status=ProcessingStatus.DISCOVERED.value,
            )

            # 3. Resolve transcript
            logger.info(f"[PODCAST_PIPELINE] Resolving transcript: {episode.title[:50]}...")

            transcript = await self.resolution_chain.resolve(
                episode=episode,
                podcast_overrides=feed.resolution_override,
            )

            if not transcript:
                ep_record.processing_status = ProcessingStatus.FAILED.value
                ep_record.error_message = "All transcript resolvers failed"
                await storage.store_podcast_episodes([ep_record.to_bq_dict()])
                logger.warning(f"[PODCAST_PIPELINE] Transcript resolution failed: {episode.title[:40]}")
                continue

            # Update episode record with transcript info
            ep_record.transcript_text = transcript.full_text
            ep_record.transcript_source = transcript.source.value
            ep_record.transcript_has_speakers = transcript.has_speaker_labels
            ep_record.transcript_word_count = transcript.word_count
            ep_record.transcript_cost_usd = transcript.cost_usd
            ep_record.processing_status = ProcessingStatus.TRANSCRIBED.value
            feed_stats["episodes_transcribed"] += 1
            feed_stats["cost_usd"] += transcript.cost_usd

            # 4. Extract quotes (requires speaker labels)
            if not transcript.has_speaker_labels:
                logger.warning(
                    f"[PODCAST_PIPELINE] Skipping quote extraction - no speaker labels: {episode.title[:40]}"
                )
                await storage.store_podcast_episodes([ep_record.to_bq_dict()])
                continue

            speaker_info = {
                "guest_name": episode.guest_name,
                "guest_title": episode.guest_title,
                "guest_company": episode.guest_company,
                "hosts": feed.default_hosts,
            }

            extraction_result = await self.quote_extractor.extract_quotes(
                transcript_text=transcript.formatted_text,
                episode_id=episode.id,
                podcast_name=feed.name,
                episode_title=episode.title,
                published_date=episode.published_at,
                episode_url=episode.website_url,
                speaker_info=speaker_info,
            )

            if extraction_result["success"] and extraction_result["quotes"]:
                quotes = extraction_result["quotes"]
                ep_record.quotes_extracted = len(quotes)
                ep_record.processing_status = ProcessingStatus.EXTRACTED.value
                feed_stats["quotes_extracted"] += len(quotes)

                # Store quotes
                quote_rows = [q.to_bq_dict() for q in quotes]
                await storage.store_podcast_quotes(quote_rows)

                logger.info(
                    f"[PODCAST_PIPELINE] Extracted {len(quotes)} quotes from {episode.title[:40]}"
                )
            else:
                ep_record.error_message = extraction_result.get("error_message", "Unknown extraction error")
                logger.warning(
                    f"[PODCAST_PIPELINE] Quote extraction failed: {ep_record.error_message}"
                )

            # 5. Store episode record
            await storage.store_podcast_episodes([ep_record.to_bq_dict()])

        return feed_stats
