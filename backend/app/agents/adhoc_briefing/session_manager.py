"""
Ad Hoc Briefing Session Manager
===============================

Manages stateful sessions for ad-hoc briefing conversations.

Key Features:
- In-memory TTL cache for agent instances
- Session ID generation and lookup
- Automatic cleanup of expired sessions
- Conversation history tracking

Design Notes:
- Sessions expire after 30 minutes of inactivity
- Max 1000 concurrent sessions (LRU eviction)
- Thread-safe for async operations
"""

import uuid
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Optional, TYPE_CHECKING
from collections import OrderedDict
from dataclasses import dataclass, field

from app.utils.logger import get_logger

if TYPE_CHECKING:
    from .agent import AdHocBriefingAgent

logger = get_logger(__name__)


# =============================================================================
# Session Data Model
# =============================================================================

@dataclass
class BriefingSession:
    """
    Represents an ad-hoc briefing session with conversation state.
    """
    session_id: str
    created_at: datetime
    last_activity: datetime
    follow_up_count: int = 0
    max_follow_ups: int = 2
    conversation_history: list = field(default_factory=list)
    
    # Agent instance (lazy-loaded)
    _agent: Optional["AdHocBriefingAgent"] = field(default=None, repr=False)
    
    def is_expired(self, ttl_minutes: int = 30) -> bool:
        """Check if session has expired based on inactivity."""
        expiry_time = self.last_activity + timedelta(minutes=ttl_minutes)
        return datetime.utcnow() > expiry_time
    
    def touch(self):
        """Update last activity timestamp."""
        self.last_activity = datetime.utcnow()
    
    def should_redirect_to_deep_research(self) -> bool:
        """Check if follow-up limit reached."""
        return self.follow_up_count >= self.max_follow_ups
    
    def increment_follow_up(self):
        """Increment follow-up count."""
        self.follow_up_count += 1
        self.touch()
    
    def add_to_history(self, role: str, content: str):
        """Add message to conversation history."""
        self.conversation_history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat()
        })
        self.touch()
    
    def get_conversation_context(self, max_turns: int = 4) -> str:
        """
        Get recent conversation history formatted for context injection.
        
        Returns last N turns of Q&A for the agent to reference.
        """
        if not self.conversation_history:
            return ""
        
        # Get last max_turns * 2 messages (question + answer pairs)
        recent = self.conversation_history[-(max_turns * 2):]
        
        if not recent:
            return ""
        
        lines = ["Previous conversation in this session:"]
        for msg in recent:
            role_label = "User" if msg["role"] == "user" else "Assistant"
            # Truncate long messages
            content = msg["content"][:500] + "..." if len(msg["content"]) > 500 else msg["content"]
            lines.append(f"{role_label}: {content}")
        
        return "\n".join(lines)
    
    def to_dict(self) -> dict:
        """Serialize session state for API response."""
        return {
            "session_id": self.session_id,
            "follow_up_count": self.follow_up_count,
            "max_follow_ups": self.max_follow_ups,
            "turns_remaining": max(0, self.max_follow_ups - self.follow_up_count),
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "history_length": len(self.conversation_history),
        }


# =============================================================================
# Session Manager (Singleton)
# =============================================================================

class BriefingSessionManager:
    """
    Manages ad-hoc briefing sessions with TTL-based expiration.
    
    Uses an LRU OrderedDict for bounded memory usage.
    """
    
    _instance: Optional["BriefingSessionManager"] = None
    
    def __new__(cls):
        """Singleton pattern for global session manager."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._sessions: OrderedDict[str, BriefingSession] = OrderedDict()
        self._max_sessions = 1000
        self._ttl_minutes = 30
        self._cleanup_interval = 300  # 5 minutes
        self._cleanup_task: Optional[asyncio.Task] = None
        self._initialized = True
        
        logger.info(f"BriefingSessionManager initialized (max={self._max_sessions}, ttl={self._ttl_minutes}min)")
    
    def create_session(self) -> BriefingSession:
        """
        Create a new briefing session.
        
        Returns:
            New BriefingSession with unique ID
        """
        # Evict oldest if at capacity
        while len(self._sessions) >= self._max_sessions:
            oldest_id, _ = self._sessions.popitem(last=False)
            logger.debug(f"Evicted oldest session: {oldest_id}")
        
        session_id = str(uuid.uuid4())
        now = datetime.utcnow()
        
        session = BriefingSession(
            session_id=session_id,
            created_at=now,
            last_activity=now,
        )
        
        self._sessions[session_id] = session
        logger.info(f"Created new briefing session: {session_id}")
        
        return session
    
    def get_session(self, session_id: str) -> Optional[BriefingSession]:
        """
        Retrieve a session by ID.
        
        Returns None if session doesn't exist or is expired.
        """
        session = self._sessions.get(session_id)
        
        if session is None:
            return None
        
        if session.is_expired(self._ttl_minutes):
            logger.debug(f"Session expired: {session_id}")
            del self._sessions[session_id]
            return None
        
        # Move to end (most recently used)
        self._sessions.move_to_end(session_id)
        session.touch()
        
        return session
    
    def get_or_create_session(self, session_id: Optional[str] = None) -> BriefingSession:
        """
        Get existing session or create new one.
        
        Args:
            session_id: Optional existing session ID
            
        Returns:
            Existing or new BriefingSession
        """
        if session_id:
            session = self.get_session(session_id)
            if session:
                return session
            logger.debug(f"Session not found or expired: {session_id}, creating new")
        
        return self.create_session()
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session explicitly."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.debug(f"Deleted session: {session_id}")
            return True
        return False
    
    def cleanup_expired(self) -> int:
        """
        Remove all expired sessions.
        
        Returns:
            Number of sessions cleaned up
        """
        expired_ids = [
            sid for sid, session in self._sessions.items()
            if session.is_expired(self._ttl_minutes)
        ]
        
        for sid in expired_ids:
            del self._sessions[sid]
        
        if expired_ids:
            logger.info(f"Cleaned up {len(expired_ids)} expired sessions")
        
        return len(expired_ids)
    
    async def start_cleanup_task(self):
        """Start background task for periodic cleanup."""
        if self._cleanup_task is not None:
            return
        
        async def cleanup_loop():
            while True:
                await asyncio.sleep(self._cleanup_interval)
                try:
                    self.cleanup_expired()
                except Exception as e:
                    logger.error(f"Error in session cleanup: {e}")
        
        self._cleanup_task = asyncio.create_task(cleanup_loop())
        logger.info("Started session cleanup background task")
    
    def get_stats(self) -> dict:
        """Get session manager statistics."""
        active = sum(1 for s in self._sessions.values() if not s.is_expired(self._ttl_minutes))
        return {
            "total_sessions": len(self._sessions),
            "active_sessions": active,
            "max_sessions": self._max_sessions,
            "ttl_minutes": self._ttl_minutes,
        }


# =============================================================================
# Module-level accessor
# =============================================================================

_session_manager: Optional[BriefingSessionManager] = None


def get_session_manager() -> BriefingSessionManager:
    """Get the global session manager instance."""
    global _session_manager
    if _session_manager is None:
        _session_manager = BriefingSessionManager()
    return _session_manager
