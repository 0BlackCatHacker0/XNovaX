"""Discover ALL models from every provider API + cloud_config and build complete registry."""
import json, os, sys, urllib.request, ssl

# Skip SSL verification for API calls
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def api_get(url, headers=None, timeout=10):
    """GET request with optional auth headers."""
    req = urllib.request.Request(url, headers=headers or {})
    try:
        resp = urllib.request.urlopen(req, timeout=timeout, context=ctx)
        return json.loads(resp.read())
    except Exception as e:
        return None

def api_get_openrouter(key):
    """OpenRouter has the biggest catalog — 300+ models."""
    data = api_get("https://openrouter.ai/api/v1/models", {"Authorization": f"Bearer {key}"})
    if not data:
        return []
    models = []
    for m in data.get("data", []):
        mid = m.get("id", "")
        if mid:
            models.append({"provider": "openrouter", "model": mid, "context": m.get("context_length", 4096)})
    return models

def api_get_openai(key):
    """OpenAI models list."""
    data = api_get("https://api.openai.com/v1/models", {"Authorization": f"Bearer {key}"})
    if not data:
        return []
    models = []
    for m in data.get("data", []):
        mid = m.get("id", "")
        if mid and not mid.startswith("ft:"):  # skip fine-tunes
            models.append({"provider": "openai", "model": mid})
    return models

def api_get_ollama():
    """Local Ollama models."""
    data = api_get("http://127.0.0.1:11434/api/tags", timeout=3)
    if not data:
        return []
    return [{"provider": "ollama", "model": m.get("name", "")} for m in data.get("models", [])]

def api_get_groq(key):
    """Groq models."""
    data = api_get("https://api.groq.com/openai/v1/models", {"Authorization": f"Bearer {key}"})
    if not data:
        return []
    return [{"provider": "groq", "model": m.get("id", "")} for m in data.get("data", []) if m.get("id")]

def api_get_mistral(key):
    """Mistral models."""
    data = api_get("https://api.mistral.ai/v1/models", {"Authorization": f"Bearer {key}"})
    if not data:
        return []
    return [{"provider": "mistral", "model": m.get("id", "")} for m in data.get("data", []) if m.get("id")]

def api_get_together(key):
    """Together AI models."""
    data = api_get("https://api.together.xyz/v1/models", {"Authorization": f"Bearer {key}"})
    if not data:
        return []
    return [{"provider": "together", "model": m.get("id", "")} for m in data.get("data", []) if m.get("id")]

def get_cloud_config_models():
    """Models already in cloud_config.json."""
    try:
        cfg = json.load(open("C:/NovaX/cloud_config.json"))
    except:
        return []
    models = []
    for prov, pdata in cfg.items():
        if not isinstance(pdata, dict):
            continue
        mlist = pdata.get("models", [])
        if isinstance(mlist, list):
            for m in mlist:
                if isinstance(m, dict):
                    mid = m.get("id", m.get("model", ""))
                else:
                    mid = str(m)
                if mid:
                    models.append({"provider": prov, "model": mid})
        elif "model" in pdata:
            models.append({"provider": prov, "model": pdata["model"]})
    return models

