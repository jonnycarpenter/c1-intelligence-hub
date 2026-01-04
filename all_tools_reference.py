"""
C1 Intelligence Hub - Complete Tool Reference
=============================================

All 28 tools organized by category:
- Tracking Management (9 tools)
- Corpus Query (7 tools)
- Research Analytics (6 tools)
- Product Intelligence (6 tools)

These tools are used by the Intelligence Agent and Research Agent
to provide comprehensive composites industry intelligence.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Literal
import os
import httpx
from langchain_core.tools import tool

logger = logging.getLogger(__name__)


# ============================================================================
# SECTION 1: TRACKING MANAGEMENT TOOLS (9 tools)
# ============================================================================
# These tools manage what entities the hub monitors.
# Available to ALL agents (Intelligence, Research, Products).

# --- Helper mappings for natural language parsing ---

ENTITY_TYPE_ALIASES = {
    "competitor": "competitor",
    "competitors": "competitor",
    "competition": "competitor",
    "rival": "competitor",
    "rivals": "competitor",
    "oem": "oem",
    "oems": "oem",
    "original equipment manufacturer": "oem",
    "manufacturer": "oem",
    "manufacturers": "oem",
    "material manufacturer": "material_manufacturer",
    "material manufacturers": "material_manufacturer",
    "material supplier": "material_manufacturer",
    "material suppliers": "material_manufacturer",
    "material": "material",
    "materials": "material",
    "raw material": "material",
    "raw materials": "material",
    "end market": "end_market",
    "end markets": "end_market",
    "market": "end_market",
    "markets": "end_market",
    "vertical": "end_market",
    "verticals": "end_market",
    "industry": "end_market",
    "industries": "end_market",
    "distributor": "distributor",
    "distributors": "distributor",
    "supplier": "supplier",
    "suppliers": "supplier",
}

INDUSTRY_ALIASES = {
    "aerospace": "aerospace",
    "aviation": "aerospace",
    "aircraft": "aerospace",
    "automotive": "automotive",
    "auto": "automotive",
    "vehicle": "automotive",
    "marine": "marine",
    "boat": "marine",
    "ship": "marine",
    "wind": "wind_energy",
    "wind energy": "wind_energy",
    "wind turbine": "wind_energy",
    "infrastructure": "infrastructure",
    "construction": "construction",
    "sporting goods": "sporting_goods",
    "sports": "sporting_goods",
    "defense": "defense",
    "military": "defense",
    "industrial": "industrial",
}


def parse_entity_type(type_str: str) -> Optional[str]:
    """Parse a natural language entity type string"""
    return ENTITY_TYPE_ALIASES.get(type_str.lower().strip())


def parse_industry(industry_str: str) -> Optional[str]:
    """Parse a natural language industry string"""
    return INDUSTRY_ALIASES.get(industry_str.lower().strip())


# --- Tool 1: list_tracked_entities ---

@tool
async def list_tracked_entities(
    entity_type: str,
    industry: Optional[str] = None,
    show_details: bool = False
) -> str:
    """
    List entities we are currently tracking.
    
    Use this when users ask questions like:
    - "Show me competitors we're tracking"
    - "List aerospace OEMs"
    - "What material manufacturers do we have?"
    - "Which suppliers are we monitoring?"
    
    Args:
        entity_type: Type of entity to list. Options: competitor, oem, material_manufacturer, 
                    material, end_market, distributor, supplier
        industry: Optional filter by industry (aerospace, automotive, marine, wind_energy, etc.)
        show_details: Whether to show additional details like ticker, industries
    
    Returns:
        Formatted list of tracked entities
    """
    from app.db.database import get_db
    
    db = get_db()
    parsed_type = parse_entity_type(entity_type)
    
    if not parsed_type:
        return f"I don't recognize the entity type '{entity_type}'. Valid types are: competitor, oem, material_manufacturer, material, end_market, distributor, supplier."
    
    parsed_industry = parse_industry(industry) if industry else None
    
    try:
        entities = await db.list_entities(
            entity_type=parsed_type,
            industry=parsed_industry,
            is_active=True
        )
        
        if not entities:
            filter_desc = f" in {industry}" if industry else ""
            return f"No {entity_type}{filter_desc} are currently being tracked."
        
        # Format output
        if show_details:
            lines = []
            for e in entities:
                details = []
                if e.metadata.industries:
                    details.append(f"Industries: {', '.join(i.value for i in e.metadata.industries)}")
                if e.metadata.ticker:
                    details.append(f"Ticker: {e.metadata.ticker}")
                if e.priority_entity:
                    details.append("⭐ Priority")
                detail_str = f" ({'; '.join(details)})" if details else ""
                lines.append(f"• {e.name}{detail_str}")
            entity_list = "\n".join(lines)
        else:
            entity_list = ", ".join(e.name for e in entities)
        
        filter_desc = f" in {industry}" if industry else ""
        return f"**{len(entities)} {parsed_type}(s){filter_desc} being tracked:**\n\n{entity_list}"
    
    except Exception as e:
        logger.error(f"Error listing entities: {e}")
        return f"Error retrieving tracked entities: {str(e)}"


# --- Tool 2: count_tracked_entities ---

@tool
async def count_tracked_entities(
    entity_type: str,
    industry: Optional[str] = None
) -> str:
    """
    Count how many entities of a type we are tracking.
    
    Use this when users ask questions like:
    - "How many competitors are we tracking?"
    - "How many aerospace OEMs do we have?"
    - "Count the material manufacturers"
    
    Args:
        entity_type: Type of entity to count (competitor, oem, material_manufacturer, etc.)
        industry: Optional filter by industry (aerospace, automotive, marine, etc.)
    
    Returns:
        Count with context
    """
    from app.db.database import get_db
    
    db = get_db()
    parsed_type = parse_entity_type(entity_type)
    
    if not parsed_type:
        return f"I don't recognize the entity type '{entity_type}'."
    
    parsed_industry = parse_industry(industry) if industry else None
    
    try:
        count = await db.count_entities(
            entity_type=parsed_type,
            industry=parsed_industry,
            is_active=True
        )
        
        filter_desc = f" in {industry}" if industry else ""
        
        if count == 0:
            return f"We are not currently tracking any {entity_type}{filter_desc}."
        elif count == 1:
            return f"We are tracking **1** {parsed_type}{filter_desc}."
        else:
            return f"We are tracking **{count}** {parsed_type}s{filter_desc}."
    
    except Exception as e:
        logger.error(f"Error counting entities: {e}")
        return f"Error counting entities: {str(e)}"


# --- Tool 3: add_tracked_entity ---

@tool
async def add_tracked_entity(
    entity_type: str,
    name: str,
    industries: Optional[str] = None,
    ticker: Optional[str] = None,
    notes: Optional[str] = None,
    priority: bool = False
) -> str:
    """
    Add a new entity to tracking.
    
    Use this when users ask to:
    - "Add Solvay to competitors"
    - "Start tracking Toray as a material manufacturer"
    - "Add Boeing to aerospace OEMs"
    - "Track carbon fiber pricing" (material)
    
    Args:
        entity_type: Type of entity (competitor, oem, material_manufacturer, material, end_market)
        name: Name of the entity to add
        industries: Comma-separated industries (aerospace, automotive, marine, etc.)
        ticker: Stock ticker symbol if applicable
        notes: Optional notes about this entity
        priority: Whether this is a high-priority entity to monitor closely
    
    Returns:
        Confirmation of addition
    """
    from app.db.database import get_db
    from app.models.entities import TrackedEntityCreate, EntityMetadata, EntityType, Industry
    
    db = get_db()
    parsed_type = parse_entity_type(entity_type)
    
    if not parsed_type:
        return f"I don't recognize the entity type '{entity_type}'."
    
    # Check if already exists
    existing = await db.get_entity_by_name(name, EntityType(parsed_type))
    if existing:
        return f"**{name}** is already being tracked as a {parsed_type}."
    
    # Parse industries
    industry_list = []
    if industries:
        for ind_str in industries.split(","):
            parsed_ind = parse_industry(ind_str.strip())
            if parsed_ind:
                industry_list.append(Industry(parsed_ind))
    
    # Create metadata
    metadata = EntityMetadata(
        industries=industry_list,
        ticker=ticker.upper() if ticker else None,
        notes=notes
    )
    
    # Create entity
    entity_create = TrackedEntityCreate(
        entity_type=EntityType(parsed_type),
        name=name.strip(),
        metadata=metadata,
        priority_entity=priority
    )
    
    try:
        entity = await db.create_entity(entity_create)
        
        details = []
        if industry_list:
            details.append(f"Industries: {', '.join(i.value for i in industry_list)}")
        if ticker:
            details.append(f"Ticker: {ticker.upper()}")
        if priority:
            details.append("Marked as priority")
        
        detail_str = f"\n({'; '.join(details)})" if details else ""
        count = await db.count_entities(entity_type=EntityType(parsed_type), is_active=True)
        
        return f"✅ Added **{name}** to tracked {parsed_type}s.{detail_str}\n\nYou are now tracking {count} {parsed_type}(s)."
    
    except Exception as e:
        logger.error(f"Error adding entity: {e}")
        return f"Error adding entity: {str(e)}"


# --- Tool 4: add_multiple_entities ---

@tool
async def add_multiple_entities(
    entity_type: str,
    names: str,
    industries: Optional[str] = None
) -> str:
    """
    Add multiple entities to tracking at once.
    
    Use this when users ask to:
    - "Add Toray, Hexcel, and Solvay to competitors"
    - "Start tracking Boeing, Airbus, Spirit as aerospace OEMs"
    
    Args:
        entity_type: Type of entities (competitor, oem, material_manufacturer, etc.)
        names: Comma-separated list of entity names
        industries: Optional comma-separated industries to apply to all
    
    Returns:
        Summary of additions
    """
    from app.db.database import get_db
    from app.models.entities import TrackedEntityCreate, EntityMetadata, EntityType, Industry
    
    db = get_db()
    parsed_type = parse_entity_type(entity_type)
    
    if not parsed_type:
        return f"I don't recognize the entity type '{entity_type}'."
    
    name_list = [n.strip() for n in names.split(",") if n.strip()]
    if not name_list:
        return "No entity names provided."
    
    # Parse industries
    industry_list = []
    if industries:
        for ind_str in industries.split(","):
            parsed_ind = parse_industry(ind_str.strip())
            if parsed_ind:
                industry_list.append(Industry(parsed_ind))
    
    added = []
    already_exists = []
    errors = []
    
    for name in name_list:
        existing = await db.get_entity_by_name(name, EntityType(parsed_type))
        if existing:
            already_exists.append(name)
            continue
        
        metadata = EntityMetadata(industries=industry_list)
        entity_create = TrackedEntityCreate(
            entity_type=EntityType(parsed_type),
            name=name,
            metadata=metadata
        )
        
        try:
            await db.create_entity(entity_create)
            added.append(name)
        except Exception as e:
            errors.append(f"{name}: {str(e)}")
    
    response_parts = []
    if added:
        response_parts.append(f"✅ Added {len(added)} {parsed_type}(s): {', '.join(added)}")
    if already_exists:
        response_parts.append(f"ℹ️ Already tracking: {', '.join(already_exists)}")
    if errors:
        response_parts.append(f"❌ Errors: {'; '.join(errors)}")
    
    count = await db.count_entities(entity_type=EntityType(parsed_type), is_active=True)
    response_parts.append(f"\nTotal {parsed_type}s now tracked: {count}")
    
    return "\n".join(response_parts)


# --- Tool 5: remove_tracked_entity ---

@tool
async def remove_tracked_entity(
    entity_type: str,
    name: str
) -> str:
    """
    Remove an entity from tracking.
    
    Use this when users ask to:
    - "Remove Solvay from competitors"
    - "Stop tracking Boeing"
    - "Delete xyz from material manufacturers"
    
    Args:
        entity_type: Type of entity (competitor, oem, material_manufacturer, etc.)
        name: Name of the entity to remove
    
    Returns:
        Confirmation of removal
    """
    from app.db.database import get_db
    from app.models.entities import EntityType
    
    db = get_db()
    parsed_type = parse_entity_type(entity_type)
    
    if not parsed_type:
        return f"I don't recognize the entity type '{entity_type}'."
    
    entity = await db.get_entity_by_name(name, EntityType(parsed_type))
    if not entity:
        return f"**{name}** is not currently being tracked as a {parsed_type}."
    
    try:
        success = await db.delete_entity(entity.id)
        
        if success:
            count = await db.count_entities(entity_type=EntityType(parsed_type), is_active=True)
            return f"✅ Removed **{name}** from tracked {parsed_type}s.\n\nYou are now tracking {count} {parsed_type}(s)."
        else:
            return f"Failed to remove {name}."
    
    except Exception as e:
        logger.error(f"Error removing entity: {e}")
        return f"Error removing entity: {str(e)}"


# --- Tool 6: update_tracked_entity ---

@tool
async def update_tracked_entity(
    name: str,
    entity_type: Optional[str] = None,
    add_industries: Optional[str] = None,
    set_ticker: Optional[str] = None,
    set_priority: Optional[bool] = None,
    add_notes: Optional[str] = None
) -> str:
    """
    Update an existing tracked entity.
    
    Use this when users ask to:
    - "Mark Hexcel as priority"
    - "Add aerospace industry to Toray"
    - "Set ticker HXL for Hexcel"
    
    Args:
        name: Name of the entity to update
        entity_type: Type of entity (helps narrow search if name is ambiguous)
        add_industries: Comma-separated industries to add
        set_ticker: Stock ticker to set
        set_priority: Whether this is a priority entity
        add_notes: Notes to add
    
    Returns:
        Confirmation of update
    """
    from app.db.database import get_db
    from app.models.entities import TrackedEntityUpdate, EntityType, Industry
    
    db = get_db()
    parsed_type = EntityType(parse_entity_type(entity_type)) if entity_type and parse_entity_type(entity_type) else None
    
    entity = await db.get_entity_by_name(name, parsed_type)
    if not entity:
        type_desc = f" as a {parsed_type.value}" if parsed_type else ""
        return f"**{name}** is not currently being tracked{type_desc}."
    
    new_metadata = entity.metadata.model_copy()
    
    if add_industries:
        for ind_str in add_industries.split(","):
            parsed_ind = parse_industry(ind_str.strip())
            if parsed_ind:
                ind_enum = Industry(parsed_ind)
                if ind_enum not in new_metadata.industries:
                    new_metadata.industries.append(ind_enum)
    
    if set_ticker:
        new_metadata.ticker = set_ticker.upper()
    
    if add_notes:
        existing_notes = new_metadata.notes or ""
        new_metadata.notes = f"{existing_notes}\n{add_notes}".strip()
    
    updates = TrackedEntityUpdate(
        metadata=new_metadata,
        priority_entity=set_priority if set_priority is not None else None
    )
    
    try:
        await db.update_entity(entity.id, updates)
        
        changes = []
        if add_industries:
            changes.append(f"Added industries: {add_industries}")
        if set_ticker:
            changes.append(f"Set ticker: {set_ticker.upper()}")
        if set_priority is not None:
            changes.append(f"Priority: {'Yes' if set_priority else 'No'}")
        if add_notes:
            changes.append("Added notes")
        
        return f"✅ Updated **{name}**:\n" + "\n".join(f"• {c}" for c in changes)
    
    except Exception as e:
        logger.error(f"Error updating entity: {e}")
        return f"Error updating entity: {str(e)}"


# --- Tool 7: get_tracking_summary ---

@tool
async def get_tracking_summary() -> str:
    """
    Get an overview of everything being tracked.
    
    Use this when users ask:
    - "What are we tracking?"
    - "Give me a summary of tracked entities"
    - "How much are we monitoring?"
    
    Returns:
        Summary of all tracked entities by type
    """
    from app.db.database import get_db
    
    db = get_db()
    
    try:
        summary = await db.get_tracking_summary()
        
        lines = [f"**Tracking Summary** ({summary.total_entities} total entities)\n"]
        
        lines.append("**By Type:**")
        for tc in summary.by_type:
            if tc.total > 0:
                priority_str = f" ({tc.priority} priority)" if tc.priority > 0 else ""
                lines.append(f"• {tc.entity_type.value.replace('_', ' ').title()}: {tc.active} active{priority_str}")
        
        if summary.top_mentioned:
            lines.append("\n**Most Mentioned (30 days):**")
            for item in summary.top_mentioned[:5]:
                if item["mentions"] > 0:
                    lines.append(f"• {item['name']}: {item['mentions']} mentions")
        
        if summary.recently_added:
            lines.append("\n**Recently Added:**")
            for item in summary.recently_added[:3]:
                lines.append(f"• {item['name']} ({item['type']})")
        
        return "\n".join(lines)
    
    except Exception as e:
        logger.error(f"Error getting tracking summary: {e}")
        return f"Error retrieving tracking summary: {str(e)}"


# --- Tool 8: search_tracked_entities ---

@tool
async def search_tracked_entities(query: str) -> str:
    """
    Search across all tracked entities.
    
    Use this when users ask:
    - "Do we track anyone in wind energy?"
    - "Search for Toray"
    - "Find anything related to carbon fiber"
    
    Args:
        query: Search term
    
    Returns:
        Matching entities across all types
    """
    from app.db.database import get_db
    
    db = get_db()
    
    try:
        entities = await db.search_entities(query, limit=20)
        
        if not entities:
            return f"No tracked entities match '{query}'."
        
        by_type: dict = {}
        for e in entities:
            if e.entity_type not in by_type:
                by_type[e.entity_type] = []
            by_type[e.entity_type].append(e)
        
        lines = [f"**Found {len(entities)} entities matching '{query}':**\n"]
        
        for entity_type, type_entities in by_type.items():
            lines.append(f"**{entity_type.value.replace('_', ' ').title()}s:**")
            for e in type_entities:
                lines.append(f"• {e.name}")
            lines.append("")
        
        return "\n".join(lines)
    
    except Exception as e:
        logger.error(f"Error searching entities: {e}")
        return f"Error searching entities: {str(e)}"


# --- Tool 9: get_entity_details ---

@tool
async def get_entity_details(
    name: str,
    entity_type: Optional[str] = None
) -> str:
    """
    Get detailed information about a specific tracked entity.
    
    Use this when users ask:
    - "Tell me about Hexcel in our tracking"
    - "What do we know about Toray?"
    - "Details on Boeing"
    
    Args:
        name: Name of the entity
        entity_type: Optional type to narrow search
    
    Returns:
        Detailed entity information
    """
    from app.db.database import get_db
    from app.models.entities import EntityType
    
    db = get_db()
    parsed_type = EntityType(parse_entity_type(entity_type)) if entity_type and parse_entity_type(entity_type) else None
    
    entity = await db.get_entity_by_name(name, parsed_type)
    if not entity:
        return f"**{name}** is not currently being tracked."
    
    lines = [f"**{entity.name}**"]
    lines.append(f"Type: {entity.entity_type.value.replace('_', ' ').title()}")
    
    if entity.aliases:
        lines.append(f"Aliases: {', '.join(entity.aliases)}")
    if entity.metadata.industries:
        lines.append(f"Industries: {', '.join(i.value for i in entity.metadata.industries)}")
    if entity.metadata.ticker:
        lines.append(f"Ticker: {entity.metadata.ticker}")
    if entity.metadata.website:
        lines.append(f"Website: {entity.metadata.website}")
    if entity.metadata.headquarters:
        lines.append(f"HQ: {entity.metadata.headquarters}")
    if entity.priority_entity:
        lines.append("⭐ Priority entity (closely monitored)")
    if entity.alert_keywords:
        lines.append(f"Alert keywords: {', '.join(entity.alert_keywords)}")
    if entity.metadata.notes:
        lines.append(f"\nNotes: {entity.metadata.notes}")
    
    lines.append(f"\nTracking since: {entity.created_at.strftime('%Y-%m-%d')}")
    
    if entity.mention_count_30d > 0:
        lines.append(f"Mentions (30 days): {entity.mention_count_30d}")
    
    return "\n".join(lines)


# ============================================================================
# SECTION 2: CORPUS QUERY TOOLS (7 tools)
# ============================================================================
# These tools query the pre-ingested intelligence corpus.
# Available to ALL agents.

CATEGORY_ALIASES = {
    "competitor": "competitor",
    "competitors": "competitor",
    "market": "market",
    "market trend": "market",
    "trends": "market",
    "regulatory": "regulatory",
    "regulation": "regulatory",
    "product": "product",
    "product launch": "product",
    "earnings": "earnings",
    "partnership": "partnership",
    "expansion": "expansion",
    "supply chain": "supply_chain",
    "supply": "supply_chain",
}

PRIORITY_ALIASES = {
    "high": "high",
    "important": "high",
    "urgent": "high",
    "medium": "medium",
    "normal": "medium",
    "low": "low",
}


# --- Tool 10: query_corpus ---

@tool
async def query_corpus(
    query: Optional[str] = None,
    hours: int = 72,
    category: Optional[str] = None,
    priority: Optional[str] = None,
    company: Optional[str] = None,
    limit: int = 10
) -> str:
    """
    Search the pre-ingested intelligence corpus.
    
    Use this FIRST before web search for questions about recent industry activity.
    The corpus contains pre-classified, relevant composites industry content.
    
    Use this when users ask:
    - "What happened with Hexcel this week?"
    - "Any news about carbon fiber supply?"
    - "Recent competitor announcements"
    - "What's in the news about aerospace composites?"
    
    Args:
        query: Search terms (searches title and summary)
        hours: How far back to look (default 72 hours)
        category: Filter by category: competitor, market, regulatory, product, earnings, partnership, expansion, supply_chain
        priority: Filter by priority: high, medium, low
        company: Filter by company mentioned
        limit: Maximum results to return
    
    Returns:
        Relevant intelligence items from the corpus
    """
    from app.db.database import get_db
    from app.models.entities import CorpusQuery, ContentCategory, Priority
    
    db = get_db()
    
    categories = [ContentCategory(CATEGORY_ALIASES[category])] if category and category in CATEGORY_ALIASES else None
    priorities = [Priority(PRIORITY_ALIASES[priority])] if priority and priority in PRIORITY_ALIASES else None
    companies = [company] if company else None
    
    corpus_query = CorpusQuery(
        query=query,
        hours=hours,
        categories=categories,
        priorities=priorities,
        companies=companies,
        limit=limit
    )
    
    try:
        items = await db.query_corpus(corpus_query)
        
        if not items:
            filter_parts = []
            if query:
                filter_parts.append(f"matching '{query}'")
            if category:
                filter_parts.append(f"in {category}")
            if company:
                filter_parts.append(f"about {company}")
            filter_desc = " ".join(filter_parts) if filter_parts else ""
            return f"No intelligence items found {filter_desc} in the last {hours} hours."
        
        # Format results
        lines = [f"**Found {len(items)} intelligence items** (last {hours} hours)\n"]
        
        for i, item in enumerate(items[:limit], 1):
            priority_icon = "🔴" if item.priority.value == "high" else "🟡" if item.priority.value == "medium" else "⚪"
            lines.append(f"**{i}. {priority_icon} {item.title}**")
            if item.summary:
                summary = item.summary[:200] + "..." if len(item.summary) > 200 else item.summary
                lines.append(summary)
            lines.append(f"*{item.source.name} | {item.published_at.strftime('%b %d')}*")
            lines.append("")
        
        return "\n".join(lines)
    
    except Exception as e:
        logger.error(f"Error querying corpus: {e}")
        return f"Error searching intelligence corpus: {str(e)}"


# --- Tool 11: get_digest ---

@tool
async def get_digest(hours: int = 72) -> str:
    """
    Get the pre-computed intelligence digest.
    
    The digest is a curated summary of the most important intelligence
    from the specified time period, organized by priority and category.
    
    Use this when users ask:
    - "What should I know about?"
    - "Give me the intelligence briefing"
    - "What happened in the last 3 days?"
    - "Show me the digest"
    
    Args:
        hours: Time period for digest (default 72 hours / 3 days)
    
    Returns:
        Formatted intelligence digest
    """
    from app.db.database import get_db
    
    db = get_db()
    
    try:
        digest = await db.get_current_digest(hours=hours)
        
        if not digest:
            return f"No digest available for the last {hours} hours. The digest may still be generating."
        
        lines = [
            f"# Intelligence Digest",
            f"*{digest.period_start.strftime('%b %d')} - {digest.period_end.strftime('%b %d, %Y')}*",
            ""
        ]
        
        if digest.executive_summary:
            lines.append(f"**Summary:** {digest.executive_summary}")
            lines.append("")
        
        lines.append(f"**{digest.stats.total_items}** items from **{digest.stats.sources_count}** sources")
        lines.append("")
        
        # High priority items
        high_priority = [i for i in digest.items if i.priority.value == "high"]
        if high_priority:
            lines.append("## 🔴 Priority Items")
            for item in high_priority:
                lines.append(f"• **{item.title}** ({item.source_name})")
            lines.append("")
        
        return "\n".join(lines)
    
    except Exception as e:
        logger.error(f"Error getting digest: {e}")
        return f"Error retrieving digest: {str(e)}"


# --- Tool 12: get_entity_mentions ---

@tool
async def get_entity_mentions(
    entity_name: str,
    hours: int = 72,
    limit: int = 10
) -> str:
    """
    Get recent mentions of a specific tracked entity.
    
    Use this when users ask:
    - "What's been said about Hexcel recently?"
    - "Recent mentions of Toray"
    - "News about Boeing in composites"
    
    Args:
        entity_name: Name of the entity to find mentions for
        hours: How far back to look (default 72 hours)
        limit: Maximum mentions to return
    
    Returns:
        Recent corpus items mentioning the entity
    """
    from app.db.database import get_db
    from app.models.entities import CorpusQuery
    
    db = get_db()
    
    entity = await db.get_entity_by_name(entity_name)
    
    if entity:
        items = await db.get_entity_mentions(entity.id, hours=hours, limit=limit)
    else:
        corpus_query = CorpusQuery(query=entity_name, hours=hours, limit=limit)
        items = await db.query_corpus(corpus_query)
    
    if not items:
        return f"No mentions of '{entity_name}' found in the last {hours} hours."
    
    lines = [f"**{len(items)} mentions of {entity_name}** (last {hours} hours)\n"]
    
    for i, item in enumerate(items[:limit], 1):
        lines.append(f"**{i}. {item.title}**")
        lines.append(f"*{item.source.name} | {item.published_at.strftime('%b %d')}*")
        lines.append("")
    
    return "\n".join(lines)


# --- Tool 13: get_corpus_stats ---

@tool
async def get_corpus_stats(hours: int = 72) -> str:
    """
    Get statistics about the intelligence corpus.
    
    Use this when users ask:
    - "How much content do we have?"
    - "What's the corpus coverage like?"
    - "How many articles this week?"
    
    Args:
        hours: Time period to analyze (default 72 hours)
    
    Returns:
        Corpus statistics
    """
    from app.db.database import get_db
    
    db = get_db()
    
    try:
        stats = await db.get_corpus_stats(hours=hours)
        
        lines = [
            f"**Corpus Statistics** (last {hours} hours)",
            "",
            f"📊 **Total Items:** {stats['total_items']}",
            f"📰 **Unique Sources:** {stats['unique_sources']}",
            "",
            "**By Priority:**"
        ]
        
        for priority, count in stats.get('by_priority', {}).items():
            icon = "🔴" if priority == "high" else "🟡" if priority == "medium" else "⚪"
            lines.append(f"  {icon} {priority.title()}: {count}")
        
        return "\n".join(lines)
    
    except Exception as e:
        logger.error(f"Error getting corpus stats: {e}")
        return f"Error retrieving corpus statistics: {str(e)}"


# --- Tool 14: get_priority_items ---

@tool
async def get_priority_items(hours: int = 72, limit: int = 10) -> str:
    """
    Get high-priority intelligence items.
    
    Use this when users ask:
    - "What's most important right now?"
    - "Any urgent news?"
    - "Show me priority items"
    
    Args:
        hours: Time period (default 72 hours)
        limit: Maximum items to return
    
    Returns:
        High-priority intelligence items
    """
    from app.db.database import get_db
    from app.models.entities import CorpusQuery, Priority
    
    db = get_db()
    
    corpus_query = CorpusQuery(hours=hours, priorities=[Priority.HIGH], limit=limit)
    
    try:
        items = await db.query_corpus(corpus_query)
        
        if not items:
            return f"No high-priority items in the last {hours} hours. This is good news! 🎉"
        
        lines = [f"**🔴 {len(items)} High-Priority Items**\n"]
        
        for i, item in enumerate(items[:limit], 1):
            lines.append(f"**{i}. {item.title}**")
            if item.summary:
                lines.append(item.summary[:200])
            lines.append(f"*{item.source.name} | {item.published_at.strftime('%b %d')}*")
            lines.append("")
        
        return "\n".join(lines)
    
    except Exception as e:
        logger.error(f"Error getting priority items: {e}")
        return f"Error retrieving priority items: {str(e)}"


# --- Tool 15: get_competitor_activity ---

@tool
async def get_competitor_activity(
    competitor_name: Optional[str] = None,
    hours: int = 72,
    limit: int = 10
) -> str:
    """
    Get recent competitor activity and news.
    
    Use this when users ask:
    - "What are competitors doing?"
    - "Any news from Hexcel?"
    - "Competitor announcements this week"
    
    Args:
        competitor_name: Specific competitor (optional, shows all if not specified)
        hours: Time period (default 72 hours)
        limit: Maximum items to return
    
    Returns:
        Competitor-related intelligence
    """
    from app.db.database import get_db
    from app.models.entities import CorpusQuery, ContentCategory
    
    db = get_db()
    
    corpus_query = CorpusQuery(
        hours=hours,
        categories=[ContentCategory.COMPETITOR_NEWS],
        companies=[competitor_name] if competitor_name else None,
        limit=limit
    )
    
    try:
        items = await db.query_corpus(corpus_query)
        
        if not items:
            if competitor_name:
                return f"No activity from **{competitor_name}** in the last {hours} hours."
            return f"No competitor activity recorded in the last {hours} hours."
        
        header = f"**Activity from {competitor_name}**" if competitor_name else "**Competitor Activity**"
        lines = [f"{header} (last {hours} hours)\n"]
        
        for i, item in enumerate(items[:limit], 1):
            lines.append(f"**{i}. {item.title}**")
            lines.append(f"*{item.source.name} | {item.published_at.strftime('%b %d')}*")
            lines.append("")
        
        return "\n".join(lines)
    
    except Exception as e:
        logger.error(f"Error getting competitor activity: {e}")
        return f"Error retrieving competitor activity: {str(e)}"


# --- Tool 16: get_market_signals ---

@tool
async def get_market_signals(
    industry: Optional[str] = None,
    hours: int = 168,
    limit: int = 10
) -> str:
    """
    Get market trend signals and indicators.
    
    Use this when users ask:
    - "What are the market trends?"
    - "Aerospace market signals"
    - "Any demand indicators?"
    
    Args:
        industry: Filter by industry (aerospace, automotive, marine, wind_energy, etc.)
        hours: Time period (default 168 hours / 1 week)
        limit: Maximum items to return
    
    Returns:
        Market trend intelligence
    """
    from app.db.database import get_db
    from app.models.entities import CorpusQuery, ContentCategory, Industry
    
    db = get_db()
    
    parsed_industry = Industry(parse_industry(industry)) if industry and parse_industry(industry) else None
    
    corpus_query = CorpusQuery(
        hours=hours,
        categories=[ContentCategory.MARKET_TREND],
        industries=[parsed_industry] if parsed_industry else None,
        limit=limit
    )
    
    try:
        items = await db.query_corpus(corpus_query)
        
        if not items:
            industry_desc = f" for {industry}" if industry else ""
            return f"No market signals{industry_desc} in the last {hours} hours."
        
        industry_desc = f" — {industry.title()}" if industry else ""
        lines = [f"**📊 Market Signals{industry_desc}** (last {hours // 24} days)\n"]
        
        for i, item in enumerate(items[:limit], 1):
            lines.append(f"**{i}. {item.title}**")
            lines.append(f"*{item.source.name} | {item.published_at.strftime('%b %d')}*")
            lines.append("")
        
        return "\n".join(lines)
    
    except Exception as e:
        logger.error(f"Error getting market signals: {e}")
        return f"Error retrieving market signals: {str(e)}"


# ============================================================================
# SECTION 3: RESEARCH ANALYTICS TOOLS (6 tools)
# ============================================================================
# These are longer-running analytical tools for deep research.
# Available to RESEARCH AGENT only.

FMP_API_KEY = os.getenv("FMP_API_KEY", "")
FMP_BASE_URL = "https://financialmodelingprep.com/api/v3"

COMPANY_TICKERS = {
    "hexcel": "HXL",
    "toray": "TRYIY",
    "solvay": "SOLVY",
    "owens corning": "OC",
    "huntsman": "HUN",
    "teijin": "TINLY",
    "mitsubishi chemical": "MTLHY",
    "gurit": "GUR.SW",
    "boeing": "BA",
    "airbus": "EADSY",
    "spirit aerosystems": "SPR",
    "general electric": "GE",
    "siemens": "SIEGY",
    "vestas": "VWDRY",
}


async def fmp_request(endpoint: str, params: dict = None) -> dict:
    """Make a request to the FMP API"""
    if not FMP_API_KEY:
        raise ValueError("FMP_API_KEY not configured")
    
    params = params or {}
    params["apikey"] = FMP_API_KEY
    
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{FMP_BASE_URL}/{endpoint}", params=params, timeout=30.0)
        response.raise_for_status()
        return response.json()


def get_ticker(company_name: str) -> Optional[str]:
    """Get ticker symbol for a company name"""
    ticker = COMPANY_TICKERS.get(company_name.lower())
    if ticker:
        return ticker
    
    for name, tick in COMPANY_TICKERS.items():
        if name in company_name.lower() or company_name.lower() in name:
            return tick
    
    if company_name.upper() == company_name and len(company_name) <= 5:
        return company_name
    
    return None


# --- Tool 17: get_earnings_transcript ---

@tool
async def get_earnings_transcript(
    company: str,
    quarter: Optional[int] = None,
    year: Optional[int] = None
) -> str:
    """
    Get an earnings call transcript for a company.
    
    Use this when users ask for:
    - "Get Hexcel's last earnings call"
    - "Show me Toray's Q3 2024 transcript"
    - "What did Boeing say in their earnings?"
    
    Args:
        company: Company name or ticker symbol
        quarter: Quarter (1-4), defaults to most recent
        year: Year (YYYY), defaults to current year
    
    Returns:
        Earnings call transcript text
    """
    ticker = get_ticker(company)
    if not ticker:
        return f"Could not find ticker symbol for '{company}'. Try using the ticker directly (e.g., HXL, BA)."
    
    try:
        endpoint = f"earning_call_transcript/{ticker}"
        params = {}
        if quarter:
            params["quarter"] = quarter
        if year:
            params["year"] = year
        
        data = await fmp_request(endpoint, params)
        
        if not data:
            return f"No earnings transcript found for {company} ({ticker})."
        
        transcript = data[0] if isinstance(data, list) else data
        content = transcript.get("content", "")
        date = transcript.get("date", "Unknown date")
        q = transcript.get("quarter", "?")
        y = transcript.get("year", "?")
        
        if len(content) > 15000:
            content = content[:15000] + "\n\n... [Transcript truncated]"
        
        return f"# {company} ({ticker}) Earnings Call Transcript\n**Q{q} {y}** | {date}\n\n{content}"
    
    except Exception as e:
        logger.error(f"Error fetching earnings transcript: {e}")
        return f"Error retrieving earnings transcript for {company}: {str(e)}"


# --- Tool 18: analyze_earnings_themes ---

@tool
async def analyze_earnings_themes(
    companies: str,
    focus_areas: Optional[str] = None,
    quarters_back: int = 2
) -> str:
    """
    Analyze themes across multiple companies' earnings calls.
    
    This is a longer-running tool that fetches and analyzes multiple transcripts.
    
    Use this when users ask:
    - "What themes emerged from Hexcel and Toray's recent earnings?"
    - "Compare aerospace outlook from competitors"
    - "Analyze supply chain commentary from last 2 quarters"
    
    Args:
        companies: Comma-separated list of company names or tickers
        focus_areas: Specific topics to focus on (e.g., "aerospace, supply chain, pricing")
        quarters_back: How many quarters to analyze (default 2)
    
    Returns:
        Thematic analysis across companies
    """
    company_list = [c.strip() for c in companies.split(",")]
    
    if len(company_list) > 5:
        return "Please limit analysis to 5 companies at a time for performance."
    
    transcripts = []
    errors = []
    
    for company in company_list:
        ticker = get_ticker(company)
        if not ticker:
            errors.append(f"Could not find ticker for {company}")
            continue
        
        try:
            endpoint = f"earning_call_transcript/{ticker}"
            data = await fmp_request(endpoint, {"limit": quarters_back})
            
            if data:
                for t in data[:quarters_back]:
                    transcripts.append({
                        "company": company,
                        "ticker": ticker,
                        "quarter": t.get("quarter"),
                        "year": t.get("year"),
                        "content": t.get("content", "")[:10000]
                    })
        except Exception as e:
            errors.append(f"Error fetching {company}: {str(e)}")
    
    if not transcripts:
        return "Could not retrieve any transcripts. " + "; ".join(errors)
    
    focus_desc = f" focusing on {focus_areas}" if focus_areas else ""
    
    lines = [
        f"# Earnings Analysis: {', '.join(company_list)}",
        f"*Analyzing {len(transcripts)} transcripts{focus_desc}*",
        "",
        "## Transcripts Retrieved:"
    ]
    
    for t in transcripts:
        lines.append(f"- {t['company']} Q{t['quarter']} {t['year']}")
    
    lines.append("")
    lines.append("**Analysis Notes:** Review above transcripts for common themes, sentiment, and forward guidance.")
    
    return "\n".join(lines)


# --- Tool 19: get_earnings_calendar ---

@tool
async def get_earnings_calendar(days_ahead: int = 30) -> str:
    """
    Get upcoming earnings dates for tracked companies.
    
    Use this when users ask:
    - "When is Hexcel reporting?"
    - "Upcoming earnings dates"
    - "Who's reporting this month?"
    
    Args:
        days_ahead: How many days to look ahead (default 30)
    
    Returns:
        Upcoming earnings dates for tracked companies
    """
    from app.db.database import get_db
    from app.models.entities import EntityType
    
    db = get_db()
    competitors = await db.list_entities(entity_type=EntityType.COMPETITOR, is_active=True)
    
    tickers = []
    for comp in competitors:
        ticker = comp.metadata.ticker or get_ticker(comp.name)
        if ticker:
            tickers.append((comp.name, ticker))
    
    if not tickers:
        return "No tracked competitors have ticker symbols configured."
    
    try:
        from_date = datetime.now().strftime("%Y-%m-%d")
        to_date = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
        
        data = await fmp_request("earning_calendar", {"from": from_date, "to": to_date})
        
        if not data:
            return f"No earnings calendar data available for the next {days_ahead} days."
        
        ticker_set = {t[1].upper() for t in tickers}
        relevant = [d for d in data if d.get("symbol", "").upper() in ticker_set]
        
        if not relevant:
            return f"None of our tracked competitors are reporting in the next {days_ahead} days."
        
        lines = [f"**Upcoming Earnings** (next {days_ahead} days)\n"]
        
        for item in sorted(relevant, key=lambda x: x.get("date", "")):
            symbol = item.get("symbol", "")
            date = item.get("date", "TBD")
            company_name = next((name for name, tick in tickers if tick.upper() == symbol.upper()), symbol)
            lines.append(f"• **{company_name}** ({symbol}): {date}")
        
        return "\n".join(lines)
    
    except Exception as e:
        logger.error(f"Error getting earnings calendar: {e}")
        return f"Error retrieving earnings calendar: {str(e)}"


# --- Tool 20: compare_financials ---

@tool
async def compare_financials(
    companies: str,
    metrics: Optional[str] = None
) -> str:
    """
    Compare financial metrics across companies.
    
    Use this when users ask:
    - "Compare Hexcel vs Toray financials"
    - "How do competitor margins compare?"
    - "Revenue comparison across suppliers"
    
    Args:
        companies: Comma-separated list of company names or tickers
        metrics: Specific metrics to compare. Default: all key metrics
    
    Returns:
        Side-by-side financial comparison
    """
    company_list = [c.strip() for c in companies.split(",")]
    
    if len(company_list) > 5:
        return "Please limit comparison to 5 companies at a time."
    
    results = []
    
    for company in company_list:
        ticker = get_ticker(company)
        if not ticker:
            results.append({"company": company, "error": "Ticker not found"})
            continue
        
        try:
            ratios = await fmp_request(f"ratios/{ticker}", {"limit": 1})
            profile = await fmp_request(f"profile/{ticker}")
            
            if ratios and profile:
                ratio_data = ratios[0] if isinstance(ratios, list) else ratios
                profile_data = profile[0] if isinstance(profile, list) else profile
                
                results.append({
                    "company": company,
                    "ticker": ticker,
                    "market_cap": profile_data.get("mktCap"),
                    "revenue": profile_data.get("revenue"),
                    "gross_margin": ratio_data.get("grossProfitMargin"),
                    "operating_margin": ratio_data.get("operatingProfitMargin"),
                    "net_margin": ratio_data.get("netProfitMargin"),
                    "roe": ratio_data.get("returnOnEquity"),
                })
        except Exception as e:
            results.append({"company": company, "error": str(e)})
    
    # Format as table
    lines = ["# Financial Comparison\n"]
    lines.append("| Metric | " + " | ".join(r.get("company", "?") for r in results) + " |")
    lines.append("|--------|" + "|".join(["--------"] * len(results)) + "|")
    
    def fmt(val, pct=False, money=False):
        if val is None:
            return "N/A"
        if pct:
            return f"{val*100:.1f}%"
        if money:
            return f"${val/1e9:.1f}B" if val >= 1e9 else f"${val/1e6:.0f}M"
        return f"{val:.2f}"
    
    metrics_list = [
        ("Market Cap", "market_cap", True, False),
        ("Revenue", "revenue", True, False),
        ("Gross Margin", "gross_margin", False, True),
        ("Operating Margin", "operating_margin", False, True),
        ("Net Margin", "net_margin", False, True),
        ("ROE", "roe", False, True),
    ]
    
    for label, key, is_money, is_pct in metrics_list:
        values = [fmt(r.get(key), pct=is_pct, money=is_money) if "error" not in r else "Error" for r in results]
        lines.append(f"| {label} | " + " | ".join(values) + " |")
    
    return "\n".join(lines)


# --- Tool 21: get_commodity_trends ---

@tool
async def get_commodity_trends(commodity: str, period: str = "1Y") -> str:
    """
    Get historical commodity price trends.
    
    Use this when users ask:
    - "How have carbon fiber prices trended?"
    - "Aluminum pricing over the last year"
    - "Resin cost trends"
    
    Args:
        commodity: Commodity (aluminum, copper, oil, natural_gas)
        period: Time period (1M, 3M, 6M, 1Y, 2Y)
    
    Returns:
        Price trend analysis
    """
    commodity_symbols = {
        "aluminum": "ALUUSD",
        "copper": "CUUSD",
        "oil": "CLUSD",
        "crude": "CLUSD",
        "natural gas": "NGUSD",
        "gas": "NGUSD",
    }
    
    symbol = commodity_symbols.get(commodity.lower())
    if not symbol:
        return f"Commodity '{commodity}' not found. Available: {', '.join(commodity_symbols.keys())}"
    
    period_days = {"1M": 30, "3M": 90, "6M": 180, "1Y": 365, "2Y": 730}
    days = period_days.get(period.upper(), 365)
    
    try:
        data = await fmp_request(f"historical-price-full/{symbol}")
        
        if not data or "historical" not in data:
            return f"No historical data available for {commodity}."
        
        historical = data["historical"][:days]
        prices = [d.get("close", 0) for d in historical]
        
        current = prices[0]
        oldest = prices[-1]
        high = max(prices)
        low = min(prices)
        change = ((current - oldest) / oldest) * 100 if oldest else 0
        
        trend = "📈 Up" if change > 5 else "📉 Down" if change < -5 else "➡️ Stable"
        
        return f"""# {commodity.title()} Price Trends
