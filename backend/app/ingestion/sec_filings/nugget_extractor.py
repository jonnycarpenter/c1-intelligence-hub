"""
SEC Filing Nugget Extractor - C1 Intelligence Hub
==================================================

LLM-based extraction of strategic insights from SEC filings.
Focuses on risk factors, competitive disclosures, and material changes.

Optimized for:
- RPM International and coatings/construction industry
- Competitor filings (Sherwin-Williams, PPG, Sika, etc.)
- Raw material suppliers and channel partners

Uses resilient LLM wrapper with Gemini fallback.

Usage:
    from app.ingestion.sec_filings.nugget_extractor import SecNuggetExtractor

    extractor = SecNuggetExtractor()
    result = await extractor.extract_nuggets(filing_data)

    for nugget in result.nuggets:
        if nugget.is_actionable:
            print(f"[{nugget.nugget_type.value}] {nugget.nugget_text}")
"""

import json
import time
import asyncio
import logging
import re
from datetime import datetime
from typing import Optional, Dict, Any, List

from app.ingestion.sec_filings.models import (
    ExtractedSecNugget,
    SecNuggetExtractionResult,
    FilingType,
    FilingSection,
    NuggetType,
    DisclosureSignalStrength,
    SecFilingTheme,
)
from app.utils.resilient_llm import get_resilient_async_client
from app.config.settings import settings

logger = logging.getLogger(__name__)


# =============================================================================
# RPM-SPECIFIC EXTRACTION PROMPT
# =============================================================================

RPM_NUGGET_EXTRACTION_PROMPT = """You are an SEC filing analyst extracting strategic intelligence for RPM International, a specialty coatings and building materials company.

<filing_metadata>
Company: {company_name}
Ticker: {ticker}
Filing Type: {filing_type}
Fiscal Year: {fiscal_year}
Filing Date: {filing_date}
</filing_metadata>

<filing_content>
{filing_content}
</filing_content>

Extract 15-30 strategic intelligence nuggets from this filing. Focus on:

**RPM BUSINESS CONTEXT:**
RPM International operates in four segments:
- Construction Products (Tremco, Dryvit, Euclid Chemical) - waterproofing, roofing, concrete
- Performance Coatings (Carboline, Stonhard, Flowcrete) - industrial flooring, fireproofing
- Consumer Group (Rust-Oleum, DAP, Zinsser) - DIY paints, sealants, stains
- Specialty Products (Legend Brands, Day-Glo) - restoration equipment, fluorescent pigments

**HIGH-VALUE NUGGET CATEGORIES:**

1. **COMPETITIVE DISCLOSURES** (HIGHEST VALUE)
   - Named competitors (companies MUST disclose material competitive threats)
   - Market position statements
   - Competitive dynamics in coatings, construction chemicals, sealants

2. **RISK ADMISSIONS**
   - Material risks affecting coatings/construction business
   - New risks not disclosed in prior filings
   - Raw material cost risks (TiO2, resins, solvents)
   - Construction market cycle risks

3. **FORWARD GUIDANCE**
   - Strategic initiatives
   - Capital allocation plans
   - Market expansion plans
   - New product/technology investments

4. **REGULATORY EXPOSURE**
   - EPA regulations, VOC compliance
   - Building codes, fire safety standards
   - Environmental remediation liabilities
   - Product liability litigation

5. **MATERIAL CHANGES** (for 8-K)
   - Leadership changes
   - M&A activity (acquisitions, divestitures)
   - Significant agreements
   - Restructuring actions

6. **MARKET CONDITIONS**
   - Commercial construction outlook
   - Residential construction/housing starts
   - Infrastructure spending
   - Industrial facility investments

**CRITICAL INSTRUCTIONS:**
- Extract EXACT quotes when possible (within quotes)
- Flag NEW disclosures (not in prior filings) - these are GOLD
- Identify BURIED disclosures (deep in filing) - may hide concerns
- Note HEDGED language (heavy legal caveats)
- Score relevance to RPM's coatings/construction business (0.0-1.0)

Return a JSON array with nuggets containing:
- nugget_text: The key disclosure (1-3 sentences, exact quote if possible)
- section: "risk_factors", "business", "mda", "legal_proceedings", "market_risk", or "unknown"
- nugget_type: "competitive_disclosure", "risk_admission", "market_position", "forward_guidance", "regulatory_exposure", "litigation_disclosure", "material_change", "strategic_initiative", "supply_chain", "raw_materials", "financial_metric", "esg_disclosure", or "acquisition"
- themes: Array of 1-3 themes from: construction_products, performance_coatings, consumer_group, specialty_products, commercial_construction, residential_construction, infrastructure, industrial_facilities, waterproofing, protective_coatings, concrete_repair, flooring_systems, sealants_adhesives, fireproofing, sherwin_williams, ppg_industries, sika_group, competitive_landscape, raw_material_costs, supply_chain, pricing_strategy, ma_activity, margin_improvement, interest_rates, economic_conditions, regulatory_environment, sustainability, retail_channel, contractor_channel, oem_industrial
- signal_strength: "explicit", "standard", "hedged", "buried", or "new"
- companies_mentioned: Array of company names mentioned
- brands_mentioned: Array of brand names mentioned
- competitors_named: Array of explicitly named competitors (CRITICAL)
- regulators_mentioned: Array of regulatory bodies (EPA, OSHA, etc.)
- risk_level: "high", "medium", or "low"
- is_new_disclosure: true/false (is this a NEW disclosure vs. standard boilerplate?)
- strategic_relevance: "high", "medium", or "low" for RPM's business
- relevance_score: 0.0-1.0 relevance to RPM/coatings industry
- is_actionable: true/false (contains actionable competitive intelligence?)
- actionability_reason: Brief explanation
- business_segment: "construction_products", "performance_coatings", "consumer_group", "specialty_products", "corporate", or null

Return ONLY the JSON array, no other text."""


