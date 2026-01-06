import json
import logging
import re
import asyncio
from typing import List, Tuple, Dict, Any, Optional
from dataclasses import dataclass

from app.utils.resilient_llm import get_resilient_async_client
from app.models.corpus import RawArticle, ClassificationResult, ContentCategory, Priority, Industry

logger = logging.getLogger(__name__)

# Keywords for classification assistance
CATEGORY_KEYWORDS = {
    ContentCategory.COMPETITOR: [
        "hexcel", "toray", "solvay", "owens corning", "huntsman", "gurit", 
        "teijin", "mitsubishi chemical", "sgf", "acquired", "acquisition",
        "market share", "competitive", "rival"
    ],
    ContentCategory.MARKET: [
        "demand", "growth", "forecast", "trend", "outlook", "market size",
        "CAGR", "billion", "million", "increase", "decrease", "surge"
    ],
    ContentCategory.REGULATORY: [
        "regulation", "EPA", "FAA", "compliance", "standard", "certification",
        "REACH", "RoHS", "environmental", "emission", "sustainability", "ban"
    ],
    ContentCategory.PRODUCT: [
        "launch", "introduce", "new product", "unveil", "debut", "release",
        "next-generation", "innovative", "breakthrough"
    ],
    ContentCategory.EARNINGS: [
        "earnings", "revenue", "profit", "quarterly", "fiscal", "guidance",
        "EPS", "margin", "financial results", "outlook"
    ],
    ContentCategory.PARTNERSHIP: [
        "partnership", "collaboration", "joint venture", "agreement", "deal",
        "alliance", "MOU", "contract", "supply agreement"
    ],
    ContentCategory.EXPANSION: [
        "expansion", "facility", "plant", "investment", "capacity", "production",
        "manufacturing", "new site", "construction", "million investment"
    ],
    ContentCategory.SUPPLY_CHAIN: [
        "supply chain", "shortage", "logistics", "raw material", "supplier",
        "inventory", "lead time", "disruption", "sourcing"
    ],
    ContentCategory.LOGISTICS: [
        "freight", "shipping", "container", "port", "trucking", "delivery",
        "ocean freight", "air freight", "trade lane", "carrier", "logistics"
    ],
}

INDUSTRY_KEYWORDS = {
    Industry.AEROSPACE: ["aerospace", "aircraft", "aviation", "boeing", "airbus", "jet", "fuselage", "wing"],
    Industry.AUTOMOTIVE: ["automotive", "vehicle", "car", "EV", "electric vehicle", "OEM", "tier 1"],
    Industry.MARINE: ["marine", "boat", "yacht", "ship", "naval", "offshore"],
    Industry.WIND_ENERGY: ["wind", "turbine", "blade", "renewable", "offshore wind", "vestas", "siemens gamesa"],
    Industry.INFRASTRUCTURE: ["infrastructure", "bridge", "construction", "civil", "rebar"],
    Industry.SPORTING_GOODS: ["sporting", "golf", "bicycle", "ski", "tennis", "recreation"],
    Industry.DEFENSE: ["defense", "military", "army", "navy", "air force", "DoD"],
}

# Source-based score boosts applied after LLM classification
# Matches against source_name (case-insensitive, partial match)
SOURCE_SCORE_BOOSTS = {
    # Tier 1: Core Composites (+0.15)
    "compositesworld.com": 0.15,
    "compositesworld": 0.15,
    "jec composites": 0.15,
    "jeccomposites.com": 0.15,
    "composites manufacturing": 0.15,
    "composites.media": 0.15,
    
    # Tier 2: Premium Business (+0.10)
    "reuters": 0.10,
    "reuters.com": 0.10,
    "wsj.com": 0.10,
    "wall street journal": 0.10,
    "barrons.com": 0.10,
    "barron's": 0.10,
    "ft.com": 0.10,
    "financial times": 0.10,
    "bloomberg.com": 0.10,
    "bloomberg": 0.10,
    "bnnbloomberg.ca": 0.10,
    
    # Tier 3: Quality Sector (+0.05)
    "aviationweek.com": 0.05,
    "aviation week": 0.05,
    "defensenews.com": 0.05,
    "defense news": 0.05,
    "freightwaves": 0.05,
    "supply chain dive": 0.05,
    "seekingalpha.com": 0.05,
    "seeking alpha": 0.05,
    "flightglobal.com": 0.05,
    "flight global": 0.05,
    "breakingdefense.com": 0.05,
    "breaking defense": 0.05,
    "spacenews.com": 0.05,
    "space news": 0.05,
    "cnbc.com": 0.05,
    "cnbc": 0.05,
    "manufacturingdive.com": 0.05,
    "manufacturing dive": 0.05,
    "plasticsnews.com": 0.05,
    "plastics news": 0.05,
    "chemengonline.com": 0.05,
}

