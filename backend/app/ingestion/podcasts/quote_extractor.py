"""
Quote Extractor
===============

LLM-based extraction of key practitioner insights from podcast transcripts.
Uses Claude Sonnet with chunked extraction for comprehensive coverage.

Adapted for C1 Intelligence Hub (composites industry focus).

Features:
- Chunked processing for long podcasts (60-90+ min)
- Overlap windows to catch quotes at chunk boundaries
- Deduplication via sequence matching
- Speaker healing: maps generic labels to real names
"""

import json
import time
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any, List
from difflib import SequenceMatcher

from app.utils.logger import get_logger
from app.utils.resilient_llm import create_resilient_llm_with_gemini_fallback
from app.config.settings import settings
from .models import PodcastQuoteRecord, QuoteTheme, SpeakerRole

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# C1 Composites Industry extraction prompt
# ---------------------------------------------------------------------------

EXTRACTION_PROMPT = """You are an intelligence analyst extracting quotable insights from composites, chemicals, and materials industry podcast transcripts.

Your job is to identify 10-20 key quotes that would be valuable for a composites materials distributor making strategic decisions about fiber reinforcements, resin systems, manufacturing processes, and end-market demand.

## What Makes a Good Quote

INCLUDE:
- Specific, actionable insights (not generic commentary)
- First-hand observations from practitioners ("We're seeing...", "Our data shows...")
- Contrarian or surprising perspectives
- Quantifiable trends ("Carbon fiber demand up 15%", "Styrene prices softened 8% this quarter")
- Strategic signals about supply chain, pricing, or market direction
- Raw material pricing dynamics and feedstock economics
- Regulatory changes (EPA styrene, TSCA, VOC regulations, ACMA advocacy)
- End market demand signals (wind energy, aerospace, automotive, infrastructure)
- Competitive intelligence (Hexcel, Toray, Owens Corning, Ashland, AOC, Hexion moves)
- Technology and manufacturing process breakthroughs
- Sustainability initiatives (recycling, bio-based resins, thermoplastic composites)

EXCLUDE:
- Generic statements ("The market is competitive")
- Promotional content about the speaker's company
- Introductions and small talk
- Repeated points (pick the best articulation)

## Theme Taxonomy

Use these themes for classification:

**Materials & Processes:**
- fiber_materials: Carbon fiber, glass fiber, aramid (Hexcel, Toray, Owens Corning)
- resin_systems: Epoxy, vinyl ester, polyester, polyurethane (Ashland, AOC, Hexion, Polynt)
- manufacturing_processes: Pultrusion, infusion, filament winding, RTM, compression molding

**End Markets:**
- wind_energy: Blade manufacturing, turbine OEM production, offshore wind
- aerospace_composites: Aircraft structures, defense applications, certification
- automotive_composites: Lightweighting, EV battery enclosures, SMC/BMC
- infrastructure: FRP rebar, bridge decks, utility poles, pipes
- marine_composites: Boat building, hull construction

**Strategic Topics:**
- sustainability: Recycling, bio-based resins, thermoplastic composites, end-of-life
- regulatory: EPA styrene limits, TSCA, VOC regulations, ACMA advocacy
- supply_chain: Raw material availability, logistics, capacity constraints
- market_dynamics: M&A, capacity expansion, market share shifts
- innovation: New chemistries, additive manufacturing, automation, digital twins
- workforce: Skilled labor shortage, training, IACMI programs
- pricing: Feedstock economics, petrochemical costs, price increases
- competitive: Competitor moves, customer wins/losses

## Output Format

Return a JSON array of quotes. Each quote must have:
- quote_text: The exact words (1-3 sentences, punchy and quotable)
- speaker_name: Who said it (use provided speaker info if available)
- speaker_role: "host" or "guest"
- themes: Array of 1-3 theme codes from the taxonomy above
- relevance_score: 0.0-1.0 (how actionable/insightful for composites industry executives)
- context_summary: One sentence on what prompted this insight

Example:
```json
[
  {{
    "quote_text": "We're seeing a fundamental shift in wind blade manufacturing - the move to thermoplastic resins could reduce cycle times by 40% and finally solve the end-of-life recycling problem.",
    "speaker_name": "Jane Smith",
    "speaker_role": "guest",
    "themes": ["wind_energy", "sustainability", "resin_systems"],
    "relevance_score": 0.92,
    "context_summary": "Discussion about next-generation wind blade materials"
  }}
]
```

## Diarization & Attribution

The transcript includes speaker labels (e.g., "Speaker 1:", "Speaker 2:").
Map these labels to the specific names provided in the Speaker Context.
- Look for where speakers introduce themselves or each other.
- If you can't determine the name, use "Guest" or "Host" but try your best.

## Transcript

{transcript_text}

## Speaker Context

{speaker_info}

Return ONLY the JSON array, no other text."""


