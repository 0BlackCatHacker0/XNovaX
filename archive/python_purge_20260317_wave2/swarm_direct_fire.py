"""
NovaX Swarm DIRECT FIRE — Bypass cloud router, hit APIs directly
Concurrent threads, multiple providers, deep context upgrade tasks
"""
import urllib.request, json, time, os, threading, ssl

OUT_DIR = "C:/NovaX/swarm_upgrades"
os.makedirs(OUT_DIR, exist_ok=True)
ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

NOVA_CTX = """You are upgrading NovaX, an AI Operating System with 111 services, 29 providers, 510K+ models.
Language: NovaLang (.nova files, ternary-native Rust VM). Key syntax:
- if3/match3/try3/while3 (3-way branching: +1/0/-1)
- dict_set() returns NEW dict (MUST reassign: d = dict_set(d, k, v))
- append() returns NEW list (MUST reassign: l = append(l, item))
- dict_get() only on dicts, bracket syntax for lists: list[i]
- try3 { expr } { fallback } (NO fail keyword)
- http_post(url, json_encode(body)) (must encode)
- shell() returns {ok, stdout, stderr, code} dict
- No || or && operators (use nested if3)
- tserve(PORT, NAME) with troute() for HTTP endpoints
Architecture: Orchestrator(:9999) -> CloudRouter(:9878) -> Fractal(:9874) -> Hivemind(:9881)
N-S Flow: Reynolds Re=rho*u*L/mu, harmonics 3-5-7-13, Chladni routing, Kolmogorov cascade
Write production-ready code. Follow ALL gotchas above."""

# Provider configs with actual working endpoints
PROVIDERS = {
    "openai": {
        "url": "https://api.openai.com/v1/chat/completions",
        "key": os.environ.get("OPENAI_API_KEY", ""),
        "model": "gpt-4.1-nano",
        "type": "openai"
    },
    "openrouter-free1": {
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "key": "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",
        "model": "meta-llama/llama-3.3-70b-instruct:free",
        "type": "openai"
    },
    "openrouter-free2": {
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "key": "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",
        "model": "qwen/qwen3-coder:free",
        "type": "openai"
    },
    "openrouter-free3": {
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "key": "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",
        "model": "deepseek/deepseek-chat-v3.1",
        "type": "openai"
    },
    "openrouter-free4": {
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "key": "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",
        "model": "google/gemma-3-27b-it:free",
        "type": "openai"
    },
    "openrouter-free5": {
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "key": "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",
        "model": "nousresearch/hermes-3-llama-3.1-405b:free",
        "type": "openai"
    },
    "openrouter-free6": {
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "key": "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",
        "model": "arcee-ai/trinity-large-preview:free",
        "type": "openai"
    },
    "openrouter-free7": {
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "key": "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",
        "model": "nvidia/nemotron-3-nano-30b-a3b:free",
        "type": "openai"
    },
    "openrouter-deepseek-r1": {
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "key": "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",
        "model": "deepseek/deepseek-r1-0528",
        "type": "openai"
    },
    "cerebras": {
        "url": "https://api.cerebras.ai/v1/chat/completions",
        "key": "",  # loaded from config
        "model": "qwen-3-235b-a22b-instruct-2507",
        "type": "openai"
    },
    "google-ai-studio": {
        "url": "",  # special handling
        "key": "",  # loaded from config
        "model": "gemini-2.0-flash",
        "type": "google"
    },
    "sambanova": {
        "url": "https://api.sambanova.ai/v1/chat/completions",
        "key": "",
        "model": "Meta-Llama-3.3-70B-Instruct",
        "type": "openai"
    }
}

