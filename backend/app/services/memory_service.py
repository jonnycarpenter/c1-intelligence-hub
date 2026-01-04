"""Memory service for long-term organizational memory.

Handles:
- Org preferences (priorities, blocks)
- Memory log (saved briefings, research exports)
- Vector search with time-weighted scoring
- Pin/unpin with team limits
"""

import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel

from app.config.settings import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Constants
MAX_PINS_PER_TEAM = 10
MEMORY_EXPIRY_DAYS = 60
TEAMS = ["Sales East", "Sales West", "Marketing", "Product/Supplier", "All Others"]


# =============================================================================
# Data Models
# =============================================================================

class OrgPreference(BaseModel):
    """Organization preference (priority or block)."""
    preference_id: str
    preference_type: Literal["prioritize", "block"]
    target: str
    description: Optional[str] = None
    team: Optional[str] = None  # None = org-wide
    active: bool = True
    created_by: str = "anonymous"
    created_at: datetime = datetime.utcnow()


class MemoryLogEntry(BaseModel):
    """Logged memory entry from briefing or research."""
    memory_id: str
    source: Literal["briefing", "research_export"]
    title: str
    content: str
    query: str
    entities: List[str] = []
    team: Optional[str] = None
    pinned: bool = False
    expires_at: Optional[datetime] = None
    created_by: str = "anonymous"
    created_at: datetime = datetime.utcnow()
    # Computed fields for retrieval
    similarity: Optional[float] = None
    confidence: Optional[Literal["high", "medium", "low"]] = None
    is_deprioritized: bool = False


class MemoryContext(BaseModel):
    """Context bundle for agent prompts."""
    preferences: Dict[str, List[Dict]]
    memories: List[Dict]
    prompt_addition: str
    proactive_intro: Optional[str] = None


# =============================================================================
# BigQuery Client Helper
# =============================================================================

def _get_bigquery_client():
    """Get BigQuery client (lazy-loaded)."""
    if not settings.gcp_project_id:
        logger.warning("GCP not configured, memory features disabled")
        return None
    try:
        from google.cloud import bigquery
        return bigquery.Client(project=settings.gcp_project_id)
    except ImportError:
        logger.warning("google-cloud-bigquery not installed")
        return None
    except Exception as e:
        logger.error(f"Could not create BigQuery client: {e}")
        return None


def _get_vertex_embedding(text: str) -> Optional[List[float]]:
    """Generate embedding using Vertex AI."""
    if not settings.gcp_project_id:
        return None
    try:
        from google.cloud import aiplatform
        from vertexai.language_models import TextEmbeddingModel
        
        aiplatform.init(project=settings.gcp_project_id, location=settings.gcp_location)
        model = TextEmbeddingModel.from_pretrained("text-embedding-004")
        embeddings = model.get_embeddings([text])
        return embeddings[0].values
    except Exception as e:
        logger.error(f"Failed to generate embedding: {e}")
        return None


# =============================================================================
# Preferences Service
# =============================================================================

async def get_org_preferences(user_team: Optional[str] = None) -> Dict[str, List[Dict]]:
    """
    Get preferences for the user's team + org-wide preferences.
    Team-specific preferences are merged with org-wide (team=null).
    """
    client = _get_bigquery_client()
    if not client:
        return {"priorities": [], "blocks": []}
    
    try:
        query = f"""
            SELECT preference_id, preference_type, target, description, team
            FROM `{settings.gcp_project_id}.{settings.gcp_dataset_id}.org_preferences`
            WHERE active = TRUE
              AND (team IS NULL OR team = @userTeam)
            ORDER BY 
              CASE WHEN team IS NULL THEN 1 ELSE 0 END,
              created_at DESC
        """
        
        job_config = None
        if user_team:
            from google.cloud import bigquery
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("userTeam", "STRING", user_team)
                ]
            )
        
        rows = list(client.query(query, job_config=job_config).result())
        
        return {
            "priorities": [
                {"id": r.preference_id, "target": r.target, "description": r.description, "team": r.team}
                for r in rows if r.preference_type == "prioritize"
            ],
            "blocks": [
                {"id": r.preference_id, "target": r.target, "description": r.description, "team": r.team}
                for r in rows if r.preference_type == "block"
            ]
        }
    except Exception as e:
        logger.error(f"Error fetching preferences: {e}")
        return {"priorities": [], "blocks": []}


