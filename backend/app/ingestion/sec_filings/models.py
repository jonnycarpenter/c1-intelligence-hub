"""
SEC Filing Nugget Models - C1 Intelligence Hub
===============================================

Pydantic models for extracted strategic insights from SEC filings.
Optimized for RPM International and coatings/construction industry.

Adapted from REFERENCE_sec_filings/models/filing.py (dataclass-based)
into Pydantic models with BigQuery serialization support.

Key Features:
- Legally mandated disclosures (companies MUST disclose risks)
- Risk factor analysis (Item 1A gold mine)
- Competitive disclosure signals (named competitors)
- Forward-looking statement analysis
- Material change detection (8-K triggers)
- RPM-specific themes for coatings, construction chemicals, building materials
"""

import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field
import uuid


# =============================================================================
# ENUMS - SEC Filing Taxonomy
# =============================================================================

class FilingType(str, Enum):
    """SEC filing form types."""
    FORM_10K = "10-K"
    FORM_10Q = "10-Q"
    FORM_8K = "8-K"
    FORM_S1 = "S-1"
    FORM_DEF14A = "DEF 14A"
    FORM_20F = "20-F"
    FORM_6K = "6-K"
    OTHER = "other"


class FilingSection(str, Enum):
    """Key sections of SEC filings."""
    RISK_FACTORS = "risk_factors"
    BUSINESS = "business"
    MDA = "mda"
    LEGAL_PROCEEDINGS = "legal_proceedings"
    MARKET_RISK = "market_risk"
    PROPERTIES = "properties"
    EXHIBITS = "exhibits"
    FORWARD_LOOKING = "forward_looking"
    EXECUTIVE_COMPENSATION = "executive_comp"
    UNKNOWN = "unknown"


class NuggetType(str, Enum):
    """Type of insight extracted from the filing."""
    COMPETITIVE_DISCLOSURE = "competitive_disclosure"
    RISK_ADMISSION = "risk_admission"
    MARKET_POSITION = "market_position"
    FORWARD_GUIDANCE = "forward_guidance"
    REGULATORY_EXPOSURE = "regulatory_exposure"
    LITIGATION_DISCLOSURE = "litigation_disclosure"
    MATERIAL_CHANGE = "material_change"
    STRATEGIC_INITIATIVE = "strategic_initiative"
    SUPPLY_CHAIN = "supply_chain"
    RAW_MATERIALS = "raw_materials"
    FINANCIAL_METRIC = "financial_metric"
    ESG_DISCLOSURE = "esg_disclosure"
    ACQUISITION = "acquisition"


class DisclosureSignalStrength(str, Enum):
    """How explicit/strong is the disclosure signal?"""
    EXPLICIT = "explicit"
    STANDARD = "standard"
    HEDGED = "hedged"
    BURIED = "buried"
    NEW = "new"


class SecFilingTheme(str, Enum):
    """Taxonomy of themes aligned with RPM strategic priorities."""
    # Business Segments
    CONSTRUCTION_PRODUCTS = "construction_products"
    PERFORMANCE_COATINGS = "performance_coatings"
    CONSUMER_GROUP = "consumer_group"
    SPECIALTY_PRODUCTS = "specialty_products"
    # Construction Markets
    COMMERCIAL_CONSTRUCTION = "commercial_construction"
    RESIDENTIAL_CONSTRUCTION = "residential_construction"
    INFRASTRUCTURE = "infrastructure"
    INDUSTRIAL_FACILITIES = "industrial_facilities"
    # Product Categories
    WATERPROOFING = "waterproofing"
    PROTECTIVE_COATINGS = "protective_coatings"
    CONCRETE_REPAIR = "concrete_repair"
    FLOORING_SYSTEMS = "flooring_systems"
    SEALANTS_ADHESIVES = "sealants_adhesives"
    FIREPROOFING = "fireproofing"
    # Competitive Dynamics
    SHERWIN_WILLIAMS = "sherwin_williams"
    PPG_INDUSTRIES = "ppg_industries"
    SIKA_GROUP = "sika_group"
    COMPETITIVE_LANDSCAPE = "competitive_landscape"
    # Operations & Finance
    RAW_MATERIAL_COSTS = "raw_material_costs"
    SUPPLY_CHAIN = "supply_chain"
    PRICING_STRATEGY = "pricing_strategy"
    MA_ACTIVITY = "ma_activity"
    MARGIN_IMPROVEMENT = "margin_improvement"
    # External Factors
    INTEREST_RATES = "interest_rates"
    ECONOMIC_CONDITIONS = "economic_conditions"
    REGULATORY_ENVIRONMENT = "regulatory_environment"
    SUSTAINABILITY = "sustainability"
    # Channels
    RETAIL_CHANNEL = "retail_channel"
    CONTRACTOR_CHANNEL = "contractor_channel"
    OEM_INDUSTRIAL = "oem_industrial"


# =============================================================================
# MAIN DATA MODELS
# =============================================================================

