"""Discover all models, classify into Go territories, and POST to Cloud Router."""
import json, sys, urllib.request

TERRITORY_PATTERNS = {
    "code": ["code", "coder", "starcoder", "codellama", "sqlcoder", "codegen", "codegeex", "granite-code", "wizardcoder", "deepseek-coder", "qwen2.5-coder"],
    "reasoning": ["o1-", "o3-", "o4-", "deepseek-r1", "reasoning", "think", "reflection"],
    "image": ["vision", "llava", "bakllava", "dall", "stable-diffusion", "image", "moondream"],
    "audio": ["whisper", "audio", "tts", "speech"],
    "embedding": ["embed", "nomic", "bge", "e5-", "minilm", "mxbai"],
    "fast": ["tiny", "mini", ":1b", "-1b", ":3b", "-3b", "phi-2", "gemma-2b", "flash", "haiku", "instant"],
}

MAX_TOKENS = {
    "chat": 8192, "code": 16384, "reasoning": 32768, "image": 4096,
    "audio": 4096, "embedding": 512, "fast": 2048,
}

def classify(name):
    nl = name.lower()
    terrs = []
    for terr, patterns in TERRITORY_PATTERNS.items():
        if any(p in nl for p in patterns):
            terrs.append(terr)
    if not terrs:
        terrs = ["chat"]
    return terrs

def main():
    # Discover models
    all_models = []
    try:
        resp = urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=3)
        data = json.loads(resp.read())
        for m in data.get("models", []):
            all_models.append(("ollama", m.get("name", "")))
    except Exception:
        pass

    try:
        with open("C:/NovaX/cloud_config.json", "r") as f:
            cfg = json.load(f)
        for prov, pdata in cfg.items():
            if not isinstance(pdata, dict):
                continue
            models = pdata.get("models", [])
            if isinstance(models, list):
                for m in models:
                    mid = m.get("id", m.get("model", "")) if isinstance(m, dict) else str(m)
                    all_models.append((prov, mid))
            elif "model" in pdata:
                all_models.append((prov, pdata["model"]))
    except Exception:
        pass

    # Classify and build pieces
    pieces = {}
    by_territory = {}
    for provider, model in all_models:
        if not model:
            continue
        terrs = classify(model)
        for terr in terrs:
            key = f"{provider}:{model}:{terr}"
            pieces[key] = {
                "provider": provider, "model": model, "territory": terr,
                "max_tokens": MAX_TOKENS.get(terr, 8192), "wins": 0, "losses": 0, "active": 1,
            }
            by_territory[terr] = by_territory.get(terr, 0) + 1

    # Output summary
    total = len(pieces)
    # Write full data to file (too large for shell stdout)
    with open("C:/NovaX/data/go_pieces.json", "w") as f:
        json.dump({"total": total, "by_territory": by_territory, "pieces": pieces}, f)
    # Print just the summary for NovaLang
    print(json.dumps({"total": total, "by_territory": by_territory, "file": "C:/NovaX/data/go_pieces.json"}))

if __name__ == "__main__":
    main()