async def add_preference(
    pref_type: Literal["prioritize", "block"],
    target: str,
    description: Optional[str],
    user_name: str,
    user_team: Optional[str] = None
) -> Dict[str, Any]:
    """Add a new preference."""
    client = _get_bigquery_client()
    if not client:
        return {"success": False, "error": "Database not configured"}
    
    try:
        from google.cloud import bigquery
        
        pref_id = str(uuid.uuid4())
        query = f"""
            INSERT INTO `{settings.gcp_project_id}.{settings.gcp_dataset_id}.org_preferences`
            (preference_id, preference_type, target, description, team, active, created_by, created_at)
            VALUES (@prefId, @prefType, @target, @description, @team, TRUE, @createdBy, CURRENT_TIMESTAMP())
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("prefId", "STRING", pref_id),
                bigquery.ScalarQueryParameter("prefType", "STRING", pref_type),
                bigquery.ScalarQueryParameter("target", "STRING", target),
                bigquery.ScalarQueryParameter("description", "STRING", description),
                bigquery.ScalarQueryParameter("team", "STRING", user_team),
                bigquery.ScalarQueryParameter("createdBy", "STRING", user_name),
            ]
        )
        
        client.query(query, job_config=job_config).result()
        logger.info(f"Added preference: {pref_type} - {target}")
        
        return {"success": True, "preference_id": pref_id}
    except Exception as e:
        logger.error(f"Error adding preference: {e}")
        return {"success": False, "error": str(e)}


async def remove_preference(preference_id: str) -> Dict[str, Any]:
    """Remove (deactivate) a preference."""
    client = _get_bigquery_client()
    if not client:
        return {"success": False, "error": "Database not configured"}
    
    try:
        from google.cloud import bigquery
        
        query = f"""
            UPDATE `{settings.gcp_project_id}.{settings.gcp_dataset_id}.org_preferences`
            SET active = FALSE
            WHERE preference_id = @prefId
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("prefId", "STRING", preference_id)
            ]
        )
        
        client.query(query, job_config=job_config).result()
        return {"success": True}
    except Exception as e:
        logger.error(f"Error removing preference: {e}")
        return {"success": False, "error": str(e)}


# =============================================================================
# Memory Log Service
# =============================================================================

