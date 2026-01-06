"""Test parallel execution fix for Deep Research workflow."""
import asyncio
from app.graph.research_workflow import research_workflow


async def test_parallel():
    print("Testing parallel execution with reducer fix...")
    print("=" * 60)
    
    initial_state = {
        "user_query": "What is the outlook for carbon fiber in aerospace?",
        "conversation_history": [],
        "research_brief": None,
        "clarification_count": 0,
        "financial_output": None,
        "industry_output": None,
        "final_report": None,
        "category_output": None,
        "validator_output": None,
        "current_status": "starting",
        "errors": [],
    }
    
    try:
        # Run with streaming to see progress
        async for event in research_workflow.astream(initial_state):
            for node, output in event.items():
                if node == "__end__":
                    continue
                status = output.get("current_status", "unknown")
                print(f"[{node}] Status: {status}")
                
                # Show errors if any
                errors = output.get("errors", [])
                if errors:
                    for err in errors:
                        print(f"  ⚠ Error: {err}")
                
                # Show outputs
                if output.get("research_brief"):
                    print(f"  → Research brief generated")
                if output.get("financial_output"):
                    print(f"  → Financial output ready")
                if output.get("industry_output"):
                    print(f"  → Industry output ready")
                if output.get("final_report"):
                    print(f"  → Final report synthesized!")
                if output.get("category_output"):
                    print(f"  → Category output ready")
                if output.get("validator_output"):
                    print(f"  → Validation complete")
        
        print("=" * 60)
        print("✓ Workflow completed without InvalidUpdateError!")
        print("\nCheck LangSmith dashboard for traces:")
        print("  https://smith.langchain.com")
        return True
        
    except Exception as e:
        print("=" * 60)
        print(f"✗ Error: {type(e).__name__}")
        print(f"  {e}")
        return False


if __name__ == "__main__":
    asyncio.run(test_parallel())
