"""Visual Research Agent for Deep Research workflow.

This agent searches the article_images BigQuery table for relevant charts,
graphs, and visual assets that support research findings.

Runs in parallel with Financial and Industry agents. Uses LLM reasoning to:
1. Analyze the research brief to determine what visuals would be valuable
2. Execute strategic searches against the article_images corpus
3. Rank and select the most impactful visuals for the report
4. Generate contextual captions that tie visuals to research findings
5. Determine optimal section placement for each visual

NOTE: The article_images table must exist for this agent to return results.
If the table doesn't exist or is empty, the agent gracefully returns an empty
visual list without failing the workflow.
"""

from typing import Dict, Any, List, Optional
from langchain_core.messages import SystemMessage, HumanMessage
from app.agents.research.state import DeepResearchState, VisualAgentOutput, SupportingVisual
from app.agents.research.progress import emit_progress_sync, ToolProgress
from app.utils.resilient_llm import create_resilient_llm_with_gemini_fallback
from app.config.settings import settings
from app.mcp.tools.corpus_visuals import corpus_visuals_search
import json
import time
import logging

logger = logging.getLogger(__name__)


VISUAL_AGENT_SYSTEM_PROMPT = """
You are a Visual Research Agent specializing in selecting impactful charts, graphs, and visual assets to support financial and industry research reports.

## Your Responsibilities

1. ANALYZE the research brief to identify visual needs:
   - What data visualizations would strengthen the findings?
   - Which companies/industries need visual representation?
   - What metrics or trends would benefit from charts?

2. EVALUATE candidate visuals using the RICH METADATA available:
   - **description**: AI-generated summary of what the visual shows
   - **alt_text**: HTML alt text (often describes the visual's purpose)
   - **extracted_text**: OCR text extracted FROM the image itself - this tells you what labels, numbers, and text appear in the visual
   - **extracted_data_points**: Structured data extracted from charts (e.g., [{"label": "Q1 Revenue", "value": "45M"}]) - this is the actual quantitative data shown
   - **companies/industries/topics**: Entities and themes the visual relates to
   
   Use extracted_text and extracted_data_points to understand what SPECIFIC DATA the visual contains. This helps you match visuals to the research query more precisely.

3. SELECT the most impactful visuals (aim for 3-8 per report):
   - Prioritize visuals with extracted_data_points that contain relevant metrics
   - Prioritize visuals where extracted_text matches research entities/topics
   - Balance coverage across key themes
   - Avoid redundant visuals showing similar data

4. GENERATE contextual captions that:
   - Tie the visual directly to research findings
   - Reference specific data points from extracted_data_points when available
   - Highlight the key insight shown
   - Cite the source article

5. DETERMINE optimal placement:
   - "financial_section" - Revenue, earnings, margin data
   - "competitive_section" - Market share, competitive positioning
   - "market_section" - Trends, forecasts, demand/supply
   - "technology_section" - Product diagrams, technical specs
   - "supporting_evidence" - General supporting visuals

## Visual Type Priority
1. Line/Area charts - Best for trends over time
2. Bar charts - Best for comparisons
3. Tables - Best for detailed metrics (often have rich extracted_data_points!)
4. Infographics - Best for market overviews
5. Diagrams - Best for supply chain/process flows

## Output Format
Respond with valid JSON matching the VisualAgentOutput schema. Include:
- supporting_visuals: List of selected visuals with captions and placements
- data_gaps: Topics that would benefit from visuals but none were found
- warnings: Any quality concerns about selected visuals
"""


