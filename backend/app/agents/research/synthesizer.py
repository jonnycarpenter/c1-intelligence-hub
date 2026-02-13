from typing import Dict, Any, List, Optional
from langchain_core.messages import SystemMessage, HumanMessage
from app.agents.research.state import DeepResearchState, SynthesisAgentOutput, FindingSection, FieldSalesSection, SupportingVisual, CompanyWithLogo
from app.agents.research.memory import get_research_memory
from app.config.settings import settings
from app.utils.resilient_llm import create_resilient_llm_with_gemini_fallback, get_resilient_async_client
from app.services.logo_service import logo_service, company_name_to_domain
import asyncio
import json
import re
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
        "data_gaps": data.get("data_gaps", [])[:5],
    }
    
    # Condense findings to just the core content
    for f in data.get("findings", [])[:20]:  # Widened from 10 to surface more findings
        citation = f.get("citation", {}) or {}
        entry = {
            "finding": f.get("finding"),
            "type": f.get("finding_type") or f.get("event_type"),
            "confidence": f.get("confidence"),
            "entities": f.get("entities_mentioned", [])[:6],
            "source": citation.get("source_title"),
            "source_url": citation.get("source_url"),
            "source_date": citation.get("source_date"),
        }

        # Preserve fields critical for quote blocks and rich synthesis
        if citation.get("direct_quote"):
            entry["direct_quote"] = citation["direct_quote"]
        if citation.get("source_type"):
            entry["source_type"] = str(citation["source_type"])
        if citation.get("page_or_section"):
            entry["page_or_section"] = citation["page_or_section"]

        # Preserve sentiment for quote block styling
        sentiment = f.get("sentiment")
        if sentiment:
            entry["sentiment"] = str(sentiment)

        # Preserve metrics for metric_grid blocks
        metrics = f.get("metrics")
        if metrics:
            entry["metrics"] = metrics

        condensed["findings"].append(entry)

    return condensed


def _extract_quotable_findings(financial_condensed, industry_condensed) -> Dict[str, List[Dict]]:
    """
    Extract findings with direct_quote into categorized buckets for explicit
    presentation to the synthesizer LLM.

    Returns dict with keys: executive_quotes, sec_nuggets, podcast_quotes
    """
    buckets = {
        "executive_quotes": [],
        "sec_nuggets": [],
        "podcast_quotes": [],
    }

    for condensed in [financial_condensed, industry_condensed]:
        if not condensed:
            continue
        for f in condensed.get("findings", []):
            quote = f.get("direct_quote")
            if not quote:
                continue

            source_type = (f.get("source_type") or "").lower()
            entry = {
                "quote": quote,
                "finding": f.get("finding"),
                "source": f.get("source"),
                "source_type": source_type,
                "source_url": f.get("source_url"),
                "source_date": f.get("source_date"),
                "sentiment": f.get("sentiment"),
                "entities": f.get("entities", []),
            }

            if source_type in ("earnings_call",):
                buckets["executive_quotes"].append(entry)
            elif source_type in ("sec_10k", "sec_10q", "sec_8k", "sec_filing"):
                buckets["sec_nuggets"].append(entry)
            elif source_type in ("podcast", "trade_publication"):
                buckets["podcast_quotes"].append(entry)
            else:
                # Default: treat as executive quote if it has a quote
                buckets["executive_quotes"].append(entry)

    return buckets


