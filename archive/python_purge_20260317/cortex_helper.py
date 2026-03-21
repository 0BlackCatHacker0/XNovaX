"""
NovaX Cortex Helper — Desktop AI Bridge Automation
Called by nova_cortex_service.nova via nova_run()
Must run under pythonw.exe from ai_env for Session-1 access

Usage: python cortex_helper.py <action> <json_args>

Actions:
  discover        — Find Claude/GPT Desktop windows
  query_claude    — Type prompt into Claude, wait for response
  query_gpt       — Type prompt into GPT, wait for response
  get_response    — Read last AI response from clipboard
  new_chat        — Start new chat session
  select_model    — Select model from dropdown
  arrange         — Tile Claude+GPT side-by-side
  status          — Check which apps are available

Returns JSON to stdout.
"""

import sys
import json
import time

try:
    import ctypes
    import ctypes.wintypes
    HAS_CTYPES = True
except ImportError:
    HAS_CTYPES = False

try:
    import pyautogui
    pyautogui.FAILSAFE = False
    pyautogui.PAUSE = 0.15
    HAS_PYAUTOGUI = True
except ImportError:
    HAS_PYAUTOGUI = False

try:
    import pyperclip
    HAS_PYPERCLIP = True
except ImportError:
    HAS_PYPERCLIP = False

# 3-5-7-13 constants
H3, H5, H7, H13 = 3, 5, 7, 13
POLL_INTERVAL = 1.0
STABLE_POLLS = H3  # 3 stable polls = response complete
MAX_WAIT = H13 * H5  # 65 seconds max wait for response

def result_ok(data):
    print(json.dumps({"ok": True, "trit": 1, **data}))
    sys.exit(0)

def result_error(msg):
    print(json.dumps({"ok": False, "trit": -1, "error": str(msg)}))
    sys.exit(1)

def result_maybe(data):
    print(json.dumps({"ok": True, "trit": 0, **data}))
    sys.exit(0)

def find_window(title_fragment):
    """Find window HWND by title fragment."""
    if not HAS_CTYPES:
        return 0

    user32 = ctypes.windll.user32
    result = [0]

    def callback(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        if title_fragment.lower() in buf.value.lower():
            if "browser" not in buf.value.lower():
                result[0] = hwnd
                return False  # Stop enumeration
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
    user32.EnumWindows(WNDENUMPROC(callback), 0)
    return result[0]

def focus_hwnd(hwnd):
    """Bring window to foreground."""
    if not hwnd or not HAS_CTYPES:
        return False
    user32 = ctypes.windll.user32
    user32.ShowWindow(hwnd, 9)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.5)
    return True

# ── Discover ──
def discover(args):
    claude_hwnd = find_window("Claude")
    gpt_hwnd = find_window("ChatGPT")
    result_ok({
        "claude": {"hwnd": claude_hwnd, "found": claude_hwnd != 0},
        "gpt": {"hwnd": gpt_hwnd, "found": gpt_hwnd != 0}
    })

# ── Query Claude Desktop ──
def query_claude(args):
    prompt = args.get("prompt", "")
    if not prompt:
        result_error("missing prompt")
    if not HAS_PYAUTOGUI:
        result_error("pyautogui not available")

    hwnd = find_window("Claude")
    if not hwnd:
        result_error("Claude Desktop not found")

    focus_hwnd(hwnd)
    time.sleep(0.3)

    # Clear any existing text and type prompt
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.1)
    pyautogui.write(prompt) if prompt.isascii() else pyautogui.typewrite(prompt, interval=0.02)
    time.sleep(0.2)
    pyautogui.press("enter")

    # Wait for response — poll clipboard stability
    time.sleep(2.0)  # Initial wait for generation to start
    last_clip = ""
    stable_count = 0
    waited = 0

    while waited < MAX_WAIT:
        time.sleep(POLL_INTERVAL)
        waited += POLL_INTERVAL

        # Try to copy response
        pyautogui.hotkey("ctrl", "shift", "c")  # Copy last response
        time.sleep(0.3)
        if HAS_PYPERCLIP:
            clip = pyperclip.paste()
            if clip == last_clip and len(clip) > 10:
                stable_count += 1
            else:
                stable_count = 0
                last_clip = clip

            if stable_count >= STABLE_POLLS:
                result_ok({"response": clip[:2187], "waited_s": waited, "source": "claude"})

    # Timeout — return whatever we have
    if last_clip:
        result_maybe({"response": last_clip[:2187], "waited_s": waited, "source": "claude", "partial": True})
    else:
        result_error("timeout waiting for Claude response")

