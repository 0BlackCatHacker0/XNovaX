"""
MaxTripple Test — Full Ability/Attribute/Skill/Feature Scanner
===============================================================
Scans all 588+ models across 70 providers, classifies abilities,
maps Go territories, runs Pacman infrastructure provisioning,
and feeds advanced models into Hivemind.

Usage: python scripts/max_tripple_test.py
"""
import json, urllib.request, time, sys, os

BASE = "http://127.0.0.1"
HIVEMIND = f"{BASE}:9881"
REGISTRY = f"{BASE}:9860"
ORCHESTRATOR = f"{BASE}:9999"
CLOUD_ROUTER = f"{BASE}:9878"
MS_ENGINE = f"{BASE}:9851"

# ── Helpers ──────────────────────────────────────────────

def get(url, timeout=10):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}

def post(url, data, timeout=15):
    try:
        req = urllib.request.Request(url, json.dumps(data).encode(),
                                     {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}

# ── Ability classifier (mirrors NovaLang Tripple) ────────

ABILITY_PATTERNS = {
    "chat": ["gpt", "claude", "sonnet", "haiku", "opus", "llama", "mistral",
             "falcon", "qwen", "phi", "gemma", "yi", "vicuna", "openchat",
             "zephyr", "hermes", "dolphin", "orca", "aya", "internlm", "glm",
             "starling", "exaone", "stablelm", "samantha", "deepseek", "grok",
             "ernie", "olmo", "command", "solar", "neural"],
    "reasoning": ["deepseek-r1", "marco-o1", "o1", "o3", "o4", "thinking",
                  "think", "sonar-reasoning", "maestro-reasoning", "reflection"],
    "code": ["code", "coder", "codex", "codellama", "codegeex", "magicoder",
             "starcoder", "granite-code", "stable-code", "sqlcoder", "codestral",
             "qwen3-coder", "mercury-coder", "kat-coder", "grok-code", "devstral"],
    "math": ["mathstral", "wizard-math", "math", "nemotron"],
    "vision": ["llava", "moondream", "minicpm-v", "bakllava", "image", "dall",
               "gpt-image", "vision", "-vl-", "qwen3-vl"],
    "embedding": ["embed", "minilm", "nomic", "snowflake", "mxbai", "bge", "e5-"],
    "audio": ["audio", "whisper"],
    "voice": ["realtime"],
    "tts": ["tts"],
    "stt": ["transcribe", "whisper"],
    "video": ["sora"],
    "search": ["search", "sonar"],
    "fast": ["nano", "mini", "tiny", "flash", "turbo", "-fast", "lite", "haiku",
             "instant", "speed"],
    "flagship": ["pro", "opus", "405b", "70b", "large", "max"],
    "system": ["function", "tool", "agent", "computer-use"],
}

def classify_model(model_id):
    mid = model_id.lower()
    abilities = {}
    for ability, patterns in ABILITY_PATTERNS.items():
        for p in patterns:
            if p in mid:
                abilities[ability] = 1
                break
    if not abilities:
        abilities["general"] = 1
    return abilities


# ── Phase 1: System Health Check ─────────────────────────

def phase1_health():
    print("\n" + "="*60)
    print("  PHASE 1: System Health Verification")
    print("="*60)

    services = [
        ("Hivemind", f"{HIVEMIND}/health"),
        ("Registry", f"{REGISTRY}/health"),
        ("CloudRouter", f"{CLOUD_ROUTER}/health"),
        ("MicrosoftEngine", f"{MS_ENGINE}/health"),
        ("Orchestrator", f"{ORCHESTRATOR}/api/services/health"),
    ]

    all_ok = True
    for name, url in services:
        result = get(url)
        status = "OK" if "error" not in result else "FAIL"
        if status == "FAIL":
            all_ok = False
        print(f"  [{status}] {name}")

    # Check Tripple PRIME
    tripple = get(f"{HIVEMIND}/hive/tripple/status")
    prime = tripple.get("prime_locked", 0)
    hyper = tripple.get("hyper_locked", 0)
    score = tripple.get("resonance_score", 0)
    ripples = tripple.get("total_ripples", 0)
    print(f"\n  PRIME: {'LOCKED' if prime else 'UNLOCKED'} | HYPER: {'LOCKED' if hyper else 'UNLOCKED'}")
    print(f"  Score: {score:.1f} | Ripples: {ripples}")

    return all_ok


# ── Phase 2: Full Model Scan ─────────────────────────────

def phase2_scan():
    print("\n" + "="*60)
    print("  PHASE 2: Full Model Catalog Scan (588+ models)")
    print("="*60)

    catalog = get(f"{REGISTRY}/catalog")
    if "error" in catalog:
        print(f"  ERROR: Registry unreachable: {catalog['error']}")
        return {}, {}

    providers = catalog.get("providers", {})
    total_models = 0
    ability_counts = {}
    ability_models = {}  # ability -> list of model IDs
    model_abilities = {}  # model_id -> abilities dict
    provider_counts = {}
    advanced_models = []

    for prov, models in providers.items():
        if not isinstance(models, list):
            continue
        provider_counts[prov] = len(models)
        for m in models:
            if isinstance(m, dict):
                mid = m.get("id", m.get("name", ""))
            else:
                mid = str(m)
            if not mid:
                continue
            total_models += 1
            abilities = classify_model(mid)
            model_abilities[mid] = abilities

            for ab in abilities:
                ability_counts[ab] = ability_counts.get(ab, 0) + 1
                if ab not in ability_models:
                    ability_models[ab] = []
                ability_models[ab].append(mid)

            # "Advanced" = has 3+ abilities or has rare abilities
            rare = set(abilities.keys()) & {"system", "video", "voice", "tts", "stt", "search"}
            if len(abilities) >= 3 or rare:
                advanced_models.append({"id": mid, "abilities": abilities})

    print(f"\n  Total models scanned: {total_models}")
    print(f"  Total providers: {len(provider_counts)}")
    print(f"  Advanced models found: {len(advanced_models)}")
    print(f"\n  Ability Distribution:")
    for ab in sorted(ability_counts, key=ability_counts.get, reverse=True):
        count = ability_counts[ab]
        bar = "#" * min(count // 5, 40)
        print(f"    {ab:12s} : {count:4d} models  {bar}")

    return {
        "total": total_models,
        "providers": len(provider_counts),
        "ability_counts": ability_counts,
        "ability_models": ability_models,
        "model_abilities": model_abilities,
        "advanced_models": advanced_models,
    }, provider_counts


# ── Phase 3: Go Engine Territory Mapping ─────────────────

def phase3_territories(scan_results):
    print("\n" + "="*60)
    print("  PHASE 3: Go Engine Territory Mapping")
    print("="*60)

    territories = ["chat", "code", "reasoning", "image", "audio", "embedding", "fast", "system"]
    ability_counts = scan_results.get("ability_counts", {})

    territory_status = {}
    for t in territories:
        count = ability_counts.get(t, 0)
        if count >= 20:
            status = "DOMINATED"
        elif count >= 5:
            status = "CONTESTED"
        elif count >= 1:
            status = "CLAIMED"
        else:
            status = "EMPTY"
        territory_status[t] = {"count": count, "status": status}

    print(f"\n  Territory Map (8 zones):")
    for t in territories:
        ts = territory_status[t]
        indicator = {"DOMINATED": "[###]", "CONTESTED": "[## ]", "CLAIMED": "[#  ]", "EMPTY": "[   ]"}
        print(f"    {indicator[ts['status']]} {t:12s} : {ts['count']:4d} models ({ts['status']})")

    dominated = sum(1 for t in territory_status.values() if t["status"] == "DOMINATED")
    contested = sum(1 for t in territory_status.values() if t["status"] == "CONTESTED")
    claimed = sum(1 for t in territory_status.values() if t["status"] == "CLAIMED")
    empty = sum(1 for t in territory_status.values() if t["status"] == "EMPTY")

    print(f"\n  Summary: {dominated} dominated, {contested} contested, {claimed} claimed, {empty} empty")

    return territory_status


# ── Phase 4: Pacman Infrastructure Check ─────────────────

def phase4_pacman(scan_results, territory_status):
    print("\n" + "="*60)
    print("  PHASE 4: Pacman Infrastructure Provisioning")
    print("="*60)

    infra_map = {
        "chat":      {"service": "cloud-router",     "port": 9878, "tier": 1},
        "reasoning": {"service": "nova-reasoner",    "port": 9912, "tier": 2},
        "code":      {"service": "nova-sandbox",     "port": 9913, "tier": 2},
        "search":    {"service": "nova-search",      "port": 9914, "tier": 2},
        "image":     {"service": "nova-vision",      "port": 9915, "tier": 3},
        "audio":     {"service": "nova-audio",       "port": 9916, "tier": 3},
        "voice":     {"service": "nova-voice",       "port": 9917, "tier": 3},
        "tts":       {"service": "nova-tts",         "port": 9918, "tier": 2},
        "stt":       {"service": "nova-stt",         "port": 9919, "tier": 2},
        "video":     {"service": "nova-video",       "port": 9920, "tier": 3},
        "embedding": {"service": "nova-embed",       "port": 9921, "tier": 2},
        "fast":      {"service": "nova-fastpath",    "port": 9922, "tier": 1},
        "flagship":  {"service": "nova-premium",     "port": 9923, "tier": 1},
        "system":    {"service": "microsoft-engine", "port": 9851, "tier": 1},
        "math":      {"service": "nova-math",        "port": 9924, "tier": 2},
    }

    installed = []
    pending = []
    upgraded = []

    ability_counts = scan_results.get("ability_counts", {})

    for ability, infra in infra_map.items():
        port = infra["port"]
        service = infra["service"]
        count = ability_counts.get(ability, 0)

        # Check if service is running
        health = get(f"http://127.0.0.1:{port}/health", timeout=2)
        is_up = "error" not in health

        if count > 0 and is_up:
            installed.append({"ability": ability, "service": service, "port": port, "models": count, "status": "INSTALLED"})
        elif count > 0 and not is_up:
            pending.append({"ability": ability, "service": service, "port": port, "models": count, "status": "PENDING"})
        elif count == 0:
            # No models with this ability
            pass

    print(f"\n  Installed Infrastructure ({len(installed)}):")
    for item in installed:
        print(f"    [OK] {item['service']:20s} :{item['port']}  ({item['models']} models)")

    if pending:
        print(f"\n  Pending Infrastructure ({len(pending)}):")
        for item in pending:
            print(f"    [..] {item['service']:20s} :{item['port']}  ({item['models']} models, needs provisioning)")

    return {"installed": installed, "pending": pending}


# ── Phase 5: Inject Advanced Models to Hivemind ──────────

def phase5_inject(scan_results):
    print("\n" + "="*60)
    print("  PHASE 5: Advanced Model Injection to Hivemind")
    print("="*60)

    advanced = scan_results.get("advanced_models", [])
    if not advanced:
        print("  No advanced models to inject.")
        return {}

    # Inject in batches of 50
    model_ids = [m["id"] for m in advanced]
    batch_size = 50
    total_injected = 0
    batches = 0

    for i in range(0, len(model_ids), batch_size):
        batch = model_ids[i:i+batch_size]
        result = post(f"{HIVEMIND}/hive/models/bulk", {"models": batch})
        if "error" not in result:
            total_injected += result.get("added", 0)
            batches += 1

    print(f"  Advanced models identified: {len(advanced)}")
    print(f"  Batches sent: {batches}")
    print(f"  Models injected: {total_injected}")

    # Show top advanced models by ability count
    top = sorted(advanced, key=lambda m: len(m["abilities"]), reverse=True)[:15]
    print(f"\n  Top 15 Advanced Models:")
    for m in top:
        abs_str = ", ".join(sorted(m["abilities"].keys()))
        print(f"    [{len(m['abilities'])}] {m['id'][:50]:50s}  {abs_str}")

    return {"injected": total_injected, "advanced_count": len(advanced), "batches": batches}


# ── Phase 6: Tripple Mirror Scan ─────────────────────────

def phase6_mirror():
    print("\n" + "="*60)
    print("  PHASE 6: Tripple Mirror Resonance Scan")
    print("="*60)

    # Trigger a mirror scan via Hivemind
    mirror = get(f"{HIVEMIND}/hive/tripple/mirror")
    if "error" in mirror:
        print(f"  Mirror unavailable: {mirror['error']}")
        return {}

    mode = mirror.get("mirror_mode", "?")
    discovered = mirror.get("abilities_discovered", {})
    models_scanned = mirror.get("models_scanned", 0)

    print(f"  Mirror mode: {mode}")
    print(f"  Models in mirror: {models_scanned}")
    print(f"  Abilities discovered: {len(discovered)}")

    if discovered:
        print(f"\n  Discovered Ability Frequencies:")
        for ab, count in sorted(discovered.items(), key=lambda x: x[1], reverse=True):
            bar = "#" * min(count, 30)
            print(f"    {ab:12s} : {count:4d}  {bar}")

    return {"mode": mode, "discovered": discovered, "models_scanned": models_scanned}


# ── Phase 7: Microsoft Engine Integration Test ───────────

def phase7_microsoft():
    print("\n" + "="*60)
    print("  PHASE 7: Microsoft Engine Integration Test")
    print("="*60)

    # Test system info tool
    result = post(f"{MS_ENGINE}/microsoft/system", {"op": "info"})
    if "error" in result:
        print(f"  System info: FAIL ({result['error']})")
    else:
        os_info = result.get("os", "?")
        cpu = result.get("cpu", "?")
        mem = result.get("memory", {})
        print(f"  System info: OK")
        print(f"    OS: {os_info}")
        print(f"    CPU: {cpu}")
        if isinstance(mem, dict):
            total_gb = mem.get("total", 0) / (1024**3) if mem.get("total") else 0
            print(f"    RAM: {total_gb:.1f} GB")

    # Test process list
    result2 = post(f"{MS_ENGINE}/microsoft/process", {"op": "list"})
    proc_count = len(result2.get("processes", [])) if "processes" in result2 else 0
    print(f"  Processes: {proc_count} running")

    # Test theme
    result3 = post(f"{MS_ENGINE}/microsoft/theme", {"op": "darkmode"})
    dark = result3.get("dark_mode", "?")
    print(f"  Dark mode: {dark}")

    status = get(f"{MS_ENGINE}/status")
    total_calls = status.get("stats", {}).get("total_calls", 0)
    print(f"  Total API calls: {total_calls}")

    return {"system": "error" not in result, "processes": proc_count}


# ── Phase 8: Final Resonance Check ───────────────────────

def phase8_resonance():
    print("\n" + "="*60)
    print("  PHASE 8: Final Resonance & PRIME Status")
    print("="*60)

    tripple = get(f"{HIVEMIND}/hive/tripple/status")
    score = tripple.get("resonance_score", 0)
    prime = tripple.get("prime_locked", 0)
    hyper = tripple.get("hyper_locked", 0)
    ripples = tripple.get("total_ripples", 0)
    regime = tripple.get("regime", "?")

    print(f"\n  Resonance Score:  {score:.2f}")
    print(f"  PRIME Lock:       {'PERMANENT' if prime else 'UNLOCKED'}")
    print(f"  HYPER Lock:       {'PERMANENT' if hyper else 'UNLOCKED'}")
    print(f"  Total Ripples:    {ripples}")
    print(f"  Flow Regime:      {regime}")

    # Get Hivemind status
    hive = get(f"{HIVEMIND}/hive/status")
    models = hive.get("models", 0)
    channels = hive.get("flow_channels", 0)

    print(f"  Hivemind Models:  {models}")
    print(f"  Flow Channels:    {channels}")

    return {
        "score": score,
        "prime": bool(prime),
        "hyper": bool(hyper),
        "ripples": ripples,
        "models": models,
        "channels": channels,
    }


# ── Main ─────────────────────────────────────────────────

def main():
    print("\n" + "#"*60)
    print("  MAX TRIPPLE TEST")
    print("  Full Ability/Attribute/Skill/Feature Scanner")
    print("  NovaX Hivemind + Tripple + Go + Pacman + Microsoft")
    print("#"*60)

    t0 = time.time()

    # Phase 1: Health
    ok = phase1_health()
    if not ok:
        print("\n  WARNING: Some services unhealthy. Continuing anyway...")

    # Phase 2: Scan
    scan_results, provider_counts = phase2_scan()
    if not scan_results:
        print("\n  FATAL: No scan results. Aborting.")
        return

    # Phase 3: Territories
    territory_status = phase3_territories(scan_results)

    # Phase 4: Pacman
    infra_status = phase4_pacman(scan_results, territory_status)

    # Phase 5: Inject
    inject_results = phase5_inject(scan_results)

    # Phase 6: Mirror
    mirror_results = phase6_mirror()

    # Phase 7: Microsoft Engine
    ms_results = phase7_microsoft()

    # Phase 8: Final resonance
    final = phase8_resonance()

    elapsed = time.time() - t0

    # ── Summary ──
    print("\n" + "="*60)
    print("  MAX TRIPPLE TEST — COMPLETE")
    print("="*60)
    print(f"  Time:           {elapsed:.1f}s")
    print(f"  Models scanned: {scan_results.get('total', 0)}")
    print(f"  Providers:      {scan_results.get('providers', 0)}")
    print(f"  Abilities:      {len(scan_results.get('ability_counts', {}))}")
    print(f"  Advanced found: {len(scan_results.get('advanced_models', []))}")
    print(f"  Injected:       {inject_results.get('injected', 0)}")
    print(f"  Territories:    {len(territory_status)} zones")
    print(f"  Installed svc:  {len(infra_status.get('installed', []))}")
    print(f"  Pending svc:    {len(infra_status.get('pending', []))}")
    print(f"  PRIME:          {'LOCKED' if final.get('prime') else 'UNLOCKED'}")
    print(f"  HYPER:          {'LOCKED' if final.get('hyper') else 'UNLOCKED'}")
    print(f"  Score:          {final.get('score', 0):.2f}")
    print(f"  Channels:       {final.get('channels', 0)}")
    print("="*60)

    # Write results to file
    report = {
        "test": "MaxTripple",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "elapsed_seconds": round(elapsed, 1),
        "scan": {
            "total_models": scan_results.get("total", 0),
            "providers": scan_results.get("providers", 0),
            "ability_counts": scan_results.get("ability_counts", {}),
            "advanced_count": len(scan_results.get("advanced_models", [])),
        },
        "territories": territory_status,
        "infrastructure": infra_status,
        "injection": inject_results,
        "mirror": mirror_results,
        "microsoft_engine": ms_results,
        "final_state": final,
    }

    report_path = "C:/NovaX/tmp/max_tripple_report.json"
    os.makedirs("C:/NovaX/tmp", exist_ok=True)
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\n  Report saved: {report_path}")


if __name__ == "__main__":
    main()