async def save_to_memory(
    source: Literal["briefing", "research_export"],
    question: str,
    answer: str,
    sources: Optional[List[Dict]] = None,
    confidence: Optional[str] = None,
    tags: Optional[List[str]] = None,
    user_name: str = "anonymous",
    user_team: Optional[str] = None
) -> Dict[str, Any]:
    """Save a briefing or research export to memory log."""
    client = _get_bigquery_client()
    if not client:
        # Fallback: log but don't fail
        logger.warning("Memory save skipped - database not configured")
        return {"success": True, "memory_id": None, "note": "Memory storage not configured"}
    
    try:
        from google.cloud import bigquery
        
        memory_id = str(uuid.uuid4())
        expires_at = datetime.utcnow() + timedelta(days=MEMORY_EXPIRY_DAYS)
        
        # Generate embedding for vector search
        embedding_text = f"{question}\n{answer}"
        embedding = _get_vertex_embedding(embedding_text)
        
        # Extract entities from tags or content
        entities = tags or []
        
        # Truncate title to first 100 chars of question
        title = question[:100] if len(question) > 100 else question
        
        query = f"""
            INSERT INTO `{settings.gcp_project_id}.{settings.gcp_dataset_id}.memory_log`
            (memory_id, source, title, content, query, entities, embedding, team, pinned, expires_at, created_by, created_at)
            VALUES (@memoryId, @source, @title, @content, @query, @entities, @embedding, @team, FALSE, @expiresAt, @createdBy, CURRENT_TIMESTAMP())
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("memoryId", "STRING", memory_id),
                bigquery.ScalarQueryParameter("source", "STRING", source),
                bigquery.ScalarQueryParameter("title", "STRING", title),
                bigquery.ScalarQueryParameter("content", "STRING", answer),
                bigquery.ScalarQueryParameter("query", "STRING", question),
                bigquery.ArrayQueryParameter("entities", "STRING", entities),
                bigquery.ArrayQueryParameter("embedding", "FLOAT64", embedding or []),
                bigquery.ScalarQueryParameter("team", "STRING", user_team),
                bigquery.ScalarQueryParameter("expiresAt", "TIMESTAMP", expires_at.isoformat()),
                bigquery.ScalarQueryParameter("createdBy", "STRING", user_name),
            ]
        )
        
        client.query(query, job_config=job_config).result()
        logger.info(f"Saved to memory: {source} - {title[:50]}...")
        
        return {"success": True, "memory_id": memory_id}
    except Exception as e:
        logger.error(f"Error saving to memory: {e}")
        return {"success": False, "error": str(e)}


async def get_relevant_memories(
    query: str,
    user_team: Optional[str] = None,
    limit: int = 5
) -> List[Dict[str, Any]]:
    """
    Retrieve relevant memories with time-weighted scoring and team prioritization.
    
    Scoring formula:
      final_score = base_similarity * time_decay * team_boost * block_penalty
    
    Where:
      - base_similarity: cosine similarity from vector search (0.0 to 1.0)
      - time_decay: linear decay from 1.0 to 0.3 over 60 days
      - team_boost: 1.2x for same team, 1.0 otherwise
      - block_penalty: 0.3x if topic is blocked, 1.0 otherwise
    """
    client = _get_bigquery_client()
    if not client:
        return []
    
    try:
        from google.cloud import bigquery
        
        # Generate embedding for query
        query_embedding = _get_vertex_embedding(query)
        if not query_embedding:
            logger.warning("Could not generate embedding for query")
            return []
        
        # Get blocked topics for penalty calculation
        preferences = await get_org_preferences(user_team)
        blocked_topics = [b["target"].lower() for b in preferences.get("blocks", [])]
        
        # Vector search with time-weighted scoring
        search_query = f"""
            WITH memory_scores AS (
              SELECT 
                memory_id,
                source,
                title,
                content,
                query,
                entities,
                team,
                pinned,
                expires_at,
                created_by,
                created_at,
                -- Base similarity (cosine distance converted to similarity)
                1 - ML.DISTANCE(embedding, @queryEmbedding, 'COSINE') AS base_similarity,
                -- Time decay: linear from 1.0 to 0.3 over 60 days
                GREATEST(0.3, 1.0 - (0.7 * TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), created_at, DAY) / 60.0)) AS time_decay,
                -- Team boost: 1.2x for same team
                CASE WHEN team = @userTeam THEN 1.2 ELSE 1.0 END AS team_boost
              FROM `{settings.gcp_project_id}.{settings.gcp_dataset_id}.memory_log`
              WHERE (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP())
                AND (pinned = TRUE OR expires_at > CURRENT_TIMESTAMP())
            )
            SELECT 
              *,
              base_similarity * time_decay * team_boost AS final_score,
              CASE 
                WHEN base_similarity >= 0.8 THEN 'high'
                WHEN base_similarity >= 0.6 THEN 'medium'
                ELSE 'low'
              END AS confidence
            FROM memory_scores
            WHERE base_similarity > 0.3
            ORDER BY final_score DESC
            LIMIT @limit
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ArrayQueryParameter("queryEmbedding", "FLOAT64", query_embedding),
                bigquery.ScalarQueryParameter("userTeam", "STRING", user_team or "All Others"),
                bigquery.ScalarQueryParameter("limit", "INT64", limit),
            ]
        )
        
        rows = list(client.query(search_query, job_config=job_config).result())
        
        memories = []
        for row in rows:
            # Check if any blocked topic appears in content
            content_lower = (row.content or "").lower()
            is_deprioritized = any(topic in content_lower for topic in blocked_topics)
            
            # Apply block penalty (soft deprioritization)
            final_score = row.final_score * (0.3 if is_deprioritized else 1.0)
            
            memories.append({
                "id": row.memory_id,
                "source": row.source,
                "title": row.title,
                "content": row.content[:500] if row.content else "",  # Truncate for context
                "query": row.query,
                "team": row.team,
                "pinned": row.pinned,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "similarity": row.base_similarity,
                "confidence": row.confidence,
                "is_deprioritized": is_deprioritized,
                "final_score": final_score,
            })
        
        # Re-sort after applying block penalty
        memories.sort(key=lambda m: m["final_score"], reverse=True)
        
        return memories[:limit]
    except Exception as e:
        logger.error(f"Error retrieving memories: {e}")
        return []


