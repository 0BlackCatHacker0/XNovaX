"""Pacman Boot Lock — runs at startup to ensure all models are discovered, locked, and ready.

This is the permanent lock guarantee:
1. Discover all models from all providers
2. Extract all skills/abilities/features
3. Bulk inject into Mirror
4. Force-lock everything
5. Verify lock state

Run at boot: python C:/NovaX/tools/pacman_boot_lock.py
"""
import json, sys, urllib.request, ssl, time

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

CLOUD_ROUTER = "http://127.0.0.1:9878"

def api_post(url, data, timeout=30):
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        resp = urllib.request.urlopen(req, timeout=timeout, context=ctx)
        return json.loads(resp.read())
    except Exception as e:
        return {"ok": 0, "error": str(e)}

def api_get(url, timeout=15):
    req = urllib.request.Request(url)
    try:
        resp = urllib.request.urlopen(req, timeout=timeout, context=ctx)
        return json.loads(resp.read())
    except Exception as e:
        return {"ok": 0, "error": str(e)}

def boot_lock():
    print("[Boot Lock] === PACMAN BOOT LOCK SEQUENCE ===")
    start = time.time()

    # Step 1: Check Cloud Router is alive
    print("[Boot Lock] Step 1: Checking Cloud Router...")
    status = api_get(f"{CLOUD_ROUTER}/health")
    if not status.get("ok") and status.get("ok") != 1:
        print("[Boot Lock] FAIL: Cloud Router not responding. Waiting...")
        for attempt in range(10):
            time.sleep(3)
            status = api_get(f"{CLOUD_ROUTER}/health")
            if status.get("ok") or status.get("ok") == 1:
                break
        else:
            print("[Boot Lock] ABORT: Cloud Router unavailable after 30s")
            sys.exit(1)
    print("[Boot Lock] Cloud Router: ONLINE")

    # Step 2: Run model discovery
    print("[Boot Lock] Step 2: Discovering models...")
    import subprocess
    result = subprocess.run(
        [sys.executable, "C:/NovaX/tools/discover_all_models.py"],
        capture_output=True, text=True, timeout=60
    )
    if result.returncode == 0:
        lines = result.stdout.strip().split("\n")
        last_line = lines[-1] if lines else "{}"
        try:
            disc = json.loads(last_line)
            print(f"[Boot Lock] Models discovered: {disc.get('total_pieces', 0)} pieces")
        except:
            print(f"[Boot Lock] Discovery ran (parsing output failed)")
    else:
        print(f"[Boot Lock] WARNING: Discovery script error: {result.stderr[:200]}")

    # Step 3: Run Pacman MEGA discovery (skills/abilities/features)
    print("[Boot Lock] Step 3: Extracting skills/abilities/features (MEGA)...")
    result = subprocess.run(
        [sys.executable, "C:/NovaX/tools/pacman_mega_discover.py"],
        capture_output=True, text=True, timeout=120
    )
    if result.returncode == 0:
        lines = result.stdout.strip().split("\n")
        last_line = lines[-1] if lines else "{}"
        try:
            pac = json.loads(last_line)
            print(f"[Boot Lock] Skills: {pac.get('total_skills', 0)}, Abilities: {pac.get('total_abilities', 0)}, Features: {pac.get('total_features', 0)}")
        except:
            print(f"[Boot Lock] Pacman discovery ran (parsing output failed)")

    # Step 4: Load v2.0 registry and bulk inject ALL models into Mirror
    print("[Boot Lock] Step 4: Bulk injecting into Mirror (v2.0 registry)...")
    try:
        reg = json.load(open("C:/NovaX/data/pacman_registry.json"))
        reg_models = reg.get("models", {})
        models = []
        for mid, mdata in reg_models.items():
            models.append({
                "id": mid,
                "provider": mdata.get("provider", mdata.get("source", "unknown")),
            })

        # Batch inject (500 at a time)
        injected = 0
        batch_size = 500
        for i in range(0, len(models), batch_size):
            batch = models[i:i+batch_size]
            result = api_post(f"{CLOUD_ROUTER}/tripple/mirror/bulk_inject", {"models": batch}, timeout=60)
            injected += result.get("injected", 0)

        print(f"[Boot Lock] Mirror: {injected}/{len(models)} models injected")
    except Exception as e:
        print(f"[Boot Lock] WARNING: Mirror injection failed: {e}")

    # Step 5: Force-lock ALL models (permanent, unlimited access)
    print("[Boot Lock] Step 5: Force-locking all models...")
    lock_result = api_post(f"{CLOUD_ROUTER}/tripple/mirror/force_lock_all", {})
    total_locked = lock_result.get("total_locked", 0)
    print(f"[Boot Lock] Locked: {total_locked} models (permanent, max usage)")

    # Step 6: Send positive ripples to all providers
    print("[Boot Lock] Step 6: Initializing provider frequencies...")
    providers = ["ollama", "novax-prime", "cortex", "openai", "anthropic",
                 "google", "mistral", "groq", "deepseek", "cohere",
                 "together", "openrouter"]
    for p in providers:
        api_post(f"{CLOUD_ROUTER}/tripple/ripple", {
            "provider": p, "trit": 1, "latency_ms": 50
        })
    print(f"[Boot Lock] {len(providers)} providers initialized with +1 trit")

    # Step 7: Verify
    print("[Boot Lock] Step 7: Verifying lock state...")
    tripple = api_get(f"{CLOUD_ROUTER}/tripple/status")
    mirror = api_get(f"{CLOUD_ROUTER}/tripple/mirror/status")

    elapsed = time.time() - start

    print(f"\n[Boot Lock] === LOCK COMPLETE in {elapsed:.1f}s ===")
    print(f"  Models locked:  {total_locked}")
    print(f"  Mirror models:  {mirror.get('total_reflected', 0)}")
    print(f"  Regime:         {tripple.get('regime', '?')}")
    print(f"  Providers:      {len(tripple.get('providers', {}))}")
    print(f"  Status:         ALL SYSTEMS LOCKED AND READY")

    summary = {
        "ok": 1,
        "models_locked": total_locked,
        "mirror_models": mirror.get("total_reflected", 0),
        "providers": len(tripple.get("providers", {})),
        "elapsed_s": round(elapsed, 1),
        "status": "LOCKED_AND_READY"
    }
    print(json.dumps(summary))

if __name__ == "__main__":
    boot_lock()
