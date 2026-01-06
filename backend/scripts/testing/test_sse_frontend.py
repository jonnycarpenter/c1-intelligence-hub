"""
Test script for Deep Research SSE integration.

This script triggers a deep research query and displays all SSE events
to verify the frontend integration is working correctly.
"""

import httpx
import json
import time
from datetime import datetime

API_URL = "http://localhost:8000/api/research/deep/run"
QUERY = "What's the outlook for carbon fiber in aerospace manufacturing over the next 2 years?"

def format_timestamp():
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]

def format_event(event_type: str, content: dict) -> str:
    """Format an event for console display"""
    ts = format_timestamp()
    
    if event_type == "status":
        msg = content if isinstance(content, str) else content.get("message", "")
        return f"[{ts}] 📊 STATUS: {msg}"
    
    elif event_type == "cache_hit":
        return f"[{ts}] ⚡ CACHE HIT: {content.get('message', '')} (hash: {content.get('query_hash', 'N/A')})"
    
    elif event_type == "node_start":
        node = content.get("node", "?")
        desc = content.get("description", "")
        parallel = content.get("parallel_with")
        extra = f" [PARALLEL with {parallel}]" if parallel else ""
        return f"[{ts}] ▶️  NODE START: {node} - {desc}{extra}"
    
    elif event_type == "node_complete":
        node = content.get("node", "?")
        return f"[{ts}] ✅ NODE COMPLETE: {node}"
    
    elif event_type == "tool_progress":
        tool = content.get("tool", "?")
        message = content.get("message", "")
        ticker = content.get("ticker")
        ticker_str = f" ({ticker})" if ticker else ""
        return f"[{ts}] 🔧 TOOL: {tool}{ticker_str} - {message}"
    
    elif event_type == "clarification":
        return f"[{ts}] ❓ CLARIFICATION NEEDED"
    
    elif event_type == "report":
        headline = content.get("executive_summary", {}).get("headline", "N/A")
        sections = len(content.get("sections", []))
        return f"[{ts}] 📄 REPORT READY: {sections} sections - {headline}"
    
    elif event_type == "category":
        east = content.get("territory_insights", {}).get("east_relevance", 0)
        west = content.get("territory_insights", {}).get("west_relevance", 0)
        return f"[{ts}] 🎯 CATEGORY: East={east:.0%} West={west:.0%}"
    
    elif event_type == "validation":
        passed = content.get("validation_passed", False)
        issues = len(content.get("citation_issues", []))
        return f"[{ts}] ✓ VALIDATION: {'PASSED' if passed else 'FAILED'} ({issues} issues)"
    
    elif event_type == "warnings":
        count = len(content) if isinstance(content, list) else 1
        return f"[{ts}] ⚠️  WARNINGS: {count} warnings"
    
    elif event_type == "error":
        msg = content if isinstance(content, str) else content.get("message", "Unknown error")
        return f"[{ts}] ❌ ERROR: {msg}"
    
    else:
        return f"[{ts}] 🔹 {event_type.upper()}: {str(content)[:100]}"

def test_sse_stream():
    """Test the SSE stream by triggering a deep research query"""
    
    print("=" * 80)
    print("🧪 Testing Deep Research SSE Integration")
    print("=" * 80)
    print(f"Query: {QUERY}")
    print("=" * 80)
    print()
    
    start_time = time.time()
    event_count = 0
    events_by_type = {}
    
    try:
        with httpx.Client(timeout=300.0) as client:
            with client.stream(
                "POST",
                API_URL,
                json={"query": QUERY, "history": []},
                headers={"Accept": "text/event-stream"}
            ) as response:
                
                if response.status_code != 200:
                    print(f"❌ HTTP {response.status_code}: {response.text}")
                    return
                
                print("✅ Connected to SSE stream\n")
                
                for line in response.iter_lines():
                    if not line:
                        continue
                    
                    if line.startswith("data: "):
                        data_str = line[6:]  # Remove "data: " prefix
                        
                        if data_str == "[DONE]":
                            print("\n" + "=" * 80)
                            print("✅ Stream complete!")
                            break
                        
                        try:
                            event_data = json.loads(data_str)
                            event_type = event_data.get("type", "unknown")
                            content = event_data.get("content", {})
                            
                            # Track event counts
                            event_count += 1
                            events_by_type[event_type] = events_by_type.get(event_type, 0) + 1
                            
                            # Display formatted event
                            print(format_event(event_type, content))
                            
                        except json.JSONDecodeError as e:
                            print(f"⚠️  Failed to parse JSON: {e}")
                            print(f"   Raw data: {data_str[:200]}")
    
    except httpx.ReadTimeout:
        print("\n❌ Request timed out after 5 minutes")
    except httpx.ConnectError:
        print("\n❌ Failed to connect to backend. Is it running on port 8000?")
    except Exception as e:
        print(f"\n❌ Error: {type(e).__name__}: {e}")
    
    finally:
        elapsed = time.time() - start_time
        
        print("=" * 80)
        print("📊 Test Summary")
        print("=" * 80)
        print(f"Duration: {elapsed:.1f}s")
        print(f"Total events: {event_count}")
        print("\nEvents by type:")
        for event_type, count in sorted(events_by_type.items()):
            print(f"  {event_type:20s}: {count:3d}")
        print()

if __name__ == "__main__":
    test_sse_stream()