def _build_quotes_section(quotable: Dict[str, List[Dict]]) -> str:
    """Build a structured prompt section highlighting available quotable material."""
    if not any(quotable.values()):
        return ""

    parts = ["\n## QUOTABLE MATERIAL (USE THESE FOR `quote` BLOCKS)\nYou MUST use `quote` blocks for the direct quotes below.\n"]

    if quotable["executive_quotes"]:
        parts.append(f"### Executive Quotes ({len(quotable['executive_quotes'])} available)")
        for i, q in enumerate(quotable["executive_quotes"][:8]):
            parts.append(f'{i+1}. "{q["quote"]}"')
            parts.append(f'   Source: {q.get("source", "Unknown")} | {q.get("source_date", "")}')
            parts.append(f'   Sentiment: {q.get("sentiment", "neutral")} | source_type: earnings_call')
            parts.append("")

    if quotable["sec_nuggets"]:
        parts.append(f"### SEC Filing Nuggets ({len(quotable['sec_nuggets'])} available)")
        for i, q in enumerate(quotable["sec_nuggets"][:8]):
            parts.append(f'{i+1}. "{q["quote"]}"')
            parts.append(f'   Source: {q.get("source", "Unknown")} | {q.get("source_date", "")}')
            parts.append(f'   source_type: sec_filing')
            parts.append("")

    if quotable["podcast_quotes"]:
        parts.append(f"### Podcast Expert Insights ({len(quotable['podcast_quotes'])} available)")
        for i, q in enumerate(quotable["podcast_quotes"][:8]):
            parts.append(f'{i+1}. "{q["quote"]}"')
            parts.append(f'   Source: {q.get("source", "Unknown")} | {q.get("source_date", "")}')
            parts.append(f'   source_type: podcast')
            parts.append("")

    return "\n".join(parts)


def _hydrate_visual_blocks(sections: list, available_visuals: list) -> list:
    """
    Inject image_url and other visual metadata into blocks that reference a visual_id.
    
    The LLM generates visual_split blocks with just a visual_id reference.
    This function hydrates the block.data with the actual image_url, caption,
    and data_summary from the available_visuals list.
    """
    if not available_visuals:
        return sections
    
    # Create lookup by visual_id
    visual_lookup = {v.get("visual_id"): v for v in available_visuals}
    
    for section in sections:
        if not isinstance(section, dict):
            continue
        for block in section.get("blocks", []):
            if not isinstance(block, dict):
                continue
            if block.get("block_type") in ("visual_split", "visual_hero"):
                data = block.get("data", {})
                vid = data.get("visual_id")
                if vid and vid in visual_lookup:
                    visual = visual_lookup[vid]
                    # Hydrate missing fields from available_visuals
                    if not data.get("image_url"):
                        data["image_url"] = visual.get("image_url")
                    if not data.get("caption"):
                        data["caption"] = visual.get("caption")
                    if not data.get("data_summary"):
                        data["data_summary"] = visual.get("data_summary")
                    # Also include article_url for sourcing
                    if not data.get("article_url"):
                        data["article_url"] = visual.get("article_url")
                    logger.debug(f"[SYNTHESIZER] Hydrated visual block {vid} with image_url: {data.get('image_url')[:50] if data.get('image_url') else 'N/A'}...")
    
    return sections