*{period} period*

**Current Price:** ${current:.2f}
**{period} Change:** {change:+.1f}% {trend}

**Range:** ${low:.2f} - ${high:.2f}
"""
    
    except Exception as e:
        logger.error(f"Error getting commodity trends: {e}")
        return f"Error retrieving commodity data: {str(e)}"


# --- Tool 22: get_stock_performance ---

@tool
async def get_stock_performance(company: str, period: str = "1Y") -> str:
    """
    Get stock performance for a company.
    
    Use this when users ask:
    - "How is Hexcel's stock doing?"
    - "Toray stock performance this year"
    
    Args:
        company: Company name or ticker
        period: Time period (1M, 3M, 6M, 1Y, YTD)
    
    Returns:
        Stock performance summary
    """
    ticker = get_ticker(company)
    if not ticker:
        return f"Could not find ticker for '{company}'."
    
    try:
        quote = await fmp_request(f"quote/{ticker}")
        
        if not quote:
            return f"No quote data available for {company} ({ticker})."
        
        q = quote[0] if isinstance(quote, list) else quote
        
        price = q.get("price", 0)
        change = q.get("change", 0)
        change_pct = q.get("changesPercentage", 0)
        year_high = q.get("yearHigh", 0)
        year_low = q.get("yearLow", 0)
        market_cap = q.get("marketCap", 0)
        
        trend = "📈" if change > 0 else "📉" if change < 0 else "➡️"
        
        return f"""# {company} ({ticker}) Stock Performance

