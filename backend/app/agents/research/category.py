"""Category Agent - Territory-specific sales intelligence layer.

This agent takes the synthesized research report and adds a sales intelligence 
layer with territory-specific insights, product recommendations, and sales plays.

Business Context (from Dave, CCO):
- Give 100-person field sales team "ammo to win" in customer conversations
- Break out insights for specific industries and use cases
- Force multiplier for strategic decisions

Territory Focus Areas:
- East: Aerospace, Wind Energy, Automotive (utility vehicles), Defense
- West: Marine (boats), RVs, Spas
Note: Both territories sell to all industries; these are strategic focuses only.
"""

import json
import time
from typing import Dict, Any, List, Optional
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.tools import BaseTool

from app.agents.research.state import (
    DeepResearchState,
    CategoryAgentOutput,
    TerritoryInsight,
    ProductRecommendation,
    SalesPlay,
)
from app.utils.resilient_llm import create_resilient_llm_with_openai_fallback
from app.config.settings import settings
from app.utils.logger import get_logger

# Import datasheet tools for product lookups
from app.mcp.tools.datasheets import (
    query_datasheets,
    get_datasheet_detail,
    get_products_by_industry,
)
from app.mcp.tools.corpus_query import query_corpus

logger = get_logger(__name__)

# Territory → Industry mappings (strategic focus areas)
TERRITORY_INDUSTRIES = {
    "east": {
        "primary": ["aerospace", "wind", "automotive", "defense"],
        "description": "East Coast territory focuses on aerospace & defense OEMs, wind energy projects, and utility vehicle manufacturers.",
    },
    "west": {
        "primary": ["marine", "recreation", "spa"],
        "description": "West Coast territory focuses on marine/boat builders, RV manufacturers, and spa/pool OEMs.",
    },
}

# Industry → Material Category mappings for product recommendations
INDUSTRY_MATERIALS = {
    "aerospace": ["carbon_fiber", "prepreg", "core_honeycomb", "adhesive"],
    "defense": ["carbon_fiber", "aramid_fiber", "prepreg", "core_honeycomb"],
    "wind": ["glass_fiber", "carbon_fiber", "resin_epoxy", "core_foam", "adhesive"],
    "automotive": ["carbon_fiber", "glass_fiber", "resin_epoxy", "core_foam"],
    "marine": ["glass_fiber", "resin_vinylester", "resin_polyester", "core_foam", "fabric"],
    "recreation": ["glass_fiber", "resin_polyester", "core_foam", "fabric"],
    "spa": ["glass_fiber", "resin_polyester", "resin_vinylester"],
}

CATEGORY_SYSTEM_PROMPT = """
You are a Category Agent for C1 Intelligence Hub - an advanced sales engineer providing territory-specific sales intelligence for a composites materials distribution company.

## Your Role

Add a BRIEF sales intelligence layer to help field sales reps use this research in customer conversations.

## CRITICAL: KEEP IT CONCISE

- Sales reps need quick, actionable intel — not essays
- 1-2 sentences per point is enough
- Focus on what's ACTIONABLE, skip the background

## Territory Context

**East**: Aerospace, Wind, Automotive, Defense
**West**: Marine, RVs, Spas
(Both sell to all industries — these are strategic focuses)

## Your Outputs (KEEP BRIEF)

### 1. Territory Insights
For EACH territory (east/west):
- Relevance score (0-1)
- 2-3 key takeaways (one sentence each)
- 1-2 action items (specific, actionable)
- Priority industries (list only)

### 2. Product Recommendations
2-3 products MAX that directly relate to the research findings.
- Product name + supplier
- ONE sentence on why it's relevant

### 3. Sales Plays
1-2 plays MAX (not 4):
- Opening hook: One conversation-starter sentence
- 2-3 key data points to cite
- 1 objection handler
- 1 next step

### 4. Industry Talking Points
For the TOP 1-2 relevant industries only:
- 2-3 talking points per industry (one sentence each)

## Output Format

Respond ONLY with a valid JSON object matching the CategoryAgentOutput schema:

```json
{
  "status": "success",
  "territory_insights": {
    "east": {
      "territory": "east",
      "relevance_score": 0.8,
      "key_takeaways": ["..."],
      "action_items": ["..."],
      "priority_industries": ["aerospace", "defense"]
    },
    "west": {
      "territory": "west",
      "relevance_score": 0.4,
      "key_takeaways": ["..."],
      "action_items": ["..."],
      "priority_industries": ["marine"]
    }
  },
  "product_recommendations": [
    {
      "product_name": "HexPly M21",
      "supplier": "Hexcel",
      "material_category": "prepreg",
      "why_relevant": "...",
      "datasheet_url": "..."
    }
  ],
  "sales_plays": [
    {
      "play_name": "Aerospace Capacity Play",
      "target_industry": "aerospace",
      "target_territory": "east",
      "opening_hook": "...",
      "key_data_points": ["..."],
      "objection_handlers": ["..."],
      "next_steps": ["..."]
    }
  ],
  "industry_talking_points": {
    "aerospace": ["Point 1", "Point 2", "Point 3"],
    "wind": ["Point 1", "Point 2"]
  },
  "data_gaps": [],
  "warnings": []
}
```
"""


