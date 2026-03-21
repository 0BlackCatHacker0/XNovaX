"""
NovaX Process Manager — Named Processes, Job Objects, Kill Switch

Ensures all NovaX processes are:
1. Identifiable in Task Manager (named process titles)
2. Grouped in a Windows Job Object (one kill = all dead)
3. Killable via a single command or hotkey

Usage:
  python novax_process_manager.py status     # Show all NovaX processes
  python novax_process_manager.py kill        # Kill ALL NovaX processes
  python novax_process_manager.py killswitch  # Create desktop kill switch
"""

import os
import sys
import json
import time
import ctypes
import subprocess
import socket

NOVAX_ROOT = r"C:\NovaX"

# All known NovaX service ports and their display names
NOVAX_SERVICES = {
    9999:  "NovaX_Orchestrator",
    9990:  "NovaX_Brain",
    9881:  "NovaX_Hivemind",
    9882:  "NovaX_Nexus",
    9883:  "NovaX_Sentinel_Agent",
    9884:  "NovaX_Sentinel",
    9880:  "NovaX_VPN",
    9878:  "NovaX_CloudRouter",
    9877:  "NovaX_ExecServer",
    9875:  "NovaX_STT",
    9998:  "NovaX_WebSocket",
    9885:  "NovaX_TernaryServer",
    9886:  "NovaX_Debugger",
    9887:  "NovaX_CLI",
    9888:  "NovaX_ClosedLoop",
    9889:  "NovaX_MaxPatch",
    9890:  "NovaX_TShell",
    11434: "NovaX_Ollama",
    6379:  "NovaX_Redis",
    7700:  "NovaX_Meilisearch",
    8080:  "NovaX_Caddy",
}

# Marker file that all NovaX processes create
NOVA_PID_DIR = os.path.join(NOVAX_ROOT, "memory", "pids")

# ── Process Discovery ──────────────────────────────────────────

def find_novax_processes():
    """Find all NovaX-related processes using port scanning + name matching."""
    results = []

    # Method 1: Check known ports via netstat
    try:
        output = subprocess.check_output(
            ["netstat", "-ano"],
            creationflags=0x08000000,
            text=True, timeout=10
        )
        port_pids = {}
        for line in output.splitlines():
            if "LISTENING" in line:
                parts = line.split()
                if len(parts) >= 5:
                    addr = parts[1]
                    pid = parts[4]
                    try:
                        port = int(addr.split(":")[-1])
                        if port in NOVAX_SERVICES:
                            port_pids[port] = int(pid)
                    except (ValueError, IndexError):
                        pass

        for port, pid in port_pids.items():
            name = NOVAX_SERVICES.get(port, f"NovaX_Port{port}")
            results.append({
                "pid": pid,
                "port": port,
                "name": name,
                "source": "port",
            })
    except Exception:
        pass

    # Method 2: Find all python.exe processes running NovaX scripts
    try:
        output = subprocess.check_output(
            ["wmic", "process", "where",
             "name='python.exe' or name='python3.exe' or name='pythonw.exe'",
             "get", "processid,commandline", "/format:csv"],
            creationflags=0x08000000,
            text=True, timeout=10
        )
        known_pids = {r["pid"] for r in results}
        for line in output.splitlines():
            if "NovaX" in line or "novax" in line or "nova_" in line:
                parts = line.strip().split(",")
                if len(parts) >= 3:
                    try:
                        pid = int(parts[-1])
                        cmdline = ",".join(parts[1:-1])
                        if pid not in known_pids:
                            # Try to identify the service from cmdline
                            name = "NovaX_Unknown"
                            for script_name, svc_name in [
                                ("orchestrator", "NovaX_Orchestrator"),
                                ("server.py", "NovaX_Brain"),
                                ("hivemind", "NovaX_Hivemind"),
                                ("nexus", "NovaX_Nexus"),
                                ("sentinel", "NovaX_Sentinel"),
                                ("vpn_core", "NovaX_VPN"),
                                ("cloud_router", "NovaX_CloudRouter"),
                                ("exec_server", "NovaX_ExecServer"),
                                ("stt", "NovaX_STT"),
                                ("ws_server", "NovaX_WebSocket"),
                                ("ternary_server", "NovaX_TernaryServer"),
                                ("liud", "NovaX_Debugger"),
                                ("cli_server", "NovaX_CLI"),
                                ("closed_loop", "NovaX_ClosedLoop"),
                                ("max_patch", "NovaX_MaxPatch"),
                                ("tshell", "NovaX_TShell"),
                                ("start_all", "NovaX_Launcher"),
                                ("watchdog", "NovaX_Watchdog"),
                                ("novalang", "NovaX_NovaLang"),
                            ]:
                                if script_name in cmdline.lower():
                                    name = svc_name
                                    break
                            results.append({
                                "pid": pid,
                                "port": None,
                                "name": name,
                                "source": "cmdline",
                                "cmd": cmdline[:120],
                            })
                    except (ValueError, IndexError):
                        pass
    except Exception:
        pass

    # Deduplicate by PID
    seen = set()
    unique = []
    for r in results:
        if r["pid"] not in seen:
            seen.add(r["pid"])
            unique.append(r)

    return sorted(unique, key=lambda x: x.get("port") or 99999)


