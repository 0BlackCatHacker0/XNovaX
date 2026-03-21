"""
NovaX OS Integration — Deep Windows Overlay
Makes Windows look and feel like NovaX IS the operating system.
All changes are reversible. Preserves all drivers, software, credentials.

Features:
  1. Desktop Wallpaper (NovaX branded)
  2. Windows Theme (dark mode + cyan accent)
  3. Protocol Handler (novax:// deep links)
  4. Context Menu (right-click "Open with NovaX" / "Ask NovaX AI")
  5. File Associations (common types → NovaX viewer)
  6. Taskbar Hiding (hide Windows taskbar)
  7. Lock Screen Branding
  8. App Discovery (scan installed Windows apps)
  9. Master Enable/Disable All

State persists in C:/NovaX/memory/os_integration_state.json
"""
import os
import sys
import json
import ctypes
import time
import subprocess
import logging
from pathlib import Path

log = logging.getLogger("NovaX.OSIntegration")

NOVAX_ROOT = r"C:\NovaX"
MEMORY_DIR = os.path.join(NOVAX_ROOT, "memory")
STATE_FILE = os.path.join(MEMORY_DIR, "os_integration_state.json")
WALLPAPER_PATH = os.path.join(NOVAX_ROOT, "web", "assets", "novax_wallpaper.bmp")
LOCKSCREEN_PATH = os.path.join(NOVAX_ROOT, "web", "assets", "novax_lockscreen.jpg")

PYTHON = str(Path(r"C:\Users\Jupit\AppData\Local\Programs\Python\Python312\python.exe"))
if not Path(PYTHON).exists():
    PYTHON = sys.executable


# ══════════════════════════════════════════
# STATE MANAGEMENT
# ══════════════════════════════════════════

def _load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_state(state):
    os.makedirs(MEMORY_DIR, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


# ══════════════════════════════════════════
# 1. DESKTOP WALLPAPER
# ══════════════════════════════════════════

def _get_current_wallpaper():
    """Read current wallpaper path from registry."""
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             r"Control Panel\Desktop", 0, winreg.KEY_READ)
        val, _ = winreg.QueryValueEx(key, "Wallpaper")
        winreg.CloseKey(key)
        return val
    except Exception:
        return ""


def set_wallpaper():
    """Set NovaX-branded wallpaper, saving original for restore."""
    if not os.path.exists(WALLPAPER_PATH):
        return {"ok": False, "error": f"Wallpaper not found: {WALLPAPER_PATH}"}

    state = _load_state()
    if "original_wallpaper" not in state:
        state["original_wallpaper"] = _get_current_wallpaper()

    # SPI_SETDESKWALLPAPER = 0x0014, SPIF_UPDATEINIFILE | SPIF_SENDCHANGE = 3
    result = ctypes.windll.user32.SystemParametersInfoW(0x0014, 0, WALLPAPER_PATH, 3)

    if result:
        state["wallpaper_set"] = True
        state["wallpaper_set_at"] = time.time()
        _save_state(state)
        return {"ok": True, "wallpaper": WALLPAPER_PATH}
    return {"ok": False, "error": "SystemParametersInfoW failed"}


def restore_wallpaper():
    """Restore original wallpaper."""
    state = _load_state()
    original = state.get("original_wallpaper", "")

    if original and os.path.exists(original):
        ctypes.windll.user32.SystemParametersInfoW(0x0014, 0, original, 3)
    else:
        # Set to empty = Windows default
        ctypes.windll.user32.SystemParametersInfoW(0x0014, 0, "", 3)

    state["wallpaper_set"] = False
    _save_state(state)
    return {"ok": True, "restored": original or "(default)"}


def wallpaper_status():
    state = _load_state()
    return {
        "enabled": state.get("wallpaper_set", False),
        "current": _get_current_wallpaper(),
        "novax_wallpaper_exists": os.path.exists(WALLPAPER_PATH),
        "original_saved": "original_wallpaper" in state,
    }


# ══════════════════════════════════════════
# 2. WINDOWS THEME (DARK MODE + ACCENT)
# ══════════════════════════════════════════

THEME_PERSONALIZE = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize"
THEME_DWM = r"SOFTWARE\Microsoft\Windows\DWM"
# NovaX cyan #00E5FF in BGR DWORD = 0x00FFE500
NOVAX_ACCENT_BGR = 0x00FFE500


