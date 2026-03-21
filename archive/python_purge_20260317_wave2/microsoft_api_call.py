"""
microsoft_api_call.py -- Win32 Python bridge for nova_microsoft_engine.nova
Stdlib only: ctypes, winreg, subprocess, json, os, sys, platform, shutil, struct
No pip installs required.

Usage:
    python microsoft_api_call.py --file C:/NovaX/tmp_microsoft_payload.json
    echo '{"tool":"system","op":"info"}' | python microsoft_api_call.py
"""

import sys
import json
import os
import ctypes
import ctypes.wintypes
import winreg
import subprocess
import platform
import shutil
import struct


# ──────────────────────────────────────────────────────────────
# Tool: windows — list, focus, resize, minimize, maximize
# ──────────────────────────────────────────────────────────────

def handle_windows(op, payload):
    user32 = ctypes.windll.user32

    if op == "list":
        try:
            out = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Get-Process | Where-Object {$_.MainWindowTitle -ne ''} "
                 "| Select-Object Id,ProcessName,MainWindowTitle "
                 "| ConvertTo-Json -Compress"],
                capture_output=True, text=True, timeout=10
            )
            raw = out.stdout.strip()
            if not raw:
                return {"ok": True, "windows": []}
            data = json.loads(raw)
            if isinstance(data, dict):
                data = [data]
            return {"ok": True, "windows": data}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    hwnd = int(payload.get("hwnd", 0))
    if hwnd == 0:
        return {"ok": False, "error": "hwnd_required"}

    if op == "focus":
        try:
            user32.SetForegroundWindow(hwnd)
            return {"ok": True, "action": "focus", "hwnd": hwnd}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    if op == "minimize":
        SW_MINIMIZE = 6
        user32.ShowWindow(hwnd, SW_MINIMIZE)
        return {"ok": True, "action": "minimize", "hwnd": hwnd}

    if op == "maximize":
        SW_MAXIMIZE = 3
        user32.ShowWindow(hwnd, SW_MAXIMIZE)
        return {"ok": True, "action": "maximize", "hwnd": hwnd}

    if op == "resize":
        width = int(payload.get("width", 800))
        height = int(payload.get("height", 600))
        SWP_NOMOVE = 0x0002
        SWP_NOZORDER = 0x0004
        user32.SetWindowPos(hwnd, 0, 0, 0, width, height, SWP_NOMOVE | SWP_NOZORDER)
        return {"ok": True, "action": "resize", "hwnd": hwnd, "width": width, "height": height}

    return {"ok": False, "error": "unknown_op", "op": op}


# ──────────────────────────────────────────────────────────────
# Tool: registry — read, query (READ-ONLY)
# ──────────────────────────────────────────────────────────────

HIVE_MAP = {
    "HKLM": winreg.HKEY_LOCAL_MACHINE,
    "HKEY_LOCAL_MACHINE": winreg.HKEY_LOCAL_MACHINE,
    "HKCU": winreg.HKEY_CURRENT_USER,
    "HKEY_CURRENT_USER": winreg.HKEY_CURRENT_USER,
    "HKCR": winreg.HKEY_CLASSES_ROOT,
    "HKEY_CLASSES_ROOT": winreg.HKEY_CLASSES_ROOT,
    "HKU": winreg.HKEY_USERS,
    "HKEY_USERS": winreg.HKEY_USERS,
}


def _parse_reg_key(key_path):
    """Split 'HKLM\\SOFTWARE\\...' into (hive_constant, subkey_path)."""
    parts = key_path.replace("/", "\\").split("\\", 1)
    hive_str = parts[0].upper()
    hive = HIVE_MAP.get(hive_str)
    subkey = parts[1] if len(parts) > 1 else ""
    return hive, subkey


def _reg_value_to_json(data, dtype):
    """Convert registry value to JSON-safe representation."""
    if dtype in (winreg.REG_SZ, winreg.REG_EXPAND_SZ):
        return str(data)
    if dtype == winreg.REG_DWORD:
        return int(data)
    if dtype == winreg.REG_QWORD:
        return int(data)
    if dtype == winreg.REG_MULTI_SZ:
        return list(data)
    if dtype == winreg.REG_BINARY:
        return data.hex() if isinstance(data, bytes) else str(data)
    return str(data)


