from typing import Dict, Any, List, Optional
from langchain_core.messages import SystemMessage, HumanMessage
from app.agents.research.state import DeepResearchState, SynthesisAgentOutput, FindingSection, FieldSalesSection, SupportingVisual, CompanyWithLogo
from app.agents.research.memory import get_research_memory
from app.config.settings import settings
from app.utils.resilient_llm import create_resilient_llm_with_openai_fallback, get_resilient_async_client
from app.services.logo_service import logo_service, company_name_to_domain
import json
import time
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


# =============================================================================
# LLM Output Normalization
# =============================================================================
# The LLM sometimes returns enum values that don't exactly match Pydantic schemas:
# - "text" instead of "paragraph" for block types
# - "High" instead of "high" for confidence
# - Missing required nested fields
# This normalizer fixes these issues before Pydantic validation.

# Block type mapping - LLM variations to valid BlockType enum values
BLOCK_TYPE_MAPPING = {
    "text": "paragraph",
    "para": "paragraph",
    "metric": "metric_grid",
    "metrics": "metric_grid",
    "visual": "visual_split",
    "image": "visual_split",
    "chart": "visual_split",
    "quote_callout": "quote",
    "callout": "quote",
    "data_table": "table",
}

# Valid enum values (lowercase)
VALID_BLOCK_TYPES = {"paragraph", "metric_grid", "visual_hero", "visual_split", "quote", "table"}
VALID_CONFIDENCE_LEVELS = {"high", "medium", "low"}
VALID_DATA_COMPLETENESS = {"complete", "partial", "limited"}


def _normalize_block_type(block_type: str) -> str:
    """Normalize block type string to valid BlockType enum value."""
    if not block_type:
        return "paragraph"  # Default
    
    normalized = block_type.lower().strip()
    
    # Check mapping first
    if normalized in BLOCK_TYPE_MAPPING:
        return BLOCK_TYPE_MAPPING[normalized]
    
    # Check if already valid
    if normalized in VALID_BLOCK_TYPES:
        return normalized
    
    # Default to paragraph for unknown types
    logger.warning(f"[SYNTHESIZER] Unknown block_type '{block_type}', defaulting to 'paragraph'")
    return "paragraph"


def _normalize_confidence(value: str) -> str:
    """Normalize confidence level to valid enum value."""
    if not value:
        return "medium"
    
    normalized = value.lower().strip()
    if normalized in VALID_CONFIDENCE_LEVELS:
        return normalized
    
    # Map common variations
    if "hi" in normalized:
        return "high"
    if "lo" in normalized:
        return "low"
    
    return "medium"


def _normalize_data_completeness(value: str) -> str:
    """Normalize data completeness to valid enum value."""
    if not value:
        return "partial"
    
    normalized = value.lower().strip()
    if normalized in VALID_DATA_COMPLETENESS:
        return normalized
    
    return "partial"


def _normalize_citation(citation: dict) -> dict:
    """Ensure citation has all required fields with defaults."""
    if not citation or not isinstance(citation, dict):
        return {
            "source_type": "industry_news",
            "source_title": "Unknown Source",
            "source_url": None,
            "source_date": None,
        }
    
    return {
        "source_type": citation.get("source_type") or "industry_news",
        "source_title": citation.get("source_title") or "Unknown Source",
        "source_url": citation.get("source_url"),
        "source_date": citation.get("source_date"),
        "page_or_section": citation.get("page_or_section"),
        "direct_quote": citation.get("direct_quote"),
    }


def _normalize_block(block: dict) -> dict:
    """Normalize a report block to match schema requirements."""
    if not block or not isinstance(block, dict):
        return None
    
    return {
        "block_type": _normalize_block_type(block.get("block_type", "paragraph")),
        "block_id": block.get("block_id") or f"blk_{id(block)}",
        "data": block.get("data") or {},
        "citations": [_normalize_citation(c) for c in (block.get("citations") or [])],
    }