def _read_reg_dword(path, name, hive=None):
    """Read a DWORD from HKCU registry."""
    try:
        import winreg
        h = hive or winreg.HKEY_CURRENT_USER
        key = winreg.OpenKey(h, path, 0, winreg.KEY_READ)
        val, _ = winreg.QueryValueEx(key, name)
        winreg.CloseKey(key)
        return val
    except Exception:
        return None


def _write_reg_dword(path, name, value, hive=None):
    """Write a DWORD to HKCU registry."""
    try:
        import winreg
        h = hive or winreg.HKEY_CURRENT_USER
        key = winreg.OpenKey(h, path, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, name, 0, winreg.REG_DWORD, value)
        winreg.CloseKey(key)
        return True
    except Exception as e:
        return str(e)


def set_theme():
    """Enable dark mode and set NovaX cyan accent color."""
    state = _load_state()

    # Save originals
    if "original_theme" not in state:
        state["original_theme"] = {
            "AppsUseDarkTheme": _read_reg_dword(THEME_PERSONALIZE, "AppsUseDarkTheme"),
            "SystemUsesLightTheme": _read_reg_dword(THEME_PERSONALIZE, "SystemUsesLightTheme"),
            "AccentColor": _read_reg_dword(THEME_DWM, "AccentColor"),
            "ColorizationColor": _read_reg_dword(THEME_DWM, "ColorizationColor"),
            "ColorPrevalence": _read_reg_dword(THEME_DWM, "ColorPrevalence"),
        }

    errors = []
    # Dark mode
    r = _write_reg_dword(THEME_PERSONALIZE, "AppsUseDarkTheme", 1)
    if r is not True:
        errors.append(f"AppsUseDarkTheme: {r}")
    r = _write_reg_dword(THEME_PERSONALIZE, "SystemUsesLightTheme", 0)
    if r is not True:
        errors.append(f"SystemUsesLightTheme: {r}")

    # Accent color — NovaX cyan
    r = _write_reg_dword(THEME_DWM, "AccentColor", NOVAX_ACCENT_BGR)
    if r is not True:
        errors.append(f"AccentColor: {r}")
    r = _write_reg_dword(THEME_DWM, "ColorizationColor", NOVAX_ACCENT_BGR)
    if r is not True:
        errors.append(f"ColorizationColor: {r}")
    r = _write_reg_dword(THEME_DWM, "ColorPrevalence", 1)
    if r is not True:
        errors.append(f"ColorPrevalence: {r}")

    state["theme_set"] = True
    state["theme_set_at"] = time.time()
    _save_state(state)

    if errors:
        return {"ok": True, "warnings": errors, "note": "Some settings may require admin"}
    return {"ok": True, "dark_mode": True, "accent": "#00E5FF"}


def restore_theme():
    """Restore original Windows theme settings."""
    state = _load_state()
    orig = state.get("original_theme", {})

    if orig.get("AppsUseDarkTheme") is not None:
        _write_reg_dword(THEME_PERSONALIZE, "AppsUseDarkTheme", orig["AppsUseDarkTheme"])
    if orig.get("SystemUsesLightTheme") is not None:
        _write_reg_dword(THEME_PERSONALIZE, "SystemUsesLightTheme", orig["SystemUsesLightTheme"])
    if orig.get("AccentColor") is not None:
        _write_reg_dword(THEME_DWM, "AccentColor", orig["AccentColor"])
    if orig.get("ColorizationColor") is not None:
        _write_reg_dword(THEME_DWM, "ColorizationColor", orig["ColorizationColor"])
    if orig.get("ColorPrevalence") is not None:
        _write_reg_dword(THEME_DWM, "ColorPrevalence", orig["ColorPrevalence"])

    state["theme_set"] = False
    _save_state(state)
    return {"ok": True, "restored": True}


def theme_status():
    dark = _read_reg_dword(THEME_PERSONALIZE, "AppsUseDarkTheme")
    accent = _read_reg_dword(THEME_DWM, "AccentColor")
    state = _load_state()
    return {
        "enabled": state.get("theme_set", False),
        "dark_mode": dark == 1,
        "accent_is_novax": accent == NOVAX_ACCENT_BGR,
        "accent_value": hex(accent) if accent is not None else None,
    }


# ══════════════════════════════════════════
# 3. PROTOCOL HANDLER (novax://)
# ══════════════════════════════════════════

PROTOCOL_HANDLER_SCRIPT = os.path.join(NOVAX_ROOT, "installer", "novax_protocol.py")