def handle_registry(op, payload):
    key_path = payload.get("key", "")
    if not key_path:
        return {"ok": False, "error": "key_required"}

    hive, subkey = _parse_reg_key(key_path)
    if hive is None:
        return {"ok": False, "error": "unknown_hive", "key": key_path}

    if op == "read":
        value_name = payload.get("value", "")
        try:
            handle = winreg.OpenKey(hive, subkey, 0, winreg.KEY_READ)
            data, dtype = winreg.QueryValueEx(handle, value_name if value_name else None)
            winreg.CloseKey(handle)
            return {"ok": True, "key": key_path, "value_name": value_name,
                    "data": _reg_value_to_json(data, dtype), "type": dtype}
        except FileNotFoundError:
            return {"ok": False, "error": "key_not_found", "key": key_path}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    if op == "query":
        try:
            handle = winreg.OpenKey(hive, subkey, 0, winreg.KEY_READ)
            subkeys = []
            i = 0
            while True:
                try:
                    subkeys.append(winreg.EnumKey(handle, i))
                    i += 1
                except OSError:
                    break
            values = []
            i = 0
            while True:
                try:
                    name, data, dtype = winreg.EnumValue(handle, i)
                    values.append({"name": name, "data": _reg_value_to_json(data, dtype), "type": dtype})
                    i += 1
                except OSError:
                    break
            winreg.CloseKey(handle)
            return {"ok": True, "key": key_path, "subkeys": subkeys, "values": values}
        except FileNotFoundError:
            return {"ok": False, "error": "key_not_found", "key": key_path}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    return {"ok": False, "error": "unknown_op", "op": op}


# ──────────────────────────────────────────────────────────────
# Tool: process — list, info, ports
# ──────────────────────────────────────────────────────────────

def handle_process(op, payload):
    if op == "list":
        try:
            out = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Get-Process | Select-Object Id,ProcessName,"
                 "@{N='MemMB';E={[math]::Round($_.WorkingSet64/1MB,1)}},"
                 "@{N='CPU_s';E={[math]::Round($_.CPU,2)}} "
                 "| ConvertTo-Json -Compress"],
                capture_output=True, text=True, timeout=15
            )
            raw = out.stdout.strip()
            if not raw:
                return {"ok": True, "processes": []}
            data = json.loads(raw)
            if isinstance(data, dict):
                data = [data]
            return {"ok": True, "count": len(data), "processes": data}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    if op == "info":
        pid = payload.get("pid", 0)
        name = payload.get("name", "")
        filt = ""
        if pid:
            filt = f"| Where-Object {{$_.Id -eq {int(pid)}}}"
        elif name:
            filt = f"| Where-Object {{$_.ProcessName -like '*{name}*'}}"
        else:
            return {"ok": False, "error": "pid_or_name_required"}
        try:
            out = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 f"Get-Process {filt} | Select-Object Id,ProcessName,Path,"
                 f"@{{N='MemMB';E={{[math]::Round($_.WorkingSet64/1MB,1)}}}},"
                 f"@{{N='CPU_s';E={{[math]::Round($_.CPU,2)}}}},"
                 f"StartTime,MainWindowTitle | ConvertTo-Json -Compress"],
                capture_output=True, text=True, timeout=10
            )
            raw = out.stdout.strip()
            if not raw:
                return {"ok": False, "error": "not_found"}
            data = json.loads(raw)
            if isinstance(data, dict):
                data = [data]
            return {"ok": True, "processes": data}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    if op == "ports":
        try:
            out = subprocess.run(
                ["netstat", "-ano"],
                capture_output=True, text=True, timeout=10
            )
            lines = out.stdout.strip().split("\n")
            entries = []
            for line in lines[4:]:  # skip header lines
                parts = line.split()
                if len(parts) >= 5:
                    entries.append({
                        "proto": parts[0],
                        "local": parts[1],
                        "remote": parts[2],
                        "state": parts[3] if len(parts) == 5 else "",
                        "pid": int(parts[-1]) if parts[-1].isdigit() else 0
                    })
            # Filter by pid or name if provided
            pid = payload.get("pid", 0)
            if pid:
                entries = [e for e in entries if e["pid"] == int(pid)]
            return {"ok": True, "count": len(entries), "connections": entries[:200]}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    return {"ok": False, "error": "unknown_op", "op": op}


# ──────────────────────────────────────────────────────────────
# Tool: system — info, cpu, memory, disk, gpu, os
# ──────────────────────────────────────────────────────────────

