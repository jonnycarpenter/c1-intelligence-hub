"""
ImportYeti Data Models
======================

Pydantic models for ImportYeti trade data.
Maps to BigQuery tables defined in importyeti_data_architecture_reference.md
"""

from datetime import datetime, date
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
import uuid
import re


class SupplierTier(str, Enum):
    """Supplier tier classification."""
    RAW_MATERIAL = "raw_material"
    INTERMEDIATE = "intermediate"
    OTHER = "other"


class CompanyType(str, Enum):
    """US company type classification."""
    DISTRIBUTOR = "distributor"
    OEM = "oem"
    FABRICATOR = "fabricator"
    OTHER = "other"


class ChangeEventType(str, Enum):
    """Types of detected changes."""
    NEW_CUSTOMER = "new_customer"
    LOST_CUSTOMER = "lost_customer"
    NEW_SUPPLIER = "new_supplier"
    LOST_SUPPLIER = "lost_supplier"
    VOLUME_INCREASE = "volume_increase"
    VOLUME_DECREASE = "volume_decrease"
    NEW_PRODUCT = "new_product"
    MARKET_ENTRY = "market_entry"
    DIRECT_SALE_DETECTED = "direct_sale_detected"


class Significance(str, Enum):
    """Event significance levels."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


def normalize_key(name: str) -> str:
    """Normalize a name to a key format (lowercase, hyphenated)."""
    if not name:
        return ""
    # Remove special characters, lowercase, replace spaces with hyphens
    key = re.sub(r'[^\w\s-]', '', name.lower())
    key = re.sub(r'[\s_]+', '-', key)
    return key.strip('-')


def normalize_name(name: str) -> str:
    """Normalize a name for matching (lowercase, stripped)."""
    if not name:
        return ""
    return name.lower().strip()


# =============================================================================
# Nested Structures (for ARRAY<STRUCT> fields)
# =============================================================================

@dataclass
class HSCodeChapter:
    """HS code breakdown."""
    chapter: str
    name: str
    shipments: int
    shipments_pct: float
    weight_kg: Optional[float] = None


@dataclass
class TimePeriod:
    """Time series data point."""
    period: str  # e.g., "2024-01"
    shipments: int
    weight_kg: Optional[float] = None
    teu: Optional[float] = None


@dataclass
class TopSupplier:
    """Summary of a top supplier."""
    supplier_name: str
    shipments_12m: int
    total_shipments: int


@dataclass
class TopCompany:
    """Summary of a top customer."""
    company_name: str
    shipments_12m: int
    total_shipments: int


@dataclass
class TopHSCode:
    """Top HS code with metrics."""
    hs_code: str
    description: str
    shipments: int
    shipments_12m: Optional[int] = None


# =============================================================================
# Entity Models (iy_suppliers, iy_companies)
# =============================================================================

@dataclass
class SupplierProfile:
    """
    Supplier master record.
    Maps to: iy_suppliers BigQuery table
    """
    supplier_id: str  # Normalized key
    supplier_name: str
    also_known_names: List[str] = field(default_factory=list)
    
    # Location
    country: Optional[str] = None
    country_code: Optional[str] = None
    address: Optional[str] = None
    
    # Contact
    website: Optional[str] = None
    phone_number: Optional[str] = None
    
    # Aggregate metrics
    total_shipments: Optional[int] = None
    total_us_customers: Optional[int] = None
    
    # Top products
    primary_hs_codes: List[TopHSCode] = field(default_factory=list)
    
    # Classification
    is_c1_supplier: bool = False
    is_tracked_competitor: bool = False
    supplier_tier: Optional[SupplierTier] = None
    
    # Tracking
    first_seen_date: Optional[date] = None
    last_updated: Optional[datetime] = None
    
    # Raw API response for debugging
    raw_data: Optional[Dict[str, Any]] = None
    
    @classmethod
    def from_api_response(cls, data: Dict[str, Any], snapshot_date: date) -> "SupplierProfile":
        """Create from ImportYeti API response."""
        supplier_id = normalize_key(data.get("title", ""))
        
        # Extract HS codes
        hs_codes = []
        for hs in data.get("hs_code_charts", [])[:5]:  # Top 5
            hs_codes.append(TopHSCode(
                hs_code=str(hs.get("hs_code", "")),
                description=hs.get("name", ""),
                shipments=hs.get("shipments", 0),
                shipments_12m=hs.get("shipments_12m"),
            ))
        
        return cls(
            supplier_id=supplier_id,
            supplier_name=data.get("title", ""),
            also_known_names=data.get("also_known_names", []),
            country=data.get("country"),
            country_code=data.get("country_code"),
            address=data.get("address"),
            website=data.get("website"),
            phone_number=data.get("phone_number"),
            total_shipments=data.get("total_shipments"),
            total_us_customers=data.get("total_companies"),
            primary_hs_codes=hs_codes,
            first_seen_date=snapshot_date,
            last_updated=datetime.utcnow(),
            raw_data=data,
        )


@dataclass
class CompanyProfile:
    """
    US Company (importer) master record.
    Maps to: iy_companies BigQuery table
    """
    company_id: str  # Normalized key
    company_name: str
    also_known_names: List[str] = field(default_factory=list)
    
    # Location
    country: str = "United States"
    country_code: str = "US"
    address: Optional[str] = None
    
    # Contact
    website: Optional[str] = None
    phone_number: Optional[str] = None
    
    # Aggregate metrics
    total_shipments: Optional[int] = None
    total_suppliers: Optional[int] = None
    
    # Top products
    primary_hs_codes: List[TopHSCode] = field(default_factory=list)
    
    # Classification
    company_type: Optional[CompanyType] = None
    industries: List[str] = field(default_factory=list)
    is_c1_customer: bool = False
    is_prospect: bool = False
    
    # Tracking
    first_seen_date: Optional[date] = None
    last_updated: Optional[datetime] = None
    
    # Raw API response
    raw_data: Optional[Dict[str, Any]] = None
    
    @classmethod
    def from_api_response(cls, data: Dict[str, Any], snapshot_date: date) -> "CompanyProfile":
        """Create from ImportYeti API response."""
        company_id = normalize_key(data.get("title", ""))
        
        hs_codes = []
        for hs in data.get("hs_code_charts", [])[:5]:
            hs_codes.append(TopHSCode(
                hs_code=str(hs.get("hs_code", "")),
                description=hs.get("name", ""),
                shipments=hs.get("shipments", 0),
            ))
        
        return cls(
            company_id=company_id,
            company_name=data.get("title", ""),
            also_known_names=data.get("also_known_names", []),
            address=data.get("address"),
            website=data.get("website"),
            phone_number=data.get("phone_number"),
            total_shipments=data.get("total_shipments"),
            total_suppliers=data.get("total_suppliers"),
            primary_hs_codes=hs_codes,
            first_seen_date=snapshot_date,
            last_updated=datetime.utcnow(),
            raw_data=data,
        )


# =============================================================================
# Relationship Models (iy_supplier_customers, iy_company_suppliers)
# =============================================================================

@dataclass
class SupplierCustomerRelationship:
    """
    Supplier → Customer relationship.
    Maps to: iy_supplier_customers BigQuery table
    
    This is the KEY table for competitive intelligence.
    Shows who each supplier sells to.
    """
    relationship_id: str
    snapshot_date: date
    
    # Supplier side
    supplier_id: str
    supplier_name: str
    
    # Customer side (US company)
    customer_name: str
    
    # Optional fields (must come after required fields)
    supplier_country: Optional[str] = None
    customer_name_normalized: str = ""
    customer_address: Optional[str] = None
    customer_country: str = "United States"
    customer_key: Optional[str] = None
    
    # Relationship metrics
    total_shipments_to_customer: Optional[int] = None
    shipments_pct_of_supplier: Optional[float] = None
    shipments_pct_of_customer: Optional[float] = None
    shipments_12m: Optional[int] = None
    
    # Weight/volume
    total_weight_kg: Optional[float] = None
    total_teu: Optional[float] = None
    
    # Products
    hs_code_chapters: List[HSCodeChapter] = field(default_factory=list)
    product_descriptions: List[str] = field(default_factory=list)
    
    # Customer's other suppliers (competitive intel!)
    customer_top_suppliers: List[TopSupplier] = field(default_factory=list)
    
    # Time series
    relationship_time_series: List[TimePeriod] = field(default_factory=list)
    
    # Relationship history
    first_shipment_date: Optional[date] = None
    most_recent_shipment_date: Optional[date] = None
    business_length: Optional[str] = None
    is_new_customer: bool = False
    
    # Tracking
    first_seen_date: Optional[date] = None
    last_seen_date: Optional[date] = None
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def __post_init__(self):
        if not self.customer_name_normalized:
            self.customer_name_normalized = normalize_name(self.customer_name)
        if not self.relationship_id:
            self.relationship_id = str(uuid.uuid4())
    
    @classmethod
    def from_supplier_companies_table(
        cls,
        supplier_data: Dict[str, Any],
        customer_row: Dict[str, Any],
        snapshot_date: date,
    ) -> "SupplierCustomerRelationship":
        """Create from companies_table row in supplier response."""
        
        # Parse HS code chapters
        hs_chapters = []
        for hs in customer_row.get("hs_code_chapters", []):
            hs_chapters.append(HSCodeChapter(
                chapter=str(hs.get("chapter", "")),
                name=hs.get("name", ""),
                shipments=hs.get("shipments", 0),
                shipments_pct=hs.get("shipments_percents", 0),
                weight_kg=hs.get("weight"),
            ))
        
        # Parse time series
        time_series = []
        for period, values in customer_row.get("company_time_series", {}).items():
            time_series.append(TimePeriod(
                period=period,
                shipments=values.get("shipments", 0),
                weight_kg=values.get("weight"),
                teu=values.get("teus"),
            ))
        
        # Parse top suppliers (who else customer buys from)
        top_suppliers = []
        for sup in customer_row.get("top_suppliers", []):
            top_suppliers.append(TopSupplier(
                supplier_name=sup.get("supplier_name", ""),
                shipments_12m=sup.get("shipments_12m", 0),
                total_shipments=sup.get("total_shipments", 0),
            ))
        
        # Parse dates
        first_shipment = None
        if customer_row.get("first_shipment"):
            try:
                first_shipment = datetime.strptime(
                    customer_row["first_shipment"], "%Y-%m-%d"
                ).date()
            except:
                pass
        
        most_recent = None
        if customer_row.get("most_recent_shipment"):
            try:
                most_recent = datetime.strptime(
                    customer_row["most_recent_shipment"], "%Y-%m-%d"
                ).date()
            except:
                pass
        
        return cls(
            relationship_id=str(uuid.uuid4()),
            snapshot_date=snapshot_date,
            supplier_id=normalize_key(supplier_data.get("title", "")),
            supplier_name=supplier_data.get("title", ""),
            supplier_country=supplier_data.get("country"),
            customer_name=customer_row.get("company_name", ""),
            customer_address=customer_row.get("company_address"),
            customer_key=customer_row.get("key"),
            total_shipments_to_customer=customer_row.get("total_shipments_supplier"),
            shipments_pct_of_supplier=customer_row.get("shipments_percents_supplier"),
            shipments_pct_of_customer=customer_row.get("shipments_percents_company"),
            shipments_12m=customer_row.get("shipments_12m"),
            total_weight_kg=customer_row.get("total_weight"),
            total_teu=customer_row.get("total_teus"),
            hs_code_chapters=hs_chapters,
            product_descriptions=customer_row.get("product_descriptions", []),
            customer_top_suppliers=top_suppliers,
            relationship_time_series=time_series,
            first_shipment_date=first_shipment,
            most_recent_shipment_date=most_recent,
            business_length=customer_row.get("business_length"),
            is_new_customer=customer_row.get("is_new_company", False),
            first_seen_date=snapshot_date,
            last_seen_date=snapshot_date,
        )


@dataclass
class CompanySupplierRelationship:
    """
    Company → Supplier relationship.
    Maps to: iy_company_suppliers BigQuery table
    
    Shows who each company buys from.
    """
    relationship_id: str
    snapshot_date: date
    
    # Company side (US importer)
    company_id: str
    company_name: str
    
    # Supplier side
    supplier_name: str
    supplier_name_normalized: str = ""
    supplier_address: Optional[str] = None
    supplier_country: Optional[str] = None
    supplier_key: Optional[str] = None
    
    # Relationship metrics
    total_shipments_from_supplier: Optional[int] = None
    shipments_pct_of_company: Optional[float] = None
    shipments_pct_of_supplier: Optional[float] = None
    shipments_12m: Optional[int] = None
    
    # Weight/volume
    total_weight_kg: Optional[float] = None
    total_teu: Optional[float] = None
    
    # Products
    hs_code_chapters: List[HSCodeChapter] = field(default_factory=list)
    product_descriptions: List[str] = field(default_factory=list)
    
    # Supplier's other customers
    supplier_top_companies: List[TopCompany] = field(default_factory=list)
    
    # Time series
    relationship_time_series: List[TimePeriod] = field(default_factory=list)
    
    # History
    first_shipment_date: Optional[date] = None
    most_recent_shipment_date: Optional[date] = None
    business_length: Optional[str] = None
    
    # Tracking
    first_seen_date: Optional[date] = None
    last_seen_date: Optional[date] = None
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def __post_init__(self):
        if not self.supplier_name_normalized:
            self.supplier_name_normalized = normalize_name(self.supplier_name)
        if not self.relationship_id:
            self.relationship_id = str(uuid.uuid4())
    
    @classmethod
    def from_company_suppliers_table(
        cls,
        company_data: Dict[str, Any],
        supplier_row: Dict[str, Any],
        snapshot_date: date,
    ) -> "CompanySupplierRelationship":
        """Create from suppliers_table row in company response."""
        
        # Parse HS code chapters
        hs_chapters = []
        for hs in supplier_row.get("hs_code_chapters", []):
            hs_chapters.append(HSCodeChapter(
                chapter=str(hs.get("chapter", "")),
                name=hs.get("name", ""),
                shipments=hs.get("shipments", 0),
                shipments_pct=hs.get("shipments_percents", 0),
            ))
        
        # Parse time series
        time_series = []
        for period, values in supplier_row.get("supplier_time_series", {}).items():
            time_series.append(TimePeriod(
                period=period,
                shipments=values.get("shipments", 0),
                weight_kg=values.get("weight"),
                teu=values.get("teus"),
            ))
        
        # Parse top companies (who else supplier sells to)
        top_companies = []
        for comp in supplier_row.get("top_companies", []):
            top_companies.append(TopCompany(
                company_name=comp.get("company_name", ""),
                shipments_12m=comp.get("shipments_12m", 0),
                total_shipments=comp.get("total_shipments", 0),
            ))
        
        # Parse dates
        first_shipment = None
        if supplier_row.get("first_shipment"):
            try:
                first_shipment = datetime.strptime(
                    supplier_row["first_shipment"], "%Y-%m-%d"
                ).date()
            except:
                pass
        
        most_recent = None
        if supplier_row.get("most_recent_shipment"):
            try:
                most_recent = datetime.strptime(
                    supplier_row["most_recent_shipment"], "%Y-%m-%d"
                ).date()
            except:
                pass
        
        return cls(
            relationship_id=str(uuid.uuid4()),
            snapshot_date=snapshot_date,
            company_id=normalize_key(company_data.get("title", "")),
            company_name=company_data.get("title", ""),
            supplier_name=supplier_row.get("supplier_name", ""),
            supplier_address=supplier_row.get("supplier_address"),
            supplier_country=supplier_row.get("supplier_country"),
            supplier_key=supplier_row.get("key"),
            total_shipments_from_supplier=supplier_row.get("total_shipments_company"),
            shipments_pct_of_company=supplier_row.get("shipments_percents_company"),
            shipments_pct_of_supplier=supplier_row.get("shipments_percents_supplier"),
            shipments_12m=supplier_row.get("shipments_12m"),
            total_weight_kg=supplier_row.get("total_weight"),
            total_teu=supplier_row.get("total_teus"),
            hs_code_chapters=hs_chapters,
            product_descriptions=supplier_row.get("product_descriptions", []),
            supplier_top_companies=top_companies,
            relationship_time_series=time_series,
            first_shipment_date=first_shipment,
            most_recent_shipment_date=most_recent,
            business_length=supplier_row.get("business_length"),
            first_seen_date=snapshot_date,
            last_seen_date=snapshot_date,
        )


# =============================================================================
# Product Market Model
# =============================================================================

@dataclass
class ProductMarketResult:
    """
    Product search result.
    Maps to: iy_product_market BigQuery table
    """
    record_id: str
    snapshot_date: date
    
    # Search parameters
    product_search_term: str
    result_type: str  # 'supplier' or 'company'
    
    # Entity info
    entity_name: str
    entity_link: Optional[str] = None
    entity_country: Optional[str] = None
    entity_country_code: Optional[str] = None
    entity_address: Optional[str] = None
    
    # Metrics
    matching_shipments: Optional[int] = None
    specialization_pct: Optional[float] = None
    total_shipments: Optional[int] = None
    experience_years: Optional[float] = None
    relevance_score: Optional[float] = None
    total_weight_kg: Optional[float] = None
    
    # Related entities
    related_entities: List[str] = field(default_factory=list)
    total_related_count: Optional[int] = None
    
    # Products
    product_descriptions: List[str] = field(default_factory=list)
    
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def __post_init__(self):
        if not self.record_id:
            self.record_id = str(uuid.uuid4())


# =============================================================================
# Analytics Models (Trends, Concentration, Changes)
# =============================================================================

@dataclass
class ShipmentTrend:
    """
    Time series metrics for charting.
    Maps to: iy_shipment_trends BigQuery table
    """
    trend_id: str
    period_date: date  # First of month
    
    # Dimension (required fields)
    dimension_type: str  # 'supplier', 'company', 'relationship', 'hs_code', 'country'
    dimension_key: str
    
    # Optional fields (must come after required fields)
    period_type: str = "monthly"
    dimension_name: Optional[str] = None
    
    # Optional secondary dimension
    dimension_key_2: Optional[str] = None
    dimension_name_2: Optional[str] = None
    
    # Metrics
    shipment_count: Optional[int] = None
    weight_kg: Optional[float] = None
    teu: Optional[float] = None
    unique_counterparties: Optional[int] = None
    
    # Change metrics
    shipment_count_prev: Optional[int] = None
    shipment_count_change: Optional[int] = None
    shipment_count_change_pct: Optional[float] = None
    
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ConcentrationMetrics:
    """
    Supplier/customer concentration risk.
    Maps to: iy_concentration_metrics BigQuery table
    """
    metric_id: str
    snapshot_date: date
    entity_type: str  # 'company' or 'supplier'
    entity_id: str
    entity_name: Optional[str] = None
    
    # Counterparty concentration
    total_counterparties: Optional[int] = None
    top_counterparty_name: Optional[str] = None
    top_counterparty_pct: Optional[float] = None
    top_3_counterparty_pct: Optional[float] = None
    top_5_counterparty_pct: Optional[float] = None
    top_10_counterparty_pct: Optional[float] = None
    hhi_index: Optional[float] = None
    
    # Country concentration
    total_countries: Optional[int] = None
    top_country: Optional[str] = None
    top_country_pct: Optional[float] = None
    china_pct: Optional[float] = None
    
    # Product concentration
    total_hs_chapters: Optional[int] = None
    top_hs_chapter: Optional[str] = None
    top_hs_chapter_name: Optional[str] = None
    top_hs_chapter_pct: Optional[float] = None
    
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class CompetitorOverlap:
    """
    C1 supplier direct sales analysis.
    Maps to: iy_competitor_overlap BigQuery table
    """
    overlap_id: str
    snapshot_date: date
    
    # The C1 supplier
    supplier_id: str
    supplier_name: str
    
    # The other customer
    other_customer_name: str
    
    supplier_country: Optional[str] = None
    shipments_to_c1: Optional[int] = None
    
    other_customer_normalized: str = ""
    other_customer_type: Optional[str] = None  # 'oem', 'fabricator', 'distributor', 'other'
    other_customer_industry: Optional[str] = None
    shipments_to_other: Optional[int] = None
    
    # Comparison
    c1_vs_other_ratio: Optional[float] = None
    
    # Products overlap
    shared_hs_codes: List[str] = field(default_factory=list)
    shared_products: List[str] = field(default_factory=list)
    
    # Classification
    overlap_type: Optional[str] = None  # 'direct_competitor', 'oem_bypass', 'market_expansion'
    threat_level: Optional[Significance] = None
    opportunity_flag: bool = False
    
    # Notes
    insight_summary: Optional[str] = None
    
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ChangeEvent:
    """
    Detected change for alerts/digest.
    Maps to: iy_change_events BigQuery table
    """
    event_id: str
    detected_date: datetime
    # Event classification
    event_type: ChangeEventType
    
    snapshot_id: Optional[str] = None
    
    event_category: Optional[str] = None
    
    # Entities involved
    primary_entity_type: Optional[str] = None  # 'supplier' or 'company'
    primary_entity_id: Optional[str] = None
    primary_entity_name: Optional[str] = None
    secondary_entity_name: Optional[str] = None
    
    # Change details
    previous_value: Optional[float] = None
    new_value: Optional[float] = None
    change_absolute: Optional[float] = None
    change_pct: Optional[float] = None
    
    # Context
    hs_codes: List[str] = field(default_factory=list)
    products: List[str] = field(default_factory=list)
    
    # For digest
    summary: str = ""
    significance: Significance = Significance.MEDIUM
    
    # Integration
    digest_item_id: Optional[str] = None
    acknowledged: bool = False
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def __post_init__(self):
        if not self.event_id:
            self.event_id = str(uuid.uuid4())


# =============================================================================
# Snapshot Model (Raw API Responses)
# =============================================================================

@dataclass
class Snapshot:
    """
    Raw API response storage.
    Maps to: iy_snapshots BigQuery table
    """
    snapshot_id: str
    snapshot_date: datetime
    
    # What we pulled
    endpoint_type: str  # 'company', 'supplier', 'product_suppliers', 'product_companies'
    entity_key: str
    entity_name: Optional[str] = None
    
    # Response metadata
    request_cost: int = 1
    credits_remaining: Optional[int] = None
    execution_time_ms: Optional[int] = None
    
    # Raw data
    raw_response: Optional[str] = None  # JSON string
    
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def __post_init__(self):
        if not self.snapshot_id:
            self.snapshot_id = str(uuid.uuid4())
