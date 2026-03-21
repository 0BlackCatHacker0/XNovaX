"""
Hivemind Model Merge
====================
Reads existing models from a JSON file, fetches registry models,
merges them (deduped), and writes the result back.
Input:  C:/NovaX/tmp/existing_models.json  (written by NovaLang before calling this)
Output: C:/NovaX/tmp/merged_models.json    (read by NovaLang after this returns)
Also prints JSON summary to stdout.
"""
import json, urllib.request, os

def fetch_json(url, timeout=10):
    try:
        resp = urllib.request.urlopen(url, timeout=timeout)
        return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}

# Read existing models (written by NovaLang)
existing = []
try:
    with open("C:/NovaX/tmp/existing_models.json") as f:
        existing = json.load(f)
except:
    pass

# Fetch from registry — providers is dict of provider→model_list
catalog = fetch_json("http://127.0.0.1:9860/catalog")
models = []
if "error" not in catalog:
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

# Merge and dedup (preserving order)
merged = list(dict.fromkeys(existing + models))

# Write merged result
os.makedirs("C:/NovaX/tmp", exist_ok=True)
with open("C:/NovaX/tmp/merged_models.json", "w") as f:
    json.dump(merged, f)

print(json.dumps({
    "ok": True,
    "existing": len(existing),
    "registry": len(models),
    "merged": len(merged)
}))
