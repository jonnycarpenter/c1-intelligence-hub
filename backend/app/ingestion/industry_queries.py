"""
Expanded Industry Query Architecture
=====================================

Target: 250 total queries
- Exa.ai: 100 queries (critical, high-quality)
- Tavily: 150 queries (broadening, cost-efficient)

Pricing Reference (approximate):
- Exa: ~$0.003-0.005 per search (with contents)
- Tavily: ~$0.001-0.002 per search (basic)

At 2x daily cadence:
- 250 queries × 2 × 30 days = 15,000 queries/month
- Exa portion: 6,000 queries × $0.004 = ~$24/month
- Tavily portion: 9,000 queries × $0.0015 = ~$13.50/month
- Total: ~$37.50/month (very reasonable for this coverage)
"""

from dataclasses import dataclass
from typing import List, Literal
from enum import Enum

class SearchEngine(Enum):
    EXA = "exa"      # High quality, semantic, better for nuanced queries
    TAVILY = "tavily" # Cost-efficient, good for broad sweeps

class QueryTier(Enum):
    CRITICAL = 1     # Business-critical, fast-moving intel
    STRATEGIC = 2    # Important but less time-sensitive
    MONITORING = 3   # Broad awareness, nice-to-have

@dataclass
class IndustryQuery:
    """Enhanced query with engine assignment"""
    query: str
    category: str
    engine: SearchEngine
    tier: QueryTier
    search_depth: str = "basic"
    max_results: int = 5
    exa_category: str = None  # "news", "company", "research paper", etc.
    notes: str = ""


# =============================================================================
# TIER 1: EXA CRITICAL QUERIES (40 queries)
# These are high-value, fast-moving signals where quality matters most
# =============================================================================

EXA_CRITICAL_SUPPLY_CHAIN = [
    # Supply disruptions - these need to surface FAST
    IndustryQuery(
        query="carbon fiber supply shortage allocation",
        category="supply_chain",
        engine=SearchEngine.EXA,
        tier=QueryTier.CRITICAL,
        search_depth="advanced",
        max_results=10,
        exa_category="news",
        notes="Core material, any disruption affects entire supply chain"
    ),
    IndustryQuery(
        query="epoxy resin shortage price increase 2024 2025",
        category="supply_chain",
        engine=SearchEngine.EXA,
        tier=QueryTier.CRITICAL,
        search_depth="advanced",
        max_results=8,
        exa_category="news",
    ),
    IndustryQuery(
        query="composites raw material shortage force majeure",
        category="supply_chain",
        engine=SearchEngine.EXA,
        tier=QueryTier.CRITICAL,
        search_depth="advanced",
        max_results=8,
        exa_category="news",
    ),
    IndustryQuery(
        query="prepreg supply constraint aerospace backlog",
        category="supply_chain",
        engine=SearchEngine.EXA,
        tier=QueryTier.CRITICAL,
        search_depth="advanced",
        max_results=8,
        exa_category="news",
    ),
    IndustryQuery(
        query="glass fiber production halt plant closure",
        category="supply_chain",
        engine=SearchEngine.EXA,
        tier=QueryTier.CRITICAL,
        search_depth="advanced",
        max_results=8,
        exa_category="news",
    ),
    IndustryQuery(
        query="composite materials tariff import duty trade",
        category="supply_chain",
        engine=SearchEngine.EXA,
        tier=QueryTier.CRITICAL,
        search_depth="advanced",
        max_results=8,
        exa_category="news",
        notes="Trade policy can shift overnight"
    ),
]

EXA_CRITICAL_MA_INVESTMENT = [
    # M&A - high business impact, needs quality sources
    IndustryQuery(
        query="composites company acquisition merger agreement",
        category="ma_investment",
        engine=SearchEngine.EXA,
        tier=QueryTier.CRITICAL,
        search_depth="advanced",
        max_results=10,
        exa_category="news",
    ),
    IndustryQuery(
        query="carbon fiber manufacturer acquisition private equity",
        category="ma_investment",
        engine=SearchEngine.EXA,
        tier=QueryTier.CRITICAL,
        search_depth="advanced",
        max_results=8,
        exa_category="news",
    ),
    IndustryQuery(
        query="composites materials company IPO SPAC funding round",
        category="ma_investment",
        engine=SearchEngine.EXA,
        tier=QueryTier.CRITICAL,
        search_depth="advanced",
        max_results=8,
        exa_category="news",
    ),
    IndustryQuery(
        query="aerospace composites supplier bankruptcy restructuring",
        category="ma_investment",
        engine=SearchEngine.EXA,
        tier=QueryTier.CRITICAL,
        search_depth="advanced",
        max_results=8,
        exa_category="news",
        notes="Supplier distress = supply chain risk"
    ),
]

EXA_CRITICAL_CONTRACTS = [
    # Major contract wins - direct revenue signals
    IndustryQuery(
        query="aerospace composites contract award Boeing Airbus",
        category="contracts",
        engine=SearchEngine.EXA,
        tier=QueryTier.CRITICAL,
        search_depth="advanced",
        max_results=10,
        exa_category="news",
    ),
    IndustryQuery(
        query="defense composites contract military Pentagon DoD",
        category="contracts",
        engine=SearchEngine.EXA,
        tier=QueryTier.CRITICAL,
        search_depth="advanced",
        max_results=8,
        exa_category="news",
    ),
    IndustryQuery(
        query="wind turbine blade contract GE Vestas Siemens Gamesa",
        category="contracts",
        engine=SearchEngine.EXA,
        tier=QueryTier.CRITICAL,
        search_depth="advanced",
        max_results=8,
        exa_category="news",
    ),
    IndustryQuery(
        query="automotive lightweighting contract OEM supplier",
        category="contracts",
        engine=SearchEngine.EXA,
        tier=QueryTier.CRITICAL,
        search_depth="basic",
        max_results=8,
        exa_category="news",
    ),
]