# Load keys from cloud_config
try:
    with open("C:/NovaX/cloud_config.json") as f:
        cc = json.load(f)
    # OpenAI key
    if not PROVIDERS["openai"]["key"]:
        PROVIDERS["openai"]["key"] = cc.get("openai", {}).get("key", "")
    # Cerebras
    PROVIDERS["cerebras"]["key"] = cc.get("cerebras_direct", {}).get("key", "")
    # Google AI Studio
    PROVIDERS["google-ai-studio"]["key"] = cc.get("google_ai_studio", {}).get("key", "")
    # SambaNova
    PROVIDERS["sambanova"]["key"] = cc.get("sambanova_direct", {}).get("key", "")
    print(f"Loaded keys from cloud_config.json", flush=True)
except Exception as e:
    print(f"Warning: {e}", flush=True)

TASKS = [
    ("router-enhance", "Improve Cloud Router: smart Chladni-based provider selection, Reynolds quality scoring, ternary exponential backoff failover. Write NovaLang code with function signatures."),
    ("hive-token-max", "Token maximizer: Kolmogorov cascade decomposition of tasks, parallel multi-provider dispatch, N-S synthesis. Write NovaLang micro-tool for millions tok/hr."),
    ("fractal-depth", "Fractal Engine enhancement: adaptive depth via Reynolds number, recursive 3-13 child splitting, Chladni frequency modulation for routing. Write NovaLang code."),
    ("swarm-consensus", "Swarm consensus algorithm: N-S Reynolds scoring of responses, ternary fingerprint grouping, best-parts synthesis, balanced ternary voting. Write NovaLang."),
    ("self-heal", "Self-healing service mesh: health3() monitoring 111 services, auto-restart via shell(), degraded detection, Reynolds flow regime classification. Write NovaLang."),
    ("vm-optimize", "NovaLang VM optimization: HAMT persistent data structures replacing clone-on-write, auto JSON parsing in tserve, async request handling. Write Rust code."),
    ("tripple-enhance", "Tripple search engine: Chladni 9 eigenmodes for domain classification, multi-provider parallel search, Reynolds dedup+ranking, model discovery. Write NovaLang."),
    ("event-system", "Event-driven architecture: central event bus service, publish/subscribe pattern, ternary event classification (+1/0/-1), fleet coordination. Write NovaLang."),
    ("security-harden", "Security: ternary rate-limiting with trit states, JSON schema validation, balanced ternary request signing (bt_pack), cross-service audit log. Write NovaLang."),
    ("perf-benchmark", "Benchmark suite: identical prompts to all providers, Reynolds number scoring, ternary leaderboard, auto-tune cascade order from results. Write NovaLang."),
    ("knowledge-graph", "Knowledge graph: nodes=services+providers+models, ternary edge weights, bt() encoded relationships, optimal routing path-finder. Write NovaLang."),
    ("swarm-codegen", "Swarm code generator: description->multi-provider fire->collect code->ternary voting->best impl->novalang.exe syntax check. Write NovaLang."),
    ("stdlib-enhance", "Enhance NovaLang stdlib: add graph3 module (graph operations), crypto3 (ternary hashing), stream3 (data streaming), cluster3 (service clustering). Write NovaLang."),
]

# Results
lock = threading.Lock()
results = []
total_tokens = 0
total_hits = 0

def call_openai_api(url, key, model, prompt, max_tokens=2048):
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.7
    }).encode()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}"
    }
    if "openrouter" in url:
        headers["HTTP-Referer"] = "https://novax.ai"
    req = urllib.request.Request(url, data=body, headers=headers)
    resp = urllib.request.urlopen(req, timeout=120, context=ssl_ctx)
    data = json.loads(resp.read().decode())
    text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    return text

def call_google_api(key, model, prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": 2048}
    }).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    resp = urllib.request.urlopen(req, timeout=120, context=ssl_ctx)
    data = json.loads(resp.read().decode())
    text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
    return text

