"""
Research Memory Service
=======================

Provides memory and context integration for Deep Research workflow.

Features:
- Query caching with BigQuery persistence (beyond in-memory TTL)
- Related research discovery (semantic search on past reports)
- Context injection to avoid redundant API calls
- Entity tracking for better personalization

Usage:
    memory = ResearchMemory()
    
    # Check for existing research
    cached = await memory.get_cached_report(query)
    
    # Find related past research  
    related = await memory.find_related(query, entities)
    
    # Store completed research
    await memory.store_report(report_id, query, state)
"""

import hashlib
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from app.db.gcp_storage import get_storage

logger = logging.getLogger(__name__)


class ResearchMemory:
    """
    Memory service for Deep Research workflow.
    
    Provides persistent caching and context retrieval to:
    1. Avoid re-running expensive research for similar queries
    2. Surface relevant prior findings to enrich new research
    3. Track entities and topics for personalized results
    """
    
    def __init__(self, cache_hours: int = 24, max_related: int = 5):
        """
        Initialize memory service.
        
        Args:
            cache_hours: How long to consider cached reports valid
            max_related: Max number of related reports to surface
        """
        self.cache_hours = cache_hours
        self.max_related = max_related
        self._storage = None
    
    async def _get_storage(self):
        """Lazy-load storage singleton."""
        if self._storage is None:
            self._storage = await get_storage()
        return self._storage
    
    @staticmethod
    def compute_query_hash(query: str) -> str:
        """
        Compute normalized hash for query deduplication.
        
        Normalizes query (lowercase, strip, collapse whitespace) before hashing.
        """
        normalized = " ".join(query.lower().strip().split())
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]
    
    async def get_cached_report(
        self,
        query: str,
        max_age_hours: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Check if we have a recent report for this query.
        
        Args:
            query: User's research query
            max_age_hours: Override default cache TTL
            
        Returns:
            Cached report dict or None
        """
        storage = await self._get_storage()
        query_hash = self.compute_query_hash(query)
        
        try:
            report = await storage.get_deep_research_report_by_hash(
                query_hash=query_hash,
                max_age_hours=max_age_hours or self.cache_hours,
            )
            
            if report:
                logger.info(f"Cache HIT for query hash {query_hash}")
                return report
            
            logger.debug(f"Cache MISS for query hash {query_hash}")
            return None
            
        except Exception as e:
            logger.error(f"Error checking cache: {e}")
            return None
    
    async def find_related_research(
        self,
        query: str,
        companies: Optional[List[str]] = None,
        industries: Optional[List[str]] = None,
        exclude_hash: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Find related past research for context enrichment.
        
        This enables the workflow to:
        - Reference prior findings instead of re-researching
        - Note when topics were previously covered
        - Build on historical context
        
        Args:
            query: Current research query
            companies: Companies mentioned in current query
            industries: Industries relevant to current query
            exclude_hash: Query hash to exclude (e.g., current query)
            
        Returns:
            List of related report summaries
        """
        storage = await self._get_storage()
        
        try:
            related = await storage.search_related_research(
                query=query,
                companies=companies,
                industries=industries,
                max_age_days=90,  # Look back 90 days
                limit=self.max_related + 1,  # +1 to filter out self
            )
            
            # Filter out the current query if it was already stored
            if exclude_hash:
                related = [r for r in related if r.get("query_hash") != exclude_hash]
            
            # Limit to max_related
            related = related[:self.max_related]
            
            if related:
                logger.info(f"Found {len(related)} related reports for context")
            
            return related
            
        except Exception as e:
            logger.error(f"Error finding related research: {e}")
            return []
    
    async def store_report(
        self,
        report_id: str,
        query: str,
        state: Dict[str, Any],
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> bool:
        """
        Store a completed research report for future reference.
        
        Args:
            report_id: Unique report identifier
            query: Original user query
            state: Complete workflow state with all outputs
            user_id: Optional user identifier
            session_id: Optional session identifier
            
        Returns:
            True if stored successfully
        """
        storage = await self._get_storage()
        query_hash = self.compute_query_hash(query)
        
        try:
            success = await storage.store_deep_research_report(
                report_id=report_id,
                query=query,
                query_hash=query_hash,
                state=state,
                user_id=user_id,
                session_id=session_id,
            )
            
            if success:
                logger.info(f"Stored research report {report_id} (hash: {query_hash})")
            
            return success
            
        except Exception as e:
            logger.error(f"Error storing research report: {e}")
            return False
    
    async def get_report_by_id(self, report_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific research report by ID."""
        storage = await self._get_storage()
        
        try:
            return await storage.get_deep_research_report_by_id(report_id)
        except Exception as e:
            logger.error(f"Error fetching report {report_id}: {e}")
            return None
    
    async def get_recent_reports(
        self,
        user_id: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Get recent research reports for a user."""
        storage = await self._get_storage()
        
        try:
            return await storage.get_deep_research_reports(
                user_id=user_id,
                limit=limit,
                offset=offset,
            )
        except Exception as e:
            logger.error(f"Error fetching recent reports: {e}")
            return []
    
    def format_context_for_prompt(
        self,
        related_reports: List[Dict[str, Any]],
    ) -> str:
        """
        Format related research as context for agent prompts.
        
        Creates a concise summary of prior research that can be
        injected into agent system prompts.
        
        Args:
            related_reports: List of related report summaries
            
        Returns:
            Formatted context string
        """
        if not related_reports:
            return ""
        
        lines = ["## Prior Research Context", ""]
        lines.append("The following related research was previously conducted:")
        lines.append("")
        
        for i, report in enumerate(related_reports, 1):
            title = report.get("title", "Untitled")
            query = report.get("query", "")[:100]
            date = report.get("created_at", "")[:10] if report.get("created_at") else "Unknown date"
            summary = report.get("executive_summary", "")[:200]
            companies = ", ".join(report.get("companies", [])[:5])
            confidence = report.get("overall_confidence", "unknown")
            
            lines.append(f"### {i}. {title}")
            lines.append(f"- **Query**: {query}")
            lines.append(f"- **Date**: {date}")
            lines.append(f"- **Confidence**: {confidence}")
            if companies:
                lines.append(f"- **Companies**: {companies}")
            if summary:
                lines.append(f"- **Key findings**: {summary}")
            lines.append("")
        
        lines.append("---")
        lines.append("Consider referencing these prior findings where relevant, but always verify with fresh data.")
        lines.append("")
        
        return "\n".join(lines)


# Singleton instance
_memory_instance: Optional[ResearchMemory] = None


async def get_research_memory() -> ResearchMemory:
    """Get or create the research memory singleton."""
    global _memory_instance
    if _memory_instance is None:
        _memory_instance = ResearchMemory()
    return _memory_instance
