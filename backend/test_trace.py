"""Quick test to generate a LangSmith trace."""
import requests
import json

url = "http://localhost:8000/api/research/deep/run"
payload = {"query": "What is the outlook for carbon fiber demand in aerospace for 2026?", "history": []}

print("Sending Deep Research request...")
print(f"Query: {payload['query']}")
print("-" * 50)

try:
    response = requests.post(url, json=payload, stream=True, timeout=120)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        for line in response.iter_lines():
            if line:
                decoded = line.decode('utf-8')
                if decoded.startswith('data: '):
                    data = decoded[6:]
                    if data == '[DONE]':
                        print("\n✓ DONE - Check LangSmith for traces!")
                        break
                    try:
                        event = json.loads(data)
                        event_type = event.get('type', 'unknown')
                        if event_type == 'status':
                            print(f"[STATUS] {event.get('content')}")
                        elif event_type == 'node_start':
                            content = event.get('content', {})
                            print(f"[NODE START] {content.get('node')} - {content.get('description')}")
                        elif event_type == 'node_complete':
                            content = event.get('content', {})
                            print(f"[NODE COMPLETE] {content.get('node')}")
                        elif event_type == 'tool_progress':
                            content = event.get('content', {})
                            print(f"  [TOOL] {content.get('tool')}: {content.get('message')}")
                        elif event_type == 'report':
                            print(f"[REPORT] Generated successfully!")
                        elif event_type == 'clarification':
                            print(f"[CLARIFICATION] {event.get('content')}")
                        elif event_type == 'error':
                            print(f"[ERROR] {event.get('content')}")
                        elif event_type == 'warnings':
                            print(f"[WARNINGS] {event.get('content')}")
                        else:
                            print(f"[{event_type.upper()}] {event.get('content', {})}")
                    except json.JSONDecodeError:
                        pass
    else:
        print(f"Error: {response.text}")
except Exception as e:
    print(f"Request failed: {e}")
