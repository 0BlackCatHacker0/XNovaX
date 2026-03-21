"""
NovaX Swarm MAX RUN — All Providers, Deep Context, Real Upgrades
Fires 13 upgrade domains x 15 providers = 195 queries
Each query carries condensed NovaX architecture context
Output: C:/NovaX/swarm_upgrades/
"""
import urllib.request, json, time, os, sys, threading, traceback

ROUTER = "http://127.0.0.1:9878/query"
OUT_DIR = "C:/NovaX/swarm_upgrades"
os.makedirs(OUT_DIR, exist_ok=True)

# Condensed NovaX context (key architecture info the swarm needs)
NOVA_CONTEXT = """=== NOVAX SYSTEM CONTEXT ===
NovaX is an AI Operating System. 111 services on localhost, 29 providers, 510K+ models.
Language: NovaLang (.nova files, ternary-native Rust VM at C:/NovaX/novalang.exe)
Key features: if3/match3/try3/while3 (3-way branching), balanced ternary arithmetic (bt/bt_val/bt_add)
CRITICAL GOTCHAS: dict_set() returns NEW dict (must reassign), append() returns NEW list (must reassign),
dict_get() only works on dicts NOT lists (use bracket syntax for lists), try3 syntax is try3 { } { fallback },
http_post body must use json_encode(), shell() returns dict not string, no || or && chains.
Architecture: Orchestrator(:9999) -> CloudRouter(:9878) -> 15+ AI providers -> Hivemind(:9881)
Fractal Engine(:9874): splits tasks into domain sub-tasks, dispatches across providers
N-S Flow: Reynolds scoring Re=density*velocity*length/viscosity, 3-5-7-13 harmonic constants
Ternary: +1/0/-1 states, MAYBE is valid (not error), negation is free (flip trits)
Services pattern: tserve(PORT, NAME) with troute() for endpoints, /health GET required
"""

# 13 upgrade domains (H13 carrier frame)
TASKS = [
    ("router-enhance", "code", "Improve the Nova Cloud Router. Write NovaLang code adding: smart provider selection based on query type using Chladni patterns, response quality scoring using Reynolds number, automatic failover with ternary exponential backoff."),
    ("hive-token-max", "system", "Design a token output maximizer for NovaX Hivemind. Write NovaLang code for a micro-tool that divides tasks using Kolmogorov cascade, dispatches to different providers simultaneously, synthesizes responses. Goal: millions of tokens per hour."),
    ("fractal-depth", "code", "Enhance the Fractal Engine. Write NovaLang code for adaptive fractal depth based on task complexity, recursive sub-task splitting (3-13 children), Chladni frequency modulation for domain routing."),
    ("swarm-consensus", "reasoning", "Build better swarm consensus. Write NovaLang code scoring responses using N-S Reynolds number, grouping similar responses with ternary fingerprints, synthesizing best parts, balanced ternary voting (+1/0/-1)."),
    ("self-heal", "system", "Build self-healing service mesh for 111 services. Write NovaLang code monitoring with health3(), auto-restarting crashed services, detecting degraded (trit 0), using Reynolds flow regime classification."),
    ("vm-optimize", "code", "Propose NovaLang Rust VM optimizations. Key bottlenecks: dict_set/append clone data (O(n)), JSON parsing every HTTP body, single-threaded tserve. Suggest Rust code for HAMTs, auto JSON parsing, async handling."),
    ("quant-hardware", "system", "Integrate quantized hardware layer. Write NovaLang code routing ternary computation to BitNet (1.58-bit on port 9925), standard queries to Ollama/cloud, using hardware service (9943) data for model placement."),
    ("tripple-enhance", "search", "Enhance Tripple search engine. Write NovaLang code using Chladni frequency modulation (9 eigenmodes), firing searches across all providers, deduplicating with N-S Reynolds scoring, discovering new models from catalogs."),
    ("event-system", "code", "Design event-driven architecture for 111 services. Write NovaLang code using event3 stdlib: central event bus, services publish events (success/info/error), ternary event classification."),
    ("security-harden", "system", "Harden NovaX security. Write NovaLang code for rate-limiting with ternary states, JSON body validation, request signing with balanced ternary hashes, audit logging of cross-service calls."),
    ("perf-benchmark", "code", "Build benchmark suite. Write NovaLang code testing all providers with identical prompts, scoring with Reynolds number, ternary leaderboard (+1=fast/0=avg/-1=slow), auto-tuning cascade order."),
    ("knowledge-graph", "reasoning", "Design knowledge graph mapping 111 services, 29 providers, 510K models. Write NovaLang code with ternary edge weights (+1=strong/0=weak/-1=inverse), path-finding for optimal routing."),
    ("swarm-codegen", "code", "Build swarm code generator. Write NovaLang code: takes description, fires to 5+ providers, collects generated code, ternary voting for best implementation, auto-validates syntax."),
]

PROVIDERS = [
    "ollama", "openai", "anthropic", "cerebras_direct",
    "sambanova_direct", "google_ai_studio", "openrouter",
    "mistral", "groq", "deepseek", "cohere", "together",
    "google", "cortex", "novax-prime"
]

