"""
Document Chunking Utilities
===========================

Smart chunking strategies for different document types to optimize
semantic search. Production uses Vertex AI text-embedding-004 (768 dims),
local development falls back to all-MiniLM-L6-v2 (384 dims).

Chunks long documents (like earnings transcripts) intelligently to
stay within embedding model context limits.
"""

import re
from typing import List, Dict, Any, Optional, Tuple, Callable
from dataclasses import dataclass

from app.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class DocumentChunk:
    """A single chunk from a larger document."""
    chunk_id: str
    parent_id: str  # Original document ID
    text: str
    metadata: Dict[str, Any]
    chunk_index: int
    total_chunks: int


def chunk_earnings_transcript(
    transcript_id: str,
    ticker: str,
    company_name: str,
    quarter: int,
    year: int,
    transcript_split: List[Dict[str, Any]],
    full_text: str,
    base_metadata: Dict[str, Any],
    max_chunk_chars: int = 1500,  # legacy fallback
    max_chunk_tokens: Optional[int] = 350,  # prefer token-based budget
    overlap_turns: int = 1,  # one-turn overlap across chunk boundaries
) -> List[DocumentChunk]:
    """
    Chunk an earnings transcript by speaker turns.
    
    Strategy:
    - Group consecutive speaker turns into chunks
    - Keep Q&A pairs together when possible
    - Add context (speaker, role, company) to each chunk
    - Preserve dialogue flow
    
    Args:
        transcript_id: Unique ID for the transcript
        ticker: Stock ticker
        company_name: Company name
        quarter: Earnings quarter
        year: Earnings year
        transcript_split: List of speaker sections from API
        full_text: Full transcript text (fallback)
        base_metadata: Base metadata to include in each chunk
        max_chunk_chars: Maximum characters per chunk
    
    Returns:
        List of DocumentChunk objects
    """
    chunks = []
    
    # If we have structured speaker data, use it
    if transcript_split:
        chunks = _chunk_by_speaker_turns(
            transcript_id=transcript_id,
            ticker=ticker,
            company_name=company_name,
            quarter=quarter,
            year=year,
            sections=transcript_split,
            base_metadata=base_metadata,
            max_chunk_chars=max_chunk_chars,
            max_chunk_tokens=max_chunk_tokens,
            overlap_turns=overlap_turns,
        )
    else:
        # Fallback: chunk the raw text
        chunks = _chunk_raw_text(
            doc_id=transcript_id,
            text=full_text,
            base_metadata=base_metadata,
            max_chunk_chars=max_chunk_chars,
            max_chunk_tokens=max_chunk_tokens,
            context_prefix=f"{company_name} ({ticker}) Q{quarter} {year} Earnings Call: ",
        )
    
    logger.info(f"Chunked {ticker} Q{quarter} {year} earnings into {len(chunks)} chunks")
    return chunks


