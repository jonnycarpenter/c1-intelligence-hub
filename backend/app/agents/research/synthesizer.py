from typing import Dict, Any, List
from langchain_core.messages import SystemMessage, HumanMessage
from app.agents.research.state import DeepResearchState, SynthesisAgentOutput, FindingSection, FieldSalesSection, SupportingVisual
from app.config.settings import settings
from app.utils.resilient_llm import create_resilient_llm_with_openai_fallback
import json
import time
from datetime import datetime

SYNTHESIZER_SYSTEM_PROMPT = """
You are a Lead Synthesis Agent for C1 Intelligence Hub. Your job is to take the separate findings from the Financial, Industry, and Visual agents and merge them into a CONCISE, executive-ready research report.

## CRITICAL: BREVITY IS KEY

**Executives are busy. Keep it short.**
- Total report should be readable in 3-5 minutes
- Prioritize the TOP 3-5 most important findings
- Cut anything that doesn't directly answer the user's question
- Use bullet points over paragraphs where possible
- NO filler phrases like "It's worth noting that..." or "Interestingly..."

## Your Goal

Create a FOCUSED report that answers the user's question directly. Quality over quantity.

## Synthesis Rules

1. PRIORITIZE RUTHLESSLY: Only include findings that directly answer the user's question. Skip tangential information.
2. MERGE & DEDUPLICATE: Combine overlapping findings into single, concise statements.
3. CONNECT THE DOTS: One sentence explaining how financial data connects to market trends is enough.
4. CITE EFFICIENTLY: Include citations but don't repeat the same source multiple times.
5. INCORPORATE VISUALS: Use visual assets (charts, graphs) from visual_assets to support key findings. Place visuals in appropriate sections based on their placement hints.

## Report Structure (KEEP IT TIGHT)

### 1. EXECUTIVE SUMMARY
- **headline**: One punchy sentence (15 words max).
- **key_points**: 3-4 bullet points MAX. Each point should be one sentence.
- **key_metrics**: 2-3 numbers only — the ones that matter most.
- **data_caveat**: One sentence if needed, otherwise null.

### 2. THEMATIC SECTIONS
Create 2-3 sections MAX (not 4-6).
- **section_title**: Short, descriptive (5 words max).
- **content**: 1-2 SHORT paragraphs (3-4 sentences each). Get to the point.
- **tables**: Only if there's genuine tabular data. Don't force tables.
- **supporting_visuals**: Include relevant visuals from visual_assets that support this section. Each visual should have placement="section_name".
- **confidence**: High, Medium, or Low.

### 3. FIELD SALES IMPLICATIONS (BRIEF)
- **offensive_angles**: 2 MAX. One sentence each for angle + rationale.
- **defensive_angles**: 1 MAX. One sentence.
- **questions_to_explore**: 2-3 questions MAX.
- **caution_note**: One standard sentence.

### 4. SOURCES
- **sources_used**: List only the unique, key sources (not every single article).
- **data_gaps**: 1-2 sentence summary of what's missing.

### 5. ALL VISUALS
- **all_visuals**: Aggregate all visual assets from visual_assets.supporting_visuals into this array for the report.

## Anti-Patterns to AVOID
- ❌ Long introductory paragraphs before getting to findings
- ❌ Repeating the same information in different sections
- ❌ Excessive caveats and qualifications
- ❌ Tables with only 2 rows of data
- ❌ More than 3 thematic sections
- ❌ Verbose field sales angles with multiple paragraphs
- ❌ Ignoring visual assets when they're available

## Output Format
Always respond with valid JSON matching the SynthesisAgentOutput schema.
"""

