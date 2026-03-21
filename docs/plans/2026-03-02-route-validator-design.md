# Route Validator — Unified Security Sublayer

**Date:** 2026-03-02
**Status:** Approved
**Approach:** C — Unified Security Sublayer (shared module, many consumers)

## Problem

All NovaX monitoring systems (VCC, DebugEngine, Watchdog, Health Monitor) operate at the PORT level — "is port 9999 alive?" None inspect Flask route registration. A broken route (`/api/pm/status` returning 404 from catch-all) is invisible to every monitoring system because the orchestrator process is alive and `/health` returns 200.

## Solution

A thin `route_validator.py` module in `C:\NovaX\core\` that both the DebugEngine AND VCC call into. One validator, many consumers.

## Architecture

```
route_validator.py (shared sublayer)
    |
    +-- VCC calls it:        port_open() -> VERIFIED, routes_valid() -> TRUSTED
    +-- DebugEngine calls it: ROUTE_REGISTERED + ROUTE_CALLABLE proof types
    +-- Watchdog calls it:    after restart, verify routes before declaring "fixed"
    +-- TShell triggers it:   file fingerprint change on orchestrator.py -> revalidate
    +-- Desktop UI reads it:  /api/routes/verify endpoint shows route health
```

## Core Module: route_validator.py

### Boot-time catalog
- Introspects `app.url_map` to build a route manifest
- Every `/api/*` route cataloged with methods, function name, tier

### Continuous validation (background thread)
- **Tier 1 — Smoke (every 30s):** OPTIONS request to every `/api/*` route. 404 = DEAD, anything else = ALIVE.
- **Tier 2 — Deep (every 5 min):** GET critical routes, validate response contains expected keys.

### Route Manifest Schema
```json
{
  "generated_at": "timestamp",
  "orchestrator_pid": 12345,
  "source_hash": "sha256 of orchestrator.py",
  "routes": {
    "/api/pm/status": {
      "methods": ["GET"],
      "function": "route_pm_status",
      "tier": "critical",
      "expected_keys": ["processes", "count"],
      "last_check": "timestamp",
      "status": "ALIVE|DEAD|DEGRADED",
      "consecutive_failures": 0
    }
  },
  "summary": {
    "total": 145,
    "alive": 143,
    "dead": 1,
    "degraded": 1
  }
}
```

### Exposed functions
- `build_manifest(flask_app)` — Introspect Flask, return manifest
- `smoke_test_all()` — Tier 1 all routes
- `deep_validate_critical()` — Tier 2 critical routes
- `get_route_status(path)` — One route's status
- `get_summary()` — Overall health
- `start_continuous(interval=30)` — Background thread
- `stop_continuous()` — Stop thread

## Integration Points

### VCC (vcc.py)
- `get_vcc_status()` upgraded: service reaches TRUSTED only if port is open AND routes validate
- New field: `routes_verified: true/false`, `routes_dead: [list]`

### DebugEngine (novax/debugger/engine.py)
- New proof types: ROUTE_REGISTERED, ROUTE_CALLABLE
- Orchestrator contract includes route verification

### Watchdog (novax_watchdog.py)
- After restarting a service, call route validator to confirm fix worked

### Orchestrator (orchestrator.py)
- Boot: call `build_manifest(app)` after all routes registered
- Boot: call `start_continuous(30)` to begin live validation
- Endpoints: `/api/routes/verify`, `/api/routes/manifest`, `/api/routes/status/<path>`

### Desktop UI (nova_desktop.html)
- Debug panel shows route health alongside process list
- Dead routes highlighted in red with last-known-good timestamp

## Critical Routes (Tier 2 deep validation)
- /health — expected keys: status, version, uptime
- /api/status — expected keys: version, services
- /api/vcc — expected keys: orchestrator, hivemind
- /api/pm/status — expected keys: processes, count
- /api/watch/status — expected keys: running, uptime
- /api/hive/status — expected keys: model_count
- /api/tshell/status — expected keys: running, enabled
