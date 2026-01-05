"""
Test Ad Hoc Briefing Session Management
======================================

This script tests the new session-based follow-up tracking for ad-hoc briefings.

Tests:
1. Session creation on first request
2. Session persistence on follow-up requests
3. Follow-up count accumulation
4. Redirect to Deep Research after max follow-ups
5. Session expiration (manual cleanup)

Run:
    cd backend
    python scripts/testing/test_briefing_sessions.py
"""

import asyncio
import sys
sys.path.insert(0, ".")

from app.agents.adhoc_briefing import (
    get_session_manager,
    BriefingSession,
    AdHocBriefingAgent,
    BriefingContext,
)


def test_session_creation():
    """Test that session manager creates sessions correctly."""
    print("\n=== Test 1: Session Creation ===")
    
    manager = get_session_manager()
    
    # Create a new session
    session = manager.create_session()
    print(f"Created session: {session.session_id}")
    print(f"  follow_up_count: {session.follow_up_count}")
    print(f"  max_follow_ups: {session.max_follow_ups}")
    print(f"  turns_remaining: {max(0, session.max_follow_ups - session.follow_up_count)}")
    
    assert session.session_id is not None
    assert session.follow_up_count == 0
    assert session.max_follow_ups == 2
    print("✓ Session creation works correctly")
    
    return session.session_id


def test_session_retrieval(session_id: str):
    """Test that we can retrieve an existing session."""
    print("\n=== Test 2: Session Retrieval ===")
    
    manager = get_session_manager()
    
    # Retrieve existing session
    session = manager.get_session(session_id)
    assert session is not None
    print(f"Retrieved session: {session.session_id}")
    print(f"  follow_up_count: {session.follow_up_count}")
    print("✓ Session retrieval works correctly")
    
    # Test get_or_create with existing
    session2 = manager.get_or_create_session(session_id)
    assert session2.session_id == session_id
    print("✓ get_or_create returns existing session")
    
    # Test get_or_create with None (creates new)
    session3 = manager.get_or_create_session(None)
    assert session3.session_id != session_id
    print(f"✓ get_or_create with None creates new session: {session3.session_id}")


def test_follow_up_tracking():
    """Test that follow-up count increments and persists."""
    print("\n=== Test 3: Follow-up Tracking ===")
    
    manager = get_session_manager()
    session = manager.create_session()
    session_id = session.session_id
    
    print(f"Initial state: follow_up_count={session.follow_up_count}")
    
    # Simulate first follow-up
    session.increment_follow_up()
    print(f"After 1st follow-up: follow_up_count={session.follow_up_count}")
    assert session.follow_up_count == 1
    
    # Retrieve session and verify state persists
    session = manager.get_session(session_id)
    assert session.follow_up_count == 1
    print("✓ Follow-up count persists across retrieval")
    
    # Simulate second follow-up
    session.increment_follow_up()
    print(f"After 2nd follow-up: follow_up_count={session.follow_up_count}")
    assert session.follow_up_count == 2
    
    # Check redirect trigger
    assert session.should_redirect_to_deep_research() == True
    print("✓ should_redirect_to_deep_research returns True at max")
    
    return session_id


def test_conversation_history():
    """Test conversation history tracking."""
    print("\n=== Test 4: Conversation History ===")
    
    manager = get_session_manager()
    session = manager.create_session()
    
    # Add messages
    session.add_to_history("user", "What's the latest on carbon fiber pricing?")
    session.add_to_history("assistant", "Based on recent articles, carbon fiber prices have...")
    session.add_to_history("user", "How does this compare to last quarter?")
    session.add_to_history("assistant", "Comparing to Q3 2025, we see a 5% increase...")
    
    print(f"History length: {len(session.conversation_history)}")
    assert len(session.conversation_history) == 4
    
    # Test context generation
    context = session.get_conversation_context(max_turns=2)
    print(f"\nConversation context (last 2 turns):")
    print(context)
    
    assert "User:" in context
    assert "Assistant:" in context
    print("✓ Conversation history tracking works")


def test_session_cleanup():
    """Test session deletion and cleanup."""
    print("\n=== Test 5: Session Cleanup ===")
    
    manager = get_session_manager()
    
    # Create a session
    session = manager.create_session()
    session_id = session.session_id
    
    # Verify it exists
    assert manager.get_session(session_id) is not None
    
    # Delete it
    deleted = manager.delete_session(session_id)
    assert deleted == True
    print(f"Deleted session: {session_id}")
    
    # Verify it's gone
    assert manager.get_session(session_id) is None
    print("✓ Session deleted successfully")
    
    # Delete non-existent should return False
    deleted = manager.delete_session("non-existent-session-id")
    assert deleted == False
    print("✓ Deleting non-existent session returns False")


def test_session_stats():
    """Test session manager statistics."""
    print("\n=== Test 6: Session Stats ===")
    
    manager = get_session_manager()
    
    # Clean up any existing sessions for accurate count
    initial_stats = manager.get_stats()
    print(f"Initial stats: {initial_stats}")
    
    # Create a few sessions
    sessions = [manager.create_session() for _ in range(3)]
    
    stats = manager.get_stats()
    print(f"After creating 3 sessions: {stats}")
    
    assert stats['total_sessions'] >= 3
    print("✓ Stats tracking works")
    
    # Cleanup
    for s in sessions:
        manager.delete_session(s.session_id)


async def test_agent_with_session():
    """Test that the agent works with session state."""
    print("\n=== Test 7: Agent with Session Integration ===")
    
    manager = get_session_manager()
    session = manager.create_session()
    
    # Create agent and context
    agent = AdHocBriefingAgent()
    context = BriefingContext(
        current_brief_headlines=["Hexcel expands capacity", "Boeing increases production"],
        current_brief_date="2026-01-05",
        recent_digest_topics=["carbon fiber", "aerospace", "supply chain"],
    )
    
    print(f"Testing agent with session {session.session_id}")
    print(f"Initial follow_up_count: {session.follow_up_count}")
    
    # Note: This test requires API keys and BigQuery, so we'll just test the method signature
    # In a real test, you'd mock these or use test fixtures
    
    # For now, verify the agent accepts session parameter without error
    try:
        # We won't actually call generate_briefing as it requires API access
        # Just verify the method signature is correct
        import inspect
        sig = inspect.signature(agent.generate_briefing)
        params = list(sig.parameters.keys())
        assert 'session' in params, "Agent should accept session parameter"
        print(f"✓ Agent.generate_briefing accepts parameters: {params}")
    except Exception as e:
        print(f"Error: {e}")
        raise


def main():
    """Run all tests."""
    print("=" * 60)
    print("Ad Hoc Briefing Session Management Tests")
    print("=" * 60)
    
    try:
        # Test 1: Session creation
        session_id = test_session_creation()
        
        # Test 2: Session retrieval
        test_session_retrieval(session_id)
        
        # Test 3: Follow-up tracking
        test_follow_up_tracking()
        
        # Test 4: Conversation history
        test_conversation_history()
        
        # Test 5: Cleanup
        test_session_cleanup()
        
        # Test 6: Stats
        test_session_stats()
        
        # Test 7: Agent integration (async)
        asyncio.run(test_agent_with_session())
        
        print("\n" + "=" * 60)
        print("All tests passed! ✓")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