EXA_CRITICAL_KEY_SUPPLIERS = [
    # Tier 1 strategic suppliers - direct C1 impact
    IndustryQuery(
        query="Hexcel carbon fiber production capacity earnings",
        category="key_suppliers",
        engine=SearchEngine.EXA,
        tier=QueryTier.CRITICAL,
        search_depth="basic",
        max_results=8,
        exa_category="news",
    ),
    IndustryQuery(
        query="Toray carbon fiber expansion investment plant",
        category="key_suppliers",
        engine=SearchEngine.EXA,
        tier=QueryTier.CRITICAL,
        search_depth="basic",
        max_results=8,
        exa_category="news",
    ),
    IndustryQuery(
        query="Owens Corning glass fiber composites production",
        category="key_suppliers",
        engine=SearchEngine.EXA,
        tier=QueryTier.CRITICAL,
        search_depth="basic",
        max_results=8,
        exa_category="news",
    ),
    IndustryQuery(
        query="Solvay Syensqo aerospace prepreg composite materials",
        category="key_suppliers",
        engine=SearchEngine.EXA,
        tier=QueryTier.CRITICAL,
        search_depth="basic",
        max_results=8,
        exa_category="news",
    ),
    IndustryQuery(
        query="DuPont Kevlar aramid fiber production",
        category="key_suppliers",
        engine=SearchEngine.EXA,
        tier=QueryTier.CRITICAL,
        search_depth="basic",
        max_results=8,
        exa_category="news",
    ),
    IndustryQuery(
        query="Teijin carbon fiber CFRP thermoplastic",
        category="key_suppliers",
        engine=SearchEngine.EXA,
        tier=QueryTier.CRITICAL,
        search_depth="basic",
        max_results=8,
        exa_category="news",
    ),
    IndustryQuery(
        query="BASF Huntsman epoxy resin polyurethane composites",
        category="key_suppliers",
        engine=SearchEngine.EXA,
        tier=QueryTier.CRITICAL,
        search_depth="basic",
        max_results=8,
        exa_category="news",
    ),
    IndustryQuery(
        query="SGL Carbon graphite carbon fiber automotive aerospace",
        category="key_suppliers",
        engine=SearchEngine.EXA,
        tier=QueryTier.CRITICAL,
        search_depth="basic",
        max_results=8,
        exa_category="news",
    ),
    IndustryQuery(
        query="Gurit wind energy marine composites core materials",
        category="key_suppliers",
        engine=SearchEngine.EXA,
        tier=QueryTier.CRITICAL,
        search_depth="basic",
        max_results=8,
        exa_category="news",
    ),
    IndustryQuery(
        query="Spirit AeroSystems aerostructures composites Boeing",
        category="key_suppliers",
        engine=SearchEngine.EXA,
        tier=QueryTier.CRITICAL,
        search_depth="basic",
        max_results=8,
        exa_category="news",
        notes="Key fabricator, Boeing supply chain bellwether"
    ),
]

EXA_CRITICAL_EMERGING = [
    # Emerging applications - high growth potential
    IndustryQuery(
        query="hydrogen storage tank composite pressure vessel",
        category="emerging",
        engine=SearchEngine.EXA,
        tier=QueryTier.CRITICAL,
        search_depth="advanced",
        max_results=10,
        exa_category="news",
        notes="Major growth market for composites"
    ),
    IndustryQuery(
        query="eVTOL urban air mobility composite airframe structure",
        category="emerging",
        engine=SearchEngine.EXA,
        tier=QueryTier.CRITICAL,
        search_depth="advanced",
        max_results=10,
        exa_category="news",
    ),
    IndustryQuery(
        query="electric vehicle EV battery enclosure composite",
        category="emerging",
        engine=SearchEngine.EXA,
        tier=QueryTier.CRITICAL,
        search_depth="advanced",
        max_results=10,
        exa_category="news",
    ),
    IndustryQuery(
        query="satellite constellation composite structure SpaceX",
        category="emerging",
        engine=SearchEngine.EXA,
        tier=QueryTier.CRITICAL,
        search_depth="advanced",
        max_results=8,
        exa_category="news",
    ),
]


# =============================================================================
# TIER 1: EXA STRATEGIC QUERIES (60 queries)
# Important signals, slightly less time-sensitive
# =============================================================================

EXA_STRATEGIC_OEM_DEMAND = [
    # Major OEM signals - demand indicators
    IndustryQuery(
        query="Boeing 737 787 production rate composite",
        category="oem_demand",
        engine=SearchEngine.EXA,
        tier=QueryTier.STRATEGIC,
        search_depth="basic",
        max_results=8,
        exa_category="news",
    ),
    IndustryQuery(
        query="Airbus A350 A320 production composite materials",
        category="oem_demand",
        engine=SearchEngine.EXA,
        tier=QueryTier.STRATEGIC,
        search_depth="basic",
        max_results=8,
        exa_category="news",
    ),
    IndustryQuery(
        query="Lockheed Martin F-35 composite aerostructure",
        category="oem_demand",
        engine=SearchEngine.EXA,
        tier=QueryTier.STRATEGIC,
        search_depth="basic",
        max_results=8,
        exa_category="news",
    ),
    IndustryQuery(
        query="Northrop Grumman B-21 composite aircraft",
        category="oem_demand",
        engine=SearchEngine.EXA,
        tier=QueryTier.STRATEGIC,
        search_depth="basic",
        max_results=8,
        exa_category="news",
    ),
    IndustryQuery(
        query="GE Vernova wind turbine blade manufacturing",
        category="oem_demand",
        engine=SearchEngine.EXA,
        tier=QueryTier.STRATEGIC,
        search_depth="basic",
        max_results=8,
        exa_category="news",
    ),
    IndustryQuery(
        query="Vestas Siemens Gamesa wind blade composites",
        category="oem_demand",
        engine=SearchEngine.EXA,
        tier=QueryTier.STRATEGIC,
        search_depth="basic",
        max_results=8,
        exa_category="news",
    ),
    IndustryQuery(
        query="Tesla BMW carbon fiber CFRP lightweighting",
        category="oem_demand",
        engine=SearchEngine.EXA,
        tier=QueryTier.STRATEGIC,
        search_depth="basic",
        max_results=8,
        exa_category="news",
    ),
    IndustryQuery(
        query="Raytheon RTX missile defense composite",
        category="oem_demand",
        engine=SearchEngine.EXA,
        tier=QueryTier.STRATEGIC,
        search_depth="basic",
        max_results=8,
        exa_category="news",
    ),
]

EXA_STRATEGIC_CAPACITY = [
    # Capacity expansion - leading indicator
    IndustryQuery(
        query="carbon fiber plant expansion new capacity",
        category="capacity",
        engine=SearchEngine.EXA,
        tier=QueryTier.STRATEGIC,
        search_depth="advanced",
        max_results=8,
        exa_category="news",
    ),
    IndustryQuery(
        query="composites manufacturing facility investment",
        category="capacity",
        engine=SearchEngine.EXA,
        tier=QueryTier.STRATEGIC,
        search_depth="basic",
        max_results=8,
        exa_category="news",
    ),
    IndustryQuery(
        query="prepreg production line expansion aerospace",
        category="capacity",
        engine=SearchEngine.EXA,
        tier=QueryTier.STRATEGIC,
        search_depth="basic",
        max_results=8,
        exa_category="news",
    ),
    IndustryQuery(
        query="resin production capacity chemical plant",
        category="capacity",
        engine=SearchEngine.EXA,
        tier=QueryTier.STRATEGIC,
        search_depth="basic",
        max_results=8,
        exa_category="news",
    ),
]