def _create_protocol_handler():
    """Create the novax:// protocol handler script."""
    os.makedirs(os.path.dirname(PROTOCOL_HANDLER_SCRIPT), exist_ok=True)
    script = '''"""NovaX Protocol Handler — opens novax:// URLs in browser."""
import sys
import subprocess
import urllib.parse

def main():
    if len(sys.argv) < 2:
        return
    url = sys.argv[1]  # novax://chat or novax://files/path
    # Strip protocol prefix
    path = url.replace("novax://", "").replace("novax:", "").strip("/")
    if not path:
        path = "nova_desktop.html"
    target = f"http://localhost:9999/{path}"
    # Open in default browser
    subprocess.Popen(["cmd", "/c", "start", "", target],
                     creationflags=0x08000000)

if __name__ == "__main__":
    main()
'''
    with open(PROTOCOL_HANDLER_SCRIPT, "w", encoding="utf-8") as f:
        f.write(script)
    return PROTOCOL_HANDLER_SCRIPT


def register_protocol():
    """Register novax:// URL protocol handler."""
    try:
        import winreg
        handler = _create_protocol_handler()

        # Create HKCU\Software\Classes\novax
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\novax")
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "URL:NovaX Protocol")
        winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")
        winreg.CloseKey(key)

        # Set icon
        icon_key = winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                                    r"Software\Classes\novax\DefaultIcon")
        winreg.SetValueEx(icon_key, "", 0, winreg.REG_SZ, f"{PYTHON},0")
        winreg.CloseKey(icon_key)

        # Set command
        cmd_key = winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                                   r"Software\Classes\novax\shell\open\command")
        winreg.SetValueEx(cmd_key, "", 0, winreg.REG_SZ,
                          f'"{PYTHON}" "{handler}" "%1"')
        winreg.CloseKey(cmd_key)

        state = _load_state()
        state["protocol_registered"] = True
        state["protocol_registered_at"] = time.time()
        _save_state(state)

        return {"ok": True, "protocol": "novax://",
                "examples": ["novax://chat", "novax://files", "novax://settings"]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def unregister_protocol():
    """Remove novax:// URL protocol handler."""
    try:
        import winreg
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER,
                         r"Software\Classes\novax\shell\open\command")
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER,
                         r"Software\Classes\novax\shell\open")
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER,
                         r"Software\Classes\novax\shell")
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER,
                         r"Software\Classes\novax\DefaultIcon")
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER,
                         r"Software\Classes\novax")

        state = _load_state()
        state["protocol_registered"] = False
        _save_state(state)
        return {"ok": True, "removed": "novax://"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def protocol_status():
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             r"Software\Classes\novax", 0, winreg.KEY_READ)
        winreg.CloseKey(key)
        registered = True
    except Exception:
        registered = False
    return {"enabled": registered}


# ══════════════════════════════════════════
# 4. CONTEXT MENU INTEGRATION
# ══════════════════════════════════════════

CONTEXT_MENU_KEYS = [
    (r"Software\Classes\*\shell\NovaXOpen", "Open with NovaX",
     f'"{PYTHON}" "{NOVAX_ROOT}\\installer\\novax_file_handler.py" "%1"'),
    (r"Software\Classes\*\shell\NovaXAsk", "Ask NovaX AI",
     f'"{PYTHON}" "{NOVAX_ROOT}\\installer\\novax_file_handler.py" "--ask" "%1"'),
    (r"Software\Classes\Directory\shell\NovaXBrowse", "Browse with NovaX",
     f'"{PYTHON}" "{NOVAX_ROOT}\\installer\\novax_file_handler.py" "--dir" "%1"'),
]

FILE_HANDLER_SCRIPT = os.path.join(NOVAX_ROOT, "installer", "novax_file_handler.py")


def _create_file_handler():
    """Create the file handler script for context menu actions."""
    script = '''"""NovaX File Handler — opens files/folders via NovaX."""
import sys
import subprocess
import urllib.parse

def main():
    args = sys.argv[1:]
    if not args:
        return
    mode = "open"
    path = args[-1]
    if "--ask" in args:
        mode = "ask"
    elif "--dir" in args:
        mode = "dir"

    encoded = urllib.parse.quote(path, safe="")
    if mode == "ask":
        url = f"http://localhost:9999/nova_desktop.html#ask={encoded}"
    elif mode == "dir":
        url = f"http://localhost:9999/nova_desktop.html#files={encoded}"
    else:
        url = f"http://localhost:9999/nova_desktop.html#open={encoded}"

    subprocess.Popen(["cmd", "/c", "start", "", url],
                     creationflags=0x08000000)

if __name__ == "__main__":
    main()
'''
    os.makedirs(os.path.dirname(FILE_HANDLER_SCRIPT), exist_ok=True)
    with open(FILE_HANDLER_SCRIPT, "w", encoding="utf-8") as f:
        f.write(script)