**Current:** ${price:.2f} {trend} {change:+.2f} ({change_pct:+.1f}%)

**52-Week Range:** ${year_low:.2f} - ${year_high:.2f}
**Market Cap:** ${market_cap/1e9:.1f}B
"""
    
    except Exception as e:
        logger.error(f"Error getting stock performance: {e}")
        return f"Error retrieving stock data: {str(e)}"


# ============================================================================
# SECTION 4: PRODUCT INTELLIGENCE TOOLS (6 tools)
# ============================================================================
# These tools provide product catalog and competitive intelligence.
# Available to both agents.

# Mock product database (in production, this would be a real database)
MOCK_PRODUCTS = [
    {"id": "HXL-AS4", "supplier": "Hexcel", "name": "AS4 Carbon Fiber", "category": "carbon_fiber", "industries": ["aerospace", "defense"], "specs": {"tensile_strength": "4,433 MPa", "tensile_modulus": "231 GPa"}},
    {"id": "HXL-IM7", "supplier": "Hexcel", "name": "IM7 Carbon Fiber", "category": "carbon_fiber", "industries": ["aerospace", "defense", "sporting_goods"], "specs": {"tensile_strength": "5,310 MPa", "tensile_modulus": "276 GPa"}},
    {"id": "TOR-T700S", "supplier": "Toray", "name": "T700S Carbon Fiber", "category": "carbon_fiber", "industries": ["aerospace", "automotive", "wind_energy"], "specs": {"tensile_strength": "4,900 MPa", "tensile_modulus": "230 GPa"}},
    {"id": "TOR-T800S", "supplier": "Toray", "name": "T800S Carbon Fiber", "category": "carbon_fiber", "industries": ["aerospace", "defense"], "specs": {"tensile_strength": "5,880 MPa", "tensile_modulus": "294 GPa"}},
    {"id": "HXL-M21", "supplier": "Hexcel", "name": "HexPly M21", "category": "prepreg", "industries": ["aerospace"], "specs": {"resin_type": "Toughened Epoxy", "cure_temp": "180°C"}},
    {"id": "TOR-3900", "supplier": "Toray", "name": "Toray 3900 Series", "category": "prepreg", "industries": ["aerospace"], "specs": {"resin_type": "Toughened Epoxy", "cure_temp": "180°C"}},
    {"id": "OC-SE1500", "supplier": "Owens Corning", "name": "SE1500 E-Glass", "category": "glass_fiber", "industries": ["wind_energy", "marine"], "specs": {"tensile_strength": "3,445 MPa"}},
]

C1_CATALOG_IDS = ["HXL-AS4", "HXL-IM7", "TOR-T700S", "TOR-T800S", "HXL-M21", "TOR-3900", "OC-SE1500"]


def search_products(supplier=None, category=None, industry=None, query=None):
    results = MOCK_PRODUCTS.copy()
    if supplier:
        results = [p for p in results if supplier.lower() in p["supplier"].lower()]
    if category:
        results = [p for p in results if category.lower() in p["category"].lower()]
    if industry:
        results = [p for p in results if industry.lower() in [i.lower() for i in p.get("industries", [])]]
    if query:
        q = query.lower()
        results = [p for p in results if q in p["name"].lower() or q in p["supplier"].lower()]
    return results


def is_in_c1_catalog(product_id: str) -> bool:
    return product_id in C1_CATALOG_IDS


# --- Tool 23: search_competitor_products ---

@tool
async def search_competitor_products(
    supplier: Optional[str] = None,
    category: Optional[str] = None,
    industry: Optional[str] = None,
    query: Optional[str] = None
) -> str:
    """
    Search competitor product catalogs.
    
    Use this when users ask:
    - "What prepreg SKUs does Hexcel offer?"
    - "Show me Toray's aerospace products"
    - "Find carbon fiber products for wind energy"
    
    Args:
        supplier: Filter by supplier name (Hexcel, Toray, etc.)
        category: Product category (carbon_fiber, glass_fiber, prepreg, epoxy_resin)
        industry: Target industry (aerospace, automotive, marine, wind_energy)
        query: Free text search
    
    Returns:
        List of matching products
    """
    products = search_products(supplier, category, industry, query)
    
    if not products:
        return "No products found matching the criteria."
    
    lines = [f"**Found {len(products)} products**\n"]
    
    by_supplier = {}
    for p in products:
        if p["supplier"] not in by_supplier:
            by_supplier[p["supplier"]] = []
        by_supplier[p["supplier"]].append(p)
    
    for supplier_name, supplier_products in by_supplier.items():
        lines.append(f"## {supplier_name}")
        for p in supplier_products:
            in_catalog = "✅ In C1 Catalog" if is_in_c1_catalog(p["id"]) else ""
            lines.append(f"• **{p['name']}** ({p['id']}) {in_catalog}")
        lines.append("")
    
    return "\n".join(lines)


# --- Tool 24: get_product_specs ---

@tool
async def get_product_specs(product_name: str) -> str:
    """
    Get detailed specifications for a product.
    
    Use this when users ask:
    - "What are the specs for T700S?"
    - "Tell me about HexPly M21"
    
    Args:
        product_name: Product name or ID
    
    Returns:
        Detailed product specifications
    """
    products = search_products(query=product_name)
    
    if not products:
        return f"Product '{product_name}' not found."
    
    p = products[0]
    
    lines = [
        f"# {p['name']}",
        f"**Supplier:** {p['supplier']}",
        f"**ID:** {p['id']}",
        f"**Category:** {p['category'].replace('_', ' ').title()}",
        f"**Industries:** {', '.join(p.get('industries', []))}",
        "",
        "## Specifications"
    ]
    
    for key, value in p.get("specs", {}).items():
        lines.append(f"• **{key.replace('_', ' ').title()}:** {value}")
    
    if is_in_c1_catalog(p["id"]):
        lines.append("\n✅ **Available through Composites One**")
    
    return "\n".join(lines)


# --- Tool 25: compare_product_specs ---

@tool
async def compare_product_specs(product1: str, product2: str) -> str:
    """
    Compare specifications between two products.
    
    Use this when users ask:
    - "Compare Hexcel M21 vs Toray 3900"
    - "How does T700S compare to AS4?"
    
    Args:
        product1: First product name or ID
        product2: Second product name or ID
    
    Returns:
        Side-by-side specification comparison
    """
    p1_results = search_products(query=product1)
    p2_results = search_products(query=product2)
    
    if not p1_results:
        return f"Product '{product1}' not found."
    if not p2_results:
        return f"Product '{product2}' not found."
    
    p1, p2 = p1_results[0], p2_results[0]
    
    lines = [
        "# Specification Comparison",
        "",
        f"| Attribute | {p1['name']} | {p2['name']} |",
        "|-----------|-------------|-------------|",
        f"| **Supplier** | {p1['supplier']} | {p2['supplier']} |",
        f"| **Category** | {p1['category']} | {p2['category']} |",
    ]
    
    all_keys = set(p1.get("specs", {}).keys()) | set(p2.get("specs", {}).keys())
    
    for key in sorted(all_keys):
        v1 = p1.get("specs", {}).get(key, "N/A")
        v2 = p2.get("specs", {}).get(key, "N/A")
        lines.append(f"| **{key.replace('_', ' ').title()}** | {v1} | {v2} |")
    
    c1_1 = "✅ Yes" if is_in_c1_catalog(p1["id"]) else "❌ No"
    c1_2 = "✅ Yes" if is_in_c1_catalog(p2["id"]) else "❌ No"
    lines.append(f"| **C1 Catalog** | {c1_1} | {c1_2} |")
    
    return "\n".join(lines)


# --- Tool 26: find_product_gaps ---

@tool
async def find_product_gaps(category: str, industry: Optional[str] = None) -> str:
    """
    Identify product gaps vs competition.
    
    Use this when users ask:
    - "Where do we have gaps vs Gurit in marine?"
    - "What aerospace prepregs don't we carry?"
    
    Args:
        category: Product category to analyze
        industry: Optional industry filter
    
    Returns:
        Gap analysis
    """
    all_products = search_products(category=category, industry=industry)
    
    if not all_products:
        return f"No products found in category '{category}'."
    
    we_carry = [p for p in all_products if is_in_c1_catalog(p["id"])]
    gaps = [p for p in all_products if not is_in_c1_catalog(p["id"])]
    
    lines = [
        f"# Product Gap Analysis: {category.replace('_', ' ').title()}",
        "",
        f"**Total Products:** {len(all_products)}",
        f"**We Carry:** {len(we_carry)} ({len(we_carry)/len(all_products)*100:.0f}%)",
        f"**Gaps:** {len(gaps)} ({len(gaps)/len(all_products)*100:.0f}%)",
        ""
    ]
    
    if we_carry:
        lines.append("## ✅ Products We Carry")
        for p in we_carry:
            lines.append(f"• {p['name']} ({p['supplier']})")
        lines.append("")
    
    if gaps:
        lines.append("## ❌ Gaps")
        for p in gaps:
            lines.append(f"• {p['name']} ({p['supplier']})")
    
    return "\n".join(lines)


# --- Tool 27: get_c1_catalog ---

@tool
async def get_c1_catalog(
    category: Optional[str] = None,
    industry: Optional[str] = None
) -> str:
    """
    Get Composites One's product catalog.
    
    Use this when users ask:
    - "What do we distribute?"
    - "Show me our aerospace products"
    
    Args:
        category: Filter by category
        industry: Filter by industry
    
    Returns:
        C1's product catalog
    """
    all_products = search_products(category=category, industry=industry)
    c1_products = [p for p in all_products if is_in_c1_catalog(p["id"])]
    
    if not c1_products:
        return "No C1 products found matching criteria."
    
    lines = [f"# Composites One Catalog\n**{len(c1_products)} products**\n"]
    
    by_supplier = {}
    for p in c1_products:
        if p["supplier"] not in by_supplier:
            by_supplier[p["supplier"]] = []
        by_supplier[p["supplier"]].append(p)
    
    for supplier, products in by_supplier.items():
        lines.append(f"## {supplier}")
        for p in products:
            lines.append(f"• **{p['name']}** ({p['id']})")
        lines.append("")
    
    return "\n".join(lines)


# --- Tool 28: suggest_alternatives ---

@tool
async def suggest_alternatives(product_name: str) -> str:
    """
    Suggest alternative products to one we don't carry.
    
    Use this when users ask:
    - "What can we offer instead of [competitor product]?"
    - "Alternatives to Gurit prepreg"
    
    Args:
        product_name: Product to find alternatives for
    
    Returns:
        Alternative products from our catalog
    """
    products = search_products(query=product_name)
    
    if not products:
        return f"Product '{product_name}' not found."
    
    target = products[0]
    all_in_category = search_products(category=target["category"])
    alternatives = [p for p in all_in_category if is_in_c1_catalog(p["id"]) and p["id"] != target["id"]]
    
    if not alternatives:
        return f"No alternatives found in C1 catalog for {target['name']}."
    
    in_catalog = "✅ Yes" if is_in_c1_catalog(target["id"]) else "❌ No"
    
    lines = [
        f"# Alternatives to {target['name']}",
        f"**Supplier:** {target['supplier']}",
        f"**In C1 Catalog:** {in_catalog}",
        "",
        "## Recommended Alternatives",
        ""
    ]
    
    for i, alt in enumerate(alternatives[:5], 1):
        lines.append(f"**{i}. {alt['name']}** ({alt['supplier']})")
    
    return "\n".join(lines)


# ============================================================================
# TOOL REGISTRY
# ============================================================================

ALL_TOOLS = [
    # Tracking Management (9)
    list_tracked_entities,
    count_tracked_entities,
    add_tracked_entity,
    add_multiple_entities,
    remove_tracked_entity,
    update_tracked_entity,
    get_tracking_summary,
    search_tracked_entities,
    get_entity_details,
    
    # Corpus Query (7)
    query_corpus,
    get_digest,
    get_entity_mentions,
    get_corpus_stats,
    get_priority_items,
    get_competitor_activity,
    get_market_signals,
    
    # Research Analytics (6)
    get_earnings_transcript,
    analyze_earnings_themes,
    get_earnings_calendar,
    compare_financials,
    get_commodity_trends,
    get_stock_performance,
    
    # Product Intelligence (6)
    search_competitor_products,
    get_product_specs,
    compare_product_specs,
    find_product_gaps,
    get_c1_catalog,
    suggest_alternatives,
]

# Tools for Intelligence Agent (excludes deep research tools)
INTELLIGENCE_AGENT_TOOLS = [t for t in ALL_TOOLS if t.name not in [
    "analyze_earnings_themes",
    "compare_financials", 
    "find_product_gaps",
]]

# Tools for Research Agent (all tools)
RESEARCH_AGENT_TOOLS = ALL_TOOLS


if __name__ == "__main__":
    print(f"\n{'='*60}")
    print("C1 INTELLIGENCE HUB - COMPLETE TOOL REFERENCE")
    print(f"{'='*60}")
    print(f"\nTotal Tools: {len(ALL_TOOLS)}")
    print(f"Intelligence Agent: {len(INTELLIGENCE_AGENT_TOOLS)} tools")
    print(f"Research Agent: {len(RESEARCH_AGENT_TOOLS)} tools")
    print(f"\n{'='*60}")
    
    categories = {
        "Tracking Management": ALL_TOOLS[:9],
        "Corpus Query": ALL_TOOLS[9:16],
        "Research Analytics": ALL_TOOLS[16:22],
        "Product Intelligence": ALL_TOOLS[22:28],
    }
    
    for category, tools in categories.items():
        print(f"\n{category} ({len(tools)} tools)")
        print("-" * 40)
        for tool in tools:
            print(f"  • {tool.name}")
