"""
Ingestion Pipeline Configuration
================================

Configuration and constants for the data ingestion pipeline.
RSS feeds have been verified as of December 2024.
"""

import os
from dataclasses import dataclass, field
from typing import List, Dict, Any


@dataclass
class IngestionConfig:
    """Configuration for the ingestion pipeline."""
    
    # API Keys (from environment)
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    
    # Database
    db_type: str = "sqlite"
    
    # Vector Store
    chroma_persist_dir: str = field(default_factory=lambda: os.getenv("CHROMA_PERSIST_DIR", "./data/chroma_db"))
    
    # Ingestion Settings
    rss_poll_interval_hours: int = 2
    max_articles_per_feed: int = 20
    max_article_age_days: int = 7
    
    # Web Scraper
    scraper_timeout: float = 15.0
    scraper_max_concurrent: int = 5
    scraper_max_articles: int = 50  # Only enrich top N articles
    
    # Classification
    classifier_model: str = "claude-sonnet-4-5"
    classifier_temperature: float = 0.1
    classifier_max_concurrent: int = 3
    
    # Digest
    digest_hours: int = 72
    digest_max_items: int = 50
    digest_model: str = "claude-sonnet-4-5"
    
    # Briefings (Pulse tab summaries - uses Opus for higher quality)
    briefing_model: str = "claude-opus-4-5"


# ============================================================================
# RSS Feed Sources - VERIFIED December 2024
# ============================================================================

RSS_FEEDS: List[Dict[str, Any]] = [
    # =========================
    # PRIMARY: Composites Trade Publications
    # =========================
    {
        "name": "CompositesWorld",
        "url": "https://www.compositesworld.com/rss/news",
        "category": "trade_publication",
        "priority_boost": 0.15,  # High relevance boost
        "filter_keywords": [],  # No filter needed - all content relevant
    },
    {
        "name": "JEC Composites",
        "url": "https://www.jeccomposites.com/feed/",
        "category": "trade_publication",
        "priority_boost": 0.15,
    },
    {
        "name": "Composites Manufacturing (ACMA)",
        "url": "https://compositesmanufacturingmagazine.com/feed/",
        "category": "trade_publication",
        "priority_boost": 0.1,
    },
    {
        "name": "ACMA News",
        "url": "https://acmanet.org/feed/",
        "category": "trade_publication",
        "priority_boost": 0.1,
    },
    
    # =========================
    # SECONDARY: Plastics/Materials
    # =========================
    {
        "name": "Plastics Today",
        "url": "https://www.plasticstoday.com/rss.xml",
        "category": "materials",
        "priority_boost": 0.05,
        "filter_keywords": [
            "composite", "carbon fiber", "fiberglass", "glass fiber",
            "reinforced", "thermoset", "thermoplastic", "resin", "epoxy",
            "prepreg", "molding", "aerospace", "automotive", "wind"
        ],
    },
    
    # =========================
    # INDUSTRY VERTICALS: Aerospace
    # =========================
    {
        "name": "Aviation Week",
        "url": "https://aviationweek.com/rss.xml",
        "category": "aerospace",
        "priority_boost": 0.0,
        "filter_keywords": [
            "composite", "carbon fiber", "lightweight", "materials",
            "fuselage", "wing", "structure", "manufacturing"
        ],
    },
    
    # =========================
    # INDUSTRY VERTICALS: Automotive
    # =========================
    {
        "name": "Just Auto",
        "url": "https://www.just-auto.com/feed/",
        "category": "automotive",
        "priority_boost": 0.0,
        "filter_keywords": [
            "composite", "carbon fiber", "lightweight", "materials",
            "body", "structure", "EV", "electric", "battery enclosure"
        ],
    },
    
    # =========================
    # INDUSTRY VERTICALS: Wind Energy
    # =========================
    {
        "name": "Wind Power Engineering",
        "url": "https://www.windpowerengineering.com/feed/",
        "category": "wind_energy",
        "priority_boost": 0.05,
        "filter_keywords": [
            "blade", "composite", "fiber", "material", "manufacturing",
            "turbine", "offshore", "supplier"
        ],
    },
    {
        "name": "Offshore Wind",
        "url": "https://www.offshorewind.biz/feed/",
        "category": "wind_energy",
        "priority_boost": 0.0,
        "filter_keywords": [
            "blade", "composite", "material", "manufacturing", "supplier"
        ],
    },
    
    # =========================
    # INDUSTRY VERTICALS: Marine
    # =========================
    {
        "name": "Boating Industry",
        "url": "https://boatingindustry.com/feed/",
        "category": "marine",
        "priority_boost": 0.0,
        "filter_keywords": [
            "composite", "fiberglass", "hull", "manufacturing",
            "material", "resin", "gelcoat"
        ],
    },
    {
        "name": "Marine Industry News",
        "url": "https://www.marineindustrynews.co.uk/feed/",
        "category": "marine",
        "priority_boost": 0.0,
        "filter_keywords": [
            "composite", "fiberglass", "hull", "material",
            "manufacturing", "supplier"
        ],
    },
    
    # =========================
    # LOGISTICS & SUPPLY CHAIN
    # =========================
    {
        "name": "FreightWaves",
        "url": "https://www.freightwaves.com/feed",
        "category": "logistics_news",
        "priority_boost": 0.1,
    },
    {
        "name": "Supply Chain Dive",
        "url": "https://www.supplychaindive.com/feeds/news/",
        "category": "logistics_news",
        "priority_boost": 0.05,
    },
    {
        "name": "Supply Chain Dive - Logistics",
        "url": "https://www.supplychaindive.com/feeds/topic/logistics/",
        "category": "logistics_news",
        "priority_boost": 0.05,
    },
]


