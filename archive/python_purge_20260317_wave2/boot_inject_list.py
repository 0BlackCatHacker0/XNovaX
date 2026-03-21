"""Output ALL models from go_pieces.json for boot-time Mirror injection."""
import json
try:
    d = json.load(open("C:/NovaX/data/go_pieces.json"))
    pieces = d.get("pieces", {})
    models = []
    for v in pieces.values():
        models.append({"id": v.get("model", ""), "provider": v.get("provider", "")})
    print(json.dumps({"count": len(models), "models": models}))
except Exception as e:
    print(json.dumps({"count": 0, "models": [], "error": str(e)}))
