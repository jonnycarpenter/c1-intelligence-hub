import requests
import json

print('Testing streaming endpoint...')
r = requests.post('http://localhost:8000/api/chat/stream', json={'message': 'Show me carbon fiber products', 'mode': 'products'}, stream=True)
print('Status:', r.status_code)

tool_results = []
all_events = []

for line in r.iter_lines():
    if line:
        decoded = line.decode('utf-8')
        if decoded.startswith('data: '):
            try:
                event = json.loads(decoded[6:])
                event_type = event.get('type', '')
                all_events.append(event_type)
                
                if event_type == 'tool_end':
                    print(f'\n  Event: {event_type}')
                    print(f'    Tool name: {event.get("tool_name")}')
                    print(f'    Has output field: {"output" in event}')
                    if event.get('output'):
                        output = event.get('output')
                        print(f'    Output preview: {output[:500]}...')
                        try:
                            parsed = json.loads(output)
                            print(f'    Parsed successfully! Keys: {list(parsed.keys())}')
                            if 'products_by_supplier' in parsed:
                                print(f'    Found products_by_supplier with suppliers: {list(parsed["products_by_supplier"].keys())}')
                            if 'products_by_category' in parsed:
                                print(f'    Found products_by_category!')
                        except Exception as e:
                            print(f'    Parse error: {e}')
                        tool_results.append(event)
            except Exception as e:
                print(f'Parse error: {e}')

print(f'\nAll event types: {set(all_events)}')
print(f'Total tool_end events with output: {len(tool_results)}')
