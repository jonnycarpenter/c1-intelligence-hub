from typing import Dict, Any, List, Optional
from langchain_core.messages import SystemMessage, HumanMessage
from app.agents.research.state import DeepResearchState, SynthesisAgentOutput, FindingSection, FieldSalesSection, SupportingVisual, CompanyWithLogo
from app.agents.research.memory import get_research_memory
from app.config.settings import settings
from app.utils.resilient_llm import create_resilient_llm_with_openai_fallback
from app.services.logo_service import logo_service, company_name_to_domain
import json
import time
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


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


SYNTHESIZER_SYSTEM_PROMPT = """You are a synthesis agent. Convert research findings into a BRIEF executive report.

## GOLDEN RULE: Be ruthlessly concise. Every sentence must earn its place.

## OUTPUT STRUCTURE (follow exactly)

1. EXECUTIVE SUMMARY
   - headline: One sentence, 12 words max. Lead with the insight.
   - key_metrics: 2-3 numbers max. Format: {"label": "Name", "value": "$X.XB"}
   - key_points: 3-4 bullets. One sentence each. No fluff.

2. SECTIONS (2-4 max, you have creative license on structure)
   - section_title: 3-5 words - make them punchy and informative
   - content: 2-4 sentences of insight. Use markdown bullets if listing items. No preamble.
   - tables: ONLY if comparing 3+ data points. Otherwise skip.
   - Include relevant EXECUTIVE QUOTES from earnings calls when available - these ground the analysis

3. SOURCES & CITATIONS
   - sources_used: List 3-5 key sources (not every article)
   - CRITICAL: Include source_url from findings data. Users need clickable links!
   - data_gaps: What's missing (1 sentence)

## EXECUTIVE QUOTES
When financial findings include direct_quote from earnings calls, USE THEM:
- Format as blockquote with speaker attribution
- These verbatim CEO/CFO statements ground your analysis
- Example: "> 'We see strong demand in narrowbody...' — Nick Stanage, CEO, Q3 2025"

## YOU HAVE CREATIVE LICENSE
Structure the report based on what the data tells you. You can:
- Create thematic sections that make sense for THIS query
- Highlight key quotes from executives
- Focus on what matters most for the research question
- Include forward-looking implications

## ANTI-PATTERNS (avoid these)
- "It's worth noting..." / "Interestingly..." / "Additionally..."
- Repeating findings across sections
- Tables with <3 rows
- Paragraphs >5 sentences

## PRIOR RESEARCH
If prior research context is provided, you may reference it: "Building on our [date] analysis..." or "This confirms earlier findings that..."
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
    Synthesis node. Merges financial, industry, and visual outputs into a CONCISE final report.
    """
    start_time = time.time()
    logger.info(f"[SYNTHESIZER] START - query: {state.get('user_query', '')[:50]}...")
    
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
    
    # Extract entities for prior research lookup
    companies = research_brief.entities_to_track if research_brief else []
    industries = []
    if research_brief and research_brief.domain_context:
        industries = [research_brief.domain_context]
    
    # Fetch prior research context
    prior_context = await _get_prior_research_context(user_query, companies, industries)
    if prior_context:
        logger.info(f"[SYNTHESIZER] Injecting prior research context ({len(prior_context)} chars)")
    
    # Build condensed research data (strip verbose fields)
    # Format available visuals for LLM to place in sections
    available_visuals = []
    if visual and visual.supporting_visuals:
        for v in visual.supporting_visuals:
            available_visuals.append({
                "visual_id": v.visual_id,
                "image_url": v.image_url,
                "caption": v.caption,
                "placement": v.placement,  # e.g., financial_section, market_section
                "size": v.size,
                "data_summary": v.data_summary,
            })
        logger.info(f"[SYNTHESIZER] {len(available_visuals)} visuals available for section placement")
    
    research_data = {
        "query": user_query,
        "brief": {
            "intent": research_brief.clarified_intent if research_brief else user_query,
            "entities": companies[:5],
            "timeframe": research_brief.timeframe if research_brief else None,
        } if research_brief else None,
        "financial": _condense_findings(financial) if financial else None,
        "industry": _condense_findings(industry) if industry else None,
        "available_visuals": available_visuals,  # For LLM to place in sections
    }
    
    # Generate planning scratchpad for structured pre-synthesis analysis
    planning_notes = _generate_planning_scratchpad(
        financial=financial,
        industry=industry,
        visual=visual,
        research_brief=research_brief,
        user_query=user_query,
    )
    planning_scratchpad = "\n".join(planning_notes)
    logger.info(f"[SYNTHESIZER] Planning scratchpad: {len(planning_notes)} notes")
    logger.debug(f"[SYNTHESIZER] Scratchpad content:\n{planning_scratchpad}")
    
    # Build system prompt with prior context
    system_content = SYNTHESIZER_SYSTEM_PROMPT
    if prior_context:
        system_content += f"\n\n{prior_context}"
    
    # Visual placement instructions for the LLM
    visual_placement_instructions = ""
    if available_visuals:
        visual_placement_instructions = f"""
## VISUAL PLACEMENT INSTRUCTIONS

You have {len(available_visuals)} curated visuals from the Visual Research agent. Place them in sections where they add value:

1. Match the visual's `placement` field to section themes:
   - "financial_section" → sections about revenue, earnings, margins
   - "competitive_section" → sections about market share, competitors
   - "market_section" → sections about trends, forecasts, demand/supply
   - "technology_section" → sections about products, R&D, innovation
   - "supporting_evidence" → general supporting data

2. Include at most 2 visuals per section in `supporting_visuals`

3. For each visual you place, copy the EXACT visual_id, image_url, caption, size, and data_summary

4. Any visuals you don't place in sections will appear in the footer gallery

Available visuals to place:
{json.dumps(available_visuals, indent=2)}
"""
    
    synthesis_prompt = f"""Synthesize into a BRIEF report for: "{user_query}"

## PLANNING ANALYSIS (use this to structure your report)
{planning_scratchpad}
{visual_placement_instructions}
## RESEARCH DATA
{json.dumps(research_data, indent=2, default=str)}

OUTPUT FORMAT (valid JSON):
{{
  "report_id": "REP-{int(time.time())}",
  "generated_at": "{datetime.now().isoformat()}",
  "query": "{user_query}",
  "data_completeness": "complete|partial|limited",
  "overall_confidence": "high|medium|low",
  "executive_summary": {{
    "headline": "12 words max - lead with insight",
    "key_points": ["Point 1", "Point 2", "Point 3"],
    "key_metrics": [
      {{"label": "Metric Name", "value": "$X.XB or X%"}}
    ],
    "data_caveat": null
  }},
  "sections": [
    {{
      "section_id": "sec_001",
      "section_title": "Short Title",
      "content": "2-4 sentences of insight. Use markdown bullets for lists. Include executive quotes when relevant.",
      "tables": [],
      "citations": [{{"source_type": "type", "source_title": "Title", "source_url": "https://... (USE URL FROM FINDINGS DATA)", "source_date": "2025-01-01"}}],
      "confidence": "high|medium|low",
      "supporting_visuals": []
    }}
  ],
  "all_visuals": [],
  "sources_used": [{{"source_type": "type", "source_title": "Title", "source_url": "https://... (USE URL FROM FINDINGS DATA)", "source_date": "2025-01-01"}}],
  "source_breakdown": {{}},
  "data_gaps": ["What's missing"],
  "warnings": [],
  "research_time_seconds": 0.0
}}

Structure the sections based on what the data tells you. Include executive quotes where they add value."""
    
    messages = [
        SystemMessage(content=system_content),
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
        
        # Ensure required fields
        if "generated_at" not in output_data:
            output_data["generated_at"] = datetime.now().isoformat()
        if "report_id" not in output_data:
            output_data["report_id"] = f"REP-{int(time.time())}"
        if "query" not in output_data:
            output_data["query"] = user_query
        
        # Normalize key_metrics to have both label (frontend) and metric_name (backend schema)
        exec_summary = output_data.get("executive_summary", {})
        if "key_metrics" in exec_summary:
            for metric in exec_summary["key_metrics"]:
                # Frontend expects "label", backend schema expects "metric_name"
                if "label" in metric and "metric_name" not in metric:
                    metric["metric_name"] = metric["label"]
                elif "metric_name" in metric and "label" not in metric:
                    metric["label"] = metric["metric_name"]
                # Ensure required backend fields have defaults
                metric.setdefault("context", "")
                metric.setdefault("source", "Research data")
                metric.setdefault("confidence", "medium")
        
        # Ensure arrays exist
        output_data.setdefault("all_visuals", [])
        output_data.setdefault("sources_used", [])
        output_data.setdefault("source_breakdown", {})
        output_data.setdefault("data_gaps", [])
        output_data.setdefault("warnings", [])
        output_data.setdefault("sections", [])
        
        # Populate all_visuals with any unplaced visuals from Visual Agent
        if available_visuals:
            # Collect visual IDs that were placed in sections
            placed_visual_ids = set()
            for section in output_data.get("sections", []):
                for sv in section.get("supporting_visuals", []):
                    if sv.get("visual_id"):
                        placed_visual_ids.add(sv["visual_id"])
            
            # Add unplaced visuals to all_visuals footer gallery
            for v in available_visuals:
                if v["visual_id"] not in placed_visual_ids:
                    output_data["all_visuals"].append(v)
            
            placed_count = len(placed_visual_ids)
            unplaced_count = len(output_data["all_visuals"])
            logger.info(f"[SYNTHESIZER] Visuals: {placed_count} placed in sections, {unplaced_count} in footer gallery")
        
        # Ensure section fields
        for section in output_data.get("sections", []):
            section.setdefault("tables", [])
            section.setdefault("citations", [])
            section.setdefault("supporting_visuals", [])
            section.setdefault("confidence", "medium")
        
        # Enrich companies with logos
        # Extract all entities mentioned across findings
        all_entities = list(_extract_entities_from_findings(financial, industry))
        
        # Also include entities from research brief if available
        if research_brief and research_brief.entities_to_track:
            all_entities.extend(research_brief.entities_to_track)
        
        # Enrich with logo URLs
        companies_with_logos = _enrich_companies_with_logos(all_entities)
        output_data["companies_with_logos"] = [c.model_dump() for c in companies_with_logos]
        logger.info(f"[SYNTHESIZER] Enriched {len(companies_with_logos)} companies with logos")
        
        final_report = SynthesisAgentOutput(**output_data)
        final_report.research_time_seconds = time.time() - start_time
        
        elapsed = time.time() - start_time
        logger.info(f"[SYNTHESIZER] COMPLETE in {elapsed:.1f}s - sections: {len(final_report.sections)}")
        
        state["final_report"] = final_report
        state["current_status"] = "synthesis_complete"
        
    except Exception as e:
        logger.error(f"[SYNTHESIZER] Failed to parse LLM output: {e}")
        logger.error(f"[SYNTHESIZER] Raw response: {response.content[:500] if response else 'None'}...")
        state["errors"].append({"node": "synthesis", "error": str(e)})
        state["current_status"] = "synthesis_failed"
        
    return state