# ── Query GPT Desktop ──
def query_gpt(args):
    prompt = args.get("prompt", "")
    if not prompt:
        result_error("missing prompt")
    if not HAS_PYAUTOGUI:
        result_error("pyautogui not available")

    hwnd = find_window("ChatGPT")
    if not hwnd:
        result_error("ChatGPT Desktop not found")

    focus_hwnd(hwnd)
    time.sleep(0.3)

    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.1)
    pyautogui.write(prompt) if prompt.isascii() else pyautogui.typewrite(prompt, interval=0.02)
    time.sleep(0.2)
    pyautogui.press("enter")

    time.sleep(2.0)
    last_clip = ""
    stable_count = 0
    waited = 0

    while waited < MAX_WAIT:
        time.sleep(POLL_INTERVAL)
        waited += POLL_INTERVAL
        pyautogui.hotkey("ctrl", "shift", "c")
        time.sleep(0.3)
        if HAS_PYPERCLIP:
            clip = pyperclip.paste()
            if clip == last_clip and len(clip) > 10:
                stable_count += 1
            else:
                stable_count = 0
                last_clip = clip
            if stable_count >= STABLE_POLLS:
                result_ok({"response": clip[:2187], "waited_s": waited, "source": "gpt"})

    if last_clip:
        result_maybe({"response": last_clip[:2187], "waited_s": waited, "source": "gpt", "partial": True})
    else:
        result_error("timeout waiting for GPT response")

# ── Get Last Response ──
def get_response(args):
    target = args.get("target", "claude")
    title = "Claude" if target == "claude" else "ChatGPT"
    hwnd = find_window(title)
    if not hwnd:
        result_error(f"{title} Desktop not found")

    focus_hwnd(hwnd)
    time.sleep(0.2)
    pyautogui.hotkey("ctrl", "shift", "c")
    time.sleep(0.5)
    if HAS_PYPERCLIP:
        text = pyperclip.paste()
        result_ok({"response": text[:2187], "source": target})
    else:
        result_error("pyperclip not available")

# ── New Chat ──
def new_chat(args):
    target = args.get("target", "claude")
    title = "Claude" if target == "claude" else "ChatGPT"
    hwnd = find_window(title)
    if not hwnd:
        result_error(f"{title} Desktop not found")

    focus_hwnd(hwnd)
    time.sleep(0.2)
    pyautogui.hotkey("ctrl", "n")  # Standard new chat shortcut
    time.sleep(0.5)
    result_ok({"new_chat": True, "target": target})

# ── Select Model ──
def select_model(args):
    model = args.get("model", "")
    target = args.get("target", "claude")
    if not model:
        result_error("missing model name")

    title = "Claude" if target == "claude" else "ChatGPT"
    hwnd = find_window(title)
    if not hwnd:
        result_error(f"{title} Desktop not found")

    focus_hwnd(hwnd)
    # Model selection varies by app — this is a best-effort approach
    result_maybe({"message": "model selection requires app-specific UI navigation", "target": target, "model": model})

# ── Arrange Windows ──
def arrange(args):
    if not HAS_CTYPES:
        result_error("ctypes not available")

    user32 = ctypes.windll.user32
    screen_w = user32.GetSystemMetrics(0)
    screen_h = user32.GetSystemMetrics(1)
    half_w = screen_w // 2

    claude_hwnd = find_window("Claude")
    gpt_hwnd = find_window("ChatGPT")

    arranged = []
    if claude_hwnd:
        user32.ShowWindow(claude_hwnd, 9)
        user32.MoveWindow(claude_hwnd, 0, 0, half_w, screen_h, True)
        arranged.append("claude")
    if gpt_hwnd:
        user32.ShowWindow(gpt_hwnd, 9)
        user32.MoveWindow(gpt_hwnd, half_w, 0, half_w, screen_h, True)
        arranged.append("gpt")

    result_ok({"arranged": arranged, "screen": {"w": screen_w, "h": screen_h}})

# ── Status ──
def status(args):
    claude_hwnd = find_window("Claude")
    gpt_hwnd = find_window("ChatGPT")
    result_ok({
        "claude_available": claude_hwnd != 0,
        "gpt_available": gpt_hwnd != 0,
        "pyautogui": HAS_PYAUTOGUI,
        "pyperclip": HAS_PYPERCLIP,
        "ctypes": HAS_CTYPES
    })

# ── Action Dispatch ──
ACTIONS = {
    "discover": discover,
    "query_claude": query_claude,
    "query_gpt": query_gpt,
    "get_response": get_response,
    "new_chat": new_chat,
    "select_model": select_model,
    "arrange": arrange,
    "status": status,
}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        result_error("usage: cortex_helper.py <action> [json_args]")

    action = sys.argv[1]
    args = {}
    if len(sys.argv) > 2:
        try:
            args = json.loads(sys.argv[2])
        except json.JSONDecodeError:
            args = {"text": sys.argv[2]}

    if action not in ACTIONS:
        result_error(f"unknown action: {action}. Available: {list(ACTIONS.keys())}")

    try:
        ACTIONS[action](args)
    except Exception as e:
        result_error(f"{action} failed: {e}")
