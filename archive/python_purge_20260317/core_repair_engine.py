# repair_engine.py — Self-healing engine for NovaX
# Diagnoses failing components, logs failures, uses AI for root-cause analysis.
# Orchestrator uses: diagnose(), diagnose_with_ai(), recent_failures(), get_repair_stats()

import time
import os
import subprocess
import threading
import logging
from collections import deque

log = logging.getLogger("NovaX.Repair")

# ── Known services and their health endpoints ─────────────────────
_KNOWN_SERVICES = {
    "orchestrator":    {"port": 9999, "path": "/health"},
    "cloud_router":    {"port": 9878, "path": "/health"},
    "exec_server":     {"port": 9877, "path": "/health"},
    "hivemind":        {"port": 9881, "path": "/health"},
    "ternary_server":  {"port": 9900, "path": "/health"},
    "cortex":          {"port": 9860, "path": "/health"},
    "vault":           {"port": 9870, "path": "/health"},
    "nova_core":       {"port": 9890, "path": "/health"},
    "browser_bridge":  {"port": 9850, "path": "/health"},
    "uia_bridge":      {"port": 9840, "path": "/health"},
    "vision":          {"port": 9830, "path": "/health"},
    "nova_sync":       {"port": 9820, "path": "/health"},
    "nova_tts":        {"port": 9810, "path": "/health"},
    "gamepad":         {"port": 9800, "path": "/health"},
    "nova_monitor":    {"port": 9801, "path": "/health"},
    "voice_router":    {"port": 9905, "path": "/health"},
    "skill_store":     {"port": 9906, "path": "/health"},
    "context_engine":  {"port": 9907, "path": "/health"},
    "memory_index":    {"port": 9908, "path": "/health"},
    "log_collector":   {"port": 9909, "path": "/health"},
    "metrics":         {"port": 9910, "path": "/health"},
    "code_runner":     {"port": 9911, "path": "/health"},
}

# ── Failure log (bounded) ─────────────────────────────────────────
_failure_log = deque(maxlen=500)
_repair_log = deque(maxlen=200)
_stats = {"total_diagnoses": 0, "auto_fixed": 0, "failed_repairs": 0}
_lock = threading.Lock()


def _probe_health(name, info, timeout=4):
    """HTTP probe a service's /health endpoint. Returns (ok, detail)."""
    import urllib.request
    import urllib.error
    url = f"http://127.0.0.1:{info['port']}{info['path']}"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read(2048).decode("utf-8", errors="replace")
            return (True, {"status_code": resp.status, "body": body[:500]})
    except urllib.error.HTTPError as e:
        return (False, {"error": f"HTTP {e.code}", "reason": str(e.reason)[:200]})
    except urllib.error.URLError as e:
        return (False, {"error": "unreachable", "reason": str(e.reason)[:200]})
    except Exception as e:
        return (False, {"error": type(e).__name__, "reason": str(e)[:200]})


def diagnose(component=None, context=None, **kwargs):
    """
    Diagnose a specific component or all known services.
    Returns: {"component": str|"all", "status": str, "issues": list, "healthy": list}
    """
    _stats["total_diagnoses"] += 1
    issues = []
    healthy = []

    targets = {}
    if component and component in _KNOWN_SERVICES:
        targets[component] = _KNOWN_SERVICES[component]
    elif component:
        # Unknown component — try as a port number
        try:
            port = int(component)
            targets[f"port_{port}"] = {"port": port, "path": "/health"}
        except (ValueError, TypeError):
            return {"component": component, "status": "unknown",
                    "issues": [{"error": f"Unknown component: {component}"}], "healthy": []}
    else:
        targets = _KNOWN_SERVICES

    for name, info in targets.items():
        ok, detail = _probe_health(name, info)
        if ok:
            healthy.append({"name": name, "port": info["port"], "status": "up"})
        else:
            issue = {"name": name, "port": info["port"], "status": "down", **detail}
            issues.append(issue)
            with _lock:
                _failure_log.append({
                    "component": name, "port": info["port"],
                    "error": detail.get("error", "unknown"),
                    "time": time.time(),
                })

    status = "healthy" if not issues else ("degraded" if healthy else "critical")
    return {
        "component": component or "all",
        "status": status,
        "issues": issues,
        "healthy": healthy,
        "total_checked": len(targets),
    }


def diagnose_with_ai(component=None, error=None, context=None, **kwargs):
    """
    Use HiveMind AI to diagnose a component failure.
    Falls back to rule-based suggestions if AI is unavailable.
    """
    # Gather context
    diag = diagnose(component) if component else {"issues": []}
    issues_text = "\n".join(
        f"- {i['name']}: {i.get('error', 'unknown')} ({i.get('reason', '')})"
        for i in diag.get("issues", [])
    ) or "No issues detected via probing."

    error_text = str(error)[:500] if error else "No specific error provided."

    prompt = (
        f"NovaX repair engine diagnosis request.\n"
        f"Component: {component or 'general'}\n"
        f"Error: {error_text}\n"
        f"Probe results:\n{issues_text}\n\n"
        f"Provide: 1) Root cause analysis, 2) Suggested fixes (max 3), "
        f"3) Whether auto-restart is safe."
    )

    # Try HiveMind
    ai_result = None
    try:
        from core.hive_mind import hive
        if hive:
            ai_result = hive.fan_out(prompt, max_models=1, timeout=15)
    except Exception as e:
        log.debug(f"AI diagnosis unavailable: {e}")

    if ai_result and ai_result.get("results"):
        best = ai_result["results"][0]
        diagnosis = best.get("text", "")[:2000]
    else:
        # Rule-based fallback
        diagnosis = _rule_based_diagnosis(component, error, diag)

    suggestions = _extract_suggestions(diagnosis, component, diag)

    return {
        "component": component or "general",
        "diagnosis": diagnosis,
        "suggestions": suggestions,
        "source": "ai" if ai_result else "rules",
        "issues_found": len(diag.get("issues", [])),
    }


