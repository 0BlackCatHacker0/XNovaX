import urllib.request, json, re, time, os

def query(prompt, provider=''):
    body = json.dumps({'prompt': prompt, 'provider': provider}).encode()
    req = urllib.request.Request('http://127.0.0.1:9878/query', data=body, headers={'Content-Type':'application/json'})
    try:
        raw = urllib.request.urlopen(req, timeout=90).read().decode('utf-8','replace')
        clean = re.sub(r'[\x00-\x1f]', ' ', raw)
        d = json.loads(clean)
        result = d.get('result', {})
        resp = result.get('response', d.get('response', ''))
        tok = result.get('tokens', max(len(resp)//4, 1) if resp else 0)
        return {'ok': d.get('ok'), 'tokens': tok, 'provider': d.get('provider', provider), 'response': resp}
    except Exception as e:
        return {'ok': False, 'tokens': 0, 'error': str(e)}

# === DEEP CONTEXT: Real NovaX knowledge baked into every prompt ===

NOVA_CONTEXT = """CONTEXT: NovaX is an AI operating system built in NovaLang (custom language, Rust VM at novalang.exe).
KEY FACTS:
- 111 microservices on ports 9800-9999, all pure NovaLang
- 29 cloud AI providers (Cerebras, OpenAI, Anthropic, SambaNova, Google AI Studio, Mistral, NVIDIA NIM, Groq, DeepSeek, Cohere, Together, DeepInfra, Cloudflare, Kluster.ai, OpenRouter, etc)
- 510,455 total models (102 local Ollama + 471 cloud + 509,882 HuggingFace)
- NovaLang syntax: if3/else/try3/fail/while3/for3, dict_get/dict_set (returns NEW dict), append (returns NEW list), tserve/troute/tstart for HTTP
- Navier-Stokes flow model: Re=rhoUL/mu, laminar(<100)/transitional(100-500)/turbulent(500-2000)/chaotic(2000+)
- 3-5-7-13 constants: 3=ternary, 5=TZip(3^5=243), 7=composition, 13=carrier
- CRITICAL GOTCHAS: dict_set/append return NEW values (must reassign), no || or && operators, let inside if3 is scope-local, try3 inside while3 causes parser issues

KNOWN BUGS TO FIX:
- Chladni strength=0 (sin_approx loaded wrong in router)
- sha256 builtin is cascaded FNV-1a (NOT real SHA-256)
- while3 loop with 500+ appends crashes services (Python helper needed for bulk ops)
- 20th route in tserve silently dropped (hard cap)
- else3{} swallows everything after it if no condition given

SERVICE ARCHITECTURE:
- Orchestrator (9999): 470+ routes, Python, gateway to everything
- Cloud Router (9878): 24 providers, cascade query, Tripple resonance ranking
- HiveMind (9881): Model swarm, deliberation, synthesis
- Fractal Engine (9874): 5-stage pipeline (Fractalizer->Dispatcher->Quantizer->Synthesizer->Amplifier)
- Quantizer (9939): BitNet 1.58 ternary weights, threshold T=0.7*mean(|W|)
- TMemory (9945): Store/recall/forget/consolidate AI memories
"""

PROVIDERS = [
    "cerebras_direct", "openai", "sambanova_direct", "google_ai_studio",
    "openrouter", "groq", "mistral", "deepseek", "cohere", "together",
    "mistral_direct", "nvidia_nim", "deepinfra", "together_direct",
    "cloudflare_ai", "cohere_direct", "kluster_ai", "anthropic",
    "github_models", "apifreellm"
]

# Deep upgrade prompts that reference REAL NovaX state
DEEP_PROMPTS = [
    "Fix the Chladni modulation layer: strength=0 because _sin_approx loaded wrong values. The layer routes prompts to 9 eigenmodes (code, math, creative, analysis, translation, research, system, debug, general). Rewrite the domain classifier with keyword matching instead of sin approximation. Each domain needs 20+ keywords. Return domain name + confidence 0-1000.",
    "The cloud router cascade_query tries providers sequentially but wastes time on slow ones. Redesign: fire top 3 providers in parallel (based on Tripple resonance ranking), take the fastest response, cancel the others. Handle the case where all 3 fail and need to cascade further. Use NovaLang try3 blocks.",
    "The HiveMind synthesis mode fires all providers and merges responses. Current problem: some return empty, merge is simple concatenation. Design quality-weighted merge: score each response (length, keyword overlap, no error messages), weight by score, take top 3 responses, synthesize by finding common themes and unique insights.",
    "NovaX has 3-5-7-13 constants throughout. Design a harmonic scheduler that uses these: tasks queued in groups of 3, dispatched in waves of 5, composed across 7 services, with 13-step monitoring cycles. Each constant maps to a scheduling tier. Write the scheduler in NovaLang.",
    "The Navier-Stokes flow model classifies queries by Reynolds number. Current thresholds: <100 laminar, <500 transitional, <2000 turbulent, 2000+ chaotic. But the Reynolds calculation is basic. Improve: include token density (complexity per word), vocabulary breadth, question depth (nested clauses), and urgency signals. Write compute_reynolds(prompt) in NovaLang.",
    "Design a self-healing service mesh for 111 services. Known failure modes: port conflicts (service starts but can't bind), zombie processes (old instances holding ports), parser crashes (bad NovaLang syntax), memory leaks (long-running services). For each failure mode, write detection + remediation in NovaLang.",
    "The Tripple resonance system ranks providers by success rate and latency. Improve it: add model-specific tracking (same provider, different models perform differently), add task-type awareness (code tasks route to code-optimized models), add time-of-day patterns (some providers are slower at peak hours). NovaLang code.",
    "NovaX Fractal Engine splits prompts into sub-tasks across 7 domains. Current limit: max_splits=13, max_rounds=13, max_depth=7. The synthesizer just concatenates sub-results. Design intelligent synthesis: identify redundancies, resolve contradictions between sub-results, weight by domain expertise, produce coherent unified output.",
    "The TMemory service stores AI memories as JSON. Current recall is basic keyword match. Design semantic recall: compute similarity between query and stored memories using word overlap + position weighting + recency decay. Return top-K most relevant memories with confidence scores. NovaLang code.",
    "NovaX needs a unified telemetry system. All 111 services should report: requests/sec, error rate, latency p50/p95/p99, token throughput, memory usage. Design a lightweight telemetry collector that services push to via HTTP, stores in memory with configurable retention, and exposes dashboards. Port 9971.",
    "The Quantizer uses BitNet 1.58 with fixed threshold T=0.7*mean(|W|). This is suboptimal for different layer types. Design adaptive quantization: different thresholds for attention weights vs FFN weights vs embedding weights. Include calibration pass that measures each layer's sensitivity. NovaLang implementation.",
    "Design a NovaX API versioning system. Current services have no versioning. New design: /v1/ prefix on all routes, version negotiation via Accept header, backward compatibility layer that translates v1 requests to v2 format. Automatic deprecation warnings. NovaLang middleware pattern.",
    "NovaX providers have different strengths: Cerebras is fastest (1-2s), OpenAI is highest quality, SambaNova has largest context, Google AI Studio has best multimodal. Design smart routing: classify prompt into requirements (speed, quality, context-length, multimodal) and route to optimal provider. NovaLang code.",
    "Build a NovaX integration test suite. Test the critical path: user sends prompt -> orchestrator routes to cloud router -> cloud router picks provider -> provider returns response -> response flows back to user. Mock each layer, test error cases, verify cascade works. 30+ test cases in NovaLang.",
    "The Kolmogorov cascade decomposes complex queries into sub-queries until they reach the Kolmogorov microscale (individual trit decisions). Current implementation is basic recursion. Design proper cascade: energy spectrum analysis of prompt, scale-dependent decomposition, parallel execution at each scale, inverse cascade for synthesis.",
    "Design NovaX hot-reload: update a service's .nova code without stopping it. Current method: kill process, restart (5-10s downtime). New design: shadow instance on temporary port, health check, traffic swap, old instance graceful shutdown. Zero-downtime deployments for all 111 services.",
    "The Go territory system classifies prompts into chess-like territories. Current: 7 territories. Expand to 13 (matching H13 constant): code, math, creative, analysis, translation, research, system, debug, planning, education, summarization, conversation, multimodal. Each territory maps to optimal provider+model pair.",
    "NovaX uses dict_get/dict_set everywhere but these are O(n) on large dicts. For services tracking 500+ model stats, this is slow. Design a B-tree or hash-based lookup that works within NovaLang's constraints. Or propose a new builtin bt_get/bt_set for the Rust VM. Include performance analysis.",
    "Build the NovaX Swarm Orchestrator v2: 510K models organized into specialization squads. Each squad (5-13 models) has a domain specialty. Squads are arranged in a hierarchy: individual models -> squads -> platoons -> divisions -> the swarm. Orders flow down, results flow up. NovaLang design.",
    "The DIDT (Dual Imprint Dissonance Theory) maps psychological concepts to NovaX: Emotional Encoding = Reynolds urgency, Intellectual Imprint = Flow Channel logic, Cognitive Dissonance = Deliberation Vortex, Belief Cohesion = TSpeak bridge, Narrative Lock-In = Laminar Output consensus. Design a DIDT-aware prompt classifier that uses these psychological dimensions to route queries optimally.",
]

total_tokens = 0
total_hits = 0
total_queries = 0
provider_stats = {}

print("=" * 60)
print("  DEEP CONTEXT WAVE - ARCHIVE KNOWLEDGE IN EVERY QUERY")
print("=" * 60)

for i, deep_prompt in enumerate(DEEP_PROMPTS):
    prov = PROVIDERS[i % len(PROVIDERS)]
    full_prompt = NOVA_CONTEXT + "\n\nTASK: " + deep_prompt + "\n\nWrite complete, production-ready NovaLang code. Use if3/try3/while3/for3 syntax. dict_set and append MUST be reassigned. No || or && operators."

    t0 = time.time()
    r = query(full_prompt, prov)
    elapsed = time.time() - t0
    tok = r.get('tokens', 0)
    total_tokens += tok
    total_queries += 1
    actual = r.get('provider', prov)

    if tok > 0:
        total_hits += 1

    if actual not in provider_stats:
        provider_stats[actual] = {'hits': 0, 'tokens': 0}
    provider_stats[actual]['hits'] += 1
    provider_stats[actual]['tokens'] += tok

    tag = "DIRECT" if actual == prov else f"CASCADE->{actual}"
    safe = (r.get('response','') or '')[:100].encode('ascii','replace').decode('ascii')
    print(f"  [{actual:20s}] {tag:25s} +{tok:5d} tok ({elapsed:.1f}s) | {safe[:80]}...")

print(f"\n{'='*60}")
print(f"  DEEP CONTEXT WAVE COMPLETE")
print(f"  Queries: {total_queries} | Hits: {total_hits} | Tokens: {total_tokens}")
print(f"  Hit rate: {total_hits*100//max(total_queries,1)}%")
print(f"\n  PROVIDER LEADERBOARD:")
for prov, st in sorted(provider_stats.items(), key=lambda x: x[1]['tokens'], reverse=True):
    bar = "#" * (st['tokens'] // 500)
    print(f"    {prov:25s}  hits={st['hits']:3d}  tokens={st['tokens']:6d}  {bar}")

with open(os.path.join('C:', os.sep, 'NovaX', 'deep_context_results.json'), 'w') as f:
    json.dump({
        'total_queries': total_queries,
        'total_hits': total_hits,
        'total_tokens': total_tokens,
        'provider_stats': provider_stats,
        'type': 'deep_context_with_archive_knowledge'
    }, f, indent=2)

print(f"\n  Results saved to C:/NovaX/deep_context_results.json")