def _normalize_section(section: dict) -> dict:
    """Normalize a finding section to match schema requirements."""
    if not section or not isinstance(section, dict):
        return None
    
    normalized_blocks = []
    for block in (section.get("blocks") or []):
        normalized = _normalize_block(block)
        if normalized:
            normalized_blocks.append(normalized)
    
    return {
        "section_id": section.get("section_id") or f"sec_{id(section)}",
        "section_title": section.get("section_title") or "Untitled Section",
        "content": section.get("content"),  # Legacy field
        "blocks": normalized_blocks,
        "citations": [_normalize_citation(c) for c in (section.get("citations") or [])],
        "confidence": _normalize_confidence(section.get("confidence", "medium")),
        "supporting_visuals": section.get("supporting_visuals") or [],
        "tables": section.get("tables") or [],
    }


def _normalize_key_metric(metric: dict) -> dict:
    """Normalize a key metric to match schema requirements."""
    if not metric or not isinstance(metric, dict):
        return None
    
    label = metric.get("label") or metric.get("metric_name") or "Metric"
    return {
        "metric_name": label,
        "label": label,
        "value": str(metric.get("value", "")),
        "context": metric.get("context") or "",
        "source": metric.get("source") or "Research data",
        "confidence": _normalize_confidence(metric.get("confidence", "medium")),
    }


def _normalize_executive_summary(summary: dict) -> dict:
    """Normalize executive summary to match schema requirements."""
    if not summary or not isinstance(summary, dict):
        return {
            "headline": "Research Summary",
            "key_points": [],
            "key_metrics": [],
            "key_point_citations": [],
        }
    
    return {
        "headline": summary.get("headline") or "Research Summary",
        "key_points": summary.get("key_points") or [],
        "key_metrics": [m for m in (_normalize_key_metric(m) for m in (summary.get("key_metrics") or [])) if m],
        "key_point_citations": [_normalize_citation(c) for c in (summary.get("key_point_citations") or [])],
        "data_caveat": summary.get("data_caveat"),
    }


def _normalize_synthesis_output(data: dict) -> dict:
    """
    Master normalizer for LLM synthesis output.
    
    Preprocesses the raw JSON from Claude to ensure all fields match
    Pydantic schema requirements before validation.
    """
    if not data or not isinstance(data, dict):
        return data
    
    try:
        normalized = {
            "report_id": data.get("report_id") or f"REP-{int(time.time())}",
            "generated_at": data.get("generated_at") or "",
            "query": data.get("query") or "",
            "data_completeness": _normalize_data_completeness(data.get("data_completeness", "partial")),
            "overall_confidence": _normalize_confidence(data.get("overall_confidence", "medium")),
            "executive_summary": _normalize_executive_summary(data.get("executive_summary")),
            "sections": [s for s in (_normalize_section(s) for s in (data.get("sections") or [])) if s],
            "thinking_content": data.get("thinking_content"),
            "all_visuals": data.get("all_visuals") or [],
            "companies_with_logos": data.get("companies_with_logos") or [],
            "sources_used": [_normalize_citation(c) for c in (data.get("sources_used") or [])],
            "source_breakdown": data.get("source_breakdown") or {},
            "data_gaps": data.get("data_gaps") or [],
            "warnings": data.get("warnings") or [],
            "research_time_seconds": data.get("research_time_seconds", 0.0),
            "field_sales": data.get("field_sales"),  # Legacy, pass through
        }
        
        logger.info(f"[SYNTHESIZER] Normalized output: {len(normalized['sections'])} sections, {len(normalized['executive_summary'].get('key_points', []))} key points")
        return normalized
        
    except Exception as e:
        logger.error(f"[SYNTHESIZER] Normalization failed: {e}, returning original data")
        return data