# Sources to block entirely - articles from these sources are filtered out
# Matches against source_name or URL (case-insensitive, partial match)
BLOCKED_SOURCES = {
    # Aggregators - Repackaged/low-value content
    "sa.markets",
    "tradingview",
    "coincodex",
    "macrotrends",
    "stockanalysis",
    "gurufocus",
    "morningstar",
    "global.morningstar",
    
    # Social/Noise - Not news sources
    "wikipedia",
    "youtube",
    "linkedin",
    "reddit",
    "facebook",
    "instagram",
    "twitter",
    "x.com",
    
    # E-commerce - Not news
    "amazon.com",
    "ebay.com",
    "alibaba.com",
    "made-in-china",
    "books.google",
    "scribd",
    
    # AI Search - Not primary sources
    "perplexity",
    
    # Paywalled Teasers - Just subscription prompts
    "grandviewresearch",
    "marketsandmarkets",
    "researchandmarkets",
    "mordorintelligence",
    "precedenceresearch",
    "fortunebusinessinsights",
    "imarcgroup",
    "marketresearch",
    "lucintel",
    "bccresearch",
    "gminsights",
    "stratviewresearch",
    "futuremarketinsights",
    "transparencymarketresearch",
    "verifiedmarketresearch",
    "databridge",
    "alliedmarketresearch",
    "technavio",
}


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
- Aerospace: Boeing, Airbus, Embraer, Lockheed Martin, Northrop Grumman, GE Aerospace, Safran, Leonardo, Bombardier, Gulfstream, Textron Aviation (Cessna, Beechcraft), Joby Aviation (eVTOL), Archer Aviation
- Wind: Vestas, Siemens Gamesa, GE Vernova, Nordex, Goldwind, Envision Energy, Enercon, Mingyang Smart Energy, LM Wind Power (owned by GE)
- Construction: Skanska, Turner Construction, Bechtel, Kiewit, AECOM, Jacobs Engineering, Fluor Corporation, PCL Construction, Mortenson, Hensel Phelps, Bedford Reinforced Plastics
- Marine: Brunswick, Beneteau, Groupe Beneteau, Malibu Boats, MasterCraft, Correct Craft, Azimut-Benetti, Ferretti Group, Grady-White, Regulator Marine
- Automotive: Toyota, BMW, Ford, GM, Tesla, Rivian
- Infrastructure: Caterpillar, John Deere, CNH Industrial, Komatsu, Volvo Construction Equipment, Vulcan Materials, Martin Marietta, Hughes Brothers (composite rebar), Composite Advantage
- Transportation: Wabtec, Alstom, Siemens Mobility, CRRC, Stadler Rail, PACCAR (Kenworth, Peterbilt), Daimler Truck, Volvo Trucks, New Flyer, Proterra, BYD

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
    "primary_category": "Competitor|Market|Regulatory|Product|Earnings|Partnership|Expansion|Supply Chain|Logistics|C1 Mention|General",
    "secondary_categories": ["Category1", "Category2"],
    "industries": ["Aerospace", "Wind", "Construction", "Marine", "Automotive", "Infrastructure", "Transportation", "Sporting Goods", "Defense Space", "Industrial"],
    "priority": "High|Medium|Low",
    "relevance_score": 0.0-1.0,
    "headline": "concise, punchy 5-8 word headline capturing the core event",
    "summary": "2-3 sentence summary focusing on implications for composites industry",
    "key_entities": ["Company1", "Company2", "Product1"],
    "sentiment": "positive|negative|neutral",
    "confidence": 0.0-1.0,
    "reasoning": "Brief explanation of classification"
}}

