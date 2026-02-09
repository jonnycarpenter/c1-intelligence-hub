"""
SEC Filing Nugget Extraction Module - C1 Intelligence Hub
=========================================================

LLM-based extraction of strategic insights from SEC filings.

Components:
- models.py - Pydantic models for extracted nuggets (NuggetType, SecFilingTheme, etc.)
- nugget_extractor.py - Claude Haiku extraction engine
"""

from .models import (
    ExtractedSecNugget,
    SecNuggetExtractionResult,
    FilingType,
    FilingSection,
    NuggetType,
    DisclosureSignalStrength,
    SecFilingTheme,
)
from .nugget_extractor import SecNuggetExtractor

__all__ = [
    "SecNuggetExtractor",
    "ExtractedSecNugget",
    "SecNuggetExtractionResult",
    "FilingType",
    "FilingSection",
    "NuggetType",
    "DisclosureSignalStrength",
    "SecFilingTheme",
]
