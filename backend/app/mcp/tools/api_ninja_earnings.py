"""API Ninjas Earnings Transcript tool for Market Scout agent."""

from typing import Optional
import httpx
import json
from langchain_core.tools import tool

from app.config.settings import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


@tool
def get_earnings_transcript_ninja(
    ticker: str,
    year: Optional[int] = None,
    quarter: Optional[int] = None,
) -> str:
    """
    Get earnings call transcript for a specific company from API Ninjas.
    
    This provides detailed earnings call transcripts with speaker attribution,
    participant lists, and structured transcript sections.
    
    Args:
        ticker: Stock ticker symbol (e.g., "TRYIY", "MMM", "HXL")
        year: Year of the earnings call (e.g., 2024). If not provided, gets most recent.
        quarter: Quarter (1-4). If not provided, gets most recent.
    
    Returns:
        JSON string with transcript details including:
        - Full transcript text
        - Participants (executives, analysts)
        - Split transcript by speaker
        - Date and timing info
    """
    logger.info(f"Fetching earnings transcript from API Ninjas: ticker={ticker}, year={year}, quarter={quarter}")
    
    if not settings.api_ninja_key:
        return '{"error": "API Ninja key not configured"}'
    
    try:
        url = f"{settings.api_ninja_base_url}/earningstranscript"
        
        # Build params
        params = {"ticker": ticker.upper()}
        if year:
            params["year"] = year
        if quarter:
            params["quarter"] = quarter
        
        headers = {
            "X-Api-Key": settings.api_ninja_key,
        }
        
        with httpx.Client(timeout=60) as client:
            response = client.get(url, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()
        
        # Check if we got data
        if not data:
            return json.dumps({
                "error": f"No earnings transcript found for {ticker}",
                "ticker": ticker,
                "year": year,
                "quarter": quarter,
            })
        
        # Structure the response
        result = {
            "source": "API Ninjas Earnings Transcript",
            "ticker": data.get("ticker"),
            "date": data.get("date"),
            "year": data.get("year"),
            "quarter": data.get("quarter"),
            "earnings_timing": data.get("earnings_timing"),  # before_market, after_market
        }
        
        # Include participants summary (limit to key roles)
        participants = data.get("participants", [])
        if participants:
            key_participants = []
            for p in participants[:15]:  # Limit to first 15
                if isinstance(p, dict):
                    key_participants.append({
                        "name": p.get("name"),
                        "role": p.get("role"),
                        "company": p.get("company"),
                    })
            result["participants"] = key_participants
            result["total_participants"] = len(participants)
        
        # Include transcript preview (full transcript can be very long)
        transcript = data.get("transcript", "")
        if transcript:
            result["transcript_preview"] = transcript[:3000] + "..." if len(transcript) > 3000 else transcript
            result["transcript_length"] = len(transcript)
        
        # Include structured transcript sections if available
        transcript_split = data.get("transcript_split", [])
        if transcript_split:
            # Include first 15 sections for context (increased for quote extraction)
            sections = []
            for section in transcript_split[:15]:
                if isinstance(section, dict):
                    sections.append({
                        "speaker": section.get("speaker"),
                        "role": section.get("role"),
                        "company": section.get("company"),
                        "text_preview": section.get("text", "")[:1000] + "..." if len(section.get("text", "")) > 1000 else section.get("text", ""),
                    })
            result["transcript_sections"] = sections
            result["total_sections"] = len(transcript_split)
        
        return json.dumps(result, indent=2)
        
    except httpx.HTTPStatusError as e:
        logger.error(f"API Ninjas HTTP error: {e.response.status_code} - {e.response.text}")
        if e.response.status_code == 404:
            return json.dumps({
                "error": f"Earnings transcript not found for {ticker}",
                "ticker": ticker,
                "year": year,
                "quarter": quarter,
            })
        return json.dumps({"error": f"API error: {e.response.status_code}"})
    except Exception as e:
        logger.error(f"API Ninjas earnings transcript error: {e}")
        return json.dumps({"error": str(e)})


@tool
def search_earnings_keywords(
    ticker: str,
    keywords: list[str],
    year: Optional[int] = None,
    quarter: Optional[int] = None,
) -> str:
    """
    Search an earnings call transcript for specific keywords or topics.
    
    Use this to find what executives said about specific topics like:
    - Raw material costs, supply chain, pricing
    - Specific products or markets
    - Guidance, outlook, challenges
    
    Args:
        ticker: Stock ticker symbol (e.g., "MSFT", "HXL")
        keywords: List of keywords to search for (e.g., ["carbon fiber", "pricing", "demand"])
        year: Year of the earnings call (optional)
        quarter: Quarter 1-4 (optional)
    
    Returns:
        JSON with relevant excerpts containing the keywords
    """
    logger.info(f"Searching earnings transcript: ticker={ticker}, keywords={keywords}")
    
    if not settings.api_ninja_key:
        return '{"error": "API Ninja key not configured"}'
    
    try:
        url = f"{settings.api_ninja_base_url}/earningstranscript"
        params = {"ticker": ticker.upper()}
        if year:
            params["year"] = year
        if quarter:
            params["quarter"] = quarter
        
        headers = {"X-Api-Key": settings.api_ninja_key}
        
        with httpx.Client(timeout=60) as client:
            response = client.get(url, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()
        
        if not data:
            return json.dumps({
                "error": f"No earnings transcript found for {ticker}",
                "ticker": ticker,
            })
        
        # Search through transcript sections
        transcript_split = data.get("transcript_split", [])
        matches = []
        
        keywords_lower = [k.lower() for k in keywords]
        
        for section in transcript_split:
            if isinstance(section, dict):
                text = section.get("text", "").lower()
                # Check if any keyword is in this section
                found_keywords = [k for k in keywords_lower if k in text]
                if found_keywords:
                    matches.append({
                        "speaker": section.get("speaker"),
                        "role": section.get("role"),
                        "company": section.get("company"),
                        "matched_keywords": found_keywords,
                        "text": section.get("text", "")[:1000],  # Limit text length
                    })
        
        return json.dumps({
            "source": "API Ninjas Earnings Transcript Search",
            "ticker": ticker,
            "date": data.get("date"),
            "year": data.get("year"),
            "quarter": data.get("quarter"),
            "search_keywords": keywords,
            "matches_found": len(matches),
            "matches": matches[:20],  # Limit to 20 most relevant
        }, indent=2)
        
    except Exception as e:
        logger.error(f"API Ninjas earnings search error: {e}")
        return json.dumps({"error": str(e)})
