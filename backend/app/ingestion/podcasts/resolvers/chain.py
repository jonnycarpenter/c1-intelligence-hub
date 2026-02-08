"""
Resolution Chain Orchestrator
=============================

Orchestrates transcript resolution through multiple sources.
Quality gate enforces speaker attribution for quote extraction.

Default chain:
1. youtube_transcript  -> FREE (usually no speaker labels)
2. site_transcript     -> FREE (may have speaker labels)
3. assemblyai          -> PAID (~$0.37/hr) with speaker diarization
"""

import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from app.utils.logger import get_logger
from ..models import PodcastEpisode, TranscriptResult
from .base import TranscriptResolver, ResolutionResult

logger = get_logger(__name__)


@dataclass
class ResolutionConfig:
    """Configuration for transcript resolution."""
    resolver_order: List[str] = field(default_factory=lambda: [
        "youtube_transcript",
        "site_transcript",
        "assemblyai",
    ])
    quality_min_length: int = 500
    quality_min_confidence: float = 0.5
    require_speaker_labels: bool = True
    max_cost_per_episode: float = 1.0
    allow_paid_resolvers: bool = True


class ResolutionChain:
    """
    Orchestrates transcript resolution with quality gates.
    Tries each resolver in order until one passes quality checks.
    """

    def __init__(
        self,
        resolvers: Dict[str, TranscriptResolver],
        config: Optional[ResolutionConfig] = None,
    ):
        self.resolvers = resolvers
        self.config = config or ResolutionConfig()

    async def resolve(
        self,
        episode: PodcastEpisode,
        podcast_overrides: Optional[Dict[str, Any]] = None,
    ) -> Optional[TranscriptResult]:
        """
        Attempt to resolve transcript for an episode.

        Returns TranscriptResult if successful, None if all resolvers failed.
        """
        resolver_order = self._get_resolver_order(podcast_overrides)

        logger.info(
            f"[CHAIN] Resolving: {episode.title[:50]}... "
            f"chain={resolver_order}, require_speakers={self.config.require_speaker_labels}"
        )

        resolvers_attempted = []

        for resolver_name in resolver_order:
            if resolver_name not in self.resolvers:
                logger.warning(f"[CHAIN] Unknown resolver: {resolver_name}")
                continue

            resolver = self.resolvers[resolver_name]

            if not resolver.can_handle(episode):
                logger.debug(f"[CHAIN] Skipping {resolver_name}: can_handle=False")
                continue

            # Cost budget check for paid resolvers
            if resolver.is_paid:
                if not self.config.allow_paid_resolvers:
                    logger.warning(f"[CHAIN] Skipping {resolver_name}: paid resolvers disabled")
                    continue
                estimated_cost = resolver.estimate_cost(episode)
                if estimated_cost > self.config.max_cost_per_episode:
                    logger.warning(
                        f"[CHAIN] Skipping {resolver_name}: estimated ${estimated_cost:.2f} "
                        f"> max ${self.config.max_cost_per_episode:.2f}"
                    )
                    continue

            resolvers_attempted.append(resolver_name)
            logger.info(f"[CHAIN] Attempting resolver: {resolver_name} (paid={resolver.is_paid})")

            attempt_start = time.time()
            try:
                result = await resolver.resolve(episode)
                attempt_duration = time.time() - attempt_start

                if result.success and result.transcript:
                    if self._passes_quality_gates(result.transcript, resolver_name):
                        logger.info(
                            f"[CHAIN] Resolved via {resolver_name} in {attempt_duration:.1f}s, "
                            f"cost=${result.cost_usd:.4f}, "
                            f"speakers={result.transcript.has_speaker_labels}"
                        )
                        return result.transcript
                    else:
                        logger.warning(
                            f"[CHAIN] {resolver_name} failed quality gates "
                            f"(speakers={result.transcript.has_speaker_labels}, "
                            f"len={len(result.transcript.full_text)})"
                        )
                else:
                    logger.warning(
                        f"[CHAIN] {resolver_name} failed: {result.error_message}"
                    )

            except Exception as e:
                logger.error(
                    f"[CHAIN] {resolver_name} threw exception: {e}",
                    exc_info=True,
                )

        logger.error(
            f"[CHAIN] All resolvers failed for: {episode.title[:50]}... "
            f"attempted={resolvers_attempted}"
        )
        return None

    def _get_resolver_order(self, overrides: Optional[Dict[str, Any]] = None) -> List[str]:
        order = list(self.config.resolver_order)
        if overrides:
            if 'prefer' in overrides:
                preferred = list(overrides['prefer'])
                for r in preferred:
                    if r in order:
                        order.remove(r)
                order = preferred + order
            if 'skip' in overrides:
                order = [r for r in order if r not in overrides['skip']]
        return order

    def _passes_quality_gates(self, transcript: TranscriptResult, resolver_name: str) -> bool:
        if len(transcript.full_text) < self.config.quality_min_length:
            logger.debug(f"[CHAIN] Quality gate failed: length {len(transcript.full_text)}")
            return False

        if (transcript.confidence is not None
                and transcript.confidence < self.config.quality_min_confidence):
            logger.debug(f"[CHAIN] Quality gate failed: confidence {transcript.confidence}")
            return False

        if self.config.require_speaker_labels and not transcript.has_speaker_labels:
            logger.warning(
                f"[CHAIN] Quality gate failed: no speaker labels from {resolver_name} "
                f"(required for quote extraction)"
            )
            return False

        return True
