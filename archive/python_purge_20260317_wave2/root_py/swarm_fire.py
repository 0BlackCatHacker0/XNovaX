"""
NovaX Swarm FIRE — Sequential, paced, all providers, deep context
One query at a time to respect tserve single-threaded nature
"""
import urllib.request, json, time, os, sys

ROUTER = "http://127.0.0.1:9878/query"
OUT_DIR = "C:/NovaX/swarm_upgrades"
os.makedirs(OUT_DIR, exist_ok=True)

NOVA_CTX = """NovaX: AI OS, 111 services, 29 providers, 510K models.
NovaLang: ternary Rust VM (.nova), if3/match3/try3/while3.
GOTCHAS: dict_set returns NEW dict (reassign!), append returns NEW list (reassign!),
dict_get only on dicts not lists (use brackets), try3 { } { fallback } (no fail keyword),
http_post needs json_encode(), shell() returns dict, no || or &&.
Arch: Orchestrator(:9999)->CloudRouter(:9878)->Hivemind(:9881)->FractalEngine(:9874)
N-S: Reynolds Re=rho*u*L/mu, 3-5-7-13 harmonics, Chladni routing, Kolmogorov cascade.
Ternary: +1/0/-1, MAYBE valid, negation=flip trits, bt() balanced ternary."""

TASKS = [
    ("router-enhance", "Improve Cloud Router: smart provider selection via Chladni, Reynolds quality scoring, ternary failover with backoff. Write NovaLang code."),
    ("hive-token-max", "Token maximizer for Hivemind: Kolmogorov cascade task decomposition, parallel provider dispatch, synthesis. Goal: millions tok/hr. Write NovaLang."),
    ("fractal-depth", "Enhance Fractal Engine: adaptive depth via Reynolds, recursive splitting 3-13 children, Chladni frequency modulation. Write NovaLang."),
    ("swarm-consensus", "Swarm consensus: N-S Reynolds scoring, ternary fingerprint grouping, best-parts synthesis, balanced ternary voting. Write NovaLang."),
    ("self-heal", "Self-healing mesh for 111 services: health3() monitoring, auto-restart crashed, detect degraded trit 0, Reynolds flow regime. Write NovaLang."),
    ("vm-optimize", "NovaLang Rust VM optimization: HAMTs for dict_set/append O(1), auto JSON body parse in tserve, async request handling. Write Rust code."),
    ("quant-hardware", "Quantized hardware integration: route ternary to BitNet(:9925), standard to Ollama/cloud, use hardware service(:9943) data. Write NovaLang."),
    ("tripple-enhance", "Tripple search: Chladni 9 eigenmodes, fire all providers, deduplicate with Reynolds, discover+lock new models. Write NovaLang."),
    ("event-system", "Event-driven architecture: central event bus, services publish success/info/error events, ternary classification. Write NovaLang."),
    ("security-harden", "Security: ternary rate-limiting, JSON validation, balanced ternary request signing, audit logging. Write NovaLang."),
    ("perf-benchmark", "Benchmark suite: test all providers identical prompts, Reynolds scoring, ternary leaderboard, auto-tune cascade. Write NovaLang."),
    ("knowledge-graph", "Knowledge graph: 111 services + 29 providers + 510K models as nodes, ternary edge weights, path-finding. Write NovaLang."),
    ("swarm-codegen", "Swarm code generator: description->fire 5+ providers->collect code->ternary voting->best impl->syntax validate. Write NovaLang."),
]

PROVIDERS = [
    "ollama", "openai", "anthropic", "cerebras_direct",
    "sambanova_direct", "google_ai_studio", "openrouter",
    "mistral", "groq", "deepseek", "cohere", "together",
    "google", "cortex", "novax-prime"
]

total_tokens = 0
total_hits = 0
total_queries = 0
t0 = time.time()

def query(prompt, provider, task_id):
    global total_tokens, total_hits, total_queries
    total_queries += 1
    body = json.dumps({"prompt": prompt, "provider": provider, "max_tokens": 2048}).encode()
    req = urllib.request.Request(ROUTER, data=body, headers={"Content-Type": "application/json"})
    try:
        resp = urllib.request.urlopen(req, timeout=90)
        data = json.loads(resp.read().decode())
        text = data.get("text", data.get("response", ""))
        tokens = len(text.split())
        if tokens > 5:
            total_tokens += tokens
            total_hits += 1
            fname = f"{OUT_DIR}/{task_id}_{provider}.json"
            with open(fname, "w", encoding="utf-8") as f:
                json.dump({"task": task_id, "provider": provider, "tokens": tokens, "text": text}, f, ensure_ascii=False)
            print(f"  HIT  {task_id} | {provider}: {tokens} tok | Total: {total_tokens}", flush=True)
            return tokens
        else:
            print(f"  MISS {task_id} | {provider}: empty", flush=True)
            return 0
    except Exception as e:
        print(f"  FAIL {task_id} | {provider}: {str(e)[:50]}", flush=True)
        return 0

print("=" * 60, flush=True)
print("NOVA SWARM FIRE — SEQUENTIAL, ALL PROVIDERS", flush=True)
print(f"Tasks: {len(TASKS)} | Providers: {len(PROVIDERS)} | Max: {len(TASKS)*len(PROVIDERS)}", flush=True)
print("=" * 60, flush=True)

# Wave 1: Each task to each provider, one at a time
for ti, (task_id, task_desc) in enumerate(TASKS):
    print(f"\n--- Task {ti+1}/{len(TASKS)}: {task_id} ---", flush=True)
    prompt = NOVA_CTX + "\n\nTASK: " + task_desc
    for pi, provider in enumerate(PROVIDERS):
        query(prompt, provider, task_id)
        time.sleep(0.3)  # pace to not overwhelm tserve

elapsed = time.time() - t0
print(f"\n{'=' * 60}", flush=True)
print(f"SWARM FIRE COMPLETE", flush=True)
print(f"Queries: {total_queries} | Hits: {total_hits} | Tokens: {total_tokens}", flush=True)
print(f"Time: {elapsed:.0f}s | Rate: {total_tokens/max(elapsed,1):.0f} tok/s", flush=True)
print(f"Files: {OUT_DIR}/", flush=True)
print(f"{'=' * 60}", flush=True)

summary = {
    "tasks": len(TASKS), "providers": len(PROVIDERS),
    "queries": total_queries, "hits": total_hits,
    "total_tokens": total_tokens,
    "elapsed": round(elapsed, 1),
    "rate": round(total_tokens/max(elapsed,1), 1)
}
with open(f"{OUT_DIR}/swarm_summary.json", "w") as f:
    json.dump(summary, f, indent=2)
