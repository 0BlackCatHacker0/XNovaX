"""
NovaX Desktop Launcher — Zero-window bootstrap
Starts the orchestrator (which boots all services via BOOT_ORDER),
waits for health, then opens the desktop UI in the default browser.
"""

import subprocess
import sys
import os
import time
import urllib.request
import webbrowser
import ctypes

# ── Hide any console window ──────────────────────────────────────────
try:
    hwnd = ctypes.windll.kernel32.GetConsoleWindow()
    if hwnd:
        ctypes.windll.user32.ShowWindow(hwnd, 0)
except Exception:
    pass

# ── Constants ─────────────────────────────────────────────────────────
NOVAX_DIR = r"C:\NovaX"
ORCHESTRATOR = os.path.join(NOVAX_DIR, "core", "orchestrator.py")
ORCHESTRATOR_URL = "http://localhost:9999"
DESKTOP_URL = f"{ORCHESTRATOR_URL}/nova_desktop.html"
BOOT_URL = f"{ORCHESTRATOR_URL}/api/services/boot"
PYTHON = sys.executable.replace("pythonw.exe", "python.exe")

CREATE_NO_WINDOW = 0x08000000


def is_running():
    """Check if orchestrator is already responding."""
    try:
        with urllib.request.urlopen(f"{ORCHESTRATOR_URL}/health", timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


def wait_for_health(timeout=60):
    """Wait for orchestrator to become healthy."""
    start = time.time()
    while time.time() - start < timeout:
        if is_running():
            return True
        time.sleep(1)
    return False


def boot_services():
    """Tell orchestrator to boot all child services."""
    try:
        import json
        req = urllib.request.Request(
            BOOT_URL,
            data=json.dumps({}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status == 200
    except Exception:
        return False


def show_toast(title, msg):
    """Show a Windows toast notification (best-effort)."""
    try:
        from ctypes import windll
        windll.user32.MessageBoxW(0, msg, title, 0x40)
    except Exception:
        pass


def main():
    already_running = is_running()

    if not already_running:
        # Start orchestrator as a hidden subprocess
        env = os.environ.copy()
        env["PYTHONPATH"] = NOVAX_DIR

        subprocess.Popen(
            [PYTHON, ORCHESTRATOR],
            cwd=NOVAX_DIR,
            creationflags=CREATE_NO_WINDOW,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Wait for orchestrator to come up
        if not wait_for_health(timeout=45):
            show_toast("NovaX", "Orchestrator failed to start within 45 seconds.")
            return

        # Give it a moment then boot all services
        time.sleep(2)
        boot_services()

        # Wait a bit for services to initialize
        time.sleep(3)

    # NovaX Desktop is available at http://localhost:9999/nova_desktop.html
    # and via the static server at http://localhost:8888/nova_desktop.html
    # Do NOT auto-open a browser — it hijacks Edge and steals focus.
    # Users can open the desktop manually or via the tray icon.
    show_toast("NovaX", f"NovaX OS is ready!\n{DESKTOP_URL}")


if __name__ == "__main__":
    main()
