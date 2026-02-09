"""
Earnings Quote Extraction Module - C1 Intelligence Hub
======================================================

LLM-based extraction of executive insights from earnings call transcripts.

Components:
- models.py - Pydantic models for extracted quotes (SpeakerRole, QuoteType, etc.)
- quote_extractor.py - Claude Haiku extraction engine
"""

from .models import (
    ExtractedEarningsQuote,
    EarningsQuoteExtractionResult,
    SpeakerRole,
    QuoteType,
    ConfidenceLevel,
    CallSection,
    EarningsQuoteTheme,
)
from .quote_extractor import EarningsQuoteExtractor

__all__ = [
    "EarningsQuoteExtractor",
    "ExtractedEarningsQuote",
    "EarningsQuoteExtractionResult",
    "SpeakerRole",
    "QuoteType",
    "ConfidenceLevel",
    "CallSection",
    "EarningsQuoteTheme",
]