def handle_system(op, payload):
    if op in ("info", "os"):
        return {
            "ok": True,
            "os": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python": platform.python_version(),
            "node": platform.node(),
            "release": platform.release(),
            "version": platform.version()
        }

    if op == "cpu":
        try:
            out = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Get-CimInstance Win32_Processor "
                 "| Select-Object Name,NumberOfCores,NumberOfLogicalProcessors,"
                 "MaxClockSpeed,LoadPercentage "
                 "| ConvertTo-Json -Compress"],
                capture_output=True, text=True, timeout=10
            )
            raw = out.stdout.strip()
            data = json.loads(raw) if raw else {}
            if isinstance(data, list):
                data = data[0]
            return {"ok": True, "cpu": data}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    if op == "memory":
        try:
            # Use GlobalMemoryStatusEx via ctypes
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.wintypes.DWORD),
                    ("dwMemoryLoad", ctypes.wintypes.DWORD),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]
            mem = MEMORYSTATUSEX()
            mem.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem))
            total_gb = round(mem.ullTotalPhys / (1024**3), 2)
            avail_gb = round(mem.ullAvailPhys / (1024**3), 2)
            used_gb = round(total_gb - avail_gb, 2)
            return {
                "ok": True,
                "memory": {
                    "total_gb": total_gb,
                    "available_gb": avail_gb,
                    "used_gb": used_gb,
                    "percent_used": mem.dwMemoryLoad
                }
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    if op == "disk":
        try:
            drives = []
            for letter in "CDEFGHIJ":
                path = f"{letter}:\\"
                if os.path.exists(path):
                    usage = shutil.disk_usage(path)
                    drives.append({
                        "drive": f"{letter}:",
                        "total_gb": round(usage.total / (1024**3), 2),
                        "used_gb": round(usage.used / (1024**3), 2),
                        "free_gb": round(usage.free / (1024**3), 2),
                        "percent_used": round(usage.used / usage.total * 100, 1)
                    })
            return {"ok": True, "drives": drives}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    if op == "gpu":
        try:
            out = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Get-CimInstance Win32_VideoController "
                 "| Select-Object Name,AdapterRAM,DriverVersion,VideoProcessor,"
                 "@{N='VRAM_MB';E={[math]::Round($_.AdapterRAM/1MB,0)}} "
                 "| ConvertTo-Json -Compress"],
                capture_output=True, text=True, timeout=10
            )
            raw = out.stdout.strip()
            if not raw:
                return {"ok": True, "gpus": []}
            data = json.loads(raw)
            if isinstance(data, dict):
                data = [data]
            return {"ok": True, "gpus": data}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    return {"ok": False, "error": "unknown_op", "op": op}


# ──────────────────────────────────────────────────────────────
# Tool: theme — darkmode, accent, wallpaper
# ──────────────────────────────────────────────────────────────

def handle_theme(op, payload):
    if op == "darkmode":
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
                0, winreg.KEY_READ
            )
            apps_light, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            sys_light, _ = winreg.QueryValueEx(key, "SystemUsesLightTheme")
            winreg.CloseKey(key)
            return {
                "ok": True,
                "dark_mode_apps": apps_light == 0,
                "dark_mode_system": sys_light == 0
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    if op == "accent":
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\DWM",
                0, winreg.KEY_READ
            )
            color, _ = winreg.QueryValueEx(key, "AccentColor")
            colorization, _ = winreg.QueryValueEx(key, "ColorizationColor")
            winreg.CloseKey(key)
            # AccentColor is ABGR as DWORD
            a = (color >> 24) & 0xFF
            b = (color >> 16) & 0xFF
            g = (color >> 8) & 0xFF
            r = color & 0xFF
            hex_color = f"#{r:02x}{g:02x}{b:02x}"
            return {
                "ok": True,
                "accent_color": hex_color,
                "accent_abgr": color,
                "colorization": colorization
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    if op == "wallpaper":
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Control Panel\Desktop",
                0, winreg.KEY_READ
            )
            wallpaper, _ = winreg.QueryValueEx(key, "WallPaper")
            style, _ = winreg.QueryValueEx(key, "WallpaperStyle")
            tile, _ = winreg.QueryValueEx(key, "TileWallpaper")
            winreg.CloseKey(key)
            mode = "unknown"
            if tile == "1":
                mode = "tile"
            elif style == "0":
                mode = "center"
            elif style == "2":
                mode = "stretch"
            elif style == "6":
                mode = "fit"
            elif style == "10":
                mode = "fill"
            elif style == "22":
                mode = "span"
            return {"ok": True, "wallpaper": wallpaper, "style": mode}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    return {"ok": False, "error": "unknown_op", "op": op}


