"""
Knowledge Base Models
=====================

Data models for Wikipedia articles and knowledge documents.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Any, Optional


@dataclass
class WikiArticle:
    """Parsed Wikipedia article."""
    
    title: str
    page_id: int
    url: str
    extract: str  # Short summary
    full_text: str  # Full article content
    sections: Dict[str, str]  # Section name -> content
    categories: List[str]
    infobox: Dict[str, Any]  # Wikidata structured data
    wikidata_id: Optional[str] = None
    retrieved_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class KnowledgeDocument:
    """A document to be stored in the knowledge base."""
    
    id: str
    title: str
    content: str
    source: str = "wikipedia"
    entity_type: str = ""  # company, material, industry, process
    entity_name: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CompanyEntity:
    """Company entity for seeding."""
    
    name: str
    wiki_title: Optional[str]
    ticker: Optional[str] = None
    industries: List[str] = field(default_factory=list)
    description: str = ""
    fallback_content: Optional[str] = None
    entity_type_override: Optional[str] = None  # Override default category


@dataclass
class MaterialEntity:
    """Material/process entity for seeding."""
    
    name: str
    wiki_title: Optional[str]
    category: str  # resin, reinforcement, intermediate, thermoplastic, core, process
    margin_tier: str = "MEDIUM"  # LOW, MEDIUM, HIGH
    industries: List[str] = field(default_factory=list)
    examples: str = ""
    fallback_content: Optional[str] = None


@dataclass 
class IndustryEntity:
    """Industry entity for seeding."""
    
    name: str
    wiki_title: Optional[str]
    description: str = ""
    key_materials: List[str] = field(default_factory=list)
    key_processes: List[str] = field(default_factory=list)


@dataclass
class SeederStats:
    """Statistics from a seeding run."""
    
    success: int = 0
    failed: int = 0
    skipped: int = 0
    documents_created: int = 0
    
    def __add__(self, other: "SeederStats") -> "SeederStats":
        return SeederStats(
            success=self.success + other.success,
            failed=self.failed + other.failed,
            skipped=self.skipped + other.skipped,
            documents_created=self.documents_created + other.documents_created,
        )
    
    def to_dict(self) -> Dict[str, int]:
        return {
            "success": self.success,
            "failed": self.failed,
            "skipped": self.skipped,
            "documents_created": self.documents_created,
        }
