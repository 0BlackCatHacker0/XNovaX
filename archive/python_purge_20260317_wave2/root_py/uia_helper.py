"""
NovaX UIA Helper — Desktop UI Automation via COM/UIA
Called by nova_uia_bridge_service.nova via nova_run()
Must run under pythonw.exe from ai_env for Session-1 access

Usage: python uia_helper.py <action> <json_args>

Actions:
  discover_windows   — Find Claude/GPT desktop windows
  capture_tree       — Capture UIA element tree for a window
  type_text          — Type text into focused element
  press_key          — Press key combination
  click_element      — Click element by name/automation ID
  focus_window       — Focus/bring to front a window
  get_clipboard      — Read clipboard contents
  set_clipboard      — Write text to clipboard

Returns JSON to stdout.
"""

import sys
import json
import time

# Try importing Windows automation modules
try:
    import ctypes
    import ctypes.wintypes
    HAS_CTYPES = True
except ImportError:
    HAS_CTYPES = False

try:
    import comtypes
    import comtypes.client
    HAS_COMTYPES = True
except ImportError:
    HAS_COMTYPES = False

try:
    import pyautogui
    pyautogui.FAILSAFE = False
    pyautogui.PAUSE = 0.1
    HAS_PYAUTOGUI = True
except ImportError:
    HAS_PYAUTOGUI = False

try:
    import pyperclip
    HAS_PYPERCLIP = True
except ImportError:
    HAS_PYPERCLIP = False

# UIA constants
UIA_WINDOW = 50032
UIA_TEXT = 50020
UIA_DOCUMENT = 50030
UIA_BUTTON = 50000
UIA_EDIT = 50004
UIA_LIST_ITEM = 50007

# Known app window classes
CLAUDE_CLASSES = ["Chrome_WidgetWin_1"]
CLAUDE_TITLES = ["Claude"]
GPT_CLASSES = ["Chrome_WidgetWin_1"]
GPT_TITLES = ["ChatGPT"]

def result_ok(data):
    print(json.dumps({"ok": True, "trit": 1, **data}))
    sys.exit(0)

def result_error(msg):
    print(json.dumps({"ok": False, "trit": -1, "error": str(msg)}))
    sys.exit(1)

def result_maybe(data):
    print(json.dumps({"ok": True, "trit": 0, **data}))
    sys.exit(0)

# ── Window Discovery ──
def discover_windows(args):
    """Find Claude and GPT desktop windows by title."""
    if not HAS_CTYPES:
        result_error("ctypes not available")

    user32 = ctypes.windll.user32
    windows = []

    def enum_callback(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value

        cls_buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, cls_buf, 256)
        cls_name = cls_buf.value

        # Check for Claude Desktop
        for ct in CLAUDE_TITLES:
            if ct.lower() in title.lower() and "browser" not in title.lower():
                windows.append({
                    "hwnd": hwnd,
                    "title": title,
                    "class": cls_name,
                    "app": "claude"
                })

        # Check for ChatGPT Desktop
        for gt in GPT_TITLES:
            if gt.lower() in title.lower() and "browser" not in title.lower():
                windows.append({
                    "hwnd": hwnd,
                    "title": title,
                    "class": cls_name,
                    "app": "gpt"
                })

        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
    user32.EnumWindows(WNDENUMPROC(enum_callback), 0)

    result_ok({"windows": windows, "count": len(windows)})