# ──────────────────────────────────────────────────────────────
# Tool: clipboard — read
# ──────────────────────────────────────────────────────────────

def handle_clipboard(op, payload):
    if op == "read":
        CF_UNICODETEXT = 13
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        user32.OpenClipboard(0)
        try:
            # Try unicode first
            handle = user32.GetClipboardData(CF_UNICODETEXT)
            if handle:
                kernel32.GlobalLock.restype = ctypes.c_void_p
                ptr = kernel32.GlobalLock(handle)
                if ptr:
                    text = ctypes.wstring_at(ptr)
                    kernel32.GlobalUnlock(handle)
                    return {"ok": True, "content": text, "encoding": "unicode"}
                kernel32.GlobalUnlock(handle)

            # Fallback to CF_TEXT (ANSI)
            CF_TEXT = 1
            handle = user32.GetClipboardData(CF_TEXT)
            if handle:
                kernel32.GlobalLock.restype = ctypes.c_void_p
                ptr = kernel32.GlobalLock(handle)
                if ptr:
                    text = ctypes.string_at(ptr).decode("utf-8", errors="replace")
                    kernel32.GlobalUnlock(handle)
                    return {"ok": True, "content": text, "encoding": "ansi"}
                kernel32.GlobalUnlock(handle)

            return {"ok": True, "content": "", "encoding": "empty"}
        except Exception as e:
            return {"ok": False, "error": str(e)}
        finally:
            user32.CloseClipboard()

    return {"ok": False, "error": "unknown_op", "op": op}


# ──────────────────────────────────────────────────────────────
# Tool: notify — toast (non-blocking)
# ──────────────────────────────────────────────────────────────

def handle_notify(op, payload):
    if op == "toast":
        title = str(payload.get("title", "NovaX")).replace('"', "'").replace("`", "'")
        message = str(payload.get("message", "")).replace('"', "'").replace("`", "'")

        # Method 1: PowerShell balloon notification (non-blocking)
        ps_script = (
            "[void][System.Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms');"
            "$n = New-Object System.Windows.Forms.NotifyIcon;"
            "$n.Icon = [System.Drawing.SystemIcons]::Information;"
            "$n.BalloonTipTitle = '{title}';"
            "$n.BalloonTipText = '{message}';"
            "$n.Visible = $true;"
            "$n.ShowBalloonTip(5000);"
            "Start-Sleep -Seconds 6;"
            "$n.Dispose()"
        ).format(title=title, message=message)

        try:
            # Fire and forget -- use Popen so it doesn't block
            subprocess.Popen(
                ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps_script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=0x08000000  # CREATE_NO_WINDOW
            )
            return {"ok": True, "sent": True, "method": "balloon", "title": title}
        except Exception:
            pass

        # Method 2: msg.exe fallback (sends to current session, also non-blocking feel)
        try:
            subprocess.Popen(
                ["msg", "*", f"/TIME:5", f"{title}: {message}"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=0x08000000
            )
            return {"ok": True, "sent": True, "method": "msg", "title": title}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    return {"ok": False, "error": "unknown_op", "op": op}


# ──────────────────────────────────────────────────────────────
# Main dispatcher
# ──────────────────────────────────────────────────────────────

TOOL_HANDLERS = {
    "windows": handle_windows,
    "registry": handle_registry,
    "process": handle_process,
    "system": handle_system,
    "theme": handle_theme,
    "clipboard": handle_clipboard,
    "notify": handle_notify,
}


def main():
    args = sys.argv[1:]

    # Load payload from file or stdin
    if "--file" in args:
        idx = args.index("--file")
        path = args[idx + 1]
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
    else:
        raw = sys.stdin.read().strip()
        if not raw:
            print(json.dumps({"ok": False, "error": "no_input"}))
            return
        payload = json.loads(raw)

    tool = payload.get("tool", "")
    op = payload.get("op", "")

    handler = TOOL_HANDLERS.get(tool)
    if handler is None:
        print(json.dumps({"ok": False, "error": "unknown_tool", "tool": tool}))
        return

    try:
        result = handler(op, payload)
    except Exception as e:
        result = {"ok": False, "error": str(e), "tool": tool, "op": op}

    print(json.dumps(result))


if __name__ == "__main__":
    main()
