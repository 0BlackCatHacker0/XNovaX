"""
Hivemind Batch Merge
====================
Reads incoming_batch.json, merges into registry_models_live.json (deduped).
Called by Hivemind's /hive/models/bulk endpoint.
"""
import json, os

LIVE = "C:/NovaX/tmp/registry_models_live.json"
BATCH = "C:/NovaX/tmp/incoming_batch.json"

# Read existing
existing = []
if os.path.exists(LIVE):
    try:
        existing = json.load(open(LIVE))
    except:
        pass

# Read incoming batch
incoming = []
if os.path.exists(BATCH):
    try:
        incoming = json.load(open(BATCH))
    except:
        pass

# Merge and dedup
merged = list(dict.fromkeys(existing + incoming))

# Write back
os.makedirs("C:/NovaX/tmp", exist_ok=True)
with open(LIVE, "w") as f:
    json.dump(merged, f)

print(json.dumps({"added": len(incoming), "total": len(merged)}))
