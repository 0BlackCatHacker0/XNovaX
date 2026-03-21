"""
MODEL BLITZ — Fire queries through ALL 591 models across ALL providers
Maxes out: ripples, provider frequencies, trit scores, resonance lock
"""
import requests
import time
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

ROUTER = "http://127.0.0.1:9878"
REGISTRY = "http://127.0.0.1:9860"

# Provider routing map — which provider prefix routes to which preferred provider
PROVIDER_MAP = {
    "openai": "openai",
    "anthropic": "anthropic",
    "google": "google",
    "mistralai": "mistral",
    "mistral": "mistral",
    "meta-llama": "groq",       # groq has llama models
    "deepseek": "deepseek",
    "cohere": "cohere",
    "together": "together",
    "openrouter": "openrouter",
    "ollama": "ollama",
    "qwen": "openrouter",       # qwen via openrouter
    "nvidia": "openrouter",
    "x-ai": "openrouter",
    "z-ai": "openrouter",
    "amazon": "openrouter",
    "liquid": "openrouter",
    "minimax": "openrouter",
    "perplexity": "openrouter",
    "nousresearch": "openrouter",
    "arcee-ai": "together",
    "inception": "openrouter",
    "inflection": "openrouter",
    "fleet": "openrouter",
    "allenai": "openrouter",
    "sao10k": "openrouter",
    "thedrummer": "openrouter",
    "bytedance-seed": "openrouter",
    "moonshotai": "openrouter",
    "baidu": "openrouter",
    "stepfun": "openrouter",
    "ibm-granite": "openrouter",
    "aion-labs": "openrouter",
}

# Stats
stats = {
    "total": 0, "success": 0, "fail": 0,
    "by_provider": {},
    "start_time": time.time()
}
stats_lock = threading.Lock()

def fire_query(model_id, provider, prompt="ping"):
    """Fire a single query with model override"""
    try:
        r = requests.post(f"{ROUTER}/api/v1/query", json={
            "prompt": prompt,
            "preferred": provider,
            "model": model_id
        }, timeout=15)
        d = r.json()
        ok = d.get("ok", False)
        with stats_lock:
            stats["total"] += 1
            if ok:
                stats["success"] += 1
            else:
                stats["fail"] += 1
            pkey = provider
            if pkey not in stats["by_provider"]:
                stats["by_provider"][pkey] = {"ok": 0, "fail": 0}
            if ok:
                stats["by_provider"][pkey]["ok"] += 1
            else:
                stats["by_provider"][pkey]["fail"] += 1
        return ok
    except Exception as e:
        with stats_lock:
            stats["total"] += 1
            stats["fail"] += 1
        return False

def get_status():
    """Get current tripple status"""
    try:
        r = requests.get(f"{ROUTER}/tripple/status", timeout=10)
        return r.json()
    except:
        return {}

def print_status(phase=""):
    d = get_status()
    score = d.get("resonance_score", 0)
    prime = d.get("prime_locked", False)
    hyper = d.get("hyper_locked", False)
    f = d.get("formula", {})
    elapsed = time.time() - stats["start_time"]

    state = "HYPER-PRIME" if (hyper == True or hyper == 1) else "PRIME" if (prime == True or prime == 1) else "ACTIVE"

    print(f"\n{'='*60}")
    print(f"  {phase}")
    print(f"  Score: {score:.1f} | State: {state}")
    print(f"  R={f.get('R_resolvent',0):.0f} T={f.get('T_ternary',0):.0f} C={f.get('C_coupled',0):.0f} A={f.get('ability_amplifier',0)}")
    print(f"  Queries: {stats['total']} | OK: {stats['success']} | Fail: {stats['fail']} | Time: {elapsed:.1f}s")
    print(f"  Rate: {stats['total']/max(elapsed,1):.1f} queries/sec")
    for pk, pv in sorted(stats["by_provider"].items(), key=lambda x: x[1]["ok"], reverse=True):
        print(f"    {pk:15s}: {pv['ok']:4d} ok / {pv['fail']:3d} fail")
    print(f"{'='*60}")

