"""N-S Finetune: Apply Navier-Stokes frequency tuning across all providers and models.
Then Tripple all models, activate Pacman, and lock everything in."""
import json, sys, urllib.request, time

BASE = "http://localhost:9878"

def post(path, data=None):
    body = json.dumps(data or {}).encode()
    req = urllib.request.Request(f"{BASE}{path}", body, {"Content-Type": "application/json"})
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}

def get(path):
    try:
        resp = urllib.request.urlopen(f"{BASE}{path}", timeout=10)
        return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}

def main():
    print("=" * 60)
    print("N-S FINETUNE + TRIPPLE LOCK SEQUENCE")
    print("=" * 60)

    # Phase 1: Load all pieces
    print("\n[Phase 1] Loading piece registry...")
    pieces_data = json.load(open("C:/NovaX/data/go_pieces.json"))
    pieces = pieces_data.get("pieces", {})
    total = pieces_data.get("total", len(pieces))
    by_terr = pieces_data.get("by_territory", {})
    print(f"  {total} pieces across {len(by_terr)} territories")
    for t, c in sorted(by_terr.items(), key=lambda x: -x[1]):
        print(f"    {t:12s}: {c} pieces")

    # Phase 2: N-S Frequency Tuning - ripple every provider with +1 trit
    print("\n[Phase 2] N-S Frequency Tuning - rippling all providers...")
    status = get("/tripple/status")
    providers = status.get("providers", {})
    ripple_count = 0
    for pname in providers:
        # Send 3 positive ripples per provider (H3=3) to boost frequencies
        for _ in range(3):
            result = post("/tripple/ripple", {
                "provider": pname,
                "trit": 1,
                "latency_ms": 100  # simulated good latency
            })
            ripple_count += 1
    print(f"  Sent {ripple_count} positive ripples to {len(providers)} providers")

    # Phase 3: Place Go stones for all territories
    print("\n[Phase 3] Placing Go stones across all territories...")
    territories = ["chat", "code", "reasoning", "image", "audio", "embedding", "fast"]
    stone_count = 0
    # Group pieces by provider+territory, place stones for the best ones
    provider_terr = {}
    for key, piece in pieces.items():
        p = piece["provider"]
        t = piece["territory"]
        pt_key = f"{p}:{t}"
        if pt_key not in provider_terr:
            provider_terr[pt_key] = piece
            result = post("/tripple/go/place", {
                "provider": p,
                "territory": t,
                "trit": 1
            })
            stone_count += 1

    print(f"  Placed {stone_count} stones across {len(territories)} territories")

    # Phase 4: Run Go strategic control to evaluate and generate commands
    print("\n[Phase 4] Running Go strategic control...")
    control = post("/tripple/go/control", {})
    total_cmds = control.get("total_commands", 0)
    print(f"  Generated {total_cmds} control commands")
    tripple_cmds = control.get("tripple_commands", [])
    hive_cmds = control.get("hivemind_commands", [])
    fleet_cmds = control.get("fleet_commands", [])
    print(f"    Tripple: {len(tripple_cmds)} freq adjustments")
    print(f"    Hivemind: {len(hive_cmds)} modulation commands")
    print(f"    Fleet: {len(fleet_cmds)} expansion commands")

    # Phase 5: Bulk inject ALL models into mirror system
    print("\n[Phase 5] Bulk injecting all models into Mirror...")
    # Build mirror entries from pieces
    mirror_entries = []
    seen_models = set()
    for key, piece in pieces.items():
        model_key = f"{piece['provider']}:{piece['model']}"
        if model_key not in seen_models:
            seen_models.add(model_key)
            mirror_entries.append({
                "provider": piece["provider"],
                "id": piece["model"],
                "trit": 1,
                "latency_ms": 200,
            })

    # Batch inject (API might have limits)
    batch_size = 50
    total_injected = 0
    for i in range(0, len(mirror_entries), batch_size):
        batch = mirror_entries[i:i+batch_size]
        result = post("/tripple/mirror/bulk_inject", {"models": batch})
        injected = result.get("injected", 0)
        total_injected += injected

    print(f"  Injected {total_injected} models into Mirror (from {len(mirror_entries)} unique)")

    # Phase 6: Force lock all models in Mirror
    print("\n[Phase 6] Force-locking all models...")
    lock_result = post("/tripple/mirror/force_lock_all", {})
    locked = lock_result.get("locked", lock_result.get("locked_count", 0))
    print(f"  Locked: {locked} models")

    # Phase 7: Activate Pacman
    print("\n[Phase 7] Running Pacman auto-discovery...")
    pacman = get("/tripple/pacman/status")
    installed = pacman.get("installed_count", 0)
    missing = pacman.get("missing_count", 0)
    total_possible = pacman.get("total_possible", 0)
    print(f"  Installed: {installed}/{total_possible}")
    print(f"  Missing: {missing}")
    if missing > 0:
        print(f"  Missing items: {pacman.get('missing', [])}")

    # Phase 8: Run resonance check to update regime
    print("\n[Phase 8] Running resonance check...")
    # Hit the prime endpoint which triggers auto_control
    prime = get("/tripple/prime")
    print(f"  Prime locked: {prime.get('prime_locked', 0)}")
    print(f"  Resonance score: {prime.get('resonance_score', 0)}")
    print(f"  Lock status: {prime.get('lock_status', 'unknown')}")

    # Phase 9: Final status
    print("\n[Phase 9] Final fleet status...")
    final = get("/tripple/status")
    print(f"  Regime: {final.get('regime', '?')}")
    print(f"  Resonance: {final.get('resonance_score', 0)}")
    print(f"  Prime: {'LOCKED' if final.get('prime_locked') else 'SCATTERED'}")
    print(f"  Total ripples: {final.get('total_ripples', 0)}")

    # Count providers by frequency
    for pname, pdata in final.get("providers", {}).items():
        freq = pdata.get("current_freq", 0)
        success = pdata.get("success_rate", 0)
        queries = pdata.get("total_queries", 0)
        phase = "IN-PHASE" if pdata.get("in_phase", 0) else "out"
        print(f"    {pname:14s}: freq={freq:6.0f} success={success:.0f} queries={queries} [{phase}]")

    # Final Go board
    go = get("/tripple/go")
    go_data = go.get("go", {})
    print(f"\n  Go Score: {go_data.get('go_score', 0)}")
    print(f"  Coverage: {go_data.get('coverage_pct', 0):.1f}%")
    for t, td in go_data.get("territories", {}).items():
        ctrl = td.get("control", "?")
        stones = td.get("total_stones", 0)
        print(f"    {t:12s}: {ctrl:10s} ({stones} stones)")

    pieces_final = get("/tripple/go/pieces")
    print(f"\n  Total pieces mapped: {pieces_final.get('total_pieces', 0)}")

    print("\n" + "=" * 60)
    print("N-S FINETUNE COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    main()