# ============================================================================
# Keywords for Classification Assistance
# ============================================================================

CATEGORY_KEYWORDS = {
    "competitor": [
        "hexcel", "toray", "solvay", "owens corning", "huntsman", "gurit",
        "teijin", "mitsubishi chemical", "sgl carbon", "acquired", "acquisition",
        "market share", "competitive", "rival", "competitor"
    ],
    "market": [
        "demand", "growth", "forecast", "trend", "outlook", "market size",
        "CAGR", "billion", "million", "increase", "decrease", "surge",
        "market report", "industry analysis"
    ],
    "regulatory": [
        "regulation", "EPA", "FAA", "compliance", "standard", "certification",
        "REACH", "RoHS", "environmental", "emission", "sustainability", "ban",
        "policy", "law", "mandate"
    ],
    "product": [
        "launch", "introduce", "new product", "unveil", "debut", "release",
        "next-generation", "innovative", "breakthrough", "patent"
    ],
    "earnings": [
        "earnings", "revenue", "profit", "quarterly", "fiscal", "guidance",
        "EPS", "margin", "financial results", "outlook", "Q1", "Q2", "Q3", "Q4"
    ],
    "partnership": [
        "partnership", "collaboration", "joint venture", "agreement", "deal",
        "alliance", "MOU", "contract", "supply agreement", "strategic"
    ],
    "expansion": [
        "expansion", "facility", "plant", "investment", "capacity", "production",
        "manufacturing", "new site", "construction", "million investment"
    ],
    "supply_chain": [
        "supply chain", "shortage", "logistics", "raw material", "supplier",
        "inventory", "lead time", "disruption", "sourcing", "procurement"
    ],
    "logistics": [
        "freight", "shipping", "container", "port", "ocean freight",
        "trucking", "rail", "FBX", "baltic", "congestion", "rates",
        "capacity", "delay", "transportation", "warehouse", "logistics"
    ],
}

INDUSTRY_KEYWORDS = {
    "aerospace": [
        "aerospace", "aircraft", "aviation", "boeing", "airbus", "jet",
        "fuselage", "wing", "nacelle", "interior"
    ],
    "automotive": [
        "automotive", "vehicle", "car", "EV", "electric vehicle", "OEM",
        "tier 1", "body panel", "battery enclosure"
    ],
    "marine": [
        "marine", "boat", "yacht", "ship", "naval", "offshore", "hull"
    ],
    "wind_energy": [
        "wind", "turbine", "blade", "renewable", "offshore wind",
        "vestas", "siemens gamesa", "ge renewable"
    ],
    "infrastructure": [
        "infrastructure", "bridge", "construction", "civil", "rebar", "strengthening"
    ],
    "sporting_goods": [
        "sporting", "golf", "bicycle", "ski", "tennis", "recreation", "bike"
    ],
    "defense": [
        "defense", "military", "army", "navy", "air force", "DoD", "armor"
    ],
}


# ============================================================================
# Default Tracked Entities (fallback if CSV not loaded)
# ============================================================================

DEFAULT_COMPETITORS = [
    "Hexcel", "Toray", "Solvay", "Owens Corning", "Huntsman",
    "Gurit", "Teijin", "SGL Carbon", "Mitsubishi Chemical"
]

DEFAULT_OEMS = [
    # Aerospace
    "Boeing", "Airbus", "Spirit AeroSystems", "GE Aerospace",
    # Wind
    "Vestas", "Siemens Gamesa", "TPI Composites", "LM Wind Power",
    # Marine
    "Brunswick", "Beneteau", "Malibu Boats", "MasterCraft",
    # Automotive
    "Toyota", "BMW", "Ford", "Tesla",
    # Infrastructure/Construction
    "Caterpillar", "John Deere", "Composite Advantage",
]

DEFAULT_TICKERS = [
    "HXL",    # Hexcel
    "TRYIY",  # Toray (ADR)
    "SOLVY",  # Solvay (ADR)
    "OC",     # Owens Corning
    "HUN",    # Huntsman
]