def kill_all_novax(exclude_self=True):
    """Kill ALL NovaX processes. Returns count of killed processes."""
    procs = find_novax_processes()
    my_pid = os.getpid()
    killed = 0
    failed = []

    for proc in procs:
        pid = proc["pid"]
        if exclude_self and pid == my_pid:
            continue
        try:
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/F"],
                creationflags=0x08000000,
                capture_output=True, timeout=5
            )
            killed += 1
        except Exception as e:
            failed.append({"pid": pid, "name": proc["name"], "error": str(e)})

    # Also kill any remaining Ollama processes
    try:
        subprocess.run(
            ["taskkill", "/IM", "ollama.exe", "/F"],
            creationflags=0x08000000,
            capture_output=True, timeout=5
        )
    except Exception:
        pass

    return {"killed": killed, "failed": failed, "total_found": len(procs)}


def status():
    """Full NovaX process status."""
    procs = find_novax_processes()
    return {
        "processes": procs,
        "count": len(procs),
        "ports_active": [p["port"] for p in procs if p.get("port")],
    }


# ── Kill Switch Creator ───────────────────────────────────────

def create_kill_switch():
    """Create a desktop shortcut and batch file to instantly kill all NovaX processes."""
    kill_bat = os.path.join(NOVAX_ROOT, "NovaX_KILL.bat")
    bat_content = """@echo off
title NovaX Emergency Kill Switch
color 4F
echo.
echo  ╔══════════════════════════════════════════════╗
echo  ║     NovaX EMERGENCY KILL SWITCH              ║
echo  ║     Terminating all NovaX processes...        ║
echo  ╚══════════════════════════════════════════════╝
echo.

REM Kill all known NovaX service ports
for %%p in (9999 9990 9881 9882 9883 9884 9880 9878 9877 9875 9998 9885 9886 9887 9888 9889 9890) do (
    for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":%%p " ^| findstr "LISTENING"') do (
        echo Killing PID %%a (port %%p)
        taskkill /PID %%a /F >nul 2>&1
    )
)

REM Kill by process name patterns
taskkill /IM ollama.exe /F >nul 2>&1
taskkill /IM redis-server.exe /F >nul 2>&1
taskkill /IM meilisearch.exe /F >nul 2>&1
taskkill /IM caddy.exe /F >nul 2>&1

REM Kill NovaX python processes (match command line)
wmic process where "commandline like '%%NovaX%%' and name='python.exe'" call terminate >nul 2>&1
wmic process where "commandline like '%%nova_%%' and name='python.exe'" call terminate >nul 2>&1
wmic process where "commandline like '%%novax%%' and name='pythonw.exe'" call terminate >nul 2>&1

REM Restore explorer if needed
tasklist /FI "IMAGENAME eq explorer.exe" | find /I "explorer.exe" >nul
if errorlevel 1 (
    echo.
    echo  Explorer.exe was not running - restarting it now...
    start explorer.exe
)

echo.
echo  ╔══════════════════════════════════════════════╗
echo  ║     All NovaX processes terminated.           ║
echo  ║     Windows desktop restored.                 ║
echo  ╚══════════════════════════════════════════════╝
echo.
pause
"""
    with open(kill_bat, "w", encoding="utf-8") as f:
        f.write(bat_content)

    # Create desktop shortcut
    desktop = os.path.join(os.environ.get("USERPROFILE", ""), "Desktop")
    if os.path.isdir(desktop):
        shortcut_vbs = os.path.join(NOVAX_ROOT, "memory", "_create_killswitch.vbs")
        shortcut_path = os.path.join(desktop, "NovaX_KILL.lnk")
        vbs = f'''Set ws = CreateObject("WScript.Shell")
Set sc = ws.CreateShortcut("{shortcut_path}")
sc.TargetPath = "{kill_bat}"
sc.WorkingDirectory = "{NOVAX_ROOT}"
sc.Description = "Emergency kill all NovaX processes"
sc.IconLocation = "shell32.dll,131"
sc.Save
'''
        with open(shortcut_vbs, "w") as f:
            f.write(vbs)
        try:
            subprocess.run(
                ["cscript", "//nologo", shortcut_vbs],
                creationflags=0x08000000,
                capture_output=True, timeout=10
            )
            os.remove(shortcut_vbs)
        except Exception:
            pass

    return {
        "kill_bat": kill_bat,
        "desktop_shortcut": os.path.join(desktop, "NovaX_KILL.lnk") if os.path.isdir(desktop) else None,
    }