def fire(provider_name, task_id, task_desc):
    global total_tokens, total_hits
    prov = PROVIDERS[provider_name]
    if not prov.get("key"):
        return
    prompt = NOVA_CTX + "\n\nTASK: " + task_desc
    try:
        if prov["type"] == "google":
            text = call_google_api(prov["key"], prov["model"], prompt)
        else:
            text = call_openai_api(prov["url"], prov["key"], prov["model"], prompt)

        tokens = len(text.split())
        if tokens > 10:
            with lock:
                total_tokens += tokens
                total_hits += 1
                results.append({"task": task_id, "provider": provider_name,
                              "model": prov["model"], "tokens": tokens})
            fname = f"{OUT_DIR}/{task_id}_{provider_name}.json"
            with open(fname, "w", encoding="utf-8") as f:
                json.dump({"task": task_id, "provider": provider_name,
                          "model": prov["model"], "tokens": tokens, "text": text}, f, ensure_ascii=False)
            print(f"  HIT  {task_id} | {provider_name} ({prov['model']}): {tokens} tok | Running total: {total_tokens}", flush=True)
        else:
            print(f"  MISS {task_id} | {provider_name}: too short ({tokens}w)", flush=True)
    except Exception as e:
        err = str(e)[:80]
        print(f"  FAIL {task_id} | {provider_name}: {err}", flush=True)

print("=" * 65, flush=True)
print("NOVA SWARM DIRECT FIRE — BYPASSING CLOUD ROUTER", flush=True)
print(f"Tasks: {len(TASKS)} | Providers: {len(PROVIDERS)} | Max: {len(TASKS)*len(PROVIDERS)}", flush=True)
active = sum(1 for p in PROVIDERS.values() if p.get("key"))
print(f"Active providers (with keys): {active}", flush=True)
print("=" * 65, flush=True)

t0 = time.time()

# Fire in waves: 3 concurrent threads per wave (respect rate limits)
provider_names = [k for k, v in PROVIDERS.items() if v.get("key")]

for ti, (task_id, task_desc) in enumerate(TASKS):
    print(f"\n--- Task {ti+1}/{len(TASKS)}: {task_id} ---", flush=True)
    threads = []
    for pname in provider_names:
        t = threading.Thread(target=fire, args=(pname, task_id, task_desc))
        threads.append(t)
    # Start in groups of 4 with 1s spacing
    for i in range(0, len(threads), 4):
        batch = threads[i:i+4]
        for t in batch:
            t.start()
        time.sleep(1.5)  # pace between batches
    # Wait for all
    for t in threads:
        t.join(timeout=180)
    elapsed = time.time() - t0
    print(f"  [Progress] {total_hits} hits, {total_tokens} tokens, {elapsed:.0f}s", flush=True)

elapsed = time.time() - t0

print(f"\n{'=' * 65}", flush=True)
print(f"SWARM DIRECT FIRE COMPLETE", flush=True)
print(f"Hits:    {total_hits}/{len(TASKS)*len(provider_names)}", flush=True)
print(f"Tokens:  {total_tokens}", flush=True)
print(f"Time:    {elapsed:.0f}s", flush=True)
print(f"Rate:    {total_tokens/max(elapsed,1):.0f} tok/s", flush=True)
print(f"Files:   {OUT_DIR}/", flush=True)
print(f"{'=' * 65}", flush=True)

# Provider breakdown
print("\nProvider breakdown:", flush=True)
prov_stats = {}
for r in results:
    p = r["provider"]
    if p not in prov_stats:
        prov_stats[p] = {"hits": 0, "tokens": 0}
    prov_stats[p]["hits"] += 1
    prov_stats[p]["tokens"] += r["tokens"]
for p, s in sorted(prov_stats.items(), key=lambda x: x[1]["tokens"], reverse=True):
    print(f"  {p}: {s['hits']} hits, {s['tokens']} tokens", flush=True)

# Save summary
with open(f"{OUT_DIR}/swarm_summary.json", "w") as f:
    json.dump({
        "tasks": len(TASKS), "providers": len(provider_names),
        "hits": total_hits, "tokens": total_tokens,
        "elapsed": round(elapsed, 1),
        "rate": round(total_tokens/max(elapsed,1), 1),
        "results": results
    }, f, indent=2)
