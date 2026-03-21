# vcc.py — VCC: Verification & Compliance Checker
# Actually probes service /health endpoints to verify they're alive.
# Orchestrator calls: get_vcc_status(), vcc_summary(), verify_component()

import time
import urllib.request
import json
import threading

_LAST_CHECK = {}  # {name: {status, time, port, response_ms}}
_CHECK_INTERVAL = 30  # Minimum seconds between re-checks


def _probe_service(name, port, timeout=3):
    """Probe a service's /health endpoint. Returns result dict."""
    start = time.time()
    try:
        url = f"http://127.0.0.1:{port}/health"
        r = urllib.request.urlopen(url, timeout=timeout)
        data = r.read().decode("utf-8", errors="replace")[:500]
        elapsed_ms = round((time.time() - start) * 1000)
        try:
            body = json.loads(data)
        except Exception:
            body = {"raw": data}
        return {
            "component": name,
            "port": port,
            "verified": True,
            "status": "healthy",
            "response_ms": elapsed_ms,
            "health_data": body,
            "checked_at": time.time(),
        }
    except Exception as e:
        elapsed_ms = round((time.time() - start) * 1000)
        return {
            "component": name,
            "port": port,
            "verified": False,
            "status": "unreachable",
            "response_ms": elapsed_ms,
            "error": str(e)[:200],
            "checked_at": time.time(),
        }


def verify_component(name, port=None, **kwargs):
    """Verify a single component by probing its health endpoint."""
    if not port:
        # Try to find port from known services
        port = _KNOWN_PORTS.get(name, kwargs.get("port"))
    if not port:
        return {"component": name, "verified": False, "status": "no_port", "error": "Port unknown"}

    result = _probe_service(name, port)
    _LAST_CHECK[name] = result
    return result


def get_vcc_status():
    """Get overall VCC verification status."""
    total = len(_LAST_CHECK)
    verified = sum(1 for r in _LAST_CHECK.values() if r.get("verified"))
    failed = total - verified
    return {
        "status": "ok" if failed == 0 and total > 0 else ("degraded" if verified > 0 else "unknown"),
        "verified": verified,
        "failed": failed,
        "total": total,
        "last_check": max((r.get("checked_at", 0) for r in _LAST_CHECK.values()), default=0),
    }


def vcc_summary():
    """Get detailed VCC summary with all component results."""
    components = list(_LAST_CHECK.values())
    return {
        "components": components,
        "total": len(components),
        "verified": sum(1 for c in components if c.get("verified")),
        "failed": sum(1 for c in components if not c.get("verified")),
    }


def verify_all(services=None):
    """Verify all known services in parallel. Returns summary."""
    targets = services or _KNOWN_PORTS
    results = []

    def _check(name, port):
        r = _probe_service(name, port)
        _LAST_CHECK[name] = r
        results.append(r)

    threads = []
    for name, port in targets.items():
        t = threading.Thread(target=_check, args=(name, port), daemon=True)
        threads.append(t)
        t.start()

    for t in threads:
        t.join(timeout=5)

    verified = sum(1 for r in results if r.get("verified"))
    return {
        "total": len(results),
        "verified": verified,
        "failed": len(results) - verified,
        "results": results,
    }


# Known service ports for auto-verification
_KNOWN_PORTS = {
    "orchestrator": 9999,
    "cloud_router": 9878,
    "exec_server": 9877,
    "hivemind": 9881,
    "ternary_server": 9900,
    "ternary_tools": 9901,
    "nova_tools": 9902,
    "nova_prime": 9903,
    "nova_nexus": 9904,
    "tbus": 9905,
    "tmetrics": 9906,
    "tlog": 9907,
    "tconfig": 9908,
    "tmapper": 9909,
    "tsniffer": 9910,
    "thealth": 9911,
    "cortex": 9860,
    "mcp_server": 9870,
    "sentinel": 9865,
    "vault": 9850,
    "model_registry": 9882,
}