def add_context_menu():
    """Add NovaX items to Windows right-click context menu."""
    try:
        import winreg
        _create_file_handler()

        for reg_path, label, command in CONTEXT_MENU_KEYS:
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, reg_path)
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, label)
            winreg.SetValueEx(key, "Icon", 0, winreg.REG_SZ, f"{PYTHON},0")
            winreg.CloseKey(key)

            cmd_key = winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                                       reg_path + r"\command")
            winreg.SetValueEx(cmd_key, "", 0, winreg.REG_SZ, command)
            winreg.CloseKey(cmd_key)

        state = _load_state()
        state["context_menu_added"] = True
        state["context_menu_at"] = time.time()
        _save_state(state)

        return {"ok": True, "items": [lbl for _, lbl, _ in CONTEXT_MENU_KEYS]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def remove_context_menu():
    """Remove NovaX items from right-click context menu."""
    try:
        import winreg
        for reg_path, _, _ in CONTEXT_MENU_KEYS:
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, reg_path + r"\command")
            except FileNotFoundError:
                pass
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, reg_path)
            except FileNotFoundError:
                pass

        state = _load_state()
        state["context_menu_added"] = False
        _save_state(state)
        return {"ok": True, "removed": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def context_menu_status():
    try:
        import winreg
        winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                       r"Software\Classes\*\shell\NovaXOpen", 0, winreg.KEY_READ)
        return {"enabled": True}
    except Exception:
        return {"enabled": False}


# ══════════════════════════════════════════
# 5. FILE TYPE ASSOCIATIONS
# ══════════════════════════════════════════

FILE_TYPES = [".txt", ".md", ".json", ".log", ".csv",
              ".pdf", ".png", ".jpg", ".jpeg", ".gif", ".bmp",
              ".mp3", ".mp4", ".wav", ".webm"]
NOVAX_PROGID = "NovaX.FileViewer"


def set_file_associations():
    """Register NovaX as handler for common file types."""
    try:
        import winreg
        _create_file_handler()

        # Create ProgID
        prog_key = winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                                    rf"Software\Classes\{NOVAX_PROGID}")
        winreg.SetValueEx(prog_key, "", 0, winreg.REG_SZ, "NovaX File Viewer")
        winreg.CloseKey(prog_key)

        cmd_key = winreg.CreateKey(
            winreg.HKEY_CURRENT_USER,
            rf"Software\Classes\{NOVAX_PROGID}\shell\open\command")
        winreg.SetValueEx(cmd_key, "", 0, winreg.REG_SZ,
                          f'"{PYTHON}" "{FILE_HANDLER_SCRIPT}" "%1"')
        winreg.CloseKey(cmd_key)

        # Save originals and set associations
        state = _load_state()
        originals = state.get("original_file_assoc", {})

        associated = []
        for ext in FILE_TYPES:
            # Save original
            if ext not in originals:
                try:
                    ek = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                        rf"Software\Classes\{ext}", 0, winreg.KEY_READ)
                    orig_val, _ = winreg.QueryValueEx(ek, "")
                    winreg.CloseKey(ek)
                    originals[ext] = orig_val
                except Exception:
                    originals[ext] = ""

            # Set NovaX as handler
            try:
                ek = winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                                      rf"Software\Classes\{ext}")
                winreg.SetValueEx(ek, "", 0, winreg.REG_SZ, NOVAX_PROGID)
                winreg.CloseKey(ek)
                associated.append(ext)
            except Exception:
                pass

        state["original_file_assoc"] = originals
        state["file_assoc_set"] = True
        state["file_assoc_at"] = time.time()
        _save_state(state)

        return {"ok": True, "associated": associated, "count": len(associated)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def restore_file_associations():
    """Restore original file type associations."""
    try:
        import winreg
        state = _load_state()
        originals = state.get("original_file_assoc", {})

        for ext, orig_val in originals.items():
            try:
                if orig_val:
                    ek = winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                                          rf"Software\Classes\{ext}")
                    winreg.SetValueEx(ek, "", 0, winreg.REG_SZ, orig_val)
                    winreg.CloseKey(ek)
                else:
                    winreg.DeleteKey(winreg.HKEY_CURRENT_USER,
                                     rf"Software\Classes\{ext}")
            except Exception:
                pass

        # Clean up ProgID
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER,
                             rf"Software\Classes\{NOVAX_PROGID}\shell\open\command")
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER,
                             rf"Software\Classes\{NOVAX_PROGID}\shell\open")
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER,
                             rf"Software\Classes\{NOVAX_PROGID}\shell")
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER,
                             rf"Software\Classes\{NOVAX_PROGID}")
        except Exception:
            pass

        state["file_assoc_set"] = False
        _save_state(state)
        return {"ok": True, "restored": list(originals.keys())}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def file_assoc_status():
    state = _load_state()
    return {
        "enabled": state.get("file_assoc_set", False),
        "types": FILE_TYPES,
    }


