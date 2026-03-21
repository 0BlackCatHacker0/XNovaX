# SECURITY: Full Codebase Audit
## Date: 2026-03-05 | Total: 148+ findings

### CRITICAL (14)
1. ALL 40+ services bind 0.0.0.0 (except nova_tlight.py)
2. ALL 45+ files set CORS: * (any website can call any API)
3. ZERO authentication on ANY endpoint
4. exec_server.py: POST /exec runs arbitrary PowerShell, no auth
5. novax_core_v2.py: POST /api/exec runs exec(code), no auth
6. nova_bridge_v3.py: POST /api/terminal runs shell=True, no auth
7. core/server.py: User text → subprocess.run(text, shell=True)
8. ws_server.py: WebSocket "cmd" runs shell commands
9. novax_server.py: /api/env dumps ALL env vars (API keys exposed)
10. novax_core_v2.py: /api/env POST sets ANY env var
11. orchestrator.py: /api/fs/write + /api/fs/delete no path validation
12. nova_bridge_v3.py: /api/files/read + /api/files/write no path validation
13. novax_core_v2.py: /api/fs/read + /api/fs/write no path validation
14. 42 instances of subprocess shell=True with user input

### KEY PATTERNS
- 40+ services bind 0.0.0.0
- 70+ CORS: * instances across 45+ files
- 42 shell=True subprocess calls
- 12 eval()/exec() instances (8 file-based, 4 HTTP-accessible)
- 0 services implement authentication

### ATTACK SCENARIO
Any website user visits can: fetch("http://localhost:9877/exec", {body: {command: "whoami"}})
→ Browser allows (CORS *), server executes (no auth), exposed (0.0.0.0)

### PRIORITY REMEDIATION
1. DAY 1: Bind ALL to 127.0.0.1 (blocks network attacks)
2. DAY 2: Add token auth (generate on boot, store in .session_token)
3. WEEK 1: CORS → http://localhost:9999 only
4. WEEK 1: tsafe_path() on ALL file endpoints
5. WEEK 1: Remove /api/env, /api/exec (novax_core_v2.py)
6. WEEK 2: Audit all shell=True, switch to list-form subprocess

### POSITIVE (3 services with good security)
- nova_tlight.py: 127.0.0.1, tsafe_path(), CORS locked
- nova_tools.py: _safe_path() with allowed roots
- nova_cloud_router.py: _safe_path() with realpath + _SAFE_ROOTS
