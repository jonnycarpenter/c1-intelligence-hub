"""
Earnings Quote Extractor - C1 Intelligence Hub
===============================================

LLM-based extraction of executive insights from earnings call transcripts.
Uses Claude Haiku for cost-efficient extraction (~$0.02-0.05 per transcript).

Adapted for composites, aerospace, wind energy, marine, automotive, and
advanced materials industry intelligence.

Usage:
    from app.ingestion.earnings.quote_extractor import EarningsQuoteExtractor

    extractor = EarningsQuoteExtractor()
    result = await extractor.extract_quotes(transcript_data)

    for quote in result.quotes:
        if quote.is_quotable:
            print(f"[{quote.speaker_role.value}] {quote.speaker_name}: {quote.quote_text}")
"""

import json
import time
import asyncio
import logging
import re
from datetime import datetime
from typing import Optional, Dict, Any, List

from app.ingestion.earnings.models import (
    ExtractedEarningsQuote,
    EarningsQuoteExtractionResult,
    SpeakerRole,
    QuoteType,
    ConfidenceLevel,
    CallSection,
    EarningsQuoteTheme,
)
from app.utils.resilient_llm import get_resilient_async_client
from app.config.settings import settings

logger = logging.getLogger(__name__)


# =============================================================================
# INDUSTRY-SPECIFIC EXTRACTION PROMPT
# =============================================================================

QUOTE_EXTRACTION_PROMPT = """You are an earnings call analyst extracting strategic intelligence for a composites and advanced materials industry intelligence platform.

<transcript_metadata>
Company: {company_name}
Ticker: {ticker}
Quarter: Q{quarter} {year}
Call Date: {call_date}
</transcript_metadata>

<participants>
{participants_formatted}
</participants>

<transcript>
{transcript_text}
</transcript>

Extract 8-15 quotable insights from this earnings call transcript. Focus on intelligence relevant to:

**INDUSTRY VERTICALS:**
- Aerospace (commercial & defense): Boeing, Airbus, Spirit AeroSystems, widebody/narrowbody programs
- Wind Energy: Vestas, Siemens Gamesa, TPI Composites, blade manufacturing
- Automotive: Lightweighting, EV platforms, structural composites
- Marine: Hull construction, deck systems, corrosion resistance
- Infrastructure: Bridge decks, rebar replacement, repair systems
- Industrial: Pressure vessels, tanks, pipes, tooling

**HIGH-VALUE QUOTE CATEGORIES:**
1. **COMPETITIVE INTELLIGENCE** (HIGHEST VALUE)
   - Direct mentions of competitors (Hexcel, Toray, Solvay, Owens Corning, Huntsman, Teijin, SGL Carbon, Gurit)
   - Market share commentary, competitive dynamics, pricing vs competitors

2. **PRODUCTION RATES & CAPACITY**
   - Aircraft build rates (B737, B787, A320, A350, etc.)
   - Wind turbine installation rates, blade production
   - Facility expansions, capacity investments

3. **RAW MATERIALS & SUPPLY CHAIN**
   - Carbon fiber, glass fiber, resin pricing and availability
   - PAN precursor, epoxy systems, prepreg
   - Supply chain disruptions or improvements

4. **PRICING & MARGINS**
   - Price increase announcements
   - Cost inflation vs. price realization
   - Long-term agreement (LTA) renewals

5. **STRATEGIC INITIATIVES**
   - M&A activity, acquisitions, divestitures
   - New product launches, qualification programs
   - Geographic expansion, new customer wins

6. **MARKET CONDITIONS**
   - Aerospace aftermarket/MRO demand
   - Wind energy policy and demand outlook
   - Construction/infrastructure spending
   - Defense budget trends

7. **ANALYST PRESSURE POINTS** (Q&A section gold)
   - What are analysts worried about?
   - Hedged responses to tough questions
   - Guidance qualifications and caveats

**CRITICAL INSTRUCTIONS:**
- Extract EXACT quotes when possible (use quotation marks)
- Flag HEDGED responses in Q&A - these signal potential concerns
- Note the SPEAKER ROLE (CEO/CFO quotes are most quotable)
- Score relevance to composites/advanced materials industry (0.0-1.0)
- Mark as quotable if it's impactful for competitive intelligence briefings

Return a JSON array with quotes containing:
- quote_text: The key statement (1-3 sentences, exact if possible)
- context_summary: Brief 1-sentence context for what topic was being discussed
- speaker_name: Full name of the speaker
- speaker_role: "ceo", "cfo", "coo", "cto", "evp", "vp", "president", "analyst", "other_exec", or "unknown"
- speaker_title: Full title if known (e.g., "Chief Executive Officer")
- speaker_company: Company they represent
- speaker_firm: For analysts, their bank/firm name
- quote_type: "guidance", "strategy", "competitive", "market_commentary", "segment_insight", "channel_insight", "pricing", "innovation", "risk_factor", "regional", "analyst_pressure", "raw_materials", "acquisition", "capacity", or "supply_chain"
- section: "prepared_remarks" or "qa"
- themes: Array of 1-3 themes from: carbon_fiber, glass_fiber, resins_epoxy, thermoplastic_composites, prepreg, advanced_materials, aerospace_commercial, aerospace_defense, wind_energy, automotive, marine, infrastructure, sporting_goods, industrial, hexcel, toray, solvay, owens_corning, huntsman, teijin, gurit, sgl_carbon, competitive_landscape, boeing, airbus, spirit_aerosystems, ge_aerospace, vestas, siemens_gamesa, tpi_composites, raw_material_costs, supply_chain, pricing_strategy, ma_activity, margin_improvement, capacity_expansion, production_rates, trade_policy, economic_conditions, regulatory_environment, sustainability, interest_rates, energy_transition, widebody_programs, narrowbody_programs, defense_programs
- sentiment: "bullish", "bearish", "cautious", or "neutral"
- confidence_level: "definitive", "cautious", "speculative", or "hedged"
- companies_mentioned: Array of company names mentioned
- brands_mentioned: Array of brand/product names mentioned
- metrics_mentioned: Array of specific metrics/numbers quoted
- relevance_score: 0.0-1.0 relevance to composites/advanced materials industry
- is_quotable: true/false (good for executive briefings?)
- quotability_reason: Brief explanation
- business_segment: Which segment this relates to, or null if general"""


