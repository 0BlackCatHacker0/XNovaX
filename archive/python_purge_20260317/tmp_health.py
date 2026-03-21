import json, urllib.request
try:
    req = urllib.request.Request('http://127.0.0.1:9999/api/services/health')
    with urllib.request.urlopen(req, timeout=5) as resp:
        data = json.loads(resp.read())
    svcs = data.get('services', [])
    up = sum(1 for s in svcs if s.get('trit') == 1)
    down = [s['name'] for s in svcs if s.get('trit') != 1]
    print(f"Fleet: {up}/{len(svcs)} up")
    if down:
        print(f"Down ({len(down)}): {', '.join(down)}")
    else:
        print("ALL SERVICES UP!")
except Exception as e:
    print(f"Orchestrator unreachable: {e}")