def _analyze_finding_dates(findings: list, label: str) -> list:
    """Analyze dates in findings and return scratchpad notes."""
    notes = []
    if not findings:
        notes.append(f"[DATE CHECK] {label}: No findings to analyze")
        return notes
    
    dates = []
    no_date_count = 0
    
    for f in findings:
        # Try to extract date from finding or citation
        pub_date = None
        if hasattr(f, 'citation') and f.citation:
            pub_date = getattr(f.citation, 'source_date', None)
        elif isinstance(f, dict):
            citation = f.get('citation', {})
            if isinstance(citation, dict):
                pub_date = citation.get('source_date')
        
        if pub_date:
            try:
                if isinstance(pub_date, str):
                    # Parse ISO date string
                    parsed = datetime.fromisoformat(pub_date.replace('Z', '+00:00'))
                    dates.append(parsed)
                elif isinstance(pub_date, datetime):
                    dates.append(pub_date)
            except (ValueError, AttributeError):
                no_date_count += 1
        else:
            no_date_count += 1
    
    if dates:
        oldest = min(dates)
        newest = max(dates)
        notes.append(f"[DATE CHECK] {label}: {len(findings)} items, oldest: {oldest.strftime('%Y-%m-%d')}, newest: {newest.strftime('%Y-%m-%d')}")
        
        # Flag stale content (>6 months old)
        six_months_ago = datetime.now() - timedelta(days=180)
        stale_count = sum(1 for d in dates if d < six_months_ago)
        if stale_count > 0:
            notes.append(f"[DATE WARN] {label}: {stale_count} items are >6 months old - consider as historical context only")
    
    if no_date_count > 0:
        notes.append(f"[DATE WARN] {label}: {no_date_count} items have no publication date")
    
    return notes


def _extract_entities_from_findings(financial, industry) -> set:
    """Extract all entities mentioned across findings."""
    entities = set()
    
    for output in [financial, industry]:
        if not output:
            continue
        findings = output.findings if hasattr(output, 'findings') else []
        for f in findings:
            if hasattr(f, 'entities_mentioned') and f.entities_mentioned:
                entities.update(f.entities_mentioned[:5])
            elif isinstance(f, dict) and f.get('entities_mentioned'):
                entities.update(f['entities_mentioned'][:5])
    
    return entities


def _enrich_companies_with_logos(companies: List[str]) -> List[CompanyWithLogo]:
    """
    Add logo URLs for mentioned companies.
    
    Following the same pattern as weekly_briefing.py _enrich_with_logos().
    """
    enriched = []
    seen = set()  # Deduplicate by lowercase name
    
    for company in companies:
        if not company:
            continue
        company_lower = company.lower().strip()
        if company_lower in seen:
            continue
        seen.add(company_lower)
        
        domain = company_name_to_domain(company)
        logo_url = logo_service.get_logo_url(domain) if domain else None
        
        enriched.append(CompanyWithLogo(
            name=company,
            domain=domain,
            logo_url=logo_url
        ))
    
    return enriched[:15]  # Limit to top 15 companies


