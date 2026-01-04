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

class SupportingVisual(BaseModel):
    visual_id: str
    image_url: str
    caption: str
    placement: str
    size: str
    data_summary: Optional[str] = None

class MetricsTable(BaseModel):
    """Structured tabular data for metrics, projections, comparisons"""
    table_id: str
    title: str  # e.g., "Market Projections"
    columns: List[str]  # e.g., ["Metric", "2025", "2030", "CAGR"]
    rows: List[Dict[str, Any]]  # Each row as {column_name: value}
    source: str  # e.g., "MarketsandMarkets, Dec 2025"
    notes: Optional[str] = None  # Any caveats or footnotes

class KeyMetric(BaseModel):
    metric_name: str
    value: str
    context: str
    source: str
    confidence: ConfidenceLevel

class ExecutiveSummary(BaseModel):
    headline: str
    key_points: List[str]
    key_metrics: List[KeyMetric]
    data_caveat: Optional[str] = None

class FindingSection(BaseModel):
    section_id: str
    section_title: str
    content: str
    tables: List[MetricsTable] = Field(default_factory=list) # NEW: Tables to embed in this section
    citations: List[Citation]
    confidence: ConfidenceLevel
    supporting_visuals: List[SupportingVisual]

class FieldSalesAngle(BaseModel):
    angle: str
    rationale: str
    grounding: str
    suggested_validation: Optional[str] = None

class FieldSalesSection(BaseModel):
    offensive_angles: List[FieldSalesAngle]
    defensive_angles: List[FieldSalesAngle]
    questions_to_explore: List[str]
    caution_note: str

class SynthesisAgentOutput(BaseModel):
    report_id: str
    generated_at: str
    query: str
    data_completeness: DataCompletenessLevel
    overall_confidence: ConfidenceLevel
    executive_summary: ExecutiveSummary
    sections: List[FindingSection]
    field_sales: FieldSalesSection
    all_visuals: List[SupportingVisual]
    sources_used: List[Citation]
    source_breakdown: Dict[str, int]
    data_gaps: List[str]
    warnings: List[str]
    research_time_seconds: float

# --- LangGraph State Definition ---

class DeepResearchState(TypedDict):
    """The state object for the Deep Research Workflow."""
    
    # Input/Initial query
    user_query: str
    conversation_history: Annotated[List[BaseMessage], operator.add]
    
    # Grooming results
    research_brief: Optional[ResearchBrief]
    clarification_count: int
    
    # Research outputs
    financial_output: Optional[FinancialAgentOutput]
    industry_output: Optional[IndustryAgentOutput]
    
    # Synthesis results
    final_report: Optional[SynthesisAgentOutput]
    
    # Metadata and progress tracking
    current_status: str # e.g., "grooming", "researching", "synthesizing"
    errors: List[Dict[str, Any]]