def _chunk_by_speaker_turns(
    transcript_id: str,
    ticker: str,
    company_name: str,
    quarter: int,
    year: int,
    sections: List[Dict[str, Any]],
    base_metadata: Dict[str, Any],
    max_chunk_chars: int = 1500,
    max_chunk_tokens: Optional[int] = 350,
    overlap_turns: int = 1,
) -> List[DocumentChunk]:
    """
    Group speaker turns into semantic chunks.

    Improvements:
    - Role-aware grouping to keep Q&A pairs intact where possible
    - Token-based budget (fallback to char-based if tokenizer unavailable)
    - One-turn overlap across chunk boundaries
    - Ordered speaker list preserved in metadata
    """
    tokenizer = _get_tokenizer()
    token_len = (lambda s: _count_tokens(s, tokenizer)) if max_chunk_tokens else (lambda s: len(s))

    chunks: List[DocumentChunk] = []
    current_chunk_text: List[str] = []
    current_chunk_speakers: List[str] = []
    current_tokens = 0
    current_chars = 0
    chunk_index = 0
    
    context_header = f"{company_name} ({ticker}) Q{quarter} {year} Earnings Call\n\n"
    
    def classify_role(role: str, speaker: str) -> str:
        r = (role or "").lower()
        s = (speaker or "").lower()
        if "operator" in r or "operator" in s:
            return "operator"
        if "analyst" in r or "analyst" in s:
            return "analyst"
        exec_markers = ["ceo", "cfo", "coo", "cto", "cio", "president", "chair", "chairman", "svp", "vp", "ir", "investor relations", "founder", "co-founder"]
        if any(m in r for m in exec_markers) or any(m in s for m in exec_markers):
            return "executive"
        return "unknown"

    last_turn_text: Optional[str] = None  # for overlap
    last_turn_role: Optional[str] = None
    last_was_analyst = False

    for i, section in enumerate(sections):
        speaker = section.get("speaker", "Unknown")
        role = section.get("role", "")
        text = section.get("text", "").strip()
        
        if not text:
            continue
        
        # Format this turn with speaker attribution
        role_str = f" ({role})" if role else ""
        turn_text = f"{speaker}{role_str}: {text}"
        turn_tokens = token_len(turn_text)
        turn_chars = len(turn_text)
        role_class = classify_role(role, speaker)
        
        # If last turn was analyst and the current chunk is nearly full, start a new chunk
        # so we can keep the Q together with at least one A
        if last_was_analyst and current_chunk_text:
            budget = max_chunk_tokens if max_chunk_tokens else max_chunk_chars
            will_exceed = (current_tokens + turn_tokens > (max_chunk_tokens or 10**9)) if max_chunk_tokens else (current_chars + turn_chars > max_chunk_chars)
            if will_exceed:
                # finalize current chunk
                chunk_text = context_header + "\n\n".join(current_chunk_text)
                chunk_metadata = {
                    **base_metadata,
                    "speakers": _dedupe_preserve_order(current_chunk_speakers),
                    "chunk_type": "earnings_dialogue",
                    "ticker": ticker,
                    "quarter": quarter,
                    "year": year,
                }
                chunks.append(DocumentChunk(
                    chunk_id=f"{transcript_id}_chunk_{chunk_index}",
                    parent_id=transcript_id,
                    text=chunk_text,
                    metadata=chunk_metadata,
                    chunk_index=chunk_index,
                    total_chunks=0,
                ))

                # Prepare next chunk with overlap of last turn (one-turn overlap)
                overlap_start: List[str] = []
                if overlap_turns and last_turn_text:
                    overlap_start.append(last_turn_text)
                current_chunk_text = overlap_start[:]
                current_chunk_speakers = [current_chunk_speakers[-1]] if overlap_start else []
                current_tokens = token_len("\n\n".join(current_chunk_text)) if current_chunk_text else 0
                current_chars = len("\n\n".join(current_chunk_text)) if current_chunk_text else 0
                chunk_index += 1
        
        # Add turn to current chunk
        # If adding would overflow, finalize and start new chunk (with overlap)
        would_exceed_tokens = (current_tokens + turn_tokens > (max_chunk_tokens or 10**9)) if max_chunk_tokens else False
        would_exceed_chars = (current_chars + turn_chars > max_chunk_chars) if not max_chunk_tokens else False
        if (would_exceed_tokens or would_exceed_chars) and current_chunk_text:
            # finalize current
            chunk_text = context_header + "\n\n".join(current_chunk_text)
            chunk_metadata = {
                **base_metadata,
                "speakers": _dedupe_preserve_order(current_chunk_speakers),
                "chunk_type": "earnings_dialogue",
                "ticker": ticker,
                "quarter": quarter,
                "year": year,
            }
            chunks.append(DocumentChunk(
                chunk_id=f"{transcript_id}_chunk_{chunk_index}",
                parent_id=transcript_id,
                text=chunk_text,
                metadata=chunk_metadata,
                chunk_index=chunk_index,
                total_chunks=0,
            ))

            # next chunk starts with overlap of last turn
            overlap_start = []
            if overlap_turns and last_turn_text:
                overlap_start.append(last_turn_text)
            current_chunk_text = overlap_start[:]
            current_chunk_speakers = [current_chunk_speakers[-1]] if overlap_start else []
            current_tokens = token_len("\n\n".join(current_chunk_text)) if current_chunk_text else 0
            current_chars = len("\n\n".join(current_chunk_text)) if current_chunk_text else 0
            chunk_index += 1

        current_chunk_text.append(turn_text)
        current_chunk_speakers.append(speaker)
        current_tokens += turn_tokens + token_len("\n\n")
        current_chars += turn_chars + 2
        last_turn_text = turn_text
        last_turn_role = role_class
        last_was_analyst = (role_class == "analyst")
    
    # Don't forget the last chunk
    if current_chunk_text:
        chunk_text = context_header + "\n\n".join(current_chunk_text)
        chunk_metadata = {
            **base_metadata,
            "speakers": _dedupe_preserve_order(current_chunk_speakers),
            "chunk_type": "earnings_dialogue",
            "ticker": ticker,
            "quarter": quarter,
            "year": year,
        }

        chunks.append(DocumentChunk(
            chunk_id=f"{transcript_id}_chunk_{chunk_index}",
            parent_id=transcript_id,
            text=chunk_text,
            metadata=chunk_metadata,
            chunk_index=chunk_index,
            total_chunks=0,
        ))
    
    # Update total_chunks count
    total = len(chunks)
    for idx, chunk in enumerate(chunks):
        chunk.total_chunks = total
        # Link prev/next chunk ids in metadata for retrieval-time expansion
        prev_id = chunks[idx - 1].chunk_id if idx > 0 else None
        next_id = chunks[idx + 1].chunk_id if idx < total - 1 else None
        chunk.metadata["prev_chunk_id"] = prev_id
        chunk.metadata["next_chunk_id"] = next_id
    
    return chunks