def _generate_planning_scratchpad(
    financial,
    industry,
    visual,
    research_brief,
    user_query: str
) -> list:
    """
    Generate a planning scratchpad to help the LLM structure the report.
    
    This provides:
    1. Content inventory - what data is available
    2. Date analysis - recency of information
    3. Entity coverage - who/what is mentioned
    4. Gap identification - what's missing
    """
    notes = []
    
    # === CONTENT INVENTORY ===
    notes.append("=== CONTENT INVENTORY ===")
    fin_count = len(financial.findings) if financial and hasattr(financial, 'findings') else 0
    ind_count = len(industry.findings) if industry and hasattr(industry, 'findings') else 0
    vis_count = len(visual.supporting_visuals) if visual and hasattr(visual, 'supporting_visuals') else 0
    
    notes.append(f"[INVENTORY] Financial findings: {fin_count}")
    notes.append(f"[INVENTORY] Industry findings: {ind_count}")
    notes.append(f"[INVENTORY] Visuals available: {vis_count}")
    
    # Demand signals from industry
    if industry and hasattr(industry, 'demand_signals') and industry.demand_signals:
        notes.append(f"[INVENTORY] Demand signals: {len(industry.demand_signals)}")
    
    # === DATE ANALYSIS ===
    notes.append("=== DATE ANALYSIS ===")
    if financial and hasattr(financial, 'findings'):
        notes.extend(_analyze_finding_dates(financial.findings, "Financial"))
    if industry and hasattr(industry, 'findings'):
        notes.extend(_analyze_finding_dates(industry.findings, "Industry"))
    
    # Add timeframe instruction if available
    if research_brief and hasattr(research_brief, 'timeframe') and research_brief.timeframe:
        notes.append(f"[TIMEFRAME] User requested: {research_brief.timeframe}")
        notes.append(f"[TIMEFRAME] Prioritize content matching this period; older content is context only")
    
    # === ENTITY COVERAGE ===
    notes.append("=== ENTITY COVERAGE ===")
    entities = _extract_entities_from_findings(financial, industry)
    if entities:
        notes.append(f"[ENTITIES] Mentioned in findings: {', '.join(list(entities)[:10])}")
    
    # Check if requested entities are covered
    if research_brief and hasattr(research_brief, 'entities_to_track') and research_brief.entities_to_track:
        requested = set(e.lower() for e in research_brief.entities_to_track)
        found = set(e.lower() for e in entities)
        missing = requested - found
        if missing:
            notes.append(f"[GAP] Requested but not found: {', '.join(missing)}")
        else:
            notes.append(f"[COVERAGE] All requested entities covered")
    
    # === DATA QUALITY ===
    notes.append("=== DATA QUALITY ===")
    if fin_count == 0 and ind_count == 0:
        notes.append("[GAP] No findings from either agent - report will be limited")
    elif fin_count == 0:
        notes.append("[GAP] No financial data - rely on industry sources only")
    elif ind_count == 0:
        notes.append("[GAP] No industry data - rely on financial sources only")
    else:
        notes.append("[QUALITY] Both financial and industry data available")
    
    return notes


def _condense_findings(output) -> Dict[str, Any]:
    """Strip verbose fields from agent output to reduce token count."""
    if not output:
        return None
    
    data = output.model_dump() if hasattr(output, 'model_dump') else output
    
    # Keep only essential fields, drop verbose metadata
    condensed = {
        "findings": [],
        "key_metrics": data.get("key_metrics_summary"),
        "data_gaps": data.get("data_gaps", [])[:3],  # Limit gaps
    }
    
    # Condense findings to just the core content
    for f in data.get("findings", [])[:10]:  # Limit to top 10 findings
        citation = f.get("citation", {}) or {}
        condensed["findings"].append({
            "finding": f.get("finding"),
            "type": f.get("finding_type") or f.get("event_type"),
            "confidence": f.get("confidence"),
            "entities": f.get("entities_mentioned", [])[:3],
            "source": citation.get("source_title"),
            "source_url": citation.get("source_url"),  # Include URL for citation linking
            "source_date": citation.get("source_date"),
        })
    
    return condensed