SYNTHESIZER_SYSTEM_PROMPT = """You are a synthesis agent producing comprehensive, deep-dive intelligence briefs. Convert research findings into a thorough, block-based report with rich evidence.

## GOLDEN RULE: Thoroughness with visual structure. Every claim needs evidence, every section needs depth. Use block variety to create a scannable yet comprehensive intelligence brief.

## AVAILABLE COMPONENTS (BLOCK TYPES)

You build the report by stacking these blocks. Choose the best block for the data.

1. `paragraph`: Detailed text analysis (3-6 sentences per block).
   - Use for: Narrative explanation, context, synthesis, implications.
   - Write substantive multi-sentence paragraphs, NOT 1-2 sentence summaries.
   - Must include `citation_badges` metadata.

2. `metric_grid`: A horizontal row of 3-4 key numbers with context.
   - Use for: "At a glance" financials or KPI comparisons.
   - Each metric should have a `context` string explaining significance.
   - Example: Revenue $1.2B (+12% YoY) | Margin 18% (up 200bps) | CapEx $340M (record) | Backlog $4.1B

3. `visual_split`: Side-by-side layout with Text (left/right) and Visual (right/left).
   - Use for: Highlighting a specific chart while analyzing it.
   - constraint: **ONLY use if you have a relevant visual in `available_visuals`**.
   - constraint: You MUST copy the `visual_id` exactly from the input.

4. `quote`: A styled executive/expert quote callout — your most important evidence tool.
   - Use for: Verbatim quotes from earnings calls, podcasts, or SEC filings that ground the narrative.
   - source: Must come from `direct_quote` in findings.
   - REQUIRED fields in data:
     - text: The actual quote text (copy exactly from direct_quote, WITHOUT the speaker attribution suffix)
     - speaker: Full name and title (e.g., "Nick Stanage, CEO, Hexcel")
     - context: Source event — format depends on source_type:
       - For earnings_call: "{Quarter} {Year} Earnings Call" (e.g., "Q3 2025 Earnings Call")
       - For podcast: "{Episode Title}, {Podcast Name}" (e.g., "Wind Blade Recycling, CW Talks")
       - For sec_filing: "{Filing Type}, {Section}" (e.g., "10-K Annual Report, Risk Factors")
     - source_type: "earnings_call" | "podcast" | "sec_filing" | "other" (REQUIRED — determines styling)
     - sentiment: "positive" | "neutral" | "negative" (optional)

5. `table`: A structured data table.
   - Use for: Comparing 3+ items or dimensions across companies/time periods/metrics.

## CITATION REQUIREMENTS (CRITICAL)
Every block that makes a factual claim MUST have a `citations` array with `source_url`.
- Copy `source_url` directly from findings — users need clickable links.
- Include `source_title`, `source_date`, and `source_type` in each citation.
- If a block has no citation, use empty array (but valid blocks usually have sources).

## QUOTE BLOCK MANDATE (CRITICAL)
- If findings contain `direct_quote` fields, you MUST create `quote` blocks for them.
- Minimum: If 3+ direct quotes are available, include AT LEAST 4 `quote` blocks.
- Target: 6-10 quote blocks across the full report (approximately 1-2 per section).
- Maximum: 12 quote blocks total.
- DIVERSITY: Include quotes from DIFFERENT sources (earnings calls, podcasts, SEC filings) and different companies/speakers. Do not repeat the same speaker twice.
- PLACEMENT: Each quote block goes AFTER the paragraph that introduces the topic it covers.
- Quote blocks are PROOF POINTS — they let readers verify your analysis with primary sources.
- Look in the QUOTABLE MATERIAL section of the prompt for pre-extracted quotes ready to use.

## VISUALS STRATEGY (CRITICAL)
- **IF visuals are available**: Use `visual_split` or `visual_hero` to weave them into the narrative.
- **IF NO visuals are available**: Do NOT force visual blocks. Use `paragraph`, `metric_grid`, and `quote` blocks to create visual interest through layout instead.
- **NEVER invent visual_ids**. only use what is provided.

## OUTPUT STRUCTURE (follow exactly)

1. EXECUTIVE SUMMARY
   - headline: 8-15 words, insight-driven with a specific finding or data point (not generic).
   - key_metrics: 3-5 metrics with sources.
   - key_points: 5-8 bullets, each 15-30 words. Every key point must reference a specific data point, date, or source.
   - key_point_citations: Include a citation for EVERY key point.

2. SECTIONS (4-8 sections, proportional to findings volume)
   - For single-company queries: 4-5 sections minimum.
   - For multi-company or industry-wide queries: 6-8 sections.
   - Each section should have 3-7 blocks with a MIX of block types.
   - title: Insight-driven header (not generic like "Financial Overview").
   - blocks: Array of component blocks — mix paragraphs, metric_grids, quotes, tables, and visuals.

## DEPTH AND THOROUGHNESS REQUIREMENTS

This is a COMPREHENSIVE intelligence brief, NOT an executive summary. It should rival the depth of a professional analyst report.

1. **Paragraph blocks**: 3-6 sentences each with context, analysis, and implications. NOT 1-2 sentence summaries. Explain the "so what" — why does this matter?
2. **Multi-paragraph sections**: Most sections should have 2-4 paragraph blocks interspersed with metric_grid and quote blocks.
3. **Quote blocks are PROOF POINTS** — they validate your analysis. Place them after the analysis they support.
4. **Metric grids**: 3-4 metrics with context strings explaining significance (e.g., "+12% YoY", "record high", "below guidance").
5. **Tables**: Compare 3+ dimensions (companies, time periods, metrics) when data supports it.
6. **Connect findings**: Show how financial data relates to industry signals. Draw cause-and-effect connections between different sources.
7. **Be specific**: Use exact numbers, dates, company names, and speaker attributions. Never use vague language like "industry sources say" or "expected to grow."
8. **Do NOT discard findings**: If you receive 20+ findings, create enough sections to cover them all. Every finding with a direct_quote should appear as a quote block.
9. **Source attribution**: Every paragraph should reference which data source supports its claims via the citations array.

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


def _repair_truncated_json(raw: str) -> Optional[Dict]:
    """
    Attempt to repair truncated JSON from an LLM that hit max_tokens.
    
    Strategy:
    1. Strip any trailing incomplete string/value
    2. Close all open brackets/braces
    3. Try to parse
    
    Returns parsed dict on success, None on failure.
    """
    if not raw or not raw.strip():
        return None
    
    text = raw.strip()
    
    # Strategy 1: Truncate to last complete value and close brackets
    # Find the last complete JSON value boundary (}, ], ", number, true/false/null)
    # Walk backwards to find a safe truncation point
    
    attempts = []
    
    # Attempt A: Cut at last complete array element or object
    # Find last occurrence of }, ] followed by optional comma
    for pattern in [r'}\s*,?\s*$', r']\s*,?\s*$', r'"\s*,?\s*$']:
        match = re.search(pattern, text)
    
    # Attempt B: Progressively truncate from the end and try closing brackets
    # Find the last "good" position - a complete key-value or array element
    last_good = len(text)
    for i in range(len(text) - 1, max(0, len(text) - 500), -1):
        ch = text[i]
        if ch in ('}', ']', '"') or text[i:i+4] in ('true', 'null') or text[i:i+5] == 'false':
            # Check if we're inside a string by counting unescaped quotes
            # Simple heuristic: try truncating here and closing
            candidate = text[:i+1]
            # Remove trailing comma if present
            candidate = candidate.rstrip().rstrip(',')
            
            # Count open/close brackets
            open_braces = candidate.count('{') - candidate.count('}')
            open_brackets = candidate.count('[') - candidate.count(']')
            
            # Check for unterminated strings (rough heuristic)
            # Count unescaped quotes
            quote_count = 0
            j = 0
            while j < len(candidate):
                if candidate[j] == '"' and (j == 0 or candidate[j-1] != '\\'):
                    quote_count += 1
                j += 1
            
            in_string = quote_count % 2 == 1
            
            if in_string:
                # Close the string first
                candidate += '"'
            
            # Close all open brackets/braces
            candidate += ']' * max(0, open_brackets)
            candidate += '}' * max(0, open_braces)
            
            try:
                result = json.loads(candidate)
                # Validate it has the minimum required structure
                if isinstance(result, dict) and 'executive_summary' in result:
                    logger.info(f"[SYNTHESIZER] JSON repair SUCCEEDED at position {i}/{len(text)} "
                                f"(closed {open_braces} braces, {open_brackets} brackets, in_string={in_string})")
                    logger.info(f"[SYNTHESIZER] Repaired report has {len(result.get('sections', []))} sections")
                    return result
            except json.JSONDecodeError:
                continue
    
    logger.warning("[SYNTHESIZER] JSON repair FAILED - could not find valid truncation point")
    return None


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
            gemini_api_key=settings.gemini_api_key,
            timeout=240.0,  # Extended thinking + large synthesis needs generous timeout
        )
    else:
        llm = create_resilient_llm_with_gemini_fallback(
            primary_model=settings.deep_research_synthesizer_model,
            anthropic_api_key=settings.anthropic_api_key,
            gemini_api_key=settings.gemini_api_key,
            temperature=0,
            max_tokens=20000,  # Synthesis JSON reports need 8-15k tokens; 4096 default was truncating output
        )
        logger.info(f"[SYNTHESIZER] LLM initialized with max_tokens=20000 (non-thinking path)")
    
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
    
    # Prior research context lookup removed to reduce latency
    
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
    
    # Condense findings (preserves direct_quote, source_type, sentiment, metrics)
    financial_condensed = _condense_findings(financial) if financial else None
    industry_condensed = _condense_findings(industry) if industry else None

    # Extract quotable material for explicit presentation to the LLM
    quotable = _extract_quotable_findings(financial_condensed, industry_condensed)
    quotes_section = _build_quotes_section(quotable)

    total_quotes = sum(len(v) for v in quotable.values())
    logger.info(f"[SYNTHESIZER] Quotable material: {total_quotes} quotes ({len(quotable['executive_quotes'])} exec, {len(quotable['sec_nuggets'])} SEC, {len(quotable['podcast_quotes'])} podcast)")

    research_data = {
        "query": user_query,
        "brief": {
            "intent": research_brief.clarified_intent if research_brief else user_query,
            "entities": companies[:5],
            "timeframe": research_brief.timeframe if research_brief else None,
        } if research_brief else None,
        "financial": financial_condensed,
        "industry": industry_condensed,
        "available_visuals": available_visuals,
    }

    # Generate scratchpad
    planning_notes = _generate_planning_scratchpad(financial, industry, visual, research_brief, user_query)
    planning_scratchpad = "\n".join(planning_notes)

    system_content = SYNTHESIZER_SYSTEM_PROMPT

    synthesis_prompt = f"""Synthesize a dynamic block-based report for: "{user_query}"

