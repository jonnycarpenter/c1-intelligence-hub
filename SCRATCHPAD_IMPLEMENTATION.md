# Scratchpad Implementation Guide

Implementation reference for adding scratchpad logic to the Deep Research workflow.

## Overview

Scratchpads provide working memory for agents to accumulate findings across tool calls and plan before generating outputs. This improves output quality and provides debugging visibility.

## State Schema Updates

**File**: `app/graph/state.py`

Add these fields to `ResearchState`:

```python
from typing import Annotated
from operator import add

class ResearchState(TypedDict):
    # ... existing fields ...
    
    # Scratchpads - use `add` reducer to accumulate across steps
    financial_scratchpad: Annotated[list[str], add]
    industry_scratchpad: Annotated[list[str], add]
    synthesis_scratchpad: Annotated[list[str], add]
    validation_scratchpad: Annotated[list[str], add]
```

**Important**: The `add` reducer appends new items to the list. Each node returns a list of strings, which gets merged into the cumulative scratchpad.

## Implementation by Node

### 1. Financial Research (`app/agents/research/financial.py`)

**Purpose**: Track which tools were called, what was found, and what was skipped (conditional gating).

```python
async def financial_research_node(state: ResearchState) -> dict:
    scratchpad = []
    user_query = state["user_query"]
    research_brief = state["research_brief"]
    
    # Log start
    scratchpad.append(f"[START] Processing query: {user_query[:100]}...")
    scratchpad.append(f"[BRIEF] Entities: {research_brief.entities}, Industries: {research_brief.industries}")
    
    # Tool: Corpus Query (always runs)
    corpus_results = await query_corpus(research_brief.financial_queries)
    scratchpad.append(f"[CORPUS] Found {len(corpus_results)} articles")
    if corpus_results:
        scratchpad.append(f"[CORPUS] Top themes: {_extract_themes(corpus_results)}")
    
    # Tool: Earnings (conditional)
    if research_brief.entities:  # Only if specific companies mentioned
        for entity in research_brief.entities[:3]:  # Limit to 3
            earnings = await get_earnings_transcript_ninja(entity)
            if earnings:
                scratchpad.append(f"[EARNINGS] {entity}: Retrieved {earnings.quarter} transcript")
                scratchpad.append(f"[EARNINGS] {entity}: Key points - {_summarize_key_points(earnings)}")
            else:
                scratchpad.append(f"[EARNINGS] {entity}: No transcript found")
    else:
        scratchpad.append("[EARNINGS] Skipped - no specific companies in query")
    
    # Tool: SEC Filings
    sec_results = await get_sec_filings(research_brief.entities)
    scratchpad.append(f"[SEC] Retrieved {len(sec_results)} filings")
    
    # Tool: Analyst Ratings
    ratings = await get_analyst_ratings(research_brief.entities)
    scratchpad.append(f"[RATINGS] Found {len(ratings)} analyst opinions")
    if ratings:
        scratchpad.append(f"[RATINGS] Consensus: {_summarize_consensus(ratings)}")
    
    # Synthesis - include scratchpad in prompt for context
    synthesis_prompt = f"""
Based on your research notes:
{chr(10).join(scratchpad)}

Generate a FinancialAgentOutput with findings and citations.
Focus on the most significant insights from the tools that returned data.
"""
    
    financial_output = await _generate_financial_output(synthesis_prompt, corpus_results, earnings, sec_results, ratings)
    
    scratchpad.append(f"[COMPLETE] Generated {len(financial_output.findings)} findings")
    
    logger.info(f"[FINANCIAL_RESEARCH] Scratchpad entries: {len(scratchpad)}")
    
    return {
        "financial_output": financial_output,
        "financial_scratchpad": scratchpad,
        "current_status": "financial_complete"
    }
```

### 2. Industry Research (`app/agents/research/industry.py`)

**Purpose**: Track news sources, demand signals, and competitive intelligence gathered.