class SecNuggetExtractor:
    """
    LLM-based nugget extraction from SEC filings.

    Uses Claude Sonnet 4.6 via resilient LLM wrapper for high-quality extraction
    with RPM-specific themes and classification.

    Upgraded from Haiku to Sonnet 4.6 for richer metadata extraction.
    Target cost: ~$0.20-0.60 per filing (using Sonnet 4.6)
    """

    def __init__(
        self,
        model: str = "claude-sonnet-4-6",
        max_tokens: int = 16000,
        temperature: float = 0.2,
        max_content_chars: int = 150000,
    ):
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.max_content_chars = max_content_chars

    async def extract_nuggets(
        self,
        filing_data: Dict[str, Any],
    ) -> SecNuggetExtractionResult:
        """
        Extract strategic nuggets from an SEC filing.

        Args:
            filing_data: Dict with filing information:
                - id or filing_id
                - ticker, company_name, cik
                - filing_type, fiscal_year, fiscal_quarter
                - filing_date
                - sections_json or sections (dict of section_name -> content)
                - raw_content or full_text (fallback if no sections)

        Returns:
            SecNuggetExtractionResult with extracted nuggets
        """
        start_time = time.time()

        # Normalize fields
        filing_id = filing_data.get("id") or filing_data.get("filing_id", "unknown")
        ticker = filing_data.get("ticker", "UNK")
        company_name = filing_data.get("company_name", "Unknown Company")
        cik = filing_data.get("cik", "")
        filing_type = filing_data.get("filing_type") or filing_data.get("form_type", "10-K")
        fiscal_year = filing_data.get("fiscal_year", datetime.now().year)
        fiscal_quarter = filing_data.get("fiscal_quarter")
        filing_date = filing_data.get("filing_date", "Unknown")

        # Initialize result
        result = SecNuggetExtractionResult(
            filing_id=str(filing_id),
            ticker=ticker,
            company_name=company_name,
            filing_type=FilingType(filing_type) if filing_type in [e.value for e in FilingType] else FilingType.OTHER,
            fiscal_year=fiscal_year,
            fiscal_quarter=fiscal_quarter,
            extraction_model=self.model,
            success=False,
        )

        # Get filing content
        filing_content = self._prepare_content(filing_data)
        result.filing_length = len(filing_content)

        if len(filing_content.strip()) < 1000:
            result.error_message = f"Filing content too short for extraction ({len(filing_content)} chars, need 1000+)"
            logger.warning(f"[SEC-EXTRACT] {ticker} {filing_type} {fiscal_year}: {result.error_message}")
            return result

        try:
            # Format filing date
            date_str = filing_date
            if isinstance(filing_date, datetime):
                date_str = filing_date.strftime("%Y-%m-%d")
            elif hasattr(filing_date, 'isoformat'):
                date_str = filing_date.isoformat()

            # Build prompt
            prompt = RPM_NUGGET_EXTRACTION_PROMPT.format(
                company_name=company_name,
                ticker=ticker,
                filing_type=filing_type,
                fiscal_year=fiscal_year,
                filing_date=date_str,
                filing_content=filing_content,
            )

            # Call LLM with resilient client
            logger.info(f"[SEC-EXTRACT] Extracting nuggets from {ticker} {filing_type} {fiscal_year} ({len(filing_content):,} chars)")

            client = get_resilient_async_client(
                anthropic_api_key=settings.anthropic_api_key,
                gemini_api_key=settings.gemini_api_key,
            )

            response = await asyncio.wait_for(
                client.messages_create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    messages=[{"role": "user", "content": prompt}],
                ),
                timeout=120.0,
            )

            # Parse response
            raw_text = response.content[0].text
            raw_nuggets = self._parse_response(raw_text)

            # Convert to ExtractedSecNugget objects
            nuggets = []
            for i, n in enumerate(raw_nuggets):
                try:
                    nugget = self._create_nugget(
                        n,
                        filing_id=str(filing_id),
                        ticker=ticker,
                        company_name=company_name,
                        cik=cik,
                        filing_type=filing_type,
                        fiscal_year=fiscal_year,
                        fiscal_quarter=fiscal_quarter,
                        filing_date=date_str,
                    )
                    nuggets.append(nugget)
                except Exception as e:
                    logger.warning(f"[SEC-EXTRACT] Failed to parse nugget {i+1}: {e}")
                    continue

            result.nuggets = nuggets
            result.success = True
            result.compute_statistics()

            elapsed = time.time() - start_time
            result.extraction_time_seconds = elapsed

            logger.info(
                f"[SEC-EXTRACT] Extracted {len(nuggets)} nuggets from {ticker} {filing_type} {fiscal_year} "
                f"({result.actionable_count} actionable, {result.new_disclosure_count} new) in {elapsed:.1f}s"
            )

        except asyncio.TimeoutError:
            elapsed = time.time() - start_time
            result.error_message = f"LLM call timed out after {elapsed:.1f}s"
            result.extraction_time_seconds = elapsed
            logger.error(f"[SEC-EXTRACT] TIMEOUT for {ticker} {filing_type} {fiscal_year}: exceeded 120s")

        except Exception as e:
            elapsed = time.time() - start_time
            result.error_message = str(e)
            result.extraction_time_seconds = elapsed
            logger.error(f"[SEC-EXTRACT] Extraction FAILED for {ticker} {filing_type} {fiscal_year}: {e}", exc_info=True)

        return result

    def _prepare_content(self, filing_data: Dict[str, Any]) -> str:
        """Prepare filing content for extraction, prioritizing key sections."""
        # Try to get parsed sections
        sections_json = filing_data.get("sections_json", "{}")
        if isinstance(sections_json, str):
            try:
                sections = json.loads(sections_json)
            except (json.JSONDecodeError, TypeError):
                sections = {}
        else:
            sections = sections_json or {}

        # Also check for sections dict directly
        if not sections:
            sections = filing_data.get("sections", {})

        if sections:
            # Prioritize key sections
            priority_sections = [
                "risk_factors",
                "mda",
                "business",
                "legal_proceedings",
                "market_risk",
            ]

            content_parts = []
            for section in priority_sections:
                if section in sections and sections[section]:
                    content_parts.append(f"=== {section.upper().replace('_', ' ')} ===\n{sections[section]}")

            # Add full text if we have room
            if "full_text" in sections:
                remaining = self.max_content_chars - sum(len(p) for p in content_parts)
                if remaining > 10000:
                    content_parts.append(f"=== OTHER CONTENT ===\n{sections['full_text'][:remaining]}")

            content = "\n\n".join(content_parts)
        else:
            # Use raw content or full_text
            content = (
                filing_data.get("raw_content")
                or filing_data.get("full_text")
                or ""
            )

        # Truncate if needed
        if len(content) > self.max_content_chars:
            content = content[:self.max_content_chars] + "\n[TRUNCATED]"

        return content

    def _parse_response(self, response_text: str) -> List[Dict]:
        """Parse LLM response into nugget dicts."""
        text = response_text.strip()

        # Handle markdown code fences
        if "```" in text:
            parts = text.split("```")
            for part in parts:
                part = part.strip()
                if part.startswith("json"):
                    part = part[4:].strip()
                if part.startswith("["):
                    text = part
                    break

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Try to find JSON array
            match = re.search(r'\[[\s\S]*\]', text)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass

            # Handle truncated JSON (model hit max_tokens)
            if text.startswith('['):
                last_complete = text.rfind('},')
                if last_complete == -1:
                    last_complete = text.rfind('}')
                if last_complete > 0:
                    truncated = text[:last_complete + 1] + ']'
                    try:
                        result = json.loads(truncated)
                        logger.warning(f"[SEC-EXTRACT] Recovered {len(result)} nuggets from truncated JSON response")
                        return result
                    except json.JSONDecodeError:
                        pass

            logger.error("[SEC-EXTRACT] Failed to parse JSON response")
            return []

    def _create_nugget(
        self,
        data: Dict[str, Any],
        filing_id: str,
        ticker: str,
        company_name: str,
        cik: str,
        filing_type: str,
        fiscal_year: int,
        fiscal_quarter: Optional[int],
        filing_date: str,
    ) -> ExtractedSecNugget:
        """Create an ExtractedSecNugget from parsed LLM data."""

        # Map section string to enum
        section_str = data.get("section", "unknown").lower()
        section_map = {
            "risk_factors": FilingSection.RISK_FACTORS,
            "business": FilingSection.BUSINESS,
            "mda": FilingSection.MDA,
            "legal_proceedings": FilingSection.LEGAL_PROCEEDINGS,
            "market_risk": FilingSection.MARKET_RISK,
        }
        section = section_map.get(section_str, FilingSection.UNKNOWN)

        # Map nugget type
        type_str = data.get("nugget_type", "risk_admission").lower()
        type_map = {
            "competitive_disclosure": NuggetType.COMPETITIVE_DISCLOSURE,
            "risk_admission": NuggetType.RISK_ADMISSION,
            "market_position": NuggetType.MARKET_POSITION,
            "forward_guidance": NuggetType.FORWARD_GUIDANCE,
            "regulatory_exposure": NuggetType.REGULATORY_EXPOSURE,
            "litigation_disclosure": NuggetType.LITIGATION_DISCLOSURE,
            "material_change": NuggetType.MATERIAL_CHANGE,
            "strategic_initiative": NuggetType.STRATEGIC_INITIATIVE,
            "supply_chain": NuggetType.SUPPLY_CHAIN,
            "raw_materials": NuggetType.RAW_MATERIALS,
            "financial_metric": NuggetType.FINANCIAL_METRIC,
            "esg_disclosure": NuggetType.ESG_DISCLOSURE,
            "acquisition": NuggetType.ACQUISITION,
        }
        nugget_type = type_map.get(type_str, NuggetType.RISK_ADMISSION)

        # Map signal strength
        signal_str = data.get("signal_strength", "standard").lower()
        signal_map = {
            "explicit": DisclosureSignalStrength.EXPLICIT,
            "standard": DisclosureSignalStrength.STANDARD,
            "hedged": DisclosureSignalStrength.HEDGED,
            "buried": DisclosureSignalStrength.BURIED,
            "new": DisclosureSignalStrength.NEW,
        }
        signal_strength = signal_map.get(signal_str, DisclosureSignalStrength.STANDARD)

        # Map themes
        themes = []
        for theme_str in data.get("themes", []):
            try:
                themes.append(SecFilingTheme(theme_str.lower()))
            except ValueError:
                continue

        return ExtractedSecNugget(
            filing_id=filing_id,
            nugget_text=data.get("nugget_text", ""),
            filing_type=FilingType(filing_type) if filing_type in [e.value for e in FilingType] else FilingType.OTHER,
            section=section,
            nugget_type=nugget_type,
            themes=themes,
            signal_strength=signal_strength,
            companies_mentioned=data.get("companies_mentioned", []),
            brands_mentioned=data.get("brands_mentioned", []),
            competitors_named=data.get("competitors_named", []),
            regulators_mentioned=data.get("regulators_mentioned", []),
            risk_level=data.get("risk_level", "medium"),
            is_new_disclosure=data.get("is_new_disclosure", False),
            strategic_relevance=data.get("strategic_relevance", "medium"),
            relevance_score=float(data.get("relevance_score", 0.5)),
            is_actionable=data.get("is_actionable", False),
            actionability_reason=data.get("actionability_reason"),
            business_segment=data.get("business_segment"),
            ticker=ticker,
            company_name=company_name,
            cik=cik,
            fiscal_year=fiscal_year,
            fiscal_quarter=fiscal_quarter,
            filing_date=filing_date,
            extraction_model=self.model,
        )