async def visual_research_node(state: DeepResearchState) -> Dict[str, Any]:
    """
    Visual research node. Uses LLM to intelligently search, rank, and select 
    charts and visual assets to support research findings.
    
    Returns PARTIAL STATE dict with only the fields this node updates.
    This is required for LangGraph's Send API parallel execution.
    
    This node runs in parallel with Financial and Industry agents.
    
    Graceful degradation: If the article_images table doesn't exist or is empty,
    returns an empty visual list without failing the workflow.
    """
    start_time = time.time()
    logger.info(f"[VISUAL_RESEARCH] START - query: {state.get('user_query', '')[:50]}...")
    logger.info(f"[VISUAL_RESEARCH] State keys: {list(state.keys())}")
    
    brief = state.get("research_brief")
    if not brief:
        logger.info("No research brief - skipping visual research")
        return {
            "current_status": "visual_research_skipped",
            "visual_output": None,
            "errors": [],
        }
    
    logger.info("Starting visual research with LLM reasoning")
    emit_progress_sync(ToolProgress(tool_name="visual_agent", message="Analyzing visual needs for research"))
    
    # Initialize LLM for intelligent visual selection
    llm = create_resilient_llm_with_gemini_fallback(
        primary_model=settings.deep_research_financial_model,  # Use same model as financial agent
        anthropic_api_key=settings.anthropic_api_key,
        gemini_api_key=settings.gemini_api_key,
        temperature=0,
    )
    
    all_visuals = []
    search_executed = []
    errors = []
    
    # =========================================================================
    # STEP 1: Extract search parameters from research brief
    # =========================================================================
    
    companies = brief.entities_to_track if brief.entities_to_track else []
    industries = []
    topics = []
    
    # Extract industries from industry_agent_queries
    if brief.industry_agent_queries:
        industry_keywords = ["aerospace", "automotive", "wind", "marine", "defense", "energy", "composites"]
        for query in brief.industry_agent_queries:
            for industry in industry_keywords:
                if industry.lower() in query.lower():
                    if industry not in industries:
                        industries.append(industry)
    
    # Extract topics from financial_agent_queries
    if brief.financial_agent_queries:
        topic_keywords = [
            "revenue", "earnings", "profit", "margin", "guidance",
            "forecast", "market_share", "growth", "trend",
            "supply", "demand", "pricing", "competition"
        ]
        for query in brief.financial_agent_queries:
            for topic in topic_keywords:
                if topic.lower() in query.lower():
                    if topic not in topics:
                        topics.append(topic)
    
    # =========================================================================
    # STEP 2: Execute corpus searches to gather candidate visuals
    # =========================================================================
    
    # Search by companies (most specific)
    if companies:
        emit_progress_sync(ToolProgress(
            tool_name="corpus_visuals_search",
            message=f"Searching visuals for {len(companies)} companies"
        ))
        
        try:
            results_json = corpus_visuals_search.invoke({
                "companies": companies[:5],
                "limit": 15,
                "days": 90,
            })
            
            results = json.loads(results_json)
            if results.get("status") == "success" and results.get("visuals"):
                all_visuals.extend(results["visuals"])
                search_executed.append(f"Companies: {', '.join(companies[:3])}")
                logger.info(f"Found {len(results['visuals'])} visuals by company")
                
        except Exception as e:
            logger.error(f"Company visual search failed: {str(e)}")
            errors.append({
                "node": "visual_research",
                "phase": "company_search",
                "error": str(e)
            })
    
    # Search by industries (broader context)
    if industries:
        emit_progress_sync(ToolProgress(
            tool_name="corpus_visuals_search",
            message=f"Searching visuals for {len(industries)} industries"
        ))
        
        try:
            results_json = corpus_visuals_search.invoke({
                "industries": industries[:5],
                "limit": 15,
                "days": 90,
            })
            
            results = json.loads(results_json)
            if results.get("status") == "success" and results.get("visuals"):
                existing_urls = {v.get("image_url") for v in all_visuals}
                new_visuals = [v for v in results["visuals"] if v.get("image_url") not in existing_urls]
                all_visuals.extend(new_visuals)
                search_executed.append(f"Industries: {', '.join(industries[:3])}")
                logger.info(f"Found {len(new_visuals)} new visuals by industry")
                
        except Exception as e:
            logger.error(f"Industry visual search failed: {str(e)}")
            errors.append({
                "node": "visual_research",
                "phase": "industry_search",
                "error": str(e)
            })
    
    # Search by topics (key metrics and themes)
    if topics:
        emit_progress_sync(ToolProgress(
            tool_name="corpus_visuals_search",
            message=f"Searching visuals for {len(topics)} topics"
        ))
        
        try:
            results_json = corpus_visuals_search.invoke({
                "topics": topics[:5],
                "limit": 15,
                "days": 90,
            })
            
            results = json.loads(results_json)
            if results.get("status") == "success" and results.get("visuals"):
                existing_urls = {v.get("image_url") for v in all_visuals}
                new_visuals = [v for v in results["visuals"] if v.get("image_url") not in existing_urls]
                all_visuals.extend(new_visuals)
                search_executed.append(f"Topics: {', '.join(topics[:3])}")
                logger.info(f"Found {len(new_visuals)} new visuals by topic")
                
        except Exception as e:
            logger.error(f"Topic visual search failed: {str(e)}")
            errors.append({
                "node": "visual_research",
                "phase": "topic_search",
                "error": str(e)
            })
    
    # =========================================================================
    # STEP 3: Use LLM to intelligently select and rank visuals
    # =========================================================================
    
    execution_time = time.time() - start_time
    
    if not all_visuals:
        logger.info("No visuals found - returning empty output")
        visual_output = VisualAgentOutput(
            status="success",
            visuals_found=0,
            searches_executed=search_executed,
            supporting_visuals=[],
            data_gaps=["No visuals found for the specified criteria"],
            warnings=[],
        )
        return {
            "current_status": "visual_research_complete",
            "visual_output": visual_output,
            "errors": errors,
        }
    
    # Prepare candidate visuals for LLM evaluation
    emit_progress_sync(ToolProgress(tool_name="visual_agent", message=f"Evaluating {len(all_visuals)} candidate visuals"))
    
    candidates_summary = []
    for i, v in enumerate(all_visuals[:25]):  # Limit to 25 candidates for LLM context
        # Include rich metadata fields for LLM to understand image contents
        extracted_text = v.get("extracted_text", "")
        extracted_data_points = v.get("extracted_data_points", [])
        
        candidates_summary.append({
            "index": i,
            "visual_id": v.get("visual_id", ""),
            "image_url": v.get("image_url", ""),
            "article_url": v.get("article_url", ""),  # Source article URL
            "description": v.get("description", "")[:400],
            "alt_text": v.get("alt_text", "")[:200],  # Image alt text
            # Extracted OCR text from the image (tells what's actually IN the visual)
            "extracted_text": extracted_text[:500] if extracted_text else "",
            # Structured data points extracted from charts (quantitative data)
            "extracted_data_points": extracted_data_points[:5] if extracted_data_points else [],
            "article_title": v.get("article_title", ""),
            "image_type": v.get("image_type", ""),
            "chart_type": v.get("chart_type", ""),
            "companies": v.get("companies", [])[:3],
            "industries": v.get("industries", [])[:2],
            "topics": v.get("topics", [])[:3],
            "relevance_score": v.get("relevance_score", 0),
        })
    
    # Build LLM prompt
    llm_prompt = f"""
## Research Context

**Original Query**: {brief.original_query}
**Clarified Intent**: {brief.clarified_intent or 'N/A'}
**Entities to Track**: {', '.join(brief.entities_to_track or [])}
**Financial Queries**: {brief.financial_agent_queries or []}
**Industry Queries**: {brief.industry_agent_queries or []}

## Candidate Visuals Found

{json.dumps(candidates_summary, indent=2)}

## Your Task

Select 3-8 of the most impactful visuals from the candidates above. For each selected visual:

1. Explain why it's valuable for this research
2. Write a contextual caption that ties it to the research findings
3. Assign the optimal placement section
4. Recommend a size (small, medium, large)

Respond with valid JSON in this exact format:
{{
    "selected_visuals": [
        {{
            "index": <candidate index>,
            "visual_id": "<from candidate>",
            "image_url": "<from candidate>",
            "caption": "<contextual caption you write>",
            "placement": "<financial_section|competitive_section|market_section|technology_section|supporting_evidence>",
            "size": "<small|medium|large>",
            "selection_rationale": "<why this visual is valuable>"
        }}
    ],
    "data_gaps": ["<topics that would benefit from visuals but none found>"],
    "quality_warnings": ["<any concerns about selected visuals>"]
}}
"""

    try:
        response = await llm.ainvoke([
            SystemMessage(content=VISUAL_AGENT_SYSTEM_PROMPT),
            HumanMessage(content=llm_prompt)
        ])
        
        # Parse LLM response
        response_text = response.content.strip()
        
        # Extract JSON from response (handle markdown code blocks)
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
        
        llm_output = json.loads(response_text)
        
        # Convert LLM selections to SupportingVisual objects
        supporting_visuals = []
        for selection in llm_output.get("selected_visuals", []):
            supporting_visual = SupportingVisual(
                visual_id=selection.get("visual_id", ""),
                image_url=selection.get("image_url", ""),
                caption=selection.get("caption", ""),
                placement=selection.get("placement", "supporting_evidence"),
                size=selection.get("size", "medium"),
                data_summary=selection.get("selection_rationale", ""),
            )
            supporting_visuals.append(supporting_visual)
        
        data_gaps = llm_output.get("data_gaps", [])
        warnings = llm_output.get("quality_warnings", [])
        
        logger.info(f"LLM selected {len(supporting_visuals)} visuals from {len(all_visuals)} candidates")
        
    except Exception as e:
        logger.error(f"LLM visual selection failed: {str(e)}")
        errors.append({
            "node": "visual_research",
            "phase": "llm_selection",
            "error": str(e)
        })
        
        # Fallback: Use simple heuristic selection
        supporting_visuals = _fallback_visual_selection(all_visuals[:10])
        data_gaps = []
        warnings = [f"LLM selection failed, using fallback heuristics: {str(e)}"]
    
    visual_output = VisualAgentOutput(
        status="success",
        visuals_found=len(all_visuals),
        searches_executed=search_executed,
        supporting_visuals=supporting_visuals,
        data_gaps=data_gaps,
        warnings=warnings,
    )
    
    total_time = time.time() - start_time
    logger.info(f"Visual research complete: {len(supporting_visuals)} visuals selected in {total_time:.1f}s")
    
    # Return PARTIAL state - only fields this node updates
    return {
        "current_status": "visual_research_complete",
        "visual_output": visual_output,
        "errors": errors,
    }