class ExtractedSecNugget(BaseModel):
    """
    An extracted strategic insight from an SEC filing.

    Nuggets are extracted during ingestion using LLM-based analysis.
    Each 10-K typically yields 15-30 high-value nuggets from
    risk factors and MD&A sections.
    """

    # Identity
    nugget_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    filing_id: str = ""

    # The nugget itself
    nugget_text: str = ""
    context_text: Optional[str] = None

    # Filing context
    filing_type: FilingType = FilingType.FORM_10K
    section: FilingSection = FilingSection.UNKNOWN

    # Nugget classification
    nugget_type: NuggetType = NuggetType.RISK_ADMISSION
    themes: List[SecFilingTheme] = Field(default_factory=list)
    signal_strength: DisclosureSignalStrength = DisclosureSignalStrength.STANDARD

    # Entity references
    companies_mentioned: List[str] = Field(default_factory=list)
    brands_mentioned: List[str] = Field(default_factory=list)
    competitors_named: List[str] = Field(default_factory=list)
    regulators_mentioned: List[str] = Field(default_factory=list)

    # Risk & relevance
    risk_level: str = "medium"
    is_new_disclosure: bool = False
    strategic_relevance: str = "medium"
    relevance_score: float = 0.5
    is_actionable: bool = False
    actionability_reason: Optional[str] = None
    business_segment: Optional[str] = None

    # Source context
    ticker: str = ""
    company_name: str = ""
    cik: str = ""
    fiscal_year: int = 0
    fiscal_quarter: Optional[int] = None
    filing_date: Optional[str] = None

    # Audit fields
    extracted_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    extraction_model: str = "claude-sonnet-4-6"

    def to_bq_row(self) -> Dict[str, Any]:
        """Convert to BigQuery row dict for insert_rows_json."""
        return {
            "nugget_id": self.nugget_id,
            "filing_id": self.filing_id,
            "nugget_text": self.nugget_text,
            "context_text": self.context_text,
            "filing_type": self.filing_type.value if isinstance(self.filing_type, FilingType) else self.filing_type,
            "section": self.section.value if isinstance(self.section, FilingSection) else self.section,
            "nugget_type": self.nugget_type.value if isinstance(self.nugget_type, NuggetType) else self.nugget_type,
            "themes": json.dumps([t.value if isinstance(t, SecFilingTheme) else t for t in self.themes]),
            "signal_strength": self.signal_strength.value if isinstance(self.signal_strength, DisclosureSignalStrength) else self.signal_strength,
            "companies_mentioned": json.dumps(self.companies_mentioned),
            "brands_mentioned": json.dumps(self.brands_mentioned),
            "competitors_named": json.dumps(self.competitors_named),
            "regulators_mentioned": json.dumps(self.regulators_mentioned),
            "risk_level": self.risk_level,
            "is_new_disclosure": self.is_new_disclosure,
            "strategic_relevance": self.strategic_relevance,
            "relevance_score": self.relevance_score,
            "is_actionable": self.is_actionable,
            "actionability_reason": self.actionability_reason,
            "business_segment": self.business_segment,
            "ticker": self.ticker,
            "company_name": self.company_name,
            "cik": self.cik,
            "fiscal_year": self.fiscal_year,
            "fiscal_quarter": self.fiscal_quarter,
            "filing_date": self.filing_date,
            "extracted_at": self.extracted_at,
            "extraction_model": self.extraction_model,
        }

    def to_display_dict(self) -> Dict[str, Any]:
        """Convert to display-friendly dictionary for API responses."""
        return {
            "nugget_id": self.nugget_id,
            "nugget_text": self.nugget_text,
            "context_text": self.context_text,
            "source": {
                "ticker": self.ticker,
                "company": self.company_name,
                "filing_type": self.filing_type.value if isinstance(self.filing_type, FilingType) else self.filing_type,
                "section": self.section.value if isinstance(self.section, FilingSection) else self.section,
                "fiscal_year": self.fiscal_year,
                "fiscal_quarter": self.fiscal_quarter,
                "filing_date": self.filing_date,
            },
            "classification": {
                "nugget_type": self.nugget_type.value if isinstance(self.nugget_type, NuggetType) else self.nugget_type,
                "themes": [t.value if isinstance(t, SecFilingTheme) else t for t in self.themes],
                "signal_strength": self.signal_strength.value if isinstance(self.signal_strength, DisclosureSignalStrength) else self.signal_strength,
                "risk_level": self.risk_level,
            },
            "relevance_score": self.relevance_score,
            "is_actionable": self.is_actionable,
            "is_new_disclosure": self.is_new_disclosure,
            "business_segment": self.business_segment,
            "competitors_named": self.competitors_named,
            "companies_mentioned": self.companies_mentioned,
        }


class SecNuggetExtractionResult(BaseModel):
    """
    Result of nugget extraction from an SEC filing.

    Contains extracted nuggets plus metadata about the extraction process.
    """

    # Source info
    filing_id: str = ""
    ticker: str = ""
    company_name: str = ""
    filing_type: FilingType = FilingType.FORM_10K
    fiscal_year: int = 0
    fiscal_quarter: Optional[int] = None

    # Extraction results
    nuggets: List[ExtractedSecNugget] = Field(default_factory=list)
    total_nuggets: int = 0
    actionable_count: int = 0
    new_disclosure_count: int = 0

    # Statistics
    nuggets_by_section: Dict[str, int] = Field(default_factory=dict)
    nuggets_by_type: Dict[str, int] = Field(default_factory=dict)

    # Process metadata
    success: bool = False
    error_message: Optional[str] = None
    extraction_model: str = "claude-haiku-4-5"
    extraction_time_seconds: float = 0.0
    filing_length: int = 0

    def compute_statistics(self):
        """Compute statistics from extracted nuggets."""
        self.total_nuggets = len(self.nuggets)
        self.actionable_count = sum(1 for n in self.nuggets if n.is_actionable)
        self.new_disclosure_count = sum(1 for n in self.nuggets if n.is_new_disclosure)

        self.nuggets_by_section = {}
        for n in self.nuggets:
            section = n.section.value if isinstance(n.section, FilingSection) else n.section
            self.nuggets_by_section[section] = self.nuggets_by_section.get(section, 0) + 1

        self.nuggets_by_type = {}
        for n in self.nuggets:
            ntype = n.nugget_type.value if isinstance(n.nugget_type, NuggetType) else n.nugget_type
            self.nuggets_by_type[ntype] = self.nuggets_by_type.get(ntype, 0) + 1