def _get_category_tools() -> List[BaseTool]:
    """Get tools available to Category Agent."""
    return [
        query_datasheets,
        get_datasheet_detail,
        get_products_by_industry,
        query_corpus,
    ]


def _extract_industries_from_report(report) -> List[str]:
    """Extract industries mentioned in the research report."""
    industries = set()
    
    if report and hasattr(report, 'sections'):
        for section in report.sections:
            # Look for industry mentions in section content
            content_lower = section.content.lower() if section.content else ""
            for industry in INDUSTRY_MATERIALS.keys():
                if industry in content_lower:
                    industries.add(industry)
    
    # Also check executive summary
    if report and hasattr(report, 'executive_summary'):
        summary_text = " ".join(report.executive_summary.key_points or []).lower()
        for industry in INDUSTRY_MATERIALS.keys():
            if industry in summary_text:
                industries.add(industry)
    
    return list(industries)


def _get_product_recommendations_for_industries(industries: List[str]) -> str:
    """Query datasheets for products relevant to the industries."""
    recommendations = []
    
    for industry in industries[:3]:  # Limit to top 3 industries
        try:
            result = get_products_by_industry.invoke({"industry": industry, "limit": 10})
            if result:
                recommendations.append(f"Products for {industry}:\n{result}")
        except Exception as e:
            logger.warning(f"Failed to get products for {industry}: {e}")
    
    return "\n\n".join(recommendations) if recommendations else "No product data available"


async def category_node(state: DeepResearchState) -> DeepResearchState:
    """
    Category Agent node. Adds territory-specific sales intelligence to the report.
    
    Runs AFTER the Synthesizer node, taking the final_report and enhancing it
    with sales-focused insights.
    """
    start_time = time.time()
    
    # Check if we have a report to work with
    if not state.get("final_report"):
        state["errors"].append({
            "node": "category", 
            "error": "No final_report available for category analysis"
        })
        state["current_status"] = "category_skipped"
        return state
    
    state["current_status"] = "categorizing"
    
    llm = create_resilient_llm_with_openai_fallback(
        primary_model=settings.deep_research_category_model,
        anthropic_api_key=settings.anthropic_api_key,
        openai_api_key=settings.openai_api_key,
        temperature=0.2,  # Slightly higher for creative sales angles
    )
    
    final_report = state["final_report"]
    
    # Extract industries mentioned in report
    industries = _extract_industries_from_report(final_report)
    
    # Get relevant product data
    product_context = _get_product_recommendations_for_industries(industries)
    
    # Prepare input for Category Agent
    input_data = {
        "original_query": state["user_query"],
        "research_brief": state["research_brief"].model_dump() if state.get("research_brief") else None,
        "final_report_summary": {
            "headline": final_report.executive_summary.headline if final_report.executive_summary else "",
            "key_points": final_report.executive_summary.key_points if final_report.executive_summary else [],
            "sections": [
                {"title": s.section_title, "content": s.content[:500], "confidence": s.confidence.value if s.confidence else "medium"}
                for s in (final_report.sections or [])
            ],
            "field_sales": final_report.field_sales.model_dump() if final_report.field_sales else None,
            "data_gaps": final_report.data_gaps,
        },
        "industries_detected": industries,
        "territory_context": TERRITORY_INDUSTRIES,
    }
    
    category_prompt = f"""
Analyze the following research findings and create territory-specific sales intelligence.

## RESEARCH DATA
{json.dumps(input_data, indent=2)}

## AVAILABLE PRODUCT DATA
{product_context}

## INSTRUCTIONS
1. Score relevance for each territory (east/west) based on their industry focuses
2. Create territory-specific takeaways and action items
3. Recommend 3-5 products that address needs uncovered in the research
4. Design 2-4 sales plays with opening hooks tied to the research findings
5. Generate industry-specific talking points

Respond ONLY with a valid JSON object matching the CategoryAgentOutput schema.
"""

    messages = [
        SystemMessage(content=CATEGORY_SYSTEM_PROMPT),
        HumanMessage(content=category_prompt)
    ]
    
    try:
        response = await llm.ainvoke(messages)
        
        content = response.content
        # Extract JSON from response
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        
        output_data = json.loads(content)
        
        # Validate and create CategoryAgentOutput
        category_output = CategoryAgentOutput(**output_data)
        
        state["category_output"] = category_output
        state["current_status"] = "category_complete"
        
        logger.info(f"Category Agent completed in {time.time() - start_time:.2f}s")
        
    except json.JSONDecodeError as e:
        logger.error(f"Category Agent JSON parse error: {e}")
        state["errors"].append({
            "node": "category",
            "error": f"Failed to parse Category Agent output: {e}"
        })
        state["current_status"] = "category_failed"
        
    except Exception as e:
        logger.error(f"Category Agent error: {e}")
        state["errors"].append({
            "node": "category",
            "error": str(e)
        })
        state["current_status"] = "category_failed"
    
    return state