```python
async def industry_research_node(state: ResearchState) -> dict:
    scratchpad = []
    research_brief = state["research_brief"]
    
    scratchpad.append(f"[START] Industry queries: {len(research_brief.industry_queries)}")
    
    # Tool: News Search (Exa)
    news_results = await news_search(research_brief.industry_queries)
    scratchpad.append(f"[NEWS] Found {len(news_results)} articles from Exa")
    if news_results:
        sources = set(r.source for r in news_results)
        scratchpad.append(f"[NEWS] Sources: {', '.join(list(sources)[:5])}")
    
    # Tool: Corpus Query
    corpus_results = await query_corpus(research_brief.industry_queries)
    scratchpad.append(f"[CORPUS] Found {len(corpus_results)} pre-ingested articles")
    
    # Tool: Google Trends
    trends = await get_google_trends(research_brief.industries)
    scratchpad.append(f"[TRENDS] Analyzed {len(trends)} trend signals")
    for trend in trends[:3]:
        scratchpad.append(f"[TRENDS] {trend.keyword}: {trend.direction} ({trend.change_pct}%)")
    
    # Tool: Market Signals
    signals = await get_market_signals(research_brief.industries)
    scratchpad.append(f"[SIGNALS] Retrieved {len(signals)} market indicators")
    
    # Tool: Freight Rates (supply chain)
    freight = await get_freight_rates(research_brief.industries)
    if freight:
        scratchpad.append(f"[FREIGHT] Rates: {freight.summary}")
    else:
        scratchpad.append("[FREIGHT] No relevant freight data")
    
    # Note any gaps
    if not news_results and not corpus_results:
        scratchpad.append("[GAP] Limited news coverage - may need to broaden search terms")
    
    # Synthesis
    synthesis_prompt = f"""
Research notes:
{chr(10).join(scratchpad)}

Generate IndustryAgentOutput focusing on demand signals and competitive shifts.
"""
    
    industry_output = await _generate_industry_output(synthesis_prompt, news_results, corpus_results, trends, signals, freight)
    
    scratchpad.append(f"[COMPLETE] Generated {len(industry_output.findings)} findings, {len(industry_output.demand_signals)} demand signals")
    
    return {
        "industry_output": industry_output,
        "industry_scratchpad": scratchpad,
        "current_status": "industry_complete"
    }
```

### 3. Synthesizer (`app/agents/research/synthesizer.py`) — HIGHEST VALUE

**Purpose**: Plan report structure, identify overlaps/conflicts, map visuals to sections.

```python
async def synthesizer_node(state: ResearchState) -> dict:
    scratchpad = []
    
    financial = state["financial_output"]
    industry = state["industry_output"]
    visuals = state["visual_output"]
    research_brief = state["research_brief"]
    
    # Step 1: Inventory available content
    scratchpad.append("=== CONTENT INVENTORY ===")
    scratchpad.append(f"[INVENTORY] Financial findings: {len(financial.findings) if financial else 0}")
    scratchpad.append(f"[INVENTORY] Industry findings: {len(industry.findings) if industry else 0}")
    scratchpad.append(f"[INVENTORY] Demand signals: {len(industry.demand_signals) if industry else 0}")
    scratchpad.append(f"[INVENTORY] Visuals available: {len(visuals.visuals) if visuals else 0}")
    scratchpad.append(f"[INVENTORY] Total citations: {_count_citations(financial, industry)}")
    
    # Step 2: Identify themes and overlaps
    scratchpad.append("=== THEME ANALYSIS ===")
    themes = _identify_themes(financial, industry)
    for theme in themes:
        scratchpad.append(f"[THEME] {theme.name}: mentioned in {theme.sources}")
        if theme.has_conflict:
            scratchpad.append(f"[CONFLICT] {theme.name}: {theme.conflict_description}")
    
    # Step 3: Check for data gaps
    scratchpad.append("=== GAP ANALYSIS ===")
    if not financial or len(financial.findings) < 2:
        scratchpad.append("[GAP] Limited financial data - will rely on industry sources")
    if not industry.demand_signals:
        scratchpad.append("[GAP] No demand signals - cannot validate market momentum")
    if research_brief.entities and not _entities_covered(financial, research_brief.entities):
        scratchpad.append(f"[GAP] Missing coverage for: {_missing_entities(financial, research_brief.entities)}")
    
    # Step 4: Plan report structure
    scratchpad.append("=== STRUCTURE PLAN ===")
    sections = _plan_sections(themes, financial, industry)
    for i, section in enumerate(sections, 1):
        scratchpad.append(f"[SECTION {i}] {section.title}: {section.rationale}")
    
    # Step 5: Visual placement
    scratchpad.append("=== VISUAL PLACEMENT ===")
    if visuals and visuals.visuals:
        for visual in visuals.visuals:
            best_section = _match_visual_to_section(visual, sections)
            scratchpad.append(f"[VISUAL] '{visual.description[:50]}...' -> {best_section}")
    else:
        scratchpad.append("[VISUAL] No visuals to place")
    
    # Step 6: Citation strategy
    scratchpad.append("=== CITATION STRATEGY ===")
    scratchpad.append(f"[CITATIONS] Primary sources: {_count_primary_sources(financial, industry)}")
    scratchpad.append(f"[CITATIONS] Will prioritize: earnings calls, SEC filings, trade publications")
    
    # Generate report with scratchpad context
    synthesis_prompt = f"""
You are synthesizing a research report. Here is your planning analysis:

{chr(10).join(scratchpad)}

Original query: {state['user_query']}

Using the structure plan above, generate a comprehensive Report.
- Follow the section order in STRUCTURE PLAN
- Place visuals as indicated in VISUAL PLACEMENT  
- Address any conflicts noted in THEME ANALYSIS
- Acknowledge gaps noted in GAP ANALYSIS where relevant
"""
    
    final_report = await _generate_report(synthesis_prompt, financial, industry, visuals, research_brief)
    
    scratchpad.append(f"[COMPLETE] Generated report with {len(final_report.sections)} sections")
    
    logger.info(f"[SYNTHESIZER] Planning scratchpad: {len(scratchpad)} entries")
    
    return {
        "final_report": final_report,
        "synthesis_scratchpad": scratchpad,
        "current_status": "synthesis_complete"
    }
```