def _chunk_raw_text(
    doc_id: str,
    text: str,
    base_metadata: Dict[str, Any],
    max_chunk_chars: int = 1500,
    max_chunk_tokens: Optional[int] = 350,
    context_prefix: str = "",
    overlap_chars: int = 200,
) -> List[DocumentChunk]:
    """
    Simple text chunking with overlap.
    
    Used as fallback when structured data isn't available.
    Tries to break at sentence boundaries.
    """
    if not text:
        return []
    
    tokenizer = _get_tokenizer()
    token_len = (lambda s: _count_tokens(s, tokenizer)) if max_chunk_tokens else (lambda s: len(s))
    budget = max_chunk_tokens or max_chunk_chars
    chunks: List[DocumentChunk] = []
    chunk_index = 0
    
    # Split into sentences (rough)
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    current_chunk: List[str] = []
    current_tokens = 0 if max_chunk_tokens else None
    current_chars = 0 if not max_chunk_tokens else None
    
    for sentence in sentences:
        sent_tokens = token_len(sentence)
        sent_chars = len(sentence)

        would_exceed = False
        if max_chunk_tokens:
            would_exceed = (current_tokens + sent_tokens > budget) if current_chunk else (sent_tokens > budget)
        else:
            would_exceed = (current_chars + sent_chars > budget) if current_chunk else (sent_chars > budget)

        if would_exceed and current_chunk:
            # Save current chunk
            chunk_text = context_prefix + " ".join(current_chunk)
            chunks.append(DocumentChunk(
                chunk_id=f"{doc_id}_chunk_{chunk_index}",
                parent_id=doc_id,
                text=chunk_text,
                metadata={**base_metadata, "chunk_type": "text"},
                chunk_index=chunk_index,
                total_chunks=0,
            ))

            # Overlap by characters: include tail of previous chunk until overlap_chars
            if overlap_chars > 0 and current_chunk:
                tail = []
                acc = 0
                # walk from end backwards until we reach overlap_chars
                for s in reversed(current_chunk):
                    acc += len(s) + 1
                    tail.append(s)
                    if acc >= overlap_chars:
                        break
                tail.reverse()
                current_chunk = tail
            else:
                current_chunk = []

            # reset counters
            if max_chunk_tokens:
                current_tokens = token_len(" ".join(current_chunk)) if current_chunk else 0
            else:
                current_chars = len(" ".join(current_chunk)) if current_chunk else 0
            chunk_index += 1

        current_chunk.append(sentence)
        if max_chunk_tokens:
            current_tokens = (current_tokens or 0) + sent_tokens + 1
        else:
            current_chars = (current_chars or 0) + sent_chars + 1
    
    # Last chunk
    if current_chunk:
        chunk_text = context_prefix + " ".join(current_chunk)
        chunks.append(DocumentChunk(
            chunk_id=f"{doc_id}_chunk_{chunk_index}",
            parent_id=doc_id,
            text=chunk_text,
            metadata={**base_metadata, "chunk_type": "text"},
            chunk_index=chunk_index,
            total_chunks=0,
        ))
    
    # Update totals
    total = len(chunks)
    for idx, chunk in enumerate(chunks):
        chunk.total_chunks = total
        prev_id = chunks[idx - 1].chunk_id if idx > 0 else None
        next_id = chunks[idx + 1].chunk_id if idx < total - 1 else None
        chunk.metadata["prev_chunk_id"] = prev_id
        chunk.metadata["next_chunk_id"] = next_id
    
    return chunks