## PLANNING & VISUALS
{planning_scratchpad}
Available Visuals: {json.dumps(available_visuals, indent=2)}
{quotes_section}

## RESEARCH DATA
{json.dumps(research_data, indent=2, default=str)}

IMPORTANT: Output ONLY valid JSON. Do NOT wrap in markdown code fences. Produce 4-8 sections, each with 3-7 blocks mixing paragraph, metric_grid, quote, and visual_split types.

JSON SCHEMA (follow exactly):
{{
  "report_id": "REP-{int(time.time())}",
  "generated_at": "{datetime.now().isoformat()}",
  "query": "{user_query}",
  "data_completeness": "complete|partial",
  "overall_confidence": "high|medium",
  "executive_summary": {{
    "headline": "Insight-driven 8-15 word headline with specific data",
    "key_metrics": [{{"label": "Name", "value": "$X.XB", "context": "Why it matters"}}],
    "key_points": ["Specific claim with data point and source reference (15-30 words each). Include 5-8 points."],
    "key_point_citations": [{{"source_type": "earnings_call|sec_filing|podcast|trade_publication|financial_news", "source_title": "Title", "source_url": "https://...", "source_date": "YYYY-MM-DD"}}]
  }},
  "sections": [
    {{
      "section_id": "sec_01",
      "section_title": "Insight-Driven Section Title",
      "content": null,
      "blocks": [
        {{"block_type": "paragraph", "block_id": "blk_01", "data": {{"text": "3-6 sentence analysis..."}}, "citations": [{{"source_type": "...", "source_title": "...", "source_url": "https://..."}}]}},
        {{"block_type": "metric_grid", "block_id": "blk_02", "data": {{"metrics": [{{"label": "...", "value": "...", "context": "..."}}]}}}},
        {{"block_type": "quote", "block_id": "blk_03", "data": {{"text": "Direct quote from findings", "speaker": "Name, Title, Company", "context": "Q3 2025 Earnings Call", "source_type": "earnings_call", "sentiment": "positive"}}, "citations": [{{"source_type": "...", "source_title": "...", "source_url": "https://..."}}]}}
      ],
      "citations": [],
      "supporting_visuals": []
    }}
  ],
  "sources_used": [{{"source_type": "...", "source_title": "...", "source_url": "https://...", "source_date": "..."}}],
  "data_gaps": ["What data was missing or unavailable"],
  "warnings": []
}}