async def pin_memory(memory_id: str, user_team: str) -> Dict[str, Any]:
    """Pin a memory (max 10 per team)."""
    client = _get_bigquery_client()
    if not client:
        return {"success": False, "error": "Database not configured"}
    
    try:
        from google.cloud import bigquery
        
        # Check current pin count for team
        count_query = f"""
            SELECT COUNT(*) as pin_count 
            FROM `{settings.gcp_project_id}.{settings.gcp_dataset_id}.memory_log`
            WHERE team = @team AND pinned = TRUE
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("team", "STRING", user_team)
            ]
        )
        
        result = list(client.query(count_query, job_config=job_config).result())
        pin_count = result[0].pin_count if result else 0
        
        if pin_count >= MAX_PINS_PER_TEAM:
            return {
                "success": False,
                "error": f"Maximum {MAX_PINS_PER_TEAM} pinned memories per team. Unpin something first."
            }
        
        # Pin the memory (remove expiration)
        pin_query = f"""
            UPDATE `{settings.gcp_project_id}.{settings.gcp_dataset_id}.memory_log`
            SET pinned = TRUE, expires_at = NULL
            WHERE memory_id = @memoryId
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("memoryId", "STRING", memory_id)
            ]
        )
        
        client.query(pin_query, job_config=job_config).result()
        logger.info(f"Pinned memory: {memory_id}")
        
        return {"success": True}
    except Exception as e:
        logger.error(f"Error pinning memory: {e}")
        return {"success": False, "error": str(e)}


