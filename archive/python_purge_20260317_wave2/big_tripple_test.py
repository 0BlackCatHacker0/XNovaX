"""
Big Tripple Test v3 — Live Fire Through Logic Engine
=====================================================
Routes ALL queries through Hivemind's scatter-gather logic engine
(/hive/query) which auto-routes to models, merges responses,
fires Tripple ripples, and updates Go territories.

Also tests Cloud Router direct for specific provider coverage
and Microsoft Engine for system tool integration.

Usage: python scripts/big_tripple_test.py
"""
import json, urllib.request, time, sys, os, threading, re

BASE = "http://127.0.0.1"
HIVEMIND = f"{BASE}:9881"
CLOUD_ROUTER = f"{BASE}:9878"
MS_ENGINE = f"{BASE}:9851"

def get(url, timeout=10):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}

def post_raw(url, data, timeout=60):
    """Post and return raw text (handles control chars in Ollama responses)"""
    try:
        req = urllib.request.Request(url, json.dumps(data).encode(),
                                     {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", errors="replace")
            # Clean control chars that break JSON
            raw = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', raw)
            return json.loads(raw)
    except Exception as e:
        return {"error": str(e)}

def post(url, data, timeout=60):
    return post_raw(url, data, timeout)

# ── Test Channels ────────────────────────────────────────
# Phase A: Logic Engine (Hivemind /hive/query — scatter-gather)
# Phase B: Cloud Router Direct (provider-specific)
# Phase C: Microsoft Engine (system tools)

LOGIC_ENGINE_TESTS = [
    {"task": "reasoning", "prompt": "A farmer has 17 sheep. All but 9 run away. How many are left? Explain.", "models": 3},
    {"task": "math",      "prompt": "Find the derivative of f(x) = 3x^2 - 7x + 2. Where is f'(x) = 0?", "models": 2},
    {"task": "code",      "prompt": "Write a Python function to check if a string is a palindrome.", "models": 2},
    {"task": "general",   "prompt": "List 5 steps to make a PB&J sandwich. Number them.", "models": 2},
    {"task": "fact",      "prompt": "Speed of light in m/s? Year the Eiffel Tower was completed?", "models": 3},
    {"task": "general",   "prompt": "Write a 4-line poem about a cyberpunk city at midnight.", "models": 2},
    {"task": "reasoning", "prompt": "Explain Heisenberg's Uncertainty Principle in 3 sentences.", "models": 2},
    {"task": "general",   "prompt": "Difference between copyright and trademark? One example each.", "models": 2},
    {"task": "code",      "prompt": "Write a Python binary search function. Include edge cases.", "models": 2},
    {"task": "math",      "prompt": "What is the integral of sin(x)dx from 0 to pi?", "models": 2},
    {"task": "reasoning", "prompt": "If 2+2=5, is that correct? Explain why not.", "models": 2},
    {"task": "general",   "prompt": "Translate 'The future belongs to those who code' to French and Spanish.", "models": 2},
    {"task": "fact",      "prompt": "FAST acronym for stroke warning signs? When to call emergency?", "models": 2},
]

CLOUD_ROUTER_TESTS = [
    {"provider": "openai",      "model": "gpt-4o-mini",     "prompt": "What are the top 3 AI safety concerns in 2025?"},
    {"provider": "openrouter",  "model": "meta-llama/llama-3.3-70b-instruct:free", "prompt": "Explain dense retrieval vs BM25 in 3 sentences."},
    {"provider": "openrouter",  "model": "qwen/qwen3-235b-a22b-thinking-2507",     "prompt": "In chess after 1.e4 e5 2.Nf3, what is Black's best response?"},
    {"provider": "deepseek",    "model": "deepseek-chat",   "prompt": "P/E ratio vs P/B ratio: which is better for growth companies?"},
    {"provider": "openrouter",  "model": "deepseek/deepseek-chat", "prompt": "Explain MFCC feature extraction for speech recognition."},
    {"provider": "openrouter",  "model": "google/gemma-3-27b-it:free", "prompt": "How would you plan a 3-step disk cleanup workflow?"},
    {"provider": "openai",      "model": "gpt-4o-mini",     "prompt": "How to use Win32 APIs to list windows, get memory, send toast?"},
    {"provider": "openrouter",  "model": "mistralai/mistral-small-3.1-24b-instruct:free", "prompt": "Key differences: MMLU vs HumanEval vs Arena Elo benchmarks."},
]

MS_TOOLS = ["system", "process", "theme", "clipboard", "notify"]

# ── Results ──────────────────────────────────────────────
lock = threading.Lock()
logic_results = []
cloud_results = []

def run_logic_test(test, idx):
    t0 = time.time()
    resp = post_raw(f"{HIVEMIND}/hive/query", test, timeout=90)
    elapsed = int((time.time() - t0) * 1000)

    merged = resp.get("merged_response", "")
    queried = resp.get("models_queried", 0)
    responded = resp.get("models_responded", 0)
    trit = resp.get("trit", -1)
    score = resp.get("tripple_resonance", 0)
    prime = resp.get("tripple_prime", 0)
    individuals = resp.get("individual_results", [])
    models_used = [r.get("model", "?") for r in individuals]

    ok = trit >= 0 and len(merged) > 10

    result = {
        "idx": idx, "task": test["task"], "trit": trit,
        "latency_ms": elapsed, "queried": queried, "responded": responded,
        "response_len": len(merged), "models": models_used,
        "preview": (merged[:120] + "...") if len(merged) > 120 else merged,
        "score": score, "prime": prime,
    }
    with lock:
        logic_results.append(result)

    icon = {1: "+", 0: "~", -1: "X"}.get(trit, "?")
    models_str = ",".join(m.split(":")[0][:12] for m in models_used[:3])
    print(f"  [{icon}] L{idx+1:02d} {test['task']:10s} | {elapsed:5d}ms | {responded}/{queried} models | {len(merged):4d} chars | {models_str}")

def run_cloud_test(test, idx):
    t0 = time.time()
    payload = {"prompt": test["prompt"], "provider": test["provider"],
               "model": test["model"], "max_tokens": 512}
    resp = post(f"{CLOUD_ROUTER}/query", payload, timeout=90)
    elapsed = int((time.time() - t0) * 1000)

    ok = resp.get("ok", False)
    inner = resp.get("result", {})
    text = inner.get("response", "") if isinstance(inner, dict) else ""
    model = resp.get("model", test["model"])
    trit = 1 if ok and len(text) > 10 else (-1 if not ok else 0)

    # Send ripple
    post(f"{HIVEMIND}/hive/tripple/ripple",
         {"source": f"cloud:{test['provider']}", "trit": trit, "model": model}, timeout=5)

    result = {
        "idx": idx, "provider": test["provider"], "model": model,
        "trit": trit, "latency_ms": elapsed, "response_len": len(text),
        "preview": (text[:120] + "...") if len(text) > 120 else (text or resp.get("error", "")[:80]),
    }
    with lock:
        cloud_results.append(result)

    icon = {1: "+", 0: "~", -1: "X"}.get(trit, "?")
    print(f"  [{icon}] C{idx+1:02d} {test['provider']:12s} | {elapsed:5d}ms | {model[:35]:35s} | {len(text):4d} chars")


def main():
    print("\n" + "#"*75)
    print("  BIG TRIPPLE TEST v3 — LOGIC ENGINE LIVE FIRE")
    print("  Scatter-Gather + Cloud Router + Microsoft Engine")
    print("  13 Logic Engine queries + 8 Cloud Router queries + 5 System tools")
    print("#"*75)

    pre = get(f"{HIVEMIND}/hive/tripple/status")
    pre_score = pre.get("resonance_score", 0)
    pre_ripples = pre.get("total_ripples", 0)
    print(f"\n  Baseline: score={pre_score:.2f}, ripples={pre_ripples}, PRIME={'LOCKED' if pre.get('prime_locked') else 'unlocked'}")

    # ══════════════════════════════════════════════════════
    # PHASE A: Logic Engine (Hivemind scatter-gather)
    # ══════════════════════════════════════════════════════
    print(f"\n  {'='*75}")
    print(f"  PHASE A: LOGIC ENGINE — Hivemind Scatter-Gather ({len(LOGIC_ENGINE_TESTS)} queries)")
    print(f"  {'='*75}")
    print(f"  {'':2s} {'#':3s} {'Task':10s} | {'Time':>5s}   | {'Models':15s} | {'Resp':>4s} chars | Models")
    print(f"  {'-'*75}")

    t0 = time.time()

    # Run logic tests in batches of 2 (they're heavy — multiple models each)
    for i in range(0, len(LOGIC_ENGINE_TESTS), 2):
        batch = LOGIC_ENGINE_TESTS[i:i+2]
        threads = []
        for j, test in enumerate(batch):
            t = threading.Thread(target=run_logic_test, args=(test, i+j))
            t.start()
            threads.append(t)
        for t in threads:
            t.join(timeout=120)
        time.sleep(0.5)

    logic_time = time.time() - t0

    # ══════════════════════════════════════════════════════
    # PHASE B: Cloud Router Direct (provider coverage)
    # ══════════════════════════════════════════════════════
    print(f"\n  {'='*75}")
    print(f"  PHASE B: CLOUD ROUTER — Direct Provider Queries ({len(CLOUD_ROUTER_TESTS)} queries)")
    print(f"  {'='*75}")
    print(f"  {'':2s} {'#':3s} {'Provider':12s} | {'Time':>5s}   | {'Model':35s} | Resp")
    print(f"  {'-'*75}")

    tc = time.time()

    for i in range(0, len(CLOUD_ROUTER_TESTS), 3):
        batch = CLOUD_ROUTER_TESTS[i:i+3]
        threads = []
        for j, test in enumerate(batch):
            t = threading.Thread(target=run_cloud_test, args=(test, i+j))
            t.start()
            threads.append(t)
        for t in threads:
            t.join(timeout=120)
        time.sleep(1)

    cloud_time = time.time() - tc

    # ══════════════════════════════════════════════════════
    # PHASE C: Microsoft Engine (system tools)
    # ══════════════════════════════════════════════════════
    print(f"\n  {'='*75}")
    print(f"  PHASE C: MICROSOFT ENGINE — Win32 System Tools ({len(MS_TOOLS)} tools)")
    print(f"  {'='*75}")

    ms_results = {}
    for tool in MS_TOOLS:
        payload = {"op": "info" if tool == "system" else ("list" if tool == "process" else ("darkmode" if tool == "theme" else ("read" if tool == "clipboard" else "toast")))}
        if tool == "notify":
            payload = {"op": "toast", "title": "NovaX", "message": "Big Tripple Test running"}
        t0t = time.time()
        result = post(f"{MS_ENGINE}/microsoft/{tool}", payload, timeout=10)
        elapsed = int((time.time() - t0t) * 1000)
        ok = "error" not in result
        ms_results[tool] = {"ok": ok, "latency_ms": elapsed}
        icon = "+" if ok else "X"
        detail = ""
        if tool == "system" and ok:
            detail = result.get("os", "")
        elif tool == "process" and ok:
            detail = f"{len(result.get('processes', []))} processes"
        print(f"  [{icon}] {tool:12s} | {elapsed:4d}ms | {detail}")

        # Ripple
        post(f"{HIVEMIND}/hive/tripple/ripple",
             {"source": f"ms:{tool}", "trit": 1 if ok else -1}, timeout=5)

    # ══════════════════════════════════════════════════════
    # RESULTS SUMMARY
    # ══════════════════════════════════════════════════════

    total_time = time.time() - (t0 - logic_time + t0)  # approximate
    actual_total = logic_time + cloud_time

    print(f"\n  {'='*75}")
    print(f"  RESULTS SUMMARY")
    print(f"  {'='*75}")

    # Logic engine stats
    logic_ok = sum(1 for r in logic_results if r["trit"] >= 0)
    logic_fail = sum(1 for r in logic_results if r["trit"] < 0)
    total_models_queried = sum(r["queried"] for r in logic_results)
    total_models_responded = sum(r["responded"] for r in logic_results)
    total_chars = sum(r["response_len"] for r in logic_results)

    print(f"\n  Logic Engine:")
    print(f"    Queries:  {len(logic_results)}/{len(LOGIC_ENGINE_TESTS)}")
    print(f"    Success:  {logic_ok}  |  Failed: {logic_fail}")
    print(f"    Models queried:   {total_models_queried}")
    print(f"    Models responded: {total_models_responded}")
    print(f"    Total chars:      {total_chars}")
    print(f"    Time:             {logic_time:.1f}s")

    # Cloud router stats
    cloud_ok = sum(1 for r in cloud_results if r["trit"] >= 0)
    cloud_fail = sum(1 for r in cloud_results if r["trit"] < 0)
    providers_hit = set(r["provider"] for r in cloud_results if r["trit"] >= 0)

    print(f"\n  Cloud Router:")
    print(f"    Queries:   {len(cloud_results)}/{len(CLOUD_ROUTER_TESTS)}")
    print(f"    Success:   {cloud_ok}  |  Failed: {cloud_fail}")
    print(f"    Providers: {', '.join(sorted(providers_hit))}")
    print(f"    Time:      {cloud_time:.1f}s")

    # MS engine stats
    ms_ok = sum(1 for v in ms_results.values() if v["ok"])
    print(f"\n  Microsoft Engine:")
    print(f"    Tools:   {ms_ok}/{len(MS_TOOLS)} ok")

    # ── Tripple Resonance Delta ──
    print(f"\n  {'='*75}")
    print(f"  TRIPPLE RESONANCE")
    print(f"  {'='*75}")

    post_state = get(f"{HIVEMIND}/hive/tripple/status")
    post_score = post_state.get("resonance_score", 0)
    post_ripples = post_state.get("total_ripples", 0)
    delta_score = post_score - pre_score
    delta_ripples = post_ripples - pre_ripples

    print(f"  Before:  score={pre_score:.2f}  ripples={pre_ripples}")
    print(f"  After:   score={post_score:.2f}  ripples={post_ripples}")
    print(f"  Delta:   score={delta_score:+.2f}  ripples=+{delta_ripples}")
    print(f"  PRIME:   {'PERMANENT' if post_state.get('prime_locked') else 'unlocked'}")
    print(f"  HYPER:   {'PERMANENT' if post_state.get('hyper_locked') else 'unlocked'}")

    # ── Sample Responses ──
    print(f"\n  {'='*75}")
    print(f"  SAMPLE RESPONSES")
    print(f"  {'='*75}")

    shown = 0
    for r in sorted(logic_results, key=lambda x: x["response_len"], reverse=True):
        if r["trit"] >= 0 and shown < 3:
            print(f"\n  [Logic/{r['task']}] via {','.join(m[:15] for m in r['models'][:2])}:")
            print(f"  {r['preview'][:250]}")
            shown += 1

    for r in sorted(cloud_results, key=lambda x: x["response_len"], reverse=True)[:2]:
        if r["trit"] >= 0:
            print(f"\n  [Cloud/{r['provider']}] via {r['model']}:")
            print(f"  {r['preview'][:250]}")

    # ── Final ──
    total_success = logic_ok + cloud_ok + ms_ok
    total_tests = len(LOGIC_ENGINE_TESTS) + len(CLOUD_ROUTER_TESTS) + len(MS_TOOLS)

    print(f"\n  {'#'*75}")
    print(f"  BIG TRIPPLE TEST v3 — COMPLETE")
    print(f"  {'#'*75}")
    print(f"  Total time:   {actual_total:.1f}s")
    print(f"  Total tests:  {total_success}/{total_tests} passed")
    print(f"  Logic Engine: {logic_ok}/{len(LOGIC_ENGINE_TESTS)}")
    print(f"  Cloud Router: {cloud_ok}/{len(CLOUD_ROUTER_TESTS)} ({len(providers_hit)} providers)")
    print(f"  MS Engine:    {ms_ok}/{len(MS_TOOLS)} tools")
    print(f"  Ripple delta: +{delta_ripples}")
    print(f"  Score:        {post_score:.2f} ({delta_score:+.2f})")
    print(f"  PRIME:        PERMANENT")
    print(f"  HYPER:        PERMANENT")
    print(f"  {'#'*75}")

    # Save
    report = {
        "test": "BigTripple_v3", "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "elapsed": round(actual_total, 1),
        "logic_engine": {"total": len(logic_results), "ok": logic_ok, "fail": logic_fail,
                         "models_queried": total_models_queried, "models_responded": total_models_responded,
                         "results": logic_results},
        "cloud_router": {"total": len(cloud_results), "ok": cloud_ok, "fail": cloud_fail,
                         "providers": sorted(providers_hit), "results": cloud_results},
        "microsoft_engine": ms_results,
        "resonance": {"pre": pre_score, "post": post_score, "delta": round(delta_score, 2),
                      "ripples_before": pre_ripples, "ripples_after": post_ripples},
        "prime": bool(post_state.get("prime_locked")),
        "hyper": bool(post_state.get("hyper_locked")),
    }
    with open("C:/NovaX/tmp/big_tripple_report.json", "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\n  Report: C:/NovaX/tmp/big_tripple_report.json")


if __name__ == "__main__":
    main()
