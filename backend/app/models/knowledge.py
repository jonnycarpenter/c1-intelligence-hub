"""
Knowledge Base Models
=====================

Data models for the Wikipedia knowledge base that provides
foundational context for C1 Intelligence Hub agents.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum


class EntityType(str, Enum):
    """Types of entities in the knowledge base."""
    COMPANY = "company"
    MATERIAL = "material"
    PROCESS = "process"
    INDUSTRY = "industry"


class CompanyType(str, Enum):
    """Types of companies in the composites supply chain."""
    RAW_MATERIAL_MANUFACTURER = "raw_material_manufacturer"
    INTERMEDIATE_MANUFACTURER = "intermediate_manufacturer"
    DISTRIBUTOR = "distributor"
    PROCESSOR_FABRICATOR = "processor_fabricator"
    OEM_AEROSPACE = "oem_aerospace"
    OEM_SPACE = "oem_space"
    OEM_WIND = "oem_wind"
    OEM_MARINE = "oem_marine"
    OEM_AUTOMOTIVE = "oem_automotive"
    END_USER = "end_user"


class MaterialCategory(str, Enum):
    """Categories of materials."""
    RESIN = "resin"
    REINFORCEMENT = "reinforcement"
    INTERMEDIATE = "intermediate"
    CORE = "core"
    THERMOPLASTIC = "thermoplastic"
    COMPOSITE = "composite"


class MarginTier(str, Enum):
    """Margin tiers for materials."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


@dataclass
class WikiArticle:
    """Parsed Wikipedia article content."""
    title: str
    page_id: int
    url: str
    extract: str
    full_text: str
    sections: Dict[str, str]
    categories: List[str]
    infobox: Dict[str, Any]
    wikidata_id: Optional[str] = None
    retrieved_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class CompanyEntity:
    """A company entity to seed into the knowledge base."""
    name: str
    company_type: CompanyType
    wiki_title: Optional[str] = None
    ticker: Optional[str] = None
    industries: List[str] = field(default_factory=list)
    description: str = ""
    processes_services: List[str] = field(default_factory=list)
    fallback_content: Optional[str] = None
    
    @property
    def entity_id(self) -> str:
        """Generate a unique ID for this entity."""
        safe_name = self.name.lower().replace(' ', '_').replace('.', '').replace(',', '')
        return f"company_{safe_name}"


@dataclass
class MaterialEntity:
    """A material entity to seed into the knowledge base."""
    name: str
    category: MaterialCategory
    wiki_title: Optional[str] = None
    margin_tier: MarginTier = MarginTier.MEDIUM
    industries: List[str] = field(default_factory=list)
    examples: str = ""
    fallback_content: Optional[str] = None
    
    @property
    def entity_id(self) -> str:
        """Generate a unique ID for this entity."""
        safe_name = self.name.lower().replace(' ', '_').replace('-', '_').replace('/', '_')
        return f"material_{safe_name}"


@dataclass
class ProcessEntity:
    """A manufacturing process entity to seed into the knowledge base."""
    name: str
    wiki_title: Optional[str] = None
    margin_tier: MarginTier = MarginTier.MEDIUM
    industries: List[str] = field(default_factory=list)
    examples: str = ""
    fallback_content: Optional[str] = None
    
    @property
    def entity_id(self) -> str:
        """Generate a unique ID for this entity."""
        safe_name = self.name.lower().replace(' ', '_').replace('-', '_').replace('/', '_')
        return f"process_{safe_name}"


@dataclass
class IndustryEntity:
    """An industry entity to seed into the knowledge base."""
    name: str
    wiki_title: Optional[str] = None
    description: str = ""
    key_materials: List[str] = field(default_factory=list)
    key_processes: List[str] = field(default_factory=list)
    
    @property
    def entity_id(self) -> str:
        """Generate a unique ID for this entity."""
        safe_name = self.name.lower().replace(' ', '_').replace('&', 'and').replace('/', '_')
        return f"industry_{safe_name}"


@dataclass
class KnowledgeDocument:
    """A document stored in the knowledge base vector store."""
    id: str
    title: str
    content: str
    entity_type: EntityType
    entity_name: str
    source: str = "wikipedia"
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "entity_type": self.entity_type.value if isinstance(self.entity_type, EntityType) else self.entity_type,
            "entity_name": self.entity_name,
            "source": self.source,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class SeedingProgress:
    """Progress tracking for seeding operations."""
    total: int = 0
    completed: int = 0
    failed: int = 0
    skipped: int = 0
    current_entity: str = ""
    status: str = "idle"  # idle, running, completed, error
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    errors: List[str] = field(default_factory=list)
    
    @property
    def progress_percent(self) -> float:
        """Calculate progress percentage."""
        if self.total == 0:
            return 0.0
        return (self.completed + self.failed + self.skipped) / self.total * 100
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "total": self.total,
            "completed": self.completed,
            "failed": self.failed,
            "skipped": self.skipped,
            "current_entity": self.current_entity,
            "status": self.status,
            "progress_percent": round(self.progress_percent, 1),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "errors": self.errors[-10:],  # Last 10 errors
        }