# Thread-safe results
results_lock = threading.Lock()
results = []
total_tokens = 0
total_hits = 0

def query(prompt, provider, task_id, attempt=1):
    global total_tokens, total_hits
    body = json.dumps({
        "prompt": prompt,
        "provider": provider,
        "max_tokens": 2048
    }).encode()
    req = urllib.request.Request(ROUTER, data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        resp = urllib.request.urlopen(req, timeout=60)
        data = json.loads(resp.read().decode())
        text = data.get("text", data.get("response", ""))
        tokens = len(text.split())
        if tokens > 5:  # meaningful response
            with results_lock:
                total_tokens += tokens
                total_hits += 1
                results.append({
                    "task": task_id, "provider": provider,
                    "tokens": tokens, "text": text[:500]
                })
            # Save full response
            fname = f"{OUT_DIR}/{task_id}_{provider}.json"
            with open(fname, "w", encoding="utf-8") as f:
                json.dump({"task": task_id, "provider": provider,
                          "tokens": tokens, "text": text}, f)
            print(f"  HIT {task_id} via {provider}: {tokens} tok")
            return tokens
        else:
            print(f"  MISS {task_id} via {provider}: empty/short")
            return 0
    except Exception as e:
        print(f"  FAIL {task_id} via {provider}: {str(e)[:60]}")
        return 0

def fire_wave(wave_num, task_indices, provider_indices):
    """Fire a wave of queries"""
    threads = []
    for ti in task_indices:
        task_id, domain, task_desc = TASKS[ti % len(TASKS)]
        prompt = NOVA_CONTEXT + f"\nTASK ({domain}): " + task_desc
        for pi in provider_indices:
            provider = PROVIDERS[pi % len(PROVIDERS)]
            t = threading.Thread(target=query,
                               args=(prompt, provider, task_id))
            threads.append(t)
    # Fire all threads
    for t in threads:
        t.start()
        time.sleep(0.1)  # slight stagger to avoid socket exhaustion
    # Wait for completion
    for t in threads:
        t.join(timeout=90)
    return len(threads)

print("=" * 60)
print("NOVA SWARM MAX RUN — ALL PROVIDERS, ALL TASKS")
print(f"Tasks: {len(TASKS)} | Providers: {len(PROVIDERS)}")
print(f"Max queries: {len(TASKS) * len(PROVIDERS)}")
print("=" * 60)

t0 = time.time()

# Wave 1: Each task to top 5 providers (65 queries)
print("\n=== WAVE 1: Priority Providers (5 per task) ===")
for ti in range(len(TASKS)):
    task_id = TASKS[ti][0]
    print(f"[W1] Task {ti+1}/{len(TASKS)}: {task_id}")
    fire_wave(1, [ti], list(range(5)))

elapsed1 = time.time() - t0
print(f"\n[W1] {total_hits} hits, {total_tokens} tokens in {elapsed1:.0f}s")

# Wave 2: Each task to remaining providers (rest)
print("\n=== WAVE 2: Extended Providers ===")
for ti in range(len(TASKS)):
    task_id = TASKS[ti][0]
    print(f"[W2] Task {ti+1}/{len(TASKS)}: {task_id}")
    fire_wave(2, [ti], list(range(5, len(PROVIDERS))))

elapsed2 = time.time() - t0
print(f"\n[W2] {total_hits} total hits, {total_tokens} total tokens in {elapsed2:.0f}s")

# Wave 3: Bonus — cross-pollinate top results
print("\n=== WAVE 3: Cross-Pollination ===")
# Take the best results and ask other providers to improve them
with results_lock:
    top_results = sorted(results, key=lambda r: r["tokens"], reverse=True)[:5]

for i, r in enumerate(top_results):
    cross_prompt = NOVA_CONTEXT + f"\nA previous AI model wrote this code for NovaX upgrade task '{r['task']}':\n{r['text'][:800]}\n\nIMPROVE this code. Fix any bugs, add missing features, optimize for ternary operations. Return improved NovaLang code."
    provider = PROVIDERS[(i + 3) % len(PROVIDERS)]  # different provider
    query(cross_prompt, provider, f"cross_{r['task']}")

elapsed3 = time.time() - t0

# Summary
print("\n" + "=" * 60)
print("SWARM MAX RUN COMPLETE")
print(f"Total hits:   {total_hits}")
print(f"Total tokens: {total_tokens}")
print(f"Time:         {elapsed3:.0f}s")
print(f"Rate:         {total_tokens/max(elapsed3,1):.0f} tok/s")
print(f"Files:        {OUT_DIR}/")
print("=" * 60)

# Save summary
summary = {
    "tasks": len(TASKS), "providers": len(PROVIDERS),
    "total_hits": total_hits, "total_tokens": total_tokens,
    "elapsed_seconds": round(elapsed3, 1),
    "rate_tok_s": round(total_tokens/max(elapsed3,1), 1),
    "results": [{"task": r["task"], "provider": r["provider"],
                 "tokens": r["tokens"]} for r in results]
}
with open(f"{OUT_DIR}/swarm_summary.json", "w") as f:
    json.dump(summary, f, indent=2)
print(f"\nSummary saved to {OUT_DIR}/swarm_summary.json")