def _fallback_visual_selection(visuals: List[Dict]) -> List[SupportingVisual]:
    """
    Fallback heuristic selection when LLM fails.
    Selects top visuals by relevance score with basic placement logic.
    """
    # Sort by relevance score
    sorted_visuals = sorted(visuals, key=lambda v: v.get("relevance_score", 0), reverse=True)
    
    supporting = []
    for visual in sorted_visuals[:8]:
        # Determine placement based on topics
        placement = "supporting_evidence"
        visual_topics = visual.get("topics", [])
        if isinstance(visual_topics, str):
            visual_topics = [visual_topics]
        
        topic_str = " ".join(visual_topics).lower()
        if any(t in topic_str for t in ["revenue", "earnings", "profit", "margin"]):
            placement = "financial_section"
        elif any(t in topic_str for t in ["market_share", "competition", "competitor"]):
            placement = "competitive_section"
        elif any(t in topic_str for t in ["supply", "demand", "trend", "forecast", "growth"]):
            placement = "market_section"
        
        supporting.append(SupportingVisual(
            visual_id=visual.get("visual_id", ""),
            image_url=visual.get("image_url", ""),
            caption=visual.get("description", "")[:200],
            placement=placement,
            size="medium",
            data_summary=f"Source: {visual.get('article_title', 'Unknown')}",
        ))
    
    return supporting