class EarningsQuoteExtractor:
    """
    LLM-based quote extraction from earnings call transcripts.

    Uses Claude Haiku via resilient LLM wrapper for cost-efficient extraction
    with composites/materials industry-specific themes and classification.

    Target cost: ~$0.02-0.05 per transcript (using Haiku)
    """

    def __init__(
        self,
        model: str = "claude-haiku-4-5",
        max_tokens: int = 16000,
        temperature: float = 0.2,
        max_transcript_chars: int = 100000,
    ):
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.max_transcript_chars = max_transcript_chars

    async def extract_quotes(
        self,
        transcript_data: Dict[str, Any],
    ) -> EarningsQuoteExtractionResult:
        """
        Extract key quotes from an earnings transcript.

        Args:
            transcript_data: Dict with keys:
                - id or transcript_id
                - ticker, company_name, year, quarter
                - transcript_date or date or call_date
                - transcript or content or full_text (the full text)
                - participants (optional list of dicts)

        Returns:
            EarningsQuoteExtractionResult with extracted quotes
        """
        start_time = time.time()

        # Normalize field names (support both article-style and direct transcript dicts)
        transcript_id = (
            transcript_data.get("id")
            or transcript_data.get("transcript_id")
            or transcript_data.get("article_id")
            or "unknown"
        )
        ticker = transcript_data.get("ticker", "UNK")
        company_name = transcript_data.get("company_name", "Unknown Company")
        year = transcript_data.get("year", datetime.now().year)
        quarter = transcript_data.get("quarter", 1)
        call_date = (
            transcript_data.get("transcript_date")
            or transcript_data.get("date")
            or transcript_data.get("call_date")
            or "Unknown"
        )
        # Support multiple field names for transcript text
        transcript_text = (
            transcript_data.get("transcript")
            or transcript_data.get("content")
            or transcript_data.get("full_text")
            or ""
        )

        # Initialize result
        result = EarningsQuoteExtractionResult(
            transcript_id=str(transcript_id),
            ticker=ticker,
            company_name=company_name,
            year=year,
            quarter=quarter,
            transcript_length=len(transcript_text),
            extraction_model=self.model,
            success=False,
        )

        # Validate input
        if not transcript_text or len(transcript_text.strip()) < 1000:
            result.error_message = f"Transcript too short for extraction ({len(transcript_text)} chars, need 1000+)"
            logger.warning(f"[EARNINGS-EXTRACT] {ticker} Q{quarter} {year}: {result.error_message}")
            return result

        try:
            # Format participants (if available)
            participants = transcript_data.get("participants", [])
            if isinstance(participants, str):
                try:
                    participants = json.loads(participants)
                except (json.JSONDecodeError, TypeError):
                    participants = []
            participants_formatted = self._format_participants(participants)

            # Truncate transcript if needed
            transcript_text = self._truncate_transcript(transcript_text)

            # Build prompt
            date_str = call_date
            if isinstance(call_date, datetime):
                date_str = call_date.isoformat()
            elif hasattr(call_date, 'isoformat'):
                date_str = call_date.isoformat()

            prompt = QUOTE_EXTRACTION_PROMPT.format(
                company_name=company_name,
                ticker=ticker,
                quarter=quarter,
                year=year,
                call_date=date_str,
                participants_formatted=participants_formatted,
                transcript_text=transcript_text,
            )

            # Call LLM with resilient client
            logger.info(f"[EARNINGS-EXTRACT] Extracting quotes from {ticker} Q{quarter} {year} ({len(transcript_text):,} chars)")

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
                timeout=240.0,
            )

            # Parse response
            raw_text = response.content[0].text
            raw_quotes = self._parse_response(raw_text)

            # Convert to ExtractedEarningsQuote objects
            quotes = []
            for i, q in enumerate(raw_quotes):
                try:
                    quote = self._create_quote(
                        q,
                        transcript_id=str(transcript_id),
                        ticker=ticker,
                        company_name=company_name,
                        year=year,
                        quarter=quarter,
                        call_date=date_str,
                        position=i + 1,
                    )
                    quotes.append(quote)
                except Exception as e:
                    logger.warning(f"[EARNINGS-EXTRACT] Failed to parse quote {i+1}: {e}")
                    continue

            result.quotes = quotes
            result.success = True
            result.compute_statistics()

            elapsed = time.time() - start_time
            result.extraction_time_seconds = elapsed

            logger.info(
                f"[EARNINGS-EXTRACT] Extracted {len(quotes)} quotes from {ticker} Q{quarter} {year} "
                f"({result.quotable_count} quotable) in {elapsed:.1f}s"
            )

        except asyncio.TimeoutError:
            elapsed = time.time() - start_time
            result.error_message = f"LLM call timed out after {elapsed:.1f}s"
            result.extraction_time_seconds = elapsed
            logger.error(f"[EARNINGS-EXTRACT] TIMEOUT for {ticker} Q{quarter} {year}: exceeded 240s")

        except Exception as e:
            elapsed = time.time() - start_time
            result.error_message = str(e)
            result.extraction_time_seconds = elapsed
            logger.error(f"[EARNINGS-EXTRACT] Extraction FAILED for {ticker} Q{quarter} {year}: {e}", exc_info=True)

        return result

    def _format_participants(self, participants: List[Dict]) -> str:
        """Format participants list for prompt."""
        if not participants:
            return "Participants not specified in transcript metadata."

        lines = []
        for p in participants:
            if isinstance(p, str):
                lines.append(f"- {p}")
                continue
            name = p.get("name", "Unknown")
            title = p.get("title", "") or p.get("role", "")
            company = p.get("company", "")

            parts = [name]
            if title:
                parts.append(f": {title}")
            if company:
                parts.append(f", {company}")
            lines.append("- " + "".join(parts))

        return "\n".join(lines)

    def _truncate_transcript(self, text: str) -> str:
        """Truncate transcript if too long, keeping beginning and end (preserves Q&A)."""
        if len(text) <= self.max_transcript_chars:
            return text

        # Keep first 60% and last 40% to preserve Q&A section
        first_part = int(self.max_transcript_chars * 0.6)
        last_part = self.max_transcript_chars - first_part

        logger.info(f"[EARNINGS-EXTRACT] Truncating transcript from {len(text):,} to {self.max_transcript_chars:,} chars")

        return (
            text[:first_part]
            + "\n\n[... transcript truncated for length ...]\n\n"
            + text[-last_part:]
        )

    def _parse_response(self, response_text: str) -> List[Dict]:
        """Parse LLM response into quote dicts."""
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
            # Try to extract JSON array
            match = re.search(r'\[[\s\S]*\]', text)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass            
            # Handle truncated JSON (model hit max_tokens before closing the array)
            # Find the last complete JSON object and close the array
            if text.startswith('['):
                # Find last complete object by looking for last },
                last_complete = text.rfind('},')
                if last_complete == -1:
                    last_complete = text.rfind('}')
                if last_complete > 0:
                    truncated = text[:last_complete + 1] + ']'
                    try:
                        result = json.loads(truncated)
                        logger.warning(f"[EARNINGS-EXTRACT] Recovered {len(result)} quotes from truncated JSON response")
                        return result
                    except json.JSONDecodeError:
                        pass
                        raise ValueError(f"Could not parse quotes from response: {text[:500]}")

    def _create_quote(
        self,
        raw: Dict[str, Any],
        transcript_id: str,
        ticker: str,
        company_name: str,
        year: int,
        quarter: int,
        call_date: str,
        position: int,
    ) -> ExtractedEarningsQuote:
        """Convert raw LLM dict to ExtractedEarningsQuote."""

        # Parse speaker role
        role_str = raw.get("speaker_role", "unknown").lower()
        try:
            speaker_role = SpeakerRole(role_str)
        except ValueError:
            speaker_role = SpeakerRole.UNKNOWN

        # Parse quote type
        type_str = raw.get("quote_type", "market_commentary").lower()
        try:
            quote_type = QuoteType(type_str)
        except ValueError:
            quote_type = QuoteType.MARKET_COMMENTARY

        # Parse confidence level
        conf_str = raw.get("confidence_level", "cautious").lower()
        try:
            confidence_level = ConfidenceLevel(conf_str)
        except ValueError:
            confidence_level = ConfidenceLevel.CAUTIOUS

        # Parse section
        section_str = raw.get("section", "unknown").lower()
        try:
            section = CallSection(section_str)
        except ValueError:
            section = CallSection.UNKNOWN

        # Parse themes
        themes = []
        for theme_str in raw.get("themes", []):
            try:
                themes.append(EarningsQuoteTheme(theme_str.lower()))
            except ValueError:
                continue  # Skip invalid themes

        return ExtractedEarningsQuote(
            transcript_id=transcript_id,
            quote_text=raw.get("quote_text", ""),
            context_summary=raw.get("context_summary"),
            speaker_name=raw.get("speaker_name", "Unknown"),
            speaker_role=speaker_role,
            speaker_title=raw.get("speaker_title"),
            speaker_company=raw.get("speaker_company"),
            speaker_firm=raw.get("speaker_firm"),
            quote_type=quote_type,
            themes=themes,
            sentiment=raw.get("sentiment", "neutral"),
            confidence_level=confidence_level,
            companies_mentioned=raw.get("companies_mentioned", []),
            brands_mentioned=raw.get("brands_mentioned", []),
            metrics_mentioned=raw.get("metrics_mentioned", []),
            relevance_score=float(raw.get("relevance_score", 0.5)),
            is_quotable=bool(raw.get("is_quotable", False)),
            quotability_reason=raw.get("quotability_reason"),
            business_segment=raw.get("business_segment"),
            ticker=ticker,
            company_name=company_name,
            year=year,
            quarter=quarter,
            call_date=call_date if isinstance(call_date, str) else str(call_date),
            section=section,
            position_in_section=position,
            extraction_model=self.model,
            extraction_confidence=float(raw.get("extraction_confidence", 0.8)),
        )
