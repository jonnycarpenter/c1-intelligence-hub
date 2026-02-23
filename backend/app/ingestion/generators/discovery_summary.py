"""
Discovery Summary Generator - Thematic analysis for category accordion drawers.

Generates AI-powered thematic summaries for the Discovery tab's category accordions.
When a user clicks "AI Summary" on a category, this generator analyzes the articles
and surfaces:
- 2 Key Themes (strategic groupings of related items)
- One-off Summary (count and description of remaining ungrouped items)
"""

import json
import time
import asyncio
from typing import List, Dict, Any
from datetime import datetime

from app.utils.logger import get_logger
from app.config.settings import settings

logger = get_logger(__name__)


class DiscoverySummaryGenerator:
    """
    Generates thematic summaries for Discovery category accordion drawers.
    Matches the "Key Theme 1/2" and "One-off stories" structure.
    """
    
    PROMPT = """You are a senior analyst prepping a category-specific thematic breakdown for an executive intelligence hub.

CATEGORY: {category}
PERIOD: Last 30 days
ARTICLE COUNT: {article_count}

ARTICLES:
{articles_text}

YOUR TASK:
1. Identify the 2 most significant "Key Themes" in this category from the last 30 days. Each theme should group related articles.
2. Summarize the remaining articles as "one-off stories" by grouping their topics (e.g., "8 one-off stories about product launches and pricing").

RESPONSE FORMAT (JSON ONLY):
{{
    "themes": [
        {{
            "title": "Clear Descriptive Theme Title",
            "content": "1-2 sentence analytical summary of this theme."
        }},
        {{
            "title": "Clear Descriptive Theme Title",
            "content": "1-2 sentence analytical summary of this theme."
        }}
    ],
    "one_off_summary": "X one-off stories about [topic A], [topic B], and [topic C]"
}}

RULES:
- Be punchy, analytical, and direct. Skip the fluff.
- If there aren't enough articles for 2 distinct themes, provide 1 theme and adjust the one_off_summary.
- If the articles are fragmented, provide 0 themes and use one_off_summary to describe the activity.
- Ensure the one_off_summary includes the count of articles it covers.
"""

    def __init__(self, model: str = "claude-haiku-4-5"):
        """Initialize with model selection."""
        self.model = model
        self._client = None
    
    async def _get_client(self):
        """Lazy-load Anthropic client."""
        if self._client is None:
            from anthropic import AsyncAnthropic
            self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        return self._client

    async def generate(self, category: str, articles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate thematic summary for a category.
        
        Args:
            category: Category name (e.g., 'Competitor', 'Market')
            articles: List of article dicts with 'title', 'summary', etc.
            
        Returns:
            Dict with themes, one_off_summary, and metadata
        """
        start_time = time.time()
        logger.info(f"[DISCOVERY_SUMMARY] Generate START: category={category}, article_count={len(articles)}")
        
        if not articles:
            logger.info(f"[DISCOVERY_SUMMARY] Generate COMPLETE (empty): 0 articles")
            return {
                "category": category,
                "period_label": "Past 30 days",
                "themes": [],
                "one_off_summary": "No recent articles in this category.",
                "article_count": 0,
                "generated_at": datetime.utcnow().isoformat()
            }

        # Format articles for the prompt (title and summary)
        articles_text = ""
        for i, a in enumerate(articles[:40]):  # Analyze top 40 for context
            title = a.get('title', 'Untitled')
            summary = a.get('summary', '') or a.get('description', '') or a.get('digest_summary', '') or ''
            articles_text += f"[{i+1}] {title}\nSummary: {summary[:300]}\n\n"

        # Format category label nicely
        category_label = category.replace('_', ' ').replace('-', ' ').title()
        
        prompt = self.PROMPT.format(
            category=category_label,
            article_count=len(articles),
            articles_text=articles_text
        )

        try:
            client = await self._get_client()
            
            response = await asyncio.wait_for(
                client.messages.create(
                    model=self.model,
                    max_tokens=1000,
                    temperature=0,  # Deterministic for consistent summaries
                    messages=[{"role": "user", "content": prompt}]
                ),
                timeout=30.0
            )
            
            result_text = response.content[0].text.strip()
            
            # Extract JSON from potential markdown wrapping
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()
            
            data = json.loads(result_text)
            
            elapsed = time.time() - start_time
            logger.info(f"[DISCOVERY_SUMMARY] Generate COMPLETE: {elapsed:.2f}s, themes={len(data.get('themes', []))}")
            
            return {
                "category": category,
                "period_label": "Past 30 days",
                "themes": data.get("themes", []),
                "one_off_summary": data.get("one_off_summary", ""),
                "article_count": len(articles),
                "generated_at": datetime.utcnow().isoformat()
            }
            
        except asyncio.TimeoutError:
            elapsed = time.time() - start_time
            logger.error(f"[DISCOVERY_SUMMARY] Generate TIMEOUT: {elapsed:.2f}s, exceeded 30s")
            return self._fallback_response(category, len(articles), "Summary generation timed out.")
            
        except json.JSONDecodeError as e:
            elapsed = time.time() - start_time
            logger.error(f"[DISCOVERY_SUMMARY] Generate JSON ERROR: {elapsed:.2f}s, error={str(e)}")
            return self._fallback_response(category, len(articles), "Failed to parse AI response.")
            
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"[DISCOVERY_SUMMARY] Generate FAILED: {elapsed:.2f}s, error={str(e)}", exc_info=True)
            return self._fallback_response(category, len(articles), f"Summary generation encountered an error.")
    
    def _fallback_response(self, category: str, article_count: int, error_msg: str) -> Dict[str, Any]:
        """Return a fallback response on error."""
        return {
            "category": category,
            "period_label": "Past 30 days",
            "themes": [],
            "one_off_summary": f"{article_count} articles detected. {error_msg}",
            "article_count": article_count,
            "generated_at": datetime.utcnow().isoformat()
        }
