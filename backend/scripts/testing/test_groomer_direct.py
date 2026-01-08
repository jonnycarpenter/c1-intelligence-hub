"""
Direct test of the groomer agent without the full workflow.

Run from backend directory:
    python scripts/testing/test_groomer_direct.py

This bypasses LangGraph and tests just the groomer LLM call.
"""
import asyncio
import sys
import os
import json
import time

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
load_dotenv()

async def test_groomer():
    """Test the groomer directly."""
    from app.agents.research.state import DeepResearchState
    from app.agents.research.groomer import query_grooming_node, GROOMER_SYSTEM_PROMPT
    
    print("=" * 60)
    print("GROOMER DIRECT TEST")
    print("=" * 60)
    
    # Test query
    test_query = "marine/yacht composites"
    print(f"\nTest Query: {test_query}")
    print(f"System Prompt Length: {len(GROOMER_SYSTEM_PROMPT)} chars")
    print("-" * 60)
    
    # Create minimal initial state
    initial_state: DeepResearchState = {
        "user_query": test_query,
        "conversation_history": [],
        "research_brief": None,
        "clarification_count": 0,
        "financial_output": None,
        "industry_output": None,
        "visual_output": None,
        "final_report": None,
        "category_output": None,
        "validator_output": None,
        "current_status": "starting",
        "errors": [],
    }
    
    print("\nCalling groomer node...")
    start = time.time()
    
    try:
        result_state = await query_grooming_node(initial_state)
        elapsed = time.time() - start
        
        print(f"\n✅ Groomer completed in {elapsed:.1f}s")
        print("-" * 60)
        
        # Check result
        print(f"\nCurrent Status: {result_state.get('current_status')}")
        print(f"Errors: {result_state.get('errors')}")
        
        brief = result_state.get("research_brief")
        if brief:
            print("\n📋 RESEARCH BRIEF:")
            print(f"  Status: {brief.status}")
            print(f"  Original Query: {brief.original_query}")
            print(f"  Clarified Intent: {brief.clarified_intent}")
            print(f"  Timeframe: {brief.timeframe}")
            print(f"\n  Financial Queries ({len(brief.financial_agent_queries or [])}):")
            for q in (brief.financial_agent_queries or []):
                print(f"    - {q}")
            print(f"\n  Industry Queries ({len(brief.industry_agent_queries or [])}):")
            for q in (brief.industry_agent_queries or []):
                print(f"    - {q}")
            print(f"\n  Entities to Track: {brief.entities_to_track}")
            print(f"\n  Domain Context Preview: {(brief.domain_context or '')[:200]}...")
            
            if brief.clarifying_question:
                print(f"\n⚠️ CLARIFICATION REQUESTED:")
                print(f"  Question: {brief.clarifying_question}")
        else:
            print("\n❌ NO RESEARCH BRIEF RETURNED")
            
    except asyncio.TimeoutError:
        elapsed = time.time() - start
        print(f"\n❌ TIMEOUT after {elapsed:.1f}s")
    except Exception as e:
        elapsed = time.time() - start
        print(f"\n❌ ERROR after {elapsed:.1f}s: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


async def test_llm_only():
    """Test just the LLM call without any groomer logic."""
    from app.config.settings import settings
    from app.utils.resilient_llm import create_resilient_llm_with_openai_fallback
    from langchain_core.messages import SystemMessage, HumanMessage
    
    print("\n" + "=" * 60)
    print("RAW LLM CALL TEST")
    print("=" * 60)
    
    llm = create_resilient_llm_with_openai_fallback(
        primary_model=settings.deep_research_groomer_model,
        anthropic_api_key=settings.anthropic_api_key,
        openai_api_key=settings.openai_api_key,
        temperature=0,
    )
    
    print(f"\nModel: {settings.deep_research_groomer_model}")
    print(f"Testing basic LLM connectivity...")
    
    messages = [
        SystemMessage(content="You are a helpful assistant. Respond with a single word."),
        HumanMessage(content="Say 'working' if you can read this.")
    ]
    
    start = time.time()
    try:
        response = await asyncio.wait_for(llm.ainvoke(messages), timeout=30)
        elapsed = time.time() - start
        print(f"\n✅ LLM responded in {elapsed:.1f}s: {response.content}")
    except asyncio.TimeoutError:
        elapsed = time.time() - start
        print(f"\n❌ LLM TIMEOUT after {elapsed:.1f}s")
    except Exception as e:
        elapsed = time.time() - start
        print(f"\n❌ LLM ERROR after {elapsed:.1f}s: {type(e).__name__}: {e}")


if __name__ == "__main__":
    print("\n🧪 Starting Groomer Tests\n")
    
    # First test raw LLM connectivity
    asyncio.run(test_llm_only())
    
    # Then test full groomer
    asyncio.run(test_groomer())
    
    print("\n" + "=" * 60)
    print("TESTS COMPLETE")
    print("=" * 60)