SYNTHESIZER_SYSTEM_PROMPT = """You are a synthesis agent. Convert research findings into a dynamic, block-based executive report.

## GOLDEN RULE: Design the report page. Don't just write text blocks.

## AVAILABLE COMPONENTS (BLOCK TYPES)

You build the report by stacking these blocks. Choose the best block for the data.

1. `paragraph`: Standard text analysis.
   - Use for: Narrative explanation, context, synthesis.
   - Must include `citation_badges` metadata.

2. `metric_grid`: A horizontal row of 2-4 key numbers.
   - Use for: "At a glance" financials or KPI comparisons.
   - Example: Revenue $1.2B | Margin 18% | YoY +12%

3. `visual_split`: Side-by-side layout with Text (left/right) and Visual (right/left).
   - Use for: Highlighting a specific chart while analyzing it.
   - constraint: **ONLY use if you have a relevant visual in `available_visuals`**.
   - constraint: You MUST copy the `visual_id` exactly from the input.

4. `quote`: A styled executive quote callout.
   - Use for: Verbatim CEO/CFO quotes that ground the narrative.
   - source: Must come from `direct_quote` in findings.

5. `table`: A structured data table.
   - Use for: Comparing 3+ items or dimensions.

## CITATION REQUIREMENTS (CRITICAL)
Every block that makes a claim MUST have a `citations` array.
- Use `source_url` from findings.
- If a block has no citation, use empty array (but valid blocks usually have sources).

## VISUALS STRATEGY (CRITICAL)
- **IF visuals are available**: Use `visual_split` or `visual_hero` to weave them into the narrative.
- **IF NO visuals are available**: Do NOT force visual blocks. Use `paragraph`, `metric_grid`, and `quote` blocks to create visual interest through layout instead.
- **NEVER invent visual_ids**. only use what is provided.

## OUTPUT STRUCTURE (follow exactly)

1. EXECUTIVE SUMMARY
   - headline: 12 words max.
   - key_metrics: 2-3 top metadata metrics.
   - key_points: 3-4 bullets.

2. SECTIONS (2-4 customized sections)
   - title: Punchy header.
   - blocks: Array of component blocks (mix paragraphs, grids, quotes, visuals).

"""

async def _get_prior_research_context(query: str, companies: List[str] = None, industries: List[str] = None) -> str:
    """Fetch related prior research for context injection."""
    try:
        memory = await get_research_memory()
        related = await memory.find_related_research(
            query=query,
            companies=companies,
            industries=industries,
        )
        if related:
            return memory.format_context_for_prompt(related)
        return ""
    except Exception as e:
        logger.warning(f"[SYNTHESIZER] Failed to fetch prior research: {e}")
        return ""