EXA_STRATEGIC_TECHNOLOGY = [
    # Technology shifts - competitive intelligence
    IndustryQuery(
        query="automated fiber placement AFP ATL robotics",
        category="technology",
        engine=SearchEngine.EXA,
        tier=QueryTier.STRATEGIC,
        search_depth="advanced",
        max_results=8,
        exa_category="news",
    ),
    IndustryQuery(
        query="thermoplastic composites PEEK PEKK aerospace automotive",
        category="technology",
        engine=SearchEngine.EXA,
        tier=QueryTier.STRATEGIC,
        search_depth="advanced",
        max_results=8,
        exa_category="news",
    ),
    IndustryQuery(
        query="composite recycling carbon fiber reclamation",
        category="technology",
        engine=SearchEngine.EXA,
        tier=QueryTier.STRATEGIC,
        search_depth="advanced",
        max_results=8,
        exa_category="news",
    ),
    IndustryQuery(
        query="out-of-autoclave OOA composite curing",
        category="technology",
        engine=SearchEngine.EXA,
        tier=QueryTier.STRATEGIC,
        search_depth="basic",
        max_results=8,
        exa_category="news",
    ),
    IndustryQuery(
        query="composite 3D printing additive manufacturing continuous fiber",
        category="technology",
        engine=SearchEngine.EXA,
        tier=QueryTier.STRATEGIC,
        search_depth="advanced",
        max_results=8,
        exa_category="news",
    ),
    IndustryQuery(
        query="digital twin composites manufacturing simulation",
        category="technology",
        engine=SearchEngine.EXA,
        tier=QueryTier.STRATEGIC,
        search_depth="basic",
        max_results=6,
        exa_category="news",
    ),
]

EXA_STRATEGIC_REGULATORY = [
    # Regulatory/policy - can create sudden shifts
    IndustryQuery(
        query="PFAS composites regulation ban fluoropolymer",
        category="regulatory",
        engine=SearchEngine.EXA,
        tier=QueryTier.STRATEGIC,
        search_depth="advanced",
        max_results=8,
        exa_category="news",
        notes="PFAS regulations could impact coatings/release agents"
    ),
    IndustryQuery(
        query="carbon border adjustment composites manufacturing",
        category="regulatory",
        engine=SearchEngine.EXA,
        tier=QueryTier.STRATEGIC,
        search_depth="basic",
        max_results=6,
        exa_category="news",
    ),
    IndustryQuery(
        query="EPA VOC composites manufacturing regulation styrene",
        category="regulatory",
        engine=SearchEngine.EXA,
        tier=QueryTier.STRATEGIC,
        search_depth="basic",
        max_results=6,
        exa_category="news",
    ),
    IndustryQuery(
        query="REACH composites chemical regulation Europe",
        category="regulatory",
        engine=SearchEngine.EXA,
        tier=QueryTier.STRATEGIC,
        search_depth="basic",
        max_results=6,
        exa_category="news",
    ),
]

EXA_STRATEGIC_ADDITIONAL_SUPPLIERS = [
    # Additional key suppliers - C1 network
    IndustryQuery(
        query="Mitsubishi Chemical carbon fiber MRC",
        category="key_suppliers",
        engine=SearchEngine.EXA,
        tier=QueryTier.STRATEGIC,
        search_depth="basic",
        max_results=6,
        exa_category="news",
    ),
    IndustryQuery(
        query="AOC Polynt vinyl ester polyester resin",
        category="key_suppliers",
        engine=SearchEngine.EXA,
        tier=QueryTier.STRATEGIC,
        search_depth="basic",
        max_results=6,
        exa_category="news",
    ),
    IndustryQuery(
        query="3M composites adhesives abrasives aerospace",
        category="key_suppliers",
        engine=SearchEngine.EXA,
        tier=QueryTier.STRATEGIC,
        search_depth="basic",
        max_results=6,
        exa_category="news",
    ),
    IndustryQuery(
        query="Hexion epoxy phenolic resin composites",
        category="key_suppliers",
        engine=SearchEngine.EXA,
        tier=QueryTier.STRATEGIC,
        search_depth="basic",
        max_results=6,
        exa_category="news",
    ),
    IndustryQuery(
        query="DIAB core materials foam wind marine",
        category="key_suppliers",
        engine=SearchEngine.EXA,
        tier=QueryTier.STRATEGIC,
        search_depth="basic",
        max_results=6,
        exa_category="news",
    ),
    IndustryQuery(
        query="Chomarat Vectorply reinforcement fabrics",
        category="key_suppliers",
        engine=SearchEngine.EXA,
        tier=QueryTier.STRATEGIC,
        search_depth="basic",
        max_results=6,
        exa_category="news",
    ),
]

EXA_STRATEGIC_INDUSTRY_DEMAND = [
    # Industry-specific demand signals
    IndustryQuery(
        query="aerospace composites forecast demand outlook",
        category="industry_demand",
        engine=SearchEngine.EXA,
        tier=QueryTier.STRATEGIC,
        search_depth="advanced",
        max_results=8,
        exa_category="news",
    ),
    IndustryQuery(
        query="wind energy composites market growth forecast",
        category="industry_demand",
        engine=SearchEngine.EXA,
        tier=QueryTier.STRATEGIC,
        search_depth="advanced",
        max_results=8,
        exa_category="news",
    ),
    IndustryQuery(
        query="automotive composites lightweighting market forecast",
        category="industry_demand",
        engine=SearchEngine.EXA,
        tier=QueryTier.STRATEGIC,
        search_depth="advanced",
        max_results=8,
        exa_category="news",
    ),
    IndustryQuery(
        query="marine boat building fiberglass composites demand",
        category="industry_demand",
        engine=SearchEngine.EXA,
        tier=QueryTier.STRATEGIC,
        search_depth="basic",
        max_results=6,
        exa_category="news",
    ),
    IndustryQuery(
        query="defense composites spending budget military",
        category="industry_demand",
        engine=SearchEngine.EXA,
        tier=QueryTier.STRATEGIC,
        search_depth="basic",
        max_results=6,
        exa_category="news",
    ),
]

EXA_STRATEGIC_FABRICATORS = [
    # Key fabricators/processors
    IndustryQuery(
        query="TPI Composites wind blade manufacturing",
        category="fabricators",
        engine=SearchEngine.EXA,
        tier=QueryTier.STRATEGIC,
        search_depth="basic",
        max_results=6,
        exa_category="news",
    ),
    IndustryQuery(
        query="Albany International aerospace composites 3D woven",
        category="fabricators",
        engine=SearchEngine.EXA,
        tier=QueryTier.STRATEGIC,
        search_depth="basic",
        max_results=6,
        exa_category="news",
    ),
    IndustryQuery(
        query="Park Aerospace composite materials prepreg",
        category="fabricators",
        engine=SearchEngine.EXA,
        tier=QueryTier.STRATEGIC,
        search_depth="basic",
        max_results=6,
        exa_category="news",
    ),
    IndustryQuery(
        query="Ducommun aerospace composite structures",
        category="fabricators",
        engine=SearchEngine.EXA,
        tier=QueryTier.STRATEGIC,
        search_depth="basic",
        max_results=6,
        exa_category="news",
    ),
]


# =============================================================================
# TIER 2: TAVILY BROADENING QUERIES (150 queries)
# Wider coverage, less time-sensitive, cost-efficient
# =============================================================================

