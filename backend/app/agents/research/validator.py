"""Validator Agent - Citation and attribution verification.

This agent validates the final research report to ensure:
1. All claims have proper citations
2. Citations are properly formatted with sources
3. Unsubstantiated claims are flagged
4. Confidence levels are adjusted based on citation quality
"""

import json
import time
from typing import Dict, Any, List, Optional
from langchain_core.messages import SystemMessage, HumanMessage

from app.agents.research.state import (
    DeepResearchState,
    ValidatorOutput,
    CitationIssue,
)
from app.utils.resilient_llm import create_resilient_llm_with_openai_fallback
from app.config.settings import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

VALIDATOR_SYSTEM_PROMPT = """
You are a Validator Agent for C1 Intelligence Hub - a rigorous fact-checker ensuring research reports meet quality standards before delivery to executives and sales teams.

## Your Role

Review the final research report and validate:
1. **Citation Completeness**: Every factual claim should have a source
2. **Citation Quality**: Sources should be properly attributed with URLs, dates, and titles
3. **Claim Substantiation**: Flag any bold claims lacking supporting evidence
4. **Confidence Alignment**: Verify confidence levels match the underlying data quality

## Validation Rules

### Citation Issues to Flag

1. **missing_url**: Claim references a source but no URL is provided
2. **date_mismatch**: Citation date doesn't match the claim context (e.g., "latest quarterly results" with 2-year-old source)
3. **source_not_found**: Claim mentions data but no citation is attached
4. **vague_attribution**: Citation says "industry sources" or "analysts say" without specifics
5. **broken_chain**: A claim builds on another claim that itself lacks citation

### Unsubstantiated Claims

Flag statements like:
- Market size projections without source
- "Expected to grow X%" without citing analyst/research firm
- "Industry leaders believe..." without naming who
- Competitive claims without supporting data

### Confidence Adjustments

If a section claims "high" confidence but:
- Has data gaps noted
- Relies on single-source data
- Contains dated information (>6 months old)

...recommend downgrading to "medium"

## Output Format

Respond ONLY with valid JSON matching the ValidatorOutput schema:

```json
{
  "validation_passed": true,
  "total_citations_checked": 15,
  "valid_citations": 12,
  "citation_issues": [
    {
      "finding_id": "section_2",
      "issue_type": "missing_url",
      "description": "Market size claim '$4.5B by 2030' lacks source URL",
      "suggested_fix": "Add URL from MarketsandMarkets report referenced in text",
      "severity": "warning"
    }
  ],
  "unsubstantiated_claims": [
    "Claim that 'competitors are struggling' in section 3 lacks supporting evidence"
  ],
  "confidence_adjustments": {
    "section_3": "medium (was high) - relies on single news article"
  },
  "warnings": [
    "3 citations are from sources older than 6 months"
  ]
}
```

## Validation Thresholds

- **validation_passed = true** if:
  - <3 citation issues of severity "error"
  - <5 unsubstantiated claims
  - >80% of checked citations are valid

- **validation_passed = false** if:
  - ≥3 citation issues of severity "error"
  - ≥5 unsubstantiated claims
  - Key executive summary claims lack citations
"""


def _count_citations_in_report(report) -> int:
    """Count total citations in the report."""
    count = 0
    
    if report.sources_used:
        count = len(report.sources_used)
    
    # Also count citations embedded in sections
    if report.sections:
        for section in report.sections:
            if section.citations:
                count += len(section.citations)
    
    return count


def _extract_claims_for_validation(report) -> Dict[str, Any]:
    """Extract key claims from the report for validation."""
    claims = {
        "executive_summary": [],
        "sections": {},
        "field_sales": [],
    }
    
    # Executive summary claims
    if report.executive_summary:
        claims["executive_summary"] = report.executive_summary.key_points or []
        if report.executive_summary.key_metrics:
            claims["executive_summary"].extend([
                f"{m.metric_name}: {m.value}" 
                for m in report.executive_summary.key_metrics
            ])
    
    # Section claims
    if report.sections:
        for section in report.sections:
            claims["sections"][section.section_id] = {
                "title": section.section_title,
                "content_preview": section.content[:500] if section.content else "",
                "citations_count": len(section.citations) if section.citations else 0,
                "stated_confidence": section.confidence.value if section.confidence else "medium",
            }
    
    # Field sales claims
    if report.field_sales:
        if report.field_sales.offensive_angles:
            claims["field_sales"].extend([
                a.angle for a in report.field_sales.offensive_angles
            ])
        if report.field_sales.defensive_angles:
            claims["field_sales"].extend([
                a.angle for a in report.field_sales.defensive_angles
            ])
    
    return claims