### 4. Validator (`app/agents/research/validator.py`)

**Purpose**: Track QA checks performed and issues found.

```python
async def validator_node(state: ResearchState) -> dict:
    scratchpad = []
    report = state["final_report"]
    issues = []
    
    scratchpad.append("=== VALIDATION START ===")
    
    # Check 1: Section completeness
    scratchpad.append("[CHECK] Section completeness")
    for section in report.sections:
        if len(section.content) < 100:
            issues.append(f"Section '{section.title}' is too short ({len(section.content)} chars)")
            scratchpad.append(f"[ISSUE] Section '{section.title}': content too short")
        else:
            scratchpad.append(f"[PASS] Section '{section.title}': {len(section.content)} chars")
    
    # Check 2: Citation validity
    scratchpad.append("[CHECK] Citation validity")
    for citation in report.citations:
        if not citation.url:
            issues.append(f"Missing URL for citation: {citation.title[:50]}")
            scratchpad.append(f"[ISSUE] Citation missing URL: {citation.title[:50]}")
        elif not _is_valid_url(citation.url):
            issues.append(f"Invalid URL format: {citation.url}")
            scratchpad.append(f"[ISSUE] Invalid URL: {citation.url}")
        else:
            scratchpad.append(f"[PASS] Citation valid: {citation.title[:40]}...")
    
    # Check 3: Visual references
    scratchpad.append("[CHECK] Visual references")
    visual_refs = _extract_visual_refs(report)
    visuals_available = state.get("visual_output")
    if visuals_available:
        for ref in visual_refs:
            if not _visual_exists(ref, visuals_available):
                scratchpad.append(f"[ISSUE] Visual referenced but not found: {ref}")
                issues.append(f"Missing visual: {ref}")
    
    # Check 4: Entity coverage
    scratchpad.append("[CHECK] Entity coverage")
    brief = state["research_brief"]
    if brief.entities:
        mentioned = _entities_mentioned_in_report(report, brief.entities)
        for entity in brief.entities:
            if entity in mentioned:
                scratchpad.append(f"[PASS] Entity covered: {entity}")
            else:
                scratchpad.append(f"[WARN] Entity not covered: {entity}")
    
    # Check 5: Minimum quality bar
    scratchpad.append("[CHECK] Quality metrics")
    word_count = _count_words(report)
    scratchpad.append(f"[METRIC] Word count: {word_count}")
    scratchpad.append(f"[METRIC] Sections: {len(report.sections)}")
    scratchpad.append(f"[METRIC] Citations: {len(report.citations)}")
    
    if word_count < 500:
        issues.append("Report too short (< 500 words)")
        scratchpad.append("[ISSUE] Report below minimum word count")
    
    # Determine validation status
    blocking_issues = [i for i in issues if "Missing" in i or "Invalid" in i]
    if blocking_issues:
        validation_status = "needs_review"
        scratchpad.append(f"[RESULT] NEEDS REVIEW - {len(blocking_issues)} blocking issues")
    else:
        validation_status = "passed"
        scratchpad.append(f"[RESULT] PASSED - {len(issues)} minor issues noted")
    
    scratchpad.append("=== VALIDATION COMPLETE ===")
    
    logger.info(f"[VALIDATOR] Status: {validation_status}, Issues: {len(issues)}")
    
    return {
        "validation_scratchpad": scratchpad,
        "validation_status": validation_status,
        "validation_issues": issues,
        "current_status": "validation_complete"
    }
```

