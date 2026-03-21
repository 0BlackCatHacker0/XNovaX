"""
Hivemind Model Injector (Post-Boot)
====================================
Fetches models from Model Registry (:9860) and injects them into
Hivemind (:9881) via POST /hive/models/bulk in batches of 50.
"""
import json, urllib.request

def fetch_json(url, timeout=10):
    try:
        resp = urllib.request.urlopen(url, timeout=timeout)
        return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}

def post_json(url, data, timeout=15):
    try:
        req = urllib.request.Request(url,
            data=json.dumps(data).encode(),
            headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=timeout)
        return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}

# Check Hivemind is up
hive = fetch_json("http://127.0.0.1:9881/health")
if "error" in hive:
    print(json.dumps({"ok": False, "error": "Hivemind unreachable"}))
    exit()

# Fetch models from Model Registry
catalog = fetch_json("http://127.0.0.1:9860/catalog")
if "error" in catalog:
    print(json.dumps({"ok": False, "error": "Registry unreachable"}))
    exit()

# Extract model IDs from providers dict
models = []
providers = catalog.get("providers", {})
for prov, model_list in providers.items():
    if isinstance(model_list, list):
        for m in model_list:
            if isinstance(m, dict):
                mid = m.get("id", m.get("name", ""))
            else:
                mid = str(m)
            if mid:
                models.append(mid)

# Inject in batches of 50
BATCH = 50
total_added = 0
batches = 0
for i in range(0, len(models), BATCH):
    batch = models[i:i+BATCH]
    result = post_json("http://127.0.0.1:9881/hive/models/bulk", {"models": batch})
    if "error" not in result:
        total_added += (result.get("added") or 0)
        batches += 1

print(json.dumps({
    "ok": True,
    "registry_models": len(models),
    "injected": total_added,
    "batches": batches,
    "providers": len(providers)
}))