async def synthesis_node(state: DeepResearchState) -> DeepResearchState:
    """
    Synthesis node. Merges financial, industry, and visual outputs into a final report.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    start_time = time.time()
    logger.info(f"[SYNTHESIZER] START - query: {state.get('user_query', '')[:50]}...")
    logger.info(f"[SYNTHESIZER] State keys: {list(state.keys())}")
    logger.info(f"[SYNTHESIZER] Has financial_output: {state.get('financial_output') is not None}")
    logger.info(f"[SYNTHESIZER] Has industry_output: {state.get('industry_output') is not None}")
    logger.info(f"[SYNTHESIZER] Has visual_output: {state.get('visual_output') is not None}")
    
    llm = create_resilient_llm_with_openai_fallback(
        primary_model=settings.deep_research_synthesizer_model,
        anthropic_api_key=settings.anthropic_api_key,
        openai_api_key=settings.openai_api_key,
        temperature=0,
    )
    
    financial = state["financial_output"]
    industry = state["industry_output"]
    visual = state.get("visual_output")
    
    if not financial and not industry:
        state["current_status"] = "synthesis_failed_no_input"
        return state
        
    # Prepare input for synthesizer
    input_data = {
        "original_query": state["user_query"],
        "research_brief": state["research_brief"].model_dump() if state["research_brief"] else None,
        "financial_findings": financial.model_dump() if financial else None,
        "industry_findings": industry.model_dump() if industry else None,
        "visual_assets": visual.model_dump() if visual else None,  # NEW: Include visual output
    }
    
    synthesis_prompt = f"""
    Synthesize the following research findings into a comprehensive report for the user's query: '{state["user_query"]}'.
    
    RESEARCH DATA:
    {json.dumps(input_data, indent=2)}
    
    Respond ONLY with a JSON object matching this EXACT schema:

    {{
      "report_id": "REP-{int(time.time())}",
      "generated_at": "{datetime.now().isoformat()}",
      "query": "{state["user_query"]}",
      "data_completeness": "complete" | "partial" | "limited",
      "overall_confidence": "high" | "medium" | "low",
      "executive_summary": {{
        "headline": "Single sentence capturing key takeaway",
        "key_points": ["Point 1", "Point 2", "Point 3"],
        "key_metrics": [
          {{
            "metric_name": "Name of metric",
            "value": "$X.XB or X.X%",
            "context": "Brief context for this metric",
            "source": "Source of this metric (required!)",
            "confidence": "high" | "medium" | "low"
          }}
        ],
        "data_caveat": "Data caveat if incomplete, or null"
      }},
      "sections": [
        {{
          "section_id": "sec_001",
          "section_title": "Section Title",
          "content": "2-4 paragraphs of synthesized prose",
          "tables": [
            {{
              "table_id": "tbl_001",
              "title": "Table Title",
              "columns": ["Column1", "Column2", "Column3"],
              "rows": [{{"Column1": "val1", "Column2": "val2", "Column3": "val3"}}],
              "source": "Source of table data",
              "notes": "Optional notes or null"
            }}
          ],
          "citations": [
            {{
              "source_type": "sec_10k|earnings_call|trade_publication|etc",
              "source_title": "Title",
              "source_url": "URL or null",
              "source_date": "YYYY-MM-DD or null",
              "page_or_section": "Section ref or null",
              "direct_quote": "Quote or null"
            }}
          ],
          "confidence": "high" | "medium" | "low",
          "supporting_visuals": []
        }}
      ],
      "field_sales": {{
        "offensive_angles": [
          {{
            "angle": "Opportunity angle",
            "rationale": "Why this is an opportunity",
            "grounding": "Data/evidence supporting this",
            "suggested_validation": "How to validate with customer"
          }}
        ],
        "defensive_angles": [
          {{
            "angle": "Defensive angle",
            "rationale": "Why this matters",
            "grounding": "Data/evidence",
            "suggested_validation": "How to address"
          }}
        ],
        "questions_to_explore": ["Question 1", "Question 2"],
        "caution_note": "Standard disclaimer about validating against account knowledge"
      }},
      "all_visuals": [],
      "sources_used": [
        {{
          "source_type": "sec_10k|earnings_call|trade_publication|etc",
          "source_title": "Title",
          "source_url": "URL or null",
          "source_date": "YYYY-MM-DD or null",
          "page_or_section": "Section ref or null",
          "direct_quote": null
        }}
      ],
      "source_breakdown": {{"sec_filings": 3, "earnings_call": 2, "trade_publication": 5}},
      "data_gaps": ["Gap 1", "Gap 2"],
      "warnings": ["Warning 1"],
      "research_time_seconds": 0.0
    }}

    CRITICAL REQUIREMENTS:
    - "query" field MUST be included and match the user's query
    - "data_completeness" MUST be lowercase: "complete", "partial", or "limited"
    - "overall_confidence" MUST be lowercase: "high", "medium", or "low"
    - ALL KeyMetric objects MUST have "source" and "confidence" fields
    - ALL FieldSalesAngle objects MUST have "angle", "rationale", and "grounding" fields
    - ALL lists (sections, all_visuals, sources_used, data_gaps, warnings) MUST be arrays, even if empty []
    - "research_time_seconds" MUST be a number (will be updated programmatically)
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
        
        elapsed = time.time() - start_time
        logger.info(f"[SYNTHESIZER] COMPLETE in {elapsed:.1f}s - sections: {len(final_report.sections)}, data_completeness: {final_report.data_completeness}")
        
        state["final_report"] = final_report
        state["current_status"] = "synthesis_complete"
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Synthesizer failed to parse LLM output: {e}")
        logger.error(f"Raw response content: {response.content[:500] if response else 'No response'}...")
        state["errors"].append({"node": "synthesis", "error": str(e)})
        state["current_status"] = "synthesis_failed"
        
    return state
