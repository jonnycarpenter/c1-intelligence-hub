"""
Datasheet Scraper Module
========================

Scrapes technical datasheets from composite material suppliers
and loads them into BigQuery for agent retrieval.

Target Suppliers:
- Hexcel (carbon fiber, prepregs, honeycomb)
- Owens Corning (glass fiber reinforcements)
- Toray (carbon fiber, prepregs)
- Polynt-Reichhold (polyester/vinyl ester resins)
- Gurit (core materials, prepregs)

Usage:
    # Run all suppliers
    python -m app.scrapers.orchestrator --all
    
    # Run specific supplier
    python -m app.scrapers.orchestrator --supplier hexcel
    
    # Test mode (3 datasheets per supplier)
    python -m app.scrapers.orchestrator --test
    
    # Health check
    python -m app.scrapers.health_check
"""

from app.scrapers.config import ScraperConfig
from app.scrapers.orchestrator import run_scraper

__all__ = ["ScraperConfig", "run_scraper"]
