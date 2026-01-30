from typing import TypedDict, Annotated, List, Optional, Dict, Any, Union
from enum import Enum
from pydantic import BaseModel, Field
import operator
from langchain_core.messages import BaseMessage

# --- Enums and Pydantic Models for Schema Validation ---

class QueryStatus(str, Enum):
    READY = "ready"
    NEEDS_CLARIFICATION = "needs_clarification"

class ClarifyingQuestion(BaseModel):
    question: str
    options: Optional[List[str]] = None
    default_if_skipped: str

class ResearchBrief(BaseModel):
    status: QueryStatus
    clarifying_question: Optional[ClarifyingQuestion] = None
    original_query: Optional[str] = None
    clarified_intent: Optional[str] = None
    timeframe: Optional[str] = None
    financial_agent_queries: Optional[List[str]] = None
    industry_agent_queries: Optional[List[str]] = None
    entities_to_track: Optional[List[str]] = None
    domain_context: Optional[str] = None
    priority_sources: Optional[Dict[str, List[str]]] = None
    exclusions: Optional[List[str]] = None

class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class SourceType(str, Enum):
    SEC_10K = "sec_10k"
    SEC_10Q = "sec_10q"
    SEC_8K = "sec_8k"
    EARNINGS_CALL = "earnings_call"
    INVESTOR_PRESENTATION = "investor_presentation"
    FINANCIAL_NEWS = "financial_news"
    PRESS_RELEASE = "press_release"
    TRADE_PUBLICATION = "trade_publication"
    INDUSTRY_NEWS = "industry_news"

class Citation(BaseModel):
    source_type: Union[SourceType, str]
    source_title: str
    source_url: Optional[str] = None
    source_date: Optional[str] = None
    page_or_section: Optional[str] = None
    direct_quote: Optional[str] = None

class FinancialFinding(BaseModel):
    finding_id: str
    finding: str
    finding_type: str
    confidence: ConfidenceLevel
    relevance_score: float
    citation: Citation
    entities_mentioned: List[str]
    metrics: Optional[Dict[str, Any]] = None

class FinancialAgentOutput(BaseModel):
    status: str
    queries_executed: List[str]
    sources_searched: int
    sources_with_results: int
    execution_time_seconds: float
    findings: List[FinancialFinding]
    key_metrics_summary: Optional[Dict[str, Any]] = None
    failed_sources: List[Dict[str, Any]]
    data_gaps: List[str]
    warnings: List[str]

