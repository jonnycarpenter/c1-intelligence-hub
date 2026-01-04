"""
Knowledge Base Configuration
============================

Configuration for Wikipedia seeding and knowledge base management.
"""

import os
from dataclasses import dataclass, field
from typing import List
from pathlib import Path


@dataclass
class SeederConfig:
    """Configuration for the knowledge base seeder."""
    
    # ChromaDB settings
    chroma_persist_dir: str = field(default_factory=lambda: os.getenv(
        "KNOWLEDGE_CHROMA_DIR",
        str(Path(__file__).parent.parent.parent.parent / "data" / "knowledge_base")
    ))
    collection_name: str = "c1_knowledge_base"
    
    # Wikipedia API settings
    wiki_api_url: str = "https://en.wikipedia.org/api/rest_v1"
    wiki_mediawiki_url: str = "https://en.wikipedia.org/w/api.php"
    wikidata_api_url: str = "https://www.wikidata.org/w/api.php"
    wiki_user_agent: str = "C1IntelligenceHub/1.0 (contact@example.com) httpx/0.25"
    
    # Rate limiting (be nice to Wikipedia)
    requests_per_second: float = 2.0
    request_timeout: float = 30.0
    
    # Content limits
    max_content_length: int = 15000  # Characters per article
    max_section_length: int = 5000  # Characters per section
    
    # Sections to include from Wikipedia articles
    include_sections: List[str] = field(default_factory=lambda: [
        "Products",
        "Products and services", 
        "Operations",
        "History",
        "Manufacturing",
        "Applications",
        "Properties",
        "Business segments",
        "Divisions",
        "Services",
        "Production",
        "Technology",
        "Research and development",
        "Markets",
        "Industry",
        "Uses",
        "Types",
        "Composition",
        "Structure",
        "Processing",
        "Materials",
    ])


def get_seeder_config() -> SeederConfig:
    """Get seeder configuration."""
    return SeederConfig()
