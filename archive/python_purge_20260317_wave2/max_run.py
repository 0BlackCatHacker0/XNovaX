import urllib.request, json, re, time, sys, os

def query(prompt, provider='', model=''):
    body = json.dumps({'prompt': prompt, 'provider': provider, 'model': model}).encode()
    req = urllib.request.Request('http://127.0.0.1:9878/query', data=body, headers={'Content-Type':'application/json'})
    try:
        raw = urllib.request.urlopen(req, timeout=90).read().decode('utf-8','replace')
        clean = re.sub(r'[\x00-\x1f]', ' ', raw)
        d = json.loads(clean)
        result = d.get('result', {})
        resp = result.get('response', d.get('response', ''))
        tok = result.get('tokens', max(len(resp)//4, 1) if resp else 0)
        prov = d.get('provider', provider)
        return {'ok': d.get('ok'), 'tokens': tok, 'provider': prov, 'response': resp}
    except Exception as e:
        return {'ok': False, 'tokens': 0, 'error': str(e)}

ALL_PROVIDERS = [
    "cerebras_direct", "google_ai_studio", "sambanova_direct", "github_models",
    "mistral_direct", "nvidia_nim", "kluster_ai", "openai", "anthropic",
    "google", "mistral", "groq", "deepseek", "cohere", "together",
    "deepinfra", "together_direct", "cloudflare_ai", "cohere_direct",
    "apifreellm", "openrouter", "ollama"
]

TOPICS = [
    "cloud router parallel dispatch with 3-provider racing",
    "token throughput maximizer with burst scheduling",
    "response quality scoring with length and coherence metrics",
    "service auto-healer that detects crashes within 10 seconds",
    "adaptive load balancer based on response time history",
    "smart caching layer with TTL and LRU eviction",
    "distributed tracing across all 111 microservices",
    "Chladni eigenmode classifier with 13 skill domains",
    "ternary neural network with 27-trit input layer",
    "swarm consensus algorithm merging 5+ model responses",
    "knowledge graph with subject-predicate-object triples",
    "event-driven pub/sub bus connecting all services",
    "API gateway with rate limiting and auth middleware",
    "prompt engineering engine with automatic optimization",
    "model benchmark suite testing speed and quality",
    "feature flag system with gradual rollout percentages",
    "anomaly detector using z-score on latency trends",
    "code generation service that writes NovaLang services",
    "context manager with windowing and compression",
    "Navier-Stokes flow control for request routing",
    "BitNet 1.58 quantizer with adaptive thresholds",
    "fractal engine with recursive depth control",
    "connection pooling for HTTP client reuse",
    "self-documenting system that catalogs all APIs",
    "ternary CPU emulator with 9 registers",
    "model specialization map for task-to-model routing",
    "NovaLang VM memory compaction for long-running services",
    "neural fabric mesh connecting all 111 services",
    "quantum bridge between binary and ternary computing",
    "reinforcement learning router with ternary rewards",
    "data pipeline with map-reduce-filter on streams",
    "state machine engine for service lifecycle management",
    "chaos engineering tool for resilience testing",
    "fleet commander with rolling restarts and circuit breakers",
    "unified API gateway routing natural language to services",
    "AI training pipeline collecting fine-tuning data",
    "ternary compression with run-length encoding on trits",
    "performance profiler with p50 p95 p99 percentiles",
    "model arena with ELO rating system for competitions",
    "intelligence fabric v3 with semantic routing",
    "CLI tool for fleet management with colored output",
    "system report generator with uptime and throughput stats",
    "migration tool for zero-downtime version upgrades",
    "capability discovery scanning models for strengths",
]

BASE = "You are upgrading NovaX, an AI OS with 111 microservices in NovaLang (if3/try3/while3/for3, dict_get/dict_set, tserve/troute/tstart). Write a complete implementation for: "

grand_total = 0
grand_hits = 0
grand_queries = 0
provider_stats = {}

print("=" * 60)
print("  NOVAX MAX RUN - ALL 24 PROVIDERS - FULL POWER")
print("=" * 60)

# ROUND 1: Every single provider
print("\n=== ROUND 1: ALL PROVIDERS FIRST PASS ===")
for i, prov in enumerate(ALL_PROVIDERS):
    topic = TOPICS[i % len(TOPICS)]
    prompt = BASE + topic + ". Full NovaLang code, production-ready."
    t0 = time.time()
    r = query(prompt, prov)
    elapsed = time.time() - t0
    tok = r.get('tokens', 0)
    grand_total += tok
    grand_queries += 1
    actual = r.get('provider', prov)
    if tok > 0:
        grand_hits += 1
        tag = "DIRECT" if actual == prov else "CASCADE->"+actual
    else:
        tag = "MISS"
    if actual not in provider_stats:
        provider_stats[actual] = {'hits': 0, 'tokens': 0}
    provider_stats[actual]['hits'] += 1
    provider_stats[actual]['tokens'] += tok
    safe = (r.get('response','') or '')[:80].encode('ascii','replace').decode('ascii')
    print(f"  [{prov:20s}] {tag:25s} +{tok:5d} tok ({elapsed:.1f}s) | {safe}...")

print(f"\n  Round 1: {grand_hits}/{grand_queries} hits, {grand_total} tokens")

# ROUND 2: All providers again with different topics
print("\n=== ROUND 2: ALL PROVIDERS SECOND PASS ===")
r2_hits = 0
r2_tok = 0
for i, prov in enumerate(ALL_PROVIDERS):
    topic = TOPICS[(i + 22) % len(TOPICS)]
    prompt = BASE + topic + ". Write complete deployable NovaLang code with health endpoint and JSON API."
    r = query(prompt, prov)
    tok = r.get('tokens', 0)
    grand_total += tok
    r2_tok += tok
    grand_queries += 1
    actual = r.get('provider', prov)
    if tok > 0:
        grand_hits += 1
        r2_hits += 1
        tag = "DIRECT" if actual == prov else "CASCADE->"+actual
    else:
        tag = "MISS"
    if actual not in provider_stats:
        provider_stats[actual] = {'hits': 0, 'tokens': 0}
    provider_stats[actual]['hits'] += 1
    provider_stats[actual]['tokens'] += tok
    print(f"  [{prov:20s}] {tag:25s} +{tok:5d} tok")

print(f"\n  Round 2: {r2_hits}/{len(ALL_PROVIDERS)} hits, {r2_tok} tokens")

# ROUND 3: Top 8 performers get 3 bonus queries each
print("\n=== ROUND 3: TOP PERFORMER BONUS (3x each) ===")
top = sorted(provider_stats.items(), key=lambda x: x[1]['tokens'], reverse=True)[:8]
r3_tok = 0
r3_hits = 0
for prov, st in top:
    for j in range(3):
        topic = TOPICS[(grand_queries + j) % len(TOPICS)]
        prompt = BASE + topic + ". Maximum detail. Full implementation. Production-grade."
        r = query(prompt, prov)
        tok = r.get('tokens', 0)
        grand_total += tok
        r3_tok += tok
        grand_queries += 1
        if tok > 0:
            grand_hits += 1
            r3_hits += 1
        print(f"  [{prov:20s}] +{tok:5d} tok (bonus {j+1})")

print(f"\n  Round 3: {r3_hits} hits, {r3_tok} tokens")

# ROUND 4: Scatter shot - random providers rapid fire
print("\n=== ROUND 4: SCATTER SHOT RAPID FIRE ===")
import random
random.seed(42)
scatter_provs = ALL_PROVIDERS * 2
random.shuffle(scatter_provs)
r4_tok = 0
r4_hits = 0
for i, prov in enumerate(scatter_provs[:20]):
    topic = TOPICS[(i * 3) % len(TOPICS)]
    prompt = BASE + topic + ". Concise but complete NovaLang code."
    r = query(prompt, prov)
    tok = r.get('tokens', 0)
    grand_total += tok
    r4_tok += tok
    grand_queries += 1
    if tok > 0:
        grand_hits += 1
        r4_hits += 1
    print(f"  [{prov:20s}] +{tok:5d} tok")

print(f"\n  Round 4: {r4_hits}/20 hits, {r4_tok} tokens")

# Final report
print("\n" + "=" * 60)
print("  MAX RUN COMPLETE")
print("=" * 60)
print(f"  Total queries:  {grand_queries}")
print(f"  Total hits:     {grand_hits}")
print(f"  Hit rate:       {grand_hits*100//max(grand_queries,1)}%")
print(f"  Total tokens:   {grand_total}")
print(f"\n  PROVIDER LEADERBOARD:")
for prov, st in sorted(provider_stats.items(), key=lambda x: x[1]['tokens'], reverse=True):
    bar = "#" * (st['tokens'] // 500)
    print(f"    {prov:25s}  hits={st['hits']:3d}  tokens={st['tokens']:6d}  {bar}")

with open(os.path.join('C:', os.sep, 'NovaX', 'max_run_results.json'), 'w') as f:
    json.dump({
        'total_queries': grand_queries,
        'total_hits': grand_hits,
        'total_tokens': grand_total,
        'hit_rate': f"{grand_hits*100//max(grand_queries,1)}%",
        'provider_stats': provider_stats
    }, f, indent=2)

print(f"\n  Results saved to C:/NovaX/max_run_results.json")
