"""Quick test of the workflow to debug empty responses."""
import asyncio
from app.graph.workflow import run_workflow

async def test():
    print("=" * 60)
    print("Testing Industry Watcher workflow...")
    print("=" * 60)
    
    chunk_count = 0
    async for chunk in run_workflow(
        message="Hello, what can you help me with?",
        agent_type="industry_watcher",
        supply_chain="C1"
    ):
        chunk_count += 1
        chunk_type = chunk.get("type", "unknown")
        content = chunk.get("content", "")
        
        print(f"\n[{chunk_count}] TYPE: {chunk_type}")
        
        if chunk_type in ("content", "final"):
            print(f"    CONTENT ({len(content)} chars): {content[:300]}...")
        elif chunk_type == "error":
            print(f"    ERROR: {content}")
        else:
            print(f"    {content[:100] if content else '(no content)'}")
    
    print("\n" + "=" * 60)
    print(f"Total chunks received: {chunk_count}")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test())
