"""Add missing services to tool_registry.json: TTimeout, TMapper, TDebug, TPacman, TSpin, TReplay."""
import json

with open(r"C:\NovaX\tool_registry.json", "r") as f:
    reg = json.load(f)

services = reg["services"]

# Fix 9970: was labeled treplay, should be tspin (VCC confirms tspin owns 9970)
# Find and fix the service on port 9970
for key, val in list(services.items()):
    if val.get("port") == 9970:
        val["description"] = "TSpin v2.0 - Ternary Process Spinner. Manages all Python processes. MAX_PYTHON=243 (3^5). Protected list prevents killing NovaLang hosts. Triad integration."
        print(f"  FIXED :{key} (port 9970) -> tspin description")
        break

# Add TSpin (if key doesn't exist yet, the loop above fixed the existing one)

# Add TTimeout (:9995)
services["ttimeout"] = {
    "port": 9995,
    "description": "TTimeout v1.0 - Fleet Timeout Hardening Engine. Audit all services for timeout vulnerabilities. Stress-test individual services.",
    "routes": {
        "health": {"method": "GET", "path": "/health", "desc": "Health check with audit/test counts"},
        "audit": {"method": "GET", "path": "/timeout/audit", "desc": "Scan all services for timeout vulnerabilities"},
        "status": {"method": "GET", "path": "/timeout/status", "desc": "Last audit results summary"},
        "test": {"method": "POST", "path": "/timeout/test", "desc": "Stress-test a specific service (body: {port, duration})"}
    }
}
print("  ADDED ttimeout (:9995)")

# Add TMapper (:9994)
services["tmapper"] = {
    "port": 9994,
    "description": "TMapper v1.0 - Mapping Debugger. Parallel port scanner + VCC/registry differ + auto-patcher. Never manually debug port mismatches again.",
    "routes": {
        "health": {"method": "GET", "path": "/health", "desc": "Health check with scan/patch counts"},
        "scan": {"method": "GET", "path": "/mapper/scan", "desc": "Full parallel port scan (9877-9999)"},
        "diff": {"method": "GET", "path": "/mapper/diff", "desc": "Compare live fleet vs VCC+registry"},
        "status": {"method": "GET", "path": "/mapper/status", "desc": "Last scan/diff results summary"},
        "patch": {"method": "POST", "path": "/mapper/patch", "desc": "Auto-patch VCC and tool_registry from live scan"}
    }
}
print("  ADDED tmapper (:9994)")

# Add TDebug (:9992)
services["tdebug"] = {
    "port": 9992,
    "description": "TDebug v1.0 - Universal Debugger. 27+ gotcha patterns, side-by-side comparison, fleet diagnostics.",
    "routes": {
        "health": {"method": "GET", "path": "/health", "desc": "Health check"},
        "stats": {"method": "GET", "path": "/stats", "desc": "Debug session statistics"},
        "diagnostics": {"method": "GET", "path": "/diagnostics", "desc": "Fleet-wide diagnostics scan"},
        "validate": {"method": "POST", "path": "/validate", "desc": "Validate NovaLang syntax (body: {code} or {file})"},
        "compare": {"method": "POST", "path": "/compare", "desc": "Side-by-side Python vs NovaLang comparison"},
        "probe": {"method": "POST", "path": "/probe", "desc": "Deep probe a running service"},
        "diagnose": {"method": "POST", "path": "/diagnose", "desc": "Full service diagnosis (syntax + health + routes)"}
    }
}
print("  ADDED tdebug (:9992)")

# Add TPacman (:9991)
services["tpacman"] = {
    "port": 9991,
    "description": "TPacman v1.0 - Python-to-Nova Converter. Eats Python services, outputs NovaLang. Batch scan for unconverted files.",
    "routes": {
        "health": {"method": "GET", "path": "/health", "desc": "Health check"},
        "stats": {"method": "GET", "path": "/stats", "desc": "Conversion statistics"},
        "analyze": {"method": "POST", "path": "/analyze", "desc": "Dry-run: analyze Python file, show what Nova output would look like"},
        "convert": {"method": "POST", "path": "/convert", "desc": "Convert Python file to .nova and write to disk"},
        "batch": {"method": "POST", "path": "/batch", "desc": "Batch scan all nova_*.py files for conversion readiness"}
    }
}
print("  ADDED tpacman (:9991)")

# Add TReplay (:9996 - reassigned from 9970 to avoid TSpin conflict)
services["treplay"] = {
    "port": 9996,
    "description": "TReplay v1.0 - Query Replay and Temporal Analysis. Replays past queries with current models to detect regressions or improvements.",
    "routes": {
        "health": {"method": "GET", "path": "/health", "desc": "Health check"},
        "replay_status": {"method": "GET", "path": "/replay/status", "desc": "Replay engine status"},
        "replay": {"method": "POST", "path": "/replay", "desc": "Replay a query against current models"},
        "compare": {"method": "POST", "path": "/replay/compare", "desc": "Compare historical vs current model responses"}
    }
}
print("  ADDED treplay (:9996 - reassigned from 9970)")

# Update meta
reg["_meta"]["total_services"] = len(services)
reg["_meta"]["generated"] = "Session 62 - patched descriptions + added TTimeout/TMapper/TDebug/TPacman/TReplay"

with open(r"C:\NovaX\tool_registry.json", "w") as f:
    json.dump(reg, f, indent=2)

print(f"\nTotal services in registry: {len(services)}")
print("Registry saved.")