async def synthesis_node(state: DeepResearchState) -> DeepResearchState:
    """
    Synthesis node. Merges outputs into a dynamic BLOCK-BASED report.
    """
    start_time = time.time()
    logger.info(f"[SYNTHESIZER] START - query: {state.get('user_query', '')[:50]}...")
    
    # Use raw SDK client for extended thinking support
    use_thinking = settings.deep_research_thinking_enabled
    thinking_budget = settings.deep_research_thinking_budget_tokens
    
    if use_thinking:
        logger.info(f"[SYNTHESIZER] Extended thinking ENABLED with budget: {thinking_budget} tokens")
        client = get_resilient_async_client(
            anthropic_api_key=settings.anthropic_api_key,
            openai_api_key=settings.openai_api_key,
        )
    else:
        llm = create_resilient_llm_with_openai_fallback(
            primary_model=settings.deep_research_synthesizer_model,
            anthropic_api_key=settings.anthropic_api_key,
            openai_api_key=settings.openai_api_key,
            temperature=0,
        )
    
    financial = state.get("financial_output")
    industry = state.get("industry_output")
    visual = state.get("visual_output")
    research_brief = state.get("research_brief")
    user_query = state.get("user_query", "")
    
    if not financial and not industry:
        state["current_status"] = "synthesis_failed_no_input"
        return state
    
    # Extract entities and context
    companies = research_brief.entities_to_track if research_brief else []
    industries = []
    if research_brief and research_brief.domain_context:
        industries = [research_brief.domain_context]
    
    prior_context = await _get_prior_research_context(user_query, companies, industries)
    
    # Prepare visuals for placement
    available_visuals = []
    if visual and visual.supporting_visuals:
        for v in visual.supporting_visuals:
            available_visuals.append({
                "visual_id": v.visual_id,
                "image_url": v.image_url,
                "caption": v.caption,
                "data_summary": v.data_summary,
            })
    
    research_data = {
        "query": user_query,
        "brief": {
            "intent": research_brief.clarified_intent if research_brief else user_query,
            "entities": companies[:5],
            "timeframe": research_brief.timeframe if research_brief else None,
        } if research_brief else None,
        "financial": _condense_findings(financial) if financial else None,
        "industry": _condense_findings(industry) if industry else None,
        "available_visuals": available_visuals,
    }
    
    # Generate scratchpad
    planning_notes = _generate_planning_scratchpad(financial, industry, visual, research_brief, user_query)
    planning_scratchpad = "\n".join(planning_notes)
    
    system_content = SYNTHESIZER_SYSTEM_PROMPT
    if prior_context:
        system_content += f"\n\n{prior_context}"

    synthesis_prompt = f"""Synthesize a dynamic block-based report for: "{user_query}"

## PLANNING & VISUALS
{planning_scratchpad}
Available Visuals: {json.dumps(available_visuals, indent=2)}

## RESEARCH DATA
{json.dumps(research_data, indent=2, default=str)}

OUTPUT FORMAT (valid JSON):
{{
  "report_id": "REP-{int(time.time())}",
  "generated_at": "{datetime.now().isoformat()}",
  "query": "{user_query}",
  "data_completeness": "complete|partial",
  "overall_confidence": "high|medium",
  "executive_summary": {{
    "headline": "Insight lead headline",
    "key_metrics": [{{"label": "Rev", "value": "$1B"}}],
    "key_points": ["Point 1", "Point 2"],
    "key_point_citations": [
       {{"source_type": "sec", "source_title": "10K", "source_url": "http...", "source_date": "2025-01-01"}}
    ]
  }},
  "sections": [
    {{
      "section_id": "sec_01",
      "section_title": "Financial Performance",
      "content": null, // LEGACY field - leave null
      "blocks": [
        {{
            "block_type": "paragraph",
            "block_id": "blk_1",
            "data": {{ "text": "Revenue grew 12%..." }},
            "citations": [{{ "source_url": "..." }}]
        }},
        {{
            "block_type": "metric_grid",
            "block_id": "blk_2",
            "data": {{ 
                "metrics": [
                    {{ "label": "Revenue", "value": "$1.2B", "context": "+12% YoY" }}
                ]
            }}
        }},
        {{
            "block_type": "visual_split",
            "block_id": "blk_3",
            "data": {{
                "visual_id": "vis_123",
                "layout": "text_left",
                "text": "As seen in the chart...",
                "caption": "Figure 1: Revenue trend"
            }},
            "citations": []
        }}
      ],
      "citations": [],
      "supporting_visuals": [] // LEGACY field - okay to leave empty if visuals are in blocks
    }}
  ],
  "sources_used": [],
  "data_gaps": [],
  "warnings": []
}}
"""
    
    # Variable to capture thinking content
    thinking_content = None
    
    if use_thinking:
        messages_raw = [{"role": "user", "content": synthesis_prompt}]
        response = await client.messages_create(
            model=settings.deep_research_synthesizer_model,
            max_tokens=16000,
            messages=messages_raw,
            system=system_content,
            thinking={"type": "enabled", "budget_tokens": thinking_budget},
        )
        # Parser for thinking blocks (same as before)
        text_content_parts = []
        for block in response.content:
            if getattr(block, 'type', None) == 'thinking':
                thinking_content = getattr(block, 'thinking', None)
            elif getattr(block, 'type', None) == 'text':
                text_content_parts.append(getattr(block, 'text', ''))
        content = '\n'.join(text_content_parts)
    else:
        messages = [SystemMessage(content=system_content), HumanMessage(content=synthesis_prompt)]
        response = await llm.ainvoke(messages)
        content = response.content
        
    try:
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
            
        output_data = json.loads(content)
        
        if thinking_content:
            output_data["thinking_content"] = thinking_content
        
        # Pre-populate all_visuals from visual agent's supporting_visuals
        # This ensures the field has data even if LLM doesn't include it
        if visual and visual.supporting_visuals:
            output_data["all_visuals"] = [v.model_dump() for v in visual.supporting_visuals]
            
        # Enrich companies with logos
        # Extract all entities mentioned across findings
        all_entities = list(_extract_entities_from_findings(financial, industry))
        if research_brief and research_brief.entities_to_track:
            all_entities.extend(research_brief.entities_to_track)
        
        companies_with_logos = _enrich_companies_with_logos(all_entities)
        output_data["companies_with_logos"] = [c.model_dump() for c in companies_with_logos]

        # CRITICAL: Normalize LLM output before Pydantic validation
        # This fixes enum mismatches (e.g., "text" -> "paragraph", "High" -> "high")
        # and ensures all nested models have required defaults
        output_data = _normalize_synthesis_output(output_data)

        # Final object
        final_report = SynthesisAgentOutput(**output_data)
        final_report.research_time_seconds = time.time() - start_time
        
        logger.info(f"[SYNTHESIZER] COMPLETE in {time.time() - start_time:.1f}s - {len(final_report.sections)} sections")
        state["final_report"] = final_report
        state["current_status"] = "synthesis_complete"
        
    except Exception as e:
        logger.error(f"[SYNTHESIZER] Failed to parse LLM output: {e}")
        # Log raw response for debugging (first 2000 chars)
        logger.error(f"[SYNTHESIZER] Raw LLM response (first 2000 chars): {content[:2000] if content else 'EMPTY'}")
        logger.error(f"[SYNTHESIZER] Output data keys: {list(output_data.keys()) if 'output_data' in dir() else 'N/A'}")
        
        # FALLBACK: Generate minimal valid report so user gets SOMETHING
        try:
            from app.agents.research.state import ExecutiveSummary, FindingSection, ReportBlock, BlockType
            
            # Create a minimal valid report from raw research data
            fallback_report = SynthesisAgentOutput(
                report_id=f"REP-FALLBACK-{int(time.time())}",
                generated_at=datetime.now().isoformat(),
                query=user_query,
                data_completeness="partial",
                overall_confidence="low",
                executive_summary=ExecutiveSummary(
                    headline=f"Research Results for: {user_query[:100]}",
                    key_points=["Report generation encountered an issue - raw research data available below"],
                    data_caveat="This is a fallback report due to synthesis error."
                ),
                sections=[
                    FindingSection(
                        section_id="fallback_financial",
                        section_title="Financial Research (Raw)",
                        blocks=[ReportBlock(
                            block_type=BlockType.PARAGRAPH,
                            block_id="fb_1",
                            data={"text": f"Financial findings: {len(financial.findings) if financial else 0} items collected. Review logs for details."}
                        )]
                    ),
                    FindingSection(
                        section_id="fallback_industry",
                        section_title="Industry Research (Raw)",
                        blocks=[ReportBlock(
                            block_type=BlockType.PARAGRAPH,
                            block_id="fb_2",
                            data={"text": f"Industry findings: {len(industry.findings) if industry else 0} items collected. Review logs for details."}
                        )]
                    )
                ],
                warnings=[f"Fallback report: {str(e)[:200]}"]
            )
            fallback_report.research_time_seconds = time.time() - start_time
            state["final_report"] = fallback_report
            state["current_status"] = "synthesis_complete_with_fallback"
            logger.warning("[SYNTHESIZER] Generated FALLBACK report due to parsing error")
        except Exception as fallback_error:
            logger.error(f"[SYNTHESIZER] Fallback report generation also failed: {fallback_error}")
            state["errors"].append({
                "node": "synthesis", 
                "error": str(e),
                "response_preview": content[:500] if content else "Empty response"
            })
            state["current_status"] = "synthesis_failed"
        
    return state