# ══════════════════════════════════════════
# 6. TASKBAR HIDING
# ══════════════════════════════════════════

SW_HIDE = 0
SW_SHOW = 5


def hide_taskbar():
    """Hide the Windows taskbar."""
    try:
        hwnd = ctypes.windll.user32.FindWindowW("Shell_TrayWnd", None)
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, SW_HIDE)
        # Secondary taskbar (multi-monitor)
        hwnd2 = ctypes.windll.user32.FindWindowW("Shell_SecondaryTrayWnd", None)
        if hwnd2:
            ctypes.windll.user32.ShowWindow(hwnd2, SW_HIDE)

        state = _load_state()
        state["taskbar_hidden"] = True
        _save_state(state)
        return {"ok": True, "hidden": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def show_taskbar():
    """Show the Windows taskbar."""
    try:
        hwnd = ctypes.windll.user32.FindWindowW("Shell_TrayWnd", None)
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, SW_SHOW)
        hwnd2 = ctypes.windll.user32.FindWindowW("Shell_SecondaryTrayWnd", None)
        if hwnd2:
            ctypes.windll.user32.ShowWindow(hwnd2, SW_SHOW)

        state = _load_state()
        state["taskbar_hidden"] = False
        _save_state(state)
        return {"ok": True, "visible": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def taskbar_status():
    state = _load_state()
    hwnd = ctypes.windll.user32.FindWindowW("Shell_TrayWnd", None)
    visible = False
    if hwnd:
        visible = ctypes.windll.user32.IsWindowVisible(hwnd) != 0
    return {
        "enabled": state.get("taskbar_hidden", False),
        "taskbar_visible": visible,
        "taskbar_hwnd": hwnd,
    }


# ══════════════════════════════════════════
# 7. LOCK SCREEN BRANDING
# ══════════════════════════════════════════

LOCK_REG = r"SOFTWARE\Microsoft\Windows\CurrentVersion\PersonalizationCSP"


def set_lock_screen():
    """Set NovaX-branded lock screen image."""
    if not os.path.exists(LOCKSCREEN_PATH):
        # Use wallpaper as fallback
        src = WALLPAPER_PATH if os.path.exists(WALLPAPER_PATH) else None
        if not src:
            return {"ok": False, "error": "No lock screen image available"}
    else:
        src = LOCKSCREEN_PATH

    try:
        import winreg
        state = _load_state()

        # Save original lock screen path
        if "original_lockscreen" not in state:
            try:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, LOCK_REG,
                                     0, winreg.KEY_READ)
                val, _ = winreg.QueryValueEx(key, "LockScreenImagePath")
                winreg.CloseKey(key)
                state["original_lockscreen"] = val
            except Exception:
                state["original_lockscreen"] = ""

        # Set lock screen
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, LOCK_REG)
        winreg.SetValueEx(key, "LockScreenImagePath", 0, winreg.REG_SZ, src)
        winreg.SetValueEx(key, "LockScreenImageUrl", 0, winreg.REG_SZ, src)
        winreg.SetValueEx(key, "LockScreenImageStatus", 0, winreg.REG_DWORD, 1)
        winreg.CloseKey(key)

        state["lockscreen_set"] = True
        state["lockscreen_at"] = time.time()
        _save_state(state)
        return {"ok": True, "image": src}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def restore_lock_screen():
    """Restore original lock screen."""
    try:
        import winreg
        state = _load_state()
        original = state.get("original_lockscreen", "")

        try:
            if original:
                key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, LOCK_REG)
                winreg.SetValueEx(key, "LockScreenImagePath", 0, winreg.REG_SZ, original)
                winreg.SetValueEx(key, "LockScreenImageUrl", 0, winreg.REG_SZ, original)
                winreg.CloseKey(key)
            else:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, LOCK_REG)
        except Exception:
            pass

        state["lockscreen_set"] = False
        _save_state(state)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def lockscreen_status():
    state = _load_state()
    return {
        "enabled": state.get("lockscreen_set", False),
        "image_exists": os.path.exists(LOCKSCREEN_PATH),
    }