CRITICAL: Generate 4-8 full sections (the schema above shows ONE). Each section needs 3-7 blocks. Mix paragraph, metric_grid, quote, table, and visual_split blocks for a scannable layout. Every factual claim needs a citation with source_url.
"""
    
    # Variable to capture thinking content
    thinking_content = None
    
    if use_thinking:
        messages_raw = [{"role": "user", "content": synthesis_prompt}]
        # max_tokens MUST be greater than thinking.budget_tokens (Anthropic API requirement)
        # We add 16k output tokens on top of the thinking budget for the actual report content
        synthesis_max_tokens = thinking_budget + 16000
        logger.info(f"[SYNTHESIZER] max_tokens={synthesis_max_tokens} (thinking_budget={thinking_budget} + 16000 output)")
        try:
            response = await client.messages_create(
                model=settings.deep_research_synthesizer_model,
                max_tokens=synthesis_max_tokens,
                messages=messages_raw,
                system=system_content,
                thinking={"type": "enabled", "budget_tokens": thinking_budget},
                _caller="synthesizer",
            )
        except Exception as llm_error:
            logger.error(f"[SYNTHESIZER] LLM call failed: [{type(llm_error).__name__}] {llm_error}", exc_info=True)
            raise

        # Parse response content — handle both Anthropic native and Gemini adapter formats
        text_content_parts = []
        try:
            for block in response.content:
                block_type = getattr(block, 'type', None)
                if block_type == 'thinking':
                    thinking_content = getattr(block, 'thinking', None)
                elif block_type == 'text':
                    text_content_parts.append(getattr(block, 'text', ''))
        except Exception as parse_error:
            logger.warning(f"[SYNTHESIZER] Response block parsing error: {parse_error}, attempting raw text extraction")
            # Fallback: try extracting text from any block with a .text attribute
            for block in response.content:
                if hasattr(block, 'text') and block.text:
                    text_content_parts.append(block.text)

        content = '\n'.join(text_content_parts)
        if not content:
            logger.error(f"[SYNTHESIZER] Empty content after parsing {len(response.content)} response blocks")
            raise ValueError("Synthesizer LLM returned empty text content")
    else:
        messages = [SystemMessage(content=system_content), HumanMessage(content=synthesis_prompt)]
        try:
            response = await asyncio.wait_for(
                llm.ainvoke(messages),
                timeout=settings.deep_research_llm_timeout
            )
        except asyncio.TimeoutError:
            logger.error(f"[SYNTHESIZER] LLM call timed out after {settings.deep_research_llm_timeout}s")
            raise TimeoutError(f"Synthesizer LLM call timed out after {settings.deep_research_llm_timeout}s")
        content = response.content
        
    try:
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        
        # First attempt: direct parse
        try:
            output_data = json.loads(content)
        except json.JSONDecodeError as json_err:
            logger.warning(f"[SYNTHESIZER] Direct JSON parse failed: {json_err}. Attempting repair...")
            output_data = _repair_truncated_json(content)
            if output_data is None:
                raise json_err  # Re-raise original error if repair fails
        
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

        # CRITICAL: Hydrate visual blocks with actual image URLs
        # The LLM generates visual_split blocks with only visual_id references.
        # This step injects the actual image_url, caption, etc. from available_visuals.
        if output_data.get("sections") and available_visuals:
            output_data["sections"] = _hydrate_visual_blocks(output_data["sections"], available_visuals)
            logger.info(f"[SYNTHESIZER] Hydrated visual blocks using {len(available_visuals)} available visuals")

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