# ── UIA Tree Capture ──
def capture_tree(args):
    """Capture UIA element tree for a target window."""
    hwnd = args.get("hwnd", 0)
    max_depth = args.get("depth", 13)  # H13 default

    if not HAS_COMTYPES:
        result_error("comtypes not available - install with: pip install comtypes")

    try:
        uia = comtypes.client.CreateObject(
            "{ff48dba4-60ef-4201-aa87-54103eef594e}",
            interface=comtypes.gen.UIAutomationClient.IUIAutomation
        )
    except Exception as e:
        # Fallback: try to generate the typelib
        try:
            from comtypes.client import GetModule
            GetModule("UIAutomationCore.dll")
            uia = comtypes.client.CreateObject(
                "{ff48dba4-60ef-4201-aa87-54103eef594e}",
                interface=comtypes.gen.UIAutomationClient.IUIAutomation
            )
        except Exception as e2:
            result_error(f"UIA init failed: {e2}")

    if hwnd:
        root = uia.ElementFromHandle(hwnd)
    else:
        root = uia.GetRootElement()

    elements = []

    def walk(elem, depth):
        if depth > max_depth:
            return
        try:
            name = elem.CurrentName or ""
            ctrl_type = elem.CurrentControlType
            auto_id = elem.CurrentAutomationId or ""
            rect = elem.CurrentBoundingRectangle

            elements.append({
                "name": name[:200],
                "type": ctrl_type,
                "id": auto_id[:100],
                "depth": depth,
                "x": rect.left,
                "y": rect.top,
                "w": rect.right - rect.left,
                "h": rect.bottom - rect.top
            })

            # Walk children
            walker = uia.ControlViewWalker
            child = walker.GetFirstChildElement(elem)
            while child:
                walk(child, depth + 1)
                child = walker.GetNextSiblingElement(child)
        except Exception:
            pass

    walk(root, 0)
    result_ok({"elements": elements, "count": len(elements), "hwnd": hwnd})

# ── Type Text ──
def type_text(args):
    """Type text into the currently focused element."""
    text = args.get("text", "")
    if not text:
        result_error("missing text")
    if not HAS_PYAUTOGUI:
        result_error("pyautogui not available")

    pyautogui.typewrite(text, interval=0.02) if text.isascii() else pyautogui.write(text)
    result_ok({"typed": len(text)})

# ── Press Key ──
def press_key(args):
    """Press a key combination (e.g., 'enter', 'ctrl+a')."""
    key = args.get("key", "")
    if not key:
        result_error("missing key")
    if not HAS_PYAUTOGUI:
        result_error("pyautogui not available")

    if "+" in key:
        parts = key.split("+")
        pyautogui.hotkey(*parts)
    else:
        pyautogui.press(key)
    result_ok({"pressed": key})

# ── Click Element ──
def click_element(args):
    """Click at coordinates or find element by name and click."""
    x = args.get("x", 0)
    y = args.get("y", 0)
    if not HAS_PYAUTOGUI:
        result_error("pyautogui not available")

    if x and y:
        pyautogui.click(x, y)
        result_ok({"clicked": {"x": x, "y": y}})
    else:
        result_error("missing x/y coordinates")

# ── Focus Window ──
def focus_window(args):
    """Bring a window to the foreground."""
    hwnd = args.get("hwnd", 0)
    if not hwnd:
        result_error("missing hwnd")
    if not HAS_CTYPES:
        result_error("ctypes not available")

    user32 = ctypes.windll.user32
    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.3)
    result_ok({"focused": hwnd})

# ── Clipboard ──
def get_clipboard(args):
    if not HAS_PYPERCLIP:
        result_error("pyperclip not available")
    text = pyperclip.paste()
    result_ok({"text": text[:2187]})  # BLOCK_SIZE limit

def set_clipboard(args):
    text = args.get("text", "")
    if not HAS_PYPERCLIP:
        result_error("pyperclip not available")
    pyperclip.copy(text)
    result_ok({"copied": len(text)})

# ── Action Dispatch ──
ACTIONS = {
    "discover_windows": discover_windows,
    "capture_tree": capture_tree,
    "type_text": type_text,
    "press_key": press_key,
    "click_element": click_element,
    "focus_window": focus_window,
    "get_clipboard": get_clipboard,
    "set_clipboard": set_clipboard,
}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        result_error("usage: uia_helper.py <action> [json_args]")

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