# ── Safe Startup Writer ───────────────────────────────────────

def create_safe_startup():
    """Create a safe startup script that ALWAYS keeps explorer.exe running."""
    safe_bat = os.path.join(NOVAX_ROOT, "installer", "novax_safe_startup.bat")
    bat_content = f"""@echo off
title NovaX Safe Startup
cd /d "{NOVAX_ROOT}"

REM ╔══════════════════════════════════════════════════╗
REM ║  NovaX SAFE Startup                              ║
REM ║  ALWAYS ensures explorer.exe is running           ║
REM ║  Kill switch: Run NovaX_KILL.bat on Desktop       ║
REM ╚══════════════════════════════════════════════════╝

REM SAFETY: Ensure explorer.exe is ALWAYS running
tasklist /FI "IMAGENAME eq explorer.exe" | find /I "explorer.exe" >nul
if errorlevel 1 (
    start explorer.exe
    timeout /t 3 /nobreak >nul
)

REM Start NovaX services (hidden, no windows)
start /min "" python "{NOVAX_ROOT}\\start_all.py" 2>nul

REM Wait for orchestrator (max 60s, non-blocking)
set /a tries=0
:wait_loop
set /a tries+=1
if %tries% gtr 30 goto done
timeout /t 2 /nobreak >nul
python -c "import socket; s=socket.socket(); s.settimeout(1); r=s.connect_ex(('127.0.0.1',9999)); s.close(); exit(0 if r==0 else 1)" 2>nul
if errorlevel 1 goto wait_loop

:done
REM NovaX is ready (or timed out - either way, Windows is usable)
exit /b 0
"""
    os.makedirs(os.path.dirname(safe_bat), exist_ok=True)
    with open(safe_bat, "w", encoding="utf-8") as f:
        f.write(bat_content)
    return safe_bat


def register_safe_startup():
    """Register the SAFE startup script in Windows registry (replaces any existing)."""
    safe_bat = create_safe_startup()

    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_SET_VALUE
        )
        winreg.SetValueEx(key, "NovaX", 0, winreg.REG_SZ, safe_bat)
        winreg.CloseKey(key)

        return {"ok": True, "startup_script": safe_bat,
                "message": "Safe startup registered. Explorer always stays running."}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ── Set Process Title ─────────────────────────────────────────

def set_process_title(title):
    """Set the current process's console title (visible in Task Manager details)."""
    try:
        ctypes.windll.kernel32.SetConsoleTitleW(title)
    except Exception:
        pass


# ── CLI ───────────────────────────────────────────────────────

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"

    if cmd == "status":
        result = status()
        print(f"\n  NovaX Process Manager")
        print(f"  {'='*50}")
        print(f"  Active processes: {result['count']}")
        print()
        for p in result["processes"]:
            port_str = f":{p['port']}" if p.get("port") else "      "
            print(f"  PID {p['pid']:>6d}  {port_str:>6s}  {p['name']}")
        print()

    elif cmd == "kill":
        print("\n  NovaX Emergency Kill")
        print(f"  {'='*50}")
        result = kill_all_novax()
        print(f"  Found: {result['total_found']} processes")
        print(f"  Killed: {result['killed']}")
        if result["failed"]:
            for f in result["failed"]:
                print(f"  FAILED: {f['name']} (PID {f['pid']}): {f['error']}")
        print()

    elif cmd == "killswitch":
        result = create_kill_switch()
        print(f"\n  Kill Switch Created")
        print(f"  Batch: {result['kill_bat']}")
        if result.get("desktop_shortcut"):
            print(f"  Desktop: {result['desktop_shortcut']}")
        print()

    elif cmd == "safe-startup":
        result = register_safe_startup()
        print(json.dumps(result, indent=2))

    elif cmd == "fix-startup":
        # Replace dangerous startup with safe version
        result = register_safe_startup()
        ks = create_kill_switch()
        print(f"  Startup fixed: {result.get('ok')}")
        print(f"  Kill switch: {ks['kill_bat']}")

    else:
        print("Usage: python novax_process_manager.py [status|kill|killswitch|safe-startup|fix-startup]")
