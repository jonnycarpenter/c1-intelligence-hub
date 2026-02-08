"""
C1 Podcast Feed Configurations
================================

5 composites-industry podcasts for C1 Intelligence Hub.

Layers:
  - Core composites: CW Talks, Composites Weekly
  - Key end market (wind): Uptime Wind Energy
  - Upstream supply chain: The Chemical Show
  - Raw material pricing: ICIS Chemical Podcasts
"""

from typing import List, Dict, Any


C1_PODCAST_FEEDS: List[Dict[str, Any]] = [
    {
        "id": "cw-talks",
        "name": "CW Talks (CompositesWorld)",
        "rss_url": "https://sites.libsyn.com/452433/rss",
        "website_url": "https://www.compositesworld.com/podcasts",
        "description": "Core composites industry podcast from CompositesWorld. "
                       "Covers fiber suppliers (Hexcel, Toray), resin systems, manufacturing processes, "
                       "and end market demand across aerospace, wind, marine, infrastructure, automotive.",
        "publisher": "Gardner Business Media",
        "has_site_transcripts": False,
        "has_youtube_versions": True,
        "default_hosts": [],
        "resolution_override": {"prefer": ["youtube_transcript", "assemblyai"]},
        "priority": "tier1",
        "avg_duration_minutes": 30,
    },
    {
        "id": "composites-weekly",
        "name": "Composites Weekly",
        "rss_url": "https://compositesweeklypodcast.libsyn.com/rss",
        "website_url": None,
        "description": "Weekly composites industry pulse. ACMA updates, trade policy, tariffs, "
                       "TSCA/styrene regulation, workforce, new materials, additive manufacturing.",
        "publisher": "Jonathan Taylor",
        "has_site_transcripts": False,
        "has_youtube_versions": False,
        "default_hosts": ["Jonathan Taylor"],
        "resolution_override": {"prefer": ["assemblyai"]},
        "priority": "tier1",
        "avg_duration_minutes": 45,
    },
    {
        "id": "uptime-wind-energy",
        "name": "Uptime Wind Energy",
        "rss_url": "https://weatherguardwind.com/feed/podcast/",
        "website_url": "https://weatherguardwind.com/wind-turbine-podcast/",
        "description": "Wind blade manufacturing, turbine OEM production rates (Vestas, GE Vernova, "
                       "Siemens Gamesa), blade quality, offshore wind buildout, policy shifts.",
        "publisher": "WeatherGuard Wind",
        "has_site_transcripts": False,
        "has_youtube_versions": False,
        "default_hosts": ["Allen Hall", "Rosemary Barnes", "Joel Saxum", "Yolanda Padron"],
        "resolution_override": {"prefer": ["assemblyai"]},
        "priority": "tier1",
        "avg_duration_minutes": 35,
    },
    {
        "id": "the-chemical-show",
        "name": "The Chemical Show",
        "rss_url": "https://feeds.transistor.fm/the-chemical-show",
        "website_url": "https://thechemicalshow.com",
        "description": "Upstream supply chain. C-suite interviews across specialty chemicals, "
                       "petrochemicals, and materials. Supply chain disruptions, M&A, feedstock economics, "
                       "pricing for epoxy, vinyl ester, polyester resins.",
        "publisher": "Treble",
        "has_site_transcripts": True,
        "has_youtube_versions": True,
        "default_hosts": ["Victoria Meyer"],
        "resolution_override": {"prefer": ["site_transcript", "youtube_transcript", "assemblyai"]},
        "priority": "tier1",
        "avg_duration_minutes": 45,
    },
    {
        "id": "icis-chemical",
        "name": "ICIS Chemical Podcasts",
        "rss_url": "https://icisnews-europe.podomatic.com/rss2.xml",
        "website_url": "https://www.icis.com/explore/resources/podcast-library/",
        "description": "Macro pricing and feedstock intelligence. Styrene, propylene, ethylene, BPA, "
                       "epichlorohydrin pricing, capacity utilization, tariff impacts on chemical trade.",
        "publisher": "ICIS (S&P Global)",
        "has_site_transcripts": False,
        "has_youtube_versions": False,
        "default_hosts": [],
        "resolution_override": {"prefer": ["assemblyai"]},
        "priority": "tier1",
        "avg_duration_minutes": 25,
    },
]


def get_feed_by_id(feed_id: str) -> Dict[str, Any]:
    """Get feed configuration by ID."""
    for feed in C1_PODCAST_FEEDS:
        if feed["id"] == feed_id:
            return feed
    raise ValueError(f"Feed ID not found: {feed_id}")


def get_active_feeds() -> List[Dict[str, Any]]:
    """Get all feeds that have an RSS URL configured."""
    return [f for f in C1_PODCAST_FEEDS if f.get("rss_url")]