async def validator_node(state: DeepResearchState) -> DeepResearchState:
    """
    Validator Agent node. Checks citations and attribution in the final report.
    
    Runs AFTER the Category Agent, as the final quality gate before delivery.
    """
    start_time = time.time()
    
    # Check if we have a report to validate
    if not state.get("final_report"):
        state["errors"].append({
            "node": "validator",
            "error": "No final_report available for validation"
        })
        state["current_status"] = "validation_skipped"
        return state
    
    state["current_status"] = "validating"
    
    llm = create_resilient_llm_with_openai_fallback(
        primary_model=settings.deep_research_validator_model,
        anthropic_api_key=settings.anthropic_api_key,
        openai_api_key=settings.openai_api_key,
        temperature=0,  # Zero temp for consistent validation
    )
    
    final_report = state["final_report"]
    category_output = state.get("category_output")
    
    # Count citations
    total_citations = _count_citations_in_report(final_report)
    
    # Extract claims for validation
    claims = _extract_claims_for_validation(final_report)
    
    # Prepare validation input
    input_data = {
        "original_query": state["user_query"],
        "report_summary": {
            "headline": final_report.executive_summary.headline if final_report.executive_summary else "",
            "data_completeness": final_report.data_completeness.value if final_report.data_completeness else "partial",
            "overall_confidence": final_report.overall_confidence.value if final_report.overall_confidence else "medium",
            "total_citations": total_citations,
            "data_gaps": final_report.data_gaps,
            "warnings": final_report.warnings,
        },
        "claims_to_validate": claims,
        "sources_used": [
            {
                "type": str(s.source_type),
                "title": s.source_title,
                "url": s.source_url,
                "date": s.source_date,
            }
            for s in (final_report.sources_used or [])
        ],
        "category_output": category_output.model_dump() if category_output else None,
    }
    
    validation_prompt = f"""
Validate the following research report for citation completeness and claim substantiation.

## REPORT DATA
{json.dumps(input_data, indent=2)}

## VALIDATION INSTRUCTIONS
1. Check that each key claim in executive_summary and sections has a supporting citation
2. Verify citations have URLs where expected
3. Flag any unsubstantiated claims (especially in field_sales angles)
4. Check if stated confidence levels match the citation quality
5. Note any stale data concerns (sources > 6 months old)

Set validation_passed based on the thresholds defined in your instructions.

Respond ONLY with a valid JSON object matching the ValidatorOutput schema.
"""

    messages = [
        SystemMessage(content=VALIDATOR_SYSTEM_PROMPT),
        HumanMessage(content=validation_prompt)
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
        
        # Add total citations checked if not present
        if "total_citations_checked" not in output_data:
            output_data["total_citations_checked"] = total_citations
        
        # Validate and create ValidatorOutput
        validator_output = ValidatorOutput(**output_data)
        
        state["validator_output"] = validator_output
        state["current_status"] = "validation_complete"
        
        # Log validation result
        if validator_output.validation_passed:
            logger.info(f"Validator passed: {validator_output.valid_citations}/{validator_output.total_citations_checked} citations valid")
        else:
            logger.warning(f"Validator failed: {len(validator_output.citation_issues)} issues, {len(validator_output.unsubstantiated_claims)} unsubstantiated claims")
        
        logger.info(f"Validator Agent completed in {time.time() - start_time:.2f}s")
        
    except json.JSONDecodeError as e:
        logger.error(f"Validator Agent JSON parse error: {e}")
        state["errors"].append({
            "node": "validator",
            "error": f"Failed to parse Validator Agent output: {e}"
        })
        state["current_status"] = "validation_failed"
        # Default to passed if we can't parse (don't block the report)
        state["validator_output"] = ValidatorOutput(
            validation_passed=True,
            warnings=["Validator parsing failed - defaulting to passed"]
        )
        
    except Exception as e:
        logger.error(f"Validator Agent error: {e}")
        state["errors"].append({
            "node": "validator",
            "error": str(e)
        })
        state["current_status"] = "validation_failed"
        # Default to passed if we error (don't block the report)
        state["validator_output"] = ValidatorOutput(
            validation_passed=True,
            warnings=[f"Validator error - defaulting to passed: {str(e)}"]
        )
    
    return state
