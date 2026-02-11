"""
Digest Classifier Service
=========================

LLM-powered classification of news articles for the intelligence digest.

Responsibilities:
- Categorize articles into digest categories (market, supply-chain, competitor, etc.)
- Assign priority levels based on business impact
- Extract relevant entities (companies, materials, topics, industries)
- Generate concise summaries optimized for scanning

Uses Claude for classification with structured output.
"""

import os
import json
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum

from app.utils.resilient_llm import get_resilient_async_client

from app.api.schemas import DigestCategory, Priority
from app.db.gcp_storage import ArticleRecord
from app.config.settings import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


# =============================================================================
# Classification Models
# =============================================================================

@dataclass
class ClassifiedArticle:
    """Article with LLM-generated classification."""
    # Original article data
    article_id: str
    title: str
    url: str
    published_at: datetime
    source_name: str
    source_type: str
    original_summary: str
    
    # LLM-generated fields
    category: DigestCategory
    priority: Priority
    digest_summary: str  # Optimized 2-3 sentence summary
    companies: List[str] = field(default_factory=list)
    materials: List[str] = field(default_factory=list)
    topics: List[str] = field(default_factory=list)
    industries: List[str] = field(default_factory=list)
    relevance_score: float = 0.5
    confidence: float = 0.0
    
    # Coverage/Virality tracking (from deduplication)
    coverage_count: int = 1  # How many sources covered this story
    duplicate_sources: List[str] = field(default_factory=list)  # Other sources that ran this story
    all_urls: List[str] = field(default_factory=list)  # All URLs for this story
    
    # Metadata
    classified_at: datetime = field(default_factory=datetime.utcnow)
    classifier_model: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "article_id": self.article_id,
            "title": self.title,
            "url": self.url,
            "published_at": self.published_at.isoformat(),
            "source_name": self.source_name,
            "source_type": self.source_type,
            "original_summary": self.original_summary,
            "category": self.category.value,
            "priority": self.priority.value,
            "digest_summary": self.digest_summary,
            "companies": self.companies,
            "materials": self.materials,
            "topics": self.topics,
            "industries": self.industries,
            "relevance_score": self.relevance_score,
            "confidence": self.confidence,
            "coverage_count": self.coverage_count,
            "duplicate_sources": self.duplicate_sources,
            "all_urls": self.all_urls,
            "classified_at": self.classified_at.isoformat(),
            "classifier_model": self.classifier_model,
        }


# =============================================================================
# Classification Prompts
# =============================================================================

CLASSIFICATION_SYSTEM_PROMPT = """You are an intelligence analyst for Composites One, a leading distributor of composite materials and supplies in North America.

Your job is to classify news articles for an executive intelligence digest. You need to:
1. Categorize articles into the appropriate business category
2. Assign a priority based on business impact
3. Extract relevant entities (companies, materials, topics, industries)
4. Write a concise 2-3 sentence summary optimized for quick scanning

CONTEXT ABOUT COMPOSITES ONE:
- Primary Business: Distribution of composite materials (carbon fiber, fiberglass, resins, etc.)
- Key Industries: Aerospace, Automotive, Marine, Wind Energy, Construction
- Competitors: Major distributors and material manufacturers
- Geography: North America focused, global supply chain awareness

CATEGORIES:
- market: General market trends, industry outlook, demand signals
- supply-chain: Logistics, shipping, supplier issues, raw material availability
- regulatory: Government regulations, environmental policies, trade policies
- competitor: Competitor news, M&A, capacity changes, new products
- pricing: Commodity prices, material costs, pricing announcements
- product: New materials, technology innovations, product launches
- c1_mention: Direct mentions of Composites One

PRIORITY LEVELS (based on business impact):
- critical: Immediate business impact, requires action within 24-48 hours
  Examples: Major supply disruption, critical competitor move, regulatory deadline
- high: Significant business impact, should be reviewed within the week
  Examples: Price changes affecting margins, competitor expansion, new regulations
- medium: Notable but not urgent, useful for planning
  Examples: Market trends, industry forecasts, technology developments
- low: Background information, nice to know
  Examples: General news, minor updates, distant future outlook

INDUSTRIES (use lowercase with hyphens):
- aerospace (commercial aviation, defense aircraft, space)
- automotive (cars, trucks, EVs, racing)
- wind-energy (wind turbines, blades, renewable energy)
- marine (boats, yachts, shipbuilding)
- construction (infrastructure, building materials)
- defense (military applications, armor, UAVs)
- sporting-goods (bicycles, golf, tennis, outdoor equipment)
- industrial (general manufacturing, tooling)

Respond ONLY with valid JSON in this exact format:
{
    "category": "market|supply-chain|regulatory|competitor|pricing|product|c1_mention",
    "priority": "critical|high|medium|low",
    "summary": "2-3 sentence summary optimized for quick scanning",
    "companies": ["Company1", "Company2"],
    "materials": ["Material1", "Material2"],
    "topics": ["Topic1", "Topic2", "Topic3"],
    "industries": ["aerospace", "wind-energy"],
    "relevance_score": 0.0-1.0,
    "confidence": 0.0-1.0,
    "reasoning": "Brief explanation of classification"
}"""