## Debugging with Scratchpads

### Logging Pattern

Every node should log scratchpad summary:

```python
logger.info(f"[{NODE_NAME}] Scratchpad entries: {len(scratchpad)}")
logger.debug(f"[{NODE_NAME}] Scratchpad: {scratchpad}")  # Full dump at debug level
```

### Cloud Run Log Filtering

```bash
# View all scratchpad summaries
gcloud logging read 'textPayload=~"Scratchpad entries"' --limit=50

# Debug specific node scratchpad
gcloud logging read 'textPayload=~"\[SYNTHESIZER\] Scratchpad:"' --limit=10
```

### LangSmith Integration

Scratchpads appear in LangSmith traces as part of node outputs. To make them more visible:

```python
# Add as metadata for easier filtering
from langsmith import traceable

@traceable(metadata={"has_scratchpad": True})
async def synthesizer_node(state: ResearchState) -> dict:
    ...
```

## SSE Streaming (Optional)

If you want to stream scratchpad updates to frontend for real-time visibility:

```python
from app.agents.research.progress import emit_progress

async def financial_research_node(state: ResearchState) -> dict:
    scratchpad = []
    
    # After each tool call
    corpus_results = await query_corpus(...)
    note = f"[CORPUS] Found {len(corpus_results)} articles"
    scratchpad.append(note)
    
    # Optionally emit to frontend
    await emit_progress("financial_research", "scratchpad", {"note": note})
    
    ...
```

## Helper Functions

Add to `app/agents/research/utils.py`:

```python
def format_scratchpad_for_prompt(scratchpad: list[str], max_entries: int = 50) -> str:
    """Format scratchpad for inclusion in LLM prompt."""
    if len(scratchpad) > max_entries:
        # Keep first 10 and last (max_entries - 10) for context
        truncated = scratchpad[:10] + ["... truncated ..."] + scratchpad[-(max_entries - 10):]
        return "\n".join(truncated)
    return "\n".join(scratchpad)


def summarize_scratchpad(scratchpad: list[str]) -> dict:
    """Generate summary stats from scratchpad for logging."""
    return {
        "total_entries": len(scratchpad),
        "tools_called": len([s for s in scratchpad if s.startswith("[") and "]" in s]),
        "issues_found": len([s for s in scratchpad if "[ISSUE]" in s or "[GAP]" in s]),
        "passes": len([s for s in scratchpad if "[PASS]" in s]),
    }
```

## Testing Scratchpads

```python
# tests/test_scratchpad.py

def test_financial_scratchpad_accumulates():
    """Verify scratchpad entries are added correctly."""
    initial_state = {
        "user_query": "Hexcel outlook",
        "research_brief": mock_brief,
        "financial_scratchpad": [],
    }
    
    result = await financial_research_node(initial_state)
    
    assert len(result["financial_scratchpad"]) > 0
    assert any("[START]" in entry for entry in result["financial_scratchpad"])
    assert any("[COMPLETE]" in entry for entry in result["financial_scratchpad"])


def test_scratchpad_reducer_merges():
    """Verify parallel scratchpads merge correctly."""
    # Simulate parallel return from financial + industry
    financial_return = {"financial_scratchpad": ["[F1]", "[F2]"]}
    industry_return = {"industry_scratchpad": ["[I1]", "[I2]"]}
    
    # After merge, both should be in state
    merged_state = reducer(initial_state, [financial_return, industry_return])
    
    assert merged_state["financial_scratchpad"] == ["[F1]", "[F2]"]
    assert merged_state["industry_scratchpad"] == ["[I1]", "[I2]"]
```

## Summary

| Node | Scratchpad Field | Primary Purpose |
|------|------------------|-----------------|
| Financial | `financial_scratchpad` | Track tool calls, conditional gating decisions, findings |
| Industry | `industry_scratchpad` | Track sources, demand signals, coverage gaps |
| Synthesizer | `synthesis_scratchpad` | Plan structure, map themes, place visuals |
| Validator | `validation_scratchpad` | Log QA checks, issues found, pass/fail status |

**Key Principle**: Scratchpads serve dual purpose:
1. **LLM Context**: Helps the agent "remember" what it found across tool calls
2. **Debugging**: Provides visibility into agent reasoning for troubleshooting
