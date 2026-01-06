"""
Quick test to run Deep Research and verify LangSmith traces.
"""
import httpx
import json
import time

print("Waiting for server to start...")
time.sleep(3)

print("\n" + "=" * 50)
print("Testing Deep Research API with LangSmith Tracing")
print("=" * 50)

url = "http://localhost:8000/api/deep-research/run"
payload = {
    "query": "What is the outlook for carbon fiber demand in aerospace?",
    "history": []
}

print(f"\nQuery: {payload['query']}")
print("\nStarting request (this may take 1-2 minutes)...\n")

try:
    with httpx.Client(timeout=180.0) as client:
        with client.stream("POST", url, json=payload) as response:
            event_count = 0
            for line in response.iter_lines():
                if line.startswith("data: "):
                    event_count += 1
                    data = line[6:]  # Remove "data: " prefix
                    if data == "[DONE]":
                        print(f"\n✓ Stream complete! Received {event_count} events")
                        break
                    try:
                        event = json.loads(data)
                        event_type = event.get("type", "unknown")
                        
                        if event_type == "status":
                            print(f"  📊 Status: {event.get('content')}")
                        elif event_type == "node_start":
                            node = event.get("content", {}).get("node", "?")
                            desc = event.get("content", {}).get("description", "")
                            parallel = event.get("content", {}).get("parallel_with")
                            parallel_str = f" (parallel with {parallel})" if parallel else ""
                            print(f"  🟢 Node START: {node} - {desc}{parallel_str}")
                        elif event_type == "node_complete":
                            node = event.get("content", {}).get("node", "?")
                            print(f"  🔵 Node DONE: {node}")
                        elif event_type == "tool_progress":
                            tool = event.get("content", {}).get("tool", "?")
                            msg = event.get("content", {}).get("message", "")
                            print(f"    🔧 {tool}: {msg}")
                        elif event_type == "report":
                            print(f"  📄 Report received!")
                        elif event_type == "error":
                            print(f"  ❌ Error: {event.get('content')}")
                        else:
                            print(f"  [{event_type}]")
                    except json.JSONDecodeError:
                        pass
                        
    print("\n" + "=" * 50)
    print("✓ Test complete!")
    print("Check LangSmith dashboard for traces:")
    print("  https://smith.langchain.com")
    print("  Project: c1-intelligence-hub-prod")
    print("  Filter by tag: deep_research")
    print("=" * 50)
    
except httpx.ConnectError:
    print("❌ Could not connect to server. Make sure it's running on port 8000")
except Exception as e:
    print(f"❌ Error: {e}")
