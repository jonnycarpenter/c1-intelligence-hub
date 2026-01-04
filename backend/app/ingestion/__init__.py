"""
C1 Intelligence Hub - Data Ingestion Pipeline
==============================================

Components:
- RSS Feed Fetcher
- Web Scraper (full article extraction)
- Content Classifier (Claude-based)
- Entity Linker
- Deduplication Service
- Digest Generator
- Orchestrator
"""

from app.ingestion.config import IngestionConfig, RSS_FEEDS
from app.ingestion.fetchers import RSSFetcher
from app.ingestion.processing import WebScraper, ContentClassifier, EntityLinker, DeduplicationService
from app.ingestion.generators import DigestGenerator, BriefingGenerator
from app.ingestion.orchestrator import IngestionOrchestrator

__all__ = [
    "IngestionConfig",
    "RSS_FEEDS",
    "RSSFetcher",
    "WebScraper",
    "ContentClassifier",
    "EntityLinker",
    "DeduplicationService",
    "DigestGenerator",
    "BriefingGenerator",
    "IngestionOrchestrator",
]
