"""
NovaX Orchestrator Health Check Patch
-------------------------------------
Monkey-patches _check_service_health and route_services_health3 in the running
orchestrator to fix false "dead" reports.

Fixes:
1. Adds TCP-only probe for non-HTTP services (Redis 6379, Ollama 11434)
2. Accepts any HTTP 2xx as healthy (removes strict "ok" body check)
3. Falls back to GET / when /health returns error
4. Falls back to TCP connect when all HTTP fails (marks as "degraded" not "dead")
5. Reduces timeout from 5s to 2s

Load via: import health_patch  (from orchestrator or boot script)
"""
import socket as _sock
import time
import threading
import sys
import types

def apply_patch():
    """Apply health check patches to the running orchestrator module."""
    # Find the orchestrator module — it's loaded as __main__ by boot_orchestrator.py
    orch = None
    # First try __main__ (normal boot path)
    main_mod = sys.modules.get("__main__")
    if main_mod and hasattr(main_mod, '_check_service_health') and hasattr(main_mod, 'KNOWN_SERVICES'):
        orch = main_mod
    else:
        # Fallback: scan all modules
        for name, mod in sys.modules.items():
            if mod and hasattr(mod, '_check_service_health') and hasattr(mod, 'KNOWN_SERVICES'):
                orch = mod
                break

    if orch is None:
        print("[health_patch] WARNING: orchestrator module not found, patch not applied")
        return False

    # Patch constants
    orch.HEALTH_TIMEOUT = 2  # was 5

    # Add TCP-only service set
    orch._TCP_ONLY_SERVICES = {6379, 11434}  # Redis, Ollama

    # Add TCP probe function
    def _tcp_probe(port, timeout=1.0):
        """Quick TCP connect probe. Returns (alive: bool, elapsed_ms: float)."""
        t0 = time.time()
        s = _sock.socket(_sock.AF_INET, _sock.SOCK_STREAM)
        s.settimeout(timeout)
        try:
            result = s.connect_ex(("127.0.0.1", port))
            elapsed_ms = (time.time() - t0) * 1000
            return (result == 0, round(elapsed_ms, 1))
        except Exception:
            elapsed_ms = (time.time() - t0) * 1000
            return (False, round(elapsed_ms, 1))
        finally:
            s.close()

    orch._tcp_probe = _tcp_probe

    # Store references to orchestrator globals we need
    _health_lock = orch._health_lock
    _service_health = orch._service_health
    _health_record = orch._health_record
    _tripple_ripple_report = orch._tripple_ripple_report
    RE_TURBULENT = orch.RE_TURBULENT
    MAX_CONSECUTIVE_FAILURES = orch.MAX_CONSECUTIVE_FAILURES
    _TCP_ONLY_SERVICES = orch._TCP_ONLY_SERVICES

    def _check_service_health(port, name):
        """Check a single service's health. Strategy:
        1. Non-HTTP services (Redis, Ollama): TCP connect probe only.
        2. HTTP services: GET /health first, fallback to GET / if /health fails.
        3. If HTTP fails entirely, TCP connect fallback -> 'degraded' (port open but no HTTP).
        Returns dict with status ('healthy'|'degraded'|'dead'), trit (+1/0/-1), response_ms."""
        import urllib.request as _ur

        HEALTH_TIMEOUT = orch.HEALTH_TIMEOUT

        # -- Non-HTTP services: TCP-only probe --
        if port in _TCP_ONLY_SERVICES:
            alive, elapsed_ms = _tcp_probe(port, HEALTH_TIMEOUT)
            with _health_lock:
                entry = _service_health.get(port, {
                    "status": "healthy", "consecutive_failures": 0,
                    "last_check": 0, "last_recovery": 0, "response_ms": 0.0,
                })
                entry["last_check"] = time.time()
                entry["response_ms"] = elapsed_ms
                if alive:
                    entry["consecutive_failures"] = 0
                    entry["status"] = "healthy"
                else:
                    entry["consecutive_failures"] += 1
                    if entry["consecutive_failures"] >= MAX_CONSECUTIVE_FAILURES:
                        entry["status"] = "dead"
                    else:
                        entry["status"] = "degraded"
                _service_health[port] = entry
            trit = 1 if entry["status"] == "healthy" else (0 if entry["status"] == "degraded" else -1)
            _health_record(name, entry["status"], elapsed_ms)
            _tripple_ripple_report(name, trit, elapsed_ms)
            return {"port": port, "name": name, "status": entry["status"],
                    "trit": trit, "response_ms": elapsed_ms,
                    "consecutive_failures": entry["consecutive_failures"]}

        # -- HTTP services: try /health, fallback to /, then TCP --
        t0 = time.time()
        try:
            req = _ur.Request(f"http://127.0.0.1:{port}/health", method="GET")
            resp = _ur.urlopen(req, timeout=HEALTH_TIMEOUT)
            elapsed_ms = (time.time() - t0) * 1000
            # Any 2xx response = healthy (don't require "ok" in body)
            with _health_lock:
                entry = _service_health.get(port, {
                    "status": "healthy", "consecutive_failures": 0,
                    "last_check": 0, "last_recovery": 0, "response_ms": 0.0,
                })
                entry["last_check"] = time.time()
                entry["response_ms"] = round(elapsed_ms, 1)
                if 200 <= resp.status < 300:
                    entry["consecutive_failures"] = 0
                    if elapsed_ms > RE_TURBULENT:
                        entry["status"] = "degraded"
                    else:
                        entry["status"] = "healthy"
                else:
                    entry["consecutive_failures"] += 1
                    if entry["consecutive_failures"] >= MAX_CONSECUTIVE_FAILURES:
                        entry["status"] = "dead"
                    else:
                        entry["status"] = "degraded"
                _service_health[port] = entry
            trit = 1 if entry["status"] == "healthy" else (0 if entry["status"] == "degraded" else -1)
            _health_record(name, entry["status"], elapsed_ms)
            _tripple_ripple_report(name, trit, round(elapsed_ms, 1))
            return {"port": port, "name": name, "status": entry["status"],
                    "trit": trit, "response_ms": round(elapsed_ms, 1),
                    "consecutive_failures": entry["consecutive_failures"]}
        except Exception:
            # /health failed -- try fallback to GET /
            try:
                req2 = _ur.Request(f"http://127.0.0.1:{port}/", method="GET")
                resp2 = _ur.urlopen(req2, timeout=HEALTH_TIMEOUT)
                elapsed_ms = (time.time() - t0) * 1000
                if 200 <= resp2.status < 300:
                    with _health_lock:
                        entry = _service_health.get(port, {
                            "status": "healthy", "consecutive_failures": 0,
                            "last_check": 0, "last_recovery": 0, "response_ms": 0.0,
                        })
                        entry["last_check"] = time.time()
                        entry["response_ms"] = round(elapsed_ms, 1)
                        entry["consecutive_failures"] = 0
                        if elapsed_ms > RE_TURBULENT:
                            entry["status"] = "degraded"
                        else:
                            entry["status"] = "healthy"
                        _service_health[port] = entry
                    trit = 1 if entry["status"] == "healthy" else 0
                    _health_record(name, entry["status"], elapsed_ms)
                    _tripple_ripple_report(name, trit, round(elapsed_ms, 1))
                    return {"port": port, "name": name, "status": entry["status"],
                            "trit": trit, "response_ms": round(elapsed_ms, 1),
                            "consecutive_failures": 0}
            except Exception:
                pass  # Fall through to TCP probe

            # -- Final fallback: TCP connect probe --
            alive, tcp_ms = _tcp_probe(port, 1.0)
            elapsed_ms = (time.time() - t0) * 1000
            with _health_lock:
                entry = _service_health.get(port, {
                    "status": "healthy", "consecutive_failures": 0,
                    "last_check": 0, "last_recovery": 0, "response_ms": 0.0,
                })
                entry["last_check"] = time.time()
                entry["response_ms"] = round(elapsed_ms, 1)
                if alive:
                    # Port open but no HTTP -- degraded, not dead
                    entry["consecutive_failures"] = 0
                    entry["status"] = "degraded"
                else:
                    # Truly unreachable
                    entry["consecutive_failures"] += 1
                    if entry["consecutive_failures"] >= MAX_CONSECUTIVE_FAILURES:
                        entry["status"] = "dead"
                    else:
                        entry["status"] = "degraded"
                _service_health[port] = entry
            trit = 0 if entry["status"] == "degraded" else -1
            _health_record(name, entry["status"], elapsed_ms)
            _tripple_ripple_report(name, trit, round(elapsed_ms, 1))
            return {"port": port, "name": name, "status": entry["status"],
                    "trit": trit, "response_ms": round(elapsed_ms, 1),
                    "consecutive_failures": entry["consecutive_failures"]}

    # Patch the function
    orch._check_service_health = _check_service_health

    # Also patch _check_all_services to ensure it calls our new function
    import concurrent.futures as _cf
    KNOWN_SERVICES = orch.KNOWN_SERVICES
    H7 = orch.H7
    _bt_string = orch._bt_string
    _merge_ternary = orch._merge_ternary

    def _check_all_services():
        """Check all known services in parallel. Uses patched _check_service_health."""
        results = []
        with _cf.ThreadPoolExecutor(max_workers=H7) as pool:
            futures = {pool.submit(_check_service_health, port, name): (port, name)
                       for port, name in KNOWN_SERVICES.items()}
            for f in _cf.as_completed(futures):
                try:
                    results.append(f.result())
                except Exception:
                    port, name = futures[f]
                    results.append({"port": port, "name": name, "status": "dead",
                                    "trit": -1, "response_ms": 0, "consecutive_failures": 99})
        results.sort(key=lambda r: r["port"])
        healthy = sum(1 for r in results if r["trit"] == 1)
        degraded = sum(1 for r in results if r["trit"] == 0)
        dead = sum(1 for r in results if r["trit"] == -1)
        trits = [r["trit"] for r in results]
        overall_trit = _merge_ternary(trits) if results else -1
        return {
            "total": len(results), "healthy": healthy, "degraded": degraded, "dead": dead,
            "overall_trit": overall_trit, "bt": _bt_string(trits), "services": results,
        }

    orch._check_all_services = _check_all_services

    # Patch route_services_health3 to use _check_all_services instead of inline loop
    # (the inline loop only checked 21 services and only /health)
    from flask import jsonify as _jsonify

    def route_services_health3():
        """Ternary system health: delegates to _check_all_services() for accurate probing."""
        result = _check_all_services()
        return _jsonify({
            "services": result["services"], "bt": result["bt"],
            "overall_trit": result["overall_trit"],
            "healthy": result["healthy"], "degraded": result["degraded"],
            "down": result["dead"], "total": result["total"],
        })

    orch.route_services_health3 = route_services_health3

    # Reset consecutive_failures for all services so the fix takes effect immediately
    with _health_lock:
        for port in list(_service_health.keys()):
            _service_health[port]["consecutive_failures"] = 0
            _service_health[port]["status"] = "healthy"  # Will be re-evaluated on next check

    print(f"[health_patch] APPLIED: patched _check_service_health + route_services_health3")
    print(f"[health_patch]   HEALTH_TIMEOUT: {orch.HEALTH_TIMEOUT}s")
    print(f"[health_patch]   TCP_ONLY_SERVICES: {orch._TCP_ONLY_SERVICES}")
    print(f"[health_patch]   Reset {len(_service_health)} service states")
    return True


# Auto-apply on import
if __name__ != "__main__":
    apply_patch()
else:
    # Manual apply for testing
    apply_patch()
