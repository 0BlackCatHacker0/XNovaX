"""Quick test for nova_service_creator.py endpoints"""
import urllib.request
import json

BASE = "http://127.0.0.1:9942"

def get(path):
    r = urllib.request.urlopen(BASE + path, timeout=5)
    return json.loads(r.read().decode())

def post(path, data):
    payload = json.dumps(data).encode()
    req = urllib.request.Request(BASE + path, data=payload,
                                 headers={"Content-Type": "application/json"})
    r = urllib.request.urlopen(req, timeout=30)
    return json.loads(r.read().decode())

print("=== /health ===")
print(json.dumps(get("/health"), indent=2))

print("\n=== /ports ===")
ports = get("/ports")
print(f"Available: {ports['available_count']} ports")
print(f"Range: {ports['range']}")

print("\n=== /list (empty) ===")
print(json.dumps(get("/list"), indent=2))

print("\n=== POST /create (cpu-monitor) ===")
result = post("/create", {
    "description": "Monitor CPU temperature and alert when above 80C",
    "name": "cpu-monitor"
})
print(json.dumps(result, indent=2))

print("\n=== POST /create (data-cleaner) ===")
result2 = post("/create", {
    "description": "Transform and clean CSV data, removing duplicates",
    "name": "data-cleaner"
})
print(json.dumps(result2, indent=2))

print("\n=== POST /create (webhook-handler) ===")
result3 = post("/create", {
    "description": "Listen for GitHub webhook events and trigger CI builds",
    "name": "github-webhook"
})
print(json.dumps(result3, indent=2))

print("\n=== /list (after creation) ===")
lst = get("/list")
print(f"Services: {lst['count']}")
for name, svc in lst["services"].items():
    print(f"  {name}: port={svc['port']} template={svc['template']} status={svc['status']}")

print("\n=== /source/cpu-monitor (first 10 lines) ===")
src = get("/source/cpu-monitor")
lines = src["source"].split("\n")[:10]
for l in lines:
    print(f"  {l}")

print("\n=== /ports (after creation) ===")
ports2 = get("/ports")
print(f"Available: {ports2['available_count']} ports")
print(f"Used: {ports2['used']}")

print("\n=== ALL TESTS PASSED ===")
