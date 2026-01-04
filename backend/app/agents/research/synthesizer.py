from typing import Dict, Any, List
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, HumanMessage
from app.agents.research.state import DeepResearchState, SynthesisAgentOutput, FindingSection, FieldSalesSection, SupportingVisual
from app.config.settings import settings
import json
import time
from datetime import datetime

SYNTHESIZER_SYSTEM_PROMPT = """
You are a Lead Synthesis Agent for C1 Intelligence Hub. Your job is to take the separate findings from the Financial and Industry agents and merge them into a cohesive, executive-ready research report.

## Your Goal

Create a report that doesn't just list facts, but connects the dots between financial reality and market activity. Your output should be "Executive Ready" and "Sales Actionable."

## Synthesis Rules

1. MERGE & DEDUPLICATE: If both agents found the same news (e.g., a huge Hexcel contract), merge them into one cohesive narrative with all metrics and qualitative context.
2. CONNECT THE DOTS: If the Financial Agent found declining margins and the Industry Agent found rising raw material prices, explicitly state the connection.
3. MAINTAIN CITATIONS: Never lose a citation. Every claim in the final report must be attributed.
4. SALES ACTIONABLE: The "Field Sales Implications" section is critical. It should translate data into offensive and defensive angles for sales teams.

## Data Presentation Guidelines

### When to Use Tables vs Prose

**USE TABLES for:**
- Multi-year projections or forecasts (like market sizing)
- Side-by-side company comparisons (revenue, margins, growth)
- Lists of metrics with consistent structure (same columns apply to all rows)
- Anything with 3+ data points that share the same dimensions

**USE PROSE for:**
- Narrative explanations and context
- Single metrics that need interpretation
- Qualitative findings without numeric comparisons
- Connecting insights across different data points

### Table Formatting Rules
When creating structured `MetricsTable` objects:
1. Clear title: What is this table showing?
2. Consistent units: Don't mix $M and $B in same column — pick one.
3. Trajectory: Include CAGR or % change for projections.
4. Correct Schemas: Ensure rows are dictionaries where keys match column names.

### Number Formatting Standards
- Revenue/Market Size: $X.XXB or $XXXM (e.g., $4.82B, $312M)
- Growth rates: X.X% (e.g., 7.2%)
- Volume: XX.XX + units (e.g., 207.64 kilotons)

## Report Structure

Your output must follow this structure:

### 1. EXECUTIVE SUMMARY
- **headline**: One sentence capturing the key takeaway.
- **key_points**: 3-5 bullet points summarizing findings (not a brain dump — the most important insights only).
- **key_metrics**: 2-4 highlight numbers (`KeyMetric` schema).
- **data_caveat**: If data is incomplete, say so upfront.

### 2. THEMATIC SECTIONS
Create 2-4 thematic sections based on the findings.
- **section_title**: Descriptive title.
- **content**: 2-4 paragraphs of synthesized prose (not bullets).
- **tables**: Embed `MetricsTable` objects where data is dense.
- **supporting_visuals**: Reference charts from the Industry Agent inline and include them in the `supporting_visuals` list with appropriate `placement` ("right" or "full_width") and `size` ("small", "medium", "large").
- **confidence**: High, Medium, or Low for each section.

### 3. FIELD SALES IMPLICATIONS
- **offensive_angles**: 2-3 opportunities to pursue based on findings.
- **defensive_angles**: 1-2 threats to address or objections to prepare for.
- **questions_to_explore**: Things worth investigating with customers/internally.
- **caution_note**: Standard disclaimer about validating against account knowledge.

### 4. SUPPORTING MATERIALS & TRANSPARENCY
- **sources_used**: Full list of all unique citations.
- **source_breakdown**: Count by source type (e.g., {"sec_filings": 3, "earnings_call": 2}).
- **data_gaps**: List specific gaps identified (e.g., "Company X financials unavailable").
- **warnings**: Any data quality or consistency warnings.
- **data_completeness**: "complete", "partial", or "limited".
- **overall_confidence**: "high", "medium", or "low".

## Output Format
Always respond with valid JSON matching the SynthesisAgentOutput schema.
"""

async def synthesis_node(state: DeepResearchState) -> DeepResearchState:
    """
    Synthesis node. Merges financial and industry outputs into a final report.
    """
    start_time = time.time()
    llm = ChatAnthropic(
        model="claude-opus-4-5",
        anthropic_api_key=settings.anthropic_api_key,
        temperature=0,
    )
    
    financial = state["financial_output"]
    industry = state["industry_output"]
    
    if not financial and not industry:
        state["current_status"] = "synthesis_failed_no_input"
        return state
        
    # Prepare input for synthesizer
    input_data = {
        "original_query": state["user_query"],
        "research_brief": state["research_brief"].model_dump() if state["research_brief"] else None,
        "financial_findings": financial.model_dump() if financial else None,
        "industry_findings": industry.model_dump() if industry else None,
    }
    
    synthesis_prompt = f"""
    Synthesize the following research findings into a comprehensive report for the user's query: '{state["user_query"]}'.
    
    RESEARCH DATA:
    {json.dumps(input_data, indent=2)}
    
    Respond ONLY with a JSON object matching the SynthesisAgentOutput schema.
    """
    
    messages = [
        SystemMessage(content=SYNTHESIZER_SYSTEM_PROMPT),
        HumanMessage(content=synthesis_prompt)
    ]
    
    response = await llm.ainvoke(messages)
    
    try:
        content = response.content
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
            
        output_data = json.loads(content)
        # Ensure some fields are present
        if "generated_at" not in output_data:
            output_data["generated_at"] = datetime.now().isoformat()
        if "report_id" not in output_data:
            output_data["report_id"] = f"REP-{int(time.time())}"
            
        final_report = SynthesisAgentOutput(**output_data)
        final_report.research_time_seconds = time.time() - start_time
        
        state["final_report"] = final_report
        state["current_status"] = "synthesis_complete"
        
    except Exception as e:
        state["errors"].append({"node": "synthesis", "error": str(e)})
        state["current_status"] = "synthesis_failed"
        
    return state
