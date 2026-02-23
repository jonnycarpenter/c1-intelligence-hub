"""
Bulletin Board Generator
========================

Generates contextual guidance bullets for the Market Intelligence bulletin board.
Uses Haiku LLM to create brief, actionable pointers to priority content.
"""

import os
import json
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from pathlib import Path

from anthropic import Anthropic

from app.utils.logger import get_logger

logger = get_logger(__name__)

# Category display name mapping - aligned with C1's taxonomy
CATEGORY_DISPLAY_NAMES = {
    "Competitor": "Competitor Moves",
    "competitor": "Competitor Moves",
    "Market": "Market Dynamics",
    "market": "Market Dynamics",
    "Regulatory": "Regulatory",
    "regulatory": "Regulatory",
    "Product": "Product News",
    "product": "Product News",
    "Earnings": "Earnings & Financial",
    "earnings": "Earnings & Financial",
    "Partnership": "Partnerships",
    "partnership": "Partnerships",
    "Expansion": "Expansion & Investment",
    "expansion": "Expansion & Investment",
    "Supply Chain": "Supply Chain",
    "supply_chain": "Supply Chain",
    "supply-chain": "Supply Chain",
    "Logistics": "Logistics",
    "logistics": "Logistics",
    "C1 Mention": "C1 Mentions",
    "c1_mention": "C1 Mentions",
    "General": "General",
    "general": "General",
}


class BulletinBoardGenerator:
    """Generates contextual bulletin board guidance using Haiku LLM."""
    
    def __init__(self, anthropic_api_key: Optional[str] = None):
        self.api_key = anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("Anthropic API key required")
        self.client = Anthropic(api_key=self.api_key)
        self._prompt_template = self._load_prompt_template()
    
    def _load_prompt_template(self) -> str:
        """Load the bulletin board prompt template."""
        prompt_path = Path(__file__).parent.parent.parent.parent / "inputs" / "agent_prompts" / "bulletin_board_prompt.md"
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")
        # Fallback minimal prompt
        return """Generate 1-3 brief bullet points guiding users to priority content. 
Return JSON array of strings only."""
    
    async def generate_market_pulse(
        self,
        priority_items: List[Dict[str, Any]],
        hours_window: int = 72,
        extended: bool = False
    ) -> Dict[str, Any]:
        """
        Generate a single 'Market Pulse' strategic summary sentence.
        
        Args:
            priority_items: List of HIGH/CRITICAL articles
            hours_window: Time window used
            extended: Whether we extended to 7 days
            
        Returns:
            {
                "market_pulse": "Single sentence summary...",
                "total_priority_items": int,
                "categories_covered": ["Market", ...],
                "time_window_hours": int,
                "extended_to_7_days": bool,
                "generated_at": str
            }
        """
        # Group by category
        by_category: Dict[str, List[Dict]] = {}
        for item in priority_items:
            cat = item.get("category") or item.get("primary_category") or "General"
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(item)
        
        # Sort categories by count (descending), take top 3
        sorted_categories = sorted(by_category.items(), key=lambda x: len(x[1]), reverse=True)[:3]
        
        if not sorted_categories:
            return {
                "market_pulse": "No critical signals detected in the last few days.",
                "total_priority_items": 0,
                "categories_covered": [],
                "time_window_hours": hours_window,
                "extended_to_7_days": extended,
                "generated_at": datetime.utcnow().isoformat()
            }
        
        # Prepare context for LLM
        context = self._build_context(sorted_categories, hours_window, extended)
        
        # Call Haiku
        try:
            market_pulse = await self._call_haiku_pulse(context)
        except Exception as e:
            logger.error(f"Haiku pulse call failed: {e}")
            market_pulse = self._generate_fallback_pulse(sorted_categories)
        
        return {
            "market_pulse": market_pulse,
            "total_priority_items": len(priority_items),
            "categories_covered": [cat for cat, _ in sorted_categories],
            "time_window_hours": hours_window,
            "extended_to_7_days": extended,
            "generated_at": datetime.utcnow().isoformat()
        }
    
    def _build_context(
        self,
        sorted_categories: List[tuple],
        hours_window: int,
        extended: bool
    ) -> str:
        """Build context string for LLM."""
        now = datetime.utcnow()
        lines = []
        
        time_label = "7 days" if extended else "72 hours"
        lines.append(f"Priority items from the last {time_label}:\n")
        
        for category, items in sorted_categories:
            display_name = CATEGORY_DISPLAY_NAMES.get(category, category.replace("_", " ").title())
            lines.append(f"\n## {display_name} ({len(items)} items)")
            
            # Add up to 5 sample titles with recency
            for item in items[:5]:
                title = item.get("title", "Untitled")[:80]
                lines.append(f"  - {title}")
        
        return "\n".join(lines)
    
    async def _call_haiku_pulse(self, context: str) -> str:
        """Call Claude Haiku to generate a single pulse sentence."""
        system_prompt = """You are a senior market intelligence analyst.
Analyze the provided high-priority items and generate ONE single, powerful sentence that summarizes the current market state.
Focus on the "So What?" - connect the dots between categories if possible.
Style: Professional, concise, executive-level. No "Here is a summary". Just the insight.
Max 20 words."""

        # Synchronous call (Anthropic SDK)
        response = self.client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=100,
            system=system_prompt,
            messages=[
                {"role": "user", "content": context}
            ]
        )
        
        return response.content[0].text.strip()
    
    def _generate_fallback_pulse(self, sorted_categories: List[tuple]) -> str:
        """Generate templated pulse sentence without LLM."""
        top_cat = CATEGORY_DISPLAY_NAMES.get(sorted_categories[0][0], sorted_categories[0][0])
        count = len(sorted_categories[0][1])
        return f"High volume of activity detected in {top_cat} with {count} critical items."
