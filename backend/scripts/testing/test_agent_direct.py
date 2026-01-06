"""Test the industry_watcher agent directly."""
import asyncio
from langchain_core.messages import HumanMessage

from app.graph.workflow import _get_agent
from app.utils.grounding import get_grounding_context

async def test():
    print("=" * 60)
    print("Testing Industry Watcher agent directly...")
    print("=" * 60)
    
    grounding = get_grounding_context()
    
    agent = _get_agent("industry_watcher")
    
    state = {
        "messages": [HumanMessage(content="Hello, what can you help me with?")],
        "query": "Hello, what can you help me with?",
        "agent_type": "industry_watcher",
        "companies": grounding["companies"],
        "materials": grounding["materials"],
        "industries": grounding["industries"],
        "exclusions": grounding["exclusions"],
        "supply_chain": "C1",
        "tool_results": [],
        "response": None,
    }
    
    print("\nCalling agent.astream()...")
    chunk_count = 0
    
    async for chunk in agent.astream(state):
        chunk_count += 1
        print(f"\n[{chunk_count}] CHUNK KEYS: {list(chunk.keys())}")
        
        # The chunk is keyed by node name
        for node_name, node_output in chunk.items():
            print(f"    NODE: {node_name}")
            print(f"    OUTPUT KEYS: {list(node_output.keys()) if isinstance(node_output, dict) else type(node_output)}")
            
            if isinstance(node_output, dict):
                if "messages" in node_output and node_output["messages"]:
                    print(f"      MESSAGES ({len(node_output['messages'])} msgs):")
                    for i, msg in enumerate(node_output["messages"]):
                        msg_type = type(msg).__name__
                        content = getattr(msg, "content", None)
                        tool_calls = getattr(msg, "tool_calls", None)
                        print(f"        [{i}] type={msg_type}")
                        print(f"            content ({len(content) if content else 0} chars): {content[:200] if content else '(none)'}...")
                        if tool_calls:
                            print(f"            tool_calls: {tool_calls}")
                
                if "response" in node_output and node_output["response"]:
                    print(f"      RESPONSE: {node_output['response'][:200]}...")
                
                if "tool_results" in node_output:
                    print(f"      TOOL_RESULTS: {node_output['tool_results']}")
    
    print("\n" + "=" * 60)
    print(f"Total chunks: {chunk_count}")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test())
