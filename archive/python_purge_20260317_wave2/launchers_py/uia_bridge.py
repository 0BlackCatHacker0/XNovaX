"""NovaX UIA Bridge v2 - Session 1 Desktop Window Monitor
Runs in user's desktop session via pythonw.exe (no console window).
Monitors Claude Desktop and ChatGPT Desktop windows, sends window
metadata + HWND hints to Cortex every 3 seconds.

Solves cross-session issue: Cortex in session 0 can't see desktop
windows. This bridge in session 1 discovers them and feeds Cortex.

Usage:
  pythonw.exe uia_bridge.py
  python nowindow.py uia_bridge.py
"""
import json, time, os, sys, urllib.request
import ctypes
import ctypes.wintypes

# 3-5-7-13 harmonic constants
H3, H5 = 3, 5
POLL_INTERVAL = H3  # 3 seconds
CORTEX_URL = "http://127.0.0.1:9896"

user32 = ctypes.windll.user32
WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)


def find_windows():
    """Find Claude Desktop and ChatGPT Desktop windows."""
    buf = ctypes.create_unicode_buffer(256)
    results = {"claude": None, "gpt": None}

    def callback(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            user32.GetWindowTextW(hwnd, buf, 256)
            title = buf.value.lower()
            if "claude" in title and not results["claude"]:
                results["claude"] = hwnd
            elif ("chatgpt" in title or title == "gpt") and not results["gpt"]:
                results["gpt"] = hwnd
        return True

    user32.EnumWindows(WNDENUMPROC(callback), 0)
    return results


def get_window_info(hwnd):
    """Get basic window metadata."""
    buf = ctypes.create_unicode_buffer(256)
    user32.GetWindowTextW(hwnd, buf, 256)
    rect = ctypes.wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    is_minimized = user32.IsIconic(hwnd)
    is_focused = user32.GetForegroundWindow() == hwnd

    # Count child windows
    child_count = [0]
    def count_cb(child_hwnd, _):
        child_count[0] += 1
        return True
    user32.EnumChildWindows(hwnd, WNDENUMPROC(count_cb), 0)

    return {
        "title": buf.value,
        "hwnd": hwnd,
        "rect": {"left": rect.left, "top": rect.top,
                 "right": rect.right, "bottom": rect.bottom},
        "size": {"w": rect.right - rect.left, "h": rect.bottom - rect.top},
        "minimized": bool(is_minimized),
        "focused": bool(is_focused),
        "children": child_count[0],
        "visible": True,
    }


def post_json(path, data):
    """POST JSON to Cortex."""
    try:
        payload = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(
            f"{CORTEX_URL}{path}",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        resp = urllib.request.urlopen(req, timeout=H5)
        return json.loads(resp.read())
    except Exception:
        return None


def bridge_loop():
    """Main loop: find windows, send hints + metadata to Cortex."""
    last_full_hint = 0

    while True:
        try:
            windows = find_windows()
            now = time.time()

            # Send HWND hints every 30 seconds (or on first discovery)
            if now - last_full_hint > 30:
                hints = {}
                if windows["claude"]:
                    hints["claude_hwnd"] = windows["claude"]
                if windows["gpt"]:
                    hints["gpt_hwnd"] = windows["gpt"]
                if hints:
                    post_json("/cortex/hint", hints)
                    last_full_hint = now

            # Send window snapshots (metadata only - UIA won't work for Electron content)
            for target in ("claude", "gpt"):
                hwnd = windows.get(target)
                if hwnd:
                    info = get_window_info(hwnd)
                    snapshot = {
                        "elements": [
                            {"name": info["title"], "type": "Window", "type_id": 50032,
                             "class": "Chrome_WidgetWin_1", "text": info["title"], "depth": 0},
                            {"name": "Active" if info["focused"] else "Background",
                             "type": "Status", "type_id": 50020,
                             "class": "",
                             "text": "{} | {}".format(
                                 "Focused" if info["focused"] else "Background",
                                 "Minimized" if info["minimized"] else "{}x{}".format(info["size"]["w"], info["size"]["h"])
                             ),
                             "depth": 1},
                        ],
                        "total": 2,
                        "window": info,
                    }
                    post_json("/cortex/live/update", {
                        "target": target,
                        "snapshot": snapshot,
                        "messages": [],
                    })

        except Exception:
            pass

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    # Write PID file
    pid_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "memory", "uia_bridge.pid")
    try:
        os.makedirs(os.path.dirname(pid_file), exist_ok=True)
        with open(pid_file, "w") as f:
            f.write(str(os.getpid()))
    except Exception:
        pass

    bridge_loop()