async def unpin_memory(memory_id: str) -> Dict[str, Any]:
    """Unpin a memory and set new expiration."""
    client = _get_bigquery_client()
    if not client:
        return {"success": False, "error": "Database not configured"}
    
    try:
        from google.cloud import bigquery
        
        expires_at = datetime.utcnow() + timedelta(days=MEMORY_EXPIRY_DAYS)
        
        query = f"""
            UPDATE `{settings.gcp_project_id}.{settings.gcp_dataset_id}.memory_log`
            SET pinned = FALSE, expires_at = @expiresAt
            WHERE memory_id = @memoryId
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("memoryId", "STRING", memory_id),
                bigquery.ScalarQueryParameter("expiresAt", "TIMESTAMP", expires_at.isoformat()),
            ]
        )
        
        client.query(query, job_config=job_config).result()
        logger.info(f"Unpinned memory: {memory_id}")
        
        return {"success": True}
    except Exception as e:
        logger.error(f"Error unpinning memory: {e}")
        return {"success": False, "error": str(e)}


async def block_topic(topic: str, user_team: str, user_name: str) -> Dict[str, Any]:
    """Add a topic to the block list (soft deprioritization)."""
    return await add_preference(
        pref_type="block",
        target=topic,
        description=f"Blocked by {user_name}",
        user_name=user_name,
        user_team=user_team
    )


# =============================================================================
# Memory Log List & Delete (for UI)
# =============================================================================

async def list_memory_log(
    user_team: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    pinned_only: bool = False
) -> Dict[str, Any]:
    """
    List memories for the Memory Log UI.
    Returns team-visible memories (own team + All Others).
    """
    client = _get_bigquery_client()
    if not client:
        # Return mock data for development
        return {
            "items": [],
            "total": 0
        }
    
    try:
        from google.cloud import bigquery
        
        # Build WHERE clause for team visibility
        team_filter = ""
        if user_team and user_team != "All Others":
            team_filter = "AND (team = @team OR team = 'All Others' OR team IS NULL)"
        
        pinned_filter = "AND pinned = TRUE" if pinned_only else ""
        
        # Get total count
        count_query = f"""
            SELECT COUNT(*) as total
            FROM `{settings.gcp_project_id}.{settings.gcp_dataset_id}.memory_log`
            WHERE (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP() OR pinned = TRUE)
            {team_filter}
            {pinned_filter}
        """
        
        # Get paginated items
        items_query = f"""
            SELECT 
                memory_id as id,
                source,
                title,
                content as answer,
                query as question,
                entities as tags,
                team,
                pinned,
                expires_at,
                created_by as user_name,
                created_at
            FROM `{settings.gcp_project_id}.{settings.gcp_dataset_id}.memory_log`
            WHERE (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP() OR pinned = TRUE)
            {team_filter}
            {pinned_filter}
            ORDER BY pinned DESC, created_at DESC
            LIMIT @limit
            OFFSET @offset
        """
        
        params = [
            bigquery.ScalarQueryParameter("limit", "INT64", limit),
            bigquery.ScalarQueryParameter("offset", "INT64", offset),
        ]
        
        if user_team and user_team != "All Others":
            params.append(bigquery.ScalarQueryParameter("team", "STRING", user_team))
        
        job_config = bigquery.QueryJobConfig(query_parameters=params)
        
        # Execute count query
        count_result = list(client.query(count_query, job_config=job_config).result())
        total = count_result[0].total if count_result else 0
        
        # Execute items query
        items_result = client.query(items_query, job_config=job_config).result()
        
        items = []
        for row in items_result:
            items.append({
                "id": row.id,
                "source": row.source,
                "question": row.question or row.title,
                "answer": row.answer[:500] if row.answer else "",  # Truncate for list view
                "tags": list(row.tags) if row.tags else [],
                "team": row.team,
                "pinned": row.pinned,
                "expires_at": row.expires_at.isoformat() if row.expires_at else None,
                "user_name": row.user_name,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            })
        
        return {
            "items": items,
            "total": total
        }
    except Exception as e:
        logger.error(f"Error listing memory log: {e}")
        return {"items": [], "total": 0}


async def delete_memory(memory_id: str) -> Dict[str, Any]:
    """Delete a specific memory entry."""
    client = _get_bigquery_client()
    if not client:
        return {"success": False, "error": "Database not configured"}
    
    try:
        from google.cloud import bigquery
        
        query = f"""
            DELETE FROM `{settings.gcp_project_id}.{settings.gcp_dataset_id}.memory_log`
            WHERE memory_id = @memoryId
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("memoryId", "STRING", memory_id)
            ]
        )
        
        result = client.query(query, job_config=job_config).result()
        deleted_count = result.num_dml_affected_rows or 0
        
        if deleted_count > 0:
            logger.info(f"Deleted memory: {memory_id}")
            return {"success": True}
        else:
            return {"success": False, "error": "Memory not found"}
    except Exception as e:
        logger.error(f"Error deleting memory: {e}")
        return {"success": False, "error": str(e)}


# =============================================================================
# Cleanup Job
# =============================================================================