Priority Guidelines:
- HIGH: Direct competitor announcements, major market shifts, regulatory changes affecting composites, C1 mentions
- MEDIUM: Industry trends, partnerships, expansions in composites space
- LOW: Tangentially related news, general market updates

Relevance Score Guidelines:
- 0.9-1.0: Directly about composites, competitors, or C1's markets
- 0.7-0.9: Strongly related to composites industry
- 0.5-0.7: Moderately related (adjacent industries, materials)
- 0.3-0.5: Weakly related
- 0.0-0.3: Minimally relevant
"""

    def __init__(self, config):
        self.config = config
        self.client = get_resilient_async_client(
            anthropic_api_key=config.anthropic_api_key,
            openai_api_key=getattr(config, 'openai_api_key', None),
        )
        self.model = config.classifier_model
        self.temperature = config.classifier_temperature
        
        # Cache for tracked entities (populated from DB)
        self._competitors: List[str] = []
        self._oems: List[str] = []
    
    async def load_tracked_entities(self, storage=None):
        """Load tracked entities from BigQuery for classification context.
        
        Args:
            storage: BigQuery storage instance (optional, will be fetched if not provided)
        """
        try:
            # Use provided storage or fetch from BigQuery
            if storage is None:
                from app.db.gcp_storage import get_storage
                storage = await get_storage()
            
            # Get companies from BigQuery
            companies = await storage.get_companies()
            
            # Filter by type for competitors and OEMs
            self._competitors = [
                c.get("name") for c in companies 
                if c.get("type", "").lower() == "competitor" and c.get("name")
            ]
            self._oems = [
                c.get("name") for c in companies 
                if c.get("type", "").lower() == "oem" and c.get("name")
            ]
            
            logger.info(f"Loaded {len(self._competitors)} competitors, {len(self._oems)} OEMs from BigQuery")
        except Exception as e:
            logger.warning(f"Could not load tracked entities from BigQuery: {e}")
            # Fallback to hardcoded lists
            self._competitors = ["Hexcel", "Toray", "Solvay", "Owens Corning", "Huntsman", "Gurit", "Teijin"]
            self._oems = [
                "Boeing", "Airbus", "Spirit AeroSystems", "GE Aerospace",  # Aerospace
                "Vestas", "Siemens Gamesa", "TPI Composites",  # Wind
                "Brunswick", "Malibu Boats", "MasterCraft",  # Marine
                "Toyota", "BMW", "Ford", "Tesla",  # Automotive
                "Caterpillar", "John Deere",  # Infrastructure
            ]
    
    async def classify(self, article: RawArticle) -> Optional[ClassificationResult]:
        """Classify a single article.
        
        Returns None if the article's source is blocked.
        """
        # Check if source is blocked
        if self._is_source_blocked(article.source_name, article.url):
            logger.debug(f"Blocked source: {article.source_name} - {article.url[:50]}")
            return None
        
        
        content = article.full_text or article.summary
        if len(content) > 4000:
            content = content[:4000] + "..."
        
        prompt = self.CLASSIFICATION_PROMPT.format(
            title=article.title,
            source=article.source_name,
            content=content,
            competitors=", ".join(self._competitors) if self._competitors else "Not loaded",
            oems=", ".join(self._oems) if self._oems else "Not loaded",
        )
        
        try:
            response = await self.client.messages_create(
                model=self.model,
                max_tokens=1000,
                temperature=self.temperature,
                messages=[{"role": "user", "content": prompt}]
            )
            
            result_text = response.content[0].text.strip()
            
            # Clean up potential markdown code blocks
            if result_text.startswith("```"):
                result_text = re.sub(r'^```json?\n?', '', result_text)
                result_text = re.sub(r'\n?```$', '', result_text)
            
            data = json.loads(result_text)
            
            # Map to enums
            try:
                primary_cat = ContentCategory(data.get("primary_category", "General"))
            except ValueError:
                # Fallback to general if not found
                primary_cat = ContentCategory.GENERAL
                
            secondary_cats = [
                ContentCategory(c) for c in data.get("secondary_categories", [])
                if c in [e.value for e in ContentCategory]
            ]
            industries = [
                Industry(i) for i in data.get("industries", [])
                if i in [e.value for e in Industry]
            ]
            try:
                # Normalize priority to title case (e.g., "high" → "High", "LOW" → "Low")
                raw_priority = data.get("priority", "low")
                priority = Priority(raw_priority.title() if raw_priority else "Low")
            except ValueError:
                priority = Priority.LOW
            
            # Apply source-based score boost
            base_score = float(data.get("relevance_score", 0.5))
            source_boost = self._get_source_boost(article.source_name)
            boosted_score = min(1.0, base_score + source_boost)  # Cap at 1.0
            
            if source_boost > 0:
                logger.debug(f"Source boost: {article.source_name} +{source_boost} ({base_score:.2f} → {boosted_score:.2f})")
            
            return ClassificationResult(
                categories=[primary_cat] + secondary_cats,
                primary_category=primary_cat,
                industries=industries,
                priority=priority,
                relevance_score=boosted_score,
                headline=data.get("headline", ""),
                summary=data.get("summary", article.summary[:200]),
                key_entities=data.get("key_entities", []),
                sentiment=data.get("sentiment", "neutral"),
                confidence=float(data.get("confidence", 0.7)),
            )
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse classification JSON: {e}")
            return self._default_classification(article)
        except Exception as e:
            logger.error(f"Classification error: {e}")
            return self._default_classification(article)
    
    async def classify_batch(
        self, 
        articles: List[RawArticle],
        max_concurrent: int = 10
    ) -> List[Tuple[RawArticle, ClassificationResult]]:
        """Classify multiple articles with rate limiting"""
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def classify_one(article: RawArticle) -> Tuple[RawArticle, ClassificationResult]:
            async with semaphore:
                result = await self.classify(article)
                await asyncio.sleep(0.2)
                return (article, result)
        
        tasks = [classify_one(article) for article in articles]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        valid_results = []
        blocked_count = 0
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Batch classification error: {result}")
            elif result[1] is None:
                # Article was from blocked source
                blocked_count += 1
            else:
                valid_results.append(result)
        
        if blocked_count > 0:
            logger.info(f"Filtered {blocked_count} articles from blocked sources")
        logger.info(f"Classified {len(valid_results)}/{len(articles)} articles")
        return valid_results
    
    def _default_classification(self, article: RawArticle) -> ClassificationResult:
        """Return default classification when AI fails"""
        text = f"{article.title} {article.summary}".lower()
        
        categories = []
        for cat, keywords in CATEGORY_KEYWORDS.items():
            if any(kw.lower() in text for kw in keywords):
                categories.append(cat)
        
        industries = []
        for ind, keywords in INDUSTRY_KEYWORDS.items():
            if any(kw.lower() in text for kw in keywords):
                industries.append(ind)
        
        primary = categories[0] if categories else ContentCategory.GENERAL
        
        return ClassificationResult(
            categories=categories or [ContentCategory.GENERAL],
            primary_category=primary,
            industries=industries,
            priority=Priority.LOW,
            relevance_score=0.5,
            summary=article.summary[:200],
            key_entities=[],
            sentiment="neutral",
            confidence=0.3,
        )
    
    def _get_source_boost(self, source_name: str) -> float:
        """Get score boost based on source quality tier.
        
        Returns the highest matching boost for the source name.
        Matching is case-insensitive and uses partial matching.
        """
        if not source_name:
            return 0.0
        
        source_lower = source_name.lower()
        max_boost = 0.0
        
        for source_key, boost in SOURCE_SCORE_BOOSTS.items():
            if source_key.lower() in source_lower or source_lower in source_key.lower():
                max_boost = max(max_boost, boost)
        
        return max_boost
    
    def _is_source_blocked(self, source_name: str, url: str = "") -> bool:
        """Check if a source should be blocked entirely.
        
        Matches against both source_name and URL using case-insensitive partial matching.
        """
        # Combine source name and URL for matching
        check_strings = []
        if source_name:
            check_strings.append(source_name.lower())
        if url:
            check_strings.append(url.lower())
        
        for check_str in check_strings:
            for blocked in BLOCKED_SOURCES:
                if blocked.lower() in check_str:
                    return True
        
        return False