def main():
    print("=" * 60)
    print("  NOVAX MODEL BLITZ — 591 MODELS × ALL PROVIDERS")
    print("  Maxing out ripples, frequencies, resonance")
    print("=" * 60)

    # Get all models from registry
    r = requests.get(f"{REGISTRY}/models", timeout=10)
    data = r.json()
    models = data.get("models", data.get("data", []))
    print(f"\nLoaded {len(models)} models from registry")

    # Group by provider prefix
    model_groups = {}
    for m in models:
        mid = m["id"]
        parts = mid.split("/")
        prefix = parts[0] if len(parts) > 1 else "local"
        if prefix not in model_groups:
            model_groups[prefix] = []
        model_groups[prefix].append(mid)

    print(f"Grouped into {len(model_groups)} provider prefixes")
    print_status("BEFORE BLITZ")

    # ═══════════════════════════════════════
    # PHASE 1: Parallel provider blitz
    # Fire 4 concurrent queries per provider
    # ═══════════════════════════════════════
    print(f"\n>>> PHASE 1: PARALLEL PROVIDER BLITZ")

    prompts = [
        "What is 2+2?",
        "Hello",
        "Explain gravity in one sentence",
        "ping",
        "What is NovaX?",
        "List 3 colors",
        "Summarize AI in 10 words",
    ]
    prompt_idx = 0

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = []
        for prefix, model_list in sorted(model_groups.items(), key=lambda x: len(x[1]), reverse=True):
            # Map prefix to actual provider
            provider = PROVIDER_MAP.get(prefix, "openrouter")  # default to openrouter

            for mid in model_list:
                prompt = prompts[prompt_idx % len(prompts)]
                prompt_idx += 1
                futures.append(pool.submit(fire_query, mid, provider, prompt))

                # Print progress every 50 queries
                if len(futures) % 50 == 0:
                    # Wait for this batch
                    done = sum(1 for f in futures if f.done())
                    print(f"  Dispatched {len(futures)} / {len(models)} | Completed: {done}")

        # Wait for all
        print(f"\n  Waiting for {len(futures)} queries to complete...")
        for f in as_completed(futures):
            pass

    print_status("AFTER PHASE 1 — FULL MODEL SWEEP")

    # ═══════════════════════════════════════
    # PHASE 2: Provider frequency boost
    # Rapid-fire 20 queries per active provider
    # to maximize provider frequencies
    # ═══════════════════════════════════════
    print(f"\n>>> PHASE 2: PROVIDER FREQUENCY BOOST")

    active_providers = ["ollama", "openai", "openrouter", "anthropic", "google",
                       "mistral", "groq", "deepseek", "cohere", "together"]

    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = []
        for prov in active_providers:
            for i in range(20):
                prompt = prompts[i % len(prompts)]
                futures.append(pool.submit(fire_query, "", prov, prompt))

        print(f"  Boosting {len(active_providers)} providers × 20 = {len(futures)} queries")
        for f in as_completed(futures):
            pass

    print_status("AFTER PHASE 2 — FREQUENCY BOOST")

    # ═══════════════════════════════════════
    # PHASE 3: Resonance lock hammer
    # Rapid consecutive queries to lock prime + hyper
    # ═══════════════════════════════════════
    print(f"\n>>> PHASE 3: RESONANCE LOCK HAMMER")

    for i in range(30):
        fire_query("", "ollama", f"resonance lock {i}")
        if (i + 1) % 10 == 0:
            print(f"  Lock hammer: {i+1}/30")

    print_status("AFTER PHASE 3 — LOCK HAMMER")

    # ═══════════════════════════════════════
    # PHASE 4: Force re-lock all models with
    # updated trit scores from real queries
    # ═══════════════════════════════════════
    print(f"\n>>> PHASE 4: FORCE LOCK ALL")
    try:
        r = requests.post(f"{ROUTER}/tripple/mirror/force_lock_all", timeout=10)
        d = r.json()
        print(f"  Locked: {d.get('total_locked', 0)} | New: {d.get('new_locks', 0)}")
    except Exception as e:
        print(f"  Lock error: {e}")

    # Final status
    print_status("BLITZ COMPLETE — FINAL STATE")

    # Get mirror stats
    try:
        r = requests.get(f"{ROUTER}/tripple/mirror/status", timeout=10)
        d = r.json()
        print(f"\n  Mirror: {d.get('unique_models', 0)} unique models")
        print(f"  Total reflections: {d.get('total_reflected', 0)}")
    except:
        pass

    try:
        r = requests.get(f"{ROUTER}/tripple/advance/status", timeout=10)
        d = r.json()
        print(f"  Locked: {d.get('locked_count', 0)} | Good: {d.get('good_count', 0)} | Bad: {d.get('bad_count', 0)}")
    except:
        pass

if __name__ == "__main__":
    main()
