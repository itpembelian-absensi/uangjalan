import urllib.request
import json

try:
    req = urllib.request.Request('http://127.0.0.1:8001/api/toll-sections')
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode())
        found = False
        for s in data:
            if 'merak' in s.get('name', '').lower() or 'tangerang' in s.get('name', '').lower():
                print(f"Found via API 8001: {s['name']}, active: {s['is_active']}")
                found = True
        if not found:
            print('Not found in API 8001 response')
except Exception as e:
    print(f'Error: {e}')