def _rule_based_diagnosis(component, error, diag):
    """Rule-based diagnosis when AI is unavailable."""
    issues = diag.get("issues", [])
    if not issues and not error:
        return "No issues detected. All probed endpoints are responding."

    lines = []
    for issue in issues:
        name = issue.get("name", "unknown")
        err = issue.get("error", "unknown")
        reason = issue.get("reason", "")
        if "unreachable" in err.lower() or "connection refused" in reason.lower():
            lines.append(f"{name}: Service not running or port blocked. Try restarting.")
        elif "HTTP" in err:
            lines.append(f"{name}: Service responding with error ({err}). Check logs.")
        elif "timeout" in err.lower():
            lines.append(f"{name}: Service too slow. Possible resource exhaustion.")
        else:
            lines.append(f"{name}: {err} — {reason}")

    if error:
        error_str = str(error).lower()
        if "import" in error_str:
            lines.append("Import error detected. Check dependencies and Python path.")
        elif "port" in error_str or "address" in error_str:
            lines.append("Port conflict detected. Check for zombie processes.")
        elif "memory" in error_str:
            lines.append("Memory issue detected. Consider restarting heavy services.")

    return "\n".join(lines) if lines else "Unable to determine specific issue."


def _extract_suggestions(diagnosis, component, diag):
    """Extract actionable suggestions from diagnosis text."""
    suggestions = []
    diag_lower = diagnosis.lower()

    if "restart" in diag_lower or "not running" in diag_lower:
        suggestions.append({
            "action": "restart_service",
            "target": component or "affected_services",
            "risk": "low",
            "description": "Restart the failing service",
        })

    if "port" in diag_lower or "address" in diag_lower:
        suggestions.append({
            "action": "clear_port",
            "target": component,
            "risk": "medium",
            "description": "Kill processes on the conflicting port",
        })

    if "memory" in diag_lower or "resource" in diag_lower:
        suggestions.append({
            "action": "reduce_load",
            "target": "system",
            "risk": "low",
            "description": "Reduce memory usage by stopping non-essential services",
        })

    if "import" in diag_lower or "module" in diag_lower:
        suggestions.append({
            "action": "check_dependencies",
            "target": component,
            "risk": "low",
            "description": "Verify Python path and installed packages",
        })

    if not suggestions:
        suggestions.append({
            "action": "manual_review",
            "target": component or "system",
            "risk": "low",
            "description": "Review service logs for detailed error information",
        })

    return suggestions[:5]


def attempt_repair(component, action="restart_service", **kwargs):
    """
    Attempt an automatic repair action on a component.
    Returns: {"success": bool, "action": str, "detail": str}
    """
    info = _KNOWN_SERVICES.get(component)
    if not info:
        return {"success": False, "action": action,
                "detail": f"Unknown component: {component}"}

    result = {"action": action, "component": component, "time": time.time()}

    if action == "restart_service":
        # Try to restart via orchestrator API
        try:
            import urllib.request
            import json
            payload = json.dumps({"service": component}).encode()
            req = urllib.request.Request(
                "http://127.0.0.1:9999/api/services/boot",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                body = resp.read(4096).decode("utf-8", errors="replace")
                result["success"] = resp.status < 400
                result["detail"] = body[:500]
        except Exception as e:
            result["success"] = False
            result["detail"] = str(e)[:300]

    elif action == "clear_port":
        port = info["port"]
        try:
            # Find and kill process on port (Windows)
            out = subprocess.run(
                ["netstat", "-ano", "-p", "TCP"],
                capture_output=True, text=True, timeout=10,
                creationflags=0x08000000
            )
            pids = set()
            for line in out.stdout.splitlines():
                if f":{port}" in line and "LISTENING" in line:
                    parts = line.split()
                    if parts:
                        try:
                            pids.add(int(parts[-1]))
                        except ValueError:
                            pass
            for pid in pids:
                subprocess.run(
                    ["taskkill", "/F", "/PID", str(pid)],
                    capture_output=True, timeout=10,
                    creationflags=0x08000000
                )
            result["success"] = True
            result["detail"] = f"Cleared {len(pids)} process(es) on port {port}"
        except Exception as e:
            result["success"] = False
            result["detail"] = str(e)[:300]
    else:
        result["success"] = False
        result["detail"] = f"Unknown repair action: {action}"

    # Log the repair attempt
    with _lock:
        _repair_log.append(result)
        if result.get("success"):
            _stats["auto_fixed"] += 1
        else:
            _stats["failed_repairs"] += 1

    return result


def recent_failures(limit=20, **kwargs):
    """Get recent failure events from the log."""
    with _lock:
        entries = list(_failure_log)
    return entries[-limit:]


def get_repair_stats(**kwargs):
    """Get repair engine statistics."""
    with _lock:
        return {
            "total_diagnoses": _stats["total_diagnoses"],
            "auto_fixed": _stats["auto_fixed"],
            "failed_repairs": _stats["failed_repairs"],
            "pending": len([f for f in _failure_log
                           if f.get("time", 0) > time.time() - 300]),
            "failure_log_size": len(_failure_log),
            "repair_log_size": len(_repair_log),
        }


def get_repair_history(limit=50, **kwargs):
    """Get history of repair attempts."""
    with _lock:
        entries = list(_repair_log)
    return entries[-limit:]
