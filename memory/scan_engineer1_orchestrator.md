# ENGINEER-1: Orchestrator Audit Report
## C:\NovaX\core\orchestrator.py (5806 lines)

### CRITICAL (10)
1. **line:163** CORS wildcard `origins="*"` — any website can call all APIs
2. **line:5806** Server binds `0.0.0.0` — exposed to entire network
3. **line:5806** `allow_unsafe_werkzeug=True` in production
4. **line:659-674** RCE via `/api/run` and `/api/exec` — no auth, no validation
5. **line:677-682** Duplicate RCE route `/api/execute`
6. **line:504-510** Think endpoint `executor` model passes raw text as shell cmd
7. **line:705-720** Filesystem write/delete with no path validation
8. **line:1316-1326** Wallet export via unauthenticated GET
9. **line:997** Path traversal in profile import (`f.filename` unvalidated)
10. **line:1824-1844** NovaLang code execution via subprocess, no sandbox

### HIGH (7)
1. **line:1904+1916** Duplicate BOOT_ORDER entry for nova-tbuffer (different interpreters)
2. **line:1429-1433** Voice command calls think() as function but it's a Flask route
3. **line:219-250** Rate limiter bypassable + memory leak (no IP expiry)
4. **line:293-294** Race condition in health request counter (read outside lock)
5. **line:2147-2156** Command injection in software check
6. **line:3510-3511** Port conflict: nova-cli and AppControl both on 9887
7. **line:164** SocketIO threading async_mode not production-safe

### MEDIUM (12)
- External HTTP calls (npm/PyPI) in hot path of every AI query
- Three nearly identical proxy helper functions
- Boot order iterates 40+ services sequentially
- PowerShell spawned per service during boot (N+1)
- Health3 makes 21 sequential HTTP requests
- App discovery scans filesystem every request
- sys.path manipulation at module level
- Redundant re-imports in handlers
- sys.path.insert inside route handler (grows per request)
- Inconsistent HTTP client (requests vs urllib)
- Unified logs reads entire files into memory
- Comment/code port mismatches

### LOW (11)
- Stale docstrings (claims 26 endpoints, has 470+)
- FALSE_ naming convention confusing
- Duplicate section numbers in comments
- Module-level imports inside handlers
- Global mutable dicts without locks

### TOP 3 FIXES
1. Bind to 127.0.0.1 (line 5806)
2. Add auth middleware (@app.before_request)
3. Remove/gate RCE routes (/api/run, /api/exec, /api/execute)