# Territory classification patterns
TERRITORY_PATTERNS = {
    "code": ["code", "coder", "starcoder", "codellama", "sqlcoder", "codegen", "codegeex",
             "granite-code", "wizardcoder", "deepseek-coder", "qwen2.5-coder", "codestral",
             "stable-code", "phind", "replit", "magicoder", "octocoder", "sourcegraph",
             "cursor", "aider", "copilot", "code-davinci", "code-cushman"],
    "reasoning": ["o1-", "o3-", "o4-", "deepseek-r1", "reasoning", "think", "reflection",
                   "qwq", "orca", "reasoner", "chain-of-thought", "cot"],
    "image": ["vision", "llava", "bakllava", "dall", "stable-diffusion", "image", "moondream",
              "cogvlm", "internvl", "fuyu", "img", "pix", "visual", "clip", "siglip",
              "flux", "midjourney", "sdxl", "kandinsky", "playground-v"],
    "audio": ["whisper", "audio", "tts", "speech", "voice", "sound", "music",
              "bark", "tortoise", "coqui", "xtts", "parler"],
    "embedding": ["embed", "nomic", "bge", "e5-", "minilm", "mxbai", "jina-embed",
                   "text-embedding", "voyage", "cohere-embed", "gte-"],
    "fast": ["tiny", "mini", ":1b", "-1b", ":3b", "-3b", "phi-2", "gemma-2b",
             "flash", "haiku", "instant", "lite", "nano", "small", "turbo",
             "smollm", "tinyllama", "orca-mini", "stablelm-zephyr"],
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
    # Load cloud config for API keys
    try:
        cfg = json.load(open("C:/NovaX/cloud_config.json"))
    except:
        cfg = {}

    def get_key(provider):
        pdata = cfg.get(provider, {})
        if isinstance(pdata, dict):
            return pdata.get("key") or pdata.get("api_key")
        return None

    all_models = []
    sources = {}

    # 1. Ollama (local)
    ollama = api_get_ollama()
    all_models.extend(ollama)
    sources["ollama"] = len(ollama)

    # 2. OpenAI (live API)
    openai_key = os.environ.get("OPENAI_API_KEY") or get_key("openai")
    if openai_key:
        openai_models = api_get_openai(openai_key)
        all_models.extend(openai_models)
        sources["openai_api"] = len(openai_models)

    # 3. OpenRouter (biggest catalog)
    or_key = get_key("openrouter")
    if or_key:
        or_models = api_get_openrouter(or_key)
        all_models.extend(or_models)
        sources["openrouter_api"] = len(or_models)

    # 4. Groq
    groq_key = get_key("groq")
    if groq_key:
        groq_models = api_get_groq(groq_key)
        all_models.extend(groq_models)
        sources["groq_api"] = len(groq_models)

    # 5. Mistral
    mistral_key = get_key("mistral")
    if mistral_key:
        mistral_models = api_get_mistral(mistral_key)
        all_models.extend(mistral_models)
        sources["mistral_api"] = len(mistral_models)

    # 6. Together
    together_key = get_key("together")
    if together_key:
        together_models = api_get_together(together_key)
        all_models.extend(together_models)
        sources["together_api"] = len(together_models)

    # 7. Cloud config (catches anthropic, google, deepseek, cohere, local proxies)
    cc_models = get_cloud_config_models()
    all_models.extend(cc_models)
    sources["cloud_config"] = len(cc_models)

    # Deduplicate by provider:model
    seen = set()
    unique = []
    for m in all_models:
        key = f"{m['provider']}:{m['model']}"
        if key not in seen:
            seen.add(key)
            unique.append(m)

    # Classify and build pieces
    pieces = {}
    by_territory = {}
    for m in unique:
        provider = m["provider"]
        model = m["model"]
        if not model:
            continue
        terrs = classify(model)
        ctx = m.get("context", 0)
        for terr in terrs:
            key = f"{provider}:{model}:{terr}"
            max_tok = MAX_TOKENS.get(terr, 8192)
            # If we got context length from API, use it if larger
            if ctx and ctx > max_tok:
                max_tok = min(ctx, 128000)  # cap at 128k
            pieces[key] = {
                "provider": provider, "model": model, "territory": terr,
                "max_tokens": max_tok, "wins": 0, "losses": 0, "active": 1,
            }
            by_territory[terr] = by_territory.get(terr, 0) + 1

    total = len(pieces)

    # Preserve win/loss data from existing registry
    try:
        old = json.load(open("C:/NovaX/data/go_pieces.json"))
        old_pieces = old.get("pieces", {})
        for key, piece in pieces.items():
            if key in old_pieces:
                piece["wins"] = old_pieces[key].get("wins", 0)
                piece["losses"] = old_pieces[key].get("losses", 0)
    except:
        pass

    # Write full registry
    output = {
        "total": total,
        "unique_models": len(unique),
        "by_territory": by_territory,
        "sources": sources,
        "pieces": pieces,
    }
    with open("C:/NovaX/data/go_pieces.json", "w") as f:
        json.dump(output, f)

    # Print summary
    print(json.dumps({
        "total_pieces": total,
        "unique_models": len(unique),
        "by_territory": by_territory,
        "sources": sources,
        "file": "C:/NovaX/data/go_pieces.json"
    }))

if __name__ == "__main__":
    main()