def chunk_sec_filing(
    filing_id: str,
    ticker: str,
    company_name: str,
    filing_type: str,
    sections: Dict[str, str],
    base_metadata: Dict[str, Any],
    max_chunk_chars: int = 1500,
    max_chunk_tokens: Optional[int] = 350,
) -> List[DocumentChunk]:
    """
    Chunk SEC filing by section, then by paragraphs within sections.
    
    SEC filings are already structured by section (1, 1A, 7, etc.)
    which makes chunking more straightforward.
    
    Args:
        filing_id: Unique ID for the filing
        ticker: Stock ticker
        company_name: Company name
        filing_type: e.g., "10-K", "10-Q", "8-K"
        sections: Dict mapping section ID to content
        base_metadata: Base metadata to include in each chunk
        max_chunk_chars: Maximum characters per chunk
    
    Returns:
        List of DocumentChunk objects
    """
    tokenizer = _get_tokenizer()
    token_len = (lambda s: _count_tokens(s, tokenizer)) if max_chunk_tokens else (lambda s: len(s))
    chunks: List[DocumentChunk] = []
    chunk_index = 0
    
    SEC_SECTION_NAMES = {
        "1": "Business",
        "1A": "Risk Factors", 
        "7": "MD&A (Management Discussion & Analysis)",
        "7A": "Quantitative and Qualitative Disclosures About Market Risk",
        "8": "Financial Statements",
    }
    
    # Iterate sections in a stable, sorted order (1, 1A, 7, 7A, 8, ...)
    def _sec_sort_key(sec_id: str) -> Tuple[int, str]:
        # split numeric prefix and suffix like '1A'
        m = re.match(r"(\d+)([A-Za-z]?)", str(sec_id))
        if m:
            return (int(m.group(1)), m.group(2).upper())
        return (999, str(sec_id))

    for section_id in sorted(sections.keys(), key=_sec_sort_key):
        content = sections.get(section_id)
        if not content:
            continue
        
        section_name = SEC_SECTION_NAMES.get(section_id, f"Section {section_id}")
        context_prefix = f"{company_name} ({ticker}) {filing_type} - {section_name}\n\n"
        
        # Split into sub-sections by headings to preserve topical cohesion
        subsections = _split_by_subsections(content)

        section_chunks: List[DocumentChunk] = []
        for sub_idx, sub in enumerate(subsections):
            sub_title = sub.get("title")
            sub_prefix = context_prefix + (f"{sub_title}\n\n" if sub_title else "")
            sub_chunks = _chunk_raw_text(
                doc_id=f"{filing_id}_sec{section_id}_sub{sub_idx}",
                text=sub.get("text", ""),
                base_metadata={
                    **base_metadata,
                    "section_id": section_id,
                    "section_name": section_name,
                    "subsection_title": sub_title or "",
                    "filing_type": filing_type,
                    "ticker": ticker,
                    "chunk_type": "sec_filing",
                },
                max_chunk_chars=max_chunk_chars,
                max_chunk_tokens=max_chunk_tokens,
                context_prefix=sub_prefix,
                overlap_chars=200,
            )
            section_chunks.extend(sub_chunks)
        
        # Re-index to global chunk numbering
        for chunk in section_chunks:
            chunk.chunk_id = f"{filing_id}_chunk_{chunk_index}"
            chunk.parent_id = filing_id
            chunk.chunk_index = chunk_index
            chunk_index += 1
        
        chunks.extend(section_chunks)
    
    # Update totals
    total = len(chunks)
    for idx, chunk in enumerate(chunks):
        chunk.total_chunks = total
        prev_id = chunks[idx - 1].chunk_id if idx > 0 else None
        next_id = chunks[idx + 1].chunk_id if idx < total - 1 else None
        chunk.metadata["prev_chunk_id"] = prev_id
        chunk.metadata["next_chunk_id"] = next_id
    
    logger.info(f"Chunked {ticker} {filing_type} into {len(chunks)} chunks")
    return chunks


