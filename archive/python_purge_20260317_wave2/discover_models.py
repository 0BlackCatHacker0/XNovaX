"""Discover all models from Ollama + cloud_config.json and output as JSON list."""
import json, sys, urllib.request

def main():
    all_models = []

    # Ollama models
    try:
        resp = urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=3)
        data = json.loads(resp.read())
        for m in data.get("models", []):
            all_models.append({"provider": "ollama", "model": m.get("name", "")})
    except Exception:
        pass

    # Cloud config models
    try:
        with open("C:/NovaX/cloud_config.json", "r") as f:
            cfg = json.load(f)
        for prov_name, prov_data in cfg.items():
            if not isinstance(prov_data, dict):
                continue
            models = prov_data.get("models", [])
            if isinstance(models, list):
                for m in models:
                    if isinstance(m, dict):
                        mid = m.get("id", m.get("model", ""))
                    else:
                        mid = str(m)
                    all_models.append({"provider": prov_name, "model": mid})
            # Single model entry
            elif "model" in prov_data and not models:
                all_models.append({"provider": prov_name, "model": prov_data["model"]})
    except Exception:
        pass

    print(json.dumps(all_models))

if __name__ == "__main__":
    main()