async def cleanup_expired_memories() -> Dict[str, Any]:
    """Delete expired, unpinned memories. Run daily via Cloud Scheduler."""
    client = _get_bigquery_client()
    if not client:
        return {"success": False, "error": "Database not configured"}
    
    try:
        query = f"""
            DELETE FROM `{settings.gcp_project_id}.{settings.gcp_dataset_id}.memory_log`
            WHERE expires_at IS NOT NULL 
              AND expires_at < CURRENT_TIMESTAMP()
              AND pinned = FALSE
        """
        
        result = client.query(query).result()
        deleted_count = result.num_dml_affected_rows or 0
        
        logger.info(f"Memory cleanup: deleted {deleted_count} expired memories")
        
        return {"success": True, "deleted_count": deleted_count}
    except Exception as e:
        logger.error(f"Error in memory cleanup: {e}")
        return {"success": False, "error": str(e)}


# =============================================================================
# Context Building for Agent Prompts
# =============================================================================

def format_preferences_for_prompt(preferences: Dict[str, List[Dict]]) -> str:
    """Format preferences for injection into agent prompts."""
    rules = ""
    
    priority_targets = [p["target"] for p in preferences.get("priorities", [])]
    block_targets = [b["target"] for b in preferences.get("blocks", [])]
    
    if priority_targets:
        rules += f"\nPRIORITY TOPICS - Pay special attention to: {', '.join(priority_targets)}"
    
    if block_targets:
        rules += f"\nSOFT EXCLUDE - Deprioritize (but don't completely hide) information about: {', '.join(block_targets)}"
    
    return rules or "\nNo specific preferences set."


def format_memories_for_prompt(memories: List[Dict]) -> str:
    """Format retrieved memories for agent context."""
    if not memories:
        return ""
    
    high_conf = [m for m in memories if m.get("confidence") == "high" and not m.get("is_deprioritized")]
    
    if not high_conf:
        return ""
    
    lines = ["\n\nRELEVANT PAST CONTEXT:"]
    for m in high_conf[:3]:  # Max 3 memories
        date_str = m.get("created_at", "")[:10] if m.get("created_at") else "unknown"
        team_note = f" ({m['team']})" if m.get("team") else ""
        lines.append(f"- [{date_str}]{team_note} {m['title']}: {m['content'][:200]}...")
    
    return "\n".join(lines)


def generate_proactive_intro(memories: List[Dict]) -> Optional[str]:
    """
    Generate the "I remember when..." intro for agent responses.
    Creates the "part of the team" feel by proactively referencing past work.
    """
    high_conf = [m for m in memories if m.get("confidence") == "high" and not m.get("is_deprioritized")]
    
    if not high_conf:
        return None
    
    most_relevant = high_conf[0]
    date_str = most_relevant.get("created_at", "")[:10] if most_relevant.get("created_at") else "recently"
    team_note = f"your {most_relevant['team']} team's" if most_relevant.get("team") else "your team's"
    
    if most_relevant.get("source") == "research_export":
        return f"Based on {team_note} previous research on \"{most_relevant['title']}\" ({date_str}), I'll focus on what's changed or new..."
    else:
        return f"I noticed this relates to a briefing {team_note} saved on {date_str} about \"{most_relevant['title']}\". I'll build on that context..."


async def build_agent_context(query: str, user_team: Optional[str] = None) -> MemoryContext:
    """
    Build full context bundle for agent prompts.
    Returns preferences, memories, and formatted prompt additions.
    """
    # Layer 1: Always-on preferences
    preferences = await get_org_preferences(user_team)
    preferences_prompt = format_preferences_for_prompt(preferences)
    
    # Layer 2: Retrieved memories (vector search)
    memories = await get_relevant_memories(query, user_team, limit=5)
    memories_prompt = format_memories_for_prompt(memories)
    
    # Layer 3: Proactive intro
    proactive_intro = generate_proactive_intro(memories)
    
    return MemoryContext(
        preferences=preferences,
        memories=memories,
        prompt_addition=preferences_prompt + memories_prompt,
        proactive_intro=proactive_intro
    )
