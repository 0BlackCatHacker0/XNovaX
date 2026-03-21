# drivers.py — Action Bus: routes driver commands to handlers
# Implements execute() for orchestrator, dispatch() for legacy,
# and execute_plan() for multi-step plan execution.
# Real drivers: terminal, file, system — each executes actual commands.

import os
import json
import subprocess
import shutil
import platform
from collections import namedtuple, deque

# ── Result type ──
ActionResult = namedtuple("ActionResult", ["ok", "output", "error"], defaults=[True, "", ""])

# ── _CREATE_NO_WINDOW flag for subprocess ──
_CREATE_NO_WINDOW = 0x08000000 if platform.system() == "Windows" else 0

class ActionBus:
    """Action Bus — routes execute(driver, action, params) to registered handlers."""

    def __init__(self):
        self.drivers = {}
        self.log = deque(maxlen=1000)
        # Register built-in drivers
        self.register("terminal", TerminalDriver())
        self.register("file", FileDriver())
        self.register("system", SystemDriver())

    def register(self, name, handler):
        self.drivers[name] = handler

    def execute(self, driver_name, action, params=None):
        """Execute an action on a named driver. Returns ActionResult."""
        params = params or {}
        drv = self.drivers.get(driver_name)
        if not drv:
            return ActionResult(ok=False, output="", error=f"No driver: {driver_name}")
        handler = getattr(drv, action, None)
        if not handler:
            return ActionResult(ok=False, output="", error=f"No action: {driver_name}.{action}")
        try:
            result = handler(**params)
            self.log.append({"driver": driver_name, "action": action, "ok": True})
            if isinstance(result, ActionResult):
                return result
            if isinstance(result, dict):
                return ActionResult(
                    ok=result.get("ok", True),
                    output=result.get("output", result.get("data", "")),
                    error=result.get("error", "")
                )
            return ActionResult(ok=True, output=str(result), error="")
        except Exception as e:
            self.log.append({"driver": driver_name, "action": action, "ok": False, "error": str(e)})
            return ActionResult(ok=False, output="", error=str(e))

    def execute_plan(self, actions):
        """Execute a list of actions sequentially. Returns list of results."""
        results = []
        for act in actions:
            driver = act.get("driver", "terminal")
            action = act.get("action", "run_command")
            params = act.get("params", {})
            r = self.execute(driver, action, params)
            results.append({
                "driver": driver,
                "action": action,
                "ok": r.ok,
                "output": r.output,
                "error": r.error,
            })
        return results

    def dispatch(self, action, **kwargs):
        """Legacy dispatch interface."""
        if action in self.drivers:
            return self.drivers[action](**kwargs)
        return {"status": "no_driver", "action": action}

    def list_drivers(self):
        return list(self.drivers.keys())


class TerminalDriver:
    """Executes shell commands safely."""

    def run_command(self, cmd="", timeout=30, **kwargs):
        if not cmd:
            return ActionResult(ok=False, output="", error="No command")
        try:
            si = None
            cf = 0
            if platform.system() == "Windows":
                si = subprocess.STARTUPINFO()
                si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                si.wShowWindow = 0
                cf = _CREATE_NO_WINDOW
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                timeout=timeout, creationflags=cf, startupinfo=si,
                cwd=r"C:\NovaX"
            )
            output = result.stdout.strip()
            error = result.stderr.strip()
            return ActionResult(
                ok=(result.returncode == 0),
                output=output or error,
                error=error if result.returncode != 0 else ""
            )
        except subprocess.TimeoutExpired:
            return ActionResult(ok=False, output="", error=f"Command timed out after {timeout}s")
        except Exception as e:
            return ActionResult(ok=False, output="", error=str(e))

    def run_python(self, code="", timeout=30, **kwargs):
        if not code:
            return ActionResult(ok=False, output="", error="No code")
        try:
            si = None
            cf = 0
            if platform.system() == "Windows":
                si = subprocess.STARTUPINFO()
                si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                si.wShowWindow = 0
                cf = _CREATE_NO_WINDOW
            result = subprocess.run(
                ["C:\\Python314\\python.exe", "-c", code],
                capture_output=True, text=True, timeout=timeout,
                creationflags=cf, startupinfo=si,
                cwd=r"C:\NovaX"
            )
            output = result.stdout.strip()
            error = result.stderr.strip()
            return ActionResult(
                ok=(result.returncode == 0),
                output=output or error,
                error=error if result.returncode != 0 else ""
            )
        except Exception as e:
            return ActionResult(ok=False, output="", error=str(e))


class FileDriver:
    """File system operations."""

    _ALLOWED_ROOTS = [r"C:\NovaX" + os.sep, r"C:\Users\Jupit" + os.sep]

    def _safe(self, path):
        path = os.path.realpath(os.path.abspath(path))
        # Append sep to path check to prevent C:\Users\Jupiter matching C:\Users\Jupit
        return any(path.startswith(r) or path.rstrip(os.sep) + os.sep == r for r in self._ALLOWED_ROOTS)

    def list_dir(self, path=r"C:\NovaX", **kwargs):
        if not self._safe(path):
            return ActionResult(ok=False, output="", error="Path outside allowed roots")
        try:
            entries = []
            for name in os.listdir(path):
                full = os.path.join(path, name)
                is_dir = os.path.isdir(full)
                size = 0
                try:
                    size = os.path.getsize(full) if not is_dir else 0
                except Exception:
                    pass
                entries.append({
                    "name": name,
                    "path": full,
                    "type": "dir" if is_dir else "file",
                    "is_dir": is_dir,
                    "size": size,
                })
            return ActionResult(ok=True, output=json.dumps(entries), error="")
        except Exception as e:
            return ActionResult(ok=False, output="", error=str(e))

    def read_file(self, path="", **kwargs):
        if not path or not self._safe(path):
            return ActionResult(ok=False, output="", error="Invalid path")
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            return ActionResult(ok=True, output=content, error="")
        except Exception as e:
            return ActionResult(ok=False, output="", error=str(e))

    def write_file(self, path="", content="", append=False, **kwargs):
        if not path or not self._safe(path):
            return ActionResult(ok=False, output="", error="Invalid path")
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            mode = "a" if append else "w"
            with open(path, mode, encoding="utf-8") as f:
                f.write(content)
            return ActionResult(ok=True, output=f"Written: {path}", error="")
        except Exception as e:
            return ActionResult(ok=False, output="", error=str(e))

    def delete_file(self, path="", **kwargs):
        if not path or not self._safe(path):
            return ActionResult(ok=False, output="", error="Invalid path")
        try:
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
            return ActionResult(ok=True, output=f"Deleted: {path}", error="")
        except Exception as e:
            return ActionResult(ok=False, output="", error=str(e))


class SystemDriver:
    """System information and operations."""

    def get_system_info(self, **kwargs):
        import psutil
        try:
            info = {
                "cpu_percent": psutil.cpu_percent(interval=0.5),
                "memory": dict(psutil.virtual_memory()._asdict()),
                "disk": dict(psutil.disk_usage("C:\\")._asdict()),
                "platform": platform.platform(),
                "python": platform.python_version(),
            }
            return ActionResult(ok=True, output=json.dumps(info), error="")
        except Exception as e:
            return ActionResult(ok=False, output="", error=str(e))


# ── Singleton ──
bus = ActionBus()