BATCH_CLASSIFICATION_PROMPT = """Classify the following {count} articles for the intelligence digest.

{articles}

Respond with a JSON array containing one classification object per article, in the same order.
Each object should have: category, priority, summary, companies, materials, topics, relevance_score, confidence, reasoning.
"""


# =============================================================================
# Classifier Service
# =============================================================================

class DigestClassifier:
    """
    LLM-powered classifier for digest articles.
    
    Features:
    - Single article classification
    - Batch classification (more efficient for multiple articles)
    - Retry logic with exponential backoff
    - Confidence thresholds for quality control
    """
    
    def __init__(
        self,
        model: str = "claude-sonnet-4-5",
        temperature: float = 0.1,
        max_concurrent: int = 3,
    ):
        self.model = model
        self.temperature = temperature
        self.max_concurrent = max_concurrent
        self.client = get_resilient_async_client(
            anthropic_api_key=settings.anthropic_api_key,
            gemini_api_key=settings.gemini_api_key,
        )
        self._semaphore = asyncio.Semaphore(max_concurrent)
    
    async def classify_article(
        self,
        article: ArticleRecord,
        retry_count: int = 2,
    ) -> ClassifiedArticle:
        """
        Classify a single article.
        
        Args:
            article: Raw article record to classify
            retry_count: Number of retries on failure
            
        Returns:
            ClassifiedArticle with LLM-generated classification
        """
        async with self._semaphore:
            article_text = f"""Title: {article.title}
Source: {article.source_name} ({article.source_type})
Published: {article.published_at.strftime('%Y-%m-%d %H:%M')}
Content: {article.summary or 'No summary available'}"""

            for attempt in range(retry_count + 1):
                try:
                    response = await self.client.messages_create(
                        model=self.model,
                        max_tokens=1024,
                        temperature=self.temperature,
                        system=CLASSIFICATION_SYSTEM_PROMPT,
                        messages=[
                            {"role": "user", "content": article_text}
                        ],
                    )
                    
                    result_text = response.content[0].text.strip()
                    
                    # Parse JSON response
                    result = self._parse_classification_json(result_text)
                    
                    return ClassifiedArticle(
                        article_id=article.id,
                        title=article.title,
                        url=article.url,
                        published_at=article.published_at,
                        source_name=article.source_name,
                        source_type=article.source_type,
                        original_summary=article.summary or "",
                        category=DigestCategory(result.get("category", "market")),
                        priority=Priority(result.get("priority", "medium")),
                        digest_summary=result.get("summary", article.summary or "")[:500],
                        companies=result.get("companies", [])[:10],
                        materials=result.get("materials", [])[:10],
                        topics=result.get("topics", [])[:5],
                        industries=result.get("industries", [])[:5],
                        relevance_score=float(result.get("relevance_score", 0.5)),
                        confidence=float(result.get("confidence", 0.7)),
                        classifier_model=self.model,
                    )
                    
                except Exception as e:
                    if attempt < retry_count:
                        wait_time = 2 ** attempt
                        logger.warning(f"Classification attempt {attempt + 1} failed, retrying in {wait_time}s: {e}")
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(f"Classification failed after {retry_count + 1} attempts: {e}")
                        # Return with default classification
                        return self._default_classification(article, str(e))
    
    async def classify_batch(
        self,
        articles: List[ArticleRecord],
        batch_size: int = 5,
    ) -> List[ClassifiedArticle]:
        """
        Classify multiple articles efficiently.
        
        For smaller batches, uses single-call batch classification.
        For larger batches, processes in parallel chunks.
        
        Args:
            articles: List of articles to classify
            batch_size: Max articles per batch call
            
        Returns:
            List of ClassifiedArticle objects
        """
        if not articles:
            return []
        
        results = []
        
        # Process in batches
        for i in range(0, len(articles), batch_size):
            batch = articles[i:i + batch_size]
            
            if len(batch) == 1:
                # Single article - use regular classification
                result = await self.classify_article(batch[0])
                results.append(result)
            else:
                # Multiple articles - use batch classification
                batch_results = await self._classify_batch_internal(batch)
                results.extend(batch_results)
            
            # Small delay between batches to avoid rate limits
            if i + batch_size < len(articles):
                await asyncio.sleep(0.5)
        
        return results
    
    async def _classify_batch_internal(
        self,
        articles: List[ArticleRecord],
    ) -> List[ClassifiedArticle]:
        """Internal batch classification using a single LLM call."""
        
        # Format articles for batch prompt
        articles_text = "\n\n---\n\n".join([
            f"ARTICLE {i+1}:\nTitle: {a.title}\nSource: {a.source_name}\nPublished: {a.published_at.strftime('%Y-%m-%d')}\nContent: {(a.summary or '')[:400]}"
            for i, a in enumerate(articles)
        ])
        
        prompt = BATCH_CLASSIFICATION_PROMPT.format(
            count=len(articles),
            articles=articles_text,
        )
        
        try:
            # Use messages_create wrapper (handles Anthropic SDK system param bug)
            response = await self.client.messages_create(
                model=self.model,
                max_tokens=4096,
                temperature=self.temperature,
                system=CLASSIFICATION_SYSTEM_PROMPT,
                messages=[
                    {"role": "user", "content": prompt}
                ],
            )
            
            result_text = response.content[0].text.strip()
            
            # Parse JSON array
            classifications = self._parse_batch_json(result_text)
            
            # Match classifications to articles
            results = []
            for i, article in enumerate(articles):
                if i < len(classifications):
                    c = classifications[i]
                    results.append(ClassifiedArticle(
                        article_id=article.id,
                        title=article.title,
                        url=article.url,
                        published_at=article.published_at,
                        source_name=article.source_name,
                        source_type=article.source_type,
                        original_summary=article.summary or "",
                        category=DigestCategory(c.get("category", "market")),
                        priority=Priority(c.get("priority", "medium")),
                        digest_summary=c.get("summary", article.summary or "")[:500],
                        companies=c.get("companies", [])[:10],
                        materials=c.get("materials", [])[:10],
                        topics=c.get("topics", [])[:5],
                        industries=c.get("industries", [])[:5],
                        relevance_score=float(c.get("relevance_score", 0.5)),
                        confidence=float(c.get("confidence", 0.7)),
                        classifier_model=self.model,
                    ))
                else:
                    results.append(self._default_classification(article, "Missing from batch response"))
            
            return results
            
        except Exception as e:
            logger.error(f"Batch classification failed: {e}")
            # Fall back to individual classification
            return await asyncio.gather(*[
                self.classify_article(a) for a in articles
            ])
    
    def _parse_classification_json(self, text: str) -> Dict[str, Any]:
        """Parse classification JSON from LLM response."""
        # Try to extract JSON from response
        text = text.strip()
        
        # Handle markdown code blocks
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        
        text = text.strip()
        
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Try to find JSON object in text
            import re
            json_match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except:
                    pass
            
            logger.warning(f"Failed to parse classification JSON: {text[:200]}")
            return {}
    
    def _parse_batch_json(self, text: str) -> List[Dict[str, Any]]:
        """Parse batch classification JSON array from LLM response."""
        text = text.strip()
        
        # Handle markdown code blocks
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        
        text = text.strip()
        
        try:
            result = json.loads(text)
            if isinstance(result, list):
                return result
            return [result]
        except json.JSONDecodeError:
            # Try to find JSON array in text
            import re
            json_match = re.search(r'\[[\s\S]*\]', text)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except:
                    pass
            
            logger.warning(f"Failed to parse batch JSON: {text[:200]}")
            return []
    
    def _default_classification(
        self,
        article: ArticleRecord,
        error_msg: str,
    ) -> ClassifiedArticle:
        """Create default classification for failed articles."""
        # Try to infer category from source type
        category_map = {
            "rss": DigestCategory.MARKET,
            "press_release": DigestCategory.COMPETITOR,
            "earnings_transcript": DigestCategory.COMPETITOR,
            "web_news": DigestCategory.MARKET,
            "freight_news": DigestCategory.SUPPLY_CHAIN,
        }
        
        return ClassifiedArticle(
            article_id=article.id,
            title=article.title,
            url=article.url,
            published_at=article.published_at,
            source_name=article.source_name,
            source_type=article.source_type,
            original_summary=article.summary or "",
            category=category_map.get(article.source_type, DigestCategory.MARKET),
            priority=Priority.MEDIUM,
            digest_summary=article.summary[:300] if article.summary else "Classification unavailable",
            companies=article.companies_mentioned or [],
            materials=[],
            topics=article.topics or [],
            industries=[],
            relevance_score=article.relevance_score,
            confidence=0.0,  # Zero confidence indicates fallback
            classifier_model=f"{self.model} (fallback: {error_msg[:50]})",
        )


# =============================================================================
# Singleton Instance
# =============================================================================

_classifier_instance: Optional[DigestClassifier] = None

def get_classifier() -> DigestClassifier:
    """Get or create the classifier singleton."""
    global _classifier_instance
    if _classifier_instance is None:
        _classifier_instance = DigestClassifier()
    return _classifier_instance
