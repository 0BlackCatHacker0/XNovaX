# NovaX Critical Rules — NEVER VIOLATE
## Learned from painful experience across 20+ sessions

1. NEVER use `start` command from bridge — crashes bridge every time
2. NEVER open separate PowerShell windows — one unified script only
3. OpenClaw handles process launching — without it bridge crashes on subprocess
4. nova_bridge_v3.py is NOT the real server — just bootstrap
5. REAL entry point: C:\NovaX\novax\main.py — boots brain:9990, ws:9998, bridge:9999
6. Python venv: C:\NovaX\ai_env\Scripts\python.exe (always use this)
7. PYTHONUTF8=1 — always set for Python processes
8. Static UI files: C:\ProgramData\NovaX\app\shell\static\
9. Base64 packet protocol for large files (2500 char chunks)
10. Nova Relay on :9877 for fast file operations
11. Always verify file sizes after transfer
12. Kill zombie processes before starting services
13. Check ports with netstat before binding
14. Never fake results — real execution or real errors
15. User is physically disabled — minimize typing, maximize automation
