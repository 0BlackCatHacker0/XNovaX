"""NovaX No-Window Wrapper
Hides the console window, then runs the target script or module.
Usage:
  python nowindow.py <script.py> [args...]
  python nowindow.py -m <module> [args...]

Prevents blue PowerShell/console windows from appearing on Windows.
Stdout/stderr still flow to the parent process for log capture.
"""
import sys, os

if len(sys.argv) < 2:
    print("Usage: python nowindow.py <script.py> [args...]")
    sys.exit(1)

# Hide the console window immediately
try:
    import ctypes
    hwnd = ctypes.windll.kernel32.GetConsoleWindow()
    if hwnd:
        ctypes.windll.user32.ShowWindow(hwnd, 0)  # SW_HIDE = 0
except Exception:
    pass

# Handle -m module invocation
if sys.argv[1] == "-m":
    # python nowindow.py -m http.server 8888 --directory ...
    sys.argv = sys.argv[1:]  # remove "nowindow.py", keep "-m module args..."
    import runpy
    module = sys.argv[1]
    sys.argv = sys.argv[1:]  # now argv[0] = module name
    runpy.run_module(module, run_name="__main__", alter_sys=True)
else:
    # python nowindow.py script.py [args...]
    target = sys.argv[1]
    sys.argv = sys.argv[1:]  # shift so target sees correct argv

    # Add target's directory to path
    target_dir = os.path.dirname(os.path.abspath(target))
    if target_dir not in sys.path:
        sys.path.insert(0, target_dir)

    with open(target, encoding="utf-8") as f:
        code = f.read()

    globals_dict = {"__name__": "__main__", "__file__": os.path.abspath(target)}
    exec(compile(code, target, "exec"), globals_dict)
