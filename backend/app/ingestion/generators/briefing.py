import uuid
import json
import logging
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from collections import Counter
from anthropic import AsyncAnthropic

from app.models.corpus import ContentCategory, Priority
from app.db.database import get_db
from app.config.settings import settings

logger = logging.getLogger(__name__)


class BriefingGenerator:
    """
    Generates "Need to Know" executive briefings for the Pulse tab.
    
    Features:
    - 30-day rolling window briefings
    - Full source citation tracking for transparency
    - Entity extraction for quarterly trending analysis
    - BigQuery storage (production)
    - Scheduler metadata for 8 AM / 8 PM refresh tracking
    """
    
    NEED_TO_KNOW_PROMPT = """You are a senior composites industry analyst preparing a "Need to Know" briefing for C1 executives.

<context>
Category: {category}
Period: Last 30 days ({period_start} to {period_end})
Total articles analyzed: {article_count}
</context>

<articles>
{articles_text}
</articles>

Generate a concise executive briefing for the "{category}" category. This should answer: "What happened in the last 30 days that a composites industry executive MUST know?"

CRITICAL CITATION REQUIREMENT:
- Every claim, statistic, or company mention MUST reference the source article by [Source: Article Title]
- Each key insight should cite at least one source article
- Include specific publication names when mentioning information

Requirements:
1. Lead with the single most important development (1-2 sentences) with [Source: Article Title] citation
2. Follow with 3-5 key insights as bullet points, each with source citations
3. Each bullet should be actionable intelligence, not generic news
4. Highlight company names, materials, and specific numbers when relevant
5. Note emerging patterns or trends across multiple articles
6. Flag anything that requires immediate attention or action

Tone: Direct, analytical, no fluff. Write for a busy executive who has 30 seconds.

Respond with JSON only:
{{
    "headline": "One sentence capturing the most critical development [Source: Article Title]",
    "summary": "A 2-3 sentence overview with citations [Source: Article Title]",
    "key_insights": [
        "Insight 1 with specific details [Source: Article Title]",
        "Insight 2 with specific details [Source: Article Title]", 
        "Insight 3 with specific details [Source: Article Title]"
    ],
    "trend_signal": "emerging|accelerating|stable|declining|mixed",
    "attention_flag": "high|medium|low",
    "attention_reason": "Why this category needs attention (or null if low)",
    "companies_mentioned": ["Company A", "Company B"],
    "materials_mentioned": ["carbon fiber", "epoxy resin"],
    "key_figures": [
        {{"figure": "$500M", "context": "Hexcel Q3 revenue", "source": "Article Title"}},
        {{"figure": "15%", "context": "aerospace growth rate", "source": "Article Title"}}
    ],
    "topics_extracted": ["capacity expansion", "supply chain resilience", "sustainability"]
}}"""

    def __init__(self, config, scheduler_run: str = None):
        """
        Initialize the BriefingGenerator.
        
        Args:
            config: Application configuration
            scheduler_run: "morning" (8 AM CST) or "evening" (8 PM CST) - for tracking
        """
        self.config = config
        self.db = get_db()
        self.client = AsyncAnthropic(api_key=config.anthropic_api_key)
        self.model = getattr(config, 'briefing_model', "claude-opus-4-5")
        self.scheduler_run = scheduler_run or self._detect_scheduler_run()
        
        # BigQuery storage for production
        self._bq_storage = None
    
    def _detect_scheduler_run(self) -> str:
        """Detect if this is morning or evening run based on current time."""
        hour = datetime.utcnow().hour
        # 8 AM CST = 14:00 UTC, 8 PM CST = 02:00 UTC
        return "morning" if 6 <= hour < 18 else "evening"
    
    async def _get_bq_storage(self):
        """Lazy-load BigQuery storage for production."""
        if self._bq_storage is None:
            try:
                from app.db.gcp_storage import BigQueryDataStorage, gcp_config
                if gcp_config.is_configured:
                    self._bq_storage = BigQueryDataStorage(gcp_config)
                    await self._bq_storage.initialize()
                    logger.info("BigQuery storage initialized for briefings")
                else:
                    logger.info("GCP not configured, skipping BigQuery storage for briefings")
            except Exception as e:
                logger.warning(f"Could not initialize BigQuery storage: {e}")
        return self._bq_storage
    
    async def generate_all_categories(self, days: int = 30) -> List[Dict[str, Any]]:
        """Generate briefings for all relevant categories."""
        categories = [
            ContentCategory.MARKET,
            ContentCategory.COMPETITOR,
            ContentCategory.PRODUCT,
            ContentCategory.REGULATORY,
            ContentCategory.SUPPLY_CHAIN,
        ]
        
        briefings = []
        for category in categories:
            briefing = await self.generate_for_category(category, days)
            if briefing:
                briefings.append(briefing)
        
        return briefings

    def _build_source_articles(self, articles) -> List[Dict[str, Any]]:
        """Build full source article metadata for citation tracking."""
        source_articles = []
        for a in articles:
            source_articles.append({
                "id": a.id,
                "title": a.title,
                "url": a.url,
                "source_name": a.source.name if hasattr(a.source, 'name') else str(a.source),
                "source_type": a.source.source_type if hasattr(a.source, 'source_type') else "",
                "published_at": a.published_at.isoformat() if a.published_at else None,
                "summary": a.summary[:500] if a.summary else "",  # Truncate for storage
                "priority": a.priority.value if hasattr(a.priority, 'value') else str(a.priority),
                "relevance_score": getattr(a, 'relevance_score', 0.5),
            })
        return source_articles
    
    def _build_sources_breakdown(self, articles) -> Dict[str, int]:
        """Build breakdown of sources by publication name."""
        sources = []
        for a in articles:
            source_name = a.source.name if hasattr(a.source, 'name') else str(a.source)
            sources.append(source_name)
        return dict(Counter(sources))
    
    def _calculate_quality_metrics(self, articles) -> Dict[str, Any]:
        """Calculate quality metrics for the briefing."""
        relevance_scores = [getattr(a, 'relevance_score', 0.5) for a in articles]
        avg_relevance = sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0.0
        
        high_priority_count = sum(
            1 for a in articles 
            if hasattr(a, 'priority') and a.priority.value in ['CRITICAL', 'HIGH']
        )
        
        return {
            "avg_article_relevance": round(avg_relevance, 3),
            "high_priority_count": high_priority_count,
        }

    async def generate_for_category(self, category: ContentCategory, days: int = 30) -> Optional[Dict[str, Any]]:
        """Generate a briefing for a specific category with full source tracking."""
        logger.info(f"Generating briefing for category: {category.value}")
        
        period_end = datetime.utcnow()
        period_start = period_end - timedelta(days=days)
        
        # Query articles for the category
        articles = await self.db.query_corpus(
            hours=days * 24,
            categories=[category],
            limit=100
        )
        
        if not articles:
            logger.info(f"No articles found for category {category.value} in the last {days} days.")
            return None
        
        # Build source article details for citations
        source_articles = self._build_source_articles(articles)
        sources_breakdown = self._build_sources_breakdown(articles)
        quality_metrics = self._calculate_quality_metrics(articles)
        
        # Include source name in article text for better citation
        articles_text = "\n\n".join([
            f"[{i+1}] Title: {a.title}\nSource: {a.source.name if hasattr(a.source, 'name') else 'Unknown'}\nDate: {a.published_at.date()}\nSummary: {a.summary}"
            for i, a in enumerate(articles)
        ])
        
        prompt = self.NEED_TO_KNOW_PROMPT.format(
            category=category.value.replace('_', ' ').title(),
            period_start=period_start.date(),
            period_end=period_end.date(),
            article_count=len(articles),
            articles_text=articles_text
        )
        
        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=1500,  # Increased for citations
                temperature=0,
                messages=[{"role": "user", "content": prompt}]
            )
            
            result_json = response.content[0].text.strip()
            # Handle potential markdown wrapping
            if result_json.startswith("```json"):
                result_json = result_json.split("```json")[1].split("```")[0].strip()
            elif result_json.startswith("```"):
                result_json = result_json.split("```")[1].split("```")[0].strip()
            
            data = json.loads(result_json)
            
            # Build comprehensive briefing record
            briefing_record = {
                "id": str(uuid.uuid4()),
                "category": category.value,
                "headline": data.get("headline", ""),
                "summary": data.get("summary", ""),
                "key_insights": data.get("key_insights", []),
                "trend_signal": data.get("trend_signal", "stable"),
                "attention_flag": data.get("attention_flag", "low"),
                "attention_reason": data.get("attention_reason"),
                "period_start": period_start,
                "period_end": period_end,
                "generated_at": datetime.utcnow(),
                "model": self.model,
                
                # Source tracking (for citations)
                "article_ids": [a.id for a in articles],
                "article_count": len(articles),
                "source_articles": source_articles,
                "sources_breakdown": sources_breakdown,
                
                # Entity extraction (for trending)
                "companies_mentioned": data.get("companies_mentioned", []),
                "materials_mentioned": data.get("materials_mentioned", []),
                "topics_extracted": data.get("topics_extracted", []),
                "key_figures": data.get("key_figures", []),
                
                # Scheduler metadata
                "scheduler_run": self.scheduler_run,
                
                # Quality metrics
                **quality_metrics,
            }
            
            # Save to BigQuery
            bq_storage = await self._get_bq_storage()
            if bq_storage:
                try:
                    await bq_storage.save_briefing(briefing_record)
                    logger.info(f"Saved briefing to BigQuery for {category.value}")
                except Exception as e:
                    logger.error(f"Failed to save briefing to BigQuery: {e}")
            else:
                logger.warning(f"BigQuery storage not available - briefing for {category.value} not saved")
            
            return briefing_record
            
        except Exception as e:
            logger.error(f"Error generating briefing for {category.value}: {e}")
            return None
