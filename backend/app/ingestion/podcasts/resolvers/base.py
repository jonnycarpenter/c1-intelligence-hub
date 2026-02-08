"""
Base Resolver Interface
=======================

Abstract base class for transcript resolvers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from ..models import PodcastEpisode, TranscriptResult


@dataclass
class ResolutionResult:
    """Result of a transcript resolution attempt."""
    success: bool
    transcript: Optional[TranscriptResult] = None
    error_message: Optional[str] = None
    cost_usd: float = 0.0
    processing_time_seconds: float = 0.0


class TranscriptResolver(ABC):
    """Abstract base class for transcript resolvers."""

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def is_paid(self) -> bool:
        pass

    @abstractmethod
    async def resolve(self, episode: PodcastEpisode) -> ResolutionResult:
        pass

    @abstractmethod
    def estimate_cost(self, episode: PodcastEpisode) -> float:
        pass

    def can_handle(self, episode: PodcastEpisode) -> bool:
        return True

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name='{self.name}' paid={self.is_paid}>"
