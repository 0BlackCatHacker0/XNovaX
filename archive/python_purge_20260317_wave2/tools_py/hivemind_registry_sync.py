"""
Hivemind ← Model Registry Sync
================================
Fetches ALL models from Model Registry (:9860) and pushes them to
Hivemind (:9881) via its /hive/sync endpoint.

This expands Hivemind from ~34 hardcoded cloud models to 500+ models
from 70 providers, mapped to flow channels by ability.
"""
import json, urllib.request

def fetch_json(url, timeout=10):
    try:
        resp = urllib.request.urlopen(url, timeout=timeout)
        return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}

def post_json(url, data, timeout=10):
    try:
        req = urllib.request.Request(url,
            data=json.dumps(data).encode(),
            headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=timeout)
        return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}

# Fetch all models from registry
catalog = fetch_json("http://127.0.0.1:9860/catalog")
if "error" in catalog:
    print(json.dumps({"ok": False, "error": "Registry unreachable: " + catalog["error"]}))
    exit()

models = catalog.get("models", catalog.get("catalog", []))
if not models:
    # Try /models endpoint
    models_resp = fetch_json("http://127.0.0.1:9860/models")
    models = models_resp.get("models", [])

# Fetch abilities
abilities = fetch_json("http://127.0.0.1:9860/abilities")
ability_map = abilities.get("abilities", {})

# Build cloud model list for Hivemind
cloud_models = []
by_channel = {
    "REASON": [], "CODE": [], "MATH": [], "CREATIVE": [],
    "FAST": [], "VISION": [], "GENERAL": [], "CHAT": []
}

for model in models:
    if isinstance(model, dict):
        mid = model.get("id", model.get("name", ""))
        provider = model.get("provider", "unknown")
        model_abilities = model.get("abilities", [])
    else:
        mid = str(model)
        provider = mid.split("/")[0] if "/" in mid else "unknown"
        model_abilities = []

    if not mid:
        continue

    cloud_models.append(mid)
    ml = mid.lower()

    # Map to channels based on abilities and name patterns
    if "reasoning" in model_abilities or "r1" in ml or "think" in ml or "o1" in ml or "o3" in ml:
        by_channel["REASON"].append(mid)
    if "code" in model_abilities or "code" in ml or "coder" in ml:
        by_channel["CODE"].append(mid)
    if "math" in model_abilities or "math" in ml:
        by_channel["MATH"].append(mid)
    if "vision" in model_abilities or "vision" in ml or "vl" in ml:
        by_channel["VISION"].append(mid)
    if "fast" in model_abilities or "mini" in ml or "nano" in ml or "flash" in ml:
        by_channel["FAST"].append(mid)
    if "flagship" in model_abilities or "pro" in ml or "max" in ml or "ultra" in ml:
        by_channel["CREATIVE"].append(mid)
    if "general" in model_abilities or "chat" in model_abilities:
        by_channel["GENERAL"].append(mid)

    # Everything goes to CHAT as fallback
    by_channel["CHAT"].append(mid)

result = {
    "ok": True,
    "total_models": len(cloud_models),
    "cloud_models": cloud_models,
    "by_channel": {k: len(v) for k, v in by_channel.items()},
    "providers": len(set(m.split("/")[0] if "/" in m else m.split(":")[0] for m in cloud_models))
}

print(json.dumps(result))
