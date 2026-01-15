"""
Content Classifier
==================

Claude-based content classification for categorizing and prioritizing articles.
"""

import re
import json
import asyncio
from typing import List, Tuple

from app.utils.resilient_llm import get_resilient_async_client

from app.models.corpus import (
    RawArticle,
    ClassificationResult,
    ContentCategory,
    Priority,
    Industry,
)
from app.ingestion.config import (
    IngestionConfig,
    CATEGORY_KEYWORDS,
    INDUSTRY_KEYWORDS,
    DEFAULT_COMPETITORS,
    DEFAULT_OEMS,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ContentClassifier:
    """
    Uses Claude to classify and score content.
    
    Determines:
    - Category (competitor news, market trend, regulatory, etc.)
    - Industries (aerospace, automotive, etc.)
    - Priority (high, medium, low)
    - Relevance score (0-1)
    - Summary
    - Key entities mentioned
    
    Usage:
        classifier = ContentClassifier(config)
        result = await classifier.classify(article)
    """
    
    CLASSIFICATION_PROMPT = """You are a content classifier for a composites industry intelligence system serving Composites One, North America's largest composites distributor.

Your job is to classify articles based on their relevance to the COMPOSITES SUPPLY CHAIN - not general manufacturing or industrial news.

## CLASSIFICATION REFERENCE

Use this reference to identify composites-relevant content and distinguish supply chain players from end customers:

**SUPPLIERS & COMPETITORS (tag as "competitor" or "supply_chain"):**
These are material suppliers, manufacturers, distributors, and fabricators IN the composites industry:
- Raw Material Mfrs: Owens Corning, BASF, DuPont, 3M, Huntsman, Hexion, Ashland, Evonik, Sika, Mitsubishi Chemical, Polynt-Reichhold
- Intermediate Mfrs: Hexcel, Toray, SGL Carbon, Gurit, Teijin, Solvay, Vectorply, Axiom Materials
- Distributors: Composites One, North American Composites, Revchem
- Processors/Fabricators: Spirit AeroSystems, TPI Composites, Strongwell, Markforged, 9T Labs, Arris Composites

**OEMs / END CUSTOMERS (tag as "market"):**
These are companies that BUY composites - they are customers, not competitors:
- Aerospace: Boeing, Airbus, Embraer, Lockheed Martin, Northrop Grumman, GE Aerospace, Safran, Leonardo, Bombardier, Embraer, Gulfstream, Textron Aviation (Cessna, Beechcraft), Joby Aviation (eVTOL), Archer Aviation
- Wind: Vestas, Siemens Gamesa, GE Vernova, Nordex, Goldwind, Envision Energy, Enercon, Mingyang Smart Energy, SGRE (Siemens Gamesa Renewable Energy), TPI Composites (blade manufacturer), LM Wind Power (blade manufacturer, owned by GE)
- Construction: Skanska, Turner Construction, Bechtel, Kiewit, AECOM, Jacobs Engineering, Fluor Corporation, PCL Construction, Mortenson, Hensel Phelps, Strongwell (composite building products), Bedford Reinforced Plastics
- Marine: Brunswick, Beneteau, Groupe Beneteau, Malibu Boats, MasterCraft, Correct Craft, Azimut-Benetti, Ferretti Group, Grady-White, Regulator Marine, Fountain Powerboats, Wellcraft, Chaparral Boats, Cobalt Boats are also end customers in marine sector.
- Automotive: Toyota, BMW, Ford, GM, Tesla, Rivian
- Infrastructure: Caterpillar, John Deere, CNH Industrial, Komatsu, Volvo Construction Equipment, Vulcan Materials, Martin Marietta, CRH plc, Summit Materials, U.S. Concrete, Granite Construction, Quanta Services, MasTec, Primoris Services, Infrastructure & Energy Alternatives (IEA), Hughes Brothers (composite rebar), Composite Advantage
- Transportation: Wabtec, Alstom, Siemens Mobility, CRRC, Stadler Rail, Bombardier Transportation (now Alstom), PACCAR (Kenworth, Peterbilt), Daimler Truck, Volvo Trucks, Navistar, Freightliner, New Flyer, Proterra, BYD, Gillig, Nova Bus
- Defense/Space: Raytheon, Northrop Grumman, Lockheed Martin, Boeing Defense, SpaceX, Blue Origin, Sierra Nevada Corporation, Aerojet Rocketdyne, L3Harris Technologies, General Dynamics, BAE Systems, Thales Group

**MATERIALS TO RECOGNIZE:**
- Resins: polyester, vinyl ester, epoxy, phenolic, polyurethane
- Fibers: glass fiber (E-glass, S-glass), carbon fiber, aramid (Kevlar), basalt, natural fibers
- Intermediates: prepreg, SMC, BMC, woven fabrics, multiaxial, unidirectional tape, chopped strand mat
- Cores: honeycomb (Nomex, aluminum), PVC foam (Divinycell), PET foam, balsa, SAN foam
- Thermoplastics: PEEK, PEKK, PPS, nylon/polyamide
- Finished: CFRP, GFRP, FRP

**PROCESSES TO RECOGNIZE:**
RTM, VARTM, vacuum infusion, compression molding, autoclave curing, hand layup, spray-up, pultrusion, filament winding, AFP, ATL, composite 3D printing

**INDUSTRIES:**
Aerospace, Defense, Space, Marine, Wind Energy, Automotive, Construction, Infrastructure, Sports/Recreation, Industrial, Medical, Electronics, Oil & Gas

## CLASSIFICATION RULES

1. **HIGH relevance (0.8-1.0):** Article is primarily about composites materials, suppliers, processes, or C1's markets
2. **MEDIUM relevance (0.5-0.8):** Article mentions composites as part of a broader story (e.g., "Boeing 787 uses carbon fiber composites")
3. **LOW relevance (0.2-0.5):** Tangential mention or adjacent industry
4. **REJECT (<0.2):** No meaningful connection to composites

**IMPORTANT:** An article about Boeing's financial results is LOW relevance UNLESS it specifically discusses composites usage, supply chain, or material sourcing.

Analyze the following article and provide classification in JSON format.

<article>
Title: {title}
Source: {source}
Content: {content}
</article>

<tracked_competitors>
{competitors}
</tracked_competitors>

<tracked_oems>
{oems}
</tracked_oems>

Classify this article and respond with ONLY valid JSON (no markdown, no explanation):

{{
    "primary_category": "competitor|market|regulatory|product|earnings|partnership|expansion|supply_chain|c1_mention|general",
    "secondary_categories": ["category1", "category2"],
    "industries": ["aerospace", "wind", "construction", "marine", "automotive", "infrastructure", "transportation", "sporting_goods", "defense_space"],
    "priority": "high|medium|low",
    "is_hero": true|false,
    "relevance_score": 0.0-1.0,
    "summary": "2-3 sentence summary focusing on implications for composites industry",
    "companies": ["Company1", "Company2"],
    "materials": ["carbon fiber", "epoxy resin"],
    "key_entities": ["Company1", "Company2", "Product1"],
    "sentiment": "positive|negative|neutral",
    "confidence": 0.0-1.0
}}

ENTITY EXTRACTION GUIDELINES:
- companies: Extract specific company names mentioned (e.g., "Hexcel", "Boeing", "Toray", "Spirit AeroSystems")
- materials: Extract specific composite materials mentioned (e.g., "carbon fiber", "fiberglass", "epoxy", "PEEK", "prepreg", "SMC", "vinyl ester")
- industries: Select from ONLY these values: aerospace, wind, construction, marine, automotive, infrastructure, transportation, sporting_goods, defense_space

Priority Guidelines:
- HIGH: Direct competitor announcements (M&A, earnings, new products, capacity expansion), significant supply chain disruptions, major market shifts or forecasts, regulatory changes with direct impact, key OEM program updates (e.g. Boeing/Airbus production rates), strategic partnerships, or ANY C1 mentions.
- MEDIUM: General industry trends, minor expansions, technology updates without immediate commercial impact, routine announcements.
- LOW: Tangentially related news, general market updates, financial news without specific composites angle.

TIE-BREAKER: If undecided between Medium and High, choose HIGH if the article contains specific quantitative data, mentions a Tier 1 competitor, or involves a key OEM program.

Hero Guidelines (is_hero field):
Set is_hero=true ONLY for articles that should appear in the "Breaking News" section of the dashboard. These must be:
- HIGH or CRITICAL priority AND one of:
  - M&A announcements (acquisitions, mergers, divestitures)
  - Major supply chain disruptions (plant closures, material shortages)
  - Key competitor strategic announcements (new facilities, major capacity changes)
  - Significant regulatory changes with direct industry impact
  - Key OEM program updates (Boeing/Airbus production rate changes, major program wins/losses)
- Must have high confidence and clear composites relevance
- Default to false unless the article is truly "breaking news" level

Relevance Score Guidelines:
- 0.9-1.0: Directly about composites, competitors, or C1's markets
- 0.7-0.9: Strongly related to composites industry
- 0.5-0.7: Moderately related (adjacent industries, materials)
- 0.3-0.5: Weakly related
- 0.0-0.3: Minimally relevant"""

    def __init__(self, config: IngestionConfig):
        self.config = config
        self.client = get_resilient_async_client(
            anthropic_api_key=config.anthropic_api_key,
            openai_api_key=getattr(config, 'openai_api_key', None),
        )
        self.model = config.classifier_model
        self.temperature = config.classifier_temperature
        
        # Tracked entities - initialized with defaults, then loaded from BigQuery
        # via load_tracked_entities() during orchestrator initialization
        self._competitors: List[str] = DEFAULT_COMPETITORS.copy()
        self._oems: List[str] = DEFAULT_OEMS.copy()
    
    async def load_tracked_entities(self, db):
        """Load tracked entities from BigQuery companies table for classification context.
        
        This is the single source of truth for company data. The BigQuery `companies` table
        should be updated when adding/removing tracked companies.
        """
        try:
            # Load from BigQuery companies table (single source of truth)
            companies = await db.get_companies()
            
            self._competitors = [c['name'] for c in companies if c.get('type') == 'competitor']
            self._oems = [c['name'] for c in companies if c.get('type') == 'oem']
            
            logger.info(f"Loaded {len(self._competitors)} competitors, {len(self._oems)} OEMs from BigQuery")
        except Exception as e:
            logger.warning(f"Could not load tracked entities from BigQuery, using defaults: {e}")
            self._competitors = DEFAULT_COMPETITORS.copy()
            self._oems = DEFAULT_OEMS.copy()
    
    async def classify(self, article: RawArticle) -> ClassificationResult:
        """Classify a single article."""
        
        # Build content (prefer full text, fall back to summary)
        content = article.full_text or article.summary
        if len(content) > 4000:
            content = content[:4000] + "..."
        
        prompt = self.CLASSIFICATION_PROMPT.format(
            title=article.title,
            source=article.source_name,
            content=content,
            competitors=", ".join(self._competitors),
            oems=", ".join(self._oems),
        )
        
        try:
            response = await self.client.messages_create(
                model=self.model,
                max_tokens=1000,
                temperature=self.temperature,
                messages=[{"role": "user", "content": prompt}]
            )
            
            # Parse JSON response
            result_text = response.content[0].text.strip()
            
            # Clean up potential markdown code blocks
            if result_text.startswith("```"):
                result_text = re.sub(r'^```json?\n?', '', result_text)
                result_text = re.sub(r'\n?```$', '', result_text)
            
            data = json.loads(result_text)
            
            # Map to enums with validation via name lookup (robust to casing)
            
            # Primary Category
            raw_primary = data.get("primary_category", "general")
            try:
                primary_enum = ContentCategory[raw_primary.upper()]
            except KeyError:
                logger.warning(f"Invalid primary category from LLM: {raw_primary}")
                primary_enum = ContentCategory.GENERAL

            # Secondary Categories
            secondary_enums = []
            for c in data.get("secondary_categories", []):
                try:
                    secondary_enums.append(ContentCategory[c.upper()])
                except KeyError:
                    pass
            
            # Industries
            industry_enums = []
            for i in data.get("industries", []):
                try:
                    industry_enums.append(Industry[i.upper()])
                except KeyError:
                    pass
            
            # Priority
            raw_priority = data.get("priority", "low")
            try:
                priority_enum = Priority[raw_priority.upper()]
            except KeyError:
                logger.warning(f"Invalid priority from LLM: {raw_priority}")
                priority_enum = Priority.LOW
            
            return ClassificationResult(
                categories=[primary_enum] + secondary_enums,
                primary_category=primary_enum,
                industries=industry_enums,
                priority=priority_enum,
                relevance_score=float(data.get("relevance_score", 0.5)),
                summary=data.get("summary", article.summary[:200]),
                key_entities=data.get("key_entities", []),
                companies=data.get("companies", []),
                materials=data.get("materials", []),
                sentiment=data.get("sentiment", "neutral"),
                confidence=float(data.get("confidence", 0.7)),
                is_hero=bool(data.get("is_hero", False)),
            )
        
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse classification JSON: {e}")
            return self._fallback_classification(article)
        except Exception as e:
            logger.warning(f"Classification error: {e}")
            return self._fallback_classification(article)
    
    async def classify_batch(
        self,
        articles: List[RawArticle],
        max_concurrent: int = None,
    ) -> List[Tuple[RawArticle, ClassificationResult]]:
        """Classify multiple articles with rate limiting."""
        max_concurrent = max_concurrent or self.config.classifier_max_concurrent
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def classify_one(article: RawArticle) -> Tuple[RawArticle, ClassificationResult]:
            async with semaphore:
                result = await self.classify(article)
                # Small delay to avoid rate limits
                await asyncio.sleep(0.3)
                return (article, result)
        
        tasks = [classify_one(article) for article in articles]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out errors
        valid_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Batch classification error: {result}")
                # Use fallback for failed articles
                fallback = self._fallback_classification(articles[i])
                valid_results.append((articles[i], fallback))
            else:
                valid_results.append(result)
        
        logger.info(f"Classified {len(valid_results)} articles")
        return valid_results
    
    def _fallback_classification(self, article: RawArticle) -> ClassificationResult:
        """Use keyword matching when Claude classification fails."""
        text = f"{article.title} {article.summary}".lower()
        
        # Find matching categories
        categories = []
        for cat, keywords in CATEGORY_KEYWORDS.items():
            if any(kw.lower() in text for kw in keywords):
                try:
                    categories.append(ContentCategory[cat.upper()])
                except KeyError:
                    logger.warning(f"Unknown category in keywords: {cat}")
        
        # Find matching industries
        industries = []
        for ind, keywords in INDUSTRY_KEYWORDS.items():
            if any(kw.lower() in text for kw in keywords):
                try:
                    industries.append(Industry[ind.upper()])
                except KeyError:
                    logger.warning(f"Unknown industry in keywords: {ind}")
        
        # Determine priority based on category
        priority = Priority.LOW
        if categories:
            if any(c in [ContentCategory.COMPETITOR, ContentCategory.REGULATORY, ContentCategory.C1_MENTION] for c in categories):
                priority = Priority.MEDIUM
        
        primary = categories[0] if categories else ContentCategory.GENERAL
        
        # Calculate basic relevance
        relevance = 0.3
        if categories:
            relevance = 0.5
        if any(comp.lower() in text for comp in self._competitors):
            relevance = 0.7
        
        return ClassificationResult(
            categories=categories or [ContentCategory.GENERAL],
            primary_category=primary,
            industries=industries,
            priority=priority,
            relevance_score=relevance,
            summary=article.summary[:300] if article.summary else article.title,
            key_entities=[],
            sentiment="neutral",
            confidence=0.3,  # Low confidence for fallback
        )
