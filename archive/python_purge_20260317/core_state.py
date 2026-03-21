# state.py — System state context builder for NovaX
# Builds rich context snapshots for AI prompt injection.
# Orchestrator uses: format_for_prompt(), full_system_context()

import time
import os
import platform
import logging

log = logging.getLogger("NovaX.State")

_NOVA_ROOT = r"C:\NovaX"
_CLOUD_CFG = os.path.join(_NOVA_ROOT, "cloud_config.json")

# Cache to avoid re-probing every call (refreshes every 30s)
_cache = {"context": None, "ts": 0, "ttl": 120}


def _get_cloud_providers():
    """Check which AI providers have keys configured."""
    providers = {}
    try:
        import json
        if os.path.isfile(_CLOUD_CFG):
            with open(_CLOUD_CFG, encoding="utf-8") as f:
                cfg = json.load(f)
            for name, val in cfg.items():
                if isinstance(val, dict) and val.get("key"):
                    key = val["key"]
                    providers[name] = {
                        "configured": True,
                        "key_preview": key[:6] + "..." if len(key) > 6 else "***",
                    }
    except Exception as e:
        log.debug(f"Cloud config read error: {e}")

    # Also check env vars
    for env_key, provider in [
        ("OPENAI_API_KEY", "openai"),
        ("ANTHROPIC_API_KEY", "anthropic"),
        ("OPENROUTER_API_KEY", "openrouter"),
    ]:
        val = os.environ.get(env_key, "")
        if val and provider not in providers:
            providers[provider] = {
                "configured": True,
                "key_preview": val[:6] + "..." if len(val) > 6 else "***",
                "source": "env",
            }

    return providers


def _get_active_services():
    """Parallel probe of known service ports — all 20 checked at once."""
    import urllib.request
    import concurrent.futures

    ports = {
        "orchestrator": 9999, "cloud_router": 9878, "exec_server": 9877,
        "hivemind": 9881, "ternary_server": 9900, "cortex": 9860,
        "vault": 9870, "nova_core": 9890, "browser_bridge": 9850,
        "chess_engine": 9901, "go_engine": 9902, "novalang_debugger": 9903,
        "route_validator": 9904, "tzip_service": 9905, "treynolds_service": 9906,
        "tcompose_service": 9907, "tframe_service": 9908, "tblock_service": 9909,
        "tharmonic_service": 9910, "tpurity_service": 9911,
    }

    def _probe(name_port):
        name, port = name_port
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{port}/health", method="GET")
            with urllib.request.urlopen(req, timeout=0.5) as resp:
                return (name, "up" if resp.status < 400 else "error")
        except Exception:
            return (name, "down")

    services = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as ex:
        for name, status in ex.map(_probe, ports.items()):
            services[name] = status
    return services


def _get_system_info():
    """Gather basic system info."""
    try:
        import psutil
        mem = psutil.virtual_memory()
        cpu = psutil.cpu_percent(interval=0.1)
        return {
            "os": platform.system(),
            "os_version": platform.version()[:50],
            "python": platform.python_version(),
            "cpu_percent": cpu,
            "memory_total_gb": round(mem.total / (1024**3), 1),
            "memory_used_percent": mem.percent,
            "hostname": platform.node(),
        }
    except ImportError:
        return {
            "os": platform.system(),
            "os_version": platform.version()[:50],
            "python": platform.python_version(),
            "hostname": platform.node(),
        }


def _get_active_tasks():
    """Get current task state from task graph."""
    try:
        from core import tasks
        active = tasks.get_active()
        if active and active[0]:
            tid, task = active
            return {
                "active_task": task.get("name", ""),
                "step": task.get("current", 0),
                "total_steps": len(task.get("steps", [])),
                "status": task.get("status", ""),
            }
    except Exception:
        pass
    return {"active_task": None}


def _get_recent_events(limit=5):
    """Get recent events from the event bus."""
    try:
        from core.event_bus import bus
        return bus.recent(limit=limit)
    except Exception:
        return []


def full_system_context(**kwargs):
    """
    Build a comprehensive system context snapshot.
    Returns a rich dict with services, providers, system info, tasks, and events.
    Caches for _cache['ttl'] seconds to avoid excessive probing.
    """
    now = time.time()
    if _cache["context"] and (now - _cache["ts"]) < _cache["ttl"]:
        return _cache["context"]

    ctx = {
        "timestamp": now,
        "nova_root": _NOVA_ROOT,
        "profile": os.environ.get("NOVAX_PROFILE", "default"),
        "mode": os.environ.get("NOVAX_MODE", "standard"),
        "system": _get_system_info(),
        "services": _get_active_services(),
        "providers": _get_cloud_providers(),
        "tasks": _get_active_tasks(),
        "recent_events": _get_recent_events(5),
    }

    # Count service states
    svc = ctx["services"]
    ctx["service_summary"] = {
        "total": len(svc),
        "up": sum(1 for v in svc.values() if v == "up"),
        "down": sum(1 for v in svc.values() if v == "down"),
    }

    _cache["context"] = ctx
    _cache["ts"] = now
    return ctx


def format_for_prompt(**kwargs):
    """
    Format system state as a concise text block for AI prompt injection.
    This gets prepended to every AI query so the model knows the system state.
    """
    ctx = full_system_context()

    lines = ["[NovaX System State]"]

    # System
    sys_info = ctx.get("system", {})
    lines.append(f"OS: {sys_info.get('os', '?')} | Python: {sys_info.get('python', '?')}")
    if "cpu_percent" in sys_info:
        lines.append(f"CPU: {sys_info['cpu_percent']}% | RAM: {sys_info.get('memory_used_percent', '?')}%")

    # Services — list EVERY service by name, port, and status
    svc = ctx.get("services", {})
    summary = ctx.get("service_summary", {})
    lines.append(f"Services: {summary.get('up', 0)}/{summary.get('total', 0)} up")

    # Known port map for display
    _port_map = {
        "orchestrator": 9999, "cloud_router": 9878, "exec_server": 9877,
        "hivemind": 9881, "ternary_server": 9900, "cortex": 9860,
        "vault": 9870, "nova_core": 9890, "browser_bridge": 9850,
        "chess_engine": 9901, "go_engine": 9902, "novalang_debugger": 9903,
        "route_validator": 9904, "tzip_service": 9905, "treynolds_service": 9906,
        "tcompose_service": 9907, "tframe_service": 9908, "tblock_service": 9909,
        "tharmonic_service": 9910, "tpurity_service": 9911,
    }

    up_list = []
    down_list = []
    for name, status in svc.items():
        port = _port_map.get(name, "?")
        if status == "up":
            up_list.append(f"{name} (:{port})")
        else:
            down_list.append(f"{name} (:{port})")

    if up_list:
        lines.append(f"UP: {', '.join(up_list)}")
    if down_list:
        lines.append(f"DOWN: {', '.join(down_list)}")

    # AI Providers
    providers = ctx.get("providers", {})
    if providers:
        lines.append(f"AI providers: {', '.join(sorted(providers.keys()))}")

    # Active task
    tasks = ctx.get("tasks", {})
    if tasks.get("active_task"):
        lines.append(f"Active task: {tasks['active_task']} (step {tasks.get('step', 0)}/{tasks.get('total_steps', 0)})")

    # Profile/Mode
    if ctx.get("profile") != "default" or ctx.get("mode") != "standard":
        lines.append(f"Profile: {ctx.get('profile')} | Mode: {ctx.get('mode')}")

    return "\n".join(lines)


def invalidate_cache():
    """Force the next call to rebuild context."""
    _cache["context"] = None
    _cache["ts"] = 0
