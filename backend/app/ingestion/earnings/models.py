"""
Extracted Earnings Quote Models - C1 Intelligence Hub
=====================================================

Pydantic models for pre-extracted executive insights from earnings call transcripts.
Adapted for composites, aerospace, wind energy, marine, automotive, and infrastructure
industry intelligence.

Key Features:
- Speaker role tracking (CEO, CFO, Analyst, etc.)
- Quote type taxonomy (guidance, strategy, competitive, analyst_pressure, etc.)
- Confidence level tracking (definitive vs hedged responses)
- Q&A section awareness for analyst pressure signals
- Industry-specific themes for composites, advanced materials, and end markets
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field
import uuid


# =============================================================================
# ENUMS - Taxonomy for Earnings Calls
# =============================================================================

class SpeakerRole(str, Enum):
    """Speaker role on the earnings call."""
    CEO = "ceo"
    CFO = "cfo"
    COO = "coo"
    CMO = "cmo"
    CTO = "cto"
    EVP = "evp"
    VP = "vp"
    PRESIDENT = "president"
    ANALYST = "analyst"
    OTHER_EXEC = "other_exec"
    OPERATOR = "operator"
    UNKNOWN = "unknown"


class QuoteType(str, Enum):
    """
    Type of quote - what kind of insight does it provide?

    Critical for briefing integration:
    - guidance, strategy -> Forward-looking strategic context
    - competitive -> Direct competitive intelligence
    - analyst_pressure -> What Wall Street is worried about (GOLD)
    - risk_factor -> Headwinds and challenges (often hidden value)
    """
    GUIDANCE = "guidance"
    STRATEGY = "strategy"
    COMPETITIVE = "competitive"
    MARKET_COMMENTARY = "market_commentary"
    SEGMENT_INSIGHT = "segment_insight"
    CHANNEL_INSIGHT = "channel_insight"
    PRICING = "pricing"
    INNOVATION = "innovation"
    RISK_FACTOR = "risk_factor"
    REGIONAL = "regional"
    ANALYST_PRESSURE = "analyst_pressure"
    RAW_MATERIALS = "raw_materials"
    ACQUISITION = "acquisition"
    CAPACITY = "capacity"
    SUPPLY_CHAIN = "supply_chain"


class ConfidenceLevel(str, Enum):
    """
    How confident/definitive is the speaker?

    CRITICAL: 'hedged' responses to analyst questions are often
    the most valuable signals - what are they NOT saying clearly?
    """
    DEFINITIVE = "definitive"
    CAUTIOUS = "cautious"
    SPECULATIVE = "speculative"
    HEDGED = "hedged"


class CallSection(str, Enum):
    """
    Which part of the earnings call did this come from?

    Q&A section often contains more candid insights because
    analysts push for specifics that aren't in prepared remarks.
    """
    PREPARED_REMARKS = "prepared_remarks"
    QA = "qa"
    UNKNOWN = "unknown"


class EarningsQuoteTheme(str, Enum):
    """
    Taxonomy of themes for quote classification.
    Aligned with composites/advanced materials industry intelligence.
    """
    # Core Materials & Product Categories
    CARBON_FIBER = "carbon_fiber"
    GLASS_FIBER = "glass_fiber"
    RESINS_EPOXY = "resins_epoxy"
    THERMOPLASTIC_COMPOSITES = "thermoplastic_composites"
    PREPREG = "prepreg"
    ADVANCED_MATERIALS = "advanced_materials"

    # End Markets / Applications
    AEROSPACE_COMMERCIAL = "aerospace_commercial"
    AEROSPACE_DEFENSE = "aerospace_defense"
    WIND_ENERGY = "wind_energy"
    AUTOMOTIVE = "automotive"
    MARINE = "marine"
    INFRASTRUCTURE = "infrastructure"
    SPORTING_GOODS = "sporting_goods"
    INDUSTRIAL = "industrial"

    # Competitive Dynamics
    HEXCEL = "hexcel"
    TORAY = "toray"
    SOLVAY = "solvay"
    OWENS_CORNING = "owens_corning"
    HUNTSMAN = "huntsman"
    TEIJIN = "teijin"
    GURIT = "gurit"
    SGL_CARBON = "sgl_carbon"
    COMPETITIVE_LANDSCAPE = "competitive_landscape"

    # OEM / Customer Dynamics
    BOEING = "boeing"
    AIRBUS = "airbus"
    SPIRIT_AEROSYSTEMS = "spirit_aerosystems"
    GE_AEROSPACE = "ge_aerospace"
    VESTAS = "vestas"
    SIEMENS_GAMESA = "siemens_gamesa"
    TPI_COMPOSITES = "tpi_composites"

    # Operations & Finance
    RAW_MATERIAL_COSTS = "raw_material_costs"
    SUPPLY_CHAIN = "supply_chain"
    PRICING_STRATEGY = "pricing_strategy"
    MA_ACTIVITY = "ma_activity"
    MARGIN_IMPROVEMENT = "margin_improvement"
    CAPACITY_EXPANSION = "capacity_expansion"
    PRODUCTION_RATES = "production_rates"

    # External Factors
    TRADE_POLICY = "trade_policy"
    ECONOMIC_CONDITIONS = "economic_conditions"
    REGULATORY_ENVIRONMENT = "regulatory_environment"
    SUSTAINABILITY = "sustainability"
    INTEREST_RATES = "interest_rates"
    ENERGY_TRANSITION = "energy_transition"

    # Aircraft Programs
    WIDEBODY_PROGRAMS = "widebody_programs"
    NARROWBODY_PROGRAMS = "narrowbody_programs"
    DEFENSE_PROGRAMS = "defense_programs"


# =============================================================================
# MAIN DATA MODELS
# =============================================================================

class ExtractedEarningsQuote(BaseModel):
    """
    A pre-extracted executive insight from an earnings call.

    Quotes are extracted during ingestion using LLM-based analysis.
    Each transcript typically yields 10-20 high-value quotes that are
    tagged with themes, speaker role, and confidence level.

    Special attention to:
    - Q&A section analyst questions (what Wall Street is worried about)
    - Hedged responses (potential weakness signals)
    - Competitive commentary (direct mentions of competitors)
    """

    # Identity
    quote_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    transcript_id: str = ""

    # The quote itself
    quote_text: str = ""
    context_summary: Optional[str] = None

    # Speaker attribution
    speaker_name: str = "Unknown"
    speaker_role: SpeakerRole = SpeakerRole.UNKNOWN
    speaker_title: Optional[str] = None
    speaker_company: Optional[str] = None
    speaker_firm: Optional[str] = None  # For analysts (bank/firm)

    # Quote classification
    quote_type: QuoteType = QuoteType.MARKET_COMMENTARY
    themes: List[EarningsQuoteTheme] = Field(default_factory=list)
    sentiment: str = "neutral"  # bullish, bearish, cautious, neutral
    confidence_level: ConfidenceLevel = ConfidenceLevel.CAUTIOUS

    # Entity references
    companies_mentioned: List[str] = Field(default_factory=list)
    brands_mentioned: List[str] = Field(default_factory=list)
    metrics_mentioned: List[str] = Field(default_factory=list)

    # Relevance & quotability
    relevance_score: float = 0.5
    is_quotable: bool = False
    quotability_reason: Optional[str] = None
    business_segment: Optional[str] = None

    # Source context
    ticker: str = ""
    company_name: str = ""
    year: int = 0
    quarter: int = 0
    call_date: Optional[str] = None
    section: CallSection = CallSection.UNKNOWN
    position_in_section: int = 0

    # Audit fields
    extracted_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    extraction_model: str = "claude-haiku-4-5"
    extraction_confidence: float = 0.8

    def to_bq_row(self) -> Dict[str, Any]:
        """Convert to BigQuery row dict for insert_rows_json."""
        import json
        return {
            "quote_id": self.quote_id,
            "transcript_id": self.transcript_id,
            "quote_text": self.quote_text,
            "context_summary": self.context_summary,
            "speaker_name": self.speaker_name,
            "speaker_role": self.speaker_role.value if isinstance(self.speaker_role, SpeakerRole) else self.speaker_role,
            "speaker_title": self.speaker_title,
            "speaker_company": self.speaker_company,
            "speaker_firm": self.speaker_firm,
            "quote_type": self.quote_type.value if isinstance(self.quote_type, QuoteType) else self.quote_type,
            "themes": json.dumps([t.value if isinstance(t, EarningsQuoteTheme) else t for t in self.themes]),
            "sentiment": self.sentiment,
            "confidence_level": self.confidence_level.value if isinstance(self.confidence_level, ConfidenceLevel) else self.confidence_level,
            "companies_mentioned": json.dumps(self.companies_mentioned),
            "brands_mentioned": json.dumps(self.brands_mentioned),
            "metrics_mentioned": json.dumps(self.metrics_mentioned),
            "relevance_score": self.relevance_score,
            "is_quotable": self.is_quotable,
            "quotability_reason": self.quotability_reason,
            "business_segment": self.business_segment,
            "ticker": self.ticker,
            "company_name": self.company_name,
            "year": self.year,
            "quarter": self.quarter,
            "call_date": self.call_date,
            "call_section": self.section.value if isinstance(self.section, CallSection) else self.section,
            "position_in_section": self.position_in_section,
            "extracted_at": self.extracted_at,
            "extraction_model": self.extraction_model,
            "extraction_confidence": self.extraction_confidence,
        }

    def to_display_dict(self) -> Dict[str, Any]:
        """Convert to display-friendly dictionary (for API responses / briefings)."""
        return {
            "quote_id": self.quote_id,
            "quote_text": self.quote_text,
            "context_summary": self.context_summary,
            "speaker": {
                "name": self.speaker_name,
                "role": self.speaker_role.value if isinstance(self.speaker_role, SpeakerRole) else self.speaker_role,
                "title": self.speaker_title,
                "company": self.speaker_company,
                "firm": self.speaker_firm,
            },
            "classification": {
                "quote_type": self.quote_type.value if isinstance(self.quote_type, QuoteType) else self.quote_type,
                "themes": [t.value if isinstance(t, EarningsQuoteTheme) else t for t in self.themes],
                "sentiment": self.sentiment,
                "confidence_level": self.confidence_level.value if isinstance(self.confidence_level, ConfidenceLevel) else self.confidence_level,
            },
            "relevance_score": self.relevance_score,
            "is_quotable": self.is_quotable,
            "business_segment": self.business_segment,
            "source": {
                "ticker": self.ticker,
                "company": self.company_name,
                "year": self.year,
                "quarter": self.quarter,
                "section": self.section.value if isinstance(self.section, CallSection) else self.section,
            },
        }


class EarningsQuoteExtractionResult(BaseModel):
    """
    Result of quote extraction from an earnings transcript.

    Contains extracted quotes plus metadata about the extraction process.
    """

    # Source info
    transcript_id: str = ""
    ticker: str = ""
    company_name: str = ""
    year: int = 0
    quarter: int = 0

    # Extraction results
    quotes: List[ExtractedEarningsQuote] = Field(default_factory=list)
    total_quotes: int = 0
    quotable_count: int = 0

    # Statistics
    quotes_by_section: Dict[str, int] = Field(default_factory=dict)
    quotes_by_type: Dict[str, int] = Field(default_factory=dict)
    quotes_by_role: Dict[str, int] = Field(default_factory=dict)

    # Process metadata
    success: bool = False
    error_message: Optional[str] = None
    extraction_model: str = "claude-haiku-4-5"
    extraction_time_seconds: float = 0.0
    transcript_length: int = 0

    def compute_statistics(self):
        """Compute statistics from extracted quotes."""
        self.total_quotes = len(self.quotes)
        self.quotable_count = sum(1 for q in self.quotes if q.is_quotable)

        self.quotes_by_section = {}
        for q in self.quotes:
            section = q.section.value if isinstance(q.section, CallSection) else q.section
            self.quotes_by_section[section] = self.quotes_by_section.get(section, 0) + 1

        self.quotes_by_type = {}
        for q in self.quotes:
            qtype = q.quote_type.value if isinstance(q.quote_type, QuoteType) else q.quote_type
            self.quotes_by_type[qtype] = self.quotes_by_type.get(qtype, 0) + 1

        self.quotes_by_role = {}
        for q in self.quotes:
            role = q.speaker_role.value if isinstance(q.speaker_role, SpeakerRole) else q.speaker_role
            self.quotes_by_role[role] = self.quotes_by_role.get(role, 0) + 1