# -----------------------------
# Helpers: tokenization & utils
# -----------------------------

def _get_tokenizer():
    """Return a tiktoken encoding if available, else None."""
    try:
        import tiktoken  # type: ignore
        return tiktoken.get_encoding("cl100k_base")
    except Exception:
        return None


def _count_tokens(text: str, tokenizer) -> int:
    """Count tokens using tiktoken if available, else simple heuristic."""
    if tokenizer:
        try:
            return len(tokenizer.encode(text))
        except Exception:
            pass
    # Heuristic: ~4 chars per token
    return max(1, len(text) // 4)


def _dedupe_preserve_order(items: List[str]) -> List[str]:
    """Remove duplicates while preserving original order."""
    seen = set()
    out: List[str] = []
    for x in items:
        if x not in seen:
            out.append(x)
            seen.add(x)
    return out


def _split_by_subsections(text: str) -> List[Dict[str, str]]:
    """
    Split SEC section text into subsections by detecting headings.
    Heuristics: a heading is a short line (< 120 chars) that is either
    ALL CAPS or Title Case and not ending with a period.
    Returns list of {title, text} blocks.
    """
    if not text:
        return []

    lines = text.splitlines()
    blocks: List[Dict[str, str]] = []
    current_title: Optional[str] = None
    current_buf: List[str] = []

    def is_heading(line: str) -> bool:
        l = line.strip()
        if not l:
            return False
        if len(l) > 120:
            return False
        if l.endswith('.'):
            return False
        # ALL CAPS or Title Case (most words capitalized)
        if l.isupper():
            return True
        words = l.split()
        if len(words) <= 12 and sum(w[:1].isupper() for w in words) >= max(3, int(0.7 * len(words))):
            return True
        # Matches "Item 7", "Item 7A" style
        if re.match(r"^Item\s+\d+[A-Za-z]?(\.|:)?$", l, re.IGNORECASE):
            return True
        return False

    for line in lines:
        if is_heading(line):
            # flush previous
            if current_buf:
                blocks.append({"title": current_title or "", "text": "\n".join(current_buf).strip()})
                current_buf = []
            current_title = line.strip()
        else:
            current_buf.append(line)

    if current_buf:
        blocks.append({"title": current_title or "", "text": "\n".join(current_buf).strip()})

    # If we didn't detect any headings, return the whole text as one subsection
    if not blocks:
        return [{"title": "", "text": text}]

    # Clean empty blocks
    return [b for b in blocks if b.get("text")]