class QuoteExtractor:
    """
    LLM-based quote extraction using chunked processing.

    Uses the project's resilient LLM wrapper (Claude + OpenAI fallback).
    """

    DEFAULT_CHUNK_SIZE = 30000
    DEFAULT_CHUNK_OVERLAP = 3000
    SIMILARITY_THRESHOLD = 0.85

    def __init__(
        self,
        model: str = "claude-sonnet-4-5",
        max_tokens: int = 4000,
        temperature: float = 0.3,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    ):
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self._llm = None

    def _get_llm(self):
        """Lazy-initialize LLM with resilient wrapper."""
        if self._llm is None:
            self._llm = create_resilient_llm_with_gemini_fallback(
                primary_model=self.model,
                anthropic_api_key=settings.anthropic_api_key,
                gemini_api_key=settings.gemini_api_key,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
        return self._llm

    def _create_chunks(self, text: str) -> List[str]:
        if len(text) <= self.chunk_size:
            return [text]

        chunks = []
        start = 0
        while start < len(text):
            end = start + self.chunk_size
            if end >= len(text):
                chunks.append(text[start:])
                break

            # Find a good break point
            break_point = text.rfind("\n\n", start + self.chunk_size - 1000, end)
            if break_point == -1:
                break_point = text.rfind(". ", start + self.chunk_size - 500, end)
                if break_point != -1:
                    break_point += 1
            if break_point == -1 or break_point <= start:
                break_point = end

            chunks.append(text[start:break_point])
            start = break_point - self.chunk_overlap
            if start < 0:
                start = 0

        return chunks

    def _deduplicate_quotes(self, quotes: List[PodcastQuoteRecord]) -> List[PodcastQuoteRecord]:
        if len(quotes) <= 1:
            return quotes

        unique = []
        for quote in quotes:
            is_dup = False
            for i, existing in enumerate(unique):
                similarity = SequenceMatcher(
                    None, quote.quote_text.lower(), existing.quote_text.lower()
                ).ratio()
                if similarity >= self.SIMILARITY_THRESHOLD:
                    is_dup = True
                    if quote.relevance_score > existing.relevance_score:
                        unique[i] = quote
                    break
            if not is_dup:
                unique.append(quote)
        return unique

    async def extract_quotes(
        self,
        transcript_text: str,
        episode_id: str,
        podcast_name: str,
        episode_title: str,
        published_date: datetime,
        episode_url: Optional[str] = None,
        speaker_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Extract quotes from a transcript using chunked processing.

        Returns:
            Dict with keys: quotes (List[PodcastQuoteRecord]), success, error_message,
            extraction_duration_seconds, cost_usd
        """
        start_time = time.time()

        result = {
            "quotes": [],
            "success": False,
            "error_message": None,
            "extraction_duration_seconds": 0.0,
            "cost_usd": 0.0,
        }

        if not transcript_text or len(transcript_text.strip()) < 500:
            result["error_message"] = "Transcript too short for extraction"
            logger.warning(f"[QUOTE_EXTRACT] Transcript too short ({len(transcript_text.strip())} chars)")
            return result

        chunks = self._create_chunks(transcript_text)
        logger.info(
            f"[QUOTE_EXTRACT] Processing {len(chunks)} chunk(s) for {episode_title[:40]}..."
        )

        speaker_context = self._build_speaker_context(speaker_info)
        speaker_context = f"Episode Title: {episode_title}\n{speaker_context}"

        all_quotes: List[PodcastQuoteRecord] = []

        try:
            llm = self._get_llm()

            for i, chunk in enumerate(chunks):
                chunk_quotes = await self._extract_from_chunk(
                    llm=llm,
                    chunk_text=chunk,
                    chunk_index=i,
                    total_chunks=len(chunks),
                    speaker_context=speaker_context,
                    episode_id=episode_id,
                    podcast_name=podcast_name,
                    episode_title=episode_title,
                    episode_url=episode_url,
                    published_date=published_date,
                    speaker_info=speaker_info,
                )
                if chunk_quotes:
                    all_quotes.extend(chunk_quotes)

            deduped = self._deduplicate_quotes(all_quotes)
            deduped.sort(key=lambda q: q.relevance_score, reverse=True)

            result["quotes"] = deduped
            result["success"] = True
            result["extraction_duration_seconds"] = time.time() - start_time

            logger.info(
                f"[QUOTE_EXTRACT] {podcast_name} - {episode_title[:40]}... "
                f"quotes={len(deduped)} (deduped from {len(all_quotes)}), "
                f"duration={result['extraction_duration_seconds']:.1f}s"
            )

        except Exception as e:
            result["error_message"] = str(e)
            result["extraction_duration_seconds"] = time.time() - start_time
            logger.error(
                f"[QUOTE_EXTRACT] Failed: {type(e).__name__} - {e}",
                exc_info=True,
            )

        return result

    async def _extract_from_chunk(
        self,
        llm,
        chunk_text: str,
        chunk_index: int,
        total_chunks: int,
        speaker_context: str,
        episode_id: str,
        podcast_name: str,
        episode_title: str,
        episode_url: Optional[str],
        published_date: datetime,
        speaker_info: Optional[Dict[str, Any]],
    ) -> Optional[List[PodcastQuoteRecord]]:
        """Extract quotes from a single chunk."""
        if total_chunks > 1:
            chunk_note = (
                f"\n\n[NOTE: This is segment {chunk_index + 1} of {total_chunks} "
                f"from a longer episode. Extract the best quotes from THIS segment.]\n\n"
            )
            prompt = EXTRACTION_PROMPT.format(
                transcript_text=chunk_note + chunk_text,
                speaker_info=speaker_context,
            )
        else:
            prompt = EXTRACTION_PROMPT.format(
                transcript_text=chunk_text,
                speaker_info=speaker_context,
            )

        try:
            # LLM timeout protection per CLAUDE.md rules
            response = await asyncio.wait_for(
                llm.ainvoke(prompt),
                timeout=120.0,
            )

            response_text = response.content if hasattr(response, 'content') else str(response)
            return self._parse_quotes_response(
                response_text=response_text,
                episode_id=episode_id,
                podcast_name=podcast_name,
                episode_title=episode_title,
                episode_url=episode_url,
                published_date=published_date,
                speaker_info=speaker_info,
            )

        except asyncio.TimeoutError:
            logger.error(f"[QUOTE_EXTRACT] LLM timeout on chunk {chunk_index + 1}")
            return None
        except Exception as e:
            logger.warning(f"[QUOTE_EXTRACT] Chunk {chunk_index + 1} failed: {e}")
            return None

    def _build_speaker_context(self, speaker_info: Optional[Dict[str, Any]]) -> str:
        if not speaker_info:
            return "No speaker information available."

        parts = []
        if speaker_info.get("hosts"):
            hosts = speaker_info["hosts"]
            if isinstance(hosts, list):
                parts.append(f"Hosts: {', '.join(hosts)}")
            else:
                parts.append(f"Host: {hosts}")

        if speaker_info.get("guest_name"):
            guest_parts = [f"Guest: {speaker_info['guest_name']}"]
            if speaker_info.get("guest_title"):
                guest_parts.append(f"Title: {speaker_info['guest_title']}")
            if speaker_info.get("guest_company"):
                guest_parts.append(f"Company: {speaker_info['guest_company']}")
            parts.append(", ".join(guest_parts))

        return "\n".join(parts) if parts else "No speaker information available."

    def _parse_quotes_response(
        self,
        response_text: str,
        episode_id: str,
        podcast_name: str,
        episode_title: str,
        episode_url: Optional[str],
        published_date: datetime,
        speaker_info: Optional[Dict[str, Any]],
    ) -> List[PodcastQuoteRecord]:
        import re
        quotes = []

        try:
            text = response_text.strip()
            if "```" in text:
                match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
                if match:
                    text = match.group(1).strip()

            start_idx = text.find('[')
            end_idx = text.rfind(']')
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                text = text[start_idx:end_idx + 1]

            raw_quotes = json.loads(text)
            if not isinstance(raw_quotes, list):
                raw_quotes = [raw_quotes]

            for raw in raw_quotes:
                try:
                    quote = self._parse_single_quote(
                        raw, episode_id, podcast_name, episode_title,
                        episode_url, published_date, speaker_info,
                    )
                    if quote:
                        quotes.append(quote)
                except Exception as e:
                    logger.warning(f"[QUOTE_EXTRACT] Failed to parse quote: {e}")

        except json.JSONDecodeError as e:
            logger.error(f"[QUOTE_EXTRACT] JSON parse error: {e}")

        return quotes

    def _parse_single_quote(
        self,
        raw: Dict[str, Any],
        episode_id: str,
        podcast_name: str,
        episode_title: str,
        episode_url: Optional[str],
        published_date: datetime,
        speaker_info: Optional[Dict[str, Any]],
    ) -> Optional[PodcastQuoteRecord]:
        quote_text = raw.get("quote_text", "").strip()
        if not quote_text:
            return None

        speaker_name = raw.get("speaker_name", "Unknown").strip()
        speaker_role_str = raw.get("speaker_role", "unknown").lower()
        try:
            speaker_role = SpeakerRole(speaker_role_str)
        except ValueError:
            speaker_role = SpeakerRole.UNKNOWN

        # Speaker healing
        if speaker_info:
            guest_name = speaker_info.get("guest_name")
            hosts = speaker_info.get("hosts", [])
            if isinstance(hosts, str):
                hosts = [hosts]

            if speaker_role == SpeakerRole.GUEST:
                if guest_name and (
                    speaker_name.lower() in ["guest", "speaker", "unknown", ""]
                    or "speaker" in speaker_name.lower()
                ):
                    speaker_name = guest_name

            elif speaker_role == SpeakerRole.HOST:
                if hosts and (
                    speaker_name.lower() in ["host", "speaker", "unknown", ""]
                    or "speaker" in speaker_name.lower()
                ):
                    speaker_name = hosts[0]

        # Speaker metadata
        speaker_title = None
        speaker_company = None
        if speaker_role == SpeakerRole.GUEST and speaker_info:
            speaker_title = speaker_info.get("guest_title")
            speaker_company = speaker_info.get("guest_company")

        # Themes
        raw_themes = raw.get("themes", [])
        if isinstance(raw_themes, str):
            raw_themes = [raw_themes]
        themes = []
        for t in raw_themes:
            try:
                QuoteTheme(t.lower())
                themes.append(t.lower())
            except ValueError:
                logger.debug(f"[QUOTE_EXTRACT] Unknown theme: {t}")

        # Relevance
        relevance = raw.get("relevance_score", 0.5)
        if isinstance(relevance, str):
            try:
                relevance = float(relevance)
            except ValueError:
                relevance = 0.5
        relevance = max(0.0, min(1.0, relevance))

        return PodcastQuoteRecord(
            episode_id=episode_id,
            podcast_name=podcast_name,
            episode_title=episode_title,
            episode_url=episode_url,
            published_at=published_date,
            quote_text=quote_text,
            context_summary=raw.get("context_summary"),
            speaker_name=speaker_name,
            speaker_role=speaker_role.value,
            speaker_title=speaker_title,
            speaker_company=speaker_company,
            themes=themes,
            relevance_score=relevance,
            extraction_model=self.model,
        )