class Sentiment(str, Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"

class IndustryFinding(BaseModel):
    finding_id: str
    finding: str
    event_type: str
    sentiment: Sentiment
    confidence: str
    relevance_score: float
    citation: Citation
    entities_mentioned: List[str]
    is_historical: bool
    importance: str

class IndustryAgentOutput(BaseModel):
    status: str
    queries_executed: List[str]
    findings: List[IndustryFinding]
    demand_signals: Optional[Dict[str, Any]] = None
    competitive_landscape_shifts: List[str]
    data_gaps: List[str]
    warnings: List[str]

class DataCompletenessLevel(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    LIMITED = "limited"

class CompanyWithLogo(BaseModel):
    """Company enriched with logo URL for display."""
    name: str
    domain: Optional[str] = None
    logo_url: Optional[str] = None

class SupportingVisual(BaseModel):
    visual_id: str
    image_url: str
    caption: str
    placement: str
    size: str
    data_summary: Optional[str] = None

class VisualAgentOutput(BaseModel):
    """Output from Visual Research Agent - charts, graphs, and visual assets."""
    status: str = "success"
    visuals_found: int = 0  # Total visuals found before filtering
    searches_executed: List[str] = Field(default_factory=list)  # List of search types run
    supporting_visuals: List[SupportingVisual] = Field(default_factory=list)  # Selected visuals for report
    data_gaps: List[str] = Field(default_factory=list)  # Topics with no visual coverage
    warnings: List[str] = Field(default_factory=list)  # Any issues during search

class MetricsTable(BaseModel):
    """Structured tabular data for metrics, projections, comparisons"""
    table_id: str
    title: str  # e.g., "Market Projections"
    columns: List[str]  # e.g., ["Metric", "2025", "2030", "CAGR"]
    rows: List[Dict[str, Any]]  # Each row as {column_name: value}
    source: str  # e.g., "MarketsandMarkets, Dec 2025"
    notes: Optional[str] = None  # Any caveats or footnotes

class KeyMetric(BaseModel):
    metric_name: str = ""  # Backend schema field
    label: Optional[str] = None  # Frontend expects this
    value: str
    context: str = ""
    source: str = "Research data"
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
    
    def __init__(self, **data):
        # Allow either metric_name or label, sync them
        if 'label' in data and 'metric_name' not in data:
            data['metric_name'] = data['label']
        elif 'metric_name' in data and 'label' not in data:
            data['label'] = data['metric_name']
        super().__init__(**data)

class ExecutiveSummary(BaseModel):
    headline: str
    key_points: List[str]
    key_metrics: List[KeyMetric]
    key_point_citations: List[Citation] = Field(default_factory=list, description="Citation for each key point, order matches key_points")
    data_caveat: Optional[str] = None

class BlockType(str, Enum):
    PARAGRAPH = "paragraph"
    METRIC_GRID = "metric_grid"
    VISUAL_HERO = "visual_hero"
    VISUAL_SPLIT = "visual_split"
    QUOTE_CALLOUT = "quote"
    TABLE = "table"
    
class ReportBlock(BaseModel):
    block_type: BlockType
    block_id: str
    # Flexible data payload - schema depends on block_type
    # paragraph: {text: str}
    # metric_grid: {metrics: List[KeyMetric]}
    # visual_split: {visual_id: str, text: str, layout: str, caption: str}
    # quote: {text: str, speaker: str, context: str, sentiment: str}
    data: Dict[str, Any]
    citations: List[Citation] = Field(default_factory=list)

class FindingSection(BaseModel):
    section_id: str
    section_title: str
    # Legacy: content string for older reports
    content: Optional[str] = None
    # New: component-based blocks
    blocks: List[ReportBlock] = Field(default_factory=list)
    
    tables: List[MetricsTable] = Field(default_factory=list) # Legacy tables
    citations: List[Citation]
    confidence: ConfidenceLevel
    supporting_visuals: List[SupportingVisual]

class FieldSalesAngle(BaseModel):
    """Field sales angle - supports both offensive and defensive formats."""
    angle: str = ""  # Backend schema (offensive)
    rationale: str = ""  # Backend schema
    grounding: str = ""  # Backend schema (optional)
    suggested_validation: Optional[str] = None
    # Frontend-compatible fields
    target_segment: Optional[str] = None  # Frontend expects for offensive
    risk: Optional[str] = None  # Frontend expects for defensive
    mitigation: Optional[str] = None  # Frontend expects for defensive
    
    def __init__(self, **data):
        # Map frontend fields to backend fields
        if 'target_segment' in data and not data.get('rationale'):
            data['rationale'] = data['target_segment']
        if 'risk' in data and not data.get('angle'):
            data['angle'] = data['risk']
        if 'mitigation' in data and not data.get('rationale'):
            data['rationale'] = data['mitigation']
        super().__init__(**data)

class FieldSalesSection(BaseModel):
    offensive_angles: List[FieldSalesAngle]
    defensive_angles: List[FieldSalesAngle]
    questions_to_explore: List[str]
    caution_note: str


# --- Category Agent Schemas (Phase 2) ---

class TerritoryInsight(BaseModel):
    """Territory-specific insights for sales teams."""
    territory: str  # "east" | "west"
    relevance_score: float = Field(ge=0, le=1, description="How relevant to this territory (0-1)")
    key_takeaways: List[str]
    action_items: List[str]
    priority_industries: List[str] = Field(default_factory=list, description="Top industries for this territory")


class ProductRecommendation(BaseModel):
    """Product recommendation for sales context."""
    product_name: str
    supplier: str
    material_category: str
    why_relevant: str
    datasheet_url: Optional[str] = None
    competitive_positioning: Optional[str] = None


class SalesPlay(BaseModel):
    """Structured sales play for field reps."""
    play_name: str
    target_industry: str
    target_territory: Optional[str] = None  # "east", "west", or None for both
    opening_hook: str  # Conversation starter based on research
    key_data_points: List[str]  # Facts to cite from research
    objection_handlers: List[str]  # Anticipated objections and responses
    next_steps: List[str]  # Recommended follow-up actions


class CategoryAgentOutput(BaseModel):
    """Output from Category Agent - sales intelligence layer."""
    status: str = "success"
    territory_insights: Dict[str, TerritoryInsight] = Field(
        default_factory=dict,
        description="Territory-specific insights keyed by 'east' or 'west'"
    )
    product_recommendations: List[ProductRecommendation] = Field(default_factory=list)
    sales_plays: List[SalesPlay] = Field(default_factory=list)
    industry_talking_points: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Industry-specific talking points keyed by industry name"
    )
    data_gaps: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


# --- Validator Agent Schemas (Phase 2) ---

class CitationIssue(BaseModel):
    """Issue found during citation validation."""
    finding_id: str
    issue_type: str  # "missing_url", "date_mismatch", "source_not_found", "broken_link"
    description: str
    suggested_fix: Optional[str] = None
    severity: str = "warning"  # "warning" | "error"


class ValidatorOutput(BaseModel):
    """Output from Validator Agent - citation verification."""
    validation_passed: bool
    total_citations_checked: int = 0
    valid_citations: int = 0
    citation_issues: List[CitationIssue] = Field(default_factory=list)
    unsubstantiated_claims: List[str] = Field(default_factory=list)
    confidence_adjustments: Dict[str, str] = Field(
        default_factory=dict,
        description="finding_id -> adjusted confidence level"
    )
    warnings: List[str] = Field(default_factory=list)

class SynthesisAgentOutput(BaseModel):
    report_id: str
    generated_at: str
    query: str
    data_completeness: DataCompletenessLevel
    overall_confidence: ConfidenceLevel
    executive_summary: ExecutiveSummary
    sections: List[FindingSection]
    # Extended thinking output from Claude - shows model's reasoning process
    thinking_content: Optional[str] = Field(default=None, description="Claude's extended thinking/reasoning process before generating the report")
    all_visuals: List[SupportingVisual]
    companies_with_logos: List[CompanyWithLogo] = Field(default_factory=list)
    sources_used: List[Citation]
    source_breakdown: Dict[str, int]
    data_gaps: List[str]
    warnings: List[str]
    research_time_seconds: float
    # Legacy field - kept for backward compatibility with cached reports
    field_sales: Optional[FieldSalesSection] = None

# --- LangGraph State Definition ---

# --- Reducer Functions for Parallel State Merge ---

def _keep_first(a, b):
    """Keep the first (original) value - for immutable fields set early in the workflow.
    
    Handles both None and empty string cases - prefers non-empty values.
    """
    # If a has a truthy value (not None, not empty string, not 0 for strings), keep it
    if a is not None and a != "":
        return a
    return b


def _keep_last(a, b):
    """Keep the last (most recent) value - for fields updated sequentially.
    
    Handles both None and empty values - prefers the newer non-empty value.
    """
    if b is not None and b != "":
        return b
    return a


def _merge_errors(left: List[Dict[str, Any]], right: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Merge errors from parallel branches, avoiding duplicates."""
    # Use set-like deduplication based on error content
    seen = set()
    merged = []
    for err in left + right:
        key = (err.get("node", ""), str(err.get("error", "")))
        if key not in seen:
            seen.add(key)
            merged.append(err)
    return merged


class DeepResearchState(TypedDict):
    """
    The state object for the Deep Research Workflow.
    
    IMPORTANT: All fields need reducer annotations for LangGraph's Send API parallel execution.
    When Financial + Industry agents run in parallel, both receive copies of state. On merge,
    LangGraph needs reducers to know how to combine values.
    
    Reducer strategy:
    - _keep_first: Immutable fields set early (user_query, research_brief, clarification_count)
    - _keep_last: Fields written by specific nodes (financial_output, industry_output, etc.)
    - operator.add: Lists that should concatenate (conversation_history)
    - _merge_errors: Custom deduplication for errors
    """
    
    # Input/Initial query - IMMUTABLE after initial set
    user_query: Annotated[str, _keep_first]
    conversation_history: Annotated[List[BaseMessage], operator.add]
    
    # Grooming results - IMMUTABLE after groomer sets them
    research_brief: Annotated[Optional[ResearchBrief], _keep_first]
    clarification_count: Annotated[int, _keep_first]
    last_clarification: Annotated[Optional[ClarifyingQuestion], _keep_last]  # Track last asked question for context
    
    # Research outputs - Each written by ONE specific branch, keep latest
    financial_output: Annotated[Optional[FinancialAgentOutput], _keep_last]
    industry_output: Annotated[Optional[IndustryAgentOutput], _keep_last]
    visual_output: Annotated[Optional[VisualAgentOutput], _keep_last]
    
    # Synthesis results - Written sequentially post-merge
    final_report: Annotated[Optional[SynthesisAgentOutput], _keep_last]
    
    # Category Agent outputs (Phase 2) - Written sequentially
    category_output: Annotated[Optional[CategoryAgentOutput], _keep_last]
    
    # Validator outputs (Phase 2) - Written sequentially
    validator_output: Annotated[Optional[ValidatorOutput], _keep_last]
    
    # Metadata and progress tracking
    current_status: Annotated[str, _keep_last]  # Last writer wins for status
    errors: Annotated[List[Dict[str, Any]], _merge_errors]  # Merged from parallel branches