TAVILY_INDUSTRY_VERTICAL = [
    # Deeper industry coverage - 16 industries × 3-4 queries each
    # AEROSPACE
    IndustryQuery(
        query="commercial aircraft composites supply chain",
        category="industry_aerospace",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="business jet composite airframe nacelle",
        category="industry_aerospace",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="helicopter rotor blade composite manufacturing",
        category="industry_aerospace",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    # DEFENSE
    IndustryQuery(
        query="military vehicle composite armor protection",
        category="industry_defense",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="naval ship composite superstructure hull",
        category="industry_defense",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="UAV drone composite airframe military",
        category="industry_defense",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    # WIND ENERGY
    IndustryQuery(
        query="offshore wind turbine blade composites",
        category="industry_wind",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="wind blade recycling end-of-life composite",
        category="industry_wind",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="wind turbine nacelle cover composite fiberglass",
        category="industry_wind",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    # MARINE
    IndustryQuery(
        query="boat hull construction fiberglass infusion",
        category="industry_marine",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="yacht superyacht carbon fiber composite",
        category="industry_marine",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="commercial fishing boat fiberglass manufacturing",
        category="industry_marine",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="pontoon boat deck composite materials",
        category="industry_marine",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    # AUTOMOTIVE
    IndustryQuery(
        query="automotive body panel SMC carbon fiber",
        category="industry_automotive",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="electric vehicle structural composite battery",
        category="industry_automotive",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="truck trailer composite body lightweight",
        category="industry_automotive",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="automotive OEM Tier 1 composite supplier",
        category="industry_automotive",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    # CONSTRUCTION
    IndustryQuery(
        query="FRP rebar concrete reinforcement construction",
        category="industry_construction",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="composite cladding facade building panel",
        category="industry_construction",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="fiberglass window door profile pultrusion",
        category="industry_construction",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    # INFRASTRUCTURE
    IndustryQuery(
        query="composite bridge deck FRP pedestrian",
        category="industry_infrastructure",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="utility pole composite fiberglass transmission",
        category="industry_infrastructure",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="pipeline composite repair rehabilitation",
        category="industry_infrastructure",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    # RAIL
    IndustryQuery(
        query="train interior composite panel fire safety",
        category="industry_rail",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="rail car composite body lightweight",
        category="industry_rail",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    # SPORTS & RECREATION
    IndustryQuery(
        query="bicycle frame carbon fiber CFRP manufacturing",
        category="industry_sports",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="golf club shaft carbon fiber composite",
        category="industry_sports",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="RV recreational vehicle composite body panel",
        category="industry_sports",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    # SPACE
    IndustryQuery(
        query="rocket payload fairing composite structure",
        category="industry_space",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="spacecraft composite tank cryogenic propellant",
        category="industry_space",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    # MEDICAL
    IndustryQuery(
        query="medical imaging table carbon fiber radiolucent",
        category="industry_medical",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="prosthetic limb carbon fiber composite",
        category="industry_medical",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    # OIL & GAS
    IndustryQuery(
        query="composite pipe offshore oil gas",
        category="industry_oilgas",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="spoolable composite pipe TCP RTP",
        category="industry_oilgas",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
]

TAVILY_MATERIALS_COVERAGE = [
    # Materials-specific monitoring - catching niche material news
    IndustryQuery(
        query="vinyl ester resin marine corrosion resistant",
        category="materials",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="phenolic resin fire retardant composite",
        category="materials",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="polyurethane foam core composite sandwich",
        category="materials",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="PVC foam core Divinycell structural",
        category="materials",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="balsa wood core composite marine wind",
        category="materials",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="honeycomb core aluminum Nomex aerospace",
        category="materials",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="natural fiber composite flax hemp sustainable",
        category="materials",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="basalt fiber reinforcement construction infrastructure",
        category="materials",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="S-glass high strength ballistic armor",
        category="materials",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="E-glass fiberglass reinforcement general purpose",
        category="materials",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="gel coat finish marine mold release",
        category="materials",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="structural adhesive bonding composite assembly",
        category="materials",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
]

TAVILY_PROCESS_COVERAGE = [
    # Process-specific monitoring
    IndustryQuery(
        query="vacuum infusion VARTM process marine wind",
        category="processes",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="resin transfer molding RTM aerospace automotive",
        category="processes",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="compression molding SMC BMC automotive",
        category="processes",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="pultrusion FRP profile window infrastructure",
        category="processes",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="filament winding pressure vessel tank pipe",
        category="processes",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="hand layup open mold fiberglass boat",
        category="processes",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="spray up chopper gun fiberglass mold",
        category="processes",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
]

TAVILY_REGIONAL_MARKETS = [
    # Regional market coverage
    IndustryQuery(
        query="China composites manufacturing carbon fiber",
        category="regional",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="Europe composites industry Germany France UK",
        category="regional",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="Japan composites Toray Teijin Mitsubishi",
        category="regional",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="India composites manufacturing growth",
        category="regional",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="Mexico nearshoring composites manufacturing",
        category="regional",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="Middle East composites Saudi Arabia UAE",
        category="regional",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
]

TAVILY_EVENTS_CONFERENCES = [
    # Trade shows and industry events
    IndustryQuery(
        query="CAMX composites trade show conference",
        category="events",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="JEC World composites show Paris",
        category="events",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="IBEX boat show marine composites",
        category="events",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="SAMPE conference aerospace materials",
        category="events",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="CompositesWorld news article",
        category="events",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
]

TAVILY_SECONDARY_SUPPLIERS = [
    # Broader supplier coverage (not Tier 1)
    IndustryQuery(
        query="Ashland specialty ingredients composites",
        category="suppliers_secondary",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="Arkema adhesives composites Bostik",
        category="suppliers_secondary",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="Evonik additives silica composites",
        category="suppliers_secondary",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="Strongwell pultrusion FRP structural",
        category="suppliers_secondary",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="Creative Composites Group infrastructure",
        category="suppliers_secondary",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="Barrday prepreg aerospace defense",
        category="suppliers_secondary",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="A&P Technology braided reinforcements",
        category="suppliers_secondary",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="AGY glass fiber reinforcement S-glass",
        category="suppliers_secondary",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="PRO-SET epoxy marine composites",
        category="suppliers_secondary",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="Scott Bader adhesives gelcoat resins",
        category="suppliers_secondary",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
]

TAVILY_ADDITIONAL_EMERGING = [
    # More emerging applications
    IndustryQuery(
        query="data center composite cooling thermal management",
        category="emerging",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="hyperloop high speed rail composite tube",
        category="emerging",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="autonomous vehicle robotaxi composite body",
        category="emerging",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="modular construction composite prefab building",
        category="emerging",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="electric aircraft hybrid propulsion composite",
        category="emerging",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="green hydrogen electrolyzer composite",
        category="emerging",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
]

TAVILY_SUSTAINABILITY = [
    # Sustainability focus
    IndustryQuery(
        query="sustainable composites bio-based resin",
        category="sustainability",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="composite recycling pyrolysis solvolysis",
        category="sustainability",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="circular economy composites end of life",
        category="sustainability",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="EPD environmental product declaration composites",
        category="sustainability",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="low carbon composites manufacturing emissions",
        category="sustainability",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
]

TAVILY_WORKFORCE_OPERATIONS = [
    # Workforce and operations
    IndustryQuery(
        query="composites workforce shortage skilled labor",
        category="operations",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="composites manufacturing training apprenticeship",
        category="operations",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="composites factory automation robotics",
        category="operations",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
]

TAVILY_ADDITIONAL_OEMS = [
    # Additional OEM coverage
    IndustryQuery(
        query="Textron aviation composite aircraft",
        category="oem_secondary",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="Embraer composite aircraft structures",
        category="oem_secondary",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="Bombardier business jet composite",
        category="oem_secondary",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="General Dynamics defense composite",
        category="oem_secondary",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="Collins Aerospace RTX composite structures",
        category="oem_secondary",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="Safran aerospace composite nacelle",
        category="oem_secondary",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="Brunswick marine boat fiberglass composite",
        category="oem_secondary",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="Malibu Boats composite hull manufacturing",
        category="oem_secondary",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="PACCAR Peterbilt Kenworth composite truck",
        category="oem_secondary",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="Ford GM composite pickup truck bed",
        category="oem_secondary",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
]

TAVILY_ADDITIONAL_CONTRACTS = [
    # Broader contract coverage
    IndustryQuery(
        query="marine boat builder composites contract",
        category="contracts_secondary",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="infrastructure FRP composite bridge contract",
        category="contracts_secondary",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="rail transit composite interior contract",
        category="contracts_secondary",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="sporting goods composite manufacturing contract",
        category="contracts_secondary",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
]


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_all_exa_queries() -> List[IndustryQuery]:
    """Get all Exa queries (100 total target)"""
    return (
        EXA_CRITICAL_SUPPLY_CHAIN +
        EXA_CRITICAL_MA_INVESTMENT +
        EXA_CRITICAL_CONTRACTS +
        EXA_CRITICAL_KEY_SUPPLIERS +
        EXA_CRITICAL_EMERGING +
        EXA_STRATEGIC_OEM_DEMAND +
        EXA_STRATEGIC_CAPACITY +
        EXA_STRATEGIC_TECHNOLOGY +
        EXA_STRATEGIC_REGULATORY +
        EXA_STRATEGIC_ADDITIONAL_SUPPLIERS +
        EXA_STRATEGIC_INDUSTRY_DEMAND +
        EXA_STRATEGIC_FABRICATORS
    )


def get_all_tavily_queries() -> List[IndustryQuery]:
    """Get all Tavily queries (150 total target)"""
    return (
        TAVILY_INDUSTRY_VERTICAL +
        TAVILY_MATERIALS_COVERAGE +
        TAVILY_PROCESS_COVERAGE +
        TAVILY_REGIONAL_MARKETS +
        TAVILY_EVENTS_CONFERENCES +
        TAVILY_SECONDARY_SUPPLIERS +
        TAVILY_ADDITIONAL_EMERGING +
        TAVILY_SUSTAINABILITY +
        TAVILY_WORKFORCE_OPERATIONS +
        TAVILY_ADDITIONAL_OEMS +
        TAVILY_ADDITIONAL_CONTRACTS
    )


def get_all_queries() -> List[IndustryQuery]:
    """Get all queries"""
    return get_all_exa_queries() + get_all_tavily_queries()


def get_queries_by_engine(engine: SearchEngine) -> List[IndustryQuery]:
    """Get queries for a specific search engine"""
    all_queries = get_all_queries()
    return [q for q in all_queries if q.engine == engine]


def get_queries_by_tier(tier: QueryTier) -> List[IndustryQuery]:
    """Get queries by priority tier"""
    all_queries = get_all_queries()
    return [q for q in all_queries if q.tier == tier]


def get_query_stats():
    """Print query statistics"""
    all_queries = get_all_queries()
    exa_queries = get_all_exa_queries()
    tavily_queries = get_all_tavily_queries()
    
    print("=" * 60)
    print("QUERY ARCHITECTURE STATISTICS")
    print("=" * 60)
    print(f"\nTotal Queries: {len(all_queries)}")
    print(f"  - Exa.ai:  {len(exa_queries)}")
    print(f"  - Tavily:  {len(tavily_queries)}")
    
    print(f"\nBy Tier:")
    for tier in QueryTier:
        count = len([q for q in all_queries if q.tier == tier])
        print(f"  - {tier.name}: {count}")
    
    print(f"\nBy Category (Exa):")
    exa_cats = {}
    for q in exa_queries:
        exa_cats[q.category] = exa_cats.get(q.category, 0) + 1
    for cat, count in sorted(exa_cats.items(), key=lambda x: -x[1]):
        print(f"  - {cat}: {count}")
    
    print(f"\nBy Category (Tavily):")
    tavily_cats = {}
    for q in tavily_queries:
        tavily_cats[q.category] = tavily_cats.get(q.category, 0) + 1
    for cat, count in sorted(tavily_cats.items(), key=lambda x: -x[1]):
        print(f"  - {cat}: {count}")
    
    # Estimate monthly cost
    monthly_queries_exa = len(exa_queries) * 2 * 30  # 2x daily
    monthly_queries_tavily = len(tavily_queries) * 2 * 30
    exa_cost = monthly_queries_exa * 0.004
    tavily_cost = monthly_queries_tavily * 0.0015
    
    print(f"\nEstimated Monthly Cost:")
    print(f"  - Exa ({monthly_queries_exa:,} queries): ${exa_cost:.2f}")
    print(f"  - Tavily ({monthly_queries_tavily:,} queries): ${tavily_cost:.2f}")
    print(f"  - Total: ${exa_cost + tavily_cost:.2f}")


if __name__ == "__main__":
    get_query_stats()


# =============================================================================
# ADDITIONAL QUERIES TO HIT 250 TARGET
# =============================================================================

# Additional Exa queries to reach ~100
EXA_ADDITIONAL_SUPPLIERS = [
    IndustryQuery(
        query="Cytec Solvay aerospace composite prepreg",
        category="key_suppliers",
        engine=SearchEngine.EXA,
        tier=QueryTier.STRATEGIC,
        search_depth="basic",
        max_results=6,
        exa_category="news",
    ),
    IndustryQuery(
        query="Zoltek carbon fiber wind automotive",
        category="key_suppliers",
        engine=SearchEngine.EXA,
        tier=QueryTier.STRATEGIC,
        search_depth="basic",
        max_results=6,
        exa_category="news",
    ),
    IndustryQuery(
        query="Covestro polyurethane composites automotive",
        category="key_suppliers",
        engine=SearchEngine.EXA,
        tier=QueryTier.STRATEGIC,
        search_depth="basic",
        max_results=6,
        exa_category="news",
    ),
    IndustryQuery(
        query="Lanxess high performance materials composites",
        category="key_suppliers",
        engine=SearchEngine.EXA,
        tier=QueryTier.STRATEGIC,
        search_depth="basic",
        max_results=6,
        exa_category="news",
    ),
    IndustryQuery(
        query="Continental Structural Plastics CSP SMC",
        category="key_suppliers",
        engine=SearchEngine.EXA,
        tier=QueryTier.STRATEGIC,
        search_depth="basic",
        max_results=6,
        exa_category="news",
    ),
    IndustryQuery(
        query="GKN Aerospace composite aerostructures",
        category="key_suppliers",
        engine=SearchEngine.EXA,
        tier=QueryTier.STRATEGIC,
        search_depth="basic",
        max_results=6,
        exa_category="news",
    ),
]

EXA_ADDITIONAL_SUPPLY_CHAIN = [
    IndustryQuery(
        query="aerospace supply chain bottleneck composite",
        category="supply_chain",
        engine=SearchEngine.EXA,
        tier=QueryTier.CRITICAL,
        search_depth="advanced",
        max_results=8,
        exa_category="news",
    ),
    IndustryQuery(
        query="raw material cost inflation composites chemicals",
        category="supply_chain",
        engine=SearchEngine.EXA,
        tier=QueryTier.CRITICAL,
        search_depth="advanced",
        max_results=8,
        exa_category="news",
    ),
    IndustryQuery(
        query="shipping logistics composites freight delay",
        category="supply_chain",
        engine=SearchEngine.EXA,
        tier=QueryTier.STRATEGIC,
        search_depth="basic",
        max_results=6,
        exa_category="news",
    ),
    IndustryQuery(
        query="inventory destocking composites manufacturing",
        category="supply_chain",
        engine=SearchEngine.EXA,
        tier=QueryTier.STRATEGIC,
        search_depth="basic",
        max_results=6,
        exa_category="news",
    ),
]

EXA_ADDITIONAL_CONTRACTS = [
    IndustryQuery(
        query="NASA space launch system composite contract",
        category="contracts",
        engine=SearchEngine.EXA,
        tier=QueryTier.STRATEGIC,
        search_depth="basic",
        max_results=6,
        exa_category="news",
    ),
    IndustryQuery(
        query="Army Navy Marine Corps composite contract award",
        category="contracts",
        engine=SearchEngine.EXA,
        tier=QueryTier.STRATEGIC,
        search_depth="basic",
        max_results=6,
        exa_category="news",
    ),
    IndustryQuery(
        query="infrastructure bill composite FRP project award",
        category="contracts",
        engine=SearchEngine.EXA,
        tier=QueryTier.STRATEGIC,
        search_depth="basic",
        max_results=6,
        exa_category="news",
    ),
]

EXA_ADDITIONAL_EMERGING = [
    IndustryQuery(
        query="flying car air taxi composite fuselage",
        category="emerging",
        engine=SearchEngine.EXA,
        tier=QueryTier.STRATEGIC,
        search_depth="basic",
        max_results=6,
        exa_category="news",
    ),
    IndustryQuery(
        query="carbon capture storage composite tank vessel",
        category="emerging",
        engine=SearchEngine.EXA,
        tier=QueryTier.STRATEGIC,
        search_depth="basic",
        max_results=6,
        exa_category="news",
    ),
    IndustryQuery(
        query="fusion energy composite structural materials",
        category="emerging",
        engine=SearchEngine.EXA,
        tier=QueryTier.STRATEGIC,
        search_depth="basic",
        max_results=6,
        exa_category="news",
    ),
    IndustryQuery(
        query="supersonic aircraft composite structure Boom",
        category="emerging",
        engine=SearchEngine.EXA,
        tier=QueryTier.STRATEGIC,
        search_depth="basic",
        max_results=6,
        exa_category="news",
    ),
]

EXA_ADDITIONAL_MA = [
    IndustryQuery(
        query="composites materials divestiture spinoff sale",
        category="ma_investment",
        engine=SearchEngine.EXA,
        tier=QueryTier.STRATEGIC,
        search_depth="basic",
        max_results=6,
        exa_category="news",
    ),
    IndustryQuery(
        query="carbon fiber joint venture partnership strategic",
        category="ma_investment",
        engine=SearchEngine.EXA,
        tier=QueryTier.STRATEGIC,
        search_depth="basic",
        max_results=6,
        exa_category="news",
    ),
]

EXA_ADDITIONAL_TECHNOLOGY = [
    IndustryQuery(
        query="dry fiber placement composites manufacturing",
        category="technology",
        engine=SearchEngine.EXA,
        tier=QueryTier.STRATEGIC,
        search_depth="basic",
        max_results=6,
        exa_category="news",
    ),
    IndustryQuery(
        query="high rate composite production automation",
        category="technology",
        engine=SearchEngine.EXA,
        tier=QueryTier.STRATEGIC,
        search_depth="basic",
        max_results=6,
        exa_category="news",
    ),
    IndustryQuery(
        query="structural health monitoring composite NDT",
        category="technology",
        engine=SearchEngine.EXA,
        tier=QueryTier.STRATEGIC,
        search_depth="basic",
        max_results=6,
        exa_category="news",
    ),
    IndustryQuery(
        query="AI machine learning composites manufacturing quality",
        category="technology",
        engine=SearchEngine.EXA,
        tier=QueryTier.STRATEGIC,
        search_depth="basic",
        max_results=6,
        exa_category="news",
    ),
]

EXA_ADDITIONAL_OEM = [
    IndustryQuery(
        query="Joby Archer Lilium eVTOL composite production",
        category="oem_demand",
        engine=SearchEngine.EXA,
        tier=QueryTier.STRATEGIC,
        search_depth="basic",
        max_results=6,
        exa_category="news",
    ),
    IndustryQuery(
        query="SpaceX Starship composite tank structure",
        category="oem_demand",
        engine=SearchEngine.EXA,
        tier=QueryTier.STRATEGIC,
        search_depth="basic",
        max_results=6,
        exa_category="news",
    ),
    IndustryQuery(
        query="Blue Origin rocket composite structures",
        category="oem_demand",
        engine=SearchEngine.EXA,
        tier=QueryTier.STRATEGIC,
        search_depth="basic",
        max_results=6,
        exa_category="news",
    ),
]

# Additional Tavily queries to reach ~150
TAVILY_MORE_INDUSTRIES = [
    IndustryQuery(
        query="pool spa hot tub fiberglass composite",
        category="industry_consumer",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="bathroom fixture composite sink tub shower",
        category="industry_consumer",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="playground equipment composite structure",
        category="industry_consumer",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="electrical enclosure composite SMC BMC",
        category="industry_electrical",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="telecommunications antenna radome composite",
        category="industry_telecom",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="agricultural equipment composite tractor",
        category="industry_agriculture",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="mining equipment composite wear parts",
        category="industry_mining",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="water wastewater treatment composite FRP",
        category="industry_water",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="chemical processing tank composite corrosion",
        category="industry_chemical",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="food processing equipment composite sanitary",
        category="industry_food",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
]

TAVILY_MORE_MATERIALS = [
    IndustryQuery(
        query="chopped strand mat CSM fiberglass hand layup",
        category="materials",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="woven roving fabric fiberglass reinforcement",
        category="materials",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="multiaxial fabric stitched reinforcement",
        category="materials",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="unidirectional tape UD composite layup",
        category="materials",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="mold release agent composites wax silicone",
        category="materials",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="initiator catalyst MEKP composites curing",
        category="materials",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="surfacing veil non-woven composites finish",
        category="materials",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="peel ply release fabric vacuum bagging",
        category="materials",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
]

TAVILY_MORE_SUPPLIERS = [
    IndustryQuery(
        query="Nouryon initiators composites polyester",
        category="suppliers_secondary",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="Magnum Venus Products MVP composites equipment",
        category="suppliers_secondary",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="Chem-Trend mold release composites",
        category="suppliers_secondary",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="Freudenberg nonwoven veil composites",
        category="suppliers_secondary",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="Lincoln Fabrics BGF carbon aramid",
        category="suppliers_secondary",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="Nan Ya epoxy resin composites",
        category="suppliers_secondary",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="Entropy bio-based epoxy sustainable composites",
        category="suppliers_secondary",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="CPIC glass fiber reinforcement China",
        category="suppliers_secondary",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="Jushi glass fiber production capacity",
        category="suppliers_secondary",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
]

TAVILY_MORE_REGIONAL = [
    IndustryQuery(
        query="Southeast Asia composites manufacturing Vietnam Thailand",
        category="regional",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="Turkey composites manufacturing wind marine",
        category="regional",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="Brazil South America composites market",
        category="regional",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="Korea composites Hyosung SK Chemicals",
        category="regional",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="Taiwan composites manufacturing Formosa",
        category="regional",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
]

TAVILY_MORE_TECHNOLOGY = [
    IndustryQuery(
        query="closed mold composites light RTM infusion",
        category="technology",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="in-situ consolidation thermoplastic composites",
        category="technology",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="UV curing composites rapid manufacturing",
        category="technology",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="snap cure epoxy fast cycle composites",
        category="technology",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="electromagnetic forming joining composites metal",
        category="technology",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="induction heating composites welding thermoplastic",
        category="technology",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
]

TAVILY_MORE_MARKET = [
    IndustryQuery(
        query="composites market size forecast CAGR growth",
        category="market",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="carbon fiber market price trend forecast",
        category="market",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="glass fiber market capacity demand supply",
        category="market",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="epoxy resin market outlook demand drivers",
        category="market",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
    IndustryQuery(
        query="prepreg market aerospace automotive growth",
        category="market",
        engine=SearchEngine.TAVILY,
        tier=QueryTier.MONITORING,
        search_depth="basic",
        max_results=5,
    ),
]


# Update the helper functions
def get_all_exa_queries_v2() -> List[IndustryQuery]:
    """Get all Exa queries (100 total target)"""
    return (
        EXA_CRITICAL_SUPPLY_CHAIN +
        EXA_CRITICAL_MA_INVESTMENT +
        EXA_CRITICAL_CONTRACTS +
        EXA_CRITICAL_KEY_SUPPLIERS +
        EXA_CRITICAL_EMERGING +
        EXA_STRATEGIC_OEM_DEMAND +
        EXA_STRATEGIC_CAPACITY +
        EXA_STRATEGIC_TECHNOLOGY +
        EXA_STRATEGIC_REGULATORY +
        EXA_STRATEGIC_ADDITIONAL_SUPPLIERS +
        EXA_STRATEGIC_INDUSTRY_DEMAND +
        EXA_STRATEGIC_FABRICATORS +
        # Additional queries
        EXA_ADDITIONAL_SUPPLIERS +
        EXA_ADDITIONAL_SUPPLY_CHAIN +
        EXA_ADDITIONAL_CONTRACTS +
        EXA_ADDITIONAL_EMERGING +
        EXA_ADDITIONAL_MA +
        EXA_ADDITIONAL_TECHNOLOGY +
        EXA_ADDITIONAL_OEM
    )


def get_all_tavily_queries_v2() -> List[IndustryQuery]:
    """Get all Tavily queries (75 total - optimized Jan 2026)
    
    Reduced from 145 to 75 queries to fit within Cloud Scheduler timeout.
    Prioritized: core industry verticals, key materials, critical suppliers.
    """
    return TAVILY_OPTIMIZED_75


# =============================================================================
# OPTIMIZED TAVILY QUERIES (75 queries) - January 2026
# Reduced from 145 to improve ingestion reliability
# =============================================================================

TAVILY_OPTIMIZED_75 = [
    # --- Industry Verticals (25) ---
    IndustryQuery(query="commercial aircraft composites supply chain", category="industry_aerospace", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    IndustryQuery(query="helicopter rotor blade composite manufacturing", category="industry_aerospace", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    IndustryQuery(query="military vehicle composite armor protection", category="industry_defense", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    IndustryQuery(query="UAV drone composite airframe military", category="industry_defense", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    IndustryQuery(query="offshore wind turbine blade composites", category="industry_wind", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    IndustryQuery(query="wind blade recycling end-of-life composite", category="industry_wind", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    IndustryQuery(query="boat hull construction fiberglass infusion", category="industry_marine", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    IndustryQuery(query="yacht superyacht carbon fiber composite", category="industry_marine", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    IndustryQuery(query="pontoon boat deck composite materials", category="industry_marine", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    IndustryQuery(query="automotive body panel SMC carbon fiber", category="industry_automotive", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    IndustryQuery(query="electric vehicle structural composite battery", category="industry_automotive", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    IndustryQuery(query="truck trailer composite body lightweight", category="industry_automotive", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    IndustryQuery(query="FRP rebar concrete reinforcement construction", category="industry_construction", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    IndustryQuery(query="composite cladding facade building panel", category="industry_construction", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    IndustryQuery(query="fiberglass window door profile pultrusion", category="industry_construction", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    IndustryQuery(query="composite bridge deck FRP pedestrian", category="industry_infrastructure", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    IndustryQuery(query="utility pole composite fiberglass transmission", category="industry_infrastructure", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    IndustryQuery(query="pipeline composite repair rehabilitation", category="industry_infrastructure", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    IndustryQuery(query="train interior composite panel fire safety", category="industry_rail", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    IndustryQuery(query="pool spa hot tub fiberglass composite", category="industry_consumer", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    IndustryQuery(query="electrical enclosure composite SMC BMC", category="industry_electrical", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    IndustryQuery(query="water wastewater treatment composite FRP", category="industry_water", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    IndustryQuery(query="chemical processing tank composite corrosion", category="industry_chemical", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    IndustryQuery(query="telecommunications antenna radome composite", category="industry_telecom", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    IndustryQuery(query="rocket payload fairing composite structure", category="industry_space", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    
    # --- Materials (15) ---
    IndustryQuery(query="vinyl ester resin marine corrosion resistant", category="materials", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    IndustryQuery(query="phenolic resin fire retardant composite", category="materials", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    IndustryQuery(query="PVC foam core Divinycell structural", category="materials", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    IndustryQuery(query="balsa wood core composite marine wind", category="materials", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    IndustryQuery(query="E-glass fiberglass reinforcement general purpose", category="materials", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    IndustryQuery(query="gel coat finish marine mold release", category="materials", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    IndustryQuery(query="structural adhesive bonding composite assembly", category="materials", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    IndustryQuery(query="chopped strand mat CSM fiberglass hand layup", category="materials", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    IndustryQuery(query="woven roving fabric fiberglass reinforcement", category="materials", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    IndustryQuery(query="multiaxial fabric stitched reinforcement", category="materials", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    IndustryQuery(query="initiator catalyst MEKP composites curing", category="materials", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    IndustryQuery(query="mold release agent composites wax silicone", category="materials", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    IndustryQuery(query="natural fiber composite flax hemp sustainable", category="materials", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    IndustryQuery(query="honeycomb core aluminum Nomex aerospace", category="materials", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    IndustryQuery(query="S-glass high strength ballistic armor", category="materials", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    
    # --- Processes (6) ---
    IndustryQuery(query="vacuum infusion VARTM process marine wind", category="processes", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    IndustryQuery(query="resin transfer molding RTM aerospace automotive", category="processes", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    IndustryQuery(query="compression molding SMC BMC automotive", category="processes", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    IndustryQuery(query="pultrusion FRP profile window infrastructure", category="processes", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    IndustryQuery(query="filament winding pressure vessel tank pipe", category="processes", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    IndustryQuery(query="closed mold composites light RTM infusion", category="technology", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    
    # --- Suppliers & Competitors (10) ---
    IndustryQuery(query="Ashland specialty ingredients composites", category="suppliers", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    IndustryQuery(query="Strongwell pultrusion FRP structural", category="suppliers", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    IndustryQuery(query="Scott Bader adhesives gelcoat resins", category="suppliers", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    IndustryQuery(query="AGY glass fiber reinforcement S-glass", category="suppliers", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    IndustryQuery(query="Jushi glass fiber production capacity", category="suppliers", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    IndustryQuery(query="Nan Ya epoxy resin composites", category="suppliers", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    IndustryQuery(query="A&P Technology braided reinforcements", category="suppliers", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    IndustryQuery(query="Magnum Venus Products MVP composites equipment", category="suppliers", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    IndustryQuery(query="Creative Composites Group infrastructure", category="suppliers", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    IndustryQuery(query="Entropy bio-based epoxy sustainable composites", category="suppliers", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    
    # --- OEMs & Customers (6) ---
    IndustryQuery(query="Brunswick marine boat fiberglass composite", category="oem", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    IndustryQuery(query="Malibu Boats composite hull manufacturing", category="oem", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    IndustryQuery(query="marine boat builder composites contract", category="contracts", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    IndustryQuery(query="infrastructure FRP composite bridge contract", category="contracts", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    IndustryQuery(query="Ford GM composite pickup truck bed", category="oem", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    IndustryQuery(query="Textron aviation composite aircraft", category="oem", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    
    # --- Regional Markets (4) ---
    IndustryQuery(query="China composites manufacturing carbon fiber", category="regional", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    IndustryQuery(query="Mexico nearshoring composites manufacturing", category="regional", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    IndustryQuery(query="Europe composites industry Germany France UK", category="regional", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    IndustryQuery(query="India composites manufacturing growth", category="regional", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    
    # --- Events & News (3) ---
    IndustryQuery(query="CAMX composites trade show conference", category="events", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    IndustryQuery(query="JEC World composites show Paris", category="events", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    IndustryQuery(query="CompositesWorld news article", category="events", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    
    # --- Sustainability (4) ---
    IndustryQuery(query="sustainable composites bio-based resin", category="sustainability", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    IndustryQuery(query="composite recycling pyrolysis solvolysis", category="sustainability", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    IndustryQuery(query="low carbon composites manufacturing emissions", category="sustainability", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    IndustryQuery(query="circular economy composites end of life", category="sustainability", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    
    # --- Market Intelligence (2) ---
    IndustryQuery(query="composites market size forecast CAGR growth", category="market", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
    IndustryQuery(query="glass fiber market capacity demand supply", category="market", engine=SearchEngine.TAVILY, tier=QueryTier.MONITORING, search_depth="basic", max_results=5),
]


def get_query_stats_v2():
    """Print query statistics - version 2"""
    exa_queries = get_all_exa_queries_v2()
    tavily_queries = get_all_tavily_queries_v2()
    all_queries = exa_queries + tavily_queries
    
    print("\n" + "=" * 60)
    print("EXPANDED QUERY ARCHITECTURE STATISTICS (v2)")
    print("=" * 60)
    print(f"\nTotal Queries: {len(all_queries)}")
    print(f"  - Exa.ai:  {len(exa_queries)}")
    print(f"  - Tavily:  {len(tavily_queries)}")
    
    print(f"\nBy Tier:")
    for tier in QueryTier:
        count = len([q for q in all_queries if q.tier == tier])
        print(f"  - {tier.name}: {count}")
    
    print(f"\nExa Categories ({len(exa_queries)} queries):")
    exa_cats = {}
    for q in exa_queries:
        exa_cats[q.category] = exa_cats.get(q.category, 0) + 1
    for cat, count in sorted(exa_cats.items(), key=lambda x: -x[1]):
        print(f"  - {cat}: {count}")
    
    print(f"\nTavily Categories ({len(tavily_queries)} queries):")
    tavily_cats = {}
    for q in tavily_queries:
        tavily_cats[q.category] = tavily_cats.get(q.category, 0) + 1
    for cat, count in sorted(tavily_cats.items(), key=lambda x: -x[1])[:15]:
        print(f"  - {cat}: {count}")
    print(f"  ... and {len(tavily_cats) - 15} more categories")
    
    # Estimate monthly cost
    monthly_queries_exa = len(exa_queries) * 2 * 30  # 2x daily
    monthly_queries_tavily = len(tavily_queries) * 2 * 30
    exa_cost = monthly_queries_exa * 0.004
    tavily_cost = monthly_queries_tavily * 0.0015
    
    print(f"\nEstimated Monthly Cost (2x daily cadence):")
    print(f"  - Exa ({monthly_queries_exa:,} queries @ $0.004): ${exa_cost:.2f}")
    print(f"  - Tavily ({monthly_queries_tavily:,} queries @ $0.0015): ${tavily_cost:.2f}")
    print(f"  - Total: ${exa_cost + tavily_cost:.2f}")
    print(f"\n  Annual estimate: ${(exa_cost + tavily_cost) * 12:.2f}")


get_query_stats_v2()
