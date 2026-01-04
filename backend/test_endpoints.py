"""Quick endpoint test script."""
import requests
import json

BASE = 'http://127.0.0.1:8000'

def test_endpoint(method, path, data=None, desc=""):
    try:
        if method == 'GET':
            r = requests.get(f'{BASE}{path}', timeout=10)
        elif method == 'POST':
            r = requests.post(f'{BASE}{path}', json=data, timeout=30)
        
        status = r.status_code
        try:
            body = r.json()
        except:
            body = r.text[:200]
        
        print(f"✓ {method} {path}: {status}")
        if desc:
            print(f"  {desc}: {body if isinstance(body, str) else json.dumps(body)[:200]}")
        return True
    except Exception as e:
        print(f"✗ {method} {path}: FAILED - {str(e)[:100]}")
        return False

print("=" * 50)
print("Testing C1 Intelligence Hub API Endpoints")
print("=" * 50)

# Health
print("\n--- Health Check ---")
test_endpoint('GET', '/api/health')

# Data endpoints
print("\n--- Data Endpoints ---")
test_endpoint('GET', '/api/data/companies', desc="companies count")
test_endpoint('GET', '/api/data/materials', desc="materials count")
test_endpoint('GET', '/api/data/industries', desc="industries count")
test_endpoint('GET', '/api/data/preferences', desc="preferences")

# Chat endpoint (simple test)
print("\n--- Chat Endpoint (Pulse Mode) ---")
test_endpoint('POST', '/api/chat', 
              data={"message": "What companies are we tracking?", "mode": "pulse"},
              desc="chat response")

# Streaming chat endpoint
print("\n--- Streaming Chat Endpoint ---")
try:
    import httpx
    with httpx.Client(timeout=60.0) as client:
        with client.stream('POST', f'{BASE}/api/chat/stream', 
                          json={"message": "What companies are tracked?", "mode": "pulse"}) as r:
            print(f"✓ POST /api/chat/stream: {r.status_code}")
            if r.status_code == 200:
                chunks = 0
                for line in r.iter_lines():
                    if line and line.startswith('data:'):
                        chunks += 1
                        if chunks <= 3:
                            print(f"  chunk {chunks}: {line[:150]}...")
                        if chunks >= 8:
                            print(f"  ... (received {chunks}+ SSE events)")
                            break
except ImportError:
    # Fall back to requests if httpx not installed
    try:
        r = requests.post(f'{BASE}/api/chat/stream', 
                          json={"message": "What companies are tracked?", "mode": "pulse"},
                          stream=True, timeout=60,
                          headers={"Accept": "text/event-stream"})
        print(f"✓ POST /api/chat/stream: {r.status_code}")
        if r.status_code == 200:
            chunks = 0
            for line in r.iter_lines():
                if line:
                    chunks += 1
                    decoded = line.decode('utf-8')
                    if chunks <= 3:
                        print(f"  chunk {chunks}: {decoded[:150]}...")
                    if chunks >= 8:
                        print(f"  ... (received {chunks}+ chunks)")
                        break
    except Exception as e:
        print(f"✗ POST /api/chat/stream: FAILED - {str(e)[:100]}")
except Exception as e:
    print(f"✗ POST /api/chat/stream: FAILED - {str(e)[:100]}")

print("\n" + "=" * 50)
print("Endpoint testing complete!")
print("=" * 50)