# ══════════════════════════════════════════
# 8. APP DISCOVERY
# ══════════════════════════════════════════

def scan_installed_apps():
    """Scan Windows Start Menu for installed applications."""
    apps = []
    seen = set()

    search_dirs = [
        os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"),
        os.path.expandvars(r"%PROGRAMDATA%\Microsoft\Windows\Start Menu\Programs"),
    ]

    for base in search_dirs:
        if not os.path.exists(base):
            continue
        for root, dirs, files in os.walk(base):
            for f in files:
                if f.lower().endswith(".lnk"):
                    name = f[:-4]  # Strip .lnk
                    if name.lower() in seen:
                        continue
                    seen.add(name.lower())
                    full_path = os.path.join(root, f)
                    # Get relative category from folder
                    rel = os.path.relpath(root, base)
                    category = rel if rel != "." else "General"
                    apps.append({
                        "name": name,
                        "shortcut": full_path,
                        "category": category,
                    })

    apps.sort(key=lambda a: a["name"].lower())
    return {"apps": apps, "count": len(apps)}


# ══════════════════════════════════════════
# 9. MASTER STATUS & TOGGLE
# ══════════════════════════════════════════

def integration_status():
    """Full status of all OS integration features."""
    return {
        "wallpaper": wallpaper_status(),
        "theme": theme_status(),
        "protocol": protocol_status(),
        "context_menu": context_menu_status(),
        "file_associations": file_assoc_status(),
        "taskbar": taskbar_status(),
        "lock_screen": lockscreen_status(),
    }


def enable_all():
    """Enable all non-destructive OS integration features."""
    results = {}
    results["wallpaper"] = set_wallpaper()
    results["theme"] = set_theme()
    results["protocol"] = register_protocol()
    results["context_menu"] = add_context_menu()
    results["file_associations"] = set_file_associations()
    results["taskbar"] = hide_taskbar()
    results["lock_screen"] = set_lock_screen()

    success = sum(1 for r in results.values() if r.get("ok"))
    return {"ok": True, "enabled": success, "total": len(results),
            "details": results}


def disable_all():
    """Revert all OS integration features to Windows defaults."""
    results = {}
    results["wallpaper"] = restore_wallpaper()
    results["theme"] = restore_theme()
    results["protocol"] = unregister_protocol()
    results["context_menu"] = remove_context_menu()
    results["file_associations"] = restore_file_associations()
    results["taskbar"] = show_taskbar()
    results["lock_screen"] = restore_lock_screen()

    success = sum(1 for r in results.values() if r.get("ok"))
    return {"ok": True, "disabled": success, "total": len(results),
            "details": results}


# ══════════════════════════════════════════
# CLI
# ══════════════════════════════════════════

if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "status"
    actions = {
        "status": integration_status,
        "enable-all": enable_all,
        "disable-all": disable_all,
        "wallpaper-set": set_wallpaper,
        "wallpaper-restore": restore_wallpaper,
        "theme-set": set_theme,
        "theme-restore": restore_theme,
        "protocol-register": register_protocol,
        "protocol-unregister": unregister_protocol,
        "context-menu-add": add_context_menu,
        "context-menu-remove": remove_context_menu,
        "file-assoc-set": set_file_associations,
        "file-assoc-restore": restore_file_associations,
        "taskbar-hide": hide_taskbar,
        "taskbar-show": show_taskbar,
        "lockscreen-set": set_lock_screen,
        "lockscreen-restore": restore_lock_screen,
        "apps": scan_installed_apps,
    }
    fn = actions.get(action)
    if fn:
        print(json.dumps(fn(), indent=2))
    else:
        print(f"Usage: python os_integration.py [{' | '.join(actions.keys())}]")
