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
    "Regulatory": "Health & Regulatory",
    "regulatory": "Health & Regulatory",
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
    
    async def generate(
        self,
        priority_items: List[Dict[str, Any]],
        hours_window: int = 72,
        extended: bool = False
    ) -> Dict[str, Any]:
        """
        Generate bulletin board content.
        
        Args:
            priority_items: List of HIGH/CRITICAL articles with category, title, published_at
            hours_window: Time window used (72 or 168)
            extended: Whether we extended from 72h to 7 days due to no items
            
        Returns:
            {
                "bullets": ["bullet 1", "bullet 2", ...],
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
            # No priority items
            return {
                "bullets": ["All clear – no urgent items in the last few days. Explore the themes below."],
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
            bullets = await self._call_haiku(context)
        except Exception as e:
            logger.error(f"Haiku call failed: {e}")
            # Fallback to templated bullets
            bullets = self._generate_fallback_bullets(sorted_categories)
        
        return {
            "bullets": bullets,
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
                pub_at = item.get("published_at")
                recency = ""
                if pub_at:
                    try:
                        if isinstance(pub_at, str):
                            pub_dt = datetime.fromisoformat(pub_at.replace("Z", "+00:00"))
                        else:
                            pub_dt = pub_at
                        hours_ago = (now - pub_dt.replace(tzinfo=None)).total_seconds() / 3600
                        if hours_ago < 1:
                            recency = " (just now)"
                        elif hours_ago < 6:
                            recency = f" ({int(hours_ago)}h ago)"
                        elif hours_ago < 24:
                            recency = " (today)"
                        elif hours_ago < 48:
                            recency = " (yesterday)"
                    except:
                        pass
                lines.append(f"  - {title}{recency}")
        
        return "\n".join(lines)
    
    async def _call_haiku(self, context: str) -> List[str]:
        """Call Claude Haiku to generate bullets."""
        # Synchronous call (Anthropic SDK)
        response = self.client.messages.create(
            model="claude-3-5-haiku-latest",
            max_tokens=300,
            system=self._prompt_template,
            messages=[
                {"role": "user", "content": context}
            ]
        )
        
        # Parse response
        content = response.content[0].text.strip()
        
        # Extract JSON array
        if content.startswith("["):
            try:
                bullets = json.loads(content)
                if isinstance(bullets, list) and all(isinstance(b, str) for b in bullets):
                    return bullets[:3]  # Max 3
            except json.JSONDecodeError:
                pass
        
        # Try to find JSON in response
        match = re.search(r'\[.*?\]', content, re.DOTALL)
        if match:
            try:
                bullets = json.loads(match.group())
                if isinstance(bullets, list):
                    return [str(b) for b in bullets[:3]]
            except:
                pass
        
        # Fallback: treat as single bullet
        return [content[:200]] if content else ["Check out the priority items below."]
    
    def _generate_fallback_bullets(
        self,
        sorted_categories: List[tuple]
    ) -> List[str]:
        """Generate templated bullets without LLM."""
        now = datetime.utcnow()
        bullets = []
        
        for category, items in sorted_categories[:3]:
            display_name = CATEGORY_DISPLAY_NAMES.get(category, category.replace("_", " ").title())
            count = len(items)
            
            # Find most recent item
            recency = ""
            if items:
                most_recent = items[0]
                pub_at = most_recent.get("published_at")
                if pub_at:
                    try:
                        if isinstance(pub_at, str):
                            pub_dt = datetime.fromisoformat(pub_at.replace("Z", "+00:00"))
                        else:
                            pub_dt = pub_at
                        hours_ago = (now - pub_dt.replace(tzinfo=None)).total_seconds() / 3600
                        if hours_ago < 3:
                            recency = f", latest just {int(hours_ago)} hours ago"
                        elif hours_ago < 24:
                            recency = ", latest today"
                    except:
                        pass
            
            bullet = f"Check out {display_name} – {count} priority item{'s' if count != 1 else ''}{recency}."
            bullets.append(bullet)
        
        return bullets
